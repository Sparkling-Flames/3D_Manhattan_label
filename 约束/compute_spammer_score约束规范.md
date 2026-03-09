# compute_spammer_score.py 约束规范（辅助审计版）

## 0. 定位

本规范约束 `compute_spammer_score.py` 对连续偏离分数 `S_u` 的计算、输出与审计。

当前主线要求已经发生变化：

1. 主画像不再使用连续 `S_u` 作为横轴。
2. 主画像与主路由依赖 `LCB(r_u)` 加离散风险层级 `R0/R1/R2/R3`，以及风险签名 `T_u/C_u/G_u`。
3. `S_u` 只保留为辅助审计量、legacy 兼容字段或 worker card 附加信息。

因此，本脚本的角色是：

- 生成一个可复现的连续偏离摘要，供附录、兼容表、worker card 或 legacy 字段回写使用。
- 不得把 `S_u` 重新抬升为主画像轴或唯一分组规则。

---

## 1. 作用边界

`compute_spammer_score.py` 只负责：

- 从有效的 leave-one-out 一致性记录中计算辅助连续偏离量 `S_u`。
- 输出 worker 级结果表与审计 JSON。
- 可选回写 `merged_all.csv` 的 `S_u*` 字段。

禁止：

- 在本脚本中直接生成 `worker_group` 或 `R_u^{tier}`。
- 用 `S_u` 单独定义 Stable / Vulnerable / Noise / Fragile。
- 用 `S_u` 覆盖 `T_u/C_u/G_u` 这三类主风险签名。

---

## 2. 指标定义

### 2.1 辅助连续偏离定义

为兼容已有字段名，保留：

$$
S_u = Q_q\bigl(1 - \mathrm{IoU}_{u,t}^{LOO}\bigr)
$$

其中：

- `IoU_{u,t}^{LOO}` 来自 `iou_to_consensus_loo`
- `Q_q` 为固定分位数函数
- 默认 `q = 0.90`

解释边界：

- `S_u` 越高，表示该 worker 在其较差任务上的几何偏离更严重。
- `S_u` 不是盲信风险 `T_u`。
- `S_u` 不是条件脆弱风险 `C_u`。
- `S_u` 不是可计算失败倾向 `G_u`。

### 2.2 当前项目中的地位

- 允许作为辅助审计量。
- 允许保留在 `merged_all.csv` 中做 legacy 兼容。
- 不得作为论文主图 D 的主横轴。
- 不得单独触发主路由决策。

---

## 3. 输入契约

输入表至少包含：

- `annotator_id`
- `task_id`
- `iou_to_consensus_loo`

推荐字段：

- `reliability_used` 或等价可用性标志
- `reliability_gate_reason`
- `dataset_group`
- `scope`
- `type4_flag`

默认只使用可进入可靠度分析的记录。以下行必须排除：

- `iou_to_consensus_loo` 为空
- `type4_flag=True`
- 被标记为 `excluded_from_consensus`
- 非主分析口径的无效/损坏记录

推荐默认来源：

- `Calibration_manual` 主表或等价的主可靠度输入表

---

## 4. 计算规则

### 4.1 worker 级聚合

对每个 `annotator_id`：

1. 收集全部有效 `iou_to_consensus_loo`
2. 转为 `deviation = 1 - iou_to_consensus_loo`
3. 取固定分位数 `q=0.90`
4. 输出 `S_u`

### 4.2 样本量门槛

- 默认 `min_tasks_required = 5`
- 若某 worker 有效任务数不足：
  - `S_u=NA`
  - `S_u_status=insufficient_tasks`
  - 仍需写入审计

### 4.3 稳定性要求

- 相同输入重复运行，`S_u` 到小数点后 6 位一致。
- 分位数实现必须固定插值策略。

---

## 5. 输出字段契约

至少输出：

- `annotator_id`
- `S_u`
- `S_u_status`
- `S_u_quantile`
- `S_u_n_tasks`
- `S_u_compute_ts`
- `S_u_role`

其中：

- `S_u_role` 固定写为 `auxiliary_only`

如需回写到 `merged_all.csv`：

- 同一 `annotator_id` 的 `S_u` 在所有对应行应一致
- 仅回写 `S_u*`
- 不直接写 `worker_group`
- 不直接写 `risk_tier`

---

## 6. 与主画像和主路由的协作边界

### 6.1 主画像主线

主画像应由以下量支撑：

- 纵轴：`LCB(r_u)`
- 横轴：离散风险层级 `R0/R1/R2/R3`
- 签名：`T_u`、`C_u`、`G_u`，辅以 `E_u`、`M_u`

### 6.2 `S_u` 的允许用途

- worker card 补充信息
- 附录审计表
- 历史版本兼容
- 与旧版结果对账

### 6.3 `S_u` 的禁止用途

- 作为论文主图 D 的主横轴
- 作为 worker 分组的唯一触发依据
- 作为高风险任务派单的唯一排序依据

---

## 7. 审计产物

必须产出：

1. `data/worker/spammer_scores.csv`
2. `data/worker/spammer_score_audit.json`
3. 可选 `data/worker/spammer_score_failures.csv`

审计 JSON 至少包含：

```json
{
  "rule_version": "spammer-score-v2-auxiliary",
  "primary_quantile": 0.9,
  "min_tasks_required": 5,
  "role": "auxiliary_only",
  "n_workers_total": 0,
  "n_workers_scored": 0,
  "n_workers_na": 0
}
```

---

## 8. Python 接口

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

## 9. 验收清单

1. `S_u` 主定义固定为 `q=0.90` 分位数偏离。
2. 样本不足 worker 必须输出 `NA + insufficient_tasks`。
3. 回写 `merged_all.csv` 时同 worker 各行 `S_u` 一致。
4. 输出中必须标明 `S_u_role=auxiliary_only`。
5. 本脚本不得直接生成 `worker_group` 或 `R_u^{tier}`。
6. 文档和下游不得把 `S_u` 重新表述为当前主画像横轴。
