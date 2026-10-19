#!/usr/bin/env python3
"""Descriptive whole-class tail, cohort association and coassignment diagnostics."""
from pathlib import Path
import argparse, json, itertools
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_mutual_info_score

HERE=Path(__file__).resolve().parent
SELECTED=['reverse_selected','reverse_selected_global','reverse_selected_difficulty','reverse_selected_geometry','reverse_selected_swap']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',default=str(HERE/'results'))
    ap.add_argument('--features',default=str(HERE.parent/'forward/fold_features.csv.gz'))
    args=ap.parse_args();p=Path(args.results)
    c=pd.read_csv(p/'all_candidate_classes.csv.gz').fillna({'class_id':'unknown'})
    c=c[c.method_id.isin(SELECTED)]
    f=pd.read_csv(args.features);f=f[f.metric.eq('B8L2')]
    if 'inner_group' in f:f=f[f.inner_group.isna()]
    s=c.merge(f[['fold_id','worker_id','person_origin']],on=['fold_id','worker_id'],how='left',validate='many_to_one')
    overview=[]
    for (fold,method,dom),g in s.groupby(['fold_id','method_id','domain']):
        z=g[g.class_id.ne('unknown')].copy();sizes=z.groupby('class_id').size()
        byorigin=z.dropna(subset=['person_origin'])
        counts=pd.crosstab(byorigin.class_id,byorigin.person_origin)
        overview.append({'fold_id':fold,'method_id':method,'domain':dom,'n_workers':len(g),'known_workers':len(z),
                         'unknown_workers':g.class_id.eq('unknown').sum(),'n_classes':len(sizes),
                         'singleton_classes':sizes.eq(1).sum(),'doubleton_classes':sizes.eq(2).sum(),
                         'workers_in_singletons':sizes[sizes.eq(1)].sum(),'workers_with_at_least_one_classmate':sizes[sizes.ge(2)].sum(),
                         'largest_class_size':sizes.max() if len(sizes) else 0,
                         'class_origin_adjusted_mutual_information':adjusted_mutual_info_score(byorigin.class_id,byorigin.person_origin) if len(byorigin)>1 else np.nan,
                         'class_origin_purity':counts.max(axis=1).sum()/counts.to_numpy().sum() if counts.size else np.nan,
                         'majority_origin_baseline':byorigin.person_origin.value_counts(normalize=True).max() if len(byorigin) else np.nan})
    pd.DataFrame(overview).to_csv(p/'selected_partition_overview.csv',index=False)
    stability=pd.read_csv(p/'coassignment_stability.csv.gz')
    sums=[]
    for (method,dom),g in stability.groupby(['method_id','domain']):
        z=g[g.n_supported_folds.ge(16)]
        sums.append({'method_id':method,'domain':dom,'all_person_pairs':len(g),'pairs_known_at_least16of22_folds':len(z),
                     'pair_known_mean_folds':g.n_supported_folds.mean(),
                     'mean_distinct_fold_disagreement':z.distinct_fold_disagreement.mean(),
                     'pairs_consistently_same_p_ge_point9':z.coassignment_rate.ge(.9).sum(),
                     'pairs_consistently_different_p_le_point1':z.coassignment_rate.le(.1).sum(),
                     'pairs_boundary_point1_to_point9':(z.coassignment_rate.gt(.1)&z.coassignment_rate.lt(.9)).sum()})
    pd.DataFrame(sums).to_csv(p/'coassignment_stability_summary.csv',index=False)
    # Compare known classmate sets, not arbitrary C01/C02 identifiers. Empty singleton
    # sets do not count as demonstrated interchangeability.
    ws=[]
    for (method,dom),g in c.groupby(['method_id','domain']):
        full=g[g.fold_id.eq('FULL')].set_index('worker_id').class_id.to_dict()
        folds={fold:gg.set_index('worker_id').class_id.to_dict() for fold,gg in g[g.fold_id.ne('FULL')].groupby('fold_id')}
        for w,cl in full.items():
            fm={u for u,cc in full.items() if cc==cl and u!=w and cc!='unknown'}
            vals=[];nfunknown=0;empty=0
            for fold,labels in folds.items():
                if cl=='unknown' or labels.get(w,'unknown')=='unknown':nfunknown+=1;continue
                common={u for u in full if u!=w and full[u]!='unknown' and labels.get(u,'unknown')!='unknown'}
                a=fm&common;b={u for u in common if labels[u]==labels[w]}
                union=a|b
                if not union:empty+=1;continue
                vals.append(len(a&b)/len(union))
            ws.append({'method_id':method,'domain':dom,'worker_id':w,'full_class':cl,'full_classmates':len(fm),
                       'unknown_folds':nfunknown,'singleton_empty_comparisons':empty,'nonempty_comparisons':len(vals),
                       'mean_classmate_jaccard':np.mean(vals) if vals else np.nan,'minimum_classmate_jaccard':min(vals) if vals else np.nan})
    pd.DataFrame(ws).to_csv(p/'worker_classmate_stability.csv',index=False)
    # Pair tails are evaluated over all pairs in a whole class. The weakest five are
    # an index for review, not the sole source of a class's average or pass rate.
    worst=[];wedges=[]
    for fp in sorted((p/'folds').glob('*/pair_relations.csv.gz')):
        fold=fp.parent.name;rel=pd.read_csv(fp)
        cg=c[c.fold_id.eq(fold)]
        for (method,dom),g in cg.groupby(['method_id','domain']):
            rr=rel[rel.domain.eq(dom)]
            labels=g.set_index('worker_id').class_id.to_dict()
            for cl,gg in g[g.class_id.ne('unknown')].groupby('class_id'):
                mem=set(gg.worker_id);r=rr[rr.worker_a.isin(mem)&rr.worker_b.isin(mem)]
                for metric,support in [('same9_observed','geometry_pair_supported'),('swap_stability_observed','swap_pair_supported')]:
                    valid=r[r[support].eq(True)].sort_values(metric)
                    for rank,(_,v) in enumerate(valid.head(5).iterrows(),1):
                        worst.append({'fold_id':fold,'method_id':method,'domain':dom,'class_id':cl,'metric':metric,'rank':rank,
                                      'worker_a':v.worker_a,'worker_b':v.worker_b,'value':v[metric],
                                      'n_images':v.n_images,'n_buildings':v.n_buildings,'n_swap_images':v.n_swap_images,'n_swap_buildings':v.n_swap_buildings,
                                      'total_supported_within_pairs':len(valid)})
        # This graph diagnostic is independent of selected partition, counted once.
        for dom,rr in rel.groupby('domain'):
            known=rr[rr.geometry_pair_supported.eq(True)]
            ids=sorted(set(rr.worker_a)|set(rr.worker_b));lookup={w:i for i,w in enumerate(ids)}
            values=np.full((len(ids),len(ids)),np.nan);support=np.zeros_like(values,dtype=bool)
            for _,r in known.iterrows():
                i,j=lookup[r.worker_a],lookup[r.worker_b];values[i,j]=values[j,i]=r.same9_observed;support[i,j]=support[j,i]=True
            close=values>=.8;far=values<=.2;nclose=nsknown=nviolate=nunknown=0
            for middle in range(len(ids)):
                nbr=np.flatnonzero(close[middle])
                for a,b in itertools.combinations(nbr,2):
                    nclose+=1
                    if support[a,b]:nsknown+=1;nviolate+=bool(far[a,b])
                    else:nunknown+=1
            wedges.append({'fold_id':fold,'domain':dom,'supported_person_pairs':len(known),'close_probability_cutoff':.8,'far_probability_cutoff':.2,
                           'close_two_edge_wedges':nclose,'wedge_endpair_supported':nsknown,'unknown_endpair_wedges':nunknown,
                           'close_AB_close_BC_far_AC':nviolate})
    pd.DataFrame(worst).to_csv(p/'selected_class_worst_training_pairs.csv.gz',index=False)
    pd.DataFrame(wedges).to_csv(p/'nontransitivity_diagnostic.csv',index=False)
    (p/'PARTITION_DIAGNOSTICS_RECEIPT.json').write_text(json.dumps({'selected_methods':SELECTED,'coassignment_support_summary_min_folds':16,
        'class_id_comparison':'only shared-class relation / classmate set, numeric label IDs never compared across folds',
        'fold_disagreement_uncertainty':'descriptive stability; overlapping 22 folds are not 22 independent replications',
        'bad_tails':'all-pair class summaries retained; worst-five table is a review index only',
        'origin':'descriptive confounding diagnostic, not a class input'},indent=2)+'\n')

if __name__=='__main__':main()
