# 信息价值与比较政策研究（D → E，附 E2 后验核查）

建议先读 ROUND_D_ZH.md、ROUND_E_ZH.md、ROUND_E2_POSTAUDIT_ZH.md。

D 是全 259 研究图入口的数值研究：2181 个合格入口原答/226 图/22 建筑，2565 个明确版本参考比较；并非旧报告 49 图切片。E 先测试旧固定候选，再原样接入第 C 轮新连续拟合。E2 是终稿复核发现下界遗漏后的后验扩展，原四项结果未被覆盖。

主要结论：三维没有新增原始观测，但可补充压缩标量的空间误差含义。C 候选中，上下角与底边三维都在指定变化容差内时，墙顶三维另阻止 2 次改变。最初四项 97 次提议在补足下界保护后为六项 92 次；这不是 92 份人审通过的布局。

## 输入与依赖

Python 3，numpy、scipy、pandas、shapely、matplotlib。没有网络调用或源码写入。

需要三个只读目录：

1. --source：原 quality_deep_20261007 目录，包含 src/、vendor/、inputs/、results/
2. --expanded：扩展原包目录，包含 current/panel.json
3. --density：本轮 density_study 目录，包含 round_c_reference_comparisons.csv、round_c_fit_status.csv、round_c_inputs.json、round_c_fit_artifacts.json

输出用 --out 指定。默认路径相对于当前这套研究目录组织；所有输入/输出也支持显式路径，不依赖特定工作区绝对地址。

完整复算示例（路径替换成实际位置）：

```bash
bash reproduce_information.sh \
  --source /path/to/quality_deep_20261007 \
  --expanded /path/to/expanded_input \
  --density /path/to/density_study \
  --out /path/to/recomputed_information
```

脚本顺序：round_d.py → summarize_d.py → round_e.py → summarize_e.py → verify_e.py → postaudit_e2.py → verify_e2.py → render_figures.py → test_policy.py。

单步同样接受上述参数，例如：

```bash
python round_e.py --source /path/to/quality_deep_20261007 \
  --expanded /path/to/expanded_input --density /path/to/density_study \
  --out /path/to/recomputed_information
```

E 需要同一输出目录中先有 D_full_panel_metrics.csv。--help 列出路径参数。图件只是从实际控制/指标渲染，不需要原图 PNG；没有声称看过未打开的原图。

## 关键文件

- D_full_panel_metrics.csv：全资格入口、原/修参考、源/参考单独 NA 状态
- D_controls.csv / D_control_geometries.json：可追溯控制与完整生成点
- D_independent_recomputation.csv：22 建筑独立数值核
- D_actual_same_floor_pairs.csv / D_actual_matched_pairs.csv：真实作答反例与零匹配负结果
- E_experiment_definition.json：原冻结权重、两档容差与停止条件
- E_policy_decisions.csv / E_policy_summary.csv：逐建议与分母
- E_common_domain_summary.csv：相同可比较域，避免拿覆盖变化当收益
- E_lobo_calibration_scales.csv / E_building_heldout_results.csv：楼外尺度与结果，非语义质量概率
- E_independent_incremental_cases.csv：三例墙顶增量的独立重算
- E2_lower_boundary_summary.csv / E2_independent_lower_checks.csv：后验下界扩展及核验
- E_reference_policy_reversals.csv / E2_reference_reversals.csv：原/修政策敏感性
- E_named_local_comparisons.csv：具名隔墙/壁炉观察，非新局部 GT
- acceptance_checks.json：编译、表行数、核心选择数与重算门限核验

所有失败/NA 保留；不把 unknown 当 0。源数据、原资格、原环、现有融合及票权不变。计算三维不等于知道人员是否看过三维界面。
