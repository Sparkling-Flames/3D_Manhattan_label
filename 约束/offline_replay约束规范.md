# offline_replay.py 约束规范（按当前提纲修订版）

## 0. 目标

本规范约束 `offline_replay.py` 对真实历史标注的离线回放，用于比较当前 RQ3 主线下的三类策略在不同 split 条件中的表现。

脚本目标不是生成新标注，而是：

- 从候选池中按策略选出 `k_used` 个 worker 的真实提交记录。
- 复用主项目一致性口径计算 `IAA_t_replay` 等离线结果。
- 为 Phase 2 在线路由服务提供可复现的 shadow evaluation 原型。

---

## 1. 当前主线下的策略集合

当前提纲建议的主比较对象为：

1. `Random`
2. `Global`
3. `Full`

说明：

- `Global` 指只用全局 `LCB(r_u)` 的保守排序。
- `Full` 指结合标注前风险代理、离散风险层级、场景特异可靠度与退化规则的完整策略。
- 旧版 `GlobalReliability / Stratified` 命名可保留在兼容层，但主报告与 manifest 建议使用 `Random / Global / Full`。

---

## 2. 输入与依赖

必需输入：

- `merged_all.csv` 或等价长表
- 风险代理 split manifest 或等价任务集合
- 已计算好的：
  - `r_u`
  - `r_u_lcb`
  - `worker_risk_tier` 或等价 `R_u^{tier}`
  - `worker_group_reason`
  - 可选 `r_u_s_lcb`
  - `d_t`
  - `I_t_OOD`
  - `g_t_triggered`
- 可调用的一致性函数：`compute_iaa()` 或等价封装

可选辅助输入：

- `core_scene`
- `T_u`
- `C_u`
- `G_u`
- `activation_rate` / `degeneration_rate`

禁止：

- 修改真实标注几何
- 读取未来轮次信息
- 按 replay 结果反向改写 `r_u_lcb`、`worker_risk_tier` 或主表

---

## 3. 基本数据单位

回放的基本单位为 `(task_id, annotator_id)` 真实提交记录。

每次回放实验至少固定：

- `split_mode`
- `strategy`
- `seed`
- `k0`
- `k_max`
- 候选池定义
- 停止准则版本

同一 `(task_id, strategy, split_mode, seed, config_hash)` 必须得到完全一致的 worker 选择结果。

---

## 4. 候选池约束

### 4.1 基本过滤

候选记录必须满足：

- `scope` 可进入主分析
- 非 Type 4 过程损坏
- 对应 task 在当前 split 内
- `annotator_id` 非空

### 4.2 主线允许的风险过滤

按配置可过滤：

- `worker_risk_tier == R3`
- 对高风险任务排除已知在该风险桶失效的 `R2`
- 对依赖人工纠错的 semi 任务排除 `R1` 的高 blind-trust 工人

这些过滤必须在 manifest 中显式披露，禁止隐式发生。

---

## 5. 三种策略定义

### 5.1 Random

- 在候选池内做固定 seed 随机抽样。
- 作为 baseline。

### 5.2 Global

- 仅按 `r_u_lcb` 降序排序。
- 相同分数时按 `annotator_id` 字典序稳定打破。
- 不使用 scene-specific 可靠度。
- 不读取连续 `S_u` 作为主排序依据。

### 5.3 Full

- 使用 `d_t`、`I_t_OOD`、`g_t_triggered` 识别高风险任务。
- 优先使用场景特异可靠度 `r_u_s_lcb`，若场景未激活或样本不足，则显式退化到全局 `r_u_lcb`。
- 结合离散风险层级：
  - 高风险任务优先 `R0`
  - 已知桶内失效的 `R2` 不得进入对应高风险桶
  - `R3` 默认不进入主路由池
- 必须记录 `activation_status` 与 `degeneration_status`。

---

## 6. 序贯冗余与停止

### 6.1 配置

必须固定：

- `k0`
- `k_max`
- `stop_threshold`
- `stop_rule_version`

### 6.2 规则

- 先按策略选择 `k0` 名 worker。
- 若未达到停止准则，则按同一策略追加 worker，直到 `k_max`。
- `k_used` 必须如实记录。
- 到达 `k_max` 仍未满足停止准则时，必须记为 `max_k_reached`，不得伪造成功。

---

## 7. 回放接口

```python
import pandas as pd

class ReplayStrategy:
    name: str
    def select(self, candidate_df: pd.DataFrame, k: int, seed: int, context: dict) -> pd.DataFrame: ...

class RandomStrategy(ReplayStrategy): ...
class GlobalStrategy(ReplayStrategy): ...
class FullStrategy(ReplayStrategy): ...

def run_replay(df: pd.DataFrame, split: dict, strategies: list, seed: int = 42) -> pd.DataFrame: ...
```

要求：

- `run_replay()` 必须返回长表结果。
- 每行代表一次 `(task_id, strategy)` 回放结果。
- 所有策略必须可被 JSON 配置注入。

---

## 8. 输出字段

`replay_results.csv` 至少包含：

- `task_id`
- `split_mode`
- `strategy`
- `k0`
- `k_max`
- `k_used`
- `selected_workers`
- `n_candidate_workers`
- `IAA_t_replay`
- `replay_success`
- `failure_reason`
- `activation_status`
- `degeneration_status`
- `risk_bucket`
- `seed`
- `config_hash`
- `run_ts`

可选补充：

- `core_scene`
- `I_t_OOD`
- `g_t_triggered`
- `used_scene_specific_reliability`

规则：

- `selected_workers` 应使用稳定顺序拼接，如 `u01;u03;u07`
- 回放失败时 `IAA_t_replay=NA` 且 `failure_reason` 必填

---

## 9. 一致性计算约束

- `IAA_t_replay` 应与主项目 `compute_iaa()` 口径一致。
- 若 `k_used < 2` 无法计算一致性，则必须：
  - `IAA_t_replay=NA`
  - `failure_reason=insufficient_k_for_iaa`
- 不允许为单 worker 伪造一致性分数。

---

## 10. 审计与复现

必须产出：

1. `data/replay/replay_results.csv`
2. `data/replay/replay_manifest.json`
3. `data/replay/replay_failures.csv`

Manifest 至少包含：

```json
{
  "rule_version": "offline-replay-v2",
  "seed": 42,
  "strategies": ["Random", "Global", "Full"],
  "k0": 2,
  "k_max": 3,
  "split_mode": "stress_validation",
  "config_hash": "sha256:..."
}
```

附加要求：

- manifest 必须记录候选池过滤条件。
- manifest 必须记录 activation / degeneration 统计。
- hash log 必须可用于 Phase 2 在线服务对齐。

---

## 11. CLI 契约

```bash
python offline_replay.py \
  --input data/cleaned/merged_all.csv \
  --split-manifest data/splits/split_manifest.json \
  --output-dir data/replay/ \
  --seed 42
```

---

## 12. 验收清单

1. 三种策略在同一 seed 下输出完全可复现。
2. `Global` 必须稳定按 `r_u_lcb` 排序。
3. `Full` 的 activation / degeneration 必须写入审计，不得隐式发生。
4. 所有失败行均有 `failure_reason`。
5. 输出必须含 `strategy`、`k_used`、`split_mode`、`IAA_t_replay`。
6. 主实现不得把连续 `S_u` 当成当前主路由的唯一核心输入。
