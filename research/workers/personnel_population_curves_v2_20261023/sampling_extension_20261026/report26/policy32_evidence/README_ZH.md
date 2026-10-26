# 历史四策略32对：小表入口

本目录由已完成157图、22栋建筑的策略结果提取。自然48→256全量结果不在本目录内；策略图集与自然N≥30图集同为157图，交集为148图。

报告入口：[POLICY32_COMPLETED_FINDINGS_ZH.md](../POLICY32_COMPLETED_FINDINGS_ZH.md)。提取代码：[extract_policy32_evidence.py](../extract_policy32_evidence.py)。这些文件没有重新融合、重抽或训练分类。

|小表|用途|
|---|---|
|P01|主早段各难度、版本、图／楼计权及路径／建筑范围|
|P02|主早段、3—6人、20至缺一人、满员的标准汇总|
|P03|旧16／新16／合32的主早段宽表|
|P04|全部157图×4策略×3版本的1884条主早段结果|
|P05|同来源Q/T逐图节时／费时及双收益计数，劳动比与1比较|
|P06|从完整结果选择的六个正反解释例，各保留三个版本|
|P07|两个157图集的精确名单及成员标记|
|P08|当前三版本共同k与原main采用支持的差别|
|P09—P11|高Q新16时间机会最少的8图：逐k机会、原答字段和来源计数|
|P12|既定主早段与现成3—6阶段的时间路径／建筑范围|
|P13|独立新旧批次的单图效果重复情况|
|P14|旧16／新16／合32单图Q效果MCSE|
|P15|各策略两早段中，每张图自身可估重抽数及全支持解释所需的计数|

每张表保留英文原字段、中文角色和`source_table`。`EVIDENCE_MANIFEST.json`记录行数、字段及SHA，CSV/gzip已读至结尾。精确团队和进入顺序复用正式输入，不在此重复打包：

- `analysis_policy26/results/EXACT_PAIRED_EVENTS.csv.gz`：配对路径、人数、自然及策略端点；
- `analysis_policy26/results/FIXED_SUPPORT.csv.gz`：共同k、点估计、可估重抽支持；
- `analysis_policy26/results/POLICY_IMAGE_K.csv.gz`和`POLICY_IMAGE_PHASE.csv`：逐k与逐阶段；
- `analysis_policy26/results/POLICY_PRECISION_SUMMARY.csv`及`presentation/`：标准汇总与独立批次比较；
- 冻结main中的原时间记录及旧`local_audit/policy/FIXED_K_SUPPORT.csv.gz`：时间来源和原采用口径。

从完整本轮工作目录运行：

```bash
python report26/extract_policy32_evidence.py --base /path/to/population_extension_20261026
```

解释时沿用各表的支持：Q/T当前为115／94／72／117图；main原116／96／73／119图属于其原版本。不能把劳动比的正数误作费时，也不能将全支持不可估的路径区间替换成建筑区间。
