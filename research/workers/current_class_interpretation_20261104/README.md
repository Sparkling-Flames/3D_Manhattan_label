# HOHONET v2.1 当前类别的原答、Q/T 与团队效果

**本轮已经完成解释层补充。** 当前类别的标法、质量、合法来源记录劳动、困难响应、成员容量，以及既有团队中的替换、联盟、比例、成员和背景作用，现已通过同图统计和完整原图串联。

当前方法保持为 DSTRUCT K3（K2 粗分）、RFUSE GEOM K2、OPPJOINT K3/K4。本轮未增加分类候选、Q/T 选队、进入策略、融合端点或评分。

## 直接阅读

1. [研究台](workbench/index.html)：离线切换分类、方式、目标、难度与时间来源。
2. [完整整合报告](REPORT_ZH.html)：结论、数据、原图、团队混合及逐条采用判断。
3. [逐类“类别—原答—团队效果”表](basis/CLASS_ORIGINAL_TEAM_TABLES.md)：12 个当前主要类别，人员、容量、原答和团队证据完整列出。
4. [完整原图图册](examples/index.html)：4 张原图，DSTRUCT K3、RFUSE K2、JOINT K3/K4 共 92 个典型展示位、1 个近共线附例，39 个不同原答。

## 内容目录

| 路径 | 内容 |
|---|---|
| `REPORT_ZH.md` / `.html` | 完整研究解释与采用稿 |
| `METHODS_AND_METRICS.md` | 预处理接续、参考、类别、计权、Q 分项和合法时间定义 |
| `basis/` | 当前合同、ALL 名单、楼外标签、每池容量、AC 标签关系、逐类总矩阵 |
| `dstruct/` | DSTRUCT 同图画像、分项、类内分布、来源敏感性、同楼及同人难度响应 |
| `rfuse_joint/` | RFUSE/JOINT 原答画像；五法统一的同记录同源 Q/T；Semi/其他目标 |
| `team_effects/` | 2,084 条团队条件与指标；ABC、AC、同房、纯类/联盟、配比/成员/背景 |
| `examples/` | 原始 PNG、完整有效坐标、个人分项、选样规则、17 幅静态板与离线图册 |
| `figures/` | 两张整合科研图 PNG/SVG；团队图和例图在对应目录 |
| `workbench/` | 内嵌数据的离线研究台 |
| `UNIFIED_COMMON_CLASS_PROFILES.csv` | 10,162 行全类同图共同支持画像 |
| `CONCLUSION_LEDGER.csv` | 整合后的逐条采用判断与来源 |
| `SOURCE_INDEX.csv` | 实际读取的固定版本来源、SHA-256、完整 URL |
| `DELIVERY_CHECKS.json` | 最终数值、支持、版本、引用及网页检查 |

## 批次与安装

继续此前第 01–07 批，提供两个仓库相对路径覆盖包：

- **第 08 批：类别原答画像与团队效果。** 包含完整数值表、逐类矩阵、方法合同、分析代码、专题报告和来源索引。
- **第 09 批：原图图册、科研图与研究台整合。** 包含原图、完整标注图册、交互页、整合报告及 v2.1/研究台入口更新。
- **第 10 批：JOINT K4 原图对照补齐。** 在同一四张图上增加 28 个 K4 展示位和 4 幅完整板；各图 C3 可用 1 人并全部展示，其余类各取 2 人。见 [K4 图册直达](examples/index.html#method=OPPJOINT_K4)、[补充报告](examples/JOINT_K4_SUPPLEMENT.html)和 [28 个个人指标](examples/JOINT_K4_SELECTED_RECORDS.csv)。K4 模型、总体 Q/T 和团队统计保持原值。

将两个 ZIP 按内部仓库相对路径解压至 `D:/Work/HOHONET`。完成后可从 `research/statistics/research_explorer_v1_r2_20261017/index.html` 的新入口进入，或直接双击本目录 `workbench/index.html`。这些包针对已有仓库交付增量，不包含整个原仓库，也不替代此前批次中的历史端点和自动结果。

本轮基于 GitHub 固定提交 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b` 制作。原始数值依赖应使用该提交下列出的版本；输出统计与源码保留各自清单。当前文档入口是本轮新增版本，因此其文字哈希可与源提交的历史入口不同。

## 复现

依赖：Python 3、NumPy、pandas；绘图另需 Matplotlib、Pillow、fontTools，以及可用中文字体。全部 PNG/SVG 与离线 HTML 已生成，阅读无需安装这些依赖。

在仓库根按以下依赖顺序运行（没有新拟合或新融合）：

```text
python research/workers/current_class_interpretation_20261104/basis/build_basis.py
python research/workers/current_class_interpretation_20261104/dstruct/build_profiles.py
python research/workers/current_class_interpretation_20261104/dstruct/build_person_difficulty_responses.py
python research/workers/current_class_interpretation_20261104/rfuse_joint/build_profiles.py
python research/workers/current_class_interpretation_20261104/rfuse_joint/build_quality_time_pairs.py
python research/workers/current_class_interpretation_20261104/team_effects/build_team_effects.py
python research/workers/current_class_interpretation_20261104/basis/build_class_original_team_matrix.py
python research/workers/current_class_interpretation_20261104/build_synthesis.py --font C:/Windows/Fonts/msyh.ttc
```

字体参数可替换为自己的 Noto Sans CJK 或其他支持中文的字体。图册复现脚本与选样、原图获取方式见 `examples/README.md`；源 PNG 已随第 09 批提供，不必为阅读重取 Release。

若已有仓库缺少固定源文件，可先运行：

```text
python research/workers/current_class_interpretation_20261104/fetch_frozen_sources.py --download-missing
```

该工具只从来源索引中的固定 GitHub 路径获取缺少文件，并核对 SHA-256；不会覆盖已有内容不同的数据文件。已经由本轮更新的说明入口作为文档版本差异单列。原图 Release 的获取由 `examples/fetch_originals.py` 单独处理。

`render_reports.mjs` 使用 Node 与 `marked` 将本目录报告转换为离线 HTML；此步骤仅影响显示，已经提供生成后的 HTML。

## 关键阅读规则

- `ALL` 名单是描述名单；真实原答、团队解释采用对应建筑的楼外标签。
- 全类共同支持、两类共同支持、Q/T 同记录支持分别保留，不共用分母。
- 主目标、其他合法目标和 Semi 分开；未知类和缺失 Q 不填零。
- 原答短墙特征与 RFUSE 团队训练短边特征保留各自原定义。
- 人工连接接续改变的是部分团队结果的可评支持；原共同支持不被写成从零分改善。
- 时间为同源合法记录劳动；几何平均时间比与算术总秒数不是同一个量。

核心结论和正反方向均以完整条件报告。当前成果能够支持人群不确定性的解释；若今后提出新的进入顺序或任务分配收益主张，再针对那项应用验证。
