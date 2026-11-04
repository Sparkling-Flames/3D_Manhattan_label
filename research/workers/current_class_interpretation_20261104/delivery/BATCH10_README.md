# HOHONET v2.1 第 10 批：JOINT K4 原图对照补充

本包补齐 JOINT K4 四类的真实完整标注与个人指标，并更新现有图册、整合报告、当前研究口径和研究台入口。冻结研究源提交继续为 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。

## 使用

按 ZIP 内仓库相对路径解压到 `D:/Work/HOHONET`，在第 08 / 09 批基础上覆盖本包对应文件。无需重新运行统计、融合或分类。

- 图册：`research/workers/current_class_interpretation_20261104/examples/index.html`，选择 **JOINT K4**。
- K4 专项图文：`research/workers/current_class_interpretation_20261104/examples/JOINT_K4_SUPPLEMENT.html`。
- 研究台：`research/workers/current_class_interpretation_20261104/workbench/index.html`，点击 **直接查看 JOINT K4 四类**。
- K4 个人指标：`research/workers/current_class_interpretation_20261104/examples/JOINT_K4_SELECTED_RECORDS.csv`。

本包包含完整 `examples/`、四张原始 PNG、全部 17 幅静态板以及自带数据的离线图册，因此原图浏览可直接使用。完整研究台与上级统计报告仍接续第 08 / 09 批；本包不重复打包全部研究统计源。

## 本次补充

保持原简单、中等、困难三主图及跨楼附图，追加 K4 四类同图对照。每图 C1 / C2 / C3 / C4 展示 2 / 2 / 1 / 2 人，C3 在当前 new 同源组只有 W121，明确为本图全量 1 / 1，不重复补位。新增 28 个展示位，其中 23 个对象复用既有图册、5 个为新增独立原答。全图册现为 4 种分区、92 个典型位、1 个近共线附例、39 个独立原答。

每个原答保留完整上下点、保存顺序、当前参考、底面、结构标记、Q/D10、IoU、位置/方向/高度分项和合法同源 T。原三分区的对象选择与数值保持；静态板标题明确 K3/K4，底面按新增对象后的同图共同范围显示。研究坐标不变。

## 验收与研究关系

新增 K4 选样、原始楼外标签、参考版本、预处理坐标、分项与时间已独立核对；原 65 展示位、34 个对象的数据保持。已有 102 份画像与团队分析文件保持原值。四张 K4 板已目视检查，离线引用和 JavaScript 语法检查通过；本环境未运行真实浏览器交互测试。

本批新增的是展示和说明。JOINT K4 全量同图 Q/T 的支持与数值、分类模型以及既有团队结果保持；没有新分类拟合、融合、评分或选队。案例不替代总体估计；单张图中 C3 的容量不代表全部训练折的类别人数。

本批有效载荷 **59 文件、39911598 字节**，另附本说明和 `BATCH10_FILES.csv`。完整指标与出处见图册数据及 K4 专项说明，检查见 `examples/JOINT_K4_INDEPENDENT_REVIEW.json`、`examples/DISPLAY_VALIDATION.json` 与顶层 `DELIVERY_CHECKS.json`。
