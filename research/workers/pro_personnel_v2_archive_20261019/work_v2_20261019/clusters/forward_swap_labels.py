"""Nested heldout personnel labels and actual fixed-background swap changes."""
from __future__ import annotations
import argparse,gzip,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_fusion_clusters import attach_flags,bs

HERE=Path(__file__).resolve().parent;FUSION=HERE.parent/'fusion'
METRICS=['abs_B8L2_change','abs_D10_change','floor_jaccard_difference','joint_geometric_stable',
         'node_changed','any_failure','joint_with_shared_connections','joint_with_shared_connections_and_retention']

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--input',type=Path,default=FUSION/'INITIAL_replacements.csv.gz');a=ap.parse_args()
    out=HERE/'forward_swaps';out.mkdir(exist_ok=True)
    d=pd.read_csv(a.input);d=d[d.layer.eq('ordinary_manual')].copy();attempt_n=len(d)
    d['event_key']=[p+'|'+'|'.join(sorted((x,y))) for p,x,y in zip(d.pool_id,d.team_id_a,d.team_id_b)]
    d=d.drop_duplicates('event_key').reset_index(drop=True);d=attach_flags(d)
    lab=pd.read_csv(HERE/'assignments.csv');lab=lab[lab.method.eq('affinity') & lab.threshold_deg.eq(9)]
    count={(r.pool_id,r.worker_id):r.pair_count for r in lab.itertuples()}
    d['pair_count_a']=[count[p,w] for p,w in zip(d.pool_id,d.entrant_a)];d['pair_count_b']=[count[p,w] for p,w in zip(d.pool_id,d.entrant_b)]
    d['equal_entrant_count']=d.pair_count_a.eq(d.pair_count_b)
    fold=pd.read_csv(HERE.parent/'profiles/fold_profiles.csv').set_index(['heldout_building','worker_id'])
    flabels=['Q2','QT','difficulty_type','fine_dtype_merged']
    for suffix,entrant in [('a','entrant_a'),('b','entrant_b')]:
        rows=fold.reindex(pd.MultiIndex.from_arrays([d.building_id,d[entrant]],names=fold.index.names)).reset_index(drop=True)
        assert len(rows)==len(d)
        for c in ['Q_supported','T_source_supported','difficulty_supported_easy','difficulty_supported_medium','difficulty_supported_hard']:
            d[c+'_'+suffix]=rows[c].fillna(False).to_numpy(bool)
        for metric in ['B8L2','D10']:
            for label in flabels:d[label+'_'+metric+'_'+suffix]=rows[label+'_'+metric].to_numpy()
    d['Q_known']=d.Q_supported_a & d.Q_supported_b
    d['QT_known']=d.Q_known & d.T_source_supported_a & d.T_source_supported_b
    d['all_difficulty_known']=True
    for z in ['easy','medium','hard']:d['all_difficulty_known'] &= d['difficulty_supported_'+z+'_a'] & d['difficulty_supported_'+z+'_b']
    d['common_known']=d.QT_known & d.all_difficulty_known
    # One event record stores labels and raw outcomes. Unknown labels remain in this ledger.
    cols=['event_key','pool_id','image_id','image_code','building_id','difficulty','k','background_id','entrant_a','entrant_b',
          'equal_entrant_count','Q_known','QT_known','all_difficulty_known','common_known']+METRICS
    cols += [x for x in d if any(x.startswith(f+'_') for f in flabels)]
    d[cols].to_csv(out/'labeled_events.csv.gz',index=False)
    coverage=[];strata=[]
    base=['pool_id','image_id','image_code','building_id','difficulty','k','background_id','pair_count_a','parent_class']
    families=[('Q2_same_vs_different','Q2',None,'Q_known'),('QT_within_Q2','QT','Q2','QT_known'),
              ('difficulty_within_QT','difficulty_type','QT','common_known'),
              ('merged_difficulty_within_QT','fine_dtype_merged','QT','common_known')]
    for metric in ['B8L2','D10']:
        for family,child,parent,support in families:
            ca,cb=child+'_'+metric+'_a',child+'_'+metric+'_b'
            classified=d[support] & ~d[ca].fillna('unknown').str.contains('unknown') & ~d[cb].fillna('unknown').str.contains('unknown')
            parent_same=pd.Series(True,index=d.index)
            if parent:
                pa,pb=parent+'_'+metric+'_a',parent+'_'+metric+'_b'
                classified &= ~d[pa].fillna('unknown').str.contains('unknown') & ~d[pb].fillna('unknown').str.contains('unknown')
                parent_same=d[pa].eq(d[pb])
            for panel in ['dimension_available','common_Q_T_all_three_difficulties']:
                eligible=classified & parent_same & d.equal_entrant_count
                if panel.startswith('common'):eligible &= d.common_known
                h=d.loc[eligible].copy();h['parent_class']=h[pa] if parent else 'all_supported_Q'
                h['same_child']=h[ca].eq(h[cb]);h['relation']=np.where(h.same_child,'same','different')
                coverage.append(dict(label_metric=metric,family=family,panel=panel,all_attempts=attempt_n,
                    distinct_events=len(d),label_unsupported_or_unknown=int((~classified).sum()),parent_mismatch=int((classified & ~parent_same).sum()),
                    different_entrant_count=int((classified & parent_same & ~d.equal_entrant_count).sum()),
                    eligible_events=len(h),same_child=int(h.same_child.sum()),different_child=int((~h.same_child).sum()),
                    images=h.image_id.nunique(),buildings=h.building_id.nunique(),parents=h.parent_class.nunique()))
                if not len(h):continue
                grouped=h.groupby(base+['relation'],dropna=False)
                means=grouped[METRICS].mean();counts=grouped[METRICS].count();ns=grouped.size()
                for outcome in METRICS:
                    m=means[outcome].unstack('relation');n=counts[outcome].unstack('relation');attempts=ns.unstack('relation')
                    if 'same' not in m or 'different' not in m:continue
                    both=attempts['same'].notna() & attempts['different'].notna()
                    x=m[both].reset_index()[base];x['same_mean']=m.loc[both,'same'].to_numpy();x['different_mean']=m.loc[both,'different'].to_numpy()
                    x['difference']=x.different_mean-x.same_mean
                    x.loc[x.difference.isna(),['same_mean','different_mean']]=np.nan
                    x['same_observed']=n.loc[both,'same'].to_numpy();x['different_observed']=n.loc[both,'different'].to_numpy()
                    x['same_attempts']=attempts.loc[both,'same'].to_numpy();x['different_attempts']=attempts.loc[both,'different'].to_numpy()
                    x['label_metric']=metric;x['family']=family;x['panel']=panel;x['outcome']=outcome;strata.append(x)
    s=pd.concat(strata,ignore_index=True);s.to_csv(out/'matched_strata.csv',index=False);pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False)
    keys=['label_metric','family','panel','outcome','k','pool_id','image_id','image_code','building_id','difficulty']
    im=s.groupby(keys,dropna=False).agg(difference=('difference','mean'),same_mean=('same_mean','mean'),different_mean=('different_mean','mean'),
        same_attempts=('same_attempts','sum'),different_attempts=('different_attempts','sum'),same_observed=('same_observed','sum'),different_observed=('different_observed','sum'),
        matched_strata=('difference','size')).reset_index();im.to_csv(out/'image_effects.csv',index=False)
    result=[];bld=[]
    expanded=[im.assign(difficulty_panel='all')]
    for name,value in [('easy','简单'),('medium','中等'),('hard','困难')]:expanded.append(im[im.difficulty.eq(value)].assign(difficulty_panel=name))
    im_expanded=pd.concat(expanded,ignore_index=True)
    for key,g in im_expanded.groupby(['label_metric','family','panel','outcome','k','difficulty_panel'],dropna=False):
        b=g.groupby('building_id')[['difference','same_mean','different_mean']].mean();z=bs(b.difference)
        result.append(dict(zip(['label_metric','family','panel','outcome','k','difficulty_panel'],key),images=g.image_id.nunique(),measurable_images=g[g.difference.notna()].image_id.nunique(),
            buildings=z['n'],same_mean=b.same_mean.mean(),different_mean=b.different_mean.mean(),difference=z['mean'],low=z['low'],high=z['high'],
            positive_buildings=int(b.difference.gt(0).sum()),negative_buildings=int(b.difference.lt(0).sum()),
            same_attempts=int(g.same_attempts.sum()),different_attempts=int(g.different_attempts.sum())))
        for name,r in b.iterrows():bld.append(dict(zip(['label_metric','family','panel','outcome','k','difficulty_panel'],key),building_id=name,**r.to_dict()))
    pd.DataFrame(result).to_csv(out/'summary.csv',index=False);pd.DataFrame(bld).to_csv(out/'building_effects.csv',index=False)
    receipt=dict(ordinary_images=d.pool_id.nunique(),buildings=d.building_id.nunique(),original_attempts=attempt_n,distinct_events=len(d),
        equal_count_events=int(d.equal_entrant_count.sum()),same_frozen_teams_two_label_metrics=True,unknown_never_classified_low=True,
        source=str(a.input),source_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),
        registration_sha256=hashlib.sha256((HERE/'FORWARD_SWAP_REGISTRATION.json').read_bytes()).hexdigest(),
        labels_sha256=hashlib.sha256((HERE.parent/'profiles/fold_profiles.csv').read_bytes()).hexdigest())
    (out/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
