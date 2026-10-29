# HOHONET v2.1：容量、执行、输出状态与既有严格 ABC 的衔接

## 1. 已完成什么

本目录没有新增 ABC、重聚类或重评旧 ABC。它把本轮冻结的直接 AC/整类/联盟登记与实际端点结果连起来，
并将既有严格 ABC 作为有明确成员关系的独立参照。正式来源提交为
`ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff`。

全量状态分析覆盖 **258 个目标池、471,758 个方法事件、
412,839 个不同物理端点对、478,012 个不同团队端点**。
方法事件可以共享同一物理对，多个设计链接也可以共享同一事件；这几种计数不能互当独立样本。
主漏斗限于普通 Manual、等人数、两个纯类别替换块，共 **311,640 个方法事件、
226 个实际登记目标池**。容量分母仍是全部 236 个普通 Manual 合法目标池：
主目标 206，其他准入目标 30。状态表另保留 Semi 等数据域，空间目标始终不混合。

`FUNNEL_AND_STRICT_BRIDGE_RECEIPT.json` 与 `OUTPUT_STATE_TRANSITION_RECEIPT.json` 均为 complete=true。
每个指标有自身有效分母；缺 Q 保持缺失，不填 0。
容量阶段 USED 标签与角色表虽沿用 ALL_LOBO 文件名，实际只有 22 个 LOBO 折，不含 ALL。
完整入口另含 5 方法的 ALL 描述名单，但 ALL 不参与逐图容量、组队或本节比较。

## 2. 容量到结果：先看覆盖，再解释方向

完整链条为：全部合法池 → N≥n+m → 已有历史分类人员≥2m → 存在两类各≥m → 实际登记 →
原生执行完成 → 该指标可评 → 正、负、零变化。
`history_insufficient_after_total_pools` 是在总人数充足后，可用于 X/Z 的历史分类人员不足；
类别容量不足在其后单列。未登记、运行未完成、实际结构失败、几何无效、测量异常和指标不可评各保留独立字段。
历史未知人员可进入 D，但不能被臆测为某类后进入 X/Z。

以下 B8L2 表对每张池内的精确 X/Z 块先平均各登记背景，再等权块；同池不同类别方向等权，最后等权池。
这是本次冻结设计覆盖内的描述量，不是随机抽取真实人群的无偏总体效应。
正向以每楼外折既有角色排名从低到高的 **canonical A→C** 定义；TARGET/RAW 的角色轴与 JOINT 的轴不同。
均值ΔQ及平均|ΔQ|是不同量。零以绝对值≤1e-9定义。
不同方法的实际可行池及具体成员可能不同；本表用于各方法自身覆盖的说明，不能直接按均值大小给方法排名。
跨方法的共同池、共同人数与块规模比较应另读主效果报告。

| 方法 | n | m | 容量池 | 登记池 | B8L2可评池 | 可评楼 | 均值ΔQ | 平均\|ΔQ\| | 正向池 | 负向池 | 零池 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OPPJOINT K3 | 20 | 10 | 82 | 82 | 82 | 11 | 0.4234 | 3.1981 | 45 | 37 | 0 |
| OPPJOINT K4 | 20 | 10 | 107 | 107 | 107 | 16 | 1.0967 | 3.4879 | 54 | 53 | 0 |
| TARGET K3 | 20 | 10 | 3 | 3 | 3 | 2 | 0.6032 | 1.4212 | 2 | 1 | 0 |
| RAW3 K3 | 20 | 10 | 19 | 19 | 19 | 7 | 0.1348 | 5.0093 | 11 | 8 | 0 |
| OPPJOINT K3 | 20 | 12 | 25 | 25 | 25 | 6 | 0.5992 | 4.0869 | 13 | 12 | 0 |
| OPPJOINT K4 | 20 | 12 | 36 | 36 | 36 | 10 | -0.0493 | 3.6342 | 17 | 19 | 0 |
| TARGET K3 | 20 | 12 | 0 | 0 | 0 | 0 | — | — | 0 | 0 | 0 |
| RAW3 K3 | 20 | 12 | 6 | 6 | 6 | 2 | -4.8400 | 6.9764 | 2 | 4 | 0 |
| OPPJOINT K3 | 22 | 12 | 24 | 11 | 11 | 4 | 1.0535 | 5.8123 | 3 | 8 | 0 |
| OPPJOINT K4 | 22 | 12 | 35 | 16 | 16 | 6 | 0.4917 | 3.8936 | 5 | 11 | 0 |
| TARGET K3 | 22 | 12 | 0 | 0 | 0 | 0 | — | — | 0 | 0 | 0 |
| RAW3 K3 | 22 | 12 | 4 | 0 | 0 | 0 | — | — | 0 | 0 | 0 |
| OPPJOINT K3 | 23 | 12 | 19 | 19 | 19 | 6 | 1.2897 | 4.1271 | 12 | 7 | 0 |
| OPPJOINT K4 | 23 | 12 | 27 | 27 | 27 | 10 | 0.8204 | 3.7124 | 15 | 12 | 0 |
| RAW3 K3 | 23 | 12 | 4 | 4 | 4 | 1 | -7.4557 | 7.5410 | 0 | 4 | 0 |
| OPPJOINT K3 | 25 | 10 | 52 | 52 | 52 | 11 | 0.2615 | 2.3016 | 28 | 24 | 0 |
| OPPJOINT K4 | 25 | 10 | 73 | 73 | 73 | 16 | 0.9323 | 2.6602 | 39 | 34 | 0 |
| TARGET K3 | 25 | 10 | 1 | 1 | 1 | 1 | 0.4113 | 0.4227 | 1 | 0 | 0 |
| RAW3 K3 | 25 | 10 | 9 | 9 | 9 | 4 | -0.0812 | 5.0367 | 4 | 5 | 0 |

对应 D10、全部阶段计数和运行/不可评原因在 `MAIN_SCALE_FUNNEL_BRIEF.csv`。
本轮的较大团队并非仅 n20：n23/m12 与 n25/m10 都是 N=35 池的最大共同背景前沿，表中这些容量池均已执行。
中间 n22/m12 并非处处被预先登记；例如 RAW 有 4 池容量而 n22 未登记，却都执行了 n23/m12。
这属于冻结设计选用门槛附近与实际池前沿网格，不是运行失败或该池无法换 12 人。
逐池根源在 `FIXED_SCALE_POOL_FUNNEL.csv.gz`；逐方向、逐 n/m、逐指标支持在
`POOL_DIRECTION_N_M_METRIC_SUPPORT.csv.gz`；完整汇总在
`CAPACITY_REGISTRATION_EXECUTION_EVALUABILITY_DIRECTION_FUNNEL.csv.gz`。
该主漏斗不把不等人数联盟及加人设计混入“等量替换”；这些设计的状态仍进入全量状态表，效应见主报告及成员背景敏感性目录。

必须保留两条解释边界：TARGET K3 的 m9/m10 全部在同一 TARGET K2 父类内；
JOINT K3/K4 的 m10/m12 全部不含对应楼外折历史最高 Q 的小类。
较广容量不能直接说明分类更优，也不能改写为“最高 Q 人群整块换入”。
n=m 的无背景全队替换有 `pure_n_equals_m` 独立标记；块能否达到 ceil(n/2) 的人数门槛与实际节点票数、定位、连接分开。

## 3. 输出状态不是缺 Q 风险差的附注

全量物理对中，两端都缺 Q 的有 **997 对**，
其中 **71 对**两端的原始输出状态还不同。
这些对的“缺 Q 风险变化”均可能为 0，因此不能据此写成“两队都成功”或“无输出差异”。
各域分母如下，物理对已经跨方法去重。

| condition | layer | scope | physical_pairs | both_present_pairs | one_missing_pairs | both_missing_pairs | both_missing_different_pairs | observed_failure_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| manual | ordinary_manual | other_admitted | 10570 | 8676 | 1674 | 220 | 0 | 1894 |
| manual | ordinary_manual | primary | 365766 | 358115 | 6993 | 658 | 71 | 7651 |
| semi | ordinary_semi | other_admitted | 8 | 8 | 0 | 0 | 0 | 0 |
| semi | ordinary_semi | primary | 36495 | 35130 | 1246 | 119 | 0 | 1365 |

`OUTPUT_STATE_TRANSITIONS_BY_POOL_METHOD_NM.csv.gz` 保留每池/方法/两队人数/实际 XZ 人数的
A_output_state→C_output_state 及所有原始 score_status 和状态标记；
`OUTPUT_STATE_TRANSITIONS_BY_DESIGN_FAMILY_INPUT_DIRECTION.csv.gz` 则按原设计输入方向恢复 A/C，
同一事件跨设计族不累加为新证据。
`GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv` 只按原生团队 key 排序确定列次序，
其 low/high 不是类别方向，更不是好坏方向。
`UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv` 提供不同团队而非对照对的分母。

below_four 表示入选节点不足四个；legacy `no_connection` 在表中显示为“未形成可用点序列”，
既可能涉及来源环缺失，也可能涉及入选节点位置未决，不能仅按旧字段名断言纯连接失败，需用 full_state 区分。
invalid_floor/invalid_full_geometry 表示几何无效；
measurement_exception、floor_only_reference 与未知原因缺 Q 独立保留。定义来自当前冻结测量代码，
不能把所有缺 Q 都称作融合失败。原始列和 example_event_id 均能回连完整事件与几何。

## 4. 严格 ABC 与新直接 AC 分别回答什么

已归一化 **18,847 个旧严格 ABC 事件**：既有 m7/m8 6,367，最新 m9/m10 12,480。
旧合并来源已含此前完成的 6,548 个新增 ABC，未再叠加一遍。
严格对照保持真实互斥的 D/X/Y/Z，B 始终是原来源类的同类换人。
`G_A=|C−A|−|B−A|` 和 `G_S=(|C−A|+|C−B|)/2−|B−A|` 仅在三条腿该指标均有效时保留。
新 AC 没有 B，不计算新 G_A/G_S，也不写“新跨类变化超过同类”。

旧 ABC 的 AC/BC 去重后共有 35,051 个物理端点对；与本轮全部新登记 AC 对的完整端点对交集为 **0**。
单个团队仍可以精确复用既有缓存。这意味着以下是同池、同目标、同 n/m、同类别方向的条件参照，
不是把同一对端点换个名字当成重复证据。

共有 2,037 个旧有向条件获得至少一种新直接 AC 参照。
三个参照集合分开：`A_registered_m7_m8`、`F_neutral_common_n`、`B_outside_equal_anchor`。
同一旧条件在多个集合中重复出现只是多种查看方式，不能增加旧 ABC 样本数。

十人严格条件的 B8L2 具体衔接如下。方向使用原严格 source→target，因而 TARGET 表中可能与主漏斗 canonical 方向相反。

| 图片 | 方法 | n | 原严格方向 | 新AC背景参照 | 严格ΔQ | 严格同类\|ΔQ\| | 严格GA | 新ACΔQ | 新AC\|ΔQ\| | 新AC有效事件 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q9vSo1VnCiC-34 | RAW3 K3 | 12 | 2/3->3/3 | F_neutral_common_n | 8.7626 | 5.9169 | 2.8492 | 7.4881 | 7.4881 | 8 |
| q9vSo1VnCiC-34 | RAW3 K3 | 12 | 2/3->3/3 | B_outside_equal_anchor | 8.7626 | 5.9169 | 2.8492 | 11.6284 | 11.6284 | 4 |
| q9vSo1VnCiC-34 | RAW3 K3 | 15 | 2/3->3/3 | F_neutral_common_n | 7.3925 | 4.0154 | 3.3771 | 7.1724 | 7.2805 | 8 |
| q9vSo1VnCiC-34 | RAW3 K3 | 15 | 2/3->3/3 | B_outside_equal_anchor | 7.3925 | 4.0154 | 3.3771 | 8.4273 | 8.4273 | 4 |
| yqstnuAEVhm-04 | TARGET K3 | 12 | 2/3->1/3 | F_neutral_common_n | 1.8607 | 2.9071 | -0.6412 | 0.6484 | 1.4872 | 8 |
| yqstnuAEVhm-04 | TARGET K3 | 12 | 2/3->1/3 | B_outside_equal_anchor | 1.8607 | 2.9071 | -0.6412 | 0.3999 | 1.3356 | 8 |
| yqstnuAEVhm-04 | TARGET K3 | 14 | 2/3->1/3 | F_neutral_common_n | 2.3320 | 3.3695 | -0.6398 | 0.6144 | 1.1707 | 8 |
| yqstnuAEVhm-04 | TARGET K3 | 14 | 2/3->1/3 | B_outside_equal_anchor | 2.3320 | 3.3695 | -0.6398 | 1.1544 | 1.4972 | 4 |

完整分项及有效数在 `STRICT_M10_COMMON_CONDITION_BRIEF.csv` 和
`STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz`。
不能将新 AC 与旧 ABC 的均值差直接归因于“取消 B”：具体 X/Z 抽样和 D 构成也不同，需进一步看下一节。

## 5. 固定精确 X/Z 后，背景到底改变了什么

只依据冻结身份，在最新严格 66 个条件内，将 F-neutral 与已有 B-outside 等人数锚点匹配。
要求 pool、method、n、m、canonical X 和 Z 全部相同，D 不同。
得到 **120 个方法对照、108 个物理四端点对照，
覆盖 21/66 条件**。其余 45 条件没有相同 n/m 的已登记 B-outside，
没有用仅人数相同但 X/Z 不同的事件冒充背景控制。
本严格子集的 120 对全部同时改变 D 的类别人数向量，固定 D 类别配比的对照为 0。
所以这里控制了替换块身份与 n/m，但改变的是背景成员及类别构成；纯粹同配比换背景成员的证据应读更广背景研究的相应子集。
质量的四端点共同可评为 109/120 个方法对照；跨方法去重后为 **99/108 个物理四端点对照，16 图、9 楼**。
其中 18 个物理对照在两种背景下的 B8L2 替换效果正负相反，涉及 8 张图。
这些仍共享成员和团队，不能作为 99 个独立受试对象；完整有效分母与物理分布见
`STRICT66_BACKGROUND_PHYSICAL_SUPPORT_SUMMARY.csv`。几何与劳动继续使用各自分母。

严格 ABC 需要额外保留同类 Y，故其 D 可用空间随 X/Y/Z 选择受到约束。
只有来源类恰 2m 人且目标类恰 m 人时，严格 D 的整个可用空间才恰好等于两类以外人员。
这只发生于 **8/66 条件**。
一般 m9 条件仍可有剩余来源/目标类成员进入 D，不能一律解释为第三类背景。
TARGET 与 RAW 的当前严格 m10 条件则满足该等价条件。

下表只比较同精确 X/Z 下更换 D 的 B8L2 结果，方向使用统一 canonical。
F−B 是两个跨类效果之差，正值表示相同替换块在 F 背景下具有更正的 Q 变化；它不等于 F 队本身更好。
原始四队 Q 与 A、C 各自背景变化在逐对表中保留。
这里的 F 均值只取双方确实共享的 X/Z 块（十人案例为 4 块），上一节 F 条件参照使用其全部 8 个登记块。
二者的样本分母不同，F 均值可不同；背景效应只能使用本节精确匹配的差分。

| 图片 | 方法 | n | F中性ΔQ | B外类ΔQ | F−B | 平均\|F−B\| | 有效对照 | XZ块 | 严格D空间=外类 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q9vSo1VnCiC-34 | RAW3 K3 | 12 | 10.7527 | 11.6284 | -0.8756 | 3.1181 | 4 | 4 | True |
| q9vSo1VnCiC-34 | RAW3 K3 | 15 | 9.4620 | 8.4273 | 1.0347 | 2.4926 | 4 | 4 | True |
| yqstnuAEVhm-04 | TARGET K3 | 12 | -0.8588 | -0.3999 | -0.4589 | 0.5085 | 8 | 4 | True |
| yqstnuAEVhm-04 | TARGET K3 | 14 | -1.0941 | -1.1544 | 0.0603 | 1.0041 | 4 | 4 | True |

`STRICT66_EXACT_F_NEUTRAL_VS_B_OUTSIDE_BACKGROUND_PAIRS.csv.gz` 保存精确成员、事件与四个团队 key，
`STRICT66_EXACT_BACKGROUND_EFFECTS.csv.gz` 保存全部指标和四端输出状态，
`STRICT66_EXACT_BACKGROUND_CONDITION_EFFECTS.csv` 先等权 B 背景、再等权 XZ 块形成条件汇总。
登记覆盖见 `STRICT66_F_VS_B_BACKGROUND_CONDITION_COVERAGE.csv`；旧严格 D 的实际类构成分布见
`STRICT66_ACTUAL_STRICT_D_CLASS_COMPOSITIONS.csv`。

与更广的主 A/B_equal 背景研究存在 4 个方法对照重叠，已提供统一 background_comparison_id 和
physical_background_comparison_id 去重。物理四端点不因方法不同就变成新证据。

### 一个接近条件均值、不是最大值的背景机制例

`wc2JMjhGNzB-53` 的 n=11/m=9 在上述完整子研究中出现较大背景敏感。
该条件四端点共同 Q 可评的 6 个物理候选，按与条件平均 F−B=31.6462 的距离排序，
选择 +33.4583 的候选（距离 1.8121），未选择最大 +76.2362。
TARGET 与 RAW 在这里命中相同四端点，只计一份物理证据；以主解释 TARGET 标签显示。

固定 canonical C1→C2 的 9 人 X/Z，F 背景为 W017(C2)+W126(C3)，B-outside 背景为 W027+W122（均 C3）。
F 的原队 A 为 B8L2=36.5304、4 节点，换入 Z 后 C 为 67.2328、5 节点；
B-outside 原队 A 为 35.8650、4 节点，换入同一 Z 后 C 为 33.1090、4 节点。
两原队 A 较接近，C 的结构与几何响应却明显分化；全部四队均有可评分的条件完整输出。
9 人块已经超过该 n 的 MV50 名义门槛 6，但人数不能保证某一节点身份、定位和连接形成。
是否由身份分组、节点未入选、定位或源环导致，需要接续该例完整 full_state 票账，不能从总 Q 或入选节点数直接推定。

完整选择规则、全部 6 候选、原始登记方向、4 个团队 key、节点/几何复核分别在
`BACKGROUND_WC2_53_REPRESENTATIVE_SELECTION.json`、`BACKGROUND_WC2_53_ALL_VALID_PHYSICAL_CANDIDATES.csv`、
`BACKGROUND_WC2_53_SELECTED_FOUR_ENDPOINTS.csv` 和 `BACKGROUND_WC2_53_SELECTED_FOUR_GEOMETRIES.json`。
这是对已完成事件的解释性案例选择，没有增加团队或改变冻结设计。

记录劳动先要求每个 AC 的来源计数相同且数值已知；本节 F−B 劳动差又要求四队来源计数签名全部一致。
原各对合法劳动差与进一步控制后的差分均保留。
本严格背景子集中，F 与 B 各自 AC 的合法来源计数劳动比较均为 0，因此劳动差分没有有效观测，全部留空。
这不是“劳动变化为零”，也没有在本子集用无效记录验证秒数不变性。
固定 X/Z 时绝对秒数差理论上不随 D 改变；百分比却可以因原队劳动分母改变而变化。
这里描述的是记录标注劳动，不能改写为新实验的实际用时或速度因果效应。

## 6. 复现、有效分母与文件索引

完整代码均在 `code/`。执行次序：

1. `prepare_strict_bridge.py`：只归一化已完成旧事件，支持 `inputs/` 中 compact 最小输入。
2. `inspect_exact_pair_overlaps.py`：核对完整物理端点对交集。
3. `compare_strict_common_backgrounds.py`：先写 score-blind 身份索引；加 `--reuse-index --metrics` 连接完成指标。
4. `analyze_execution_funnel.py` 与 `analyze_status_transitions.py`：读取完整 metrics 分片，缺分片默认拒绝写正式结论。
5. `write_funnel_bridge_report.py`：由 complete=true 的正式结果生成本文及四张简表。

当前源数据来自各 pool 原生 CHECKS.json 与 `stage04_metrics/metric_shards/`，不重新融合、评分或选标签。
source SHA-256 在各 RECEIPT 和输入 provenance 中；成员及对象身份来源于最终统一登记。
向量化漏斗已与原循环实现的 35,652 个非空共同汇总单元核对，分母完全一致、浮点误差<5e-13。
两份 partial_preview 目录只保留中途代码诊断，不属于最终数值依据；正式结论只读本目录根部 complete=true 的文件。
所有正式 CSV/gzip 会另外逐行读取到 EOF，检查列宽、CRC 与哈希，不用“文件存在”代替可读验证。
