# 独立结构质量研究交付 — 2026-10-16

先读 `REPORT.zh.md`。本包主候选为 **RCS-0.2-20261016**；它替换综合质量里的固有D分支，但仍是研究工作原型，未获胜过B8L2的确认性证据。

**范围：冻结实际几何快照 + 当前资格/参考路由。不是fresh loader完整复算；未获得LFS与263张原图；Sb/Hcenter沿用冻结值。** 详细失败日志与来源在 `PROVENANCE.json`、`results/live_loader_probe.txt`。

## 离线重现

在新虚拟环境安装requirements（依赖已安装时可直接运行）：

```bash
python -m pip install -r requirements.txt
python reproduce.py --out /absolute/path/to/NEW_replay_directory
```

输出目录必须不存在，避免覆盖历史结果。脚本会校验输入SHA-256，重算当前891和历史1145的WQ/A10/B公式、30对人工面板几何、60份ERP转换、227对当前兼容快照、新72合成控制、77参考自比，并运行67单元测试。30与227有5条当前重复；当前兼容合并为242份/32图，不是257份。2036仅是891+1145分项公式行数，两个集合并非互斥独立样本。

本包已在独立新目录执行以上入口通过。重放不重新生成所有探索网格；全部探索结果和原脚本同时保留。`src/run_experiments.py`可重做网格和描述表，但默认写包内results，建议先复制整个包到新位置。`src/run_audit.py --repo ... --out ...`用于重新读取完整交接资料的冻结源，仍不替代fresh loader。

## 版本化评分接口

```bash
python score_fixed_manifest.py --input inputs/fixed_manifest_example3.json --out NEW_scores.csv
python compare_versions.py --old results/versioned_B8L2_227.csv --new results/versioned_RCS227.csv --out NEW_comparison
```

固定manifest由上游loader/资格流程提供；评分器不选参考、不改变资格、不补缺失几何。版本比较同时匹配作答身份、条件、完整作答与参考哈希、资格版本。变化的参考和输入单列，不能把其引起的差值解释成算法改善。缺失任一有权分项返回not_evaluable而不是0误差。working_config()是0.2；Config()默认值特意保留0.1初版，不应误用。

## 关键结果

- `results/review30_working.csv`：当前RCS综合分字段`Q_RCS02`；`current_full_reference_geometry_same`标记20份当前可比；WQ/A10/B8L2/IoU3D并列。
- `results/current227_working.csv`：227份当前兼容真实作答的同参考比较，非盲审样本。
- `results/review30_working_correspondences.json`：逐事件原始成员、信用、未匹配质量的解释。
- `results/synthetic_controls.csv`：新72控制；Sb相关合成分数显式命名arc_analogue。
- `results/working_parameter_sensitivity.csv`：工作版及10种配置；不按均分或反序次数择优。
- `results/ordinal_descriptions.csv`：粗档反序描述，共享样本、曝光，不作独立配对统计。
- `results/height_subdivision_counterexample.json`：当前角点均高棱柱IoU的同几何细分依赖。
- `results/raw_feedback_audit.csv`：原始等级/评论/身份回接；23条首次揭示前有等级，7条没有，6条改变。
- `results/offline_replay_verification/`：本包最终离线重放收据。

`review30_results.csv`及`current_matched_geometry_results.csv`是初版0.1结果；工作结果中带`RCS01_`的列也属于初版保留值，不能与新版C组合解释。主报告只用`Q_RCS02`。

## 文档与图

REPORT.zh.md：结论和证据；MATHEMATICS.md：定义、参数、不变性与失败；LITERATURE.md：原始论文、作者代码与访问边界；NEXT_AUDIT.md：普通→门洞条件校准；geometry_gallery.html：无需联网的44个几何卡片。虚线参考、实线作答，图是坐标俯视图，不是263张照片的替代品。

不包含原图、字体或LFS真实源；没有更改原仓库、原始作答、参考或正式成绩。
