"""Join frozen local clusters to actual teams/swaps; all failures stay visible.

This consumes fusion/compare_fusions.py outputs. No fusion is rerun or selected
based on outcomes, and target-picture clusters are always labelled retrospective.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,itertools,json,math
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;FUSION=HERE.parent/'fusion';SEED=2026101933

METRICS=['abs_B8L2_change','abs_D10_change','floor_jaccard_difference','structure_bound_cyclic_deg',
         'node_changed','any_failure','joint_geometric_stable','joint_with_shared_connections',
         'joint_with_shared_connections_and_retention','edge_relation_jaccard_difference',
         'selected_shared_observation_difference','mean_height_prism_pair_iou']

def write_gz(path,frames):
    frames=[x for x in frames if len(x)]
    if not frames:return 0
    temporary=path.with_suffix(path.suffix+'.tmp')
    with gzip.open(temporary,'wt',encoding='utf-8',newline='') as f:
        for i,frame in enumerate(frames):frame.to_csv(f,index=False,header=i==0)
    # Read the entire gzip stream before publishing so an interrupted or
    # concurrent early analysis can never masquerade as a usable ledger.
    with gzip.open(temporary,'rb') as f:
        while f.read(1024*1024):pass
    temporary.replace(path)
    return sum(len(f) for f in frames)

def bs(d):
    d=np.asarray(d,float);d=d[np.isfinite(d)]
    if not len(d):return dict(mean=np.nan,low=np.nan,high=np.nan,n=0)
    rng=np.random.default_rng(SEED);m=rng.choice(d,(3000,len(d)),replace=True).mean(1)
    return dict(mean=float(d.mean()),low=float(np.quantile(m,.025)),high=float(np.quantile(m,.975)),n=len(d))

def attach_flags(d):
    d=d.copy();d['node_changed']=np.where(d.node_count_difference.notna(),d.node_count_difference.ne(0),np.nan)
    d['any_failure']=~(d.complete_a & d.complete_b)
    if 'joint_geometric_stable' not in d:d['joint_geometric_stable']=d.joint_stable_main
    if 'joint_with_shared_connections' not in d:d['joint_with_shared_connections']=d.joint_geometric_stable & d.edge_relation_jaccard_difference.eq(0)
    if 'joint_with_shared_connections_and_retention' not in d:d['joint_with_shared_connections_and_retention']=d.joint_with_shared_connections & d.selected_shared_observation_difference.eq(0)
    d['mean_pair_B8L2']=(d.B8L2_a+d.B8L2_b)/2
    d['building_id']=d.building;d['image_code']=d.image
    return d

def summaries(df,by,relation):
    # The vectorized group reductions are identical to the pilot's scalar
    # reductions, while keeping all missing/failed rows in attempt counts.
    w=df.copy();metrics=[m for m in METRICS if m in w]
    w['_both_source']=w.source_time_complete_a & w.source_time_complete_b
    w['_both_target']=w.target_time_complete_a & w.target_time_complete_b
    for m in metrics:w[m]=pd.to_numeric(w[m],errors='coerce').astype(float)
    g=w.groupby(by,dropna=False,observed=True)
    base=g.agg(attempts=('team_id_a','size'),quality_comparable=('B8L2_change','count'),
        both_complete=('both_complete','sum'),both_source_time_complete=('_both_source','sum'),
        both_target_time_complete=('_both_target','sum'),same_subset_draws=('same_subset','sum'))
    base['distinct_team_pairs']=base.attempts
    mean=g[metrics].mean();count=g[metrics].count();q=g[metrics].quantile([.1,.5,.9,.95])
    rows=[]
    for m in metrics:
        x=base.copy();x['metric']=m;x['n']=count[m];x['mean']=mean[m]
        for label,quantile in [('q10',.1),('median',.5),('q90',.9),('q95',.95)]:x[label]=q[m].xs(quantile,level=-1)
        rows.append(x.reset_index())
    return pd.concat(rows,ignore_index=True)

def paired_contrasts(table,keys,category,left,right,name):
    out=[]
    for key,g in table.groupby(keys,dropna=False):
        if not isinstance(key,tuple):key=(key,)
        a=g[g[category]==left];b=g[g[category]==right]
        if len(a)!=1 or len(b)!=1:continue
        aa,bb=a.iloc[0],b.iloc[0]
        out.append(dict(zip(keys,key),contrast=name,left=left,right=right,
            left_attempts=int(aa.attempts),right_attempts=int(bb.attempts),left_n=int(aa.n),right_n=int(bb.n),
            left_mean=aa['mean'],right_mean=bb['mean'],difference=bb['mean']-aa['mean']))
    return pd.DataFrame(out)

def collapse_contrasts(contrasts,out,prefix):
    if not len(contrasts):return
    contrasts.to_csv(out/(prefix+'_matched_strata.csv'),index=False)
    keys=['threshold_deg','k','contrast','metric','pool_id','image_id','image_code','building_id','difficulty']
    image=contrasts.groupby(keys,dropna=False).agg(difference=('difference','mean'),matched_strata=('difference','size'),
        left_attempts=('left_attempts','sum'),right_attempts=('right_attempts','sum'),left_n=('left_n','sum'),right_n=('right_n','sum')).reset_index()
    image.to_csv(out/(prefix+'_image_effects.csv'),index=False)
    rows=[];building=[]
    for key,g in image.groupby(['threshold_deg','k','contrast','metric'],dropna=False):
        by=g.groupby('building_id').difference.mean();stat=bs(by)
        rows.append(dict(zip(['threshold_deg','k','contrast','metric'],key),images=g.image_id.nunique(),buildings=int(by.notna().sum()),
            attempted_buildings=len(by),measurable_images=g.loc[g.difference.notna(),'image_id'].nunique(),
            image_equal_difference=g.difference.mean(),building_equal_difference=stat['mean'],low=stat['low'],high=stat['high'],
            positive_buildings=int((by>0).sum()),negative_buildings=int((by<0).sum()),left_attempts=int(g.left_attempts.sum()),right_attempts=int(g.right_attempts.sum()),
            left_measurable=int(g.left_n.sum()),right_measurable=int(g.right_n.sum())))
        for b,v in by.items():building.append(dict(zip(['threshold_deg','k','contrast','metric'],key),building_id=b,difference=v))
    pd.DataFrame(rows).to_csv(out/(prefix+'_summary.csv'),index=False);pd.DataFrame(building).to_csv(out/(prefix+'_building_effects.csv'),index=False)

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--pilot',action='store_true');ap.add_argument('--replacements-only',action='store_true');ap.add_argument('--replacement-input',type=Path,default=FUSION/'INITIAL_replacements.csv.gz');args=ap.parse_args()
    out=HERE/('fusion_analysis_pilot' if args.pilot else 'fusion_analysis');out.mkdir(exist_ok=True)
    labels=pd.read_csv(HERE/'assignments.csv');labels=labels[labels.method.eq('affinity') & labels.layer.eq('ordinary_manual')]
    label_map={(r.pool_id,int(r.threshold_deg),r.worker_id):r.local_cluster_id for r in labels.itertuples()}
    count_map={(r.pool_id,r.worker_id):r.pair_count for r in labels[labels.threshold_deg.eq(9)].itertuples()}
    oid_map={(r.pool_id,r.worker_id):r.object_id for r in labels[labels.threshold_deg.eq(9)].itertuples()}
    pools=set(labels.pool_id);meta=labels.drop_duplicates('pool_id').set_index('pool_id')
    fold=pd.read_csv(HERE.parent/'profiles/fold_profiles.csv').set_index(['heldout_building','worker_id'])
    fold_dict=fold.to_dict('index')
    source_replacements=pd.read_csv(args.replacement_input)
    file_candidates=sorted(source_replacements.pool_id.unique())
    if args.pilot:
        pilot=set(json.loads((FUSION/'DESIGN.json').read_text())['pilot_pool_ids']);file_candidates=[p for p in file_candidates if p in pilot]
    replacement_summaries=[];cross_summaries=[];composition_summaries=[];case_candidates=[];coverage=[]
    fullframes=[];compframes=[]
    for pid in file_candidates:
        if pid not in pools:continue
        raw=source_replacements[source_replacements.pool_id.eq(pid)].copy()
        if not len(raw):continue
        raw=attach_flags(raw);original_n=len(raw)
        raw['event_key']=[a+'|'+b if a<=b else b+'|'+a for a,b in zip(raw.team_id_a,raw.team_id_b)]
        raw=raw.drop_duplicates('event_key').copy();assert not raw.same_subset.any()
        for cut in [9,12]:
            d=raw.copy();d['threshold_deg']=cut
            d['entrant_cluster_a']=[label_map[pid,cut,w] for w in d.entrant_a];d['entrant_cluster_b']=[label_map[pid,cut,w] for w in d.entrant_b]
            d['entrant_pair_count_a']=[count_map[pid,w] for w in d.entrant_a];d['entrant_pair_count_b']=[count_map[pid,w] for w in d.entrant_b]
            d['same_point_count']=d.entrant_pair_count_a.eq(d.entrant_pair_count_b);d['same_cluster']=d.entrant_cluster_a.eq(d.entrant_cluster_b)
            assert (d.same_point_count|~d.same_cluster).all()
            d['relation']=np.where(d.same_cluster,'within_cluster_same_count',np.where(d.same_point_count,'cross_cluster_same_count','cross_cluster_different_count'))
            building=meta.loc[pid,'building_id']
            for scheme in ['Q2_B8L2','QT_B8L2','fine_dtype_merged_B8L2']:
                aa=[];bb=[];known=[]
                for wa,wb in zip(d.entrant_a,d.entrant_b):
                    a,b=fold_dict[(building,wa)],fold_dict[(building,wb)]
                    support=bool(a['Q_supported'] and b['Q_supported'])
                    if scheme!='Q2_B8L2':support &= bool(a['T_source_supported'] and b['T_source_supported'])
                    support &= ('unknown' not in str(a[scheme]) and 'unknown' not in str(b[scheme]))
                    aa.append(a[scheme]);bb.append(b[scheme]);known.append(support)
                d[scheme+'_a']=aa;d[scheme+'_b']=bb;d[scheme+'_known']=known
                d[scheme+'_same']=np.where(known,d[scheme+'_a'].eq(d[scheme+'_b']),np.nan)
            by=['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','background_id','entrant_pair_count_a','relation']
            # Different-count stratum has a descriptive source count, never treated as matched equal-complexity contrast.
            replacement_summaries.append(summaries(d,by,'relation'))
            # Within a concrete prospective QT class, compare actual cluster relations.
            qt=d[d.QT_B8L2_known & d.QT_B8L2_a.eq(d.QT_B8L2_b) & d.same_point_count].copy()
            if len(qt):
                qt['parent_QT_class']=qt.QT_B8L2_a
                qby=['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','background_id','entrant_pair_count_a','parent_QT_class','relation']
                cross_summaries.append(summaries(qt,qby,'relation'))
            # Uniform background draws were frozen; select only rank-defined display candidates.
            candidate_sets=[('within_cluster_large_geometry',d[d.same_cluster & d.both_complete].sort_values('floor_jaccard_difference',ascending=False)),
                ('within_cluster_stable',d[d.same_cluster & d.joint_geometric_stable].sort_values(['floor_jaccard_difference','abs_B8L2_change'])),
                ('cross_cluster_large_geometry',d[~d.same_cluster & d.same_point_count & d.both_complete].sort_values('floor_jaccard_difference',ascending=False)),
                ('cross_cluster_small_geometry',d[~d.same_cluster & d.same_point_count & d.both_complete].sort_values(['floor_jaccard_difference','abs_B8L2_change'])),
                ('stable_low_quality',d[d.joint_geometric_stable].sort_values('mean_pair_B8L2')),
                ('within_cluster_failure',d[d.same_cluster & d.any_failure])]
            for kind,g in candidate_sets:
                if len(g):
                    r=g.iloc[0].to_dict();r.update(case_kind=kind,pool_candidate_denominator=len(g));case_candidates.append(r)
            fullframes.append(d)
        coverage.append(dict(pool_id=pid,image_id=meta.loc[pid,'image_id'],building_id=meta.loc[pid,'building_id'],
            replacement_attempt_rows=original_n,distinct_replacement_team_pairs=len(raw),duplicates_collapsed=original_n-len(raw),thresholds=2))
        composition_file=FUSION/'comparisons'/pid/'composition_comparisons.csv.gz'
        if args.replacements_only or not composition_file.exists():continue
        try:
            comp=pd.read_csv(composition_file)
        except pd.errors.EmptyDataError:
            continue
        if not len(comp) or 'comparison_family' not in comp:continue
        comp=comp[comp.comparison_family.eq('cluster_oracle_comparison')].copy()
        if not len(comp):continue
        comp=attach_flags(comp)
        def representation(ws,cut):
            workers=ws.split('|');co=collections.Counter(label_map[pid,int(cut),w] for w in workers);ct=collections.Counter(count_map[pid,w] for w in workers)
            return json.dumps(sorted(co.items()),separators=(',',':')),json.dumps(sorted(ct.items()),separators=(',',':'))
        ra=[representation(w,c) for w,c in zip(comp.member_workers_a,comp.threshold)];rb=[representation(w,c) for w,c in zip(comp.member_workers_b,comp.threshold)]
        comp['canonical_composition_a']=[r[0] for r in ra];comp['canonical_composition_b']=[r[0] for r in rb]
        comp['point_count_hist_a']=[r[1] for r in ra];comp['point_count_hist_b']=[r[1] for r in rb]
        comp['same_local_composition']=comp.canonical_composition_a.eq(comp.canonical_composition_b)
        assert comp.same_local_composition.eq(comp.same_composition).all()
        comp['same_point_count_hist']=comp.point_count_hist_a.eq(comp.point_count_hist_b)
        comp['turnover']=comp.k-comp.shared_workers;comp['threshold_deg']=comp.threshold
        comp['event_key']=[str(c)+'|'+('|'.join(sorted([a,b]))) for c,a,b in zip(comp.threshold,comp.team_id_a,comp.team_id_b)]
        comp=comp.drop_duplicates('event_key').copy();compframes.append(comp)
        comparable=comp[~comp.same_subset & comp.same_point_count_hist].copy()
        comparable['relation']=np.where(comparable.same_local_composition,'same_cluster_composition','different_cluster_composition')
        by=['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','turnover','point_count_hist_a','relation']
        composition_summaries.append(summaries(comparable,by,'relation'))
    if not fullframes:raise ValueError('No completed ordinary-Manual replacement comparisons available')
    pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False)
    nrep=write_gz(out/'replacement_cluster_details.csv.gz',fullframes)
    ncomp=write_gz(out/'composition_cluster_details.csv.gz',compframes)
    repl=pd.concat(replacement_summaries,ignore_index=True);repl.to_csv(out/'replacement_background_statistics.csv',index=False)
    keys=['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','background_id','entrant_pair_count_a','metric']
    matched=paired_contrasts(repl,keys,'relation','within_cluster_same_count','cross_cluster_same_count','cross_minus_within_same_point_count')
    collapse_contrasts(matched,out,'replacement')
    if cross_summaries:
        cross=pd.concat(cross_summaries,ignore_index=True);cross.to_csv(out/'cross_route_background_statistics.csv',index=False)
        matched=paired_contrasts(cross,keys[:-1]+['parent_QT_class','metric'],'relation','within_cluster_same_count','cross_cluster_same_count','cross_minus_within_cluster_same_concrete_QT_class')
        collapse_contrasts(matched,out,'cross_route')
    if composition_summaries:
        comp=pd.concat(composition_summaries,ignore_index=True);comp.to_csv(out/'composition_statistics.csv',index=False)
        keys=['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','turnover','point_count_hist_a','metric']
        matched=paired_contrasts(comp,keys,'relation','same_cluster_composition','different_cluster_composition','changed_composition_minus_same_composition_at_same_turnover_and_point_count_hist')
        collapse_contrasts(matched,out,'composition')
    cases=pd.DataFrame(case_candidates);cases.to_csv(out/'case_candidates_all_pools.csv',index=False)
    selected=[]
    for (cut,kind),g in cases.groupby(['threshold_deg','case_kind']):
        if kind in ['within_cluster_large_geometry','cross_cluster_large_geometry']:g=g.sort_values('floor_jaccard_difference',ascending=False)
        elif kind in ['cross_cluster_small_geometry','within_cluster_stable']:g=g.sort_values(['floor_jaccard_difference','abs_B8L2_change'])
        elif kind=='stable_low_quality':g=g.sort_values('mean_pair_B8L2')
        chosen=g.drop_duplicates('building_id').head(3).copy();chosen['all_pool_candidate_denominator']=len(g);selected.append(chosen)
    pd.concat(selected,ignore_index=True).to_csv(out/'representative_counterexample_candidates.csv',index=False)
    receipt=dict(stage='pilot_interface_check' if args.pilot else 'current_completed_fusion_comparisons',
        ordinary_images=len(coverage),buildings=len({r['building_id'] for r in coverage}),
        replacement_attempts=sum(r['replacement_attempt_rows'] for r in coverage),
        unique_replacement_team_pairs=sum(r['distinct_replacement_team_pairs'] for r in coverage),
        threshold_labeled_replacement_rows=nrep,composition_rows=ncomp,
        failures_retained=True,reference_and_fusion_unchanged=True,same_count_and_background_matched=True,
        composition_comparison_turnover_and_point_count_hist_matched=True,
        target_local_clusters_are_oracle=True,random_draws_are_not_independent_people=True,
        source_files=[str(args.replacement_input)],source_replacements_sha256=hashlib.sha256(args.replacement_input.read_bytes()).hexdigest(),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'ANALYSIS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
