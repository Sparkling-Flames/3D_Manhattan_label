# Part A 反向人员类别发现

先读 [`REPORT_ZH.md`](REPORT_ZH.md)。本目录实际从训练建筑的历史几何/共簇及真实替换关系发现人员分区，并输出 Q/T/难度/行为解释。它不是 QT 标签预测共簇，也不只是人员相容表。

## 冻结范围

- 数据为 GitHub main `dafa73ac7d8ada9a7f5c0e483d695adcbd916550` 对应 v2，普通 Manual 5719 份/177 图/22 楼/60 人。
- 64 候选：4 种人员关系×2 种人员级 linkage×4 个 K×全局/基础加难度。全部候选与内层选择记录保留。
- FULL 是描述拟合；外层 22 楼逐楼留出，所有内层关系与规则重新使用对应训练楼。
- 仅 `Pro_exact_fixed_background_v1` 可用于关系拟合、内层选择、校准；`A_nested_even_v1` 只评价，不学习。
- 注册、分折、共享选择器及解释规则见 `REGISTRATION.json`、`FROZEN_BUILDING_SPLITS.json`、`selection_common.py`、`EXPLANATION_REGISTRATION.json`。`DESIGN_FREEZE_SHA256.json` 保留冻结哈希。

## 结果入口

| 内容 | 文件 |
|---|---|
| 60 人 FULL 主/替换/简单/中等/困难候选及边界 | `results/FULL_PERSONNEL_TYPES.csv` |
| 64 候选及 5 选择 alias 的逐折成员 | `results/all_candidate_classes.csv.gz` |
| 每外折具体选择的候选 | `results/selected_candidates.csv`、`results/SELECTOR_COUNTS.csv` |
| 每候选内层建筑误差及 1SE 过程 | `results/all_candidate_selection.csv.gz`、`results/all_inner_building_scores.csv.gz` |
| 各内层训练名单 | `results/folds/<fold>/inner_classes.csv.gz` |
| 全人员对的几何/替换率、共同图/楼、先验和支持 | `results/all_pair_relations.csv.gz` |
| 整类人数、所有支持对与坏尾 | `results/all_class_diagnostics.csv.gz` |
| 跨折共类关系、逐人类友变化 | `results/coassignment_stability.csv.gz`、`results/worker_classmate_stability.csv` |
| 类整体成员关系稳定性 | `results/FULL_CLASS_MEMBERSHIP_STABILITY.csv` |
| 最弱支持对索引（不是只抽这些对计算） | `results/selected_class_worst_training_pairs.csv.gz` |
| 64 候选＋5 alias 的每事件预测 | `results/folds/<building>/predictions.csv.gz`、`results/PREDICTION_MANIFEST.json` |
| 冻结训练校准概率 | `results/all_calibration.csv.gz` |
| 规则类别、覆盖、逐人留一、类画像 | `explanations/rule_classes.csv.gz`、`explanation_coverage.csv`、`leave_one_worker_out_rule_predictions.csv.gz`、`class_feature_profiles.csv.gz` |
| 规则正文与分裂特征记录 | `explanations/rules.txt`、`RULE_FEATURE_USAGE.csv` |
| 原请求/新请求的真实成员、背景、参考、结果 | `../events/common_events.csv.gz`，通过 `event_id` 连接 |
| 逐事件全部团队几何/失败 | 由 `../events/FIELD_CONTRACT.json` 指向精确 requests 和 native states |

逐折类别键是 `method_id, fold_id, domain, worker_id`；`domain` 为 global 或 easy/medium/hard。`class_id=unknown` 必须保持未知。数字类号只在该拟合上下文有效，跨折稳定性使用共类关系/类友集合。

事件预测键是 `event_id, method_id`；字段 `probability` 与 `predicted_stability` 相同。`relation` 为 within/between/unknown；未知使用训练 k×难度基线，并未删除事件。`source_candidate_id` 说明 selector alias 来自哪个真实候选。

`reverse_selected`、`reverse_selected_global`、`reverse_selected_geometry` 在本次 22 外折恰好选择相同候选，不能算三条独立正证据。`reverse_selected_swap`、`reverse_selected_difficulty` 为事先保留的受限 selector。FULL 类号不得用于目标楼验证；应连接对应留出楼的历史名单。

## 复现

在 `work_personnel_typing_A_20261019` 根目录执行。输入由 main 紧凑归档 bootstrap 恢复到 `recovered/work_v2_20261019`；本程序默认读取该原布局。

```bash
python reverse/safe_replay.py --program discover --fast --stage geometry
python reverse/safe_replay.py --program discover --fast --stage discover --events events/common_events.csv.gz
python reverse/safe_replay.py --program discover --stage consolidate
python reverse/safe_replay.py --program explain
python reverse/safe_replay.py --program diagnostics
python reverse/make_exchange_summaries.py
python reverse/verify_final_outputs.py
```

`safe_replay.py` 只更改导出方式。它将路径型 CSV 写到 UUID 临时文件，关闭并 fsync，完整读回列数/行数及 gzip footer/CRC，然后 rename 发布。`--fast` 使用已与原始 `selection_common.py` 全候选核对的等价 NumPy 汇总；不加 `--fast` 可直接运行冻结原算法。

指定 `--folds FULL,2t7WUuJeko7` 可做小范围重放。只要存在 `COMPLETE.json`，原核心默认复用完成折。**若从紧凑交付省略了大预测缓存，但保留了 COMPLETE 元数据，须用 `--force` 重建对应折**，或者将 `--output` 指向新的空目录。大预测缓存可由同一份精确事件、冻结输入及这些确定性步骤重建，不需要重新采集或重新审核。新输出目录的 consolidate 使用同一 `--output`；解释可通过 `--classes` 和 `--output` 指向该新目录。

全量三进程科学计算有原实现和经核对加速实现的真实运行日志。此次受 8 GiB 共享内存约束，预测按折保存，不把 19779954 行再次拼成一个巨型表。重放时不建议同时启动多个全宽 CSV 分析任务。

## 运行证据与限制

- `PROBE_BOOTSTRAP_PARITY.json`：main 探针与恢复局部测量的字节/解压内容一致；不代表重新实施了人工预处理。
- `FAST_SELECTION_PARITY.json`：FULL＋1 外楼的全部 64 候选、3 内组，概率/建筑 Brier 和 1SE 选择校核。
- `TRAINING_ISOLATION_RECEIPT.json`：外楼、内层验证楼和评价专用背景污染不改变训练结果。初次负控构造改变了整列 bool dtype，不能代表“只改变测试行”；保留 dtype 后重做，科学核心未改。初次日志 `isolation_dtype_probe_failure.log` 保留。
- `FORWARD_SUPPORT_PARITY.json`：正反向 23 折人员支持 1380 行一致。
- `PREDICTION_INITIAL_CRC_AUDIT.json`、`ALL_NONPREDICTION_GZIP_INITIAL_AUDIT.json` 记录初次导出发现的截断。两预测与两聚合表从冻结完整源重建；原可读前缀与重建结果核对。没有重新选择类别，也不推断底层截断根因。
- `PREDICTION_OUTPUT_INTEGRITY.json`、`AGGREGATE_EXPORT_REPAIR_RECEIPT.json`、`safe_io_receipts/` 和 `FINAL_OUTPUT_INTEGRITY.json` 给出重建、最终 SHA/CRC/关键键和行数。

本目录不更改融合、正式评分、参考、难度、排除裁定和 main。历史个体严重错误仅作有审核覆盖的事实台账，不造总体错误率；Semi 旧确认与新报告机会分开；scope 有限相容 gold 不被扩成总体 scope 准确率。缺原图不影响冻结几何计算，也没有据此宣称视觉审查。

Part B 仍应独立核验组队机制和外楼结论。本目录的正反例与不足不能被自动升级成正式人员类别。
