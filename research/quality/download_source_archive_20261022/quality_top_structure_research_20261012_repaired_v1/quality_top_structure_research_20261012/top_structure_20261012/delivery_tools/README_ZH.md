# 离线组装与新目录复现

本入口复现**已经固定的研究轮次 `20261012`**。编号不是实际执行日期；清单的 `actual_utc` 记录真实 UTC 时间，本轮初次研究在 2026-10-11 执行。代码不访问网络、不重新融合、不修改标注或用户回执、不增选参数，也不把开发复算称为独立科学验证。

## 包内范围

新包包含本轮全部代码、配置、数值结果、来源与排除台账、复核材料，以及本轮实际使用的 **6 张 2048×1024 原图**。还保留可运行的冻结质量引擎、官方 HoHoNet 对照源码及许可、当前原始导出／编辑后／共享后正式输入、冻结几何、3152 条历史分量、原分组留出、30 题原回执、115 题原回执和覆盖层。

旧 portable foundation 提供了有边界的数值依赖清单。没有携带旧 24 张原图库、旧可视化、261 张全原图库或完整 ZIP。全库图片及 ZIP 的既有哈希／CRC／读取记录仍作为历史来源证据随包保留，不能把它们称为此次离线复現重新读过完整 ZIP。

`study_quality/results/candidate_scores.json` 等前轮数值表是**明确标记的历史输入**。本入口重新计算本轮高度机制、当前表示、原始边界、候选组合、校准与敏感性、固定融合端点评价和已冻结自由探索；不把带入的前轮表称作本入口重新完成。

## 一、在原工作区组装

需要原工作区中的本轮目录，以及旧 portable foundation 目录：

```bash
python top_structure_20261012/delivery_tools/prepare_and_reproduce.py assemble \
  --source-root . \
  --foundation-root delivery/quality_representation_severe_research_20261011 \
  --package-root delivery/quality_top_structure_research_20261012
```

默认要求新交付目录不存在。完成总报告后，可对**此工具已创建的新包**追加 `--refresh`，同步本轮报告和结果。旧包、旧数据和人工回执不会被覆盖；发现已携带的历史输入字节变化会拒绝刷新。

组装输出包括：

- 原工作区 `top_structure_20261012/delivery_tools/COPY_PLAN.json`：精确到文件的复制计划、SHA256、字节数、用途，以及与旧 portable foundation 是否相同。
- 包内 `provenance/COPY_MANIFEST.json`：实际复制清单。
- 包内 `provenance/PACKAGE_SCOPE.json`：数据范围、实际 UTC、原图数量、未带入部分。
- 包内 `requirements.txt`：本轮使用的 Python 依赖版本。

复制清单不含自身，避免自引用 hash；最终总包清单和 ZIP 由交付步骤在报告完成后补齐。

## 二、仅核验离线包

在解压后的新包根目录执行：

```bash
python top_structure_20261012/delivery_tools/prepare_and_reproduce.py verify \
  --package-root .
```

核对每份复制文件 SHA256、12 份 main 文件的 Git blob 和 SHA256、6 张原图的精确字节。当前 main 为 `38e259c043fed0817307dbc3d21c6dba06bd6662`。这一步不宣称完成数值复现。

## 三、离线数值复现

先在运行环境安装 `requirements.txt` 中固定的 NumPy、SciPy、Shapely、Pillow 和 Matplotlib。入口不会联网安装依赖；无外部模型权重或字体依赖。依赖已具备后，以下运行只读取本地包。

```bash
python top_structure_20261012/delivery_tools/prepare_and_reproduce.py reproduce \
  --package-root . \
  --output-root ../reproduction_top_structure_fresh \
  --workers 2
```

输出目录必须不存在且位于包外。工具先复制到新目录，再清除**新工作副本中**本轮可再生数值目录；包内原结果和所有原始输入保持不动。仅检查准备工作可追加 `--prepare-only`，这种运行会明确标记为尚未数值复现。

固定顺序是：资格与曝光审计、旧排序复核、907 成员规则、当前表示审计、922 条原始球面边界、12 个 X 控制、71 个高度设计、39 真实高度、中心化与不变量、候选组合、同预算楼栋分组切点校准、相邻档与移除敏感性、907 无标签描述、67 个固定源成员及三个不同融合坐标端点、已冻结的高度幅度／作用范围自由探索。

完整数值路径包括 **17 步**。`reproduction/EXECUTED_STEPS.json` 和逐步日志记录实际执行，任一步失败立即停止，不把带入的结果当作已生成结果。

## 四、同时重绘本轮材料

```bash
python top_structure_20261012/delivery_tools/prepare_and_reproduce.py reproduce \
  --package-root . \
  --output-root ../reproduction_top_structure_with_figures_fresh \
  --with-figures
```

完整路径增加到 **22 步**，包含本轮科学图、盲审图和 HTML、研究版 HTML、固定融合端点图。工具在新目录将六图索引重定位到 `assets/originals`，保留原 261 图索引的来源副本；不会用不存在的旧绝对路径，也不会把图片复制到自身。重绘不是新人工复核，原视觉判断和所有空白答案保持其原有含义。

## 五、结果对照与限制

工具逐文件比较本轮 JSON／CSV：数值绝对和相对容差为 `1e-10`；身份、状态、标签、缺失值、列表结构和键需相同。执行耗时、实际自由探索运行时间和环境版本信息单独报告，不混入科学数值差异。主要记录为：

- `reproduction/START.json`
- `reproduction/PLANNED_STEPS.json`
- `reproduction/EXECUTED_STEPS.json`
- `reproduction/NUMERICAL_COMPARISON.json`
- `reproduction/REPRODUCTION_VERIFICATION.json`

成功后再次检查包内所有携带源文件没有变化。失败会保留新目录、日志和差异表，便于定位；工具不会为了通过比较改值、删样本或放宽资格。

`top_structure_20261012/inputs/verify_sources.py` 是完整原始恢复环境中的 ZIP 验证入口，依赖另行持有的两份历史研究 ZIP 和四个基础 ZIP，**有意不在最小离线子集运行**。本包可以重做上述固定质量研究，但不能重演未包含的全原图库读取，也不新增正式留出验证或新的人数／组成融合轨迹。

## 六、本次实际封包验证

已在 **2026-10-11 14:59 UTC** 完成一次全新的离线工作目录执行，包含 `--with-figures` 的 **22 步**。104 份 JSON／CSV 对照通过，比较 65,359 个数值，最大数值差为 **0**；包内携带源文件全部未变。六张原图重绘了本轮盲审、研究版 HTML 和固定融合端点图，未将重绘当新人工判断。

记录保存在 `top_structure_20261012/delivery_tools/reproduction_evidence/`，包含逐步命令、日志、文件比较和验证摘要。这是固定开发实验的工程复现，不增加科学独立样本，不验证新人工等级或最差档阈值。随后对说明文字和包范围字段的更新没有改变科学计算入口或候选参数。
