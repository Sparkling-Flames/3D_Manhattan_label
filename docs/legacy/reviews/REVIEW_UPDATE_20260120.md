# 代码修改审查意见（2026-01-20 修订）

> **审稿人视角**: Top-tier HCI/CV venue  
> **对比基准**: 之前的审稿意见 (REVIEW_CRITIQUE_20260120.md)  
> **更新日期**: 2026-01-20 22:00+

---

## 📊 修改概览

### 发现的改进

✅ **改进1**: Notebook结构重组（Section 0-7）
- 之前混乱的单元格顺序已按RQ逻辑重新组织
- 现在有明确的Section标题和流程说明
- CONFIG配置已集中管理（解决硬编码路径问题）

✅ **改进2**: 新增诊断工具 `diagnose_gating_bias.py`
- 快速评估Selection Bias风险的独立脚本
- 包含风险评分系统 (0-8分)
- 支持命令行调用和quiet模式

---

## 🔴 仍存在的Critical Issues

### C1. **RQ2/RQ3的实现仍是TODO** (Blocking)

**现状**:
```
Section 4: RQ2 - Quality & Reliability (6-8个单元格)
  - [新增] Markdown: Section 4标题 + RQ2简述
  - [新增实现] Cell: Fig 5A代码（IAA分布）  <- TODO
  - [新增实现] Cell: Fig 5B代码（个体 vs LOO共识） <- TODO
  - ...

Section 5: RQ3 - Expert Identification & Task Assignment <- 完全空白
```

**后果**:
- RQ2的所有图表仍未实现（IAA/LOO/可靠性）
- RQ3完全缺失（无$r_u$估计、无分配策略对比）
- 审稿人会说："你说有3个RQ，但只有RQ1的图表"

**建议修复**:
1. **立即补充RQ2的核心图表代码**:
   - IAA分布（df_rel上iou_to_others_median）
   - LOO共识vs个体（scatter或box对比）
   - 改动幅度vs质量的关系（证明可分离）

2. **补充RQ3框架**:
   - $r_u$估计与聚合（per-annotator中位数+CI）
   - $r_u$vs效率的关系图
   - 分配策略对比表（如有验证集）

---

### C2. **诊断工具虽然有用，但不能替代论文图表** (Design Issue)

**现状**: `diagnose_gating_bias.py` 做得不错，包含：
- ✅ 覆盖率统计
- ✅ 门控原因分布  
- ✅ mismatch特征分析
- ✅ 按condition/annotator分层
- ✅ 风险评分系统

**问题**:
- 这个工具是**文本报告**，不能直接用于论文
- 论文需要的是**Figure/Table**（panel A/B/C/D），而不是打印输出
- 诊断脚本可以用于内部评估，但不能替代visualize_output.ipynb的Figure生成

**后果**: 审稿人说："你给了诊断报告，但没给论文Figure"

**建议**:
1. `diagnose_gating_bias.py`保留为内部诊断工具（不用于论文）
2. visualize_output.ipynb的**Section 2**应该**调用diagnose_gating_bias的逻辑**来生成Figure 2
   ```python
   # Section 2: 对标diagnose_gating_bias.py的逻辑，但输出Figure而不是文本
   def plot_coverage_and_gating(df_transparent, df_inscope):
       fig, axes = plt.subplots(2, 2, figsize=(14, 10))
       # Panel A: 覆盖率
       # Panel B: 门控原因分布
       # Panel C: mismatch vs matched的耗时对比
       # Panel D: 按condition分层
       return fig
   ```

---

### C3. **P0-1敏感性分析（Section 6）还是TODO** (Major)

**论文提纲要求**:
> "对至少一组核心结果同步给出'严格 gate（历史口径）'与'P0-1 口径'的对照，明确说明差异来自覆盖率变化而非指标定义漂移。"

**现状**: visualize_output.ipynb Section 6仍然是空白

**后果**: 审稿人会质疑："你修改了gate逻辑，但没证明修正前后结论的稳定性"

**建议**:
1. 立即实现Section 6的敏感性分析
2. 生成对比表（见下面示例）
3. 演示P0-1修正的必要性

---

## ⚠️ Medium Priority Issues

### M1. **统计检验全部缺失**

**现状**: visualize_output.ipynb的所有TODO单元格都只是框架，没有统计代码

**建议**: 每个Figure都要包含：
```python
from scipy.stats import mannwhitneyu
from scipy.stats import spearmanr

# Example: Manual vs Semi的active_time对比
manual_time = df_main[df_main['condition_clean'] == 'manual']['active_time'].dropna()
semi_time = df_main[df_main['condition_clean'] == 'semi']['active_time'].dropna()

stat, pval = mannwhitneyu(manual_time, semi_time, alternative='two-sided')
effect_size = (manual_time.median() - semi_time.median()) / manual_time.std()

print(f"Manual vs Semi: U={stat:.0f}, p={pval:.4f}, Cohen's d={effect_size:.3f}")
```

---

### M2. **分层表（Table A/B）仍未实现**

**论文要求**: Section 7需要生成：
- **Table A**: 按|Δn_pairs|分层（Δn=0, ±1, ±2, >2）
- **Table B**: 按difficulty/model_issue分层

**现状**: visualize_output.ipynb有说明但没代码

**建议**: 立即补充代码
```python
# Section 7: Stratification Tables

# Table A: 按Δn_pairs分层
df_inscope['delta_n_pairs'] = abs(df_inscope['pred_n_pairs'] - df_inscope['ann_n_pairs'])
bins = [-0.1, 0.1, 1.1, 2.1, np.inf]
labels = ['Δn=0', 'Δn=±1', 'Δn=±2', 'Δn>2']
df_inscope['delta_bin'] = pd.cut(df_inscope['delta_n_pairs'], bins=bins, labels=labels)

table_a = df_inscope.groupby('delta_bin').agg({
    'task_id': 'count',
    'layout_used_clean': 'mean',
    'layout_2d_iou': 'mean',
    'active_time': 'median'
}).rename(columns={'task_id': 'N', 'layout_used_clean': 'Coverage', ...})
```

---

## 📋 对比修复前后的完成度

| 功能 | 修复前 | 修复后 | 目标 | 完成度 |
|------|-------|--------|------|--------|
| **Notebook结构** | 混乱(10-20%) | 清晰，按RQ组织(70%) | 100% | 70% |
| **Section 0-1** | 混在一起 | 分离清晰 | 100% | 95% ✅ |
| **Section 2（透明披露）** | 文本报告 | 有框架 | 100% | 40% |
| **Section 3（RQ1效率）** | 框架缺 | 有框架 | 100% | 50% |
| **Section 4（RQ2质量）** | 完全空 | 有标题 | 100% | 10% ❌ |
| **Section 5（RQ3专家）** | 完全空 | 完全空 | 100% | 0% ❌ |
| **Section 6（敏感性）** | 无 | 框架说明 | 100% | 20% |
| **Section 7（分层表）** | 无 | 框架说明 | 100% | 15% |
| **诊断工具** | 无 | 有diagnose_gating_bias.py | 100% | 90% ✅ |
| **统计检验** | 无 | 无 | 100% | 0% ❌ |

**整体进度**: 修复前 ~25% → 修复后 ~35%（⬆️ +10%）

---

## ✅ 评价：改进的方向是对的，但需要加速补齐核心内容

### 改进做得好的地方：

1. ✅ **CONFIG集中管理** - 解决了硬编码路径问题
2. ✅ **Section标题清晰** - 论文逻辑现在一目了然
3. ✅ **诊断工具独立** - diagnose_gating_bias.py可以单独复现
4. ✅ **框架完整** - 所有Section都有Markdown说明

### 需要立即加速的地方：

1. ❌ **RQ2完全空白** - 必须补齐IAA/LOO/可靠性的图表代码
2. ❌ **RQ3完全缺失** - 必须补充$r_u$估计和任务分配对比
3. ❌ **统计检验零** - 所有对比都需要显著性标注
4. ❌ **分层表零** - Table A/B必须生成

---

## 🚀 优先级排序与工作量估计

### P0（必须在投稿前完成）: 3天

1. **补齐RQ2图表** (1天)
   - IAA分布图（1h）
   - LOO共识vs个体（1h）
   - 改动幅度vs质量scatter（2h）
   
2. **实现P0-1敏感性对比** (0.5天)
   - 模拟旧逻辑（0.5h）
   - 对比表生成（1h）
   
3. **生成分层表A/B** (0.5天)
   - Table A（1h）
   - Table B（1h）

4. **补充RQ3框架** (0.5天)
   - $r_u$估计（1h）
   - 关系图（1h）

5. **添加统计检验** (0.5天)
   - Mann-Whitney U + effect size（2h）
   - Spearman相关（1h）

### P1（质量优化）: 1-2天

6. **美化Figure** (0.5天)
   - Publication-quality设置
   - 统一colormap
   - 添加导出

7. **补充RQ3验证集对比** (0.5天)
   - 若有验证集数据

---

## 📝 给开发者的建议

### 立即行动清单：

- [ ] **今天**: 补齐 Section 2 的Figure 2代码（覆盖率+门控原因+mismatch特征）
- [ ] **明天**: 补齐 Section 4 的RQ2图表（IAA/LOO/可靠性）
- [ ] **后天**: 实现 Section 6 的P0-1敏感性对比
- [ ] **第4天**: 添加 Section 7 的分层表
- [ ] **第5-6天**: 补充所有统计检验和美化

### 代码组织建议：

```python
# Section 2: Transparency & Data Hygiene
# ==========================================

## Fig 2: Coverage & Gating Transparency
def plot_fig2_coverage_gating(df_transparent, df_inscope, output_dir):
    """Multi-panel figure展示覆盖率与门控偏差"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Panel A: In-scope覆盖率
    # Panel B: 门控原因分布
    # Panel C: mismatch vs matched耗时对比（这里调用diagnose_gating_bias的逻辑）
    # Panel D: 按condition分层
    
    fig.suptitle('Figure 2: Coverage Rate and Gating Bias Analysis', fontsize=16)
    plt.tight_layout()
    fig.savefig(output_dir / 'fig2_coverage_gating.pdf', dpi=300, bbox_inches='tight')
    return fig

# 在Section 2主单元格中调用
fig2 = plot_fig2_coverage_gating(df_transparent, df_inscope, CONFIG['output_dir'])
```

---

## 总体评价

**修复前的问题**: Notebook混乱，代码结构不清
**修复后的改进**: 结构清晰，但内容仍不完整
**当前状态**: **"框架搭好了，还需填肉"**

**预计审稿人的反应（当前代码）**:
> "好消息是结构清晰了，框架也对。坏消息是RQ2/RQ3还没有结果，统计检验都缺，分层表也没有。建议重新投稿时补齐这些。"

**建议**:
1. 不要被"框架搭好"误导，要立即补齐RQ2/RQ3的**实际代码**
2. 每一行代码都要对应一个论文Figure/Table，没有"完成度60%"的状态
3. 投稿前务必Run All，确保没有错误

---

## 附录：修改前后对比

### 改进1: CONFIG集中管理

```python
# 修改前
CSV_PATH = "../analysis_results/quality_report_20260118.csv"  # 硬编码
plt.rcParams['figure.figsize'] = (10, 6)  # 分散设置

# 修改后
CONFIG = {
    "csv_path": Path("../analysis_results/quality_report_20260118.csv"),
    "random_seed": 42,
    "output_dir": Path("../paper_figures/"),
    "bootstrap_n": 1000,
}
CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
# 集中管理，方便修改和复现
```

### 改进2: Section标题清晰

```python
# 修改前
# 数据清洗（可审计口径）
# 目标：统一字段语义...

# 修改后
# Section 0: Setup & Data Loading
# Section 1: Data Cleaning & Definitions
# Section 2: Transparency & Data Hygiene (Table 1, Fig 1-2)
# Section 3: RQ1 - Efficiency Analysis (Fig 3-4)  
# Section 4: RQ2 - Quality & Reliability (Fig 5-6)
# ...
```

### 改进3: 新增诊断工具

```python
# diagnose_gating_bias.py (新增)
# - 快速评估Selection Bias风险
# - 风险评分系统 (0-8分)
# - 支持命令行调用

python diagnose_gating_bias.py --csv quality_report.csv
```

---

## 最终建议

**不要停留在"改进框架"阶段，要立即进入"填充内容"阶段。**

核心工作量集中在:
1. RQ2/RQ3的实现（不是框架说明，而是真实代码）
2. 统计检验（每个对比都要显著性标注）
3. 分层表生成（Table A/B）

**目标**: 投稿前所有Figure/Table都能直接从visualize_output.ipynb Run All生成。
