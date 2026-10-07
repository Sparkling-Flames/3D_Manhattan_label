# 工作台技术验收记录

原工作台构建有 42 项检查通过、0 项失败。证据为 [all-results.tap](all-results.tap)、发布前同组复跑的 [publish-checks.tap](publish-checks.tap)，以及 [tested-build.json](tested-build.json) 中的被测试源文件 SHA-256。两份日志是重复验证同一组检查，不相加为 84 项。

## 42 项检查覆盖

- 数据 10 项：36 份、六图、空白评分、原／修参考分离，现存点位／点对／连接，44 个几何对象的独立投影，ERP 端点与接缝，原图哈希及固定抽样
- 核心规则 13 项：1–5 整数、无法判断／草稿分离，新存储空间，JSON 往返，CSV 编码／空值／公式转义，批次指纹、身份和字段验证，按更新时间合并
- 静态及旧版 4 项：原旧版程序、样式及数据保持字节一致，旧存储与视图保留，新旧入口和新页面资源可达
- 应用流程 15 项：在 Node DOM 环境运行实际应用代码，检查自动保存／恢复、切换状态与作答、A/B 评分归属、无分数的指标查看、存储故障／损坏、参考上下文以及导入取消／拒绝／往返

线上 v3 已于 2026-10-07 17:23:06 UTC 成功部署，保留仅所有者访问；实际浏览器访问受私有站点登录门槛阻挡。上述42项检查在 Node 环境运行，不能代替真实浏览器验收。WebGL 渲染、实际鼠标手势、响应式视觉布局、下载行为、键盘焦点与已登录线上访问，不在此记录的已验证范围内。技术检查也不验证评分锚点的有效性、样本代表性或最终质量权重。

## 与公开源码的绑定

归档时重新读取当前源码，index.html 和三个 review36 JavaScript 文件及样式均匹配上述测试哈希。frontend/index.html 的历史链接随后单独由相对地址改成既有私有站点的绝对地址；其余既有源文件逐字节保留。完整源／归档哈希和每项路径改动见 [frontend_source_receipt.json](../../provenance/frontend_source_receipt.json)。

tested-build.json 中保留原测试构建的数据与旧版文件哈希，不表示这些大文件或旧数据已复制进本公开目录。其浏览器验证说明仅做了措辞归一，测试哈希、计数与时间未变；证据文件原／归档哈希见 [qa_evidence_receipt.json](../../provenance/qa_evidence_receipt.json)。

原42项测试工具依赖更完整的私有输入，未包装成此公开小包的一键全量测试。这里的可移植公开复现入口是根目录 replay_public.py 与 build_frontend_data.py，其实际可复现范围分别说明。

## 公开数据重建检查

[rebuild_check.json](rebuild_check.json)记录1,153项额外检查：重建后的36份作答和8份参考，共44对象、1,120个记录字段，与私有工作台对应字段相同；批次指纹和浏览器数据绑定正确。

默认重建没有复制原图。明确提供已有原图目录时，仅复制六张核对了哈希和尺寸的原 PNG；错图会在写出数据或复制图片前被拒绝。测试产物留在归档目录之外，公开payload没有生成 data36.js 或照片。

这个重建检查没有重新计算质量指标，也没有运行浏览器／WebGL。独立数值与几何重放记录见上一级 [public_metric_replay_validation.json](../public_metric_replay_validation.json) 和 [public_replay_validation.json](../public_replay_validation.json)。
