# difficulty_split.py 约束规范（详细执行稿）

## 0. 目标与上位约束
本规范约束 `difficulty_split.py` 的难度映射、任务级共识、IID/non-IID 切分、泄漏检查、KL 验证与输出格式。


## 1. 脚本职责
`difficulty_split.py` 只负责：
- 将 `difficulty` 标签映射到 `easy/medium/hard`；
- 在任务级形成共识难度；
- 产出两类切分：
  - 模式 A：DifficultyBasedSplit
  - 模式 B：IIDBreaker
- 验证 train/test 的难度分布差异；
- 输出 split manifest 与 leakage audit。

禁止：
- 修改原始 `difficulty` 文本；
- 读取 `model_issue` 作为难度代理进入主切分；
- 用 `d_t` 替代 `difficulty` 直接定义主切分。

---

## 2. 输入契约
输入表至少包含：
- `task_id`
- `difficulty`
- `dataset_group`
- `condition`
- `image_id` 或 `image_path`
- 可选 `base_task_id`

主切分默认作用于任务级表，而非单行 worker 级重复记录；若输入为 worker 级长表，必须先做任务级聚合。

---

## 3. 难度映射

### 3.1 固定映射
```python
DIFFICULTY_MAPPING = {
    "trivial": "easy",
    "occlusion": "medium",
    "low_texture": "medium",
    "seam": "medium",
    "reflection": "hard",
    "low_quality": "hard",
}
```

### 3.2 多选处理
- 原始格式必须为分号分隔 alias。
- `trivial` 与其他标签互斥；若共存，按审计冲突记录并丢弃 `trivial`。
- 多选时采用 `highest_wins`：`hard > medium > easy`。
- 空值不自动补 `easy`，而应记为 `difficulty_missing`。

---

## 4. 任务级共识口径

### 4.1 共识形成
- 聚合层级：`task_id`
- 最少标注数：2
- 共识方法：多数投票
- 平局处理：固定 `seed` 打破
- 无法形成共识：排除出 split，但必须写入审计

### 4.2 固定函数接口
```python
from collections import Counter

def derive_difficulty_level(difficulty_tags: str) -> str | None: ...
def form_task_level_difficulty_consensus(df_task, seed: int = 42) -> str | None: ...
```

共识审计字段：
- `task_id`
- `n_annotations`
- `difficulty_votes`
- `consensus_level`
- `tie_broken`
- `excluded_reason`

---

## 5. Split 模式

### 5.1 模式 A：DifficultyBasedSplit
目标：训练集为 `easy/medium`，测试集为 `hard`。

固定接口：
```python
class DifficultyBasedSplit:
    def split(self, df, difficulty_col="difficulty_consensus",
              train_levels=("easy", "medium"),
              test_levels=("hard",)) -> tuple[pd.DataFrame, pd.DataFrame]: ...
```

规则：
- 同一任务只能在 train 或 test 出现一次。
- 若 `hard` 样本不足，允许在审计中提示，但不得偷混 `medium` 进入 test 而不披露。

### 5.2 模式 B：IIDBreaker
目标：按预注册比例打破 IID。

固定接口：
```python
class IIDBreaker:
    def split(self, df, train_ratio: dict, test_ratio: dict, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]: ...
```

默认比例由外部 JSON 注入，例如：
```json
{
  "train_ratio": {"easy": 0.55, "medium": 0.35, "hard": 0.10},
  "test_ratio": {"easy": 0.20, "medium": 0.35, "hard": 0.45}
}
```

要求：
- 比例规则 Week 1 锁定；
- 抽样必须是确定性的；
- 若样本池不足以满足比例，必须输出 `split_feasibility_warning`。

---

## 6. Leakage Check

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

## 7. KL 验证与敏感性分析

### 7.1 主函数
```python
def validate_kl_divergence(train_df, test_df, col="difficulty_consensus") -> float: ...
```

### 7.2 规则
- 主分析必须输出 `KL(train || test)`。
- 附录允许对不同阈值/比例做敏感性分析。
- 主 split 规则与附录敏感性结果不得混写。

---

## 8. 输出产物
必须产出：
1. `data/splits/difficulty_split_train.csv`
2. `data/splits/difficulty_split_test.csv`
3. `data/splits/difficulty_split_manifest.json`
4. `data/splits/difficulty_split_audit.json`

Manifest 至少包含：
```json
{
  "rule_version": "difficulty-split-v1",
  "mode": "difficulty_based",
  "seed": 42,
  "difficulty_mapping_hash": "sha256:...",
  "split_counts": {"train": 0, "test": 0},
  "kl_divergence": 0.0,
  "leakage_check_passed": true
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
  --input data/cleaned/merged_all_with_dt.csv \
  --mode difficulty_based \
  --out data/splits/
```

---

## 10. 验收清单
1. 映射表与 XML difficulty alias 完全一致。
2. 任务级共识在相同 seed 下可复现。
3. 任一 split 中不存在 `task_id` / `base_task_id` / `image_id` 重叠。
4. `KL` 与 split counts 必须写入 manifest。
5. 无法共识与样本不足必须进入审计，不得静默丢弃。
