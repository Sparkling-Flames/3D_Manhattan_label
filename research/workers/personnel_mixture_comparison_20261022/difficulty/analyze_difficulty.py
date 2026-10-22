#!/usr/bin/env python3
"""New difficulty-conditioned raw-answer analysis; frozen v2 inputs, no fusion.

Uses published outer-building labels, never aligns class numbers across folds.
Class roles are the previously frozen extrema of training class feature centers.
Opposite/zero effects, unscored records and support gaps remain explicit.
"""
from __future__ import annotations
import hashlib
import gzip
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TAX = ROOT / 'research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy'
DIF = ROOT / 'research/difficulty/difficulty_mechanisms_v2_20261020'
PROFILE = ROOT / 'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz'
INPUTS = [TAX/'BEHAVIOR_RECORDS.csv.gz', TAX/'ALL_METHOD_LABELS_LOBO.csv.gz',
          TAX/'OUTER_CLASS_ROLE_MAP.csv.gz', PROFILE,
          DIF/'record_conditions.csv.gz', DIF/'scope_closeout_20261022/image_scope_support.csv']
METRICS = ['turn_n','short_turn_edges','near_straight_nodes_5deg',
           'log_area','log_height','B8L2','D10','log_time_peer_delta',
           'reference_turn_deficit','reference_turn_excess','reference_reduced',
           'reference_extra','unmatched_ref_9','unmatched_ref_12',
           'bottom_bias_9','abs_bottom_bias_9','omission','extension','log_area_ratio']
GROUP = ['method','condition','tier','role','source']

def save(df: pd.DataFrame, name: str):
    p=HERE/name; t=p.with_name(p.name+'.partial')
    raw=df.to_csv(index=False).encode('utf-8-sig')
    data=gzip.compress(raw,mtime=0) if name.endswith('.gz') else raw
    with open(t,'wb') as f:
        assert f.write(data)==len(data);f.flush();os.fsync(f.fileno())
    assert t.read_bytes()==data
    check=pd.read_csv(t,compression='gzip' if name.endswith('.gz') else None,low_memory=False)
    assert check.shape==df.shape, (name,check.shape,df.shape)
    os.replace(t,p)

def write_json(name,obj):
    p=HERE/name;t=p.with_name(p.name+'.partial')
    data=(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    with open(t,'wb') as f:
        assert f.write(data)==len(data);f.flush();os.fsync(f.fileno())
    assert t.read_bytes()==data
    os.replace(t,p)

def load():
    x=pd.read_csv(INPUTS[0]); r=pd.read_csv(PROFILE)
    keep=['object_id','difficulty_class','difficulty_reference_match','panel',
          'scope_response','scope_opportunity','scope_correct','time_task_key',
          'target_matched_time_seconds','scene','doorway_status']
    x=x.merge(r[keep],on='object_id',validate='one_to_one')
    s=pd.read_csv(INPUTS[-1]).rename(columns={'coarse_class':'current_difficulty'})
    s=s[['image_id','target_id','current_difficulty','is_oos','is_doorway','target_full_status']]
    x=x.merge(s,on='image_id',validate='many_to_one')
    g=pd.read_csv(INPUTS[-2],low_memory=False)
    extra=['object_id','ref_geometry_status','ref_turn5','ref_H','ref_short_edges',
           'unmatched_ref_9','unmatched_ref_12','bottom_bias_9','omission',
           'extension','log_area_ratio','mechanism']
    x=x.merge(g[extra],on='object_id',validate='one_to_one')
    x['same_current_target']=x.reference_id.eq(x.target_id)
    x['primary_behavior']=x.behavior_usable & x.layer.eq('ordinary') & x.same_current_target & ~x.is_oos
    x['main_difficulty']=x.current_difficulty.isin(['简单','中等','困难'])
    x['reference_opportunity']=np.select(
        [x.ref_H.gt(0),x.ref_H.eq(0)&x.ref_short_edges.gt(0),x.ref_H.eq(0)&x.ref_short_edges.eq(0)],
        ['geometric_self_occlusion','short_edge_H0','plain_H0'],default='reference_unavailable')
    refok=x.same_current_target & x.ref_geometry_status.eq('valid_camera_inside') & x.ref_turn5.notna()
    delta=(x.turn_n-x.ref_turn5).where(refok)
    x['reference_turn_deficit']=(-delta).clip(lower=0)
    x['reference_turn_excess']=delta.clip(lower=0)
    x['reference_reduced']=delta.lt(0).astype(float).where(refok)
    x['reference_extra']=delta.gt(0).astype(float).where(refok)
    x['abs_bottom_bias_9']=x.bottom_bias_9.abs()
    # Per-record reference geometry only applies to exactly its frozen target.
    x.loc[~refok,['unmatched_ref_9','unmatched_ref_12','bottom_bias_9','abs_bottom_bias_9',
                 'omission','extension','log_area_ratio']]=np.nan
    # B8L2/D10 retain the existing quality gates; behavioral eligibility never requalifies Q.
    x.loc[~x.quality_usable,['B8L2','D10']]=np.nan
    x['source_time_seconds_valid']=x.source_active_time_seconds.where(x.source_active_time_seconds.gt(0))
    return x

def support_inventory(x):
    fields=['condition','layer','current_difficulty','primary_behavior','same_current_target',
            'behavior_usable','quality_usable','reference_opportunity','complex_opportunity']
    out=x.groupby(fields,dropna=False).agg(records=('object_id','size'),images=('image_id','nunique'),
        buildings=('building_id','nunique'),workers=('worker_id','nunique')).reset_index()
    save(out,'inventory_support.csv')
    cols=['object_id','worker_id','condition','origin','layer','image_id','image_code','building_id',
          'reference_id','target_id','same_current_target','current_difficulty','target_full_status',
          'primary_behavior','main_difficulty','behavior_usable','quality_usable','quality_use',
          'independent_vote_eligible','cleaning_disposition','complex_opportunity',
          'reference_opportunity','ref_turn5','ref_H','ref_short_edges',
          'source_active_time_seconds','time_source_kind','time_task_key']+METRICS
    save(x[cols],'record_opportunity_index.csv.gz')

def role_panels(x):
    roles=pd.read_csv(INPUTS[2]); x=x[x.primary_behavior].copy()
    d=x.merge(roles,left_on=['condition','worker_id','building_id'],
              right_on=['condition','worker_id','heldout_building'],validate='many_to_many')
    keys=['method','condition','tier','role','image_id','reference_id']
    rows=[]
    for key,g in d.groupby(keys,dropna=False):
        for source in ['all','new','v1']:
            z=g if source=='all' else g[g.origin.eq(source)]
            lo=z[z.role_group.eq('low')];hi=z[z.role_group.eq('high')]
            if min(lo.worker_id.nunique(),hi.worker_id.nunique())<2: continue
            row=dict(zip(keys,key));row.update(source=source,
                building_id=g.building_id.iloc[0],image_code=g.image_code.iloc[0],
                current_difficulty=g.current_difficulty.iloc[0],
                reference_opportunity=g.reference_opportunity.iloc[0],
                complex_opportunity=bool(g.complex_opportunity.iloc[0]),
                ref_turn5=g.ref_turn5.iloc[0],ref_H=g.ref_H.iloc[0],ref_short_edges=g.ref_short_edges.iloc[0],
                low_class=lo.training_class.iloc[0],high_class=hi.training_class.iloc[0],
                low_members='|'.join(sorted(lo.worker_id.unique())),
                high_members='|'.join(sorted(hi.worker_id.unique())),
                low_objects='|'.join(sorted(lo.object_id.unique())),
                high_objects='|'.join(sorted(hi.object_id.unique())),
                n_low=lo.worker_id.nunique(),n_high=hi.worker_id.nunique())
            for m in METRICS:
                a=lo[m].dropna();b=hi[m].dropna()
                row[m+'_n_low']=len(a);row[m+'_n_high']=len(b)
                row[m+'_low_mean']=a.mean();row[m+'_high_mean']=b.mean()
                row[m+'_difference']=b.mean()-a.mean() if min(len(a),len(b))>=2 else np.nan
            rows.append(row)
    out=pd.DataFrame(rows);save(out,'role_image_contrasts.csv.gz');return out

def aggregate(p, group, name, delta_suffix='_difference'):
    rows=[]; image_rows=[];building_rows=[]
    stratum_options=[[],['current_difficulty'],['reference_opportunity'],['complex_opportunity'],
                     ['current_difficulty','reference_opportunity']]
    for strata in stratum_options:
        for key,g in p.groupby(group+strata,dropna=False):
            base=dict(zip(group+strata,key if isinstance(key,tuple) else (key,)))
            base['stratification']='+'.join(strata) or 'all'
            for m in METRICS:
                col=m+delta_suffix
                valid=g[g[col].notna()]
                byimage=valid.groupby(['building_id','image_id','image_code'])[col].mean()
                bybuilding=byimage.groupby(level='building_id').mean()
                r=dict(base,metric=m,panels=len(g),valid_panels=len(valid),
                    images=len(byimage),buildings=len(bybuilding),
                    image_equal_mean=byimage.mean(),building_equal_mean=bybuilding.mean(),
                    image_median=byimage.median(),image_p10=byimage.quantile(.1),image_p90=byimage.quantile(.9),
                    positive_images=int(byimage.gt(1e-9).sum()),negative_images=int(byimage.lt(-1e-9).sum()),
                    zero_images=int(byimage.abs().le(1e-9).sum()),positive_buildings=int(bybuilding.gt(1e-9).sum()),
                    negative_buildings=int(bybuilding.lt(-1e-9).sum()),zero_buildings=int(bybuilding.abs().le(1e-9).sum()))
                rows.append(r)
                # Keep granular rows only once per all-strata-free source to avoid duplicate caches.
                if not strata:
                    for (b,i,c),v in byimage.items(): image_rows.append(dict(base,metric=m,building_id=b,image_id=i,image_code=c,difference=v))
                    for b,v in bybuilding.items(): building_rows.append(dict(base,metric=m,building_id=b,difference=v))
    out=pd.DataFrame(rows);save(out,name+'_summary.csv')
    save(pd.DataFrame(image_rows),name+'_images.csv.gz')
    save(pd.DataFrame(building_rows),name+'_buildings.csv')
    return out

def same_class_speed_pairs(x):
    labels=pd.read_csv(INPUTS[1]);labels=labels[labels.method.eq('V3_JOINT_QT') & labels.known & labels.qt_supported.eq(True)]
    cols=['worker_id','condition','heldout_building','coarse_label','fine_label','q_history','t_history',
          'q_images','q_buildings','t_images','t_buildings']
    z=x[x.primary_behavior].merge(labels[cols],left_on=['worker_id','condition','building_id'],
        right_on=['worker_id','condition','heldout_building'],validate='many_to_one')
    rows=[]
    for tier in ['coarse_label','fine_label']:
        for key,g in z.groupby(['condition','image_id','reference_id','origin',tier],dropna=False):
            # Deterministic actual-member pairs; only the historical features select the pair.
            for a,b in itertools.combinations(g.sort_values('worker_id').to_dict('records'),2):
                if abs(a['q_history']-b['q_history'])>3:continue
                if abs(a['t_history']-b['t_history'])<math.log(1.5):continue
                fast,slow=(a,b) if a['t_history']<b['t_history'] else (b,a)
                if fast['time_source_kind']!=slow['time_source_kind']:continue
                r=dict(condition=key[0],image_id=key[1],reference_id=key[2],origin=key[3],tier=tier,
                    training_class=key[4],worker_fast=fast['worker_id'],worker_slow=slow['worker_id'],
                    object_fast=fast['object_id'],object_slow=slow['object_id'],
                    worker_pair='|'.join(sorted([fast['worker_id'],slow['worker_id']])),
                    building_id=fast['building_id'],image_code=fast['image_code'],
                    current_difficulty=fast['current_difficulty'],
                    reference_opportunity=fast['reference_opportunity'],
                    complex_opportunity=fast['complex_opportunity'],
                    history_q_fast=fast['q_history'],history_q_slow=slow['q_history'],
                    history_time_log_slow_minus_fast=slow['t_history']-fast['t_history'],
                    time_source_kind=fast['time_source_kind'],
                    observed_seconds_fast=fast['source_time_seconds_valid'],
                    observed_seconds_slow=slow['source_time_seconds_valid'])
                for m in METRICS:
                    r[m+'_difference']=slow[m]-fast[m]
                rows.append(r)
    p=pd.DataFrame(rows);save(p,'same_class_nearQ_speed_pairs.csv.gz')
    aggregate(p,['condition','tier','origin'],'same_class_nearQ_speed')
    # Paired same-worker-pair difficulty comparison (simple vs difficult), maintaining source and direction.
    longitudinal=[]
    for key,g in p.groupby(['condition','tier','origin','worker_fast','worker_slow']):
        easy=g[g.current_difficulty.eq('简单')];hard=g[g.current_difficulty.eq('困难')]
        if min(easy.image_id.nunique(),hard.image_id.nunique())<2:continue
        base=dict(zip(['condition','tier','origin','worker_fast','worker_slow'],key))
        for m in METRICS:
            a=easy.groupby('building_id')[m+'_difference'].mean().dropna()
            b=hard.groupby('building_id')[m+'_difference'].mean().dropna()
            longitudinal.append(dict(base,metric=m,easy_images=int(easy[m+'_difference'].notna().sum()),
                hard_images=int(hard[m+'_difference'].notna().sum()),easy_buildings=len(a),hard_buildings=len(b),
                easy_mean=a.mean(),hard_mean=b.mean(),hard_minus_easy=b.mean()-a.mean()))
    save(pd.DataFrame(longitudinal),'same_people_speed_difficulty.csv')
    return p

def main():
    x=load();support_inventory(x)
    write_json('STAGE_01.json',dict(status='saved',data_version='real_v2',new_fusion=0,
        git_read_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        records=len(x),behavior_primary=int(x.primary_behavior.sum()),
        primary_images=int(x.loc[x.primary_behavior,'image_id'].nunique()),
        note='Raw-answer opportunity inventory saved before analyses. Quality qualification unchanged.'))
    print('saved stage 01 opportunity inventory',flush=True)
    p=role_panels(x);summary=aggregate(p,GROUP,'role_difficulty')
    print('saved role contrasts',len(p),len(summary),flush=True)
    pairs=same_class_speed_pairs(x)
    print('saved within-class near-Q speed pairs',len(pairs),flush=True)
    manifest=[]
    for f in INPUTS:manifest.append(dict(path=str(f.relative_to(ROOT)),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    write_json('RUN_MANIFEST.json',dict(stage='complete_numeric_analysis',data_version='real_v2',new_fusion=0,
        inputs=manifest,git_read_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        parameters=dict(role_min_workers_per_side=2,nearQ_max_absolute_historical_peer_Q_difference=3,
            min_historical_time_ratio=1.5,time_pairs_same_source=True,
            reference_self_occlusion='frozen geometry H>0; not RGB obstruction',
            reference_more_or_less_turns='expression relation, not semantic correctness',
            role_alignment='existing outer-fold extreme class centroids; no class-number pooling',
            primary='ordinary, valid behavioral evidence, same current target, non-OOS; Q keeps qualification',
            weighting='member pairs -> equal image -> equal building; counts never independent sample claims')))

if __name__=='__main__':main()
