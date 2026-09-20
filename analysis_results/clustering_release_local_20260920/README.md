# 本地统一计算与16图审核

本轮为工作候选，尚未通过用户最终视觉验收。运行说明见仓库 `docs/thesis_main/分簇工作版_统一数据入口_20260920.md`。

云端包解压后，在解压根目录运行：

```sh
python -X utf8 -B -m tools.thesis_main.analysis.clustering_release --run-root study
```

依赖 Python、numpy、pandas、scipy、scikit-learn。无需原始导出、日志或本机绝对路径；原路径仅用于追溯，不用于复算。请先读 PRO_TASK.md。study/input/source 是旧证据快照，当前计算入口严格使用 study/inputs，禁止把旧点集与新版距离混用。

历史2,501份身份不变；原始奇数点已人工确认复原的作答按有效点集计算。主候选2,381份，已排除113份，非排除但不可计算7份。结果目录的 CONFIRMED_ODD_REPAIR_AUDIT.json 逐份列明补删点与实际计算资格。

本地 review/ 为独立审核页，复用 Studio foundation，用户答案默认空白。visual_review/ 中JSON是AI意见和覆盖记录，图片叠加仅留本地；云端不得把文字观察提升为人工裁决。AI意见来自修复前RC1选定点集，此16图不包含本次变更的rPc-22。

软件拆批试验不代表新增480份已完成；新时间未冻结，不进入时间分析。最终正式发布仍待人工裁决、真实新导出和日志审计。
