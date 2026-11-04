# 当前类别的真实原答案例

本组已经把 **DSTRUCT K3、RFUSE K2、JOINT K3/K4 的当前留楼外类别**接到实际完整标注：4 张原图、92 个按预定规则选择的典型展示位，加 1 个近共线释义附例，共 **39 个独立原答对象**。图中可同时核对结构、位置、上下边界、已有 Q 分项和同源劳动时间。它们使类别的含义可以在原图上查看，不承担全库效应估计；总体差异由同图、建筑汇总表回答。

直接打开 [index.html](index.html) 即可离线查看。切换图片与体系后，各类至多显示 2 个工人；K4 C3 在每张图上可用 1 人并全部展示；点击完整全景可放大，并可开关参考、点号及结构标记。原图、数据和脚本均在本目录，无 HTTP 服务或外部字体依赖。

第 10 批新增 [JOINT K4 原图直达](index.html#method=OPPJOINT_K4)与 [K4 补充报告](JOINT_K4_SUPPLEMENT.html)：4 幅完整同图板、28 个展示位和对应个人分项，原三种分区的 64 个典型位及近共线附例保持。

## 一、这些具体实例说明了什么

以下数值均来自 [SELECTED_RECORDS.csv](SELECTED_RECORDS.csv)，Q 为已有 `B8L2`，T 为登记的 `source_active_time_seconds`。同一对象在不同体系重复展示时没有成为新的独立观测。

### 1. 简单图：类别区别不要求每张图都表现为不同点数

`jtcxE69GiFV-10` 的采用参考有 4 个转折、0 条短墙，三种体系的全部典型实例也都是 4 对点、4 个转折。完整环序和上下点均保留，位置与质量分项仍有差异。例如 DSTRUCT C1 的 W125 与 W127 都是四角表达，Q 分别为 **85.96、98.02**，T 分别为 **206.747、89.665 秒**；C3 的 W122 与 W126 的 Q 为 **99.46、99.64**，T 为 **111.260、59.402 秒**。这些是具体对象的差异，不是六人样本对总体类别的估计。

### 2. 中等图：同样四角表达，也有类内质量和时间跨度

`jtcxE69GiFV-09` 的参考同样是 4 个转折。DSTRUCT C3 两个典型原答的 Q 为 **63.20、88.98**，T 为 **97.332、378.920 秒**；C2 两例为 **83.41、92.73**，T 为 **500.864、72.594 秒**。因此，当前结构类编号不应被直接换成每图固定的“高、中、低质量”标签。该图可以具体解释为何同样的结构数量还需接着查看几何位置与分项：W126 的 `dir=6.109`，而 W127 的 `dir=0.822`，两人仍都是 4 对点。

### 3. 困难图：结构保留的类别含义变得直观

`jtcxE69GiFV-26` 的参考有 **8 个转折、3 条短墙**。DSTRUCT C3 / JOINT K3 C3 与 RFUSE C2 的两位典型实例恰好是 W112、W115，两人都保留 **8 个转折、3 条短墙**。DSTRUCT C1、C2 的典型实例则是 **5–6 个转折、0–1 条短墙**。底面图及黄色短墙把这个区别落在了具体位置上。

结构表达与评分是两个相连但不等同的观察量：保留 6 个转折的 W125 的 Q 为 **73.51**；保留 8 个转折的 W112、W115 分别为 **61.80、68.45**。相应方向、边界、高度分项均已披露，不用节点数代替 Q。W112 与 W115 的 T 分别为 **3559.413、1018.229 秒**，说明相同结构类别内仍有劳动差异。该对照不会推翻结构类别；它使“结构保留”“位置精度”和“劳动”可以分别解释。

### 4. 跨建筑附页：结构数量相同以后，还要看位置和上下边界

`yqstnuAEVhm-01` 的参考有 **8 个转折、2 条短墙**。按同一覆盖规则选出的 DSTRUCT C1 两例均是 4 个转折；C2、C3 两例均是 8 个转折、2 条短墙。C2 的 W108、W123 的 Q 为 **70.89、67.26**，C3 的 W130、W115 为 **97.75、94.38**。即使计数相同，边界和方向分项也不同：W108 / W130 的 `S_bottom_deg` 分别为 **0.458° / 0.139°**，`dir` 为 **4.760 / 0.825**。这一页展示了第二个建筑中的具体表达；不同建筑的类别按各自模型折训练中心解释。

### 5. 近共线附例：6 对点可以只有 5 个有效转折

原规则选出的 64 个展示位的近共线计数均为 0，不能为讲述该特征而把主图偷偷换样。本组另按“近共线特征存在、再最接近本类几何中位数”的规则选择困难图 W114，独立标为释义附例。W114 有 **6 对点、5 个转折、1 个近共线点**；同图、同为 DSTRUCT C2 的既有典型 W116 有 **6 对点、6 个转折、0 个近共线点**。粉色圈显示具体节点，这说明“有多少对点”和“保留多少转折”应分开统计。两例原答均完整保留，未删掉近共线点。

## 二、选择规则与统计角色

详细冻结规则见 [SELECTION_RULE.md](SELECTION_RULE.md)，完整候选排序见 [SELECTION_RANKS.csv](SELECTION_RANKS.csv)。选图只用正式范围、官方难度、当前楼外类别覆盖、同源合法 T 和可回源原图；不用 Q / T 的大小。选人使用 8 个原答结构 / 位置 / 高度特征与本类中位数的距离，不用 Q / T 或其排名。

主图三个难度共享建筑 `jtcxE69GiFV`，因而共享同一套留楼外训练折；每图原三种分区的每个类别至少有 5 个同源候选；跨楼 `yqstnuAEVhm-01` 的原三种分区每类至少 4 人。K4 后续接入相同候选组，C3 每图只有 1 人，其他类至少 6 人；据实际容量取至多两人。典型示例不承担类别高低排名的抽样估计，不用这些重复展示位计算显著性或总体均值。

| 图 | 难度 | 同源候选人数 | DSTRUCT C1/C2/C3 | RFUSE C1/C2 | JOINT K3 C1/C2/C3 | JOINT K4 C1/C2/C3/C4 |
|---|---|---:|---|---|---|---|
| jtcxE69GiFV-10 | 简单 | 34 | 5 / 22 / 7 | 29 / 5 | 10 / 17 / 7 | 16 / 10 / 1 / 7 |
| jtcxE69GiFV-09 | 中等 | 34 | 5 / 23 / 6 | 29 / 5 | 11 / 17 / 6 | 16 / 11 / 1 / 6 |
| jtcxE69GiFV-26 | 困难 | 31 | 5 / 20 / 6 | 26 / 5 | 10 / 15 / 6 | 14 / 10 / 1 / 6 |
| yqstnuAEVhm-01 | 中等，跨楼 | 30 | 6 / 18 / 6 | 26 / 4 | 17 / 6 / 7 | 17 / 6 / 1 / 6 |

## 三、版本、预处理和计量合同

- **冻结仓库版本**：`48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。普通 Manual 的主目标 `primary` 范围；未把门洞、半自动或其它合法目标并入本图。
- **当前模型**：`TARGET_DSTRUCT_K3`、`RFUSE_GEOM_K2`、`OPPJOINT_K3`、`OPPJOINT_K4`。只绑定图片建筑对应的 `heldout_building` 且 `known=true`。不把 `ALL` 标签替换成楼外标签。DSTRUCT 类编号按训练困难结构中心排序，RFUSE 按训练困难融合转折响应中心排序，JOINT 按训练 Q 残差中心排序。各折中心见 [SELECTED_FOLD_CENTERS.csv](SELECTED_FOLD_CENTERS.csv)。
- **坐标与环序**：从 v2.1 `analysis_input/data.json.gz` 取当前有效 `points_1024x512`，包括上、下点对的既有共享 x 预处理及保存环序。显示时等比映射 2048×1024 原图。空间直线投影为全景大圆弧，接缝处拆段；无重排、删点、合点、坐标平均或高度回拟合。当前有效输入对象的原始导出、预处理前、预处理后及来源字段保存在 [SOURCE_OBJECTS.json.gz](SOURCE_OBJECTS.json.gz)。
- **结构定义**：转角 `>5°` 计转折，`≤5°` 计近共线。短墙要求边长/周长 `<0.04`，且两端转角均 `≥15°`。这是原答 `short_turn_edges` 的定义，与 RFUSE 训练响应的 `floor_short_edge_03_n` 不是同一个指标。全部 39 对象的三个结构计数已从有效坐标复核一致。
- **参考与 Q**：按 `(object_id, reference_id, reference_version)` 精确接入 `quality_records.csv`；93 展示位已有 Q 与 D10 的差值均小于 `1e-8`，全部为 `full_score_state=computed`。同一参考 ID / 版本的完整参考坐标来自 `reference_catalog.json`。这里不重评分，不用新参考静默替代旧参考。
- **劳动 T**：全部示例使用 `new` 同源记录，来源是 `user_processed_reported_not_raw_log_replayed`。图中 T 是合法登记秒数；本次未重放原始日志，也未将不同计时来源混合成同图对照。`target_time_seconds` 在源表缺失时保留缺失，不从缺失值构造 0。
- **单位**：平面图以相机到地板高度为 1，同图所有原答和参考共用尺度。位置偏差沿全景 x 向右、y 向下为正，单位为角度。匹配点均值不覆盖未匹配结构，故同时披露匹配比例。

## 四、文件与复现

| 文件 | 用途 |
|---|---|
| `index.html`、`originals/` | 离线完整原图叠加浏览，含放大、切换及原答分项 |
| `figures/`、`FIGURE_INDEX.json` | 四种分区 × 四图的 16 幅静态科学图，另有 `near_collinear_W114_W116.png` 释义对照图 |
| `SELECTED_RECORDS.csv` | 93 展示位的对象、类别、Q 分项、T、来源和结构字段 |
| `EXAMPLE_DATA.json` | 当前有效坐标、完整参考、标签、选择数据和展示元数据 |
| `SOURCE_OBJECTS.json.gz` | 39 个原始有效输入对象的完整源字段快照 |
| `CANDIDATE_IMAGE_COVERAGE.csv`、`SELECTION_RANKS.csv` | 选图和选人的完整候选审计 |
| `ORIGINAL_IMAGE_RECEIPT.json` | Release URL、ZIP 条目 CRC32、PNG SHA-256 与原始尺寸 |
| `BINDING_AND_VERIFICATION.json` | 来源文件哈希和坐标、Q、版本绑定核验 |
| `DISPLAY_VALIDATION.json`、`verify_examples.py` | 原表独立标签核验、17 PNG 完整解码、原图哈希、接缝路径及 HTML 本地引用 / JS 语法验收 |
| `fetch_originals.py` | 从既有 Release 用验证过的字节范围读取这四张原图；不会下载全部图库 |
| `build_examples.py` | 从冻结 repo 输入重建选择与绑定；不拟合、不评分、不改写标注 |
| `render_examples.py` | 仅从本目录冻结数据及 PNG 重绘 HTML 和静态板，无网络依赖 |

重绘：`python render_examples.py --font /path/to/NotoSansCJKsc-Regular.otf`。HTML 使用系统中文字体，不需要安装绘图库；静态图重绘需要 Python、NumPy、Matplotlib、Pillow 和可显示中文的字体。已有 PNG 可以直接使用。

原 12 主板与近共线板已有目视验收；第 10 批再检查 4 幅 K4 主板、单人类标识和个人分项，全部 17 幅 PNG 完整解码。全景接缝路径和顶点对应按新增对象复核，数值见 `DISPLAY_VALIDATION.json`；原坐标数组与保存的节点顺序保持一致。HTML 的本地文件引用与 `node --check` 语法检查通过。本环境没有安装浏览器，未把这些检查写成真实浏览器点击验收。

### 可核查源

1. HOHONET 项目，2026，当前有效输入：`research/data/releases/v2.1/analysis_input/data.json.gz`；参考目录：`research/data/releases/v2.1/reference_catalog.json`；现有 Q：`research/data/releases/v2.1/quality_records.csv`。
2. HOHONET 项目，2026，统一官方难度下原答记录：`research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz`。
3. HOHONET 项目，2026，当前 DSTRUCT / RFUSE：同目录 `classification/LABELS_ALL_LOBO.csv.gz`、`rfuse/RFUSE_LABELS_ALL_LOBO.csv.gz`；当前继续采用的 JOINT：`research/workers/personnel_v21_reselection_20261029/classification/MAIN45_LABELS_ALL_LOBO.csv.gz`。本次统一标签与训练中心汇总在上级 `basis/`。
4. HOHONET 项目，2026，原答几何公式：`research/workers/personnel_v21_reselection_20261029/classification/code/build_target_aware_candidates.py::geometry`。本次只复核和显示其已有结构计数。
5. HOHONET 项目，2026，原图索引：`analysis_results/quality/quality_scope_model_handoff_20261015/original_images/IMAGE_INDEX.csv`；[GitHub Release 原图资源](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015)。原 PNG 字节均经过 ZIP CRC32 校验，回执给出 SHA-256。

上述源统一固定于所列仓库版本，完整内容哈希见绑定核验文件。此图组描述个人原答，与 57 组定向人工融合顺序辅助结果属于不同对象层；没有把人工融合几何当成原答，也没有将个别坐标修正候选推广为类别规则。
