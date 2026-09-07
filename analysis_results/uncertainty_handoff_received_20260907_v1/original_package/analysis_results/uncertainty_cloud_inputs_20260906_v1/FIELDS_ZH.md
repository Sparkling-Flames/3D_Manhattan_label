# 字段与数据关系

本包版本为 `uncertainty_cloud_inputs_20260906_v1`，属于回顾性研究输入，不修改正式协议。完整字段目录见 `FIELD_INDEX.csv`；上游事实字段原字典在 `facts/DATA_DICTIONARY.csv.gz`。旧字段名称与值保留，不借清理之名改变其含义。

## 身份与版本

| 字段/表 | 含义及空白规则 |
|---|---|
| `images.image_id` | 380张图的唯一身份；`population_role`区分214历史图与166无历史响应候选 |
| `annotations.canonical_annotation_id` | 2501条选定响应的唯一ID，字符串；不能解析成数值或丢弃前导字符 |
| `context_key` | `stage|block_index|base_task_id|raw_condition`；不是历史所有分析包共用的旧task ID |
| `current20_member` | 用户确认的当前人员名单标记；不是质量标签或历史准入规则 |
| `raw_annotation_version_id` | 2513条原始版本身份，连接`raw_annotation_versions.jsonl`；是否独立看原谱系字段 |
| `selected_canonical_version` | 当前身份底座是否选用该版本，不表示最后一次提交必然正确 |
| `related_canonical_annotation_id` | raw-only旧分簇成员所在版本组的当前选定响应，只能追溯，不能代替该成员的坐标 |
| `room_instance_id` | 未获得可靠实体房间映射，全部留空；`region_class_values_json`是已有类别集合 |

JSONL中的 `points_1024x512` 保留原点序，`raw_keypoint_results` 保留原始百分比关键点记录。模型另有 `raw_file_text` 和Bi的 `floor_uv_text`。源文本的UV和像素不能混用；顶部/底部点对不能未经检查按x重新排序。规范化和修复后的几何仍只在各自variant中使用。

## 模型与参考

- `layout_id`由图像、模型、输出头和来源角色组成。380份HoHoNet ep300回放与166份候选预筛旧输出是不同角色；Bi两头共用同一个模型身份。
- `models/layouts.jsonl`共1306条，仅放模型。`references.jsonl`共603条放参考变体，其中候选原始标签也保留其原始文本。所有参考带独立来源，不自动选择距人最近者作为GT。
- `parse_status=ordered_pairs_parseable_not_manhattan_certified`只检查有限坐标、范围、偶数点及相邻垂直点对等条件；不承诺闭合、Manhattan或当前房间范围正确。`declared_is_polygon`和`manifest_status`是原模型导出的独立声明。
- `raw_sequence_equal`：按原顺序的坐标完全相同；`ordered_cycle_equal`：允许点对环起点和环向改变后的完全相同，不改变点对内部顺序，不对布局做旋转、拉伸或拟合。
- 当几何退化不可比较时，两种相等性字段留空，`comparison_status=not_evaluable`；不能把空数组相等当成有效布局一致。
- `legacy_linear_gap`是已归档的周期线性墙面带1−IoU；候选图没有这份历史度量时留空。本轮不填补新值。`legacy_linear_gap_zero`与原始坐标相等性分别保存。
- `source_path`、checkpoint路径、上游CSV里的路径是可追溯文字，不由云端默认打开。云端实际布局坐标均在包内；图片访问只使用`images.image_url`。

## 分簇与旧代表标注

`clusters/partitions.csv.gz`的 `version` 必须参与连接。`extended73` 与 `historical42` 同图也不能覆盖或合并；分区中的簇rank只是原排序，支持数并列时没有唯一的大小次序语义。

- `min_boundary_similarity`和`min_wallwall_similarity`分别为原0.95条件，还需点对应兼容性；不是线性mask差≤0.05的另一种拼写。
- `partition_status`、`structure_status`、`reported_support`及`original_row_json`保留原定义。若原分析不可评估，可保留已有计算分区，但不能改称有效多模态。
- `memberships.mapping_status=matched`时，`canonical_annotation_id`可以连接工作响应。`raw_version_only`须读取 `raw_annotation_version_id` 指定的原版本；两者不能使用同一合并规则。
- `cluster_support`按该版本实际簇成员计数；`top_support_tie`及`second_support_tie`记录并列；空`semantic_label`表示尚未解释为enclosed、extended或其他语义。
- 115份主工作分区的原表未保存代表标注身份，因此没有新选medoid。旧213单元的实际代表身份在独立档案及 `legacy_representative_links.csv` 中；只能配合那一版分区使用。
- 代表标注状态 `not_saved` 是原字段空白，`source_not_identifiable` 是原表明确不可识别，均不同于数据连接程序失败。

## 连接、时间和审核

`response_links.csv.gz`的JSON数组分别列出分区、模型布局、参考及实际初始化ID；空数组表示对应源未提供关联，不表示没有分歧。候选图没有真人响应，因此不出现在此表。

`metric_identity_links.csv.gz`逐行对应 `archive/legacy_geometry_comparisons.csv.gz`，`source_row`是含表头的CSV记录序号。两侧均为真人时，根据恢复的完整context判断 `same_context`／`different_context`；不能只按stage汇总。其余为 `not_two_human_responses`。它只修复连接视图，不重算或重命名旧距离。

`facts/active_time_context.csv.gz`、session和event资料单独保存。`active_time_seconds`、`lead_time_seconds`与事件片段不互填；字段存在不代表连续工作或休息已被可靠识别。本包不生成疲劳、分心或行为状态。

`archive/human30.json`是原人工回答，空白判断保留空白；`archive/ai50.json`只是AI建议。不能把原人工的scope判断推广为对所有模型或所有参考都认可。两类审核的图片身份借已有选择清单连接，候选资料不能虚构真人响应。

## 缺失、单位与验证

- CSV布尔值可能继承上游 `true/false` 或生成器 `True/False`，应显式按字符串解析；不要用Python的 `bool('False')`。
- 所有缺失、结构不适用、不可计算、未审核状态保留原值，不统一补0。历史异常状态不是新研究的自动剔除名单。
- `SOURCE_CATALOG.csv`区分压缩但内容不变的源快照与事件字段投影；`FIELD_INDEX.csv`列字段位置，不把旧上游模糊说明升级成规范。
- 关键点提取只使用仓库既有导出解析，核对容差1e−8像素用于数值一致性，不是歧义阈值。重复版本、跨block同名任务、分区并列、模型退化、房间身份和人机判断边界均有检查。
