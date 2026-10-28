# 2026-10-28文档口径修订检查

本轮仅修文档和目录，不拟合、不评分、不重跑端点。统筹独立验收的1071次重拟合、最大预测差约2.29e-12属于统筹提供的回执；本轮没有复做该计算。

## 修订文件

- 本专题README：限定两种旧档合并、分列几何变量及非自动定档的结论；新增第7节完整方法依赖和三种成本；记录统筹验收来源。
- docs/thesis_main/topics/difficulty/图片难度可计算依据与最小比较方案_20261028.md：标注方案已执行与历史章节；补齐RFUSE等依赖，链接实证结论。
- 同目录图片难度定义_跨领域依据与复核建议_20261028.md：历史人工优先建议在章节与正文就地标记，不再作为当前任务；保留文献事实。
- 同目录图片难度全量复核与分层标准_20261010.md：顶部链接已执行结论，旧方法史保留。
- docs/thesis_main/研究讨论讲解稿_研究台路线与术语_20261028.md：更新讨论口径，去除当前人工复核优先建议。
- research/catalog/CATALOG.json及生成的INDEX、难度主题README：更新current_basis，避免重新生成时恢复旧建议；登记本回执。

## 代码证据（只读）

- unpacked/03/reverse/code/learn_natural_fusion_roles.py：STRATA第22行；内层alpha第78—109行；响应、资格、编码第112—130行。
- unpacked/03/classifications/code/build_condition_response_classes.py：域及方法第34—64行；manual_geometry/manual_time第161—162行。
- 上述classifications/code/build_scope_increment.py：联合资格和hard-minus-easy第14—19行；联合轴第25—38行。

以上路径均相对analysis_results/personnel_exchange_discrimination_audit_20261025，完整可点击路径在README第7节。RFUSE和前向类别的支持门槛不同，未混用。

## 定向验收

- 检查7份报告/入口Markdown的本地文件链接存在性；外部文献未重新联网核验。
- 检查当前主题README和讲解稿不再出现“判定表和独立复核为下一步建议”“目前最需要补清”等旧当前优先口径；历史段落就地标记。
- 检查方案不再写“尚未执行”，报告含RFUSE、DBOUNDARY、DJOINT、MSDGEOM、scope依赖及policy32身份。
- 运行build_research_catalog.py --write和--check；684项资料、11项算法、22项结果快照通过。
- git -c core.whitespace=cr-at-eol,-blank-at-eol diff --check通过。

地图/README_INDEX原有实证入口仍指向本报告，无路径迁移，无需追加重复入口。未运行模型或测试：本轮无代码和数据变更，3项测试通过为前次执行与统筹验收记录。未改正式标签、参考、资格、OOS、Word；未提交推送。已有并行修改保持。

实际执行回执：7份Markdown的158处本地文件引用通过，当前口径与方法依赖断言通过。初检发现长路径链接受Windows路径长度限制，已改指向逐字节相同的unpacked/03较短副本，再验通过；未新增哈希。
