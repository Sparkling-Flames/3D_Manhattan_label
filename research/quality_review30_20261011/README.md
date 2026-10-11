# 30份唯一标注的选样交付（主审私有）

已冻结候选清单，先供dot主线程审核。**不是最后用户审核包；未生成最终叠线、页面、回执或人工答案。**

- [30份完整清单与覆盖/缺口](research/COVERAGE_AND_GAPS.md)
- [30行直接可审CSV](results/selection_private.csv)
- [完整私有来源和五原方案数值](results/selection_private.json)
- [边界覆盖及实际距离](results/boundary_coverage_private.json)
- [24张原字节照片](results/selected_original_photos_private.zip)
- [选定几何及6份待顶界B底面](results/selected_geometry_private.json)
- [真实像素观察及适用性疑点](results/pixel_audit_private.json)
- [去重、留出、字节重跑和原照片哈希检查](results/selection_checks.json)
- [数值初筛规则](research/SELECTION_RULES_V1.md)

24质量+6空间，30个不同record_id和object_id；24图，质量12个房间分组。907质量开发池/83图，冻结282留出无交集。已合入main `9c1d91173bf8ec50de4983daaff325b339965e04`，不推main。旧8例不修改。

Q95/85/50两侧真实最近邻全部覆盖。D20/F8上侧缺失、受控F6上侧缺失；F7.640835例仅混合诊断。补充Q90/60和Q75上侧缺紧邻；照片语义适用性仍归主审终审。全空间B仍top_pending，不造完整GT/Q，连续量与不确定性保留，不能用最高Q指定目标。

运行：

```bash
python code/freeze_selection.py --frozen-root /path/to/unpacked/cloud_compute --photo-root /path/to/original/assets --out /path/to/new_results
```

输入来自既有[完整云端计算工件](../quality_cloud_compute_20261011/README.md)。24原图可解压本目录ZIP，以originals为photo-root。冻结入口重跑四项选样文件逐字节相同。包照片脚本另支持--frozen-root、--photo-root、--out-root；不涉及最终用户渲染。本文目录完全是新增研究适配，不修改Pro原件或其许可证。

私有工件包含人员、分数和阈值导向理由，禁止整包作为用户盲评文件。阈值导向30份不能估计总体严重比例，不能调66组后宣称泛化成功。主审通过清单及小样后再做最后渲染和独立30份回执。
