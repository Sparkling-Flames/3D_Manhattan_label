# 融合分析修订r2交接（数据仍为v1）

2026-10-17。本轮两项修订已完成。消费者先读CURRENT.json，再读MANIFEST.json；活动数据仍在本包根目录，旧表和旧清单封存在history/v1_complete_measurement_cache_main_panel_r2_20261017/pre_revision_tables.zip。未复制原融合states.json.gz，未改原始输入／参考／资格／评分参数。

## 修复范围与实际验证

- 缓存改为pools/<pool>/score_cache.json完整测量字典，含输入、源索引、环序及参考的上下文绑定。扩请求后不丢旧字段，未来新字段也保留；上下文不符拒用该测量缓存。旧CSV不是完整载荷，缺完整缓存时需有来源恢复或实际重测已存几何。
- 恢复7641唯一子集、101007字段单元；包含15个辅助数值字段与4个子集的失败原因。补值全部来自匹配成员／参考／核心数值的旧快照，逐字段来源在measurement_field_recovery.csv。审查窗口2435行floor_WQ_upper_bound及其它14字段各2402行已恢复，另把更早Q/T扩请求的相同缺口一起修复。
- 无批量重评分或重融；7次已存状态测量只核验冻结引擎载荷schema。41859前缀、23951子集、233池208图、14603完成团队和536同房状态的成员／参考／资格不变，B8L2、D10及原核心分项最大绝对差均为0。证据为REVISION_CHECKS.json。
- 主比较改为显式27图／11建筑：质量18升9降、B8L2均+0.272973、D10均+0.199946。含3原留出30图描述仍保留。原资格标志未改，只正式使用两端既有main_comparison_allowed。
- 主面板V按端点可用对为25降2升，4图有效对集合变化；严格相同有效对为26降1升，单列敏感性。V的具体对ID和两端／共同分母均已保存，不能混写两种估计量。
- 10项定向测试通过；新增扩请求保持完整载荷（含未知未来字段）及上下文改变拒用测试，以及主面板排留出／端点与严格V可反向的回归测试。修订前已复现缓存字段丢失的失败测试，修正后通过。无全库语义审核或全几何重建。

## 精确机器接口与主键

- CURRENT.json：data_release=v1；analysis_revision=v1_complete_measurement_cache_main_panel_r2_20261017；manifest=MANIFEST.json。
- trajectory_scores.csv：主键(pool_id,path_id,k)，subset是实际成员集合；原B8L2/D10、成员、参考和资格保持。
- unique_subsets.csv：主键(pool_id,subset)，与同池完整score_cache.json键对应。
- measurement_field_recovery.csv：主键(pool_id,subset,field)；value为实际源值，source指向已归档的随机基线或统计旧快照。归档映射在REVISION_CHECKS.json.source_checks。
- random_8to16_main_panel.csv：正式27图，主键(pool_id,k_from,k_to)；以原main门配对质量。
- random_8to16_descriptive_panel.csv：含原留出30图，仅描述；同主键。
- random_8to16_main_strict_V.csv：同27图，对两端相同path_a/path_b取交集；V_strict_*不是端点各自均值。V_valid_pair_ids_from/to、V_pairs_from/to、V_strict_pairs、V_pair_sets_equal为完整机会信息。
- random_8to16_panel_summary.csv：主键analysis_scope，三种口径分别读。
- TEAM_RESULTS.csv主键request_id；SAME_ROOM_PROCESS_RESULTS.json及same_room_trajectory.csv主键(request_id,replay_id,side,k)。主结果接口未变，统筹可用原ID对账，不必重发请求。

复现修订：python -m tools.thesis_main.analysis.wall_consensus_v1_revision_20261017。脚本消费归档前表与归档来源，只恢复缺失字段，保存完整缓存，再重汇总。它不重新融合或选择新成员，不读取未来的数据v2。当前数字和计数须以本次CURRENT修订为准。

## 统筹登记、未完成与人工事项

本轮只改融合专属执行／汇总脚本、测试、本包文档与结果。新增tools/thesis_main/analysis/wall_consensus_v1_revision_20261017.py及本修订文件需由统筹登记CATALOG和总地图；未改任何全局模型、合同、索引或其它模块结果，未提交／推送，未向其它聊天发送消息。

数据接口已经可供统计接入。尚未完成的是通用墙线身份正确率认证、固定构成换具体成员的更多实验、未来人员／数据v2结论；这些不阻碍当前修订交付。原4个输入问题池仍保持原因，本轮不要求用户为修缓存重复审核。

**本轮确需用户人工裁决的新增案例：没有。** 后续只有具体语义判断会改变结论时再集中展示最小案例。

---

以下为前轮真实重放交付背景；计数继续可对账，旧8测试等历史陈述不替代上方本次10项验证。

# 数据v1融合过程：本轮交付

2026-10-17。本模块工作已实际完成：随机基线、人员Q/T请求和同房共同人员请求均有真实几何与逐状态结果，不是仅给计划或接入端点评分。

## 完成范围

- 237个过来源门的池全部尝试：3池准备时缺点对、1池执行时源坐标越界；其余233池完成，208张独立图片。Manual181图／Semi43图／OOS来源9图分开，条件图片可重叠。
- 4条随机基线11,248状态；加人员请求30,075状态、同房536状态，合计41,859状态／23,951唯一成员子集。新计算23,739、复用历史212。没有把重复路径计作独立图片。
- Q/T请求172图、2,580路径；14,603团队完成，rPc-22的242团队请求因同一整池输入问题未执行，不是242次数值计算失败。另15条路径有拒收原因。
- 同房9对／7建筑／18图，536个状态全部实际保存，未运行数0；434质量分数、447完整诊断数值。2人72、仅底面13、缺连接4分别保留。
- 原作答两两分歧、实际成员构成、同k随机换组差、相邻身份和票变化、完整／失败／可计算率、分项与B8L2/D10、真实来源用时及缺失均可查询。

## 消费入口

统计：MANIFEST.json、pool_eligibility.csv、STATUS.json、trajectory_scores.csv、unique_subsets.csv、by_pool_k.csv。先按condition/layer/quality_allowed/main_comparison_allowed声明用途；diagnostic字段不能直接进入质量排名。

人员：TEAM_RESULTS.csv、TEAM_RESULT_STATUS.json、worker_policy_coverage.csv、worker_policy_vs_random.csv、worker_direct_contrasts.csv、subset_composition.csv。选择指标与评价指标分别读，优先顺序不是纯组别；Q/T支持不足和时间缺失不能藏掉。

同房：SAME_ROOM_PROCESS_RESULTS.json、same_room_trajectory.csv、same_room_within_view_stability.csv。JSON包含精确CSV及几何位置。相同request/replay/k两侧人员完全相同；共同人员终点不是原图全员终点，不跨视角计算底面相交。后续迁移统计由同房模块负责。

每池pools/<pool_id>/states.json.gz保存自动身份、节点、候选几何、完整人员顺序及缓存来源。一个图×成员集合只算一次；所有前缀只用当前作答，不传全员身份／人工顺序。fresh_set_checks.json中3张真实全员集合逆传参从头融合，与保存节点及连接一致。

## 验证与修正

8项定向测试通过：tests/test_wall_consensus_v1_process_20261017.py及tests/test_wall_consensus_d10_20261017.py。输出检查覆盖重复集合一致、两指标同掩码、OOS禁质量、k2暂缓、同房两侧同人员和所有请求状态。CHECKS.json保存结果。已查看科学图process_comparison.png；它是交付图，不是临时截图，本轮没有新增临时截图。

曾修正本模块CSV文本False错误解释为留出的读取问题。holdout_flag_correction.json和history/保留修正来源；当前用途已重汇总，原71份明确留出保留，几何及评分值未变。它是数据v1内的分析修订，不是数据v2。原数据release及其它模块均未修改。

未运行全仓测试：本次只新增融合模块执行与汇总工具，未改共享评分、正式合同、源清洗和算法参数。未调参、改绑定、改难度／GT排除、修改冻结release、提交或推送。

## 待统筹登记与地图检查

按本轮授权不改全局catalog、模型、合同、索引或共享包。请统筹登记本包及：

- tools/thesis_main/analysis/wall_consensus_v1_process_20261017.py
- tools/thesis_main/analysis/wall_consensus_v1_summary_20261017.py
- tests/test_wall_consensus_v1_process_20261017.py

请同步检查docs/README_INDEX.md、docs/PROJECT_MAP_CLEAN_20260308.md和research/catalog/CATALOG.json，入口指向本README与MANIFEST；旧18图和旧用途快照仍保留原身份。

## 尚未完成及下一步安全任务

没有认证全部自动墙线身份、给出自动正确率、证明长期新增人员收敛或通用最优人数／人员策略。Q/T各政策主要一条优先顺序，没有完成固定构成再换人的独立稳定性设计。时间齐全的长前缀很少，不作普遍成本优势结论。

本轮直接对照已显示策略差异和图片／建筑构成敏感性；下一步应由人员与同房线程消费真实几何做固定可比面板分析，按有效机会及建筑／用户关系组汇总，不再用旧18图代替当前扩展。不需要先修完4个输入池才能使用已完成部分；修源须由相应来源流程另记分析修订。
