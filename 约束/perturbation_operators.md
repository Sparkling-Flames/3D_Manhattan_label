# C1: 扰动算子约束规范（2026重构版，详细执行稿）

## 0. 适用范围与目标

本规范用于 Dev A / Dev B 实现 PreScreen_semi 的误导性初始化生成、冻结与审计。

核心目标：

1. 与论文正文、附录 A1、Label Studio XML 中的 model_issue 口径严格对齐。
2. 用可复现、可审计的方式生成 semi trap 初始化，而不是依赖现场手工挑样。
3. 明确哪些 failure family 以 synthetic operators 为主，哪些以 natural exemplar bank 为主，哪些仅保留 intentional-invalid 小配额。
4. 避免像素平面直觉与全景几何语义冲突，锁死表示层与越界规则。

---

## 1. 与论文 / XML / 现有实现的对齐

### 1.1 与论文正文对齐

- PreScreen_manual：只负责 difficulty coverage 与基础能力锚点，不使用本规范生成的误导性初始化。
- PreScreen_semi：用于测量纠错能力与盲信风险；其误导性初始化遵循“双来源但主次分明”：
  - 主来源：规则化 synthetic operators
  - 补充来源：fixed natural-failure exemplar bank
- topology_failure 与 fail 仅允许固定小配额，用于稳健性披露或 intentional-invalid 审计，不作为主成分。

### 1.2 与 XML alias 对齐

本规范中 operator_id / family_id 必须与 XML alias 一致：

| family_id           | XML alias           | 备注                         |
| ------------------- | ------------------- | ---------------------------- |
| acceptable          | acceptable          | 高质量初始化，对照组         |
| overextend_adjacent | overextend_adjacent | 跨门扩张                     |
| underextend         | underextend         | 漏标                         |
| over_parsing        | over_parsing        | 非结构细节误判               |
| corner_drift        | corner_drift        | 局部、近邻、拓扑基本保持     |
| corner_duplicate    | corner_duplicate    | 同一物理角附近多点           |
| topology_failure    | topology_failure    | 非法拓扑 / 闭合崩溃          |
| fail                | fail                | 整体严重误导，几乎需从零重画 |

### 1.3 与现有实现对齐

- tools/analyze_quality.py 与 tools/ls_3d_logic.js 消费的是 Label Studio 百分比坐标映射后的像素坐标。
- 因此项目现实中存在三层表示：
  1. Label Studio 原始百分比域
  2. 冻结清单真源域
  3. 运行时像素域
- 本规范禁止再把“像素 dict”写成唯一 canonical representation。

---

## 2. canonical 表示层与转换规则

### 2.1 三层表示

#### A. LS 原始表示（采集层）

Label Studio 导出中，点坐标以百分比表示：

- x_pct in [0, 100]
- y_pct in [0, 100]

#### B. Frozen canonical 表示（冻结层，真源）

freeze manifest 中必须使用归一化 / 百分比域，而不是运行时像素：

```json
{
  "base_task_id": "scene_001",
  "image_id": "scene_001_view_03",
  "image_width": 2048,
  "image_height": 1024,
  "corners_norm": [{ "x_pct": 12.5, "y_top_pct": 21.1, "y_bottom_pct": 78.3 }]
}
```

#### C. Runtime pixel 表示（消费层）

运行时可映射为像素：

$$
x_{px} = x_{pct} \cdot W / 100, \qquad y_{px} = y_{pct} \cdot H / 100
$$

此层仅用于：

- 3D preview
- 几何可视化
- analyze_quality 等运行时消费

### 2.2 全景越界规则

必须锁死以下规则：

1. x 方向：wrap，而不是 clamp。
2. y 方向：clamp 到 [0, H] 或 [0, 100] 对应范围。

原因：

- panorama 的水平方向是周期角度，不是普通平面边界。
- 在 seam 附近直接 clamp 会制造伪边界与假拓扑。

### 2.3 禁止写法

以下写法视为不合规：

1. “内部唯一表示为像素 dict”。
2. “坐标越界统一 clamp”。
3. 不区分 freeze 层与 runtime 层。

---

## 3. 家族分治策略

### 3.1 三层家族

#### synthetic-first

适合规则化几何扰动的家族：

- acceptable
- underextend
- corner_drift
- corner_duplicate

#### exemplar-first

语义依赖较强，natural exemplar bank 更有说服力：

- overextend_adjacent
- over_parsing

#### intentional-invalid

仅保留小配额，不追求高频复现：

- topology_failure
- fail

### 3.2 配额原则

1. synthetic-first 家族可作为 PreScreen_semi 主来源。
2. exemplar-first 家族优先使用自然失败样本；若不足，再用预先批准的 surrogate synthetic 版本补足。
3. intentional-invalid 家族仅允许小配额，不得成为 semi trap 主成分。

---

## 4. 每个 operator 的统一模板

每个 operator 必须完整描述以下 6 项，不允许只写“做什么”的散文说明：

1. preconditions
2. transform scope
3. parameter schema
4. output guarantees
5. failure codes
6. audit metadata

### 4.1 通用输入接口

```python
apply(
    corners_norm: list[dict],
    image_width: int,
    image_height: int,
    seed: int,
    lambda_level: str,
    config: dict | None = None,
) -> dict
```

### 4.2 通用输出接口

```python
{
  "status": "success" | "invalid" | "reject",
  "family_id": "corner_duplicate",
  "corners_norm": [...],
  "failure_code": null,
  "audit": {
    "seed": 42,
    "lambda_level": "medium",
    "transform_scope": "single_physical_corner",
    "x_rule": "wrap",
    "y_rule": "clamp"
  }
}
```

### 4.3 通用 failure codes

| code                 | 含义                                      |
| -------------------- | ----------------------------------------- |
| invalid_input        | 输入角点结构不合法                        |
| insufficient_corners | 输入角点数不足以执行该变换                |
| config_missing       | exemplar-first operator 缺失预批准 config |
| transform_degenerate | 扰动后退化为不可消费结果                  |
| unsupported_family   | family_id 未注册                          |

---

## 5. family 级规范

### 5.1 acceptable

- preconditions：输入 corners 合法。
- transform scope：全局轻微抖动或无扰动。
- parameter schema：
  - weak：允许极小抖动
  - none：不扰动
- output guarantees：
  - 不改变角点数量
  - 不改变拓扑顺序
- failure codes：仅允许 invalid_input。
- audit metadata：记录 jitter_px 或 jitter_pct 上限。

### 5.2 underextend

- preconditions：至少 4 个 corner 列，且存在可删减局部边界。
- transform scope：局部边界或一段 wall span。
- parameter schema：
  - weak：删减一个局部 span
  - medium：删减两个相邻 span
  - strong：仅在预批准样本上允许
- output guarantees：
  - 保持闭合顺序
  - 不得直接退化为空布局
- failure codes：insufficient_corners, transform_degenerate。
- audit metadata：记录删除的 span 索引与幅度。

### 5.3 corner_drift

- preconditions：必须能识别单个物理 corner boundary 或局部上下边界对。
- transform scope：单个物理 corner 或一对局部边界。
- parameter schema：
  - weak / medium / strong 对应归一化幅度上限
  - 不允许再写死 5px / 15px / 30px 为唯一真值
- output guarantees：
  - 拓扑基本保持
  - 不引入新 corner 列
  - 不把 drift 做成 fail 或 topology_failure
- failure codes：config_missing, transform_degenerate。
- audit metadata：记录受影响的 local corner id、归一化位移、是否触发 wrap/clamp。

### 5.4 corner_duplicate

- preconditions：存在明确物理角点可复制。
- transform scope：单个物理角附近。
- parameter schema：按 weak / medium / strong 控制 duplicate 偏移与是否插入 1 个或 2 个伪点。
- output guarantees：
  - 新增点必须紧邻原物理 corner
  - 不得把 duplicate 扩散成一整段 ghost wall
- failure codes：invalid_input, transform_degenerate。
- audit metadata：记录 duplicate anchor id、新点数与偏移量。

### 5.5 overextend_adjacent

此家族默认 exemplar-first。

- preconditions：
  - 若使用 natural exemplar：样本已进入 exemplar bank 并完成专家复核。
  - 若使用 synthetic surrogate：必须提供预批准的 candidate edge / side config。
- transform scope：单条预批准的 outward extension edge。
- parameter schema：
  - weak / medium 控制 outward extension 幅度
  - strong 仅附录稳健性，不进主 trap
- output guarantees：
  - 只允许在预批准 edge 上外扩
  - 禁止“随机选一条边直接延长”作为主实现
- failure codes：config_missing, transform_degenerate。
- audit metadata：记录 approved_edge_id、outward direction、extension ratio。

### 5.6 over_parsing

此家族默认 exemplar-first。

- preconditions：
  - natural exemplar 优先
  - 若使用 synthetic surrogate，仅能作为弱 surrogate
- transform scope：局部边界中插入额外伪折点
- parameter schema：
  - weak：1 个伪点
  - medium：2 个伪点
  - strong：不建议作为主实现
- output guarantees：
  - 目标是制造额外伪角，不是重写整个包络
  - 若产生整段新假墙，应改判为 fail 或 topology_failure，不再算 over_parsing
- failure codes：config_missing, transform_degenerate。
- audit metadata：记录插点位置、插点数、是否为 exemplar / surrogate。

### 5.7 topology_failure

- preconditions：至少 4 个 corner 列。
- transform scope：配对/闭合结构。
- parameter schema：仅允许 fixed small quota。
- output guarantees：
  - 故意制造非法拓扑
  - 默认不进入主可比 IoU 集合
- failure codes：insufficient_corners。
- audit metadata：记录非法类型，如 self_intersection / closure_break / pair_mismatch。

### 5.8 fail

- preconditions：无。
- transform scope：整体初始化。
- parameter schema：仅允许 fixed small quota。
- output guarantees：
  - 可以输出明显误导的整体包络
  - 若返回空布局，必须视为 intentional-invalid，而不是普通缺失
- failure codes：无额外代码，但必须在 audit 中写明 fail_mode。
- audit metadata：记录 fail_mode、是否空布局、下游消费约束。

---

## 6. exemplar bank 与 freeze manifest

### 6.1 natural exemplar bank 最小字段

```json
{
  "task_id": "task499",
  "base_task_id": "q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d",
  "source_type": "natural_failure",
  "primary_issue_family": "overextend_adjacent",
  "secondary_issue_families": ["corner_duplicate"],
  "expert_review_status": "approved",
  "recommended_role": "main_trap"
}
```

### 6.2 synthetic freeze manifest 最小字段

```json
{
  "task_id": "semi_syn_001",
  "base_task_id": "scene_001",
  "source_type": "synthetic_operator",
  "family_id": "corner_duplicate",
  "operator_id": "corner_duplicate",
  "lambda_level": "medium",
  "seed": 42,
  "config": {
    "approved_edge_id": null,
    "approved_corner_id": 3
  },
  "x_rule": "wrap",
  "y_rule": "clamp",
  "rule_version": "c1-v2026-rebuilt"
}
```

### 6.3 planned / realized quotas

freeze 输出必须支持披露：

- planned_family_quota
- realized_family_quota
- planned_source_quota
- realized_source_quota

---

## 7. 与下游模块的边界

### 7.1 与 userscript / LS / 3D

- C1 只负责生成冻结后的初始化与审计元数据。
- 不负责在 Label Studio 前端解释 fail / topology_failure 的 UI 行为。
- 若 intentional-invalid 进入前端，必须由调用方显式声明消费策略。

### 7.2 与 analyze_quality

- topology_failure / fail 的主用途是审计与稳健性披露。
- 默认不进入主可比 IoU 聚合。
- 若进入附录对照，需单独标记 denominator。

---

## 8. 验收清单

1. 表示层检查：freeze 真源为归一化/百分比域，而不是像素域。
2. 全景几何检查：x wrap / y clamp 已写死并被实现。
3. 家族分治检查：synthetic-first / exemplar-first / intentional-invalid 已分层。
4. operator 模板检查：每个 operator 都含 6 个固定字段块。
5. exemplar 检查：overextend_adjacent / over_parsing 的自然案例或预批准 surrogate 已冻结。
6. 审计检查：每个冻结任务都含 source_type、base_task_id、rule_version、seed、family_id。
7. 配额检查：planned / realized family/source quota 可披露。

---

## 9. 当前结论

本规范不是“算子解释笔记”，而是 Dev A 的详细执行稿。其定位是：

1. 锁死表示层与越界规则。
2. 锁死 family 分治策略。
3. 锁死 freeze manifest 的审计字段。
4. 给后续实现保留最小必要自由度，而不是让实现者临场发明 geometry 规则。
