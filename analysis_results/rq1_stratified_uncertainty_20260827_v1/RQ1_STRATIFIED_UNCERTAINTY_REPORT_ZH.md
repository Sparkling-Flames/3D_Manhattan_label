# RQ1 分层标注不确定性分析（探索性草稿）

生成日期：2026-08-27  
状态：**探索性、非规范、供导师讨论**。本分析不改写现行 P1/C1/C2/T1/V1 合同，也不把历史 eligibility 当作本研究的新排除规则；仅保留去重、批次、条件、可计算性和来源审计。

## 核心裁决

1. **现有数据足以先写出一个有证据的 RQ1 草稿，但证据强度必须分层。** Manual 共有 218 个“批次×图片”单元、187 张唯一图片、22 栋 building。118 个单元达到 `k≥5`，其中 46 个达到 `k≥15`；不是只有 42 张能用。
2. **42 张 P1/C1 高密度图仍是标注人数校准主层。** C2-B 另有 4 个 `k=19–20` 的共同任务，可作独立批次复核，不能无条件与 42 张混成同一总体。
3. **增加人数主要改善当前历史有效标注 roster 的均值估计和稀有 cardinality 检出，不表示标注者“随着人数增加而收敛”。** `D_mask` 是同图两两距离均值的 U-statistic；随机抽取 k 人时其期望近似不随 k 系统改变，变化的是估计误差和类别检出率。
4. **当前只能讨论标注后的困难线索与行为负担，不能称为客观图像难度。** 未校正关联在 P1/C1 间不同，但 scope 分歧与 `D_mask` 本身高度相关；控制 scope 后，困难和 seam 关联均明显减弱，所以不能把 seam 写成已证实的独立机制。
5. **现有数据能筛出有限 roster 下的高输出差异候选，但尚未证明稳定的 1–2 个几何模式或多个正确答案。** cluster 目前只做阈值状态诊断，没有验证同一分区、成员或原型随人数稳定。
6. **人的成分存在，但当前不支持稳定工人画像。** geometry 的跨任务 worker 主效应约2.75%，图片/任务约65.25%，残差约31.99%；后者混合图片×标注者反应、测量误差和未建模因素。部分 worker tendency 可检测，但随机 split-half 稳定性偏弱，不能把“人的不确定性”等同于质量或固定类型。

## 1. 数据分层，而不是只看高密度图

| 层级 | Manual 单元数 | 当前能回答什么 |
|---|---:|---|
| `k≥5` | 118 | 任务级连续分歧分布；按阶段做困难/时间关联；不能把不同批次当 iid |
| `k=2–4` | 60 | 有限的成对/小样本描述，可进入分层敏感性；不宜给单图稳定模式定性 |
| `k=1` | 39 | 不提供同图人际分歧，只能提供有效性、元标签、时长等单标注结局 |
| `k=0` | 1 | 不可评估几何分歧，必须显式保留而非填成最大分歧 |

`D_mask=1−wall-region mask IoU`，0 表示两份输出完全一致，值越大表示空间范围差异越大。在 `k≥5` 层，118 个 Manual 单元的中位数为 0.097（IQR 0.059–0.164）；按阶段分别为 P1（n=30）0.105（0.062–0.191）、C1（n=84）0.095（0.060–0.151）、C2-B（n=4）0.095（0.054–0.206）。`k=2–4` 的 60 个单元中位数为 0.068（0.044–0.137），但任务构成与估计噪声均不同，不能把它与高支持层的差值解释成“人数增加导致分歧变大”。

上述 k 是**计算几何有效支持数**，不是提交人数。1693 个 Manual selected annotations 中，1641 个进入计算几何、52 个进入 invalid lane（3.1%）。`k≥5=118` 使用 C1 amendment calculation repair；若所有阶段统一按 raw-computable 或 strict-normalized 口径，分别为 117 和 116。46 个 `k≥15` 不受该口径变化影响。困难关联与 rarefaction 都是 conditional-valid 结果，invalid 可能相关所造成的选择偏差尚未消除。

Manual 的 218 个单元对应 187 张唯一图片，原因是 C2-B 与 C2-A-RP、以及两个 RP block 中存在同图重复。分析单位始终是 `base image × stage/batch × condition`；同图跨批次可做重复测量，但不是新的独立图片。

P1 另有 18 个 Semi 与 9 个 OOS 高密度单元，C1 有 25 个 Semi 单元。它们全部保留在表中，但 RQ1 的自然人际分歧主分析只使用 Manual；Semi 是 RQ2 的观察性桥接层，因为共享模型初值可能同时降低方差并引入共同偏差。这里的 Manual 独立性是 protocol assumption；当前没有逐条阶段事件去技术证明工人未受他人输出影响。

详见 `support_strata_summary.csv`、`task_cell_metrics.csv` 和 `manual_support_strata.png`。

## 2. 不确定性与困难度

历史界面**没有统一 1–5 主观难度分数**；只有 `trivial` 或遮挡、低纹理、拼接缝、反射、低画质等多选原因。因此下列结果是 post-response perceived-difficulty 关联，不是图像固有难度，也不是因果效应；本版本没有 pre-task、image-only 的客观难度指标。

### P1 Manual（30 个高密度任务，12 栋 building）

- `D_mask` vs 非平凡困难标签率：Spearman ρ=0.687，building bootstrap 95% CI [0.348, 0.929]。
- `D_mask` vs seam 标签率：ρ=0.743，95% CI [0.478, 0.826]。
- `D_mask` vs scope 非 normal 率：ρ=0.808，95% CI [0.658, 0.910]。

### C1 Manual（84 个 `k≥5` 任务，13 栋 building）

- `D_mask` vs 非平凡困难标签率：ρ=0.153，95% CI [-0.107, 0.404]，没有稳定关联证据。
- `D_mask` vs seam 标签率：ρ=0.444，95% CI [0.212, 0.609]。
- `D_mask` vs scope 非 normal 率：ρ=0.548，95% CI [0.365, 0.678]。
- `D_mask` vs 每图 median formal active time：ρ=0.244，95% CI [0.031, 0.372]。
- worker 固定效应后，排除本人几何的 LOO 分歧与 `log1p(active time)` 的组内相关为 0.198（594 个 worker-task，22 人）。

scope-adjusted partial-rank 敏感性进一步显示：P1 的非平凡困难/ seam 关联降至 0.240 [-0.267, 0.798] / 0.225 [-0.097, 0.523]；C1 为 0.137 [-0.101, 0.377] / 0.275 [0.060, 0.467]。这仍不能处理重复 worker、post-response 共因或多重比较，只能说明 raw seam 关联有明显 scope 混杂。boundary/wall 指标方向一致也只是同源几何度量的敏感性，不是独立复现。

因此不能写成“越难就越不一致”或“seam 已被证实为机制”。更准确的草稿是：**标注者报告的困难、scope 判断和几何输出差异共同变化；scope 是当前最强的描述性伴随量，耗时仅呈弱到中等关联。**所有标签比较均未做 multiplicity 调整，阶段差异也未做正式 interaction test。

本次还修正了旧 C1 difficulty parser：原实现没有识别原始 vocabulary 中带下划线的 `low_texture`/`low_quality`，导致旧表中 C1 nontrivial ρ=0.017；修正后为 0.153。旧值由本报告 supersede，几何分歧本身未改变。

### 2.1 人的不确定性、质量与 active time

“图片不确定性”和“人的不确定性”不能从观测数据中完全解绑。更准确的数据生成表述是：在给定图片、协议、界面和工人 cohort 下观察到输出。人的成分至少包含：

- **worker 主效应**：跨图片相对稳定的坐标/复杂度倾向；
- **图片×worker 反应**：不同人面对同一证据作出不同解释；
- **同一人内部波动**：需要盲重复图才能直接估计，当前数据没有。

现有全数据交叉方差输出显示（这是既有辅助模型，不是对本轮RQ1 Manual子集重新拟合；各 outcome 的可用人群也不同）：

| outcome | task/image | worker | residual | 支持 |
|---|---:|---:|---:|---|
| geometry mean pairwise RMSE | 65.25% | 2.75% | 31.99% | 2168行、205任务、26人 |
| quality IoU to GT | 55.99% | 2.91% | 41.10% | 717行、79任务、23人 |
| `log1p(active_time)` | 11.56% | 51.72% | 36.73% | 2069行、214任务、24人 |

这不表示 geometry 只有2.75%与人有关：worker 主效应只捕获跨任务稳定平移，图片×worker 反应进入残差。另一方面，也不能把31.99%全部命名为“人的内部不确定性”。任务分层置换检测到 largest-mode participation 与任务中心化结构数量的 worker heterogeneity，但 supported-minority tendency 未检出；Manual 随机 split-half 的 worker largest-mode rate 中位 Spearman 仅0.257（IQR 0.149–0.360）。因此本研究可报告 worker random effect/tendency，不应建立固定工人类型。

人的差异与质量有联系，但不是同义词。若 reference 本身不唯一或图像支持替代解释，与 GT 较远不自动等于错误；需把分歧、结构有效性、reference质量和盲审并列。全新工人可以用于后续三臂实验，因为 RQ2/RQ3 估计的是统一流程下新 cohort 的平均响应；只要统一培训、跨条件平衡、保留匿名 worker ID并在模型中控制 worker。只有研究历史画像的纵向预测时才必须使用原工人。

active time 更像个人节奏、工作投入、熟悉度和编辑量的混合指标。22名有完整时间画像的工人，其 task-adjusted active time 中位数为123.0秒（IQR 65.4–165.1，范围11.0–401.8）；与 `Q_GT_EB`、`R_peer_stable`、`F_struct_EB` 的 Spearman 分别为 -0.287、-0.159、-0.012。结合上面的51.72% worker时间方差，active time 只能作效率/努力和人—任务反应的辅助分析，不能作为不确定性分数、质量代理或工人筛选轴。

对应复核表见 `human_component_summary.csv`。

## 3. 人数增加后，哪些东西稳定

在 42 张 P1/C1 高密度图上，从每图当前 23–26 个 strict-valid 历史 roster 中，对 `k={3,5,8,10,12,15,20}` 做 1000 次无放回随机子样本。目标是恢复包含该子样本的**有限历史有效 roster** 的 full-sample 值；它不外推到新 worker population，也不包含 invalid 风险。以下两个目标必须分开：

- **估准平均连续分歧**：k=5 时，平均 `P(|D(k)-D(full)|≤0.03)` 为 0.648；k=8 为 0.751；k=15 为 0.909。
- **发现 full support 中存在的多个垂直边界数量**：在 full 确有多种 cardinality 的任务中，k=5 的平均检出率为 0.634，k=8 为 0.731，k=15 为 0.882，k=20 为 0.954。

所以，“5 个人够不够”没有一个单一答案：对这个有限 roster 的平均连续分歧做粗略估计，k=5 已经有信息；对稀有 cardinality 检出，k=5 明显偏薄。这里没有检验完整几何模式的恢复。

以 `P(|D(k)-D(full)|≤ε)≥0.80` 且以后各**预设网格节点**均满足为操作性标准，结果高度依赖 ε：

| ε | early `k*≤5` | intermediate `8–12` | late `15–20` | unresolved |
|---:|---:|---:|---:|---:|
| 0.02 | 7 | 15 | 14 | 6 |
| 0.03 | 13 | 19 | 10 | 0 |
| 0.05 | 27 | 11 | 4 | 0 |

因此 early/late 是 tolerance-conditional 标签，不是图片固有类别；0.03 只是便于阅读的中间容差，并非规范阈值。1000 次 Monte Carlo 在 p≈0.80 时的二项标准误约 0.013，临界任务应视为 borderline。

## 4. “几个人可估准”“看到两种 count”“高差异候选”如何落到真实图片

### 4.1 几个人就够

这里的“够”仅表示在 ε=0.03 下估准有限 roster 的 `D_mask`，不表示恢复完整模式：

- `uNb9QFRL6hY_5948424345f541b9a570b48f1cfcf622`（C1，k=23，D_mask=0.142，k*₀.₀₃=5，cardinality=diffuse_cardinality，threshold-status=supported_multimodal）
- `uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97`（C1，k=23，D_mask=0.109，k*₀.₀₃=5，cardinality=two_dominant_cardinalities，threshold-status=supported_multimodal）
- `wc2JMjhGNzB_dc4a9f470b834de1983c7e605ff06b2e`（P1，k=24，D_mask=0.066，k*₀.₀₃=3，cardinality=cardinality_concentrated，threshold-status=threshold_sensitive）
- `rPc6DW4iMge_9d3eb9f5d38844bfb4e5fb2cd05fd3fd`（C1，k=23，D_mask=0.066，k*₀.₀₃=5，cardinality=cardinality_concentrated，threshold-status=dominant_with_dissent）
- `wc2JMjhGNzB_dda6efcba51c40de8552408953719515`（C1，k=23，D_mask=0.059，k*₀.₀₃=3，cardinality=cardinality_concentrated，threshold-status=threshold_sensitive）
- `uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384`（P1，k=25，D_mask=0.055，k*₀.₀₃=3，cardinality=cardinality_concentrated，threshold-status=dominant_with_dissent）

### 4.2 较大 k 才较常覆盖 full roster 中频数前两种 cardinality

该计算只要求 full roster 中频数前两种垂直边界 count 在子样本里各出现至少一次；第二种可能仅来自 1 人，既不保证它是“主要类别”，也不保证它在子样本中成为 mode：

- `B6ByNegPMKs_cee80ced97274e248d4ccaa582e12624`（P1，k=25，D_mask=0.383，k*₀.₀₃=20，cardinality=cardinality_concentrated，threshold-status=supported_multimodal）
- `B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993`（P1，k=24，D_mask=0.267，k*₀.₀₃=20，cardinality=cardinality_concentrated，threshold-status=not_evaluable）
- `b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15`（P1，k=26，D_mask=0.262，k*₀.₀₃=8，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `yqstnuAEVhm_e3face7b2196414d95ed97151aa13058`（P1，k=24，D_mask=0.252，k*₀.₀₃=20，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4`（P1，k=24，D_mask=0.225，k*₀.₀₃=12，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `rPc6DW4iMge_fbc169773c954580baea6d2798c0d486`（P1，k=23，D_mask=0.222，k*₀.₀₃=15，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）

full-roster cardinality 形状计数为：`concentrated` 19、`dominant+dissent` 7、`two dominant` 2、`diffuse` 14。只有 2/42 在 count 层满足当前 two-dominant 规则；这里的 cardinality 只是垂直边界数量，**不是完整拓扑签名或几何模式**。

### 4.3 当前 roster 下的固定阈值高分歧筛查

全局筛查固定使用 42 张 full-roster `D_mask` 的 q80 cutoff：full 值、任意单 worker leave-one-out 值均超过该固定 cutoff，且 k=15 子样本估计至少 80% 超过同一 cutoff。它不是每次重抽后重新排名 top 20%。满足者 6 张，全部来自 P1，scope 非 normal 率为 20.8%–62.5%：

- `B6ByNegPMKs_cee80ced97274e248d4ccaa582e12624`（P1，k=25，D_mask=0.383，k*₀.₀₃=20，cardinality=cardinality_concentrated，threshold-status=supported_multimodal）
- `B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993`（P1，k=24，D_mask=0.267，k*₀.₀₃=20，cardinality=cardinality_concentrated，threshold-status=not_evaluable）
- `b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15`（P1，k=26，D_mask=0.262，k*₀.₀₃=8，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `yqstnuAEVhm_e3face7b2196414d95ed97151aa13058`（P1，k=24，D_mask=0.252，k*₀.₀₃=20，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4`（P1，k=24，D_mask=0.225，k*₀.₀₃=12，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `rPc6DW4iMge_fbc169773c954580baea6d2798c0d486`（P1，k=23，D_mask=0.222，k*₀.₀₃=15，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）

这首先提示全局 cutoff 受 stage/scope 混杂。改用 P1、C1 各自的固定 q80 后，满足相同 LOO 与 k=15 条件者共 6 张（P1 4，C1 2）：

- `B6ByNegPMKs_cee80ced97274e248d4ccaa582e12624`（P1，k=25，D_mask=0.383，k*₀.₀₃=20，cardinality=cardinality_concentrated，threshold-status=supported_multimodal）
- `B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993`（P1，k=24，D_mask=0.267，k*₀.₀₃=20，cardinality=cardinality_concentrated，threshold-status=not_evaluable）
- `b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15`（P1，k=26，D_mask=0.262，k*₀.₀₃=8，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4`（P1，k=24，D_mask=0.225，k*₀.₀₃=12，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）
- `yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56`（C1，k=23，D_mask=0.216，k*₀.₀₃=20，cardinality=dominant_with_cardinality_dissent，threshold-status=threshold_sensitive）
- `wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6`（C1，k=23，D_mask=0.190，k*₀.₀₃=8，cardinality=diffuse_cardinality，threshold-status=threshold_sensitive）

这些只能称为“当前历史有效 roster 下对固定相对阈值不敏感的高输出差异候选”。不能外推为“无论增加多少人都不会收敛”，也不能把 scope 分歧自动解释为场景多解。

连续分歧最高的 10 个主层任务如下，便于下一步盲审：

- `B6ByNegPMKs_cee80ced97274e248d4ccaa582e12624`：D_mask=0.383，LOO范围=0.368–0.390，k*₀.₀₃=20，cardinality_concentrated，threshold-status=supported_multimodal
- `B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993`：D_mask=0.267，LOO范围=0.206–0.274，k*₀.₀₃=20，cardinality_concentrated，threshold-status=not_evaluable
- `b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15`：D_mask=0.262，LOO范围=0.258–0.266，k*₀.₀₃=8，diffuse_cardinality，threshold-status=threshold_sensitive
- `yqstnuAEVhm_e3face7b2196414d95ed97151aa13058`：D_mask=0.252，LOO范围=0.202–0.259，k*₀.₀₃=20，diffuse_cardinality，threshold-status=threshold_sensitive
- `q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4`：D_mask=0.225，LOO范围=0.210–0.229，k*₀.₀₃=12，diffuse_cardinality，threshold-status=threshold_sensitive
- `rPc6DW4iMge_fbc169773c954580baea6d2798c0d486`：D_mask=0.222，LOO范围=0.196–0.226，k*₀.₀₃=15，diffuse_cardinality，threshold-status=threshold_sensitive
- `yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56`：D_mask=0.216，LOO范围=0.178–0.223，k*₀.₀₃=20，dominant_with_cardinality_dissent，threshold-status=threshold_sensitive
- `e9zR4mvMWw7_4fb8c9be319e4784b4b66f9ca5d839ab`：D_mask=0.199，LOO范围=0.186–0.205，k*₀.₀₃=15，diffuse_cardinality，threshold-status=supported_multimodal
- `B6ByNegPMKs_4b983544c13946e3a3a518c565ad1086`：D_mask=0.194，LOO范围=0.187–0.198，k*₀.₀₃=12，cardinality_concentrated，threshold-status=threshold_sensitive
- `wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6`：D_mask=0.190，LOO范围=0.182–0.193，k*₀.₀₃=8，diffuse_cardinality，threshold-status=threshold_sensitive

### 4.4 operational cluster 仅作阈值状态诊断

完整支持下，用 boundary/wall 阈值 `.90/.925/.95/.97/.98` 做 complete-link operational clustering：8/42 张在至少 4/5 个阈值下都被标为 strong split；20/42 张连状态名称都未在 4/5 阈值下一致。该计数没有比较同一 partition、cluster membership 或 medoid，也没有做 worker 子样本稳定性；即使状态名称重复，也不能称为稳健 cluster/mode。阈值升高还会增加 `not_evaluable`，任何单一阈值的“多峰率”都不能当作真实多解 prevalence。

cluster 结果必须与连续 `D_mask`、cardinality、scope 分歧分轴阅读。尤其是 `scope_non_normal_rate` 较高的候选，可能是协议适用性分歧，不一定是两个同样合理的布局。

## 5. 可用于论文的 RQ1 草稿

> **RQ1：在曼哈顿全景布局标注协议下，默认独立的 Manual 输出在连续几何、垂直边界数量与可计算性方面呈现多大、何种形式的差异；其中图片/任务、标注者主效应与未分解的人—图反应各占什么角色；这些差异的估计随每图支持数增加如何稳定，并与主观困难及行为负担有何关联？**

建议主术语使用 **inter-annotator output variability / operational annotation reproducibility**。在没有专家确认多个模式都与图像证据相容前，不用 ground-truth uncertainty 或 multiple correct layouts。

### 方法段草稿

我们将分析单元定义为 `base image × stage/batch × condition`，同一 worker 在单元内保留分析器所选的最新未取消版本。Manual 独立性按协议假定，历史 formal eligibility 不作为新的探索性排除规则；几何不可计算记录独立计数，不赋为最大距离。连续主指标为同图 calculation-valid 标注之间 `1 − wall-region mask IoU` 的平均值，并以 boundary 与 vertical-wall-event 距离作同源敏感性；结构轴仅统计垂直边界 cardinality，不将角点数误称为完整拓扑。所有总体汇总按图片单元而非 pair 加权。对高密度 P1/C1 子集从有限有效 roster 随机无放回 rarefaction，估计不同 k 下连续分歧误差与 cardinality 检出概率。交叉方差与任务分层 worker 稳定性用于区分图片、worker主效应和未分解残差；困难标签与 active time 仅作 post-response 描述性关联。

### 结果段草稿

现有 Manual 数据覆盖 218 个批次内图片单元，其中按当前 C1 repair/calculation 口径有 118 个达到 `k≥5`，46 个达到 `k≥15`；`k≥5` 层 `D_mask` 中位数为 0.097（IQR 0.059–0.164）。geometry 方差中图片/任务、worker主效应、残差约占65.25%、2.75%、31.99%；部分worker tendency可检测但split-half稳定性弱，故不建立工人类型。高密度有限-roster重抽样表明，较少标注者可粗略估计平均连续分歧，但稀有cardinality检出需要更高支持，且k*对容差选择敏感。困难与seam的raw关联受到scope明显混杂；active time仅呈弱到中等关联且主要具有worker-specific成分。固定阈值候选只能进入盲法专家审查，不能视为已经证明的多个合理真值。

## 6. 与 Semi / 曼哈顿约束的边界

Semi 的模型初始 proposal 被强制满足曼哈顿结构，但仍可能偏离真实墙角。这里必须按 residual 的参照对象拆开：对 Manhattan/墙体内部约束的 residual 下降，只说明 **constraint compliance / internal geometric consistency** 改善；只有相对独立 reference 或图像边界证据的误差下降，才说明 **evidence fit** 改善。不能把二者统称“墙残差下降”。

1. constraint compliance：输出是否满足曼哈顿/结构规则；
2. evidence fit：输出是否贴合图像墙角或独立参考；
3. inter-annotator variability：不同人的输出有多散。

共享预标注可能降低第 3 轴，同时通过共同偏差损害第 2 轴。因此 RQ2 不能只比较方差；必须先冻结 residual 的数学定义，再同时报告 proposal 正误、constraint residual、独立 evidence-fit error，以及 Manual/Semi 输出分歧。

## 7. 仍不能声称什么

- 不能由有限的 23–26 人证明“无限增加人数仍然分歧”。
- 不能把 `C(k,2)` 个 pair 当作独立样本量。
- 不能把垂直边界数量差异叫完整拓扑差异。
- 不能把旧 difficulty 原因映射成不存在的 1–5 难度分数。
- 不能由 42 张高密度图估计所有 187 张图片或总体房型的歧义 prevalence。
- 不能把 cluster 自动解释为多个合理答案；需要盲法视觉审查。
- 不能把 Semi 修正前后坐标变化本身解释为视觉质量提升；至少需要独立图像证据或参考 residual。
- 不能把 finite-roster rarefaction 当成新标注者总体的样本量保证；重复 worker 与 invalid selection 仍需后续敏感性分析。
- 不能把未经 multiplicity 调整的 difficulty/tag 关联或未检验的阶段差值当作确认性结果。

## 8. 文献定位与创新性

多评者分歧并非新主题；创新性应落在结构化 360° 曼哈顿布局、高密度独立重复标注、支持数校准，以及连续几何/cardinality/可计算性的多层分解。外部研究也显示所需评者数依任务和 estimand 而变，没有可直接套用的“每图必须 15 人”：

- Wang et al., TACL 2023：主观 STS 中高一致样本和争议样本的稳定人数不同，不能迁移成布局几何通用阈值。https://aclanthology.org/2023.tacl-1.56/
- CrowdTruth：多个任务的稳定点不同，开放任务在较高支持下仍可能未稳。https://journals.sagepub.com/doi/10.3233/SW-200415
- Berkeley Segmentation：同图多个人工分割被用于评价与人际一致性分析，其评价度量允许不同粒度的分割结果。https://vision.ics.uci.edu/papers/MartinFTM_ICCV_2001/
- QUBIQ：其任务说明强调不确定性的操作定义依任务和数据而定；公开赛道实际使用 3–7 名专家标注，但这只是设计事实，不是最优人数证明。https://qubiq.grand-challenge.org/About/ ；https://qubiq.grand-challenge.org/Participation/
- Pavlick & Kwiatkowski：有些语言任务分歧在增加评者和上下文后仍持续。https://aclanthology.org/Q19-1043/
- Jiang & de Marneffe：分歧可来自输入歧义、指南欠规定与标注者行为，不能只归因于场景本身。https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00523/114372/Investigating-Reasons-for-Disagreement-in-Natural

不依赖“文献中从未做过”这一难以由有限检索证明的表述，当前可直接由本研究设计支撑的候选增量是：

> 面向结构化 360° 曼哈顿布局，本研究利用高密度独立重复标注进行任务内支持数校准，并联合描述连续几何、垂直边界 cardinality 与可计算性三层输出差异。

## 9. 原始数据审计

本次直接重读 18 个 Label Studio 原始导出，而不是只读整理表：

- `export_label/stage1_English/project-39-at-2026-06-28-05-14-65ca3316.json` — 362 annotation versions, SHA256 `f79fb49ae721…`
- `export_label/stage1_chinese/project-28-at-2026-07-01-07-14-56a198ba.json` — 420 annotation versions, SHA256 `a40ea344c04c…`
- `export_label/stage1_English/project-40-at-2026-06-28-05-14-bb74a057.json` — 216 annotation versions, SHA256 `1ce8a32e5708…`
- `export_label/stage1_chinese/project-29-at-2026-06-30-09-00-e7ea6931.json` — 253 annotation versions, SHA256 `63b34e8adce3…`
- `export_label/stage1_English/project-41-at-2026-06-28-05-13-8641854f.json` — 108 annotation versions, SHA256 `307f6e6974a8…`
- `export_label/stage1_chinese/project-30-at-2026-06-30-09-00-69d8051b.json` — 126 annotation versions, SHA256 `2f274f31c2ac…`
- `export_label/stage2_English/project-66-at-2026-07-30-13-01-cdb9fe80.json` — 135 annotation versions, SHA256 `04b95b86ef77…`
- `export_label/stage2_Chinese/project-69-at-2026-07-30-13-02-cb472115.json` — 144 annotation versions, SHA256 `818b27e8ae07…`
- `export_label/stage2_English/project-67-at-2026-07-30-13-01-f5126135.json` — 203 annotation versions, SHA256 `f20c24a83f22…`
- `export_label/stage2_Chinese/project-71-at-2026-07-30-14-18-54a73158.json` — 198 annotation versions, SHA256 `9caa6d1ffad1…`
- `export_label/stage2_English/project-68-at-2026-07-30-13-02-cf7d8306.json` — 54 annotation versions, SHA256 `455a0f2e543d…`
- `export_label/stage2_Chinese/project-72-at-2026-07-30-13-02-f69c5ac4.json` — 54 annotation versions, SHA256 `40f9dd7d1efb…`
- `export_label/c2B_Chinese/project-77-at-2026-08-06-14-39-a247e8c0.json` — 80 annotation versions, SHA256 `faca85af24fd…`
- `export_label/c2B_English/project-76-at-2026-08-06-14-41-45400e98.json` — 80 annotation versions, SHA256 `1f0bd8f88e82…`
- `export_label/c2arp_block1/project-78-at-2026-08-10-07-22-d878a022.json` — 20 annotation versions, SHA256 `1138c36c3f72…`
- `export_label/c2arp_block1/project-79-at-2026-08-10-07-21-c5055ba6.json` — 20 annotation versions, SHA256 `87d6e7ccbb7f…`
- `export_label/c2arp_block2/project-84-at-2026-08-14-08-36-31615637.json` — 20 annotation versions, SHA256 `ed8c8652c7e6…`
- `export_label/c2arp_block2/project-85-at-2026-08-14-08-36-71fffb37.json` — 20 annotation versions, SHA256 `711fd7192849…`

原始版本数 2513；按 `stage/project/runtime task/worker` 取最新未取消版本后 2501。该数量与中性整理底座 `annotation_spine.csv` 的 2501 行一致，但逐 acquisition key 比较只有 2500/2501 个 annotation identity 相同。唯一差异是 C1 project 66 / task 3192 / worker 34：分析器按时间选 6053，正式 spine 选 6052；两版本 result content 完全相同，因此本次几何与 difficulty 数值不变，但它是 provenance gap，不能写成 canonical 身份完全一致。

整理底座仅用于覆盖/身份交叉核验，没有被提升为本次几何重算的输入真源。P1/C1 的整理层与原始重算已有既有审计；C2-B 作为历史证据保留，C2-A-RP 已 terminal closeout。`SOURCE_AND_METHOD_SUMMARY.json` 记录生成器及直接依赖脚本 SHA、dirty worktree 状态、seed 和参数；所有生成表的 SHA 写入 `OUTPUT_MANIFEST.csv`。

## 10. 本轮方向审计附件

- `human_component_summary.csv`：从现有方差、worker viewpoint、时间画像和RQ1时间结果中抽取的可复核长表；没有重估正式工人画像。
- `meta_label_research_mapping.csv`：当前 forward-local 元标签的构念、RQ、分析角色、保留/删除候选与 legacy 兼容边界；不改变 XML。
- `literature_claim_audit.csv`：对最相关原始论文逐条记录“能支持什么/不能推出什么”，并修正 Zhou 文献出处与 Schroeder 元数据冲突。

三张表都是本探索性草稿的审计附件，不是正式 schema、方法合同或启动授权；原始导出、active logs、旧元标签和已关闭 C2 工件均未改动。
