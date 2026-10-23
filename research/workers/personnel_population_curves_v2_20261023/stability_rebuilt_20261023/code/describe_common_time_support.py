#!/usr/bin/env python3
"""Describe the existing four-policy exact time/QT intersection; no bootstrap."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd

POLICIES=['joint_fast_first','joint_highq_first','structure_dominant_first','structure_moreturn_first']
KEY=['pool_id','base_path_id','k']
META=['pool_id','image','building','condition','layer']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args();r=a.root/'results/time_semantics'
    d=pd.read_csv(r/'SAME_SEMANTICS_EARLY_EXACT_PAIRS.csv.gz',low_memory=False);assert not d.duplicated(KEY+['policy']).any();assert set(d.policy)==set(POLICIES)
    key=d.groupby(KEY).agg(policy_n=('policy','nunique'),all_time=('same_semantics_time_pair','all'),all_QT=('same_semantics_QT_pair','all')).reset_index();key['common_four_time']=key.policy_n.eq(4)&key.all_time;key['common_four_QT']=key.policy_n.eq(4)&key.all_QT
    d=d.merge(key[KEY+['policy_n','common_four_time','common_four_QT']],on=KEY,validate='many_to_one');c=d[d.common_four_time].copy()
    inputs=pd.read_csv(a.root/'inputs/PREFIX_VALUES_COMPACT.csv.gz',usecols=['team_key','B8L2','score_failure_nonpolicy','incomplete_nonpolicy','policy_deferred'],low_memory=False).drop_duplicates('team_key')
    for field in ['score_failure_nonpolicy','incomplete_nonpolicy','policy_deferred']:inputs[field]=inputs[field].astype(float)
    for prefix,keycol in [('natural','natural_team_key'),('priority','priority_team_key')]:
        q=inputs.rename(columns={x:prefix+'_'+x for x in inputs.columns if x!='team_key'}).rename(columns={'team_key':keycol});c=c.merge(q,on=keycol,validate='many_to_one')
    assert c.groupby(KEY).size().eq(4).all();assert c.groupby(KEY).natural_time_kind.nunique().eq(1).all();assert (c.natural_time_kind==c.priority_time_kind).all()
    c['time_source_kind']=c.natural_time_kind;c['time_ratio']=c.priority_source_seconds/c.natural_source_seconds;c['time_seconds_delta']=c.priority_source_seconds-c.natural_source_seconds;c['time_log_ratio']=np.log(c.time_ratio)
    c['Q_delta']=c.priority_B8L2-c.natural_B8L2;c['Q_loss_gt5']=c.Q_delta.lt(-5).where(c.Q_delta.notna())
    c['natural_Q_unavailable']=c.natural_B8L2.isna().astype(float);c['priority_Q_unavailable']=c.priority_B8L2.isna().astype(float);c['Q_unavailable_delta']=c.priority_Q_unavailable-c.natural_Q_unavailable
    c['score_failure_delta']=c.priority_score_failure_nonpolicy-c.natural_score_failure_nonpolicy;c['incomplete_delta']=c.priority_incomplete_nonpolicy-c.natural_incomplete_nonpolicy
    failcounts=c.groupby(['condition','layer','time_source_kind','policy']).agg(prefix_attempts=('priority_team_key','size'),natural_failed=('natural_score_failure_nonpolicy','sum'),priority_failed=('priority_score_failure_nonpolicy','sum'),natural_incomplete=('natural_incomplete_nonpolicy','sum'),priority_incomplete=('priority_incomplete_nonpolicy','sum')).reset_index()
    failcounts.to_csv(r/'FOUR_POLICY_COMMON_TIME_FAILURE_COUNTS.csv',index=False)
    c.to_csv(r/'FOUR_POLICY_COMMON_TIME_EXACT_PAIRS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    rows=[];ims=[]
    full=d[d.policy_n.eq(4)][META+KEY[1:]].drop_duplicates(KEY)
    for (condition,layer),f in full.groupby(['condition','layer']):
        rows.append(dict(condition=condition,layer=layer,time_source_kind='all_semantics_design_denominator',domain='four_policy_design',images=f.pool_id.nunique(),buildings=f.building.nunique(),paired_base_k_units=len(f),policy_rows=len(f)*4))
    for domain,cd in [('four_policy_time_common',c),('four_policy_QT_common',c[c.common_four_QT])]:
        for (condition,layer,kind),f in cd.groupby(['condition','layer','time_source_kind']):
            rows.append(dict(condition=condition,layer=layer,time_source_kind=kind,domain=domain,images=f.pool_id.nunique(),buildings=f.building.nunique(),paired_base_k_units=len(f)//4,policy_rows=len(f)))
        if domain=='four_policy_QT_common':cols=['Q_delta','time_ratio','time_seconds_delta','time_log_ratio','Q_loss_gt5']
        else:cols=['natural_Q_unavailable','priority_Q_unavailable','Q_unavailable_delta','natural_score_failure_nonpolicy','priority_score_failure_nonpolicy','score_failure_delta','natural_incomplete_nonpolicy','priority_incomplete_nonpolicy','incomplete_delta']
        per_k=cd.groupby(META+['time_source_kind','policy','k'],dropna=False)[cols].mean().reset_index()
        for names,g in per_k.groupby(META+['time_source_kind','policy'],dropna=False):
            rec=dict(zip(META+['time_source_kind','policy'],names));rec.update(domain=domain,k_values='|'.join(map(str,sorted(g.k))),k_n=len(g));rec.update(g[cols].mean().to_dict());ims.append(rec)
    sup=pd.DataFrame(rows);sup.to_csv(r/'FOUR_POLICY_COMMON_TIME_SUPPORT.csv',index=False)
    im=pd.DataFrame(ims);im.to_csv(r/'FOUR_POLICY_COMMON_TIME_PER_IMAGE.csv',index=False)
    est=[]
    idcols=META+['time_source_kind','policy','domain','k_values','k_n']
    for names,g in im.groupby(['condition','layer','time_source_kind','policy','domain'],dropna=False):
        meta=dict(zip(['condition','layer','time_source_kind','policy','domain'],names));vals=[x for x in im.columns if x not in idcols and g[x].notna().any()]
        for metric in vals:
            gb=g.groupby('building')[metric].mean();est.append({**meta,'metric':metric,'image_equal':g[metric].mean(),'building_equal':gb.mean(),'images':g[metric].notna().sum(),'buildings':gb.notna().sum(),'positive_image_fraction':g.loc[g[metric].notna(),metric].gt(0).mean()})
    effect=pd.DataFrame(est);effect.to_csv(r/'FOUR_POLICY_COMMON_TIME_EFFECTS.csv',index=False)
    outlines=[]
    for row in sup.itertuples():outlines.append(f'|{row.condition}|{row.layer}|{row.time_source_kind}|{row.domain}|{row.images}|{row.buildings}|{row.paired_base_k_units:,}|')
    qlines=[]
    z=effect[effect.domain.eq('four_policy_QT_common')]
    for names,g in z.groupby(['condition','layer','time_source_kind','policy']):
        m=dict(zip(g.metric,g.image_equal));row=g.iloc[0];qlines.append('|'+ '|'.join(map(str,names))+f'|{int(row.images)}图/{int(row.buildings)}楼|{m["Q_delta"]:+.3f}|{m["time_ratio"]:.3f}|{m["Q_loss_gt5"]:.1%}|')
    flines=[]
    for names,g in effect[effect.domain.eq('four_policy_time_common')].groupby(['condition','layer','time_source_kind','policy']):
        m=dict(zip(g.metric,g.image_equal));fc=failcounts
        for col,val in zip(['condition','layer','time_source_kind','policy'],names):fc=fc[fc[col].eq(val)]
        assert len(fc)==1;f=fc.iloc[0]
        flines.append('|'+ '|'.join(map(str,names))+f'|{int(f.natural_failed)}/{int(f.prefix_attempts)}|{int(f.priority_failed)}/{int(f.prefix_attempts)}|{m["natural_score_failure_nonpolicy"]:.2%}|{m["priority_score_failure_nonpolicy"]:.2%}|{m["score_failure_delta"]*100:+.3f}|')
    lines=['# 四策略相同pool/base/k的同语义共同域：只重新汇总','',
      '从现有精确前段事件自然取交集，没有新增团队、重抽或补齐缺失。先要求四策略都存在，再要求同一自然队与四个策略队的时间分别齐全、队内语义单一且五队语义相同。质量/时间/坏尾进一步要求五队全可评；失败另在前一层全部时间合法尝试中报告，不以QT全可评交集的零失败证明无风险。',
      '', '|条件|分层|时间语义|域|图片|建筑|base×k配对单位|','|---|---|---|---|---:|---:|---:|',*outlines,'',
      '|条件|分层|时间语义|策略|共同QT支持|Q差值|时间比|Q损失>5|','|---|---|---|---|---|---:|---:|---:|',*qlines,'',
      '|条件|分层|时间语义|策略|自然失败/全部尝试|策略失败/全部尝试|图等权自然失败率|图等权策略失败率|差值百分点|','|---|---|---|---|---:|---:|---:|---:|---:|',*flines,'',
      '每个指标先逐图逐k对合法base路径平均，再在该共同域可用k等权，最后按图片/建筑汇总。四策略在同一来源层的图、k和base支持完全一致；算术时间比不是总秒数之比。逐图及楼等权值也保留在CSV。这个交集是更窄的观察域，不能代替157图全质量结果。快类在自身来源时间子域68图Q+0.228；严格四策略交集67图18楼（还缩小了同图的base/k支持）为Q−0.873、时间比0.776、坏尾14.0%，与157图全质量共同域Q−1.651并列。这是支持变化，不能把正值写成普遍无质量代价。高Q优先在该67图共同域Q+7.419、时间比1.026；较多转折优先Q+6.810、比1.097，坏尾分别4.4%、5.4%。',
      '',
      '`FOUR_POLICY_COMMON_TIME_EFFECTS.csv`的`four_policy_time_common`保留自然和策略的Q不可用、评分失败、不完整及差值，分母为全部共同时间合法base×k尝试；不完整/失败定义沿用冻结原标量。`four_policy_QT_common`的质量/时间分母另列。表中的事件行数只是精确覆盖，不是独立样本数。',
      '',
      '代码：`python code/describe_common_time_support.py --root .`。输出`results/time_semantics/FOUR_POLICY_COMMON_TIME_*.csv*`；没有重抽区间，采用范围以实际图/楼/配对单位为准。']
    (a.root/'FOUR_POLICY_TIME_COMMON_ZH.md').write_text('\n'.join(lines)+'\n')
    (r/'FOUR_POLICY_COMMON_TIME_RECEIPT.json').write_text(json.dumps(dict(operation='existing_exact_four_policy_same_pool_base_k_intersection_reaggregate_only',new_fusion=0,new_orders=0,new_bootstrap=0,all_early_policy_rows=len(d),four_time_common_policy_rows=len(c),four_QT_common_policy_rows=int(c.common_four_QT.sum()),equal_policy_coverage_checks='passed',quality_and_time_joint_domain='all_five_teams_scored_and_single_identical_semantics',failure_domain='all_four_policy_same_semantics_time_attempts_before_quality_selection'),ensure_ascii=False,indent=2)+'\n')
    print(sup.to_string(index=False));print('saved exact common-support description; no new bootstrap')

if __name__=='__main__':main()
