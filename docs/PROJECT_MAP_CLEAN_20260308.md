# HOHONET 项目地图

- 259图全量难度/范围复核：[分层标准与字段合同](thesis_main/图片难度全量复核与分层标准_20261010.md)、[全量报告](../analysis_results/image_difficulty_full_review_20261010/REPORT.md)、[人工粗审页](../analysis_results/image_difficulty_full_review_20261010/review.html)。259图3152份台账，13张范围优先候选、20张改档建议；尚待用户粗审，旧工作表保留。

更新：2026-10-09。仓库用于半自动全景布局标注与研究。当前方法版本为 `consensus_research_20260923_v1`；日期化实验结论以各自唯一报告为准。

## 当前研究入口

- [文档总索引](README_INDEX.md)：当前模型、术语、数据、难度和融合入口。
- 当前人员／图片研究：[统一研究模型](thesis_main/研究模型_人员图片与融合不确定性_20261006.md)、[术语](thesis_main/CONTEXT.md)、[数据说明](thesis_main/研究数据说明_来源预处理与用途_20261006.md)。
- 最新图片工作分类：[6点对低遮挡看图更新](../analysis_results/objective_difficulty_20261009/review_examples/SIX_PAIR_UPDATE_20261010.md)、[259图工作表](../analysis_results/objective_difficulty_20261009/review_examples/working_classification_20261010.csv)。6图改简单；特殊组继续单列；保留旧自动结构类与看图来源。
- 图片难度：[当前GT结构粗分类入口](thesis_main/图片客观难度评分_20261009.md)、[259图主表及原GT对照](../analysis_results/objective_difficulty_20261009/structure_classification/REPORT.md)、[旧d_model冻结补缺与有限比较](../analysis_results/objective_difficulty_20261009/d_model_expansion/REPORT.md)。新增`tools/thesis_main/analysis/difficulty_{structure,dmodel}_20261009.py`及对应测试／字段合同；OOS、门洞与可标性独立。历史工具`difficulty_{features,score,strata,model_probe,bilayout_probe,model_comparison,dino}_20261009.py`及其结果保留，12图事实核查为可选补充；Bi同源结果在`bilayout_probe/research_source/`。
- 图片难度审图：[21图原图与GT点位图集](../analysis_results/objective_difficulty_20261009/review_examples/index.html)、[样例名单、旧评分口径及场景交叉表](../analysis_results/objective_difficulty_20261009/review_examples/README.md)。特殊场景单列；一致／不一致／未评分目的性示例，不作为盲法验证，不改主分类。 最新[评分复核与使用解释](../analysis_results/objective_difficulty_20261009/review_examples/SCORE_RECHECK.md)：门洞／OOS独立评分待定，x8-01参考待核。
- 图片难度外部审查：[自包含讨论汇总与Pro任务](thesis_main/图片难度研究汇总与Pro深度研究任务_20261009.md)，补充旧HoHoNet特征／风险定义与方法取舍，属于支撑材料，不新增算法或协议。
- 墙线融合：[方法](thesis_main/共识投票机制与三路线推进_20261007.md)、[操作 SOP](thesis_main/融合共识操作SOP_20261008.md)、[当前交付](../analysis_results/consensus_delivery_20261008/REPORT.md)。
- GT结构条件：[环序与自遮挡审计](../analysis_results/gt_order_visibility_20261009/REPORT.md)；工具`tools/thesis_main/analysis/gt_order_visibility_20261009.py`，测试`tests/test_gt_order_visibility_20261009.py`。原／修订GT及循环接缝分开，不将几何条件当作已识别的人类难度或噪声量。
- [机器可读方法合同](thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)是规范真源；Markdown 由合同生成。历史 v23 消费者仍固定读取其原版本合同。

## 目录地图

| 路径 | 职责 |
|---|---|
| `tools/thesis_main/` | 主研究线分析、registry、freeze、风险规则和数据准备 |
| `tools/paper_a_manhattan/` | Paper A Manhattan、sandbox、expert review 与 audit-only 工具 |
| `tools/paper_b/` | Paper B 训练、审计、cue、bilayout 与 B0/B1/B2 工具 |
| `tools/label_studio/` | 共享 Label Studio 配置、viewer、server、upload 与 import helper |
| `docs/thesis_main/` | 主研究线模型、方法、SOP、数据说明与状态 |
| `docs/paper_a_manhattan/`、`docs/paper_b/` | 对应论文支线资料 |
| `docs/label_studio/`、`docs/agent/`、`docs/shared/` | 运营、agent 规则与共享写作材料 |
| `docs/legacy/` | 历史文档；默认只追溯，不迁移或更新 |
| `import_json/`、`export_label/`、`active_logs/` | planned import、运行时标注和原始 active-time 真源 |
| `analysis_results/` | 派生结果、审计、manifest 与图表，不作为输入真源 |
| `research/` | 外部材料、独立复算和研究交接包，须按来源状态解释 |
| `tests/` | 工具、字段合同及边界测试 |
| `data/`、`output/` | 数据资产与模型推理／中间结果 |

## 真源和读取边界

- 后续分析从 `analysis_results/research_input_20260929/manifest.json` 和 `load_current_bundle()` 读取统一包；包名日期不代表补充审核都已写入。
- 不由分析结果反写 `export_label/`、`import_json/`、`active_logs/` 或原始标注；历史审核、输入坐标与来源映射保持可追溯。
- 当前合同、round-based SOP 和统计分析计划分别承担规范、执行与分析职责，不重复定义 eligibility 或字段语义。
- `tools/label_studio/create_labelstudio_split_by_outline.py` 的旧配额逻辑不得覆盖冻结协议或导入工件。
- `/tools/vis_3d.html` 是部署兼容路由，不代表仓库源码位于 `tools/` 根目录。

## 写入位置

- 新 Python 脚本按职责放进 `tools/thesis_main/analysis|registry|data_prep/`、`tools/paper_a_manhattan/`、`tools/paper_b/` 或 `tools/label_studio/`，不写入 `tools/` 根目录。
- 新主题文档放入对应 `docs/` 分类；根目录只保留 `README_INDEX.md` 与本项目地图。
- 新增、删除或移动文件后检查本页与文档总索引。协议、统计计划或 Label Studio 运营语义改动须按对应 playbook 核对。
- 不移动或修改 `export_label/`；未经授权不改变 protocol、schema、routing 或 SOP 语义。

## 历史文档

- [历史文档目录](thesis_main/history/README.md)区分已归档原文、旧版导航与仍因兼容而留在原路径的快照。
- [整理前的项目地图](thesis_main/history/项目地图历史快照_20261009.md)保留逐阶段结果和旧路径索引。
- 更早的研究清理包见 `analysis_results/repo_cleanup/`；外部材料按各归档下的 `README`、`MANIFEST` 或 `field_contract` 追溯。

## Agent 规则

参见 [Agent 上下文](agent/AGENT_CONTEXT_INDEX.md)、[文档同步](agent/playbooks/docs_sync.md)、[代码验证](agent/playbooks/code_change_verification.md)。协议和统计变更另读 `protocol_guard.md` 与 `statistical_plan_guard.md`；Label Studio 运营先读 CE-only SOP。

## 109条独立点复核工作台（2026-10-09）

- `tools/thesis_main/analysis/build_point_edit_review_20261009.py` 与 `serve_point_edit_review_20261009.py`：构建109队列并在本机提供绿色全景工作台；`point_edit_review_20261009*` 为伴随编辑器。
- [输出、操作与验证](../analysis_results/point_edit_review_20261009/README.md)位于 `analysis_results/point_edit_review_20261009/`；收到的对照包保留在 `research/point_review_109_received_20261009/`。
- `tests/test_point_edit_review_20261009.py`、`test_point_edit_review_20261009.cjs`、`point_edit_review_browser_20261009.cjs` 覆盖来源身份、编辑补丁和实际浏览器往返。审核返回不写正式数据或恢复资格。
- `tests/point_edit_review_ux_20261009.cjs` 验证绿色工作台鼠标操作、旧草稿保留与最近记录恢复；不操作用户日常浏览器缓存。
- `point_edit_review_20261009_sort.js` 适配旧完整点对拖动代码；`tests/test_point_sort_review_20261009.cjs`、`point_sort_review_browser_20261009.cjs` 与 `point_sort_visible_20261010.cjs` 验证周期x候选点对、排序留痕、卡片可见与实际拖动。
- `research/point_review_109_received_20261009/109份复核重筛清单_20261010.csv` 是重筛来源，`queue_resolution_20261010.json` 记录既有单条排除与OOS无法计算不重复召回；[范围与返回说明](thesis_main/109份点编辑审核范围与返回核对_20261010.md)及 `analysis_results/point_edit_review_20261009/109份审核范围与返回核对_20261010.csv`逐条说明109→14份／8图。该输出目录的`received_return_audit_20261010.json`保存18条返回与旧排序的核对，原件存`evidence/`；`tests/point_review_rescreen_browser_20261010.cjs`验证默认队列、全量查看和旧草稿保留。
