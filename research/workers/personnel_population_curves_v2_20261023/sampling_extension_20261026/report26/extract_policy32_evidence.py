#!/usr/bin/env python3
"""Read the completed policy32 sub-study; no resampling, fusion or new policies."""
from pathlib import Path
import argparse,csv,gzip,hashlib,json
import numpy as np
import pandas as pd

ROLES={'joint_highq_first':'历史联合高Q优先','structure_moreturn_first':'历史较多转折优先',
       'joint_fast_first':'历史联合快速优先','structure_dominant_first':'历史人数最多结构类优先'}
METRICS=['paired_Q_delta','paired_D10_delta','Q_p10_delta_common','Q_sd_delta_common_ddof1',
         'actual_consensus_failure_delta','output_generated_unscorable_delta','failure_delta',
         'Q_loss_gt5_rate','QT_paired_Q_delta','labor_ratio_legal','nodes_delta','turn5_delta']


def save(d,path,source,manifest):
    d=d.copy()
    if 'policy' in d: d['role_zh']=d.policy.map(ROLES)
    d['source_table']=source
    raw=d.to_csv(index=False,lineterminator='\n').encode('utf-8')
    data=gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw
    t=path.with_name(path.name+'.writing');t.write_bytes(data);t.replace(path)
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'rt',encoding='utf-8',newline='') as f:
        r=csv.reader(f);cols=next(r);n=0
        for n,row in enumerate(r,1): assert len(row)==len(cols)
    assert n==len(d)
    manifest.append(dict(file=path.name,rows=n,columns=cols,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),read_to_EOF=True))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,default=Path(__file__).resolve().parent.parent)
    args=ap.parse_args();base=args.base.resolve();src=base/'analysis_policy26/results'
    receipt=json.loads((src/'RECEIPT.json').read_text())
    assert receipt['completed'] and receipt['images']==157 and set(receipt['versions'])=={'old16','new16','pooled32'}
    out=base/'report26/policy32_evidence';out.mkdir(exist_ok=True);manifest=[]
    s=pd.read_csv(src/'POLICY_PRECISION_SUMMARY.csv')
    early=s[s.phase.eq('early_3_to_half')&s.metric.isin(METRICS)].copy()
    save(early,out/'P01_EARLY_STANDARD_SUMMARY.csv','analysis_policy26/results/POLICY_PRECISION_SUMMARY.csv',manifest)
    scope=s[s.difficulty.eq('全部')&s.weighting.eq('image_equal')&s.phase.isin(['early_3_to_half','low_3_to_6','late_20_to_Nminus1','full'])&s.metric.isin(METRICS)]
    save(scope,out/'P02_ALL_PHASES_STANDARD_SUMMARY.csv','analysis_policy26/results/POLICY_PRECISION_SUMMARY.csv',manifest)
    wide=early[early.difficulty.eq('全部')&early.weighting.eq('image_equal')].pivot(index=['policy','version'],columns='metric',values='estimate').reset_index()
    wide['labor_change_percent']=(wide.labor_ratio_legal-1)*100
    wide['actual_failure_delta_pp']=wide.actual_consensus_failure_delta*100
    save(wide,out/'P03_EARLY_VERSION_COMPARISON.csv','analysis_policy26/results/POLICY_PRECISION_SUMMARY.csv',manifest)
    phase=pd.read_csv(src/'POLICY_IMAGE_PHASE.csv')
    e=phase[phase.phase.eq('early_3_to_half')].copy()
    save(e,out/'P04_EARLY_IMAGE_RESULTS.csv.gz','analysis_policy26/results/POLICY_IMAGE_PHASE.csv',manifest)
    qt=[]
    for (policy,version),g in e.groupby(['policy','version']):
        x=g[g.QT_paired_Q_delta.notna()&g.labor_ratio_legal.notna()]
        qt.append(dict(policy=policy,version=version,images=len(x),buildings=x.building.nunique(),
            labor_saving_images=int(x.labor_ratio_legal.lt(1-1e-9).sum()),labor_increasing_images=int(x.labor_ratio_legal.gt(1+1e-9).sum()),
            labor_equal_images=int(x.labor_ratio_legal.sub(1).abs().le(1e-9).sum()),
            Q_improving_images=int(x.QT_paired_Q_delta.gt(1e-9).sum()),Q_declining_images=int(x.QT_paired_Q_delta.lt(-1e-9).sum()),
            Q_nearzero_images=int(x.QT_paired_Q_delta.abs().le(1e-9).sum()),
            Q_improving_and_labor_saving_images=int((x.QT_paired_Q_delta.gt(1e-9)&x.labor_ratio_legal.lt(1-1e-9)).sum()),
            ratio_estimand='mean of legal paired path ratios, not ratio of total labor'))
    save(pd.DataFrame(qt),out/'P05_QT_IMAGE_DIRECTION_COUNTS.csv','analysis_policy26/results/POLICY_IMAGE_PHASE.csv',manifest)
    selected=[('joint_highq_first','X7HyMhZNoso-07'),('joint_highq_first','B6ByNegPMKs-18'),
        ('structure_moreturn_first','e9zR4mvMWw7-19'),('structure_moreturn_first','uNb9QFRL6hY-60'),
        ('joint_fast_first','VFuaQ6m2Qom-04'),('joint_fast_first','Z6MFQCViBuw-08')]
    cases=e[[tuple(x) in set(selected) for x in e[['policy','image']].to_numpy()]].copy()
    cases['selection_rule']='post-result explanatory examples; all-image results retained in P04'
    save(cases,out/'P06_SELECTED_COUNTERCASES.csv','analysis_policy26/results/POLICY_IMAGE_PHASE.csv',manifest)

    # Final delivery retains stage2, while S05 used the then-available stage0
    # metadata. Both define the same frozen pool inventory; no Q is read here.
    natural_meta_rel='analysis_precision26/results_stage2/NATURAL_CURVES.csv.gz'
    if not (base/natural_meta_rel).exists():
        natural_meta_rel='analysis_precision26/results_stage0/NATURAL_CURVES.csv.gz'
    natural=pd.read_csv(base/natural_meta_rel,usecols=['pool_id','image','building','layer','pool_n']).drop_duplicates('pool_id')
    natural=natural[natural.layer.eq('ordinary_manual')&natural.pool_n.ge(30)]
    policy=pd.read_csv(base/'analysis_policy26/COMMON_IMAGES.csv')
    ids=set(natural.pool_id)|set(policy.pool_id)
    sets=pd.concat([natural,policy[['pool_id','image','building','layer','pool_n']]]).drop_duplicates('pool_id')
    sets=sets[sets.pool_id.isin(ids)].copy();sets['natural_fixed_N_ge_30']=sets.pool_id.isin(natural.pool_id);sets['historical_policy']=sets.pool_id.isin(policy.pool_id)
    assert len(natural)==157 and len(policy)==157 and int((sets.natural_fixed_N_ge_30&sets.historical_policy).sum())==148
    save(sets,out/'P07_TWO_157_SUPPORT_SETS.csv',natural_meta_rel+' pool metadata; analysis_policy26/COMMON_IMAGES.csv',manifest)

    fixed=pd.read_csv(src/'FIXED_SUPPORT.csv.gz')
    changed=fixed[fixed.version.eq('old16')&fixed.phase.eq('early_3_to_half')&fixed.metric.isin(['paired_Q_delta','QT_paired_Q_delta','labor_ratio_legal'])&fixed.lost_k.gt(0)]
    legacy_path=base/'repo/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/local_audit/policy/FIXED_K_SUPPORT.csv.gz'
    old=pd.read_csv(legacy_path)
    old=old[old.batch.eq('combined16')][['pool_id','policy','phase','metric','fixed_k_list','point']].rename(columns={'point':'legacy_point'})
    changed=changed.merge(old,on=['pool_id','policy','phase','metric'],how='left',validate='many_to_one')
    def kset(value):
        return set() if pd.isna(value) or str(value)=='' else set(map(int,str(value).split('|')))
    changed['dropped_k_list']=['|'.join(map(str,sorted(kset(a)-kset(b)))) for a,b in zip(changed.fixed_k_list,changed.matched_k_list)]
    save(changed,out/'P08_CHANGED_LEGACY_K_SUPPORT.csv','current FIXED_SUPPORT; pinned-main local_audit/policy/FIXED_K_SUPPORT',manifest)

    # Sparse time opportunities: use saved k counts and exact event semantics,
    # not additional draws. Rank a fixed diagnostic by valid saved bootstrap counts.
    focus=fixed[fixed.policy.eq('joint_highq_first')&fixed.version.eq('new16')&fixed.phase.eq('early_3_to_half')&fixed.metric.eq('labor_ratio_legal')&fixed.point.notna()].sort_values(['valid_bootstraps','pool_id']).head(8)
    focus_ids=set(focus.pool_id)
    kcols=['pool_id','image','building','difficulty','pool_n','policy','version','k','base_paths','both_Q_paths','legal_QT_paths','labor_ratio_legal']
    k=pd.read_csv(src/'POLICY_IMAGE_K.csv.gz',usecols=kcols)
    rows=[]
    for r in focus.itertuples():
        keep=set(map(int,r.matched_k_list.split('|')))
        q=k[k.pool_id.eq(r.pool_id)&k.policy.eq(r.policy)&k.version.eq('new16')&k.k.isin(keep)].copy()
        q['phase_valid_bootstraps']=r.valid_bootstraps;q['phase_invalid_bootstraps']=r.invalid_bootstraps
        q['phase_matched_k_list']=r.matched_k_list
        rows.append(q)
    sparse=pd.concat(rows,ignore_index=True)
    event_fields=['version','policy','pool_id','base_path_id','k','B8L2_natural','B8L2_policy',
        'source_time_total_seconds_natural','source_time_total_seconds_policy','labor_kind_natural','labor_kind_policy']
    parts=[]
    for z in pd.read_csv(src/'EXACT_PAIRED_EVENTS.csv.gz',usecols=event_fields,chunksize=80000,low_memory=False):
        z=z[z.version.eq('new16')&z.policy.eq('joint_highq_first')&z.pool_id.isin(focus_ids)]
        if len(z):parts.append(z)
    ev=pd.concat(parts,ignore_index=True)
    a=ev.labor_kind_natural.fillna('');b=ev.labor_kind_policy.fillna('')
    complete=ev.source_time_total_seconds_natural.gt(0)&ev.source_time_total_seconds_policy.gt(0)
    time=complete&a.ne('')&a.eq(b);quality=ev.B8L2_natural.notna()&ev.B8L2_policy.notna()
    ev['both_time_legal']=time;ev['both_Q_legal']=quality;ev['legal_QT']=time&quality
    ev['empty_or_mixed_source_kind']=a.eq('')|b.eq('')
    ev['between_team_source_mismatch']=a.ne('')&b.ne('')&a.ne(b)
    ev['known_same_source_but_incomplete_time']=a.ne('')&a.eq(b)&~complete
    ev['legal_time_but_Q_missing']=time&~quality
    fields=['both_time_legal','both_Q_legal','legal_QT','empty_or_mixed_source_kind',
        'between_team_source_mismatch','known_same_source_but_incomplete_time','legal_time_but_Q_missing']
    counts=ev.groupby(['pool_id','k'],as_index=False)[fields].sum()
    sparse=sparse.merge(counts,on=['pool_id','k'],validate='one_to_one')
    assert sparse.legal_QT.eq(sparse.legal_QT_paths).all()
    save(sparse,out/'P09_HIGHQ_NEW16_SPARSE_TIME_K.csv','fixed support + POLICY_IMAGE_K + EXACT_PAIRED_EVENTS',manifest)
    record_path=base/'repo/research/workers/personnel_population_curves_v2_20261023/stability_rebuilt_20261023/inputs/RECORD_TIME_SOURCE_INDEX.csv.gz'
    records=pd.read_csv(record_path);records=records[records.pool_id.isin(focus_ids)].copy()
    records['source_time_positive_known']=pd.to_numeric(records.source_time_seconds,errors='coerce').gt(0)
    save(records,out/'P10_SPARSE_CASE_ORIGINAL_TIME_RECORDS.csv','pinned-main stability_rebuilt/inputs/RECORD_TIME_SOURCE_INDEX.csv.gz',manifest)
    summaries=[]
    for pid,g in records.groupby('pool_id'):
        kinds=g.time_source_kind.fillna('').value_counts().to_dict()
        summaries.append(dict(pool_id=pid,image=g.image.iloc[0],indexed_original_records=len(g),positive_known_time_records=int(g.source_time_positive_known.sum()),
            source_kind_counts=json.dumps(kinds,ensure_ascii=False),missing_or_nonpositive_workers='|'.join(g.loc[~g.source_time_positive_known,'worker_id'].astype(str))))
    save(pd.DataFrame(summaries),out/'P11_SPARSE_CASE_TIME_RECORD_SUMMARY.csv','P10 original record index',manifest)
    # Existing source summaries already contain low-k and full early time ranges.
    time_rows=s[s.difficulty.eq('全部')&s.phase.isin(['early_3_to_half','low_3_to_6'])&s.metric.isin(['labor_ratio_legal','QT_paired_Q_delta'])]
    save(time_rows,out/'P12_EARLY_AND_LOWK_TIME_RANGES.csv','analysis_policy26/results/POLICY_PRECISION_SUMMARY.csv',manifest)
    time_support=fixed[fixed.metric.eq('labor_ratio_legal')&fixed.phase.isin(['early_3_to_half','low_3_to_6'])]
    support_rows=[]
    for (policy,version,phase_name),g in time_support.groupby(['policy','version','phase']):
        q=g[g.point.notna()]
        support_rows.append(dict(policy=policy,version=version,phase=phase_name,candidate_images=len(g),point_estimable_images=len(q),
            images_with_incomplete_resamples=int(q.invalid_bootstraps.gt(0).sum()),
            image_min_valid_bootstraps=int(q.valid_bootstraps.min()) if len(q) else None,
            image_median_valid_bootstraps=float(q.valid_bootstraps.median()) if len(q) else None,
            images_with_zero_valid_bootstraps=int(q.valid_bootstraps.eq(0).sum()),
            interpretation='per-image fixed-k estimability; aggregate needs every fixed image in same resample'))
    save(pd.DataFrame(support_rows),out/'P15_TIME_RESAMPLE_SUPPORT_PER_IMAGE.csv','analysis_policy26/results/FIXED_SUPPORT.csv.gz',manifest)
    presentation=base/'analysis_policy26/presentation'
    presentation_complete=(presentation/'RECEIPT.json').exists()
    if presentation_complete:
        pr=json.loads((presentation/'RECEIPT.json').read_text());assert pr['complete'] and pr['images']==157
        for source,dest in [('POLICY_INDEPENDENT_BATCH_SUMMARY.csv','P13_INDEPENDENT_BATCH_REPETITION.csv'),
                            ('POLICY_PRECISION_COUNTS.csv','P14_SINGLE_IMAGE_PRECISION.csv')]:
            q=pd.read_csv(presentation/source)
            save(q[q.phase.eq('early_3_to_half')],out/dest,'analysis_policy26/presentation/'+source,manifest)
    result=dict(completed_policy_substudy=True,policy_images=157,policy_buildings=22,natural_fixed30_images=157,
        intersection_images=148,source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',presentation_available=presentation_complete,
        no_new_fusion=True,no_new_resampling=True,no_new_classification=True,files=manifest)
    (out/'EVIDENCE_MANIFEST.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False),flush=True)
    print('SPARSE_CASE_SUMMARY',pd.DataFrame(summaries).to_dict('records'),flush=True)
    print('LOWK_TIME',time_rows[time_rows.phase.eq('low_3_to_6')&time_rows.weighting.eq('image_equal')][['policy','version','metric','estimate','images','path_valid_replicates','path_lo','path_hi','building_lo','building_hi']].to_dict('records'),flush=True)


if __name__=='__main__':main()
