# HOHONET v2.1：人工顺序接入后的直接 AC 全链影响评估

版本：`v21_targeted_manual_order_assisted_20261104_v1`。冻结来源提交：`ac395e703d1fef573d1ef3e105df0286d62a0468`。本目录是独立辅助分析分支；原 `research/workers/personnel_ac_v21_20261030/` 的自动结果保留。

## 1. 交付结论与适用边界

本批已经完成直接 AC 的真实引用闭包：**11 个确认顺序端点、9 个池、339 个方法事件，去重后 245 个物理对**。其中 10 个端点成为可评的条件完整输出，1 个端点在固定坐标下仍有底面自交。原受影响事件的配对 Q 全部缺失；辅助顺序接入后新增 **257 个可评方法事件，对应 193 个物理对**。这说明可评覆盖扩大，不能计算“原 Q 为零时的提升”。

主域的直接 AC 50% 主目标条件没有新增 Q 支持。本批改变的主域主表有符号 Q 条件均保持方向，但有些更细的研究叙述必须改写或加条件：共同池的方法绝对幅度次序、主域 3→1 三段分解的补人段、固定换人块且 m=5 时背景人数增大的阶差，以及部分 `other_admitted` 纯类、联盟和同 XZ 背景效果。逐条判定及精确选行条件见 [CONCLUSIONS.csv](CONCLUSIONS.csv)。

57 组来自定向反例审查；本目录只处理其中实际被 AC 引用的 11 组。不能由本结果推断所有无环输出都能被人工顺序修复。辅助顺序的成功也不等于自动方法成功，更不等于场景几何得到新的真值验证。

## 2. 方法、固定合同与可评支持

端点来自第一批 [ENDPOINTS.jsonl.gz](../endpoints/ENDPOINTS.jsonl.gz)，以 `team_key + reference_id + reference_version` 绑定。本批仅复用这些已核查的几何和分项，读取其他 237 个必要同伴的原生保存端点，共载入 248 个端点身份。没有重新融合、选择节点、组织团队、拟合分类、重新选择分类方案或更改参考。为了保持原流程，差值和几何距离仍通过冻结 `ac_measure_events.compute`、`legacy_geometry_diagnostics` 及原汇总定义生成。

固定项包括节点和成员、原坐标与票数、团队、身份/参考、类别及方向、登记事件和链接、官方难度及结构/几何情境、原始记录劳动与其来源。输出状态和几何/质量指标是可变项。人工排序劳动没有时间记录，因此保持未知；不能将其记作零，或由原记录时间不变推出人工辅助更省工。

| 范围 | 被触达方法事件 | 被触达物理对 | 原配对 Q 可评 | 辅助后配对 Q 可评 | 辅助后可评物理对 |
|---|---:|---:|---:|---:|---:|
| primary | 203 | 154 | 0 | 137 | 113 |
| other_admitted | 136 | 91 | 0 | 120 | 80 |
| 合计 | 339 | 245 | 0 | 257 | 193 |

来源：[SUPPORT_SUMMARY.csv](SUPPORT_SUMMARY.csv)。方法事件的重复方法标记不能作为独立物理重复实验。完整 Q 与地面分项也必须分开：完整 B8L2/D10 有 257 个可评事件，IoU2D 等部分地面指标有 260 个；每项按自己的有限值支持计算，见 [AFFECTED_EVENT_SUPPORT_BY_METRIC.csv](AFFECTED_EVENT_SUPPORT_BY_METRIC.csv)。

三个层次分别报告：

1. **连接方式变化**：人工确认顺序替代失败的自动连接，固定选择的节点及全部原坐标不变。
2. **可评支持扩展**：新增有效几何使原本缺 Q 的端点/事件进入相关指标。
3. **原共同支持变化**：9 个池中原来可评的 B8L2、D10 及两端标量在共同支持上保持不变。聚合均值变化来自新增支持及原权重重新归一化；不能称为原有可评几何质量改善。检查见 [COMMON_SUPPORT_AUDIT.csv](COMMON_SUPPORT_AUDIT.csv)。

## 3. 主表、50% 换人、纯类及方法对照

直接 AC 的主域 `n/m=14/7、16/8、18/9、20/10、22/11` 没有新增 Q 支持或主表 Q 改变，因此这条直接 AC 50% 主目标判断保持。严格半队的已有 B 团队支持及 G 指标是另一条真实依赖，见第 6 节；不能把“直接 AC 不变”扩写为“全部半队结果不变”。

主表共更新 92 个池×条件单元、76 个条件组，产生 4,656 条改变的条件×指标记录。每个改变的条件用完整原池支持重聚合，未触达的原条件行仍是正式来源，并非只对 9 个受影响池取平均。

| 条件 | 原图像等权 ΔQ | 辅助后 ΔQ | 有效事件/图像支持 | 判定 |
|---|---:|---:|---|---|
| primary，TARGET_K3，2→3，A 固定 n=28,m=7 | 3.076845 | 4.136295 | 478/60 → 485/61 | 幅度变化，方向保持 |
| primary，TARGET_K3，2→3，完整类等人数池前沿 | 2.390479 | 2.810688 | 1,140/200 → 1,150/202 | 幅度变化，方向保持 |
| other_admitted，RAW3，1→2，纯类 n=m=4 | 15.212662 | −13.675955 | 7/1 → 13/2 | 需改写，小支持翻向 |
| other_admitted，RAW3，1→2，不等人数全类、无背景 | 4.374652 | −3.541337 | 6/5 → 7/6 | 需改写，新增图像后翻向 |

来源：[MAIN_SUMMARY_CHANGES.csv.gz](MAIN_SUMMARY_CHANGES.csv.gz)。`ΔQ=Q_C−Q_A` 保留原方向；角色标签保持冻结名称，不重新按本次分数重命名。

在主域 `n=28,m=7` 的共同池方法对照中，RAW3 相对 OPPSTRUCT 的平均绝对换人幅度差由 **+1.054490 变为 −0.103143**（54→55 个共同可评图像）；相对 TARGET_K2 由 **+0.038760 变为 −1.156838**（52→53 个图像）。因此，无条件的方法幅度排序需改写。这里各方法先平均自己的冻结类别方向，成员和类别语义并不相同；它是描述性对照，不能据此判定分类器优劣或重新开展分类选型。来源：[COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz](context_common/COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz)。

## 4. 七类敏感性与原校正分母

全部实际触达的七类敏感性均已补算。原定义、原方向、原登记身份和权重保持；每类先重现原局部行、池表与原全局受影响条件，确认一致后覆盖受影响行。普通 V1/V2 汇总与后来修正的 `valid≥2`、三段共同支持结果均保留，解释优先使用修正版本。

| 敏感性家族 | 实际改变的原始行 | 改变的池行 | 改变的条件×指标行 |
|---|---:|---:|---:|
| MEMBER_PANELS | 20 | 19 | 1,415 |
| BACKGROUND_CHANGES | 6 | 3 | 63 |
| FIXED_BLOCK_BACKGROUND_STEPS | 110 | 16 | 285 |
| FIXED_A_REPLACEMENT_STEPS | 14 | 4 | 72 |
| UNEQUAL_DECOMPOSITION | 168 | 29 | 1,089 |
| COMPLETE_COALITIONS | 87 | 87 | 1,239 |
| SAMPLING_BATCHES | 14 | 12 | 433 |

来源：[DEPENDENCY_COUNTS.csv](sensitivity/DEPENDENCY_COUNTS.csv)、[SENSITIVITY_SUMMARY_CHANGES.csv.gz](sensitivity/SENSITIVITY_SUMMARY_CHANGES.csv.gz)。上述总计 4,596 条改变记录包含分项和支持列，不是 4,596 个新实验。

### 4.1 同配比成员波动

每个指标仍要求至少两个可评观察。单个合法物理对只能表示覆盖，不被写成“零波动”。本批变化均属 `class_count_preserving_members_D_not_fixed`；`exact_fixed_D_member_panel` 没有受影响行。因此不能把这组成员变化解释为固定背景的纯成员效应。

在主域 n=28,m=7、2→3：TARGET_K3 的 ΔQ 范围均值由 **3.945020→3.916720**，标准差均值 **1.529602→1.516888**，正负混合面板比例 **0.166667→0.163934**，有效图像/面板 60→61。RAW3 的范围由 **4.184275→5.302761**、标准差 **1.530296→1.915816**，有效图像仍为 60。后者说明即使图像/面板数量未变，既有面板内新增可评事件仍可扩大观察到的范围；原共同事件值本身没有变化。

主域 TARGET_K3 纯类 n=m=8、1→2 的混合比例 **0.733333→0.709677**（30→31 个图像），所以“具体成员可改变方向”的判断保持，比例需更新。来源：[MEMBER_VARIABILITY_VALID_GE2_SUMMARY_CHANGES.csv.gz](sensitivity/member_variability_v2/MEMBER_VARIABILITY_VALID_GE2_SUMMARY_CHANGES.csv.gz)。

### 4.2 不等人数三段分解

三段解释使用**同一路径的 total、equal、addition 三段全部有限**的支持；中间子集先在同一 parent 内平均，再按原 parent/池/图像权重汇总。不能把各段分别可评的不同支持直接相加解释。

主域 TARGET_K3、`all_outside_D`、3→2 的结果为：

| 段 | 原图像等权 ΔQ | 辅助后 ΔQ |
|---|---:|---:|
| 等人数替换段 | −7.407800 | −7.502893 |
| 补入剩余目标类成员段 | +2.685634 | +2.386840 |
| 总段 | −4.722166 | −5.116053 |

共同有效路径 784→792、图像 197→199。替换损失仍被补人段**部分抵消**，但净结果仍负；不能概括为一般人数增加都会改善。

同一背景下主域 3→1 的补人段由 **+0.197560→−0.152840**，等人数段 **−2.655621→−2.697412**，总段 **−2.458060→−2.850252**；有效路径 312→316、图像 57→58。因此该方向“补人能抵消损失”的无条件说法需改写。`other_admitted` 还有总段及补人段翻向，应保留独立范围与背景条件，不能混入主域均值。来源：[COMMON_VALID_THREE_LEG_IMAGE_SUMMARY_CHANGES.csv.gz](sensitivity/three_leg_common_support_v2/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY_CHANGES.csv.gz)；人数覆盖见同目录 `COMMON_VALID_DECOMPOSITION_SIZE_COVERAGE_CHANGES.csv.gz`。

### 4.3 背景人数、固定 A 及同 XZ 背景

冻结 X/Z 换人块、嵌套增加 D、n=20→28 时，**m=5 的主域阶差出现翻向**：TARGET_K2 1→2 从 **−0.666286→+3.905215**，TARGET_K3 1→3 从 **−0.170801→+4.271162**，2→3 从 **−0.755925→+3.823113**，三者均为 3→4 个可评图像。m=7 的 TARGET_K3 2→3 仍为 **−1.889315→−0.786955**（60→61 个图像）。因此背景人数增大是否稀释换人效应需要保留 m 与支持条件，不能只给一个总方向。

固定 A 扩大换人块的四个受影响 Q 阶差条件全部从无图像支持变成一个图像可评，提供新增条件证据，尚不能支持稳定单调的换人比例规律。来源均为 [SENSITIVITY_SUMMARY_CHANGES.csv.gz](sensitivity/SENSITIVITY_SUMMARY_CHANGES.csv.gz)。

严格相同 X/Z、相同 n/m 的外部背景对照另行匹配：仅 `other_admitted` 的 Q 结果受影响。TARGET_K3 n=4,m=2、2→3 的背景效果差 **−2.164310→+4.972688**（1→2 图像），池内绝对幅度经图像等权后 **6.970884→9.540285**。1→3 则是从无支持新增一个图像，差值 **6.881548**，不能视为从零改善。固定 X/Z 的原已记录时间消去关系不变；排序新增劳动仍未知。来源：[SUMMARY_CHANGES.csv.gz](sensitivity/exact_outside_background/SUMMARY_CHANGES.csv.gz)。

### 4.4 完整联盟和抽样批次

本批改变的主域完整联盟 ΔQ 条件均保持方向；其幅度与支持更新。`other_admitted` 有多处翻向，例如 RAW3 `role1 → role1+role2`、`more_people`、不含 unknown 背景，从 **3.506096→−4.152378**（5→6 图像）。解释必须携带原 `number_condition` 与 `unknown_background_included`，不能把完整类联盟和等人数纯类对照混为同一实验。

抽样批次仍是原登记样本之间的敏感性比较。TARGET_K3 纯类 n=m=8、1→2 的两批均值差由 **+0.248327→−0.047021**，但方向一致比例由 **0.766667→0.774194**；该近零差的符号改变不等于发现新的稳定方法优劣。RAW3 n=28,m=7、2→3 的批间差 **−0.202463→+0.079943**，同样需区分方向与绝对大小。来源：[SENSITIVITY_SUMMARY_CHANGES.csv.gz](sensitivity/SENSITIVITY_SUMMARY_CHANGES.csv.gz)。

## 5. 难度、输出状态与执行漏斗

原官方难度、结构情境、几何挑战以及冻结类别不改动，仅在这些既有分层下补受影响汇总。`context_common` 更新 312 条情境×指标记录、166 条共同方法指标记录、4 条小响应诊断及 4 条方法池均值记录。没有重新拟合 RFUSE 特征或重新开展分类选型；这些标签是本流程的固定上游，而人工端点重建不是它们的新输入。

全域登记仍为 **412,839 个去重物理对、478,012 个唯一团队**。物理对状态按原配对 ID 去重，图像/楼栋支持按真实集合检查：

| 手工域 | 物理对分母 | 两端 Q 均可评，原→新 | 观察到失败的物理对，原→新 |
|---|---:|---:|---:|
| primary | 365,766 | 358,115→358,228 | 7,651→7,538 |
| other_admitted | 10,570 | 8,676→8,756 | 1,894→1,814 |

半自动域不变。固定坐标下仍自交的端点从 `no_connection` 进入 `invalid_floor`，这是失败类型变化，不能记作恢复可评。完整状态表与分母见 [STATE_DOMAIN_DENOMINATOR_SUMMARY.csv](states/STATE_DOMAIN_DENOMINATOR_SUMMARY.csv)、[GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv](states/GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv)、[UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv](states/UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv)。

执行漏斗沿用原权重：先同一 X/Z block 内背景均值，再等权 block；合并方向时各类方向等权，最后等权池。更新 446 个池×指标单元、792 个总体队列×指标单元，能力/登记/执行计数不变，主规模简表没有改变。来源：[FUNNEL_CHANGES.csv.gz](funnel/FUNNEL_CHANGES.csv.gz) 及 [FUNNEL_IMPACT_RECEIPT.json](funnel/FUNNEL_IMPACT_RECEIPT.json)。

## 6. 严格半队桥接是已有实验的复用

原严格规范化事件中，13 个事件与已补算的人工顺序半队事件完全重叠。仅更新这 13 个事件及其真实桥接汇总，保留其 A/B/C、参考与类方向。339 个直接 AC 事件与该严格条件无交集；严格 66 的相同 F/B 背景对照也无交集，因此这两处没有额外重算。

TARGET_K3 2/3→3/3、已有 `prior_m7_m8` 桥中：

| n/m | 共同可评池 | 严格 G_A，原→新 | 严格 G_S，原→新 | 严格有符号 CA，原→新 |
|---|---:|---:|---:|---:|
| 14/7 | 83→84 | 3.325621→2.927147 | 3.288605→3.032044 | 6.391586→5.910501 |
| 20/7 | 70→71 | 1.464950→1.983032 | 1.346836→1.860570 | 4.318795→3.707231 |

这些 G 仍为正，但幅度变化。桥接复用不是 13 个新的独立实验；直接 AC 没有 B，不能由本次新增配对构造新的跨类减同类效应。来源：[STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz](strict_bridge/STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz)。

## 7. F2/F9 坐标候选：独立展示，未采用

用户提出的 pa4-18 候选将不同身份节点 F2/F9 的 x 同置为 438.8037，y 与原顺序保持。它改变了固定坐标合同，故独立保存于 `coordinate_candidate/`，没有写回上述固定 57 版。

候选端点按原参考和公式得到 B8L2 **39.61561918763198**、D10 **41.30578782236161**；多边形有效、无交叉，但 camera 不在 visibility kernel。沿 50 个实际 AC 引用，仅 44 个获得配对 Q，另 6 个仍因同伴缺 Q 不可评。候选主表有 12 个池条件、558 条条件×指标记录变化，见 [MAIN_SUMMARY_CHANGES_CANDIDATE_ONLY.csv.gz](coordinate_candidate/MAIN_SUMMARY_CHANGES_CANDIDATE_ONLY.csv.gz)。这些变化不并入主固定坐标状态、漏斗、敏感性或最终研究主结论，也不证明坐标调整已获采用。

## 8. 版本、数值、支持与引用检查

本次采用的证据链是：原保存端点 → 原事件测量复现 → 原局部池表复现 → 原全局受影响条件复现 → 单独覆盖人工端点 → 原权重传播。两次早先中断留下的截断 gzip 已从冻结源和已保存的事件覆盖表定向修复；保存函数改为完整字节生成后原子替换。交付前对本目录所有 CSV、gzip、JSON 完整读取，核验 EOF、列宽和重复表头，并清除仅供运行的 staging 链接和过时临时文件。

最终状态见 [CHECKS.json](CHECKS.json)；逐文件 SHA256、大小和行列数见 [FILE_INTEGRITY.csv](FILE_INTEGRITY.csv)；数值误差见 [PARITY_SUMMARY.csv](PARITY_SUMMARY.csv)。所有基线和固定字段检查必须在绝对容差 `1e-7` 内且零不匹配。原始来源文件再以冻结 Git blob 与 SHA256 检查，见 [SOURCE_VERSION_CHECKS.csv](SOURCE_VERSION_CHECKS.csv)。引用参考与节点第一批检查继续由端点目录提供，不以本批聚合结果替代。

原 `EVENT_AND_UNTOUCHED_PARITY.csv` 中仍保留 **40 条字段检查、合计 641 个单元的 `missing_disagreements`**：这列是在文本规范化前直接比较 pandas `isna` 的结果。它们只涉及 `A/C_single_time_source` 和 `actual_D/X/Z_members`；冻结 CSV 的空 token 被 pandas 读为 NaN，原 Python 函数则返回空字符串。已从原记录来源与原成员集合独立重建这 5 个文本字段的全部 1,695 个单元，字面内容逐一一致，实质缺失不一致为零。单元证据见 [TEXT_EMPTY_NORMALIZATION_EVIDENCE.csv.gz](TEXT_EMPTY_NORMALIZATION_EVIDENCE.csv.gz)。原审计列没有删除或置零，数值指标缺失与文本表示差异分开处理。

### 复现顺序

从仓库根目录运行，端点第一批与原冻结源须已存在：

```bash
python -m tools.thesis_main.analysis.evaluate_manual_order_ac_20261104
python -m tools.thesis_main.analysis.evaluate_manual_order_ac_sensitivity_20261104 --phase all
python -m tools.thesis_main.analysis.evaluate_manual_order_ac_context_20261104
python -m tools.thesis_main.analysis.evaluate_manual_order_ac_states_20261104
python -m tools.thesis_main.analysis.evaluate_manual_order_ac_funnel_20261104
python -m tools.thesis_main.analysis.evaluate_manual_order_ac_strict_bridge_20261104
python -m tools.thesis_main.analysis.evaluate_manual_order_ac_coordinate_candidate_20261104
python -m tools.thesis_main.analysis.finalize_manual_order_ac_20261104
```

严格桥还需已有 `half_qonly/HALF_AUTOMATIC_EVENTS.csv.gz`、`HALF_ASSISTED_EVENTS.csv.gz`；坐标候选命令需根目录独立候选保存状态。前五条不依赖候选。所有结果写入本独立目录，原自动来源保持。`metric_shards/` 是 9 个受影响池的完整覆盖表；主表、敏感性和 funnel 标为 patch/affected 的表仅替换其声明键，不可当作完整全域结果。完整去重状态表和严格规范化表则有明确全域分母。
