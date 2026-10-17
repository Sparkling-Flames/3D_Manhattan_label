# Manual 35 难度驱动合成批次交付

## 结果

本地实现与全量生成完成。259 张图共有 2387 个真实 Manual 图人身份，补入 6678 份合成作答，合计 9065 个图人身份。每图总数为 35。合成部分含 wild 1492 份、正常组 5186 份。

|难度|图数|每图 wild 最小值|最大值|均值|
|---|---:|---:|---:|---:|
|简单|134|0|2|0.6493|
|中等|37|5|7|6.0541|
|困难|38|8|20|13.6842|
|单列|45|8|20|13.0889|
|待修正GT|4|12|19|14.75|
|待复核|1|13|13|13|

几何检查问题 0、导出拒绝 0、模型原样复制 0。385 个受保护输入文件哈希检查全部通过。相同 seed 的两个独立全量进程产出 36 个数据、审计和逐建筑拟合文件逐字节一致。未推送，未修改真源或正式资格。

## 输出

批次根目录：`/Users/ethan/Documents/ChatGPT/manha/output/difficulty_wild_35_20261017/`。

- `inputs/`：冻结输入、Git 提交与 LFS 内容哈希。
- `full/`：正式本地交付，含 simulations.jsonl、label_studio_synthetic.json、difficulty_wild_audit.csv、summary.json、VALIDATION.json、source_integrity.json。
- `full/REPRODUCIBILITY.json`：36 文件字节复现结果。
- `full/TEST_RESULTS.json`：测试清单与基线数量差异。
- `full/review.html`：离线点位核验页，覆盖三类单独退化、各难度、10 张范围问题图及坏 GT。
- `full/source_snapshot/`：本轮实现和测试源码及哈希。
- `replay/`：独立全量复现。
- `smoke_final/`：13 图、367 份冒烟验证。此前 smoke 目录保留调试证据，不用于交付。

## 输入与实现选择

冻结提交 `1bbcf8ad6a5aa3a30be1b4f4e0249a62e02d79c8`。数据 v1 的 3222 份规范作答与 3513 个对象逐项核对身份。每图人数取全部规范 Manual 作答中的不同源人员身份，包含库存中未获训练资格的身份；训练独立使用获准的 1048 份质量面板，并按目标建筑留出。

v6 的实际全量标签数为 134/37/38/45/4/1；交接中的 133/35/37 对应普通候选子集。数据 v1 多出的 `2t7WUuJeko7-02` 和 `2t7WUuJeko7-03` 单列于 difficulty_unassigned.json，未纳入本轮 259 图。

原 bank 有 23 图无模型、2 图模型族不完整。经用户明确批准，新模式用已有 test/validation ep300 回放 TXT 为 23 图建立只读补充索引，其余图片只使用已有模型族。原 bank 文件未修改，补充来源与哈希见 supplemental_model_index.json。没有重新推理、伪造模型族或用 GT 填补模型。

新模式按 B8L2 的楼外画像选择高/低质量模板。D10 保存为敏感性轴。预算固定，三类 wild 操作使用真实低质量训练 donor 的残差、95% 分位 cap 和实测删除频率。连续区段删除保留环序，组合删点仅删区段端部。几何失败确定性地减轻操作并重采样，失败次数与原因保留。

正常组使用相对较高模板、优先同点数无删点 donor，并保留整份残差结构。模板类别描述来源人员，不保证每份合成结果均达到某个绝对质量阈值。

独立合成人员编号使用 S_MANUAL 命名空间，每图每槽位独立 seed。Label Studio completed_by 与真人模板身份分离，source_worker_profile_id 继续保留。旧模式沿用原有导出编号和默认 seed。

## 范围、质量与核验边界

29 张范围待核图沿用 v6 已确认底面与参考状态，仅底面可用时不合成参考顶界。10 张范围问题图全部标记；4 张坏 GT 不评分。生成几何来自模型及楼外真人残差，范围修正用于固定参照、底面评价和审计，未重新画参考。

冻结 B8L2/D10 公式与 1911 份真实质量记录重组一致，最大绝对误差约 2.13e-14。5845 份合成记录可完整评价，702 份仅底面、124 份排除坏 GT、7 份完整度量不可用；缺失分数保持空值。

可完整评价的合成 wild B8L2 均值约 25.20，正常组约 57.75，楼外真实低质量人员作答约 62.98。wild 明显更严重，且不同组图片组成不同，当前不能称为已验证的真人分布匹配。质量比较为诊断，未使用目标图质量反馈挑高分输出，也未将工程几何合法等同完整空间正确。

已检查离线点位核验图：删点、连续范围缩减及部分点位偏移可见；正常组仍可能继承模型范围偏差。图像检查保留此边界，未冒称学长人工确认。

## 测试与复现

相关测试 120 项通过，其中原有八个模拟器测试文件 91 项、新增 29 项。交接所称 99 项未能对应到当前本地测试集合，不声称已验证不存在的八项。另探索的旧建筑人数统计测试依赖 sklearn，当前模拟器环境缺少此包，该文件未计入通过数量。

从仓库根目录执行，输出目录必须尚不存在：

```bash
/Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python -m tools.thesis_main.analysis.personality_simulation_review --mode fill-to-35-wild --seed 20261017 --output ../output/difficulty_wild_35_20261017/new_run
```

独立入口 `python -m tools.thesis_main.analysis.difficulty_wild_run` 还支持 `--inputs` 与 `--pilot-only`。复现检查及核验页生成使用 `python -m tools.thesis_main.analysis.difficulty_wild_review --run <first> --replay <second>`。

回归清单见 TEST_RESULTS.json。覆盖预算、人数去重与零缺额、连续子集跨环、三类几何退化、无证据失败、源不变性、建筑隔离、坏 GT/缺参考、35 个合成人员复用同模板及导出唯一性。

最终批次同图完全重复几何为0；11份记录触发了确定性去重重采样。正常组的残差幅度在真实较高质量训练donor幅度四分位区间内插值，消除重复模板产生的精确副本。`initial_full/` 与 `initial_replay/` 保留首次重复率审计，不属于最终交付。

交互可视化入口：`full/dashboard.html`，包含259图、6678份合成与2329份可显示真人坐标。单文件内嵌图片与数据，可离线打开；支持难度/范围筛选、逐份样本、模型/真人/合成全景叠加、底面空间与质量分布。浏览器交互及手机布局检查见 `full/DASHBOARD_VALIDATION.json`。
