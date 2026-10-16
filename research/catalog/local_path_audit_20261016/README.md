# 本机输入路径统计与迁移（2026-10-16）

统计固定提交 f081b267907173cddf2580e34684ba81681cc585 的全部Git跟踪文本。9,092行目录形式引用、241个文件：Windows本机路径9,021行，GitHub URL 11行，其他网络URL 5行，相对路径/脱敏来源55行。另纳入f16394d历史指南第55行，共242个来源文件；631个去重Windows目标包含目录，不代表须搬移631个文件。新增清单以 `<LOCAL_DOWNLOADS>` 隐去用户名；JSON片段与源码行号不作为不同文件。新增表仅保留路径与用途，不复制无关原文内容。二进制归档、工作簿、PDF及外部LFS载荷内部未展开。历史来源字段不修改。

- [逐文件与行号](by_file.md)
- [逐行清单](occurrences.csv)
- [唯一目标与全部引用位置](unique_windows_targets.csv)
- [16个tools脚本的18行引用](executable_dependencies.csv)
- [本机Downloads引用核对与资料回收结果](DOWNLOADS_RECONCILIATION.md)：区分运行输入、已归档重复件、已回收历史证据及仍留在本机的完整包。
- [可执行归档映射及SHA256](../../../tools/thesis_main/local_input_archives.json)

## 14个输入目标及默认位置

“已有归档”按原接收脚本明确的逐字节复制关系定位，并固定本次仓库文件SHA256。未访问本机原件，不能将本次哈希检查说成再次比对本机文件。固定归档被修改将拒绝执行；显式新输入仍须通过各工具原有绑定/来源校验。仓库归档可能就是该工具输出的证据副本，同路径复制现在安全跳过；不重新运行历史数据变更流程。

|输入名称|用途|已有归档 / 默认位置|
|---|---|---|
|label_data.zip|当前原GT核验与空间参考构造|未核实原ZIP；`data/external/label_data.zip`|
|八组采集采用_我的审核.json|历史复现工具|`analysis_results/new_manual_analysis_20260921/用户_八组采集采用_原始.json`|
|补齐配对复核.json|历史复现工具|`analysis_results/pairing_applied_20260929/evidence/completed_pairing.json`|
|全历史标注_二次复核_20260925(2).json|历史复现工具|`analysis_results/review_return_20260927/evidence/second_review.json`|
|上下点配对审核.json|历史复现工具|`analysis_results/x_pairing_audit_20260929/evidence/pairing_return.json`|
|image_difficulty_scope_preferred_my_review.json|当前/增量接收|`research/difficulty/difficulty_review_update_20261015/user_review_receipt.json`|
|角点顺序审核(4).json|历史复现工具|`analysis_results/final_review_summary_20260929/evidence/order23.json`|
|全历史标注_定向补审_20260927.json|历史复现工具|`analysis_results/review_closeout_20260928/evidence/returned_review.json`|
|角点顺序审核(2).json|历史复现工具|`analysis_results/order_model_same_image_20260929/evidence/user_followup.json`|
|角点顺序审核(1).json|历史复现工具|`analysis_results/order_pattern_recall_20260929/evidence/user.json`|
|角点顺序审核.json|历史复现工具|`analysis_results/order_same_room_review_20260928/evidence/user.json`|
|角点顺序审核(3).json|历史复现工具|`analysis_results/order_completion_audit_20260929/evidence/same_image35.json`|
|空间范围人工审核_2026-10-15(1).json|当前/增量接收|`analysis_results/research_input_20260929/scope_receipt_20261015_1.json`|
|project-65-at-2026-07-02-16-49-f641e0f6.json|历史复现工具|`analysis_results/calibration_rebuild_20260702/manual_zh_analysis_chain_precheck_v3_1/snapshots/project-65-at-2026-07-02-16-49-f641e0f6.json`|

## 配置与本机尚需执行的步骤

1. 本次未访问本机目录、未搬移或删除任何文件。确认仓库根目录为本机HOHONET后，核对可信原 `label_data.zip` 的来源、大小及SHA256；将同一份文件**复制并保留原件**至 `data/external/label_data.zip`，比较复制前后SHA256。目标已存在时先核对，不覆盖不同数据。用户最终需要迁出下载目录时，原件的后续处理另由本机确认，本次不删除。
2. 默认源ZIP相对仓库根目录解析；可用 `HOHONET_SOURCE_ZIP` 明确指定路径。显式路径优先，缺失直接报错，绝不搜索或回退下载目录。既有GT转换逐值核验仍执行，错误版本不能跳过核验。云端无该原ZIP，因此未重跑研究算法。
3. 其余13项默认复用表内固定归档，无须为复现再次从下载目录取件。要读取新回执，先将选定文件保存在 `inputs/local_reviews/<原文件名>`，设置 `HOHONET_REVIEW_INPUT_DIR=inputs/local_reviews`；此配置对该目录明确负责，不回退旧归档。也可在Python中调用 `review_input(name, explicit=path)`；project-65工具保留原有 `--manual-zh-export`。新回执必须匹配各工具原有schema、绑定与版本规则。不要仅因同名就覆盖归档。
4. `data/`维持既有忽略策略，新增 `/inputs/local_reviews/` 明确忽略本地回执。只提交审计表、说明、配置和代码。历史复现工具还可能依赖原有微信/临时文件等非下载目录来源；本次不访问、不声称已解决这些无关依赖，也不把旧接收工具当作当前一键重放入口。

本次只修复必要输入路径，不改变公式、参考、质量结果或冻结证据。不把网络URL、浏览器download属性或历史来源词条机械替换。待恢复指南见[空间重评分扩展指南](../../data/scope_quality_rescore_20261016/EXTENSION_GUIDE.md)。
