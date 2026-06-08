# Paper B：Ambiguity-aware enclosed HoHoNet 研究计划 v1

> 状态：Paper B / 非 thesis-facing 的研究规划
>
> 范围：仅规划。本文档不会实现训练代码，不会修改当前 A 线协议，不会修改 Label Studio 生产导入，也不会生成任何路由工件。

## 0. Paper B 的定位与 A 线边界

本文档对应第二条研究线，以下简称 **Paper B：Ambiguity-aware enclosed HoHoNet**。

Paper B 与当前 A 线的标注流程论文相互独立，不是 A 线 thesis-facing 工作流的正式协议扩展。

A 线 HOHONET 主协议保持不变：

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

本文档不修改 `P1 / C1 / C2 / T1 / V1`，不改变 worker admission、`w_max`、`r_u`、`r_u^(s)`、`tau_d`、Score、worker tier、routing freeze、`k0/kmax` 或 stop rules，也不得使用 A 线 Main/Test/Validation 的结果回改这些合同。

Paper B 的目标是：

- 训练一个只输出 enclosed layout 的 HoHoNet 布局预测器。
- 为模糊性和 overextend 风险增加辅助监督。
- 在推理时只输出 enclosed layout 以及风险提示。
- 将风险提示用于 relabel 审计、候选挖掘，以及可能的标注者谨慎提醒支持。

Paper B 明确不是：

- 在 HoHoNet 内部运行时嵌套 Bi-Layout；
- 一个最终的双布局 `enclosed + extended` 预测系统；
- 当前 enclosed-only 标注协议的替代方案；
- A 线 OOS gate 的替代方案；
- 一个 OOS 分类器；
- 一个正式的 `g_t` 实现，或正式 `g_t` 字段的来源；
- 一个 thesis-facing 的 V1 路由工件；
- A 线主结论链的来源。

Bi-Layout 风格的数据与 relabel 思路，只作为模糊性监督、GT 清洗和 overextend 风险学习的来源。

## 1. Paper B 的研究问题

### RQ-B1：Bi-Layout relabel 审计

Bi-Layout 风格的 relabel，是否能减少 MP3D / MatterportLayout 风格标注中的跨门扩张，以及 enclosed / extended 策略混用？

核心关注：

- relabel 后的 enclosed 目标，是否比原始混合策略标签更稳定地停在预期房间边界；
- relabel 是否减少 `overextend_adjacent` 情况；
- relabel 是否为 opening ambiguity 提供了可用的监督信号。

这个 RQ 必须在训练前回答。如果 relabel 并没有减少跨门扩张，Paper B 就不应继续基于这些标签提出模型层面的主张。

### RQ-B2：面向模糊性的 enclosed HoHoNet

一个带模糊性感知的 enclosed HoHoNet，能否在保持 enclosed 布局精度的同时减少 `overextend_adjacent`？

核心关注：

- enclosed-only 布局质量；
- 跨门扩张减少；
- 将辅助的 ambiguity 和 overextend head 作为正则项 / 风险估计器；
- 与一个仅做 enclosed-only fine-tuning 的基线比较。

### RQ-B3：风险提示是候选挖掘，而不是 OOS 分类

ambiguity / overextend 提示，能否作为人工 relabel 和谨慎复核的候选挖掘器，而不是 OOS 分类器？

核心关注：

- 挖掘出的 relabel 候选的精确率；
- 提示暴露带来的假阳性负担；
- 风险被漏掉时的假阴性案例；
- 证明这些提示能丰富 ambiguity 案例，但不会变成自动的 `scope` 或 OOS 标签。

## 2. B0 数据审计优先级：Bi-Layout relabel 审计

在任何训练开始前，Paper B 必须先执行 **B0：Bi-Layout relabel 审计**。

目标：

- 验证 relabel 后的数据是否真的减少跨门扩张；
- 验证在项目的 enclosed-only 标注策略下，relabel 是否减少 `overextend_adjacent` / 跨门扩张；
- 评估负面副作用，尤其是 under-coverage 和过度保守截断；
- 将可靠的 enclosed 目标与不确定或弱派生目标区分开；
- 判断 ambiguity 与 overextend 标签是否足以作为辅助监督。

B0 不是模型训练。其输出应是审计表和过滤后的训练候选列表，而不是自动 GT 替换。

计划输出目录：

`analysis_results/bilayout_relabel_audit/`

计划输出：

- `relabel_inventory.csv`
- `overextend_reduction_audit.csv`
- `ambiguity_case_contact_sheets/`
- `relabel_audit_report.md`

这些输出只属于 Paper B 的研究工件，不是 A 线 P1/C1/C2/T1/V1 工件，也不得被 A 线路由合同消费。

### 2.0 将最新视觉审计观察转化为 B0 检查

HoHoNet-vs-Bi-Layout 的 relabel contact sheet 暗示了以下工作假设。B0 必须把这些视觉观察转化为描述性审计计数，而不是假定它们在全局上都成立。

`hard_prediction_failure`：

- Bi-Layout 风格 relabel 往往减少 HoHoNet 的跨门扩张和 over-parsing。
- 这种改善在许多样本上肉眼可见。
- 但仍有一些样本，HoHoNet 和 Bi-Layout 都错。
- 少量样本里，Bi-Layout 还引入了 HoHoNet 没有的新错误，包括新的跨门扩张或 over-parsing。

`highest_g_score`：

- 与 `hard_prediction_failure` 类似。
- Bi relabel 往往把布局拉回到相机所在房间，减少 `overextend_adjacent` / over-parsing。
- 该组可能与 `hard_prediction_failure` 重叠或重复；B0 在报告组级统计前必须按 `task_id`、`image_id` 和 `scene_id` 去重。

`nominal_prediction_structure`：

- HoHoNet 和 Bi relabel 大体相似。
- Bi relabel 在少数样本里可能略微减少跨门标注。
- 这一组主要是安全性检查：测试 Bi 风格 enclosed relabel 是否不会损伤本来已经正常的样本。

`soft_prediction_complexity`：

- 这是关键反例组。
- 一些样本是 OOS 或疑似 OOS，另一些则极其复杂。
- Bi relabel 可以减少跨门扩张幅度，但也可能变得过于保守。
- 若干样本表现出明显的 under-coverage，即 Bi 忽略了本应被标成相机房间一部分的区域。
- 一些样本的 Bi relabel 很奇怪或不稳定。
- 这些案例应进入 holdout / ambiguity 审计库，而不是盲目当作 enclosed 训练目标。

### 2.1 `relabel_inventory.csv`

建议的行粒度：

- 每一行对应一张图像 / 一个布局实例。

建议字段：

- `sample_id`
- `image_id`
- `scene_id`
- `original_label_ref`
- `relabel_enclosed_ref`
- `extended_reference_ref`
- `has_enclosed_target`
- `has_extended_reference`
- `has_ambiguity_mask`
- `has_overextend_risk_label`
- `target_source`
- `review_status`
- `review_notes`

### 2.2 `overextend_reduction_audit.csv`

目的：

- 比较原始标签与 relabel 后的 enclosed 目标在跨门扩张上的差异。

建议字段：

- `sample_id`
- `original_overextend_adjacent_flag`
- `relabel_overextend_adjacent_flag`
- `overextend_reduced`
- `opening_region_present`
- `boundary_stop_changed`
- `manual_review_required`
- `audit_decision`
- `audit_reason`

B0 的核心审计问题是：

- 在原本存在跨门扩张的样本中，有多少比例的 relabel 能在不损坏 enclosed-room 几何的前提下完成纠正？

### 2.3 B0 审计 schema

B0 应为每个去重后的样本生成一条审计记录。推荐使用 CSV 便于检查，并可选用 JSONL 记录更丰富的备注。

最低必需字段：

- `task_id`
- `image_id`
- `scene_id`
- `source_group`
- `hohonet_corner_count`
- `bilayout_corner_count`
- `hohonet_crossdoor_score`
- `bilayout_crossdoor_score`
- `overextend_reduced`
- `overparse_reduced`
- `bilayout_undercoverage`
- `bilayout_new_error`
- `both_wrong`
- `oos_suspect`
- `open_boundary_ambiguity`
- `expert_verdict`
- `usable_for_B1`
- `audit_notes`

固定的 `source_group` 词表：

- `hard_prediction_failure`
- `highest_g_score`
- `nominal_prediction_structure`
- `soft_prediction_complexity`

固定的 `expert_verdict` 词表：

- `accept_bilayout_enclosed`
- `accept_with_minor_fix`
- `reject_undercoverage`
- `reject_ambiguous_or_oos`

字段解释：

- `hohonet_crossdoor_score` 和 `bilayout_crossdoor_score` 是描述性风险分数，不是准确率，除非存在专家 GT 对比。
- `overextend_reduced=true` 表示相较于 HoHoNet 或原始混合策略标签，Bi relabel 减少了跨门扩张。
- `overparse_reduced=true` 表示 Bi relabel 减少了多余碎片、虚假角点或过度解析的结构。
- `bilayout_undercoverage=true` 表示 Bi relabel 看起来过于保守，遗漏了相机房间的一部分。
- `bilayout_new_error=true` 表示 Bi relabel 引入了 HoHoNet 或原始候选中没有的可见错误。
- `both_wrong=true` 表示 HoHoNet 和 Bi relabel 都不适合作为 enclosed 目标。
- `oos_suspect=true` 只是审计标记，不是 OOS 分类器，也不替代 A 线 scope 裁决。
- `usable_for_B1=true` 只允许用于 `accept_bilayout_enclosed` 以及经过仔细复核的 `accept_with_minor_fix` 行。

### 2.4 B0 描述性指标

B0 应报告去重样本上的描述性比例：

- `overextend_reduction_rate`
- `overparse_reduction_rate`
- `undercoverage_introduction_rate`
- `new_error_rate`
- `both_wrong_rate`
- `usable_enclosed_target_rate`
- `ambiguous_or_oos_holdout_rate`

建议定义：

- `overextend_reduction_rate = mean(overextend_reduced)`
- `overparse_reduction_rate = mean(overparse_reduced)`
- `undercoverage_introduction_rate = mean(bilayout_undercoverage)`
- `new_error_rate = mean(bilayout_new_error)`
- `both_wrong_rate = mean(both_wrong)`
- `usable_enclosed_target_rate = mean(usable_for_B1)`
- `ambiguous_or_oos_holdout_rate = mean(expert_verdict == reject_ambiguous_or_oos OR oos_suspect)`

除非真的有专家 GT 对比，否则这些都应称为描述性审计指标，而不是准确率指标。

所有指标都应报告：

- 总体；
- 按 `source_group` 分层；
- 在去重后的 `hard_prediction_failure + highest_g_score` 联合集合上；
- 单独对 `nominal_prediction_structure` 报告；
- 单独对 `soft_prediction_complexity` 报告。

### 2.5 分组解释

`hard_prediction_failure` 和 `highest_g_score`：

- 潜在 overextend 缩减的主要证据来源。
- 组级结论前必须去重。
- 若 B0 是正向信号，则应表现为：`overextend_reduced` 和 `overparse_reduced` 很常见，而 `bilayout_new_error` 仍不常见。

`nominal_prediction_structure`：

- 安全性检查组。
- 预期效果应较小。
- 核心问题：Bi relabel 是否不会破坏已经正常的样本？
- 若该组中的 `reject_undercoverage` 或 `bilayout_new_error` 比例很高，就应阻止天真地采用 relabel。

`soft_prediction_complexity`：

- 压力 / 反例组。
- 核心问题：Bi relabel 什么时候会变得过于保守或不稳定？
- 除非专家复核明确标记可用，否则这些样本应优先进入 holdout / ambiguity 审计库。
- 这一组必须报告 under-coverage 与 OOS 污染风险，而不是隐藏它们。

### 2.6 B1 门控条件

只有在满足所有条件时，才能从 B0 进入 B1：

- 去重后的 `hard_prediction_failure + highest_g_score` 样本中，`overextend_reduced` 明显比 `bilayout_new_error` 更常见；
- `nominal_prediction_structure` 样本的 `reject_undercoverage` / `bilayout_undercoverage` 比例较低；
- `soft_prediction_complexity` 样本能够被清晰拆分为 `usable_for_B1=false` 的 holdout 案例，而不是被强行塞进训练；
- 审计表能识别出足够多的 `accept_bilayout_enclosed` 和 `accept_with_minor_fix` 样本，以构建干净的 enclosed-only fine-tuning 集合。

B1 保持为：

- 只做 enclosed-only 的 HoHoNet fine-tuning 基线；
- 还没有 ambiguity head；
- 还没有 overextend-risk 辅助 head；
- 还没有双头模型；
- 还没有 Label Studio 谨慎提示。

### 2.7 `ambiguity_case_contact_sheets/`

目的：

- 视觉检查原始边界与 relabel 后边界不一致的案例；
- 区分真实 opening ambiguity 和噪声 relabel；
- 为 Paper B 的数据质量提供定性证据。

每张 contact sheet 应包含：

- 输入全景图；
- 原始 / extended 参考边界；
- relabel 后的 enclosed 目标；
- opening 区域候选；
- 可选的当前 HoHoNet 预测；
- 审计标签和备注。

### 2.8 `relabel_audit_report.md`

必须包含的章节：

- inventory 汇总；
- relabel 来源与 provenance；
- overextend 缩减总结；
- under-coverage / 过度保守截断总结；
- 新错误总结；
- 带去重说明的组级指标；
- 模糊性案例分类法；
- 弱目标排除标准；
- 是否值得进入 B1/B2 训练的判断；
- 已知局限。

## 3. 基于 Bi-Layout 风格 relabel 的训练目标构建

应谨慎解读 Bi-Layout。它并不提供一个完全自动的 MatterportLayout enclosed-vs-extended 分类器。它对 Paper B 的真正价值，是一种半自动识别 opening 引起的模糊性的方法，并据此导出围绕 enclosed 房间边界停止决策的训练信号。

### 3.1 源对象

对于每张全景图，Paper B 可以使用：

- `G_orig`：原始 MatterportLayout / MP3D 风格布局标注，通常更接近 extended-room 或 mixed-policy 布局；
- `G_enc`：经裁决或重标的 enclosed 目标；
- `G_ext`：extended 参考；
- `Q_enc`：relabel 过程中生成的一个或多个 enclosed 候选；
- `opening_candidates`：被怀疑包含开口或跨房间模糊性的列、角点或 BEV 区域；
- `P_hoho`：可选的当前 HoHoNet 预测，仅用于 Paper B 的辅助分析。

最低 provenance 字段：

- `target_source`: `manual_adjudicated`、`bilayout_relabel`、`original_as_extended`、`single_enclosed_only` 或 `unknown`；
- `has_enclosed_target`: 布尔；
- `has_extended_reference`: 布尔；
- `has_ambiguity_mask`: 布尔；
- `has_overextend_risk_label`: 布尔；
- `review_required`: 布尔。

### 3.2 `enclosed_target`

`enclosed_target` 是主布局头唯一优化的布局目标。

优先级顺序：

1. 若有人工裁决的 enclosed GT，优先使用。
2. 只有当选择步骤具有人工批准或等价的审计裁决记录时，才使用 Bi-Layout 风格选出的 enclosed 候选。
3. 如果数据集本来就是 enclosed-only，且没有识别出 opening ambiguity，就使用现有的 enclosed 标注。
4. 如果只有 `G_orig`，且其 enclosed-vs-extended 状态不清晰，除非 B0 审计标记其安全，否则不要把它当作可靠的 enclosed 目标。

建议字段：

- `enclosed_target_cor`
- `enclosed_target_bon`
- `enclosed_target_valid`
- `enclosed_target_source`
- `enclosed_target_review_note`

训练含义：

- `enclosed_target_valid=true` 的样本进入 `L_layout_enclosed`。
- 没有可靠 enclosed 目标的样本，不得作为干净监督来训练主 enclosed layout head。

### 3.3 `extended_reference`

`extended_reference` 不是最终模型的输出目标。它是用于推导模糊性与 overextend 风险监督的参考。

可能来源：

- 原始 MP3D / MatterportLayout 标注，只要它遵循 extended 或 mixed policy；
- Bi-Layout 原始 / extended 分支标签；
- 同一图像的人为保留 extended 参考。

训练含义：

- 同时具有 `enclosed_target` 和 `extended_reference` 的样本，可以提供强辅助监督；
- 只有 `extended_reference` 而没有可靠 `enclosed_target` 的样本，不应训练 enclosed layout head；
- `extended_reference` 不会在推理时输出，也不应被展示为权威的替代标注。

### 3.4 `ambiguity_mask`

`ambiguity_mask` 标记的是图像列或局部区域中 enclosed 与 extended 边界发生分歧的位置，尤其是 opening、doorway 或跨房间连续性线索附近。

建议构造方式：

1. 将 `enclosed_target` 和 `extended_reference` 转换为对齐的 1D 边界曲线。
2. 逐列计算边界不一致：
   - ceiling 差异；
   - floor 差异；
   - 可选的角点邻域差异。
3. 若某列的边界不一致超过预设像素阈值，或者位于已审计的 opening 候选区域中，则标记为 ambiguous。
4. 可选择围绕候选 opening 对 mask 做膨胀，以反映标注不确定性。

建议字段：

- `ambiguity_mask_1d`
- `ambiguity_score_1d`
- `ambiguity_mask_source`
- `ambiguity_mask_valid`

训练含义：

- 当同时有 enclosed 与 extended 参考，或者 opening 区域经过人工审计时，才有强标签；
- 由 proposal 推导出的弱 mask 应降低权重。

### 3.5 `overextend_risk_label`

`overextend_risk_label` 是一个辅助的任务级标签，用来预测模型是否有可能跨越一个在 enclosed-only 协议下应当停住的边界。

建议的正样本来源：

- opening 附近存在较大的 enclosed-vs-extended 分歧；
- 原始标注或模型候选跨入相邻房间，而 enclosed 目标在 doorway / 墙边界处停住；
- 人工复核标记了跨门扩张风险；
- Paper B 特定的 overextend 案例，而不是 A 线 P1 的评分输出。

建议的负样本来源：

- enclosed 目标与 extended 参考在容差内一致；
- 没有 opening 候选，也没有跨房间连续性证据；
- 人工复核后的典型 enclosed 房间。

建议字段：

- `overextend_risk_label`: `0`、`1` 或 `NA`；
- `overextend_risk_confidence`: `strong`、`weak` 或 `unknown`；
- `overextend_risk_source`: `enc_ext_delta`、`manual_review`、`proposal_crossing` 或 `none`。

训练含义：

- 强二元标签用于训练 `L_overextend_risk`；
- 弱标签可以降低权重训练，或只用于验证；
- `overextend_risk_label` 不能被解释为 OOS 真值。

### 3.6 `opening_region_candidate`

`opening_region_candidate` 是一个几何或视觉支撑区域，用来指示 doorway/opening 可能解释边界模糊的位置。

建议构造方式：

- BEV 投影识别可见的候选角点或中断墙段；
- enclosed proposal 生成在 opening 附近标记候选停止点；
- enclosed 与 extended 参考之间的边界差异，定位一段不一致区间；
- 可选的人工作业确认或拒绝该 opening 区域。

训练含义：

- 可以直接监督 ambiguity heatmap，也可以辅助数据过滤；
- 不能演变为 OOS gate 或正式的 non-IID 切分真值。

## 4. Paper B 的最终分阶段路线

Paper B 采用 `B0 -> B0-Z -> B1a/B1b -> B2 -> B3 -> B4` 的保守路线。所有阶段均为 Paper B / non-thesis-facing 研究线程，不改变 A 线 `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)` 主协议，也不修改 `P1 / C1 / C2 / T1 / V1`。

### B0：target-domain MP3D / MatterportLayout relabel audit

B0 是目标域 relabel 审计，不是模型训练。

数据：

- MP3D / MatterportLayout 目标域样本；
- HoHoNet-vs-Bi-Layout relabel contact sheets；
- 已人工审计或待人工审计的 enclosed / extended 差异候选。

目标：

- 验证 Bi-Layout-style relabel 是否真的减少 `overextend_adjacent` / cross-door expansion；
- 量化 `undercoverage`、`new_error`、`both_wrong`、`oos_suspect` 和 `open_boundary_ambiguity`；
- 区分可用的 enclosed 训练目标与 holdout / ambiguity audit bank；
- 产出 B0-cleaned target-domain enclosed targets，而不是自动 GT replacement。

输出：

- B0-cleaned MP3D / MatterportLayout `Y_enc` 候选；
- `usable_for_B1=true` 的 target-domain enclosed target list；
- `usable_for_B1=false` 的 holdout / ambiguity audit bank；
- 描述性 relabel audit report，包括 under-coverage 与 new-error 风险。

退出条件：

- 去重后的 `hard_prediction_failure + highest_g_score` 样本中，`overextend_reduced` 明显多于 `bilayout_new_error`；
- `nominal_prediction_structure` 的 `reject_undercoverage` / `bilayout_undercoverage` 率较低；
- `soft_prediction_complexity` 可以被清楚拆分为 holdout / ambiguity audit bank，而不是被强行用于训练；
- 审计表能识别足够的 `accept_bilayout_enclosed` 和 `accept_with_minor_fix` 样本。

### B0-Z：ZInD raw / visible mapping audit

B0-Z 是 ZInD 数据映射审计，不是训练阶段，也不是 B0 的替代品。

目的：

- 审计 ZInD 的哪一种 layout label 可以映射为 Paper B 的 `Y_enc`；
- 审计 ZInD 的哪一种 layout label 可以作为 `Y_ext_ref`；
- 产出 `usable_for_B1Z` 和 `usable_for_B2_aux` 标记；
- 明确 raw / visible 不自动等价于本项目的 enclosed / extended policy。

边界：

- ZInD 不替代 MP3D / MatterportLayout 的 B0 target-domain audit；
- ZInD raw / visible label 只能经过映射审计后使用；
- 任何 ZInD 派生目标都不得回流 A 线 `g_t`、routing、OOS gate 或正式轮次 artifact。

输出：

- `usable_for_B1Z=true/false` 的 ZInD `Y_enc` 候选；
- `usable_for_B2_aux=true/false` 的 enc/ext paired auxiliary supervision 候选；
- raw / visible 与本项目 enclosed policy 不一致的失败案例 taxonomy；
- 相对 MP3D / MatterportLayout 的 domain gap 风险说明。

详细字段与报告要求见 `docs/paper_b/ZIND_MAPPING_AUDIT_PROTOCOL_v1.md`。

### B1a：target-domain enclosed-only HoHoNet fine-tuning baseline

B1a 是 Paper B 的第一条训练基线。

数据：

- 只使用 B0-cleaned MP3D / MatterportLayout enclosed targets；
- 不使用未经 B0 审计的 Bi-Layout relabel；
- 不使用 A 线 `P1 / C1 / C2 / T1 / V1` 结果训练或调参。

目的：

- 测试清洗后的 target-domain enclosed supervision 本身是否减少 overextend；
- 建立 enclosed 2D / 3D IoU 与 `overextend_adjacent` error rate 的基线；
- 避免在标签质量未确认前把收益归因于 auxiliary head。

输出：

- `P_enc` only。

约束：

- no ambiguity head；
- no overextend-risk head；
- no dual-head；
- no Label Studio caution cue。

### B1b / B1-Z：ZInD layout-only pretraining + target-domain fine-tuning

B1b 也可记为 B1-Z，是数据来源消融，不替代 B1a。

数据：

- 先使用 B0-Z accepted ZInD `Y_enc` targets 做 layout-only pretraining；
- 再使用 B0-cleaned target-domain targets 做 fine-tuning。

目的：

- 测试 ZInD 是否提供有用的 layout prior；
- 量化 ZInD pretraining 对 target-domain enclosed accuracy 与 overextend reduction 的影响；
- 将数据规模收益与 target-domain relabel cleaning 收益分开。

约束：

- B1b / B1-Z 不替代 B1a；
- 没有对应监督时，不加入 depth loss 或 semantic loss；
- 输出仍然是 `P_enc` only；
- 不加入 ambiguity head、overextend-risk head、dual-head 或 caution cue。

### B2：HoHoNet-AE

B2 是默认的 ambiguity-aware enclosed HoHoNet 路线。模型名为 **HoHoNet-AE: HoHoNet with Enclosed Layout Supervision and Ambiguity-aware Auxiliary Heads**。

架构：

```text
I -> HoHoNet encoder -> LHFeat H in R^{W x C}
H -> enclosed layout head -> P_enc
H -> ambiguity heatmap head -> A_amb(x)
pool(H, A_amb) -> overextend-risk head -> r_over
```

输出：

- `P_enc`
- `A_amb(x)`
- `r_over`

训练：

- `L_layout_enc` 只用于 reliable enclosed targets；
- `L_amb` 只用于 audited enc/ext paired samples；
- `L_over` 只用于 audited overextend-risk labels；
- `L_policy_margin` 或 `L_overextend_penalty` 只能作为后续 extension，不能作为默认主张。

约束：

- no final `P_ext` output；
- no automatic `scope`；
- no OOS classifier；
- no formal A-line `g_t`。

详细架构、输入输出合同与损失定义见 `docs/paper_b/PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.md`。

### B3：dual-head HoHoNet ablation only

B3 是消融，不是默认部署模型。

架构：

```text
H -> P_enc
H -> P_ext
```

目的：

- 比较显式 `P_enc` / `P_ext` 双头是否提升 ambiguity 表征；
- 检查 B2 的 auxiliary ambiguity / overextend heads 是否已足够；
- 为 Paper B 的 ablation table 和 failure analysis 提供证据。

约束：

- 不是默认 deployment model；
- 不是最终 annotation interface；
- 不是 A 线 routing signal；
- 不把 `P_ext` 暴露为最终 Paper B 输出；
- 不将双头分歧合并进正式 A 线 `g_t`。

### B4：Label Studio caution cue pilot

B4 只能在 B1/B2 已有证据后进行，并且仍然是 Paper B / non-thesis-facing pilot。

前置条件：

- B1a/B1b 已说明 enclosed-only baseline 的行为；
- B2 已说明 `A_amb(x)` 与 `r_over` 的有效性；
- cue threshold 已冻结；
- cue false positive burden 可接受。

允许用途：

- 非阻塞地提示人工复核 doorway / opening / possible cross-door extension；
- 记录 `cue_level`、`cue_reason`、`warning_text_version`、`cue_shown` 和 `cue_acknowledged`；
- 作为 relabel candidate mining 和 caution support 的研究证据。

约束：

- non-blocking cue only；
- no auto `scope` / `model_issue` / `difficulty`；
- no task hiding；
- no A-line protocol effect；
- 不加入 A 线正式 Semi-Auto condition。

## 5. 损失设计

B2 的总损失：

```text
L = L_layout_enc
  + lambda_amb * L_amb
  + lambda_over * L_over
```

权重必须只在 Paper B 的开发数据上选择，不能使用 A 线 P1/C1/C2/T1/V1 的结果来调参。

### 5.1 `L_layout_enc`

目的：

- 训练主布局头去预测 enclosed-only 的房间边界。

可用样本：

- `enclosed_target_valid=true` 的样本。

排除样本：

- 只有模糊原始 GT、但没有可靠 enclosed target 的样本；
- enclosed 选择没有经过审计、可能编码了错误停止边界的样本。

### 5.2 `L_amb`

目的：

- 训练辅助 head 去定位模糊的 opening 或跨房间连续性区域。

可用样本：

- 强：同时存在 `enclosed_target` 和 `extended_reference`；
- 强：存在人工 opening 区域候选；
- 弱：存在由 proposal 推导的 ambiguity mask，但缺少人工确认。

可选项：

- 二元交叉熵；
- 用于稀疏正样本的 focal loss；
- 用于稀疏 opening 区域的 soft Dice loss；
- 对弱 mask 给予更低样本权重。

### 5.3 `L_over`

目的：

- 训练一个任务级标量，用来预测跨门扩张风险。

可用样本：

- `overextend_risk_label in {0,1}`。

可选项：

- 二元交叉熵；
- 当正样本稀少时使用 class-balanced BCE；
- 对弱标签降低权重。

### 5.4 标签可用性矩阵

| 样本类型                                               | `L_layout_enc` |                        `L_amb` |                   `L_over` | 备注                            |
| ------------------------------------------------------ | -------------: | -----------------------------: | -------------------------: | ------------------------------- |
| 人工裁决的 enclosed-only                               |            yes |              no，除非已有 mask | 若复核过，可作为可选负样本 | 干净的 enclosed 监督            |
| enclosed + extended 配对标签                           |            yes |                            yes |                        yes | 最强的辅助监督                  |
| 只有原始 extended                                      |             no | 只有在 proposal 被复核时才弱用 |                  弱 / 可选 | 不是干净的 enclosed 监督        |
| 经过审计 proposal 的 Bi-Layout 风格 relabeled enclosed |            yes |     若保留 extended 参考则 yes |         若已裁决风险则 yes | 对 opening ambiguity 有用       |
| 只有 proposal、无人批准的候选                          |      no 或弱用 |                         仅弱用 |                     仅弱用 | 不应驱动主目标                  |
| A 线 P1/C1/C2/T1/V1 的正式数据                         |             no |                             no |                         no | 不得用 A 线结果训练或调 Paper B |

## 6. Paper B 的评估指标

### 6.1 布局精度

主要布局指标：

- enclosed 2D IoU；
- enclosed 3D IoU。

这些指标只评估 enclosed layout 的准确性。

### 6.2 Overextend 与 relabel side effect

主要错误与副作用指标：

- `overextend_adjacent` 错误率。
- `undercoverage_rate`；
- `new_error_rate`；
- `both_wrong_rate`；
- `opening_region_boundary_error`。

建议拆分：

- 所有评估样本；
- 有 opening-region 候选的样本；
- relabeled enclosed/extended 存在分歧的样本；
- 高风险提示子集。

这些指标应优先在 B0 / B0-Z 的人工审计标签或专家 GT 对照上报告。若没有专家 GT，只能称为描述性审计比例，不能称为 accuracy。

### 6.3 模糊性与候选挖掘

候选挖掘指标：

- opening ambiguity 候选精确率；
- ambiguity heatmap precision / recall / F1；
- overextend-risk AUROC / AUPRC；
- relabel 候选挖掘精确率；
- cue false positive burden；
- cue false negative cases。

建议定义：

- `opening ambiguity candidate precision`：cue 为正的 opening 候选中，被人工审计确认是真实模糊性 / 边界策略风险的比例；
- `ambiguity heatmap precision / recall / F1`：在 audited ambiguity mask 或 opening-region label 上评估 `A_amb(x)`；
- `overextend-risk AUROC / AUPRC`：在 audited overextend-risk labels 上评估 `r_over`；
- `relabel candidate mining precision`：被挖掘的候选中，最终得到确认 relabel 或确认 overextend 风险案例的比例；
- `cue false positive burden`：cue 为正、但审计后其实是容易的典型 enclosed 案例的比例；
- `cue false negative cases`：确认存在 overextend 或 ambiguity、但 cue 没有标出来的案例。

### 6.4 不作为 Paper B 主指标的指标

Paper B 不能把 OOS 准确率作为主指标。

原因：

- Paper B 的 cue 不是 OOS 分类器；
- OOS 有效性是另一条 A 线 scope-gate 问题；
- overextend 风险和 opening ambiguity，比 OOS 更窄。

若在人工复核中出现 OOS 相关观察，也只能作为描述性审计备注报告。

## 7. Label Studio 谨慎提示集成

Paper B 只可以将信息作为决策支持喂给 Label Studio，不能预填、锁定或推荐最终的 `scope`、`difficulty` 或 `model_issue`。

### 7.1 任务元数据字段

建议的任务级字段：

- `cue_level`: `none`、`low`、`medium` 或 `high`；
- `cue_reason`: 原因码列表；
- `warning_text_version`: warning 文本 / UI 文案版本；
- `ambiguity_heatmap_ref`: 指向 heatmap 载荷或预览资产的可选引用；
- `overextend_risk_score`: 用于审计的数值标量，可选对标注者隐藏；
- `cue_model_version`: 模型 checkpoint 或推理版本；
- `cue_generated_at`: 时间戳。

建议的运行时字段：

- `cue_shown`: 布尔；
- `cue_acknowledged`: 布尔；
- `cue_acknowledged_at`: 可空时间戳；
- `cue_interaction_count`: 可选整数；
- `cue_dismissed`: 可选布尔。

### 7.2 UI 行为

允许：

- 展示一个非阻塞的谨慎提示卡；
- 展示诸如 `possible_cross_door_extension` 的原因标签；
- 若可用，展示 ambiguity overlay 或 heatmap；
- 提醒标注者仔细检查 doorway / opening；
- 记录提示是否被展示，以及是否被确认。

禁止：

- 自动填写 `scope`；
- 自动填写 `model_issue`；
- 自动填写 `difficulty`；
- 强制 OOS 选择；
- 在无人复核的情况下隐藏任务；
- 把 `cue_level=high` 当作 OOS 分类器；
- 将 cue 值当成正式的 CE-only 任务分布真值。

建议的警示文案：

```text
该样本可能存在开口边界或跨门扩张风险。请按 enclosed-only 标注规则独立判断：只标注相机所在房间，不自动采纳模型提示。
```

具体文案应通过 `warning_text_version` 进行版本化。

## 8. 禁止用途

Paper B 不能：

- 把 cue 当成自动 OOS 标签；
- 将 cue 回流到 A 线路由；
- 使用 A 线 P1/C1/C2/T1/V1 的结果来训练或调参；
- 使用 A 线 Main/Test/Validation 结果重置 Paper B 阈值；
- 将 Paper B 结果写入当前 A 线 thesis 主结论链；
- 修改 A 线协议 / SOP / 论文主文 / P1 imports / tools / tests / analysis_results；
- 将 Bi-Layout cue 合并进正式 A 线 `g_t`；
- 生成 V1 路由工件；
- 声称替代 OOS gate；
- 假定 Bi-Layout relabel 自动正确；
- 自动用 Bi-Layout relabel 替换 GT；
- 将 B 线谨慎提示加到 A 线正式的 Semi-Auto 条件中；
- 隐藏 under-coverage 或过度保守截断案例。

## 9. 本规划文档的验收标准

只有当未来读者能一眼看出以下几点时，这份文档才算完整：

- Paper B 是一份独立研究计划，而不是 A 线协议扩展；
- A 线主协议不变；
- 最终 Paper B 的布局输出只采用 enclosed-only；
- Bi-Layout 只用于 relabel 审计、监督和清洗思路，而不是运行时嵌套推理；
- 风险提示只是候选挖掘和谨慎提醒信号，不是 OOS 标签；
- 这份计划不会改动任何现有正式 HOHONET 工件。
