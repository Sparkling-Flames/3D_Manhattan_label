# Project98正式接入：当前完整研究输入

**当前共同评分更新（2026-10-17，v2）：** 已接既有局部结构与底面兜底归属，B8L2主指标与D10并列同分母，质量可用1911份（1699普通、188门洞、24其它）。原1787同分保留；新增70中63份质量可用、6份仅底面、1份其它空间受限。详细统计与关键图见 `research/statistics/b8l2_d10_statistics_20261017/`。下方“新增70待绑定/质量空”属于正式接入当时的历史阶段，不代表当前评分。

当前合同已指向本目录 `manifest.json`；通过 `load_current_bundle()` 读取。有效数据由旧完整基线加70份Project98作答构成：3222份人员作答、261研究图、261份原GT及30份手工GT，共3513对象；另有2张仅参考图片。1382份确认环不表示所有作答均可评分。

## 采用依据及限制

- 7个源账号已映射既有W001、W006、W008、W010、W012、W015、W017；没有新增人员身份，也没有恢复W019/W026或其它旧排除。证据见[接入审计](../../research/statistics/new_annotation_intake_20261017/README.md)。
- 原审核绑定的完整导出与当前导出一致。按用户“有序号就行了”的要求，采用当前明确编号：最小周期水平差上下配对，保留原top源索引顺序，再应用审核order。`pair_maps.json`逐作答记录源点身份；不先按x重编号。旧task8编号算法未恢复，`historical_basis_recovered=false`。补交HTML对应融合共识排序入口，不能作为原task8实现的证明。
- 70份均为新增独立人图作答，19图中17图已有、2图新增。新两图原GT完整，各6点对；难度均为中等，“偏简单”仅备注。完整GT不代替作答目标绑定。
- active time采用v10任务—人员合同：每session取累计峰值后跨session求和；70键共5205秒。279行、277去重事件、2重传；没有用lead_time替代、缺失填0或推算annotation生命周期耗时。Project93/94历史unfrozen/null不追改。
- scope原选择69 in_scope、1 out_of_scope；保留为独立情况字段，不据此修改来源condition或自动选目标。

库存现保留2991份、25位人员、261图（2图零人）；移出231份继续保留原原因。b8cTxDM8gDG-04按用户要求待定，库存24人保留、当前分析暂停。新增70份质量均为空、待目标绑定；原B8L2用途v2的1787份正常质量及历史难度/参考快照不重算。新增任务人员时间不直接冒称与某个质量目标同范围的耗时。

## 生成与验证

1. `python -m tools.thesis_main.data_prep.prepare_annotation_batch_20261017`：显式准备本包，并验证完整输入。`--activate`仅在审阅后切换合同数据入口，本轮已执行。
2. `python -m tools.thesis_main.analysis.new_annotation_intake_audit_20261017`：读取当前合同及本包登记核验采用状态。
3. `python -m tools.thesis_main.analysis.annotation_counts_20261017`、`python -m tools.thesis_main.analysis.annotation_gallery_data_20261017`：生成当前人数与图库。工作簿使用已有 `annotation_counts_workbook_20261017.mjs` 消费相同表。

`CHECKS.json`记录完整输入验证与旧对象不变检查。当前质量上下文消费者 `current_annotation_context_20261017.py` 严格要求旧评分ID与当前新增登记完整衔接，只为登记的新增ID补空分数。旧manifest可显式加载复现；本包的 `quality_review_metadata` 是已应用旧审核的来源记录，不再次回放修改。

相关测试覆盖原基线显式加载、独立人图/排除门、编号与源点漂移、时间来源身份、上下文新增ID、图库计数及HTTP保存。具体通过数量见本包 `HANDOFF.md`。浏览器已复核新图7/6人、中等标签、点对与原图/GT、b8c04待定；补人计划前后不变。Excel六页已渲染检查，临时预览清理。

合同版本、评分公式、旧原始导出/日志、旧输入与质量快照均保持；本次只采用数据增量和任务人员时间。研究目录、项目地图及文档索引已同步。未运行全仓测试，未推送或提交Git。下一步安全工作是明确新增作答目标绑定后另建质量版本，不能按最高分自动挑空间。
