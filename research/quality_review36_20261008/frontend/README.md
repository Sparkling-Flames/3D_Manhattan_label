# 36 份评分工作台前端源码

这里保存本轮工作台 HTML、CSS、JavaScript 与随附 Three.js 库，不包含照片或重复的数据包。源码来自当前工作台的已测试版本；逐文件来源、SHA-256 和归档修改见 [frontend_source_receipt.json](../provenance/frontend_source_receipt.json)。

唯一的既有源码修改是 index.html 中的历史入口：相对 legacy.html 改为[已存在的私有历史页](https://panorama-quality-review.fringnb.chatgpt.site/legacy.html)。旧版59份数据、照片和旧页面不复制进公开目录。访问权限仍由原站点控制，保存链接不授予新的访问权限。

线上版本：[36份评分工作台](https://panorama-quality-review.fringnb.chatgpt.site)，v3 已于 2026-10-07 17:23:06 UTC 成功部署，仍为仅所有者访问。源码归档不改变这个范围。私有登录门槛阻挡了本轮真实浏览器／WebGL视觉验收；下文42项检查通过仍仅指其声明的技术范围。

## 本地重建

三个较大的归档文件以 gzip + base64 分片保存，包含本页使用的 Three.js 库与冻结输入。先恢复原始字节，再重建数据；恢复脚本使用标准库，并核对大小及 SHA-256。详见[分片清单](../packed/manifest.json)。

在本研究目录运行：

```sh
python restore_packed.py
python build_frontend_data.py
```

脚本从 data/frozen_geometry.json 生成 frontend/data36.js，保留36份作答及8份参考的点位、连接、几何、数值与状态，只增加浏览器所需的标签、图片相对路径、初始参考和批次信息。生成数据受 .gitignore 保护，不重复提交。

原图不在本目录中。如果已有获准使用的六张原 PNG，可明确提供其目录：

```sh
python restore_packed.py
python build_frontend_data.py --image-dir /path/to/authorized/originals
```

此选项先核对六张图片的文件名、SHA-256 和尺寸，全部通过后才复制到 frontend/images/。只复制清单指定的六张，不扫描复制其他图片，也不联网下载。images/ 同样忽略，不应加进公开提交。没有原图时不能把运行中的几何页面当成完整视觉评审材料。

通过本地静态 HTTP 服务打开 frontend/index.html。评分只保存于所用浏览器的本地存储；公开 GitHub 源码不会收到评分。JSON 备份与继续评分规则见[工作台说明](../WORKBENCH_AND_RESULTS.md)。

## 验证范围

[42项检查记录](../validation/frontend/all-results.tap)与[被测试源文件哈希](../validation/frontend/tested-build.json)针对原工作台构建。它们验证数据、核心规则、应用事件与旧版保留，使用 Node DOM 环境；没有运行真实浏览器／WebGL。

本归档重建另外核对44个几何对象与私有工作台完全一致，并验证无原图默认复制、指定图片哈希及错误图片拒绝。重建数据文件的整体字节不会等于私有完整数据包，因为未复制不需要的元数据；几何、数值与参考版本保持相同。导航路径修改不是几何修改，也没有被冒称为新的完整浏览器验收。
