# 半自动标注项目测试计划与代码审查报告

> **版本**: 1.0  
> **日期**: 2026-01-18  
> **适用范围**: `tools/analyze_quality.py`, `tools/visualize_output.ipynb`, 及相关工具链

---

## 目录

1. [测试计划 (Test Plan)](#1-测试计划-test-plan)
2. [测试用例设计 (Test Cases)](#2-测试用例设计-test-cases)
3. [配置项与变更控制 (CFG/COC)](#3-配置项与变更控制-cfgcoc)
4. [代码逻辑缺陷分析](#4-代码逻辑缺陷分析)
5. [权威专家视角优化建议](#5-权威专家视角优化建议)

---

## 1. 测试计划 (Test Plan)

### 1.1 测试目标

验证半自动标注分析工具链的以下关键能力：

| ID | 测试目标 | 对应论文研究问题 |
|----|---------|-----------------|
| T1 | 数据解析正确性 | 所有 RQ 的数据基础 |
| T2 | 指标计算准确性 | RQ1 效率 / RQ2 质量 |
| T3 | 门控逻辑严密性 | RQ2 可靠性不被污染 |
| T4 | 一致性/可靠度计算 | RQ3 专家识别 |
| T5 | 端到端可复现性 | 审稿可复现要求 |

### 1.2 测试范围

```
┌─────────────────────────────────────────────────────────────────┐
│                      测试边界 (Scope)                            │
├─────────────────────────────────────────────────────────────────┤
│ ✅ 纳入测试                                                      │
│    - analyze_quality.py (核心计算层)                            │
│    - visualize_output.ipynb (下游展示层)                        │
│    - save_quality_figures.py (批量可视化)                       │
│    - aggregate_analysis.py (跨数据集汇总)                       │
│    - active_logs 解析逻辑                                       │
│                                                                  │
│ ❌ 不纳入测试                                                    │
│    - HoHoNet 模型训练/推理代码 (已有独立测试)                   │
│    - Label Studio 前端 (第三方)                                 │
│    - Nginx/日志服务器 (运维层)                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 测试策略

采用 **分层测试** 策略：

| 层级 | 测试类型 | 覆盖目标 | 工具 |
|------|---------|---------|------|
| L0 | 单元测试 | 核心函数正确性 | pytest |
| L1 | 集成测试 | 模块间数据流 | pytest + fixtures |
| L2 | 回归测试 | 已修复 Bug 不复发 | pytest + golden files |
| L3 | 端到端测试 | 完整工作流 | CLI + diff |

### 1.4 测试环境要求

```yaml
# test_environment.yml
python: ">=3.8"
dependencies:
  - numpy>=1.20
  - scipy>=1.7
  - shapely>=2.0
  - pandas>=1.5
  - matplotlib>=3.5
  - seaborn>=0.12
  - pytest>=7.0
  - pytest-cov>=4.0
```

### 1.5 通过标准 (Exit Criteria)

| 指标 | 阈值 | 说明 |
|------|------|------|
| 单元测试通过率 | 100% | 所有用例必须通过 |
| 代码覆盖率 | ≥80% | 核心计算函数 ≥95% |
| 回归测试 | 0 失败 | 历史 Bug 不复发 |
| Golden File Diff | 0 差异 | 可复现性验证 |

---

## 2. 测试用例设计 (Test Cases)

### 2.1 单元测试用例

#### 2.1.1 数据解析模块

| TC-ID | 测试名称 | 输入 | 期望输出 | 优先级 |
|-------|---------|------|---------|--------|
| TC-U001 | `extract_data` 空结果 | `results=[]` | `corners=[], poly=[], choice_map={}` | P0 |
| TC-U002 | `extract_data` 正常角点 | 8 个 keypoint | `corners.shape==(8,2)` | P0 |
| TC-U003 | `extract_data` 多选框解析 | `scope=["In-scope"], difficulty=["遮挡","低纹理"]` | `choice_map` 正确分离 | P0 |
| TC-U004 | `parse_quality_flags_v2` scope 缺失 | `choice_map={}` | `scope_missing=True, is_oos=None, is_normal=None` | P0 |
| TC-U005 | `parse_quality_flags_v2` OOS 判定 | `scope=["OOS：边界不可判定"]` | `is_oos=True` | P0 |
| TC-U006 | `parse_quality_flags_v2` In-scope 判定 | `scope=["In-scope：只标相机房间"]` | `is_oos=False, is_normal=True` | P0 |
| TC-U007 | `_split_choice_values` 分号分隔 | `"a;b;c"` | `["a","b","c"]` | P1 |
| TC-U008 | `_split_choice_values` 列表输入 | `["a","b"]` | `["a","b"]` | P1 |

#### 2.1.2 几何计算模块

| TC-ID | 测试名称 | 输入 | 期望输出 | 优先级 |
|-------|---------|------|---------|--------|
| TC-G001 | `compute_iou` 完全重合 | 相同多边形 | `IoU=1.0` | P0 |
| TC-G002 | `compute_iou` 完全不重合 | 分离多边形 | `IoU=0.0` | P0 |
| TC-G003 | `compute_iou` 无效多边形 | `[]` | `IoU=0.0` (不报错) | P0 |
| TC-G004 | `compute_boundary_mse_rmse` 相同边界 | 相同角点 | `RMSE=0.0` | P0 |
| TC-G005 | `compute_boundary_mse_rmse` 点数不一致 | 8 vs 6 角点 | 仍能计算 (鲁棒) | P0 |
| TC-G006 | `compute_pointwise_rmse_cyclic` 循环对齐 | 拼接缝偏移 | `best_shift` 正确 | P1 |
| TC-G007 | `_pair_keypoints_to_layout` 配对 | 8 个角点 | 4 对 (ceil/floor) | P0 |
| TC-G008 | `_pair_keypoints_to_layout` 奇数点 | 7 个角点 | `odd_points=True` | P0 |

#### 2.1.3 门控逻辑模块

| TC-ID | 测试名称 | 输入条件 | 期望 `layout_used` | 期望 `gate_reason` | 优先级 |
|-------|---------|---------|-------------------|-------------------|--------|
| TC-L001 | OOS 门控 | `is_oos=True` | `False` | `"out_of_scope"` | P0 |
| TC-L002 | scope 缺失门控 | `scope_missing=True` | `False` | `"scope_missing"` | P0 |
| TC-L003 | 覆盖率不足 | `coverage<0.9` | `False` | `"low_coverage"` | P0 |
| TC-L004 | 点数不匹配（L1 不门控） | `n_pred != n_ann` | `True` | `""`（不应为 mismatch） | P0 |
| TC-L005 | 正常通过 | In-scope + 点数一致 | `True` | `""` | P0 |

> 说明：P0-1 之后，`n_pairs_mismatch` 不再作为 L1 标准 layout 指标的门控条件；它仍作为 **pointwise** 指标的门控原因（见下表）。

#### 2.1.3.1 Pointwise 门控（cyclic RMSE）

| TC-ID | 测试名称 | 输入条件 | 期望 `pointwise_rmse_used` | 期望 `pointwise_gate_reason` | 优先级 |
|-------|---------|---------|---------------------------|-----------------------------|--------|
| TC-P001 | 覆盖率不足 | `coverage<0.9` | `False` | `"low_coverage"` | P0 |
| TC-P002 | 点数不匹配 | `n_pred != n_ann` | `False` | `"n_pairs_mismatch"` | P0 |
| TC-P003 | 正常通过 | In-scope + 点数一致 | `True` | `""` | P0 |

#### 2.1.4 一致性/可靠度模块

| TC-ID | 测试名称 | 输入 | 期望输出 | 优先级 |
|-------|---------|------|---------|--------|
| TC-R001 | `_bootstrap_ci` 空数组 | `[]` | `(None, None, None)` | P0 |
| TC-R002 | `_bootstrap_ci` 单值 | `[0.5]` | `(0.5, 0.5, 0.5)` | P1 |
| TC-R003 | LOO 共识 2 人任务 | 2 annotators | LOO 共识 = 对方 | P0 |
| TC-R004 | LOO 共识 3+ 人任务 | 3 annotators | medoid 从其他人选 | P0 |
| TC-R005 | mixed-scope 任务排除 | 同任务 In-scope + OOS | 不参与共识计算 | P0 |
| TC-R006 | `layout_used=False` 不进入共识 | L1 门控失败 | `iou_to_consensus_loo=None` | P0 |

### 2.2 集成测试用例

| TC-ID | 测试名称 | 测试流程 | 验证点 |
|-------|---------|---------|--------|
| TC-I001 | 端到端 CSV 生成 | `analyze_quality.py` → CSV | CSV 字段完整、格式正确 |
| TC-I002 | active_logs 合并 | JSONL → active_time | session max + sum 逻辑 |
| TC-I003 | 多数据集聚合 | `aggregate_analysis.py` | dataset/condition/subset 列正确 |
| TC-I004 | 可视化流程 | CSV → `visualize_output.ipynb` | 清洗逻辑与上游一致 |

### 2.3 回归测试用例

| TC-ID | 对应 Bug | 测试场景 | 验证条件 |
|-------|---------|---------|---------|
| TC-REG001 | BUG #1 LOO 门控污染 | `layout_used=False` 的行 | `iou_to_consensus_loo` 必须为 `None` |
| TC-REG002 | BUG #2 scope_missing 口径 | scope 字段缺失 | `is_normal` 必须为 `None`，不是 `True` |
| TC-REG003 | scope_missing 列输出 | 任意导出 | CSV 必须包含 `scope_missing` 列 |

### 2.4 Golden File 测试

```
tests/
├── fixtures/
│   ├── sample_export_minimal.json     # 最小有效导出
│   ├── sample_export_edge_cases.json  # 边缘场景
│   └── sample_active_logs/            # active_logs 样例
└── golden/
    ├── quality_report_minimal.csv     # 预期输出
    └── reliability_report_minimal.csv
```

测试逻辑：
```python
def test_golden_file_match():
    result = run_analyze_quality("fixtures/sample_export_minimal.json")
    expected = load_golden("golden/quality_report_minimal.csv")
    assert_dataframes_equal(result, expected, rtol=1e-4)
```

---

## 3. 配置项与变更控制 (CFG/COC)

### 3.1 配置项清单 (Configuration Items)

| CI-ID | 配置项 | 路径 | 版本控制 | 说明 |
|-------|-------|------|---------|------|
| CI-001 | Label Studio 视图配置 | `tools/label_studio_view_config.xml` | Git | 定义 scope/difficulty/model_issue 选项 |
| CI-002 | 分析脚本默认参数 | `tools/analyze_quality.py` CLI | Git | `--metric corner --quality_mode v2` |
| CI-003 | 聚合配置 | `tools/aggregate_config.json` | Git | 数据集映射与分组策略 |
| CI-004 | 可视化清洗逻辑 | `tools/visualize_output.ipynb` | Git | `clean_quality_df()` 函数 |
| CI-005 | 测试 fixtures | `tests/fixtures/*.json` | Git | 测试用导出样例 |
| CI-006 | Golden files | `tests/golden/*.csv` | Git | 预期输出基线 |

### 3.2 变更控制流程 (Change Control)

```
┌──────────────────────────────────────────────────────────────┐
│                    变更控制流程                                │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. 提出变更请求 (Issue/Discussion)                           │
│         │                                                     │
│         ▼                                                     │
│  2. 影响分析                                                   │
│     • 涉及哪些配置项？                                         │
│     • 是否影响已发布数据的可复现性？                           │
│     • 是否需要更新文档/Golden Files？                          │
│         │                                                     │
│         ▼                                                     │
│  3. 实施变更 (Branch)                                          │
│     • 修改代码                                                 │
│     • 更新配置项                                               │
│     • 更新 Golden Files (如需)                                 │
│         │                                                     │
│         ▼                                                     │
│  4. 测试验证                                                   │
│     • 单元测试通过                                             │
│     • 回归测试通过                                             │
│     • Golden File Diff = 0 (或预期内变化)                      │
│         │                                                     │
│         ▼                                                     │
│  5. 文档同步                                                   │
│     • 更新 CHANGELOG                                           │
│     • 更新 HANDOVER 文档                                       │
│     • 更新 README (如需)                                       │
│         │                                                     │
│         ▼                                                     │
│  6. 合并 & 发布                                                │
│     • Code Review                                              │
│     • Merge to main                                            │
│     • Tag release (如需)                                       │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 版本命名约定

```
quality_report_YYYYMMDD.csv          # 日期标记
reliability_report_YYYYMMDD.csv      # 日期标记
analyze_quality.py v2.3.0            # SemVer (Major.Minor.Patch)
```

**Major**: 不兼容的输出格式变更（如新增必要字段）  
**Minor**: 新增功能（如新指标列）  
**Patch**: Bug 修复（不改变输出格式）

---

## 4. 代码逻辑缺陷分析

经过全面审查，发现以下问题：

### 4.1 严重问题 (Critical)

| ID | 问题 | 位置 | 影响 | 建议 |
|----|------|------|------|------|
| **BUG-C01** | `reliability_used` 与 `task_user_poly` 门控逻辑分离 | `analyze_quality.py` L1225-1240 | `reliability_used` 字段与实际进入共识计算的条件不完全一致 | 统一 `reliability_used = True` 的条件与 `task_user_poly` 填充条件 |

**详细分析**：

当前代码在 L1225-1240 计算 `reliability_used`：
```python
if bool(qflags.get('scope_missing')):
    reliability_gate_reason = "scope_missing"
elif qflags.get('is_oos') is not False:
    reliability_gate_reason = "oos_or_unknown"
elif not final_ann_poly:
    reliability_gate_reason = "empty_poly"
elif not _poly_is_valid(final_ann_poly):
    reliability_gate_reason = "invalid_poly"
else:
    reliability_used = True
    task_user_poly[t_id][u_id] = final_ann_poly
```

但在后续共识计算 L1310+ 中，还额外排除了 `mixed_scope_tasks` 和 `scope_unknown_tasks`：
```python
if str(t_id) in mixed_scope_tasks:
    continue
if str(t_id) in scope_unknown_tasks:
    continue
```

**问题**：`reliability_used=True` 的行可能因任务级条件被排除，但 CSV 输出的 `reliability_used` 仍为 True，造成下游误解。

**修复建议**：
```python
# 在共识计算后，更新被排除任务的 reliability_used
for r in rows:
    t_id = str(r.get('task_id'))
    if t_id in mixed_scope_tasks or t_id in scope_unknown_tasks:
        if r.get('reliability_used'):
            r['reliability_used'] = False
            r['reliability_gate_reason'] = 'task_excluded_mixed_or_unknown_scope'
```

### 4.2 中等问题 (Medium)

| ID | 问题 | 位置 | 影响 | 建议 |
|----|------|------|------|------|
| **BUG-M01** | 2 人任务 LOO 退化 | `analyze_quality.py` L1415+ | 2 人任务 LOO 共识 = 对方，统计意义弱 | 在 CSV 中增加 `n_others` 列，供下游过滤 |
| **BUG-M02** | medoid 平局不稳定 | `analyze_quality.py` L1375 | 相同 median 时结果依赖遍历顺序 | 增加确定性二级排序（如 uid 字典序） |
| **BUG-M03** | `visualize_output.ipynb` 缺少 LOO sanity check | notebook | 可能展示不应有 LOO 值的行 | 添加 `assert (layout_used==False).implies(iou_to_consensus_loo.isna())` |
| **BUG-M04** | `condition` 推断依赖 prediction 存在性 | `analyze_quality.py` L1037-1050 | 如果 prediction 格式变化可能误判 | 建议在 Label Studio 导出时显式标记 condition |

**BUG-M02 修复代码**：

当前代码 L1375:
```python
scores.append((med, mean, uid, i))
# ...
best_idx = sorted(scores, key=lambda x: (-x[0], -x[1], x[2]))[0][3]
```

这已经包含了 uid 作为第三排序键，但应确保 uid 是字符串且排序一致：
```python
# 确保 uid 是字符串，避免混合类型比较问题
best_idx = sorted(scores, key=lambda x: (-x[0], -x[1], str(x[2])))[0][3]
```

### 4.3 低风险问题 (Low)

| ID | 问题 | 位置 | 影响 | 建议 |
|----|------|------|------|------|
| **BUG-L01** | 小样本 CI 无警告 | `analyze_quality.py` L1595 | `n_tasks<5` 时 CI 可能不可信 | 已有 `[WARN]` 但仅在控制台，建议在 CSV 中增加 `ru_sample_warning` 列 |
| **BUG-L02** | `_safe_float` 对 bool 的处理 | `analyze_quality.py` L119 | `True` → `1.0`，可能不符预期 | 明确文档说明或在解析时排除 bool 类型列 |
| **BUG-L03** | 缺少类型注解 | 多处 | 可维护性 | 逐步添加 type hints |
| **BUG-L04** | 边界条件：空 JSON 导出 | `analyze_quality.py` | 空任务列表时无明确错误信息 | 增加 early return 和用户友好提示 |

### 4.4 代码质量建议

| 建议 | 当前状态 | 改进方向 |
|------|---------|---------|
| 函数文档字符串 | 部分有 | 所有公开函数添加 docstring + 类型注解 |
| 常量集中管理 | 硬编码在函数中 | 提取到模块顶部或配置文件 |
| 日志级别 | 只有 `print` | 引入 `logging` 模块，支持 DEBUG/INFO/WARN |
| 错误处理 | 部分 try-except | 统一异常类型，提供可操作的错误信息 |

---

## 5. 权威专家视角优化建议

### 5.1 领域权威人士

标注质量与标注者一致性（Inter-Annotator Agreement）领域的权威专家：

| 专家 | 贡献 | 与本项目的关联 |
|------|------|---------------|
| **Klaus Krippendorff** | Krippendorff's Alpha，可靠性理论奠基人 | 你的 $r_u$ / IAA 计算理念 |
| **Ron Artstein & Massimo Poesio** | IAA 计算标准化（Computational Linguistics, 2008） | 多标注者共识方法论 |
| **Jacob Cohen** | Cohen's Kappa，评分者一致性 | 分类任务一致性（可扩展） |
| **Joseph L. Fleiss** | Fleiss' Kappa，多评分者 | 多标注者场景 |

### 5.2 Krippendorff 视角的优化建议

以 Klaus Krippendorff 的**可靠性理论**和**可审计性原则**为指导：

#### 5.2.1 明确区分 Agreement vs Reliability

> "Agreement is what you measure; reliability is what you infer."  
> — Krippendorff

**问题**：当前代码中 `iou_to_consensus_loo` 混合了 agreement 和 reliability 的含义。

**建议**：
- 将指标明确命名为 `agreement_to_loo_consensus`（描述性名称）
- 在文档中区分：
  - **Agreement**：观察到的标注者间一致性（IoU 值本身）
  - **Reliability**：推断的"真值"可重现性（通过 bootstrap CI 估计）

#### 5.2.2 处理"不可标注"样本

> Krippendorff 强调：reliability 计算应排除"无法达成共识"的单元。

**问题**：当前 OOS 处理是合理的，但缺少对 OOS 判定本身的一致性分析。

**建议**：
```python
# 新增指标：OOS 判定一致性
oos_agreement = compute_oos_agreement(task_scope_counts)
# 报告：标注者对"什么是 OOS"是否有共识
```

这对论文很重要：如果标注者对 OOS 的定义不一致，主指标可能系统性偏高。

#### 5.2.3 报告单位一致性 (Unitizing Reliability)

**问题**：当前指标假设"任务"是固定单位，但实际上：
- 不同标注者可能标注了不同数量的角点
- 边界定义可能有差异

**建议**：增加"单位化"诊断指标：
```python
# 角点数量一致性
n_corners_agreement = compute_krippendorff_alpha(
    task_annotator_n_corners_matrix,
    metric='interval'
)
```

### 5.3 Artstein-Poesio 视角的优化建议

参考《Inter-Coder Agreement for Computational Linguistics》(2008)：

#### 5.3.1 多重比较校正

**问题**：当同时报告多个指标时，需要注意多重比较问题。

**建议**：
- 明确声明主指标 vs 探索性指标
- 对探索性比较应用 Bonferroni 校正或 FDR 控制

#### 5.3.2 样本量与效应量报告

**建议**：在 reliability_report 中增加：
```csv
annotator_id, n_tasks, ru_median_iou, ru_ci_low, ru_ci_high, effect_size_vs_random, sample_adequacy
```

其中 `effect_size_vs_random` = 与随机猜测基线的差异，`sample_adequacy` = 是否达到最小样本量（如 n≥10）。

### 5.4 具体可操作改进清单

| 优先级 | 改进项 | 工作量 | 预期收益 |
|-------|-------|-------|---------|
| **P0** | 修复 `reliability_used` 与共识计算的不一致 | 1h | 避免审稿人质疑 |
| **P0** | 增加 `n_others` 列到 CSV | 0.5h | 2 人任务 LOO 透明化 |
| **P0** | `visualize_output.ipynb` sanity check | 0.5h | 防止展示错误数据 |
| **P1** | medoid 确定性排序 | 0.5h | 可复现性 |
| **P1** | 增加 OOS 判定一致性指标 | 2h | 方法论完整性 |
| **P2** | 引入 logging 模块 | 2h | 可维护性 |
| **P2** | 增加类型注解 | 4h | 代码质量 |
| **P3** | 单元测试框架搭建 | 8h | 长期可维护性 |

### 5.5 论文呈现建议

基于 Krippendorff/Artstein-Poesio 的最佳实践：

1. **透明报告**：
   - 明确列出所有门控条件及被排除样本数
   - 报告 OOS 比例及其分布
   - 区分 agreement（观察值）和 reliability（推断值）

2. **效应量优先**：
   - 避免仅报告 p-value
   - 报告 Cohen's d 或类似效应量
   - 提供置信区间

3. **可复现性**：
   - 公开 `aggregate_config.json` 和 seed
   - 提供 Golden Files 供验证
   - 在补充材料中公开完整分析脚本

---

## 附录 A：测试代码模板

```python
# tests/test_analyze_quality.py

import pytest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from analyze_quality import (
    parse_quality_flags_v2,
    compute_iou,
    compute_boundary_mse_rmse,
    _pair_keypoints_to_layout,
    _bootstrap_ci,
)


class TestParseQualityFlagsV2:
    """TC-U004 ~ TC-U006"""
    
    def test_scope_missing(self):
        """TC-U004: scope 缺失时返回 tri-state None"""
        result = parse_quality_flags_v2({}, mode='v2')
        assert result['scope_missing'] == True
        assert result['is_oos'] is None
        assert result['is_normal'] is None
    
    def test_oos_detection(self):
        """TC-U005: OOS 判定"""
        result = parse_quality_flags_v2(
            {'scope': ['OOS：边界不可判定']},
            mode='v2'
        )
        assert result['is_oos'] == True
        assert result['scope_missing'] == False
    
    def test_in_scope_detection(self):
        """TC-U006: In-scope 判定"""
        result = parse_quality_flags_v2(
            {'scope': ['In-scope：只标相机房间']},
            mode='v2'
        )
        assert result['is_oos'] == False
        assert result['is_normal'] == True


class TestComputeIoU:
    """TC-G001 ~ TC-G003"""
    
    def test_identical_polygons(self):
        """TC-G001: 完全重合"""
        poly = [(0,0), (1,0), (1,1), (0,1)]
        assert compute_iou(poly, poly) == pytest.approx(1.0)
    
    def test_disjoint_polygons(self):
        """TC-G002: 完全不重合"""
        poly1 = [(0,0), (1,0), (1,1), (0,1)]
        poly2 = [(10,10), (11,10), (11,11), (10,11)]
        assert compute_iou(poly1, poly2) == pytest.approx(0.0)
    
    def test_empty_polygon(self):
        """TC-G003: 空多边形"""
        assert compute_iou([], [(0,0), (1,0), (1,1)]) == 0.0


class TestBootstrapCI:
    """TC-R001 ~ TC-R002"""
    
    def test_empty_array(self):
        """TC-R001: 空数组"""
        stat, lo, hi = _bootstrap_ci([], np.median)
        assert stat is None
        assert lo is None
        assert hi is None
    
    def test_single_value(self):
        """TC-R002: 单值"""
        stat, lo, hi = _bootstrap_ci([0.5], np.median)
        assert stat == pytest.approx(0.5)
        assert lo == pytest.approx(0.5)
        assert hi == pytest.approx(0.5)


class TestRegressionBugs:
    """TC-REG001 ~ TC-REG003 回归测试"""
    
    def test_layout_used_false_no_loo(self):
        """TC-REG001: layout_used=False 时 iou_to_consensus_loo 必须为 None"""
        # 需要使用完整的 fixture 进行端到端测试
        pass  # TODO: implement with fixture
    
    def test_scope_missing_no_is_normal(self):
        """TC-REG002: scope 缺失时 is_normal 必须为 None"""
        result = parse_quality_flags_v2({}, mode='v2')
        assert result['is_normal'] is None


# pytest 运行配置
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
```

---

## 附录 B：配置文件模板

```json
// tools/test_config.json
{
    "test_fixtures_dir": "tests/fixtures",
    "golden_files_dir": "tests/golden",
    "coverage_threshold": 0.80,
    "critical_functions": [
        "parse_quality_flags_v2",
        "compute_iou",
        "compute_boundary_mse_rmse",
        "compute_layout_standard_metrics",
        "_bootstrap_ci"
    ],
    "regression_bugs": [
        {
            "id": "BUG-2026-01-18-001",
            "description": "LOO 门控污染",
            "test_case": "TC-REG001"
        },
        {
            "id": "BUG-2026-01-18-002",
            "description": "scope_missing 口径污染",
            "test_case": "TC-REG002"
        }
    ]
}
```

---

**文档版本**: 1.0  
**最后更新**: 2026-01-18  
**作者**: AI Code Review Assistant
