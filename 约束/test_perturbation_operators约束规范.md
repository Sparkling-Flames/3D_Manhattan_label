# test_perturbation_operators.py 约束规范（详细执行稿）

## 0. 目标
本规范约束 `tests/test_perturbation_operators.py` 的最小覆盖范围、fixture 设计、可复现性检查与失败语义。

测试目标不是证明算子“真实”，而是证明其：
- 接口稳定；
- alias 对齐；
- seed 可复现；
- intentional-invalid 语义被正确消费；
- `freeze_plan` 可读回精确复现。


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
至少提供三类 mock：
1. `rect_corners`：标准矩形
2. `local_corner_case`：适合 `corner_drift` / `corner_duplicate`
3. `panorama_wrap_case`：横向接近 0/1 边界的全景样本

角点真源以归一化坐标表示，例如：
```python
rect_corners = [
    {"x": 0.10, "y": 0.20, "id": 0},
    {"x": 0.80, "y": 0.20, "id": 1},
    {"x": 0.80, "y": 0.70, "id": 2},
    {"x": 0.10, "y": 0.70, "id": 3},
]
```

### 2.2 冻结计划 fixture
必须有一个最小 `perturbation_plan_frozen.json` mock，至少含：
- `meta.rule_version`
- `meta.seed_master`
- `perturbations[*].task_id`
- `perturbations[*].operator_id`
- `perturbations[*].source_type`
- 五槽位模板字段

---

## 3. 必测断言

### 3.1 接口稳定
每个算子 `apply()` 返回：
- `perturbed_corners`
- `metadata`

且 `metadata` 必须含：
- `preconditions`
- `transform`
- `postconditions`
- `failure_code`
- `audit_fields`

### 3.2 alias 对齐
- `operator_id` 必须属于 XML `model_issue` alias 集。
- 不允许测试通过未知 alias。

### 3.3 seed 可复现
对每个算子：
- 相同输入 + 相同 seed → 输出完全相同
- 相同输入 + 不同 seed → 对随机算子应允许不同

### 3.4 panorama 几何
- `x` 越界时应测试 `wrap`
- `y` 越界时应测试 `clamp`
- 不允许把 panorama 的 `x` 当普通平面一律 clamp

### 3.5 intentional invalid
对 `topology_failure` 与 `fail`：
- `audit_fields.is_intentionally_invalid is True`
- `audit_fields.iou_status == "na_intentional"`
- 即使角点为空或乱序，也不得导致测试框架崩溃

### 3.6 `freeze_plan` 读回复现
- 用同一 frozen plan 与同一原始角点，`PerturbationEngine.generate_batch()` 重跑结果应一致
- 读写 JSON 后，关键 hash/seed/params 不变

---

## 4. 算子级最小测试集

### 4.1 `AcceptableOperator`
- `weak` 允许极小扰动或 no-op
- `none` 应保持不变

### 4.2 `CornerShiftOperator`
- 只允许局部、近邻扰动
- 不应一次性把多个远距角点漂成全局崩坏

### 4.3 `CornerDuplicateOperator`
- 输出长度 `+1`
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
- 缺失五槽位模板字段

要求：
- 失败时返回 `failure_code` 或抛出受控异常
- 禁止静默 fallback 到其他算子

---

## 6. 测试组织建议
```python
import pytest

class TestOperatorDeterminism: ...
class TestOperatorContracts: ...
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
5. 测试中使用的 alias 与 XML 完全一致。
