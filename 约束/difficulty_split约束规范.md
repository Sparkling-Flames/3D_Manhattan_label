# difficulty_split.py 约束规范（按当前提纲修订版）

## 0. 定位

尽管脚本历史名称仍为 `difficulty_split.py`，当前主线下它的职责已经调整为：

1. 基于标注前可得风险代理 `d_t` 与 `g_t` 构造 IID baseline 与 non-IID stress split。
2. 对生成后的 split 做 post-hoc difficulty / model_issue 审计验证。
3. 输出 split manifest、leakage audit 与 realized risk summary。

核心原则：

- 主切分不得由标注后 difficulty 直接驱动。
- difficulty 与 model_issue 只用于解释性审计，不得反向定义主 split。

---

## 1. 脚本职责

`difficulty_split.py` 只负责：

- 将任务级表规整为唯一任务粒度。
- 依据 `d_t`、`I_t_OOD`、`g_t_triggered` 构造 IID / stress split。
- 执行 leakage check。
- 输出 split manifest 与 post-hoc difficulty audit。

禁止：

- 用 difficulty 或 model_issue 共识直接定义主 split。
- 修改原始 difficulty / model_issue 文本。
- 用人工标签对主 split 事后挑样。

---

## 2. 输入契约

输入表至少包含：

- `task_id`
- `image_id` 或 `image_path`
- `d_t`
- `d_t_status`
- 可选 `I_t_OOD`
- `g_t_triggered` 或等价结构风险触发字段
- 可选 `base_task_id`

用于 post-hoc 审计的可选字段：

- `difficulty`
- `model_issue`
- `difficulty_consensus`
- `model_issue_consensus`

主切分默认作用于任务级表，而不是 worker 级长表；若输入为长表，必须先聚合到任务级。

---

## 3. 风险代理与主切分规则

### 3.1 主风险定义

风险代理只允许来自标注前可得字段：

- `I_t_OOD = 1[d_t > tau_d]`，其中 `tau_d` 来自 calibration leave-one-out 预注册阈值
- `g_t_triggered`

定义：

- `proxy_high_risk = (I_t_OOD == 1) OR (g_t_triggered == True)`

### 3.2 主切分模式

#### 模式 A：IIDBaselineSplit

目标：构造风险代理占比接近参考母池的 baseline split。

要求：

- 风险代理占比应与母池接近，允许在预注册容差内波动。
- 抽样必须可复现。

#### 模式 B：StressValidationSplit

目标：在验证集中提高 `proxy_high_risk` 占比，形成 non-IID stress 条件。

要求：

- 目标高风险比例必须由外部配置注入并冻结。
- 不得依据标注后 difficulty / model_issue 回填或修正主 split。

### 3.3 `H` 子集与 `Validation_OOD`

- `Validation_OOD` 仅由 `I_t_OOD=1` 定义。
- `H` 允许由 `I_t_OOD=1` 或 `g_t_triggered=True` 触发。
- 二者必须分别统计，不得混为一组。

---

## 4. difficulty 与 model_issue 的 post-hoc 审计

### 4.1 允许用途

- 报告 split 后的 `S_hard` 占比
- 审计 IID 与 stress 条件下困难标签暴露是否确实提高
- 披露典型 failure family 的 realized distribution

### 4.2 禁止用途

- 反向决定主 split 的纳入/剔除
- 在 split 不理想时用标签事后补样

### 4.3 审计输出建议

至少输出：

- `difficulty_audit_summary.csv`
- `model_issue_audit_summary.csv`
- `split_realized_risk_summary.json`

---

## 5. 可复现抽样接口

```python
class IIDBaselineSplit:
    def split(self, df, config: dict, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]: ...

class StressValidationSplit:
    def split(self, df, config: dict, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]: ...

def build_task_level_table(df: pd.DataFrame) -> pd.DataFrame: ...
```

其中 `config` 至少包含：

- `target_validation_size`
- `target_high_risk_rate`
- `seed`
- `allow_g_only_fallback`

---

## 6. leakage check

### 6.1 强制检查项

1. `image_id` 或从 `image_path` 提取的 basename 不得跨 split 重叠。
2. `task_id` 不得跨 split。
3. 若存在 `base_task_id`，则 `base_task_id` 不得跨 split。
4. 若实现近重复检测，命中项必须披露。

### 6.2 失败处理

任一关键 overlap 命中时：

- `leakage_check_passed=false`
- 输出详细违规报告
- 不得将该 split 用于主分析

接口：

```python
def perform_leakage_check(train_df, test_df, config: dict) -> tuple[bool, dict]: ...
```

---

## 7. 允许的降级路径

### 7.1 主路径

主路径要求同时具备：

- `d_t`
- `tau_d`
- `I_t_OOD`
- `g_t_triggered`

### 7.2 临时降级

若 `d_t` 尚不可用，仅允许生成：

- `g_only_provisional_split`

并且必须：

- 在 manifest 中标明 `mainline_ready=false`
- 明确写入 `split_proxy_mode=g_only_fallback`
- 不得冒充正式主 split

---

## 8. 输出产物

必须产出：

1. `data/splits/iid_baseline_train.csv`
2. `data/splits/iid_baseline_validation.csv`
3. `data/splits/stress_validation_train.csv`
4. `data/splits/stress_validation_validation.csv`
5. `data/splits/split_manifest.json`
6. `data/splits/split_audit.json`

Manifest 至少包含：

```json
{
  "rule_version": "risk-proxy-split-v2",
  "mode": "stress_validation",
  "seed": 42,
  "proxy_mode": "dt_plus_gt",
  "target_high_risk_rate": 0.45,
  "realized_high_risk_rate": 0.0,
  "validation_ood_rate": 0.0,
  "leakage_check_passed": true,
  "mainline_ready": true
}
```

---

## 9. Python 接口

```python
class DifficultySplitRunner:
    def __init__(self, config: dict): ...
    def build_task_level_table(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def split(self, df: pd.DataFrame, mode: str) -> dict: ...
    def write_outputs(self, result: dict, out_dir: str) -> None: ...
```

CLI：

```bash
python difficulty_split.py \
  --input data/cleaned/task_level_with_dt.csv \
  --mode stress_validation \
  --out data/splits/
```

---

## 10. 验收清单

1. 主 split 只由标注前风险代理 `d_t/g_t` 驱动。
2. `difficulty` 与 `model_issue` 仅用于 post-hoc 审计，不得主导切分。
3. 任一 split 中不存在 `task_id` / `base_task_id` / `image_id` 重叠。
4. manifest 必须写入目标与 realized 的高风险比例。
5. `Validation_OOD` 与 `H` 必须分别统计。
6. 若走 `g_only_fallback`，必须显式标记为 provisional，而不是主线正式结果。
