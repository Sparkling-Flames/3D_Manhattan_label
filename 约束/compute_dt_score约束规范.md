# compute_dt_score.py 约束规范（详细执行稿）

## 0. 目标与边界
本规范约束 `compute_dt_score.py` 的输入、防泄漏、参考池冻结、embedding 抽取、kNN 计算、失败熔断、输出字段与审计产物。

主目标：
1. 在任何人工质量信号出现前计算 `d_t`。
2. 对同一 `task_id` 在相同模型版本与参考池下输出完全一致的结果。
3. 失败时只允许 `NA + reason`，禁止静默补值。

---

## 1. 脚本职责
`compute_dt_score.py` 只负责：
- 读取任务输入与冻结参考池；
- 抽取每个任务的 embedding；
- 计算 kNN 距离形式的 `d_t`；
- 输出带 `d_t*` 字段的数据文件与审计 JSON。

禁止：
- 直接修改 `r_u`、`worker_group`、`S_u`；
- 读取人工角点、`iou`、`IAA_t`、`model_issue`、`difficulty` 作为计算输入；
- 用替代 embedding 后端覆盖主结果。

---

## 2. 输入契约

### 2.1 必需输入
- `merged_all.csv` 或等价任务表，至少包含：
  - `task_id`
  - `image_path`
- `reference_pool_manifest.json`
- 冻结模型信息：`model_version`、checkpoint 路径、hook 层名

### 2.2 可选输入
- `base_task_id`
- `image_id`
- `camera_height`
- CLI `--k`
- CLI `--metric`
- CLI `--pool-size`（仅附录模式）

### 2.3 输入黑名单
以下字段不得参与任何主计算路径：
```text
layout_corners
manual_labels
annotated_polygons
num_walls
iou
iou_edit
IAA_t
r_u
worker_group
model_issue
difficulty
```
一旦发现读取链路中使用这些字段，必须触发：
- `leakage_check_failed=true`
- 主结果中止
- 审计报告写明违规字段名

---

## 3. 参考池冻结与 Manifest 契约

### 3.1 参考池规则
1. 仅允许来源 `Calibration_manual`。
2. 先按 `base_task_id` 去重；若无该字段，则退化为 `task_id`。
3. 再按 `task_id` 字典序取前 100。
4. 禁止基于质量、难度、标注结果做筛选。

### 3.2 Manifest 最小字段
```json
{
  "meta": {
    "strategy": "lexicographical_top_100",
    "source": "Calibration_manual",
    "frozen_at": "2026-03-01T00:00:00Z",
    "ref_hash": "sha256:...",
    "model_version": "hohonet_v2",
    "embedding_backend": "hohonet.penultimate",
    "pool_size": 100,
    "dedup_key": "base_task_id"
  },
  "refs": [
    {
      "task_id": "calib_0001",
      "base_task_id": "scene_0001",
      "image_path": "...",
      "source_split": "Calibration_manual",
      "inclusion_rank": 1,
      "embedding_hash": "sha256:..."
    }
  ]
}
```

### 3.3 Manifest 审计规则
- `refs[*].base_task_id` 不得重复。
- `pool_size` 必须与 `refs` 数量一致。
- Manifest 中不得出现 `quality`, `difficulty`, `worker`, `manual_label` 字段。
- `ref_hash` 不匹配时，必须中止批处理。

---

## 4. embedding 抽取约束

### 4.1 主实现
- 模型：HOHONet 冻结版本。
- 层：倒数第二层 embedding，对应配置中的固定 hook。
- 维度：1024。
- 推理：`torch.no_grad()`。
- 不允许训练态更新、BN 统计更新、混入随机增强。

### 4.2 附录对照边界
允许附录中使用替代 embedding 后端，但必须：
1. 独立输出 `d_t_alt_*` 字段或独立文件；
2. 独立 manifest hash；
3. 审计中标明 `appendix_only=true`；
4. 不得覆盖主结果字段 `d_t*`。

---

## 5. 距离计算规范

### 5.1 主公式
$$
 d_t = \frac{1}{K}\sum_{i=1}^{K}\|e_t - e_{ref_i}\|_2
$$

### 5.2 主参数
```python
PRIMARY_CONFIG = {
    "k": 10,
    "metric": "euclidean",
    "algorithm": "brute",
    "pool_size": 100,
    "round_digits": 6,
}
```

### 5.3 附录敏感性
仅允许：
- `k in {5, 20}`
- `metric in {euclidean, cosine}`
- `pool_size in {50, 150}`

不得将敏感性结果回填主结果列。

---

## 6. 失败熔断

### 6.1 失败码
| 状态码 | 含义 | 处理 |
|---|---|---|
| `success` | 成功 | 正常写入 `d_t` |
| `extract_fail` | embedding 提取失败 | `d_t=NA` |
| `ref_hash_mismatch` | 参考池 hash 不一致 | 整批中止 |
| `embed_dim_error` | 向量维度错误 | `d_t=NA` |
| `knn_runtime_error` | kNN 计算异常 | `d_t=NA` |
| `leakage_check_failed` | 检测到违规字段 | 整批中止 |

### 6.2 禁止行为
- 失败填 0
- 均值/中位数插补
- 静默跳过失败样本

---

## 7. 输出字段契约
写回数据表至少包含：
- `d_t`
- `d_t_status`
- `d_t_k`
- `d_t_ref_hash`
- `d_t_model_ver`
- `d_t_metric`
- `d_t_pool_size`
- `d_t_failure_reason`
- `d_t_compute_ts`

规则：
- 成功样本 `d_t >= 0`
- 失败样本 `d_t=NA`
- `d_t_status != success` 时，`d_t_failure_reason` 必填

---

## 8. Python 接口
```python
from pathlib import Path
import pandas as pd

class DtScoreComputer:
    def __init__(self, manifest_path: Path, model_version: str, config: dict): ...
    def validate_inputs(self, df: pd.DataFrame) -> dict: ...
    def build_reference_pool(self) -> dict: ...
    def extract_embedding(self, image_path: str) -> list[float]: ...
    def compute_one(self, row: pd.Series) -> dict: ...
    def run(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def build_audit_report(self) -> dict: ...
```

CLI：
```bash
python compute_dt_score.py \
  --input data/cleaned/merged_all.csv \
  --manifest data/reference_pool_manifest.json \
  --output data/cleaned/merged_all_with_dt.csv
```

---

## 9. 审计产物
必须产出：
1. `dt_audit_report.json`
2. `dt_failures.csv`
3. 可选 `reference_pool_snapshot.csv`

审计 JSON 至少包含：
- `rule_version`
- `run_at`
- `primary_config`
- `reference_pool.hash`
- `reference_pool.unique_base_task_ids`
- `runtime_summary`
- `failure_breakdown`
- `appendix_runs`

---

## 10. 验收清单
1. 相同输入重复运行，`d_t` 到小数点后 6 位一致。
2. 参考池按 `base_task_id` 去重。
3. 所有失败样本均为 `NA + reason`。
4. 检测到黑名单字段时整批中止。
5. 替代 embedding 结果不覆盖主字段。
