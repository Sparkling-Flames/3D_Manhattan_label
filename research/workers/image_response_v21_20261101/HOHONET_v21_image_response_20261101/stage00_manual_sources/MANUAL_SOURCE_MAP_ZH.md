# 普通 Manual 自然进入人数研究：源资料与缓存映射

核查日期：2026-10-31/11-01。仓库 `Sparkling-Flames/3D_Manhattan_label`，固定提交 `e1873bfadc1d0e61499809c91fba9dc39c717f83`。本阶段只读来源和方法，不重新融合、不以旧 24/48 条结论替代 256 主分析。

## 1. 当前范围的实际统计单位

从 `research/data/releases/v2.1/pools/DEPENDENCIES.json` 的 263 条记录实计：

|条件 / 层|池数|唯一图片|复用端点|复用几何重新评分|新池|
|---|---:|---:|---:|---:|---:|
|ordinary_manual|206|206|145|32|29|
|doorway_manual（历史自然池）|17|17|14|3|0|
|special_manual / OOS|2|2|1|1|0|
|ordinary_semi|37|37|24|8|5|
|special_semi / OOS|1|1|0|1|0|

因此，当前自然研究的“223 Manual”是 **206 普通 + 17 历史门洞**；194 既有池 = 177 普通 + 17 门洞；29 新池均为普通主目标。225 Manual 全体含 2 个 OOS，不能仅筛 condition=manual 就把它们纳入正式质量主分析。所有 225 个主表 Manual 池对应 225 张不同图片。普通 N≥30 是 171 图：157 既有 + 14 新。

额外合法目标位于 `admitted_space_extension`：31 池 / 231 原答，30 Manual 池 / 227 原答 + 1 Semi 池 / 4 原答，对应既有 28 图、30 目标。其 Manual 与 206 主目标相加为 236 目标池、仍 206 张普通图。不能把追加目标池当作新增独立图片；合并时先图内目标等权，再按图 / 楼汇总。额外池 N=3–17，没有 N≥30 支持。

门洞本轮以 `research_readiness_20261031/README.md` 页首明确采用的 584/439 为准。paper_evidence README 页首 553 是历史内容，不能覆盖较新的明确采用条目。439 的增补筛查发生在 533 版结果已知以后，不能写成完全盲筛或预注册。

## 2. 最小逐路径输入

主目标路径标量和成员身份已物化，无须先恢复旧巨型端点表：

1. `research/data/releases/v2.1/natural_analysis_restored/inputs/<pool_id>.csv.gz`：159 文件，327,760,505 bytes；无改变的既有 Manual 池恢复输入。
2. `research/data/releases/v2.1/natural_inputs/<pool_id>.csv.gz`：79 文件（另有两份检查 JSON）；64 Manual + 15 secondary / OOS / 小池更新输入。CSV 文件总字节 117,351,023。
3. `research/data/releases/v2.1/admitted_space_extension/natural_inputs/<pool_id>.csv.gz`：31 文件，8,456,020 bytes，合法其它空间补充。
4. 元数据 `pools/INPUT_SNAPSHOT.json`（17,148,165 bytes）；冻结难度 `paper_evidence_20261030/IMAGE_DIFFICULTY_MAPPING.csv`。
5. 可计算结构条件 `difficulty_computable_comparison/INPUT_RECORDS.csv.gz`；源自当前 `condition_classification/RAW_CONDITION_RESPONSE_RECORDS.csv.gz`，不根据本轮曲线重新分难度。

完整文件路径、字节和 Git blob sha 见本目录 `DOWNLOAD_PLAN.json`。文件目录证据见 `DIRECTORY_MANIFEST_PART1.json`。只读清单不是结果计算验证。

每行是一个精确 path × k 前缀，并包含：

- 键：team_key、pool_id、path_id、stratum、policy、k。
- 精确成员：member_workers、member_object_ids，分隔符 |。
- 元数据：image / image_id、building、condition、layer、difficulty、pool_n、reference_id、reference_version、data_release。
- 质量：B8L2、D10、WQ、IoU3D100、iou_2d、S_bottom_deg、dir、Hmean、Hcenter、omission、extension、boundary_loss、direction_loss、height_loss、global_height_loss、local_height_loss、height_mean_ratio。
- 表达 / 形状：floor_turn5_n、floor_redundant5_n、floor_short_edge_03_n、floor_area_camera_h2、height_mean_h、top_y_mean_px、bottom_y_mean_px、nodes。
- 状态：score_status、complete_evaluable、connection_available、below_four、policy_deferred、geometry_status；部分已有 score_available、score_failure_nonpolicy、incomplete_nonpolicy。
- 同源劳动：source_time_total_seconds、source_time_known_n。

这些输入保留实际路径频次。不能对 team_key 去重后再等权计算人数响应，也不能把同一团队的多次出现当独立团队。

主 `pooled256` 仅包含 old24、prior_new24、new104A、new104B，24+24+104+104=256。prior_focus48 是独立定向敏感性，排除于主256；all_history304 不能冒充主256。新目标是 new_space256。path_id 必须连同 stratum 保持唯一身份。

## 3. 两人真实补算

原 natural_inputs 的 k=2 继续存历史延期，并非融合失败。实际两人已单独完成：

- `two_person_natural256/PAIRED_PATH_RESULTS.csv.gz`（6,165,307 bytes）
- `two_person_natural256/PATH_LINKS.csv.gz`（1,983,694 bytes）
- `two_person_natural256/K2_CURVE_OVERLAY.csv`（73,817 bytes）
- `two_person_natural256/pools/` 为不同实际成员对结果及节点支持。

223 池 / 57,088 路径 / 43,257 不同成员对，49,768 路径可评分、7,304 未连接、16 底面不可评分。应以独立覆盖层补入本轮分析视图并标记来源，不改旧数据，不把实际补算和旧延期称为同一实验版本。相邻变化使用各自共同可评路径。

## 4. 既有几何波动可直接复用

`sampling_extension_20261026/analysis_geometry26/results_stage2/` 已有 pooled256 全体几何统计：

- GEOMETRY_PATH_PRECISION.csv.gz
- GEOMETRY_TO_ACTUAL_FULL_IMAGE.csv.gz
- GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz
- GEOMETRY_DISTANCE_COMPUTE_ACCOUNTING.csv.gz

完整清单见 `GEOMETRY_DOWNLOAD_PLAN.json`。按 pool_id 连接当前 v2.1 合法池并替换元数据即可复用成员与融合均未改变的池；不复用旧 Q，因为部分参考已更新。新 / 变更池已有 `v2.1/new_space_geometry/NEW_SPACE_GEOMETRY_CURVES.csv.gz`，冻结 distance_matrices 与 U 统计，同样每池 256 路径。

指标：
- V_floor = 完整合法地面团队对的 1−IoU。
- V_centroid_h = 地面多边形质心距离（相机高度单位）。
- V_height_h = 高度绝对差（相机高度单位）。
- V_turn5 / V_nodes = 转折数 / 节点数绝对差。

主估计对不同路径索引的有效成对距离等权，分母 q(q−1)，只移除同一路径自配对，保留不同路径抽中同队的零距离。MCSE 用整条路径 jackknife，不把 O(R²) 成对距离当 O(R²) 独立观测。满员合法单队 V=0 是有限人员池退化，不代表准确或意见一致。失败路径保持状态分母、没有完整几何的路径不进入几何距离分母。

全体逐路径直接相邻几何距离不在路径标量输入内。可以先算已有转折 / 面积 / 高度 / Q 跳变，再对代表团队恢复精确几何；无需重算全体两两距离。原 geometry_extension.py 的物理来源：
- 旧 `personnel_population_curves_v2_20261023/results/ENDPOINT_GEOMETRY.json.gz`
- prior 精度 `sampling_precision_20261025/new_endpoints/table_shards/NEW_ENDPOINT_GEOMETRY_COMPACT/*.jsonl.gz`
- 追加208 `sampling_extension_20261026/new_endpoints26/stage{1,2}/parts/<pool_id>/*.geometry_compact.jsonl.gz`
- 当前新目标 `v2.1/new_space_natural256/<pool_id>/part_*.jsonl.gz`。

部分物理缓存目录未在 GitHub contents 中列出；不要由缺可选整表推断缺端点。准确归档映射入口 `sampling_extension_20261026/LOCAL_SOURCE_FILES.csv`、`REUSED_INPUTS.json` 和 `SOURCE_ARCHIVE_RECEIPT.json`，作者逻辑缓存与实际原生分片分别记录。

## 5. 状态与质量分项方法

沿用已经核验的 `analysis_precision26/analyze_natural.py::status_class`：
- deferred k2（仅历史视图）
- not_executed
- scoreable
- reference_unavailable
- consensus_not_formed
- output_unscoreable
- failure_other_preserved
- unclassified_or_missing_status

不能把 failure_rate（旧“非延期缺分总率”）直接写成实际融合失败。实际 failure / output_unscoreable 按已执行非延期尝试分母，Q 按有限分数分母；真0保持0。

具名质量块从冻结 `derive_frozen_blocks.py` 投影：
B8_floor_block、B8_direction_block、B8_global_height_block、B8_local_height_block、B8_height_block、D10_direction_block。它们是无量纲损失、越低越好，不是0–100分或可加的百分点贡献。原Q不变；同时验证 B8_formula_residual。

可计算结构条件包括 ref_turn5、ref_H、ref_short_edges、ref_min_horizontal_deg、ref_short_min_horizontal_deg、has_short、conditional_short_span。人工难度维持 current mapping；例如 pa4-11 现行 medium，不从曲线反推。

## 6. 当前已做与本轮仍需新增分析

已有：256边际质量 / P10 / SD / 状态 / 分项，固定人数区间，结构均值，256同人数几何差异，有限池精确校核，整体曲线bootstrap与路径批次精度比较。这里不能只因文件存在声称本轮已验算；必须逐路径重算对照代表切片并核身份。

新增研究应集中于：每张图整条后续变化包络；短暂平缓后的跳变；质量、P10、成员波动和几何 / 状态稳定的分离；固定共同图片的区间方向分解；现行439门洞独立分析；代表团队支持票—位置—连接的可追溯机制解释。

### 已存本阶段原文

`repo/` 保留四个用户入口，以及依赖 / readme / 输入生成器 / 状态分析器 / 几何分析器 / 冻结分项脚本原文。不改来源文件，不把本索引作为原研究结论。

