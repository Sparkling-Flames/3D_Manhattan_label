# v2.1 直接AC、完整类别组合与整类替换归档

归档日期：2026-10-30。13个正式AC科研包已接入本目录：7,772条包内文件记录，7,760个实际文件。ZIP成员已按包内CRC、目标路径和长度核验；ZIP本体不纳入仓库。相同内容复用，有差异的早期`code/package_stage.py`保存在`source_variants/`。云端[来源映射](SOURCE_PATH_MAP.csv)仅列仓库内文件；高清原图、嵌入原图的四个查看器及其字体只保留在本机，另记于被Git忽略的`SOURCE_PATH_MAP_LOCAL.csv`。本机查看入口见被忽略的`README_LOCAL.md`。没有再次计算整套融合或重新选择分类。

研究采用TARGET_DSTRUCT K3结构主分类、K2粗层；OPPJOINT联合画像与配比，RFUSE反向融合响应，RAW3特征及较大块补充。分类依据、人员名单、原答、团队与结果按同一版本连接；v2冻结研究保留原身份。

## 先看成果

- [新增离线研究页](../../statistics/research_explorer_v1_r2_20261017/v21-population-study.html)：分类名单→七组合→固定人数与整类AC→严格ABC→背景与同房。
- [v2.1独立讲解材料](../../../docs/thesis_main/研究讲解_v2.1_人群构成与共识_20261030.md)：研究主线、与v2的变化及可直接引用的结果。
- [独立审查](../personnel_ac_review_20261030/README.md)：12,410候选组合成员、42,656个Manual组合对照、83,326含Semi的组合事件关联、四个主条件及28个原生案例端点的实际核对范围。
- [作者完整报告](stage08_report/HOHONET_v21_AC_population_report_ZH.md)及[自包含HTML](stage08_report/HOHONET_v21_AC_population_report_ZH.html)：全部方向、分项、几何、劳动、状态、三段与敏感性结果。作者的全面统计与本地独立核验范围分别记录。
- [pa4-11现有范围规则回查](SCOPE_PA4_11.md)：四角目标已获确认；八角原答没有被裁切，也没有被自动另立合法目标。

## 当前结论

TARGET中结构→高结构的直接20/7，85图中78图平均Q提高，图均+4.576分；固定20人、整目标类换入，185图中155图提高，图均+3.615分，实际每图替换1–8人。OPPJOINT20/10则42图提高、40图下降，均值+0.297分、平均绝对变化3.282分。正向、负向及双向变化共同说明人群构成会改变输出。

固定TARGET20/7的替换块与背景类别人数，改变背景的具体成员，85图平均绝对效果差4.564分。类别配比说明部分变化，具体人员仍重要。完整类别组合直接合并原始标注重新融合；它改变人数和类别集合，与固定n的配比实验分开。

严格ABC仍承担“跨类幅度大于同类”的比较；新直接AC没有B队。主展示先用TARGET14/7半队ABC，再用新20/7、整类和七组合扩展实际人群情境。不同实验的同一个n/m不等于相同团队。

## 来源层次与可追溯入口

|层次|路径|可回答的问题|
|---|---|---|
|当前楼外标签与来源|`stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz`、`CURRENT_INPUT_COMPATIBILITY.json`|谁属于哪类、历史来自何处；ALL仅作描述|
|真实容量与类并集|`stage01_capacity/ALL_CLASS_ALLIANCE_TEAMS.csv.gz`、`ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz`|每图每类哪些人可用、七组合的精确成员|
|冻结设计|`stage01_registered/AC_EVENTS.csv.gz`、`DESIGN_LINKS.csv.gz`|事件、方向、背景、成员、目标、n/m及重复设计链接|
|完整原生输出|`stage03_endpoints/pools/<pool_id>/part_*.jsonl.gz`|成员、原答ID、参考、几何、分数和实际输出状态|
|逐事件全部指标|`stage04_metrics/metric_shards/<pool_id>.csv.gz`|Q/D10、分项、两队几何距离、劳动来源及各指标分母|
|主效果与上下文|`stage05_main/`、`stage05_context_common/`|逐池/图/楼与条件、难度/共同条件、微变和抵消|
|严格ABC衔接|`stage05_funnel_bridge/`|容量漏斗、共同支持与旧严格对照，不把AC改名ABC|
|成员、背景、人数与整类|`stage05_sensitivity/`|同配比换具体人、固定块改变背景、扩大m、完整联盟与三段路径|
|机制与原答|[云端案例入口](stage06_cases/README_CLOUD_ZH.md)|9图、32个唯一trace团队、51展示事件；逐图结果、全部原答、未选组及连接账；高清原图和查看器仅本机保留|
|复现|[最小来源说明](stage07_reproduction/README_ZH.md)、`code/`|既有冻结引擎与完整输入；不用下载目录或重复拼接几何总文件|

数据计数以作者保存的执行会计为准：478,012支唯一团队、471,758条方法事件、412,839个不同无向物理AC端点对、550,794条设计链接。它们不是四套可相加样本。本地本轮只接入并核对展示所需关联，没有独立重跑这些全部端点。

## 复现路径与本地检查

独立审查入口现通过本目录`SOURCE_PATH_MAP.csv`读取原包对应版本，移除Downloads依赖：

```powershell
python -X utf8 tools/thesis_main/analysis/audit_ac_population_questions_20261030.py
python -X utf8 -m tools.thesis_main.analysis.build_v21_ac_workbench_20261030
```

第一条会重做既有定向统计审查，正常阅读无须重复运行。本轮仅修改读取路径并验证映射/读表，既有科学审查结果原样保留。第二条生成新页面数据，四条件Q/D10均值与独立主表逐项一致。

作者最小复现代码的根目录已按脚本位置解析；冻结计划保留原执行路径，未来需要运行时使用作者提供的`code/relocate_frozen_plan.py`另存搬迁计划。不要修改原计划或用当前默认建池覆盖冻结快照。`code/reproduce_one_team.py --help`可读取用法；本轮不重复调用原生融合。

|检查|本轮状态|
|---|---|
|安全解压、文件存在、重复/版本保留|通过；读取ZIP时执行格式自带CRC，无额外SHA校验|
|四条件展示与独立Q/D10主表|通过，388条多指标展示行，28条七组合行|
|最终标签同房、旧ABC适用性、成员敏感性|前轮已完成，见[最终分类下游](../../data/releases/v2.1/final_classification_downstream/README.md)|
|原答距离与半队诊断|前轮已恢复134,197对；见[原答差异](../personnel_v21_reselection_20261029/raw_similarity/RAW_ANSWER_SIMILARITY_ZH.md)和[半队入口](../../data/releases/v2.1/simulated_population_evidence/exchange/README.md)|
|页面交互逻辑与本地链接|通过程序检查；结果记录见[接入回执](WORKBENCH_CHECKS.json)|
|真实浏览器|未完成；工具安全策略拒绝本地文件访问，未绕过限制|
|原生全量融合、全量几何/三段独立复算|本轮未重复执行；作者结果保留来源身份|

本地接入检查记录见[LOCAL_INTEGRATION_CHECKS.json](LOCAL_INTEGRATION_CHECKS.json)：3项Python定向测试、页面条件/指标/图片/楼外折切换的Node检查通过；7,772条来源路径及长度、49处新文档链接均通过。目录核验为708项资料。这里的程序检查不替代真实浏览器操作。

## 后续写作与研究台交接

新版主入口为`v21-population-study.html`；旧`v21-reselection.html`保留前轮32条件、完整45法配比及成员页，并链接新版。本轮不覆盖旧页面数据或并行门洞页面。新页提供方法/楼外折、七组合实例、条件/指标筛选，带全部源表下载和完整原答查看器链接。

真正尚缺的不是更大的全库实验：一是新页面及导入查看器的本地真实浏览器验收；二是若论文要对VFua-07、wc2-53或S9-04的具体墙体作语义裁定，应使用[已有原图与问题表](stage06_cases/README_CASES_ZH.md)。pa4-11的当前目标已有明确记录，仅在用户希望新增八角合法目标时才需要新的人工裁定。新分类选队的同房严格ABC及大池进入策略尚未新建，现有同房重聚合和历史V3策略分别报告即可。

论文提纲只提供[改动方案](../../../docs/thesis_main/论文提纲改动方案_v2.1_20261030.md)，不修改原Word。全局CURRENT、参考、人员资格、难度、协议和融合规则均保持。
