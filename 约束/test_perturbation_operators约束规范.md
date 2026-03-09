# test_perturbation_operators.py 约束规范（按当前 C1 对齐版）

## 0. 目标

本规范约束 `tests/test_perturbation_operators.py` 的最小覆盖范围、fixture 设计、可复现性检查与失败语义。

测试目标不是证明算子“真实”，而是证明其：

- 接口稳定
- alias 与 XML / 附录 A1 完全对齐
- seed 可复现
- canonical freeze 表示层不漂移
- panorama 的 `x wrap / y clamp` 被正确实现
- intentional-invalid 语义被正确消费
- `freeze_plan` 可读回精确复现

---

## 1. 测试范围

至少覆盖以下对象：

- `AcceptableOperator`
- `CornerShiftOperator`
- `CornerDuplicateOperator`
- `OverExtendOperator`
- `UnderExtendOperator`
- `OverParsingOperator`
- `TopologyBreakOperator`
- `CatastrophicFailOperator`
- `PerturbationEngine`
- `freeze_plan()`

若代码中的类名不同，测试需通过映射表显式对齐，不得隐式猜测。

---

## 2. fixture 契约

### 2.1 基础角点 fixture

fixture 必须优先使用冻结层 canonical 表示，而不是运行时像素 dict。

建议最少提供三类 mock：

1. `rect_corners_norm`
2. `local_corner_case_norm`
3. `panorama_wrap_case_norm`

推荐格式：

```python
rect_corners_norm = [
    {"x_pct": 10.0, "y_top_pct": 20.0, "y_bottom_pct": 70.0, "id": 0},
    {"x_pct": 80.0, "y_top_pct": 20.0, "y_bottom_pct": 70.0, "id": 1},
]
```

若实现内部仍使用其他结构，测试必须通过 adapter 显式转换，并验证转换不改变语义。

### 2.2 冻结计划 fixture

必须有一个最小 `perturbation_plan_frozen.json` mock，至少含：

- `meta.rule_version`
- `meta.seed_master`
- `meta.script_hash`
- `perturbations[*].task_id`
- `perturbations[*].operator_id`
- `perturbations[*].source_type`
- `perturbations[*].lambda_level`
- `perturbations[*].seed`

对于 exemplar-first 算子，还需包含其预批准上下文字段。

---

## 3. 必测断言

### 3.1 接口稳定

每个算子 `apply()` 返回：

- `status`
- `family_id`
- `corners_norm` 或等价 canonical 输出
- `failure_code`
- `audit`

且 `audit` 至少含：

- `seed`
- `lambda_level`
- `transform_scope`
- `x_rule`
- `y_rule`

### 3.2 alias 对齐

- `operator_id` 必须属于 XML `model_issue` alias 集。
- 不允许测试通过未知 alias。
- alias 集必须同时对齐：
  - `tools/label_studio_view_config.xml`
  - 附录 A1
  - `perturbation_operators.md`

### 3.3 seed 可复现

对每个算子：

- 相同输入 + 相同 seed → 输出完全相同
- 相同输入 + 不同 seed → 对随机算子允许不同

### 3.4 panorama 几何

- `x` 越界时应测试 `wrap`
- `y` 越界时应测试 `clamp`
- 不允许把 panorama 的 `x` 当普通平面一律 clamp

### 3.5 intentional-invalid

对 `topology_failure` 与 `fail`：

- `audit.is_intentionally_invalid is True`
- `audit.iou_status == "na_intentional"`
- 即使角点为空或乱序，也不得导致测试框架崩溃

### 3.6 `freeze_plan` 读回复现

- 用同一 frozen plan 与同一原始角点，`PerturbationEngine.generate_batch()` 重跑结果应一致
- 读写 JSON 后，关键 hash、seed、params 不变

---

## 4. 算子级最小测试集

### 4.1 `AcceptableOperator`

- `weak` 允许极小扰动或 no-op
- `none` 应保持不变

### 4.2 `CornerShiftOperator`

- 只允许局部、近邻扰动
- 不应一次性把多个远距角点漂成全局崩坏

### 4.3 `CornerDuplicateOperator`

- 输出长度 `+1` 或符合冻结规范的最小增加
- 新点应位于原角点局部邻域

### 4.4 `OverExtendOperator`

- 必须依赖预批准边或显式 surrogate context
- 禁止“任意边随机膨胀”型通过测试

### 4.5 `UnderExtendOperator`

- 输出点数可减少，但不得无告警退化到不可消费状态

### 4.6 `OverParsingOperator`

- synthetic 模式只验证“增加伪折点”能力，不验证语义真实性

### 4.7 `TopologyBreakOperator`

- 应显式产出 intentional-invalid 语义

### 4.8 `CatastrophicFailOperator`

- 空列表或严重扭曲输出都可接受，但必须满足消费约束字段

---

## 5. 失败测试

必须包含以下负例：

- 非法 `lambda_level`
- 空角点输入
- 少于最小边数输入
- 缺失 `approved_edge_index` 的 `overextend_adjacent`
- 缺失 exemplar-first 所需 context
- 缺失 frozen plan 必需字段

要求：

- 失败时返回 `failure_code` 或抛出受控异常
- 禁止静默 fallback 到其他算子

---

## 6. 测试组织建议

```python
import pytest

class TestOperatorDeterminism: ...
class TestOperatorContracts: ...
class TestCanonicalRepresentation: ...
class TestPanoramaGeometry: ...
class TestIntentionalInvalid: ...
class TestFreezePlanReplay: ...
```

推荐标记：

- `@pytest.mark.unit`
- `@pytest.mark.contract`
- `@pytest.mark.repro`

---

## 7. 验收清单

1. 所有算子测试通过且 seed 复现成立。
2. `freeze_plan` JSON 读回复现通过。
3. panorama 的 `x wrap / y clamp` 有专门测试。
4. intentional-invalid 算子不被误判为普通几何失败。
5. 测试中使用的 alias 与 XML / 附录 A1 完全一致。
6. 测试覆盖 canonical freeze 表示层，不允许只测运行时像素表示。
