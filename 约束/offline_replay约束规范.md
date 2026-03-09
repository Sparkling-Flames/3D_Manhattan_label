# offline_replay.py 约束规范（详细执行稿）

## 0. 目标
本规范约束 `offline_replay.py` 对真实历史标注的离线回放，用于比较三种派单策略在不同 split 模式下的效果。

脚本目标不是生成新标注，而是：
- 从候选池中按策略选出 `k_used` 个 worker 的真实标注；
- 调用一致性函数生成 `IAA_t_replay` 等离线结果；
- 为 Phase 2 在线路由提供可复现的策略接口原型。

---

## 1. 输入与依赖
必需输入：
- `merged_all.csv`
- `difficulty_split.py` 产出的 split 结果或等价 task 集合
- 已计算好的：
  - `r_u`
  - `r_u_lcb`
  - `S_u`
  - `d_t`（若使用 Stratified/OOD 触发）
- 可调用的一致性函数：`compute_iaa()` 或等价封装

禁止：
- 修改真实标注几何；
- 回放时读取未来轮次信息；
- 按 replay 结果反向改写 `r_u_lcb`、`S_u` 主表。

---

## 2. 核心数据单位
回放的基本单位为 `(task_id, annotator_id)` 真实提交记录。

每次回放实验至少固定：
- `split_mode`
- `strategy`
- `seed`
- `k_used`
- 候选池定义

同一 `(task_id, strategy, split_mode, k_used, seed)` 必须得到完全一致的被选 worker 集。

---

## 3. 三种策略定义

### 3.1 Random
- 在候选池内做固定 seed 随机抽样。
- 作为 baseline。

### 3.2 GlobalReliability
- 按 `r_u_lcb` 降序排序。
- 相同分数时按 `annotator_id` 字典序稳定打破。
- 选择前 `k_used` 个 worker。

### 3.3 Stratified
- 以场景/风险感知为目标。
- 可读取：`r_u_lcb`, `S_u`, `d_t`, `core_scene`。
- 若 `d_t` 或风险触发满足阈值，可将 `k_used` 提升到 3。
- Phase 1 中仅做离线模拟，不做实时状态更新。

要求：
- 三种策略共享统一输入 schema。
- 任一策略都不得使用未来结果字段，如 `IAA_t_replay` 本身。

---

## 4. 候选池约束

### 4.1 基本过滤
候选记录必须满足：
- `scope` 可进入主分析；
- 非 Type 4 过程损坏；
- 对应 task 在当前 split 内；
- `annotator_id` 非空。

### 4.2 可选过滤
可按配置排除：
- `worker_group == Noise`
- `S_u` 超过阈值

但这些过滤必须在 manifest 中显式披露。

---

## 5. 回放接口
```python
import pandas as pd

class ReplayStrategy:
    name: str
    def select(self, candidate_df: pd.DataFrame, k_used: int, seed: int, context: dict) -> pd.DataFrame: ...

class RandomStrategy(ReplayStrategy): ...
class GlobalReliabilityStrategy(ReplayStrategy): ...
class StratifiedStrategy(ReplayStrategy): ...

def run_replay(df: pd.DataFrame, split: dict, strategies: list, k_range=(1, 2, 3), seed: int = 42) -> pd.DataFrame: ...
```

要求：
- `run_replay()` 必须返回长表结果；
- 每行代表一次 `(task_id, strategy, k_used)` 回放结果；
- 所有策略必须可被 JSON 配置注入。

---

## 6. 输出字段
`replay_results.csv` 至少包含：
- `task_id`
- `split_mode`
- `strategy`
- `k_used`
- `selected_workers`
- `n_candidate_workers`
- `IAA_t_replay`
- `replay_success`
- `failure_reason`
- `seed`
- `config_hash`
- `run_ts`

可选补充：
- `d_t_bucket`
- `risk_triggered`
- `core_scene`

规则：
- `selected_workers` 应用稳定顺序拼接，如 `u01;u03;u07`
- 回放失败时 `IAA_t_replay=NA` 且 `failure_reason` 必填

---

## 7. 一致性计算约束
- `IAA_t_replay` 应与主项目 `compute_iaa()` 口径一致。
- 若 `k_used < 2` 无法计算一致性，则必须：
  - `IAA_t_replay=NA`
  - `failure_reason=insufficient_k_for_iaa`
- 不允许为单 worker 伪造一致性分数。

---

## 8. 审计与复现
必须产出：
1. `data/replay/replay_results.csv`
2. `data/replay/replay_manifest.json`
3. `data/replay/replay_failures.csv`

Manifest 至少包含：
```json
{
  "rule_version": "offline-replay-v1",
  "seed": 42,
  "strategies": ["Random", "GlobalReliability", "Stratified"],
  "k_range": [1, 2, 3],
  "split_mode": "difficulty_based",
  "config_hash": "sha256:..."
}
```

附加要求：
- manifest 必须记录候选池过滤条件；
- hash log 必须可用于 Phase 2 在线服务对齐。

---

## 9. CLI 契约
```bash
python offline_replay.py \
  --input data/cleaned/merged_all.csv \
  --split-manifest data/splits/difficulty_split_manifest.json \
  --output-dir data/replay/ \
  --seed 42
```

---

## 10. 验收清单
1. 三种策略在同一 seed 下输出完全可复现。
2. `GlobalReliability` 必须稳定按 `r_u_lcb` 排序。
3. `Stratified` 的 OOD/风险触发必须写入审计，不得隐式发生。
4. 所有失败行均有 `failure_reason`。
5. `replay_results.csv` 必须含 `strategy`, `k_used`, `split_mode`, `IAA_t_replay`。
