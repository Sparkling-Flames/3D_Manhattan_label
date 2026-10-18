# 统计消费者与浏览台v1修订r2交接

2026-10-17。状态：上游融合、人员、难度与同房均已明确就绪，本消费者已捕获142文件并消费完成。`PREPARATION.json`为历史准备账；最终读`CONSUMER_INTERFACE.json`、`CHECKS.json`、`SOURCE_MANIFEST.json`及`DEPENDENCIES.json`。数据仍为v1，不是新增数据v2。

## 机器接口与实际结果

来源归档`SNAPSHOT.zip`有逐成员大小/哈希及整包哈希；旧r1过程文件原哈希单独核对。r2只补新增消费和对账，未变统计按来源引用，不复制整套旧195表。来源修订身份保留：融合`v1_complete_measurement_cache_main_panel_r2_20261017`、同房`same_room_v1_process_20261017_a1`、难度`difficulty_doorway_v1_20261017_r1`、人员`worker_v1_pro_integration_20261017`；各自完整机器元数据见DEPENDENCIES。

|接口|行/用途|主键与边界|
|---|---|---|
|same_room_process_integration.csv|268双侧前缀|request_id/replay_id/k；相同人员顺序；只用comparison_B8L2/D10|
|same_room_curve_integration.csv|67图对×k|request_id/k；两侧Q、各自视角V和各自有效支持，不算跨相机BEV|
|same_room_common_endpoints.csv|9共同池终点|request_id；不是原图全部来源人员终点，重复全员集合不算独立重复|
|same_room_endpoint_integration.csv|217候选|image_a/image_b；module_upstream_process_complete与pair_process_received分开，仅9对收到真实过程|
|auxiliary_restoration_ledger.csv|36063修复单元|pool_id/path_id/k/field；修复前r1非空→上游丢失，修复后逐值一致|
|process_field_reconciliation.csv|逐字段对账|旧非空保持、旧缺失补齐、丢失分别统计；不能把重复状态单元等同独立子集测量|

原41323过程全部保留，新增536同房后共41859；没有统计独有或消失状态。旧主分、成员、参考、资格不变；15辅助字段原有非空保持，允许有来源的旧空值补齐，4条失败原因补充单列。融合生产者的7641独特子集/101007恢复单元与本消费者重复状态层的补齐计数不是同一统计单位。

全库存3222/261图，当前质量1911（1699普通、188门洞、24其它），普通Manual Q1048未变。旧人员54/6444接口精确连回库存；新Pro3222/54接口的Q/T连续画像逐列核对，437普通兼容增益含409开发和28原留出，156强gold＝25未改＋131编辑后未知；三条usable审核评论不加入该强gold分母。scope历史gold与当前兼容、25具体/68宽剔除候选、未知归因分别保留，不增加综合罚分或恢复排除资格。

难度104普通图/312行、门洞17图808状态及75源字段和融合r2逐键一致。门洞703完整/655主质量/59完整来源时间；primary15各k60机会，k1/3/4/6质量60/57/46/53。高人数另用固定14图/4图面板。9对同房全ordinary，两诊断对整对掩码保持。

## 浏览入口与解释

本地总览：`http://127.0.0.1:8765/research/statistics/research_explorer_v1_r2_20261017/index.html`。

复用明细：`research/statistics/research_explorer_20261017/explorer.html?revision=v1r2`。默认不带revision仍是旧195表的固定Git快照；旧README、source-manifest、expected-data、data-inventory逐字节未改。原构建器未修改，不把新数据塞进旧固定目录。

新入口109表（107当前、2旧证据基线）、112分片、352997存储行。8主题都带明确工作命题、支持状态、独立图/楼、来源表和反例；工作命题不是冒称用户逐条确认的预期。首页普通Manual主用途8→16面板明确为27图/11楼，严格V采用两端共同有效重放对；不是全库27图。门洞/同房及来源/同目标时间保持用途分层。R、V、参考Q与完整率不互换，重复路径不增加独立图数。

## 实际验证

- 成功运行`python -m tools.thesis_main.analysis.v1_statistics_revision_20261017 --capture-ready-sources`，归档过程中逐文件前后哈希一致；原始输入/参考/质量资格未改。
- `python -m pytest tests/test_v1_statistics_revision_20261017.py tests/test_v1_integrated_analysis_20261017.py tests/test_b8l2_d10_statistics_20261017.py -q --basetemp=D:/Work/HOHONET/output/statistics_revision_test_20261017_05`：16 passed。独立临时目录用于规避本机受限沙箱Temp rename权限，测试工件交付前清理。
- 142源文件逐个与归档及当前源比哈希；112显示分片的字节、table_id、列、逐行宽度和总行数核验；6张新增CSV与FIELD_CONTRACT行/列一致；旧固定来源契约4文件与HEAD逐字节相同。两份JS均`node --check`通过。
- 统筹执行真实CUA浏览器验收：首页8主题/反例与3222/1911/41859/9正确；门洞primary15筛出4行，60机会和60/57/46/53、k1 R空值正确；217候选的模块完成/逐对无过程区分正确。截图仅内存、未落盘。未测下载/笔记；本模块没有重复浏览QA。
- 原浏览台构建守护测试额外尝试9项：7通过，2因沙箱禁止临时Git初始化/Windows符号链接权限失败，未改守护测试绕过。原构建器未修改，未重建整个旧195表。shell本地HTTP复验被WinError10013拦截；统筹已通过真实浏览器验收，不作为数据消费阻塞。
- 未跑全仓测试、新融合或全库原图认证；本轮只读消费者及前端分支。无提交/推送、无公网部署、无消息发往其它聊天。

## 修改范围与全局登记

新增本r2包、`research/statistics/research_explorer_v1_r2_20261017/`、专属脚本`tools/thesis_main/analysis/v1_statistics_revision_20261017.py`及测试；补旧r1缺失HANDOFF。共享浏览台`explorer.js`增加显式revision分支，保留旧默认固定数据入口、分离笔记键和来源检查。未修改原浏览台构建器、195表数据/固定清单或其它模块。

已只读检查`docs/README_INDEX.md`和`docs/PROJECT_MAP_CLEAN_20260308.md`。按统筹并发边界不写全局模型、索引、地图或CATALOG；请统筹登记本r2机器接口、浏览台README及新脚本/测试，旧入口继续保留。私有`SNAPSHOT.zip`和派生explorer-data由局部忽略规则排除，不能因元数据登记声称负载远端可取得。

## 剩余问题与最小人工清单

当前主线统计接入必需的新增人工裁决：**没有**。唯一条件性案例沿用人员HUMAN_REVIEW_CASES：W001/Uw-08，object_id=`f21c670566821ce7`。仅当研究要将其旧OOS排除归为个人几何失误时，需核对当时是否要求完整布局及invalid依据；目前保留原排除、归因待核、不罚分。不请求重审全部131个编辑后未知。

同房样本9对/7楼、仅7对主质量；时间稀缺、真实语义纠错未知、图内团队重叠和当前v1多次探索限制仍在。不把非显著写成无效，不把正向趋势当验收目标，不启动采集或v2。
