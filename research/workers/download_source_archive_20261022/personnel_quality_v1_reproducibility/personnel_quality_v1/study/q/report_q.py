#!/usr/bin/env python3
"""Render the concise Chinese Q/T audit report from computed CSVs."""
import argparse
from pathlib import Path
import json
import pandas as pd


def md_table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
        + ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows])


def main(args):
    p = Path(args.directory)
    f = pd.read_csv(p / 'worker_profiles_enriched.csv')
    q = f[f.axis.eq('B8L2')].set_index('worker_id')
    d10 = f[f.axis.eq('D10')].set_index('worker_id')
    receipt = json.loads((p / 'RUN_RECEIPT.json').read_text())
    classnames = {'above_pool|faster': '相对高／快', 'above_pool|slower': '相对高／慢',
        'below_pool|faster': '相对低／快', 'below_pool|slower': '相对低／慢',
        'above_pool|time_unknown': '相对高／T未知', 'below_pool|time_unknown': '相对低／T未知'}
    rows = []
    for w, r in q.iterrows():
        t = f'{r.T_effect:+.3f}' if r.T_supported is True or r.T_supported == True else '未知'
        if w in ['W018', 'W034']: t += f'（{int(r.T_contexts)}任务）'
        same = int(round(r.LOBO_same_sign_fraction * r.LOBO_folds))
        rows.append([w, f'{int(r.n)}/{int(r.buildings)}', f'{r["mean"]:.2f} / {r.p10:.2f}',
            f'{r.actual_task_intercept_mean:.2f}', f'{r.effect:+.2f} [{r.effect_ci95_low:+.2f}, {r.effect_ci95_high:+.2f}]',
            f'{same}/{int(r.LOBO_folds)}', t, classnames[r.QT_label],
            f'{d10.loc[w,"effect"]:+.2f}' + ('；Q跨零' if r.label != d10.loc[w,'label'] else '')])
    table = md_table(['人员', 'Q任务/楼', '原均值 / P10', '实际任务α均值', '调整Q [95%区间]', 'LOBO同号', 'T效应', 'B8L2描述类', 'D10的Q'], rows)
    text = r'''# 人员 Q/T、绝对质量与任务组成：独立复算报告

数据阶段：**v1**。仓库实际读取提交：`COMMIT`。本模块只核验和解释人员模型，不修改单份 B8L2/D10 评分、GT、资格、清洗或原留出。

## 1. 可以采用的结论

**现有 Q 的任务调整与留建筑验证确实已经实现，且本次独立复算通过。继续采用连续 Q，Q 零点二分和 Q×T 四格可作为有明确定义的描述性候选。绝对质量、Q、速度应并列展示；不把它们加成一个无明确用途的总分。**

- Q 使用同图、同条件、同参考 ID 与版本的双向固定效应模型，不是按三档难度减均值。独立实现的约束线性方程解与已发布 2,068 个 Q/T 画像、5,927 条预测逐项一致，效应最大误差 `7.11e-14`；历史 50 次互斥建筑两半的 2,400 条标签也完全一致。
- 本批重叠丰富，任务调整对排序有实质但有限的影响。W013 从原均值第 22 升至调整 Q 第 17，W031 从第 13 降至第 16；W017 的原均值略高于人员平均而调整 Q 略低。不能据此把其零点跨越解释为能力变化。
- **本轮未证明调整 Q 的预测精度优于原均值。** 主留建筑的 B8L2 相对 MSE 下降为 Q 24.98%、原均值 25.82%；Q 相对原均值的差为 −0.84 个百分点，建筑配对区间 −3.09 至 +0.89。采用 Q 的依据是同任务比较的明确估计目标，不能杜撰预测优势。简单难度调整具有相近数值也不代表已经消除了任务差异。
- Q×T 对单人 Q 预测没有一致增益，但对效率确有解释价值。同一 718 份留建筑时间作答中，Q 二分、Q×T、T 二分、连续 T 的相对时间 MSE 下降分别为 9.26%、39.49%、38.47%、54.15%。T 提供额外效率信息；四格尚未证明比单独 T 二分更好。
- 预先登记的 ±2 分只用于边界敏感性：B8L2 为 8 高／6 边界／10 低，D10 为 8／7／9。它不是合格线，不是统计置信分类，也不取代原二分。需要几何共识解释时使用目标建筑外名单，不能用此处全样本名单选择同建筑的成员。

## 2. 实际估计量与覆盖

设任务 c 的键为 `(image_id, condition, reference_id, reference_version)`，人员为 w：

\[
y_{cw}=\alpha_c+\beta_w+\varepsilon_{cw},\qquad \sum_w\beta_w=0.
\]

逐任务投影去掉截距后，对**人员设计矩阵与成绩同时中心化**，解完整最小二乘方程。原代码用特征分解，本次用带零和约束的 KKT 方程独立求解；两者没有收缩或难度分箱。只有直接对任务内残差求人员平均，通常不等于这个解。

主 Q 是 1,048 份普通 Manual、24 人、87 个精确任务、19 栋建筑，均至少 6 个可比任务、3 栋建筑，且排除了既有原留出。全库存为 3,222 份／27 人；普通 Manual 可计分 1,258 份，包括上述训练以及 210 份原留出。普通 Semi、门洞、其它条件分开列在 `absolute_quality_by_worker.csv`，不拼到主 Q 均值里。绝对分仍以 B8L2/D10 原尺度报告，不是已校准的正确概率。

任务—人员网络全样本秩为 23，24 人共同完成 7 个任务；所有人员对都有直接重叠，最少 12、中央値 31、最多 45 个任务。每个留建筑折仍连通，任意两人至少共同 9 个任务，24 人共同任务仍至少 5 个。不存在用互不连通任务池强行排全员名次的问题。连通性保证当前模型可识别，不保证所有人对所有场景的表现恒定。

每一折先剔整个目标建筑，再拟合、判断支持与分类。评价目标是测试任务内的 `y − 同任务可比人员均值`，预测也在完全相同人员集合内中心化。因此下述误差下降衡量**同任务相对成绩的可预测程度**，不预测新图的绝对分，也不表示人员能力提高了相同比例。原报告的建筑等权，是先在每栋建筑内按作答求 MSE，再对建筑等权。

## 3. 逐人画像与原尺度解释

表内原均值、P10、任务 α、Q、区间全部来自同一 1,048 份主训练面板，便于解释差别。完整文件另含中位数、P25/P75、所有可计分普通 Manual（含原留出）的绝对质量及每种条件覆盖。P10 是当前观测任务组成下的样本低分位数，不能冒充严重失误率；17 份记录人员的 P10 仅由约两个低尾样本决定。

`LOBO同号` 是 19 个主训练建筑留出折与全样本 Q 符号一致的折数，**不是 19 次独立验证**。区间来自建筑整块 2,000 次 bootstrap，2,000/2,000 均可识别；是有限人员池和既定参考/清洗条件下的未作多重比较调整的百分位区间。T 正为较慢、负为较快，单位 `log(1+active秒)`；“相对高”不等于绝对合格。

TABLE

最需要改变解释的人员如下：

- **W013：任务组成确实影响原均值。** 观察均值 61.01，实际任务 α 均值 64.19，是本面板最低；调整 Q 为 −3.18。其原始第 22 名不能直接作为能力第 22 名，调整后第 17 名仍然是相对较低。
- **W031：原始排名相对受益于任务组成。** 原均值 65.27、任务 α 67.76，调整 Q −2.49，排名第 13→16。
- **W018：较高平均表现与低尾可以并存。** 原均值 71.83、P10 26.02、Q +6.72，但区间 −2.13 至 +17.30；26 个任务／9 楼，只有 4 个可比 T 任务。应同时显示高均值、低尾与不确定性，不能借较高 Q 将低尾风险藏掉，也不能凭 P10 自动认定人为严重错误。
- **W011、W017：B8L2→D10 跨 Q 零线。** W011 为 −0.328→+0.138；W017 为 −0.214→+0.382。二者仍处预登记边界带。W011 的 T −0.0041 同样靠近零线，20 个时间留建筑折只有 11 次快、9 次慢。
- **W029：硬二分尤其敏感。** Q −0.126，19 个留建筑折只有 13 折同号，互斥建筑两半仅 2/50 次方向一致；不应将“相对低／慢”写成人的稳定属性。其连续估计仍可保留。

10 人的 Q 95% 区间不跨零，14 人跨零；这不是将 14 人排除分析的理由。区间是否跨零与预先定义的描述性二分解决不同问题，不能为了得到清楚名单而删人或调整切点。

### 任务组成分解与标准化展示

最小二乘正常方程使每人的残差均值为零，所以本面板内有精确分解：

\[
\overline y_w=\overline\alpha_{\mathcal C_w}+\widehat\beta_w.
\]

人员实际任务 α 均值在 B8L2 下为 64.19—68.55。统一的 87 任务等权 α 均值为 **66.7332**，于是共同任务池标准化预测为 `66.7332 + Q`；D10 常数为 68.4167。这个值仅为更直观地展示“若使用相同任务组成”的模型预测，**它与 Q 只差一个常数，信息完全重复，不能当第二票加权，也不能叫实测绝对均分**。模型未包含人员×任务相互作用，故该反事实有加性假设。

![绝对与相对质量](absolute_vs_relative_quality.png)

## 4. 留建筑与原留出比较

下表均是同任务相对成绩的建筑等权 MSE 下降，越高表示比零人员效应基线更能解释差异。同一列各方法用相同作答。

| 方法 | 主 LOBO B8L2：1048/19楼 | 主 LOBO D10：1048/19楼 | 原留出 B8L2：208/4楼 | 原留出 D10：208/4楼 |
| --- | ---: | ---: | ---: | ---: |
| 连续任务调整 Q | 24.98% | 23.69% | 15.93% | 15.10% |
| Q 二分 | 13.36% | 12.85% | 8.65% | 12.89% |
| 训练人员原均值 | 25.82% | 24.41% | 14.67% | 13.46% |
| 仅减简单/中等/困难三个训练均值 | 25.11% | 23.78% | 14.95% | 14.07% |
| 任务内中心化后简单人员均值 | 24.98% | 23.67% | 15.92% | 15.08% |

B8L2 连续 Q 主 LOBO 的建筑 bootstrap 95% 区间为 **10.25%—33.17%**，二分为 2.45%—20.51%。连续 Q 对原均值的配对优势区间跨零；任务调整有明确估计目标，但本次数据不能支持“它一定改善预测”的表述。丰富重叠和比较接近的任务基线使几种估计在本池数值接近，不能据此外推到任务分配更不平衡的人群。

原留出可计分 210 份，来自 16 图／4 楼。缺少主 Q 训练画像的 W022 在 S9-06、S9-10 的 2 份保留为未知，其余 208 份用于诊断。所有目标建筑外拟合；Q 在 4/4 楼的误差均低于零基线。原留出已在项目历史中被查看，**本次是保留原留出后的独立重算，不是新增盲测**；4 楼区间只能作小面板描述，不能据此宣称广泛泛化。

在 Q/T 都支持的相同 940 份上，B8L2 Q 二分为 13.40%、Q×T 为 14.01%；增益 +0.62 个百分点，配对区间 −0.68 至 +1.51。D10 为 13.12% 与 12.58%；增益 −0.54，区间 −1.41 至 +0.77。四格对 Q 没有一致且明确的增量。

## 5. 效率为何仍需保留

来源 T 训练 727 份、23 人有数值，其中 21 人满足支持，留建筑评价 718 份、87 个任务、20 楼。W014 没有主 T 训练数据；W018 仅 4 个可比任务、W034 仅 5 个，不能以其不充分的效应给速度分类。目标匹配 T 是另一面板：训练 418 份，评价 411 份／17 楼，不能用来源任务总时长补齐选定目标专属时间。

固定 B8L2 的 Q 标签，在同一 718 份时间目标上：

| 时间预测信息 | 相对时间 MSE 下降 | 解释 |
| --- | ---: | --- |
| 仅 Q 二分 | 9.26% | 质量类别只能解释少部分速度差异 |
| Q×T 四格 | 39.49% | 加入 T 后能解释更多效率差异 |
| 仅 T 二分 | 38.47% | 四格相对它仅 +1.02 个百分点，区间 −1.83 至 +4.06 |
| 连续 T | 54.15% | 在当前时间预测任务上保留连续幅度更有信息 |

Q×T 比 Q 二分增加 30.24 个百分点，配对区间 21.76 至 38.04；这支持**T 是单列效率信息**。D10 标签下同样方向，增益 33.57 个百分点。不能将预测误差下降写成耗时节省百分比，也不能将快/慢解释成认真/粗心。真实团队成本仍须加总各实际成员同口径活动时间，缺失不补 0；几何质量与共识过程由组合模块独立评价。

![Q与T画像](quality_time_profile.png)

## 6. 本轮采用与边界

主展示采用“观察到的绝对输出质量＋任务调整连续 Q＋覆盖与不确定性”，效率保留连续 T；Q 二分和 Q×T 四格用于可解释的人员构成候选。±2 分边界、低尾、难度分层及单图影响作为诊断，不增加未经验证的新综合权重。

这些 Q 来自当前可用、清洗后的普通 Manual。已被人工剔除的明确严重失误、实际初始化纠错、scope 决策仍由逐对象证据台账补充；本模块没有将它们重新算为 0 分、加权处罚或恢复几何投票。绝对 Q 与相对 Q、标准化预测之间的重复信息已经明确；低尾与严重事件可能部分重叠，仍须按 object_id 去重核对，不能把多个展示栏当多个独立错误。

当前验证是历史有限人员池上的建筑迁移。模型加性、非随机任务分配、场景相互作用、GT/路由可用性与定向审核选择仍限制因果解释。本轮不等待数据 v2，也不将提高单人 Q 预测当成分类的唯一验收条件。

## 7. 文件与可读运行证据

- `worker_profiles_enriched.csv`：24 人×2 指标，绝对分、分位数、任务 α、连续 Q、原/调整排序、区间、LOBO 与两半稳定、T、原二分/四格及 ±2 分诊断。
- `fold_profiles_recomputed.csv`：2,162 行，完整描述折及全库存涉及的 22 个目标建筑；明确训练建筑名单，可供 Semi/共识模块按 `panel,axis,fold,worker_id` 连接。不能用 `full_descriptive` 选择训练建筑的成员。
- `absolute_quality_by_worker.csv`、`worker_coverage.csv`、`worker_task_composition.csv`：全部 27 人库存覆盖及不同质量池，未知/缺失保留。
- `validation_summary.csv`、`validation_by_building.csv`、`paired_model_comparisons.csv`、`predictions_recomputed.csv`：估计目标、分母和配对不确定性。
- `profile_reproduction_bridge.csv`、`network_by_fold.csv`、`worker_pair_overlap.csv`、`bootstrap_audit.csv`、`disjoint_halves_recomputed.csv`：逐项复核、网络与不确定性证据。
- `evaluation_exclusions.csv`：原留出 W022 与时间支持不足等评价未覆盖对象；`worker_low_tail_records.csv`：低尾原对象及原分项，用于追溯，不表示新增剔除。
- `RUN_RECEIPT.json` 保存版本、输入 SHA-256、精确复现误差、原留出数量和限制；`run.log` 保存实际成功输出。两张图均有 PNG 和 SVG。

复现（Python 3，实际环境 NumPy 2.3.5、pandas 2.2.3、Matplotlib 3.10.8）：

```bash
python analyze_q.py --repo /path/to/3D_Manhattan_label --out /path/to/results/q
python plot_q.py --input /path/to/results/q --out /path/to/results/q
python report_q.py --directory /path/to/results/q
```

也可通过 `PANORAMA_REPO` 设置仓库根目录。源码不写仓库，读前/运行末尾核验六个输入文件哈希。`REGISTRATION.json` 保存分析前固定的候选；没有为差异显著而重选阈值。

算法溯源：仓库 `worker_b8l2_d10_20261017.py → worker_b8l2_20261016.py → worker_wq_integration_20261015.py → worker_classification_progress_20261014.py → fit_worker_evidence_strata_20260908.py`（均在 `tools/thesis_main/analysis/`）。原始结果位于 `research/workers/worker_b8l2_d10_20261017/`。本报告数值引用这些冻结表和本次独立运行产物，不借历史 OSPA30 或其他样本的结果代替当前 B8L2/D10。
'''
    text = text.replace('COMMIT', receipt['repository_head']).replace('TABLE', table)
    (p / 'REPORT_ZH.md').write_text(text, encoding='utf-8')
    print('Saved REPORT_ZH.md with the 24-person table.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', default=str(Path(__file__).resolve().parent))
    main(parser.parse_args())
