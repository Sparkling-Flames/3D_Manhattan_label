#!/usr/bin/env python3
"""Continue the frozen v2 matched-person difficulty question under v2.1.

No new class fitting, scoring, fusion, people, pictures, or reference changes.
All current matching uses the already archived out-of-building Q/T histories.
The current target picture's Q and time never select or orient its pair.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'stage03_speed_difficulty'
INP = OUT / 'inputs'
SRC = ROOT / 'source/research/data/releases/v2.1'
EPS = 1e-9
METRICS = ['turn_n', 'short_turn_edges', 'near_straight_nodes_5deg', 'log_area',
           'log_height', 'B8L2', 'D10', 'log_time_peer_delta',
           'reference_turn_deficit', 'reference_turn_excess', 'reference_reduced',
           'reference_extra', 'unmatched_ref_9', 'unmatched_ref_12', 'bottom_bias_9',
           'abs_bottom_bias_9', 'omission', 'extension', 'log_area_ratio',
           'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'IoU3D100',
           'matched_top_bias_deg', 'matched_bottom_bias_deg',
           'matched_horizontal_bias_deg', 'matched_boundary_abs_deg',
           'matched_pair_fraction', 'source_active_time_seconds']
V2METRICS = METRICS[:19]
QMETRICS = ['B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100']
EXPR = ['turn_n','short_turn_edges','near_straight_nodes_5deg','log_area','log_height']
REFMETRICS = ['ref_turn5','ref_H','ref_short_edges','unmatched_ref_9','unmatched_ref_12',
              'bottom_bias_9','omission','extension','log_area_ratio',
              'matched_top_bias_deg','matched_bottom_bias_deg',
              'matched_horizontal_bias_deg','matched_boundary_abs_deg','matched_pair_fraction']
KEYS = ['method','condition','origin']

def save(df, name):
    p=OUT/name; p.parent.mkdir(parents=True,exist_ok=True)
    data=df.to_csv(index=False).encode('utf-8-sig')
    if name.endswith('.gz'): data=gzip.compress(data,mtime=0)
    t=p.with_suffix(p.suffix+'.partial'); t.write_bytes(data); t.replace(p)
    check=pd.read_csv(p,low_memory=False)
    assert check.shape == df.shape, (name,check.shape,df.shape)

def js(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def read(p):return pd.read_csv(p,low_memory=False)

def records():
    b=read(SRC/'joint_history_classification/BEHAVIOR_RECORDS.csv.gz')
    old=read(INP/'v2_record_opportunity_index.csv.gz').set_index('object_id')
    q=read(SRC/'quality_inventory.csv').set_index('object_id')
    raw=read(INP/'RAW_TARGET_RESPONSE_RECORDS.csv.gz')
    assert raw.object_id.is_unique and b.object_id.is_unique and q.index.is_unique
    raw=raw.set_index('object_id')
    refs=pd.DataFrame(json.loads((SRC/'reference_catalog.json').read_text()))
    current=refs[refs.current_target].set_index('image_id')
    assert current.index.is_unique
    x=b.copy().set_index('object_id')
    x['reference_id']=q.reference_id.reindex(x.index)
    x['reference_version']=q.reference_version.reindex(x.index)
    x['primary_target_id']=x.image_id.map(current.target_id)
    x['same_current_target']=x.reference_id.eq(x.primary_target_id)
    x['current_difficulty']=q.current_class.reindex(x.index)
    x['source_pool_eligible']=q.source_pool_eligible.reindex(x.index).fillna(False)
    x['current_cleaning_disposition']=q.cleaning_disposition.reindex(x.index)
    x['current_quality_use']=q.quality_use.reindex(x.index)
    x['quality_usable']=q.quality_usable.reindex(x.index).fillna(False)
    x['primary_legal']=x.layer.eq('ordinary') & x.same_current_target & x.source_pool_eligible
    x['primary_behavior']=x.primary_legal & x.behavior_usable
    x['v2_primary_behavior']=old.primary_behavior.reindex(x.index).fillna(False)
    x['v2_quality_usable']=old.quality_usable.reindex(x.index).fillna(False)
    x['source_active_time_seconds']=q.source_active_time_seconds.reindex(x.index)
    logt=np.log(x.source_active_time_seconds.where(x.source_active_time_seconds.gt(0)))
    center=logt.where(x.primary_legal).groupby([x.condition,x.image_id,x.reference_id,x.origin,x.time_source_kind],dropna=False).transform('mean')
    x['log_time_peer_delta']=logt-center
    # Within the same image/source, subtraction of this common center cancels.
    for m in QMETRICS:
        x[m]=q[m].reindex(x.index).where(x.quality_usable & x.current_quality_use.eq('ordinary_primary'))
    for m in EXPR:
        x[m]=b.set_index('object_id')[m].where(x.behavior_usable)
    # All formal records have current reference diagnostics. For unscored
    # behavior, reuse only unchanged original-GT diagnostics, otherwise mark NA.
    unchanged=(x.reference_version.eq('gt_original') & x.reference_id.eq(old.reference_id.reindex(x.index)))
    x['reference_diagnostic_source']=np.where(unchanged,'v2_same_original_GT','unavailable_current_reference')
    for m in REFMETRICS:
        x[m]=old[m].reindex(x.index).where(unchanged) if m in old else np.nan
        if m in raw:
            use=x.index.isin(raw.index)
            x.loc[use,m]=raw[m].reindex(x.index[use])
    x.loc[x.index.isin(raw.index),'reference_diagnostic_source']='current_v21_target_response'
    refok=x.ref_turn5.notna() & x.turn_n.notna() & x.same_current_target
    delta=(x.turn_n-x.ref_turn5).where(refok)
    x['reference_turn_deficit']=(-delta).clip(lower=0)
    x['reference_turn_excess']=delta.clip(lower=0)
    x['reference_reduced']=delta.lt(0).astype(float).where(refok)
    x['reference_extra']=delta.gt(0).astype(float).where(refok)
    x['abs_bottom_bias_9']=x.bottom_bias_9.abs()
    x['reference_opportunity']=np.select([x.ref_H.gt(0),x.ref_H.eq(0)&x.ref_short_edges.gt(0),
        x.ref_H.eq(0)&x.ref_short_edges.eq(0)],['geometric_self_occlusion','short_edge_H0','plain_H0'],
        default='unavailable_current_reference')
    x['record_quality_state']=np.where(x.quality_usable,'quality_usable','quality_unavailable')
    x['full_score_state']=q.full_score_state.reindex(x.index)
    x['quality_exclusion_reasons']=q.quality_exclusion_reasons.reindex(x.index)
    x=x.reset_index()
    cols=['object_id','worker_id','condition','origin','image_id','image_code','building_id','reference_id',
          'reference_version','primary_target_id','same_current_target','current_difficulty','layer',
          'source_pool_eligible','current_cleaning_disposition','primary_legal','primary_behavior',
          'behavior_usable','quality_usable','current_quality_use','v2_primary_behavior','v2_quality_usable',
          'time_source_kind','reference_opportunity','reference_diagnostic_source','ref_turn5','ref_H',
          'ref_short_edges','full_score_state','quality_exclusion_reasons']+METRICS
    save(x[cols],'RECORDS_CURRENT_WITH_PROVENANCE.csv.gz')
    inv=x.groupby(['condition','layer','primary_legal','primary_behavior','quality_usable',
        'source_pool_eligible','current_difficulty'],dropna=False).agg(records=('object_id','size'),
        images=('image_id','nunique'),buildings=('building_id','nunique'),workers=('worker_id','nunique')).reset_index()
    save(inv,'RECORD_SUPPORT.csv')
    return x

def labels_and_history():
    hist=read(INP/'ALL_METHOD_LABELS_LOBO.csv.gz')
    hist=hist[hist.method.eq('V3_JOINT_QT') & hist.heldout_building.ne('ALL')].copy()
    assert not hist.duplicated(['worker_id','condition','heldout_building']).any()
    hcols=['worker_id','condition','heldout_building','q_history','t_history','qt_supported',
           'q_images','q_buildings','t_images','t_buildings','base_supported']
    h=hist[hcols].copy()
    labs=read(INP/'MAIN45_LABELS_ALL_LOBO.csv.gz')
    wanted=['TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K2','OPPJOINT_K3','OPPJOINT_K4']
    labs=labs[labs.method.isin(wanted) & labs.heldout_building.ne('ALL')]
    lcols=['worker_id','condition','heldout_building','method','class_id','known']
    labs=labs[lcols]
    final=read(INP/'USED_FINAL_LOBO_LABELS.csv.gz')
    chk=labs[labs.method.str.startswith('TARGET')].merge(final[lcols],
        on=['worker_id','condition','heldout_building','method'],suffixes=('_a','_b'),validate='one_to_one')
    assert len(chk)==len(labs[labs.method.str.startswith('TARGET')])
    assert chk.class_id_a.fillna('unknown').eq(chk.class_id_b.fillna('unknown')).all()
    assert chk.known_a.eq(chk.known_b).all()
    for tier,name in [('coarse_label','V3_JOINT_QT_COARSE'),('fine_label','V3_JOINT_QT_FINE')]:
        z=hist[['worker_id','condition','heldout_building',tier,'known']].rename(columns={tier:'class_id'})
        z['method']=name;labs=pd.concat([labs,z[lcols]],ignore_index=True)
    save(h,'HISTORIES_USED.csv.gz');save(labs,'LABELS_USED.csv.gz')
    return labs,h

def contrasts_from_rows(fast,slow):
    return {m+'_difference':slow.get(m,np.nan)-fast.get(m,np.nan) for m in METRICS}

def current_pairs(x,labels,hist):
    d=x[x.primary_legal].merge(hist,left_on=['worker_id','condition','building_id'],
        right_on=['worker_id','condition','heldout_building'],validate='many_to_one')
    d=d[d.qt_supported & d.q_history.notna() & d.t_history.notna()]
    d=d.merge(labels,on=['worker_id','condition','heldout_building'],validate='many_to_many')
    d=d[d.known & d.class_id.notna() & d.class_id.ne('unknown')]
    rows=[]
    group=['method','condition','image_id','reference_id','origin','time_source_kind','class_id']
    for key,g in d.groupby(group,dropna=False):
        for a,b in itertools.combinations(g.sort_values('worker_id').to_dict('records'),2):
            if abs(a['q_history']-b['q_history'])>3+1e-12:continue
            if abs(a['t_history']-b['t_history'])<math.log(1.5)-1e-12:continue
            fast,slow=(a,b) if a['t_history']<b['t_history'] else (b,a)
            row=dict(zip(group,key))
            row.update(worker_fast=fast['worker_id'],worker_slow=slow['worker_id'],
                object_fast=fast['object_id'],object_slow=slow['object_id'],
                worker_pair='|'.join(sorted([fast['worker_id'],slow['worker_id']])),
                building_id=fast['building_id'],image_code=fast['image_code'],
                current_difficulty=fast['current_difficulty'],heldout_building=fast['heldout_building'],
                reference_opportunity=fast['reference_opportunity'],
                history_q_fast=fast['q_history'],history_q_slow=slow['q_history'],
                history_time_fast=fast['t_history'],history_time_slow=slow['t_history'],
                history_time_log_slow_minus_fast=slow['t_history']-fast['t_history'],
                observed_seconds_fast=fast['source_active_time_seconds'],
                observed_seconds_slow=slow['source_active_time_seconds'],
                both_current_legal=True,both_v2_quality=fast['v2_quality_usable'] and slow['v2_quality_usable'],
                both_current_quality=pd.notna(fast['B8L2']) and pd.notna(slow['B8L2']),
                both_behavior=fast['behavior_usable'] and slow['behavior_usable'],
                geometry_source_fast=fast['reference_diagnostic_source'],
                geometry_source_slow=slow['reference_diagnostic_source'])
            row.update(contrasts_from_rows(fast,slow));rows.append(row)
    p=pd.DataFrame(rows)
    old=read(INP/'v2_record_opportunity_index.csv.gz')
    oldimages=set(map(tuple,old.loc[old.primary_behavior & old.quality_usable,['condition','image_id']].drop_duplicates().to_numpy()))
    p['v2_quality_image_support']=[(c,i) in oldimages for c,i in zip(p.condition,p.image_id)]
    p['physical_pair_key']=p.object_fast+'|'+p.object_slow
    p['methods_selecting_same_pair']=p.groupby('physical_pair_key').method.transform('nunique')
    save(p,'CURRENT_MATCHED_PAIRS.csv.gz')
    return p

def frozen_pairs(x,hist,labels):
    p=read(INP/'v2_same_class_nearQ_speed_pairs.csv.gz')
    assert len(p)==10339
    p['method']=p.tier.map({'coarse_label':'V3_JOINT_QT_COARSE','fine_label':'V3_JOINT_QT_FINE'})
    p['class_id']=p.training_class
    p['v2_current_difficulty']=p.current_difficulty
    for m in V2METRICS:p[m+'_v2_difference']=p[m+'_difference']
    r=x.set_index('object_id')
    hf=hist.set_index(['worker_id','condition','heldout_building'])
    lf=labels.set_index(['worker_id','condition','heldout_building','method'])
    rows=[]
    for old in p.to_dict('records'):
        a=r.loc[old['object_fast']];b=r.loc[old['object_slow']]
        assert a.worker_id==old['worker_fast'] and b.worker_id==old['worker_slow']
        assert a.image_id==b.image_id==old['image_id'] and a.condition==b.condition==old['condition']
        row=old.copy();row.update(current_difficulty=a.current_difficulty,reference_id=a.reference_id,
            both_current_legal=bool(a.primary_legal and b.primary_legal and a.reference_id==b.reference_id),
            both_current_quality=pd.notna(a.B8L2) and pd.notna(b.B8L2),
            both_v2_quality=pd.notna(old['B8L2_v2_difference']),
            quality_state_fast=a.full_score_state,quality_state_slow=b.full_score_state,
            current_cleaning_fast=a.current_cleaning_disposition,current_cleaning_slow=b.current_cleaning_disposition,
            reference_diagnostic_source_fast=a.reference_diagnostic_source,
            reference_diagnostic_source_slow=b.reference_diagnostic_source)
        row.update(contrasts_from_rows(a,b))
        if not row['both_current_legal']:
            for m in METRICS:row[m+'_difference']=np.nan
        ha=hf.loc[(a.worker_id,a.condition,a.building_id)];hb=hf.loc[(b.worker_id,b.condition,b.building_id)]
        la=lf.loc[(a.worker_id,a.condition,a.building_id,old['method'])]
        lb=lf.loc[(b.worker_id,b.condition,b.building_id,old['method'])]
        row.update(current_history_q_gap=hb.q_history-ha.q_history,
            current_history_log_time_gap=hb.t_history-ha.t_history,
            current_same_class=bool(la.known and lb.known and la.class_id==lb.class_id),
            current_class_fast=la.class_id,current_class_slow=lb.class_id,
            current_history_supported=bool(ha.qt_supported and hb.qt_supported))
        row['current_matching_still_holds']=bool(row['both_current_legal'] and row['current_history_supported']
            and row['current_same_class'] and abs(row['current_history_q_gap'])<=3+1e-12
            and row['current_history_log_time_gap']>=math.log(1.5)-1e-12)
        rows.append(row)
    p=pd.DataFrame(rows);save(p,'V2_FIXED_PAIR_CURRENT_RESULTS.csv.gz');return p

def summarize(p,metrics,name,cohorts=None):
    if cohorts is None:cohorts={'all_current_support':pd.Series(True,index=p.index)}
    allsum=[];allim=[];allb=[]
    for cohort,mask in cohorts.items():
        z=p[mask].copy()
        if z.empty:continue
        for keys,g in z.groupby(KEYS,dropna=False):
            base=dict(zip(KEYS,keys));base['cohort']=cohort
            options=[('all',g)] + [(str(k),gg) for k,gg in g.groupby('current_difficulty',dropna=False)]
            for difficulty,gg in options:
                for m in metrics:
                    col=m+'_difference';v=gg[gg[col].notna()]
                    ims=v.groupby(['building_id','image_id','image_code'])[col].mean()
                    bs=ims.groupby(level='building_id').mean()
                    out=dict(base,difficulty=difficulty,metric=m,pair_picture_rows=len(gg),valid_pair_picture_rows=len(v),
                        directed_people_pairs=v[['worker_fast','worker_slow']].drop_duplicates().shape[0],
                        workers=len(set(v.worker_fast)|set(v.worker_slow)),images=len(ims),buildings=len(bs),
                        image_equal_mean=ims.mean(),building_equal_mean=bs.mean(),
                        image_median=ims.median(),image_p10=ims.quantile(.1),image_p90=ims.quantile(.9),
                        mean_absolute_image_difference=ims.abs().mean(),positive_images=int(ims.gt(EPS).sum()),
                        negative_images=int(ims.lt(-EPS).sum()),zero_images=int(ims.abs().le(EPS).sum()),
                        positive_buildings=int(bs.gt(EPS).sum()),negative_buildings=int(bs.lt(-EPS).sum()),
                        zero_buildings=int(bs.abs().le(EPS).sum()))
                    allsum.append(out)
                    if difficulty!='all':
                        for (b,i,c),d in ims.items():allim.append(dict(base,difficulty=difficulty,metric=m,
                            building_id=b,image_id=i,image_code=c,difference=d))
                        for b,d in bs.items():allb.append(dict(base,difficulty=difficulty,metric=m,building_id=b,difference=d))
    save(pd.DataFrame(allsum),name+'_SUMMARY.csv')
    save(pd.DataFrame(allim),name+'_IMAGES.csv.gz')
    save(pd.DataFrame(allb),name+'_BUILDINGS.csv.gz')
    return pd.DataFrame(allsum)

def same_people(p,metrics,name,paired_building=False):
    keys=KEYS+['worker_fast','worker_slow']+(['building_id'] if paired_building else [])
    rows=[]
    for key,g in p.groupby(keys):
        easy=g[g.current_difficulty.eq('简单')];hard=g[g.current_difficulty.eq('困难')]
        minimum=1 if paired_building else 2
        if min(easy.image_id.nunique(),hard.image_id.nunique())<minimum:continue
        base=dict(zip(keys,key))
        for m in metrics:
            col=m+'_difference'
            a=easy.groupby('building_id')[col].mean().dropna();b=hard.groupby('building_id')[col].mean().dropna()
            rows.append(dict(base,metric=m,easy_images=int(easy[col].notna().sum()),hard_images=int(hard[col].notna().sum()),
                easy_buildings=len(a),hard_buildings=len(b),easy_building_ids='|'.join(a.index),hard_building_ids='|'.join(b.index),
                easy_mean=a.mean(),hard_mean=b.mean(),hard_minus_easy=b.mean()-a.mean(),
                easy_image_ids='|'.join(sorted(easy.loc[easy[col].notna(),'image_id'].unique())),
                hard_image_ids='|'.join(sorted(hard.loc[hard[col].notna(),'image_id'].unique()))))
    z=pd.DataFrame(rows);save(z,name+'.csv.gz')
    ss=[]
    for key,g in z.groupby(KEYS+['metric']):
        v=g.dropna(subset=['hard_minus_easy'])
        buildings=(set('|'.join(v.easy_building_ids).split('|'))|set('|'.join(v.hard_building_ids).split('|')))-{''}
        ss.append(dict(zip(KEYS+['metric'],key))|dict(eligible_pair_rows=len(g),valid_pair_rows=len(v),
            workers=len(set(v.worker_fast)|set(v.worker_slow)),mean=v.hard_minus_easy.mean(),median=v.hard_minus_easy.median(),
            p10=v.hard_minus_easy.quantile(.1),p90=v.hard_minus_easy.quantile(.9),
            positive=int(v.hard_minus_easy.gt(EPS).sum()),negative=int(v.hard_minus_easy.lt(-EPS).sum()),
            zero=int(v.hard_minus_easy.abs().le(EPS).sum()),easy_mean=v.easy_mean.mean(),hard_mean=v.hard_mean.mean(),
            distinct_buildings=len(buildings)))
    save(pd.DataFrame(ss),name+'_SUMMARY.csv')
    return z

def sensitivity(p,longitudinal):
    metrics=['turn_n','short_turn_edges','B8L2','D10','log_time_peer_delta','unmatched_ref_9','omission','extension']
    rows=[]
    for key,g in longitudinal[longitudinal.metric.isin(metrics)].groupby(KEYS+['metric']):
        base=dict(zip(KEYS+['metric'],key));g=g.dropna(subset=['hard_minus_easy'])
        people=sorted(set(g.worker_fast)|set(g.worker_slow))
        for w in people:
            z=g[g.worker_fast.ne(w)&g.worker_slow.ne(w)]
            rows.append(dict(base,omitted_worker=w,original_pairs=len(g),remaining_pairs=len(z),
                pair_equal_mean=z.hard_minus_easy.mean(),positive_pairs=int(z.hard_minus_easy.gt(EPS).sum()),
                negative_pairs=int(z.hard_minus_easy.lt(-EPS).sum()),zero_pairs=int(z.hard_minus_easy.abs().le(EPS).sum())))
    save(pd.DataFrame(rows),'FIXED_PEOPLE_LEAVE_ONE_WORKER.csv')
    # Leave-one-building recomputes easy/hard support. Neither labels nor matched
    # identities are refitted, and a pair falling below 2 images leaves support.
    rows=[]
    for key,g in p.groupby(KEYS):
        for omitted in sorted(g.building_id.unique()):
            z=g[g.building_id.ne(omitted)]
            vals={m:[] for m in metrics}
            for _,a in z.groupby(['worker_fast','worker_slow']):
                e=a[a.current_difficulty.eq('简单')];h=a[a.current_difficulty.eq('困难')]
                if min(e.image_id.nunique(),h.image_id.nunique())<2:continue
                for m in metrics:
                    c=m+'_difference';ev=e.groupby('building_id')[c].mean().mean();hv=h.groupby('building_id')[c].mean().mean()
                    if pd.notna(ev) and pd.notna(hv):vals[m].append(hv-ev)
            for m,v in vals.items():
                a=np.array(v);rows.append(dict(zip(KEYS,key))|dict(omitted_building=omitted,metric=m,
                    remaining_pairs=len(v),pair_equal_mean=np.mean(a) if len(a) else np.nan,
                    positive_pairs=int((a>EPS).sum()),negative_pairs=int((a<-EPS).sum()),zero_pairs=int((abs(a)<=EPS).sum())))
    save(pd.DataFrame(rows),'FIXED_PEOPLE_LEAVE_ONE_BUILDING.csv')

def validation(x,p,frozen):
    checks={}
    checks['matching_heldout_equals_target_building']=bool(p.heldout_building.eq(p.building_id).all())
    checks['all_matched_current_legal']=bool(p.both_current_legal.all())
    checks['history_Q_gap_at_most_3']=bool((p.history_q_slow-p.history_q_fast).abs().le(3+1e-10).all())
    checks['history_time_ratio_at_least_1_5']=bool(p.history_time_log_slow_minus_fast.ge(math.log(1.5)-1e-10).all())
    by=x.set_index('object_id')
    checks['same_source_origin']=bool(p.object_fast.map(by.origin).eq(p.object_slow.map(by.origin)).all())
    checks['same_time_source']=bool(p.object_fast.map(by.time_source_kind).eq(p.object_slow.map(by.time_source_kind)).all())
    checks['same_exact_target']=bool(p.object_fast.map(by.reference_id).eq(p.object_slow.map(by.reference_id)).all())
    checks['distinct_workers']=bool(p.worker_fast.ne(p.worker_slow).all())
    checks['unique_method_pair_picture']=bool(~p.duplicated(['method','condition','object_fast','object_slow']).any())
    checks['v2_frozen_rows']=len(frozen)==10339
    for k,v in checks.items():assert v,(k,v)
    js('VALIDATION.json',dict(checks=checks,current_pair_rows=len(p),
        current_physical_pair_picture_rows=p.physical_pair_key.nunique(),frozen_v2_pair_rows=len(frozen),
        current_record_inventory=len(x),current_legal_records=int(x.primary_legal.sum()),
        current_legal_behavior_records=int(x.primary_behavior.sum()),
        v2_behavior_now_source_ineligible=int((x.v2_primary_behavior & ~x.source_pool_eligible).sum()),
        new_fusion=0,new_scores=0,new_classifications=0))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    x=records();labels,h=labels_and_history()
    f=frozen_pairs(x,h,labels)
    v2=f.copy()
    for m in V2METRICS:v2[m+'_difference']=v2[m+'_v2_difference']
    v2['current_difficulty']=v2.v2_current_difficulty
    summarize(v2,V2METRICS,'V2_FROZEN')
    v2long=same_people(v2,V2METRICS,'V2_FROZEN_SAME_PEOPLE')
    # Frozen-v2 support, current values, then the explicitly expanded Q support.
    cohorts={'same_v2_pairs_current_legal':f.both_current_legal,
             'same_pairs_Q_common':f.both_current_legal & f.both_v2_quality & f.both_current_quality,
             'same_pairs_newly_Q_scorable':f.both_current_legal & ~f.both_v2_quality & f.both_current_quality,
             'same_pairs_current_matching_holds':f.current_matching_still_holds}
    summarize(v2,V2METRICS,'V2_ON_CURRENT_SUPPORT',cohorts)
    summarize(f,METRICS,'V21_FIXED_V2_PAIRS',cohorts)
    flegal=f[f.both_current_legal]
    same_people(flegal,METRICS,'V21_FIXED_V2_SAME_PEOPLE')
    p=current_pairs(x,labels,h)
    cohorts={'all_current_support':pd.Series(True,index=p.index),
             'v2_quality_image_support':p.v2_quality_image_support,
             'expanded_quality_image_support':~p.v2_quality_image_support,
             'both_originally_Q_scorable':p.both_v2_quality,
             'newly_Q_scorable_pair_records':~p.both_v2_quality & p.both_current_quality}
    summarize(p,METRICS,'CURRENT_MATCHED',cohorts)
    long=same_people(p,METRICS,'CURRENT_SAME_PEOPLE')
    same_people(p,METRICS,'CURRENT_SAME_PEOPLE_SAME_BUILDING',paired_building=True)
    sensitivity(p,long)
    # Match-method overlap is a reuse count, not independent replication.
    cross=p.groupby(['physical_pair_key','condition','image_id','building_id','worker_fast','worker_slow']).agg(
        methods=('method',lambda s:'|'.join(sorted(s))),method_count=('method','nunique')).reset_index()
    save(cross,'MATCH_METHOD_OVERLAP.csv.gz')
    usage=pd.concat([p[KEYS+['worker_fast']].rename(columns={'worker_fast':'worker_id'}).assign(role='fast'),
                     p[KEYS+['worker_slow']].rename(columns={'worker_slow':'worker_id'}).assign(role='slow')])
    save(usage.groupby(KEYS+['worker_id','role']).size().rename('pair_picture_rows').reset_index(),'MEMBER_USAGE.csv')
    validation(x,p,f)
    manifest=[]
    for file in sorted(INP.iterdir()):
        if file.is_file():manifest.append(dict(path=str(file.relative_to(ROOT)),bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
    for name in ['quality_inventory.csv','reference_catalog.json','joint_history_classification/BEHAVIOR_RECORDS.csv.gz']:
        file=SRC/name;manifest.append(dict(path=str(file.relative_to(ROOT)),bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
    js('RUN_MANIFEST.json',dict(source_commit='13a7861334749805a86dc19e9ea79fcaa71020c0',inputs=manifest,
        matching='existing v2.1 own-condition LOBO Q/T panels, same class/source, |Q gap|<=3, time ratio>=1.5',
        classification_status='working analysis only',new_fusion=0,new_scores=0,new_people=0,new_labels=0))
    print((OUT/'VALIDATION.json').read_text())

if __name__=='__main__':main()
