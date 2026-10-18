# 已处理点继承核查与v1修订（2026-10-18）

当前入口为 `manifest.json`，修订号 `confirmed_coordinate_repair_v1_20261018`。当前机器合同指向本快照；显式读取旧manifest仍得到旧结果。历史v1冻结包、原始导出、模拟数据均未改写。

## 本次核查范围与判断

- 比对9月28日已处理基线、9月29日初始化、当前3222份作答；核查坐标两个维度、原点身份、删补点、配对、环序及来源。
- 与历史 `history_confirmed_point_edits.csv` 的全部24条交叉核对；历史删除按原点label判断，`deleted_previous_point_indices`仅表示该轮删除，不能据其为空说历史未删。
- 14份10月10日点处理回执逐操作重放，包括delete/undo/pair/order；另3份环序回执复核。结果与当前快照一致。
- `effective_point_edits_current.csv` 共43条：24份当前有效点编辑，11份已有处理但无当前点增删/移动，4份历史未纳入记录缺有效点映射，1份旧单边x移动被后续共享x政策替代，2份未应用提议，1份撤销删除已恢复。类别不是新增票数。

## 需要修正的实际回退

`R01424 / 8ffe08f072e2b12e / rPc6DW4iMge-22 / W002 / annotation 4738`：9月20日明确修正源点p8为 `[191.39,389.7282406015037]`。9月29日初始化错误地将y还原为3897.2824060150374。本轮依据已记录before/after恢复，仅此一个作答的几何改变；原始导出坐标仍在对象中保留。

`R01547 / 9b8f8bec4da82b48 / 同图W018 / annotation 4784`：删除原p7仍生效，21点变20点，没有复活。

`X7HyMhZNoso-13 / W037` 的旧p8.x=p7.x操作不恢复：9月29日接收说明明确将其改为原p7/p8的周期平均x。这是后续共享x政策替代，不是本次所修的数值错误。全部其它有效删补点、借点来源、撤销删除和人工环序保持原状态。

## 质量与后续融合影响

R01424由`representation_limited`变为`surface_valid`；既有冻结评分引擎确认完整几何可用，保留`non_star_shaped_about_camera`提示。沿原预评分局部结构路由选择已准入原GT，不用得分挑参考，实算B8L2=85.0705612753、D10=88.5227041955。

该参考不是当前指定的裁后空间，因此用途门仍为`bound_other_admitted_space`，仅诊断可计算。主质量1911份、人员主画像数据不增加；完整计算2774→2775。`quality_delta.csv`是唯一变动的质量库存行，`quality_reassessment.json`保存完整路由、几何检查、用途门和分项分数。

含R01424的旧融合几何缓存应失效并重放；其它成员集合的缓存可按相同坐标、参考和成员身份继续复用。对象仅从`affected_objects.json`读取修后点，不直接复用旧`input_snapshot.json`中的该行。

## 已登记但不自动应用的事项

`unapplied_or_historical_gaps.csv`列明6条：W019的q9vSo1VnCiC-02、x8F5xyUWy9e-09、UwV83HsGsw3-09、wc2JMjhGNzB-59为历史未纳入作答，虽有旧删除记录但当前无有效点映射；b8cTxDM8gDG-19/W037与wc2JMjhGNzB-67/W034的历史补点提议尚未形成可执行已确认点位。本轮不恢复人员/作答资格，不猜点坐标。它们不影响本次R01424修复，也不作为阻塞v1人员分类的前置。

## 复现与字段

运行 `python -m tools.thesis_main.data_prep.review_processed_input_20261018` 从固定旧当前manifest重建本修订；随后运行 `python -m pytest tests/test_processed_input_review_20261018.py tests/test_apply_pairing_preprocessing_20260929.py -q`。

`manifest.json`沿用`research_analysis_bundle_v1`及原字段，较大JSON以`.json.gz`保存，由既有read入口读取。`processed_input_revision`仅记录坐标修订；`geometry.status`为计算检查，不能替代`main_quality_gate`、`independent_vote_eligible`或参考采用。`quality_delta.csv`字段沿用当前质量库存，只有该行变动，主分数保持空值。`coordinate_changes.json`保存完整前后对象。

验证：根因及统一质量消费者回归均先失败、修复后6项相关测试通过；18项既有context、bundle和合同测试通过。全bundle跨表、源点身份、共享x、环序绑定及3513对象/3222作答检查通过。未重跑不受此输入修订影响的全库质量与所有历史实验；融合重放由并行模块另交付。
