#!/usr/bin/env python3
"""Trace report values directly to saved configuration, labels and raw-pair tables."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'

def mdtable(df):
    cols=list(df.columns)
    lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
    for row in df.itertuples(index=False,name=None):lines.append('| '+' | '.join(str(x).replace('|',' / ') for x in row)+' |')
    return '\n'.join(lines)

def main():
    reg=pd.read_csv(OUT/'CANDIDATE_REGISTRY.csv')
    st=pd.read_csv(OUT/'LOBO_STABILITY_SUMMARY.csv').set_index('method')
    raw=pd.read_csv(OUT/'RAW_GEOMETRY_SUMMARY.csv')
    mainraw=raw[raw.support.eq('common_old45_new')&raw.subset.eq('same_corner_count')&raw.scope_summary.eq('ALL_TARGETS')&raw.difficulty_summary.eq('ALL')&raw.metric.eq('geometry_pair_angle')].set_index('method')
    families=['TARGET_DSTRUCT_K3','V21_DSTRUCT_FULL_K3','V21_DSTRUCT_RAW3_K3','V21_DSTRUCT_LEVEL_K3','V21_DSTRUCT_COND_K3','V21_DSTRUCT_HALF_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4']
    rows=[]
    for m in families:
        r=mainraw.loc[m]
        rr=reg[reg.method.eq(m.replace('TARGET_DSTRUCT','REPRO_TARGET_DSTRUCT') if m.startswith('TARGET') else m)&reg.heldout_building.eq('ALL')]
        rows.append({'配置':m,'ALL类人数':rr.class_sizes.iloc[0] if len(rr) else ('11/38/10' if m=='OPPSTRUCT_K3' else ('19/29/8' if m=='OPPJOINT_K3' else '26/19/3/8')),'类内角距°':f'{r.within:.6f}','类间角距°':f'{r.cross:.6f}','角距差°':f'{r.gap:.6f}','正差图片':f'{int(r.positive_gap_images)}/{int(r.images)}','正差建筑':f'{int(r.positive_gap_buildings)}/{int(r.buildings)}','楼外/ALL ARI均值':f'{st.loc[m,"mean"]:.6f}'})
    table=mdtable(pd.DataFrame(rows))
    members=pd.read_csv(OUT/'CLASS_CENTERS_ALL.csv')
    member_rows=[]
    for m in ['REPRO_TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3']:
        for r in members[members.method.eq(m)].itertuples():
            member_rows.append({'配置':m.replace('REPRO_',''),'类':r.class_id,'人数':r.workers,'困难转折残差':f'{r.m_hard_turn_n:.4f}','整体短边残差':f'{r.m_all_short_turn_edges:.4f}','整体近共线残差':f'{r.m_all_near_straight_nodes_5deg:.4f}','成员':r.members})
    support=pd.read_csv(OUT/'SUPPORT_GATE_COUNTS.csv')
    supp=support.groupby('gate_variant').eligible_workers.agg(['min','max']).reset_index()
    supp=supp.rename(columns={'gate_variant':'门槛','min':'23折最少人数','max':'23折最多人数'})
    paired=pd.read_csv(OUT/'RAW_GEOMETRY_PAIRED_VS_TARGET_K3.csv')
    paired=paired[paired.subset.eq('same_corner_count')&paired.metric.eq('geometry_pair_angle')&paired.method.isin(families)]
    pairtable=paired[['method','common_images','common_buildings','candidate_gap','baseline_gap','gap_gain','gain_images','loss_images','nearzero_images','building_gap_gain']].copy()
    for c in ['candidate_gap','baseline_gap','gap_gain','building_gap_gain']:pairtable[c]=pairtable[c].map(lambda v:f'{v:.6f}')
    retention=pd.read_csv(OUT/'EXISTING_TARGET_ABC_RETENTION_SUMMARY.csv')
    retention=retention[retention.method.str.endswith('_K3')][['method','source_events','retained_events','retained_images','retained_buildings','retained_Q_evaluable_events']]
    text=f'''# 普通 Manual 的 DSTRUCT v2.1 参数与原答解释独立审计

## 1. 当前可采用的判断

**以“不同人怎样标”为主问题，TARGET_DSTRUCT K3 仍是本轮最有依据的结构主分类候选；没有发现必须因版本变化而弃用它的参数错误。** 这是一项经过实际重拟合与原答几何复核的判断，不是沿用旧 OPPJOINT 主分类结论。OPPJOINT 的联合画像用途与团队结果由总报告另行评价。

本轮实际形成五种新的参数/特征变体，每种 K2/K3/K4，共 15 个新配置；另外精确复现 TARGET 的三个配置。不是十八种独立分类思想。每种都保留 ALL 与 22 个楼外折，所有配置在读取本轮新团队结果之前冻结。**没有使用团队 Q、时间或融合结果选择这些参数。**

新增 `V21_DSTRUCT_RAW3_K3` 值得作为一项有目的的补充：它剔除参考角点匹配诊断，仅用非冗余转折、短转折边与近共线冗余，较多转折类由 12 人扩大到 17 人。但同点数原答几何区分和楼外分区稳定性都下降，不能仅因可换人数变多就替代主分类。其必要的新严格 ABC 由团队实验部分验证，本文不预先许诺升质。

真实池容量核查也修正了一个容易出现的推断：RAW3的ALL17人**不表示每张图有17人，也不表示可以从较多转折类换出7人并再找同类7人作B**。普通Manual的n14/m7可行池，TARGET为128图22楼，RAW3为118图22楼；n16/m8则由TARGET的41图15楼变成RAW3的64图19楼。按楼外challenge角色秩检查，这两种规模可行源类均只有中间秩2，并没有高转折源类的反向m7。上述只是容量，不是已执行或已可评数量；逐池证据见并行容量审计的`M7_M8_EXACT_SUPPLEMENT_CANDIDATES.csv`。

## 2. 哪些沿用，哪些已经按 v2.1 重算

|环节|旧 DSTRUCT 至官方 v2.1|TARGET_DSTRUCT 的进一步变化|审计判断|
|---|---|---|---|
|原答结构|复用各原答已提取的转折、短边、近共线表达|定义不变|不是旧人员名单直接改名|
|参考诊断|参考变化时重算 unmatched、面积/遗漏等诊断|新增合法目标按各自参考计算|不能称完全不依赖参考的“纯原答分类”|
|难度|从 v2.1 quality_inventory.current_class 更新正式等级|只接受 target-aligned 正式等级；未知新目标不复制另一空间的等级|沿用人工分层思想，不等于沿用过期等级数值|
|历史域|官方20法非门洞且有正式难度，7,583条，包括111条特殊范围辅助历史|7,472条共同普通历史+231条新目标=7,703条；移除111条辅助历史|名单变化同时包含历史域、目标及权重变化，不能归因于单一因素|
|同行中心|官方主目标按 image×condition|按 image×reference×condition；时间另分来源|修正多目标混合的风险|
|个人历史权重|楼等权，楼内按记录/图片汇总|记录→目标→图片→建筑显式等权，逐指标处理缺失|同一图有多个目标不会额外放大权重|
|支持门槛|Manual总体12图3楼、简单5图2楼、困难4图2楼|保持相同阈值，每折重算人数|本轮已实际检查放宽/加严，见下表|
|结构输入|总体四轴，困难四轴与困难−简单四轴|保持相同字段组合|困难域并不是独立于总体的另一份实验|
|缩放|median/(p85−p15)，退化用std，再退化用1；clip±3|逐折、逐域重新拟合|规则沿用，数值不是旧版固定值|
|降维与聚类|每域最多PCA2，域RMS归一化后等权；Ward单树切K2/3/4|逐折重新拟合|K3/K4是真父子分区；未强制各类同人数|

四个原结构轴为：`turn_n`、`short_turn_edges`、`near_straight_nodes_5deg`、`unmatched_ref_9`。前三者描述作答自身表达；第四者为参考底角球面匹配的未匹配比例，受结构缺漏和角点定位共同影响。去掉 Q 并不等于去掉所有参考依赖，也不等于已识别纯粹认知风格。

现有 `OPPSTRUCT` 已经完成总体结构、challenge 结构及连续机会斜率的组合。机会由参考非冗余转折、自遮挡 H、短边计算；它既不是人工视觉难度的同义词，也不是本轮新发明。本轮 `COND` 则用 challenge 及 challenge−plain 替换人工困难域，直接检验两种条件定义。

## 3. 实际调参矩阵与支持检查

|变体|与TARGET唯一主要差别|要解决的问题|
|---|---|---|
|FULL|每域保留全部标准化维度，不截为PCA2|是否丢失了有解释性的低方差结构轴|
|RAW3|移除全部strata的unmatched_ref_9|实际标法与参考定位诊断是否应拆开|
|LEVEL|仅总体结构域|困难条件是否增加实际解释，而不只是增加字段|
|COND|总体+可计算challenge及challenge−plain，plain≥5图2楼、challenge≥4图2楼|当前目标结构条件是否比人工难度分层更适合|
|HALF|困难域相对总体权重从1:1改为1:0.5|原方法是否过度强调困难条件|

{mdtable(supp)}

放宽总体门槛至 8图3楼不会增加任何人员；当前被排除的 W019/W026 普通Manual历史为0，W022仅2图1楼且没有困难历史。普通Manual共6,739原答的四个结构字段均可计算。因此，现有七八人块的主要瓶颈不能归咎于这组历史支持门槛。加严门槛会减少可用人员，也没有理由通过加严来制造更干净的正结果。

原 TARGET 三个配置共 4,278 条 ALL/LOBO 人员登记已逐条精确复现，包括缺失资格。`EXACT_BASELINE_REPRODUCTION.csv.gz` 给出每条结果。

## 4. 原答几何的独立比较

直接复用已有原答对距离，未重新评分或融合。普通Manual单列；只比较同一合法目标内的原答对。共同支持取原45配置与全部新配置的共同已知人员，与旧比较逐折相同：多数折56人，rPc6DW4iMge与yqstnuAEVhm为55人。

下表限制两份原答**角点数相同**，因此不会仅因点数不同得到距离差。类内先各类别等权，类间先各无序类对等权；每个池至少4个类内与4个类间原答对。目标在图片内等权，图片与建筑结果分开。角距取沿用的顶底角球面配对距离；类间减类内是描述性距离差，不是融合变化，也不是预测准确率。

{table}

FULL_K3 的平均差略高，但少1张可评图、建筑等权差略低、楼外名单稳定性较弱；仅凭0.01°量级均值变化不足以更换主方法。RAW3扩大人数却削弱同点数几何区分。LEVEL、COND、HALF也没有形成足以替代 TARGET K3 的一致优势。这里没有把任何负差图片删去。

为排除两方法可评图片不同造成均值错觉，另给与 TARGET K3 的精确共同池配对：

{mdtable(pairtable)}

ARI仅衡量删去一栋楼后与ALL描述分区的一致性，不是聚类真值准确率；同点数几何区分也不能独自证明团队共识有用。最终主方法还需接入严格ABC、容量、构成、劳动与失败结果。

## 5. 名单与可解释的标法

下面是ALL描述名单；实际团队实验必须使用目标建筑对应的LOBO名单，不能拿这张名单代替。类别编号只在其具体配置与折内解释。

{mdtable(pd.DataFrame(member_rows))}

TARGET K3的C1相对常规组更偏困难结构简化且近共线冗余较多；C2更接近常规表达；C3在复杂机会中保留较多非冗余转折和短边。它们是历史相对行为组，不是永久的人格、能力档次，也不是“越多转折越正确”。

RAW3扩大较多转折类的五位具体人员为W011、W012、W013、W033、W036。这一改变是取消参考对应轴的结果，不是降低质量阈值。其较多转折类困难转折残差从旧组约+1.796降至+1.356，说明语义也变宽，不能只对外宣称“同一种类型人数更多”。逐人逐折变化、原支持与父子映射都已保存。

## 6. 粗细层与当前采用边界

TARGET K2把主要结构群与较多转折群区分开，ALL47/12。K3进一步把原47人父类拆成10/37，增加简化/冗余与常规表达的解释。K4进一步拆出4人小类；总体同点数角距差从K3的约0.684°降至约0.536°，正差图片由162/206变154/204，不能因为类数增加就默认更好。K4可作为特定小类机制补充，是否在某种团队条件有用途由已有细分结果回答。

RAW3 K4的ALL13/29/10/7保持真父子关系，但同点数角距差约0.222°、134/206图为正，较RAW3 K3也下降。无需为“更细”自动升级。

当前建议：**TARGET K3承担原答结构主解释，K2作粗层，K4按有实际机制证据的条件使用；RAW3 K3保留为不含参考定位诊断的定义敏感性与大块容量补充候选。** 此处不替总报告宣称RAW3团队效果已验证，也不否定OPPJOINT在联合画像、Q/T组织中的额外作用。

## 7. 已有结果与本轮新增计算的区分

已有：v2.1正式20前向重拟、TARGET/OPP家族、45法原答对几何、旧v2 overall/geometry条件敏感性、Q基线、K3/K4真实父子与反推RFUSE变体。上述没有冒充本轮首创或重做其融合。

新增：15个参数/特征配置的23折名单与变换、TARGET精确复现、七组支持门槛的逐人资格检查、各新配置楼外稳定性、普通Manual scalar原答差异与同点数真实原答几何比较、相同可评图片上的配对差、所有逐折名单及真实层级。后续新团队端点由总报告明确另列。

还对已完成的TARGET各K广筛与重点事件做了逐事件标签合法性审计。原D/X/Y/Z互斥、人数与A/B/C集合逐一核对；只有新标签下X/Y仍是同一纯类、Z是另一纯类的事件才能保留，D允许历史未知者。K3的4,275个既有事件、197图22楼中：

{mdtable(retention)}

这个表回答“多少旧实验仍严格适用于新分类”，并不回答“新分类性能相同/更好”。相同物理A/B/C端点的分数当然相同；只保留可复用事件也会改变成员与图片支持。因此没有把重贴标签算成新融合或新独立试验，亦没有用保留子集的均值为新方法争取主地位。FULL有85.05%的旧TARGET K3事件仍严格合法，足以说明多数原有机制可以条件性复用；它并不建立新的扩展能力。逐事件否决原因与原端点键均在`EXISTING_TARGET_ABC_RELABEL_EVENT_AUDIT.csv.gz`及`SOURCE_TARGET_ABC_EXACT_AND_SELECTED_METRICS.csv.gz`。

## 8. 可复算文件与来源

- `CONFIG_BEFORE_NEW_TEAM_RESULTS.json`：所有变体与选择边界。
- `NEW_LABELS_ALL_LOBO.csv.gz`、`NEW_LABELS_ALL.csv`：人员标签；`CLASS_CENTERS_ALL_LOBO.csv.gz`与`CLASS_CENTERS_ALL.csv`为角色中心和成员。
- `ALL_WORKER_TRANSITIONS_VS_TARGET.csv.gz`、`TRUE_K2_K3_K4_PARENT_LINKS.csv`、`WORKER_ALL_LOBO_SEMANTIC_CLASS_FRACTIONS.csv`：逐人变化和层级。
- `SUPPORT_GATE_SENSITIVITY_ALL_WORKERS.csv.gz`、`SUPPORT_GATE_COUNTS.csv`、`PER_METRIC_RAW_SUPPORT_ALL.csv`：资格与字段支持。
- `RAW_GEOMETRY_BY_POOL.csv.gz`、`RAW_GEOMETRY_BY_IMAGE.csv.gz`、`RAW_GEOMETRY_SUMMARY.csv`、`RAW_GEOMETRY_PAIRED_VS_TARGET_K3.csv`：本文每个原答几何数值的来源；不可评池另在`RAW_GEOMETRY_UNESTIMABLE.csv.gz`。
- `FIT_AND_AUDIT_RECEIPT.json`、`RAW_GEOMETRY_RECEIPT.json`、`RAW_GEOMETRY_EXISTING_BASELINE_PARITY.json`：复算与来源检查。
- `EXISTING_TARGET_ABC_RETENTION_SUMMARY.csv`、`EXISTING_TARGET_ABC_RETENTION_BY_CONDITION.csv`、`EXISTING_ABC_RELABEL_RECEIPT.json`：旧事件在新分类下的合法复用范围。
- `../code/refit_v21_structure_audit.py`、`../code/compare_new_raw_geometry.py`、`../code/relabel_existing_target_abc.py`、`../code/write_structure_audit_report.py`：实际代码。原答对来自已交付`raw_similarity/RAW_PAIR_DISTANCES.csv.gz`，输入历史来自阶段02，均保持来源不覆盖。

追溯源代码：`tools/thesis_main/analysis/refit_v21_condition_classes_20261028.py`；`analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/classifications/code/build_condition_response_classes.py`；`research/workers/personnel_v21_reselection_20261029/classification/code/build_target_aware_candidates.py`；同目录`NEW_TARGET_AWARE_METHODS_ZH.md`及`CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json`。历史方法与当前结果的区别以这些可检索源码和原始表为准。
'''
    (OUT/'DSTRUCT_V21_PARAMETER_AND_RAW_AUDIT_ZH.md').write_text(text)
    print('report saved',OUT/'DSTRUCT_V21_PARAMETER_AND_RAW_AUDIT_ZH.md')

if __name__=='__main__':main()
