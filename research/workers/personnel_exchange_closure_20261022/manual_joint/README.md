# Manual 联合分类的换块与背景扩展

本目录属于 `personnel_exchange_closure_20261022`。底层原答、参考、评分和融合使用真实数据 **v2**。`V3_JOINT_QT` 是上一轮分类方法的名称；本轮复用已保存的楼外标签，补做实际换人、换类和连续 Q/T 对照，不重新训练分类。

## 阅读入口

- `MANUAL_JOINT_FINDINGS_ZH.md`：中文结论、条件建议、效应、适用范围与机制。
- `EFFECTIVE_CONDITIONS.csv`：可直接并入总报告的条件表；三种方向差值和对称差值分别保留。
- `CONDITION_SUMMARY.csv`：所有登记方向、n、m、难度，以及明确标记的后续语义分层。
- `COMMON_ABC_SIGNED_EFFECTS.csv`：在相同三队共同可评事件和相同权重上的 B−A、C−A、C−B、C−(A+B)/2；与原逐对可评分分母并存，满足线性闭合。
- `ALL_COMPONENTS_AND_DENOMINATORS.csv.gz`：全部数值指标的图、楼、事件真实分母。
- `mechanism_case/MANUAL_JOINT_CASE_ZH.md`：真正属于本联合分类的 B6 n20/m4 精确 ABC 原答—票账—融合—分项案例，包含 ERP/BEV/3D 图；C 对 B 升质节时，同时保留 C 对 A 下降和底面/三维代价。
- `phase_b_highq_slower/`：在阶段 A 观察后选择“训练折最高 Q 且相对较慢目标类”的 n20/m4 条件；另冻结 seeds100/101 的两个新背景，完整枚举其有限成员块。阶段 B 单列，不能称全新建筑盲测。

## 输入与标签

`INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz` 是旧 `ALL_METHOD_LABELS_LOBO.csv.gz` 中 Manual、`V3_JOINT_QT` 的原样筛选，包括历史特征、机会支持和缺失状态。`TRAINING_CLASS_CENTERS.csv` 给出逐建筑排除折的语义中心；`ACTUAL_MEMBER_LABELS.csv.gz`、`AVAILABLE_CLASS_CENTERS_AND_MEMBERS.csv` 说明实际图片人员池中的成员和特征。类别编号必须连同建筑折解释。

`GLOBAL_DESCRIPTIVE_LABELS_AND_HISTORY.csv` 与 `GLOBAL_DESCRIPTIVE_CLASS_DEFINITIONS.csv` 保留全数据描述用五类及未分类者。它们不用于目标图片的实际替换。楼外折允许不同类数，本目录没有把所有折强行改成五类。

`ACTUAL_DIRECTION_HISTORY.csv` 保留源类、目标类在该图实际可用成员上的历史 Q、对数时间差及成员名单。`HISTORY_STRATUM_DEFINITION.json` 解释为什么全折中心“较快”与该图子集均值偶尔不同；初始主层未据此删除图片。

## 精确实验与可复算结果

| 文件 | 内容 |
|---|---|
| `DESIGN_FREEZE.json`、`DESIGN_INTENT_ZH.md` | 在新增端点结果前保存的范围、参数与校验和 |
| `CAPACITY_ALL_N_M.csv.gz` | 登记 n19/20/21 范围中方向与真实容量 |
| `FEASIBLE_BACKGROUND_CLASS_CONFIGURATIONS.csv.gz` | 可行背景类别人数向量 |
| `MEMBER_BLOCK_AND_BACKGROUND_COVERAGE.csv` | 全池理论规模、已登记源块/目标块/背景数及未穷尽范围 |
| `BACKGROUND_PANELS.csv.gz` | 实际有限源储备、目标储备、共同背景 |
| `EVENTS_REGISTERED.csv.gz` | 唯一物理 ABC 事件、精确成员、实际 m、类别席位变化 |
| `TEAM_REQUEST.csv.gz` | 去重团队端点请求，交由上层中央 native runner 执行 |
| `EVENTS_COMPLETE.csv.gz` | 完整逐事件结果，失败也保留 |
| `POLICIES_REGISTERED.csv.gz`、`POLICIES_COMPLETE.csv.gz` | 同 A、D、m 的分类约束/连续 Q/T 策略对照 |
| `RESULT_BATCH_INDEX.csv`、`results/*/COMPLETION.json` | 分池即时保存的结果与来源校验和 |
| `PANEL_EFFECTS.csv.gz`、`IMAGE_EFFECTS.csv.gz`、`BUILDING_EFFECTS.csv.gz` | 从精确事件逐级重聚合的结果 |
| `BACKGROUND_REPETITION.csv` | 同条件换背景后的效应均值、范围和方向支持 |
| `TARGET_MEMBER_EXCLUSION_*` | 完整有限目标块中去掉某成员后的描述对照 |
| `NESTED_N_PATHS_COMPLETE.csv.gz` | 同 X/Y/Z 与嵌套 D 的人数路径及新增背景成员 |
| `B6_FIXED_TARGET_FIVE_DIFFERENT_BACKGROUNDS.csv` | 固定五人目标块、固定类别席位，但背景改变导致成功/失败的精确案例 |
| `TARGET_WITHIN_CLASS_EXACT_SWAPS.csv.gz` | 缓存目标端点之间的实际换 1 人机制对照，单列为补充而非大块主实验 |

### 逐事件字段约定

- `same_*` 是 B−A，`cross_*` 是 C−A，`net_*` 是 C−B。
- `sym_*` 是 C−(A+B)/2。每个互补源块分区只登记一次，A/B 朝向由哈希固定，因此对称量适合概括源类替换的方向作用；原三种差值仍完整保存。
- `sym_cross_abs_B8L2` 是 (|C−A|+|C−B|)/2；`common_quality_within_abs` 是 |B−A|，仅在三队都可评分时比较。
- 时间来自既有人员作答记录，团队取已知且同来源记录秒数之和；对数比平均后转百分比。`sym_recorded_time_logratio` 比较 C 与 A/B 总记录时间算术均值。它不是新测生产工时，也不是预测误差改善率。
- 质量失败不赋零。每个指标保留已知事件/图/楼分母，另列失败事件与唯一失败端点数，避免失败被均值掩盖。
- 聚合顺序为有限背景面板内事件平均 → 图片平均 → 建筑平均。大量共用团队的事件不是同样数量的独立证据。

## 复现顺序

在仓库根目录运行；推荐保留原已恢复输入，避免重做既有研究。新端点由项目中央适配器使用冻结 engine/评分执行；本目录的评价代码不调用融合。

```bash
python research/workers/personnel_exchange_closure_20261022/manual_joint/register_design.py
python research/workers/personnel_exchange_closure_20261022/manual_joint/describe_labels.py
python research/workers/personnel_exchange_closure_20261022/manual_joint/summarize_coverage.py
```

中央 runner 完成请求后：

```bash
python research/workers/personnel_exchange_closure_20261022/manual_joint/evaluate_registered.py --require-complete
python research/workers/personnel_exchange_closure_20261022/manual_joint/summarize_results.py
python research/workers/personnel_exchange_closure_20261022/manual_joint/save_b6_case.py
python research/workers/personnel_exchange_closure_20261022/manual_joint/analyze_target_swaps.py
python research/workers/personnel_exchange_closure_20261022/manual_joint/plot_results.py
```

阶段 B 先运行 `register_phase_b.py`，完成中央请求后，给同一个评价和汇总代码传入 `--study-dir research/workers/personnel_exchange_closure_20261022/manual_joint/phase_b_highq_slower`。它拥有独立冻结清单、结果批次和汇总。主层与阶段 B 的精确团队仍由中央缓存按相同成员集合去重。

两阶段均完成后运行 `close_common_abc.py` 和 `build_final_outputs.py`，生成共同分母闭合表、中文报告和采用表。后者只重聚合已保存结果，不再选队、融合或评分。

机制小包已有3队完整状态，重画时运行 `mechanism_case/render_case.py`；投票与分项说明运行 `mechanism_case/explain_case.py`。两者只读已存内容、0次融合、0次评分。`mechanism_case/export_case.py` 记录过3次元数据重放与几何相同验证，已有 `case.json.gz` 和回执时直接返回，不额外回放。

### 必要外部输入与代码

- `research/workers/personnel_useful_taxonomy_v3_20261021/taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz`
- `research/workers/personnel_useful_taxonomy_v3_20261021/composition/PANELS.csv`
- `research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/evaluate_joint.py`
- `research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz`
- `research/workers/personnel_global_composition_20261021/continuation_20261021/n20_abc/event_kernel.py` 与其冻结几何/质量依赖
- 本轮统一 `delivery/endpoints/ALL_REQUIRED_ENDPOINT_*` 去重全集。按 `integration/reproduce/REPRODUCE_ZH.md` 恢复 `native/batches/` 后，评价器可直接读取 compact 标量与几何，不需要另打包 `native/reused/` 与 `native/runtime/` 大缓存；已有运行缓存仍优先复用。每池 `ENDPOINT_SOURCES.csv` 保存实际读入文件与 SHA256，不重复打包旧仓库输入和全量原图。

恢复时先读 `DESIGN_FREEZE.json`、`EVALUATION_RECEIPT.json`、`RESULT_BATCH_INDEX.csv`。评价器会复用已完成池，缺失池记录在 `PENDING_POOLS.csv`，不会抹去已保存结果。确定性融合终点只计算一次；本目录不展开等价成员加入顺序。
