# HOHONET同房质量研究：下载与最小复现

本交付使用main `561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9`；Dot PR固定头 `e83286b7814afc614253aa392050e9a3851ae058`另列。本轮分析为当前库存内部研究，不是旧47.1 MiB包原件恢复。报告与关键表单独提供；各ZIP是独立文件，不是分卷压缩，任选所需部分即可。

## 1. 推荐下载顺序

1. 独立HTML综合报告：所有正文与关键图嵌入，无需联网或解压即可阅读；Markdown版用于纳入仓库。
2. 关键CSV：原声明视角均值、直接图对、逐人、预测、选队、替换、停止和新旧清单。完整字段说明见本包 `FIELD_CONTRACT.md`。
3. `01_报告代码与小表.zip`：报告源、全部关键代码、方法参数、输入索引、搜索摘要与小表。
4. `02_精确事件与决策.zip`：精确团队请求/替换/选队事件、全组最大历史停止决策；重新汇总需要它。
5. `03_最终团队几何.zip`：45,552个不同团队的最终几何和质量；无需全部重新融合即可回查。可按需下载。
6. `04_个人逐历史预测.zip`：主要规则逐历史宽表、完整历史索引、逐人每个实际m结果与低尾结果。可按需下载。
7. `05_原图案例与统计图.zip`：可直接看的图、必要原答/参考/团队坐标及票账；不含原图全集。

各包解压到同一目录会形成 `HOHONET_same_room_20261021/`，互补目录，不覆盖固定仓库输入。包内 `FILE_INDEX.csv`含内容哈希与所属包。大训练缓存、runtime逐队缓存、原图全集、字体和环境均不交付。

## 2. 输入及环境

在独立取得的固定commit仓库中运行，不把个人现有工作仓库静默切版本。设：

```bash
export HOHONET_REPO="/absolute/path/to/3D_Manhattan_label"
git -C "$HOHONET_REPO" rev-parse HEAD
python -m pip install -r requirements.txt
```

本轮实际Python3.12、numpy2.3.5、pandas2.2.3、scipy1.17.0、scikit-learn1.8.0、matplotlib3.10.8、Shapely2.2.0、Pillow12.3.0。`/tmp/hohonet_deps`仅是本轮附加依赖位置，正常安装即可，无须复制它。模型/融合不需要GPU。

`INPUT_INDEX.csv`给固定仓库路径与SHA；原始证据、参考、房间直接关系、楼外人员标签/画像和冻结融合代码均由仓库提供。本交付不重复打包这些输入。

## 3. 最小重新汇总：不需要仓库或原图

下载01＋02并解压，在可写副本中执行：

```bash
python native_teams/analyze.py
```

仅需同目录 `SWAP_EVENTS.csv.gz` 与 `SELECTION_RESULTS.csv.gz`，以及numpy/pandas/scikit-learn。会重建替换效应、源端/双端同向率、历史Q校准、选队质量/劳动/坏尾及逐图建筑汇总，不重新融合。它写回当前目录，因此保留一份原交付表供对照。

嵌套人数摘要和案例楼外标签：

```bash
python native_teams/extend_summary.py
```

这一步需要 `HOHONET_REPO`（只为既有标签）和05中的案例JSON；不会新增融合。

## 4. 精确团队重放或装配

01＋02＋03已有所有最终团队，可先只重装配：

```bash
python native_teams/study.py assemble
python native_teams/analyze.py
python native_teams/raw_correspondence.py
```

`assemble`读取冻结角点对应函数，因此需要仓库和Shapely；不重新执行全体融合。要从请求重算45,552团队：

```bash
python native_teams/study.py run --jobs 4
python native_teams/study.py assemble
python native_teams/analyze.py
```

请求与参数已保存，`prepare`只在希望重新生成请求的独立副本执行；它会覆盖请求文件。原生引擎可能复用仓库中完全相同团队，本轮原始回执为45,551新算＋1复用；重跑计时与复用计数可变化，几何/评分应同合同一致。

## 5. 平均与个人预测

平均分支命令详见 `room_similarity/README.md`；入口为 `code/run_similarity.py`、`run_direct_mean.py`、`run_mean_prediction.py`。需要固定逐份证据/房间关系，不需要原图或新融合。保留成对描述、单源与全部实际多数m。

个人分支按序执行（可指定新的输出目录）：

```bash
python personal_similarity/analyze.py --repo "$HOHONET_REPO" --out /path/to/new_personal_output
python personal_similarity/lowtail_competitors.py --repo "$HOHONET_REPO" --out /path/to/new_personal_output
python personal_similarity/lowtail_class_increment.py --repo "$HOHONET_REPO" --out /path/to/new_personal_output
python personal_similarity/analyze.py --repo "$HOHONET_REPO" --out /path/to/new_personal_output --stage summarize
python personal_similarity/summarize_descriptive.py --repo "$HOHONET_REPO" --out /path/to/new_personal_output
python personal_similarity/extract_examples.py --repo "$HOHONET_REPO" --out /path/to/new_personal_output
python personal_similarity/finalize_outputs.py --repo "$HOHONET_REPO" --out /path/to/new_personal_output
```

固定参数在代码/参数JSON中；精简包不保存所有模型重复长表或全特征缓存。04中主要逐历史预测宽表可直接审阅，无需重训。其它模型按固定输入/种子重算。低尾基线补强的实际探索时序另存，不能宣称预注册。

## 6. 停止重建与在线几何

```bash
python prior_integration/rebuild_stopping.py --repo "$HOHONET_REPO" --output /path/to/new_stopping
python prior_integration/online_geometry_branch.py --repo "$HOHONET_REPO" --output /path/to/new_stopping --jobs 2
```

第一步只读取固定真实前缀，不新评分。可额外用 `--pr-dir /path/to/fixed_pr_package`与Dot保存表作数值桥；不提供也能运行主计算。第二步按固定哈希抽样新增几何；若要复用本轮已交付坐标，在已有输出目录用 `--reuse-geometry`。

Dot固定PR未合并；如需取得其原包，在独立仓库获取上述commit并用 `git archive`导出 `research/same_room/same_room_independent_followup_20261021`。不要用会移动的PR当前头替代本次固定头。

## 7. 原图、叠加图和局部票账

05已含可看的图和足以检查的原答/参考/融合坐标。重画需按 `photos*/extraction_manifest.json`取得15张指定Release PNG；可用仓库 `research/workers/personnel_interchangeability_20261020/analysis/visual_sources/range_zip.py`按范围取文件，无需下载全集。`archive/archive_path/image_id`是定位依据；旧绝对 `file`仅保留来源。

`render_cases.py`首次运行会从仓库两段固定字体归档自动解出中文字体，或可设置 `HOHONET_FONT`。字体不重复打包。先运行fusion再local：

```bash
python render_cases.py person
python render_cases.py fusion
python render_cases.py local
python cost_case.py
python native_teams/extend_summary.py
python native_teams/plot_results.py
```

`cost_case.py`为G172两个已有精确团队补全状态，会多执行2次原生融合，但不是新增不同团队。停止图命令详见 `prior_integration/REPRODUCE.md`，原图为 `photos_extra/S9hNv5qa7GM_ed36c0b595de42f0a4e13ba5d332814a.png`。

## 8. 哪些复现比较才有意义

比较键、支持、几何、评分、分子/分母和计算容差。CSV压缩字节、进程计时、库浮点末位可以不同；不要据此更改评分、目标资格或选择性删图。核心失败状态、不同角数、未知关系及缺时间保持缺失。本轮发现与检查都属于相同库存上的内部研究；增加团队数量不等于新增独立建筑或外部验证。
