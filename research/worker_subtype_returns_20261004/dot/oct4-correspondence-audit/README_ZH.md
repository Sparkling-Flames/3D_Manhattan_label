# 完整布局 Pro 原型：对应、证书与支持账本独立复核

## 结论

本复核确认一个实质实现问题，并给出比已有记录更强的影响证据：**原型可能在实际进入融合的身份映射违反全局 5° 直径约束时，仍返回条件式单结果。** 根因是认证用 minimax 对应、生成用 minsum 对应，两者未绑定。已有仓库 `ad12d64d3567235e5691f9142d045df63b38b4e4` 的复核已经发现两人版本；这里不将其冒称首次发现。本轮新增一个三人固定例，将“认证对象不同”加强为“实际全局直径越界”，并提供隔离修正与回归。

隔离修正版在发现映射脱节时保守暂缓，保留候选和诊断。**它没有接通联合优化、没有选择真实语义赢家、没有更改远程或下载原包。** 原包 25 项测试在隔离修正版通过，新增 6 项回归通过。审计记录刻意保留原型的三条失败检查，不能把这些失败藏在“全部通过”的措辞里。

## 1. 范围、版本与来源

- 审核前已完整阅读 464 行 `RESEARCH_REPORT_ZH.md`，然后检查 394 行 `src/consensus_lab.py`、两个本地入口及测试
- 被审核的是下载包 `full_layout_consensus_20261004`，声明冻结上游 `c4e8f908f3725900600dec5909586658092d6234`
- 核心源码 SHA-256：`e3d7d1efc3aa2b295174bc31fbe14ecad512135556dda076bb0131b597419cfc`
- 已知问题来源：上游较新 `ad12d64…/research/full_layout_pro_review_20261004/REVIEW.md` §5；两人固定输入为同提交 `recompute/certification_objective_mismatch.json`（Git blob `e308942c4caa05179ffd05d140026134001238c3`）
- 这里不审核或替代最新 `global_pair_consensus_20261004.py`；该代码由另一复核承担。不能把本包旧原型的问题直接归给最新全员基线
- 未重跑作者全部实验或原型原版 25 测试；别的复核承担该工作。本复核单独运行修正版 25 测试、6 个新增回归、15 个小型部分对应穷举对照和少量定向反例
- 未读取原图作视觉裁决，未改 GT、环序、独立资格或现有 Lee/点融合实验路线。不同独立人员的相同坐标继续是独立票

来源链接：
- 已有问题与当前仓库边界：[ad12d64 REVIEW](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ad12d64d3567235e5691f9142d045df63b38b4e4/research/full_layout_pro_review_20261004/REVIEW.md)
- 已有两人输入：[固定反例](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ad12d64d3567235e5691f9142d045df63b38b4e4/research/full_layout_pro_review_20261004/recompute/certification_objective_mismatch.json)

## 2. 实 bug：实际融合映射未被证书检查

### 2.1 静态调用链

原版行号：

1. `partial_alignment`（85–118 行）先最大匹配数，再最小化匹配端点最大角误差之和
2. `derive_candidates`（235–258 行）把此映射直接用于角点 donor 和坐标中位数
3. `cycle_audit`（298 行起）却用 `full_alignment` 的最小最大误差映射检查两两唯一与三人循环
4. `conditional_decision`（333–346 行）没有验证第 2、3 步是否采用同一映射
5. 最后的候选残差又调用 `full_alignment`，会重新寻找对应；它不能证明实际生成身份系统的全局直径成立

这不是说最小和或最小最大值必然应被弃用，而是一个条件式证书必须指向实际产生该候选的对象。

### 2.2 既有两人反例独立复验

`fixtures/known_certification_objective_mismatch.json` 原样保存已发表的上游例子。5° 下：

- 认证唯一 minimax：S0→S1 `[1,0,2]`，最大误差 3.831827°，次优间隔 0.476281°
- 实际唯一 minsum：`[0,1,2]`，误差和 8.607303°，最大误差 4.308108°
- 原状态为 `single_candidate_conditional_on_method_tolerance`
- 这已证明对象脱节，但两人的实际最大误差仍未超过 5°；不能将这个旧例说成阈值越界

### 2.3 本轮新增三人加强例

构造方法：保留既有 S0、S1，以两者坐标中点为基底增加 S2；对共享 x 与上下 y 使用独立固定种子小扰动。种子 `704031`，从 0 开始第 23 次满足筛选条件。脚本与完整固定坐标均保留；运行时只需固定输入，无需再次搜索。**这是存在性反例，筛选命中率没有统计意义。**

所有输入地面多边形都有效并包含相机。候选地面多边形有效、包含相机，原型的 band 检查也通过。

|记录对|证书 minimax 映射|证书最大误差|实际选中锚点所诱导映射|实际最大误差|
|---|---|---:|---|---:|
|S0–S1|`[1,0,2]`|3.831827°|`[0,1,2]`|4.308108°|
|S0–S2|`[0,1,2]`|2.926917°|`[0,1,2]`|2.926917°|
|S1–S2|`[1,0,2]`|4.056464°|`[0,1,2]`|**5.579438°**|

三份 minimax 对应都唯一，三角循环完全一致。原型选锚点 S0，其实际 donor 映射对三人全部为 `[0,1,2]`。这套实际身份系统中 S1–S2 越过 5°，原型仍返回 single 状态。

实际固定对应下，生成中位数对三位人员的残差分别为 2.069632°、4.307514°、2.340920°，仍全部低于 5°。因此本例同时说明：**候选到每位人员近，不能代替所有来源在同一身份下的两两直径检查。** 本结论完全数值化，不依赖原图，也不判定哪个物理角的语义正确。

证据：`fixtures/three_record_actual_mapping_diameter_counterexample.json`、`results/new_three_record_before_after.json`。

## 3. 最小隔离修正与回归

`patched/consensus_lab_guarded.py` 与 `patched/minimal_guard.diff` 做三件事：

1. single 认证前提取候选实际使用的完整 donor 映射，与已认证的 anchor 映射逐项比较
2. 直接计算这套实际身份下所有来源两两误差；不允许用另外一套更有利的对应替代
3. 候选到每位人员残差固定沿实际生成映射计算；映射不同或直径越界返回 `unresolved_actual_mapping_certificate_mismatch`

另修复已被上游记录的 `source_point_indices=None` / `source_point_labels=None` 直接切片 `TypeError`：空值保持未知，不伪造来源。它独立于对应问题。

两人和三人固定例修正后均暂缓 single，`single_candidate=null`，并返回实际映射差异与全对误差；原候选构造函数未被换成别的赢家。此修正是**保守的证书防护**，并非完整解决方案，可能保留原本仍在容差内的备选。若以后要输出联合解，应以明确的 joint 映射生成坐标与账本，并对同一映射验证几何、固定残差和覆盖状态，所有并列联合解仍应保留。

测试：
- 隔离修正版运行原包 25 项测试：25 通过，0 失败/错误
- 新增回归：6 通过，覆盖旧两人、新三人、普通一致控制、来源空值、原输入不变，以及原缺陷固定例仍能复现
- `audit_summary.json` 16 项审计检查中 13 项为真；3 项原版预期正确性检查为假，分别是两人错误放行、三人错误放行、来源空值崩溃。它们被明确保留，不能解读为修复后回归失败
- 最终再次核对下载原源码散列不变

## 4. partial_alignment：组合优化本身与语义门槛分开

### 4.1 未发现 top-two 动态规划错误

对 15 个独立小代价表（3×3、3×4、4×3、3×5、4×4），穷举所有保环方向/起点的 injective partial maps，对照最大匹配数、最小和、最佳映射、同 cardinality 的 runner-up，全数一致。代价表包含重复、阈值边界和不可用边。**这是组合算法验证，不能当作 15 个物理房间实验。**

每个 DP 状态保留两条不同映射而非 skip 操作轨迹，去重方式正确；本轮没有找到会把最优或次优丢掉的实现反例。

### 4.2 两种需要明确命名的限制

- 3×4 全零代价表有 24 个并列最优映射，接口只返回最佳与 runner-up 两个，并置 `ambiguous=true`。它能识别歧义，但没有枚举“全部部分对应解”，也没有导出真实并列数或截断标志。报告 §8.1 已披露 two-best；不要把 §7 联合求解的“全部并列解”误套到这里
- 一个定向代价表有“2 个零误差精确匹配”和“3 个各 4.9° 的匹配”，程序按既定目标选择 3 个、误差和 14.7°；由于只有一个最大 cardinality 映射，返回 `ambiguous=false, margin=null, runner_up_mapping=null`。这不是数值 bug，而是强制最大 cardinality 的方法假设；`margin=null` 不意味着语义身份确信，也没有比较低 cardinality 的高质量替代

当前没有最少匹配比例、局部身份可信度或 miss/false-positive 代价。唯一一对局部匹配也可以提供那个角点的一份 donor；这在局部账本含义下不等于一票整环支持。不要未经校准添加一个新硬门就宣称解决语义不足。可实施下一步是显式输出 cardinality–cost 前沿、每个 cardinality 的备选/缺点，并沿用户已允许的多候选方式对照。

## 5. joint_ring_alignment 与 conditional 尚未形成闭环

代码的联合枚举逻辑符合声明：固定首记录 gauge，其他各枚举 2m 个二面体索引；用诱导身份计算所有两两 bottleneck，全部≤τ后最小化误差和。m≥3 时状态数 `(2m)^(n−1)`，预算检查在枚举前进行，不是截断后伪称最优。

本复核不重复作者三人四角 64 状态、两个最优的整组实验；该实验由另一个复核重放。独立预算边界检查采用新两人四角控制：预算 7 返回 `budget_exceeded_no_exact_result` 且 required=8，预算 8 完整枚举 8 个状态。默认预算 100,000 对四角对时可以容纳 6 人（32,768 状态），7 人需要 262,144，明确不完成精确搜索。

针对本轮新三人三角固定例，另外运行 36 状态诊断，得到 2 个可行、1 个数值最优；最优的三对误差为 3.831827°、2.926917°、4.056464°，生成候选地面有效，固定身份残差也≤5°。这表明原错误放行并非“问题完全无可行对应”，但**没有证明这个数值最优是语义赢家**。

实际接线：
- `conditional_decision` 不调用 joint，有 pairwise 冲突直接返回 unresolved
- `run_local_panel.py` 不调用 joint
- `run_subset_schedule.py` 把 joint 与 conditional 结果并列保存，前者不会修正后者，也不会把候选的点/边/路径/完整环账本迁移到 joint 结果
- joint 候选保存源映射与 n 票点支持，但不提供 derive 的完整来源账本、band 状态或生成候选固定对应残差。仅有 `floor_polygon_valid` 不等于完整三维物理证书

因此正确描述是“已有单独的小组精确联合对应工具”，不能说已完成通用跨点数联合融合或单结果判定闭环。最多匹配、部分歧义和同点数联合歧义也不能统称同一种统计不确定性。

## 6. 支持账本：哪些计票正确、哪些还有缺口

### 已核验正确

- `derive_candidates` 先拒绝重复 worker / id；partial 映射 injective；每位来源每个槽位最多贡献一次
- 三份坐标完全相同、但独立 worker 不同的接口控制仍给每角 3 票、每直接边 3 份见证、完整环 3 份见证。**没有按坐标去重，符合既定独立票要求**
- 中性插点例中，锚点原边只有 1 份直接见证，另一来源仅记 1 条经过额外角对的路径，完整环见证也只有 1 份，没有把“经过插点的路径”误计成直接边或整环
- joint 的两两误差和只是优化目标；坐标融合按来源一份贡献，没有因 n(n−1)/2 个比较自动增加人员票
- 多个观察锚点之间支持重叠，程序有明确不可相加成模式概率的警示

### 需要补足或明确披露

- 路径 payload 只含两个端点 `source_indices`，没有实际中间节点、方向、路径坐标。完整原始来源在手时可追回，但单独看该字段无法审计它具体省略了什么；当只有两点对应时两条环向路径还可能都成立。建议导出有向中间索引列表及其来源版本，无法唯一确定就保留两条路径
- 对某条 partial mapping 一旦发现任何并列，当前跳过该来源对锚点的全部 donor，不提取所有最优映射共有的确定部分。这是保守损失覆盖，不是已验证误计票；后续可研究仅使用所有最优解不变的对应，同时保留局部歧义
- mixed synthetic/real 元数据输入可通过，顶层虽报告 real=1/synthetic=1，角点支持仍为 2，conditional 也可给 single；joint 不返回相同的 population 分拆。这是缺少证据人口隔离防护，**本复核没有证据认定当前真实三人试验受污染**。推荐按实验人口显式拒绝混用，或分别输出真实与模拟支持；不要按坐标内容判断独立性
- complete-ring mapping witness 证明整环索引映射关系，不证明来源画过生成的新坐标，不证明视觉 GT，报告在这一点上的说明是正确的

## 7. 可实施优先级

1. 先用固定三人回归防止“证书与生成映射脱节”，实施本隔离 guard 或等价的认证映射直连生成方案；保持原数据和全部备选
2. 若推进 joint 接线，先统一一个不可变的 correspondence 对象供生成、全对约束、残差、点/边/路径/环来源共同使用；不让不同阶段重新择配
3. 将 path 内部节点和 population 支持拆分补齐，再讨论支持比例；不改独立人员的相同坐标计票规则
4. 将 cardinality–cost 前沿和部分歧义范围作为研究输出，与 Lee、点融合/QTSB 等并行对照，不先决定哪个方法或候选胜出

这些建议针对Pro原型的实现；当前主研究仍按全部当前人员形成图级结果推进，不能以保留锚点候选替代它，也不把任何歧义设为永久停机前置。

## 8. 复现

环境：Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、Shapely 2.1.2。使用已有隔离依赖目录，未安装新软件。标准依赖环境中：

```bash
python code/apply_minimal_guard.py
python code/audit_checks.py
python code/test_guard_regressions.py
```

`audit_checks.py` 自带必要原测试及固定输入，只修改 `results/`。原版失败检查存于 summary，并不以异常提前中止后续检查。若希望重建新三人 fixture（会写该同名合成 fixture），运行 `python code/search_stronger.py`；一般复验不需要搜索。

主要证据：
- `results/audit_summary.json`：所有检查，原版失败保留
- `results/new_three_record_before_after.json`：三人原/修正状态、实际映射与全部误差
- `results/new_three_record_joint_diagnostic.json`：单独联合搜索结果
- `results/known_two_record_before_after.json`：上游既有两人问题复验
- `results/partial_oracle_cases.json`：部分对应独立穷举
- `results/patched_original_25_tests.log`、`results/guard_6_regressions.log`
- `patched/minimal_guard.diff`：隔离最小修改
