# Label Studio 现有不确定性标签可行性测试包

状态：`DEVELOPMENT ONLY / NOT FORMAL DATA`

本目录用于在独立中文测试项目中检查现有标签是否易懂、选项是否重叠以及页面保存是否正常。它不属于正式实验，不进入论文分析，也不改变任何已冻结协议。

## 测试范围

- 建议项目名：`DEV_uncertainty_meta_feasibility_zh_v1`
- 导入文件：`uncertainty_meta_feasibility_semi_import_zh_v1.json`
- 页面配置：`tools/label_studio/label_studio_view_config.xml`
- 样本：5 张已经完成过 P1 Semi 标注的图片；每张在历史 inventory 中均有 26 名标注者记录。
- 当前 8 名测试者均曾标注过这 5 张原图，不使用任何未标注图片。
- 分配：8 人完成同一组 5 张，共 40 条 worker–task 分配。
- 参与者：`W001, W006, W008, W010, W011, W012, W013, W015`。
- `W002`、`W017` 留给后续实验；`W018` 按用户确认排除；其他排除依据中文人员表状态记录在工作簿中。

## 本地分发工件

- 外部分配真源：`analysis_results/uncertainty_meta_feasibility_20260824_v1/assignment_manifest.csv`
- 对外中文任务表：`analysis_results/uncertainty_meta_feasibility_20260824_v1/任务分发表.xlsx`
- 内部样本清单：`analysis_results/uncertainty_meta_feasibility_20260824_v1/sample_manifest.csv`

分配表和工作簿含真实姓名，仅供本地运营，不应提交到仓库。对外工作簿只显示普通任务编号，不写测试目的、条件、样本来源、反馈字段或排除信息。Label Studio 只负责展示和采集，不能替代外部分配真源。

## 使用边界

1. 新建独立开发项目后导入 5 个任务，不复用正式项目。
2. 项目应允许每个任务收集 8 份标注；实际账号与任务映射必须在运行时另行核对。
3. 不向标注者暴露历史错误家族、GT、支持数或他人的旧结果。
4. 按当前标签原样测试，包括 `unsure`；不要为了得到特定分布诱导标注者少选或多选某一项。
5. 只汇总界面理解、选项重叠、保存问题和修改建议；不比较工人表现，不计算正式显著性。
