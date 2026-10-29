# 直接 AC / 整类替换：冻结原生端点与测量接口

本目录仅负责精确身份复用、原生端点执行与保存后测量。它不训练人员分类、不按目标图片的分数挑团队，不修改人员或原答资格、目标空间、参考、难度或融合规则。严格 ABC 九人、十人设计由已提交的独立线程提供，本目录只复用它已经存在的精确端点。

## 输入与来源

当前仓库来源提交为 `ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff`。运行代码仍从旧本地工作树读取；主线程的 `stage00_intake/CURRENT_INPUT_COMPATIBILITY.json` 记录当前与旧提交的输入 blob 一致性。端点计划进一步保存实际使用的 135 个引擎、评分包、记录劳动输入和几何模块的 SHA256、Python/依赖版本、每个完整图片池与参考的哈希。旧来源不覆盖、不重写。

请求表的最小字段为 `team_key,pool_id,member_workers,n`。`member_workers` 是用 `|` 分隔的实际合格成员；`team_key` 沿用 `pool_id + '__' + sha256(canonical_json(sorted(members)))[:20]`。同一物理团队被多个分类选中时只有一个端点请求。

端点的完整语义身份还包含目标池及全部资格记录、Manual/Semi 条件、当前参考身份与坐标、冻结引擎及劳动来源合同、成员及原答 object_id。短 `team_key` 只是索引，不能单独证明可复用。

事件表的最小字段为 `event_id,pool_id,A_team_key,C_team_key`。设计字段全部保留。若提供 `A_members/C_members`、`n_A/n_C`、`D/X/Z` 或同名 `_members` / `_workers` 字段，测量器会与端点重新推导的真实集合逐项核对。支持等量和不等量两种比较；本接口不构造 B 队。

## 先扫描再执行

`code/ac_endpoint_runtime.py prepare` 只读冻结请求并扫描以下来源：

1. 上轮独立审查的 16,818 条完整端点 `stage03_completed_abc/ENDPOINT_GEOMETRY.jsonl.gz`。
2. 当前提交中已经完成的严格 ABC 九人、十人端点，共 28,945 条、24 个池。提取到 `current_strict_cache`，保留 commit/path/Git blob/SHA256 清单。
3. 已纳入合法其它目标的 `03A/composition/other_targets_endpoints` 完整 JSONL。
4. 已有全局广筛、重点、直接 AC、固定原队、成员敏感性、细分等标量缓存。
5. 有限配比的标量：必须同时连接 `TEAM_MEMBERS.csv.gz` 和冻结 `PANELS_USED.csv`，其绑定证据类型单列。
6. same-room current_classes pool JSON：已确认是 `scalar_only_delivery_adapter`，不能当作完整几何缓存。

每个请求严格区分 `reused_full`（完整端点直接复用）、`geometry_replay_existing_team`（已有实体因旧交付只保留标量而补回几何）、`new_physical_team`（精确缓存中未存在的团队）。标量旧实体的回放必须核对旧 Q、分项及可比结构标量，不能算作新的独立人群证据。已有结果缺 Q 的状态也要保持，而非只验证已有数值。

`run` 只执行冻结计划中需要原生计算的端点。它导入已有 `new_team_engine.Engine.evaluate`，调用原有融合、原有评分和原有记录时间连接；评分缓存中已有的分项回填到结果。所有结果按池、按批 JSONL 保存，可断点续算，最后生成完整几何和标量总表。来源、成员和结果的哈希均保留。

示例（由主线程冻结实际路径后运行）：

```bash
PYTHONPATH=runtime_deps python3 stage02_engine/code/ac_endpoint_runtime.py prepare \
  --repo repo --work . --pools PRIMARY_INPUT_SNAPSHOT.json ADMITTED_INPUT_SNAPSHOT.json \
  --requests TEAM_REQUESTS.csv.gz --output stage02_engine/cache_plan \
  --commit ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff \
  --previous-import-audit HOHONET_v21_reaudit_20261029/stage06_reproduction/IMPORT_DEPENDENCY_AUDIT.json
PYTHONPATH=runtime_deps python3 stage02_engine/code/ac_endpoint_runtime.py run \
  --repo repo --plan stage02_engine/cache_plan --output ENDPOINT_OUTPUT --jobs 7
```

## 测量及解释边界

`code/ac_measure_events.py` 仅从保存的端点计算变化，所有有符号差为 `C−A`，另保留绝对差。其 Q 分项、有效转折、短结构、参考保留和几何配对沿用已有 v2.1 模块，新增结果状态、实际 n/m、MV50 人数能力提示及可比劳动分母。

缺 Q 不填 0，也不统一称为融合失败。原始 `score_status / geometry_status / geometry_reason / order_status` 保留；`fusion_execution_exception`、少于四节点、未形成可用点序列（legacy `no_connection`）、无效底面/完整几何、测量异常、仅底面参考、其它缺 Q 分别列出。legacy `no_connection`不专指连接原因，可能还包括选中节点位置未决；只有完整full_state才能具体区分。有效的部分底面可以测量几何，但完整共识几何另有独立列。状态转换使用全部已执行事件；Q、底面、射线几何、劳动各自使用有效配对分母。

记录劳动分别报告：全部记录已知且来源计数向量完全相同；全部记录已知且两队同一单一来源。后一条件可覆盖不等人数设计，必须同时报告总量和每成员值，并明确人数变化。它是历史记录劳动，不是融合 CPU 时间或新做标注的实验速度。

几何单位定向勘误：`geometry_bev_distance_AC = 1 − floor IoU`，无量纲；`geometry_centroid_distance_AC` 才是相机高度 h。面积是 h²，高度和位置坐标是 h，射线角度是度。旧包文件保持原样。本轮字典和正文采用正确单位。

冻结源码的 MV50 为 `2*support >= N`，阈值 `ceil(N/2)`，N 是团队全员数；偶数团队正好半数可入选。替换块人数达到该阈值只说明人数能力，不能证明相应节点实际共同支持、能正确定位或能连接成环。

事件保留无序/有序的物理团队对 ID。跨方法选到同一对团队不得当独立重复证据。直接 AC 没有 B 对照，因此本表不宣称“跨类比同类变化更大”；与严格 ABC 的对照由主分析在兼容条件上另做。

## 验证

`ADAPTER_OFFLINE_VALIDATION.json` 使用既有保存端点验证完整输出、无连接、少于四节点与底面无效四种接口路径；没有调用新的融合、评分或分类拟合。正式运行后，`CACHE_PLAN.json`、`RUN_RECEIPT.json`、每池 `REPLAY_PARITY.json` 和 `MEASUREMENT_RECEIPT.json` 分别记录复用、原生执行、旧实体回放一致性及测量完成率。


## 本轮冻结执行与可迁移复现

冻结请求478,012队、471,758方法事件、258个合法图片目标池；完整cache扫描预先确定474,332个新物理团队、2,027个已有实体的几何回放、1,653个完整端点直接复用。最终运行以`stage01_registered/EXECUTION_FROZEN.json`放行为准。先执行字典序前7池计时，再恢复全部池；恢复结果不重复融合或评分。

`ac_measure_events.py --watch`只在某池`CHECKS.json`完成后测量该池一次，将宽表存为独立gzip分片，全部池完成后合并一次。每个scalar和metric分片都读到gzip EOF并核对CSV列宽、无重复身份和完整身份集合。首波、逐池和最终回执分别保留。

每池`CHECKS.acquisition_counts`仅计本次pass新取得的端点，恢复首波的7池这一字段为零；`native_evaluations_this_run`因此正确排除了已恢复首波。核心端点原生评价476,359次，分为首波10,991次和后续465,368次；完整复用1,653条中2条在初次资源失败前已经保存。`code/finalize_execution_accounting.py`生成`EXECUTION_ACCOUNTING_CLARIFICATION.json`，用逐池结果和完整scalar逐行重验这些口径，并明确撤回过早的字段命名担忧。病例full_state回放、独立最小复现和其它QA另计，不增加物理团队样本。

在不同工作目录复现时，可运行`code/relocate_execution_plan.py`，指定新的目标计划目录及新旧workspace根。它复制计划，只更新运行时需要打开的源路径：引擎根、两份池输入、冻结请求表。全部科学哈希、语义身份、复用决定和原始来源路径保持；原计划不覆盖。建议加`--verify-inputs`，在运行前核验重新放置的实际输入字节。例：

```bash
python3 stage02_engine/code/relocate_execution_plan.py \
  --source-plan stage02_engine/cache_plan \
  --destination-plan stage02_engine/cache_plan_relocated \
  --old-workspace-root /workspace/scratch/2109120ca4e8 \
  --new-workspace-root /absolute/path/to/reproduction \
  --verify-inputs
```

`source_contract`中的相对引擎文件清单及两份原始池是最小科学输入；人员标签参与事件解释和设计，而不进入融合引擎。完整几何的逐池JSONL分片是主要交付，合并几何文件只是一份可再生检索副本。测量器、病例导出与配套复现代码都可以直接使用逐池分片。

## 完成状态与正式复现入口

258池、478,012个团队均已完成，完整逐池原生几何与scalar分片全部保存。端点阶段之后的可选全量geometry拼接因临时空间限制主动停止，未中断任何池的科学计算；`FINAL_CONSOLIDATION_STOP_RECEIPT.json`、`REDUNDANT_CONSOLIDATION_CLEANUP.json`保留处理经过。最终`stage03_endpoints/RUN_RECEIPT.json`由全部池CHECKS和完整标量身份集合核验生成，明确记录权威几何位于逐池分片，不声称冗余合并几何成功。`ENDPOINT_SCALARS.csv.gz`仍完整保留。

全部258个metric分片包含471,758方法事件、431列。完整测量回执为complete=true。已完成的冗余合并EVENT_METRICS副本为保存分析空间而移除，`stage04_metrics/DELIVERY_STORAGE_INDEX.json`（以实际交付索引为准）说明分片读取路径；不丢失任何事件或指标。

2,027个已有标量实体的回放逐条保持状态与Q可得性，其中71个原缺Q仍缺失；所有可比标量最大差1.4210854715202004e−13，无例外。精确证据在`OLD_SCALAR_REPLAY_PARITY_FULL.csv.gz`和`EXECUTION_ACCOUNTING_CLARIFICATION.json`。

正式最小复现优先采用研究根目录`code/reproduce_one_team.py`和`stage07_reproduction/README_ZH.md`，它已经使用导出的142个当前提交源/输入文件实际复现一个端点，验证23个标量与完整几何/状态一致。根目录`code/relocate_frozen_plan.py`已经验证四个运行路径更新而科学哈希不变；本目录`relocate_execution_plan.py`作为辅助保留。
