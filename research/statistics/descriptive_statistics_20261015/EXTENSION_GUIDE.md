# 新批次与质量版本的最小接入口

本次用户已授权复核及关键数据可视化。原 `descriptive_statistics_20261015.py` 保留3152／1145／931／836历史快照复现断言；新增入口只接入已审核的归一化输入，不改变采集、清洗、资格、质量公式或人工确认结果。

## 运行

在仓库根目录执行；JSON内CSV路径相对manifest所在目录：

```powershell
python -m tools.thesis_main.analysis.descriptive_snapshot_inputs_20261015 --manifest research/descriptive_statistics_20261015/SNAPSHOT_INPUTS.json --out research/descriptive_statistics_extension_20261015
```

输出目录必须为空或不存在。后续运行请另取目录名，已有快照拒绝覆盖。`INPUT_MANIFEST.json`保存本次原始配置；`SOURCE_LOCATIONS.json`另记原manifest位置及各源CSV解析后的绝对路径，避免把归档配置中的相对路径误解为输出目录。迁移快照时需同时保留源CSV及配置原位置或重新登记路径。

## 新人、新图与新批次

新人和新数据须先经现有正式loader及必要审核，再形成归一化`records_csv`、`images_csv`。在`batches`追加`batch_id,input_version,reference_version`及这两个CSV路径即可；没有固定人数、图片数或批次数。输入版本表示兼容的已审核几何／预处理快照，参考版本由已审核批次显式声明，均不是随意标签。算法自报参考版本不能代替批次的审核声明。

记录必需列：`object_id,image_id,worker_id,condition,reference_id,use_panel,active_time_seconds,time_status,time_source,time_source_file,time_rule_version`；图片必需列为`image_id`，接入脚本`IMAGE_AXES`列明的稳定图轴（难度／目标／场景／门洞／OOS／可标性等）。`all_answer_count,joint_quality_count`等历史覆盖计数不当作图轴；不阻止同图新增人员，覆盖另由当前记录重算。原记录中的历史计数字段可以保留追溯，但不作新快照分母。ID必须稳定非空，`reference_id`可以空（尚未绑定），但有分数时不能空。`use_panel`保留原用途层，不在入口推导正式准入。全次运行中对象ID不得重复；同图的稳定轴有冲突即停止，版本冲突也不得静默覆盖。人员ID不自动重编号；建筑、同房及可标性不从ID或难度推断。

有效时间只接收`time_status=usable`且来源、来源文件、规则版本非空，数值有限且大于0的`active_time_seconds`；来源标为`lead_time`回退的记录拒绝作为有效时间。其余状态必须保留空有效时间。`raw_active_time_seconds`等历史字段可原样保留，不由本入口转换、重估或用`lead_time`代替。新增时间来源的归一化和同房关系仍需各自审核升级。

## 新算法或新质量版本

在`algorithms`追加`algorithm_id,version,source_csv,value_column,input_version,reference_version,direction,minimum,maximum`。CSV必须含完整`object_id,image_id,worker_id,condition,reference_id`身份列及值列；如提供`input_version`或`reference_version`列，每行必须与注册项一致。每项仅消费其声明的输入及参考版本组合，允许部分行覆盖及空分数，不补0。数值必须有限且落在登记范围内。所有有分数的对象必须已在对应批次明确绑定同一参考；对象、人员、图片、条件、参考或版本不一致即停止。

同一次运行不合并同一对象的多个输入／参考修订。新参考或改几何应先完成独立审核，形成新的归一化快照，另起运行目录。版本字符串只是来源声明，不能认证几何、参考范围或算法语义正确，也不会自动赋予资格。本入口不实现参考管理、新评分或任意未来数据的全链路接入。

当前A10/B8L2版本分别沿用配置中明确声明的`WQ-A10-20261015`／`WQ-B8L2-20261015`，与原字段合同及图表指标映射一致，来源为`quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv`中的`Q_A10/Q_B8L2`，不是沿用原WQ的`score_version`。原WQ保留其自身版本；IoU3D100为现用均高棱柱口径，不是任意实体精确IoU。当前示例均为0–100、越高越好；同范围不表示不同公式具有同一语义。

## 输出字段与分母

- `snapshot_inputs.csv`：每对象一行，保留输入字段、`batch_id,input_version,reference_version,records_source_csv,images_source_csv`。不覆盖源数据。
- `score_measurements.csv`：每算法×其声明输入版本的每对象一行；保留完整身份、用途、批次、算法独立版本、参考版本、源CSV及值列。`measurement_status`区分`valid,empty_value,absent_row`，`source_row_present`区分空值与未提供行。
- `algorithm_coverage.csv`：按算法／版本／输入／参考版本，分别展示全输入、逐`use_panel`及已绑定参考分母；含有效、缺失、来源行数、人员和图片覆盖，以及`n_target_limited`（用途不为`ordinary_same_target_conditional`，仅表示不能纳入该普通同目标层，绝非所有分数无效）、未绑定参考数。全输入3152中的2007无完整评分对象不能称为2007次算法失败。
- `algorithm_common_comparisons.csv`：同输入版本、参考版本及用途层内，按对象／图／人／条件／参考ID连接；差值为右算法减左算法，只在共同非缺失集合计算均值、中位数及分散，另报两侧覆盖和不完整配对数。不同输入或参考版本不配对。小样本仍列出样本量，不自动形成优劣、能力或显著性结论。

原统计报告、33页工作簿及原始标注不由这个入口重写。实际当前基线运行输出见[扩展快照目录](../descriptive_statistics_extension_20261015/)；本入口测试用小数据实际覆盖新批次、新人、新图、第三算法部分覆盖、身份／版本／参考冲突及拒绝覆盖。

IoU原合同没有独立算法版本号，示例中的`mean_height_prism_artifact_snapshot_20261015`仅为本地已有结果工件的快照标识，不冒称上游正式算法版本。
