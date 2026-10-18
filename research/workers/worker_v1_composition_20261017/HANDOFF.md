# 人员模块交付与统筹接入

**2026-10-17接续更新：** 本文件主体记录首交状态；[人员Pro与真实TEAM_RESULTS接入](../worker_v1_pro_integration_20261017/HANDOFF.md)已完成，当前机器入口为接续包`CROSS_MODULE_INPUTS.json`。14603个请求完成、rPc-22的242个明确失败、0待发布；437普通兼容净改善及156强缺陷机会已接入。旧CSV/JSON和请求保留，不再把下文首交依赖当当前未完成项。

2026-10-17，数据v1，分析修订`worker_v1_composition_20261017`。本文件只交接本模块，不修改全局模型、合同、catalog、地图或其它模块。

## 已完成

1. 复用当前1048份普通Q、727份来源T、418份同目标T和既有拟合/支持规则，交付全27人描述、原尺度Q统计、目标建筑外画像、训练object_id清单、分组人数/覆盖/未知和跨建筑符号变化。
2. `TEAM_REQUESTS.json`：173个非OOS合格Manual池，2595条完整排列，14845个真实成员去重集合。3条预定随机顺序/图；B8L2与D10各6种组优先顺序；每条都有同图同人数随机对照、k=1/2真实前缀及全员终点。未以目标图成绩选择人员。焦点组缺失明确标记。
3. 固定成员在B8L2/D10评价与换指标后重选成员分开。`metric_selection_contrasts.csv`可供融合按固定终点指标交叉比较，不预设胜负。
4. `existing_team_reuse.csv`记录642个旧尝试及实际状态文件/JSON指针。600个有完整旧输出且当前准备坐标/环序完全相同，可按冻结融合上下文复用；35个旧失败保留；16个受uNb9QFRL6hY-36两位人员环起点变化影响，与失败有9个交集。没有静默按“几何相似”覆写环序。
5. `record_evidence.csv`覆盖3222份，`semi_evidence.csv`574份，`exclusion_evidence.csv`218份。288个实际错误初始化机会中，36原样保留、3明确修改后未纠正、249结局未知；明确修复成功未获得裁决。历史OSPA30净改善540份，未改名为B8L2/D10净改善。
6. 85份审核排除中保守列出10份最终invalid且文字明确的个人错误剔除证据，其余75归因未知。133份历史未接受中113份来自W019/W026整人排除，不能按逐条错误计；余20归因未知。各人同时保留总提交、明确判断机会、审查覆盖、未知及分条件/场景分母。S仅保留选择证据，不生成新正确性。
7. `statistics_person_evidence.csv`54行及`statistics_record_profiles.csv`6444行是统计直接连接接口。前者`worker_id × metric`唯一，后者`object_id × metric`唯一；包含全部库存资格/未知，不自动恢复排除记录。

## 来源、边界与接口

- 共同评分：`research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json`，包修订`quality_b8l2_d10_20261017_v2`；数据仍为v1。B8L2主指标、D10只改方向尺度，原参考与资格保持。
- 原始/审查来源：正式`analysis_results/research_input_20261017/manifest.json`经manifest loader验证加载；574份Semi旧证据保持原OSPA30算法与参考；报告和`INPUTS.json`/`FIELD_CONTRACT.json`列出处及字段。
- `fold_person_profiles.csv`按目标`building_id=fold + metric + worker_id`连接；`fold_training_ranges.json`列出训练object_id和建筑。所有目标建筑均排除后再拟合或使用已有对应折。当前v1已多次探索，不能包装成全新独立验证。
- `TEAM_REQUESTS.json`的`teams`是成员集合；`paths`是真实进入顺序及逐k成员集合引用。不得用全员墙线身份生成各前缀。成员集一样的确定性终点应一样。
- 每个请求有声明参考及成员原绑定参考；请求本身不授予评分资格。参考缺失/用途限制由融合线程继续判定，OOS没有请求且不得进入主质量收益。
- `source_time_known_sum`和`target_time_known_sum`只累加各自已知部分；对应缺失人数大于0时不是完整成本。不得把来源任务时间当选定空间专属时间。
- 严重失误归类是既有人工证据的保守下限和接口，不是完成全体统一严重度盲审。审查子集有选择性；不输出新的加权质量分、重复扣罚或恢复整人排除。

## 验证

- `python -m tools.thesis_main.analysis.worker_v1_composition_20261017`完成，CHECKS中的全3222/27、Q1048、T727/418、目标建筑隔离和共同manifest未变化均通过。
- `python -m pytest tests/test_worker_v1_composition_20261017.py tests/test_worker_b8l2_d10_20261017.py tests/test_worker_b8l2_20261016.py -q`：17 passed。
- 补充定向核验：报告本地相对链接、全部CSV字段/行数与FIELD_CONTRACT、逐记录JSON来源指针和唯一连接键。
- 未运行全仓测试：本轮没有修改共享消费者或算法；相关重要边界已经定向测试。未运行新融合、当前B8L2/D10初始化重评分或新人员采集。
- 本轮未截图，无截图清理项；未暂存、提交、推送。

## 待统筹登记

已只读检查`docs/README_INDEX.md`及`docs/PROJECT_MAP_CLEAN_20260308.md`现有人员入口。本轮被明确限制不修改全局文件，因此由统筹统一更新：

- 研究包：`research/workers/worker_v1_composition_20261017/`，入口`README.md`，消费者入口`TEAM_REQUESTS.json`，来源/字段入口`INPUTS.json`与`FIELD_CONTRACT.json`。
- 专属脚本：`tools/thesis_main/analysis/worker_v1_composition_20261017.py`。
- 专属测试：`tests/test_worker_v1_composition_20261017.py`。
- 请在`research/catalog/CATALOG.json`登记为“数据v1、分析修订、人员组合请求与可靠性证据接口”，保留此前人员包身份及历史分母；按既有生成器更新目录，并将本README接入地图/README。不要把请求数写成已算融合数。

## 首交时依赖及当前接续状态

首交请求现已被融合执行并由接续包消费，成员、k和策略/随机关系已核对。173池中四格齐全的池B8L2为83、D10为93，不能把每条组优先路径都当纯组实验；实际纯类比较见接续结果。

统计已经产出真实策略结果；接续包逐行核对并提供新的逐人、逐对象证据与纯类/重选解释。重叠团队、策略路径、楼外折不能当独立图。

新Pro已提供不同强度定义的156次实际缺陷机会、25次未改和437份普通B8L2/D10兼容净改善；接续包保留与本包旧288次/39条及249未知的对象桥接。新131次编辑后错误特定结局仍未知；25/68剔除编码保留为候选，不形成综合扣分。
