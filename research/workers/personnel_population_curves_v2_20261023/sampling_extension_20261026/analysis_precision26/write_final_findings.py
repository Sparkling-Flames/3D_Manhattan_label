#!/usr/bin/env python3
"""Write the concise final natural-study readout from completed saved tables.

This is reporting/reaggregation only. It launches no fusion or resampling.
"""
from pathlib import Path
import argparse
import json
import pandas as pd
from precision_core import write_bytes, save_csv


def markdown(headers, rows):
    def s(value):
        return str(value).replace("|", "／").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(s, headers)) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(s, row)) + " |" for row in rows])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    root = ap.parse_args().root.resolve(); owner = root / "analysis_precision26"; src = owner / "results_stage2"
    assert json.loads((src / "NATURAL_FINALIZATION_COMPLETE.json").read_text())["pools"] == 194
    reach = pd.read_csv(src / "PRECISION_REACH_BY_LAYER_K.csv.gz")
    bands = pd.read_csv(src / "FINAL_READOUT_WHOLE_CURVE_PRECISION.csv")
    revisions = pd.read_csv(src / "FINAL_READOUT_POINT_REVISIONS.csv")
    intervals = pd.read_csv(src / "COMMON_SUPPORT_INTERVAL_SUMMARY.csv.gz")
    selected_rows = []
    def row(panel, layer, difficulty, interval, metric, cohort="pooled256"):
        d = intervals[intervals.panel.eq(panel) & intervals.layer.eq(layer) & intervals.difficulty.eq(difficulty) &
                      intervals.interval.eq(interval) & intervals.metric.eq(metric) & intervals.cohort.eq(cohort) &
                      intervals.weighting.eq("image_equal")]
        assert len(d) == 1, (panel, layer, difficulty, interval, metric, cohort, len(d))
        r = d.iloc[0]; selected_rows.append(r.to_dict()); return r
    def interval_entry(label, r, percentage=False):
        scale = 100 if percentage else 1
        unit = " pp" if percentage else ""
        return [label, f"{r.estimate * scale:+.3f}{unit}", f"{r.images}图/{r.buildings}楼",
                f"{r.positive_images}/{r.negative_images}/{r.near_zero_images}",
                f"[{r.path95_low * scale:.3f}, {r.path95_high * scale:.3f}]",
                f"[{r.building95_low * scale:.3f}, {r.building95_high * scale:.3f}]"]

    point_rows = []
    for k in [3, 6, 10, 20, 30]:
        g = reach[reach.panel.eq("fixed_N_ge_30") & reach.layer.eq("ordinary_manual") & reach.difficulty.eq("全部") & reach.k.eq(k)].set_index("cohort")
        point_rows.append([k, f"{int(g.loc['old48','mean_mcse_gt1_images'])} → {int(g.loc['pooled256','mean_mcse_gt1_images'])}",
                           f"{int(g.loc['old48','P10_boot_halfwidth_gt2_images'])} → {int(g.loc['pooled256','P10_boot_halfwidth_gt2_images'])}",
                           f"{int(g.loc['old48','P10_rank_halfwidth_gt2_images'])} → {int(g.loc['pooled256','P10_rank_halfwidth_gt2_images'])}",
                           f"{g.loc['old48','mean_mcse_median']:.3f} → {g.loc['pooled256','mean_mcse_median']:.3f}"])
    whole_rows = []
    for scope, title in [("all_random_prefix_k", "全部合法可估k"), ("nonexact_display_k", "排除已有精确边际的其余k")]:
        for metric, label in [("Q_mean", "均值"), ("Q_p10", "P10")]:
            g = bands[bands.panel.eq("fixed_N_ge_30") & bands.difficulty.eq("全部") & bands.band_scope.eq(scope) & bands.metric.eq(metric) &
                      bands.support_rule.eq("same_images_estimable_in_three_primary_cohorts")].set_index("cohort")
            whole_rows.append([title, label] + [f"{g.loc[c,'halfwidth_median']:.3f} / {g.loc[c,'halfwidth_p90']:.3f}" for c in ["old48", "new208", "pooled256"]])
    revision_rows = []
    for k in [3, 6, 10, 20, 30]:
        g = revisions[revisions.panel.eq("fixed_N_ge_30") & revisions.difficulty.eq("全部") & revisions.newer_cohort.eq("new208") & revisions.k.eq(k)].set_index("metric")
        revision_rows.append([k, f"{g.loc['Q_mean','signed_change_mean']:+.3f}",
                              f"{g.loc['Q_mean','absolute_change_median']:.3f} / {g.loc['Q_mean','absolute_change_p90']:.3f}",
                              f"{int(g.loc['Q_mean','absolute_change_gt2_images'])}/157",
                              f"{g.loc['Q_p10','absolute_change_median']:.3f} / {g.loc['Q_p10','absolute_change_p90']:.3f}",
                              f"{int(g.loc['Q_p10','absolute_change_gt5_images'])}/157"])

    hard_rows = []
    for name, short in [("3_to_6", "3→6"), ("10_to_20", "10→20"), ("20_to_30", "20→30")]:
        for metric, label, percentage in [("marginal_Q_delta", "均Q", False), ("Q_p10_delta", "P10", False), ("Q_sd_delta", "SD", False),
                                          ("actual_consensus_failure_delta", "实际共识失败率", True)]:
            hard_rows.append(interval_entry(short + " " + label, row("fixed_N_ge_30", "ordinary_manual", "困难", name, metric), percentage))
    ab_rows = []
    for metric, label, percentage in [("marginal_Q_delta", "均Q", False), ("Q_p10_delta", "P10", False),
                                      ("Q_sd_delta", "SD", False), ("actual_consensus_failure_delta", "实际共识失败率", True)]:
        vals = [row("fixed_N_ge_30", "ordinary_manual", "困难", "20_to_30", metric, c).estimate * (100 if percentage else 1)
                for c in ["old48", "stage1_104", "stage2_104", "new208", "pooled256"]]
        ab_rows.append([label + ("（pp）" if percentage else "")] + [f"{v:+.3f}" for v in vals])
    door_rows = []
    for name, short in [("10_to_20", "10→20"), ("20_to_30", "20→30")]:
        for metric, label, percentage in [("marginal_Q_delta", "均Q", False), ("Q_p10_delta", "P10", False), ("Q_sd_delta", "SD", False),
                                          ("actual_consensus_failure_delta", "实际共识失败率", True), ("output_unscoreable_delta", "输出不可评分率", True)]:
            door_rows.append(interval_entry(short + " " + label, row("interval_eligible", "doorway_manual", "单列", name, metric), percentage))
    full_rows = []
    for panel, diff, name, label in [("fixed_N_ge_35", "全部", "30_to_35", "固定N35全体30→35"),
                                     ("fixed_N_ge_35", "困难", "30_to_35", "固定N35困难30→35"),
                                     ("fixed_N_ge_30", "全部", "30_to_full", "固定N≥30全体30→实际满员")]:
        for metric, metric_label, percentage in [("marginal_Q_delta", "均Q", False), ("Q_p10_delta", "P10", False),
                                                ("Q_sd_delta", "SD", False), ("actual_consensus_failure_delta", "实际共识失败率", True)]:
            full_rows.append(interval_entry(label + " " + metric_label, row(panel, "ordinary_manual", diff, name, metric), percentage))

    md = """# 自然随机进入：最终读数与采用判断（2026-10-26）

本文件只汇总已闭合的本轮自然抽样结果，供综合报告直接采用。实际输入提交：`b9bcec809fbaec8ab055931a1abb7baa5db44dac`。`NATURAL_FINALIZATION_COMPLETE.json`为194池完成状态；本文件没有追加融合、重抽或调参。

## 1. 主判断

**48条足以支持当前数据中跨图片的主要平均曲线形状，但不足以把多数单图低人数曲线、低尾和小概率失败精确到本项目的工作尺度。统一追加至256条显著提高了这些估计的精度；单图整曲线P10仍是最主要的未精确量。** 本轮完成了194个Manual池的统一208条独立完整排列追加，分为相互独立的A104、B104。普通177图、门洞17图分别分析；旧53重点池的额外历史路径不混入统一256主比较。

主要用途可收尾为：简单、中等图继续增人的多数收益保留；困难图后段的“均值平台、低尾与换组波动改善”被独立批次支持；门洞须同时报告均值下降和实际失败增加，不能套用普通图结论。新增顺序带来的同k数值修订是对同一固定人员池分布的估计更新，不是更换了人员、算法或GT后产生的效应。

自然主域是每池48+208次随机排列抽取，共40,352次新增自然排列抽取；小池抽到重复完整排列仍是合法抽取，统计保留频数。每条路径内部无放回，各k前缀团队均匀；同团队复用端点，满员只剩一个已知团队。k2保持设计延期。预测分类和进入策略的结果另由策略分支报告，本自然分支不赋予新分类策略验证身份。

## 2. 逐点精度提高，整条单图曲线仍不能等同逐点达标

固定普通N≥30为157图/22栋，其中简单105图/22栋，中等25图/14栋，困难27图/14栋。下表各行分母均为157；左值旧48、右值合并256。均值MCSE=1分是一个标准误，常用近似的逐点95%半宽约2分，并非95%误差≤1分。P10经验区间和总体inverse-CDF的秩区间不是同一种精度保证。

""" + markdown(["人数", "均值MCSE>1图数", "P10经验95%半宽>2图数", "P10秩95%半宽>2图数", "均值MCSE中位数"], point_rows) + """

旧历史保存表的P10经验半宽计数137/110/80/44仍保留；本轮用统一种子重算旧48为137/112/79/44。旧实现已经按旧24、新24分层重抽完整路径；差异来自随机种子及相应重抽序列，不是本轮新增融合收益，也不是把不分层方法改成分层方法。

同一157图三主版本均可估的**单图整曲线95%最大绝对偏差经验带**如下，每格为图片间“半宽中位数 / P90”（Q分）；所有相关每图重抽均有2,000个完整有效结果。全部合法k是各图从1到实际N的合法可估k，k2和不可评满员不补零；每图29—34个点。排除精确边际后为26—31个点。

""" + markdown(["曲线范围", "统计量", "旧48", "独立新208", "合并256"], whole_rows) + """

合并256的均值全曲线半宽仍有79/157图大于2；P10为152/157。排除已知精确边际后分别为42/157和130/157。这里不是宣称每张图都要达到同一严格整曲线标准，而是明确“很多单点较精确”与“整条曲线同时较精确”的用途差别。已有完整目录的单人、缺一人及满员应优先展示精确边际；纯路径结果继续保留用于衡量抽样误差。

依据：[逐点精度表](results_stage2/PRECISION_REACH_BY_LAYER_K.csv.gz)、[整曲线共同支持读数](results_stage2/FINAL_READOUT_WHOLE_CURVE_PRECISION.csv)、[逐图带与可估k](results_stage2/NATURAL_CURVE_BAND_SUMMARY.csv.gz)、图F02/F04。

## 3. 独立新样本实际改变了哪些单图读数

下表为固定157上“独立新208−旧48”，没有把包含旧样本的合并结果当作独立检验。绝对差分布均在同k、同图支持上计算。

""" + markdown(["人数", "跨图均Q修订", "单图均Q绝对修订 中位数/P90", "均Q绝对修订>2", "单图P10绝对修订 中位数/P90", "P10绝对修订>5"], revision_rows) + """

总体均值修订小而单图修订大可以同时成立。事后展示规则只选取固定157中k3—10最大均Q绝对修订、并排除三个既定案例，得到`uNb9QFRL6hY-40`：k9均Q从77.332改为70.026（−7.306）。它在k30的样本P10从82.155改为49.364，k32从95.581改为49.423；这些低分峰的频率修订可以远大于均值修订。该案例不用于决定抽样预算，也不代表全体图片。

图N05另外完整展示既定`wc2JMjhGNzB-46`、`VFuaQ6m2Qom-04`、`rPc6DW4iMge-06`。每图均保留从1到实际N的旧48、独立新208和合并256，均值逐点经验带、P10秩区间和实际共识失败CP区间，k1/N−1/N的有限目录真值采用黑色点。满员失败区间遮罩，只显示唯一团队的已知0/1。

依据：[同k修订表](results_stage2/FINAL_READOUT_POINT_REVISIONS.csv)、[逐图精确比较](results_stage2/PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz)、[N05选例](figures_stage2/N05_CASE_SELECTION.csv)、[N05绘图源数据](figures_stage2/N05_CURVE_SOURCE.csv.gz)。

## 4. 困难图：后段平台与低尾改善保留，前段增益幅度需要更新

以下全部为固定27图/14栋、合并256、图片等权。“正/负/零”是图片效应方向，零阈值保留近机器精度容差；正向不总是更好，例如失败率增加属于负面结果。路径区间固定这些图片、重抽整条路径；建筑区间固定各图估计、整栋重抽，是不同不确定性来源，不能互称。

""" + markdown(["人数段/量", "平均变化", "实际支持", "正/负/零图数", "路径95%范围", "建筑95%范围"], hard_rows) + """

困难3→6的均Q增益由旧48的+7.119修订为+6.107；A104、B104分别+6.001、+5.740，独立新208为+5.874。升质方向在26/27图成立，幅度应采用新结果。同时实际共识失败率增加4.326个百分点，不能用可评分团队的均值改善遮住失败。

困难20→30均Q变化−0.175，路径范围和建筑范围均跨零；16图升、11图降。因此保留“后段平均变化较小，现有结果未显示明确持续升高或下降；低尾和换组波动仍改善”，不写成证明完全不变。P10改善24/27、SD下降25/27；独立A/B如下。

""" + markdown(["20→30统计量", "旧48", "A104", "B104", "独立新208", "合并256"], ab_rows) + """

A/B的均Q分别−0.228/−0.207，P10分别+5.153/+3.515，SD分别−4.631/−4.792；多数改善判断相符，P10具体幅度仍明显受抽样影响。实际失败率减少1.100个百分点在当前图片路径误差范围内清楚，但建筑重抽范围跨零，不泛化为每栋建筑都会减少失败。

简单105图的20→30均Q+0.501，93升/12降，P10+2.404、105图均升；中等25图均Q+1.802，21升/4降，P10+3.909、23升/2降。简单、中等的多数增人收益保留，与困难后段平台分别叙述。

依据：[人数段完整结果](results_stage2/COMMON_SUPPORT_INTERVAL_SUMMARY.csv.gz)、[独立批次对照](results_stage2/BATCH_INTERVAL_CONTRAST_SUMMARY.csv.gz)、[方向重复逐图表](results_stage2/INDEPENDENT_INTERVAL_REPETITION_PER_IMAGE.csv.gz)。方向表前段使用各自实际容量，不能把其中31张困难3→6图误写成固定157中的27张。

## 5. 门洞：低尾收敛不等于平均提高或失败减少

门洞单列。10→20为17图/9栋；20→30的均Q/P10/SD为共同可评15图/9栋，失败用全部有该容量的16图/9栋。下面保留它们的不同分母。

""" + markdown(["人数段/量", "平均变化", "实际支持", "正/负/零图数", "路径95%范围", "建筑95%范围"], door_rows) + """

10→20均Q下降在12/17图，低尾改善在13/17图、SD下降在13/17图；20→30均Q平均仍降，但8/15图小幅升、7/15降，均值受部分较大下降影响。P10提升12/15、SD下降14/15，与实际失败率上升9.131个百分点并存。对同一有限人员池，这说明输出可能集中到较低质量或难以完整连接的结果，不应将“波动变小”自动解释为准确性改善；具体结构与连接证据交由已保存案例解释。

图F03门洞完整共同容量展示到27人，候选17、全程共同质量支持16；这不是门洞数据的终点。30人及满员仍在逐图表。30→实际满员的质量仅11图/6栋可比，均Q+0.265，但实际失败比较保留16图/9栋、增加9.717个百分点。

## 6. 35人与实际满员：质量支持和失败分母必须一起出现

固定N≥35实际为92个N35池/22栋；满员可评分91图，困难候选8图/7栋中可评分7图/6栋。`VFuaQ6m2Qom-04`满员为真实3节点共识失败，不能从失败分母删除。

""" + markdown(["范围/量", "平均变化", "实际支持", "正/负/零图数", "路径95%范围", "建筑95%范围"], full_rows) + """

普通177池的满员有1个、门洞17池有6个不可评分端点，全部属于实际共识失败，不是输出已生成后不可评分。它们是原来已经确定的固定端点，本轮没有因为重新抽到它们而新增7个独立团队。满员可评分时SD=0来自只剩一个人员集合，不表示更接近GT。固定157的30→实际满员保留10张原本N30的合法零变化图，不能删掉后只统计真正加人的图。

## 7. 48条遗漏的小概率结果，和仍然不精确的P10

在旧48实际失败次数为0而独立新208出现失败的图×人数点中：普通177全体有186点、54图/18栋；其中固定157为172点、48图/16栋。门洞17有45点、11图/6栋。输出已生成但不可评分另为普通37点、11图/8栋（固定157为33点、9图/7栋），门洞49点、8图/7栋。新增发现都在k3—N−2内部；单人、缺一人和满员没有新出现的这类0→正变化。图×k不是独立图片数。

对未穷尽的固定k，零次失败的一侧95%二项上限从48次约6.05%降至256次约1.16%；它约束未知失败频率，不把“没见到”写成不存在。已知完整目录则直接报告真实有限失败率。

精确边际还给出实际反例：合并256的177个普通单人点中，经验P10半宽≤2但距总体inverse-CDF P10超过2分有4点，超过5分有1点；按历史完整目录linear口径比较则为6点和0点。不能混用两种目标来渲染精度。`uNb9QFRL6hY-06`的低分成员真实频率1/9，却在256抽取中只出现17次，样本P10及经验区间停在下一质量峰；其完整有限目录应直接用于该点。

`wc2-46`缺一人点的低峰频率，旧48为2/48，新208为24/208，合并256为26/256；合并linear P10在两峰间插值为74.958，逆CDF估计52.601，而精确总体inverse-CDF为51.951。独立新208在这个点反而比合并256更接近精确值；保留全部旧样本，不为了让结果更漂亮删除旧样本。已有完整目录的频率和两种分位数定义均可核验。

依据：[新发现失败读数](results_stage2/FINAL_READOUT_NEW_FAILURES.csv)、[全部逐图比较](results_stage2/PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz)、[精确边际区间诊断](results_stage2/EXACT_ANCHOR_INTERVAL_CONTAINMENT_AND_NARROW_MISSES.csv)、[精确分位数预算分解](results_stage2/EXACT_P10_EXPECTATION_BUDGET_COMPARISONS.csv.gz)。这些边际区间包含率只是当前有限目录上的描述，不作外部覆盖率证明。

## 8. 质量分项解释：平台并非所有误差项都不动

在old48、新208、合并256共同图片且两端均有相应分项的支持上，合并256困难27图20→30：地面损失块平均+0.0453（15图下降、12图上升），方向损失+0.00431（14降、13升），高度损失−0.001095（24降、3升）。平均质量近平台时，高度项多数改善，范围／平面和方向的响应分化；少数较大变化能使地面损失均值与多数方向不同。

门洞10→20，17图的地面损失+0.1098、方向损失+0.01006、高度损失−0.003461；20→30同分项共同15图分别+0.1250、+0.03662、−0.000686。分项波动说明不同几何维度可以反向，不能仅从一个综合Q或SD推断全部几何更好。这里是冻结标量的条件均值描述，不作非线性Q的可加贡献分解；B8块是无量纲损失、越低越好，不是百分比或0—100分。

分项由已保存原始测量量按冻结公式补齐命名列，没有重算融合或改变Q。各分项的有效路径数和图片支持保存在原表；可用原始几何字段的支持可能大于完整质量分项，不能混用分母。

依据：[同支持分项人数段表](results_stage2/FINAL_READOUT_MATCHED_COMPONENT_INTERVALS.csv)、[逐图逐人数分项](results_stage2/NATURAL_COMPONENTS.csv.gz)。几何的独立批次及U统计量误差见几何专题，不将上述质量损失块代替几何波动。

## 9. 采用与停止建议

1. **跨图主结论可采用，当前统一预算可以停止。** 采用完整256主表、独立新208和A/B对照；保留旧48身份。简单／中等收益、困难后段均值平台而低尾改善、门洞后段风险分别写，不追求一条全体单调曲线。
2. **单图展示采用256加已有精确边际，配真实区间与状态。** 低人数和离散P10应保留区间，不把折线小拐点或单一P10值当精准判据。满员采用唯一团队的精确结果。
3. **若将来用途要求单图低人数P10在±2分以内，需要单独预定更高的完整路径预算。** 本轮同一套人员池并未改变，因此可复用端点；但对接近10%边界的低分峰，不承诺某个统一次数即可消除跳峰。先报告已有有限目录或低峰频率区间，再决定该图的精度要求是否值得计算。不是把bootstrap次数加大，也不是只根据本轮噪声选择几个k补算。
4. **类别结论不因本轮而重新分类。** 本轮改变自然团队基线的估计精度、低尾和失败读数；没有改变既有精确团队端点或严格ABC替换事件。需要更新的是将随机基线误差当成确定效应的解释，而不是重写已有分类。四策略的历史标签身份及配对支持沿策略专题说明。

## 文件入口与本轮动作

- 本文件与四张`FINAL_READOUT_*`表：从正式结果重新汇总，无新增融合、无新增重抽。
- `extract_final_natural_readout.py`和`write_final_findings.py`：可重复生成小表与本文件。
- `plot_individual_full_curves.py`：N05图、完整SOURCE、精确锚点与事后选例清单；代码要求194池最终完成标记。
- F01/F03使用全程共同图片支持；F04同时保留全部合法k和非精确边际k，图中与小表均列实际可估分母。已实际查看F01、F03、F04和N05，k1孤点可见、k2缺口保留、VFua满员缺Q未补零。
- 以上数据和图由主线程连同新增真实端点与几何统一打包、下载取回核对；本文件不将方法回执当作原始计算结果。
"""
    write_bytes(owner / "FINAL_NATURAL_FINDINGS_ZH.md", md.encode("utf-8"))
    save_csv(pd.DataFrame(selected_rows).drop_duplicates(), src / "FINAL_READOUT_REPORT_INTERVAL_ROWS.csv")


if __name__ == "__main__":
    main()
