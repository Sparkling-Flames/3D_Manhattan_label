"""Write source-linked conclusions for the completed targeted sensitivities.

This reporting pass reads saved numerical outputs; it never fuses, scores,
relabels, reconstructs bootstrap paths or changes original research inputs.
"""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
IMPACT=ROOT/'research/fusion/manual_order_impact_20261104'


def table(frame):
    def cell(x):
        if pd.isna(x):return '未评 / 不适用'
        if isinstance(x,(float,np.floating)):return f'{x:.6f}'
        return str(x).replace('|',' / ')
    cols=list(frame)
    return '\n'.join(['|'+'|'.join(cols)+'|','|'+'|'.join(['---']*len(cols))+'|']+
        ['|'+'|'.join(cell(v) for v in row)+'|' for row in frame.itertuples(index=False,name=None)])


def write(out,text,rows):
    (out/'REPORT_ZH.md').write_text(text,encoding='utf-8')
    pd.DataFrame(rows,columns=['topic','status','automatic','assisted','source','explanation']).to_csv(out/'CONCLUSIONS.csv',index=False)
    (out/'README.md').write_text('# 人工辅助顺序影响评估\n\n详见 [REPORT_ZH.md](REPORT_ZH.md)、[CONCLUSIONS.csv](CONCLUSIONS.csv) 与 [CHECKS.json](CHECKS.json)。\n\n原自动结果保留；新增可评支持、原共同支持、人工辅助分支和独立坐标候选分开记录。原无 Q 不填 0。\n',encoding='utf-8')


def natural():
    out=IMPACT/'natural';d=pd.read_csv(out/'AFFECTED_K_COMPARISON.csv');checks=json.loads((out/'CHECKS.json').read_text())
    assert checks.get('native_stage03_aggregate_completed') and checks.get('native_stage07_consumers_completed')
    keys=['pool_id','image','N','k','metric'];a=d[d.connection_version.eq('automatic')];b=d[d.connection_version.eq('manual_assisted')]
    both=a.merge(b,on=keys,suffixes=('_automatic','_assisted'),validate='one_to_one')
    display=both[['image','N','k','metric','valid_unique_teams_automatic','valid_unique_teams_assisted','valid_paths_automatic','valid_paths_assisted','mean_automatic','mean_assisted','p10_automatic','p10_assisted','sd_automatic','sd_assisted']]
    rows=[]
    for _,r in both.iterrows():
        for field,name in [('mean','均值'),('p10','线性P10'),('sd','样本标准差')]:
            old=r[field+'_automatic'];new=r[field+'_assisted']
            rows.append((f'{r.image}/k{r.k:g}/{r.metric}{name}','保持' if np.isclose(old,new,atol=1e-10,rtol=0) else '幅度变化',old,new,'AFFECTED_K_COMPARISON.csv',
                '原可评团队质量未变；新增无Q端点改变可评分母，重复路径频数继续保留'))
    rows += [
        ('自然主目标结论','保持',0,0,'DOWNSTREAM_CONSUMERS.csv','2队仅属于ordinary_manual_extra_target；原ordinary_manual_main消费者无真实命中'),
        ('新增可评支持','条件变化','34/35与9/10独立团队；248/256与231/256路径行','35/35与10/10独立团队；256/256与256/256路径行','AFFECTED_K_COMPARISON.csv','33条路径行只对应2个物理团队，不能当作33份独立证据'),
        ('人数平台及最优停止人数','尚不能判断','N=7与N=5','N=7与N=5','stage03_response/manual/PRIMARY_ONSET_DOMAIN_SUMMARY.csv','沿用N<8仅描述和后续至少max(5,ceil(.15N))人数要求，不补造平台'),
        ('原共同可评支持','保持',0,0,'ORIGINAL_SCORED_SUPPORT_CHECKS.csv','原质量与几何指标逐行差为0，新增支持均值变化不解释为旧团队改善或恶化'),
        ('原始劳动与k1/k2策略边界','保持','原有记录','原有记录','CHECKS.json','既有标注劳动、raw k1、k2补充或暂缓规则不变；人工排序耗时未知'),
        ('后段跳变与主起点摘要','保持',0,0,'CHECKS.json','两池N小于8，既有>=10后段跳变零命中；原primary onset和onset strata数值复现保持')]
    rows.append(('不加后续观察门槛的小范围诊断','条件变化','uNb complete/quality availability 起点4','同两项诊断起点3','AGGREGATE_NUMERIC_CHANGES.csv.gz','这是first_small_range_without_followup_gate；正式onset仍缺失，不得宣称人数平台提前'))
    changes=pd.read_csv(out/'AGGREGATE_NUMERIC_CHANGES.csv.gz')
    by=changes.groupby('table').size().rename('变化数值格').reset_index()
    transient=pd.read_csv(out/'TRANSIENT_AND_BAND_SUPPORT.csv')
    text=f'''# 人工辅助顺序对人数曲线的影响

## 范围与原方法

只补2个其它目标 Manual 池的现有端点：`rPc6DW4iMge-06__manual__other_space_10` 的 k=4 与 `uNb9QFRL6hY-88__manual__other_space_22` 的 k=3。两池分别 N=7、N=5，各保留256条冻结随机前缀路径。实际命中8+25=33条路径引用，但只有2个独立物理团队。成员、路径顺序、参考、票数、坐标和劳动记录保持。没有新增融合或重评分调用；使用端点交付中的既有人工顺序分数。

原自动 Q 为空，不能按0分计算改善。结果使用原 `analyze_response.py` 的路径频数、线性 P10 与 ddof=1 标准差。另保留逆CDF分位数列供定义核查；不会把线性P10与有限穷举团队P10混成同一估计。

## 实际 k 上的数值与支持

{table(display)}

来源：[AFFECTED_K_COMPARISON.csv](AFFECTED_K_COMPARISON.csv)。Q均值分别由73.467623降至72.556038、45.420856降至44.478358，来自新纳入的低Q团队，不表示原有可评团队几何恶化。uNb9 的线性P10反而升高，说明均值、尾部与波动不能用单一方向概括。原可评支持上的质量和几何逐行值差为0，见[ORIGINAL_SCORED_SUPPORT_CHECKS.csv](ORIGINAL_SCORED_SUPPORT_CHECKS.csv)。

## 全链实际消费者

两池的 per-k 状态、相邻/固定/到全员路径变化、尾部包络、平台敏感性、短暂平坦后再变化和既有带宽核查全部沿用原函数。stage03 的7张合表按原池行替换，然后直接调用原 `combine_pool_outputs`，保留目标池、图片、建筑不同分母。`FIXED_WINDOW_DOMAIN_SUMMARY.csv`、主起点表及域摘要均已补齐。

stage07 原固定面板曲线、每图边际变化、固定面板变化摘要使用原 `per_k_panels`、`marginal_changes`、`contrast_summaries`；其它域原行保持。`RESULT_FACTS.json` 也经过原 `facts` 函数复现与辅助分支更新。真实变化统计如下：

{table(by)}

逐格旧值、新值和差见[AGGREGATE_NUMERIC_CHANGES.csv.gz](AGGREGATE_NUMERIC_CHANGES.csv.gz)。原 stage07 面板成员不变；后段跳变只从 k>=10 开始，两个小池零命中；主平台起点与难度分层起点摘要保持。原 main-only 几何、结构分项、P10定义、有限尾部、连续结构和诊断脚本均无真实命中，未重算。证据见[DOWNSTREAM_CONSUMERS.csv](DOWNSTREAM_CONSUMERS.csv)。

`PRIMARY_SMALL_CHANGE_ONSETS.csv`中的两个辅助诊断格确有变化：uNb9的complete_evaluable_rate和quality_available_rate在不施加后续观察门槛时，首个小范围k由4变3；正式`onset_k`仍为空。这个区别已记录，不能将未通过门槛的诊断起点写成人数平台提前。

{table(transient)}

两池原本没有可复用置信带；没有将不存在的原带宽补为零。保存的空表、实际行数与合表引用保持可核验。

## 结论边界与复现

N=5/7仍只允许描述，不能满足原“至少还观察 max(5,ceil(.15N)) 人”的平台规则；人工顺序补入并不产生平台人数或最优停止人数的新证据。自然主目标、raw k1和原k2处理边界保持。劳动均为原标注劳动；缺少人工排序计时，不能声称包含介入成本的效率改善。

完整运行：`python -m tools.thesis_main.analysis.evaluate_manual_order_natural_20261104`。已有端点及池层输出时，`--finalize-only`仅闭合统计消费者。原汇总复现最大绝对误差 {checks['baseline_max_error']:.3g}，见[BASELINE_REPRODUCTION.csv](BASELINE_REPRODUCTION.csv)和[CHECKS.json](CHECKS.json)。57组是定向案例，本模块仅2队，不外推所有无环结果可修复。
'''
    write(out,text,rows)


def policy():
    out=IMPACT/'policy';d=pd.read_csv(out/'LATE_GLOBAL_COMPARISON.csv');keys=['version','policy','difficulty','phase','metric','weighting']
    old=d[d.connection_version.eq('automatic')].drop(columns='connection_version');new=d[d.connection_version.eq('manual_assisted')].drop(columns='connection_version')
    both=old.merge(new,on=keys,suffixes=('_automatic','_assisted'),validate='one_to_one')
    selected=both[both.metric.eq('paired_Q_delta')&both.difficulty.eq('全部')]
    display=selected[['version','weighting','estimate_automatic','estimate_assisted','images_assisted','buildings_assisted','building_lo_automatic','building_hi_automatic','building_lo_assisted','building_hi_assisted']]
    changes=[]
    for c in old:
        if c in keys or not pd.api.types.is_numeric_dtype(old[c]):continue
        a=both[c+'_automatic'];b=both[c+'_assisted'];mask=~np.isclose(a,b,atol=1e-12,rtol=0,equal_nan=True)
        for _,r in both[mask].iterrows():
            changes.append(dict(**{k:r[k] for k in keys},field=c,automatic=r[c+'_automatic'],manual_assisted=r[c+'_assisted']))
    pd.DataFrame(changes).to_csv(out/'NUMERIC_CHANGES.csv',index=False)
    sign=int(((both.estimate_automatic*both.estimate_assisted)<0).sum())
    interval={}
    for p in ['path','building']:
        a=np.select([both[p+'_lo_automatic']>0,both[p+'_hi_automatic']<0],[1,-1],default=0)
        b=np.select([both[p+'_lo_assisted']>0,both[p+'_hi_assisted']<0],[1,-1],default=0)
        interval[p]=int((a!=b).sum())
    checks=json.loads((out/'CHECKS.json').read_text());checks.update(point_sign_changes=sign,path_interval_zero_relation_changes=interval['path'],
        building_interval_zero_relation_changes=interval['building'],global_numeric_cells_changed=len(changes),
        global_point_cells_changed=int((~np.isclose(both.estimate_automatic,both.estimate_assisted,atol=1e-12,rtol=0,equal_nan=True)).sum()))
    (out/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    for _,r in selected.iterrows():
        rows.append((f'旧structure_dominant_first/{r.version}/{r.weighting}/后段Q差','幅度变化',r.estimate_automatic,r.estimate_assisted,'LATE_GLOBAL_COMPARISON.csv','仍为负；保留原固定k、路径簇与图片/建筑权重，原共同已评分端点不变'))
    rows += [
        ('旧策略方向与区间判定','保持',0,0,'NUMERIC_CHANGES.csv','352个既有后段摘要组无点估计符号变化，也无路径/建筑区间相对0的关系变化'),
        ('旧策略可评路径支持','条件变化','x8F5 n=28端点无Q','同一端点Q=30.829880','AFFECTED_PREFIX_ASSISTED.csv','新增现有路径端点支持，不是从0提升；总图片支持仍150/153'),
        ('早段、全员、old16及次要cohort','保持',0,0,'CHECKS.json','仅new16一条路径命中；pooled32继承该引用，added_reference32、次要old8、早段与全员零命中'),
        ('当前DSTRUCT策略','尚不能判断','历史V3_BEHAVIOR角色','历史V3_BEHAVIOR角色','CHECKS.json','structure_dominant_first是旧角色策略；不能用该命名代替当前DSTRUCT策略实验'),
        ('包含人工辅助的总劳动效率','尚不能判断','原标注劳动不变','人工排序成本缺失','CHECKS.json','原记录劳动保持；未知人工介入时间不能按0计入效率')]
    text=f'''# 人工辅助顺序对旧角色策略的影响

## 实际引用范围

唯一命中 `x8F5xyUWy9e-08__manual__0b13997fd3__fb261248c4a2c1b66d0b`：N=35池中的 k=28、`new16`批次、`structure_dominant_first`策略一条前缀路径。辅助Q=30.829880、D10=31.376466；原自动Q为空。该策略是历史 V3_BEHAVIOR 角色策略，不能因名称含“structure”就称为当前 DSTRUCT 策略。来源：[AFFECTED_PREFIX_AUTOMATIC.csv](AFFECTED_PREFIX_AUTOMATIC.csv)、[AFFECTED_PREFIX_ASSISTED.csv](AFFECTED_PREFIX_ASSISTED.csv)。

原主 cohort 153图/21栋保留；命中只传播到 new16 和 pooled32 的 `late_20_to_Nminus1`。old16、次要原old8、added_reference32、早段与全员端点无变化。实际后段paired-Q可评图片仍150/153、21栋，不能将一条补入路径当作新增独立图片。

## 主要结果

{table(display)}

来源：[LATE_GLOBAL_COMPARISON.csv](LATE_GLOBAL_COMPARISON.csv)。表中建筑区间沿用原2000次bootstrap。pooled32图片等权的Q差从−0.776979到−0.778220，建筑等权从−1.078062到−1.082493；方向与原区间判定保持。new16图片等权建筑区间仍跨0，而pooled32图片等权仍为负区间，不能混用两个版本的显著性。

全部22项指标、难度层和两种权重共352个后段摘要组中，{checks['global_point_cells_changed']}个点估计格数值变化，点估计符号变化{sign}处；路径区间与建筑区间相对0的关系变化均为0。质量分项、失败/不完整、达阈值、节点和结构项的全部逐格变化见[NUMERIC_CHANGES.csv](NUMERIC_CHANGES.csv)。新端点质量较低导致条件Q差略降，同时原失败支持减少；这两者可并存，不能将“能够评分”解释为Q必然更好。

## 支持、精度和劳动

保持原 fixed-k 支持、base_path_id、old8/prior_new8/new16 分层抽样以及2000次 whole-path bootstrap，seed=2026102603。原仓库未保存所需完整后段路径bootstrap缓存，故仅从既有153池标量表恢复命中策略的new16/pooled32后段缓存；没有重融合、重评分或产生新团队。恢复后的原自动全局点估计和所有区间与原保存结果最大绝对误差 {checks['baseline_parity_max_error']:.3g}。检查见[BASELINE_REPRODUCTION.csv](BASELINE_REPRODUCTION.csv)。

路径有效抽样次数及“conditional_on_estimable_draws”状态均原样保留。辅助版完整精度表见[POLICY_PRECISION_SUMMARY_ASSISTED.csv](POLICY_PRECISION_SUMMARY_ASSISTED.csv)，图片/人数/固定支持消费者见[ASSISTED_POLICY_IMAGE_PHASE.csv](ASSISTED_POLICY_IMAGE_PHASE.csv)、[ASSISTED_POLICY_IMAGE_K.csv.gz](ASSISTED_POLICY_IMAGE_K.csv.gz)、[ASSISTED_FIXED_SUPPORT.csv.gz](ASSISTED_FIXED_SUPPORT.csv.gz)。

原已评分端点值不变，原劳动3353.624秒及其它标注劳动字段保持；人工排序劳动未知。因此本节结论为旧策略后段效应幅度变化，不能推出包含人工介入成本的策略效率改善，也不能替代当前DSTRUCT策略证据。

复现：`python -m tools.thesis_main.analysis.evaluate_manual_order_policy_20261104`。数值完成后，报告生成器只读结果，不重复bootstrap。见[CHECKS.json](CHECKS.json)、[CONCLUSIONS.csv](CONCLUSIONS.csv)。
'''
    write(out,text,rows)


def alliances():
    out=IMPACT/'alliances';d=pd.read_csv(out/'FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv')
    display=d[~d.unknown_background_included][['connection_version','scope','version','pools','images','mean_full_minus_best_pure','pure_better_images','full_better_images','tied_images']]
    old=d[d.connection_version.eq('automatic')];new=d[d.connection_version.eq('manual_assisted')]
    keys=['scope','condition','unknown_background_included','version'];both=old.merge(new,on=keys,suffixes=('_automatic','_assisted'))
    rows=[]
    for _,r in both.iterrows():
        if r.scope=='primary':status='保持'
        elif r.mean_full_minus_best_pure_automatic*r.mean_full_minus_best_pure_assisted<0:status='需改写'
        else:status='幅度变化'
        rows.append((f'{r.scope}/{r.version}/unknown={r.unknown_background_included}/全员减最佳纯类',status,
            r.mean_full_minus_best_pure_automatic,r.mean_full_minus_best_pure_assisted,'FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv',
            '冻结/更新指标签快照；共同端点Q不变。其它目标均值符号变化来自新比较池和新增最佳纯类候选，不构成稳健的整体优势'))
    rows += [
        ('联盟成员与容量','保持','403可执行+11容量不足','403可执行+11容量不足','ALLIANCE_414_RESOLUTION_ASSISTED.csv','没有新增成员、改变人数或重新分类'),
        ('可评支持与最佳纯类选择','条件变化','19个被命中引用均无Q','17个引用可评，2个自交仍无Q','AFFECTED_ALLIANCE_ROWS.csv','12个物理团队的19引用；新增支持不当作19个独立样本'),
        ('原共同端点质量','保持',0,0,'POOL_SUPPORT_AND_SELECTION_CHANGES.csv','固定原已评分端点支持差0；相同池中最佳纯类可因新候选加入改变'),
        ('F2/F9单独坐标候选','条件变化','2个C1纯类引用无Q','2个引用Q=39.615619','coordinate_candidate/AFFECTED_ALLIANCE_ROWS.csv','候选未采用；只扩展C1条件均值支持，不改变全员与最佳纯类对照'),
        ('含人工介入的劳动效益','尚不能判断','原标注劳动','原标注劳动不变，人工成本未知','CHECKS.json','不得把人工排序与坐标判断成本视为0')]
    cand=out/'coordinate_candidate';parts=[]
    for v in ['MANUAL_ASSISTED_FIXED_COORDINATES','COORDINATE_CANDIDATE_NOT_ADOPTED']:
        c=pd.read_csv(cand/(v+'_CLASS_METRIC_SUMMARY.csv'))
        c=c[c.scope.eq('primary')&c.classes.eq('C1')&c.metric.eq('B8L2')&~c.unknown_background_included].copy()
        c['connection_version']=v;parts.append(c)
    ctable=pd.concat(parts)[['connection_version','version','registered_pools','eligible_pools','valid_images','mean']]
    text=f'''# 人工辅助顺序对纯类与联盟的影响

## 版本、范围与方法

在原 `closeout_20261030/alliance_completion_20261031` 的联盟表上补入12个物理团队、19个实际引用。其中17行取得条件可评分结果；pa4otMbVnkk-18同一自交端点的2个标签快照引用仍为空。当前403个可执行改变联盟与11个仅容量记录保持，既有全表其它行不变。参见[AFFECTED_ALLIANCE_ROWS.csv](AFFECTED_ALLIANCE_ROWS.csv)与[ALLIANCE_414_RESOLUTION_ASSISTED.csv](ALLIANCE_414_RESOLUTION_ASSISTED.csv)。

原字段`version=frozen/updated`表示标签快照；本交付另用`connection_version`表示自动/人工顺序。标签、成员、人数、参考、类别容量和未知背景边界不变，不进行分类选型。全员与最佳纯类采用原可评规则，先池内挑选、再图片等权；不是将各类Q行直接混合平均。原自动摘要已复现，最大绝对误差4.55e-13，见[BASELINE_REPRODUCTION.csv](BASELINE_REPRODUCTION.csv)。

## 主比较与其它目标

{table(display)}

来源：[FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv](FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv)。当前updated主目标205图仍为169图最佳纯类较好、36图全员较好，均值−6.050732保持；原frozen主目标173/32和均值−6.385821也保持。未知背景两图边界独立保留。

其它目标的比较池由24增至25，仍是23图。当前updated的全员减最佳纯类图片均值由−0.077642变为+0.049069，符号改写，但7图纯类较好、9图全员较好、7图持平不变，不能写成全员获得稳定总体优势。frozen快照则由+1.200119变为−0.548008。这两种方向变化必须按标签快照和支持条件区分。

`uNb9QFRL6hY-88`的纯C2三人队首次可评，使两个标签快照各新增同一比较池；其全员−最佳纯类为+11.493446。`wc2JMjhGNzB-26`的frozen快照在原可比较池内出现新可评纯类，最佳纯类Q由24.259815提高到67.381095，全员差由+46.644651降至+3.523370。这里是候选集合扩展，旧团队Q没有变化。详见[AFFECTED_POOL_COMPARISONS.csv](AFFECTED_POOL_COMPARISONS.csv)。

全部类别的Q、D10、IoU、结构分项与劳动分母详见[MANUAL_ASSISTED_CLASS_METRIC_SUMMARY.csv](MANUAL_ASSISTED_CLASS_METRIC_SUMMARY.csv)及[SUPPORT_COUNTS.csv](SUPPORT_COUNTS.csv)。图片/建筑层影响分别保存；多个目标池不当作多张独立图片。

## 单独的F2/F9坐标候选

主57组固定坐标结果保留。另按用户指定x=438.8037载入候选端点，固定其它y、节点身份、顺序、票数、成员与参考。候选Q=39.615619、D10=41.305788，kernel=false，属于conditional几何；没有作为正式坐标替换。

它仅命中pa4otMbVnkk-18的2个C1纯类引用。全员与最佳纯类的每个池及全部摘要均保持，新增比较池数和最佳纯类选择变化数均为0。C1自身条件均值与支持变化如下：

{table(ctable)}

来源：[coordinate_candidate/SUMMARY_COMPARISON.csv](coordinate_candidate/SUMMARY_COMPARISON.csv)、[coordinate_candidate/CHECKS.json](coordinate_candidate/CHECKS.json)。这是不同方法条件下的新增可评结果，不是原无Q从0提升，也不等同单纯排序修复。

## 可保留和需限定的解释

主目标“最佳可评纯类通常高于全员”的既有描述保持；其它目标的均值与最佳纯类候选集合需按辅助条件改写。新增可评支持不等于相同旧支持质量变化。原标注劳动字段不变，但人工排序与候选坐标审查没有计时，不能据此估计包含人工介入的效益。

复现：`python -m tools.thesis_main.analysis.evaluate_manual_order_alliances_20261104`；已完成主分支时，`--candidate-only`只运行独立坐标候选传播。定向57组不能外推全部无环结果可修复。逐条判定见[CONCLUSIONS.csv](CONCLUSIONS.csv)。
'''
    write(out,text,rows)
    (cand/'README.md').write_text('# F2/F9单独坐标候选：联盟传播\n\n候选未采用。见上级[REPORT_ZH.md](../REPORT_ZH.md)的独立分支和[CHECKS.json](CHECKS.json)。2个纯C1引用新增可评；最佳纯类、比较池和全员减最佳纯类摘要均不变。原固定坐标主分支没有覆盖。\n',encoding='utf-8')


def integrity():
    rows=[]
    for name in ['natural','policy','alliances','composition']:
        folder=IMPACT/name
        for p in sorted(folder.rglob('*.gz')):
            with gzip.open(p,'rb') as f:
                while f.read(1024*1024):pass
            rows.append(dict(module=name,path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),full_gzip_read_passed=True))
        pd.DataFrame([r for r in rows if r['module']==name]).to_csv(folder/'GZIP_INTEGRITY.csv',index=False)
    print(json.dumps(dict(gzip_files=len(rows),modules=['natural','policy','alliances','composition']),ensure_ascii=False))


def input_manifests():
    release=ROOT/'research/data/releases/v2.1'
    source=ROOT/'research/workers/image_response_v21_20261101/HOHONET_v21_image_response_20261101'
    policies=release/'current_policy_results/original_common32/analysis_policy26'
    inputs={
      'natural':[source/'scripts/analyze_response.py',source/'scripts/summarize_response.py',
          ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/engine26/derive_frozen_blocks.py',
          source/'stage02_normalized/manual/POOL_INDEX.csv',IMPACT/'endpoints/ENDPOINT_SCORES.csv',
          *[source/'stage02_normalized/manual/pools'/f'{p}.csv.gz' for p in [
              'rPc6DW4iMge-06__manual__other_space_10','uNb9QFRL6hY-88__manual__other_space_22']],
          *[source/'stage03_response/manual/by_pool'/p/n for p in [
              'rPc6DW4iMge-06__manual__other_space_10','uNb9QFRL6hY-88__manual__other_space_22'] for n in [
                  'POOL_K_STATISTICS.csv.gz','STATUS_BY_K.csv.gz','PATH_CHANGE_SUMMARY.csv.gz','TAIL_ENVELOPES.csv.gz','PLATEAU_SENSITIVITY.csv.gz']],
          *[p for p in (source/'stage03_response/manual').iterdir() if p.is_file() and not p.name.endswith('.tmp')],
          *[source/'stage07_summary/manual'/n for n in ['FIXED_PANEL_CURVES.csv.gz','PER_IMAGE_MARGINAL_CHANGES.csv.gz',
              'FIXED_PANEL_CHANGE_SUMMARY.csv.gz','FIXED_PANEL_MEMBERS.csv','ONSET_STRATA.csv','LATE_PATH_JUMP_SENSITIVITY.csv.gz','RESULT_FACTS.json']]],
      'policy':[IMPACT/'endpoints/ENDPOINT_SCORES.csv',policies/'COMMON_IMAGES.csv',
          ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/engine26/derive_frozen_blocks.py',
          *[policies/'results'/n for n in ['POLICY_IMAGE_K.csv.gz','POLICY_IMAGE_PHASE.csv','FIXED_SUPPORT.csv.gz','POLICY_PRECISION_SUMMARY.csv']],
          ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/local_audit/policy/FIXED_K_SUPPORT.csv.gz',
          *[ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/analysis_policy26'/n for n in [
              'adopted_policy_functions_20261025.py','analyze_policy32.py']],
          *[release/'current_policy_inputs'/f'{p}.csv.gz' for p in pd.read_csv(policies/'COMMON_IMAGES.csv').pool_id]],
      'alliances':[IMPACT/'endpoints/ENDPOINT_SCORES.csv',IMPACT/'coordinate_candidate/CANDIDATE_FULL_STATE.json.gz',
          *[release/'closeout_20261030/alliance_completion_20261031'/n for n in ['ALLIANCE_RESULTS.csv',
              'CLASS_METRIC_SUMMARY.csv','FULL_VS_BEST_PURE.csv','FULL_VS_BEST_PURE_SUMMARY.csv','ALLIANCE_414_RESOLUTION.csv']]],
    }
    for name,paths in inputs.items():
        rows=[]
        for p in sorted(set(paths)):
            if not p.exists():raise FileNotFoundError(p)
            rows.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                source_kind='new_assisted_endpoint_or_separate_candidate' if p.is_relative_to(IMPACT) else 'fixed_original_source'))
        (IMPACT/name/'INPUT_MANIFEST.json').write_text(json.dumps(dict(
            source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468',files=rows),ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    natural();policy();alliances();integrity();input_manifests()
