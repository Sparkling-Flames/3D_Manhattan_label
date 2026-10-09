# Agent 上下文入口

当前研究：`consensus_research_20260923_v1`。先读 `AGENTS.md`、`docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`、执行/统计 SOP，再按任务读取专题。历史 v23 合同固定为 `docs/thesis_main/PAPER_A_METHOD_CONTRACT_20260811_v23.json`，不可用当前 schema 解释旧阶段。

## 当前入口（2026-10-06）

- 接手先读[统一研究模型](../thesis_main/研究模型_人员图片与融合不确定性_20261006.md)、[术语](../thesis_main/CONTEXT.md)和[数据说明](../thesis_main/研究数据说明_来源预处理与用途_20261006.md)，再按任务读取合同与执行／统计 SOP。当前安排从统一模型第8节读取；[完整交接](../thesis_main/线程交接_连线质量与完整共识_20261004.md)保留原意与证据，推进台账记录带日期的实验，不继承旧待办顺序。
- 人员原作答分歧、融合人数过程、实际全员结果分别观察；融合稳定不代表原作答一致。增加人数后出现新标法仍是待检验猜想；困难、OOS、门洞不预设不一致，非正交但可标及门洞可标／不可标分别保留。
- Lee区域投票与点／点对融合并行。最新输入、人工补标及结果覆盖沿数据说明定位，不从旧快照猜测是否已完成实验。

## 历史工作快照（2026-10-03）

以下保留当时的进度与来源链接；其中“最新”“下一步”“先做”不再作为当前执行指令。

- 用户进一步纠正demo及输出目标：先看整份作答的标法簇，再看完整上下融合候选；Lee原文是普通对象区域分割，BEV为本项目迁移选择。直接ERP区域投票可保留上下稠密轮廓，但不自动形成稀疏配对角点。参照合同`consensus.layout_output_and_demo_20261003`，不把已有底面结果冒称完整layout。

- 最新方法安排：Lee区域投票与角点／点对中心融合并行，见合同`consensus.parallel_point_region_20261003`及研究方向第6节。先做点融合当前输入对照、Lee人数稳定性量，再接Q/T/S/B子类人数过程与真实组合；连续画像迁移同时保留。点方法仍在开发，不阻塞已有基线研究。

- 用户最新澄清：仍处研究阶段，连续画像、Q/T/S/B粗分类子类内标注收敛和不同子类组合可并行探索；不把名单稳定或天然类型确认当唯一研究目标。同房相似性描述核查与四个真实融合demo已完成，见推进台账；历史方法不自动升级，但有用历史证据应读取。新版Q/T/S/B子类曲线尚未执行。

- 最新[人员研究返回审查](../../analysis_results/worker_review_20261003/REPORT.md)与[前三轮精选归档](../../research/consensus_reviews_20261003/README.md)：本地复核已完成；用户确认重复坐标仍为独立票。下一步连续画像迁移，再扩人数×构成；不把来源独立性核查重新设为前置，不冻结高低类型。

- [研究方向与算法职责](../thesis_main/history/研究方向_空间差异与共识_20260930.md)、[推进台账](../thesis_main/研究推进台账_20261003.md)：A线136图最多24人；B线共同24人×10图画像及固定4人构成精算已完成。正式人员类型、完整人数×构成及两线联系待研究；[Chat Pro交接](../../research/worker_consensus_handoff_20261003/README.md)。先用这些入口判断当前阶段。
- [当前方法摘要](../thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.md)、[执行 SOP](../thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md)、[统计计划](../thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)。
- [最终审核数据接入](../thesis_main/最终审核数据接入_20260929.md)及[统一输入](../../analysis_results/research_input_20260929/manifest.json)。仅在追溯审核时读取[二次复核 SOP](../thesis_main/两人审核归并与二次复核SOP_20260925.md)与[历史台账](../../analysis_results/review_final_20260928/README.md)。
- [共享 x 预处理基线](../../analysis_results/shared_x_baseline_20260928/README.md)及相关输入禁止移动。预处理状态、资格与确认排列分别解释。
- [文档总索引](../README_INDEX.md)、[项目地图](../PROJECT_MAP_CLEAN_20260308.md)、[历史文档目录](../thesis_main/history/README.md)、[路径速查](REPO_PATH_MAP.md)、[写入规则](WRITE_RULES.md)。
- [CE-only 运营 SOP](../label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md)只在相应运营任务中加载；离线BEV/GT分析不据此启动采集、分发或C2阶段。

## 按任务读取 playbook

- 代码与测试：[code_change_verification](playbooks/code_change_verification.md)。
- 文件结构与入口：[docs_sync](playbooks/docs_sync.md)。
- 方法、轮次与资格：[protocol_guard](playbooks/protocol_guard.md)。
- 统计、时间与重放：[statistical_plan_guard](playbooks/statistical_plan_guard.md)。
- Label Studio 运营：[label_studio_ce_guard](playbooks/label_studio_ce_guard.md)。
- 较大交付：[handoff_summary](playbooks/handoff_summary.md)。

## 历史与保护

- [旧文档归档](../legacy/paper_a_before_consensus_20260928/README.md)、[旧结果归档](../../analysis_results/legacy/research_cleanup_20260928/README.md)。历史材料供复算与回溯，不充当当前执行入口。
- `export_label/`、`import_json/`、`active_logs/` 和原始数据不移动、不改写；已有人工裁决不追改。
- 下游读取的历史分簇输入、人工原件和测试基线保留原路径；未知来源不凭版本日期清理。
- 2026-10-03清理：移除活动目录中的 `paper-a-c2-operator`。其旧描述会被一般GT、active time和任务编号触发，且误将CURRENT合同当旧C2规范；历史版本留在Git，不再作为当前自动指引。不用新skill重复当前合同和推进台账。
- 开工核对 Git 状态；与任务无关的现有修改及新产物不纳入批量清理。提交/推送按用户当前授权执行，不沿用历史文档中的“本轮”状态。
