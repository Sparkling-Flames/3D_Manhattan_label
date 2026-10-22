# 实际不变背景D比较：精简主预算重建

交付身份：**损坏的大导出未随包提供；本轮从保存端点重建精简主预算表**（`corrupted-large-export omitted / reconstructed compact primary`）。

原 `ACTUAL_BACKGROUND_COMPARISONS.csv.gz` 解压读取报 `invalid code lengths`。本次没有使用或修补该损坏流，也没有重新融合或评分；原1954面板的摘要、组/楼结果与完成记录仍保留原件身份。重建直接读取冻结design及已经保存的原生端点标量，沿用 `analyze_same_background.py` 的完整D、实际n/m、同类块与纯跨类块比较及层级计权。

## 已恢复的实际支持

- 普通 Manual，replicate 0，中间人数 `n=max(3,k,min(N−k,floor(N/2)))`。
- 309个已登记主面板全部进入枚举；其中269个有同一个实际D下的同类与跨类比较。
- 使用22610个唯一已保存端点；输出17668行背景分层，实际m为1或2。更大的m没有符合原定义的同类比较时不补造。
- 保留 B8L2、D10、有效转折数、完整状态及各自四端有效分母。没有把失败填成0。
- 与原主摘要4行（m1/m2×两个方向）的50项字段比较，最大绝对差为1.7763568394002505e−15。新gzip以单一原子流写出并已完整回读。

## 文件与连接

`PRIMARY_ACTUAL_BACKGROUND_COMPARISONS.csv.gz` 的一行固定 `panel_id + shared_mask + m + direction`，另有稳定 `background_key`。

- `actual_core`是实际全部不变人员D，包含固定核心和两队相同的候选成员，长度为n−m。
- `same_mask_pairs_json`保存所有同类比较的 `[mask_from, mask_to]`；只用于绝对变化时，其方向是规范枚举顺序。
- `cross_mask_pairs_json`保存全部纯跨类比较，顺序已按该行 `direction` 排列，因此与 `cross_signed_*` 的符号一致。
- 每个mask通过 `design/PANEL_TEAM_LINKS.csv.gz` 的 `panel_id + selected_mask` 连接两张图片各自的规范 `team_key`；再接端点标量、人员、原答object_id和参考。
- `shared_mask`只编码共享候选，不能单独当作完整D；完整D以`actual_core`为准。
- 图像、pool、参考、类别方法和方向元数据保留。`*_0/1`分别对应面板的a/b视角。

`PRIMARY_SAME_BACKGROUND_SUMMARY.csv`为重建主摘要；`PRIMARY_SUMMARY_RECONSTRUCTION_CHECK.csv`逐字段保存与原摘要的差值；`PRIMARY_RECONSTRUCTION_RECEIPT.json`记录输入与输出哈希、重建身份、支持及未读取的损坏大导出身份。

## 用交付文件复现

以下从成果包根目录执行，仅需要已附端点标量，不需要原图、全部几何或重新运行融合：

```bash
python code/analysis/rebuild_primary_actual_background.py --design design --scalars results/native/ENDPOINT_SCALARS.csv.gz --out recheck/same_background_primary --reference-summary results/same_background/SAME_BACKGROUND_SUMMARY.csv
```

`--corrupted-export`只是本轮保存旧损坏文件身份的可选参数，复现时不需要该文件。此次未声称恢复全部人数和其它条件的逐D大表；这些条件的既有分组摘要继续保留，必要时可从冻结design和端点用完整原代码重新生成。
