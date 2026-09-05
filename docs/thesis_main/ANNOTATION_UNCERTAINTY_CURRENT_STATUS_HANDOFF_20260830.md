# 标注不确定性研究：当前状态与后续实验交接（2026-08-30）

> **状态：DRAFT / NON-NORMATIVE / NOT APPROVED**  
> 本文用于交接当前证据、候选实验和沟通歧义，不是正式协议、统计计划或启动授权。规范方法唯一真源仍是 `PAPER_A_METHOD_CONTRACT_CURRENT.json`；任何新增实验均须另行冻结研究合同、统计计划、任务/reference、assignment 和启动审批。

## 0. 一页结论

- 当前最可靠的新证据来自 42 张历史高密度手工标注图：26 名标注者、1,055 条规范标注，每图已有 23–26 条，并不是“每图不足 20 条”。
- 图上的 `k=20` 是在现有 23–26 条历史标注中无放回重采样得到的实测 roster 内结果，不是外推，也不代表后续必须补到 20 人。
- 41/42 图具备可计算 reference；C1 的 12 图作为主分析，P1 的 29 图作为敏感性分析，不能把两类 reference 无差别合并解释。
- 当前可以量化噪声恢复、整体分歧、任务分布关联和少数结构检出；不能宣称“12–15 人已经达到普适质量上限”。
- 现有沟通更可能是在要求：先不开发新自动化，选一小批任务，在严格条件下做多人独立标注和/或多人复核，量化噪声及经验饱和；并未明确要求把历史 42 图机械补到 20 人。
- 下一步最小候选路径应先做独立盲标的人数曲线；多人复核作为单独第二阶段。Wrong/Correct proposal、元标签和角点顺序残差可以后置，不应成为本轮跑通流程的启动前提。

## 1. 当前正式边界

- 正式执行链仍为 `Pilot -> PreScreen(P1) -> Calibration(C1 + C2-B + C2-A-RP) -> Main(T1 + V1)`。
- 当前方法合同版本为 `paper_a_method_20260811_v23`，`formal_launch_default=false`。
- 本交接不修改已关闭的 C2-B/C2-A-RP、C1 原始 export/assignment、T1/V1 设计、worker state、routing、active-time 或 reference 规则。
- `export_label/`、`import_json/`、`active_logs/` 仍分别是运行时标注、planned import/split 和原始 active-time 真源；`analysis_results/` 只是派生输出。
- 讨论稿中的 `24×3×4`、三臂 `Manual / Correct-Semi / Wrong-Semi`、元标签和残差都没有获批或冻结。

## 2. 当前数据与结果

### 2.1 数据地图

| 数据层 | 当前规模 | 当前用途 | 关键限制 |
|---|---:|---|---|
| 历史高密度 Manual | 42 图、26 人、1,055 条规范标注；每图 23–26 条 | 噪声恢复、整体分歧、少数结构、历史聚合曲线 | 有限历史 roster，不保证新工人人群 |
| reference-ready 子集 | 41 图 | 相对 reference 的 GT-blind 聚合质量 | C1 12 图主分析；P1 29 图仅敏感性 |
| C1 core 低密度 Manual | 75 图、约 `k=5–7` | 更广任务分布或未来补标候选 | 不是当前 42 图高密度池 |
| 全阶段中性底座 | 2,501 条 canonical | 跨阶段 provenance、geometry/meta/proposal/time 审计 | 阶段和条件异质，不能当同质实验 |
| 当前候选审核记录 | 36 图人工口径：18 PASS、6 REVISE、12 REJECT | 候选刺激物审核 | `14 clean + 4 pending` 尚未完整机器物化，未冻结、未分发 |

如果后续沟通中再次出现“原来不足 20 人的图”，必须先确认指的是 42 图高密度池还是 75 图 C1 core。前者已经超过 20；后者才可能存在追加独立标注的含义。

### 2.2 已完成的主要分析

当前统一入口：`analysis_results/historical_uncertainty_recompute_20260829_v1/`。

| 问题 | 当前结果 | 解释边界 |
|---|---|---|
| `k=20` 是否外推 | 否；来自现有标注的无放回重采样 | 不是 41 图共同 reference 质量点 |
| 12–15 人是否平台 | 无 reference 恢复率从 12 到 15 增加 0.0660，95% building-bootstrap CI `[0.0370, 0.0960]` | reference 共同支持只到 `k=13`；未冻结 SESOI，不能作等效/平台声明 |
| reference 质量 | 12→13 两端均可交付时几何质量变化约 `-0.00012`，区间跨 0 | 只能描述当前历史样本，不能推出普适上限 |
| 任务分布影响 | full-mask 分歧与 `k=15` 恢复率 Spearman `rho≈-0.777`；与 12→15 增益 `rho≈0.749` | 同一批答案导出的描述性关联，不是因果 |
| 整体分歧 | 已按 42 任务等权报告 mask、boundary、wall、角点数差异和无效提交 | 不合成难解释的单一总分 |
| 结构状态 | 阈值 0.95：2 unimodal、14 dominant-with-dissent、21 supported-multimodal、5 not-evaluable | 3/21 多模态任务存在排序并列，必须报告敏感性 |
| 少数结构 | `k=12` 支持可见约 0.642、同一第二模式恢复约 0.614；`k=20` 分别约 0.908、0.885 | “第二模式”是有限 roster 内确定性排序，不是外部真值 |
| 中英文 | 合并差约 0.0025、区间跨 0，且 P1/C1 方向相反 | 不作为主分层，只保留项目/语言敏感性 |

### 2.3 当前不能支持的结论

- 不能写“12–15 人后再增加人数无法显著提高质量”。
- 不能写“20 人是外推值”或“需要把每图补到 20 人”。
- 不能把恢复有限 roster 的统计量写成普适人类质量上限。
- 不能从历史 Manual/Semi 观察差异识别 proposal 的因果效应。
- 不能把 3D preview 方正度或低内部残差等同于外部边界正确。
- 不能把第二排序几何模式直接称作第二真值或少数正确答案。
- 不能把候选审核的人工口头数字写成已经冻结的机器任务清单。

## 3. 对现有沟通反馈的稳妥解释

### 3.1 可以确认的意思

现有反馈明确强调了以下方向：

1. 暂不以开发半自动标注工具为前提，先把人工流程跑通；
2. 可以让多个学生参与标注或复核；
3. 可以先把实验条件限制得更严格；
4. 重点是多轮数据能否量化噪声和标注质量的经验边界；
5. 先验证理论和流程，再决定是否放宽条件或增加自动化。

### 3.2 当前最合理的推断

更可能的目标是一个受控的多人重复测量/复核实验，而不是简单补齐历史人数。最接近该目标的执行结构是：

```text
固定小任务集
  -> 多名学生独立盲标，形成 k 人数曲线
  -> 可选：由不同学生对候选结果做独立盲复核，形成轮次曲线
  -> 比较噪声、聚合稳定、相对 reference 质量和少数结构检出
```

“增加独立标注者”和“看过已有答案后复核”测量的不是同一件事，不能混在同一条 `k` 曲线中。前者主要回答冗余与经验饱和；后者主要回答复核流程能否修正错误。

### 3.3 仍需确认的歧义

1. “多轮”指不断增加不同学生，还是同一结果被多轮复核？
2. 学生需要独立从零标注，还是可以看到上一轮答案后修改？
3. “自动标注和手动标注”是需要比较的实验条件，还是只作为供学生复核的候选结果？
4. 后续使用历史 42 图、低密度 C1 core 75 图，还是重新选一小批未暴露图？
5. 目标是恢复分歧统计、稳定聚合输出，还是估计相对外部 reference 的质量？
6. 是否先只做 Manual 多人重复，待流程成立后再增加 Wrong/Correct proposal 和元标签？
7. “模拟/演出来”应只理解为模拟流程、严格角色和预设刺激；合成/脚本数据必须单列并机器排除，不能冒充真实人工观察。

建议下次沟通直接确认：

> 当前理解是先选一小批任务，在固定条件下增加不同学生的独立标注，并可另做多人复核，分别观察人数和轮次增加后的噪声、聚合稳定性与相对 reference 质量。这里的“多轮”主要指增加不同标注者，还是同一结果经过多轮复核？历史 42 图已经每图 23–26 条，您希望继续利用这批历史数据，还是对 C1 core/新图做小规模前瞻补标？

## 4. 后续实验的最小候选路径

### 4.1 目标

优先回答一个基础问题：在严格、可复现的手工条件下，随着独立标注人数增加，噪声统计、聚合输出和相对 reference 质量如何变化，少数结构何时能够被观察与恢复。

没有预先冻结的 SESOI、精度目标和充分共同支持时，使用“经验饱和”“边际收益”或“当前任务集的经验边界”，不用“普适质量上限”。

### 4.2 第一阶段：独立盲标

- 从低、中、高分歧以及有/无受支持少数结构的任务中选一个很小的分层集合；不先写死 24、72 或每图 20 人。
- 冻结每图 reference、allowed answer set、结构有效规则、聚合器、`k` 检查节点、最大预算和停止规则。
- 使用现有 Manual 流程，不开发新自动化；标注者看不到旧答案、聚合结果或 reference。
- 原始提交全部保留；不因方向不理想、结果不显著或中途曲线变化而换图、换指标或临时加人。
- 历史与新增记录只有在界面、任务说明、initialization、字段和独立性可比时才合并；否则按 cohort 分层报告。

### 4.3 第二阶段：多人盲复核（可选）

- 只在第一阶段流程跑通后添加；不与独立标注人数混为同一个 estimand。
- 将 Manual、模型输出或聚合候选随机、盲化呈现给 reviewer。
- 保留每位 reviewer 的原始判断、是否修改、修复类型和最终结果。
- 比较每轮复核后的错误修复、引入新错误、非交付和成本；不能只报告“平均 IoU 上升”。

### 4.4 最小输出与停止依据

最小输出：

- task-equal pairwise geometry disagreement；
- corner-count/结构模式多样性检出；
- 新增一人后聚合结果改变概率；
- GT-blind aggregate quality `Q(k)`；
- delivery/结构无效单列；
- 少数模式支持可见率和同一模式恢复率；
- task/building clustered bootstrap interval。

启动前必须冻结：

- primary estimand 与分析单位；
- SESOI 或精度目标；
- `k` 节点、最大人数/预算和停止规则；
- reference 与 allowed-answer-set 版本；
- 聚合算法及 tie/not-evaluable 规则；
- 技术/行政失败处理；
- 排演、合成和正式记录的机器隔离字段。

### 4.5 与三臂/元标签候选方案的关系

`ANNOTATION_UNCERTAINTY_EXPERIMENT_SUPERVISOR_DRAFT_v2.md` 仍是另一个候选方向：它更适合回答 Wrong/Correct proposal 干预、纠错机制和元标签增量诊断，不直接等同于“多人多轮量化噪声与经验饱和”。

建议顺序是：

```text
严格 Manual 多人重复测量
  -> 可选多人盲复核
  -> 再决定是否加入 Correct/Wrong proposal
  -> 元标签与角点顺序/残差作为机制或诊断扩展
```

## 5. 避免重蹈旧实验失败的约束

- 描述性分歧、因果干预和预测性诊断必须拆开，不让一套数据同时承担三个无法识别的结论。
- 同图和同 building 的相关性必须进入设计/推断，不能把每条 annotation 当独立样本。
- 任务、reference、允许答案、聚合器、失败处理和停止规则必须在 outcome 可见前冻结。
- 高质量工人成功识别并修复 Wrong 不是“实验泡汤”；那可能表现为最终总效应接近零但纠错成本和机制清晰。
- UI 隐藏字段不等于清空 payload；分支逻辑必须保证不可用字段不保存。
- 内部几何残差、3D preview 方正度和外部正确性分别报告。
- 元标签跨阶段不强行同值；保留 raw value、instrument version、applicable 状态和 provenance。
- “模拟”只允许作为排演或明确标记的合成层，不得填补真实观察或追求预期显著结果。

## 6. 仓库分析结果状态与本次整理

### 6.1 当前入口（保留原路径）

| 状态 | 路径 | 用途 |
|---|---|---|
| CURRENT | `analysis_results/historical_uncertainty_recompute_20260829_v1/` | 当前 20 点、12–15、整体分歧、少数结构与 reference 质量结论 |
| CURRENT | `analysis_results/full_uncertainty_data_mining_20260821_v5/` | 当前全阶段生成交付 |
| CURRENT | `analysis_results/uncertainty_substrate_20260823_v1/` | 中性 canonical/provenance 底座 |
| CURRENT | `analysis_results/rq1_corrections_20260826/` | RQ1 raw 审计修正结果 |
| CURRENT | `analysis_results/manual_semi_correctness_oos_20260823/` | Manual–Semi correctness/OOS 唯一 canonical 派生目录 |
| ACTIVE REVIEW | `analysis_results/annotation_uncertainty_batch1_broad_review_20260828_v1/` | 139 张宽候选人工审核入口 |
| ACTIVE REVIEW | `analysis_results/annotation_uncertainty_batch1_candidate_review_20260827_v2/` | 原 28 图完整字段候选审核 |
| ACTIVE REVIEW | `analysis_results/annotation_uncertainty_batch1_supplement_review_20260828_v1/` | 8 图无重合补充审核 |

### 6.2 支撑/上游：保留路径但不能当最新结论

| 状态 | 路径 | 原因 |
|---|---|---|
| UPSTREAM | `analysis_results/rq1_raw_recompute_20260826/` | 最新历史复算仍读取其中 3 个 CSV；部分口径已被 corrections 修正 |
| UPSTREAM | `analysis_results/rq1_stratified_uncertainty_20260827_v1/` | 最新复算仍读取其 dense rarefaction 输出 |
| SUPPORTING | `analysis_results/annotation_uncertainty_evidence_20260829_v1/` | 数据资产/候选池证据仍有用；其中“尚无 reference 合同/Q(k)”已被最新复算更新 |
| SUPPORTING | `analysis_results/annotation_uncertainty_manual_semi_20260820_v2/` | 旧聚焦分析，不作为当前对外叙事；仍有脚本默认路径 |
| DEVELOPMENT | `analysis_results/historical_model_issue_construct_validation_20260827_v1/` | 元标签 taxonomy 开发审计，不是新 truth |
| DEVELOPMENT | `analysis_results/uncertainty_threshold_anchoring_worker_types_20260823/` | 阈值/worker 类型探索，不作稳定类型或因果结论 |
| LOCAL DEVELOPMENT | `analysis_results/uncertainty_meta_feasibility_20260824_v1/` | 本地开发测试，含运营信息，不对外、不进正式分析 |

### 6.3 本次物理归档

仅移动无 Git 跟踪、无外部路径引用且明确被替代/开发限定的 6 个目录；不删除文件。归档位置：

`analysis_results/repo_cleanup/legacy/annotation_uncertainty_superseded_20260830/`

- `最新分析/`：2026-08-20 interim 快照，名称已经误导；
- `annotation-uncertainty-preflight/`：development-only preflight；
- `uncertainty_data_inventory_20260820_v1/`：旧单文件盘点，已被 v5/substrate/evidence/current recompute 覆盖；
- `annotation_uncertainty_batch1_candidate_review_20260827_v1/`：旧 schema，被 v2 替代；
- `annotation_uncertainty_batch1_natural_supplement_review_20260828_v1/`：README/manifest 明示被替代；
- `annotation_uncertainty_batch1_natural_review_20260828_v2/`：README/manifest 明示被 broad review 替代。

没有移动 tracked、被脚本/测试硬编码或被 manifest 绑定的旧目录。`rq1_raw_recompute_20260826/` 即使含已修正旧口径，也必须作为最新复算上游保留原路径。

## 7. 当前交付与复现入口

优先阅读：

1. 本文；
2. `analysis_results/historical_uncertainty_recompute_20260829_v1/README_ZH.md`；
3. `analysis_results/historical_uncertainty_recompute_20260829_v1/历史标注不确定性复算工作簿.xlsx`；
4. `analysis_results/historical_uncertainty_recompute_20260829_v1/QA_SUMMARY.json`；
5. `analysis_results/historical_uncertainty_recompute_20260829_v1/ANALYSIS_MANIFEST.json`。

主要结果文件：

- `plateau_check_summary.csv`：12–15 人与平台检查；
- `disagreement_distribution_summary.csv`、`disagreement_task_distribution.csv`、`disagreement_task_ecdf.csv`：整体分歧；
- `disagreement_recovery_associations.csv`：任务分布与恢复的描述性关联；
- `minority_mode_replay_summary.csv`、`minority_mode_replay_task_k.csv`：少数结构；
- `structure_threshold_sensitivity.csv`：结构阈值敏感性；
- `image_reference_contract.csv`：42 图 reference 合同。

复现入口：

- `tools/thesis_main/analysis/materialize_historical_uncertainty_k_curves_20260829.py`；
- `tools/thesis_main/analysis/build_historical_uncertainty_workbook_20260829.mjs`；
- `tests/test_materialize_historical_uncertainty_k_curves.py`。

## 8. 下一步安全任务

1. 先确认第 3.3 节的七个歧义，不启动分发；
2. 将 36 图人工审核结果物化为机器可重放表，区分原始决定、机械检查和最终裁决；
3. 若采用多人重复测量路线，先写一页 estimand/reference/聚合/停止规则，再做资源仿真；
4. 只在方案确认后生成新的研究合同、SAP、assignment、instrument 和 pilot；
5. 若以后继续清理仓库，先更新消费者路径并运行测试，再移动任何 tracked 或 manifest-bound 目录。

