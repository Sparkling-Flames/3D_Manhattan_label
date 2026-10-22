# 顶部/高度机制核查

先读 `REPORT_ZH.md`。完整逐例解释在 `CONTROL_CONCLUSIONS_ZH.md`；精确输入、分量、采样对照及Hcenter位于 `results/`。

这些文件属于独立研究，不修改当前算法。70项可计算合成控制不带人工等级；1项越地平线控制保留空分。39份真实样本沿用原开发名单与固定参考，不是新独立验证。

从包含 `previous_research/` 与 `study_quality/` 的工作区根目录执行：

```bash
python top_structure_20261012/mechanisms/run_mechanisms.py --root . --out new_run/mechanisms
python top_structure_20261012/mechanisms/add_centered_components.py --root . --results new_run/mechanisms
python top_structure_20261012/mechanisms/summarize_mechanisms.py --root . --results new_run/mechanisms
python top_structure_20261012/mechanisms/verify_centered_invariants.py --root . --results new_run/mechanisms
```

`--out` / `--results` 设为新的目录以保留已有结果。第三个脚本也会在该结果目录的上一级生成中文逐例表与三张科学图。

依赖：numpy、scipy、shapely、matplotlib以及随包冻结引擎。所有数值可离线复算。

提供给固定融合端点及其他候选计算的函数：

```python
from centered_height import centered_height_components
features = centered_height_components(annotation, reference, samples=4096)
Hcenter = features['Hcenter']
```

需确保冻结 `height_revision` 模块在导入路径中，或通过 `height_module=` 显式传入该模块。输入必须为已有、经适用性与竖直配对核查的 `top3d` / `bottom3d`；函数不推断配对、参考选择、资格或人的意图。临时中心化剖面不是新的有效重建。
