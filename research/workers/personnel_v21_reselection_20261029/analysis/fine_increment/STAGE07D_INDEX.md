# 阶段07D：固定父构成的细类增量与OPPJOINT后续用途

数据：真人v2.1；代码和历史输入固定到 `a476461d7ede8db95da43de4139e612c05e618bc`。本包复用已完成端点，0次新增融合、0次重算评分。它补充阶段05全方法广筛与阶段03B/03D，保持各阶段身份；不重命名旧V3策略，不代替主方法跨粗类的大块替换结果。

## 阅读顺序和确实存在的结果

1. `analysis/fine_increment/README.md`：25个嵌套子/父关系的真正固定父构成用途，完整13544严格ABC、61指标，7个有实际支持的解释条件。
2. `analysis/fine_increment/FOCUS_CONDITIONS_ALL_METRICS_BOTH_WEIGHTINGS.csv`：图均、楼均、中位、同向比例分别保存。原完整汇总CA等主列为楼均，不应与图均混写。
3. `analysis/fine_increment/FIXED_PARENT_EVENT_METRICS.csv.gz`：13544个精确事件与全指标，A/B/C父构成一致；角色、人数、背景、成员、失败均可定位。
4. `analysis/fine_increment/ALL_FINE_CONDITIONS.csv.gz`：所有135432条条件/指标结果，包括负向、近零及未采用条件；`QUALITY_TAIL_AND_FAILURE_DENOMINATORS.csv`保留真实失败和较大损失分母。
5. `analysis/fine_increment/oppjoint_small_slow/`：第四个小慢类的有限面板内完整m1研究。5157共同背景、8316无序来源对、13326既有端点，真实反向AC另列。A/B来源对两个方向各半权。
6. `composition/exact_small_pool_policies_OPPJOINT_K4/`：20个Manual合法小池的OPPJOINT新角色策略，15池可比较前中段。旧阶段03D七法不变，此法单独接续。每个n取全无放回排列的精确边际，非新256顺序实验。
7. `composition/OPPJOINT_K4_complete_configuration_cases/CASE_TABLES.md`：3个完整配比代表/弱例、32格全部展开。每图924队，所有格均值、5%低尾、中位和withinSD；完整标量、成员、D、逐折角色及所有分项在同目录。

## 本包能够独立读取的内容

完整细分事件、全量汇总、重点逐图结果、全部失败分母、小慢类精确ABC关联及端点、小目标策略分布和端点概率关联、配比案例全部团队与分布均在包内。小输入另含冻结45法标签、类别历史中心、严格父子对应和合法目标条件。`STAGE07D_FINE_MANIFEST.csv`逐文件记录字节数与SHA256。

完整原图、所有原始几何和此前大缓存不重复打包。需要几何票账时，按team_key/event_id使用阶段03B/05/06的端点或机制几何；这里不把缺失的大几何说成已随包提供。

## 复算方法

将本包保持目录结构解压到共同工作根目录，Python需要pandas/numpy；绘图再需matplotlib。细分全量汇总可直接由包内事件快照复算：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis/fine_increment_analysis.py --stage summaries
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis/fine_increment_followup.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis/build_fine_increment_report.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis/oppjoint_small_slow_reverse.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python composition/code/write_oppjoint_entry_note.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis/format_oppjoint_mixture_example_note.py
```

`--stage snapshot`从阶段05的 `analysis/global_screen/EVENT_METRICS.csv.gz` 与 `analysis/global_parent_links/EVENT_PARENT_LINKS.csv.gz`重新筛出父构成固定事件；源文件SHA记录于 `SNAPSHOT.json`。两张大源表不在本包重复保存。

小慢类完整来源对与背景枚举（仍0新融合）需要阶段03B核心的 `composition/primary_panel_inputs/`：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis/oppjoint_small_slow_role.py
```

新进入策略重新聚合需要阶段03A已交付的完整合法目标输入和端点：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python composition/code/exact_small_pool_entry_policies.py --design composition/other_targets_design --endpoints composition/other_targets_endpoints/ENDPOINT_SCALARS.csv.gz --labels classification/MAIN45_LABELS_ALL_LOBO.csv.gz --roles classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz --condition manual --methods OPPJOINT_K4 --target-conditions targets/POOL_TARGET_CONDITIONS.csv --out composition/exact_small_pool_policies_OPPJOINT_K4
```

完整配比案例的选择与提取需要阶段03B核心及“03_联合与跨条件”分包。若此前使用无损压缩关联，先恢复该方法向量：

```bash
python composition/code/restore_team_vectors.py --compact composition/primary_compact_links --out composition/primary_manual45 --methods OPPJOINT_K4
MPLCONFIGDIR=/tmp/hohonet_mpl OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python analysis/extract_oppjoint_mixture_cases.py
python analysis/format_oppjoint_mixture_example_note.py
```

这是既有有限面板内完整枚举，非全池组合穷尽。主方法选型由全局比较与后续扩展支持；细分、时间角色和进入过程各有自己的支持范围。本包保存反例、质量代价与弱区分案例，不重新调标签以适配某次替换。
