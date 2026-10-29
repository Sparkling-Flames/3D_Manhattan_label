#!/usr/bin/env python3
"""Reuse exact raw-answer geometry; no fusion or Q-based parameter selection."""
import argparse, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from refit_v21_structure_audit import save_csv, save_json

METRICS=['geometry_pair_angle','geometry_top_angle','geometry_bottom_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance','turn_difference','short_edge_difference','redundancy_difference','height_log_difference','azimuth_difference_deg_9','top_difference_deg_9','bottom_difference_deg_9','unmatched_fraction_9']

def summarize_panel(g,lm,common,support,subset):
    """Exact existing class-equal formula, loaded pairs avoid Shapely dependency."""
    aa=g.worker_a.map(lm);bb=g.worker_b.map(lm)
    mask=aa.notna()&bb.notna()
    if support=='common45_known':mask &=g.worker_a.isin(common)&g.worker_b.isin(common)
    if subset=='same_corner_count':mask &=g.same_corner_count
    z=g.loc[mask];aa=aa[mask];bb=bb[mask]
    within=aa.eq(bb).to_numpy();cross=~within
    base={'member_n':len(set(z.worker_a)|set(z.worker_b)),'all_pair_n':len(z),'within_pair_n':int(within.sum()),'cross_pair_n':int(cross.sum())}
    if within.sum()<4 or cross.sum()<4:return None,{**base,'reason':'fewer_than4_within_or_cross_raw_pairs'}
    data=z[METRICS].to_numpy(float);x=aa.to_numpy();y=bb.to_numpy()
    pairkeys=np.array(['|'.join(sorted([a,b])) for a,b in zip(x,y)])
    wk=np.unique(x[within]);ck=np.unique(pairkeys[cross])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        w=np.nanmean(np.vstack([np.nanmean(data[within&(x==cl)],axis=0) for cl in wk]),axis=0)
        c=np.nanmean(np.vstack([np.nanmean(data[cross&(pairkeys==cl)],axis=0) for cl in ck]),axis=0)
    row={**base,'within_class_n':len(wk),'cross_class_pair_n':len(ck)}
    for j,m in enumerate(METRICS):
        row[m+'_within']=w[j];row[m+'_cross']=c[j];row[m+'_gap']=c[j]-w[j]
        row[m+'_within_finite_pairs']=int(np.isfinite(data[within,j]).sum());row[m+'_cross_finite_pairs']=int(np.isfinite(data[cross,j]).sum())
    return row,None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--pairs-source',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True);a=ap.parse_args()
    old=pd.read_csv(a.source/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    new=pd.read_csv(a.audit/'NEW_LABELS_ALL_LOBO.csv.gz')
    baselines=['DSTRUCT_K2','DSTRUCT_K3','DSTRUCT_K4','TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4','OPPSTRUCT_K2','OPPSTRUCT_K3','OPPSTRUCT_K4','OPPJOINT_K3','OPPJOINT_K4','Q_MEDIAN2']
    labs=pd.concat([new[~new.family.eq('REPRO_TARGET_DSTRUCT')],old[old.method.isin(baselines)]],ignore_index=True)
    labs=labs[labs.heldout_building.ne('ALL')&labs.known]
    methods=sorted(labs.method.unique());maps={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in labs.groupby(['method','heldout_building'])}
    common={}
    for b in sorted(labs.heldout_building.unique()):
        prior=[set(z.loc[z.known,'worker_id']) for _,z in old[old.heldout_building.eq(b)].groupby('method')]
        common[b]=set.intersection(*prior,*[set(maps[(m,b)]) for m in methods])
    save_csv(pd.DataFrame([dict(heldout_building=b,common_workers='|'.join(sorted(ws)),worker_n=len(ws)) for b,ws in common.items()]),a.audit/'RAW_GEOMETRY_COMMON_WORKERS.csv')
    pairs=pd.read_csv(a.pairs_source/'raw_similarity/RAW_PAIR_DISTANCES.csv.gz',low_memory=False)
    pairs=pairs[pairs.layer.eq('ordinary_manual')].copy()
    meta=['pool_id','image_id','image','building','condition','layer','scope','official_difficulty','geometric_challenge','pool_n']
    rows=[];missing=[]
    groups=list(pairs.groupby('pool_id',sort=False))
    for method in methods:
        for pid,g in groups:
            b=g.building.iloc[0];info={x:g.iloc[0][x] for x in meta}
            for support in ('native','common_old45_new'):
                for subset in ('all_pairs','same_corner_count'):
                    core_support='common45_known' if support=='common_old45_new' else 'method_all_known'
                    row,miss=summarize_panel(g,maps[(method,b)],common[b],core_support,subset)
                    base=dict(method=method,support=support,subset=subset,**info)
                    if row:rows.append({**base,**row})
                    else:missing.append({**base,**miss})
        save_csv(pd.DataFrame([r for r in rows if r['method']==method]),a.audit/'raw_geometry_shards'/(method+'.csv.gz'))
        print('raw geometry',method,flush=True)
    table=pd.DataFrame(rows);save_csv(table,a.audit/'RAW_GEOMETRY_BY_POOL.csv.gz');save_csv(pd.DataFrame(missing),a.audit/'RAW_GEOMETRY_UNESTIMABLE.csv.gz')
    summary=[];images=[]
    keys=['method','support','subset']
    for key,g in table.groupby(keys):
        for scope in ('ALL_TARGETS','primary','other_admitted'):
            z=g if scope=='ALL_TARGETS' else g[g.scope.eq(scope)]
            if z.empty:continue
            for difficulty in ('ALL','简单','中等','困难','未分级'):
                dz=z if difficulty=='ALL' else z[z.official_difficulty.eq(difficulty)]
                if dz.empty:continue
                cols=[m+'_'+v for m in METRICS for v in ('within','cross','gap')]
                im=dz.groupby(['image_id','image','building'])[cols].mean().reset_index()
                for k,v in zip(keys,key):im[k]=v
                im['scope_summary']=scope;im['difficulty_summary']=difficulty;images.append(im)
                for metric in METRICS:
                    zz=im.dropna(subset=[metric+'_within',metric+'_cross'])
                    if zz.empty:continue
                    bs=zz.groupby('building')[[metric+'_'+v for v in ('within','cross','gap')]].mean()
                    gap=zz[metric+'_gap'];bg=bs[metric+'_gap']
                    r=dict(zip(keys,key));r.update(scope_summary=scope,difficulty_summary=difficulty,metric=metric,images=len(zz),buildings=zz.building.nunique(),within=zz[metric+'_within'].mean(),cross=zz[metric+'_cross'].mean(),gap=gap.mean(),positive_gap_images=int(gap.gt(1e-10).sum()),negative_gap_images=int(gap.lt(-1e-10).sum()),nearzero_gap_images=int(gap.abs().le(1e-10).sum()),gap_p10=gap.quantile(.1),gap_p25=gap.quantile(.25),gap_median=gap.median(),gap_p75=gap.quantile(.75),gap_p90=gap.quantile(.9),building_within=bs[metric+'_within'].mean(),building_cross=bs[metric+'_cross'].mean(),building_gap=bg.mean(),positive_gap_buildings=int(bg.gt(1e-10).sum()))
                    summary.append(r)
    save_csv(pd.DataFrame(summary),a.audit/'RAW_GEOMETRY_SUMMARY.csv')
    allim=pd.concat(images,ignore_index=True);save_csv(allim,a.audit/'RAW_GEOMETRY_BY_IMAGE.csv.gz')
    paired=[]
    # Same raw people, exact same image/target pools, each candidate against K3.
    t=table[table.support.eq('common_old45_new')]
    base=t[t.method.eq('TARGET_DSTRUCT_K3')]
    for method,g in t.groupby('method'):
        if method=='TARGET_DSTRUCT_K3':continue
        merged=g.merge(base,on=['pool_id','subset'],suffixes=('_candidate','_baseline'),validate='one_to_one')
        for metric in METRICS:
            z=merged.dropna(subset=[metric+'_gap_candidate',metric+'_gap_baseline'])
            for subset,d in z.groupby('subset'):
                v=d.groupby(['image_id_candidate','building_candidate'])[[metric+'_gap_candidate',metric+'_gap_baseline']].mean()
                dif=v[metric+'_gap_candidate']-v[metric+'_gap_baseline'];bs=dif.groupby(level='building_candidate').mean()
                paired.append(dict(method=method,baseline='TARGET_DSTRUCT_K3',subset=subset,metric=metric,common_images=len(v),common_buildings=v.index.get_level_values('building_candidate').nunique(),candidate_gap=v[metric+'_gap_candidate'].mean(),baseline_gap=v[metric+'_gap_baseline'].mean(),gap_gain=dif.mean(),gap_gain_median=dif.median(),gain_images=int(dif.gt(1e-10).sum()),loss_images=int(dif.lt(-1e-10).sum()),nearzero_images=int(dif.abs().le(1e-10).sum()),building_gap_gain=bs.mean(),gain_buildings=int(bs.gt(1e-10).sum())))
    save_csv(pd.DataFrame(paired),a.audit/'RAW_GEOMETRY_PAIRED_VS_TARGET_K3.csv')
    existing=pd.read_csv(a.pairs_source/'raw_similarity/RAW_CLASS_DISTANCE_BY_POOL.csv.gz',low_memory=False)
    existing=existing[existing.method.isin(baselines)&existing.layer.eq('ordinary_manual')].copy()
    existing['support']=existing.support.map({'method_all_known':'native','common45_known':'common_old45_new'})
    scalar=[m+'_'+v for m in METRICS for v in ('within','cross','gap')]
    keys=['method','pool_id','support','subset']
    parity=table[table.method.isin(baselines)].merge(existing[keys+scalar],on=keys,suffixes=('_new','_old'),how='outer',indicator=True,validate='one_to_one')
    assert parity._merge.eq('both').all()
    errs={}
    for c in scalar:
        x=parity[c+'_new'].to_numpy();y=parity[c+'_old'].to_numpy()
        assert np.array_equal(np.isnan(x),np.isnan(y)),c
        diff=np.abs(x-y);errs[c]=float(np.nanmax(diff)) if np.isfinite(diff).any() else 0.
    assert max(errs.values())<1e-9,errs
    save_json(dict(rows=len(parity),baselines=len(baselines),same_estimable_rows=True,same_missingness=True,max_absolute_error=max(errs.values()),per_metric_error=errs),a.audit/'RAW_GEOMETRY_EXISTING_BASELINE_PARITY.json')
    save_json(dict(methods=len(methods),ordinary_manual_pairs=len(pairs),ordinary_manual_pools=pairs.pool_id.nunique(),source_pair_reused=True,new_geometry=False,new_fusion=False,Q_used=False,T_used=False,method='Exact old raw spherical Hungarian and floor overlap pairs; class and unordered class-pair equal weighting; >=4 within and >=4 cross pairs; targets equal within image, separate image and building means',common_support='intersection of all old45 and all new labels; exact worker IDs saved',interpretation='Heldout-building descriptive separation, not supervised predictive accuracy; same-point-count restriction holds point count fixed but does not equalize all complexity'),a.audit/'RAW_GEOMETRY_RECEIPT.json')

if __name__=='__main__':main()
