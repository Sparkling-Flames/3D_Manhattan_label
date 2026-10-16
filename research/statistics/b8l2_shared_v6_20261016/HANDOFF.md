# 固定v6原B8L2共同数据交接

2026-10-16。精确下游入口为[CROSS_MODULE_INPUTS.json](CROSS_MODULE_INPUTS.json)，版本`b8l2_shared_v6_20261016_v1`。本轮使用原`WQ-B8L2-20261015`参数及冻结测量，Pro新模型研究独立并行。

## 已完成

- 固定v6难度、完整loader、源采集时间状态、历史比较成员、来源回执、参考、预先绑定、模型源码及测量实现。运行只读本目录冻结资料，避免执行中途CURRENT变化。
- 3152原作答全部保留，1624份完整实测；1622份条件数值中1575普通主分析、47专项条件。旧891成员全部保留、同参考分值在1e-8内保持，731份来自原库存首次完整测量；42份旧评分仅标签分组变化。
- 43受影响图511份原作答继续展开；两份新增目标预览未当完整参考，41确认空间12完整/29待补、371份未唯一绑定。uNb-36整图质量待定，GT及旧明确hold不因新评分恢复。
- 输出逐人、逐图、人员×难度、难度、场景、建筑、直接同房、时间、共同指标对照与成员变化；35页工作簿及七组科研PNG/SVG完成数值与视觉核验。临时45张QA PNG及debug已清理。

## 改动范围

新增主入口`tools/thesis_main/analysis/b8l2_shared_snapshot_20261016.py`及描述helper `b8l2_shared_descriptive_20261016.py`，对应两份测试。现有current统计/参考审计/同房/评分helper增加显式冻结资料入口，默认调用保留；binding增加全库存可选范围，默认仍为受影响空间；图簿支持B8L2主指标。

`FIELD_CONTRACT.json`新增输入/参考/算法版本、quality_use及适用性说明。`ordinary_primary`与`special_conditional_only`分开；OOS可计算条件指数不认证表示适用性，不能迫使融合等模块开放其暂停。规范合同、原始标注、GT、CURRENT、评分参数、采集和历史结果均未改；没有新训练或新融合实验由统计线执行。

## 验证

主线程定向检查：

```powershell
python -m pytest tests/test_b8l2_shared_snapshot_20261016.py tests/test_b8l2_shared_descriptive_20261016.py tests/test_descriptive_statistics_current_20261015.py tests/test_descriptive_same_room_20261015.py tests/test_descriptive_pool_gate_20261015.py tests/test_descriptive_reference_audit_20261015.py tests/test_scope_quality_binding_20261016.py tests/test_scope_quality_scoring_20261016.py tests/test_descriptive_statistics_current_figures_20261015.py -q
```

31项通过。独立核验见[audit/SCORING_AUDIT.md](audit/SCORING_AUDIT.md)：3152身份/门与实际队列逐对象重建，长/宽汇总、4866行人员对照和3780行同房统计核对，四类新增作答直接调用冻结引擎及公式抽核。不是另外实现完整测量模型，也不是重新人工审定全部参考。

目录执行`python -m tools.thesis_main.analysis.build_research_catalog --write`及`--check`通过；共同产出与实际已落盘的难度、融合、同房包分别登记，历史版本保留。README_INDEX、PROJECT_MAP、agent上下文和统一入口第0节已同步；生成专题入口来自CATALOG，不手工复制一套新真源。其它线程已有文件和修改保留，未提交或推送。

## 下游与未做部分

新增引用[多空间点位职责与冗余整理包](../../data/scope_redundant_vertices_20261016/README.md)，实际视图见`scope_views.json`、摘要见`scope_summary.csv`；共同清单将其列为未参与本轮评分的补充几何资料。296个当前/准入目标扫描中，43个新/备选空间详查，严格共线4目标；含精度内近似则10目标11中间点，其中当前41空间有8目标。新目标的结构要求按其自身target_id和新环，不重新追加旧目标已退出的墙角。

`exact_floor_view`为数值等价视图；`precision_floor_view`仅为明确筛查尺度下的结构显示/诊断近似，不证明物理共线、不覆盖GT或B8L2参考。未知高度不生成`paired_view`，完整点对还需高度沿墙线性。原点/边编号及裁切来源保留；2份完整参考自比及1份已绑定作答差值为0，仅限这些已复算对象。本次只接交接引用，不重新审计全库、调参、改标签或简化作答，原1622条件评分和冻结参考不变。

人员建模、融合人数/换组轨迹及同房迁移由各原模块按自身职责推进；新评分表不等于这些研究自动完成。统计线已从现有文件登记原18图冻结融合B8L2和同房质量/来源时间交付，未替它们重新跑实验或承诺后续结果。

时间分母分别为库存1949、当前合格来源1750、完整质量/来源时间共有1042及原已审核同目标时间440。新覆盖不推断新目标采集时间，不用lead_time替代。人工难度粗类部分参考过作答，均值不能作为独立规则验证。

未跑全库测试、未新增采集、未调参数或填补29个不完整参考、未强行解决371份空间归属。新人员/图片仍待现有数据收束后独立批次接入；未来输入变化另起冻结版本，不覆盖本轮结果。
