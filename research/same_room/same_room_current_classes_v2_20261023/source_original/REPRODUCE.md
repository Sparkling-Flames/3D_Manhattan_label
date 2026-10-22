# 复现说明

## 先选择要复现的层次

本包提供三层复现，成本不同。

1. **阅读和重新汇总关键结果**：报告、逐组小表、分母、校准与图例都已保存，不需原图或重新融合。
2. **从精确团队标量重做本轮全部标量分析**：四个端点分块加冻结设计即可；只有原答块耗时、重新生成设计等分支额外读取固定仓库输入。逐事件由面板和掩码确定，无需下载数百万重复几何。
3. **从原始合格作答重新融合**：需要固定 GitHub 提交及依赖，运行冻结适配器；原图只在查看/重画机制图时需要，不参与 Q 或融合计算。

本轮原生实算为141,260个不同团队端点，106图，约44.8分钟墙钟时间（本次机器及并行配置）。另对16个已存在端点取 full_state 作案例票账，其中G117为4个；G015的4个端点直接提取已有保存状态。后续分解、替换穷举、模型和预算分析都复用上述端点，不算新的独立团队或新观测。

## 解压与端点拼接

各功能 ZIP 都以 `HOHONET_SRCC_20261023/` 为顶层，解压到同一个父目录。四个端点 CSV gzip 均可单独读取，放到 `results/native/parts/`；它们不是必须用特殊软件连接的压缩卷。若只查看结论，不需要它们。

在成果包根目录运行：

```bash
python code/assemble_native.py
python -m pip install -r requirements.txt
```

拼接按文本行进行，不解析或四舍五入数值；对每个分块及拼接后未压缩CSV核SHA。输出 `results/native/ENDPOINT_SCALARS.csv.gz`，141,260行、50个必要列。源完整标量102列中的重复常数、CPU计时和未用极值已省略，选列账本为 `results/native/SCALAR_SELECTION.json`。不改变正式Q、人员、对象、参考或失败状态。

## 复做精确调整、相同背景与评分分项

以下旧摘要接口按图片池读标量；用小适配器生成临时标量池。它不生成几何，也不会补回失败。

```bash
python code/analysis/materialize_scalar_pools.py --source results/native/ENDPOINT_SCALARS.csv.gz --out rebuild/scalar_native
python code/analysis/analyze_exact_changes.py --design design --native rebuild/scalar_native --out rebuild/exact_changes
python code/analysis/analyze_same_background.py --design design --native rebuild/scalar_native --out rebuild/same_background
python code/analysis/analyze_mechanism_sources.py --design design --native rebuild/scalar_native --out rebuild/mechanism_sources
```

完整实际D大表为可重建中间产物，不随包附带；主预算的精简实际D表已交付。不要同时让两个进程写同一个输出目录。各运行会输出较多有限队统计，汇总只需末尾小表。

单个精确调整可用 `inspect_event.py` 提取。例如先从 `design/PANEL_TEAM_LINKS.csv.gz` 找到要比较的两个 `selected_mask`，然后：

```bash
python code/inspect_event.py --panel SRCC23P_0fccfe57127e06188726 --from-mask 49 --to-mask 56 --out rebuild/one_event.json
```

掩码值须以实际链接表为准；该命令仅提取事件，不作选人。案例中真正的 W104→W120 两个团队已在 `results/taxonomy_response/cases/CASE_G015_SAME_CLASS_W104_W120.csv` 列明。

## 分类构成、换成员、校准与时间

可携带命令见 `results/taxonomy_response/README.md`。该分支需要的17个楼外折、2,108行Manual标签/历史字段已按字符串原样节选，未重新训练或编号；不要求下载整个仓库。

```bash
python code/taxonomy_response/analyze_response.py --labels results/taxonomy_response/inputs/LABELS_AND_HISTORIES_REQUIRED.csv.gz --design design --native results/native --out rebuild/taxonomy_response/results
python code/taxonomy_response/calibrate_response.py --labels results/taxonomy_response/inputs/LABELS_AND_HISTORIES_REQUIRED.csv.gz --design design --responses rebuild/taxonomy_response/results/PAIRED_TEAM_RESPONSES.csv.gz --budget mid_n_rep0 --out rebuild/taxonomy_response/calibration
```

评价目标团队Q时，源正式Q与源有限队库已知。一次源图需要固定核心和候选实际人员的原答及合格参考；枚举多个融合团队增加计算量，不等于新增同样数量的独立人工标注。楼外Q/T画像也有历史建立成本。本轮没有把这些已存在历史当作新部署时免费获得。时间响应可不用源GT，但仍沿用已建立的历史画像。

原答块耗时分支还需冻结快照中与原答一一连接的 `source_time_seconds`：

```bash
export HOHONET_REPO=/absolute/path/to/3D_Manhattan_label
python code/analysis/analyze_block_time.py --repo "$HOHONET_REPO" --design design --native rebuild/scalar_native --out rebuild/time_transfer
```

相同语义才能比较；两视角都保持不变的背景可抵消。它与完整队旧profile-index时间连接有不同缺失支持，两种结果分开保存。

## 预算、失败、低尾与案例

```bash
python code/budget_effects/analyze_budget.py --require-complete --out rebuild/budget_intermediate
python code/budget_effects/compact_budget.py --source rebuild/budget_intermediate --out rebuild/budget
```

这条可携带路径已从交付自身90,139个所需端点完整重跑，45,400条预算连接齐全；与原汇总最大数值差约2.28×10⁻¹³，凭据在 `results/budget/PORTABLE_REPRODUCTION_RECEIPT.json`。没有为交付重新融合。

几何主图可直接用578行主预算一人调整摘要重画；详细命令见 `code/engine/README.md`。原图机制图使用 `HOHONET_PHOTOS` 指向按Release成员取回的少量PNG，`HOHONET_FONT` 指向本地中文字体。保存的完整案例状态足以重画已交付原答、参考、融合和BEV；不需重放全库。逐图输入与几何定位见 `CASE_INDEX.csv`、`cases/mechanisms/MECHANISM_INPUT_INDEX.csv` 和 `cases/budget/G117_LOW_HIGH_INPUT_INDEX.csv`。

## 从冻结仓库重新生成全部原生团队

```bash
git clone https://github.com/Sparkling-Flames/3D_Manhattan_label.git
git -C 3D_Manhattan_label checkout 72a44e80c344975962e1071bd54d894dd86bb4b4
export HOHONET_REPO=/absolute/path/to/3D_Manhattan_label
python code/engine/new_team_engine.py --requests design/REQUESTS.json.gz --output rebuild/native --jobs 6
```

`--jobs` 是计算并行数，不是团队人数。默认保存最终几何与支持票，少量机制重放用 `Engine(full_state=True)`。预处理、参考绑定、资格、环序、MV50、B8L2/D10全部来自固定仓库；实际输入与代码哈希见 `source_index/FROZEN_INPUT_AND_CODE_MANIFEST.json`。全部几何摘要、距离与失败分支的重算命令见 `code/engine/README.md`。

原图Release：
https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015

只需索引中的少量成员，可按仓库 `research/workers/personnel_interchangeability_20261020/analysis/visual_sources/range_zip.py` 读取。本包给出已查看图片的ZIP成员、CRC/哈希及定位，不复制原图全集。

## 上一轮材料的复现身份

`prior/adopted/` 是本轮从固定main取回的原文件字节副本，`prior/dot_independent/` 保持Dot独立来源。旧47.1MiB ZIP仍未找回；当前main已经省略的全队/逐历史缓存也未从文字伪造。若需重生成那些旧中间表，使用固定仓库内上一轮 `pro/INPUT_INDEX.csv`、`pro/REPRODUCE.md` 及其代码；本轮没有声称重跑上一轮全部模型和在线停止。

## 最小依赖与运行范围

运行环境为Python3.12。`requirements.txt` 记录本轮实际版本；普通分析主要需要numpy/pandas/scipy，模型需要scikit-learn，融合几何需要shapely，作图需要matplotlib/Pillow。Markdown仅用于把报告渲染成HTML，不参与研究计算。字体、虚拟环境和库二进制不随包附带。

本包没有外部发布、修改GT、恢复筛除资格、重训类别或调用付费标注。重复运行只写到指定重建目录；原始输入不变。
