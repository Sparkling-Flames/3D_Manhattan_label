# 完整全景布局共识：独立研究交付

研究日期：2026-10-04（Australia/Melbourne）。冻结仓库提交：`c4e8f908f3725900600dec5909586658092d6234`。

**先读 `RESEARCH_REPORT_ZH.md`，或离线打开 `RESEARCH_REPORT_ZH.html`。**

本包包含：当前真实输入的一图三人小样本重算、针对性的几何/对应/统计反例、可运行共识原型、精确小组联合对应求解器、25 项测试及本地全量/组合实验入口。不是已经完成了当前 136 图全量重算，也没有原图视觉裁决。

## 本轮实际执行

读取仓库交接和关键方法/历史人工意见；将实际取得的第一张完整图片的三份坐标及所需元数据转录到输入文件；与同一来源附带的 footprint 做独立投影校验。遍历该图全部 7 个非空人员集合、6 种顺序，并先写入预测再读取单独保存的原参考。另执行合成反例、20,000 次/设置的误差模拟、300 次/设置的完整链接实验、有限池全部 4,095 个非空子集枚举、小组联合对应 64 状态精确搜索。

合成记录有 `synthetic` 或明确的变形来源；它们不构成新增独立真人，不进入真实样本数量。没有重新预处理、恢复被排除记录、使用目标 GT/未来人员挑选当前输出，或自动确认新环序。

## 复算本包

复用已有 Python 环境即可。已实测 Python 3.13.5、NumPy 2.3.5、SciPy 1.17.0、Shapely 2.1.2；不要求强制安装这些精确版本。

```bash
python -m pip install -r requirements.txt
python -X utf8 run_experiments.py
python -X utf8 -m unittest discover -s tests -v
```

数值表及几何输入/输出在 `results/`。原始测试记录为 `results/test_log.txt`。可选图表依赖及脚本为 `requirements-charts.txt`、`plot_results.py`。

## 在本地完整仓库继续

以下两个命令的输入完整字节核对**未在云端执行**；本包没有取得完整 `input.json` 到执行环境。首条命令将校验本包转录字段与完整源文件，以及冻结 Git blob。

```bash
python -X utf8 verify_local_excerpt.py --repo "/path/to/3D_Manhattan_label"
python -X utf8 run_local_panel.py --repo "/path/to/3D_Manhattan_label" --out "/path/to/NEW_consensus_results"
```

输出目录必须是仓库之外的新目录。程序不会覆盖现有结果。`run_local_panel.py` 默认比较 2.5°、5°、9°，记录每图实际成员、方法失败、条件式单结果/保留候选状态；不会把失败者静默移出分母。`source_input.json` 中未进入固定输入的记录只进入旁路清单，不被恢复为参与者。来源绑定和人员清单文件记录散列；不声称已重新解释其全部人工含义。

当前固定输入的 Git blob 应为 `faa118622c05b47c8edac1e04476282af08c97c5`。本地数据已经更新时，程序默认停止。明确使用 `--accept-new-input` 才会作为**另一版实验**运行，而非冒充冻结结果的复现。

## 真实组合 / 顺序实验

`run_subset_schedule.py` 读取明确给定的真实记录 ID 集合。每次推断只接收该集合，不接收同图其他人员、未来前缀或参考 GT。组合类别是外部研究输入，程序不自行重训或改写人员类型。

```bash
python -X utf8 run_subset_schedule.py --repo "/path/to/3D_Manhattan_label" --schedule inputs/example_real_schedule.json --out "/path/to/NEW_subset_results"
```

示例只覆盖本轮真实一图三人的 6 种顺序、18 个前缀。替换计划中的记录 ID 即可测试已有人员的其他真实组合。不得以目标图共识/GT 的结果反向选有利组合。小组同点数时还运行精确联合对应；预算超过 100,000 状态会明确返回无法完成精确枚举，不把截断搜索伪装成最优解。

## 主要文件

|文件|用途|
|---|---|
|`RESEARCH_REPORT_ZH.md` / `.html`|完整中文研究结论、推导、限制与本地目标|
|`src/consensus_lab.py`|球面距离、完整/部分对应、原环投影、角点融合、证据账本、条件式输出、联合对应搜索|
|`run_experiments.py`|复算本包全部核心数值证据|
|`run_local_panel.py`|只读当前完整固定输入，保留失败清单|
|`run_subset_schedule.py`|按真实 ID 计划独立重算每个人员集合|
|`verify_local_excerpt.py`|本地验证本包转录字段及完整源 blob|
|`tests/test_lab.py`|25 项独立测试，不是原仓库完整测试套件|
|`inputs/current_excerpt.json`|实际取得的一图三人计算字段与来源说明|
|`inputs/reference_excerpt.json`|隔离保存的原参考，仅预测冻结后评价|
|`inputs/extra_real_shape.json`|额外取得的一份示例坐标，未用于真人效果统计|
|`results/adapter_smoke_test.json`|两个本地入口在三人临时夹具上的测试，**不是全量运行**|
|`MANIFEST.sha256`|交付文件散列；`verify_artifacts.py` 可校验分发包|

所有数值候选均非人工 GT。生成坐标不会继承源环的人工确认。原型不会将 ERP 单值墙带不适用解释成人员错误，也不会把“上下一致”压成只看地面。
