# 运行与接入

本包是有限整理，不执行融合、评分、分类、路径生成或 bootstrap。

依赖：Python 3、pandas、numpy。自带10份必要小来源（类别/案例7份、人数独立复算小表3份）；SHA256和原仓库路径保存在各子目录回执中。大端点表、原图和虚拟环境未重复打包。

```bash
python directions/organize_directions.py --out reproduced/directions
python path_notes/extract_existing_path_tables.py --inputs path_notes/inputs --out reproduced/path_notes
```

第一条脚本默认从其所在目录的 `inputs/` 读原字节。两脚本也支持 `--repo /path/to/3D_Manhattan_label`；固定输入提交 `e92abe8631d7f01dc192ee796b46f295ece37a6d`。目录中的回执记录本次实际重组范围。未复算的历史记录表只是记录来源，不通过运行脚本变成验证结果。

类别键：`method, condition, heldout_building, class_id`；人员键：`worker_id`；旧面板保留 `panel_id, pair_key, pool_id`；实例保留 `before_team_key, after_team_key, object_id` 清单及 `reference_id`。拼接类别必须连同留出折，不能只用 M/J 编号。

策略逐建筑键：`condition, layer, policy, subset, difficulty_scope, difficulty, building`；其中 `subset=common` 与 `complete_time`、全部难度与逐难度行是重叠切片。`images` 是支持数，不是每个指标都必然相同的观察数；优先使用 `quality_images, p10_images, joint_qt_images`。

建议仓库位置：`research/same_room/same_room_delivery_clarifications_20261023/`。先复制本目录，再从仓库根运行 `git apply --check research/same_room/same_room_delivery_clarifications_20261023/integration/CONNECT_EXISTING_REPORTS.patch`，核对后应用。补丁只给两个已存在入口增加接续段落，不覆盖旧实验记录，不对遗失的原大块报告伪称已修改。

最终压缩包的内部CSV/gzip通读、字段和关键连接核查见 `ZIP_CONTENT_VALIDATION.json`。该核查只保证当前真实补件的读取和指定连接；不表示未取得原件通过了校验。
