# 来源与版本边界

固定提交 bba3dc7c9a79b8342ecb4ce2487affe41886eb56；主入口 research/pro_quality_handoff_20261002。

最终核对的源码 tools/thesis_main/analysis/layout_3d_quality_probe_20261002.py：Git blob 9922ebfc2d08b072575c4dd0f82ff86824d3d359。height_stats对每条边的线性墙高积分：mean=sum(length*(h_i+h_j)/2)/sum(length)；RMS对线性高度的平方偏差解析积分；model_volume采用该mean作为水平顶面模型高度。此源码没有执行角点等权高度拟合，也没有新增真实整墙对应距离。

当前REPORT.md：blob bc9c4151e9ce9b65c97fef6e7b02d5047dec9a1b。报告195作答、390参考版本行、117缺参考；134人工确认、48默认x、13不可用；182原始GT可比较。17改序来自两张定向图。这些全量数值是读取的源报告，不是本包重新跑出的结果。

当前metrics.csv：blob a473dcc8f7291cb1d824d116df47fb36a5cd847e。读取前13行，转录其6份原始GT数值到inputs/read_upstream_csv_subset.csv。身份摘录与完整源绑定仍不可等同。

此前Pro/dot：research/layout_methods_review_20261001/dot/独立审核结论.md。dot报告复跑了上一返回包与74/15/9原数值，并指出路径方向、均值/覆盖的节点密度、并列最优映射计数三项问题。本次没有重复dot的完整复跑；没有沿用该局部路径实现作为质量主指标。

重要更正：过程中曾将“顶点等权拟合”误归因给当前实现；最终核对和交付已纠正。该方法仅作为探索性反例，不代表当前源码缺陷。当前周长均高的共线细分不变性得到本轮计算支持。
