#!/usr/bin/env python3
"""Summarize the saved targeted time correction. No new bootstrap or fusion."""
from pathlib import Path
import argparse
import pandas as pd

ROLES={'joint_fast_first':'联合类：快角色优先','joint_highq_first':'联合类：高Q角色优先','structure_dominant_first':'结构类：人数最多类优先','structure_moreturn_first':'结构类：较多转折类优先'}
KINDS={'inherited_v1_audited_source':'继承v1已核时间','user_processed_reported_not_raw_log_replayed':'新来源报告时间，未重放原日志'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args();r=a.root/'results/time_semantics'
    s=pd.read_csv(r/'POLICY_MATCHED_TIME_SUPPORT.csv');im=pd.read_csv(a.root/'results/POLICY_EARLY_IMAGE_REBUILT.csv');common=set(im.groupby('pool_id').policy.nunique().loc[lambda v:v.eq(4)].index)
    s=s[s.pool_id.isin(common)];support=s.groupby(['condition','layer','policy'],dropna=False).agg(images=('pool_id','nunique'),buildings=('building','nunique'),prefix_attempts=('prefix_attempts','sum'),legacy_QT=('legacy_known_only_QT_pairs','sum'),same_semantics_QT=('same_semantics_QT_pairs','sum'),legacy_time=('legacy_known_only_time_pairs','sum'),same_semantics_time=('same_semantics_time_pairs','sum')).reset_index();support['QT_retained_fraction']=support.same_semantics_QT/support.legacy_QT;support.to_csv(r/'COMMON_POLICY_TIME_SUPPORT.csv',index=False)
    ci=pd.read_csv(r/'SAME_SEMANTICS_QT_STABILITY.csv');z=ci[ci.difficulty.eq('全部')&ci.weighting.eq('image_equal')&ci.layer.isin(['ordinary_manual','ordinary_semi'])]
    z.to_csv(r/'KEY_SAME_SEMANTICS_QT_EFFECTS.csv',index=False)
    sl=[]
    for x in support[support.layer.isin(['ordinary_manual','ordinary_semi'])].itertuples():sl.append(f'|{x.condition}|{ROLES[x.policy]}|{x.images}图/{x.buildings}楼|{x.prefix_attempts:,}|{x.legacy_QT:,}|{x.same_semantics_QT:,}|{x.QT_retained_fraction:.1%}|')
    def take(layer,policy,kind,metric,resampling):
        t=z[z.layer.eq(layer)&z.policy.eq(policy)&z.time_source_kind.eq(kind)&z.metric.eq(metric)&z.resampling.eq(resampling)];assert len(t)==1;return t.iloc[0]
    lines=[]
    for layer in ['ordinary_manual','ordinary_semi']:
        for kind,kindzh in KINDS.items():
            for policy,role in ROLES.items():
                q=take(layer,policy,kind,'QT_Q_delta_same_semantics','building_resampling_fixed_paths');t=take(layer,policy,kind,'QT_arithmetic_time_ratio_same_semantics','building_resampling_fixed_paths');p=take(layer,policy,kind,'QT_arithmetic_time_ratio_same_semantics','path_resampling_fixed_images');bad=take(layer,policy,kind,'QT_Q_loss_gt5_rate_same_semantics','building_resampling_fixed_paths')
                if not q.observed_images:continue
                def ci_text(row):return f'[{row.percentile_2_5:.3f}, {row.percentile_97_5:.3f}]'
                lines.append(f'|{layer.removeprefix("ordinary_")}|{kindzh}|{role}|{int(q.observed_images)}图/{int(q.observed_buildings)}楼|{q.estimate:+.3f}|{t.estimate:.3f}|{ci_text(p)}|{ci_text(t)}|{bad.estimate:.1%}|')
    text=f'''# 记录时间语义的针对性修正

## 这次修正了什么

新实现的第一版人数稳定性分析只要求 `source_time_known_n == k`。这排除了缺失时间，却没有排除单队中混合“继承v1已核时间”和“新来源报告时间”的情况。**旧时间列不能当作已经核实的同语义劳动比较。** 已保留旧列供追溯，并补出下面的同语义精确配对及重抽；质量、结构、全部路径、类别和评分均未改变。

本修正只处理这个具体接口。原报告中的“88图完整来源时间共同域”属于历史结果，本轮没有按其原规则和同语义要求独立复核，不能继续写成本轮已核成本结论，也不以这批新子域替代该历史研究。

## 合法支持

单队须全部成员有记录时间、合计为正且仅一种已知 `time_source_kind`；比较的自然队与策略队还须语义相同。质量—时间联合量额外要求两队同k都可评。同一配对的Q与时间使用完全相同支持。`same_semantics_QT_pair=False`保留在逐事件表，未填零。

从冻结229池的7,302份原答重新取得时间来源，并以原精确顺序重建404,082个前缀的来源类型。全已知时间合计与原标量最大差1.46×10⁻¹¹秒，说明修正的是使用资格，不是修改时长。全部原设计池、事件和失败分母仍保留。

|条件|策略|四策略共有设计池|前段配对尝试|旧仅知数QT|同语义QT|保留比例|
|---|---|---|---:|---:|---:|---:|
{chr(10).join(sl)}

表中“共有设计池”不等于每个策略都有同语义QT。下表保留每个来源和策略真正有效的图／楼；部分图只在部分前段人数有合法QT，均值先每图每k平均，再对可用k等权，再按图平均。不同策略有效图、成员、k可能不同，不能把这些均值直接排成最优策略。

## 同语义结果

时间比定义为同k策略队记录劳动 / 配对自然队记录劳动，先按路径、可用k、图片分层做**算术平均**；不是总秒数相除。完整表另有对数比及秒数差。下面按记录语义分列，未把两种来源的秒数合并成同一种活动时间。

|条件|时间语义|策略|QT支持|平均Q差值|平均时间比|固定图片路径重抽95%|建筑整块重抽95%|Q损失>5比例|
|---|---|---|---|---:|---:|---|---|---:|
{chr(10).join(lines)}

普通Manual新来源时间子域中，快角色优先的68图18楼平均Q变化+0.228，时间比0.798，建筑重抽[0.736,0.853]；这是这一可比时间子域的省时证据。全质量共同域157图的快策略Q−1.651仍保留，不能用有时间子域均值近零否定其全域质量代价。同一来源下高Q优先123图21楼Q+8.509、时间比1.119；较多转折优先102图20楼Q+7.827、比1.215，说明升质与增加记录劳动可以并存。

继承v1子域的支持明显不同：快策略14图7楼；高Q策略没有合法QT；较多转折12图5楼，Q差值−1.393且建筑范围跨零。Semi分别按来源保留条件结果，1图1楼产生的零宽建筑重抽范围只是没有跨楼变异可抽，不能解释为精确的普遍效应。

`all_pairs_matched_within_kind`汇总只聚合已经在各自来源内匹配的差值／比例，并非混合队时间重新合法化。跨来源合并的秒数差保留作诊断，主解释使用上面的分来源表。所有策略的坏尾、失败及全质量结果仍在原主表；没有用时间可用性删改它们。

## 完全共同支持的补充

四策略相同pool/base/k的自然交集已另按原事件重新汇总，没有再重抽。普通Manual仅剩新来源报告时间67图18楼，4,613个同语义时间单位、其中4,304个五队共同可评QT单位。快角色Q−0.873、时间比0.776；高Q+7.419、比1.026；较多转折+6.810、比1.097。它们使用完全相同的人数/路径支持；与上表各策略自身子域的差别来自支持变化。失败在4,613个时间合法尝试中另报告。完整同支持表、精确单位及说明见`FOUR_POLICY_TIME_COMMON_ZH.md`，不为这个交集追加人员或新抽样。

## 文件与复算

- `inputs/RECORD_TIME_SOURCE_INDEX.csv.gz`：7,302份实际记录的精确投影，含pool/worker/object/source键。
- `inputs/PREFIX_TIME_SEMANTICS.csv.gz`：404,082个前缀的来源、已知数、合计与新资格。
- `results/time_semantics/SAME_SEMANTICS_EARLY_EXACT_PAIRS.csv.gz`：97,576个前段尝试，双端团队键及合法/缺失状态。
- `results/time_semantics/POLICY_MATCHED_TIME_SUPPORT.csv`：827图×策略阶段，保留旧新分母。
- `results/time_semantics/SAME_SEMANTICS_QT_PER_IMAGE.csv`、`SAME_SEMANTICS_QT_PER_BUILDING.csv`：分来源逐图／楼结果。
- `results/time_semantics/SAME_SEMANTICS_QT_STABILITY.csv`：固定图片完整路径与建筑整块两种重抽，2,000次、seed2026102307。与主分析相同base路径抽样索引保持配对。
- `results/time_semantics/LEGACY_TIME_COLUMN_STATUS.csv`列明旧时间列状态；`CORRECTION_RECEIPT.json`保留操作与来源。

从本目录运行（使用已交付实际记录索引，不需要大原答快照）：

```bash
python code/fix_time_semantics.py --root . --replicates 2000 --seed 2026102307
python code/report_time_correction.py --root .
python code/finalize_saved_analysis.py --root .
```

这是一轮**原设计上新实现的条件分析修正**，没有新增融合、人员顺序、评分或分类，也不是遗失原bootstrap程序的恢复。
'''
    (a.root/'TIME_SEMANTICS_CORRECTION_ZH.md').write_text(text)
    status=[('results/NATURAL_*','source_labor_mean_seconds','legacy_known_count_only_mixed_semantics_possible','不作为同语义成本结论'),('results/POLICY_*','source_time_logratio;QT_Q_delta;QT_time_logratio','legacy_known_count_only_mixed_semantics_possible','请转新time_semantics表；全域paired_Q_delta不受影响'),('results/time_semantics/*','*_same_semantics','corrected_same_kind_pair','主时间结论分time_source_kind报告；all_pairs合并秒数仅作诊断')]
    pd.DataFrame(status,columns=['file_scope','columns','status','use']).to_csv(r/'LEGACY_TIME_COLUMN_STATUS.csv',index=False)
    print('saved targeted time correction report, support, key tables and column status')

if __name__=='__main__':main()
