# compute_spammer_score.py 约束规范（详细执行稿）

## 0. 目标
本规范约束 `compute_spammer_score.py` 对 worker 异常度 `S_u` 的计算、输出与审计。

`S_u` 用于工人画像横轴与 Noise/Vulnerable 风险识别，但本脚本本身**不负责**最终 `worker_group` 分类。

---

## 1. 指标定义

### 1.1 主定义
`S_u` 表示 worker 相对 leave-one-out 共识的偏离风险。

主实现定义：
$$
S_u = Q_q\bigl(1 - \mathrm{IoU}_{u,t}^{LOO}\bigr)
$$
其中：
- $\mathrm{IoU}_{u,t}^{LOO}$ 来自 `iou_to_consensus_loo`
- $Q_q$ 为分位数函数
- 主分析固定 `q = 0.90`

因此：
- `S_u` 越高，说明该 worker 在其较差任务上的偏离更严重；
- 结果应落在 $[0,1]$。

### 1.2 附录敏感性
仅允许：
- `q in {0.85, 0.95}`
- 可选 winsorization 披露

不得覆盖主字段 `S_u`。

---

## 2. 输入契约
输入表至少包含：
- `annotator_id`
- `task_id`
- `iou_to_consensus_loo`
- `reliability_gate_passed` 或等价可用性标志（若存在）
- 可选 `scope`, `type4_flag`, `dataset_group`, `condition`

默认只使用可进入可靠度分析的记录。以下行必须排除出主计算：
- `iou_to_consensus_loo` 为空
- Type 4 过程损坏
- 被主项目标记为 `excluded_from_consensus`

---

## 3. 计算规则

### 3.1 worker 级聚合
对每个 `annotator_id`：
1. 收集全部有效 `iou_to_consensus_loo`
2. 转为偏离值 `deviation = 1 - iou_to_consensus_loo`
3. 取固定分位数 `q=0.90`
4. 输出 `S_u`

### 3.2 样本量门槛
- 若某 worker 有效任务数 `< min_tasks_required`，主默认 `min_tasks_required = 5`
- 样本不足时：
  - `S_u=NA`
  - `S_u_status=insufficient_tasks`
  - 仍需写入审计

### 3.3 稳定性要求
- 相同输入重复运行，`S_u` 到小数点后 6 位一致。
- 分位数实现必须固定插值策略，例如 `linear`。

---

## 4. 输出字段契约
写回或单独导出至少包含：
- `annotator_id`
- `S_u`
- `S_u_status`
- `S_u_quantile`
- `S_u_n_tasks`
- `S_u_compute_ts`

如需回写到 `merged_all.csv`：
- 同一 `annotator_id` 的 `S_u` 在所有对应行应一致；
- 本脚本只回写 `S_u*`，不直接写 `worker_group`。

---

## 5. 审计产物
必须产出：
1. `data/worker/spammer_scores.csv`
2. `data/worker/spammer_score_audit.json`
3. 可选 `data/worker/spammer_score_failures.csv`

审计 JSON 至少包含：
```json
{
  "rule_version": "spammer-score-v1",
  "primary_quantile": 0.9,
  "min_tasks_required": 5,
  "n_workers_total": 0,
  "n_workers_scored": 0,
  "n_workers_na": 0
}
```

---

## 6. Python 接口
```python
import pandas as pd

class SpammerScoreComputer:
    def __init__(self, quantile: float = 0.90, min_tasks_required: int = 5): ...
    def filter_rows(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def compute_worker_scores(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def merge_back(self, df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame: ...
    def build_audit_report(self, scores_df: pd.DataFrame) -> dict: ...
```

CLI：
```bash
python compute_spammer_score.py \
  --input data/cleaned/merged_all.csv \
  --output data/worker/spammer_scores.csv
```

---

## 7. 与 `worker_group` 的协作边界
- `compute_spammer_score.py` 只提供 `S_u`。
- `worker_group` 的最终分类应由上游或单独分类逻辑结合 `r_u_lcb`、`S_u`、`Δ_u`、风险桶失效共同决定。
- 禁止在本脚本中偷写 Stable/Vulnerable/Noise。

---

## 8. 验收清单
1. `S_u` 主定义固定为 `q=0.90` 分位数偏离。
2. 样本不足 worker 必须输出 `NA + insufficient_tasks`。
3. 回写 `merged_all.csv` 时同 worker 各行 `S_u` 一致。
4. 主结果不得被附录敏感性覆盖。
5. `S_u` 始终限制在 `[0,1]` 或 `NA`。
