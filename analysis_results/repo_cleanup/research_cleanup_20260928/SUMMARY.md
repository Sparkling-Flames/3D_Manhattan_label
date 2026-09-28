# 2026-09-28 仓库文档与结果整理交付

## 已完成

- 展开归档 **134 份文档/写作资产**至 `docs/legacy/paper_a_before_consensus_20260928/`。包括明确 superseded 的合同/提纲、旧讨论和交接、原 history/archive_20260918、T1/V1 Overleaf 工程；全部复制后逐字节核对，历史正文不重写。
- 将 **2885 份封闭旧结果**压入 **12 个主题 ZIP**；按原 Git 跟踪状态拆分。每个成员与源逐字节核对、实际恢复并再次逐字节核对后才移除源副本。
- **17 个已有 ZIP**原样收拢，不重复压缩；搬移前逐字节核对。
- 删除 **6 份明确渲染缓存/QA截图**；未删除研究图、标注图片、原始裁决或测试输入。
- 用户追加“原始数据及共享x基线相关内容不能移动”后，历史包内 **597 份原始输入、日志、人工原件及input/inputs副本**恢复原路径。ZIP保留附带快照。
- 压缩/缓存处理净节省载荷 **433.96 MiB**。此值扣除上述已恢复原件，未把普通文档/已有ZIP搬移计为空间释放；重新遍历docs与analysis_results全部本地文件，包含新增清单/索引/快照开销，合计文件字节净减少 **427.40 MiB**（逻辑文件大小，不等同NTFS分配簇或卷剩余空间）。

## 当前入口与边界

文档总索引、项目地图、Agent上下文和结果README重整为当前 `consensus_research_20260923_v1` 研究。撤下 March PreScreen 和旧Calibration/T1/V1默认当前说明；源代码和测试仅调整移动文档的读取路径，原检查逻辑不变。旧提案和已结束研究标为历史有效证据，不以归档表示错误。

`export_label/`、`import_json/`、`active_logs/`、GT资产、研究资格、已有裁决不改写。当前/v23合同JSON和MD及其他机器JSON原字节、原路径保留。两份执行/统计SOP只替换归档链接，已与包含既有修改的清理前快照比对。当前共享x基线及其原始/复核/修复/GT链不移动；各声明源均存在。现有修改、新产物和export_label既有删除不纳入本轮清理；未commit、push或重算历史数值。

## 验证

- 当前合同和v23合同 `render_paper_a_method_contract --check` 均通过。
- `pytest -q tests/test_consensus_contract_20260923.py tests/test_materialize_c_traps.py tests/test_freeze_trap_collection.py tests/test_pro_cluster_handoff_20260922.py`：**21 passed**。
- 原 `validate_runbook_command_contract` 及原runbook测试的额外断言：通过，13项命令合同无违规。
- 修改Python语法检查；60个源码docs字面路径和9份Pro文档清单全部存在。
- 当前入口104个本地链接检查通过（最终检查含本交付页）。
- 完整C2b pytest在清理前即因缺少 `statsmodels` 无法收集；本轮未安装依赖，也不称该套测试通过。未运行全库测试或历史数值复算，因为变更仅为文件位置和导航。
- ZIP第一次恢复检查遇Windows长路径限制，源文件当时未删除；重建该未验证ZIP后使用长路径恢复核对通过。所有临时恢复目录、清理脚本最终删除。

## 清单与恢复

- [逐文件动作](actions.json)：原路径、动作、理由、替代依据、字节数、ZIP成员、保留依赖与验证结果。
- [文档路径映射](path_mapping.json)、[路径同步文件](path_updates.json)、[保留原因](retained.json)、[验证](verification.json)。
- [共享x保护范围](shared_x_protected.json)、[恢复原路径的原始输入副本](raw_snapshot_retained.json)。
- [文档归档](../../../docs/legacy/paper_a_before_consensus_20260928/README.md)、[结果归档与恢复](../../legacy/research_cleanup_20260928/README.md)。

原Git已跟踪文件的归档保持可加入Git；本来忽略的本地文件和归档仍只留本机，未自动公开。完整导航快照及操作前盘点保存在本目录的本地忽略文件中。

## 保留与剩余问题

旧39图审核页仍被工具/浏览器测试读取；旧分簇current/inputs仍被新研究读取。大型旧审核、几何裁决和接收包依赖不明确，保持原路径。其他未处理目录不因较新版本或缺少固定字符串引用而删除，具体保留原因见清单。仍有历史包只能在恢复原目录后复算；后续应先确认依赖是否已闭合，再逐主题归档。

本轮文本差异检查使用LF行尾；完整工作区的diff检查不覆盖其他进行中的修改。

## 目录实测（含本地忽略文件）

| 目录 | 操作前文件数 | 整理后文件数 | 操作前MiB | 整理后MiB |
|---|---:|---:|---:|---:|
| docs | 308 | 309 | 26.54 | 26.40 |
| analysis_results | 20147 | 17303 | 8040.08 | 7612.82 |
