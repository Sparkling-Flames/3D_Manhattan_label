# C1↔C3 严格 50% 替换：已完成补充

完整结果、方法、反例解释和逐条来源见 [REPORT_ZH.md](REPORT_ZH.md)。

本目录是固定提交 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b` 下的新增研究结果。当前 DSTRUCT K3、当前普通 Manual 主目标、现成 LOBO 标签；没有重分类、改坐标或覆盖旧实验。

## 已完成内容

- 8 人换 4 人：C1→C3 24 图、C3→C1 4 图，两个方向分别采用真实严格 ABC。
- 6 人换 3 人：36 图、10 楼的共同四端点设计，解决 8/4 两方向零共同图的问题。
- 3,200 个事件、4,992 个唯一团队端点；4,898 有正式 Q、94 个自动无连接。
- 同等自动处理；57 个已批准人工端点精确命中 0，不混入辅助处理。
- 完整分项、难度/房间用途、劳动来源、连接支持、固定块/背景成员效应、可见核诊断及数值验收。

主要表：[SUMMARY.csv](analysis/SUMMARY.csv)、[PAIRED_FOUR_SUMMARY.csv](analysis/PAIRED_FOUR_SUMMARY.csv)、[SUPPORT.csv](analysis/SUPPORT.csv)、[CONCLUSION_LEDGER.csv](CONCLUSION_LEDGER.csv)。

## 复现与验证

在 HOHONET 仓库根目录运行；代码使用当前目录相对仓库的位置识别路径，不依赖本次运行的绝对路径。

```bash
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/run_native.py --jobs 4
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/analyze.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/validate_delivery.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/diagnostics.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/plots.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/case_panels.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/write_report.py
```

`design.py` 在已冻结设计存在时拒绝覆盖。`run_native.py` 按池精确恢复已存端点；本轮来源与设计 hash 均已锁定。主均值按目标块→背景→替换块→图片汇总；建筑等权与建筑整簇区间另列。缺 Q 从未记零，T 仅在明确记录来源与合法支持内比较。

最终检查：[FINAL_VALIDATION.json](audit/FINAL_VALIDATION.json)。完整文件校验与体积：[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json)。图提供 PNG、SVG 和 PDF；端点保存最终完整几何，失败端点另保留自动融合状态及节点坐标/票数。
