# HRC C3.2 Constrained v0 Candidate Source Contract v1

## 1. 定位与边界

`constrained_v0` 的 `source_type` 为 `constrained_v0_candidate_source`，角色是未来的 expert-side、dry-run、no-writeback 候选来源。它不替代 evaluator，不绕过 C0–C6 hard gates，不修改 annotation，也不产生下游推荐授权。

初期实现只能作为 `legacy_m1528` 的并列 shadow source。`legacy_m1528` 仍是唯一 active source；在完成候选集合与 selection 的 A/B audit 前，不得替换 legacy source。shadow 输出必须保持 `accepted=false`、`downstream_recommendation=false`。

本文只冻结合同与候选家族设计，不授权实现或接入 runner。

## 2. Source interface

未来 source 必须通过 `manhattan_candidate_source_interface.py` 校验，并输出：

- `source_id`
- `source_type = constrained_v0_candidate_source`
- `source_version`
- `generator_role = shadow_constrained_generator`
- `candidate_generation_allowed`
- `candidate_count`
- `candidate_set`
- `case_contract`
- `source_provenance`
- `source_limitations`
- `output_schema_version`

`candidate_generation_allowed` 只描述该 source 是否获准按本合同生成已登记家族，不代表 apply、writeback 或 accepted recommendation 权限。

候选的 `coordinate_changes` 统一为列表；每项至少包含 `effective_pair_index`、`fields`，每个字段记录 `before`、`after`、`delta`。字段仅允许 `top_x`、`top_y`、`bottom_x`、`bottom_y` 的显式子集；不得隐式改 order、pair identity 或 topology。

## 3. 最小候选家族设计

### 3.1 `height_target_reproject`

- 输入字段：ordered pairs、projection config、dominant height target、目标 pair。
- case contract：movable pair/field、protected pair、keep-distinct、order-preservation 约束。
- evaluator/evidence：height consistency、max height residual、height outlier、projection validity；C4 evidence 仅作核验。
- eligibility gate：目标 pair 为明确 height outlier，且允许修改对应 `top_y` 或 `bottom_y`。
- hard reject：projection failure、pair fold/order mutation、protected pair 修改、keep-distinct collapse、self-intersection。
- coordinate changes：单 pair 的显式 y 字段 before/after/delta；不改 x。
- provenance：family、target pair/field、height target 来源、baseline artifact hash、contract version。
- known failure modes：错误 dominant cluster、局部 ceiling/floor 不连续、全景 seam 附近重投影失真。
- 不适用：height target unavailable、多层高度结构、目标字段受保护或 C4 evidence conflict。

### 3.2 `column_x_alignment`

- 输入字段：ordered pairs、目标 column/pair、当前 top/bottom x、projection config。
- case contract：movable x fields、protected pairs、keep-distinct、column identity。
- evaluator/evidence：floor-ceiling column consistency、local orthogonality、C4 corner-column evidence。
- eligibility gate：同一 column 的 x 不一致且 column identity/evidence 可用。
- hard reject：跨 column 合并、protected pair 修改、order mutation、keep-distinct collapse、projection failure。
- coordinate changes：同一 pair 的 `top_x`/`bottom_x` 显式 before/after/delta。
- provenance：family、column identity、alignment reference、evidence source/hash、contract version。
- known failure modes：错误 column correspondence、seam wrap 歧义、视觉上非垂直的真实边界。
- 不适用：column evidence unavailable/conflict、斜墙语义、目标 column 跨 seam 且无法消歧。

### 3.3 `short_wall_preserving_local`

- 输入字段：ordered pairs、短墙端点、邻接墙、baseline short-wall length 与 local window。
- case contract：protected/keep-distinct pairs、movable fields、minimum separation、order-preservation。
- evaluator/evidence：short-wall preserved/collapsed/newly-created、dense-corner、local orthogonality、C4 local boundary/corner evidence。
- eligibility gate：已有短墙被明确登记为需保留，且局部允许字段非空。
- hard reject：短墙 collapse、产生新短墙、dense-corner 压塌、protected pair 修改、topology/order change。
- coordinate changes：局部相邻 pair 的最小 x/y 字段集合，逐字段记录 before/after/delta。
- provenance：family、protected edge、baseline length、local window、evidence/hash、contract version。
- known failure modes：数值长度保留但 protruding pillar 视觉恶化、错误邻接关系、局部修正向外传播。
- 不适用：需要 topology hypothesis、短墙语义未确认、局部 evidence unavailable/conflict。

### 3.4 `primary_edge_direction_family_repair`

- 输入字段：primary edge 两端 pair、wall headings、direction-family assignment、projection config。
- case contract：primary edge、movable endpoint fields、protected pairs、order/keep-distinct 约束。
- evaluator/evidence：direction-family、parallel-family、turn residual、unresolved edges、local orthogonality、C4 boundary/corner evidence。
- eligibility gate：direction assignment available，primary edge unresolved，且 L1 多指标共同支持局部修正。
- hard reject：仅凭 direction residual 单项触发、unresolved/turn/local orthogonality 回归、C4 conflict、任一 L0 failure。
- coordinate changes：primary edge 端点所属 pair 的最小显式 x/y before/after/delta。
- provenance：family、primary edge、assigned family、baseline residual summary、evidence/hash、contract version。
- known failure modes：小幅方向改善掩盖局部 protrusion、错误 family assignment、短墙或高度回归。
- 不适用：heading unavailable、primary edge 不明确、需要全局优化或 topology change。

### 3.5 `floor_depth_balance`

- 输入字段：primary edge/局部 pair、floor projection、dominant height、局部 floor-depth diagnostics。
- case contract：movable bottom fields、protected pairs、short-wall/keep-distinct、order-preservation。
- evaluator/evidence：floor polygon proxy residual、height consistency、turn/local orthogonality、C4 floor-boundary/corner evidence。
- eligibility gate：局部 floor-depth imbalance 可定位，且 L1/L2 不冲突。
- hard reject：self-intersection、pair fold、height/short-wall 明显回归、C4 conflict、protected field 修改。
- coordinate changes：受限 pair 的 `bottom_x`/`bottom_y` 及必要配对字段 before/after/delta；不得隐式平移整图。
- provenance：family、target edge/pairs、baseline depth diagnostics、evidence/hash、contract version。
- known failure modes：plane proxy 改善但图像边界变差、错误 floor reference、pair-6 类局部高度回归。
- 不适用：floor evidence unavailable、非单层 floor、需要 wall-plane slide 或 topology adjustment。

## 4. 明确暂缓或禁止

- local topology hypothesis：暂缓。
- MADS / Hooke-Jeeves：暂缓。
- wall-plane slide：暂缓。
- learning / adaptive update / ranker：暂缓。
- full image-edge evidence：暂缓；不得把 C5 plane proxy 冒充 C4/L2 evidence。
- automatic apply、annotation patch、writeback、worker-facing、routing：禁止。
- 未经 A/B selection audit 替换 `legacy_m1528`：禁止。
- constrained_v0 accepted recommendation：禁止。

## 5. 后续实现准入

实现阶段必须先提供只读 shadow artifact、candidate-id/provenance 稳定性测试、C0–C6 evaluator 回归和 legacy/constrained A/B selection audit。通过前 runner active source、portfolio selection 和推荐授权边界均不得改变。
