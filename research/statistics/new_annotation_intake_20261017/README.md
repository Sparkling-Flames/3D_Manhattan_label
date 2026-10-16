# 新增中文70份作答：身份、时间、排序与接入审计

**时间边界：** 本包是正式接入时（评分前）的证据快照，下方70份待绑定与quality_analysis_included=false描述该时刻。后续局部归属与当前1911份共同质量见 `research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json`，新增70中已有63份质量可用，不能以本快照旧标志覆盖当前评分。

当前状态：**已进入当前合同指向的正式研究输入；新增质量仍待目标绑定**。`analysis_included`在本包只表示正式研究输入采用，不代表所有质量用途合格。70份新增的`quality_analysis_included=false`，质量值保持空，不能补0。旧3152份快照及旧评分不追改。

- [完整审计](audit.json)与[逐条台账](records.csv)：项目、任务、作答、既有W身份、时间和排序来源。
- [字段合同](FIELD_CONTRACT.json)、[身份登记](IDENTITY_MAPPING.json)及[身份直接证据](IDENTITY_EVIDENCE.md)。
- [历史时间方法证据](HISTORICAL_TIME_METHOD.md)：最近93/94项目未冻结时间的历史事实与本次采用分开。

## 采用判据与结果

采用只在当前合同manifest为`analysis_results/research_input_20261017/manifest.json`且`batch_admission.records`的source_id与70条原作答完整匹配时成立；准备目录存在不算采用。当前合同指向：`analysis_results/research_input_20261017/manifest.json`。

|项目|结果|
|---|---:|
|图片／作答／源账号|19／70／7|
|确认既有W身份|70份／7人|
|任务账号时间可用／正式采用|70／70|
|排序已应用|70|
|完整导出同版验证|70|
|当前surface_valid|70|
|新增质量可用|0，70份待目标绑定|

7个源账号1、6、8、10、12、15、17已确认映射既有W001、W006、W008、W010、W012、W015、W017。证据为93→98共同页面session的项目实例桥，加各账号旧93原始作答completed_by与bundle W身份精确锚；不是仅凭数字，也不是7名全新人员。既有人员排除、作答清洗与独立票门继续有效。

## 排序与参考

原审核的完整导出内容绑定已核实一致；此前“旧几何未证实”的缺口已解决。用户明确“你看有序号就行了”，本次按当前明确编号规则采用审核order，逐source保存原keypoint上下点对索引，台账`pair_map_origin`指向`analysis_results/research_input_20261017/pair_maps.json`。`historical_basis_recovered=false`：没有声称恢复旧task8工具的历史编号算法。

19图中17图已有库存，2t7-02/03为两张新增图，原GT来自valid/label_cor，人工难度为中等（偏简单）。GT完整不等于70份作答已绑定目标；新增质量用途仍待显式目标版本绑定。原图与新作答均保留全部点，不以最高质量或几何近似挑目标，不裁剪原作答。

scope仅指原导出in_scope/out_of_scope，69／1；out_of_scope为`ls98:3686:7549`。此choice不等于GT问题、人员排除或target_id，不存在另需补交的scope文件。

## 时间单位与边界

日志为v10／c2plus_task_worker_v1，身份是project|runtime_task|source_account，单位秒。每session取累计active_seconds峰值，再跨session求和；fragment不是网络增量，不能逐上报相加。70键合计5205秒；279原始日志、277去重事件，2重复，无冲突。采用状态以台账`time_adopted/task_worker_time_adopted`为准。

client epoch与有时区annotation时间统一UTC；naive服务器接收墙钟仅诊断，重传、manual flush和updated_at后的活动不自动使任务总时间无效。`annotation_active_seconds`保持空，因为采集合同未分解annotation生命周期；整份任务累计也不是裁切scope专属时间。未用lead_time替代或缺失填0。

最近93/94实际消费者历史上是unfrozen/null，本次Project98采用不追改它们的历史资格。原export_label和active_logs只读，未重算旧质量或改旧冻结包，未生成截图。目录和共享入口由主线程统一维护。
