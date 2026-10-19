# 从冻结结果重导反向全部候选预测

`reexport_reverse_predictions.py` 用于恢复精简包省略的
`reverse/results/folds/<fold>/predictions.csv.gz`。它不需要原预测文件、损坏前缀或历史故障收据，也不会调用故障修复脚本。**类别、人员关系、K 与候选选择均不重拟合，融合不重算。**

## 1. 最小输入和计算边界

默认来源是本脚本上一级的 `work_personnel_typing_A_20261019/`，只需：

- `events/common_events.csv.gz`；按窄列分块读入，保持原事件顺序。
- `reverse/selection_common.py`；执行前核对各折 `COMPLETE.json` 中的冻结 SHA。
- 指定外折的 `reverse/results/folds/<fold>/{classes.csv.gz,calibration.csv.gz,COMPLETE.json}`。

类别及 5 个所选别名从冻结类别表和 `COMPLETE.json` 读取；64 个候选的类内/类间概率及 k×难度基线从冻结校准表读取。本轮校准表没有保存全局和仅 k 的回退概率，因此入口只在 `COMPLETE` 指定的**训练楼、原训练面板**重新汇总这些回退值，并要求重汇总的 k×难度基线与保存值相差不超过 `1e-12`。这一步不重新估计类别的条件率、不重选参数，也不读取目标楼结果来校准。

每个外折输出 64 个候选＋5 个别名，共 69 个方法；`FULL` 没有目标楼事件，因此不能选择 FULL 导出。所需依赖为 Python、numpy、pandas，使用统一复现说明中的冻结版本。这里不需要 scipy、sklearn、原图或原生融合状态。

## 2. 精确命令

从各 ZIP 的共同父目录执行。默认只列全部 22 个外折的计划，不创建目录或写文件：

```bash
python work_personnel_typing_A_20261019/reproducibility/reexport_reverse_predictions.py
```

列指定折的计划；`--fold` 可重复：

```bash
python work_personnel_typing_A_20261019/reproducibility/reexport_reverse_predictions.py --fold VLzqgDo317F --fold 2t7WUuJeko7
```

只重导一个折：

```bash
python work_personnel_typing_A_20261019/reproducibility/reexport_reverse_predictions.py --fold VLzqgDo317F --output-dir /tmp/partA-reverse-predictions-one --execute
```

恢复全部被省略的 22 折预测：

```bash
python work_personnel_typing_A_20261019/reproducibility/reexport_reverse_predictions.py --output-dir /tmp/partA-reverse-predictions-all --execute
```

`--source-root <路径>` 可以指定另一处已解压的冻结研究目录。`--output-dir` 必须尚不存在，并与来源树分离；程序拒绝覆盖原结果或已有输出。若中断，部分输出保留在新目录，不自动清场；另选一个新的输出目录重导所需折即可。

输出布局为：

```text
<output-dir>/REEXPORT_PLAN.json
<output-dir>/REEXPORT_RECEIPT.json
<output-dir>/folds/<fold>/predictions.csv.gz
<output-dir>/folds/<fold>/REEXPORT_RECEIPT.json
```

输出列和原文件一致：`event_id, method_id, fold_id, relation, predicted_stability, probability, training_key, source_candidate_id`。候选行的 `source_candidate_id` 为空，别名行保留其冻结来源候选。`event_id + method_id` 为唯一键；两个概率列逐行相同。

## 3. 完整验证与可选原文件比较

每折以 UUID 临时文件写入，关闭并 fsync 后，完整回读 CSV：检查全部事件/方法身份、类内/类间/unknown 关系、训练键、别名来源、概率范围及与冻结计算的数值一致。再完整读取 gzip 到末尾验证 CRC，最后原子改名并 fsync 目录。总体收据再次核对输入 SHA 未改变。

正常重建**不使用**原预测文件。如果另有完整原文件，可加 `--compare-dir <原 results 目录>`，在发布新文件前逐行比较全部身份字段和两列概率；容差固定为 `1e-12`，任何截断或少行都会失败，不接受仅可读前缀：

```bash
python work_personnel_typing_A_20261019/reproducibility/reexport_reverse_predictions.py --fold VLzqgDo317F --output-dir /tmp/partA-reverse-predictions-compare --compare-dir work_personnel_typing_A_20261019/reverse/results --execute
```

精简包已省略原大缓存时，省略 `--compare-dir` 即可；其他完整验证仍照常运行。gzip 头与运行耗时不要求复现原字节，科学身份、关系和概率须一致。

## 4. 本轮实际入口验收

仅重导最小外折 `VLzqgDo317F`，没有重复导出全部 22 折。该折有 **1,916 个事件、69 个方法、132,204 行预测**，对应 1 图/1 个目标楼，含原面板 1,820 事件和新增面板 96 事件。与仍在工作区的完整原预测全文件比较：全部身份、关系、训练键及别名来源逐行相同，两列概率的最大差为 **1.11×10⁻¹⁶**，完整 CSV/CRC 校验通过，所有冻结输入未改变。默认 22 折计划和拒绝覆盖已有输出也已实测。实际结果和输入/代码 SHA 见同目录 `REVERSE_PREDICTION_REEXPORT_CHECK.json`。这份入口检查没有重拟合人员模型或改变已有类别，也不是全部 22 折重新导出的运行记录。
