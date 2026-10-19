# 打包与重建范围

`PACKAGING_MANIFEST.json` 是本目录交付清单，`FINAL_VALIDATION.json` 在新进程中对所有要交付的gzip读到流末尾、验证CRC、解析真实CSV行数/JSON条目，并重新核对完整预测的逐图统计。

## 必须保留

- 本目录根部代码、设计JSON、运行收据、方法审查、完整逐成员/逐簇/逐图表和中文报告。
- `CLUSTER_API.json.gz`、`pair_distances.csv.gz`、`ORACLE_REQUESTS.json.gz`，供根展示页和融合重算使用。
- `fusion_analysis/`、`forward_swaps/`、`conditional_dtype/`、`transfer/`、`prefix_analysis/`、`room_sensitivity/`、`pair_history_diagnostic/` 的最终表及注册/收据。
- `swap_transfer/heldout_predictions_wide.csv.gz`、`WIDE_PREDICTIONS_RECEIPT.json`、各汇总表、折覆盖和修复核对收据。
- `historical_v1_reference/` 中4.1MB的本地历史候选归属及来源说明，用于固定v1核对；此文件不是缺失的v2 Pro返回ZIP。
- 失败及恢复日志保留，避免把运行问题写成一次顺利完成。临时半成品本体可省略。

## 可省略的重复中间件

- `checkpoints/`：重复冻结坐标、距离和分区的恢复缓存，可从输入和代码重建。
- `fusion_analysis_pilot/`、`swap_transfer_pilot/`：接口试跑，正式结论已全部用全量重跑；保留相应运行日志即可。
- `__pycache__/`、所有`.tmp*`。
- `swap_transfer/<building>_predictions.csv.gz` 的22个长表：其6370576行的全部实际值和模型预测已无损转为270370个实际换人事件的一行宽表，逐float64回读差为0。原长表共约248MB，宽表约46MB。

省略长表时，重建入口为：

```bash
python work_v2_20261019/clusters/compact_swap_predictions.py \
  --expand-to work_v2_20261019/clusters/swap_transfer
```

重建保留每次事件、模型、目标、实际值、预测值、历史/oracle标记；平方误差和绝对误差从实际值与预测值直接计算。CSV行顺序或gzip时间戳不作为科学等价条件。

## 兄弟输入与主仓库

不能仅打包本目录并宣称能从零重放。准确输入在清单的 `required_sibling_inputs`：主要是人员逐份/全体/楼外/双排除画像、原声明组表与helper，融合冻结输入快照、完整INITIAL替换、最终构成/前缀/团队输出。主仓库保留 main固定提交中的几何/分簇/融合代码以及审计证据。

运行依赖记录在`ENVIRONMENT.json`和`requirements.txt`。重新采集或重做全部人工审核不是这些统计复放入口的功能。

