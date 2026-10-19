# 人员类型发现 Part A — v2 冻结研究交付

建议阅读顺序：

1. [中文完整报告](REPORT_ZH.html) 或 [Markdown](REPORT_ZH.md)：主判断、候选真实成员、支持、效应、反例与采用范围。
2. [离线中文联动展示](presentation/personnel_types_part_a.html)：177 图池、60 人、整簇/成员开关、ERP/BEV/3D、同背景 A/B。单文件可离线打开。
3. [60 人联合画像](assessment/WORKER_PORTRAITS_60.csv)：152 列，包含旧 QT/QTD、新候选、逐难度与行为支持；FULL 只用于描述。
4. [可读运行证据](RUN_EVIDENCE_ZH.md)：哪些新算、哪些复用、哪些没有复现，以及工程恢复记录。
5. [统一复现与交换入口](reproducibility/README_REPLAY_ZH.md)：三个 ZIP 解压至同一父目录，合并本目录前缀。

## 核心数字

10,439 库存，7,302 正式 Q，普通 Manual 5,719 作答/177 图。22 折留建筑，正向28候选、反向64候选；本轮新算58,679唯一团队、286,666替换事件/175图/22楼。固定人数8/12/16/24；新背景固定换人身份且背景嵌套，共3,936条完整四节点链/164图。

**发现了候选分区与有限的历史几何风险信息；尚未得到同时跨楼稳定、简洁可解释且普遍可互换的人员类别。** 结果不否定分类探索，但也不将K4算法选择、类内常稳定或局部小增益升级为天然人群。

## 两个固定提交

- 当前输入 main：`dafa73ac7d8ada9a7f5c0e483d695adcbd916550`
- Pro冻结科学源：`82c6164b0d4630de5316199c92aa405930973168`

没有修改 main、原标注、参考、评分、正式等级或融合。统计对照属于回顾性建筑外验证；不是新外部盲测、不是完整采集或Dot复现。

## 机器入口

- `ANALYSIS_MANIFEST.json`：数据/方法/输出与省略缓存索引。
- `reproducibility/EXCHANGE_FIELD_CONTRACT.json`：逐折类别、关系、事件、预测和缺失。
- `events/common_events.csv.gz`：真实背景与双方成员、参考、几何/质量/失败。
- `assessment/EVENT_PREDICTIONS_WIDE.csv.gz`：所有选定方案在同事件的概率和关系；不会因为未知而删事件。
- `forward/candidate_classes_by_fold.csv.gz` 与 `reverse/results/all_candidate_classes.csv.gz`：全部探索过的逐折分区。
- `assessment/REPRESENTATIVE_CASES.csv`：七个可视实例；过滤器及全部候选分母另存。

全量概率长表如因重复体积省略，已保存完整类别、校准和事件，按打包清单可精确重建。不要把缓存省略理解为缺真人数据，或把可以重建说成本轮已重放所有历史流程。
