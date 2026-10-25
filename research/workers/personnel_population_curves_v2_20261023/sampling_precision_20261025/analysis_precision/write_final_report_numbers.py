#!/usr/bin/env python3
"""Extract final readable values from completed tables; no bootstrap or fusion."""
from pathlib import Path
import argparse
import hashlib
import json
import pandas as pd
from analyze_new_natural_precision import atomic_bytes, save


def md(headers, rows):
    return '\n'.join(['|'+'|'.join(headers)+'|', '|'+'|'.join(['---']*len(headers))+'|']+
                     ['|'+'|'.join(map(str,row))+'|' for row in rows])


def main(base):
    out=base/'new_results'
    s=pd.read_csv(out/'NATURAL_FIXED_SUPPORT_STABILITY.csv.gz',low_memory=False)
    p=pd.read_csv(out/'KEY_PRECISION_BY_K.csv')
    c=s[s.domain.eq('balanced_all')&s.layer.eq('ordinary_manual')&s.difficulty.eq('全部')&
        s.panel.eq('fixed_N_ge_30')&s.kind.eq('curve')&s.position.astype(str).isin(['3','10','20','30'])&
        s.metric.isin(['Q_mean','Q_p10'])&s.weighting.eq('image_equal')&s.resampling.eq('path_MC_fixed_images')].copy()
    c['interval_halfwidth']=(c.percentile_97_5-c.percentile_2_5)/2
    save(c,out/'FINAL_FIXED157_CURVE_PRECISION.csv')
    h=s[s.domain.eq('balanced_all')&s.layer.eq('ordinary_manual')&s.difficulty.eq('困难')&s.kind.eq('interval')&
        s.metric.isin(['marginal_Q_delta','Q_p10_delta','Q_sd_delta'])&s.version.isin(['old24','new24','pooled48'])&
        (((s.panel=='fixed_N_ge_20')&s.position.isin(['6_to_10','10_to_20']))|
         ((s.panel=='fixed_N_ge_30')&(s.position=='20_to_30')))].copy()
    save(h,out/'FINAL_HARD_INTERVAL_UNCERTAINTY.csv')
    f=p[p.domain.eq('old_noise_focus')&p.panel.eq('fixed_N_ge_20')&
        p.difficulty.isin(['全部','困难','单列'])&p.version.isin(['old24','pooled48','focus96'])&p.k.isin([3,6,10,20])].copy()
    save(f,out/'FINAL_FOCUS_MATCHED_PRECISION_REACH.csv')
    levels=[]
    for k in ['3','10','20','30']:
        for metric,label in [('Q_mean','均Q'),('Q_p10','图内P10再图等权')]:
            z=c[c.position.astype(str).eq(k)&c.metric.eq(metric)].set_index('version')
            levels.append([k,label,*[f'{z.loc[v,"estimate"]:.3f}；±{z.loc[v,"interval_halfwidth"]:.3f}' for v in ['old24','new24','pooled48']]])
    intervals=[]
    for pos in ['6_to_10','10_to_20','20_to_30']:
        for metric,label in [('marginal_Q_delta','均Q变化'),('Q_p10_delta','P10变化'),('Q_sd_delta','SD变化')]:
            z=h[h.position.eq(pos)&h.metric.eq(metric)&h.version.eq('pooled48')&h.weighting.eq('image_equal')].set_index('resampling')
            a=z.loc['path_MC_fixed_images'];b=z.loc['building_resampling_fixed_paths']
            intervals.append([pos.replace('_to_','→'),label,f'{a.estimate:.3f}',
                f'[{a.percentile_2_5:.3f}, {a.percentile_97_5:.3f}]',f'[{b.percentile_2_5:.3f}, {b.percentile_97_5:.3f}]',
                f'{int(a.common_observed_images)}图/{int(a.common_observed_buildings)}楼'])
    focus=[]
    for layer,diff,label in [('ordinary_manual','全部','普通重点：固定N≥20'),('ordinary_manual','困难','困难重点：固定N≥20'),('doorway_manual','单列','门洞重点')]:
        for k in [3,6,10,20]:
            z=f[f.layer.eq(layer)&f.difficulty.eq(diff)&f.k.eq(k)].set_index('version')
            cells=[]
            for v in ['old24','pooled48','focus96']:
                q=z.loc[v];n=int(q.available_images)
                cells.append(f'{int(q.mean_MCSE_le1_images)}/{n}（{q.mean_MCSE_le1_fraction_all_images:.1%}）')
            for v in ['old24','pooled48','focus96']:
                q=z.loc[v];n=int(q.available_images)
                cells.append(f'{int(q.P10_halfwidth_le2_images)}/{n}（{q.P10_halfwidth_le2_fraction_all_images:.1%}）')
            focus.append([label,k,*cells])
    text=f'''# 自然路径最终报告数值摘取

来源 main：`40d0fe62dc62f6f6c12723af10195b7abb7bc9fe`。本文件仅从完成并完整读取的派生表筛选，没有新融合、新路径、新重抽或新模型。脚本：`write_final_report_numbers.py`。

## 固定157图、22栋建筑的均Q与P10路径精度

`NATURAL_FIXED_SUPPORT_STABILITY.csv.gz` 过滤：`domain=balanced_all, layer=ordinary_manual, difficulty=全部, panel=fixed_N_ge_30, kind=curve, position∈{{3,10,20,30}}, weighting=image_equal, resampling=path_MC_fixed_images, metric∈{{Q_mean,Q_p10}}`。

表格“±”只表示 `(percentile_97_5−percentile_2_5)/2`，不是强行把不对称区间中心放在点估计处；完整上下界另存 `FINAL_FIXED157_CURVE_PRECISION.csv`。区间固定这157张图，不能解释为新建筑误差。P10先在每图同k的可评团队内计算，再图等权，未混合全部团队求一个全局P10。

{md(['k','量','旧24：点估计；95%半宽','独立新24','合并48'],levels)}

原24已足以描述该固定集合的大平均曲线；样本加倍明显降低均Q路径误差。P10非线性，48的P10不必处于两批24的P10之间；其数值修正不能称为增加抽样使标注质量变好或变坏。

## 困难图：均值小幅变化与尾部、波动分开

以下均为合并48、图等权。路径重抽固定图片，建筑重抽固定已观测路径；是两个分别计算的误差来源，不是两个竞争模型。上两段固定N≥20的29图/15楼；20→30固定N≥30的27图/14楼。

{md(['人数段','量','点估计','路径95%','建筑95%','共同支持'],intervals)}

均Q三个小幅段的路径和建筑范围均跨零，适合写为“后段平均变化较小，现有结果未显示明确持续升高或下降”，不等于已证明完全不变。20→30的P10上升、SD下降对路径及建筑重抽都较清楚。10→20的P10点估计改善，但建筑范围略跨零；不能用固定图片的路径精度代替跨建筑稳定性。建筑等权与旧24/新24完整数值见 `FINAL_HARD_INTERVAL_UNCERTAINTY.csv`。

## 在同一预选子域比较旧24、48与96

原53重点池包括36普通池、17门洞池。为使k3/6/10/20使用同一容量支持，下表普通保留N≥20的35池，其中困难11池；另一个困难重点池N<20因此不进入这张表，不能把表中35写成全部36。门洞17池全部保留。预选依据旧24噪声；本表条件于已冻结名单，不包含重新选池的不确定性。独立新72点估计另表保存。

均Q达标：单图解析MCSE≤1；P10达标：单图经验bootstrap95%半宽≤2。两者都是实际精度量尺，不是实际误差保证，也不是本轮按结果继续抽样的停止门槛。缺失/不可估不算达标；分母为该固定图集合。

{md(['条件','k','均Q旧24达标','均Q48','均Q96','P10旧24达标','P1048','P1096'],focus)}

96仍不能支撑重点低人数单图均Q精确到MCSE1分：例如固定普通重点35池在k3无一达标，k20才19/35；门洞k3也无一达标。这不影响多图总体大方向可用。P10精度取决于尾峰权重与位置，不能从均Q/SD直接推断；wc2-46和VFua-04两种相反例已单独保存。

## 可复算入口

```bash
python analysis_precision/write_final_report_numbers.py --base <本轮目录>/analysis_precision
```

`FINAL_FOCUS_MATCHED_PRECISION_REACH.csv` 来自 `KEY_PRECISION_BY_K.csv`，其字段由 `NATURAL_POOL_K_BATCH_PRECISION.csv.gz` 的 `Q_mean_MCSE_analytic` 及 `(Q_p10_boot95_high−Q_p10_boot95_low)/2` 直接汇总；共同focus由冻结 `FOCUS_PRESELECTION_OLD24_RMS.csv` 给出。没有把重点96接到其他图片的48上形成不等预算主曲线。
'''
    atomic_bytes(base/'FINAL_NUMBERS_FOR_REPORT.md',text.encode('utf-8'))
    print(json.dumps({'files':['FINAL_NUMBERS_FOR_REPORT.md','new_results/FINAL_FIXED157_CURVE_PRECISION.csv','new_results/FINAL_HARD_INTERVAL_UNCERTAINTY.csv','new_results/FINAL_FOCUS_MATCHED_PRECISION_REACH.csv'],
        'source_stability_sha256':hashlib.sha256((out/'NATURAL_FIXED_SUPPORT_STABILITY.csv.gz').read_bytes()).hexdigest(),
        'row_counts':[len(c),len(h),len(f)],'new_fusion':0,'new_bootstrap':0},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);main(ap.parse_args().base)
