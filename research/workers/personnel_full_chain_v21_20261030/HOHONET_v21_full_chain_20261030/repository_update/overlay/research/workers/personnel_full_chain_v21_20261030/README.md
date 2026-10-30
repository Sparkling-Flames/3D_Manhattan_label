# HOHONET v2.1人员全链路接续：研究交付与复现

以冻结提交 `13a7861334749805a86dc19e9ea79fcaa71020c0` 为输入，接续v2完整解释/用途链。用户尚未最终确定人员分类；TARGET K3/K2为工作分析对象，OPPJOINT用于联合画像，RFUSE用于反向融合响应。正式数据、参考、目标归属、人员/标注排除、难度标签和融合规则未改变。

## 入口

- [中文综合报告](REPORT_ZH.md)及[HTML报告](REPORT_ZH.html)。
- [完整交付原README](DELIVERY_README.md)：从交付根README保留导入，仓库此页只负责导航。
- [v2→v2.1全链路对照](stage06_synthesis/V2_TO_V21_CROSSWALK.csv)与[剩余缺口](stage06_synthesis/GAP_REGISTER.csv)。
- [v2.1发布说明](../../data/releases/v2.1/full_chain_downstream_20261030/README.md)。

|阶段|已完成的实际研究|直接入口|
|---|---|---|
|输入与冻结核对|当前提交、原始依赖、输入池与135项冻结引擎代码一致性|`stage00_intake/`|
|最新半队反例|197事件、最新21张对称非正，全部指标/状态联合36图；原答、端点、几何、票账、20/7背景|[阶段01](stage01_half_team/README.md)、[36图完整说明](stage01_half_team/ALL_36_CASES_ZH.md)|
|同房换人、个人与预测|旧ABC适用子集实际双视角效果、原与扩展直接关系、个人均值/历史/残差和多份同房历史|[阶段02](stage02_same_room/README.md)|
|同类近Q快慢×难度|原63对、当前105对及共同52对，表达/正确/劳动及成员建筑敏感性|[阶段03](stage03_speed_difficulty/README.md)|
|选队、停止与成本|Q/QT两种身份、25,826精确团队、124,924旧前缀定向更新、已有/从零历史成本|[阶段05](stage05_selection_stop/REPORT_ZH.md)、[复现](stage05_selection_stop/README.md)|
|综合与未决事项|支持范围、变化原因、采用说法及真正需要新设计/人工项|[全链路表](stage06_synthesis/V2_TO_V21_CROSSWALK.csv)|

## 身份与分母

v2冻结结果、旧团队固定重评、当前历史重选和新设计分别表达。普通Manual为主，Semi补充，OOS及其它合法空间单列。直接关系的旧`oos_pending`标志不自动改变当前图池资格；原设计完整层与无关系待定主层并列。缺Q不填0，原生失败、输出不可评和其它缺失分开；劳动只用合法同来源记录，不能作为并行等待时间。

本轮完成已有资料可回答的下游：半队机制、旧同房ABC实际效应、近Q快慢×难度、预测用途、选队/停止/历史成本。没有自动新增人员、房间或重新跑256自然曲线。当前标签下的新选队同房ABC、类别约束大池策略和最低跨楼历史采集成本需另立具体问题，不因本目录建立就标为完成。

## 导入与复现

本入口依赖同目录的`stage*`、`scripts/`、`source/`、`REPORT_ZH.md/html`。仅应用文档patch不会生成这些研究数据。交付包`repository_update/apply_update.py --repo <仓库> --study <完整交付根> --apply`会先检查7个原文档SHA256、补丁可应用性和所有新目录目标冲突，再导入实际研究文件并更新文档；交付根README保存为`DELIVERY_README.md`。不复制`repository_update`本身，避免递归。

各阶段README提供最小输入、代码、源表、精确事件和验证。应优先复用交付端点重聚合；完整源快照用于核查，不覆盖原仓库来源。若仓库目标文件已被并行线程更改，应用程序停止并列出冲突，保留其新版本，不自动强行覆盖。

本研究在可访问的冻结仓库快照上完成。交付时尚未写入用户`D:\Work\HOHONET`、提交/推送远端或完成研究台浏览器验收；实际应用另以应用回执为准。
