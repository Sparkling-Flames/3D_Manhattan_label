"""Quality components, finite member variation and coarse/fine composition.

No endpoint is refit or recomputed. Exact near-census member populations and
sampled members in complete count-vector grids remain separate throughout.
"""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_k]='1'
import argparse
import collections
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
COMP=STUDY/'composition'
COMPONENTS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
 'omission','extension','height_mean_ratio','nodes','ref_node_recall_5','ref_node_recall_9',
 'ref_edge_recall_5','ref_edge_recall_9','diag_wall_coverage_03','diag_wall_coverage_05',
 'diag_corner_recall_05','geometry_area_h2','centroid_x_h','centroid_z_h',
 'bounds_min_x_h','bounds_min_z_h','bounds_max_x_h','bounds_max_z_h',
 'height_mean_h','height_min_h','height_max_h','top_y_mean_px','bottom_y_mean_px',
 'source_time_total_seconds','target_time_total_seconds','source_parallel_active_seconds']

def write(d,name):
    d.to_csv(HERE/name,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)

def balanced(d,metrics,groups):
    """All events within reference pool, panels within image, images/buildings equal."""
    rows=[];bsrows=[]
    if not len(d):return pd.DataFrame(),pd.DataFrame()
    # Aggregate all numeric fields together. This is algebraically the same
    # per-field pool -> image -> building mean, including fieldwise missingness,
    # without repeating thousands of groupby operations for wide vote metrics.
    pool=d.groupby(groups+['building','image','pool_id'],dropna=False)[metrics].mean()
    images=pool.groupby(level=groups+['building','image'],dropna=False).mean()
    building=images.groupby(level=groups+['building'],dropna=False).mean().reset_index()
    by_group={k if isinstance(k,tuple) else (k,):v.set_index('building') for k,v in building.groupby(groups,dropna=False)}
    for key,g in d.groupby(groups,dropna=False):
        if not isinstance(key,tuple):key=(key,)
        meta=dict(zip(groups,key));r=dict(meta,events=len(g),pools=g.pool_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique())
        for m in metrics:
            z=by_group[key][m].dropna()
            r[m+'_mean']=z.mean();r[m+'_buildings']=len(z);r[m+'_events']=int(g[m].notna().sum())
            r[m+'_positive_buildings']=int(z.gt(0).sum());r[m+'_negative_buildings']=int(z.lt(0).sum())
            if m in ('within_joint_stable_main','cross_joint_stable_main','stable_advantage',
                     'abs_Q_change_advantage','net_B8L2','net_D10','cross_loss_gt5','same_loss_gt5',
                     'fine_mse_gain_over_parent') and len(z)>=3:
                random=np.random.default_rng(20261021);a=z.to_numpy(float)
                boot=a[random.integers(len(a),size=(2000,len(a)))].mean(axis=1)
                r[m+'_lo'],r[m+'_hi']=np.quantile(boot,[.025,.975])
            for b,v in z.items():bsrows.append(dict(meta,metric=m,building=b,value=v))
        rows.append(r)
    return pd.DataFrame(rows),pd.DataFrame(bsrows)

def load():
    d=pd.read_csv(COMP/'TEAMS_SCALARS.csv.gz',low_memory=False)
    assert not d.team_key.duplicated().any()
    for c in COMPONENTS:
        if c not in d:d[c]=np.nan
    d['score_available']=d.B8L2.notna()
    d['failure']=~d.complete_evaluable.fillna(False).astype(bool)
    return d

def near_census(d):
    layers=pd.read_csv(COMP/'EXACT_LAYERS.csv') if (COMP/'EXACT_LAYERS.csv').exists() else pd.read_csv(COMP/'EXACT_LAYERS_STAGE1.csv')
    required=layers[['pool_id','n','all_member_sets']].rename(columns={'n':'k'})
    z=d.merge(required,on=['pool_id','k'],validate='many_to_one')
    rows=[]
    for (pid,n),g in z.groupby(['pool_id','k']):
        r={k:g.iloc[0][k] for k in ('pool_id','image','building','condition','layer','difficulty','pool_n')}
        r.update(n=n,sets=len(g),required_sets=int(g.all_member_sets.iloc[0]),exhaustive=len(g)==int(g.all_member_sets.iloc[0]),
            deletions=int(g.pool_n.iloc[0]-n),score_available_n=int(g.score_available.sum()),failure_rate=g.failure.mean(),
            member_variation_estimable=len(g)>1,all_unordered_endpoint_pairs=str(math.comb(len(g),2)),
            full_set_zero_variation_is_evidence=False)
        for c in COMPONENTS:
            y=g[c].dropna();r[c+'_mean']=y.mean();r[c+'_sd']=y.std(ddof=1) if len(y)>1 else np.nan
            if c in ('B8L2','D10','nodes','height_mean_h'):
                r[c+'_min']=y.min();r[c+'_max']=y.max();r[c+'_p10']=y.quantile(.1)
        rows.append(r)
    pools=pd.DataFrame(rows);write(pools,'EXACT_MEMBER_LAYER_SUMMARY.csv')
    methods=pd.read_csv(COMP/'FROZEN_LABELS.csv',keep_default_na=False)
    maps={(m,t,c,b):dict(zip(g.worker_id,g.class_id)) for (m,t,c,b),g in methods.groupby(['method_id','tier','condition','heldout_building'])}
    # Closed-form exact unordered pair moments: unlike a few sampled pairs,
    # these describe every score-available endpoint pair in a finite layer.
    out=[]
    full_members={r.pool_id:set(r.member_workers.split('|')) for r in d[d.k.eq(d.pool_n)].itertuples()}
    def moments(frame,metric):
        """All / within-count-vector unordered pair counts and sums."""
        q=frame.dropna(subset=[metric]);y=np.sort(q[metric].to_numpy(float));k=len(y)
        if k:y=y-y[0]
        result=np.array([math.comb(k,2),np.dot(2*np.arange(k)-k+1,y),k*np.dot(y,y)-y.sum()**2,0.,0.,0.])
        for _,cell in q.groupby('_composition'):
            v=np.sort(cell[metric].to_numpy(float));n=len(v)
            if n:v=v-v[0]
            result[3:]+=np.array([math.comb(n,2),np.dot(2*np.arange(n)-n+1,v),n*np.dot(v,v)-v.sum()**2])
        return result
    for (pid,n),g in z.groupby(['pool_id','k']):
        if len(g)!=int(g.all_member_sets.iloc[0]) or len(g)<2:continue
        g=g.copy();member_lists=g.member_workers.str.split('|').tolist();first=g.iloc[0]
        for (method,tier,cond,bld),mapping in maps.items():
            if (cond,bld)!=(first.condition,first.building):continue
            if method in ('Rnew2','F01') and first.layer!='ordinary_manual':continue
            keep=np.array([all(w in mapping for w in ws) for ws in member_lists])
            if keep.sum()<2:continue
            a=g.loc[keep].copy();ws=[v for v,ok in zip(member_lists,keep) if ok]
            a['_composition']=['|'.join(f'{k}:{v}' for k,v in sorted(collections.Counter(mapping[w] for w in members).items())) for members in ws]
            a['_removed']=[tuple(sorted(full_members[pid]-set(members))) for members in ws]
            r=dict(method_id=method,tier=tier,pool_id=pid,image=first.image,building=first.building,condition=cond,layer=first.layer,difficulty=first.difficulty,
                n=n,deletions=int(first.pool_n-n),known_only_member_sets=len(a),unlabelled_excluded_member_sets=len(g)-len(a),
                compositions=a._composition.nunique(),member_pair_population='all unordered score-available pairs in fully enumerated finite layer')
            metric_ms={}
            for metric in ('B8L2','D10','nodes'):
                total=moments(a,metric)
                if r['deletions']==1:
                    metric_ms[metric]={1:total}
                elif r['deletions']==2:
                    # Each pair of two-deletion sets sharing one removed
                    # worker has actual turnover m=1 and is counted once.
                    one=np.zeros(6)
                    for w in sorted({w for v in a._removed for w in v}):
                        one+=moments(a[a._removed.map(lambda v:w in v)],metric)
                    metric_ms[metric]={1:one,2:total-one}
            for m in sorted({k for v in metric_ms.values() for k in v}):
                rr=dict(r,actual_m=m)
                for metric,ms in metric_ms.items():
                    total,ab,ss,wn,wa,wsq=ms[m];cn=total-wn
                    rr[metric+'_within_pairs']=str(int(round(wn)));rr[metric+'_cross_pairs']=str(int(round(cn)))
                    rr[metric+'_within_mean_abs']=max(0.,wa/wn) if wn else np.nan
                    rr[metric+'_cross_mean_abs']=max(0.,(ab-wa)/cn) if cn else np.nan
                    rr[metric+'_within_mean_square']=max(0.,wsq/wn) if wn else np.nan
                    rr[metric+'_cross_mean_square']=max(0.,(ss-wsq)/cn) if cn else np.nan
                out.append(rr)
    exact=pd.DataFrame(out);write(exact,'EXACT_COMPOSITION_PAIR_MOMENTS.csv.gz')
    metrics=[c for c in exact if c.endswith(('_within_mean_abs','_cross_mean_abs','_within_mean_square','_cross_mean_square','_descriptive_between_fraction'))]
    if len(exact):
        s,b=balanced(exact,metrics,['method_id','tier','condition','layer','deletions','actual_m']);write(s,'EXACT_COMPOSITION_PAIR_SUMMARY.csv')
    # Every N-1 removal is an addition-path edge into the common full set. N
    # may change the majority threshold; this is separate from fixed-n swaps.
    full=d[d.k.eq(d.pool_n)].set_index('pool_id')
    edges=[]
    for r in z[z.k.lt(z.pool_n)].itertuples():
        if r.pool_id not in full.index:continue
        f=full.loc[r.pool_id];removed=sorted(set(f.member_workers.split('|'))-set(r.member_workers.split('|')))
        e=dict(pool_id=r.pool_id,image=r.image,building=r.building,condition=r.condition,layer=r.layer,difficulty=r.difficulty,
            from_n=r.k,to_n=f.k,added_workers='|'.join(removed),added_n=len(removed),team_from=r.team_key,team_to=f.team_key,
            threshold_from=r.minimum_support,threshold_to=f.minimum_support,complete_from=r.complete_evaluable,complete_to=f.complete_evaluable)
        for c in COMPONENTS:e[c+'_addition_change']=f[c]-getattr(r,c) if pd.notna(f[c]) and pd.notna(getattr(r,c)) else np.nan
        edges.append(e)
    write(pd.DataFrame(edges),'NEAR_CENSUS_ADDITION_EDGES.csv.gz')

def configurations(d):
    path=COMP/'CONFIG_MEMBERSHIP.csv.gz'
    if not path.exists():return
    c=pd.read_csv(path,low_memory=False)
    x=c.merge(d[['team_key']+COMPONENTS+['complete_evaluable','score_available','failure','new_n','old_n','time_source_kinds']],on='team_key',how='left',validate='many_to_one',indicator=True)
    x['computed']=x._merge.eq('both');x=x.drop(columns='_merge')
    metadata=['method_id','tier','pool_id','image','building','condition','layer','difficulty','n','composition','class_capacities','possible_member_sets','registered_member_sets','exhaustive_vectors','exhaustive_members','member_variation_estimable']
    gb=x.groupby('cell_id',sort=False)
    cells=gb[metadata].first()
    cells['computed_sets']=gb.computed.sum();cells['registered_sets']=gb.size();cells['score_available_sets']=gb.score_available.sum()
    cells['failure_rate']=gb.failure.mean();cells['all_members_computed']=gb.computed.all()
    cells['estimated_member_variation']=cells.computed_sets.gt(1)&cells.possible_member_sets.map(int).gt(1)
    cells['uniform_vector_weight']=1;cells['uniform_member_set_multiplicity']=cells.possible_member_sets
    means=gb[COMPONENTS].mean().add_suffix('_mean');stds=gb[COMPONENTS].std().add_suffix('_sd')
    cells=pd.concat([cells,means,stds],axis=1)
    for suffix,frame in [('min',gb[['B8L2','D10','nodes']].min()),('max',gb[['B8L2','D10','nodes']].max()),('p10',gb[['B8L2','D10','nodes']].quantile(.1))]:
        cells=pd.concat([cells,frame.add_suffix('_'+suffix)],axis=1)
    cells=cells.reset_index();write(cells,'CONFIGURATION_CELL_RESULTS.csv.gz')
    # Honest outer holdout of specific members within each count vector:
    # predict each sampled endpoint from the other two. This requires a
    # separate endpoint and does not count full/singleton teams as success.
    pred=[]
    for (method,tier,pid,n),g in x[x.computed].groupby(['method_id','tier','pool_id','n']):
        for metric in ('B8L2','D10','nodes','height_mean_h'):
            a=g.dropna(subset=[metric]).copy()
            if len(a)<4:continue
            celln=a.groupby('cell_id')[metric].transform('size');cellsum=a.groupby('cell_id')[metric].transform('sum')
            valid=celln.ge(2)
            if not valid.any():continue
            prediction=(cellsum-a[metric])/(celln-1)
            overall=(a[metric].sum()-a[metric])/(len(a)-1)
            sq=(prediction[valid]-a.loc[valid,metric])**2;nullsq=(overall[valid]-a.loc[valid,metric])**2
            pred.append(dict(method_id=method,tier=tier,pool_id=pid,image=g.image.iloc[0],building=g.building.iloc[0],condition=g.condition.iloc[0],layer=g.layer.iloc[0],difficulty=g.difficulty.iloc[0],n=n,metric=metric,
                held_member_endpoints=int(valid.sum()),composition_mse=sq.mean(),pool_n_mse=nullsq.mean(),mse_reduction=nullsq.mean()-sq.mean(),
                interpretation='sampled member holdout within image; no unseen-building outcome prediction'))
    pr=pd.DataFrame(pred);write(pr,'CONFIGURATION_MEMBER_HOLDOUT.csv')
    if len(pr):
        s,b=balanced(pr,['composition_mse','pool_n_mse','mse_reduction'],['method_id','tier','condition','layer','metric']);write(s,'CONFIGURATION_MEMBER_HOLDOUT_SUMMARY.csv')
    # A direct fine-vs-parent comparison must use identical endpoints. The
    # independently sampled coarse grid is not that comparison. Relabel only
    # the fine grid by its frozen parent map, then hold out the same endpoint
    # from the fine-cell, parent-cell and pool/n predictions.
    fl=pd.read_csv(COMP/'FROZEN_LABELS.csv',keep_default_na=False)
    parent_maps={(m,c,b):dict(zip(g.class_id,g.parent_class)) for (m,c,b),g in fl[fl.tier.eq('fine')].groupby(['method_id','condition','heldout_building'])}
    shared=[]
    for (method,pid,n),g in x[x.computed & x.tier.eq('fine')].groupby(['method_id','pool_id','n']):
        assert not g.team_key.duplicated().any()
        g=g.copy(); first=g.iloc[0]; pm=parent_maps[(method,first.condition,first.building)]
        def parent_composition(s):
            count=collections.Counter()
            for part in s.split('|'):
                label,k=part.rsplit(':',1);count[pm[label]]+=int(k)
            return '|'.join(f'{cl}:{k}' for cl,k in sorted(count.items()))
        g['_parent']=g.composition.map(parent_composition)
        for metric in ['B8L2','D10','nodes','ref_node_recall_5','ref_edge_recall_5','height_mean_h','geometry_area_h2','source_time_total_seconds']:
            a=g.dropna(subset=[metric]).copy()
            if len(a)<4:continue
            fine_n=a.groupby('cell_id')[metric].transform('size');fine_sum=a.groupby('cell_id')[metric].transform('sum')
            coarse_n=a.groupby('_parent')[metric].transform('size');coarse_sum=a.groupby('_parent')[metric].transform('sum')
            ok=fine_n.ge(2)&coarse_n.ge(2)
            if not ok.any():continue
            y=a.loc[ok,metric]
            fp=((fine_sum-a[metric])/(fine_n-1))[ok]
            cp=((coarse_sum-a[metric])/(coarse_n-1))[ok]
            zp=((a[metric].sum()-a[metric])/(len(a)-1))[ok]
            shared.append(dict(method_id=method,pool_id=pid,image=first.image,building=first.building,condition=first.condition,layer=first.layer,difficulty=first.difficulty,n=n,metric=metric,
                sampled_member_sets=len(g),held_member_endpoints=int(ok.sum()),fine_cells=a.loc[ok,'cell_id'].nunique(),parent_cells=a.loc[ok,'_parent'].nunique(),
                response_var=float(y.var(ddof=0)),fine_mse=float(((fp-y)**2).mean()),coarse_mse=float(((cp-y)**2).mean()),pool_n_mse=float(((zp-y)**2).mean()),
                fine_mse_gain_over_parent=float(((cp-y)**2-(fp-y)**2).mean()),
                time_population='new_only' if g.old_n.eq(0).all() else ('old_only' if g.new_n.eq(0).all() else 'mixed_origin'),
                source_clock_kinds='|'.join(sorted(set(g.time_source_kinds.dropna()))),
                interpretation='Identical fine-grid sampled endpoints; leave-one-member-set-out within image. All vectors, at most three draws per vector; not a held-building outcome forecast.'))
    fine=pd.DataFrame(shared);write(fine,'FINE_SHARED_MEMBER_HOLDOUT.csv')
    if len(fine):
        s,b=balanced(fine,['fine_mse','coarse_mse','pool_n_mse','fine_mse_gain_over_parent','response_var'],['method_id','condition','layer','metric'])
        write(s,'FINE_SHARED_MEMBER_HOLDOUT_SUMMARY.csv');write(b,'FINE_SHARED_MEMBER_HOLDOUT_BUILDINGS.csv')
        s,b=balanced(fine[fine.n.ge(20)],['fine_mse','coarse_mse','pool_n_mse','fine_mse_gain_over_parent','response_var'],['method_id','condition','layer','metric'])
        write(s,'FINE_SHARED_MEMBER_HOLDOUT_LARGE_SUMMARY.csv')

def abc(d):
    path=COMP/'ABC_EVENTS.csv.gz'
    if not path.exists():return
    e=pd.read_csv(path,keep_default_na=False);indexed=d.set_index('team_key');out=[]
    histories=pd.read_csv(STUDY/'multivariate/continuous_features_lobo.csv.gz')
    history={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
    def counts(s):return {v.rsplit(':',1)[0]:int(v.rsplit(':',1)[1]) for v in s.split('|')}
    def block_history(ws,condition,building,field):
        values=[getattr(history.get((condition,building,w)),field,np.nan) for w in ws.split('|') if w]
        return float(np.mean(values)) if values and np.isfinite(values).all() else np.nan
    for r in e.to_dict('records'):
        keys=[r['team_'+role] for role in 'ABC']
        if not all(k in indexed.index for k in keys):
            r['computed_all_arms']=False;out.append(r);continue
        a,b,c=[indexed.loc[k] for k in keys];r['computed_all_arms']=True
        ca,cc=counts(r['composition_A']),counts(r['composition_C'])
        delta={cl:cc.get(cl,0)-ca.get(cl,0) for cl in sorted(ca.keys()|cc.keys())}
        r['composition_delta']='|'.join(f'{cl}:{v:+d}' for cl,v in delta.items())
        targets={'M_structure':'M1','SP_scale':'SP_LOW','MV_QTD_manual':'QH','MV_QTD_manual_new':'QH',
                 'MV_QTScopeSemi_semi_new':'QH'}
        target=targets.get(r['method_id'])
        if r['tier']=='coarse' and target in delta:
            dt=delta[target];r['direction']=f'{target}_increase' if dt>0 else f'{target}_decrease';r['focal_class_count_change']=dt
        elif r['event_mode']=='within_coarse_fine_change':
            positive=','.join(f'{cl}+{v}' for cl,v in delta.items() if v>0)
            negative=','.join(f'{cl}{v}' for cl,v in delta.items() if v<0)
            r['direction']=negative+' -> '+positive
        else:r['direction']='multiple_class_vector_change'
        wa,wb,wc=[set(q.member_workers.split('|')) for q in (a,b,c)]
        assert len(wa-wb)==r['m_AB']==len(wa-wc)==r['m_AC'] and wa&wb==wa&wc
        r['all_scored']=bool(pd.notna(a.B8L2) and pd.notna(b.B8L2) and pd.notna(c.B8L2))
        r['all_complete']=bool(a.complete_evaluable and b.complete_evaluable and c.complete_evaluable)
        r['time_population']='new_only' if all(q.old_n==0 for q in (a,b,c)) else ('old_only' if all(q.new_n==0 for q in (a,b,c)) else 'mixed_origin')
        r['same_source_counts']=bool(a.new_n==b.new_n==c.new_n)
        for block,column in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z')]:
            for field in ['q_effect','q_downside','t_effect','hard_minus_easy']:
                r[block+'_history_'+field]=block_history(r[column],r['condition'],r['building'],field)
        r['same_history_block_Q_change']=r['Y_history_q_effect']-r['X_history_q_effect']
        r['cross_history_block_Q_change']=r['Z_history_q_effect']-r['X_history_q_effect']
        r['net_history_block_Q_change']=r['Z_history_q_effect']-r['Y_history_q_effect']
        for threshold in (2,5):
            r['source_and_historyQ'+str(threshold)+'_matched']=bool(r['same_source_counts'] and abs(r['same_history_block_Q_change'])<=threshold and abs(r['cross_history_block_Q_change'])<=threshold)
        for role,q in zip('ABC',(a,b,c)):
            r[role+'_failure']=not bool(q.complete_evaluable);r[role+'_score_status']=q.score_status
            r[role+'_source_time_seconds']=q.source_time_total_seconds;r[role+'_B8L2']=q.B8L2;r[role+'_D10']=q.D10;r[role+'_nodes']=q.nodes
        for prefix,left,right in (('same',a,b),('cross',a,c),('net',b,c)):
            for metric in COMPONENTS:r[prefix+'_'+metric]=right[metric]-left[metric] if pd.notna(right[metric]) and pd.notna(left[metric]) else np.nan
            dq=r[prefix+'_B8L2'];r[prefix+'_abs_B8L2']=abs(dq) if pd.notna(dq) else np.nan
            # Missing quality is not a no-loss event. Algorithm failures retain
            # the complete event denominator in the separate failure fields.
            r[prefix+'_loss_gt5']=float(dq < -5) if pd.notna(dq) else np.nan
            r[prefix+'_loss_gt10']=float(dq < -10) if pd.notna(dq) else np.nan
            r[prefix+'_quality_comparable']=pd.notna(dq)
            comparable=left.source_time_total_seconds>0 and right.source_time_total_seconds>0 and left.time_source_kinds==right.time_source_kinds
            r[prefix+'_source_log_time_ratio']=math.log(right.source_time_total_seconds/left.source_time_total_seconds) if comparable else np.nan
            r[prefix+'_time_comparable']=bool(comparable)
            r[prefix+'_joint_cost_quality_comparable']=bool(comparable and pd.notna(dq))
            r[prefix+'_joint_save20_loss_le2']=float(right.source_time_total_seconds/left.source_time_total_seconds<=.8 and dq>=-2 and left.complete_evaluable and right.complete_evaluable) if comparable and pd.notna(dq) else np.nan
        r['abs_Q_change_advantage']=r['cross_abs_B8L2']-r['same_abs_B8L2']
        r['common_quality_within_abs']=r['same_abs_B8L2'] if r['all_scored'] else np.nan
        r['common_quality_cross_abs']=r['cross_abs_B8L2'] if r['all_scored'] else np.nan
        r['net_failure_difference']=int(r['C_failure'])-int(r['B_failure'])
        out.append(r)
    events=pd.DataFrame(out)
    geo=COMP/'ABC_GEOMETRY.csv.gz'
    if geo.exists():events=events.merge(pd.read_csv(geo),on='event_id',how='left',validate='one_to_one',suffixes=('','_geometry'))
    if 'within_joint_stable_main' in events and 'cross_joint_stable_main' in events:
        events['stable_advantage']=events.within_joint_stable_main.astype(float)-events.cross_joint_stable_main.astype(float)
    write(events,'ABC_ALL_COMPONENT_EVENTS.csv.gz')
    computed=events[events.computed_all_arms.eq(True)].copy()
    measures=[c for c in computed if c.startswith(('same_','cross_','net_','common_quality_','within_')) and pd.api.types.is_numeric_dtype(computed[c]) and c not in ['same_source_counts']]
    measures+=['A_failure','B_failure','C_failure','abs_Q_change_advantage']
    if 'stable_advantage' in events:measures+=['stable_advantage']
    measures=list(dict.fromkeys(measures))
    groups=['method_id','tier','event_mode','condition','layer']
    s,b=balanced(computed,measures,groups+['n','m_AB']);write(s,'ABC_SUMMARY_N_M.csv');write(b,'ABC_BUILDING_VALUES.csv.gz')
    s,b=balanced(computed,measures,groups);write(s,'ABC_SUMMARY.csv')
    large=computed[computed.n.ge(20) & computed.m_AB.ge(4)]
    if len(large):
        s,b=balanced(large,measures,groups);write(s,'ABC_LARGE_SUMMARY.csv');write(b,'ABC_LARGE_BUILDING_VALUES.csv.gz')
        s,b=balanced(large,measures,groups+['difficulty']);write(s,'ABC_LARGE_DIFFICULTY.csv')
    s,b=balanced(computed,measures,groups+['difficulty']);write(s,'ABC_SUMMARY_DIFFICULTY.csv')
    s,b=balanced(computed,measures,groups+['direction']);write(s,'ABC_DIRECTIONAL_SUMMARY.csv')
    matched=[]
    for scope,base in [('all_registered',computed),('n_ge20_m_ge4',large)]:
        for name,subset in [('all_actual_events',base),('same_source_counts',base[base.same_source_counts]),
                            ('same_source_block_Q_within5',base[base.source_and_historyQ5_matched]),
                            ('same_source_block_Q_within2',base[base.source_and_historyQ2_matched])]:
            if not len(subset):continue
            s,b=balanced(subset,[m for m in measures if m in ['abs_Q_change_advantage','common_quality_within_abs','common_quality_cross_abs','net_B8L2','net_D10','net_nodes','net_failure_difference','within_joint_stable_main','cross_joint_stable_main','stable_advantage']],groups)
            s['posthoc_comparison_stratum']=name;s['size_scope']=scope;matched.append(s)
    if matched:write(pd.concat(matched,ignore_index=True),'ABC_Q_SOURCE_SENSITIVITY.csv')
    t=computed[computed.same_source_counts & computed.time_population.isin(['new_only','old_only'])]
    tm=[c for c in measures if c.endswith(('source_log_time_ratio','joint_save20_loss_le2','B8L2','D10','loss_gt5','quality_comparable','time_comparable'))]
    s,b=balanced(t,tm,groups+['time_population']);write(s,'ABC_EFFICIENCY_SAME_SOURCE.csv')
    if len(t[t.n.ge(20)&t.m_AB.ge(4)]):
        s,b=balanced(t[t.n.ge(20)&t.m_AB.ge(4)],tm,groups+['time_population']);write(s,'ABC_LARGE_EFFICIENCY_SAME_SOURCE.csv')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['near','grid','abc','all'],default='all');a=ap.parse_args();d=load()
    if a.part in ('near','all'):near_census(d)
    if a.part in ('grid','all'):configurations(d)
    if a.part in ('abc','all'):abc(d)
    print('Completed',a.part,'on',len(d),'deduplicated endpoints',flush=True)

if __name__=='__main__':main()
