# 门洞源核查、归一化、几何回连和案例交接

## 固定采用身份

- 仓库提交：`e1873bfadc1d0e61499809c91fba9dc39c717f83`。
- 现行门洞总体：584 份筛前、439 份筛后；17 图、9 楼。553、533、524、444 为历史版本，未作为本轮当前池。
- 85 个登记池中 72 个非空、13 个零容量；非空池各 k 保留 256 个原始排列前缀，共 372,480 行。零容量池仍在索引中。
- 共同筛前／筛后 17 图可比较到 k=14；空间1／空间2同时有 k=3 容量仅 4 图，k=4 仅 1 图，k≥5 无共同图。短侧池不宜强行宣称人数平台。
- 旧 `POOLS.json` 的 `shared_before_after_identical` 与参考 gate 个别字段为沿用字符串；本轮按最终筛查账本、真实成员及完整最终参考核验，不依赖这些旧文字。

## 交付层次

1. `stage00_doorway_sources/`：采用链原文、85 池成员核查、容量面板、下载路径和逐源指针、旧完整轨迹的外部包登记。
2. `stage02_normalized/doorway/`：纯标量标准化。每个非空池每个 k 均验证为 256 行，逐行成员等于保存的完整排列经过当前池过滤后的前缀。源均值、SD、P10、成功率、有效数与 adopted `NATURAL_CURVES.csv` 全部 4,365 行逐项一致，最大浮点差 4.7e-13。
3. `stage02_normalized/doorway_enriched/`：另存 85 个每池表和索引；精确回连几何、原指标分项与状态。102 个 gzip 全部可完整读取。原标量文件未覆盖。
4. `stage04_doorway_cases/`：两个后段案例的原图、完整原答、最终参考、四端点完整轨迹、票账、英文 PNG/PDF/SVG、5.66MB 自包含查看器及中文机制说明。

## 精确身份与几何复用

当前路径使用 240,453 个物理缓存源键，对应 240,279 个精确成员团队。源键可来自 Pro shard、逐行 native JSONL，或者一个新增目标的原答单人条目。`ENDPOINT_SOURCES.csv.gz` 保留源路径、行号、成员与统一团队键；`GEOMETRY_CATALOG_INDEX.csv` 按图索引全部可取几何。

几何 catalog 有 240,359 个已保存状态。k≥3 同成员多来源坐标均通过 atol=1e-9 核验，部分 serialization 的浮点末位或空状态字段导致不同 geometry_key；不得把这些当作独立人员证据。k=2 确实存在 Pro 实际 MV50 补充输出与后续 native 两人排序延迟的不同口径，因此保持独立状态、单独标记，不进入 k≥3 主分析。root 的距离计算按 endpoint_source_key 精确回连，保留原路径权重。

## 最终评分分项映射

- `B8L2`、`D10`、`IoU3D100` 始终以当前 `PAIRED_PATH_VALUES.csv.gz` 为正式数值，回连只做一致性验证，未覆盖这些 Q。
- Pro 分项从 `DOORWAY_04_PHYSICAL_GEOMETRY.zip` 中 `stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz` 取最终恢复参考的结果，键为 physical_team_key + target。不能使用原 shard 中尚未恢复上下点对的旧 target_scores。
- native 分项按所指 JSONL 的真实行和 target 取其 `scores[target]`，保留 `iou_2d/S_bottom_deg/dir/Hmean/Hcenter/omission/extension` 等可定义值。
- native 未显式保存的 B8 损失块按冻结 `working_models.py` 公式补出：floor 为 `(1-I)/I + Sb²/32`（仅 I>0），direction 为 `1.5 D²/(D²+64)`，height 为 `(Hm/0.8)²+(Hc/0.25)²`；D10 direction 的分母常数为 100。它们是质量公式中的损失块，不是固定权重或因果贡献。
- 所有 372,480 行 Q 的回连最大差 1.43e-14，缺失位置完全相同。

几何描述沿用已有 v2 定义：有效转折为角度>5°；短结构边为周长占比<4%、两端转折≥15°；另外保留绝对长度<0.3 个相机高度的短边数。两种“短边”没有混成一项。顶高由已保存顶底点对按原相机高度归一化公式计算，未测量新参考。对旧保存值复核：转折、短边、冗余点、面积、质心差为 0，顶高最大差 8.9e-16。

## 状态口径

`complete_output` 明确定义为原表的“完整且可评分”，并同时保留原 `complete_evaluable`。`geometry_formed`、`geometry_eligible`、`floor_valid`、连接与节点门槛分别给出，失败和生成后不可评分分开。

k≥3 全部源行的三项 Q 是否有限与 complete_evaluable 一致。筛前原答 k=1 有 21 条重复路径记录对应 3 份有限 Q 但原完整标记为 False 的记录，仍属于原答诊断，不能称为融合失败。当前 B8L2 的真实零值记录为 0；缺失没有填 0。

## 原图、原答与轨迹

- 完整原答：冻结 `FROZEN_RECORDS.json.gz`；当前 584／439 成员及最终空间标签来自筛查 ledger 和池表。
- 完整最终参考：`stage04_computation/recovered_reference_scores/FINAL_REFERENCES.json`，51 个 image×target；没有用旧草案代替。
- 17 张原始全景已嵌入 `DOORWAY_02_RESULTS_CURVES_CASES.zip/stage06_cases/DOORWAY_ANSWERS_AND_CONSENSUS.html`。本轮只抽取所需两图并重新绘制当前端点，不使用旧 553 版池结论。
- 该 ZIP 的 `stage06_cases/mechanism_traces/` 保存 78 个既有完整轨迹。另有当前使用的 460 个团队的 full_state_pointer，可从 `CURRENT_DOORWAY_FULL_STATE_CANDIDATES.csv` 回到 7 个已登记 DATA 包。已展开的 GitHub 首个具体 full_state 路径返回 404，不能把 pointer 存在当作已本地取得。
- current native JSONL 只有已选支持数，没有完整未选身份组和来源环。必要的三个案例端点进行了独立登记的诊断回放，原代码按固定提交读取，全部几何、状态、支持和 Q 验证通过，才用于机制解释。

## 案例新增结论

uNb47 31→32 人，256 路径平均 ΔB8L2=+17.877；全部 32 种缺一人组合均权 +17.376，21/32 升质、19/32 加节点。代表路径包含 15→16 票局部结构进入，同时发生另一区域原答点对重新分组。

jh09 23→24 人，256 路径平均 +5.868；精确 24 组合均权 +5.481，17/24 升质、12/24 加节点。代表路径的 11 票局部组加上 W035 达到 12 票，阈值未降低。满员仍遗漏采用整体参考约 43.1%；当前 13 人全部兼容池也遗漏约 43.6%，不能只用混合单侧答案解释。

两例满员都只有一队，换组方差为零是有限组合的结果。uNb47、jh09 仍需查看具体结构的语义范围，报告未宣称 GT 出错或人员乱标。详细说明见 `stage04_doorway_cases/DOORWAY_LATE_CASES_ZH.md`。
