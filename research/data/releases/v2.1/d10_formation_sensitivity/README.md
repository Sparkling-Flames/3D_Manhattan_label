# v2.1 D10形成链敏感性

已复用原形成、有限配比、严格ABC、选队和结构角色分析，更新v2.1原答分数、当前楼外Q历史及其标签。全部46个条件×留出折（含ALL）完成。内层与外层训练排除台账均无目标建筑泄漏。此敏感性不另行决定正式评分公式或人员主解释分类。

基线是**当前v2.1 B8L2联合分类**。沿用的字段值 `B8L2_original`、`fixed_old_model` 是原读取合同中的名称：本目录分别指当前B8L2基线、固定当前B8L2模型配置后改用D10输入；另有D10完整内层重选配置。它们不表示冻结v2标签。`current_B8_source/` 保存具体基线和选择配置。

原336个有限面板及每面板924支实际团队保持。Manual的213,442个唯一团队更新40,655个，Semi的97,016个更新26,795个；其它评分复用。没有新增融合、重选几何或新增面板。Manual与Semi分别解释。

- `TRAINING_EXCLUSION_LEDGER.csv`、`D10_INNER_BUILDING_LOSSES.csv.gz`：训练排除和原超参数选择。
- `PARTITION_COMPARISON.csv`、`LABEL_TRANSITIONS.csv`：标签与分区变化。
- `COMPOSITION_COMMON_COMPARISON.csv`：共同已知标签团队上的构成比较；有效面板支持以行内计数为准，不自动等于336。
- `ABC_COMMON_PHYSICAL_SUMMARY.csv`：各分类下均合法的同一物理三臂团队比较；全合法事件、失败和覆盖另存，不以交集替代全部尝试。
- `SELECTED_TEAM_SUMMARY.csv`、`STRUCTURE_HIGHQ_ROLE_SUMMARY.csv`：实际选队、角色及B8L2/D10交叉评价。

四个 `*_COMPLETE.json` 是计算完成回执；`INPUT_CHECKS.json`保存输入更新范围。脚本入口为 `rebuild_v21_d10_sensitivity_20261029.py`，按 prepare、formation、response、summary、structure 运行，summary须在response完成后运行。
