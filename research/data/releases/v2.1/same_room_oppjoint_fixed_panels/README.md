# OPPJOINT 接入同房固定团队面板：v2.1 条件重聚合

OPPJOINT K3/K4 已接到现有同房融合结果。普通、同范围、主预算下，双视角 Q 共同有效的 307 个面板覆盖 127 对直接同房图片、65 图、13 栋楼和 9,766 条配对团队记录。建筑等权汇总后，K3/K4 的构成间方差占比分别为 **49.64% / 61.69%**。同一构成在两视角间的响应仍有较大差异：构成均值的汇总相关分别为 **−0.115 / −0.037**，具体成员残差相关为 **0.126 / 0.104**。

多数直接图对的构成均值协方差为正：K3 为 82/127，K4 为 85/127；但各图对的幅度及方向并不一致，建筑等权的汇总相关较弱。这支持在同房结果中继续区分人员构成与具体成员，也说明单视角的构成解释比例不能直接当作跨视角重复性证据。所有结果均按原定方法保留，没有按正负方向重新选择面板或参数。

## 本轮实际完成了什么

- 保留原 v2.1 的 2,659 个有限面板、92,342 条配对团队记录、182,555 个唯一端点；未增加团队、未重新拟合分类、未融合、未评分。
- 根据每个面板的目标建筑读取 `PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz` 中的 OPPJOINT K3/K4 标签，对**完整实际团队**重新计数。
- 在两个分类都全员已知、两视角相应指标均可计算的同一支持上，重新计算构成间、构成内方差及两视角协方差/相关。
- 直接复用既有 `analyze_response.py` 的 `moments`、预算和层级汇总函数。没有调用其 V3 连续历史预测分支，也没有将新分类伪装成旧 V3 名称。

原面板依据 **V3_BEHAVIOR 楼外粗类**选取候选人员和固定核心。本结果是在这些既有面板上接入 OPPJOINT 的条件分析，不是按 OPPJOINT 重新选人的同房严格 ABC，也不是全部共同人员子集的穷举。

## 分母与主要结果

主预算沿用原设计的 `mid_n_rep0`：共同已知人员池人数的一半，按原有限面板的可行区间裁剪，仅使用 replicate 0。预算不会随新标签资格重新改变。

| 普通同范围主预算支持 | 面板 | 直接图对 | 楼 | 配对团队记录 |
|---|---:|---:|---:|---:|
| 原设计请求 | 326 | 127 | 13 | 11,646 |
| K3/K4 全员共同已知 | 326 中有 309 个至少两团队 | 127 | 13 | 9,856 |
| 双视角 Q 有效，且每面板至少两团队 | 307 | 127 | 13 | 9,766 |
| 双视角有效转折数可计算 | 307 | 127 | 13 | 9,769 |
| 双视角有效记录时间 | 60 | 44 | 11 | 1,577 |

全体原面板中，两种新分类共同全员已知的配对团队记录为 63,892 条；其余 28,450 条含未知人员，保留在构成表和支持表中。表内记录可在多个有限面板重复出现，不能作为独立样本量。

下表均取普通同范围、`mid_n_rep0`。相关系数由先按“面板→直接图对→声明组→建筑”均衡汇总的方差/协方差计算，不是把全部团队记录混在一起求相关。

| 指标 | 分类 | 构成间方差占比 | 总响应相关 | 构成均值相关 | 成员残差相关 |
|---|---|---:|---:|---:|---:|
| Q（B8L2） | K3 | 0.4964 | 0.0275 | −0.1155 | 0.1259 |
| Q（B8L2） | K4 | 0.6169 | 0.0275 | −0.0371 | 0.1035 |
| 有效转折数 | K3 | 0.5741 | 0.2447 | 0.4148 | 0.0157 |
| 有效转折数 | K4 | 0.6078 | 0.2447 | 0.4080 | −0.0083 |
| 记录时间对数 | K3 | 0.2708 | 0.6328 | 0.6325 | 0.6351 |
| 记录时间对数 | K4 | 0.3575 | 0.6328 | 0.6012 | 0.6533 |

K4 严格细分 K3；在相同团队和相同有效指标支持上，细分会使构成间方差不减、构成内方差不增。因此 49.64%→61.69% 的增加含有分组变细带来的必然成分，不能单独证明 K4 的泛化更好。检查确认两分类的总方差、总协方差和有效分母完全相同。

这组数值**不能与旧普通 231 面板的 13.41% 直接比较**：面板范围、当前标签、已知资格和有效支持均有变化。本结果也不检验多域分类相对同容量 Q-top-N 的额外价值；该问题不影响本次已完成的下游接入。

## 文件及字段合同

| 文件 | 内容与读取要点 |
|---|---|
| [TEAM_COMPOSITIONS.csv.gz](TEAM_COMPOSITIONS.csv.gz) | 原 `panel_id`、`member_set_key`、两个 `team_key` 与新 K3/K4 完整人数向量。`OPPJOINT_K3_vector` / `OPPJOINT_K4_vector` 含所有团队成员；未知者计入 `unknown`，不填成其他类。原 `structure_vector`、`joint_vector`、`hi_selected` 等仍是旧 V3 设计字段。 |
| [PANEL_COMMON_SUPPORT.csv](PANEL_COMMON_SUPPORT.csv) | 所有原面板的请求数、两方法分别已知数及共同已知数；`panel_selection_method` / `selected_family` / `class_lo` / `class_hi` 保留旧面板选择身份。 |
| [PANEL_DECOMPOSITION.csv.gz](PANEL_DECOMPOSITION.csv.gz) | 每面板×指标×新方法结果；`scheme` 才是本次 OPPJOINT 方法。`n_requested` 是共同全员已知团队数，`n_joint_finite` 是两视角该指标均有效的团队数；不足两条时保留计数，方差不计算。 |
| [DECOMPOSITION_PAIR.csv](DECOMPOSITION_PAIR.csv)、[GROUP](DECOMPOSITION_GROUP.csv)、[BUILDING](DECOMPOSITION_BUILDING.csv)、[SUMMARY](DECOMPOSITION_SUMMARY.csv) | 逐级均衡汇总。`pooled_between_fraction` 是 `(between_var_a+between_var_b)/(total_var_a+total_var_b)`；`pooled_*_rho` 使用相应汇总协方差除以两视角标准差乘积。`valid_team_pair_occurrences` 是含跨面板重复的有效记录总数；`panels`、`direct_pairs`、`declared_groups`、`buildings` 单列。 |
| [ENDPOINT_AVAILABILITY.csv](ENDPOINT_AVAILABILITY.csv) | 182,555 个源端点的完整可评性、评分状态与几何状态交叉计数，另列有限 Q 数。 |
| [CHECKS.json](CHECKS.json) | 输入路径、范围与身份、人数/构成/端点关联检查、共同分母、嵌套恒等关系和源文件原字节未改变的回执。 |

`between_*` 描述按完整人数构成分组后的组均值变化；`within_*` 描述同构成中具体成员组合的残差。这是有限面板的描述性矩分解，不是人员与图片噪声的因果分解，也不是预测准确率。`member_residual_*` 中没有重复成员组合的构成格不能提供格内重复信息；相关分母为零时保留缺失。质量、结构、时间各自使用双视角有效支持，不用零填补失效值。

继承的指标名 `failure` 实际定义为 **`1 - complete_evaluable`，即完整输出不可评**，不能统称为原生融合失败。源端点中，181,239 个为 `complete_conditional / ok`，其余为：42 个 `below_four / not_evaluable`、202 个 `below_four / ok`、14 个 `invalid_floor / unavailable`、1,058 个 `no_connection / not_evaluable`；上述不可评端点均无有限 Q。尤其 `below_four / ok` 保留几何状态正常与完整评分不可用的区别。时间要求 `recorded_time_eligible=True` 且总秒数为正，沿用已有来源，不重估 active time。

## 输入、复现与核验

- [原固定面板及设计回执](../same_room_current_extended_design/DESIGN_RECEIPT.json)
- [原 v2.1 唯一端点](../same_room_current_results/finite/native/ENDPOINT_SCALARS.csv.gz)
- [新分类正式楼外标签](../../../../workers/personnel_v21_reselection_20261029/stage07_adoption/PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz)
- [适配脚本](../../../../../tools/thesis_main/analysis/reaggregate_v21_same_room_oppjoint_fixed_panels_20261029.py)
- [定向测试](../../../../../tests/test_v21_same_room_oppjoint_fixed_panels.py)

在仓库根目录执行：

```powershell
python -m tools.thesis_main.analysis.reaggregate_v21_same_room_oppjoint_fixed_panels_20261029
python -m pytest tests/test_v21_same_room_oppjoint_fixed_panels.py -q
```

核验覆盖目标楼外折、标签唯一性、K3/K4 嵌套、全团队构成总人数、团队成员/pool/建筑/reference 对应、指标共同支持、矩分解恒等关系及源输入原字节不变。定向测试覆盖未知和重复标签、错误成员、失败/缺失时间，以及分解与层级汇总。没有运行新的全库 policy32、OPPJOINT 选人同房严格 ABC 或全量原生融合；这些都不会由本目录的完成状态自动继承。
