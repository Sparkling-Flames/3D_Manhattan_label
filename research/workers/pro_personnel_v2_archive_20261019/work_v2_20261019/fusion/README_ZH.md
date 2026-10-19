# v2 真实人员组合、替换与逐人加入

本目录只消费 GitHub main `82c6164b0d4630de5316199c92aa405930973168` 中已经审核、预处理、绑定参考的匿名逐份证据。没有重新读取原始导出，没有覆盖 R01424 修复或 W018 等删点，没有重新排序已经声明的点对环。

## 可复现入口

在交付包根目录，使用包含 numpy、pandas、scipy、shapely 的 Python 环境：

首选直接重放已经冻结的成员清单：

```bash
python work_v2_20261019/fusion/run_reproduction.py --jobs 3
```

只重建汇总时使用 `--stage summaries`。依赖实测版本在 `RUNTIME_ENVIRONMENT.json` 与 `requirements.txt`；该入口逐阶段写 `REPRODUCTION_RECEIPT.json`，每个比较表另由独立 Python 子进程流式校验 gzip CRC、行数和 SHA。以下是按研究步骤逐条运行的入口：

如果每池已有状态与请求结果，融合引擎会复用这些精确缓存；这样的运行只能称为读取已算团队并重建比较/汇总，不能称为再次调用了全部原生融合。要重新计算全部团队，可在独立解压副本中保留冻结输入与请求、移出该副本的 `fusion/pools/` 后运行入口；原交付与既有证据无需改动。每次收据的 `actual_new_fusions` 显式说明本次真正新调用的数量。

```bash
python work_v2_20261019/fusion/pool_io.py
python work_v2_20261019/fusion/register_design.py
python work_v2_20261019/fusion/fusion_engine.py --pilot --jobs 3
python work_v2_20261019/fusion/fusion_engine.py --jobs 3
python work_v2_20261019/fusion/verify_engine.py
python work_v2_20261019/fusion/register_forward.py
python work_v2_20261019/fusion/register_behavior.py
python work_v2_20261019/fusion/fusion_engine.py --requests work_v2_20261019/fusion/REQUESTS_EXTENSION.json.gz --jobs 3
python work_v2_20261019/fusion/compare_fusions.py --jobs 3
python work_v2_20261019/fusion/analyze_fusion.py
python work_v2_20261019/fusion/analyze_policies.py
python work_v2_20261019/fusion/audit_output_status.py
python work_v2_20261019/fusion/select_forward_cases.py
```

`register_forward.py` 需要本轮人员画像模块的 `fold_profiles.csv` 与难度细类注册文件，`register_behavior.py` 需要独立证据模块的楼外机会表。它们不是从目标建筑作答质量选人。已经生成的冻结请求可以直接输入 `fusion_engine.py` 重放，避免因重建画像时随机过程或依赖差异改变成员。

`REQUESTS_EXTENSION.json.gz` 是已经冻结的三个输入的无损合并：逐图簇 oracle 请求、楼外人员画像/固定组成请求、独立行为证据请求；来源哈希见 `EXTENSION_RECEIPT.json`。它不改变任一已有请求。输入库存与输出质量资格是独立边界，不能把运行生成的队伍数称作独立真人样本。

## 数据边界

`INPUT_SNAPSHOT.json.gz` 顶层 `images`：229 个同图、同条件、同参考身份及版本的人员池，来自 7,302 份质量合格且独立的真人作答。普通 Manual 主层 5,719 份、177 图、22 建筑。门洞 Manual、普通 Semi、特殊条件单列，不把它们混作相同任务。

每条 `records` 的 `points` 直接等于证据包 `points_1024x512`，保留上下点绑定、声明环、来源点对索引、审核状态。这里将 `object_id` 用作计算 ID、将 `worker_id` 用作匿名稳定人员名；12 栋旧 v1 同成员、同几何团队的独立复算核查了这种 ID 转接没有改变真实几何、存在票或物理观察分区。

`V1_PARITY_INPUT_FIXTURE.json.gz` 仅归档这 12 个已经核查的旧处理后团队输入、旧候选状态及原文件 SHA，约 42 KB。`verify_engine.py` 在缺少整套本地旧工作目录时可读取该小归档重放所选检查；它不是原始导出，也不能用于声称重建全部 v1 采集流程。

小于所需 k 的池不进入该 k，但保留覆盖分母。不存在未合格作答补零、模拟人、一个人重复投票、按参考所得分数选参考或 N1 加分。

## 冻结融合函数

原样调用 `tools.thesis_main.analysis.consensus_delivery_20261008.fuse`，核心为 `ring_correspondence_20261007.build`：

- 每次只把该团队的真实当前成员传入，重新建立点对对应；不借全员结果决定小团队身份。
- 配对代价为上下端点角距离平均，循环与反向遍历，允许跳点，跳过一个点对的代价固定为 7.5°。
- 同身份组要求组内两两匹配相容；每人最多一票；MV50 使用包含半票的 `2 × support >= N`。
- 坐标是该身份组全部成员的等人权中位数，x 保留已有周期处理。
- 连接只从覆盖全部选中节点的来源投影环选择；没有覆盖来源时保留无连接，不临时补环或回退 x 排序。
- 两人保留节点证据，但按已有规则暂不排序；它是明确的政策缺失，单列于其它失败。

这套节点融合使用的完整链接约束，和整份作答的 9°/12° 全局亲近度分簇是不同计算。整份簇只定义组成、替换或解释性选择，未更改融合算法。所有原函数与评分依赖 SHA-256 见 `DESIGN.json`。

## 实验注册与真实成员

初始注册共有 77,942 条请求、77,039 个不同成员集合：4 条完整均匀随机排列；在 k=4/8/12/16/24/32 独立抽取至多 12 个同人数团队；在 k=8/12/16/24 抽两个固定的 k−1 人背景，将其余真实成员逐一加入。固定背景内穷尽入替人对，不只挑有利案例。

三个补充注册都在检查相应策略输出之前固定：

- `FORWARD_REGISTRATION.json`：Q、Q+D、Q+T、Q+T+D，同候选人员池及时间已知候选对照，B8/D10 重新选人分开；Q2、QT、QT×难度画像三个固定组成方案都使用同一已知人员交集。每个方案的三种人数向量均固定后抽 4 个真实成员变体。
- 簇模块 `ORACLE_REQUESTS.json.gz`：9°/12° 各自的主簇优先、均衡混合、可行纯大簇，以及主簇优先和均衡的真实逐人前缀。它使用目标图已经完成的答案，属于解释性/oracle。
- `BEHAVIOR_FUSION_REGISTRATION.json`：仅在同一个有支持的错误初始化机会证据层内比较；旧确认初始化和新人报告标志绝不混作同等证据。未知机会不补零，没有把修改过解释为纠正成功。

`REQUESTS*.json.gz` 保存每队的准确匿名成员和顺序。`ORDER_CHECK_REGISTRATION.json` 另外登记了不走团队缓存的独立排列检查；108 次直接调用、36 个相同成员集合全部得出完全相同的 compact 状态。每个真实前缀的成员仍不同，因此入场过程仍可能改变内容和质量；完整同成员终点相同不证明无限人群或其它图片的稳定性。

## 结果 API

`team_results.csv` 每条请求一行，主键 `request_id`；`team_id` 是同池、无序成员集合的稳定 ID。不同路径可能共享同一团队，分析独立团队或同 k 变体时需要按 `team_id` 去重；研究真实路径时则按 `path_id, k` 保留。

每池保留：

- `pools/<pool_id>/requests.json.gz`：实际请求及准确有序成员。
- `request_results.json.gz`：逐请求质量、完整性、结构、时间与元数据。
- `states.json.gz`：顶层 `states`，每个 `team_id` 的真实最终几何、节点、每节点来源观察、存在票和来源环诊断。`automatic = null` 才表示融合执行异常；输出不完整本身通常仍有可用节点。
- `scores.json.gz`：指定相同参考的 B8L2、D10、五分项、平均高度棱柱 3D IoU、底面遗漏与延展。
- `context.json`：完整成员/参考/原函数哈希；只有上下文完全一致才复用。
- `LAST_RUN.json`：实际调用次数、耗时和异常。

跨团队表为 `replacements.csv.gz`、`random_same_k.csv.gz`、`composition_comparisons.csv.gz`、`policy_comparisons.csv.gz`、`prefix_transitions.csv.gz`。比较主键保留两侧 request/team IDs，可回查完整成员及几何。`INITIAL_` 前缀文件只包含初始冻结实验，供追加实验运行期间读取；它不是新的数据版本。

`scores.json.gz` 是可省略的加速缓存。`SCORE_CACHE_REDUNDANCY_AUDIT.json` 已逐项检查全部 144,253 个唯一团队、28 类评分字段：每一个原评分键值均原样存在于 `request_results.json.gz`，零缺项、零不同值。后者同时保留所有失败、完整性、来源时间和同目标时间字段。大包可以省去 `scores.json.gz` 和重复的逐池 CSV；完整几何与来源观察仍需保留 `states.json.gz`。重放引擎支持缺省缓存，不把它当缺源证据。

最终主要结果与采用判断见 `RESULTS_ZH.md`。`FORWARD_POLICY_*`、`FIXED_COMPOSITION_*`、`COMPOSITION_MATCHED_VARIATION_*`、`METRIC_RESELECTION_*` 分别保存逐尝试、逐图、建筑等权及原声明房组等权结果；不能把重复随机团队或重叠路径当独立人。房组只沿用原注册 `original` 且 `physical_same=支持` 的直接组，不按建筑或传递关系补组；区间仍以建筑为单位。

## 输出完整性检查与故障记录

早期两个逐池比较 gzip，以及最终政策比较的第一次全局压缩产物，曾在后续进程读取时发现缺失 gzip 尾部。已保存原错误、文件大小、重建动作和校验记录；仅从未变的已存几何或逐池比较重建，没有换人、改分类、改分数或删失败。后续对五个最终表使用两次独立进程，完整解压至 CRC、逐行解析、检查字段数及行数，并核对压缩和解压 SHA256 全部稳定。见 `INITIAL_COMPARISON_INTEGRITY_RECOVERY.json`、`FINAL_POLICY_INTEGRITY_RECOVERY.json` 与 `COMPARISON_INTEGRITY_CHECK_1/2.json`。

没有发现当时仍在运行的重复融合/比较写者，但不能据此断言已经确定截断根因。不同沙箱命令可能报告相同进程号，因此临时文件已改用 UUID；同比较输出命名空间增加排他锁；完整压缩流先在内存形成，再一次落盘、fsync、校验后发布。`INITIAL_PANEL_UNCHANGED_AFTER_EXTENSION.json` 另证实初始固定背景替换和随机同 k 表在追加实验后，解压 CSV 逐字节 SHA 完全相同。

## 量的含义及失败处理

**Q 与 R/V 分开。** B8L2/D10 是对指定参考的几何交付质量。R 是原答两两底面差异，使用固定整池并集面积归一化。V 是同图、同 k 的两次真实团队输出变化。它们不构成图片噪声与人员噪声的自动分解。

**失败留在分母。** `score_status`、可计算几何完整率和条件可评分均值同时报告。`complete_evaluable` 仅表示当前自动候选拥有不少于四个节点和可计算的完整几何，不表示已经人工确认节点物理身份、顺序或交付通过。主函数的 `geometry_review`、`source_suggestion` 和 `ring_confirmed=False` 等状态原样保留。`delivery_utility_B8L2` 仅是团队操作决策敏感性：有效输出用 Q，其余为 0。它不是缺失人员 Q，也没有用于训练人员能力或定义细类。

**几何相似与细节一致分开。** 工程容忍主设置为 |ΔB8L2|≤2、底面 Jaccard 差≤0.05、输出点对数相同且绑定循环端点距离≤3°，并要求两队完整。另列更严/更宽敏感性。`joint_geometric_stable` 只表达这些观测条件；`joint_with_shared_connections` 额外要求共同来源观察的边关系完全相同；再加 `..._and_retention` 要求共同来源观察保留一致。没有用不显著 p 值断言无影响，也没有把任何容忍当成已批准正式规则。

输出环主距离保持循环不反向；另列 `structure_reverse_allowed_deg`，用于识别仅环方向变化造成的度量敏感性。原答整份分簇仍按它自身冻结的绑定循环定义，不能混用。

**3D 是既定代理。** 团队两两 3D 范围比较使用共同底平面的平均高度棱柱，与原冻结评分的限制一致；不是连续实体体积的精确 IoU。

**时间不补。** 来源任务时间、同目标时间分别给已知人数、已知小计与完整团队总和。团队内有一个未知，总和即未知；不使用 lead time，不用来源替同目标。新报告时间和旧审计来源的同类队伍、混合队伍单列。

建筑等权区间先把重复变体汇总到图，再汇总到建筑。共同 k 面板只在确有该 k 支持的同一图/同一路径比较。它们是当前资料的探索性验证，不能重新命名历史留出为新盲测。
