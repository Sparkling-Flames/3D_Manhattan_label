"""Building-balanced effect sizes with every failure and exact support retained."""
from __future__ import annotations
from joint_design import *
import argparse

PRIMARY=['same_B8L2','cross_B8L2','net_B8L2','same_D10','cross_D10','net_D10',
 'same_recorded_time_logratio','cross_recorded_time_logratio','net_recorded_time_logratio',
 'same_B8L2_completion_lower','same_B8L2_completion_upper','cross_B8L2_completion_lower','cross_B8L2_completion_upper','net_B8L2_completion_lower','net_B8L2_completion_upper',
 'common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage','stable_advantage',
 'within_joint_stable_main','cross_joint_stable_main','A_failure','B_failure','C_failure','net_failure_difference',
 'same_loss_gt5','cross_loss_gt5','net_loss_gt5','same_loss_gt10','cross_loss_gt10','net_loss_gt10',
 'same_QT_both_improve','cross_QT_both_improve','net_QT_both_improve','net_Q_up','net_time_down',
 'common_geometry_within_floor_jaccard_difference','common_geometry_cross_floor_jaccard_difference',
 'common_geometry_advantage_floor_jaccard_difference','common_geometry_within_mean_height_prism_pair_difference',
 'common_geometry_cross_mean_height_prism_pair_difference','common_geometry_advantage_mean_height_prism_pair_difference',
 'common_expression_within_abs_fusion_turn_n','common_expression_cross_abs_fusion_turn_n','common_expression_advantage_fusion_turn_n',
 'same_fusion_turn_n','cross_fusion_turn_n','net_fusion_turn_n','net_fusion_short_turn_edges','net_fusion_redundancy_n']

def means(g,metrics):
    # A background receives one weight regardless of the number of member ties.
    bg=g.groupby(['building','image','pool_id','n','common_background'],dropna=False)[metrics].mean().reset_index()
    ni=bg.groupby(['building','image','pool_id','n'],dropna=False)[metrics].mean().reset_index()
    im=ni.groupby(['building','image'],dropna=False)[metrics].mean().reset_index()
    bu=im.groupby('building',dropna=False)[metrics].mean().reset_index()
    return bg,ni,im,bu

def subsets(d):
    yield 'all_quality',d
    yield 'scored_triple_quality_common',d[d.all_scored.eq(True)]
    t=d[d.recorded_time_single_source.eq(True)]
    yield 'time_common',t
    st=t[t.all_scored.eq(True)]
    yield 'scored_triple_time_common',st
    for direction in sorted(d.training_QT_direction.dropna().unique()):
        yield 'center_'+direction,d[d.training_QT_direction.eq(direction)]
        yield 'center_'+direction+'__time_common',t[t.training_QT_direction.eq(direction)]
        yield 'center_'+direction+'__scored_time_common',st[st.training_QT_direction.eq(direction)]
    if 'pred_QT_both_improve_BC' in d:
        yield 'pred_QT_both',d[d.pred_QT_both_improve_BC.eq(True)]
        yield 'pred_QT_both__time_common',t[t.pred_QT_both_improve_BC.eq(True)]
        yield 'pred_QT_both__scored_time_common',st[st.pred_QT_both_improve_BC.eq(True)]
    if 'selection_status' in d:
        yield 'selected_folds_only',d[d.selection_status.eq('selected')]

def summarise_group(g,meta,metrics,boot=True):
    g=g.drop_duplicates('physical_triple_id');bg,ni,im,bu=means(g,metrics);row=dict(meta)
    row.update(events=len(g),physical_triples=g.physical_triple_id.nunique(),unique_teams=len(set(g.team_A)|set(g.team_B)|set(g.team_C)),unique_AB_pairs=len(set(zip(g.team_A,g.team_B))),unique_AC_pairs=len(set(zip(g.team_A,g.team_C))),backgrounds=len(bg),images=g.image.nunique(),buildings=g.building.nunique(),panels=g.panel_id.nunique(),time_events=int(g.recorded_time_single_source.sum()),all_complete_events=int(g.all_complete.sum()),all_scored_events=int(g.all_scored.sum()),n_min=int(g.n.min()),n_max=int(g.n.max()),m_min=int(g.m_AB.min()),m_max=int(g.m_AB.max()))
    for unit,frame in [('image',im),('building',bu)]:
        q=frame.net_B8L2;t=frame.net_recorded_time_logratio;good=q.notna()&t.notna()
        row.update({unit+'_Q_known':int(q.notna().sum()),unit+'_Q_up':int(q.gt(0).sum()),unit+'_T_known':int(t.notna().sum()),unit+'_T_down':int(t.lt(0).sum()),unit+'_QT_known':int(good.sum()),unit+'_QT_both':int((q.gt(0)&t.lt(0)&good).sum())})
    comp=[];rng=np.random.default_rng(int(h('summary-bootstrap',{k:str(v) for k,v in meta.items()})[:16],16))
    for metric in metrics:
        x=bu[metric].dropna().to_numpy(float);mu=float(x.mean()) if len(x) else np.nan
        lo=hi=np.nan
        if boot and metric in PRIMARY and len(x)>1:
            bootmeans=x[rng.integers(0,len(x),size=(2000,len(x)))].mean(axis=1);lo,hi=np.quantile(bootmeans,[.025,.975])
        if metric in PRIMARY:
            row[metric]=mu;row[metric+'_lo']=lo;row[metric+'_hi']=hi;row[metric+'_buildings']=len(x)
        comp.append(dict(meta,metric=metric,building_equal_mean=mu,bootstrap_lo=lo,bootstrap_hi=hi,metric_buildings=len(x),metric_images=int(im[metric].notna().sum()),metric_events=int(g[metric].notna().sum()),all_events=len(g),positive_buildings=int((x>0).sum()),negative_buildings=int((x<0).sum())))
    for prefix in ['same','cross','net']:
        for suf in ['', '_lo','_hi']:
            val=row.get(prefix+'_recorded_time_logratio'+suf,np.nan);row[prefix+'_recorded_time_geomean_pct'+suf]=100*np.expm1(val) if np.isfinite(val) else np.nan
    for k,v in meta.items():im[k]=v;bu[k]=v
    return row,comp,im,bu

def run(kind,condition):
    source=HERE/f'{kind.upper()}_{condition.upper()}_EVENTS_COMPLETE.csv.gz';d=pd.read_csv(source,low_memory=False)
    from annotate_training_directions import attach
    d=attach(d,kind,condition)
    # Auxiliary 0--100 completion bounds only. Frozen missing scores remain
    # missing; these are not substituted into B8L2 or its primary means.
    for pre,a,b in [('same','A','B'),('cross','A','C'),('net','B','C')]:
        d[pre+'_B8L2_completion_lower']=d[b+'_B8L2'].fillna(0)-d[a+'_B8L2'].fillna(100)
        d[pre+'_B8L2_completion_upper']=d[b+'_B8L2'].fillna(100)-d[a+'_B8L2'].fillna(0)
    metricprefix=('same_','cross_','net_','within_','common_quality_','common_geometry_','common_expression_')
    metrics=[c for c in d if (c.startswith(metricprefix) or c in PRIMARY) and pd.api.types.is_numeric_dtype(d[c]) and not c.endswith('_known_n')]
    metrics=list(dict.fromkeys([c for c in PRIMARY if c in d]+metrics));out=[];components=[];images=[];buildings=[];strat=[]
    for (method,domain),g in d.groupby(['method_id','source_domain']):
        for scope,s in subsets(g):
            if s.empty:continue
            meta=dict(kind=kind,condition=condition,method_id=method,source_domain=domain,scope=scope)
            row,co,im,bu=summarise_group(s,meta,metrics);out.append(row);components.extend(co);images.append(im);buildings.append(bu)
        for (m,n,diff,direction),s in g.groupby(['m_AB','n','difficulty','training_QT_direction'],dropna=False):
            meta=dict(kind=kind,condition=condition,method_id=method,source_domain=domain,m=m,n=n,difficulty=diff,direction=direction)
            row,_,_,_=summarise_group(s,meta,[c for c in PRIMARY if c in d],boot=False);strat.append(row)
    dest=HERE/'summaries'/kind/condition;dest.mkdir(parents=True,exist_ok=True)
    write(dest/'PRIMARY.csv',pd.DataFrame(out));write(dest/'ALL_COMPONENTS.csv.gz',pd.DataFrame(components));write(dest/'IMAGE_EFFECTS.csv.gz',pd.concat(images,ignore_index=True));write(dest/'BUILDING_EFFECTS.csv.gz',pd.concat(buildings,ignore_index=True));write(dest/'N_M_DIFFICULTY_DIRECTION.csv',pd.DataFrame(strat))
    # Exact fold classes never pooled by the incidental J/X numeric IDs.
    if {'source_class','target_class'}<=set(d):
        fields=['condition','building','image','source_domain','selected_family','source_class','target_class','n','m_AB','training_QT_direction']
        fine=d.groupby(fields,dropna=False)[[c for c in PRIMARY if c in d]].mean().reset_index();write(dest/'EXACT_CLASS_DIRECTIONS.csv.gz',fine)
    receipt=dict(kind=kind,condition=condition,source_sha256=sha(source),events=len(d),distinct_physical_triples=d.physical_triple_id.nunique(),distinct_endpoints=len(set(d.team_A)|set(d.team_B)|set(d.team_C)),primary_rows=len(out),component_rows=len(components),n_m_difficulty_direction_rows=len(strat),hierarchy='member triples -> exact background -> n -> image -> building, equal at each level',bootstrap='2000 building resamples for primary metrics',time_units='sum of source recorded seconds; same one time_source_kind and known for every member',all_failure_events_included=True)
    save(dest/'SUMMARY_RECEIPT.json',receipt)
    columns=['kind','condition','source_domain','method_id','scope','events','images','buildings','net_B8L2','net_recorded_time_geomean_pct','abs_Q_change_advantage','stable_advantage','net_failure_difference','image_QT_both','image_QT_known','building_QT_both','building_QT_known']
    print(pd.DataFrame(out)[columns].to_string(index=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['native','cached','cross']);ap.add_argument('condition',choices=['manual','semi']);args=ap.parse_args();run(args.kind,args.condition)
