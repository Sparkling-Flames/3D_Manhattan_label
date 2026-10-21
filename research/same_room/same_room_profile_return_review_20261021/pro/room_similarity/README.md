# 平均质量相似性分支：最小复现

完整中文结论见 `REPORT_ZH.md`；全部有支持的原房间组见 `GROUP_ATLAS_ZH.md`。数据版本与采用状态在 `INPUTS_AND_RECEIPT.json`、`MEAN_PREDICTION_RECEIPT.json`。

## 运行

Python 3.10+，依赖 NumPy、pandas、SciPy、Matplotlib。分析只读取固定 main 的原输入，不下载原图、不运行融合、不修改参考或仓库数据。

```bash
python code/run_similarity.py --repo /path/to/3D_Manhattan_label --out /path/to/room_similarity
python code/run_direct_mean.py --repo /path/to/3D_Manhattan_label --out /path/to/room_similarity
python code/run_mean_prediction.py --repo /path/to/3D_Manhattan_label --out /path/to/room_similarity
python code/make_figures.py --out /path/to/room_similarity --font /path/to/NotoSansCJKsc-Regular.otf
```

图表中文字体只影响显示。使用 Noto Sans CJK SC 或其它完整中文字库；字体不作为本包重复输入保存。数值计算不依赖字体。

要求 repo 提交为 `561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9`，并保留这些原路径：

|输入|作用|
|---|---|
|`research/statistics/v2_evidence_audit_20261019/records.json.gz`|逐份对象、资格、Q、参考、图像条件|
|`research/same_room/relation_adoption_20261016/relations.json`|既有直接关系，不做闭包|
|同目录 `original_groups.json`、`candidate_adoption.json`|原声明组和范围子集|
|`research/workers/worker_b8l2_d10_20261017/admission_snapshot.json`|沿用历史训练准入|
|`research/same_room/same_room_multiview_20261020/GROUPS.json`|冻结多数历史组集合|
|`research/same_room/same_room_v2_prediction_20261019/pair_descriptive.csv`|旧值对齐凭据，不替代本轮重算|

`code/common.py` 只做读取、扁平化与冻结资格选择；`run_similarity.py` 生成逐对／逐组／未知背景；`run_direct_mean.py` 在全部支持图对（含两视角组）上评价单源用途；`run_mean_prediction.py` 枚举单源及全部严格多数历史并拟合楼外校准；`make_figures.py` 生成三幅图和可读组表。

## 交付内容

关键小表：`pair_summary.csv`、`declared_group_similarity.csv`、`declared_group_views.csv`、`matched_unknown_summary.csv`、`matched_control_support_bridge.csv`、`mean_holdout_summary.csv`、`mean_holdout_groups.csv`。

精确复算支持：`direct_pair_similarity.csv`、`matched_unknown_candidates.csv.gz`、`mean_feature_index.csv.gz`、`mean_prediction_values.csv.gz`、`mean_calibration_folds.csv`。宽表列保存每种方法的准确预测值，避免每种方法重复打包相同对象／历史字符串。`formal_record_index.csv.gz` 是压缩后的轻量字段索引，不含重复原图或完整几何。

原图及几何案例由综合成果包连接 G130/G202 原图、原答和参考；本分支没有伪称从原图独立确认墙角语义。
