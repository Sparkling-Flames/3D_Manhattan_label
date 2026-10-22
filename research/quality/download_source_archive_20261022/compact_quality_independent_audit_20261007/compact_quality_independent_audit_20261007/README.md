# 简洁质量方案的独立审核与新增补验

先读「独立结论_简洁质量评价_20261007.md」。本轮完成Pro新交付的复核，并新增验证目标敏感性实验。没有重做上一轮五轮研究，也没有改原数据、资格、GT、连接或融合。

## 目录

- research/reproduction：官方运行结果、独立重建数值、API与六案例验证、中文审计报告
- research/target_sensitivity：新增八方案实验、逐对/图/建筑结果、原图与原人员对固定子面板、成对效应及独立复核
- inputs/compact_results：新增补验实际依赖的五份原Pro CSV，原样复制，便于直接重算
- CONCEPTUAL_AUDIT_ZH.md：验证含义、可计算覆盖与方案选择的独立审读
- source_versions.json：固定资料的来源身份
- fusion_state_source_check.json：220个保存融合状态与既有上游状态的对象一致性

## 直接复算新增实验

本包已经包含所需的五份来源表。安装Python、NumPy和pandas后，从本包根目录运行：

    python research/target_sensitivity/run_experiment.py --source inputs/compact_results --out fresh_target_results
    python research/target_sensitivity/check_experiment.py --source inputs/compact_results --out fresh_target_results
    python research/target_sensitivity/independent_check.py --source inputs/compact_results --out fresh_target_results
    python research/target_sensitivity/write_report.py --out fresh_target_results

新输出目录与交付结果分开。各文件夹README提供详细参数；运行环境记录不要求复用任何机器专属路径。没有权重搜索、拟合新分类器或按目标挑选最有利分数。

## 重新审计Pro交付

完整审计还需要已上传的原资料：

- panorama_quality_compact_20261007.zip，Library libfile_d126170e8f6081919606e6e0946231b5；数值版libfile_28ac0db9c83881919ae031a1e38d5adf也可运行无图分析
- 前轮quality_audit_five_rounds_20261007.zip，libfile_be7ad49832308191b08328ea3f307c47
- pro_quality_expanded_data_20261007.zip，libfile_71977790d08c81918700d41c91aec899

官方reproduce.py应写入新目录。独立审计用--source、--prior-review、--expanded、--official-output明确传入各个解压目录，详见research/reproduction/README_ZH.md。区域几何需要Shapely、SciPy等原包依赖。图像语义的复查使用完整版原图，数值版不能代替看图。

## 结果怎么读

CSV符合率/效应使用0至1比例，中文报告换成百分比/百分点。每个目标内所有方案使用相同有序对；目标之间的并列、可算图/建筑不同，不能跨行挑“总赢家”。默认先图内，再建筑内，再建筑等权。相关人员对、双参考和结果行不是独立样本。重采样只反映当前建筑贡献敏感性，不是新建筑总体置信区间。

实用默认方案与已验证最优方案不同；当前标注的几何测量与历史人员分数预测未来图片也不同。三维预测没有提升，不等于三维空间差异不存在；自身规整性的局部预测信号也不等于整体质量奖励。
