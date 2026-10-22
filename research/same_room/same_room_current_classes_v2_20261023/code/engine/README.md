# 冻结引擎与几何摘要复现

本目录是本轮执行适配层。冻结仓库提交为 `72a44e80c344975962e1071bd54d894dd86bb4b4`，不修改预处理、参考绑定、正式作答资格、投票、环序或 B8L2/D10 评分。以下命令均在**本成果包根目录**执行。

## 1. 先复算交付中的几何主图和小表

这一步只需要成果包内的578条主预算、一人替换有限摘要，无需重新融合或取得原图。它重建普通 Manual 主层和同支持比较，明确不把这份子表称为全部人数或其它条件结果。

```bash
python -m pip install -r requirements.txt
python code/engine/geometry_question_tables.py --input results/geometry/GEOMETRY_PRIMARY_M1_PANEL_STRATA.csv.gz --output recheck/geometry_main --main-m1-input
python code/engine/plot_geometry_transfer.py --input recheck/geometry_main --output recheck/figures
```

生成 `recheck/geometry_main/GEOMETRY_SUMMARY_BUILDING_EQUAL.csv` 与 `recheck/figures/POSITION_CHANGE_REPETITION.png/.svg`。主图使用同一批269个面板中既存在同构成又存在跨类一人替换的交集。分母、筛选和完整源表哈希见 `results/geometry/GEOMETRY_PACKAGE_SELECTION.json`。

## 2. 从冻结仓库重建全部原生团队和几何

先取得仓库并切换到指定提交。`HOHONET_REPO` 必须是该仓库的绝对路径；适配器不再猜测本机工作区路径。

```bash
export HOHONET_REPO=/absolute/path/to/3D_Manhattan_label
git -C "$HOHONET_REPO" checkout 72a44e80c344975962e1071bd54d894dd86bb4b4
python code/engine/new_team_engine.py --requests design/REQUESTS.json.gz --output recheck/native --jobs 6
python code/engine/summarize_geometry_transfer.py --design design --native recheck/native --output recheck/geometry_full
python code/engine/geometry_question_tables.py --input recheck/geometry_full/PANEL_M_R_GEOMETRY_SUMMARY.csv.gz --output recheck/geometry_full
python code/engine/plot_geometry_transfer.py --input recheck/geometry_full --output recheck/figures_full
```

原生队计算按图保存检查点；重复同一命令会续算。`--jobs` 是本机计算并行数，不是研究中的团队人数。完整设计为141260个唯一精确团队；几何摘要为1954个面板、2140619个精确人员调整。`new_team_engine.py` 输出包括全部标量、几何、节点票数和原始状态。为保持交付精简，这些重建缓存不随成果包再次复制。

如需按图对并行续算几何摘要，可替代串行摘要命令：

```bash
python code/engine/geometry_parallel_resume.py --design design --native recheck/native --output recheck/geometry_full --jobs 4
```

先停止旧的几何摘要进程，再使用同一个输出目录续算。不要同时运行两个写入同目录的摘要进程。`--watch` 可在原生团队还在运行时消费已经保存的端点，最终结果仍保留真实缺失状态。

## 3. 输入、输出与字段

输入是 `design/REQUESTS.json.gz` 中的实际成员请求；`team_key` 使用冻结 canonical key。`design/PANEL_TEAM_LINKS.csv.gz` 连接两个视角的精确团队，`design/PANELS.csv` 保存人数、核心、候选成员、类别、关系和范围状态。

必要仓库文件与哈希位于 `source_index/FROZEN_INPUT_AND_CODE_MANIFEST.json`，原始引擎接口说明位于 `source_index/ENGINE_INTERFACE.md`。主字段合同为根目录 `FIELD_CONTRACT.md`，具体角点对应、分项、时间语义见 `source_index/GEOMETRY_FIELD_CONTRACT.md`。

对应角点距离只在同一图片内比较替换前后，不把不同相机坐标直接对齐。异数、失败、未形成完整几何和模糊对应保持状态，不转成零距离。每视角距离均值使用各自可对应的事件，跨视角距离幅度差及定位状态使用两视角共同可对应的事件。

`source_time_total_seconds` 是继承字段，表示当前图片上的成员活动时间，不是同房源图历史成本。`recorded_time_total_seconds` 只在全部时间已知且记录语义相同时有值；混合语义分别保存在 `record_time_by_kind_json`。

代码仅有一处交付适配：原先依赖工作区目录的仓库位置改为明确要求 `HOHONET_REPO`；没有修改底层算法。未附环境目录、字体、原图全集、全部端点几何或逐队临时缓存。
