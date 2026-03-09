# compute_dt_score.py 约束规范（按当前提纲修订版）

## 0. 定位

本规范约束 `compute_dt_score.py` 对标注前分布风险代理 `d_t` 的计算、冻结、失败处理与审计输出。

主目标：

1. 在任何人工质量信号出现前计算 `d_t`。
2. 对同一 `task_id` 在相同模型版本与参考池下输出完全一致的结果。
3. 失败时只允许 `NA + reason`，禁止静默补值。

当前主线要求：

1. `d_t` 的主实现必须与论文方法章节一致：冻结 HoHoNet shared pre-head latent，宽度方向全局池化，L2 归一化，基于 calibration-only 参考池计算 kNN-OOD 分数。
2. `d_t` 只用于风险分层、应激触发与审计披露，不用于静默过滤样本，也不直接判定对错。
3. 前 `K` 个近邻平均距离与 Mahalanobis 距离只能作为附录敏感性分析，不得覆盖主结果。

---

## 1. 脚本职责

`compute_dt_score.py` 只负责：

- 读取任务级输入表与冻结参考池 manifest。
- 抽取每个任务的图像级 embedding。
- 计算主实现 `d_t`。
- 可选计算 calibration leave-one-out 分数与阈值 manifest。
- 输出 `d_t*` 字段与审计产物。

禁止：

- 直接修改 `r_u`、`worker_group`、`S_u`。
- 读取人工角点、`iou`、`IAA_t`、`model_issue`、`difficulty` 作为计算输入。
- 用替代 embedding 后端覆盖主结果。

---

## 2. 输入契约

### 2.1 必需输入

- 任务级输入表，至少包含：
  - `task_id`
  - `image_path`
- `reference_pool_manifest.json`
- 冻结模型信息：
  - `model_version`
  - checkpoint 路径
  - hook 层名

### 2.2 推荐输入

- `base_task_id`
- `image_id`
- `dataset_group`
- `source_pool`

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
r_u_lcb
worker_group
worker_group_reason
difficulty
model_issue
scope
annotator_id
```

一旦发现读取链路中使用这些字段，必须触发：

- `leakage_check_failed=true`
- 主结果中止
- 审计报告写明违规字段名

---

## 3. 参考池冻结与 manifest 契约

### 3.1 主实现参考池规则

1. 仅允许来源 `Calibration_manual`。
2. 先按 `base_task_id` 去重；若无该字段，则退化为 `task_id`。
3. 再按 `task_id` 字典序排序。
4. 主实现默认取前 100 个参考任务；若未来冻结值改变，必须由 manifest 明示，不能在代码里静默改动。
5. 禁止基于质量、难度、人工标签、文件大小或 worker 表现做筛选。

### 3.2 manifest 最小字段

```json
{
  "meta": {
    "strategy": "lexicographical_top_n",
    "source": "Calibration_manual",
    "frozen_at": "2026-03-01T00:00:00Z",
    "ref_hash": "sha256:...",
    "model_version": "hohonet_v2",
    "embedding_backend": "hohonet.shared_pre_head_gapw_l2",
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

### 3.3 manifest 审计规则

- `refs[*].base_task_id` 不得重复。
- `pool_size` 必须与 `refs` 数量一致。
- manifest 中不得出现 `quality`、`difficulty`、`worker`、`manual_label` 字段。
- `ref_hash` 不匹配时，必须中止批处理。

---

## 4. embedding 抽取约束

### 4.1 主实现

- 模型：冻结 HoHoNet。
- 特征：共享 pre-head 1D latent。
- 图像级向量：沿宽度方向做全局平均池化。
- 归一化：L2 normalize。
- 推理：`torch.no_grad()`。
- 不允许：训练态更新、BN 统计更新、随机增强、测试时调参。

### 4.2 附录替代实现边界

允许在附录中报告：

- `K in {5, 20}`
- `q in {85, 95}`
- 前 `K` 个近邻平均距离
- Mahalanobis 距离

但必须满足：

1. 独立输出到 `d_t_alt_*` 字段或独立文件。
2. 独立 manifest hash。
3. 审计中标明 `appendix_only=true`。
4. 不得覆盖主字段 `d_t*`。

---

## 5. 主定义与阈值

### 5.1 主分数定义

当前提纲锁定的主实现为第 `K` 个近邻欧氏距离：

$$
d_t = D_K(\tilde z_t, \mathcal{B}_{cal}) = \|\tilde z_t - \tilde z_{(K)}\|_2
$$

其中：

- `K = 10`
- `metric = euclidean`
- `algorithm = brute`

### 5.2 calibration leave-one-out 与触发器

若脚本同时负责阈值 sidecar，则必须：

1. 对 calibration 参考池内部使用 leave-one-out 计算 `d_i^{cal,LOO}`。
2. 固定 `q = 0.90`。
3. 计算：

$$
\tau_d = Q_{0.90}(\{d_i^{cal,LOO}\}), \quad I_t^{OOD} = \mathbf{1}[d_t > \tau_d]
$$

4. 阈值与触发器必须写入独立阈值 manifest，不得隐式藏在 notebook 里。

### 5.3 禁止行为

- 将“前 K 近邻平均距离”写成主实现。
- 将 `d_t` 解释为 correctness score。
- 用 `d_t` 直接做硬过滤而不披露。

---

## 6. 失败熔断

### 6.1 失败码

| 状态码 | 含义 | 处理 |
|---|---|---|
| `success` | 成功 | 正常写入 `d_t` |
| `extract_fail` | embedding 提取失败 | `d_t=NA` |
| `ref_hash_mismatch` | 参考池 hash 不一致 | 整批中止 |
| `embed_dim_error` | 向量维度错误 | `d_t=NA` |
| `knn_runtime_error` | 距离计算异常 | `d_t=NA` |
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

可选 sidecar：

- `tau_d`
- `tau_d_quantile`
- `I_t_OOD`
- `threshold_manifest_hash`

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
  --input data/tasks/task_level_table.csv \
  --manifest data/reference_pool_manifest.json \
  --output data/cleaned/task_level_with_dt.csv
```

---

## 9. 审计产物

必须产出：

1. `dt_audit_report.json`
2. `dt_failures.csv`
3. 可选 `reference_pool_snapshot.csv`
4. 可选 `dt_threshold_manifest.json`

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
3. 主实现使用第 `K=10` 个近邻距离，而不是前 K 平均距离。
4. 所有失败样本均为 `NA + reason`。
5. 检测到黑名单字段时整批中止。
6. 替代 embedding 或平均 KNN 结果不覆盖主字段。
