# 来源与运行依赖

- 原工作台v3.4.2：17分卷恢复包 `quality_scope_review_complete_20261010/workbench_v3.4.2`；发布来源commit `e44b52969f0d18a352773a83c4b9575f720bc5a7`。本轮只保留14个相关原件，逐文件哈希在 `results/source_reuse_manifest.json`。归档源码未发现单独新许可证，不擅自赋予MIT或其他许可。
- 正式输入commit `24360ad8544d76d8aba18a8e641f784a76ca0d42`；范围基线 `42f7ea569c591c0cb3472e1b8bb8c0d883bbd3cb`；审核30题由main159e中的冻结清单定义，SHA256 `bf1c3265184fe21d313c96415c80741a65ce6f531f1141aa7ff79ea1e40d2bf8`。`results/input_provenance.json` 列20份当前记录的源快照、对象和坐标SHA。
- A/B坐标来自原工作台GT和已接收底面确认。C/D没有坐标。原图为工作台1536×768 JPEG，旧30题图片直接复制上一轮交付，不再为未确认顶界渲染3D。数据/照片不推断新许可证，按仓库原研究访问范围使用。
- 回执原件的Library身份、version、SHA及恢复核验方法见 `results/receipt_byte_verification.json`。完整原件保持不改，不替换Library version 0。
- 静态使用：现代浏览器；工作台原geometry、state和catalogue函数不引入外部网络依赖。
- 构建：Python3标准库、Node（几何QA）。实际浏览器测试：Python Playwright1.62.0、系统 `/usr/bin/chromium`。测试临时HTTP loopback及隔离浏览器上下文；QA画出的坐标和复核判断不进入用户种子数据。
- 用户ZIP只含可运行页面、输入副本、真实图像及使用说明，不含Q、参数枚举、QA临时判断或截图。既有研究包/原算法/已知数值失败留在此前研究交付，未重复搬入本轮。
