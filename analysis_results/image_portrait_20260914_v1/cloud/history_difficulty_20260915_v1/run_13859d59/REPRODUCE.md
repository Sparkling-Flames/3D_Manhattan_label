# 历史粗分类研究复算

本包包含本轮全部新代码、逐图结果、精确数值核、实际输入来源、原评论、失败日志和必要历史过程。没有原图、权重或视觉模型推理。旧实验difficulty只存在于不可变原始证据中，不进入白名单分析字段。

解压后先打开根目录START_HERE.html。命令在repo目录运行，Python3.11：

```bash
python -m pip install -r requirements-history.txt
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
python -m pytest tests/test_history_difficulty_v1.py tests/test_history_difficulty_v1_followup.py -q
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core prepare
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_targets
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_predict
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_associations
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_transfer
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people_conditioned
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_diagnostics
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_finalize
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_report
```

Windows在PowerShell使用 `$env:OPENBLAS_NUM_THREADS="1"` 与 `$env:OMP_NUM_THREADS="1"`，其余python命令相同。

预测脚本已有对应候选CSV时会复用，完整重拟合应将新OUT/prediction备份并移出后运行；不删除原始数据或旧mainspace结果。仅重算汇总使用`history_difficulty_v1_predict --summarize-only`。

本包省略重复原始模型NPZ，但保留全部70种205图精确Gram矩阵，足以复算本轮L2数值核、训练侧中心化/PCA/Ridge/kNN。不可据此恢复原空间张量，也不能宣称包含648张原数组。重新导出核须在原仓库取得相应原始数值数组后运行`history_difficulty_v1_models`；该命令只读导出数组，不推理。两张Bi extended预测不可用，反馈表和失败表均保留。

训练/检验使用包内固定隔离；目标人类人数、簇数、分歧不进入纯图片预测。E_conditioned是Manual/Semi分别训练的主人员结果；E/早期混合Q/T画像记录仅保留审计，不作为主结果。A_B/associations_verified.csv取代首次none控制标志错误的临时表。原专家评论空字符串计数修正见expert/COMMENT_COUNT_CORRECTION.json。

所有图、真实子集和定义版本都不会增加独立样本。历史重排不是日历到达顺序，累计到19在实际n较小时是观察范围截断值。粗类不是正式最终收敛判据。
