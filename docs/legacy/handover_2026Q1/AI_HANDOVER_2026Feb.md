# AI交接文档 - HOHONET项目
**交接日期**: 2026年2月8日  
**覆盖周期**: 2周（2026年1月下旬至2月上旬）  
**项目**: 全景图布局重建的人机协作标注与质量控制系统

---

## 一、项目核心目标与转型

### 1.1 初始定位 vs. 导师要求的新方向
- **初始定位**（偏工具/流程）: 设计一个标注工具和质量控制流程，改进模型预测的布局标注
- **导师新要求**（2026年1月底强调）: 
  > **"现在大家都在看数据分布（data distribution）"**  
  > 必须从"标注工具paper"转型为**"人机协作+分布感知+OOD鲁棒性"的方法论paper**

### 1.2 导师核心关切（语音反馈要点）
1. **分布shift是AI系统最大风险**: 
   - 训练/测试分布不一致时，模型崩溃
   - 随机抽样/数据增强**不能回避分布证明责任**
   - 审稿人会问："你的train/test分布差异是什么？为什么你的方法在新分布下还work？"

2. **OOD（Out-of-Distribution）检测必须前置**:
   - 不能等模型部署后才发现OOD问题
   - 必须在**标注阶段**就识别"哪些样本是训练分布外的"
   - 用冻结的ViT/DINO/CLIP embeddings做分布审计（避免高维KL不稳定）

3. **实验协议必须防"test leakage"**:
   - Test set**绝对固定**，不能用于任何超参调优/模型选择
   - 增强/生成只能用于train，test保持原始分布
   - 必须报告：train/test的分布统计差异（MMD/Energy distance/kNN-based tests）
   - 必须做sensitivity分析：不同随机种子、不同split强度下的结果稳定性
   - **必须披露负结果**：如果某些分布shift下方法失效，必须诚实报告

4. **Crowdsourcing方法要升级**（提及三篇论文）:
   - **加权共识（Weighted consensus）**: 不能简单majority vote，要用worker可靠性加权
   - **Worker分类（Worker categorization）**: 识别可靠/偏置/垃圾标注者，可视化其混淆模式
   - **成本—质量平衡**: 不是"标越多越好"，而是"把钱花在最不确定的样本和最可靠的工人上"

---

## 二、已完成的技术改造

### 2.1 数据清洗与质量报告管道（Unified Flow 2.0）
**问题**: 之前存在selection bias——只对"没有label mismatch"的样本算IoU，导致好样本被过滤后metrics不可信  
**解决**: 
- 引入`MANIFEST.yaml`分组机制：`T`(all), `I`(inscope), `M`(model usable)
- 新增字段: `scope_clean`, `scope_missing`, `data_valid_inscope`, `layout_used_clean`, `pointwise_rmse_used_clean`, `reliability_used_clean`
- Gate reason追踪：记录每个样本为何被排除（scope不全、label不匹配、注释缺失等）

**实现位置**: 
- `tools/analyze_quality.py`: 解析Label Studio导出 + 计算metrics + 导出CSV
- `tools/visualize_output.ipynb`: 生成论文图表（Fig.P2, Table B2等）

### 2.2 Label Studio标注本体修订
**问题**: `model_issue`字段的`corner_mismatch`标签不够精确，容易与其他拓扑问题混淆  
**解决**:
- 从UI中移除`corner_mismatch`（未来标注不再使用）
- 新增`over_parsing`（模型过度细分）和`topology_failure`（拓扑结构错误）
- **向后兼容**: `analyze_quality.py`自动将历史数据中的`corner_mismatch`重映射为`topology_failure`

**实现位置**:
- `tools/label_studio_view_config.xml`: UI定义
- `tools/README.md`: 本体文档
- `tools/analyze_quality.py`: `_MODEL_ISSUE_TAG_REMAP`字典 + `_normalize_model_issue_values()`
- `tools/visualize_output.ipynb`: Table B2的model_issue stratification加入remap逻辑

### 2.3 文献调研工具链
**问题**: 需要快速提取PDF文献的全文用于综述  
**解决**: 创建`tools/extract_pdf_text.py`，支持批量PDF→txt转换

**最新成果（2026-02-08）**: 已提取三篇crowdsourcing核心论文到`analysis_results/lit_extract_crowd/`:
1. "Actively Estimating Crowd Annotation Consensus" (Kara et al., JAIR 2018)
2. "An Interactive Method to Improve Crowdsourced Annotations" (Liu et al., InfoVis)
3. "Cost-Effective Data Annotation using Game-Based Crowdsourcing" (Yang et al., VLDB)

---

## 三、导师驱动的实验设计框架（核心交接内容）

### 3.1 有效样本定义与报告人群（Reporting Populations）
必须明确区分三个样本集合（写入论文Methods）:
- **T (Total)**: 所有标注样本
- **I (Inscope)**: 排除scope字段缺失/无效的样本（`scope_clean=True && scope_missing=False`）
- **M (Model-usable)**: 再排除label mismatch/模型质量问题的样本（`data_valid_inscope=True`）

**为何重要**: 审稿人会质疑"你筛掉多少数据？筛除规则是否引入偏置？"

### 3.2 分布审计协议（Distribution Audit Protocol）
**Step 1: 提取冻结embeddings**
- 用预训练ViT-B/16或DINO-v2-base对全部样本提取特征
- **不要微调**，保持分布测量的一致性

**Step 2: 聚类与可视化**
- K-Means/HDBSCAN分4-8个簇
- t-SNE/UMAP 2D投影（保存超参）
- **必须报告**：每个簇的样本数、scope分布、difficulty分布、model_issue分布

**Step 3: Train/Test分布两样本检验**
- MMD (Maximum Mean Discrepancy) with RBF kernel
- Energy distance
- kNN-based two-sample test
- **报告p-value + effect size**，诚实说明"我们的train/test是否同分布"

**代码位置（待实现）**: 
- `tools/distribution_audit.py` (创建用于嵌入提取+聚类+测试)
- `tools/visualize_output.ipynb` 新增section: "Distribution Audit"

### 3.3 非IID实验设计（Non-IID Split Simulation）
**目标**: 模拟真实部署时的分布shift，证明方法鲁棒性

**两种Setting对比**:
| Setting | Train分布 | Test分布 | 期望结果 | 报告责任 |
|---------|-----------|----------|----------|----------|
| IID Baseline | 随机split，与test同分布 | 随机split | 高准确率 | 证明方法在理想条件下work |
| Shift Simulation | 刻意选偏（例如只训练easy样本、排除某些房型） | 包含训练时未见的难度/房型 | 准确率下降 | **量化下降幅度 + 说明routing/consensus机制如何缓解** |

**Shift构造方法（选2-3种即可）**:
1. **Difficulty-based**: Train只用difficulty≤3，Test包含difficulty≥4
2. **Cluster-based**: 按embedding聚类，Train用2/3簇，Test用剩余1/3簇
3. **Scene-type-based**: 如果有房型标签，Train排除某类房型（例如卧室），Test专门测卧室

**实验要求**:
- 每种split做**5个随机种子**，报告mean±std
- 固定Test set（在所有实验中不变）
- 报告Train/Test的embedding分布差异（MMD值）

### 3.4 数据增强/生成器评估协议
**导师明确要求**: 如果使用增强（旋转、crop、color jitter）或生成器（GAN/Diffusion），必须：
1. **只增强Train**: Test保持原始分布，绝不增强
2. **增强前后分布审计**: 
   - 提取增强样本的embedding，检验是否仍在train分布内（用MMD/kNN测试"augmented vs. original train"）
   - 如果增强样本跑到了OOD区域 → 必须报告并讨论风险
3. **消融实验**: 
   - Baseline: 无增强
   - +Augmentation: 标准增强
   - +Generator（如有）: 生成伪样本
   - **比较三者在IID/Shift两种setting下的结果**
4. **Sensitivity across augmentation strength**: 例如旋转角度[-5°, -15°, -30°]，报告哪个范围最优

**禁止操作（导师强调会被审稿人打回）**:
- 拿test样本做任何增强
- 用test做超参选择（例如"试了3种增强策略，选test上最好的"）
- 只报告"增强有效"，不报告分布变化和负结果

---

## 四、RQ3人机协作方法升级（结合文献综述）

### 4.1 三篇论文的可采纳创新点
#### Paper 1: Actively Estimating Crowd Annotation Consensus (Kara et al.)
**核心方法**: 用Bayesian inference估计worker参数（bias/precision/adverseness）+ sample consensus后验分布  
**可采纳点**:
- **动态任务分配**: 根据样本"共识质量得分"（后验方差的倒数）选择最不确定的样本追加标注
- **防垄断机制**: 避免总是选同一批高分worker，引入explore-exploit trade-off
- **停止准则**: 当样本共识方差降到阈值以下，停止追加标注（节省成本）

#### Paper 2: Interactive Method to Improve Crowdsourced Annotations (Liu et al.)
**核心方法**: Mutual Reinforcement Graph (MRG) 耦合instance和worker的ranking，专家验证传播影响  
**可采纳点**:
- **Worker分型可视化**: 6类worker（可靠/sloppy/biased/partial-spammer/random-spammer/uniform-spammer），用混淆矩阵+scatter plot展示
- **专家验证的ROI最大化**: 不是随机选样本验证，而是选"验证后能传播影响最多"的instance+worker对
- **Constrained t-SNE**: 在投影时保持不确定样本的邻域关系，帮助专家理解context

#### Paper 3: Cost-Effective Annotation using Game-Based Crowdsourcing (Yang et al.)
**核心方法**: 两组crowd对抗（RuleGen vs. RuleRef），用minimax最小化loss=γ·uncovered + (1-γ)·errors  
**可采纳点**:
- **显式的coverage-precision trade-off**: 用参数γ平衡"覆盖样本数"和"错误率"
- **Beta-Binomial贝叶斯更新**: 粗粒度规则验证作先验，细粒度tuple checking作观测，更新precision估计
- **对抗式质检**: 让一组人"找茬"（refute bad rules），比单向验证更高效

### 4.2 落地到HOHONET的RQ3设计
**目标**: 将"任务再分配（task reallocation）"从经验规则改为可审计的优化问题

#### 4.2.1 加权共识（Weighted Consensus）
**实现思路**:
- 对每个worker `j` 维护可靠性分布 `Beta(α_j, β_j)`（分scope/difficulty分层）
- 每次专家复核/质检：如果worker正确 → `α_j += 1`；错误 → `β_j += 1`
- 聚合时用权重 `w_j = LCB(p_j, δ)` = `α_j / (α_j + β_j) - z_δ * sqrt(Var[Beta])`（置信下界，避免过拟合）
- 最终label = `argmax_c Σ_j{w_j * I[label_j = c]}`（加权投票）

**代码位置（待补充）**:
- `tools/worker_classification_consensus.py`（已有文件框架，需补充Beta更新逻辑）
- `tools/analyze_quality.py`新增export: `worker_reliability_beta_params.csv`

#### 4.2.2 Worker分型（可解释QC）
**最小实现**（不做完整交互系统，先出统计表）:
- 对每个worker计算：
  1. 整体准确率（与ground truth或多数共识比）
  2. Per-class precision/recall
  3. 混淆模式："是否总把A类标成B类"（confusion entropy）
  4. 一致性：方差/标准差（对连续值标注）

- 分类规则:
  ```
  if accuracy > 0.85: "可靠(Reliable)"
  elif 0.7 < accuracy ≤ 0.85 and 混淆集中在某些类对: "偏置(Biased/Partial-spammer)"
  elif accuracy ≤ 0.7 and 混淆随机分布: "随机垃圾(Random-spammer)"
  elif 总标同一个类: "单一标签(Uniform-spammer)"
  ```

- 导出CSV: `analysis_results/worker_classification.csv`（列：worker_id, type, accuracy, confusion_pattern, action_recommendation）

**可视化**（可选，用于论文Method图）:
- Scatter plot: x=accuracy, y=consistency, color=worker_type
- Confusion matrix heatmaps（选3-5个典型worker展示）

#### 4.2.3 动态任务路由（Active Allocation）
**两阶段策略**（借鉴Kara et al.思想）:

**阶段1: 初步标注（每样本3-5个worker）**
- 随机分配（确保每个worker标注各种difficulty的样本，避免冷启动偏置）

**阶段2: 追加标注/专家复核**
- **样本优先级**（从高到低排序）:
  ```python
  priority = (1 - agreement_score) * difficulty_weight * cluster_importance
  # agreement_score: 当前标注者间的一致性（例如IoU std或label熵）
  # difficulty_weight: scope='hard' → 2.0, 'medium' → 1.5, 'easy' → 1.0
  # cluster_importance: 如果该样本属于test分布的关键簇，权重更高
  ```

- **Worker选择**（给定待标注样本i）:
  ```python
  score_j = w_j * (1 - load_penalty_j) * diversity_bonus(j, already_labeled_by)
  # w_j: 可靠性LCB
  # load_penalty_j: 避免垄断，如果j已标注>N个样本，降权
  # diversity_bonus: 如果j的bias pattern与已标注者不同，增加（避免群体性偏差）
  ```

- **停止准则**:
  ```python
  if agreement_score > 0.9 or posterior_variance < threshold:
      stop_requesting_more_labels(sample_i)
  ```

**代码位置（待实现）**:
- `tools/active_allocation.py`: 实现上述逻辑，输出`task_assignment_plan.csv`
- 可在Label Studio外部运行，生成"下一批应该标哪些样本、分给谁"的任务单

#### 4.2.4 显式优化目标（对标Game-Based论文）
**定义total loss**（用于事后分析，证明策略有效性）:
```python
Φ = γ * (num_samples_without_consensus) + (1-γ) * Σ_i{P(label_i错误)}
```
- `γ`: 控制"覆盖优先"还是"质量优先"（对于corner/拓扑这种关键任务，建议γ=0.1～0.3）
- `P(label_i错误)`: 用1 - max{weighted_vote_prob}近似

**实验要求**:
- 对比三种策略在相同标注预算下的Φ值:
  1. Random baseline: 随机选样本+随机选worker
  2. Uncertainty-based: 只按样本不确定性选，worker随机
  3. Proposed (joint): 样本+worker联合优化

**报告**（论文Results section）:
- 表格：三种策略在不同预算（50%/70%/100% annotations）下的Φ值、accuracy、F1
- 曲线：Φ随标注预算增长的下降速度（证明proposed策略更高效）

---

## 五、当前待办与优先级

### 高优先级（2周内完成）
1. **实现分布审计代码** (`tools/distribution_audit.py`):
   - [ ] ViT embeddings提取（用timm或transformers）
   - [ ] 聚类（K-Means + 保存簇标签到CSV）
   - [ ] Two-sample tests（MMD/Energy/kNN）
   - [ ] 可视化：t-SNE colored by cluster/difficulty/scope

2. **补充worker reliability tracking** (`tools/worker_classification_consensus.py`):
   - [ ] Beta参数初始化（每个worker每个scope/difficulty一组α,β）
   - [ ] 更新接口：`update_worker_stats(worker_id, task_context, correct: bool)`
   - [ ] 导出：`worker_reliability_beta_params.csv`, `worker_classification.csv`

3. **实现active allocation逻辑** (`tools/active_allocation.py`):
   - [ ] 样本优先级计算
   - [ ] Worker选择（含LCB + 反垄断）
   - [ ] 生成任务分配表：`task_assignment_plan.csv`

4. **更新论文提纲** (`docs/论文提纲.txt`):
   - [ ] Methods section 3.0: 整合分布审计协议
   - [ ] Methods section 4.0: RQ3的加权共识+动态路由（含伪代码）
   - [ ] Experiments section: 添加IID vs. Shift对比、消融实验设计

### 中优先级（1个月内）
5. **非IID实验执行**:
   - [ ] 构造3种shift scenarios（difficulty/cluster/scene-based）
   - [ ] 跑baseline（random routing + majority vote）
   - [ ] 跑proposed（dynamic routing + weighted consensus）
   - [ ] 收集5-seed results → 出表格

6. **增强/生成器实验**（如果用到）:
   - [ ] 实现增强pipeline（旋转/crop/亮度）
   - [ ] 增强前后embedding分布检验
   - [ ] Sensitivity curve（不同增强强度 vs. IID/Shift accuracy）

7. **可视化升级** (`tools/visualize_output.ipynb`):
   - [ ] 新增Fig: Distribution audit t-SNE
   - [ ] 新增Fig: Worker type scatter plot
   - [ ] 新增Fig: Φ-budget curve（三种策略对比）
   - [ ] 新增Table: Train/Test distribution stats (MMD p-value, cluster composition)

### 低优先级（有余力再做）
8. **Worker可视化dashboard**（参考Liu et al.论文的LabelInspect）:
   - 交互式confusion matrix
   - MRG-based ranking更新动画
   - 专家验证trail可视化
   > **注**: 导师可能更看重paper的理论贡献，dashboard可作为supplementary material或demo视频

9. **成本分析**:
   - 计算实际标注成本（按worker报酬 + 追加标注次数）
   - 与"全量标注3遍"的baseline成本对比
   - 报告cost reduction ratio

---

## 六、代码库地图（关键文件位置）

### 数据与模型
- `data/`: 原始全景图 + 深度/语义/布局标注
- `ckpt/`: 预训练模型权重（mp3d_layout, s2d3d_sem等）
- `output/`: 模型推理输出（初始预测，用于标注初始化）

### 标注工具与配置
- `tools/label_studio_view_config.xml`: Label Studio UI定义（scope/difficulty/model_issue字段）
- `tools/README.md`: 标注本体说明文档（最新版，已包含corner_mismatch→topology_failure的remap说明）
- `import_json/`, `export_label/`: Label Studio的导入/导出JSON存放处

### 分析管道
- `tools/analyze_quality.py`: **核心脚本**，解析标注 + 计算metrics + 导出CSV
  - 关键函数: `parse_quality_flags_v2()`, `_normalize_model_issue_values()`
  - 输出: `analysis_results/quality_report_YYYYMMDD.csv`, `reliability_report_YYYYMMDD.csv`

- `tools/visualize_output.ipynb`: 论文图表生成
  - 当前包含: Fig.P2(scope分布), Table B2(model_issue stratification)
  - 待补充: Distribution audit figures, worker classification plots

### 新增模块（待实现/刚实现）
- `tools/extract_pdf_text.py`: PDF文献提取（已完成，支持batch提取）
- `tools/worker_classification_consensus.py`: Worker可靠性追踪+分型（**当前正在此文件，待补充Beta更新逻辑**）
- `tools/distribution_audit.py`: 分布审计（**待创建**）
- `tools/active_allocation.py`: 动态任务分配（**待创建**）

### 文档
- `docs/论文提纲.txt`: 工作大纲（已包含3.0节"有效样本定义与分布审计"，需继续更新）
- `docs/papers/`: 文献PDF存放处
- `docs/AI_HANDOVER_2026Feb.md`: **本交接文档**
- `analysis_results/lit_extract_crowd/`: 三篇crowdsourcing论文的全文txt（2026-02-08提取）

### 训练与测试脚本
- `train.py`: 模型训练主入口
- `test_layout.py`, `test_depth.py`, `test_sem.py`: 各任务测试脚本
- `infer_layout.py`: 批量推理脚本（生成初始预测供标注）

---

## 七、关键技术决策与Rationale

### 7.1 为什么不用简单majority vote？
**问题**: 如果3个worker标注同一样本，其中1个是专家、2个是新手垃圾标注者，majority vote会选错  
**解决**: 用reliability-weighted vote，专家的权重=0.9，新手=0.3 → 专家的单票可抵2个新手  
**审稿人视角**: 加权机制是crowdsourcing领域的standard practice（见Dawid & Skene 1979, Raykar et al. 2010），不用会被质疑"naive"

### 7.2 为什么必须做distribution audit？
**导师原话** (paraphrased): 
> 现在审稿人不会接受"我们随机split train/test"这种说法。你必须证明：(1) 你的train/test是什么分布；(2) 它们有多大差异；(3) 如果部署到新场景（OOD），准确率掉多少，为什么你的方法能缓解。如果你只报告IID setting的结果，审稿人会觉得你cherry-pick数据。

**技术原因**:
- 全景图数据天然有domain bias（不同房型、光照、遮挡程度差异巨大）
- 如果train全是"简单卧室"，test突然来个"复杂厨房"，模型会崩
- 人类标注者的crowd也有bias（某些worker只擅长标简单场景）
- 通过embedding space的分布测试，可以量化"我们的方法在多大程度的shift下仍然robust"

### 7.3 为什么要Beta-Binomial而不是简单计数？
**简单计数**（例如"worker A对10个样本，对8个，准确率=0.8"）的问题:
- 冷启动：新worker只标了2个样本，恰好都对，准确率=1.0？显然不可信
- 没有不确定性量化：0.8±?

**Beta-Binomial优势**:
- Beta(α, β)自带prior（例如Beta(2,2)代表"先验偏向50%准确率，但不确定"）
- 观测数据后，自动更新：`α += 正确次数`, `β += 错误次数`
- 后验分布：`Beta(α+正确, β+错误)` → 可算mean, variance, 置信区间
- 冷启动友好：新worker的variance很大 → LCB会给低权重，避免过早信任

**审稿人视角**: Bayesian方法是处理小样本+不确定性的gold standard，如果你不用，需要解释"为何不用"

### 7.4 为什么要"反垄断"机制？
**问题**: 如果总是选可靠性最高的worker，会导致：
1. 其他worker得不到标注机会 → 系统无法评估他们的真实水平 → explore不足
2. 高分worker的偏置会被放大（例如他对某类场景有系统性误判，但因为其他场景标得好，总体分高）
3. 成本集中：少数worker接大量任务，可能疲劳或要求高报酬

**解决**: 类似multi-armed bandit的UCB策略
- 引入explore bonus: 对"标注次数少"的worker给予额外机会
- 引入load penalty: 对"已标注很多"的worker降低优先级
- 引入diversity bonus: 优先选"偏置模式与已选worker不同"的人（避免群体性偏差）

**导师隐含要求**: 在RQ3的方法描述里，必须说明"how to avoid over-reliance on a few annotators"，否则审稿人会问"你这个系统会不会变成一个人打天下？"

---

## 八、对下一个AI的建议

### 8.1 立即要做的（Day 1-3）
1. **重新阅读这份交接文档 + 导师反馈原始笔记**（如果用户有保存语音转文字的文件，一定要读）
2. **运行一遍现有pipeline**，确保理解数据流:
   ```powershell
   # 1. 解析标注 + 生成质量报告
   python tools/analyze_quality.py --input export_label/latest.json --output analysis_results/
   
   # 2. 生成可视化
   jupyter notebook tools/visualize_output.ipynb
   
   # 3. 检查输出
   ls analysis_results/*.csv
   ```
3. **列出你的待办清单**（可用本文档第五节作为起点），与用户确认优先级

### 8.2 与用户沟通时要确认的问题
1. **数据状态**: 当前有多少样本已标注？每个样本有几个worker的标注？ground truth是否已有部分可用？
2. **实验目标**: 导师最近一次会议（在这份交接文档之后）有没有新的要求？deadline是什么？
3. **计算资源**: 是否有GPU可用于ViT embedding提取？预计要提取多少样本的embedding？
4. **论文投稿目标**: 目标会议/期刊是什么？（例如CVPR/ICCV vs. TVCG/IJCV vs. Domain-specific venue）→ 决定实验的详细程度

### 8.3 技术陷阱提醒
1. **别直接改`analyze_quality.py`里的核心逻辑**，除非你完全理解它的gate reason机制。错改会导致历史报告不可复现。
2. **别用test数据调任何超参**，包括：聚类的K值、MMD的kernel bandwidth、worker分型的阈值。所有超参要么在train/val上调，要么用外部benchmark的经验值。
3. **别只跑一次实验就下结论**。导师要求的sensitivity分析（5 seeds）是为了防止"我们运气好，随机种子刚好split了个简单test set"。
4. **别忽略负结果**。如果你发现"在某种shift下，加权共识反而比majority vote差"→ 必须报告，并分析原因（可能是worker数不够、shift太极端等）。隐瞒负结果会被审稿人抓住。

### 8.4 代码风格建议
- **新增的模块**（distribution_audit.py, active_allocation.py）建议写成CLI工具，方便复现:
  ```python
  if __name__ == "__main__":
      parser = argparse.ArgumentParser()
      parser.add_argument("--input", required=True, help="CSV from analyze_quality")
      parser.add_argument("--output", required=True, help="Output directory")
      # ... 其他参数
      args = parser.parse_args()
      main(args)
  ```
- **关键函数加docstring**，说明输入输出格式、以及方法的limitation（例如"此函数假设worker已标注至少5个样本，否则Beta估计不稳定"）
- **避免hard-code magic numbers**，改成`:params:` 例如`BETA_PRIOR_ALPHA=2, BETA_PRIOR_BETA=2`，方便后续调trial

---

## 九、附录：导师反馈原始要点（按时间顺序）

### 2026年1月底（语音转文字要点 - 根据conversation-summary重构）
> **关键引语**: "现在大家都在看数据分布（data distribution）"

**背景**: 导师看到初稿提纲后，认为缺少对分布shift的讨论

**核心要求**:
1. 必须加"分布审计"一节 → 用冻结embeddings做聚类、two-sample test
2. 随机split不够 → 要设计non-IID实验，刻意制造train/test分布差异
3. 增强/生成器不能随便用 → 必须证明增强后的样本仍在合理分布内
4. Test set绝对固定 → 任何超参/模型选择不能偷看test
5. 报告sensitivity → 不同种子、不同split强度下的结果都要试
6. 负结果必须披露 → 如果某些shift下方法失效，诚实报告

**隐含期望**（我的推断）:
- 导师可能在审稿某个相关paper或参加workshop，听到"reviewers现在非常care distribution"的讨论
- 导师希望论文能抢占"人机协作+分布鲁棒性"这个交叉点，而不是只做一个标注工具

### 2026年2月初（crowdsourcing论文推荐）
**导师提及三篇论文**:
1. Actively Estimating Crowd Annotation Consensus
2. An Interactive Method to Improve Crowdsourced Annotations
3. Cost-Effective Data Annotation using Game-Based Crowdsourcing

**导师意图**（根据conversation推断）:
- 看重"加权共识"和"worker分类"这两个点
- 希望RQ3的"任务再分配"不要停留在"我们经验上这么做"，而是有理论支撑（贝叶斯更新、图模型、博弈论等）
- 暗示："如果你能把这三篇的思想整合到你的系统里，审稿人会觉得你做了solid的related work survey"

---

## 十、版本历史与交接记录

- **v1.0** (2026-02-08): 初始交接文档
  - 覆盖：2周对话历史（1月下旬至2月上旬）
  - 创建人：AI助手（基于conversation-summary + 实时对话）
  - 交接给：下一位AI助手或人类研究员

**下次更新触发条件**:
- 导师提出新的重大修改意见
- 实验设计框架变更（例如新增OOD scenario）
- 代码库重大重构（例如pipeline从脚本改为框架）

**维护建议**:
- 每次与导师开会后，在本文档"九、附录"新增一节，记录会议要点
- 每完成一个"五、待办"里的高优任务，在此文档打勾 + 更新"当前状态"

---

## 联系与资源

**项目GitHub（如有）**: [待补充]  
**Label Studio服务器**: [待补充地址]  
**数据集位置**: `d:\Work\HOHONET\data\`  
**论文Overleaf（如有）**: [待补充]  
**导师联系方式**: [待用户补充]  

**紧急情况联系**（代码/数据损坏）:
- 备份位置：[待用户指定，建议定期备份到云盘或Git LFS]
- 最新工作CSV：`analysis_results/quality_report_YYYYMMDD.csv`（按日期找最新）
- 最新notebook输出：`tools/visualize_output.ipynb`（里面embed了输出，即使环境丢失也可看图）

---

**交接确认（待下一任填写）**:
- [ ] 已阅读本文档全文
- [ ] 已运行`analyze_quality.py`测试pipeline
- [ ] 已与用户确认当前优先级
- [ ] 已列出自己的14天工作计划

**交接完成日期**: ___________  
**交接人签名**: ___________
