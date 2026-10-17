# 第二轮：画廊独有 144 图到 35 人

## 已交付

144 图均达到真实加合成 35 人。真实库存为 2300 份，本轮新增 Manual 2740 份，其中正常组 1791 份、wild 949 份；合计 5040 份。

|经验难度|图片|每图 wild 最少|最多|均值|
|---|---:|---:|---:|---:|
|简单|48|0|2|0.7708|
|中等|48|5|7|5.9375|
|困难|48|8|19|13.0625|

工程几何问题 0、同图重复坐标 0、完整复制目标真人作答 0、导出拒绝 0、donor 建筑泄漏 0。合成人员编号唯一，并与第一轮 6678 个编号不相交。215 个受保护文件与开工预检哈希一致，包括第一轮 full 全部文件、画廊、模型 bank、v6 清单和 144 张全景。

两个独立进程生成的 44 个数据、审计及逐建筑拟合文件逐字节一致。相关 149 项测试全部通过。未推送，未改写真源，未合并画廊，未重生成第一轮产物。

## 输出位置

本轮目录：`/Users/ethan/Documents/ChatGPT/manha/output/difficulty_wild_35_20261017/round2_gallery_144_20261017/`。

- simulations.jsonl：2740 份合成数据及来源、校准、时间、scope 和难度字段。
- label_studio_synthetic.json：144 个合成任务，2740 份 annotation，完成现有解析器往返验证。
- difficulty_audit.csv：逐图真人分歧、经验难度、人数、wild 预算及实际数量、错误类型、scope 票数和合成分歧比值。
- summary.json、VALIDATION.json：数量与功能审计，包含无 GT 和分歧诊断状态。
- REPRODUCIBILITY.json：44 文件逐字节复现清单与最终哈希。
- source_integrity.json、source_manifest.json：源完整性、代码及来源哈希。
- INDEPENDENT_AUDIT.json：从输出和画廊重新核对全部 144 图的独立审计。
- full_target_manifest.json、target_manifest.json、difficulty_thresholds.json、image_calibration.json：冻结清单、阈值和逐图统计校准。
- fold_*.json、donor_manifest_*.json：15 栋目标建筑的留出拟合、训练人员及 donor 来源。
- donor_exclusions.csv：几何不合法的真人记录继续计入库存，排除其残差训练资格并保留原因。
- TEST_RESULTS.json、source_snapshot/：测试结果及本轮源码快照。

预检、冒烟及复现为同级独立目录，分别带 `_preflight`、`_smoke`、`_replay` 后缀。冒烟为三档各两图并补充 OOS 多数及平票图，共 8 图、152 份。

## 统计与身份口径

画廊 378 图中，234 图与 v6 重叠；第一轮独有的 25 图及这 234 图的历史产物均未改动。本轮只处理集合差中的 144 图，其中 140 图已有 16 份、4 图已有 15 份。

真实人数使用画廊 annCount。144 图的源采集条件均为 mixed，画廊没有逐份条件字段；`real_manual_n` 为沿用接口字段名，`real_count_basis=gallery_annCount_all_observed_conditions` 明确其实际计数含义。新增作答 condition 固定为 manual。

144 图涉及 15 栋建筑，donor 池来自画廊全部 24 栋建筑，共 5283 份几何可用作答。每栋目标建筑的残差及 lead_time donor 均排除本建筑。源人员使用 gallery_project98 命名空间；没有映射到第一轮 W 人员身份或宣称质量等级。

残差 donor 原始任务条件按实际保留：2608 份合成记录来自 mixed 来源、119 份来自 semi 来源、13 份来自 manual 来源。这里只陈述 donor 的来源，新增作答统一归本轮合成 Manual。

合成人员使用 S_MANUAL_200000 起的新号段，按完整 image_id 的排序和槽位稳定分配。画廊部分 code 只包含建筑名，全部集合运算、来源绑定和唯一性检查使用完整 image_id。

## 难度与无 GT 边界

难度来源固定为 `real_annotator_disagreement_empirical`。按用户确认的交接口径，以原数组位置比较可配对部分，x 使用 1024 周期最短差、y 直接差，汇总角点欧氏距离和所有真人组合；未按空间位置重新匹配环序起点。

144 图重算的线性三分位阈值为 188.32282914024944 / 224.99760802728764 px，三档各 48 图。该距离会受环序起点及不同点数作答尾部未配对影响，来源与局限已写入 source_manifest 和阈值文件，不称学长正式裁定。

正常组幅度从本图真人相对模型残差的 Q25 至 Q50 校准，wild 从 Q75 至 Q95 校准。图内只使用幅度、点数、底面面积和 scope 统计；完整残差向量及 lead_time 从楼外 donor 抽样。沿用几何失败减轻重试、连续环子集及同图去重，不回填模型原样输出。

scope 按本图真人投票分布采样，142 图 in_scope 多数、1 图 oos 多数、1 图平票；这些状态不授予范围正确性或 GT 资格。

全部 2740 份 `evaluation=null`，`evaluation_reason=no_gt_reference`；未调用质量评分引擎，无 B8L2/D10 分数。提交时间 t 仅作来源记录，活动时长保持为空并注明无活动时间证据，lead_time 保留其独立含义。

合成与真人有序分歧逐图比值已记录，仅作诊断：合成均值约 207.5220 px，真人均值约 199.8402 px；比值中位数约 1.0358，四分位区间约 0.9701 至 1.1158，整体范围约 0.2519 至 2.0756。不以该统计宣称真人分布已经匹配或空间质量已经通过验证。

## 测试与复现

149 项相关测试通过：原有 120 项、已修复夹具接口失配的 6 项看板测试、新增 23 项第二轮测试。看板测试继续检查数据、内嵌图、DOM 交互、离线和统计一致性，只在临时目录构建，不写第一轮 full。

新增覆盖画廊解析、坐标换算、异常与重复身份、144/2740 断言、周期距离和不同点数、三分位单调、标量校准、无 GT、时间缺失、建筑留出、编号跨轮隔离、导出元数据、源哈希及复现差异拒绝。另逐项对照第一轮已有任务的导出内容，验证可选元数据扩展未改变第一轮导出合同。

新增公共模式 `fill-144-gallery`，仅允许 Manual；旧模式默认参数与执行路径保留。新输出目录必须尚不存在。

```bash
/Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python -m tools.thesis_main.analysis.personality_simulation_review --mode fill-144-gallery --seed 20261017 --output ../output/difficulty_wild_35_20261017/round2_new_run
```

独立入口 `python -m tools.thesis_main.analysis.difficulty_wild_round2` 支持 `--pilot-only`、`--preflight-only` 及 `--verify-replay`。逐字节复现会先比较全部确定性文件，再给两份 VALIDATION 写入相同复现状态。

独立读回审计脚本位于 workspace 的 `output/difficulty_wild_35_20261017/audit_round2.py`；从仓库根使用 `PYTHONPATH=.` 和模拟器 Python 运行。
