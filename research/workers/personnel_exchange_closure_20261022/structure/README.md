# Manual 结构类：大团队有效换类条件

## 已完成的成果

本目录是 `personnel_exchange_closure_20261022` 的结构分类主线，底层真实数据 v2，分类标签复用此前 v3 研究。**29,928条登记事件全部完成，36,804个必需去重端点全部可用，缺口0。** 新登记、每图事件、分批原生端点、分析表分别完成后立即保存。

直接阅读 [中文研究报告](REPORT_ZH.md) 与 [有效换类条件表](RECOMMENDED_CONDITIONS.csv)。主要采用为 Manual 的“常规表达→较多转折”，n20/m4 和 n20/m7；保留各难度、背景、失败、时间代价及反向条件。该结论没有替代或删除其它既有分类。

| 文件 | 内容 |
|---|---|
| `REPORT_ZH.md` | 标法、成员、主要采用条件、分项、重复性、规模与人数路径、机制及范围 |
| `RECOMMENDED_CONDITIONS.csv` | 14个主要／补充／风险条件；有符号变化及各分母、共同ABC字段、实际成员容量、采用判断 |
| `COMMON_ABC_COMPARISON.csv` | 同一ABC可评分分母上的B−A、C−A、C−B及绝对幅度；总条件、难度、背景分别列出 |
| `MAIN_QUALITY_COMPONENTS.csv` | m4/m7各质量分项及真实分母 |
| `FIXED_A_M_RESPONSE.csv` | 固定A、嵌套替换块的m响应；与独立主层分别解释 |
| `figures/STRUCTURE_ADOPTION.png/pdf` | 可分享的研究图，建筑效应、绝对幅度、固定A规模增量和时间取舍 |
| `FIELD_GUIDE_ZH.md` | 标签、三队、各指标、单位、失败、时间与分层权重 |

## 标签、成员与资格

- `CLASS_LABELS_ALL_DATA_DESCRIPTION.csv`：全数据描述标签，59名有支持人员、3名未知；不用于目标图评价。
- `CLASS_DESCRIPTION_CENTERS.csv`：各描述类实际成员、结构中心和机会支持，Q/T/难度/scope/Semi辅助字段保留真实缺失。
- `CLASS_LABELS_REUSED.csv.gz`：实际实验的目标建筑外冻结标签。
- `CLASS_ROLES_REUSED.csv`、`LOBO_ROLE_CENTER_RANGE.csv`：逐折原类编号、训练角色、成员名单、历史特征中心及其范围。
- `OTHER_FOLD_FAMILIES_NOT_REGISTERED.csv`：训练选择为其他家族／类数的图片，保留其旧结果，不强行映射成三类。
- `SCOPE_NOT_IN_PRIMARY.csv`：19个门洞／特殊范围Manual池。本轮正式融合仍采用冻结资格。

本轮仅使用训练家族选为 `TURN/K3` 的16折；`E2`是常规表达，`E3`是较多转折。不同折原始M编号没有直接拼接。三类是先前数据发现的结果，不是预设所有分类只能三类。

## 完整事件与端点

**完整可读事件文件为 `EVENTS_COMPLETE.csv.gz`**。它包含精确A/B/C、D/X/Y/Z、实际n/m、类别席位变化、标签角色、全部评分与几何诊断、失败、历史特征、时间来源及条件身份。

`ALL_EVENTS_REGISTERED.csv.gz` 和 `ALL_ENDPOINT_REQUESTS.csv.gz` 是主实验加固定A路径的统一登记。`results/COMPLETION.json` 已确认29,928/29,928完成；`results/USED_ENDPOINT_INDEX.csv.gz` 与 `ENDPOINT_SOURCES.csv` 给出每个端点的中央标量／几何文件和SHA。中央端点位于：

```
../native/batches/structure_001/ … structure_011/
../native/batches/mpath_001/
```

每批有 `ENDPOINT_SCALARS.csv.gz`、`ENDPOINT_GEOMETRY.csv.gz` 和完成标记；7个旧缓存端点的恢复来源也在端点索引中。共享端点只融合一次，本目录不重复打包中央结果。`results/pools/` 是及时保存的检查点，可作为单独恢复分片，但不与完整事件表重复塞入同一精简ZIP。

## 覆盖的精确定义

`DESIGN_FREEZE.json` 和 `M_PATH_FREEZE.json` 分别保存主设计与固定A补充的冻结规则、输入SHA和参数。n20主层按方向与实际容量登记m4、m7和最大可行m≥4去重后的条件；额外展开固定XYZ的嵌套n路径。固定A的m路径与主层分别分析。

| 文件 | 含义 |
|---|---|
| `CAPACITY_AND_COVERAGE.csv.gz` | 每图／方向／n/m的可行与不可行容量、完整D和ABC组合精确数量、未覆盖数量 |
| `COUNT_VECTOR_COVERAGE.csv.gz` | 所选条件全部3,073个ABC可行背景类别人数向量，均至少有一个真实背景 |
| `BACKGROUND_PANELS.csv.gz` | 3,796个实际D；每个D可行与登记的源配对／目标块数量 |
| `MEMBER_BLOCK_INCLUSION.csv.gz` | 每个可选成员在登记块中的出现次数，含零次 |
| `N20_FULL_CLASS_VECTOR_SPACE.csv.gz` | 无约束n20的全部类别人数向量与实际观测状态 |
| `N20_FULL_MEMBER_SPACE_BY_POOL.csv`、`N20_FULL_SPACE_TOTALS.csv` | 无约束成员集合精确规模；全正式域28,108/251,050,935,840个集合 |
| `LINKED_N_PATHS.csv.gz` | 固定X/Y/Z，嵌套D的人数路径 |
| `M_PATHS.csv.gz` | 固定A，嵌套D与XYZ前缀的替换规模路径 |

深度D面板选择最多4对源类块与4个目标块作交叉，选择通过固定哈希和成员频次均衡；不是每格只取3队。可行人数向量完整覆盖不等于具体成员或顺序穷尽。大整数应按十进制字符串读取，避免float64丢失精度。

## 可重聚合的分析

`analysis/`包含逐具体背景、背景人数向量、逐图片、逐建筑、指标长表、难度／背景分层、成员多样性、保留背景检查、来源／历史Q解释、时间与质量共同分母、n/m路径和机制候选。所有指标保留各自真实分母。

主权重为：具体D内成员组合等权→同一人数向量内D等权→图内人数向量等权→楼内图等权→楼等权。`COMMON_ABC_COMPARISON.csv`统一三变化的评分分母。失败依原合同记录，不用零Q填补。

机制原图与原生票账共享整合目录 `../mechanisms/`，入口为 [机制解释_原答到融合.md](../mechanisms/机制解释_原答到融合.md)。本主题没有混入同房研究。

## 复现顺序

在仓库根目录运行。已有完成表可直接从 `analyze_structure.py` 开始重聚合，无需重复融合。

```bash
python research/workers/personnel_exchange_closure_20261022/structure/register_structure.py
python research/workers/personnel_exchange_closure_20261022/structure/register_m_paths.py
```

中央计算器根据 `ALL_ENDPOINT_REQUESTS.csv.gz` 恢复已有端点并补算缺口；完成标记存在后：

```bash
python research/workers/personnel_exchange_closure_20261022/structure/evaluate_structure.py
python research/workers/personnel_exchange_closure_20261022/structure/analyze_structure.py
python research/workers/personnel_exchange_closure_20261022/structure/describe_structure_labels.py
python research/workers/personnel_exchange_closure_20261022/structure/describe_full_vector_space.py
python research/workers/personnel_exchange_closure_20261022/structure/summarize_change_loci.py
python research/workers/personnel_exchange_closure_20261022/structure/summarize_common_abc.py
python research/workers/personnel_exchange_closure_20261022/structure/finalize_structure.py
```

中途恢复可用 `evaluate_structure.py --allow-partial`，每图及时保存。正式报告只来自所有登记完成的版本；完整表SHA在 `results/COMPLETION.json`，分析来源SHA在 `analysis/COMPLETION.json`。

核心旧依赖为 `personnel_useful_taxonomy_v3_20261021/composition/design_matched_events.py`、`personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py`、原生冻结融合／评分代码及INPUT_SNAPSHOT。精确输入路径与SHA由登记JSON保存，中央恢复说明给出依赖取得方式。报告和CSV/PDF不需要这些执行依赖即可阅读。

本轮团队／背景由不读取目标结果的规则选择；背景和难度的采用建议依据内部结果提出。材料已多轮探索，按v2内部验证说明，不冒称新的外部盲测。
