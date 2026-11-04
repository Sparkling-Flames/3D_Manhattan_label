# 第二批：严格ABC、Q-only及30图反例

主报告：[REPORT_ZH.md](REPORT_ZH.md)。逐条结论：[CONCLUSIONS.csv](CONCLUSIONS.csv)。

本目录保留原自动版、人工辅助扩展版及原共同支持的对照。固定57组人工顺序中的精确团队/参考，未重新选员、分类或改变任何节点坐标。

## 文件入口

- `HALF_AUTOMATIC_EVENTS.csv.gz` / `HALF_ASSISTED_EVENTS.csv.gz`：279条原冻结ABC事件及其对应辅助版本；`updated_class_legal`标出当前208条合法事件。
- `HALF_SUMMARY.csv` / `HALF_SUPPORT.csv`：原冻结与当前合法两种设计范围，质量及原机制分项、旧新支持、原共同支持数值差。形成/失败状态单列。
- `HALF_IMAGES.csv.gz` / `HALF_BUILDINGS.csv` / `HALF_DIFFICULTY.csv`：按原背景→替换块→池→图计权后的描述表；建筑不取代图片主估计。
- `HALF_MATCHED_BACKGROUND_LINKS.csv.gz` / `HALF_MATCHED_BACKGROUND_SUMMARY.csv`：精确XYZ的14/7与20/7配对；保留D包含关系，联合变化不可当纯人数效应。
- `QONLY_*PAIRED_EVENTS.csv.gz` / `QONLY_SUMMARY.csv` / `QONLY_IMAGE_EFFECTS.csv.gz`：五政策臂同步修补、原支持与扩展支持；沿原种子20261031的2000次建筑簇bootstrap。
- `QONLY_OUTPUT_STATUS.csv` / `QONLY_STATUS_SUMMARY.csv` / `QONLY_SUPPORT.csv`：逐臂形成/可评状态及指标特定共同支持。
- `QONLY_DIFFERENT_SELECTION_*`：保留原选员差集、固定类别构成，只更新受影响质量/结构/几何。
- `COUNTEREXAMPLE_TRANSITIONS.csv` / `COUNTEREXAMPLE_EVENT_EXPLANATIONS.csv`：原30图逐条状态和相关14/7、20/7事件解释，含旧新逐臂Q、节点数和状态。
- `QUALITY_CONDITIONED_ANNOTATION_LABOR.csv`：原劳动固定，质量支持扩展所导致的条件统计变化；人工排序劳动未计时。
- `AUXILIARY_LEGACY_REFERENCE_DIAGNOSTICS.csv` / `UNCHANGED_AUTOMATIC_LEGACY_REFERENCE_DIAGNOSTICS.csv`：按原refdiagnostic补足实际消费的4项诊断；不改中央首批端点文件。
- `UNCHANGED_AUTOMATIC_GEOMETRY_RECOVERY*`：仅2个原20人对手丢失几何的定向原自动重放，原已有标量parity最大1.42e-14；不是新增团队或人工重排。
- `CHECKS.json` / `INPUT_MANIFEST.json`：版本、来源散列、原基线parity与支持检查。

## 复现

在仓库根运行 `python -m tools.thesis_main.analysis.evaluate_manual_order_half_qonly_20261104`。已有2队几何恢复档案会直接复用；仅当该档案不存在才精确恢复这2队。原自动来源文件不覆盖。运行 `python -m pytest tests/test_manual_order_half_qonly_20261104.py -q` 检查缺失分数、计权和身份不变量。

57组是定向案例，不据此估计所有自动无环结果的修复率。新出现的Q不能与原缺失值0相减；原共同支持上的质量和几何数值完全保持。
