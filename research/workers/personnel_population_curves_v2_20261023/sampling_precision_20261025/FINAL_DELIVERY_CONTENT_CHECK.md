# 最后交付内容检查：命令、路径与现存文件

检查范围限于 `REPRODUCE_ZH.md`、`FIELD_CONTRACT_ZH.md`、`build_report.py`、`engine/restore_table_shards.py` 及其直接命令接口/几何引用。没有重跑研究、融合或评分。

## 已处理的复现阻塞

原 `analysis_geometry/GEOMETRY_METHOD_ZH.md` 仍把旧人口输入定位为工作区内部 `../repo/research/...`；按最终仓库解压布局，该路径不存在。四份案例整理脚本也使用了同一硬编码。

经授权，已只修改输入定位：

- 方法文档的 `--base`、`--source-base` 改用根复现说明已定义的 `HOHONET_POPULATION_ROOT`。
- 四份案例脚本支持 `--population-root`、环境变量 `HOHONET_POPULATION_ROOT`；未指定时先识别最终仓库布局的父人口目录，再兼容旧工作区布局。
- VFua 完整重建在没有未打包逐池检查点时，读取已交付的 `results/GEOMETRY_PATH_PRECISION.csv.gz` 对应池/人数行。公式和几何不变。

四份 `--help` 均正常，显式参数、环境变量、最终父目录和旧工作区四种路径解析均指向当前实际的原人口输入。VFua 回退读取的25行与原逐池文件逐值一致。56份已交付结果文件的SHA256全部未变，没有重导案例或新增融合。详见 `analysis_geometry/PATH_PORTABILITY_CORRECTION.json`。

## 根文件剩余需改的一处定位

`build_report.py` 几何章节依据中有 `results/GEOMETRY_FIXED157_INTERVAL_MAIN.csv`。从最终本轮根目录解析，该文件不存在；实际位置是：

`analysis_geometry/results/GEOMETRY_FIXED157_INTERVAL_MAIN.csv`

这是表引用路径问题，不影响当前报告生成计算。检查者没有编辑根报告生成文件。

## 可选验证入口的依赖

主统计、几何与报告命令的依赖接口相容。若要求用户执行 `analysis_geometry/validate_geometry_outputs.py` 的PDF完整渲染核验，该程序导入 `fitz`，目前根 `requirements_analysis.txt` 未列出提供它的 `PyMuPDF`。应在依赖中补列，或注明仅PDF渲染验证需要该可选包；不影响自然/策略统计及Matplotlib出图。

## 已确认无阻塞的部分

- 恢复命令 `engine/restore_table_shards.py --manifest ... --output ...` 与实际参数完全一致；导入所需 `engine/package_table_shards.py` 存在。
- 恢复清单包含3个统一表：新增端点标量323809行/142字段（6片）、紧凑几何323809行/13字段（6片）、新增前缀403376行/89字段（7片）。19个分片路径均存在，分片行数之和与统一表一致。这里只核现存清单/位置；最终ZIP内部EOF验证由统一交付步骤负责。
- 自然统计、策略统计、原生执行、结果编译、关键表、图表、报告生成、ZIP核验和关联核验的文档参数均与实际解析器一致。
- 根报告中的6张PNG实际存在；VFua、稀少成功及wc2小表目录均存在。几何结果和小表已有56文件实际EOF/行数/字段/关键键验证回执。
- `CURRENT_FILES.csv` 在检查时尚未生成，但不作为统计输入；若它仍处于最终统一打包阶段，生成后纳入P04即可。

本次未改变分类、团队、权重、人数范围、种子、统计公式、评分或融合。
