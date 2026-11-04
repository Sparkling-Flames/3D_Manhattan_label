#!/usr/bin/env python3
"""Frozen-label, same-target original-answer profiles; no fusion, score, or fit."""
from pathlib import Path
from itertools import combinations
import hashlib
import json
import gzip
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = OUT.parent / 'basis'
CUR = 'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/'
HEAD = '48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
METHODS = ['RFUSE_GEOM_K2','OPPJOINT_K3','OPPJOINT_K4']
INPUTS = [CUR+'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz', 'research/data/releases/v2.1/quality_records.csv', str((BASE/'WORKER_LABELS_ALL_LOBO.csv.gz').relative_to(ROOT)), CUR+'ANALYSIS_RECORDS.json']
RAW_METRICS = ['B8L2','D10','turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9','matched_top_bias_deg','matched_bottom_bias_deg','log_area_ratio','log_height','bottom_bias_9','omission','extension','matched_horizontal_bias_deg','matched_boundary_abs_deg','matched_pair_fraction']
COMPONENTS = ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100']
TIME_METRICS = ['record_time_seconds','record_log_time']
GROUP = ['method','condition','scope','source_stratum','metric']
POOL_META = ['pool_id','image','image_id','building','reference_id','reference_version','official_difficulty']

def save(df,name):
    b=df.to_csv(index=False).encode('utf-8-sig')
    if name.endswith('.gz'):b=gzip.compress(b,mtime=0)
    (OUT/name).write_bytes(b)

def wquantile(values,weights,q):
    order=np.argsort(values)
    x=np.asarray(values)[order];w=np.asarray(weights)[order]
    return float(x[min(np.searchsorted(np.cumsum(w),q*w.sum(),side='left'),len(x)-1)])

def metric_views(d):
    for metric in RAW_METRICS+COMPONENTS+TIME_METRICS:
        z=d[np.isfinite(pd.to_numeric(d[metric],errors='coerce'))].copy()
        z['metric']=metric;z['value']=z[metric].astype(float)
        if metric in TIME_METRICS:
            z['source_stratum']=z.origin.astype(str)+'|'+z.time_source.astype(str)
            yield z
        else:
            z['source_stratum']='all_origins'
            yield z
            for origin,g in z.groupby('origin'):
                g=g.copy();g['source_stratum']='origin='+str(origin)
                yield g

def summary(group,value='delta'):
    x=group[value].to_numpy(float)
    buildings=group.groupby('building')[value].mean()
    return dict(n_images=group.image_id.nunique(),n_buildings=group.building.nunique(),image_equal_mean=float(np.mean(x)),building_equal_mean=float(buildings.mean()),image_median=float(np.median(x)),image_p10=float(np.quantile(x,.1)),image_p25=float(np.quantile(x,.25)),image_p75=float(np.quantile(x,.75)),image_p90=float(np.quantile(x,.9)),positive_images=int(np.sum(x>1e-12)),negative_images=int(np.sum(x< -1e-12)),zero_images=int(np.sum(abs(x)<=1e-12)),positive_fraction=float(np.mean(x>1e-12)))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    raw=pd.read_csv(ROOT/INPUTS[0],low_memory=False)
    raw=raw[raw.layer.isin(['ordinary_manual','ordinary_semi'])].copy()
    assert raw.object_id.is_unique
    q=pd.read_csv(ROOT/INPUTS[1],low_memory=False)
    keys=['object_id','reference_id','reference_version']
    primary=raw[raw.scope.eq('primary')].merge(q[keys+['B8L2','D10']+COMPONENTS],on=keys,how='left',validate='one_to_one',indicator=True,suffixes=('','_q'))
    assert primary._merge.eq('both').all()
    for m in ['B8L2','D10']:
        assert np.allclose(primary[m],primary[m+'_q'],equal_nan=True,atol=1e-9)
    primary=primary.drop(columns=['_merge','B8L2_q','D10_q'])
    oq=pd.DataFrame(json.loads((ROOT/INPUTS[3]).read_text(encoding='utf-8-sig')))
    other=raw[raw.scope.ne('primary')].merge(oq[keys+['B8L2','D10']+COMPONENTS],on=keys,how='left',validate='one_to_one',indicator=True,suffixes=('','_q'))
    assert other._merge.eq('both').all()
    for m in ['B8L2','D10']:
        assert np.allclose(other[m],other[m+'_q'],equal_nan=True,atol=1e-9)
    other=other.drop(columns=['_merge','B8L2_q','D10_q'])
    raw=pd.concat([primary,other],ignore_index=True)
    raw['record_time_seconds']=raw.source_active_time_seconds.where(raw.source_active_time_seconds.gt(0))
    raw['record_log_time']=np.log(raw.record_time_seconds)
    labels=pd.read_csv(ROOT/INPUTS[2],low_memory=False)
    labels=labels[labels.method.isin(METHODS)&labels.heldout_building.ne('ALL')]
    d=raw.merge(labels[['method','worker_id','heldout_building','class_id','known','missing_reason','class_order_basis']],left_on=['worker_id','building'],right_on=['worker_id','heldout_building'],how='inner',validate='many_to_many')
    assert len(d)==len(raw)*len(METHODS)
    assert not d.duplicated(['method','object_id']).any()
    d['analysis_support']='ordinary_scored_raw_inventory'
    d['time_interpretation']=np.where(d.scope.eq('primary'),'recorded source labor for annotation task','recorded labor for original task; not target-specific labor')
    save(d,'ORIGINAL_ANSWERS_WITH_LOBO_LABELS.csv.gz')
    coverage=d.groupby(['method','condition','scope','class_id'],dropna=False).agg(records=('object_id','size'),workers=('worker_id','nunique'),images=('image_id','nunique'),buildings=('building','nunique'),targets=('reference_id','nunique'),Q_finite=('B8L2',lambda s:int(s.notna().sum())),positive_T=('record_time_seconds',lambda s:int(s.notna().sum()))).reset_index()
    save(coverage,'CLASS_COVERAGE.csv')
    known=d[d.known].copy()
    target_frames=[];profile_rows=[];response_frames=[]
    for z in metric_views(known):
        # One worker normally has one answer in a pool; keep worker-first rule explicit.
        wg=GROUP+POOL_META+['class_id','worker_id']
        w=z.groupby(wg,dropna=False).value.mean().reset_index()
        t=w.groupby(GROUP+POOL_META+['class_id'],dropna=False).agg(value=('value','mean'),workers=('worker_id','nunique'),within_class_median=('value','median'),within_class_p10=('value',lambda s:s.quantile(.1)),within_class_p90=('value',lambda s:s.quantile(.9))).reset_index()
        target_frames.append(t)
        for difficulty in ['ALL','简单','中等','困难']:
            sw=w if difficulty=='ALL' else w[w.official_difficulty.eq(difficulty)]
            for key,g in sw.groupby(GROUP+['class_id'],dropna=False):
                tar=g.groupby(['building','image_id','pool_id']).value.mean().reset_index()
                im=tar.groupby(['building','image_id']).value.mean().reset_index()
                b=im.groupby('building').value.mean()
                weight=(1/g.groupby('pool_id').worker_id.transform('size')/g.groupby('image_id').pool_id.transform('nunique')/g.groupby('building').image_id.transform('nunique')/g.building.nunique())
                row=dict(zip(GROUP+['class_id'],key));row.update(difficulty=difficulty,worker_target_records=len(g),workers=g.worker_id.nunique(),targets=g.pool_id.nunique(),n_images=len(im),n_buildings=len(b),image_equal_mean=float(im.value.mean()),building_equal_mean=float(b.mean()),weighted_individual_p10=wquantile(g.value,weight,.1),weighted_individual_p25=wquantile(g.value,weight,.25),weighted_individual_median=wquantile(g.value,weight,.5),weighted_individual_p75=wquantile(g.value,weight,.75),weighted_individual_p90=wquantile(g.value,weight,.9),class_image_p10=float(im.value.quantile(.1)),class_image_p90=float(im.value.quantile(.9)))
                profile_rows.append(row)
        # Hard minus easy on identical people within each held-out building.
        ix=GROUP+['building','class_id','worker_id','official_difficulty']
        pi=w.groupby(ix+['image_id']).value.mean().reset_index()
        pw=pi.groupby(ix).agg(value=('value','mean'),n_images=('image_id','nunique')).reset_index()
        a=pw[pw.official_difficulty.eq('简单')].drop(columns='official_difficulty')
        b=pw[pw.official_difficulty.eq('困难')].drop(columns='official_difficulty')
        common=a.merge(b,on=GROUP+['building','class_id','worker_id'],suffixes=('_easy','_hard'),validate='one_to_one')
        common['hard_minus_easy']=common.value_hard-common.value_easy
        response_frames.append(common)
    target=pd.concat(target_frames,ignore_index=True)
    profiles=pd.DataFrame(profile_rows)
    responses=pd.concat(response_frames,ignore_index=True)
    save(target,'CLASS_TARGET_METRICS.csv.gz')
    save(profiles,'CLASS_ORIGINAL_PROFILE_SUMMARY.csv')
    save(responses,'DIFFICULTY_SAME_WORKER_BUILDING.csv.gz')

    pair_frames=[]
    for (method,condition,scope,source,metric),g in target.groupby(GROUP,dropna=False):
        for ca,cb in combinations(sorted(g.class_id.unique()),2):
            a=g[g.class_id.eq(ca)];b=g[g.class_id.eq(cb)]
            p=a.merge(b,on=GROUP+POOL_META,suffixes=('_A','_B'),validate='one_to_one')
            p['class_A']=ca;p['class_B']=cb;p['delta']=p.value_B-p.value_A
            pair_frames.append(p[GROUP+POOL_META+['class_A','class_B','value_A','value_B','workers_A','workers_B','delta']])
    pairs=pd.concat(pair_frames,ignore_index=True)
    save(pairs,'SAME_TARGET_CLASS_PAIRS.csv.gz')
    pairkeys=GROUP+['class_A','class_B']
    image=pairs.groupby(pairkeys+['building','image','image_id','official_difficulty'],dropna=False).agg(delta=('delta','mean'),value_A=('value_A','mean'),value_B=('value_B','mean'),targets=('pool_id','nunique'),min_workers_A=('workers_A','min'),min_workers_B=('workers_B','min')).reset_index()
    save(image,'SAME_IMAGE_CLASS_PAIRS.csv.gz')
    summ=[]
    for difficulty in ['ALL','简单','中等','困难']:
        sub=image if difficulty=='ALL' else image[image.official_difficulty.eq(difficulty)]
        for key,g in sub.groupby(pairkeys,dropna=False):
            row=dict(zip(pairkeys,key));row.update(difficulty=difficulty,**summary(g),mean_A=float(g.value_A.mean()),mean_B=float(g.value_B.mean()),targets=int(g.targets.sum()),min_class_A_workers=int(g.min_workers_A.min()),min_class_B_workers=int(g.min_workers_B.min()))
            if row['metric']=='record_log_time':
                row['image_equal_geometric_time_ratio']=float(np.exp(row['image_equal_mean']))
                row['building_equal_geometric_time_ratio']=float(np.exp(row['building_equal_mean']))
            summ.append(row)
    summary_table=pd.DataFrame(summ)
    save(summary_table,'SAME_IMAGE_PAIR_SUMMARY.csv')
    building=image.groupby(pairkeys+['building'],dropna=False).agg(delta=('delta','mean'),images=('image_id','nunique')).reset_index()
    save(building,'SAME_BUILDING_PAIR_SUMMARY.csv')

    rs=[];rps=[]
    rb=responses.groupby(GROUP+['building','class_id'],dropna=False).agg(hard_minus_easy=('hard_minus_easy','mean'),workers=('worker_id','nunique')).reset_index()
    for key,g in rb.groupby(GROUP+['class_id'],dropna=False):
        row=dict(zip(GROUP+['class_id'],key));row.update(n_buildings=len(g),worker_building_support=int(g.workers.sum()),building_equal_hard_minus_easy=float(g.hard_minus_easy.mean()),building_median=float(g.hard_minus_easy.median()),building_p10=float(g.hard_minus_easy.quantile(.1)),building_p90=float(g.hard_minus_easy.quantile(.9)),positive_buildings=int(g.hard_minus_easy.gt(1e-12).sum()))
        rs.append(row)
    for key,g in rb.groupby(GROUP,dropna=False):
        for ca,cb in combinations(sorted(g.class_id.unique()),2):
            p=g[g.class_id.eq(ca)].merge(g[g.class_id.eq(cb)],on=GROUP+['building'],suffixes=('_A','_B'),validate='one_to_one')
            if p.empty:continue
            delta=p.hard_minus_easy_B-p.hard_minus_easy_A
            row=dict(zip(GROUP,key));row.update(class_A=ca,class_B=cb,n_buildings=len(p),building_equal_response_difference=float(delta.mean()),building_median=float(delta.median()),building_p10=float(delta.quantile(.1)),building_p90=float(delta.quantile(.9)),positive_buildings=int(delta.gt(1e-12).sum()),workers_buildings_A=int(p.workers_A.sum()),workers_buildings_B=int(p.workers_B.sum()))
            rps.append(row)
    save(pd.DataFrame(rs),'DIFFICULTY_RESPONSE_CLASS_SUMMARY.csv')
    save(pd.DataFrame(rps),'DIFFICULTY_RESPONSE_PAIR_SUMMARY.csv')

    # Equal-count common support for every class in each method, alongside pairwise support.
    all_class=[]
    for key,g in target.groupby(GROUP,dropna=False):
        expected=int(key[0][-1])
        pools=g.groupby('pool_id').class_id.nunique()
        eligible_pools=pools[pools.eq(expected)].index
        c=g[g.pool_id.isin(eligible_pools)].copy()
        if c.empty:continue
        ims=c.groupby(GROUP+['class_id','building','image_id','official_difficulty'],dropna=False).value.mean().reset_index()
        for difficulty in ['ALL','简单','中等','困难']:
            sub=ims if difficulty=='ALL' else ims[ims.official_difficulty.eq(difficulty)]
            for cl,h in sub.groupby('class_id'):
                row=dict(zip(GROUP,key));row.update(class_id=cl,difficulty=difficulty,all_classes_required=expected,n_images=h.image_id.nunique(),n_buildings=h.building.nunique(),image_equal_mean=float(h.value.mean()),building_equal_mean=float(h.groupby('building').value.mean().mean()))
                all_class.append(row)
    save(pd.DataFrame(all_class),'ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv')

    checks=dict(frozen_commit=HEAD,source_rows=len(raw),ordinary_manual_primary=int((raw.layer.eq('ordinary_manual')&raw.scope.eq('primary')).sum()),ordinary_manual_other=int((raw.layer.eq('ordinary_manual')&raw.scope.ne('primary')).sum()),ordinary_semi_primary=int((raw.layer.eq('ordinary_semi')&raw.scope.eq('primary')).sum()),ordinary_semi_other=int((raw.layer.eq('ordinary_semi')&raw.scope.ne('primary')).sum()),primary_exact_object_reference_version_component_matches=len(primary),other_exact_object_reference_version_component_matches=len(other),primary_Q_check='allclose within 1e-9',other_Q_check='allclose within 1e-9',other_primary_components_borrowed=0,label_rows_joined=len(d),missing_label_rows=int(d.class_id.isna().sum()),known_class_original_rows=len(known),unknown_retained_in_coverage=int((~d.known).sum()),source_positive_time_only=True,time_sources_separate=True,heldout_building_equals_target_building=bool(d.heldout_building.eq(d.building).all()),new_fusion=0,new_scoring=0,new_classification_fit=0,summary_rows=len(summary_table),metric_specific_support=True)
    assert checks['missing_label_rows']==0
    assert checks['heldout_building_equals_target_building']
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest=[]
    for p in INPUTS:
        b=(ROOT/p).read_bytes();manifest.append(dict(path=p,commit=HEAD if not p.startswith('research/workers/current_class_interpretation') else 'local_derived_frozen_HEAD',bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    save(pd.DataFrame(manifest),'INPUT_MANIFEST.csv')
    print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
