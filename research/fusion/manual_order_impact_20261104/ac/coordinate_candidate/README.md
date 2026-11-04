# F2/F9坐标候选的AC影响：独立、未采用

此处只评估用户对pa4otMbVnkk-18 / R024552提出的坐标候选：F2与F9各自上下点x均为438.8037，其余坐标、节点、顺序、票数、团队及参考固定。候选多边形有效，B8L2为39.6156191876、D10为41.3057878224，但相机仍不在可见核内。它增加了人工坐标干预，未并入固定坐标的57组主分析。

该端点有50条AC方法事件引用：固定坐标分支的配对Q均缺失；坐标候选后44条可评，6条仍因另一端缺Q而不可评。12个池条件、558条主摘要行变化，保持原计权与原团队/方法分母。旧缺失Q没有按0计分。

|文件|内容|
|---|---|
|[CANDIDATE_AC_RECEIPT.json](CANDIDATE_AC_RECEIPT.json)|方法版本、未采用标志、50/44支持及几何条件|
|[EVENT_SUPPORT_BY_METRIC.csv](EVENT_SUPPORT_BY_METRIC.csv)|各指标有效支持，完整Q与底面分项分开|
|[EVENT_METRICS_FIXED_COORDINATES.csv.gz](EVENT_METRICS_FIXED_COORDINATES.csv.gz)|固定坐标主分支的50事件|
|[EVENT_METRICS_CANDIDATE.csv.gz](EVENT_METRICS_CANDIDATE.csv.gz)|独立坐标候选的50事件|
|[MAIN_SUMMARY_CHANGES_CANDIDATE_ONLY.csv.gz](MAIN_SUMMARY_CHANGES_CANDIDATE_ONLY.csv.gz)|仅坐标候选传播的主汇总变化|
|[BASELINE_PARITY.csv](BASELINE_PARITY.csv)|重算入口与固定坐标结果对齐|

主固定坐标AC的完整结论另见[上一层报告](../REPORT_ZH.md)。联盟的2条引用另见[联盟候选检查](../../alliances/coordinate_candidate/CHECKS.json)；两者合为52条引用，不能当作52个独立团队。
