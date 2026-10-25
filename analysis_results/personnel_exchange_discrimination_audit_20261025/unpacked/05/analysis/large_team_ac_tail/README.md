# 大团队 AC 尾段分析

固定 286 个原锚点，分析原严格 ABC 末端之后的直接 AC 过程；原 Y7 的源类人员逐人进入共同背景，X7/Z7 固定，m=7。全部锚点均有 k0 至 k7，因此按 k 比较保留相同路径和图片容量。另以实际池 N=35 的固定队列，按实际人数 n21 至 n28 展示。失败不改变队列。

本分析只保留 A/C，报告 CA 有符号差和 |CA|、实际 A/C 分数与几何、失败、相对严格末端及前一步变化。**无同类 B 对照，不能把尾段结果称为同类/跨类幅度差异。** CA 净差变化与 C 自身变化分别报告；`joint_AC_*` 提供同分母的分解。

`CURVE_BY_K_*`：同一组路径的 k0…7；`FIXED_N35_BY_N_*`：固定 N35 路径的 n21…28；`FROM_STRICT_TAIL_BY_K_*` 与 `STEP_BY_K_*`：相对严格末端及相邻步。先图片内平均路径，再给图片等权和建筑结果；指标各自保留真实有效分母。失败、明显损失、方向反转保留。记录时间是已有库存 source 秒；同一人进入 A/C 时绝对时间差不变，百分比变化可来自分母增加。

默认读取 `results/large_team_ac_tail/EVENT_METRICS.csv.gz`。运行：`python analysis/large_team_ac_tail/code/analyze_ac_tail.py`。此脚本使用 `analysis/size_paths/code/analyze_fixed_block_paths.py` 中通用的保存与聚合函数，不运行融合、不读取其他实验结果选路径。
