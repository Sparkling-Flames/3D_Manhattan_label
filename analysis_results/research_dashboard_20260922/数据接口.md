# 离线研究仪表盘

## 真实结果版（2026-09-22）

沿用原六模块模板；`connect_20260922.py`只投影明确交付的终审、独立审计、人员敏感性和同房结果，不调用分簇、训练、重放或几何拟合。输出 `analysis_results/research_dashboard_20260922/` 与同名 ZIP。索引与地图由主线程统一登记。

- 全部描述：3019份、259图、25人、22建筑；无辅助计算：2444份、240图。Semi538份43图描述，530份绑定可计算；不混入无辅助重放。
- 完整链接与直径约束二次亲近度候选明确选择。原N≥8的110图1940份中，单人簇作答515/537份；**最多3个、每个至少2人支持的簇覆盖≥90%**为27/23图。这不是任意数量重复支持簇的覆盖口径，也不是持续起点。
- 重放仅接入已计算的完整链接结果；80个顺序的完整汇总覆盖110图，单图可看预定编号1—3的前缀曲线与具体进入成员。新候选未计算完整持续起点，明确显示未计算。有限池不解释为多轮修订质量上限。
- 精选uNb-55、uNb-29、q9-02、uNb-06四张完整全景；共83份完整真人点集，两个方法视图共166个可核对点集入口。所有有效坐标、原始端点ID逐项核对当前responses；几何直接复用已计算Studio输出，不重新拟合。
- GT、HoHoNet、Bi、DINOv3、DA3、uLayout按覆盖审计版本分别展示；独立图片与四相位文件不混计，648模型池不加入259真人图计数。DA3同房316对仅为资产量，非可靠重建。
- 页面隐藏结构版的通用解释卡片，只保留数据、来源、必要范围／定义；答辩讲解另在主线程文档。

接口最小扩展：chart可选`group_by_image:false`，用于跨图片同系列散点／柱图，点击仍保留原图片身份；case坐标宽高定义显示坐标基准，允许同宽高比的高分辨率原图，发布时登记`source_image_size`。3D公共库及每案例图片共享，避免每个人重复携带相同图像。数值表保留原始精度。

接入命令与换数见源码目录README。机器审查入口为包内`INPUT_AUDIT.json`、`PRESENTATION_CHECKS.json`与`assets/data.js`。验证为`tests/test_research_dashboard.py`、`tests/test_research_dashboard_real.py`及两个`research_dashboard*_browser.cjs`；截图验收后清理。

最终验收时序：12项Python检查通过；真实包与最终ZIP在仓库外以file URL、offline模式完成浏览器检查，包含真实WebGL、全部成员、版本切换、Semi隔离和单位数值。这些检查均发生在主线程CUA拒绝访问之前。随后按主线程复核，仅把DA3标签明确为“全资产库”、把特征关系说明明确为“未接入当前版本”，并进行Python／静态／ZIP字节一致性检查，没有再次启动浏览器或截图。主线程已只读查看此前截图，全部临时截图及测试包交付前清理。数据和研究数值未因文字修正改变。

## 查看

将 ZIP 完整解压到任意目录，双击 `index.html`。阅读者无需网络、Python 或服务器。保留 `assets/`、`cases/`（如有）与入口的相对位置。推荐使用桌面版 Chrome 或 Edge。

首版发布 `structure-20260921` 只有六个模块的结构、定义与完整空状态；“—”不是零。全部统计图片可进入索引，只有精选案例附带图像、点集及已计算的 3D。没有精选资源时仍可查统计。

筛选由左到右联动，只列出当前上游筛选下实际存在的结果切片。切换上游条件会重新选择下游可用范围，当前范围始终完整显示。点击“明确选择另一组结果进行对照”后，主动选中另一切片；两组各用自己的坐标、单位和分母，不能据图形高度直接跨单位比较。

图表支持悬停、图例开关、拖拽缩放、滚轮缩放及双击恢复。展开底层表格可核对原始输入值、分母、成员和来源 ID。点击图片按钮或图上实点进入详情；缺失点不绘制，可从表格进入图片。详情继承原结果的筛选条件；“重置详情”恢复点集、叠加与缩放，顶部“重置筛选”恢复本次发布首个范围。Esc 关闭详情。

全景可放大并横向滚动，点号与坐标表使用同一个点集输入。A/B 叠加仅在明确选择后出现。3D 复用 Panorama Studio，只显示输入的原始重建／拟合；扰动输入独立标记。未接入几何时明确显示不可用，不在网页中重新拟合。来源标识为逻辑 ID，可在“定义与来源”查说明，不携带本机路径。

## 替换与打包（制作端）

页面与结果分离。分析线程按照下述接口提供结果 JSON；图片放在展示清单目录以内。打包只读取指定文件，不扫描或默认填入仓库研究结果。已有 `analysis_results/` 不是自动输入源；只有分析线程明确交付并在清单中指定的结果才会读取。

在仓库根目录执行（Python、Plotly 与 Pillow 使用本机已有环境；这些仅制作端需要）：

```powershell
python -m tools.thesis_main.analysis.research_dashboard.build --manifest tools/thesis_main/analysis/research_dashboard/empty_manifest.json --out analysis_results/research_dashboard_structure_20260921
```

生成独立目录和同名 ZIP。每次使用新的输出目录，避免旧版本文件残留或覆盖历史。发送整个 ZIP。后续更新不修改页面源码；重新打包后整体替换解压目录。只有 `assets/data.js` 且资源未变时也可替换，但正式发布始终建议发送完整新包，避免混用旧案例资源。

展示清单：

```json
{"schema_version":"research_dashboard_manifest_v1","release":"发布标识",
 "results":"results.json","selected_cases":[{"case_id":"案例ID","image":"images/图片.png"}]}
```

`results: null` 表示空壳发布，且不能选择案例。文件路径相对清单目录，不能逃出该目录。仅 PNG/JPEG。清单本身不进入交付包；结果中的远程 URL、Windows 绝对路径与非有限数值会被拒绝。未知字段、重复 ID、版本错配和悬空关联也会拒绝发布。

## 展示接口 v1

以下是展示层合同，不修改研究方法合同、资格、阈值或 SOP。所有数值、成员组成、持续阶段、预测与拆分由分析线程提供；网页不合计人数，不训练分类，不重算分簇，不选择阈值。

顶层必需字段：

| 字段 | 内容 |
|---|---|
| `schema_version` | 固定 `research_dashboard_v1` |
| `release` | 与展示清单严格一致的发布标识 |
| `versions`, `methods`, `classifications`, `sources` | 数组，每项为 `{id,label,description}`；分别说明数据版本、分簇方法、分类方案及来源 |
| `participants` | `{id,label}` 数组；成员引用使用此处 ID，可采用去身份化标识 |
| `images` | `{id,building,room,scene,source_ids}` 数组；涵盖全部统计图片，房间由上游人工分组确定 |
| `views` | 预计算的完整筛选切片，见下文 |
| `cases` | 带来源与上下文的案例描述；只有清单选中的案例及点集会进入发布包 |

每个 view：`id, version, condition, method, classification, building, room, image, image_ids, modules`。前四个筛选维度必须有值；后三个为空字符串表示上游明确提供的“全部”汇总，不是前端通配或自动合计。完整七维组合唯一。`image_ids` 是此切片的全部图片身份；指定单图时只能包含该图片。建筑／房间筛选非空时，图片必须匹配。

可用选项来自 view 的实际组合。要支持建筑、房间和单图逐级筛选，分析方需提供相应切片，包括需要展示的总体范围；前端不从单图数值推算房间或总体指标。聚合口径变化必须提供新切片，不能复用别的范围的分母。

`modules` 必須包含 `overview, annotation, stability, people, rooms, features` 六项。每项：`{status,note,metrics,charts,tables}`。未就绪模块的三个数组必须为空。

状态：`ready` 已接入；`pending` 待接入结果；`not_computed` 未计算；`insufficient` 人数不足；`not_met` 未达标；`unresolved` 判断未决；`not_applicable` 不适用。指标／图表行仅 `ready` 可有有限数值，其余状态的 `value` 必须为 `null`，图表不跨缺失段连线。如果未达标但有可展示测量值，用独立 ready 测量指标及状态说明表表达，不把状态替代数值。

**metrics**：每项 `{label,value,unit,status,definition,denominator,source_ids,member_ids}`。`denominator` 是正数或 `null`（非比率指标）；`definition` 明确实际人数、覆盖、有效作答、计量及范围口径。成员可以为空数组，但存在的 ID 必须来自 participants，不能重复。

**charts**：每项 `{id,title,kind,x_label,x_unit,y_label,unit,definition,rows}`。`kind` 为 `line/scatter/bar`。每行：`{x,value,status,series,image_id,numerator,denominator,member_ids,source_ids}`。`x` 是有限数或文字；同图同系列同 x 不得重复；总体 `image_id` 为空字符串。`numerator` 为非负数或 null，有值时必须有分母且不能大于分母（计数比例口径）；非比例值的分子与分母均可为 null。网页直接使用行值，不自动把分子／分母换算为百分比。单位和换算责任在分析方；浏览器测试核对输入与绘图、表格一致。

**tables**：每项 `{id,title,columns,rows}`，可选 `replay: true`。columns 为 `{key,label,unit}` 数组，行字段必须与列完全一致。必须包含 `image_id,member_ids,source_ids` 列用于关联（总体 image_id 为空字符串）。任意分析细节可用其余列表达，如类别、配比、进入顺序、阶段、历史／预测身份、核验状态。只有显式 `replay: true` 的表才启用逐步显示；每行必须是分析方排好顺序的步骤，网页不重算。混合多条序列时先分成多张表。

**cases**：每项 `{id,image_id,version,condition,method,classification,pointset_version,source_ids,width,height,variants}`。必须匹配至少一个 view。宽高为实际图像像素。一个案例只属于一个版本／条件／方法／分类组合；跨方法对照使用另一结果切片，不能给当前案例偷偷加入其他方法。

每个 variant：`{id,name,kind,pointset_version,member_ids,source_ids,cluster_ids,pairs,connections}`。`kind` 为 `original/fit/perturbation`，显示原始重建／拟合展示／数值扰动；`cluster_ids` 是当前方法内的标签。`pairs` 每项为 `{source_pair_id,display_index,top:[x,y],bottom:[x,y]}`，display_index 连续从 1 开始；保留端点各自 x。connections 是 `[起点原始ID,终点原始ID]` 数组。坐标为原图像素，无隐式百分比换算；所有版本、成员、连接与边界均检查。

可选 `geometry` 和 `geometry_pointset_version` 接受上游已计算的 `panorama_studio_v1` 结果，其 pairs 必须逐值等于 variant.pairs，宽高和点集版本必须相同。Studio 的 3D 是闭环墙体视图，因此必须显式提供按 pairs 顺序闭合的 connections；任意非闭环点集仍可用 2D，但不能套用该 3D 组件。发布过程中不调用 `analyze()`；仅复用 Studio 的图片编码与浏览器渲染。

## 验证与边界

### 历史结果增补（2026-09-22）

`research_dashboard/history.py`由现有接入入口调用，只读取已保存结果；不重训分类、不重算分簇、不选择阈值。历史数据通过独立版本显式切换，模块上方提供版本入口；不能与当前25人、2444份计算池合为一个版本。历史全局表不重复挂到当前单图筛选中，逐图记录可从表内图片按钮或图片索引查看。超过100行的表支持本地搜索、分页，全部记录仍在离线数据包内。

最短查看路径：先进入左侧“人员与组成”，展开“其他数据版本”，点“历史09-10”按钮，即到共同39图粗分／快慢比较；点“历史09-21 · 终审前2393份”按钮，即到Q_2完整链接的全部上限与同人数对照。其他Ward配置再通过“条件→分簇方法→分类方案”选择。查看“同房与同场景”时切历史09-21，在“条件”中选持续起点或同场景跨建筑；查看“图片特征与难度”时切“独立审查研究”，读修正预测。点击“一键重置”回当前版本。上述是导航说明，不是分类推荐。

人员分类对照入口：在“人员与组成”点击“人员分类对照 · 历史09-21（新分区尚未复验）”。固定profile=4（总簇数≤3、单人作答≤20%）列出Q_2历史子类1、QT_2历史子类1及QT_3历史子类2，以及各自图片／建筑／实际H面板、成对差值和探索区间；分簇方法可明确切换历史完整链接与历史真实代表半径。下方保留Q_2全部六种上限。数值从已有切片投影，不训练或重算。图中的比例为建筑等权的稳定顺序比例，图片数不是该比例的简单分母，各面板不能直接排名。

共享x重分析接入：供数完成后，打包入口增加 `--shared-x analysis_results/shared_x_reanalysis_20260922`；适配器 `shared_x.py` 要求MANIFEST状态complete、亲近度求解认证与原始完整链接重放核验通过，否则拒绝发布。原始有效点／共享x与完整链接／全局亲近度形成独立版本内的四条件，入口仅在已接入时出现。旧版本和历史人员分类保留；新版本人员分类未复验显示未计算。

该接口读取MANIFEST、views、point_processing、pointsets、endpoint_per_image、memberships、orders、replay_per_image/summary/prefixes、room_predictions/summary/method_comparison/error_attribution。点处理审计区分预测池、人工保留、绑定未定及条件绑定；所有已有可绑定角对采用上游共享x结果，不用0.2决定是否处理，页面不计算周期均值。7036保留但不加入原预测池。仅精选清单携带新点集，保留上游点号和环连接；新点集不复用旧geometry，无3D时明确不可用。人数起点与同房终点结构预测分开；未识别起点为空，区间与比例按来源定义显示。正式计算完成通知前不更新交付包。

诊断文件DIAGNOSTIC_CHECKS与dominant_tail_per_image/summary也必须齐全。同一J3/m2/h3下并列80%和90%覆盖要求；所有h3/5及支持条件仍保留在表内。最大簇、完整簇规模、单人尾部与重复支持覆盖分别呈现，最大簇≥80%仅为描述探针，不定为最终阈值。`no_anchor_room`表示后续观察空间不足，相关顺序比例留空；`no_onset_under_rule`表示观察内未识别该判据起点，不写成普遍不收敛。通过“主簇与零散尾部 · 查看示例图”可进入供数指定图片，数字全部读取正式表，不硬编码。前缀仅在逐图切片显示固定编号1—3顺序，避免将全量80顺序重复携入所有切片。

对照页的“分类详情与历史版本”选择器可进入Q、QT、T、S、B、QB及联合方案，保留成员、覆盖、缺失和各自历史检验。S是scope误接受／误拒绝；B含参考净改善时不是无参考分类。名单重复性、质量预测和子类稳定不可混用；人员分组与标注分簇、质量筛选分开。终审前2393份结果不代表最新2444份加全局亲近度分区已经复验，不构成人员排除依据。

| 独立版本 | 来源与展示范围 |
|---|---|
| 09-04 H/L/U | `worker_manual_strata_audit_20260904_v1/manual_core_full_profiles.csv`及`manual_worker_calculation_simple.csv`：两个旧版本的20人证据分档、逐人支持和跨11楼稳定性；U是未定。仅接旧名册证据，不复用旧资格／独立性解释。 |
| 09-09 单维分类索引 | `worker_reference_feasibility_20260909_v1/pooled/groups/README_ZH.md`：OSPA30/60人员效应的quantile／Ward 2–5组索引，不接完整旧预测表。 |
| 09-10 26／20人 | `worker_four_block_exploration_20260910_v1`：303套Ward配置、全量成员与轴含义、主要求／诊断名单重复性、训练分类可用性、人数不足覆盖。`subtype_stage_validation`保留q95与OSPA30≤6两个判据；主展示沿旧报告H=8/10/13、k=H−5、可评分参考图，含逐图L/U和具体抽样池。L/U不是置信区间。全部其他H、起点及面板仍在原分析目录，不声称全量迁移。另列质量中位数粗分／快慢共同39图、4图稳定多簇的243条重复引用。 |
| 09-21 终审前严格池 | `new_manual_analysis_20260921/convergence_and_composition`：240图2393份；六套留建筑分类、两种旧方法、全部7上限、具体成员与同H对照、所有保存的四人配比和87725真实团队。后者是重叠团队，不是独立样本。持续起点保留逐图状态和近均分827拆分的可评价计数，分开中位起点与组均值曲线。父目录`room_scene_summary.json`和`scene_predictions.json`另列跨建筑同场景负结果及来源。 |
| 09-21 独立审查 | `panorama_research_received_20260921`：只用`audit/independent_checks.json`与`outer_fold_corrected_model_predictions.csv`的修正特征预测，三个目标分列。已复核原结果用于同配比换人波动、连续画像、持续起点删失、局部读数与条件性3D代理计数；不载入原隔离错误预测。 |

质量中位数粗分、Ward自动Q二分、09-21的Q_2及更早Q_GT证据分档各自保留名称与版本。旧OSPA30分数不是像素或正确率。09-10旧人员身份单列`h0910:W*`，09-04单列`h0904:W*`，不将旧名册自动当作当前身份关联证据。历史图片未携带新的图像／点集／3D资源；现有4图完整案例保留当前版本绑定。

本次验证使用Python接口／真实结果投影测试、Node渲染函数桩检查分页搜索、静态依赖及ZIP逐文件一致性。此前浏览器URL访问被策略拒绝，因此本次未运行任何浏览器或截图自动化；旧浏览器验收只属于旧包，不能作为这些新增视图的视觉验收。没有生成新截图。正式研究方法、原始导出、时间日志及当前结果数值不变；没有改索引、状态页或汇报稿，地图登记由汇报主任务统一处理。

`tests/test_research_dashboard.py` 验证接口、两版替换和拒绝错配；`tests/research_dashboard_browser.cjs` 在仓库外用 file URL、断网浏览器、笔记本／投屏尺寸检查 UI、Plotly 数值、筛选、详情与资源。测试样本仅写入临时目录，不进入导师包。临时截图由验收后删除。

统计学正确性、真实输入的单位换算和来源完整性仍须在新结果接入时核验；结构版不代表已有研究结论。正式协议、原始标注、分发与权限均不变。

## 结构版交付记录（2026-09-21）

- 新增独立打包器、六模块模板、展示接口、空清单和定向测试；Studio 源码未修改。
- `python -m pytest tests/test_research_dashboard.py -q`：11 项通过，覆盖两版替换、schema drift、空值、来源／成员／版本、点号与发布资源边界。
- `node tests/research_dashboard_browser.cjs <测试包临时目录>`：通过。使用仓库外 file URL、浏览器 offline 模式，检查全部模块、两套方案与数值、图例／悬停／缩放、表格、成员、空搜索、筛选、明确对照、无图片、无 3D、真实 WebGL、点号、接缝连线和逐步重放；无远程请求与页面错误。
- 视觉检查：1366×900 笔记本、1920×1080 投屏；另检查 800px 宽度无页面横向溢出。浏览器测试使用软件 WebGL；真实设备 GPU 性能未作基准测试。
- 项目地图与 README 索引已登记，`.gitignore` 放行展示接口文档。正式协议、资格、阈值、分类及研究计算均未改变；不涉及 Label Studio 运营写入。
- 未运行无关的全仓库统计与模型测试：本轮未修改相关实现。真实新结果的统计口径、单位换算与来源核验留待分析线程交付后逐项检查。
- 临时合成包仅用于接口验收，导师结构包不包含这些数据；临时检查截图在交付前清理。
