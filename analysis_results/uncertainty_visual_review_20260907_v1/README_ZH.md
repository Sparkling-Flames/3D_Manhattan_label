# 移交包审查与50图辅助视觉检查

本轮完成：不完整原包归档、数值复现及核心逻辑独立审查、单独勘误、5图显示校准和总计50图实际辅助视觉检查。人工最终判断仍为空。

## 从这里阅读

更新：[50图高清复看与点序勘误](ORDER_REVIEW_ZH.md)。旧12份重排现分为8份候选、2份较强保留、2份不推荐；不再把可生成网格称为修复正确。问卷新增全部标注有疑问选项，AI意见三步随时可读。现已复用预览任务的角点组顺序编辑并接入50图，操作与分别保存方式见填写说明；原始坐标不变。

2026-09-07显示升级：50张均接入仓库中对应split的2048×1024原始PNG（未AI放大），先核对与旧图的缩小图对齐，再原样复制。逐图页增加高清矢量标注叠图与新版Panorama Studio交互预览入口，保留原阅读顺序及旧概览。`hd/`的约束拟合仅为工具诊断，不回写原坐标、分簇或统计；本次没有增加审查通过数。生成命令：`python -m tools.thesis_main.analysis.upgrade_uncertainty_review_hd`。源文件和对齐记录见 `HD_UPGRADE.json`。

- [三步审查问卷入口](index.html)：①看高清原图 → ②直接看旧版3D并对照布局 → ③填写备注与状态。自动浏览器暂存、JSON备份及恢复、CSV汇总；[填写说明](QUESTIONNAIRE_ZH.md)。AI意见默认折叠，答案单独保存；[旧版资料目录](case_index.html)继续保留。
- [核心逻辑审查](CORE_LOGIC_REVIEW_ZH.md)：哪些结果可复现、已证实错误、可计算分母及解释边界。
- [视觉观察与下一步建议](VISUAL_REVIEW_ZH.md)：具体反例、场景差异、点序调整及推进顺序。
- [Sol独立审查](CORE_REVIEW_SOL.md)、[数值勘误](errata/ERRATA_QA.json)、[原表复现核对](NUMERICAL_REPRODUCTION.json)、[离线验证](VALIDATION.json)、[完成数量](REVIEW_STATUS.json)。
- [实际文件清单](DELIVERY_FILES.csv)：目录内交付文件的相对路径与字节数，清单不包含自身。

## 范围与完成数

普查底座380张：214张历史图，166张无历史响应候选；2501条canonical、2513条版本谱系。实际审查30张历史图与20张候选，覆盖22个building；未复核人工30或旧AI50。

历史30覆盖其总体全部22个building。候选166来自15个building；排除人工30和旧AI50后剩86图、8个building，本轮候选20覆盖这8个。不能把本批20候选当作全部15个building的代表。

50张全部先看无标注原图及四个80°局部透视，再看叠图和可用3D，共展示280份布局：100份Bi头输出、50份HoHo离线输出、76份参考版本、54份真人响应。原序257份可成网格，23份受阻。对其中12份提出独立点序预览并实际复看，此前记为10份可辅助定位、2份拒绝用于解释；本次高清复看将前10份进一步区分为8份候选、2份较强保留，均未核实作者意图；另11份没有保守重排方案。**50是图像审查数，不是280份布局全部通过，也不是2501条响应已逐份复核。**

原始生成日志保留 `rendered_unreviewed` 和生成时的0审查数；后来的 `layout_review_status.json`、`REVIEW_STATUS.json` 才是本次实际阅读状态。不要把不同时间点的日志混为同一状态。

## 文件与字段约定

| 文件 | 用途及关键字段 |
|---|---|
| `selection.csv` | 50图身份、building、历史/候选、旧统计、来源URL和选择理由。先building覆盖，再交替抽取旧指标高/低端；是探索性样本。 |
| `visual_reviews.jsonl` / `.csv` | 一图一行。`blind_observation`为先读图记录；`comparison`为后续对照；`question`、`tags`仅AI建议；`human_final_judgment`、`intrinsic_ambiguity_label`为空。 |
| `shown_layouts` | 精确来源ID、显示角色、context、原簇ID与支持数；`cluster_floor_support`是可计算成员数。显示代表仅为该子集medoid。 |
| `bi_raw_coordinates_equal` | 逐值坐标相等；与旧 `bi_equal`、地面距离0、视觉近似分别保留。不得转成无歧义。 |
| `cases/Vxx/*_source.json` | 每份显示布局的原坐标及来源；原点序不覆盖。`reference_*`只是来源角色，并非新确认的GT。 |
| `cases/Vxx/` | 原图、无标注透视、原序叠图、可用俯视/斜视、原始失败记录。 |
| `preview_adjustments_reviewed.json` | 原始点与预览点、原点ID到新索引映射、是否改配对/邻接、实际视觉观察、接受显示或拒绝原因；人工裁决仍为空。 |
| `images/` / `downloads_*.json` | 50份实际下载并解码的原图、URL与获取记录。图片已经在本目录，阅读不再依赖D盘外部资产。 |
| `reproduced_numerical/` | 原脚本的独立复算结果，保留原错误以便对照；后续初始化字段用 `errata/contexts_initialization_corrected.csv`。 |
| `errata/` | 完整context初始化勘误、bootstrap有效/无效分母及逐draw状态；没有用补抽无效draw改变原CI。 |

room实例ID未知仍为空。当前20人、旧资格和退出属性不作为本次历史底座过滤条件。候选真人分歧缺失不置零。离线HoHo输出不自动当作标注者当时真正看见的初始化；实际初始化仍须走便携包响应/context连接。

## 阅读与复现

直接打开本目录 `index.html`，普通浏览器即可离线查看全部50图。阅读原包数值还需要仓库内便携输入及收到的原代码；本地新增结果尚未推送，云端不会自动看到此目录。

在仓库根目录使用已有CPU依赖：Python、numpy、pandas、scipy、shapely、Pillow；本轮未安装模型权重、未推理或训练。新生成器自身不需要tabulate；原包另列自己的requirements。

```powershell
python tools/thesis_main/analysis/prepare_uncertainty_visual_review.py reproduce
python tools/thesis_main/analysis/uncertainty_handoff_errata.py
python tools/thesis_main/analysis/prepare_uncertainty_visual_review.py verify
python -m pytest tests/test_prepare_uncertainty_visual_review.py tests/test_uncertainty_handoff_errata.py tests/test_panorama_studio.py -q
```

重建图像证据分别执行生成器 `prepare --start 1 --end 5`、校准后 `prepare --start 6 --end 50`；`adjustments`生成独立建议，`finalize`只汇总已经写下的实际阅读记录。生成命令不能自动产生视觉观察或校准通过。若输入或渲染器变化，应重新视觉校准，不能沿用旧审核状态。

## 交付边界

项目地图和文档索引增加本包及归档入口；正式protocol、schema、资格、routing、Label Studio、原始导出、人工判断和Panorama Studio代码不改。本轮使用新分析脚本和独立输出目录；未运行整个仓库测试，因为正式运营与训练流程没有变化，定向检查见 `TEST_RESULTS.txt`。未生成新的论文提纲、实验定稿、疲劳模拟或停止人数。
