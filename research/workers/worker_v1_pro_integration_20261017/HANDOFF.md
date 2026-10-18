# 人员模块：Pro与真实团队结果接续交付

2026-10-17，数据v1独立分析修订`worker_v1_pro_integration_20261017`。

## 已完成与机器接口

- 消费真实TEAM_RESULTS：14845请求、14603完成/172图、242个rPc-22整池输入失败、0待发布；没有重跑融合。门洞17图1333请求已接入，完整几何1170、主质量1111；这些是普通Q/T向门洞迁移，不能冒充门洞专项选人验证。
- 消费统计24348个实际策略/随机对照与12174个重选比较，核对request_id、成员、k、主用途掩码和B8L2/D10差值；纯类与组别优先混合路径分列。逐图和逐建筑汇总复核6项已有k=3纯类比较，并保留权重敏感性和反例。
- 接入574份初始化、437普通兼容净改善、409普通Semi开发训练和28原留出；413原生初始化环未确认与计量/修订限制保留。普通Manual Q1048未变；门洞专项表、普通→门洞迁移与Semi模型均分开。
- 补齐b62a4df9e1645fe7、717840fe8221eba6两条漏项，与28935ccbb578589d合为3条原评论证据，源裁决均usable且均不在156强gold分母中。原Pro文件未修改。
- 156强缺陷机会＝25未改＋131编辑后语义未知；保留旧288/39逐对象桥接，共同机会144、旧独有144、新独有12；未改共同20、旧独有16、新独有5。历史整人排除W019/W026不恢复资格。
- 25具体/68宽剔除标记作为文本候选，保留主观幅度、OOS政策争议及范围歧义，未升级独立严重失误标签；scope历史gold与当前clear兼容条件显式区分；没有综合扣分。

统筹/统计直接读取`CROSS_MODULE_INPUTS.json`，其中列明：

|用途|文件/主键|
|---|---|
|逐对象证据|`record_evidence.csv`，object_id，3222行|
|逐人画像与证据|`person_profiles_and_evidence.csv`，worker_id×metric，54行|
|逐人机会/未知|`person_evidence_summary.csv`，worker_id，27行|
|初始化及兼容计量|`semi_initialization_scores.csv`、`initialization_evidence.csv`，574行|
|修正后纠错证据|`semi_correction_evidence.csv`，574行|
|旧新定义桥接|`correction_definition_bridge.csv`，574行|
|scope来源/历史/兼容|`scope_evidence.csv`，3222行|
|85条原剔除候选编码|`exclusion_candidate_evidence.csv`，85行|
|真实团队与覆盖|`team_results.csv`、`team_coverage.csv`|
|策略/随机对照|`strategy_vs_random.csv`、`strategy_summary.csv`|
|纯类比较及建筑权重|`pure_group_direct_comparisons.csv`、`pure_group_direct_by_image.csv`、`pure_group_direct_by_building.csv`|
|固定评价下重选成员|`metric_reselection_contrasts.csv`|

`FIELD_CONTRACT.json`列明全部CSV字段和行数；`INPUTS.json`列实际读取文件、大小/修改时间及采用边界；没有把本地原件自动当远端可取得。`HUMAN_REVIEW_CASES.json`是最小人工清单。

## 实际验证

- 完整生成命令成功：`python -m tools.thesis_main.analysis.worker_v1_pro_integration_20261017`。
- `python -m pytest tests/test_worker_v1_pro_integration_20261017.py tests/test_worker_v1_composition_20261017.py tests/test_worker_b8l2_d10_20261017.py -q`：13 passed。新增测试先于实现，确认原“还是不太对”的两条漏项、原一条、不应匹配状态、scope兼容门、纯类人数条件、实际桥接分母和usable/资格保持。
- 实际检查每条策略request/随机前缀对应关系、TEAM_RESULTS完成行成员及k、主用途掩码、两指标差值与重选差值；六项纯类比较图数/均差从逐图结果复核到现有统计。
- 输入来源在本轮读取/写出期间无变化，Pro原件未写入。统筹已经独立核过960 Q效应和2096预测，本轮没有重复完整拟合。
- 报告链接、机器入口、CSV字段/行数及逐对象/逐人主键另作定向检查。
- 未运行全仓测试、新融合、完整Pro重训或全体语义/原图复审；改动局限于人员消费者及接口，针对性检查已经覆盖相关边界。本轮没有检查截图。

## 人工裁决与剩余问题

当前主线接入所必需的新人工裁决：**没有**。

条件性归因问题仅1例：W001/Uw-08，`f21c670566821ce7`，P1 project30/task3105/annotation4790。历史scope为correct_rejection，原invalid及评语“oos,但是他只标了3个点”保持。若要把这条计为个人几何错误，需确认当时OOS是否必须提交完整成对布局以及invalid具体依据；当前统一说明允许OOS只提供足够范围证据，不能直接回推旧任务。正式输入来源、scope账、候选评论和问题均在HUMAN_REVIEW_CASES。保持排除并标归因待核，不要求重审131个编辑后未知案例。

W031/7y-13与W033/Uw-10仅保留主观严重程度/范围歧义标记；没有新总分或独立严重度率，不需要为当前交付强行二裁。131个强gold修改后结局未知不等于已修复；rPc-22的坐标输入问题仍由融合/数据边界处理。本线程不修原坐标、改参考或剔除某个成员来得到预期趋势。

## 修改范围与目录接入

新增本研究包、`tools/thesis_main/analysis/worker_v1_pro_integration_20261017.py`及对应测试；更新旧`worker_v1_composition_20261017/README.md`和`HANDOFF.md`的当前状态链接/过时等待说法，旧CSV/JSON快照及请求不变。

已只读检查`docs/README_INDEX.md`与`docs/PROJECT_MAP_CLEAN_20260308.md`人员入口。依本轮明确分工，没有修改全局模型、合同、CATALOG、索引或地图；请统筹将本包登记为“数据v1下Pro与真实组合结果的人员消费者修订”，连接README、CROSS_MODULE_INPUTS、FIELD_CONTRACT与本HANDOFF，不把候选编码登记为正式严重失误评分。

未改原始导出、参考、评分/人员资格、冻结release或其它模块；未暂存、提交或推送，也未向其它聊天发消息。下一步统计可直接连接新接口与真实过程，不需要等待新采集或重训普通Q。
