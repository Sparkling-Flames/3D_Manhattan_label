# 全景标注研究台 · 当前v2，v1 r2历史保留

2026-10-19：默认v2，已接10439作答、7302正式质量及完整综合统计/证据接口。当前方法与限制见[总说明](../../../docs/thesis_main/v2数据研究台与Pro推进_20261019.md)。切换版本不会混合分母；v1已有融合及簇实验仍为历史。

## 2026-10-20 接续接入

本次只读接入 17 张新表：7 张同房多视角、2 张人员、8 张融合与独立审计；v2 共 87 张表。人员画像、融合过程、同房比较新增对应页签，研究概览补充 4 条含支持范围和反例的接续结论。评分、资格、参考、正式人员标签、N1 及快照保持不变，接入不重算研究数值。

来源包：[角点补充与人员工作标签](../../workers/personnel_interchangeability_followup_20261020/README.md)、[类别块与角点](../../workers/personnel_composition_followup_20261019/README.md)、[独立审查与复算](../personnel_interchangeability_audit_20261020/README.md)、[同房多视角重放](../../same_room/same_room_multiview_20261020/README.md)；[人员可互换性 Pro 包](../../workers/personnel_interchangeability_20261020/README_ZH.md)仅增加报告入口。表格来源可由索引中的 `tables[].path` 追溯。

工作标签仅作 Rnew2/F01 研究参照，不能称同类任意换人曲线不变；类别块均值差受尾部事件驱动。同房面板覆盖 9 个关系组、44 图、7 栋，G057 两视角掉点、G046/G178 低平台，未知同建筑关系不等于异房，人员类型尚未接入该面板。独立审计仍保留未全量重跑、未全部重训与压缩 SHA 差异的边界。

逐次明细及大表 `replay_nodes.csv.gz`、`mean_predictions.csv.gz`、`individual_*_predictions.csv.gz`、`splits.csv.gz` 留在源包。仓库根运行 `python -m tools.thesis_main.analysis.build_research_workbench_v2_20261019` 重建离线页面，生成的 `v2-data/`、`v2-resources/` 仅留本地。显示清单见 [DISPLAY_TABLES_20261020.json](DISPLAY_TABLES_20261020.json)，验收回执见 [INTEGRATION_20261020.json](INTEGRATION_20261020.json)。

## v2离线构建

main中的匿名审计 `records.json.gz`、综合 `tables.json.gz` 和 `pro_personnel_v2_20261019/analysis_context.json.gz` 已足够生成v2研究台。仓库根运行：

```powershell
python -m tools.thesis_main.analysis.build_research_workbench_v2_20261019
```

双击 `index.html` 即可，JSON/JS分片支持file协议。生成的 `v2-data/`、`v2-resources/` 留本地，不重复提交大体积展开载荷。原图直接读取仓库内 `data/mp3d_layout/{valid,test}/img/*.png`（648 张，按[图片清单](../../workers/pro_personnel_v2_20261019/IMAGE_INDEX.csv)映射）；解析兼容分析上下文中的 Windows 风格 `source_path`（`.\data\...`），2 张未列入旧 Release 清单的图片使用仓库预览。搬迁或仅发布 HTML 时需保留 `data/` 目录与相邻前端目录。浏览器验收临时HTTP不属于运行依赖。

当前作答页支持原始点/本轮处理前散点、冻结终稿、实际参考、ERP/BEV/3D及有绑定证据的旧Semi初始图层。未确认环序不冒称已人工确认；新Semi缺初始坐标不画假初始化。scope只计语义相容裁定机会，图级OOS不作个人gold。

## 2026-10-19 同房预测接入

同房模块首个页签现为“v2预测与人数曲线”，可查看报告原图、按来源/预测模式/人数/方法筛选汇总、逐建筑增益、逐人预测及双视角几何、门洞与不支持模型折。来源：[同房首轮报告](../../same_room/same_room_v2_prediction_20261019/README.md)。运行上方同一构建命令即可更新；不用单独服务器。

消费 `CONSUMER_INTERFACE.json` 与 `FIELD_CONTRACT.json`，逐字段核对后打包13张原始表，数值与缺失原样保留；只给带图对的行补 `condition=manual`，给有向预测补 `image_a=source_image` / `image_b=target_image` 以复用几何入口。预测行锁定对应人员，避免显示另一人的标注。未改原始分析表或正式schema。

123对/64图/12栋是普通场景质量描述；人数曲线为固定30对/39图/10栋/35名新增人员；k指源视角其他人员数，排除被预测者，不是融合人数。报告图固定显示原面板，不随明细筛选重算；T预测误差为log(1+秒数)。门洞仅描述，OOS排除，人员类型尚未纳入，未有确认异房匹配对照。旧同房表及v1保留原快照。

接入核查：8项定向Python测试通过；从逐次预测独立重聚合48个汇总单元，与原结果一致，13张消费表行数一致。临时HTTP浏览器检查通过：固定人数筛选、D10、来源耗时单位、对应人员双视角、B8门洞6对、v1五个历史页签及两张报告图。浏览器截图仅内存查看，临时服务检查后关闭；file协议沿用原JS载荷方式，本轮未单独完成file浏览器验收。未重拟合预测模型、重评分或重算融合。

以下为v1及早期阶段记录，历史分母和待办不代表当前v2状态。

# 全景标注研究工作台 · 数据v1 / 消费r2

2026-10-18最新：图片标签采用uNb9QFRL6hY-01中等修订；r2聚合统计仍保留旧快照。Semi、scope等新分类想法仅记录于[讨论文档](../../../docs/thesis_main/人员分类与作答分簇讨论记录_20261018.md)，尚未执行新分类。

**同日扩大人数：** [personnel_exchangeability.html](personnel_exchangeability.html)查看6／8／12／16人的同背景单人替换（3840请求、2560对），支持高Q快筛选、实际个人作答与融合并排、共同背景链曲线和另一背景复核。[交付／构建／字段](EXCHANGEABILITY_HANDOFF_20261018.md)。原4人页已加入用户返回的6条判断，不改旧分数或团队。

**2026-10-18新增真实人员细分类页：** 双击[personnel_composition.html](personnel_composition.html)，浏览Q2/QT4/Q3的8图、528请求及6组复审实例；读取本轮实际几何，不依赖HTTP。旧index的109表保留r2快照。页面构建命令为 `python -m tools.thesis_main.analysis.build_worker_composition_view_20261018`；字段与验证见[本轮展示交付](PERSONNEL_HANDOFF_20261018.md)，研究解释见[人员包](../../workers/worker_fine_composition_20261018/README.md)。

2026-10-18人员口径澄清：菜单“Scope裁定覆盖”展示机会数，另可打开已有“历史Scope结局”表；不是最新全量OOS正确率。人员栏说明原尺度Q与任务调整Q，机会字段补中文释义。仅修展示命名和已有表入口，109表的统计值与快照不变。依据见[人员与几何独立复核](../../../docs/thesis_main/人员质量口径与几何Pro复核_20261018.md)。

## 当前入口：十模块离线工作台（2026-10-17重构）

直接双击 `index.html`。默认进入数据探索；图片与空间、人员画像、个体质量、人员组合／真实人数过程、同房、Semi、覆盖和来源共用导航和上下文。旧概览文案不再作为主页。未完成研究或尚未适配的几何、图表有明确占位。

按[研究覆盖表](COVERAGE.md)验收；展示数据合同见[DISPLAY_CONTRACT.json](DISPLAY_CONTRACT.json)。当前109张源表、B8L2/D10、参考与资格均未改写。原图／BEV／3D读取现成坐标，融合只读取保存状态；28条几何绑定不匹配已隔离，记录仍可查。历史195表源码保留，本机其派生载荷尚未构建时显示缺失，不冒充当前数据。

首次或更新资源后，从仓库根目录执行：

```powershell
python -m tools.thesis_main.analysis.build_research_workbench_20261017
```

该命令打包现有261图及现有人数过程为 `workbench-data/` 本地JSON/JS分片，不重跑统计或融合；原图仍引用仓库资产，不复制全库。目录局部忽略。仅有消费JSON而缺少本地私有原图／保存几何时，保留记录并说明缺失。主数据仍按原r2构建／重放说明准备；此命令不代替原始研究构建。

版本入口由 `dataset-config.js` 配置；该历史阶段v2尚不可选（现已接入，见本文开头）。换数据源将重载并重置筛选，笔记以快照分开。离线页面只展示构建时核对的上游状态，不声称实时最新。补人计划只读。

旧 `explorer.html?revision=v1r2` 链接自动进入统一工作台；`legacy` 参数仅保留排查旧r2前端的入口。旧195表另有自身来源；缺少其派生数据时仍明确报缺失。

以下为此前阶段的构建与验收记录，保留历史身份；当前功能与边界以上方覆盖表为准。

本入口与[旧195表浏览台](../research_explorer_20261017/README.md)并存。旧包固定Git提交、来源声明与数据哈希不变。r2使用单独的消费来源清单和快照ID，复用原浏览台的筛选、详情、对象追踪、笔记与CSV导出；不复制旧195表。

**已构建并完成数据核验和统筹真实浏览器验收。** 109张接通表：107当前、2份标明被替代的旧人员接口；352997存储行包含重复视图与路径，不能当独立样本数。142个冻结来源、112个按需读取分片，独立快照ID为`v1_integrated_analysis_20261017_r2`，不冒用Git提交。数据入口：[source-manifest.json](source-manifest.json)、[data-inventory.json](data-inventory.json)，验证：[VERIFICATION.json](VERIFICATION.json)。

首页有8个主题：库存覆盖、人员绝对/相对Q与时间、Semi及可靠性、普通/门洞与难度、门洞固定人数过程、增人稳定性/参考Q/完整率、人员策略和同房。每条结论对应明确工作命题，标明支持、不支持或证据不足，附独立图/楼数、未知与反例，不声称这些命题均由用户确认。门洞纳入v1场景层；低人数等待未来v2，不启动采集。

## 本地打开与重放

直接双击本目录的 `index.html`，即可离线浏览首页并进入修订明细表，无需启动 HTTP 服务器、联网或安装前端依赖。原 HTTP 地址仍可使用。

请保留本目录（含 `explorer-data/`）以及相邻的 `research_explorer_20261017/`：明细页、样式和共用加载器复用该目录。不是可单独搬走的单文件 HTML。旧195表入口仍沿用其原加载方式。

离线数据与原消费 JSON 一一对应，按需加载；不改变统计值、缺失值、快照身份和字段校验。`explorer-data/` 是派生本地数据，保持局部忽略、不重复提交。完整构建已自动生成离线分片；仅补建现有 JSON 的离线分片时，从仓库根目录运行：

```powershell
python -m tools.thesis_main.analysis.v1_statistics_revision_20261017 --local-data-only
```

构建命令与私有来源负载要求见[统计r2说明](../v1_integrated_analysis_20261017_r2/README.md)。上述补建命令不重跑统计，也不修改输入或原消费 JSON。每次更新消费 JSON 后需重新生成对应离线分片。浏览器可能限制本地文件的笔记持久保存，重要笔记请使用页面导出功能备份。

统筹的真实浏览器验收覆盖：首页3222/1911/41859/9及8主题/反例；门洞primary15筛出4行、每k60机会与60/57/46/53质量分母、k=1的R缺失；217候选中模块完成而无过程的pair标记为false。截图仅内存目视，未落盘。未测试下载/笔记，也未做全库原图或几何视觉认证。

统计机器接口及完整交接：[r2 CONSUMER_INTERFACE](../v1_integrated_analysis_20261017_r2/CONSUMER_INTERFACE.json)、[HANDOFF](../v1_integrated_analysis_20261017_r2/HANDOFF.md)。本地私有用途，不部署公网。

## 双击HTML改造验收（2026-10-17）

- Python定向测试：`python -m pytest tests/test_v1_statistics_revision_20261017.py -q --basetemp .tmp_offline_pytest`，6项通过，覆盖原消费者身份、隐私、缺失值及新增离线分片内容一致性和旧分片清理。
- Edge真实 `file://` 检查：`research/statistics/research_explorer_20261017/tests/offline_ui.cjs`；首页8主题、首页到明细、3222行真实明细及manual筛选、记录详情、笔记、CSV下载和缺失分片报错均通过；禁止fetch并核对HTTP请求为0。未生成截图文件。
- 114份JSON均已有对应脚本分片；离线分片保留JSON原内容，统计、资格、来源清单与协议无变更。项目地图、文档入口与研究目录已同步，目录核验通过。
- 本次未重跑统计或全库几何验证；浏览器笔记在不同浏览器或文件移动后的持久性不作保证，请导出备份。

2026-10-19接续：[51图人员换人与人数机制](../../workers/personnel_type_validation_next_20261019/index.html)已接侧栏；独立页可离线运行，含全部3672团队的保存几何、原答叠加和12个人数节点。此接入未将旧模块表格伪装成新实验全量消费者。

2026-10-19：人员替换独立叠图页现支持普通Manual／门洞Manual／普通Semi三层选择；扩展各9图，特殊层不套用普通Manual类别。细节见[机制续报](../../workers/personnel_type_validation_next_20261019/README.md#2026-10-19-机制追踪与条件扩展续报)。

2026-10-20：[类别块额外背景与4例复核](../../workers/personnel_composition_followup_20261019/index.html)已接入独立入口。451对照／1353队、66图／12栋；不代表此台全库快照重算。
