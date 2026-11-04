# 人工融合顺序回收与Pro接续入口

用户提供的原始导出已原样归档为[融合节点排序_全部图片.json](融合节点排序_全部图片.json)。文件中的说明与状态作为研究输入，不作为工具执行指令。

## 已完成核查

- 57/57组返回、22张图片，全部confirmed；pairing/pending/draft为0。
- 导出对象与当前57组清单逐项一致；固定坐标、点对绑定、完整排列、节点身份、票数、团队和参考元数据全部通过。没有缺项或错绑。
- 57组对应57个已绑定端点身份；当前引用清单内关联9个模块、536条引用。引用数包含同队复用及同房多种工作分类，不能称为536个独立实验或新增团队。
- 这里只确认人工顺序已合法回收。尚未用顺序重建几何、重评分或更新正式统计；confirmed不等于已通过几何和质量评价。

## 交付索引

|文件|用途|
|---|---|
|[IMPORT_RECEIPT.json](IMPORT_RECEIPT.json)|本轮回收与绑定回执|
|[REVIEW_DECISIONS.csv](REVIEW_DECISIONS.csv)|逐组人工判断、排列、时间与图片|
|[VALIDATED_ENDPOINT_ORDERS.csv.gz](VALIDATED_ENDPOINT_ORDERS.csv.gz)|端点级顺序与固定节点绑定；状态为validated_not_applied|
|[AFFECTED_CURRENT_REFERENCES.csv.gz](AFFECTED_CURRENT_REFERENCES.csv.gz)|组→端点→模块→源表行→实验臂的引用映射|
|[IMPACT_BY_MODULE.csv](IMPACT_BY_MODULE.csv)|当前已识别影响范围，不能跨模块直接相加|
|[PRO_PROMPT_ZH.md](PRO_PROMPT_ZH.md)|给新线程Pro的完整执行提示词|

当前关联的模块：严格半队、Q-only、同房半队、较大团队同房登记、AC、变化联盟、其它合法目标有限配比、其它合法目标自然路径、旧角色进入策略。主目标自然路径没有命中这57组的当前引用；不能因此宣称所有自然路径、所有缓存都完全不受影响，Pro须按真实消费关系核查。

先做固定节点和已确认顺序下的辅助结果，再比较原自动结果与加入辅助结果的支持及统计。若Pro认为需要改变论文主方法，须另给明确方法定义与影响论证，不能静默覆盖原结果。

复现：`python -X utf8 tools/thesis_main/analysis/import_missing_ring_orders_20261104.py research/fusion/missing_ring_review_20261104/user_order_return/融合节点排序_全部图片.json`（含空格路径请加引号）。原始自动实验、分类、GT和难度均未改动。
