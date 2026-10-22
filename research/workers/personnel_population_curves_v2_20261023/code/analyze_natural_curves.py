#!/usr/bin/env python3
"""Natural full-pool v2 prefix curves: finite sequence sampling, separate denominators.

Inputs may be original uniform-prefix rows or the new canonical PREFIX_RESULTS table.
All path repetitions remain in the empirical sampling distribution; fusion was cached
by member set upstream. No target-image outcome is used to choose these natural orders.
"""
from pathlib import Path
import argparse, gzip, io, json, os, warnings
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_population_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore',message='Mean of empty slice',category=RuntimeWarning)

METRICS = ['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter',
           'height_mean_ratio','omission','extension','nodes','reference_node_shortfall',
           'ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9',
           'candidate_unassigned_pair_n',
           'B8_floor_block','B8_direction_block','B8_global_height_block',
           'B8_local_height_block','B8_height_block','D10_direction_block',
           'source_time_total_seconds','target_time_total_seconds']
META = ['pool_id','image','image_id','building','condition','layer','difficulty','pool_n']
FLAGS = ['score_unavailable','geometry_unavailable','sorting_deferred','below_four_flag','connection_unavailable']


def save(df, path):
    path=Path(path);raw=df.to_csv(index=False).encode('utf-8')
    if path.suffix=='.gz':raw=gzip.compress(raw,mtime=0)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    tmp.replace(path)


def mean_abs_pairs(s):
    v=np.sort(pd.to_numeric(s,errors='coerce').dropna().to_numpy());n=len(v)
    return float(2*np.dot(2*np.arange(n)-n+1,v)/(n*(n-1))) if n>1 else np.nan


def asbool(s):
    if pd.api.types.is_bool_dtype(s):return s.fillna(False)
    return s.astype(str).str.lower().isin(['true','1','1.0'])


def normalize(path, annotations):
    required=set(META+METRICS+['policy','path_id','replicate','base_path_id','team_key','k','geometry_status','order_status','below_four','connection_available','reference_nodes','reference_pair_count','source_time_known_n','target_time_known_n','minimum_support','threshold'])
    def used(c):return c in required or (c.startswith(('ref_','floor_','height_','centroid_','top_','bottom_')) and not c.startswith(('ref_matched_nodes_','ref_matched_edges_')))
    parts=[]
    for chunk in pd.read_csv(path,low_memory=False,usecols=used,chunksize=50000):
        if 'policy' in chunk:chunk=chunk[chunk.policy.eq('natural_random')].copy()
        if len(chunk):parts.append(chunk)
    d=pd.concat(parts,ignore_index=True)
    if 'policy' not in d:
        d['policy']='natural_random'
    else:d=d[d.policy.eq('natural_random')].copy()
    if 'path_id' not in d:
        d['path_id']=d.pool_id.astype(str)+'__'+d.replicate.astype(str)
    if 'layer' not in d:d['layer']='ordinary_'+d.condition
    if 'building' not in d:d['building']=d.image.str.split('-').str[0]
    if 'reference_nodes' not in d and 'reference_pair_count' in d:
        d['reference_nodes']=d.reference_pair_count
    if 'reference_node_shortfall' not in d and 'reference_nodes' in d:
        d['reference_node_shortfall']=(d.reference_nodes-d.nodes).clip(lower=0)
    if 'floor_turn5' not in d and 'floor_turn5_n' in d:
        d['floor_turn5']=d.floor_turn5_n
    extra_numeric=[c for c in d if (c.startswith(('ref_','floor_','height_','centroid_','top_','bottom_')) and pd.api.types.is_numeric_dtype(d[c]) and not pd.api.types.is_bool_dtype(d[c]) and c not in METRICS and c!='floor_turn5_n')]
    METRICS.extend(extra_numeric)
    for c in METRICS:
        if c in d:d[c]=pd.to_numeric(d[c],errors='coerce')
    d['score_unavailable']=~np.isfinite(d.B8L2)
    d['geometry_unavailable']=~d.geometry_status.eq('ok')
    d['sorting_deferred']=d.order_status.fillna('').str.contains('two_person_sorting_deferred')
    d['below_four_flag']=asbool(d.below_four) if 'below_four' in d else d.nodes.lt(4)
    d['connection_unavailable']=~asbool(d.connection_available)
    for kind in ['source','target']:
        total=kind+'_time_total_seconds';known=kind+'_time_known_n'
        if total in d and known in d:d.loc[d[known]!=d.k,total]=np.nan
    assert not d.duplicated(['pool_id','path_id','k']).any(), 'Repeated path/k rows must be resolved upstream.'
    ann=pd.read_csv(annotations)
    cols=['image_id','image_layer','difficulty_conditional','difficulty_coarse','ref_turn5','ref_H','ref_short_edges','structure_opportunity','target_full_status','visual_evidence','visual_space']
    d=d.merge(ann[cols],on='image_id',how='left',validate='many_to_one')
    assert d.image_layer.notna().all(), 'Unlinked image difficulty'
    if 'floor_turn5' in d:
        d['floor_turn_gap5']=d.floor_turn5-d.ref_turn5
        d['floor_turn_deficit5']=(-d.floor_turn_gap5).clip(lower=0)
        d['floor_turn_extra5']=d.floor_turn_gap5.clip(lower=0)
        d['floor_redundant_nodes5']=d.nodes-d.floor_turn5
        for c in ['floor_turn_gap5','floor_turn_deficit5','floor_turn_extra5','floor_redundant_nodes5']:
            if c not in METRICS:METRICS.append(c)
    return d


def image_curves(d,out):
    keys=META+['k']
    g=d.groupby(keys,dropna=False,sort=False)
    core=g.agg(prefixes=('team_key','size'),unique_member_sets=('team_key','nunique'),paths=('path_id','nunique'),
               scored=('B8L2','count'),Q_mean=('B8L2','mean'),Q_median=('B8L2','median'),Q_sd=('B8L2','std'),
               Q_min=('B8L2','min'),Q_max=('B8L2','max')).reset_index()
    q=g.B8L2.quantile([.1,.25,.75,.9]).unstack().rename(columns={.1:'Q_p10',.25:'Q_p25',.75:'Q_p75',.9:'Q_p90'}).reset_index()
    core=core.merge(q,on=keys,validate='one_to_one')
    core['Q_iqr']=core.Q_p75-core.Q_p25
    pair=g.B8L2.apply(mean_abs_pairs).rename('Q_mean_absolute_pair_difference').reset_index()
    core=core.merge(pair,on=keys,validate='one_to_one')
    rates=g[FLAGS].mean().add_suffix('_rate').reset_index()
    core=core.merge(rates,on=keys,validate='one_to_one')
    core['full_pool_endpoint']=core.k.eq(core.pool_n)
    core['member_variation_estimable']=core.unique_member_sets.gt(1)
    # Repetitions of a singleton set give zero dispersion; retain but flag this
    # mechanical result so it is never treated as evidence of interchangeable people.
    annotate=d[['pool_id','image_layer','difficulty_conditional','structure_opportunity','ref_turn5','ref_H','ref_short_edges']].drop_duplicates()
    core=core.merge(annotate,on='pool_id',validate='many_to_one')
    pieces=[]
    for m in METRICS:
        if m not in d:continue
        z=g[m].agg(['count','mean','median','std','min','max']).reset_index()
        q=g[m].quantile([.1,.25,.75,.9]).unstack().rename(columns={.1:'p10',.25:'p25',.75:'p75',.9:'p90'}).reset_index()
        z=z.merge(q,on=keys,validate='one_to_one');z['metric']=m
        pieces.append(z)
    long=pd.concat(pieces,ignore_index=True)
    save(core,out/'NATURAL_IMAGE_CURVES.csv.gz')
    save(long,out/'NATURAL_IMAGE_METRIC_DISTRIBUTIONS.csv.gz')
    return core,long


def aggregate_curves(core,long,out):
    tables=[];buildings=[]
    widths=['Q_mean','Q_median','Q_sd','Q_p10','Q_p90','Q_iqr','Q_mean_absolute_pair_difference']+[c+'_rate' for c in FLAGS]
    if 'V_floor_mean' in core:widths+=['V_floor_mean']
    for limit in [0,6,10,20,30]:
        a=core if not limit else core[(core.pool_n>=limit)&(core.k<=limit)]
        a=a.copy();a['panel']='all_available' if not limit else f'fixed_pool_N_ge_{limit}'
        for axis in ['difficulty','structure_opportunity']:
            keys=['condition','layer',axis,'k','panel']
            c=a.groupby(keys,dropna=False)[widths].mean().reset_index()
            support=a.groupby(keys,dropna=False).agg(images=('image','nunique'),buildings=('building','nunique'),prefixes=('prefixes','sum'),scored_prefixes=('scored','sum'),scored_images=('Q_mean','count')).reset_index()
            if 'V_floor_mean' in a:
                vc=a.groupby(keys,dropna=False).V_floor_mean.count().rename('V_observed_images').reset_index()
                support=support.merge(vc,on=keys)
            b=a.groupby(keys+['building'],dropna=False)[widths].mean().reset_index()
            bm=b.groupby(keys,dropna=False)[widths].mean().add_suffix('_building_equal').reset_index()
            bn=b.groupby(keys,dropna=False).agg(scored_buildings=('Q_mean','count')).reset_index()
            if 'V_floor_mean' in b:
                vc=b.groupby(keys,dropna=False).V_floor_mean.count().rename('V_observed_buildings').reset_index()
                bn=bn.merge(vc,on=keys)
            c=c.merge(support,on=keys).merge(bm,on=keys).merge(bn,on=keys)
            c['axis']=axis;c=c.rename(columns={axis:'stratum'});tables.append(c)
            b['axis']=axis;b=b.rename(columns={axis:'stratum'});buildings.append(b)
    save(pd.concat(tables,ignore_index=True),out/'NATURAL_DIFFICULTY_CURVES.csv')
    save(pd.concat(buildings,ignore_index=True),out/'NATURAL_BUILDING_CURVES.csv.gz')
    # Every component uses its own observed-image denominator.
    a=long.merge(core[META+['k','structure_opportunity']].drop_duplicates(),on=META+['k'],validate='many_to_one')
    metrics=[]
    for limit in [0,20]:
        z=a if not limit else a[(a.pool_n>=limit)&(a.k<=limit)]
        for axis in ['difficulty','structure_opportunity']:
            keys=['condition','layer',axis,'k','metric']
            s=z.groupby(keys,dropna=False).agg(images=('image','nunique'),observed_images=('mean','count'),observations=('count','sum'),mean=('mean','mean'),median_of_image_means=('mean','median'),mean_within_image_p10=('p10','mean'),mean_within_image_p90=('p90','mean'),mean_within_image_sd=('std','mean')).reset_index()
            b=z.groupby(keys+['building'],dropna=False)[['mean','p10','p90','std']].mean().reset_index()
            b=b.groupby(keys,dropna=False).agg(observed_buildings=('mean','count'),mean_building_equal=('mean','mean'),within_image_p10_building_equal=('p10','mean'),within_image_p90_building_equal=('p90','mean'),within_image_sd_building_equal=('std','mean')).reset_index()
            s=s.merge(b,on=keys)
            s['axis']=axis;s['panel']='all_available' if not limit else 'fixed_pool_N_ge_20';s=s.rename(columns={axis:'stratum'});metrics.append(s)
    save(pd.concat(metrics,ignore_index=True),out/'NATURAL_COMPONENT_CURVES.csv.gz')
    return pd.concat(tables,ignore_index=True)


def contrasts(d,core,out):
    allpaths=[];allimages=[]
    validmetrics=[m for m in METRICS if m in d]+FLAGS
    designs=[(1,3),(3,6),(6,10),(10,20),(20,30),(3,20),(3,'full'),(10,'full'),(20,'full')]
    for ka,kb in designs:
        a=d[d.k==ka]
        b=d[(d.k==d.pool_n)&d.k.gt(ka)] if kb=='full' else d[d.k==kb]
        keys=['pool_id','path_id']
        cols=['pool_id','path_id','k','team_key']+validmetrics
        p=a[cols].merge(b[cols],on=keys,suffixes=('_from','_to'),validate='one_to_one')
        if p.empty:continue
        p['interval']=f'{ka}_to_{kb}'
        for m in validmetrics:
            p[m+'_delta']=p[m+'_to'].astype(float)-p[m+'_from'].astype(float)
        p['two_scored']=p.B8L2_from.notna()&p.B8L2_to.notna()
        p['gained_score']=p.B8L2_from.isna()&p.B8L2_to.notna()
        p['lost_score']=p.B8L2_from.notna()&p.B8L2_to.isna()
        p['neither_scored']=p.B8L2_from.isna()&p.B8L2_to.isna()
        p['quality_improved']=np.where(p.two_scored,p.B8L2_delta>0,np.nan)
        p['quality_loss_gt5']=np.where(p.two_scored,p.B8L2_delta.lt(-5),np.nan)
        p['quality_loss_gt10']=np.where(p.two_scored,p.B8L2_delta.lt(-10),np.nan)
        allpaths.append(p)
        ac=core[core.k==ka]
        bc=core[(core.k==core.pool_n)&core.k.gt(ka)] if kb=='full' else core[core.k==kb]
        c=ac.merge(bc,on=META+['image_layer','difficulty_conditional','structure_opportunity','ref_turn5','ref_H','ref_short_edges'],suffixes=('_from','_to'),validate='one_to_one')
        c['interval']=f'{ka}_to_{kb}'
        for field in ['Q_mean','Q_p10','Q_sd','Q_mean_absolute_pair_difference']+[f+'_rate' for f in FLAGS]+(['V_floor_mean'] if 'V_floor_mean' in core else []):
            c[field+'_delta']=c[field+'_to']-c[field+'_from']
        pg=p.groupby('pool_id',sort=False).agg(paths=('path_id','size'),two_scored=('two_scored','sum'),gained_score=('gained_score','sum'),lost_score=('lost_score','sum'),neither_scored=('neither_scored','sum'),paired_Q_delta=('B8L2_delta','mean'),paired_Q_median_delta=('B8L2_delta','median'),paired_quality_improved_rate=('quality_improved','mean'),paired_quality_loss_gt5_rate=('quality_loss_gt5','mean'),paired_quality_loss_gt10_rate=('quality_loss_gt10','mean')).reset_index()
        c=c.merge(pg,on='pool_id',validate='one_to_one');allimages.append(c)
    paths=pd.concat(allpaths,ignore_index=True);images=pd.concat(allimages,ignore_index=True)
    save(paths,out/'NATURAL_PAIRED_PATH_INTERVALS.csv.gz')
    save(images,out/'NATURAL_IMAGE_INTERVALS.csv')
    summary=[];bybuilding=[]
    fields=['Q_mean_delta','Q_p10_delta','Q_sd_delta','Q_mean_absolute_pair_difference_delta','paired_Q_delta','paired_quality_loss_gt5_rate','paired_quality_loss_gt10_rate']+[f+'_rate_delta' for f in FLAGS]+(['V_floor_mean_delta'] if 'V_floor_mean_delta' in images else [])
    for axis in ['difficulty','structure_opportunity']:
        keys=['condition','layer',axis,'interval']
        for k,g in images.groupby(keys,dropna=False):
            entry=dict(zip(keys,k));q=g.Q_mean_delta.dropna()
            bb=g.groupby('building')[fields].mean()
            entry.update(images=len(g),quality_images=len(q),improved_images=int((q>0).sum()),declined_images=int((q<0).sum()),buildings=len(bb),quality_buildings=int(bb.Q_mean_delta.notna().sum()),improved_buildings=int(bb.Q_mean_delta.gt(0).sum()),paths=int(g.paths.sum()),two_scored_paths=int(g.two_scored.sum()),gained_score_paths=int(g.gained_score.sum()),lost_score_paths=int(g.lost_score.sum()),neither_scored_paths=int(g.neither_scored.sum()))
            if 'V_floor_mean_delta' in g:entry.update(V_observed_images=int(g.V_floor_mean_delta.notna().sum()),V_observed_buildings=int(bb.V_floor_mean_delta.notna().sum()))
            for f in fields:
                entry[f+'_image_mean']=g[f].mean();entry[f+'_building_mean']=bb[f].mean()
            entry['axis']=axis;entry['stratum']=entry.pop(axis);summary.append(entry)
            bb=bb.reset_index()
            for a,b in zip(keys,k):bb[a]=b
            bb['axis']=axis;bb=bb.rename(columns={axis:'stratum'});bybuilding.append(bb)
    save(pd.DataFrame(summary),out/'NATURAL_INTERVAL_SUMMARY.csv')
    save(pd.concat(bybuilding,ignore_index=True),out/'NATURAL_BUILDING_INTERVALS.csv')
    # Early and late intervals also share one fixed image panel in the main
    # curve; expose matching direction counts instead of mixing small pools
    # into 1->3 and then silently dropping them from 10->20.
    fixed=[]
    for axis in ['difficulty','structure_opportunity']:
        keys=['condition','layer',axis,'interval']
        for key,g in images[images.pool_n.ge(20)].groupby(keys,dropna=False):
            r=dict(zip(keys,key));q=g.Q_mean_delta.dropna();b=g.groupby('building')[fields].mean()
            r.update(images=len(g),quality_images=len(q),improved_images=int(q.gt(0).sum()),declined_images=int(q.lt(0).sum()),buildings=len(b),quality_buildings=int(b.Q_mean_delta.notna().sum()),improved_buildings=int(b.Q_mean_delta.gt(0).sum()),paths=int(g.paths.sum()),two_scored_paths=int(g.two_scored.sum()),gained_score_paths=int(g.gained_score.sum()),lost_score_paths=int(g.lost_score.sum()),neither_scored_paths=int(g.neither_scored.sum()))
            if 'V_floor_mean_delta' in g:r.update(V_observed_images=int(g.V_floor_mean_delta.notna().sum()),V_observed_buildings=int(b.V_floor_mean_delta.notna().sum()))
            for f in fields:r[f+'_image_mean']=g[f].mean();r[f+'_building_mean']=b[f].mean()
            r['axis']=axis;r['stratum']=r.pop(axis);r['panel']='fixed_pool_N_ge_20';fixed.append(r)
    save(pd.DataFrame(fixed),out/'NATURAL_FIXED_N20_INTERVAL_SUMMARY.csv')
    return paths,images


def attainments(d,core,out):
    results=[]
    for (pool,path),g in d[d.k.ge(1)].groupby(['pool_id','path_id'],sort=False):
        g=g.sort_values('k');N=int(g.pool_n.iloc[0]);meta={c:g.iloc[0][c] for c in META}
        for threshold in [80,90]:
            good=(g.B8L2>=threshold)&~g.score_unavailable
            hit=g.loc[good,'k'].min()
            hit_ge3=g.loc[good&g.k.ge(3),'k'].min()
            # A miss or unscorable output breaks sustained attainment; full tail
            # must be observed, and a threshold is not made absorbing at first hit.
            complete_path=np.array_equal(g.k.to_numpy(),np.arange(1,N+1))
            bad=g.loc[~good,'k'];sustained=(int(bad.max())+1 if len(bad) else 1) if bool(good.iloc[-1]) and complete_path else np.nan
            if pd.notna(sustained) and sustained>N:sustained=np.nan
            result=dict(**meta,path_id=path,Q_threshold=threshold,first_hit_k=hit,first_hit_k_ge3=hit_ge3,sustained_from_k=sustained,final_meets=bool(good.iloc[-1]),full_observed=int(g.k.max())==N,all_integer_prefixes_observed=complete_path)
            for basis in ['source','target']:
                t=basis+'_time_total_seconds'
                if t not in g:continue
                for role,k in [('first_hit',hit),('first_hit_ge3',hit_ge3),('sustained_from',sustained)]:
                    result[role+'_'+basis+'_recorded_seconds']=g.loc[g.k.eq(k),t].iloc[0] if pd.notna(k) else np.nan
            results.append(result)
    r=pd.DataFrame(results);save(r,out/'NATURAL_THRESHOLD_PATHS.csv.gz')
    keys=META+['Q_threshold']
    def ag(g):
        return pd.Series(dict(paths=len(g),ever_met_rate=g.first_hit_k.notna().mean(),ever_met_ge3_rate=g.first_hit_k_ge3.notna().mean(),full_meets_rate=g.final_meets.mean(),first_hit_median_if_met=g.first_hit_k.median(),first_hit_ge3_median_if_met=g.first_hit_k_ge3.median(),sustained_from_median_if_met=g.sustained_from_k.median(),sustained_by6_rate=g.sustained_from_k.le(6).mean(),sustained_by10_rate=g.sustained_from_k.le(10).mean(),sustained_by20_rate=g.sustained_from_k.le(20).mean()))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',FutureWarning);s=r.groupby(keys,dropna=False).apply(ag,include_groups=False).reset_index()
    save(s,out/'NATURAL_THRESHOLD_IMAGES.csv')
    # Image-first averages: a larger available pool or more sampled paths must
    # not turn a single picture into several independent observations.
    fields=[c for c in s if c.endswith('_rate') or c.endswith('_if_met')]
    tables=[]
    for limit in [0,20]:
        z=s if not limit else s[s.pool_n.ge(limit)]
        key=['condition','layer','difficulty','Q_threshold']
        a=z.groupby(key,dropna=False)[fields].mean().reset_index()
        counts=z.groupby(key,dropna=False).agg(images=('image','nunique'),buildings=('building','nunique'),paths=('paths','sum')).reset_index()
        b=z.groupby(key+['building'],dropna=False)[fields].mean().reset_index()
        b=b.groupby(key,dropna=False)[fields].mean().add_suffix('_building_equal').reset_index()
        a=a.merge(counts,on=key).merge(b,on=key);a['panel']='all_available' if not limit else 'fixed_pool_N_ge_20';tables.append(a)
    save(pd.concat(tables,ignore_index=True),out/'NATURAL_THRESHOLD_SUMMARY.csv')


def adjacent_transitions(d,out):
    """Describe all actual additions, including decreases and missing outputs."""
    x=d.sort_values(['pool_id','path_id','k']).copy()
    fields=[m for m in METRICS if m in x]+FLAGS
    previous=x.groupby(['pool_id','path_id'])[fields+['k','team_key']].shift(1)
    z=x[META+['path_id','k','team_key']].copy()
    z['k_previous']=previous.k;z['team_key_previous']=previous.team_key
    z['threshold_previous']=np.ceil(z.k_previous/2);z['threshold_current']=np.ceil(z.k/2)
    z['threshold_change']=z.threshold_current-z.threshold_previous
    for f in fields:
        z[f+'_previous']=previous[f]
        z[f+'_current']=x[f]
        z[f+'_change']=x[f].astype(float)-previous[f].astype(float)
    z=z[z.k_previous.notna()&z.k.sub(z.k_previous).eq(1)]
    z['both_scored']=z.B8L2_previous.notna()&z.B8L2_current.notna()
    z['quality_improves']=np.where(z.both_scored,z.B8L2_change.gt(0),np.nan)
    z['quality_loss_gt5']=np.where(z.both_scored,z.B8L2_change.lt(-5),np.nan)
    z['quality_loss_gt10']=np.where(z.both_scored,z.B8L2_change.lt(-10),np.nan)
    z['nodes_lost']=np.where(z.nodes_previous.notna()&z.nodes_current.notna(),z.nodes_change.lt(0),np.nan)
    z['became_unscorable']=(~z.score_unavailable_previous.astype(bool))&z.score_unavailable_current.astype(bool)
    z['became_scorable']=z.score_unavailable_previous.astype(bool)&(~z.score_unavailable_current.astype(bool))
    save(z,out/'NATURAL_ADJACENT_TRANSITIONS.csv.gz')
    # Exclude k<=3 from threshold contrast because the n=2 sorting policy
    # creates a different process event; leave these rows in the full table.
    ordinary=z[z.k.ge(4)&z.k.le(20)&z.pool_n.ge(20)]
    aggcols=['B8L2_change','D10_change','nodes_change','quality_improves','quality_loss_gt5','quality_loss_gt10','nodes_lost','became_unscorable','became_scorable']
    image=ordinary.groupby(META+['threshold_change'],dropna=False)[aggcols].mean().reset_index()
    save(image,out/'NATURAL_THRESHOLD_STEP_BY_IMAGE.csv')
    keys=['condition','layer','difficulty','threshold_change']
    summ=image.groupby(keys,dropna=False)[aggcols].mean().reset_index()
    counts=image.groupby(keys,dropna=False).agg(images=('image','nunique'),buildings=('building','nunique'),Q_observed_images=('B8L2_change','count')).reset_index()
    b=image.groupby(keys+['building'],dropna=False)[aggcols].mean().reset_index()
    save(b,out/'NATURAL_THRESHOLD_STEP_BY_BUILDING.csv')
    bm=b.groupby(keys,dropna=False)[aggcols].mean().add_suffix('_building_equal').reset_index()
    summ=summ.merge(counts,on=keys).merge(bm,on=keys);save(summ,out/'NATURAL_THRESHOLD_STEP_SUMMARY.csv')


def process_types(core,images,out,long):
    r=core[core.k==core.pool_n].copy()
    r=r.rename(columns={'Q_mean':'Q_full','Q_p10':'Q_full_p10','score_unavailable_rate':'full_unscorable_rate'})
    keep=META+['image_layer','difficulty_conditional','structure_opportunity','ref_turn5','ref_H','ref_short_edges','Q_full','full_unscorable_rate','unique_member_sets']
    r=r[keep]
    for interval,label in [('1_to_3','initial'),('3_to_6','early'),('10_to_20','middle'),('3_to_20','to20'),('3_to_full','whole')]:
        cols=['pool_id','Q_mean_delta','Q_p10_delta','Q_sd_delta','paired_quality_loss_gt5_rate']
        if 'V_floor_mean_delta' in images:cols.append('V_floor_mean_delta')
        z=images[images.interval==interval][cols].rename(columns={c:label+'_'+c for c in cols if c!='pool_id'})
        r=r.merge(z,on='pool_id',how='left',validate='one_to_one')
    geo=['nodes','reference_node_shortfall','floor_turn5','floor_turn_deficit5','floor_turn_extra5','floor_redundant_nodes5','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9','ref_top_pair_mean_deg','ref_bottom_pair_mean_deg','ref_top_pair_max_deg','ref_bottom_pair_max_deg','ref_assigned_pair_n','ref_unassigned_pair_n','candidate_unassigned_pair_n','S_bottom_deg','dir','Hmean','height_mean_ratio','omission','extension','iou_2d','IoU3D100']
    observed=long[long.metric.isin(geo)]
    for k,label in [(3,'at3'),(10,'at10'),(20,'at20'),('full','full')]:
        z=observed[observed.k.eq(observed.pool_n)] if k=='full' else observed[observed.k.eq(k)]
        z=z.pivot(index='pool_id',columns='metric',values='mean').add_prefix(label+'_').reset_index()
        r=r.merge(z,on='pool_id',how='left',validate='one_to_one')
    r['early_mean_gain_ge5']=r.early_Q_mean_delta.ge(5)
    r['initial_mean_gain_ge5']=r.initial_Q_mean_delta.ge(5)
    r['early_mean_loss_ge5']=r.early_Q_mean_delta.le(-5)
    r['middle_mean_change_within2']=r.middle_Q_mean_delta.abs().le(2)
    r['middle_Q_dispersion_decreases']=r.middle_Q_sd_delta.lt(0)
    r['middle_little_gain_but_score_dispersion_reduces']=r.middle_mean_change_within2&r.middle_Q_dispersion_decreases
    r['middle_nonfull_comparison']=r.pool_n.gt(20)
    if 'middle_V_floor_mean_delta' in r:
        r['middle_geometric_variation_observed']=r.middle_V_floor_mean_delta.notna()
        r['middle_floor_variation_decreases']=r.middle_V_floor_mean_delta.lt(0)
        r['middle_little_mean_gain_and_floor_variation_reduces']=r.middle_mean_change_within2&r.middle_floor_variation_decreases
        r['middle_nonfull_stable_lower_reference_Q']=r.middle_little_mean_gain_and_floor_variation_reduces&r.middle_nonfull_comparison&r.Q_full.lt(80)
    r['lower_reference_Q_full_lt80']=r.Q_full.lt(80)
    r['lower_reference_Q_full_lt60']=r.Q_full.lt(60)
    r['whole_mean_change_within2']=r.whole_Q_mean_delta.abs().le(2)
    r['whole_mean_loss_ge5']=r.whole_Q_mean_delta.le(-5)
    r['early_interval_observed']=r.early_Q_mean_delta.notna()
    r['initial_interval_observed']=r.initial_Q_mean_delta.notna()
    r['middle_interval_observed']=r.middle_Q_mean_delta.notna()
    r['to20_interval_observed']=r.to20_Q_mean_delta.notna()
    r['whole_interval_observed']=r.whole_Q_mean_delta.notna()
    save(r,out/'NATURAL_PROCESS_DESCRIPTORS.csv')
    common=r[r.pool_n.ge(20)].copy()
    save(common[common.initial_mean_gain_ge5|common.early_mean_gain_ge5],out/'NATURAL_EARLY_GAIN_GE5_N20_IMAGES.csv')
    if 'middle_nonfull_stable_lower_reference_Q' in common:
        save(common[common.middle_nonfull_stable_lower_reference_Q],out/'NATURAL_LATE_STABLE_LOW_REFERENCE_IMAGES.csv')
    if all(c in common for c in ['at10_floor_turn_deficit5','at20_floor_turn_deficit5','full_floor_turn_deficit5']):
        persistent=common.at10_floor_turn_deficit5.gt(0)&common.at20_floor_turn_deficit5.gt(0)&common.full_floor_turn_deficit5.gt(0)
        save(common[persistent],out/'NATURAL_PERSISTENT_TURN_COUNT_GAP_IMAGES.csv')
    # Nonexclusive descriptions, never post-hoc difficulty reclassification.
    flags=[c for c in r if pd.api.types.is_bool_dtype(r[c])]
    s=r.groupby(['condition','layer','difficulty'],dropna=False).agg(images=('image','nunique'),Q_full_observed=('Q_full','count'),Q_full_mean=('Q_full','mean'),Q_full_median=('Q_full','median')).reset_index()
    c=r.groupby(['condition','layer','difficulty'],dropna=False)[flags].sum().reset_index()
    s=s.merge(c,on=['condition','layer','difficulty']);save(s,out/'NATURAL_PROCESS_DESCRIPTOR_COUNTS.csv')
    return r


def relative_curves(core,out,caption):
    rows=[]
    pools=core[META].drop_duplicates()
    # A common fixed panel (all pools capable of k=20), every image contributes
    # the same ten relative positions; exact integer k is preserved per image.
    pools=pools[pools.pool_n>=20]
    for fraction in np.linspace(.1,1,10):
        target=pools.copy();target['k']=np.maximum(3,np.ceil(target.pool_n*fraction-1e-12).astype(int));target['pool_fraction_requested']=fraction
        z=target.merge(core,on=META+['k'],how='left',validate='one_to_one')
        z['pool_fraction_actual']=z.k/z.pool_n;rows.append(z)
    r=pd.concat(rows,ignore_index=True)
    save(r,out/'NATURAL_RELATIVE_POOL_IMAGE_CURVES.csv.gz')
    fields=['Q_mean','Q_p10','Q_p90','Q_sd','Q_mean_absolute_pair_difference','score_unavailable_rate']
    if 'V_floor_mean' in r:fields+=['V_floor_mean']
    keys=['condition','layer','difficulty','pool_fraction_requested']
    s=r.groupby(keys,dropna=False)[fields].mean().reset_index()
    support=r.groupby(keys,dropna=False).agg(images=('image','nunique'),buildings=('building','nunique'),scored_images=('Q_mean','count'),k_min=('k','min'),k_median=('k','median'),k_max=('k','max')).reset_index()
    if 'V_floor_mean' in r:
        vc=r.groupby(keys,dropna=False).V_floor_mean.count().rename('V_observed_images').reset_index()
        support=support.merge(vc,on=keys)
    b=r.groupby(keys+['building'],dropna=False)[fields].mean().reset_index()
    bm=b.groupby(keys,dropna=False)[fields].mean().add_suffix('_building_equal').reset_index()
    s=s.merge(support,on=keys).merge(bm,on=keys);save(s,out/'NATURAL_RELATIVE_POOL_CURVES.csv')
    fig,axs=plt.subplots(2,3,figsize=(15,8),sharex=True)
    colors={'简单':'#288b6d','中等':'#da9225','困难':'#a14c94'};names={'简单':'Easy','中等':'Moderate','困难':'Difficult'}
    for row,con in enumerate(['manual','semi']):
        z=s[s.layer.eq('ordinary_'+con)]
        for difficulty,g in z.groupby('difficulty'):
            c=colors.get(difficulty,'black');g=g.sort_values('pool_fraction_requested');x=g.pool_fraction_requested*100
            axs[row,0].plot(x,g.Q_mean,color=c,label=names.get(difficulty,difficulty),lw=2)
            axs[row,0].fill_between(x,g.Q_p10,g.Q_p90,color=c,alpha=.13)
            axs[row,1].plot(x,g.Q_sd,color=c,lw=2)
            axs[row,2].plot(x,100*g.score_unavailable_rate,color=c,lw=2)
        axs[row,0].set_ylabel(con.capitalize());axs[row,0].legend(fontsize=8)
        for ax in axs[row]:ax.grid(alpha=.22);ax.set_xlabel('Fraction of actual final pool (%)')
    axs[0,0].set_title('Scorable Q: image mean and average P10-P90')
    axs[0,1].set_title('Q dispersion (full-pool zero is mechanical)')
    axs[0,2].set_title('Unscorable outputs (%)')
    fig.suptitle('Complete process in each actual pool; fixed N >= 20 image panel\n'+caption,fontsize=12)
    fig.tight_layout(rect=[0,0,1,.93]);buf=io.BytesIO();fig.savefig(buf,format='png',dpi=170);(out/'NATURAL_FULL_POOL_PROGRESS.png').write_bytes(buf.getvalue());plt.close(fig)
    return s


def time_expectation(d,core,out):
    """Exact finite-population expected recorded time; not newly measured labor."""
    allrows=[];qtime=[]
    meta=core[META].drop_duplicates()
    for kind in ['source','target']:
        t=kind+'_time_total_seconds'
        if t not in d:continue
        total=d[d.k.eq(d.pool_n)].groupby('pool_id')[t].first().rename('full_pool_recorded_seconds').reset_index()
        total=total[total.full_pool_recorded_seconds.notna()]
        sample=d.groupby(['pool_id','k'])[t].agg(['count','mean','std']).rename(columns={'count':'observed_prefixes','mean':'sampled_mean_seconds','std':'sampled_sd_seconds'}).reset_index()
        v=meta.merge(total,on='pool_id',how='inner',validate='one_to_one').merge(sample,on='pool_id',validate='one_to_many')
        v['exact_expected_seconds']=v.k/v.pool_n*v.full_pool_recorded_seconds
        v['sample_minus_exact_seconds']=v.sampled_mean_seconds-v.exact_expected_seconds
        v['sample_relative_error']=v.sample_minus_exact_seconds/v.exact_expected_seconds
        v['time_basis']=kind;allrows.append(v)
        v=v[v.pool_n.ge(20)&v.k.le(20)]
        v=v.merge(core[['pool_id','k','Q_mean','Q_p10','score_unavailable_rate']],on=['pool_id','k'],validate='one_to_one')
        keys=['condition','layer','difficulty','k','time_basis']
        z=v.groupby(keys).agg(images=('image','nunique'),buildings=('building','nunique'),quality_images=('Q_mean','count'),Q_mean=('Q_mean','mean'),Q_p10=('Q_p10','mean'),unscorable_rate=('score_unavailable_rate','mean'),expected_recorded_seconds=('exact_expected_seconds','mean'),sampled_recorded_seconds=('sampled_mean_seconds','mean'),mean_absolute_mc_error_seconds=('sample_minus_exact_seconds',lambda x:x.abs().mean())).reset_index()
        b=v.groupby(keys+['building']).agg(Q_mean=('Q_mean','mean'),Q_p10=('Q_p10','mean'),unscorable_rate=('score_unavailable_rate','mean'),expected_recorded_seconds=('exact_expected_seconds','mean'),sampled_recorded_seconds=('sampled_mean_seconds','mean')).reset_index()
        b=b.groupby(keys)[['Q_mean','Q_p10','unscorable_rate','expected_recorded_seconds','sampled_recorded_seconds']].mean().add_suffix('_building_equal').reset_index()
        z=z.merge(b,on=keys)
        qtime.append(z)
    if not allrows:return
    r=pd.concat(allrows,ignore_index=True);s=pd.concat(qtime,ignore_index=True)
    save(r,out/'NATURAL_TIME_ANALYTIC_PER_POOL.csv.gz');save(s,out/'NATURAL_Q_TIME_FIXED_SUPPORT.csv')
    fig,axs=plt.subplots(1,2,figsize=(12,4.5))
    colors={'简单':'#288b6d','中等':'#da9225','困难':'#a14c94'};names={'简单':'Easy','中等':'Moderate','困难':'Difficult'}
    for ax,con in zip(axs,['manual','semi']):
        z=s[s.layer.eq('ordinary_'+con)&s.time_basis.eq('source')&s.k.ge(1)]
        for dif,g in z.groupby('difficulty'):
            g=g.sort_values('k');ax.plot(g.expected_recorded_seconds/60,g.Q_mean,color=colors.get(dif,'black'),label=names.get(dif,dif)+f' ({int(g.images.iloc[0])} images)',lw=2,marker='o',markersize=2.5)
            for k in [1,3,6,10,20]:
                h=g[g.k.eq(k)]
                if len(h):ax.annotate(str(k),(h.expected_recorded_seconds.iloc[0]/60,h.Q_mean.iloc[0]),fontsize=8)
        ax.set_title(con.capitalize());ax.set_xlabel('Exact expected cumulative source-recorded time (minutes)');ax.set_ylabel('Mean Q');ax.grid(alpha=.22);ax.legend(fontsize=8)
    fig.suptitle('Fixed N >= 20 pools with complete source time; labels are prefix sizes\nHistorical records, not a new production-time measurement',fontsize=11)
    fig.tight_layout(rect=[0,0,1,.90]);buf=io.BytesIO();fig.savefig(buf,format='png',dpi=170);(out/'NATURAL_Q_RECORDED_TIME.png').write_bytes(buf.getvalue());plt.close(fig)


def opportunity_explanation(intervals,out,raw_features):
    raw_features=Path(raw_features)
    if not raw_features.exists():return
    raw=pd.read_csv(raw_features)
    choose=['reference_reduced','turn_n','short_turn_edges','near_straight_nodes_5deg','omission','extension','unmatched_ref_9']
    raw=raw[raw.metric.isin(choose)].pivot(index='pool_id',columns='metric',values='mean').add_prefix('raw_').reset_index()
    a=intervals.merge(raw,on='pool_id',how='left',validate='many_to_one')
    rows=[]
    for fixed6 in [False,True]:
        z=a[a.ref_turn5.eq(6)] if fixed6 else a
        for key,g in z.groupby(['condition','layer','structure_opportunity','interval'],dropna=False):
            r=dict(zip(['condition','layer','structure_opportunity','interval'],key));q=g.Q_mean_delta.dropna()
            r.update(reference_complexity='fixed_six_turns' if fixed6 else 'all_turn_counts',images=len(g),buildings=g.building.nunique(),Q_observed_images=len(q),Q_improved_images=int(q.gt(0).sum()),Q_from=g.Q_mean_from.mean(),Q_to=g.Q_mean_to.mean(),Q_mean_delta=g.Q_mean_delta.mean(),Q_p10_delta=g.Q_p10_delta.mean(),Q_sd_from=g.Q_sd_from.mean(),Q_sd_to=g.Q_sd_to.mean(),unscorable_from=g.score_unavailable_rate_from.mean(),unscorable_to=g.score_unavailable_rate_to.mean())
            for c in [v for v in g if v.startswith('raw_')]:r[c]=g[c].mean();r[c+'_observed_images']=g[c].notna().sum()
            rows.append(r)
    save(pd.DataFrame(rows),out/'NATURAL_STRUCTURE_OPPORTUNITY_EXPLANATION.csv')
    save(a,out/'NATURAL_IMAGE_INTERVAL_RAW_STRUCTURE_LINK.csv.gz')


def plot_curves(summary,out,caption):
    colors={'简单':'#288b6d','中等':'#da9225','困难':'#a14c94','单列':'#397fc0'}
    english={'简单':'Easy','中等':'Moderate','困难':'Difficult','单列':'Doorway'}
    figs=[]
    fig,axs=plt.subplots(2,3,figsize=(15,8),sharex=True)
    for row,condition in enumerate(['manual','semi']):
        z=summary[(summary.condition==condition)&summary.layer.eq('ordinary_'+condition)&summary.axis.eq('difficulty')&summary.panel.eq('fixed_pool_N_ge_20')&summary.k.ge(1)]
        for difficulty,g in z.groupby('stratum'):
            g=g.sort_values('k');c=colors.get(difficulty,'black');label=english.get(difficulty,difficulty)+f' ({int(g.images.iloc[0])} images)'
            axs[row,0].plot(g.k,g.Q_mean,color=c,label=label,lw=2,marker='o',markersize=2.5)
            axs[row,0].fill_between(g.k,g.Q_p10,g.Q_p90,color=c,alpha=.13)
            axs[row,1].plot(g.k,g.Q_sd,color=c,label=label,lw=2,marker='o',markersize=2.5)
            failure=g.score_unavailable_rate.copy();failure[g.k.eq(2)]=np.nan
            axs[row,2].plot(g.k,100*failure,color=c,label=label,lw=2,marker='o',markersize=2.5)
        for ax in axs[row]:
            ax.grid(alpha=.22);ax.set_xlim(.75,20.25);ax.set_xticks([1,3,6,10,15,20]);ax.set_xlabel('Prefix size k');ax.axvspan(1.75,2.25,color='grey',alpha=.12)
        axs[row,0].set_ylabel(condition.capitalize());axs[row,0].legend(fontsize=8)
    axs[0,0].set_title('Mean Q and average within-image P10-P90')
    axs[0,1].set_title('Within-image Q standard deviation')
    axs[0,2].set_title('Unscorable output rate (%)')
    fig.suptitle('Natural mixing: fixed N >= 20 image panel; k=2 sorting deferred (gap)\n'+caption,fontsize=13)
    fig.tight_layout(rect=[0,0,1,.93]);buf=io.BytesIO();fig.savefig(buf,format='png',dpi=170);(out/'NATURAL_FIXED_PANEL_CURVES.png').write_bytes(buf.getvalue());plt.close(fig)
    fig,axs=plt.subplots(1,3,figsize=(15,4))
    z=summary[(summary.layer=='doorway_manual')&summary.axis.eq('difficulty')&summary.panel.eq('fixed_pool_N_ge_20')&summary.k.ge(1)]
    if len(z):
        z=z.sort_values('k');axs[0].plot(z.k,z.Q_mean,lw=2,marker='o',markersize=2.5);axs[0].fill_between(z.k,z.Q_p10,z.Q_p90,alpha=.2)
        failure=z.score_unavailable_rate.copy();failure[z.k.eq(2)]=np.nan
        axs[1].plot(z.k,z.Q_sd,lw=2,marker='o',markersize=2.5);axs[2].plot(z.k,100*failure,lw=2,marker='o',markersize=2.5)
        for ax in axs:ax.grid(alpha=.22);ax.set_xlabel('Prefix size k');ax.set_xlim(.75,20.25);ax.set_xticks([1,3,6,10,15,20]);ax.axvspan(1.75,2.25,color='grey',alpha=.12)
        axs[0].set_title('Doorway Manual: Q');axs[1].set_title('Q standard deviation');axs[2].set_title('Unscorable rate (%)')
        fig.suptitle(caption+'; k=2 sorting deferred (gap)');fig.tight_layout();buf=io.BytesIO();fig.savefig(buf,format='png',dpi=170);(out/'NATURAL_DOORWAY_CURVES.png').write_bytes(buf.getvalue())
    plt.close(fig)


def main(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    d=normalize(args.prefix,args.annotations)
    core,long=image_curves(d,out)
    if args.geometry_variation:
        v=pd.read_csv(args.geometry_variation)
        if 'policy' in v:v=v[v.policy.eq('natural_random')].copy()
        v=v[['pool_id','k']+[c for c in v if c not in core and c not in ['pool_id','k']]]
        core=core.merge(v,on=['pool_id','k'],how='left',validate='one_to_one');save(core,out/'NATURAL_IMAGE_CURVES.csv.gz')
    summary=aggregate_curves(core,long,out)
    paths,intervals=contrasts(d,core,out)
    attainments(d,core,out);desc=process_types(core,intervals,out,long)
    adjacent_transitions(d,out)
    plot_curves(summary,out,args.caption.split(';')[0])
    relative_curves(core,out,args.caption)
    time_expectation(d,core,out)
    raw_features=args.raw_pool_features or str(Path(args.annotations).parent/'RAW_POOL_FEATURE_SUMMARY.csv')
    opportunity_explanation(intervals,out,raw_features)
    meta={'source':str(args.prefix),'data_version':'v2','prefixes':len(d),'unique_teams':d.team_key.nunique(),'pools':d.pool_id.nunique(),'images':d.image.nunique(),'paths':d.path_id.nunique(),'path_count_per_pool':d.groupby('pool_id').path_id.nunique().value_counts().to_dict(),'conditions':d.groupby('condition').pool_id.nunique().to_dict(),'stage':args.caption,'new_fusion_by_this_aggregation':0,'two_person_deferred_prefixes':int(d.sorting_deferred.sum()),'quality_valid_prefixes':int(d.B8L2.notna().sum()),'plots_exclude_k2_because_contract_deferred':True}
    (out/'AGGREGATION_RECEIPT.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(meta,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--annotations',required=True);p.add_argument('--out',required=True);p.add_argument('--caption',default='V2 full-pool natural permutations');p.add_argument('--geometry-variation');p.add_argument('--raw-pool-features')
    main(p.parse_args())
