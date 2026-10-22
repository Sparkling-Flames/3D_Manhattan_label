# 联合类别匹配换人/换类专题：文件与复现

本目录属于 `personnel_effective_exchange_conditions_20261022` 新阶段，不修改 `personnel_useful_taxonomy_v3_20261021`。首读 [综合判断](REPORT_ZH.md)，再按条件读 [Manual 纯块](MANUAL_NATIVE_FINDINGS_ZH.md)、[Semi 纯块](SEMI_NATIVE_FINDINGS_ZH.md)、[跨条件三方法共同锚点](CROSS_METHOD_FINDINGS_ZH.md)。

## 文件入口

| 内容 | 入口 | 主键/用途 |
|---|---|---|
| 全部阶段完成与去重 | `FINAL_COVERAGE_RECEIPT.json`、`ACTUAL_COVERAGE.csv` | 阶段×条件×支持域；事件引用、物理三元组、团队分别计数 |
| 全部事件精确索引 | `ALL_EVENT_REFERENCE_INDEX.csv.gz` | `(evaluation_stage,event_id)`；event_id 全局亦唯一 |
| 物理三队重复使用 | `PHYSICAL_TRIPLE_USE_INDEX.csv.gz` | `physical_set_id`；按实际团队键重建，不依赖旧哈希命名 |
| 完整原生逐事件结果 | `NATIVE_MANUAL_EVENTS_COMPLETE.csv.gz`、`NATIVE_SEMI_EVENTS_COMPLETE.csv.gz` | `event_id`，1,244/394 行 |
| 完整缓存新匹配逐事件结果 | `CACHED_MANUAL_EVENTS_COMPLETE.csv.gz`、`CACHED_SEMI_EVENTS_COMPLETE.csv.gz` | `event_id`，28,843/4,432 行 |
| 完整共同锚点逐事件结果 | `CROSS_MANUAL_EVENTS_COMPLETE.csv.gz`、`CROSS_SEMI_EVENTS_COMPLETE.csv.gz` | `event_id`，9,408/2,989 行；方法成员并列项是引用，不是独立锚点 |
| 去重端点精确引用 | `ALL_USED_TEAM_REFERENCES.csv.gz` | `team_key`；44,328 行，成员、请求、标量、几何源路径 |
| 可独立重读的必要端点 | `ALL_USED_ENDPOINT_SCALARS.csv.gz`、`ALL_USED_ENDPOINT_GEOMETRY.csv.gz` | 各 44,328 行，优先读取，无需取回前轮全部大缓存 |
| 端点源文件完整性 | `ENDPOINT_SOURCE_FILES.csv` | `source_kind,file`；源文件 SHA 与引用团队数 |
| 标签、训练模型、代码依赖 | `INPUT_AND_CODE_DEPENDENCIES.csv`、`ENVIRONMENT.json` | 精确 SHA，原仓库路径，Python/包版本 |
| 理论与实际机会 | `OPPORTUNITY_COMPLETION.csv`、`NATIVE_CAPACITY.csv.gz`、`CACHED_OPPORTUNITIES.csv.gz`、`CROSS_*_OPPORTUNITIES.csv.gz` | 精确未展开数量；原生有序块容量、全部背景/锚点机会、三方法机会交集 |
| 原生精确团队和请求 | `NATIVE_ALL_TEAMS.csv.gz`、`NATIVE_TEAM_REQUEST.csv.gz` | 4,844 个全部团队；4,837 个当时缺失团队 |
| 全指标、图/楼响应 | `summaries/{native,cached,cross}/{manual,semi}/` | 每个指标都有实际可用分母；不是仅有总分摘要 |
| 方法间相同支持 | `CROSS_*_ANCHOR_RESPONSES.csv.gz`、`CROSS_*_SAME_SUPPORT_SUMMARY.csv`、`CROSS_*_PAIRED_METHOD_DIFFERENCES.csv.gz` | `common_anchor_id` 下比较；最终质量/时间交集保持一致 |
| 代表方向和成员 | `NATIVE_PREFERRED_*`、`SEMI_NATIVE_PREFERRED_*` | 64 个 Manual 和 28 个 Semi 推荐方向的完整事件、成员/中心、图/楼、n/m |
| 图与原数据 | `figures/` | 独立 PNG/PDF，图中值另有 CSV |

大表以 gzip CSV 交付，可独立解压读取，不要求只从 ZIP 提取。`results/` 中的逐池工作检查点和端点子集是恢复工作副本；发布包用最终完整表、去重源引用和回执，不重复收录这些缓存。`*.tmp` 是非提交临时文件，不属于成果。

`evaluate_joint.sources()` 优先读取本目录的 44,328 端点对子；所有请求键满足后即停止回退检索。因此下载这些必要端点、完整事件/请求、小型标签/历史输入及代码即可重算本专题事件，不需要下载 V3 的全部团队缓存。原始来源仍在引用表中，读取回退不改变 typed 解析器、几何计算或已经完成的事件数值。

## 事件字段合同

`team_A/team_B/team_C` 为冻结融合的实际集合标识；`A_member_workers/B_member_workers/C_member_workers` 是完整成员；`common_background` 是 A∩B=A∩C。`outgoing_block_X/same_count_block_Y/changed_count_block_Z` 保存出入块。纯块实验三块互不相交；缓存面板 B/C 可重叠，实际 `m_BC` 单独记录。

`n` 是总人数；`m_AB/m_AC/m_BC` 是真实替换人数；`composition_turnover_AC` 是完整类别人数向量 L1 差的一半，即改变的类别席位，不能当作真实 m。`A_counts/B_counts/C_counts` 保存向量，类号只在 `condition/heldout_building` 相应外折内解释。`selected_family/coarse_k` 保留外折方法身份。

`same_*` 为 B−A，`cross_*` 为 C−A，`net_*` 为 C−B。误差类指标减小通常有利，召回/质量类增大有利；几何差异的大小只表示变化，不表示质量改善。`within_*` 和 `cross_*` 的几何比较使用原冻结方法，`common_geometry_*` 限定三队都完整且指标都可计算的共同支持。

`all_scored/all_complete` 与三臂 `*_failure/*_score_status` 保留失败；失败不自动写成 0 分。`recorded_time_single_source` 要求三臂所有成员都有有效时间且同一单一来源；秒数在 `*_source_time_total_seconds`，来源在 `*_time_source_kinds`。时间比和质量差使用同一组事件时，汇总 `scope` 含 `scored_triple_time_common`；只研究质量时用 `scored_triple_quality_common`。`all_quality` 保留全部事件但各指标可能有不同缺失分母，不能直接称为共同 Q/T 分母。

`training_class_center_QT_direction` 是完整楼外类中心方向，`training_member_QT_direction` 是本次 Y/Z 实际成员的历史均值方向。缓存冻结注册表旧字段 `training_QT_direction` 的含义见 [修订说明](DIRECTION_FIELD_CLARIFICATION_ZH.md)，不要单凭该旧字段构造类方向。`pred_QT_both_improve_BC` 则来自前轮冻结的楼外类别交互模型，未重拟合目标端点。

原生汇总先对相同物理三元组去重，然后按共同背景→n→图→楼等权。方法共同锚点比较先对方法自己的 B/C 并列成员平均，再比较相同锚点。`ALL_COMPONENTS.csv.gz` 每行给指标、均值和实际事件/图/楼数；主要指标另有楼 bootstrap 区间，其余指标的区间留空。小楼数区间不冒称外部验证。完整物理/引用分母在总索引中，不能以大量引用扩大独立样本量。

## 复现顺序

原仓库固定基础 main 为 `324dba44d0a82d9d64a62965f2e549ee05165417`；前轮 v3 的恢复交付及本轮外部标签按依赖表 SHA 校验。保持 `HOHONET/research/...` 相对目录结构。不要在复现时修改冻结评分、人员资格、原图参考、环序或融合门槛。

```bash
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/joint_design.py
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/register_cached_matches.py
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/register_cross_comparison.py manual
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/register_cross_comparison.py semi
```

上述注册程序不调用融合。原生缺口由总研究的 `expanded_blocks/run_native.py` 执行，**本次已全部完成**，按 `ALL_USED_TEAM_REFERENCES.csv.gz` 复用即可。新原生源文件在 `../expanded_blocks/batches/joint_001..003/`，每批有 REQUESTS、SCALARS、GEOMETRY、COMPLETION；没有必要重复融合已存在的精确成员集合。

```bash
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py native manual
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py native semi
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py cached manual
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py cached semi
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py cross manual
python research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py cross semi
```

之后对所需阶段/条件运行 `summarize_joint.py {native|cached|cross} {manual|semi}`；运行 `focused_native.py`、`focused_semi_native.py`、`compare_cross_methods.py manual` / `semi`、`plot_joint_results.py`、`finalize_joint_delivery.py`。所有脚本会按阶段/条件保存，不将全部结果积压到最后。汇总可直接读完成的事件表，不要求重新运行注册或评价。

代码使用 Python 标准库、NumPy、pandas、SciPy、Shapely、Matplotlib；实际版本见 `ENVIRONMENT.json`。旧冻结几何核原先从 `/tmp/hohonet_deps` 插入依赖路径，本目录不打包虚拟环境。正常环境安装对应包即可，核文件位置与 SHA 在依赖表；新代码强制 BLAS/OMP/MKL 单线程。原答图像解释归总研究案例目录，本文图为实际数值图，没有生成伪原图。

## 已完成与未覆盖

所有登记请求、全部 47,310 条事件引用和共同锚点比较已经完成。纯块仍是每方向两路径，缓存是全部背景检查后每背景一锚点，不宣称全人员具体成员组合穷尽；加入顺序没有展开。细类没有在本专题获得新的独立实际用途结论；相同新 ABC 上的连续 QT 指导策略未另行训练。前轮连续基线和真实选队研究保留原阶段身份，不能混入本次 matched ABC 的实验分母。
