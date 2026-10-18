# 人员组合离线页：字段与交付记录

2026-10-18。入口[personnel_composition.html](personnel_composition.html)，从原index侧栏和顶部提示接入。可双击离线打开，不启动HTTP服务。它读取本轮528条请求、502个保存成员集合和8图参考；原index的109表仍是r2快照。

## 实际内容

- Q2粗类、QT4细类、Q3替代细分；按图片、实验、人数、构成切换。
- 同构成换人质量极差、底面V；同成员三种进入顺序的k1–4状态。缺失处断开。
- 两队真实人员及参考的ERP／BEV／3D叠加。两侧自动适配范围，不直接比较屏幕面积；保留自动连接与人工确认的区别。
- 6组结果后挑选的理解性复审实例；逐团队完整与缺失状态、用时已知和／缺失人数、当前楼外连续画像及24份有效点编辑清单。
- 导出当前筛选CSV；不会重新拟合、融合、评分或修改输入。

## 生成字段合同

`python -m tools.thesis_main.analysis.build_worker_composition_view_20261018`生成本地`personnel-composition-data.js`，schema为`worker_composition_display_20261018_v1`。脚本路径见仓库地图，数据只作派生展示。

`teams`严格按人员包TEAM_REQUESTS与team_analysis的唯一请求ID对齐；`worker_ids`为人员数组，`state_key`为图池内排序的记录ID集合。`pools[image_id]`包含固定参考、原图相对路径、成员点及按集合定位的原保存state；每个state按精确成员绑定后携带candidate/ring_diagnostics/origin，不把缺少几何的团队替换为别人结果，不提升ring_confirmed。`cells/profiles/thresholds/support/review_cases`直接继承人员包，`point_edits`只取当前有效编辑状态。输入字段语义见[人员合同](../../workers/worker_fine_composition_20261018/FIELD_CONTRACT.json)与[融合合同](../../fusion/worker_composition_fusion_20261018/CONSUMER_INTERFACE.json)。

`main_comparison_allowed`仅表示用途门允许；页面主质量数和图同时要求分数非空。失败不填0，只有1个主质量集合的极差显示“缺少2组支持”，不误称稳定。已知活动时间合计配合缺失人数显示；不伪装完整成本。配对及重叠成员不作为独立样本。

## 验证记录

输入／分类／融合／显示相关10个测试文件合并执行，**48项通过**：

```powershell
python -m pytest tests/test_processed_input_review_20261018.py tests/test_apply_pairing_preprocessing_20260929.py tests/test_current_annotation_context_20261017.py tests/test_consolidate_research_input.py tests/test_consensus_contract_20260923.py tests/test_worker_fine_composition_20261018.py tests/test_worker_v1_composition_20261017.py tests/test_worker_composition_fusion_20261018.py tests/test_wall_consensus_v1_process_20261017.py tests/test_worker_composition_view_20261018.py -q
```

离线界面测试为同目录`personnel-composition-ui.test.cjs`，使用已安装Playwright／Edge：覆盖3分类×8图片、6实例精确队伍定位、BEV/3D/ERP、k2缺失、固定终点、导出及850px视口。无JavaScript错误、无HTTP(S)请求。检查截图只临时保存，查看后清理。

独立交叉审查另核528请求与冻结设计一致、Q/T各折目标建筑未泄漏、867结果的成员／几何／参考／用途／时间绑定，以及432同构成和3312跨构成对；普通和门洞各1组逆序输入重新融合，与保存state一致。当前主质量1911份逐条不变。目录生成／核验及文档链接检查结果记于同目录`PERSONNEL_CHECKS_20261018.json`。

## 交付边界

新增工具、研究包和统筹文档已经登记`research/catalog/CATALOG.json`，并同步主题入口、README_INDEX、PROJECT_MAP及当前研究交接；旧资料不移动。修复输入的当前机器合同只接续路径和修订说明，未改方法参数、人员资格、参考采用、运营协议或原始导出。

未重跑无关全库测试、旧109表及历史无关几何；未移植N1或新增人工墙线身份认证。当前8图、每构成3队及有限混合配比不能用来冻结最终人员类型；先由用户看6组实例，再对具体机制和相同公共面板扩验证。无需等v2补标才能阅读当前结果。
