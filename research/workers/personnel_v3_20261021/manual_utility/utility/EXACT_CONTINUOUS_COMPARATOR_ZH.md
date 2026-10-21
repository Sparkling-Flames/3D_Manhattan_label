# 最终联合分类的同字段连续对照

最终 taxonomy 冻结后，联合类别选中了 EQT、GEQT 或 CQT。通用旧 QT + 五项全局几何并不包括 CQT 的简单/复杂机会指标，且新联合类自身 q_history/t_history 与旧任务效应拟合定义不同。因此不能只比较旧通用连续特征就把联合类别的优势归因于离散分类。

在未读取新联合类目标选队成绩之前，追加两个固定对照：`exact_continuous` 与 `exact_continuous_class_fine`。它们使用每个目标建筑外最终选定 family 的**完全相同原始指标**；后者再加入最终细类人数比例。原先的通用 QT、QT+五项结构、粗类、细类仍全部保留，公共候选支持不变，模型 ridge、人数交互和两个选择目标均不变。

| family | 同字段连续输入 |
|---|---|
| EQT | turn_history、short_history、q_history、q_downside、t_history |
| GEQT | EQT 加 area_history、height_history |
| CQT | simple_turn_history、complex_turn_history、complex_short_history、q_history、q_downside、t_history |

同一规则也用于新行为类别：TURN 使用 turn/short；STRUCTURE 再加 redundancy；SCALE 使用 area/height；JOINT 使用五项全局结构；CONTEXT 使用 simple_turn/complex_turn/complex_short 加 redundancy/area/height。每折精确列名随 `FITS.csv.gz` 保存。这样既保留统一的五项几何基准，也检验分类相对其自身输入是否另有用途。

所有字段先求团队人员均值与二阶矩，和原连续基准一样加入 20/n 交互；不添加目标建筑结果。联合类别与原连续值使用同一标签文件的楼外映射，已知标签必须有上述全字段，未知不填零。粗类与细类来自同一 family 同一树，若最终未增加细分，应明确写无细分增量。

这一补充由输入信息对齐触发，不按目标效果决定采用。此前保存的规则与选择阶段包仍保留原身份；最终用途包包含这个追加对照及完整结果。
