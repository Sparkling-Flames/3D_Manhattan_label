# 人员与同房研究收束页

双击 `research-closeout.html` 即可离线打开，无 HTTP 服务器、CDN、fetch、上传或遥测。原 `index.html` 仅新增入口，不替换旧模块。

## 数据合同

- `schemaVersion: 1`，三张原始字段表：`personnel`（53条件）、`members`（2772目标楼类别映射）、`sameRoom`（8验收问题）。
- 来源相对路径、SHA-256、行数保存在 `sourceFiles`；可从仓库根部执行 `python research/statistics/research_explorer_v1_r2_20261017/build-research-closeout.py` 重建冻结 JS。
- 成员映射不是实际事件入队名单；必须同时选择方法、作答条件、目标楼。没有匹配不表示成员为零。
- 缺失显示为未提供／不适用，保留真零；Manual/Semi不合并，重叠条件不求和。
- C−A、有向差、C−B匹配净差和绝对变化各自保留；时间算术/几何百分比不混用；失败分母与单位单列。
- 对源文本使用 `textContent`，不将表内 HTML 当作可执行内容。

## 核验

`node --test research/statistics/research_explorer_v1_r2_20261017/research-closeout.test.cjs`

7 项通过：合同和唯一ID、缺失/零、条件隔离、目标楼成员隔离、停止/结构核验等级、来源/分母字段、离线资源及入口。

浏览器实际渲染尚未完成：当前环境 Chromium 启动被 `socket() failed: Operation not permitted` 阻止；安全提升后的容器又因只读挂载失败。不能把以上纯 JS 测试称作视觉验收。旧研究台其他模块不在本次重跑范围。

研究证据等级见页面逐行原始字段：面板到汇总独立重聚合不是全事件原生融合；停止和结构继承先前核验，本次未重跑。
