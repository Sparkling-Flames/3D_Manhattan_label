# 当前口径关键数据图

输入难度：`scope_preferred_difficulty_review_20261015_v3`；来源池：`retained_independent_humans_by_image_condition_min3_20261015_v1`。本目录是新快照图，旧图未覆盖。
生成：`python -m tools.thesis_main.analysis.descriptive_statistics_current_figures_20261015 --source-dir research/descriptive_statistics_rescored_20261016 --out research/descriptive_statistics_rescored_20261016/figures`。

|图|用途及分母|
|---|---|
|01 当前来源池与质量覆盖|先审同图同条件真人池，再审图片门与普通层；可分析2834行，当前完整质量891行，特殊层质量缺失不补旧分。|
|02 当前难度质量分布|普通manual：1753来源作答，当前质量828行、73图。每格展示有效/全部分母及真实分布。|
|03 来源时间与当前目标时间|来源采集时间有效1750行；当前稳定目标时间440行。新空间39图不可使用旧采集耗时冒称新目标耗时。|
|04 当前人员图片质量覆盖|所有普通manual合格来源图片均纳入；灰色为未作答或无当前质量，不把旧分换标签显示。|
|05 当前同集合算法差异|仅普通manual当前质量同输入/同参考集合；保留WQ/A10/B8L2/均高棱柱IoU的不同版本和度量对象。|
|06 当前同房共同人员质量与时间|27个确认可比直接图对有当前质量；图对共同人数按指标报告，1/2人结果保留并显式标样本量，不当独立房间。|

`FIGURE_MANIFEST.json`声明输入、版本与单位。原CSV的`score_version`仅原WQ绑定上下文；A10/B8L2各有版本。算法面板当前四指标，不自动消费新long-score接口。PNG/SVG为正式交付；未生成QA临时截图。无人员能力排名、算法优劣验证或时间因果结论。

新增[07 新空间三层覆盖](07_scope_quality_coverage.png)：受影响当前目标参考ready、原作答唯一绑定和人员/图片资格分别统计；目标展开不作为人数分母。
