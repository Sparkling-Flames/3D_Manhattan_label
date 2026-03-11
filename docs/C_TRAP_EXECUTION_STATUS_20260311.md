# C 线 Trap 生成推进状态（2026-03-11）

这份文档记录 2026-03-11 之后，C 线从只有 manifest 层推进到有可执行生成层的当前状态。

## 1. 这次推进了什么

相较于 2026-03-10 的状态，这次新增了两类硬产物：

1. `tools/perturbation_operators.py`
   - 正式实现 C1 扰动算子引擎。
   - 覆盖 acceptable、underextend、corner_drift、corner_duplicate、overextend_adjacent、over_parsing、topology_failure、fail 八类 family。
   - 使用 frozen canonical 表示层，并锁死 `x wrap / y clamp`。

2. `tools/materialize_c_traps.py`
   - 直接读取 `stage1_prescreen_semi_import.json` 的 predictions。
   - 把 `trap_manifest_draft_v1.csv` 中的 synthetic rows 转成 frozen plan，并调用 operator engine 生成实际输出。

## 2. 新 bundle 的角色

新的生成层 bundle 目录为 `analysis_results/c_manifests_20260311/`。

该目录的核心角色不是替代论文最终定稿，而是把以下事情正式落盘：

1. synthetic trap 不再只停留在 frozen_rule 描述；
2. 每个 synthetic row 都有明确 seed、lambda_level、operator_id、config；
3. frozen plan 可重放；
4. 生成结果与 A 线、C 线 manifest 可直接 join。

## 3. 仍然没解决什么

这次推进虽然是大幅前进，但仍有三个边界必须保留：

1. 这不等于 revised thesis target 已经实现；
2. 这不等于 trap 集已经收齐；
3. 这不等于最终论文定稿的 semi 池已经冻结。

## 4. 当前状态的一句话概括

C 线已经从可 join 的 manifest 层推进到有可执行 operator engine、有 frozen plan、能从当前 PreScreen_semi import predictions materialize synthetic trap 的阶段；但它还不是最终论文 target 完成证明，也不是 trap 集完全收齐证明。
