# 不确定性移交包核心逻辑独立审查（Sol）

## 审查范围与结论

本审查只读核对：

- `C:/Users/ASUS/Downloads/uncertainty_handoff_calibration_workpackage_20260906/review_code/audit.py`
- 同包 `review_results/` 数值产物
- `D:/Work/HOHONET/analysis_results/uncertainty_cloud_inputs_20260906_v1/` 实际输入

下载包 `census/input_hashes.csv` 所列 69 个输入文件，在仓库实际输入目录中 **69/69 存在且 SHA-256 一致**。因此以下判断适用于实际输入，不是副本漂移造成。没有按旧 eligibility 过滤，没有修改正式实验、已有代码或数据，也没有复算大型模型或审图。

总体判断：发现 **2 项已证实实现错误/结果审计缺口**、**1 项已证实“只计数而未使用”**，以及 **3 项当前数据下未造成数值差的方法限制**。最需要先修的是初始化连接键和 bootstrap 有效分母。

## 1. 已证实错误：actual initialization 连接键漏掉 condition，C1 Manual 被串成 Semi 缺失初始化

**代码证据：** `audit.py:100` 将 `proposal_fact` 压成 `(base_task_id, stage) -> initialization_source_kind`；`audit.py:105` 又用 `(image_id, stage)` 查询。两处都没有 `block_index` 和 `raw_condition`，而正式 `context_key` 是 `stage|block_index|base_task_id|raw_condition`。

**实际数量证据：**

- `proposal_fact.csv.gz` 共 43 行，当前 `(base_task_id, stage)` 没有重复，且 43/43 的 `base_task_id == image_id`，所以本批没有字典 last-write 覆盖。
- 但实际 annotation 中有 38 个 `image_id × stage` 同时对应两个 context。
- C1 的 25 个 proposal 均为 `missing_required_initialization`；上述连接把相同图、相同 stage 的 **25 个 Manual context（135 条人工响应）也标成 `missing_required_initialization`**。
- P1 当前 proposal 图没有跨 condition 重叠，所以本批未观察到 P1 条件串接；所有 proposal 的 `block_index` 也都是 0，所以本批未观察到 block 串接。这不消除连接键本身的缺陷。

**影响：** `analysis/contexts.csv` 的这 25 个 Manual context 的 initialization 字段错误。当前 `without_synthetic` 只剔除 `trap_synthetic_disjoint_source`，因此这次主要关联表没有因该错误额外删掉这些 Manual context；但任何按 actual initialization 分层、统计缺失初始化或扩展到多 block 的分析都会被污染。

**建议：** 用 `stage + block_index + base_task_id/image_id + raw_condition` 精确连接；Manual 无 proposal 时必须保留 `manual_or_not_recorded`，不能继承同图 Semi 的初始化状态。连接前对键做唯一性验证。

## 2. 已证实审计缺口：bootstrap 丢弃无效 draw，CI 分母不是固定 500 且未落盘

**代码证据：** `audit.py:135-141` 先在 building 层有放回抽样，把抽中的 building 内全部 context 原样带入；每次算 Spearman 后，只有有限值才 `draw.append(q)`（第 140 行），最后直接对 surviving draws 取分位数。输出只写 `interval='500_building_bootstrap...'`，没有请求次数、有效次数、无效原因或缺失比例。

**实际数量证据：** 按相同 RNG、相同循环顺序复现这段小计算：

- 88 个 association 行中，79 行具备有限原始 rho 且 building≥3，本应各请求 500 次。
- 其中只有 56 行保留满 500 个有限 draw；**23 行只保留 324–499 个**。
- 最严重的是 `extended73 / C2-B|manual / bi_floor→d_floor`：仅 **324/500** 个有效 draw；同层 `bi_floor→cluster_count` 为 **339/500**。
- 另有 9 行因原始 rho 不可算或 building<3 而没有 CI；结果表仅表现为空 CI，没有统一的 not-evaluable 原因字段。

**影响：** 这些 CI 是“条件于该次重采样仍可计算”的分布，而不是固定 500 次 bootstrap 的完整不确定性；小 strata 尤其容易因抽到单一取值/退化样本而被条件化。报告文字称“500 building bootstrap”会让读者误以为所有区间都有 500 个有效 draw。

**方法限制（单位）：** 这段实现是 building-only cluster bootstrap，并未在抽中 building 后再重采样其中的 task/context，也不重采样 worker；因此只能解释为条件于当前 building 内任务组合与历史人员。报告已写“条件于这批历史人员”，但没有同样明确“条件于每个 building 的现有任务集合”。

**建议：** 不重抽来替换坏 draw；固定保存全部 500 个状态，至少输出 `bootstrap_requested_n`、`bootstrap_evaluable_n`、各不可评估原因和基于全分母的缺失率。若目标是 building→task 两级不确定性，应显式增加第二级 task 重采样，不能沿用本 CI 名称冒充。

## 3. 已证实未使用：raw-only 历史成员只被计数，没有进入几何或 medoid

**代码证据：**

- `audit.py:116` 仅在 `membership_checks.csv` 统计 `mapping_status=='raw_version_only'`。
- `audit.py:117` 随即跳过所有非 `extended73` 分区。
- `audit.py:119` 对实际处理的簇一律构造 `norm|canonical_annotation_id`；没有读取 `raw_annotation_version_id`。

**实际数量证据：** 唯一 raw-only 成员位于 `historical42|C1|manual|rPc6...`，`source_member_id=C1|66|3192|34|6053`，`raw_annotation_version_id` 同为 6053，关联 canonical 为 `82255f7bb022fd1cd129`（选定版本 6052）。`membership_checks.csv` 正确报 `raw_only=1` 且成员数 23/23；但 `clusters_to_bi.csv` 只处理 extended73，因而该 partition **0 行**，6053 原版本坐标没有参与任何 `dp`、cluster medoid 或 Bi 距离。

**影响：** 不影响本轮明确限定的 extended73 主关联，因为 extended73 的 1,604 名成员全部可连到 `strict_normalized` 且 strict-valid；但报告中“raw-version-only 成员仍保留原版本”只对输入登记/计数成立，不能理解为已在测量中实际使用。historical42 的几何复核仍未完成。

**建议：** 若未来处理 historical42，必须按 `raw_annotation_version_id` 从 `raw_annotation_versions.jsonl` 取 6053 坐标；不得以 related canonical 6052 或其 normalized 几何替代。

## 4. 当前无数值影响的方法限制：raw 人类距离与 strict-normalized 分区在关联表中并置

**代码证据：** `audit.py:74-79` 同时建立 raw selected-canonical 与 `norm|...` 坐标；`audit.py:101-114` 的 context pair、`d_floor/d_band/...` 和 response-to-Bi 全部使用 **raw ID**；`audit.py:117-126` 的簇 medoid则使用 **strict-normalized ID**；`audit.py:130-141` 把 raw context 指标与 strict-normalized extended73 的簇字段合并做关联。

**实际数量证据：** 本输入中 2,501/2,501 条 selected raw 坐标与对应 `strict_normalized.points_json` **逐值完全相同**；raw/normalized 的 floor 可算数同为 1,611，band 可算数同为 1,517，可算状态交叉完全一致；两者可算时 floor 1-IoU 差为 0。extended73 的 1,604 个成员也全部 strict-valid。

但 strict-valid 不等于本脚本的 floor 可算：extended73 共 303 个簇，其中 **112 个簇 `floor_support=0`、110 个簇仅部分成员 floor 可算、81 个簇全员可算**；1,604 个原簇成员中只有 **1,084** 个进入 floor medoid。因此代表是“原簇内 floor 可算子集的显示 medoid”，不是整个 strict-valid 原簇的 medoid。

**影响判断：** 这是来源角色混用，但在当前冻结输入上 **没有造成数值差**，不能列为本次结果错误。风险在于未来 normalization/repair 真正改变坐标时，同一 association 会把 raw 响应差异与 normalized 分区结构并置，却没有显式版本列提醒读者。

**建议：** `contexts.csv`、`pairs.csv.gz` 和 association 输出增加 `human_geometry_variant=raw_selected_canonical`，簇侧增加 `partition_geometry_version=strict_normalized`；若版本不再逐值相同，必须并列 raw/strict 敏感性而非静默混合。

## 5. 端点角色与近地平线：当前守卫未触发，但“同一竖直边”只被弱验证

**代码证据：** `audit.py:20-27` 只按输入相邻点成对，并用两点分处地平线上下判断 ceiling/floor；它不改变坐标，也不按 x 排序。`audit.py:35-37` 仅在 floor 射线垂直分量 `<1e-5` 或 top 水平范数 `<1e-8` 时拒绝。`pair_dx_max` 只记录（第 82 行），不参与有效性 gate。

**实际数量证据（2,501 条人类 raw 布局）：**

- 角色可判 2,061；失败 440：同半球相邻对 368、奇数/不足点 70、坐标非法 2。
- 在角色可判的 2,061 条中，1,548 条至少一组上下端点 x 不完全相同；745 条最大环向 x 差>5 px，229 条>10 px，52 条>20 px，最大 507.62 px。
- 但当前可 lift 布局的 floor 端点距地平线最小仍为 7.06 px；距地平线<10 px 仅 4 条，<5 px 为 0。最大地面半径/相机高代理为 23.08。因此 `<1e-5` 数值奇点守卫在当前数据没有触发，也未见实际发散证据。

**影响判断：** floor polygon 只使用 floor 射线，band 又分别拟合上下边界，所以较大 `pair_dx` 不必然使本轮两个距离错误；但“相邻上下点代表同一物理竖直边”的语义没有由半球条件充分证明。该限制对未来 3D 墙面/顶点连接比对本轮 floor/band 更严重。近地平线阈值只是数值奇点阈值，不是稳定性阈值；当前样本尚可，但不能外推。

## 6. 非星形与分母：实现是明确的域限制，不应解释成布局失败率

**代码证据：** `audit.py:46-61` 要求 ceiling/floor 各自在环向上同向覆盖一周；不满足时报 `non_single_valued_or_nonstar_boundary`。`audit.py:101-108` 各距离只对可算 pair 求均值，确实没有把缺失补零。

**实际数量证据（人类 raw）：**

- floor 可算 1,611/2,501；主要失败为 invalid original-order polygon 404、same-hemisphere 368、odd/insufficient 70、camera outside 46、coordinate invalid 2。
- band 可算 1,517/2,501；其中 non-single-valued/non-star 540、same-hemisphere 368、odd/insufficient 70、zero-azimuth 4、coordinate invalid 2。
- 所有实际可算 band 均满足上边界<下边界，没有观察到 `db` 负厚度或负 union。

**影响判断：** 这是已公开说明的测量域限制，不是代码错误。floor、球面 band、linear、solid 的可算集合不同；不同 rho/CI 的差别同时包含几何定义与分母变化。`contexts.csv` 留有各 context 的 `floor_count/band_count`，但 `associations.csv` 只给最终 contexts/buildings 数，未给原始响应/pair 缺失构成，仍应避免把不可算比例解释为“坏标注比例”。

## 7. 其他核对通过项

- `audit.py:78` 的 `(context_key, worker_id)` 唯一性断言在实际 2,501 条 canonical 行通过，pair 均值没有同一 context 内重复人员投票。
- extended73 的 73 份 partition 均声明 `geometry_version=strict_normalized`；1,604 个成员全部 strict-valid，成员数核对 0 mismatch。
- `dp` 的 floor 1-IoU、`db` 的 band/linear/solid 是不同代理；代码没有把 0.95 complete-link 阈值偷换成距离 0.05。
- 报告已正确声明视觉审查为 0 张、关联是探索性、building bootstrap 条件于历史人员，未把结果升级为正式实验结论。

## 最小修复优先级

1. 先修 actual initialization 的完整 context 键，并重生 `contexts.csv` 及依赖它的 strata/sensitivity 输出。
2. bootstrap 固定保留 500 个 draw 状态并输出有效/无效分母；对 C2-B 等小 strata 不再只报 surviving-draw CI。
3. 若要声称 historical42/raw-only 已测量，新增按 raw version ID 的专门读取路径；否则把报告措辞收紧为“已登记但未进入本轮几何计算”。
4. 其余 raw/strict、端点和非星形问题先作为显式版本/测量域字段，不需要在当前坐标完全相同的前提下重写几何算法。

## Post-hoc 勘误实现

上述前两项已由独立入口 `tools/thesis_main/analysis/uncertainty_handoff_errata.py` 做可复现勘误；它不修改原 `audit.py` 或原结果。输出位于 `errata/`：完整 context 键修正表、逐行初始化变更清单、固定 500 次分母的 association bootstrap 汇总、全量逐 draw gzip 状态表与 `ERRATA_QA.json`。本批 `proposal_fact` 没有 condition 字段，脚本先以 `proposal_id` 对 `proposal_response.raw_condition` 做全覆盖且唯一为 Semi 的验证，才采用 Semi 约定。

实际结果：270 个 context 中修正 25 个 C1 Manual context，共影响 135 条响应；88 个 association 中 79 个请求 bootstrap，固定请求总数 39,500，实际可算 38,704、无效 796，另有 9 个 association 整体 not-evaluable。无效 draw 原样计入请求分母且未重抽；88/88 行旧 CI 均在绝对误差 `1e-12` 内复现。
