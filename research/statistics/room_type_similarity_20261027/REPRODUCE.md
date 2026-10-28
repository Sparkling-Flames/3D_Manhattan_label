# 同用途不同房间：复现说明

## 1. 从本包开始

本专题的仓库相对位置为 `research/statistics/room_type_similarity_20261027/`。命令均在这个专题目录执行；多个分包应解压到同一仓库根目录，使 `inputs/`、`code/`、`results/`、`assets/`、`cases_history/` 保持本包中的相对位置。以下流程使用已经交付的小输入，不需要私有 `research/data/releases/v2/analysis_input/data.json.gz`，也不需要下载原图全集。

本轮计算启动时读取 main `b9bcec809fbaec8ab055931a1abb7baa5db44dac`；最终采用 main `b2b0898b90bd631df37f1f2e75e8380800a43cf8`。五个核心输入的 Git blob 均未改变，见 `source/MAIN_UPDATE_SOURCE_CHECK.json`；因此不把后续采用版本当作一次新的独立验证。最新 scoping 的均值和标签对照另见 `source/NEW_MAIN_SCOPING_COMPARISON.json`。

本轮新计算对象是保存原答的用途相似性、共同人员对照、跨建筑留出预测及时间分析。既有 Q、D10、资格、参考、几何特征和旧构成实验直接复用；**没有重新分类，没有新增融合端点，没有修改 GT 或评分。**

### 最小依赖

已实际使用 CPython 3.12.14；精确 Python 包版本见 `requirements.txt`。可在已有 Python 环境中安装：

```bash
python -m pip install -r requirements.txt
```

主分析只需 NumPy、pandas、SciPy、scikit-learn；图表增加 Matplotlib，案例原图读取增加 Pillow。归档的旧难度脚本中还出现 Shapely，但下列当前执行流程直接读取冻结几何字段，不需要重跑旧脚本。中文图表使用附带的 `assets/NotoSansCJKsc-Regular.otf`，许可随字体保存。

建议运行时设置 BLAS/OMP 为 1 个线程。命令应按下文依赖次序顺序执行；同一结果目录只允许一个写入进程。可先复制完整交付目录再复算，保留已交付的结果和核验回执。不同平台、压缩时间戳或版本元数据可能改变文件字节；检查应首先比较主键、行数、数值和模型参数，而非要求所有新导出的 ZIP 字节完全一致。

## 2. 输入与基准支持

| 输入 | 用途 | 当前记录数 |
|---|---|---:|
| `inputs/annotations.csv.gz` | 全库存对象键、正式资格、用途、Q/D10、时间和冻结几何特征 | 10,439 |
| `inputs/images.csv` | 图片×条件汇总、难度、用途、参考及正式成员清单 | 313 |
| `inputs/image_labels.csv` | 原用途标签、来源和范围元数据 | 261 |
| `inputs/annotation_geometry.jsonl.gz` | 以 `object_id` 连接的原答/处理后几何、参考及坐标证据 | 10,439 |
| `inputs/historical_training_gate.csv` | 旧同房训练口径的有限敏感性输入 | 5,719 |

主分析为普通 Manual、正式质量可用且 Q/D10 均有值：5,719 份、177 图、60 人、22 栋建筑。普通 Semi 单独分析：901 份、32 图、59 人、12 栋建筑。全 177 图用于一致的总体留出评价；另有 **161 图、5,236 份、60 人、21 栋建筑**具有跨建筑重复的已记录用途。后者由既有用途及跨楼支持决定，是同一套预测的重聚合，不重拟合、不按结果删除图片。六大用途为 155 图，另加储藏 6 图；缺失、明确无法判断、开放复合和仅单楼的特殊用途仍留在全库存。

输入的单位、状态及主键见 `FIELD_CONTRACT.md`。尤其不要将 `object_id` 读为整数，不要把缺 Q、未形成有效几何、人工排除和 GT 暂停合并为一个失败状态。

## 3. 图片平均水平、分布和共同人员对照

按次序运行：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python code/image_similarity.py --inputs inputs --out results/image --part all
OPENBLAS_NUM_THREADS=1 python code/finalize_image_outputs.py --study .
MPLCONFIGDIR=/tmp/hohonet_room_mpl OPENBLAS_NUM_THREADS=1 python code/plot_image_similarity.py --study .
```

`--part all` 包含描述、跨建筑图对、共同人员三图匹配、基础预测以及两种更充分的几何模型对照。最终为 12 个方法、Q/D10 两个结局、每个结局 177 个完全相同的目标图：`LOBO_IMAGE_PREDICTIONS.csv.gz` 共 4,248 行，`LOBO_MODELS.csv` 共 528 个外折×方法×结局。`finalize_image_outputs.py` 对相同预测补充共同支持和三图难度一致子域的汇总，并检查已存结果；不会新增融合或另拟合模型。

只需重做一部分时，`--part` 还支持：

| 参数 | 执行内容及依赖 |
|---|---|
| `descriptive` | 描述统计、跨建筑成对和三图共同人员对照 |
| `prediction` | 预测主流程及两种几何模型库对照 |
| `aggregate_prediction` | 仅从当前预测表重新汇总 |
| `geometry_portfolio` | 需要已有 `LOBO_IMAGE_PREDICTIONS.csv.gz`、`LOBO_MODELS.csv`、`LOBO_INNER_TUNING.csv.gz`；替换两种几何方法并汇总 |

三个核心比较各有不同问题：全人员池均值保留现实人员构成；共同人员图对控制人员名单；三图事件固定目标 T，并在另一栋相同源建筑中比较同用途 S 与不同用途 C，还可匹配 S/C 难度与参考几何。三图原始事件并不要求 T/S/C 难度全部相同；严格三图同难度子域由收尾脚本单列。所有这些匹配是描述比较，不冒充留出预测。

预测外折整栋留出，内折按建筑分组。主程序随机种子为 `2026102703`；数值处理、模型选择均在训练支持内完成。含参考几何的预测回答“已知审定任务结构时，用途还有多少增量”，不能改称完全无参考的新图预测。详情、模型库与当前采用结果见 `results/image/IMAGE_FINDINGS_ZH.md` 和 `results/image/METHOD_IMAGE_PLAN_ZH.md`。

## 4. 个人相对表现与用途增量

### 4.1 普通 Manual 主分析

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python code/personal.py --inputs inputs --out results/personal
MPLCONFIGDIR=/tmp/hohonet_room_mpl OPENBLAS_NUM_THREADS=1 python code/personal_reporting.py --results results/personal --figures figures --font assets/NotoSansCJKsc-Regular.otf
OPENBLAS_NUM_THREADS=1 python code/personal_subdomain.py --primary results/personal --out results/personal/main161
```

默认分析 Q、D10 和 `annotation_turn5` 三个结局。每个结局均有 7 个方法：零基线、楼外个人一般历史、直接同用途历史、个人 Ridge、个人×用途、个人×难度/五参考几何、后者加个人×用途。完整 `OOF_Q.csv.gz`、`OOF_D10.csv.gz`、`OOF_annotation_turn5.csv.gz` 各 40,033 行，即 5,719 对象×7 方法；条件和每人历史机会数保留在同一对象支持上。

评价量为本人原值减去同图其他正式人员均值；本人不进入自己的同行均值。目标图真实同行值仅用于形成评价结局，不进入预测输入。训练按图片等权，预测在目标已知人员名单内中心化。一般个人历史与同用途历史都严格来自目标建筑之外，不以同一物理房间另一视角充当新房间证据。这里的“历史”是楼外资料条件，不额外声称其采集日期必然早于目标图。

主模型采用有限内建筑分组校准；Q 和结构分别选择正则强度，D10 复用 Q 的选择。五个参考字段是 `ref_turn5`、`ref_short_edges`、`ref_min_horizontal_deg`、`ref_radius_p90_h`、`ref_H`，准确含义见字段合同。当前结果以 `results/personal/COMPLETE_FINAL.json`、`FINAL_VALIDATION.json` 及完整 OOF 为准。

`personal_reporting.py` 从 OOF 生成逐人×用途卡、逐建筑证据和“去除一般能力后”的重复关系；`personal_subdomain.py` 只在固定 161 图上重聚合相同 OOF，不是新增训练。只需重汇总主表时，可对已有结果目录运行 `personal.py --summarize-only`，并传入与原结果一致的 `--condition`、`--layer`、`--outcomes`；不要将不同支持的已有文件混入同一目录。

### 4.2 保护最强一般历史基线的有限增量补充

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python code/personal_protected_purpose.py --inputs inputs --primary results/personal --out results/personal_protected_purpose
```

该补充在主模型完成后开展，身份为本数据上的有限方法补充及内部留出评价。它固定一般个人历史基线，独立收缩个人×用途偏差；内建筑分组选择强度，候选包含“完全不加用途”。因此用途不能通过改变一般个人参数而人为拖累或抬高基线。关键输出为 `PROTECTED_PURPOSE_OOF.csv.gz`、`OUTER_FOLD_LAMBDA.csv`、`INNER_CV.csv.gz`、`SUMMARY.csv`、`BY_PURPOSE.csv` 与 `BY_PERSON_PURPOSE.csv`。此流程不增加人员类别，也不是新的外部测试集。

### 4.3 旧训练口径敏感性

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python code/personal.py --inputs inputs --out results/personal_oldgate --gate-file inputs/historical_training_gate.csv --reuse-alpha-dir results/personal --outcomes Q
```

该分支保留全部 5,719 个目标评价对象，训练排除旧同房规则中的 216 个 `original_holdout` 对象，并据剩余训练作答重新计算训练同行均值；复用主分析选择的强度，不再搜索。它回答旧训练口径下是否改变结论，不能将本轮主模型重新包装成保持了早期外部测试身份。

### 4.4 Semi 次要分析

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python code/personal.py --inputs inputs --out results/personal_semi --condition semi
OPENBLAS_NUM_THREADS=1 python code/personal_reporting.py --results results/personal_semi
```

Semi 使用本条件的正式作答、同行均值和楼外训练；不与 Manual 合拟合，不恢复排除作答。门洞及 OOS 的库存支持另在次要条件表中保留，本轮没有把它们追加为普通 Manual 的模型训练。

`personal_reexport_models.py` 是保存模型导出阶段的专用归档工具，**不是全新复算的前置步骤**；正常复算使用上面的主程序。中文解释文档由研究者整合，分析命令不会自动改写所有人工撰写的判断段落。

## 5. 同来源时间和次要条件

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python code/time_and_secondary.py --base .
```

输入仍为附带的 annotations/images。输出在 `results/time_secondary/`。两个合法来源分别描述、拟合：`inherited_v1_audited_source` 且状态 `usable`；`user_processed_reported_not_raw_log_replayed` 且状态 `reported_processed`。时间必须为正，且同图同来源至少 3 个正式人员；不混合时钟语义，不补缺失时间。

结局为 `ln(source_time_seconds)` 减去同图同来源其他人的平均对数时间。一般个人历史与独立用途偏差采用外建筑留出，有限内建筑校准包含“不加用途”候选。保存逐对象 OOF、来源/用途/难度支持、逐人用途结果、外折参数以及 2,000 次建筑层 OOF 损失重抽。建筑重抽不新增图片，也不重新拟合模型；不能解释为蒙特卡洛新增路径。

## 6. 原图、完整原答案例与旧研究连接

```bash
MPLCONFIGDIR=/tmp/hohonet_room_mpl OPENBLAS_NUM_THREADS=1 python cases_history/build_case_evidence.py --cases cases_history
MPLCONFIGDIR=/tmp/hohonet_room_mpl OPENBLAS_NUM_THREADS=1 python cases_history/rebuild_common_person_figure.py
OPENBLAS_NUM_THREADS=1 python cases_history/assemble_history_links.py --out cases_history
```

案例脚本使用附带的 `case_records.json.gz`、`case_frozen_features.csv` 和三张 Release PNG，可独立重建案例表、BEV/完整边界叠加与图像定位。三个案例为 b8cTxDM8gDG-07、S9hNv5qa7GM-05、jtcxE69GiFV-13，共 104 个正式对象；三图来自不同建筑。没有必要重新下载 Release 全集。只有缺少冻结特征小表时，`--source-root` 才用于旧研究文件的备用读取。

`build_case_evidence.py` 重建几何展示与共同人员比较，直接沿用冻结 Q/D10，不重新评分。`rebuild_common_person_figure.py` 从保存的共同人员表生成 C02。`assemble_history_links.py` 读取附带的一张旧构成用途分层表，抽取原有 H1/Q9 条件及连接说明；这些条目仍是旧研究复用，不是本轮新组队实验。

案例内容、图片来源、对象键和视窗见 `cases_history/README.md`、`CASE_SOURCE_MANIFEST.csv`、`CASE_VISUAL_LOCATIONS.json`。Release 原图显示为 2048×1024，标注坐标标准域为 1024×512；绘图据此缩放。BEV 单位为相机高度，不是米。若某对象 `raw_original_available=false`，展示保存的有效/收到版本并保留此状态，不把它写成已恢复丢失原始操作记录。

## 7. 读取与交付完整性检查

本包保留现行模型、输出和来源回执。对已交付的完整目录，可再核对个人模型和图表当前值：

```bash
OPENBLAS_NUM_THREADS=1 python code/personal_verify_final.py --inputs inputs --results results/personal
OPENBLAS_NUM_THREADS=1 python cases_history/spotcheck_final_values.py
```

`personal_verify_final.py` 读取已交付的 `COMPLETE_FINAL.json`；它用于现行交付核对。若从仅代码+输入的空结果目录全新运行，主程序先生成 `COMPLETE.json` 和全部结果；不要为调用这个终稿核验工具而伪造旧的终稿回执。可直接核对新表主键和数量，并将自己的复算核验另存。

验证**实际 ZIP 文件**而非仅打包前目录：

```bash
python code/package_verify.py --zip /path/to/downloaded-package.zip --receipt /path/to/package-check.json
```

该工具检查 ZIP CRC、逐成员读取，所有 CSV/gzip 读到结尾并检查字段数，JSON/JSONL 可解析，若包中含清单则核对 SHA，并在相关输入同时存在时检查 annotations↔geometry、案例标量↔几何的对象键关联。分包分别验证；只包含报告/代码的包自然没有大表关联检查，完整合并后仍应核对跨包连接。实际行数及交付阶段验证结果以最终下载清单/回执为准。

## 8. 若要从仓库重新生成最小输入

此步骤可选；上述所有正式计算都能直接使用 bundled inputs 完成。当前 `build_inputs.py` 的固定采用版本为 b2，输入文件如下：

| 角色 | 仓库相对路径 |
|---|---|
| 真人 v2 对象及正式质量证据 | `research/statistics/v2_evidence_audit_20261019/records.json.gz` |
| 用途标签来源元数据 | `research/data/processed_input_review_20261018/data.json.gz` |
| 旧人员池用途/难度连接 | `research/workers/personnel_composition_study_20261019/analysis/independent/POOL_IMAGE_CONDITIONS.csv` |
| 保存的逐答结构/几何特征 | `research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz` |
| 冻结参考几何特征 | `research/difficulty/difficulty_mechanisms_v2_20261020/reference_conditions.csv` |

```bash
python code/build_inputs.py --repo /path/to/3D_Manhattan_label_at_b2b0898 --out /path/to/rebuilt_inputs
```

输出目录使用新路径，先与已交付输入比较，再决定用于新运行。旧元数据只用于用途来源，不替换 v2 质量或几何。此脚本不生成 `historical_training_gate.csv`；需做旧口径敏感性时，直接复用本包附带的精确 gate 表。未取得的私有 `analysis_input/data.json.gz` 不阻塞本轮已计算问题，但仍在来源记录中保持未取得状态。

## 报告、关键表和分包重建

在完成上述分析并合并各包后，可由保存结果重建报告与关键小表，不会重新训练或融合：

```bash
python code/build_delivery_report.py --base .
python code/render_report.py --base .
python code/build_packages.py --base .
```

HTML渲染额外使用Markdown 3.11.2。包构造器保留精确输入/输出，排除日志、缓存与无效历史导出；实际读取压缩CSV/JSONL至结尾，并用Pillow解码全部包内图像。交付环节还要对下载件再次运行 `package_verify.py`，不能只核对构造前的目录。
