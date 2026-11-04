# Q-only 第二次独立验收

结论：固定 208 事件、670 团队、五政策臂范围内，29/29 无连接机会全部覆盖且已评分；其余 3 条为节点不足。无需新人工排序、端点评分或新团队。

入口：[中文报告](REPORT_ZH.md)。机器回执：[CHECKS.json](CHECKS.json)。

|文件|用途|
|---|---|
|OPPORTUNITY_COVERAGE_BY_ARM.csv|按政策臂的需要处理分母与覆盖|
|ALL_1040_POLICY_OPPORTUNITIES.csv.gz|全部事件—政策机会，不只已处理端点|
|ALL_NO_CONNECTION_OPPORTUNITIES.csv|全部 29 条无连接引用及实际处理|
|REMAINING_NON_ORDER_FAILURES.csv|3 条节点不足，保持失败|
|20_7_DIFFERENT_SELECTION_ALL_FIVE_ARMS.csv|关键七事件的 35 条臂机会|
|20_7_DIFFERENT_SELECTION_EVENTS.csv|逐团队身份、成员和质量分项|
|INDEPENDENT_SUMMARY.csv|从冻结端点独立重派生的 380 条统计|
|SUPPORT_AND_WEIGHT_DECOMPOSITION.csv|原共同支持、新增事件、原图与新图的分解|
|EVENT_WEIGHT_CONTRIBUTIONS.csv.gz|精确层级权重；旧 Q 缺失仍缺失|
|NEWLY_PAIRED_Q_EVENTS.csv|新增配对事件及其团队和损失分项|
|IMAGE_INFLUENCE_DIAGNOSTIC.csv|留一图诊断，不替代正式支持|
|ADDITIONAL_HUMAN_REVIEW_QUEUE.csv|空队列，表头保留|
|INPUT_MANIFEST.csv|所有实际读取输入的 SHA-256|

仅增加验收和解释，原自动及前批人工辅助科学结果不覆盖。与前五批一起使用。
