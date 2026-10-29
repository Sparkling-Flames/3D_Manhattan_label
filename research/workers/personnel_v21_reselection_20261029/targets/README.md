# v2.1 目标级结构条件

提交：`a476461d7ede8db95da43de4139e612c05e618bc`。本阶段新算 294 个目标池、255 个目标的结构条件，覆盖 8,385 份已有正式可用原答；没有修改参考、资格、人工难度或融合。

中文说明：[TARGET_SCOPE_AND_DIFFICULTY_ZH.md](../stage01/TARGET_SCOPE_AND_DIFFICULTY_ZH.md)。

## 可直接接入

- `POOL_TARGET_CONDITIONS.csv`：以 `pool_id` 关联实验，以 `image_id + condition + reference_id` 确保目标身份；正式等级和历史意见分别保留。
- `TARGET_STRUCTURAL_FEATURES.csv`：去重目标特征，不重复 Manual/Semi 共享参考。
- `OTHER_TARGETS_EVIDENCE_AND_CONDITIONS.csv`：其它 31 池的原人工证据与主空间对比。
- `RECORD_TARGET_LINKS_AND_ALL_SUPPORT_WEIGHTS.csv.gz`：`record_id` 是原 `object_id`；附人员/目标/条件、来源、时间、B8L2/D10 和 ALL 支持权重。
- `TARGET_CONDITION_SUPPORT.csv`：结构机制组的池/图/楼/原答数。
- `OPTIONAL_EXACT_TARGET_GRADE_QUESTIONS.csv`：3 个确无精确目标人工分级意见的具体目标；当前结构研究不等待这些回答。
- `CHECKS_AND_SUPPORT.json`、`INPUT_MANIFEST.json`：实际完成范围和精确输入。
- `code/`：实际运行代码及 5 个原样提取函数的来源与哈希。
- `TARGET_SPACE_EXAMPLES.png`：四图主空间和其它合法空间的冻结底面叠图。

`source/` 是工作时读取的仓库输入副本，不是本阶段新增结果，交付时不重复打包；`INPUT_MANIFEST.json` 给出原始仓库路径和哈希。

## 关键语义

`geometric_challenge = ref_turn5 > 6 or ref_H > 0 or ref_short_edges > 0` 沿用既有结构敏感性定义。它不等于人工“困难”。`ref_H` 是相机至顶点射线在底面边界模型中的自遮挡数，不是照片内全部视觉遮挡或玻璃/开口的人工结论。

原主目标正式三档保留；其它 30 个目标中 22 个有精确历史第三方意见、5 个有助手意见、3 个缺精确意见，全部保持正式等级未知。31 池中 30 池有上述结构挑战，18 池与同图主空间的二分条件不同。

在楼外/特征有效支持筛选后，重新调用 `code/build_target_conditions.py::hierarchical_history_weights`。不要将 ALL 权重分母直接用于楼外或缺失值子集。时间保留来源；`source_time_seconds` 和 `target_time_seconds` 不合并成一个未注明来源的字段。

## 复算

```bash
PYTHONPATH=/tmp/hohonet_v21_deps python targets/code/build_target_conditions.py \
  --repo /path/to/3D_Manhattan_label --out targets
MPLCONFIGDIR=/tmp/hohonet_mpl PYTHONPATH=/tmp/hohonet_v21_deps \
  python targets/code/plot_target_space_examples.py \
  --repo /path/to/3D_Manhattan_label --out targets/TARGET_SPACE_EXAMPLES.png
```

依赖：Python、NumPy、pandas、Shapely，出图另需 Matplotlib。`--fallback-source` 仅为缺少 checkout 时读取同提交的本地原输入副本，不改变输入内容。
