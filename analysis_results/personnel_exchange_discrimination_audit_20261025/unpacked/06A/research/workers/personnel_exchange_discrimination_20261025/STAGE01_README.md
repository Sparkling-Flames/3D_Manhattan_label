# HOHONET 大块换类区分度续研：阶段01

日期：2026-10-25。读取 main：972857b2b3f548316be215400e42d6ef6e639250；底层数据真人v2。

已完成：20个新增/简单对照分类配置的ALL及22栋楼外标签，原始历史特征、类别成员与中心、难度分层及跨条件输入、scope回答倾向与机会台账。另冻结7个既有分类对照；全部27种方案进入同一首轮设计。

范围：主评价为普通Manual。建类可用Manual与Semi历史；每折同时排除目标建筑两条件。scope为回答倾向，不称正确率。286条旧oos问答从精确历史恢复，仅进入派生特征，不修改v2评分、资格或融合。

实验：A=D+X，B=D+Y，C=D+Z；X/Y同源类，Z目标类，四块互斥。实际换人数m相同，比较|B-A|与(|C-A|+|C-B|)/2，并保留有符号CA/CB/BA。n/m为10/7、12/8、12/10、14/9、16/8、17/9、18/7、20/6、24/5。严格容量不足的配置留在尝试账。

首轮：预选12栋楼、52张图片；49图有可行事件。69,948个方案/方向/n/m/图格中5,709可行，生成22,830个实际事件、68,009个去重端点。每格2个实际XYZ块，D中目标类人数取可行低、中、高层，每层抽1背景。所有成员与背景空间总数另列；这是有限均衡搜索，不是全池成员穷尽。

本阶段尚无新换类效果结论；融合正在计算，结果将另批保存。标签形成与本轮结果选型分开。v2是多轮使用的内部数据，后续检查不宣称全新外部盲测。

## 文件入口

- classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz：20个本轮配置全部标签。
- classifications/*CLASS_DEFINITIONS*：逐折成员与历史中心；AXIS_CANDIDATE_REGISTRY保存阈值/投影。
- features/HISTORY_FEATURES_ALL_LOBO.csv.gz：全部历史特征及支持。
- features_scope/README.md：scope范围、来源、286条恢复与未知状态。
- design/screen/EVENTS_EXACT.csv.gz：精确ABC及DXYZ、类别人数向量与规模。
- design/screen/REQUESTS.json.gz：唯一团队成员请求。
- design/screen/CAPACITY_AND_ATTEMPTS.csv.gz：全部尝试、不可行格、精确有限空间。
- design/screen/IMAGE_PHASE_ASSIGNMENT.csv：本轮选型及后续楼/图检查的预先划分。
- register_exchange.py、run_native.py：实际注册与冻结引擎调用代码。

冻结融合代码引用同一main下research/same_room/same_room_large_block_rebuilt_20261023/engine/frozen_repo；仅复用其封存运行依赖，没有重开同房研究。必要既有输入引用见stage00/SOURCE.json和classifications/BUILD_RECEIPT.json；首轮12模型的BUILD_RECEIPT保留其原阶段身份，完整scope增量已在scope清单中追加。
