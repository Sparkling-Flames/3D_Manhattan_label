# 严苛审稿意见：论文提纲 vs Notebook实现的差距分析

> **审稿人视角**: Top-tier HCI/CV venue (CHI/CVPR/ICCV level)  
> **评审标准**: Reproducibility, Statistical Rigor, Transparency, Contribution Clarity  
> **日期**: 2026-01-20

---

## 🔴 Major Issues (必须修复才能接受)

### M1. **RQ与可视化代码的映射不完整** (Validity Threat)

**问题**: 论文提纲定义了3个RQ，但notebook中：
- ✅ RQ1 (效率)：有 Manual vs Semi 的 active_time 对比框架
- ⚠️ RQ2 (质量/可靠性)：**只有数据结构定义（df_rel），没有实际可视化代码**
- ❌ RQ3 (任务分配)：**完全缺失**，没有 $r_u$ 估计、分配策略对比、验证集分析

**后果**: 
- 审稿人会质疑："你说要回答RQ2/RQ3，但Figure在哪里？统计检验在哪里？"
- 当前notebook只能支撑RQ1，其余是"承诺但未实现"

**建议**:
1. **立即补充**：
   - RQ2图表：IAA分布、LOO共识vs个体、可靠性分层（按annotator/task）
   - RQ3图表：$r_u$ 估计+CI、分配策略前后对比（效率/一致性）、专家识别可视化
2. 每个图都要有**统计显著性检验**（Mann-Whitney U / Wilcoxon / Bootstrap CI），不能只画分布

---

### M2. **门控透明性披露不符合论文要求** (Reporting Bias)

**问题**: 论文提纲第4节明确要求"**固定输出**"：
- ✅ 覆盖率两口径（overall + in-scope）
- ✅ 失败原因分布
- ❌ **分层表A/B缺失**：按 $|\Delta n_{pairs}|$ 和 difficulty/model_issue 分层
- ❌ **门控敏感性对比缺失**：P0-1前后的覆盖率/结论稳定性对比

**当前状态**: 图0只有文本统计，没有Panel A/B/C/D的多面板Figure，也没有P0-1敏感性分析的对照表

**后果**: 
- 审稿人会说："你提出了P0-1修正，但没证明修正前后结论是否稳定"
- Selection bias的缓解效果无法量化

**建议**:
1. **必须做**: 按论文Section 3.7的要求，在同一批数据上跑两遍：
   - 旧逻辑（保留n_pairs_mismatch gate）
   - P0-1逻辑（移除gate）
   - 对比表格：覆盖率、RQ1/RQ2结论是否变化
2. **分层表**: 至少生成Table A和Table B（见论文第4节），不能只口头描述

---

### M3. **"改动幅度 vs 质量"的循环性未解决** (Circularity)

**问题**: 论文提纲2.2节定义了 $\mathrm{IoU}_{edit}$（改动幅度），但：
- Notebook中 **没有明确分离** 改动幅度指标 vs 质量指标
- 缺少"改动大 ≠ 质量差"的证据图（例如：改动大但与LOO共识一致的案例）

**当前风险**: 审稿人会质疑：
> "你用IoU_edit来衡量工作量，又用IoU_to_consensus来衡量质量，这两个IoU有什么本质区别？会不会只是换个名字？"

**建议**:
1. **必须画图**: scatter plot，x=IoU_edit（改动幅度），y=IoU_to_consensus_loo（质量）
   - 展示两者**不是简单线性关系**（说明改动≠质量）
   - 标注"高改动+高质量"的象限（证明大改动≠低质量）
2. 在Method部分增加一段："为什么改动幅度和质量可以分离"的理论/实证论证

---

### M4. **Baseline缺失导致贡献不清晰** (Contribution)

**问题**: 论文声称贡献包括"透明门控"和"结构差异作为信号"，但：
- **没有Baseline对比**: 如果用传统方法（只报layout_used=True的样本，不分层），结论会如何？
- **没有消融**: 如果不做Δn分层，只看overall均值，RQ1的省时效果是否仍显著？

**后果**: 审稿人会说：
> "你的方法听起来复杂，但有没有证据表明这些复杂性是必要的？能不能ablation study？"

**建议**:
1. **添加对照组**: 
   - Baseline 1: 只用layout_used=True样本，不分层
   - Baseline 2: 按Δn=0 vs Δn>0简单二分，不细分
   - Proposed: 你的4层分层方案
   - 对比表格：覆盖率、效率差异、显著性水平
2. 在Discussion里说明："不分层会导致XXX偏差，分层后发现YYY规律"

---

## ⚠️ Minor Issues (建议修复但不致命)

### m1. **Notebook结构混乱，论文逻辑不清晰**

**问题**: 当前notebook的单元格顺序：
1. 重要更新说明（P0-1）
2. 导入库
3. 数据加载
4. 数据清洗（巨大函数，230行）
5. 图0：覆盖率报告
6. 图表清单说明
7. TODO标记的空白单元格（图1-10）

**审稿人感受**: 
- "这是个工程日志，不是论文支撑代码"
- "我找不到RQ2/RQ3的实现"
- "为什么清洗函数在最前面占200行，图表代码却是TODO？"

**建议重新组织** (见下面的详细方案):
1. Section 0: Setup + 数据加载
2. Section 1: 数据清洗与口径定义
3. **Section 2: 透明披露（Table 1, Fig 1-2）**
4. **Section 3: RQ1分析（Fig 3-4）**
5. **Section 4: RQ2分析（Fig 5-6）**
6. **Section 5: RQ3分析（Fig 7-8）**
7. Section 6: 敏感性分析（P0-1对比）
8. Appendix: 诊断图

---

### m2. **统计检验缺失**

**问题**: 当前代码只计算中位数/均值，**没有显著性检验**

**建议**: 每个对比（Manual vs Semi、按Δn分层）都要报告：
- Mann-Whitney U test (非参数)
- Effect size (Cohen's d / Cliff's Delta)
- Bootstrap 95% CI

在图中用星号标注显著性：\*, \*\*, \*\*\* (p<0.05/0.01/0.001)

---

### m3. **Figure质量低，无法直接用于论文**

**问题**: 当前图0是纯文本输出，不是Figure

**建议**: 
- 每个Figure都要用matplotlib/seaborn生成publication-quality图
- 统一风格：colormap、字号、legend位置
- 提供导出功能：`plt.savefig('fig2_coverage.pdf', dpi=300, bbox_inches='tight')`

---

### m4. **代码可复现性不足**

**问题**: 
- CSV路径硬编码（`CSV_PATH = "../analysis_results/quality_report_20260118.csv"`）
- 没有随机种子设置（bootstrap时需要）
- 缺少依赖版本说明

**建议**:
1. 添加配置单元格：
```python
CONFIG = {
    'csv_path': Path('../analysis_results/quality_report_20260118.csv'),
    'random_seed': 42,
    'output_dir': Path('../paper_figures/'),
    'bootstrap_n': 1000
}
np.random.seed(CONFIG['random_seed'])
```

2. 添加环境说明单元格（Python版本、关键库版本）

---

## 📊 论文提纲 vs Notebook的覆盖度矩阵

| 论文章节 | 提纲要求 | Notebook状态 | 缺失 |
|---------|---------|-------------|------|
| **2.1 标注对象** | scope/difficulty/model_issue定义 | ✅ 清洗函数已实现 | - |
| **2.2 改动幅度** | IoU_edit, BoundaryRMSE, CornerRMSE | ⚠️ 只有口径，没有可视化 | Figure缺失 |
| **2.3 质量/可靠性** | IAA, LOO, $r_u$ | ⚠️ df_rel定义，但无图表 | **RQ2全部图表** |
| **2.4 结构差异** | Δn_pairs分层 | ❌ 未实现 | **分层表A** |
| **3.3 实验设计** | 5组数据划分说明 | ❌ 未提及 | 数据来源说明 |
| **3.4 RQ1** | Manual vs Semi效率对比 | ⚠️ 框架有，图缺失 | Figure 3-4 |
| **3.5 RQ2** | IAA/LOO分布，反例筛选 | ❌ 未实现 | **RQ2全部** |
| **3.6 RQ3** | $r_u$估计，分配策略对比 | ❌ 未实现 | **RQ3全部** |
| **3.7 敏感性** | P0-1前后对比 | ❌ 未实现 | **Table对比** |
| **4 透明披露** | 覆盖率+分层表A/B | ⚠️ 只有图0文本统计 | 分层表、Figure |

**当前完成度**: ~35%（主要是数据清洗+图0框架）  
**To Acceptance需要**: 至少补齐RQ2/RQ3的核心图表，以及P0-1敏感性对比

---

## 🎯 最低可接受标准（To Pass Review）

### 必须添加的Figure/Table：

1. ✅ **Table 1**: 字段缺失率（已有框架，需完成）
2. ⚠️ **Figure 1**: Scope/OOS分布（TODO，需实现）
3. ⚠️ **Figure 2**: 覆盖率+门控原因（已有文本，需改成多Panel图）
4. ❌ **Figure 3**: Manual vs Semi active_time分布（需实现）
5. ❌ **Figure 4**: active_time vs 改动幅度/Δn（需实现）
6. ❌ **Figure 5A/B**: IAA分布 + LOO vs 个体（需实现）
7. ❌ **Table A**: 按Δn分层的覆盖率/改动/耗时（需实现）
8. ❌ **Table B**: 按difficulty分层的效率/一致性（需实现）
9. ❌ **Sensitivity Table**: P0-1前后对比（需实现）

### 必须添加的统计检验：

- Manual vs Semi: Mann-Whitney U + effect size
- 分层对比: Kruskal-Wallis + post-hoc
- Bootstrap CI: $r_u$, IAA中位数
- Correlation: active_time vs Δn (Spearman r)

---

## 💡 具体修复建议

### 建议1: 重新组织Notebook结构（详见下个文档）

**优先级**: P0  
**工作量**: 2-3小时（移动单元格+补充框架）

### 建议2: 补齐RQ2/RQ3的核心分析

**优先级**: P0  
**工作量**: 1-2天（需写新代码）

### 建议3: 生成publication-quality Figure

**优先级**: P1  
**工作量**: 0.5天（美化+导出）

### 建议4: 添加统计检验与显著性标注

**优先级**: P1  
**工作量**: 0.5天

---

## 📝 审稿人最可能的Rejection理由（如果不修复）

1. **"RQ2/RQ3没有充分evidence支撑"** (Major)
   - 原因：缺少IAA/LOO/分配策略的图表和统计检验

2. **"P0-1修正的必要性没有证明"** (Major)
   - 原因：没有敏感性分析对比修正前后

3. **"改动幅度vs质量的循环性没解决"** (Major)
   - 原因：没有scatter plot证明两者可分离

4. **"实验设计描述不清晰"** (Minor)
   - 原因：notebook里没提数据来源、参与者分组

5. **"代码可复现性差"** (Minor)
   - 原因：硬编码路径、缺随机种子、无环境说明

---

## ✅ 如果全部修复，预期评分

- **Contribution**: Strong (透明披露+分层策略+任务分配，有实证支撑)
- **Reproducibility**: Strong (代码+数据+统计检验完整)
- **Presentation**: Good (Figure清晰，统计严谨)
- **Overall**: **Accept** (可能需要minor revision补充Discussion)

---

## 🔥 最严苛的问题（Deep Review会问的）

1. **"为什么校准集只用Manual？会不会低估Semi条件下的$r_u$偏移？"**
   - 需要在Discussion里说明：工具效应污染 vs 真实能力的权衡

2. **"Δn分层是post-hoc的，会不会p-hacking？"**
   - 需要说明：分层策略是pre-registered的，或者在验证集上复现

3. **"LOO共识的medoid选择在n=2时退化，这部分数据怎么处理？"**
   - 需要在Method里说明：n=2时单独报告，或者排除

4. **"标注者之间如果有学习效应（例如看到别人的结果），LOO还有效吗？"**
   - 需要在Limitation里说明：独立标注的保证，以及潜在交互

---

## 总结

**当前状态**: Notebook是个"工程雏形"，距离"论文级分析"还有较大差距  
**核心问题**: RQ2/RQ3未实现，P0-1敏感性未验证，统计检验缺失  
**修复路径**: 按优先级补齐Figure → 添加统计检验 → 重新组织结构 → 美化图表  
**预计工作量**: 2-3天（如果全职做）

**建议**: 先做"最小可接受集"（RQ2的IAA图 + P0-1对比表），确保论文核心claim有支撑，再考虑美化。
