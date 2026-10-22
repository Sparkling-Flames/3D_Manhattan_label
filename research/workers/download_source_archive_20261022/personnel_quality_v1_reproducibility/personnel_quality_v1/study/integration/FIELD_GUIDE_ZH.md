# 人员评价数据 v1：字段说明与使用指南

适用文件：`personnel_profiles_v1.csv`、`personnel_profiles_full.csv`、`classification_candidates.csv`、`event_evidence_union.csv`。本文依据这些文件的实际表头及 `integrate_profiles.py` 编写；不更改数据、分类、资格或计算结果。

**当前前台表实际为 27 行、47 列。** 早先所称“46 个字段”与本次文件表头相差一列；下文按实际列序完整说明全部 47 个字段。完整版人员表为 27 行、226 列，分类候选表为 27 行、7 列，事件表为 3,222 行、21 列。全部属于数据 **v1**。

## 一、先确定你正在读哪一组样本

人员表每行是一名规范人员，`worker_id` 是连接键，行序不是排名。表从全部 27 名库存人员开始连接，保留 W019、W026 的历史排除和 W022 缺少主训练的情况。不同列来自不同任务和审核面板，不能因为位于同一行就共享一个分母。

| 面板 | 全部相关记录的覆盖 | 与人员表的关系 |
|---|---|---|
| 全规范库存 | 3,222 份作答、27 人 | `n_submissions` 是该人员的库存记录数，包含 Manual、Semi、OOS 条件及保留的排除状态 |
| 当前普通 Manual 绝对质量 | 1,258 份、25 人 | 前台 `absolute_manual_B8L2_*`；包含主训练 1,048 份和原留出 210 份 |
| 主 Manual 相对 Q | 1,048 份、24 人、87 个精确任务、19 楼 | 前台 Q 效应、区间和楼外同号比例；排原留出。W019、W026、W022 没有主 Q |
| 来源任务效率 T | 727 份训练记录；23 人有数值、21 人达到支持门槛 | 前台 T 来自来源任务活动时间，单位是 `log(1+活动秒)` 的人员效应，不是秒数 |
| 全部 Semi 库存 | 574 份、26 人 | 初始化恢复、实际错误机会和原始行为的库存范围；W022 没有 Semi |
| 普通 Semi 兼容计量配对 | 437 份、24 人 | 前台 I、F、净改善及分数缺口的共同分母；限当前普通质量资格，排研究者补删点信用；含原留出 |
| 普通 Semi 专门效应 | 409 份、24 人、27 个任务、11 楼 | 前台 `Semi_semi_B8L2_effect` 的主训练；原留出 28 份另置，特殊条件 24 份只作敏感性 |
| 专家确认实际初始错误 | 156 次机会、26 人、6 个任务、5 楼 | 25 次未动残留，131 次改后具体错误结局未知；主 24 人是 144 次、20 次残留、124 次未知 |
| 当前兼容 clear scope | 全 26 人共 364 次 | Manual 38/286 次误拒，Semi 10/78 次；主 24 人分别为 32/264、7/72，共 39 次误拒 |
| 人工不接纳证据 | 当前 invalid 85 份 | 严格具体个人事件 25，较宽个人归因 68，严格包含于较宽；17 份不归入较宽个人事件 |
| 个人事件可判样本 | 明确接纳 999 份；严格可判 1,024，较宽可判 1,067 | 审核是定向或选择性的，表内可判比例不能直接外推全部提交 |

“主 24 人”指有当前主 Manual Q 的人员集合，不是所有指标都只保留 24 人。W019、W026 仍各有 6 次实际初始错误机会和可追溯的 scope 回答，不能因为无 Q 就从可靠性机会台账删除。W022 有 2 份原留出绝对质量记录，但没有 Q 训练、Semi 或本轮当前兼容 scope 机会。

## 二、零、空白、False 与“未知”怎样读

1. **计数 0 表示这个被枚举集合里有零条，不代表分数为零。** 例如 `absolute_manual_B8L2_n=0` 时均分留空；`Semi_n_initialization_error_opportunities=0` 时纠错比例应为未知，不能算作 0% 错误。
2. **数值空白表示没有该指标的记录、资格或可用估计。** 不得统一填成 0。Q 空白不能解释为“恰好平均”，净改善空白不能解释为“没有改善”。详细原因在完整版人员表和对象台账中。
3. **有 T 数值也不一定有可采用的快慢类别。** W018 的 `T_effect` 约 −0.693、W034 约 +0.237，但分别只有 4、5 个任务，`T_supported=False`，都必须保留 T 未知。W014 则 T 数值、支持状态和任务数均空白。只有支持状态明确为 `True` 才能用于当前快慢分类。
4. **0/6 已知未动残留不是 6/6 已修好。** 本轮若初始实际错误被改动，具体错误是否清除仍未知。分子为零可以同时对应 6 个未知结局。
5. **证据布尔值 False 不等于审查确认没有问题。** 事件表中某类证据为 False，可能是没有这种记录、没有相关 gold 或不适用；应同时看条件、机会标志和结局状态。
6. **分类候选表的异号标志有一个特别的缺失约定。** 它由两个效应的乘积是否小于零生成；效应缺失时现有输出也为 `False`。因此只有先确认两个效应均存在且有支持，才可把 False 理解为“未异号”；W019、W026、W022 的 False 不证明两个模型一致。

CSV 以 UTF-8 带 BOM 保存。数值空白经常被软件读取为 `NaN`；带缺失的计数列可能显示为 `48.0`，仍表示 48 个任务。布尔列可能被读为布尔值或文本，应明确解析 `True`、`False` 和空白，不能把文本 `"False"` 按“非空字符串”转换为真。

## 三、来源表索引

下文“来源”使用以下缩写，并标出原字段。路径相对本文件所在的 `study/integration`。

| 缩写 | 对应来源与连接规则 |
|---|---|
| **REL** | `../reliability/worker_reliability_summary.csv`，按 `worker_id` 连接；对象依据为 `../reliability/reliability_object_ledger.csv` |
| **ABS** | `../q/absolute_quality_by_worker.csv`，筛 `pool=ordinary_manual_all`、`axis=B8L2`，再按 `worker_id` 连接 |
| **QB** | `../q/worker_profiles_enriched.csv` 的 `axis=B8L2` 行，按 `worker_id` 连接；这是全主训练的描述画像 |
| **QD** | 同上文件的 `axis=D10` 行；D10 为固定敏感性口径 |
| **SEM** | `../reliability/worker_semi_summary.csv`，按 `worker_id` 连接；计量依据为 `semi_scores_b8l2_d10.csv`，实际错误机会依据为 `correction_object_ledger.csv` 和 `worker_correction_summary.csv`，均在 `../reliability/` |
| **SCO** | `../reliability/worker_scope_summary.csv`，按 `worker_id` 连接；对象依据为同目录 `scope_object_ledger.csv` |
| **EVT** | 本目录 `event_evidence_union.csv`，先在每个唯一 `object_id` 上合并证据，再按 `worker_id` 汇总 |
| **JOIN** | 本目录 `integrate_profiles.py` 直接生成的常量、显示文本或派生字段；其来源字段在各行另述 |

整合脚本保存输入哈希于 `INTEGRATION_RECEIPT.json`。人员前台是便于阅读的投影，不是所有分母、支持状态和来源证据的全集。

## 四、前台表全部 47 个字段

### A. 身份与库存（第 1—3 列）

| 序号 / 字段 | 中文含义 | 分母、范围与缺失解释 | 对应来源 |
|---|---|---|---|
| 1 `worker_id` | 规范人员编号 | 人员级主键，27 行中唯一；不是原项目账号。跨任务原账号的身份绑定保留在对象来源记录；本列无缺失 | REL `worker_id` |
| 2 `data_release` | 研究数据版本 | 全部为字符串 `v1`。历史源目录或评分归档名称中的其他版本号不改变此研究数据版本 | JOIN 常量 |
| 3 `n_submissions` | 该人员的规范库存作答数 | 统计该人员全部库存对象，包含不同条件及历史/当前排除；全表合计 3,222。不是合格数、已审数或独立新投票数；计数无缺失 | REL 同名列；底层按 `object_id` 计数 |

### B. 普通 Manual 的绝对质量（第 4—6 列）

| 序号 / 字段 | 中文含义 | 分母、范围与缺失解释 | 对应来源 |
|---|---|---|---|
| 4 `absolute_manual_B8L2_n` | 当前可计分普通 Manual 记录数 | 是随后均分和 P10 的分母；包含原留出，合计 1,258。该人员没有此类可计分记录时明确置 0，不给其均分补 0 | ABS `n`；JOIN 对缺少此组的人员将计数置 0 |
| 5 `absolute_manual_B8L2_mean` | 上述普通 Manual 的 B8L2 均分 | 按第 4 列所列该人员记录等权平均；反映其实际任务组成，不能作为消除了任务差异的能力排名。分母为 0 时空白。不是正确概率、无本轮校准合格线 | ABS `mean` |
| 6 `absolute_manual_B8L2_p10` | 上述记录的 B8L2 第 10 百分位数 | 与均分同一记录池；刻画观察到的低尾，不是“严重错误率”或已判坏记录数。小样本分位数不稳定；分母为 0 时空白 | ABS `p10` |

**这三列使用 1,258 份全当前普通 Manual；下述 Q 列使用排原留出的 1,048 份主训练。** 不应直接用前台绝对均分减 Q 来推算任务基线。需要同样本精确分解时，应使用完整版中的 Q 训练任务基线，或 `../q/worker_profiles_enriched.csv` 内同训练样本的均分。

### C. 任务调整 Q、T 与粗类（第 7—17 列）

Q 模型为 (y_{cw}=\alpha_c+\beta_w+\epsilon_{cw}\)，约束池内人员效应之和为零。精确任务按图、条件、参考 ID、参考版本定义；有至少两人可比才提供人员相对信息。人员支持沿用至少 6 个任务、3 楼的门槛。本轮主 24 人均达到 Q 支持。

| 序号 / 字段 | 中文含义 | 分母、范围与缺失解释 | 对应来源 |
|---|---|---|---|
| 7 `Q_B8L2_contexts` | B8L2 Q 主训练可比任务数 | 该人员在 1,048 份主训练内的精确任务覆盖，不是全库存任务数；前台缺主 Q 人员为空白，不表示恰有零任务的可用效应 | QB `contexts` |
| 8 `Q_B8L2_buildings` | 上述 Q 训练建筑数 | 覆盖独立建筑的计数，与第 7 列一起看；同楼多任务不等于多楼。缺主 Q 时空白 | QB `buildings` |
| 9 `Q_B8L2_effect` | B8L2 的任务调整人员效应 β | 单位为 B8L2 分。正值表示在该池、该模型下相对较高，负值相对较低；零是池内中心，不是合格线。无主 Q 的三人空白，不能补 0 | QB `effect` |
| 10 `Q_B8L2_effect_ci95_low` | Q 效应 95% 区间下界 | 与第 11 列成对；整楼重抽样 2,000 次后重拟合的百分位区间，针对观察池和现行清洗分数，未作多重比较调整。无效应时空白；不是未来单份分数下界 | QB `effect_ci95_low` |
| 11 `Q_B8L2_effect_ci95_high` | Q 效应 95% 区间上界 | 同第 10 列。跨零表示相对方向有不确定性，不自动取消描述画像，也不证明人员能力相同 | QB `effect_ci95_high` |
| 12 `Q_D10_effect` | D10 敏感性口径的任务调整效应 | 在相同主训练和调整结构下换固定评分口径得到；只作敏感性，不与 B8L2 相加。无主 Q 时空白；其他 D10 区间和覆盖在完整版 | QD `effect` |
| 13 `T_effect` | 来源活动时间的任务调整人员效应 | 对 `log(1+活动秒)` 拟合，负值较快、正值较慢；不是秒、等待时间、lead time 或团队成本。必须与第 14 列联读：未支持者可能仍有探索数值；来源缺失时空白 | QB `T_effect`，其上游为来源 T 画像 |
| 14 `T_supported` | T 是否达到既定支持门槛 | `True` 才可用于快慢类；`False` 表示有拟合但任务/楼支持不足；空白表示前台没有可连接的 T 画像。三种状态不能合并为“慢”或数值 0 | QB `T_supported` |
| 15 `T_contexts` | 来源 T 可比任务数 | T 自身的任务池，与 Q 任务数不同。W018=4、W034=5，故未支持；W014 无 T 行，空白。不要用第 7 列代替 T 支持 | QB `T_contexts` |
| 16 `existing_QT_class_zh` | 现有 Q/T 粗类的中文显示 | Q 正/负与有支持的 T 负/正交叉为相对高/快、高/慢、低/快、低/慢；支持不足保留“相对高/低／T未知”；无 Q 显示“Q未知／T未知”。仅描述候选，不是永久人群或绩效等级 | QB `QT_label` 经 JOIN 中文映射 |
| 17 `Q_B8L2_LOBO_same_sign_fraction` | 留建筑后 Q 与全主训练效应同号的比例 | 本轮主 Q 为 19 个留建筑折；分子是与全主训练方向一致的折数，分母为这 19 折。不是 19 个独立重复试验，也不是“能力为正的概率”；无主 Q 时空白 | QB `LOBO_same_sign_fraction` |

以上 Q/T 效应为**全主训练的描述画像**。用于目标建筑的预测、选人或组成评估，应改用 `../q/fold_profiles_recomputed.csv` 中排除该目标建筑的折，不能把本表完整画像直接用于同建筑验证。

### D. Semi：计量配对与真实错误机会（第 18—28 列）

本组存在两套独立分母：**第 20 列的普通计量配对样本**与**第 25 列的实际错误机会**。后者不以最终质量可用、是否被人工拒绝或是否能计分为筛选前置。字段名中的 `attributable` 仅指排除了已识别研究者补删点信用的兼容计量视图，不能解释为已证明所有变化由个人行为因果产生，也不能据此宣称复原了当时屏幕几何。

| 序号 / 字段 | 中文含义 | 分母、范围与缺失解释 | 对应来源 |
|---|---|---|---|
| 18 `Semi_n_semi` | 该人员全部 Semi 库存数 | 包含历史排除、未知参考、不可计分与 scope 拒绝等保留状态；全表合计 574，26 人有记录。W022=0，表示没有 Semi 机会 | SEM `n_semi` |
| 19 `Semi_n_initialization_payload_verified` | 找到并绑定实际部署初始化坐标来源的 Semi 数 | 分母是第 18 列；全表 574/574。身份核实不等于已确认初始化有错、完整环序或用户确实观看过。无 Semi 时为 0 | SEM `n_initialization_payload_verified` |
| 20 `Semi_n_ordinary_attributable` | 普通 Semi 的兼容计量配对数 | 当前普通质量可用、初始/最终同参考可配对，排研究者补删点信用；合计 437。是第 21—24 列共同分母，含原留出；不是 409 份效应训练，也不是 156 次错误机会。无此样本时为 0 | SEM `n_ordinary_attributable` |
| 21 `Semi_ordinary_initial_B8L2_mean` | 计量配对样本的初始 B8L2 均值 I | 仅对第 20 列同一记录池，以最终固定参考和兼容环序计量。无配对样本时空白；不能把它当初始化无错的认证 | SEM `ordinary_initial_B8L2_mean` |
| 22 `Semi_ordinary_final_B8L2_mean` | 同一配对样本的最终 B8L2 均值 F | 与第 21、23、24 列同分母；不是包括研究者修复在内全部 441 份普通最终产物的均值。无样本时空白 | SEM `ordinary_final_B8L2_mean` |
| 23 `Semi_ordinary_worker_attributable_gain_B8L2_mean` | 同配对样本的平均净改善 F−I | 单位为 B8L2 分；负值表示当前兼容计量视图下平均变差。数值 0 可是真实相同分数或平均抵消，不表示具体错误已修好；无样本时空白，不能补 0 | SEM `ordinary_worker_attributable_gain_B8L2_mean` |
| 24 `Semi_ordinary_residual_score_deficit_B8L2_mean` | 同配对样本的平均剩余分数缺口 100−F | 只是固定质量指数距 100 的差，与 F 完全冗余；不是错误数、残留概率或严重性。无样本时空白 | SEM `ordinary_residual_score_deficit_B8L2_mean` |
| 25 `Semi_n_initialization_error_opportunities` | 专家明确确认实际初始错误的部署机会数 | 必须绑定实际部署坐标和专家看到的具体缺陷，不由计划扰动、`trap_status` 或低初始分推定。26 人各 6 次，共 156；主 24 人共 144。W022=0；不能筛成当前质量可用的 138 次 | SEM `n_initialization_error_opportunities`；上游 `correction_object_ledger.csv` 的确认机会标志 |
| 26 `Semi_n_known_error_unchanged` | 已知初始错误且原始坐标未改的残留事件数 | 分母只能取第 25 列；全 26 人 25 次，主 24 人 20 次。不是全 147 次未改作答，也不是定向审核中 36 个 trap 未改标签。0 仅表示没有观察到这种确定残留，不能解释为全部修好 | SEM `n_known_error_unchanged` |
| 27 `Semi_n_edited_error_specific_outcome_unknown` | 确认有初始错误、已改但具体错误结局未知的机会数 | 本轮全表 131，主 24 人 124；第 26+27 列等于第 25 列。不是修好数，也不是确认失败数；0 可能无机会或没有此类未知，应与第 25 列联读 | SEM `n_edited_error_specific_outcome_unknown` |
| 28 `Semi_semi_B8L2_effect` | 普通 Semi 专门的任务调整人员效应 | 主训练 409 份，排原留出、研究者补删点信用及特殊条件；同图/条件/参考/实际初始化上下文调整。24 人有支持，三人空白；不与 Manual Q 自动合并。相同初始化任务中最终分与净改善效应等价，不能计两票 | SEM `semi_B8L2_effect`；支持/任务/楼在完整版同前缀列 |

413 份库存初始化没有可按完全相同点集独立确认的既有环序来源；156 次专家错误机会都在这一状态中。绝对初始分和净改善保持计量诊断层级。25 次“原始坐标未改而保留专家确认缺陷”的事件依据，与是否充分恢复屏幕环序分开。

### E. Scope 回答、当前真值与机会（第 29—35 列）

当前可采用的小面板是历史已明确判 `in_scope`、排后续 hold、且与当前 clear 非 OOS 场景兼容的任务。它并没有建立覆盖所有场景的当前协议 `out_of_scope` gold；因此本组可以描述误拒，不能从表中缺少误接纳列推断误接纳为零。

| 序号 / 字段 | 中文含义 | 分母、范围与缺失解释 | 对应来源 |
|---|---|---|---|
| 29 `scope_n_scope_choice_recorded` | 原始作答中记录了 scope 选项的次数 | 分母是第 3 列全库存；合计 3,217。只证明有原始选择，不证明能规范化、任务真值已知或回答正确；无缺失计数 | SCO `n_scope_choice_recorded` |
| 30 `scope_n_scope_response_unknown` | 不能规范化成 in_scope/oos 的回答数 | 包括未回答或不能明确解析；本快照合计 5。与“任务真值未知”不同：可以有明确回答但没 gold。0 表示已读回答里没有此类未知，不等于回答全对 | SCO `n_scope_response_unknown` |
| 31 `scope_n_current_task_unknown` | 未获得本轮当前兼容 clear in-scope 判断的库存记录数 | 全库存中不属于当前兼容 clear 机会的数量，合计 2,858。包含可能已有历史 OOS/旧协议 gold 的任务，不能简单译为“原始 gold 缺失”；更不能视为人员不知道答案 | SCO `n_current_task_unknown` |
| 32 `scope_current_clear_manual_opportunities` | 当前兼容 clear Manual 的误拒判断机会数 | 全 26 人 286 次，主 24 人 264 次；每个有该机会的人员 11 图/7 楼。保留历史排除人员作答，不按最终几何质量筛。W022=0，分母为 0 时比例未知 | SCO `current_clear_manual_opportunities` |
| 33 `scope_current_clear_manual_false_rejection` | 上述可标 Manual 任务却回答 oos 的次数 | 分母是第 32 列；全 26 人 38、主 24 人 32。0 需结合机会数；未知场景不作错误也不作正确 | SCO `current_clear_manual_false_rejection` |
| 34 `scope_current_clear_semi_opportunities` | 当前兼容 clear Semi 的误拒判断机会数 | 全 26 人 78 次，主 24 人 72 次；每个有该机会的人员 3 个任务。与第 25 列六个实际错误任务不是同一面板。无机会时为 0 | SCO `current_clear_semi_opportunities` |
| 35 `scope_current_clear_semi_false_rejection` | 上述可标 Semi 任务却回答 oos 的次数 | 分母是第 34 列；全 26 人 10、主 24 人 7。0 不表示对所有 OOS、可见性、边界或多空间判断均正确 | SCO `current_clear_semi_false_rejection` |

例如 W030 为 Manual 9/11，来源明确为 7 次 open boundary、2 次 insufficient；这只支持这组当前兼容任务中的反复误拒标记。不能把原始 `condition=oos` 的设计任务、人员回答 oos 和现行任务真值混作同一个分母。

### F. 人工审核、个人剔除与历史状态（第 36—44 列）

这里的事件单位均为唯一作答对象，不是原批注条数。**严格具体个人事件是较宽个人不接纳事件的子集**；两个分子和两个可判分母不能相加。审核标记、可用二元判定和全部提交也不是同一层覆盖。

| 序号 / 字段 | 中文含义 | 分母、范围与缺失解释 | 对应来源 |
|---|---|---|---|
| 36 `n_individual_review_flags` | 原始记录带个人逐审标记的数量 | 分母是第 3 列；全表 1,540。标记为真不保证已有可用于个人错误二分类的裁决；0 表示没有这类逐审标记，不表示零错误 | REL 同名列；对象 `individually_reviewed_flag` |
| 37 `n_explicit_accepted` | 有明确接纳裁决的负例候选数 | 来自 `usable` 或 `retained_scope_variation`；全表 999，均核有逐审。表示当次审核可接纳，不是所有错误均不存在的 gold；用于第 40/42 列可判集合 | REL 同名列；对象 `explicitly_accepted_negative_candidate` |
| 38 `n_invalid` | 当前裁决为 invalid 的对象数 | 全表 85；包含具体个人、较宽个人、非个人及原因不明，不能全部算严重失误。与第 44 列历史整人排除不同；0 是未观察到当前 invalid 裁决 | REL 同名列；对象 `any_current_invalid` |
| 39 `n_strict_personal_severe` | 有具体机制文本证据的个人严重/明确错误剔除数 | 全表 25；分层依据是已有审核文本，如漏点、错认特征、明确严重偏斜，不是本轮新增逐图人工 gold。若描述已审比例，用第 40 列；不能用 0 声称无风险 | REL 同名列；对象 `strict_specific_personal_severe` |
| 40 `n_strict_personally_judgable` | 严格口径个人事件可判数 | 第 37 列＋第 39 列，全表 1,024。未具体说明机制的较宽事件在此保持不可判，不能作无严重错误的负例。分母为 0 时比例未知 | REL 同名列；对象 `personal_binary_strict_eligible` |
| 41 `n_reviewer_personal_nonacceptance` | 较宽的审核个人不接纳事件数 | 全表 68，包含第 39 列的 25；另外有机制未具体说明、政策歧义等更宽证据。不能全部改称“具体严重错误”，也不应与严格 25 相加；比例使用第 42 列 | REL 同名列；对象同义布尔列 |
| 42 `n_broad_personally_judgable` | 较宽口径个人事件可判数 | 第 37 列＋第 41 列，全表 1,067。不是全部已审 1,540，也不是普通 Manual 风险模型的 543；后者还有专门场景筛选。分母为 0 时比例未知 | REL 同名列；对象 `personal_binary_broad_eligible` |
| 43 `n_invalid_reason_unknown_or_nonpersonal` | 当前 invalid 但不足以归入较宽个人事件的数目 | 本快照为第 38−41 列，共 17；包含原因不明、场景/协议、GT 或范围讨论。不能作个人严重错误，也不能作正确负例；0 只表示当前 invalid 中没有此剩余类别 | REL 同名列；对象 `current_invalid_personal_reason_unknown_or_nonpersonal` |
| 44 `n_historical_worker_exclusion` | 被历史整人排除状态覆盖的作答记录数 | 统计记录，不是被排除人员数；W019=56、W026=24，共 80。保留原资格，不逐条推断为严重个人错误；它不是所有历史未接纳 133 条的总数 | REL 同名列；对象 `historical_worker_exclusion` |

可以用第 36/3、40/3、42/3 列分别说明“带审阅标记覆盖”“严格可判覆盖”“较宽可判覆盖”，但它们不是三种错误率。即使算第 39/40 或 41/42 的比例，也只能称所选已判样本中的比例，不能外推全部提交或未来任务。

### G. 去重事件计数与文字标记（第 45—47 列）

| 序号 / 字段 | 中文含义 | 分母、范围与缺失解释 | 对应来源 |
|---|---|---|---|
| 45 `documented_problem_event_union_strict` | 严格个人事件、已知初始错误未动残留、当前 clear scope 误拒的对象并集数 | 对三类布尔标记先在每个对象上取或，再按人计数；全池 95、主 24 人 81。没有共同审核机会分母，不是新综合分或总体风险率。0 只表示未记录这些事件 | EVT `strict_union_event` 按人员求和；JOIN |
| 46 `documented_problem_event_union_broad` | 将上项中的严格个人事件换为较宽个人不接纳后的并集数 | 全池 138、主 24 人 124；包含严格并集，不能与第 45 列相加。窄历史 OOS 误接纳不入当前并集；0 的解释同上 | EVT `broad_union_event` 按人员求和；JOIN |
| 47 `evidence_flags_zh` | 根据现有字段生成的中文证据提示 | 可能包括 Q 边界、D10 异号、T 楼外变号、具体/较宽个人事件、已知错误未动、scope 误拒、历史排除。它不是新增裁决、等级或完整事件清单；同一人有严格事件时文字优先显示严格件数，较宽总数仍须看第 41 列。没有触发标记也不能补为“全部正确” | JOIN 的固定文字规则；来源为本表相关数值和 QB 稳定性字段 |

严格个人 25、未动残留 25、当前 scope 误拒 48 合计有 98 个标签，但只涉及 95 个对象。重复的 3 个对象均为 rPc6DW4iMge-09 上的 W029、W032、W037，同一对象同时有 scope 误拒和具体点对错误。并集避免重复计件，但不构成第二轮扣分。

## 五、完整版人员表怎样使用

`personnel_profiles_full.csv` 是同一 27 人的完整连接，当前 226 列，不是新增样本。按前缀和来源表读取，优先保留以下字段组。

| 字段组或代表字段 | 使用要点 |
|---|---|
| `absolute_manual_B8L2_*`、`absolute_manual_D10_*` | 包含 n、图、楼、均值、中位数、P10、最小值；均为当前普通 Manual 全可计分池，含原留出 |
| `Q_B8L2_*`、`Q_D10_*` | 包含支持、区间、±2 边界、楼外同号、互斥两半一致率、训练原均分排名和效应排名；全主训练描述，选人验证仍需逐折表 |
| `Q_*_actual_task_intercept_mean` | 人员在 Q 训练中实际任务的 α 均值；可解释任务组成。它与前台全 1,258 份绝对均分不同样本，不能直接相减 |
| `Q_*_common_task_standardized_prediction` | 公共任务池平均 α＋该人员 Q；只是 Q 的线性重表达，不是又一个实测绝对均分或独立质量维度 |
| `T_*` | 支持、任务数、楼数及楼外快慢折数；前台和此组是来源 T。目标匹配活动秒及团队成本需读融合相应时间表，不能用这组 effect 代替秒数 |
| `scope_n_scope_no_task_gold`、`scope_n_scope_later_hold`、`scope_n_current_task_unknown` | 分别是缺历史任务 gold、后续 hold 和缺本轮当前兼容判断；三者不是可随意相加的互斥原因 |
| `scope_historical_*`、`scope_narrow_historical_representation_oos_*` | 原协议和窄 OOS 诊断；不可整体升级为当前协议错误率。当前 clear in-scope 样本的 `false_acceptance=0` 是真值范围限定的结果，不证明当前一般误接纳为零 |
| `Semi_n_pair_scorable`、`Semi_n_final_unscorable`、`Semi_n_native_ring_unconfirmed`、`Semi_n_researcher_point_repairs` | 区分可计分、不可计分、环序来源与研究者处理；不得与实际错误机会互相替代 |
| `Semi_n_ordinary_training`、`Semi_n_ordinary_original_holdout`、`Semi_n_special_training` | 主训练、原留出、特殊条件敏感性分开；当前总数分别 409、28、24 |
| `Semi_ordinary_all_final_*` | 包含研究者处理后的项目普通最终产物，n 合计 441；前台配对 I/F/gain 的 n 是 437。可以展示项目最终质量，但研究者修复不能给人员计改善信用 |
| `Semi_semi_*_supported`、`Semi_semi_*_contexts/buildings` | 读取 Semi effect 时的资格和覆盖。即使将来有未支持者的数值，也不得跳过支持判断 |
| `Semi_n_edited_error_specific_correction_confirmed`、`Semi_n_edited_error_specific_residual_confirmed` | 本轮均未建立改后逐错误裁定；0 表示没有被确认为这类结局，不能把另一类补成全部成功或全部失败 |
| `known_error_residual_fraction_lower_bound/upper_bound` | 对第 25 列明确机会的部分识别范围：下界为已知残留/机会，上界把全部改后未知也可能残留计入。本轮全池 25/156 至 100%；不是统计置信区间，无机会时空白 |
| `strict_known_submission_fraction`、`broad_known_submission_fraction` | 已记录该类事件占库存的比例；审核未覆盖部分仍未知，不能当完整总体错误率 |
| `strict_error_fraction_in_judgable`、`broad_error_fraction_in_judgable` | 各自已判样本中的事件比例；严格和较宽分母不同，选择性审核限制仍在 |
| `n_*_adjudication_unknown`、`*_adjudication_coverage` | 以库存减可判数和可判数/库存保留覆盖，不能把“未知”通过补零变成“正确” |
| `n_historical_*` | 历史整人排除、空几何、个人排除、技术/配对、非独立、替代版本分开，不一律计为个人严重错误 |

`proposed_profile_zh` 只是“现有 Q/T 中文类＋证据标记”的拼接。用于阅读和审核关注点，不改变 Q、不恢复历史资格、不新增分数，也不要求所有标记形成互斥人群。

## 六、分类候选表怎样使用

`classification_candidates.csv` 是 27 人的 7 列摘要，适合并排检查原粗类、证据扩展及排名变化；不替代前台的分母和完整版的支持状态。

| 字段 | 说明与限制 |
|---|---|
| `worker_id` | 与所有人员表连接的规范主键 |
| `existing_QT_class_zh` | 原有全主训练 Q/T 粗类；缺 T 保持未知 |
| `proposed_profile_zh` | 原粗类加证据标记，不是新训练出的多类模型 |
| `Q_B8L2_D10_sign_disagree` | 两种 Q 效应乘积小于零时为 True；**缺任何一方时现有结果也为 False**，先看效应及支持，再解释异同 |
| `Manual_Q_Semi_Q_sign_disagree` | Manual 与 Semi 效应是否异号；同样存在缺失时 False 的约定。方向不同说明观察条件依赖，不自动认定某一轴失效 |
| `Q_B8L2_raw_mean_rank` | **1,048 份 Q 主训练内部**人员原均分的降序排名，1 为最高；不是前台 1,258 份全普通 Manual 均分的排名 |
| `Q_B8L2_Q_effect_rank` | 同一主训练人员的任务调整 Q 降序排名；无主 Q 者空白，不排在最后或并列平均 |

±2 边界仅为登记的诊断带；符号、区间、两半稳定和实际事件不应被重新调阈值来追求显著差异。人员组合和楼外验证应使用训练排除目标建筑的标签，而不是直接使用此表全样本的类别。

## 七、事件并集表怎样使用

`event_evidence_union.csv` 每行是一个唯一 `object_id`，共 3,222 行。它保留全部作答，不只保留问题记录；跨来源追溯原评论、scope 选项或部署初始化时，用 `object_id` 回连相应对象台账。

| 字段组 | 使用要点 |
|---|---|
| `object_id`、`worker_id`、`image_id/image_code`、`building_id`、`condition` | 事件主键、人员与任务身份。不要只按人员/图或批注文本去重，避免混合条件、版本或重复来源 |
| `cleaning_disposition`、`independent_vote_eligible` | 原资格原样保留。一个对象有可靠性证据，不因此恢复几何投票；False 也不自动表示个人严重错误 |
| `strict_specific_personal_severe`、`reviewer_personal_nonacceptance` | 严格包含于较宽。False 表示该对象没有被归为该证据，不代表全部质量正确 |
| `confirmed_initialization_error_opportunity` | 是否有本轮采用的专家实际缺陷及部署绑定。非 Semi、初始缺陷未判等对象都可为 False，不能读成“初始化确认无错” |
| `known_error_unchanged`、`error_specific_residual_state` | 已知初始缺陷且坐标未改才有残留事实。Semi 状态包括 `known_persistent_by_coordinate_identity`、`unknown_after_edit`、`initial_defect_not_adjudicated`；非 Semi 的语义状态可空白 |
| `current_compatible_outcome`、`scope_current_clear_false_rejection` | 当前兼容任务的 scope 结局与误拒标志。任务判断未知保持状态，不因 False 误拒标志而当作正确回答 |
| `narrow_historical_representation_outcome`、`scope_narrow_old_false_acceptance` | 原协议几何/分层 OOS 窄诊断，**不进入**当前严格/较宽问题事件并集 |
| `strict_union_event` | 严格个人剔除 OR 已知初始错误未动 OR 当前 clear scope 误拒，在同一对象上最多记一次 |
| `broad_union_event` | 较宽个人不接纳 OR 已知初始错误未动 OR 当前 clear scope 误拒；包含严格并集 |
| `is_current_Q_worker` | 表示**该人员属于主 24 人**，不表示该对象本身进入 Q 训练。主 Q 人员的 Semi、OOS 或被剔除对象也可为 True |
| `data_release` | 均为 v1 |

使用顺序是：先选人员/任务范围，再对对象级证据标志取并集，最后计数；不要先把各来源人员计数相加再尝试扣重。全池与主 24 人的并集分别是严格 95/81、较宽 138/124；不同范围下不能直接比较绝对件数大小。交叉对象名单另见 `event_overlap_counts.csv`。

事件并集没有一个共同、完整的“所有问题机会”分母。将并集数除以 `n_submissions` 至多得到库存里被记录为这些问题的占比，不能叫总体可靠性、综合风险率或处罚权重。若研究特定风险，应回到相应的明确机会或已判面板，并继续保留未审核与未知。

## 八、几个可直接采用的阅读例子

- **W018：** 绝对质量、较高 Q、低尾和较宽区间可以同时存在；T 虽有数值但只有 4 个任务且未支持，不能据负 T 值标成快。
- **W011：** 普通 Semi 最终均值和 Semi 效应可以较高，同时存在 6/6 专家确认初始错误未动。计量质量与具体错误处理回答不同问题，不互相抵消。
- **W030：** 当前 clear Manual 误拒 9/11 是有原选项和任务真值支持的范围内事实；不是全部任务的 scope 错误率，不自动加入严格严重剔除分子。
- **W019、W026：** 无主 Q 和普通可用计量不等于没有作答或错误机会；库存、历史排除、scope 和六个实际错误机会分别保留。
- **W022：** 有两份原留出绝对分数，无 Q 训练、无 Semi、无相应 scope 机会；其空白效应、零机会和异号 False 各有含义，不能统一转成“中等且无错”。

本表适合形成“连续指标＋覆盖/缺失＋范围限定事实”的人员画像。任何跨维比较都应先检查分母、资格、参考和重复对象；无需把这些维度相加成一个总分。
