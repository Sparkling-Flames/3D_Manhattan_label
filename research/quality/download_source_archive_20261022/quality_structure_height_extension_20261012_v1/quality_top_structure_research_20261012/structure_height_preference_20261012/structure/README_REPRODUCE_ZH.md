# 本轮结构子研究的复现入口

这是新研究增量，保留旧包全部输入、回执、分数和代码。先将已修复的 `quality_top_structure_research_20261012` 包完整解压，再将本轮增量解压到它的根目录。根目录应同时含 `previous_research/`、`study_data/`、`study_quality/`、`top_structure_20261012/` 和 `structure_height_preference_20261012/`。不要用本增量取代基础包。

## 阅读顺序

1. `REPORT_ZH.md`：D 的精确定义、处罚容量、43个合成控制、907条条件开发数据的出现范围、39条对齐真实数据的复算与反例。
2. `results/explicit_exposure_application.json`：本轮显式应用最新暴露登记的结果。
3. `review_pairs/RESEARCH_REVIEW_ZH.md`：4组新同图对照的技术决策、选例偏倚和不选理由。
4. `review_pairs/review_pairs_blind_user.html`：供完整性交付验收后选择性复核的离线匿名材料；尚无新答案。

## 数值复现

从修复包根目录执行。建议 Python 3.12，依赖 NumPy、SciPy、Shapely、Pillow、Matplotlib；冻结指标及绘图辅助模块随基础包提供。

```bash
python structure_height_preference_20261012/structure/run_structure_audit.py --root . --exposure-registry structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json
python structure_height_preference_20261012/structure/render_structural_cases.py --root .
python structure_height_preference_20261012/structure/prepare_targeted_pairs.py --root .
python structure_height_preference_20261012/structure/verify_structural_delivery.py --root .
```

方向诊断代码不加载或拟合新人工等级；`--controls-only` 可只运行合成机制，`--real-only` 可只运行真实几何。真实数据需要显式提供最新暴露登记，不能只靠历史筛选 JSON。所有输出写在本新目录，不改基础包。

复核脚本读取 `height/results/development907_candidates.json` 与 `evidence/results/development_907_filter.json`，这两份本轮结果随增量提供。若需要从原始组件重算候选，请按对应两个目录的复现说明先执行，然后再重新生成复核图及哈希清单。307个翻转记录对只用于开发选例，不是独立验证结果。

## 图像与坐标可用性

本目录 `inputs/originals/` 含6个研究例的完整原 PNG；`review_pairs/inputs/originals/` 含4对复核所需的另3个完整 PNG。两个绘图脚本优先使用这些随附且核验 SHA256 的副本。历史原图索引中的绝对路径只作缺文件时的备用；不需要在新机器重建旧工作区路径或取得261张完整图库即可复现这18张对照板。

`inputs/selected_real_cases.json` 与 `review_pairs/inputs/selected_pairs_full.json` 保存当前记录的原始导出、当前编辑后未共享x、预处理后三层点位、来源索引及冻结几何。后者还保存参考原输入、所有同组共享坐标轴范围和照片哈希。未经核验的历史配对或旧错误不会被拿来再扣当前版本；本次没有新造平均前3D房间。

原图是2048×1024，点位展示域1024×512，两者比例明确；局部裁剪也使用1024坐标。长度以相机高度h为单位。绘图只调整了画布白边和包围框，不改变底面/3D坐标、各组同尺度约束或观察角度。

## 结果验收数目

- 43个可计算合成控制，完整坐标、参考、指标和配置随附。
- 39条真实对齐记录、30张图片；另有907条条件开发记录、83张图片、739个严格不同冻结坐标序列。
- 946次独立 D 与冻结 D 比较，最大绝对差2.6201e-14度。
- 1872次同曲线反序、起点循环及共线加点的诊断稳定性检查，最大变化2.9132e-13。
- 6张研究对照板；另有12张匿名对照板（4对/3图/8作答），匿名HTML内16个图片实例（含每对原图）。
- 所有新答案仍为空，无新人工标签，无留出校准记录，无误报率或严重发生率估计。

`verify_structural_delivery.py` 验证实际文件、照片解码、图像哈希、匿名页面嵌入内容、源点位逐字典一致、数值程序来源以及空答案状态；它不代替科学有效性或人工审核。实际执行结果写入 `results/delivery_verification.json`。最终包的 ZIP CRC 与重新下载验收由整个交付的清单负责。
