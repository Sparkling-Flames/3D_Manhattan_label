# Pro／dot研究返回精选归档

2026-10-03。保存前三轮有用的报告、源码、数值、反例、图示与复现证据，供论文追溯；外部结论不是规范，也未将其源码接入正式Lee工具。最新解释以[本地审查](../../analysis_results/worker_review_20261003/REPORT.md)和[推进台账](../../docs/thesis_main/研究推进台账_20261003.md)为准。

| 阶段 | Pro | dot | 主要保留价值 |
|---|---|---|---|
| 质量方法 10/2 | [报告](quality_20261002/pro/REPORT_zh.md) | [独立审核](quality_20261002/dot/独立审核结论.md) | BEV与高度／体积职责、边界采样与对应、指标效度及独立反例 |
| Lee人数曲线 10/2 | [报告](lee_20261002/pro/REPORT_zh.md) | [曲线探索](lee_20261002/dot/lee-audit-exploration/REPORT_zh.md) | 旧16排列局限、精确子集、平票奇偶机制、解析面积与警告证据 |
| 人员构成 10/3 | [报告](worker_20261003/pro/REPORT_zh.md) | [总体审核](worker_20261003/dot/独立审核与人员组合探索.md) | 分组稳定性、质心敏感性、替换背景、面积分解与人数配对精度 |

人员阶段的补充入口：[dot替换探索](worker_20261003/dot/worker-audit-exploration/REPORT_zh.md)、[十图面积分解](worker_20261003/dot/worker-audit-risk/REPORT_zh.md)、[A线配对人数差](worker_20261003/dot/expanded_count_independent_20261003/REPORT_zh.md)。10/1更早的方法、源码及反例仍在[原归档](../layout_methods_review_20261001/README.md)，未复制。

## 当前采用与限制

- 保留BEV＋等权Lee基线、连续人员画像及组合研究。上下半是校准相对组，不是已证实的稳定类型；质心不因低相关自动加权。
- 面积误差分解、成对替换及超几何计算有研究价值，但分别限定为固定池描述、背景诊断和面积期望；不能冒充平均IoU、因果协同或增人稳定速度。
- 用户已确认人员不参考他人，重复坐标按独立标注保留；不合并或降权。原报告中“优先追溯独立性”的建议留作历史意见，不再作为当前前置条件。元数据和用户提供的采集前提分开记录。
- 质量阶段的来源摘录错误、验证器极小方向角失败、边界采样问题，Lee阶段的旧16排列及警告问题，均按对应原报告保留；不据旧批评否定后来已补强的数据。人员阶段新包身份已对齐。
- 本地完成哪些复核，以[本轮报告](../../analysis_results/worker_review_20261003/REPORT.md)为准，不将外部测试数量写成本地测试，也未作视觉GT裁决。

## 归档选择与运行方式

[ARCHIVE_SELECTION.json](ARCHIVE_SELECTION.json)记录335个保留文件（17,880,332字节）及444条省略记录；保留内容逐字节核对来源一致。该计数不包括本README与选择清单自身。三个Pro包完整保留；dot保留其新增研究证据，省略重复ZIP、输入／仓库镜像、同字节重复项及无关临时工件，省略原因和重复文件去向见清单。

这是精选证据归档，**不是所有子目录均可原位独立运行的发布包**。原报告、脚本及manifest未改写，内部路径可能指向原包中已省略的副本；原manifest描述原包，不描述本精选目录。不要为满足旧manifest在此重复打包。

已有输入与正式计算入口：

- [质量交接](../pro_quality_handoff_20261002/README.md)、[Lee首轮输入与源码](../lee_tile_stage1_20261002/README.md)。
- [A线136图固定输入](../../analysis_results/lee_expanded_20261003/input.json)、[B线24人×10图固定输入](../../analysis_results/worker_profiles_20261003/input.json)及[子集结果](../../analysis_results/worker_profiles_20261003/subsets.npz)。
- [本地审查复现入口](../../tools/thesis_main/analysis/audit_worker_returns_20261003.py)读取现有固定输入与本归档保存结果，另写新输出，不覆盖历史实验。

旧源码保留用于理解或复现相应阶段。需要运行外部原脚本时，根据其参数显式指向对应固定输入并使用新输出目录；已知验证缺口见本地报告，不自动升级为生产方法。

格式检查：外部CSV的CRLF及原始日志空白会触发Git空白提示，为保持证据字节一致不重排；本轮自写代码、文档及结果单独通过定向差异检查。
