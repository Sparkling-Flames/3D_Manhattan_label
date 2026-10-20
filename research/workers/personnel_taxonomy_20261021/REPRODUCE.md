# 完整复现说明

## 1. 输入版本与目录

仓库：https://github.com/Sparkling-Flames/3D_Manhattan_label

冻结输入commit：`6503e2f54966a74352a6ec526f211fc3871c1427`。

把包内 `personnel_taxonomy_20261021/` 放入该commit仓库的 `research/workers/` 下。不要用后续变更的main悄然替代本轮输入。包内没有重复原仓库输入；各脚本中的ROOT均相对这一路径定位。关键文件摘要见 `INPUT_MANIFEST.json`、`route_a/DESIGN_AND_RECEIPT.json`、`fusion/INPUT_REFERENCES.json`、`evidence/INVENTORY_RECEIPT.json`。

实际计算环境：Python3.12.14，NumPy2.3.5，Pandas2.2.3，SciPy1.17.0，scikit-learn1.8.0，Shapely2.2.0；图像与报告使用Matplotlib、Pillow、ReportLab和fontTools。版本记录是本轮事实，不要求改写既有融合/评分依赖。Shapely的 `/tmp/hohonet_deps` 仅是本轮可选安装位置，正常安装后不需要该目录。

## 2. 独立分类与原答关系

从仓库根目录运行。下列代码会重建输出；保留已交付版本的备份以便比较。所有种子和选型参数均在代码及注册收据中固定。

```bash
python research/workers/personnel_taxonomy_20261021/route_b/run_classification.py
python research/workers/personnel_taxonomy_20261021/route_b/evaluate_classification.py
python research/workers/personnel_taxonomy_20261021/route_b/check_semi_candidates.py
python research/workers/personnel_taxonomy_20261021/route_b/explain_geometry_candidates.py
python research/workers/personnel_taxonomy_20261021/route_b/aggregate_semi_hierarchy.py
python research/workers/personnel_taxonomy_20261021/route_b/write_supplement_tables.py
python research/workers/personnel_taxonomy_20261021/route_a/run_route_a.py
python research/workers/personnel_taxonomy_20261021/route_a/check_route_b_relations.py
python research/workers/personnel_taxonomy_20261021/route_a/interpret_relations.py
python research/workers/personnel_taxonomy_20261021/route_a/select_relation_cases.py
python research/workers/personnel_taxonomy_20261021/code/integrate_labels.py
```

A的`--reuse-pairs`只能在相同冻结输入已重建 `pair_observations.csv.gz` 后使用；本精简包不含该缓存。B原始结构标签继续使用 `route_b/final_labels.csv` 与 `lobo_labels.csv`；它们不是后续Semi推荐主标签。Semi位置候选必须筛 `candidate=semi_position_scale`。

`aggregate_semi_hierarchy.py`只按已冻结SP_L/SP_A/SP_T生成SP_LOW/SP_OTHER层级，校验原标签SHA不变；不会改变38个Semi专属交换事件。根整合表使用实际有该条件的Manual22楼和Semi12楼，输出2,108行。

2026-10-21仓库采用副本修订：`evaluate_classification.py`的共享汇总先平均同图的不同参考面板，再按图、楼等权。`check_route_b_relations.py`的Q/来源匹配加入双方共同点数层；输出的`n_pairs`为匹配前对数，`n_pairs_contributing`为双侧匹配层中实际贡献的对数，`n_pairs_unmatched`为余数。原下载包与它的HTML/PDF及`PACKAGE_MANIFEST.csv`保留收到时身份；本目录修订后的Markdown报告和CSV为当前校正结果。无需重跑团队融合。

## 3. 新团队、旧端点复用与机制

下面的prepare按标签、元数据、来源和容量选择成员，run才调用原生评分/融合合同；没有按目标Q选择成员。详细输入、注册和分母见 `fusion/REPRODUCE.md`。

```bash
python research/workers/personnel_taxonomy_20261021/fusion/study.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/study.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/study.py summarize
python research/workers/personnel_taxonomy_20261021/fusion/study.py common
python research/workers/personnel_taxonomy_20261021/fusion/relabel_a2.py
python research/workers/personnel_taxonomy_20261021/fusion/nested_paths.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/nested_paths.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/a2_specific.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/a2_specific.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/semi_position.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/semi_position.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/export_cases.py
python research/workers/personnel_taxonomy_20261021/fusion/summarize_extra.py
python research/workers/personnel_taxonomy_20261021/code/build_inventory_usage.py
```

原答9°/12°分簇没有改变融合的7.5°墙角对应、MV50半票保留、坐标中位数或环序。B8L2主线和D10对同一团队几何评分。Q(C)−Q(B)是换类净效应；A–B/A–C是保持构成/改变构成的位移。缺Q、不同点数、对应不唯一、几何不完整均保留。

可直接从保留的REQUESTS、TEAMS、EVENTS和汇总核对5,808个正式设计团队，再加MECHANISM_CASES中指定jtc-26的2个不同团队，共5,810个，无须从缓存推断。旧63,476端点对使用已有几何，采样条件仍是原K3/Rnew2设计。

## 4. 原图与精确叠图

原图Release：https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015 。本轮以range请求提取所需PNG成员、检查ZIP CRC；不下载或打包原图全集。

已有仓库工具：`research/workers/personnel_interchangeability_20261020/analysis/visual_sources/range_zip.py`。使用同目录 `release_metadata.json`、`zip_directories.json`、`release_IMAGE_INDEX.csv`，按 `--image-id` 传入案例图code即可。完整相对成员名与SHA在案例证据及本包 `evidence/PHOTO_SOURCES.json` 中。

叠图需要一份覆盖中文的字体文件。图中使用Noto Sans SC，可从其官方字体项目取得兼容字体：https://github.com/notofonts/noto-cjk 。原变量字体转成Regular静态TTF仅用于排版，不影响任何数据。把下列示例路径替换成自己的照片/字体路径；可多次传入--photos。

```bash
python research/workers/personnel_taxonomy_20261021/code/build_local_evidence.py --photos /path/to/photos --font /path/to/NotoSansSC-Regular.ttf
python research/workers/personnel_taxonomy_20261021/code/build_mechanism_figures.py --photos /path/to/photos --font /path/to/NotoSansSC-Regular.ttf
```

几何使用既有连续坐标和原环序，ERP来自实际PNG。C01至C07的代表成员按楼外历史靠近类中心选择；后续案例是结果后解释性选择，不能代替全体统计。7y21的原处理输入、shared-x、CLUSTER_API与viewer floor逐点收据单列。新批原始导出缺失时，只声明可核到保存的processed输入。

## 5. 报告与精简包

`code/build_report_artifacts.py`从根 `REPORT_ZH.md`、标签及图表生成同内容的HTML/PDF，并补全成员附录。传入可用中文静态TTF与输出目录即可。PDF使用ReportLab，生成后用Poppler渲染检查。本轮的PDF检查临时PNG不在交付包中。

`code/package_results.py`按显式排除规则生成精简zip及文件SHA清单。保留正式标签、关键代码、报告、聚合表、精确团队、必要案例几何和图表；排除全部运行缓存、逐对配对缓存、预测缓存、原图全集、环境和冗余旧端点全量重贴表。库中原始文件依赖保持相对路径引用。

这些脚本不推送GitHub、不修改原参考/资格、不把类别当成新的组队授权。再研究其他任务或改变阈值时应生成新版本，不能覆盖本轮冻结结论。
