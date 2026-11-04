#!/usr/bin/env python3
"""Describe frozen DSTRUCT classes on held-out original answers. No fitting/fusion."""
from pathlib import Path
import gzip
import hashlib
import itertools
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CUR = ROOT / 'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030'
BASIS = OUT.parent / 'basis'
HEAD = '48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
METHODS = ['TARGET_DSTRUCT_K2', 'TARGET_DSTRUCT_K3']
QCOLS = ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100','height_mean_ratio']
METRICS = ['B8L2','D10'] + QCOLS + [
    'turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9',
    'matched_pair_fraction','matched_top_bias_deg','matched_bottom_bias_deg',
    'matched_horizontal_bias_deg','matched_boundary_abs_deg','omission','extension',
    'log_area_ratio','log_height','turn_deficit','turn_excess',
]
TIME = ['source_active_time_seconds','log_time']
POOL = ['method','condition','scope','source_stratum','building','image_id','image','pool_id','reference_id','reference_version','official_difficulty']
IMAGE = ['method','condition','scope','source_stratum','building','image_id','image','official_difficulty']
GROUP = ['method','condition','scope','source_stratum','metric']

def save(df, name):
    data = df.to_csv(index=False).encode('utf-8-sig')
    if name.endswith('.gz'):
        data = gzip.compress(data, compresslevel=6, mtime=0)
    (OUT/name).write_bytes(data)

def finite_num(s):
    return pd.to_numeric(s, errors='coerce').where(lambda x: np.isfinite(x))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = [CUR/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',
              ROOT/'research/data/releases/v2.1/quality_records.csv',
              CUR/'ANALYSIS_RECORDS.json', BASIS/'WORKER_LABELS_ALL_LOBO.csv.gz']
    raw = pd.read_csv(inputs[0], low_memory=False)
    raw = raw[raw.layer.isin(['ordinary_manual','ordinary_semi'])].copy()
    assert raw.object_id.is_unique
    assert not raw.duplicated(['worker_id','pool_id']).any()
    mainq = pd.read_csv(inputs[1], low_memory=False)
    otherq = pd.DataFrame(json.loads(inputs[2].read_text()))
    joined, checks = [], []
    keys = ['object_id','reference_id','reference_version']
    for scope, q in [('primary',mainq),('other_admitted',otherq)]:
        z = raw[raw.scope.eq(scope)].merge(q[keys+QCOLS+['B8L2']],on=keys,
             how='left',validate='one_to_one',indicator=True,suffixes=('','_check'))
        assert z._merge.eq('both').all(), (scope, z._merge.value_counts())
        err = float((z.B8L2-z.B8L2_check).abs().max())
        assert err < 1e-10, (scope,err)
        joined.append(z.drop(columns=['B8L2_check','_merge']))
        checks.append(dict(scope=scope,records=len(z),matched=len(z),max_abs_Q_difference=err))
    raw = pd.concat(joined,ignore_index=True)
    for col in METRICS+TIME:
        if col in raw:
            raw[col] = finite_num(raw[col])
    raw['source_active_time_seconds'] = raw.source_active_time_seconds.where(raw.source_active_time_seconds.gt(0))
    logt = np.log(raw.source_active_time_seconds)
    assert np.allclose(raw.log_time,logt,equal_nan=True,atol=1e-10)
    raw['log_time'] = logt
    raw['turn_deficit'] = (raw.ref_turn5-raw.turn_n).clip(lower=0)
    raw['turn_excess'] = (raw.turn_n-raw.ref_turn5).clip(lower=0)
    assert raw.reference_version.notna().all()
    save(raw,'ORDINARY_RECORDS_WITH_COMPONENTS.csv.gz')

    labels = pd.read_csv(inputs[3],low_memory=False)
    frames = []
    for method in METHODS:
        lab = labels[labels.method.eq(method) & labels.heldout_building.ne('ALL')]
        z = raw.merge(lab[['worker_id','heldout_building','class_id','known']],
            left_on=['worker_id','building'],right_on=['worker_id','heldout_building'],
            how='left',validate='many_to_one',indicator=True)
        assert z._merge.eq('both').all()
        z = z.drop(columns='_merge')
        z['method'] = method
        frames.append(z)
    d = pd.concat(frames,ignore_index=True)
    save(d,'HELDOUT_ORIGINAL_RECORDS.csv.gz')
    support = d.groupby(['method','condition','scope','class_id'],dropna=False).agg(
        records=('object_id','size'),workers=('worker_id','nunique'),
        images=('image_id','nunique'),buildings=('building','nunique'),
        positive_T_records=('source_active_time_seconds','count')).reset_index()
    save(support,'RECORD_SUPPORT.csv')
    d = d[d.known & d.class_id.ne('unknown')].copy()

    # Pool means and within-class distributions; every worker has one record per pool.
    pools = []
    for source in ['all_sources','origin:new','origin:v1']:
        z = d if source=='all_sources' else d[d.origin.eq(source.split(':',1)[1])]
        z=z.copy(); z['source_stratum']=source
        a=z[POOL+['class_id','worker_id','object_id']+METRICS].melt(
            id_vars=POOL+['class_id','worker_id','object_id'],value_vars=METRICS,var_name='metric',value_name='value')
        a=a[np.isfinite(a.value)]
        g=a.groupby(POOL+['class_id','metric'],dropna=False).value
        p=g.agg(n='size',mean='mean',sd='std',minimum='min',maximum='max').reset_index()
        qu=g.quantile([.1,.25,.5,.75,.9]).unstack().rename(columns={.1:'p10',.25:'p25',.5:'median',.75:'p75',.9:'p90'}).reset_index()
        pools.append(p.merge(qu,on=POOL+['class_id','metric'],validate='one_to_one'))
    z=d[d.source_active_time_seconds.notna()].copy()
    z['source_stratum']='time:'+z.origin.astype(str)+'|'+z.time_source.astype(str)
    a=z[POOL+['class_id','worker_id','object_id']+TIME].melt(
        id_vars=POOL+['class_id','worker_id','object_id'],value_vars=TIME,var_name='metric',value_name='value')
    a=a[np.isfinite(a.value)]
    g=a.groupby(POOL+['class_id','metric'],dropna=False).value
    p=g.agg(n='size',mean='mean',sd='std',minimum='min',maximum='max').reset_index()
    qu=g.quantile([.1,.25,.5,.75,.9]).unstack().rename(columns={.1:'p10',.25:'p25',.5:'median',.75:'p75',.9:'p90'}).reset_index()
    pools.append(p.merge(qu,on=POOL+['class_id','metric'],validate='one_to_one'))
    pool = pd.concat(pools,ignore_index=True)
    save(pool,'POOL_CLASS_DISTRIBUTIONS.csv.gz')

    # All classes must be present within the identical legal target and source stratum.
    expected=pool.method.str.extract(r'K(\d+)$',expand=False).astype(int)
    num=pool.groupby(POOL+['metric'],dropna=False).class_id.transform('nunique')
    common=pool[num.eq(expected)].copy()
    imin=common.groupby(POOL+['metric'],dropna=False).n.transform('min')
    common['smallest_class_n']=imin
    save(common,'ALL_CLASSES_COMMON_TARGET_PROFILE.csv.gz')
    imcols=IMAGE+['class_id','metric']
    statcols=['mean','sd','minimum','maximum','p10','p25','median','p75','p90','n','smallest_class_n']
    # Multiple admitted targets do not give an image multiple votes.
    common_image=common.groupby(imcols,dropna=False)[statcols].mean().reset_index()
    nt=common.groupby(imcols,dropna=False).pool_id.nunique().rename('targets').reset_index()
    common_image=common_image.merge(nt,on=imcols,validate='one_to_one')
    save(common_image,'ALL_CLASSES_COMMON_IMAGE_PROFILE.csv.gz')
    profile_rows=[]
    for key,g0 in common_image.groupby(GROUP+['class_id'],dropna=False):
        meta=dict(zip(GROUP+['class_id'],key))
        for difficulty in ['ALL','简单','中等','困难']:
            g=g0 if difficulty=='ALL' else g0[g0.official_difficulty.eq(difficulty)]
            if g.empty: continue
            byb=g.groupby('building')[statcols].mean()
            row=dict(**meta,difficulty=difficulty,images=g.image_id.nunique(),buildings=len(byb),
                target_image_links=int(g.targets.sum()),image_equal_mean=float(g['mean'].mean()),
                building_equal_mean=float(byb['mean'].mean()),image_mean_p10=float(g['mean'].quantile(.1)),
                image_mean_median=float(g['mean'].median()),image_mean_p90=float(g['mean'].quantile(.9)),
                mean_class_size=float(g.n.mean()),min_smallest_class_n=float(g.smallest_class_n.min()),
                profile_support='all classes within same target/source, then equal targets within image',
                quantile_definition='mean of within-image within-class individual quantile; not pooled quantile')
            for c in ['p10','p25','median','p75','p90','sd']:
                row['image_equal_within_class_'+c]=float(g[c].mean())
            if meta['metric']=='log_time':
                row['geometric_seconds']=float(np.exp(row['image_equal_mean']))
            profile_rows.append(row)
    save(pd.DataFrame(profile_rows),'ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv')

    # Pairwise common targets, including images without the third class.
    pairframes=[]
    for method in METHODS:
        pp=pool[pool.method.eq(method)]
        for ca,cb in itertools.combinations([f'C{i}' for i in range(1,int(method[-1])+1)],2):
            key=POOL+['metric']
            a=pp[pp.class_id.eq(ca)][key+['n','mean']].rename(columns={'n':'n_A','mean':'mean_A'})
            b=pp[pp.class_id.eq(cb)][key+['n','mean']].rename(columns={'n':'n_B','mean':'mean_B'})
            pair=a.merge(b,on=key,validate='one_to_one')
            pair['class_A']=ca;pair['class_B']=cb;pair['difference_B_minus_A']=pair.mean_B-pair.mean_A
            pairframes.append(pair)
    pair=pd.concat(pairframes,ignore_index=True)
    save(pair,'SAME_TARGET_CLASS_CONTRASTS.csv.gz')
    pcols=IMAGE+['metric','class_A','class_B']
    pi=pair.groupby(pcols,dropna=False)[['mean_A','mean_B','difference_B_minus_A','n_A','n_B']].mean().reset_index()
    nt=pair.groupby(pcols,dropna=False).pool_id.nunique().rename('targets').reset_index()
    pi=pi.merge(nt,on=pcols,validate='one_to_one')
    # A combined time contrast only averages already matched source-specific contrasts.
    # No unmatched new/v1 seconds enter either side of a comparison.
    ti=pi[pi.source_stratum.str.startswith('time:')].copy()
    itcols=[c for c in pcols if c!='source_stratum']
    if not ti.empty:
        tc=ti.groupby(itcols,dropna=False)[['mean_A','mean_B','difference_B_minus_A','n_A','n_B','targets']].mean().reset_index()
        ns=ti.groupby(itcols,dropna=False).source_stratum.nunique().rename('matched_source_strata').reset_index()
        tc=tc.merge(ns,on=itcols,validate='one_to_one');tc['source_stratum']='time:matched_sources_equal_within_image'
        pi['matched_source_strata']=np.where(pi.source_stratum.str.startswith('time:'),1,np.nan)
        pi=pd.concat([pi,tc],ignore_index=True)
    save(pi,'SAME_IMAGE_CLASS_CONTRASTS.csv.gz')
    sums=[]
    for key,g0 in pi.groupby(GROUP+['class_A','class_B'],dropna=False):
        meta=dict(zip(GROUP+['class_A','class_B'],key))
        for difficulty in ['ALL','简单','中等','困难']:
            g=g0 if difficulty=='ALL' else g0[g0.official_difficulty.eq(difficulty)]
            if g.empty: continue
            v=g.difference_B_minus_A
            byb=g.groupby('building')[['mean_A','mean_B','difference_B_minus_A']].mean()
            row=dict(**meta,difficulty=difficulty,images=g.image_id.nunique(),buildings=len(byb),
                mean_A=float(g.mean_A.mean()),mean_B=float(g.mean_B.mean()),
                image_equal_mean=float(v.mean()),building_equal_mean=float(byb.difference_B_minus_A.mean()),
                image_difference_p10=float(v.quantile(.1)),image_difference_p25=float(v.quantile(.25)),
                image_difference_median=float(v.median()),image_difference_p75=float(v.quantile(.75)),image_difference_p90=float(v.quantile(.9)),
                positive_images=int(v.gt(1e-10).sum()),negative_images=int(v.lt(-1e-10).sum()),zero_images=int(v.abs().le(1e-10).sum()),
                positive_buildings=int(byb.difference_B_minus_A.gt(1e-10).sum()),negative_buildings=int(byb.difference_B_minus_A.lt(-1e-10).sum()),
                mean_A_workers_per_matched_target=float(g.n_A.mean()),mean_B_workers_per_matched_target=float(g.n_B.mean()),
                difference_direction='B minus A',statistic='within-target class means, equal targets within image',
                label_use='target building excluded; class rank defined in training history')
            if meta['metric']=='log_time':
                row['geometric_T_ratio_B_over_A']=float(np.exp(row['image_equal_mean']))
                row['geometric_T_A_seconds']=float(np.exp(row['mean_A']))
                row['geometric_T_B_seconds']=float(np.exp(row['mean_B']))
            sums.append(row)
    summary=pd.DataFrame(sums)
    save(summary,'SAME_IMAGE_PAIR_SUMMARY.csv')

    # Building-level difficulty response: same class pair and same building has both grades.
    responses=[]
    bp=pi.groupby(GROUP+['class_A','class_B','building','official_difficulty'],dropna=False).agg(
        difference=('difference_B_minus_A','mean'),images=('image_id','nunique')).reset_index()
    for low,high in [('简单','中等'),('简单','困难')]:
        kk=GROUP+['class_A','class_B','building']
        aa=bp[bp.official_difficulty.eq(low)][kk+['difference','images']]
        bb=bp[bp.official_difficulty.eq(high)][kk+['difference','images']]
        r=aa.merge(bb,on=kk,validate='one_to_one',suffixes=('_easy','_hard'))
        r['lower_difficulty']=low;r['higher_difficulty']=high
        r['change_of_class_difference']=r.difference_hard-r.difference_easy
        responses.append(r)
    responses=pd.concat(responses,ignore_index=True)
    save(responses,'SAME_BUILDING_DIFFICULTY_RESPONSE.csv.gz')
    rr=responses.groupby(GROUP+['class_A','class_B','lower_difficulty','higher_difficulty'],dropna=False).agg(
        buildings=('building','nunique'),lower_mean_class_difference=('difference_easy','mean'),
        higher_mean_class_difference=('difference_hard','mean'),
        mean_change=('change_of_class_difference','mean'),median_change=('change_of_class_difference','median'),
        positive_buildings=('change_of_class_difference',lambda s:int(s.gt(1e-10).sum())),
        negative_buildings=('change_of_class_difference',lambda s:int(s.lt(-1e-10).sum()))).reset_index()
    save(rr,'DIFFICULTY_RESPONSE_SUMMARY.csv')

    manifest=[]
    for p in inputs:
        b=p.read_bytes();manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),source_commit=HEAD if not p.is_relative_to(OUT.parent) else 'derived_this_delivery'))
    save(pd.DataFrame(manifest),'INPUT_MANIFEST.csv')
    validation=dict(source_commit=HEAD,score_join_keys=keys,quality_component_joins=checks,
        ordinary_records=len(raw),ordinary_manual_primary_records=int(((raw.condition=='manual')&(raw.scope=='primary')).sum()),
        ordinary_manual_other_records=int(((raw.condition=='manual')&(raw.scope=='other_admitted')).sum()),
        ordinary_semi_primary_records=int(((raw.condition=='semi')&(raw.scope=='primary')).sum()),
        ordinary_semi_other_records=int(((raw.condition=='semi')&(raw.scope=='other_admitted')).sum()),
        worker_pool_unique=True,labels_target_building_excluded=True,
        manual_primary_K3_Q_common_images=int(pd.DataFrame(profile_rows).query("method == 'TARGET_DSTRUCT_K3' and condition == 'manual' and scope == 'primary' and source_stratum == 'all_sources' and metric == 'B8L2' and difficulty == 'ALL' and class_id == 'C1'").images.iloc[0]),
        no_new_scoring=True,no_new_fusion=True,no_new_classification=True,
        missing_Q_is_missing=True,time_positive_same_origin_source=True,
        time_other_target='recorded task time, not extra-space-specific time',
        within_class_distribution='raw individual values included; summary quantiles average within-image class quantiles',
        excluded='doorway/special-range and held reference statuses are not newly admitted; unknown class not zero',
        difficulty_response='same building has both difficulty levels; image-equal means within level then building equal; observational, not same image becoming harder')
    (OUT/'VALIDATION.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(validation,ensure_ascii=False))

if __name__=='__main__':
    main()
