## 本轮实际分组保存结果

当前本地分支为 `codex/workspace-organize-20260927`。源码／测试、文档、历史分析产物已分别保存为WIP提交；导入计划另外保存，不代表执行导入或验收通过。公开研究目录也在本地保存。上述本地整理提交未推送。

当前公开入口：[展开研究分支](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/codex/pro-layout-research-20260927/research/pro_layout_20260927)。独立分支仅新增22个研究文件及两个索引登记，不包含ZIP，不包含本地WIP历史。旧Release保留为历史快照。

新的局部整体投票与搜索减法仍为待验证假说；这次重新运行的是现有八图核心与15项既有测试，不代表全部WIP源码已验证。

整理后未提交项有意保留：4份正式方法文件的原有修改、1项原始导出删除。原导出不恢复也不提交删除，避免改写用户既有操作。前面的2172项统计是整理前快照，不再是当前状态。

隔离工作树创建因Windows长路径失败，发布改用独立Git索引；未变更全局Git配置。没有为整理删除实验、原图或原始导出。

# 工作区导航与待收尾清单（2026-09-27）

此页用于整理研究文件入口，不是方法合同，也不代表历史工作已验收。保留已有路径，以免破坏图集、脚本和证据引用。

## 从这里进入

| 工作 | 入口 | 状态 / 用途 |
|---|---|---|
| 当前人工复核 | [打开](../../analysis_results/review_reconciliation_20260925/index.html) | 继续二次复核；尚未完成全量排除与分类 |
| 最新Pro交接 | [打开](../../analysis_results/pro_cloud_layout_research_20260927/README.md) | 已公开发布；代码、坐标包和验证记录 |
| 本轮讨论及研究边界 | [打开](../../docs/thesis_main/PANORAMA_CONSENSUS_RESEARCH_DISCUSSION_20260927.md) | 区分融合共识、多空间候选及人员/图片效应 |
| 八图并集减法 | [打开](../../analysis_results/union_branch_consensus_20260926/README.md) | 已有簇的结构分支探索；不是新退火搜索验证 |
| 40图结构共识 | [打开](../../analysis_results/structural_consensus_20260926/README.md) | 历史探索结果，不当作最终清洗样本 |
| 连线和指标反例 | [打开](../../analysis_results/layout_algorithm_exploration_20260926/README.md) | ERP、3D、IoU、质心与顺序的数学初探 |
| 排序工作台（暂缓） | [打开](../../analysis_results/order_studio_20260926/index.html) | 等待二次复核；不自动全量重排 |
| 历史综合面板 | [打开](../../analysis_results/research_dashboard_20260922/index.html) | 旧分析导航，不能替代当前裁决 |

公开交接：[GitHub Release](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/pro-layout-research-20260927)。完整包公开范围已由用户明确授权；回下载ZIP与本地逐字节一致。

## 文件分工

- `tools/thesis_main/analysis/`：分析与构建源码；`tests/`：对应测试。不要以图集可打开替代源码验证。
- `analysis_results/review_reconciliation_20260925/`：当前复核界面与记录。
- `analysis_results/{layout_algorithm_exploration,structural_consensus,union_branch_consensus}_20260926/`：算法探索，保留为可复算证据。
- `analysis_results/order_*`：排序工作及历史风险提示；目前暂缓，不作为新排除决定。
- `analysis_results/pro_*`、`*_received_*`和旧dashboard：历史交接及接收材料。ZIP和解压目录功能不同，尚未证明可相互替代。
- `export_label/`、`import_json/`、`active_logs/`：真源层，不能按普通生成产物清理。

## 当前Git快照

统计仅覆盖Git看到的改动和未跟踪文件，不含被忽略的数据集、模型、缓存和全部已提交文件；不等于整个磁盘占用。快照生成时尚未计入本导航和清单本身。
共 **2172 个文件状态项**，现存文件约 **1.01 GiB**。主要体积来自图集和历史交接材料。

| 路径组 | 文件状态项 | 现存 MiB |
|---|---:|---:|
| `analysis_results/research_dashboard_20260922` | 538 | 231.01 |
| `analysis_results/review_reconciliation_20260925` | 263 | 172.88 |
| `analysis_results/order_studio_20260926` | 270 | 170.74 |
| `analysis_results/panorama_research_received_20260921` | 450 | 101.64 |
| `analysis_results/cluster_validation_received_20260922` | 14 | 65.44 |
| `analysis_results/pro_cluster_handoff_20260922` | 3 | 48.48 |
| `analysis_results/pro_research_handoff_20260921` | 4 | 45.33 |
| `analysis_results/research_dashboard_20260922.zip` | 1 | 36.55 |
| `analysis_results/cluster_screen_20260921` | 10 | 35.78 |
| `analysis_results/order_preliminary_review_20260923` | 13 | 21.67 |
| `analysis_results/structural_consensus_20260926` | 51 | 18.67 |
| `analysis_results/shared_x_reanalysis_20260922` | 300 | 18.48 |
| `analysis_results/layout_algorithm_exploration_20260926` | 20 | 16.91 |
| `analysis_results/room_partition_comparison_20260922` | 7 | 11.58 |
| `analysis_results/supervisor_independent_20260922` | 20 | 6.33 |
| `analysis_results/order_screening_20260923` | 4 | 5.73 |
| `analysis_results/consensus_research_20260923` | 1 | 5.38 |
| `analysis_results/union_branch_consensus_20260926` | 16 | 4.57 |
| `analysis_results/research_dashboard_structure_20260921` | 9 | 3.56 |
| `analysis_results/presentation_inventory_20260922` | 9 | 2.77 |
| `analysis_results/worker_cluster_sensitivity_20260921` | 35 | 2.38 |
| `analysis_results/pro_cloud_layout_research_20260927` | 28 | 1.73 |
| `analysis_results/research_dashboard_structure_20260921.zip` | 1 | 1.06 |
| `tools` | 45 | 1.05 |
| `docs` | 11 | 0.25 |
| `analysis_results/标注区域差异评论清单_20260926.json` | 1 | 0.14 |
| `tests` | 35 | 0.13 |
| `analysis_results/cn_first10_20260922` | 3 | 0.11 |
| `import_json/cn_first10_20260922` | 7 | 0.11 |
| `analysis_results/consensus_visual_review_20260923` | 1 | 0.02 |
| `.gitignore` | 1 | 0.02 |
| `export_label/新增中文20图` | 1 | 0.00 |

完整路径和状态：[机器清单](../../analysis_results/workspace_inventory_20260927/inventory.json)。

## 需要区分的未提交事项

1. **正式方法相关改动**：当前JSON/MD合同、研究SOP及统计计划已有未提交改动。本次仅盘点，不将其与研究附件合并提交，也不改写其语义。
2. **源码与测试**：新增分析、复核面板及研究dashboard散布在对应稳定目录；保留源码和测试配对。此轮只验证公开包中四个测试文件（15项），未声称其余未提交源码已全面验收。
3. **原始导出删除状态**：以下路径在本次整理开始前已被Git报告删除；本次未删除、恢复或提交它。需要结合原先操作背景确认：
   - `export_label/新增中文20图/project-93-at-2026-09-21-04-34-9e224397.json`
4. **生成结果**：不使用 `git clean` 或批量忽略来伪装干净工作区；先保留证据和引用。若后续归档，应按主题独立归档并检查消费者，不能按日期一刀切。

## 本次实际整理

- 发布最新研究包及独立提示词，记录公开地址与校验结果。
- 新增本主题导航和机器清单；在文档总索引与项目地图登记。
- 只删除本轮回下载校验的临时ZIP副本和空目录。没有移动、删除或批量提交历史实验。
- 本轮没有生成截图；没有改算法、GT、原件、排序或排除裁决。

下一步可按“复核工具、算法探索、正式方法文件、历史产物”分别审查与提交；当前仍有未提交工作是事实，不视为整理失败或可直接删除的垃圾。
