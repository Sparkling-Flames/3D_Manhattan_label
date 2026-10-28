# v2.1 既有换类端点几何重评分

限定 `pools/DEPENDENCIES.json` 中 `reuse_geometry_rescore` 的45个池，其中31池在这三个来源有已保存端点，另外14池在这三个来源未检索到端点，明细见 CHECKS.json；不生成新融合、重选团队或重拟合分类。重评分参考来自 `pools/INPUT_SNAPSHOT.json` 的 pool meta.reference_id，并从 v2.1 reference_catalog 读取同一 target 的坐标。

各源的几何和标量逐team_key连接，并核对 pool、人数、成员、原参考及状态：严格ABC闭合 10400、背景梯度 420、直接AC 775；跨来源34个重复团队的几何与成员一致，去重后11561个唯一团队。详见 COVERAGE.json，事件仍须按原事件表的 team_key 接回，不能按去重后团队频率代替原事件频率。

结果分58个 `shards/*.jsonl.gz`；按 team_key 关联 `INPUT_TEAMS.jsonl.gz` 和旧事件，团队保留实际 member_workers、原object身份字段、原状态、原参考、来源及旧标量。新结果放 `result` 下。11310完整评分（B8L2、D10、WQ、A10及原working损失与子项、omission/extension），118个少于四节点保留 floor-only 状态，133个原连接失败保留不评分；所有状态及按来源数量见 CHECKS.json。

参考依赖节点/墙线召回、角点召回及墙覆盖已用冻结 reference_structure 与 geometry_diagnostics 补算：11428队有候选点、133队因无候选点标为不适用。原值仅存在 original_metrics，禁止作为v2.1值使用；新值在 reference_dependent_diagnostics。20队评分在补诊断前后逐项完全一致；旧参考样例与原生诊断接口及旧记录一致。不可评分不补零，旧连接状态不因新参考改变。评分沿用冻结 scoring_engine、measured 和 dual_scores，full-score 的 A10 使用相同 working_models 显式推算并核对 WQ 一致性。

`python -m tools.thesis_main.analysis.rescore_v21_exchange_endpoints_20261028 --part inventory` 生成输入及覆盖；`--part score --jobs 4` 生成结果。脚本拒绝覆盖已存在分片；要重做需先在独立目标或清理此批自有结果后执行。首次运行时 A10 由后续 `--part working` 对已完成分片补充；当前代码已在 score 阶段直接附加 A10，该步骤可用于复核旧批。未重新建立事件对比、构成标签或公式依赖召回指标；此批数据需独立验收。

补算命令：`python -m tools.thesis_main.analysis.rescore_v21_same_room_20261028 --part exchange_diagnostics --jobs 4`；仅诊断，不重评分或融合。详见 DIAGNOSTICS_CHECKS.json。
