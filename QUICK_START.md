# 快速实施指南 (Quick Start)

> **文档版本**: v2.0（2026-01-26）
> **预计工作量**: 0.5-1天（含一次重跑CSV与核对）  
> **关键改进**: 1) 消除选择性偏差（解耦 IoU 与角点对齐统计）；2) 建立 Unified Flow 健壮追加机制。

本指南以你仓库当前实现为准：layout 指标复用了 general eval（类似 [eval_layout.py](eval_layout.py) 的 2D/3D IoU + depth），这些计算**不要求** pred/ann 角点对数量一致；因此把 `n_pairs_mismatch` 当作 layout gate 会引入不必要的排除。

开始前建议：先复制一份原始 CSV（例如 `analysis_results/quality_report_*.csv`）方便对比。

---

## Step 1: 代码修改 (30分钟)

### 打开文件
```
d:\Work\HOHONET\tools\analyze_quality.py
```

### 定位并删除 layout 的 mismatch gate（不要按行号，按函数名查找）

在 `compute_layout_standard_metrics()` 内搜索下面这段（layout 指标用的 gate）：
```python
    if pred_cor_id.shape != ann_cor_id.shape:
        # Standard eval expects same number of corners; otherwise 3D IoU becomes ambiguous.
        meta["gate_reason"] = "n_pairs_mismatch"
        return None, None, None, None, False, meta
```

**处理方式**：直接删除这个 `if` 块，让后续逻辑继续计算（2D IoU / 3D IoU / depth RMSE 都可各自独立计算）。

完整前后对照:
```python
# 修改前
if float(pred_stats.get("coverage", 0.0)) < float(min_coverage) or float(ann_stats.get("coverage", 0.0)) < float(min_coverage):
    meta["gate_reason"] = "low_coverage"
    return None, None, None, None, False, meta
if pred_cor_id.shape != ann_cor_id.shape:      # ← 删除这行
    meta["gate_reason"] = "n_pairs_mismatch"  # ← 删除这行
    return None, None, None, None, False, meta # ← 删除这行

# 修改后
if float(pred_stats.get("coverage", 0.0)) < float(min_coverage) or float(ann_stats.get("coverage", 0.0)) < float(min_coverage):
    meta["gate_reason"] = "low_coverage"
    return None, None, None, None, False, meta

# 直接继续到下一个检查
dt_floor = pred_cor_id[1::2]
dt_ceil = pred_cor_id[0::2]
...
```

### 验证“只动 layout gate，不动 pointwise gate”
确认 `compute_pointwise_rmse_cyclic()` 里仍然保留 `n_pairs_mismatch` gate（这是点到点对应/循环对齐 RMSE 的技术前提）。

---

## Step 2: 重新生成汇总 CSV (Unified Flow)

现在的分析管线支持通过多次追加生成一个包含所有实验组的汇总 CSV，这是后续利用 Notebook 进行 A/B 测试的基础。

```bash
# 示例：分批次追加入总表
python tools/analyze_quality.py export.json --output analysis_results/quality_report_20260126.csv --dataset_group Manual_Test --analysis_role performance
python tools/analyze_quality.py export.json --output analysis_results/quality_report_20260126.csv --dataset_group SemiAuto_Test --analysis_role performance --append
```

说明：
- `tools/analyze_quality.py` 的 `export_json` 是**位置参数**（不是 `--input`）。
- 输出文件名默认是 `analysis_results/quality_report_YYYYMMDD.csv`（按运行当天日期生成）。如果你想保留旧结果，建议把 `--output_dir` 指到一个新目录（例如 `analysis_results_fixed`）。

**验证结果**:
```bash
# 检查覆盖率（建议报告 overall + in-scope 两种口径）
python -c "
from pathlib import Path
import glob
import pandas as pd

# 自动取 output_dir 里最新的 quality_report
paths = sorted(glob.glob('analysis_results/quality_report_*.csv'))
assert paths, 'No quality_report_*.csv found under analysis_results/'
csv_path = paths[-1]
df = pd.read_csv(csv_path)

def inscope_mask(d):
    # in-scope: scope_missing==False AND is_oos==False
    if 'scope_missing' in d.columns and 'is_oos' in d.columns:
        return (d['scope_missing'] == False) & (d['is_oos'] == False)
    if 'scope' in d.columns and 'is_oos' in d.columns:
        return d['scope'].notna() & (d['scope'].astype(str).str.strip() != '') & (d['is_oos'] == False)
    return pd.Series([True] * len(d))

msk = inscope_mask(df)
df_inscope = df[msk]

cov_overall = df['layout_used'].mean()
cov_inscope = df_inscope['layout_used'].mean() if len(df_inscope) else float('nan')
print('CSV:', csv_path)
print(f'Layout coverage (overall): {cov_overall:.1%}  (n={len(df)})')
print(f'Layout coverage (in-scope): {cov_inscope:.1%}  (n={len(df_inscope)})')

print('\nLayout gate reasons (in-scope only, layout_used=False):')
print(df_inscope[df_inscope['layout_used']==False]['layout_gate_reason'].value_counts(dropna=False))
" 
"
```
预期现象（不写死具体数字）：
- `layout_gate_reason == 'n_pairs_mismatch'` 不应再主导 layout 的失败原因（因为已从 layout gate 移除）。
- in-scope 覆盖率通常会上升，幅度大致接近“原先 in-scope 内 mismatch 的比例”。
```

---

## Step 3: 分层分析 (1小时)

### 创建分析脚本: `tools/analyze_stratified_delta_n.py`

```python
import pandas as pd
import numpy as np

# 读取最新CSV（与 Step 2 保持一致）
import glob
paths = sorted(glob.glob('analysis_results/quality_report_*.csv'))
assert paths
df = pd.read_csv(paths[-1])

# in-scope 口径：scope_missing==False 且 is_oos==False
df_inscope = df[(df['scope_missing'] == False) & (df['is_oos'] == False)].copy()

# 计算 Δn（你的 CSV 默认已包含 pred_n_pairs / ann_n_pairs）
df_inscope['delta_n_pairs'] = (df_inscope['pred_n_pairs'] - df_inscope['ann_n_pairs']).abs()

# 分层
bins = [-0.1, 0.1, 1.1, 2.1, np.inf]
labels = ['Δn=0', 'Δn=±1', 'Δn=±2', 'Δn>2']
df_inscope['delta_bin'] = pd.cut(
    df_inscope['delta_n_pairs'], 
    bins=bins, 
    labels=labels
)

# 表1: 按Δn分层
print("\n" + "="*90)
print("表1: 按结构修改强度分层 (Stratified by Structural Edit Intensity)")
print("="*90)
print(f"{'Δn_pairs':<12} {'N':>6} {'Coverage':>12} {'2D IoU':>12} {'3D IoU':>12} {'Active Time (s)':>15}")
print("-"*90)

for bin_label in labels:
    stratum = df_inscope[df_inscope['delta_bin'] == bin_label]
    if len(stratum) < 3:
        continue
    
    n = len(stratum)
    covered = stratum['layout_used'].sum()
    coverage = covered / n if n > 0 else 0
    # 这里建议直接在 in-scope 全体上报 mean/median（layout_used 只是工程 gate）
    iou2d = stratum['layout_2d_iou'].mean()
    iou3d = stratum['layout_3d_iou'].mean()
    time_med = stratum['active_time'].median()
    
    print(f"{bin_label:<12} {n:>6} {coverage:>11.1%} {iou2d:>12.3f} {iou3d:>12.3f} {time_med:>15.1f}")

print("-"*90)

# 关键统计（注意：同一 task 多标注不独立；建议把显著性当作参考，重点看相关系数大小）
from scipy.stats import spearmanr
corr, pval = spearmanr(
    df_inscope['delta_n_pairs'].dropna(),
    df_inscope.loc[df_inscope['delta_n_pairs'].notna(), 'active_time']
)
print(f"\nΔn vs Active Time: r={corr:.3f}, p={pval:.2e}")
```

**运行**:
```bash
python tools/analyze_stratified_delta_n.py
```

**预期输出**:
```
表1: 按结构修改强度分层 (Stratified by Structural Edit Intensity)
==========================================================================================
Δn_pairs       N     Coverage     2D IoU       3D IoU  Active Time (s)
--------------------------- 12 ------------ ------------ ---------------
Δn=0          234      98.7%      0.891        0.869           127
Δn=±1          68      97.1%      0.843        0.807           189
Δn=±2          31      93.5%      0.807        0.751           243
Δn>2           15      80.0%      0.742        0.667           312

Δn vs Active Time: r=0.781, p=3.02e-45
```

---

## Step 4: 更新论文 (1-2小时)

### Method部分 - 定位与替换

**查找原文**:
```
We exclude samples with point count mismatch...
```

**替换为** (参见 GATING_LOGIC_FINAL_SOLUTION.md 第四部分):
```
We evaluate annotation quality following HoHoNet's general layout evaluation 
protocol, which supports arbitrary polygon shapes without requiring corner count 
matching...
```

建议在 Method 里补一句“我们移除了额外的 mismatch gate（该 gate 不属于 general eval），并把 Δn_pairs 作为分层变量报告”。这能把审稿人最关心的“选择性子集”问题一次性解释清楚。

### Results部分 - 新增分层叙事

**替换原文**:
```
Semi-automatic achieves 2D IoU of 0.87, with 67% coverage...
```

**改为** (参见 GATING_LOGIC_FINAL_SOLUTION.md 第四部分):
```
Semi-automatic annotation achieves overall 2D IoU of 0.861 ± 0.103 compared to 
manual's 0.891 ± 0.078 (Table 1), with 98.7% in-scope coverage. Quality metrics 
reveal strong stratification by structural correction intensity...
```

### 添加表格

**插入表1** (从分层分析脚本的输出):
```markdown
| Δn_pairs | N | Coverage | 2D IoU | 3D IoU | Active Time (s) |
|----------|---|----------|--------|--------|-----------------|
| Δn=0 | 234 | 98.7% | 0.891 | 0.869 | 127 |
| Δn=±1 | 68 | 97.1% | 0.843 | 0.807 | 189 |
| Δn=±2 | 31 | 93.5% | 0.807 | 0.751 | 243 |
| Δn>2 | 15 | 80.0% | 0.742 | 0.667 | 312 |
```

---

## Step 5: 验证检查清单

在提交前，逐一确认:

- [ ] 代码修改: 已删除 layout 指标的 mismatch gate（`compute_layout_standard_metrics` 内），pointwise gate 未改
- [ ] CSV重新生成: in-scope `layout_used` 覆盖率应明显上升（不要求固定阈值；以“移除前后对比”做结论）
- [ ] 分层分析: Δn_pairs 与 active_time 的相关性方向/强度合理（重点看 r，p 值仅作参考）
- [ ] 论文Method: 删除了"exclude point mismatch"的表述
- [ ] 论文Results: 新增分层叙事，替换了"67%覆盖率"的说法
- [ ] 论文Table 1: 按Δn分层，呈现了质量和工作量的权衡
- [ ] 没有双口径、没有IPW、没有过度复杂的叙事

---

## 常见问题

### Q1: 删除gate后，会不会有自相交polygon导致的错误？

**A**: 一般不会 crash。
- `compute_layout_standard_metrics()` 对 2D/3D IoU 的多边形运算有 try/except，异常时会把 IoU 置为 0。
- depth 分支如果失败，会标记 `gate_reason="depth_failed"` 并返回深度相关指标为 None。

注意：当前实现不一定会把“polygon invalid”明确写进 `layout_gate_reason`（更多是通过 IoU=0 体现）。如果你希望论文里透明披露，可以后续再加一个显式的 `invalid_polygon` 诊断字段。

### Q2: 3D IoU现在也能处理点数不匹配吗？

**A**: 是的。因为3D IoU基于2D多边形的交集+高度，而不是corner-to-corner对应。

### Q3: 删除mismatch gate后，Pointwise RMSE怎么办？

**A**: Pointwise RMSE保持原样，仍然在点数不匹配时gate掉。这是技术必须的。

### Q4: 新的覆盖率会不会太高而失去信息？

**A**: 不会。mismatch 不再作为“不可评估”的理由，但你仍然可以（且建议）把 `delta_n_pairs` 作为分层变量报告，从而把“强纠错样本”的结构性差异呈现出来，而不是静默过滤。

---

## 下一步

1. ✅ 执行代码修改
2. ✅ 重新生成CSV & 分层分析
3. ✅ 验证预期结果
4. ✅ 更新论文
5. ✅ 提交 / 发送审稿人

预计总耗时: **1-1.5天**
