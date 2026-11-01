# 05_Cases_and_Evidence.zip：案例、原始依据与冻结诊断代码

本包保持统一目录前缀 `HOHONET_v21_image_response_20261101/`，原样保存三个普通 Manual 案例及两个门洞后段案例。

## 阅读入口

- `stage05_cases/manual/README_ZH.md`：三个普通案例；每图 `VIEWER.html` 可脱网查看原图、完整个人标注、当前参考、精确团队、实际融合点对与支持票。
- `stage04_doorway_cases/DOORWAY_LATE_CASES_ZH.md` 与 `DOORWAY_LATE_RESPONSE_EVIDENCE.html`：两个门洞后段案例和离线可视证据。
- 原图、全部相关个人原答、正式参考、逐团队分数与状态、完整保存几何、实际票账和回放一致性证据均在各案例目录。正文使用的 PNG、PDF、SVG 与绘图数据保留。
- 原验证文件原样保留；本次只做封装、CRC、内层压缩读取与文件哈希核对，不重新做科学分析或视觉裁决。

## 复现依赖与边界

`stage04_doorway_cases/replay_engine/` 是固定仓库提交 e1873bfadc1d0e61499809c91fba9dc39c717f83 下恢复的冻结代码与测量引擎，不是本轮重新调参的版本。`scripts/` 中所收案例脚本及本地导入辅助脚本与主代码包采用同一当前文件字节，其 SHA256 记入外部清单。

本包不携带 vendor 二进制目录。执行代码前请依照 06 代码包的 requirements 安装依赖，其中 Shapely 固定为 `shapely==2.1.2`。脚本将不存在的 `ROOT/vendor` 加入搜索路径不妨碍使用已安装的对应依赖。

案例查看页和保存的证据可独立阅读；完整脚本复现还需要 04 输入包中的源快照、正常化输入所用数据和所引用缓存，以及相应规范化路径结果。三个普通案例的 `CURRENT_POOL_FULL_INPUT.json.gz`、`CURRENT_PATH_PREFIX_VALUES.csv.gz` 和保存端点均已包含，但现有复现脚本仍按项目标准目录读取源材料。本案例包不宣称独立包含全库数据或完整运行环境。

当前图表和统计结果没有被打包操作改变。已存在团队的诊断回放与新科学团队/新随机路径分别记账；原历史来源位于 `legacy_evidence/` 时保留其原日期、原口径与原说明。

## 验证清单

本包 SHA256、ZIP CRC、内层 gzip 完整 EOF/CRC、内层 ZIP CRC 与表格可读性记录位于统一交付清单 `stage09_delivery/CASE_PACKAGE_MANIFEST.csv` 和 `CASE_PACKAGE_VALIDATION.json`。这两份外部文件给出封装后的实际成员与哈希，不将临时渲染页、缩略图、Python 字节码缓存纳入交付。
