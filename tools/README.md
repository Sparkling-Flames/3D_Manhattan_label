# tools 目录索引

本目录按论文线和共享运行层拆分。根目录不再保留旧脚本 wrapper；所有 CLI 和 import 都应直接使用下列新路径。

## 目录边界

- `tools/thesis_main/`
  - 论文主线工具。
  - `analysis/`：质量分析、active-time audit、stage-aware 分析、图表与汇总。
  - `registry/`：registry、manifest、freeze、final-gold、trap/materialization、risk-rule、`d_t/g_t` dry-run 和 export inventory。
  - `data_prep/`：数据集准备和 MP3D smoke/import 生成。
  - `tools/thesis_main/tools/thesis_main/foreign_recruitment/`：P1/PreScreen 外国标注员 HTTPS 英文适配包。
- `tools/paper_a_manhattan/`
  - Paper A Manhattan / sandbox / expert review / post-hoc audit-only 工具。
  - `dev_only/`：Manhattan sandbox userscripts，只用于专家侧或开发侧沙盒。
- `tools/paper_b/`
  - Paper B 相关工具。当前包括 `validate_b0_relabel_audit.py`。
- `tools/label_studio/`
  - 三条线共享的 Label Studio 配置、viewer、server、COS/upload、import/build helper 和 `official/` 运行入口。
  - 仓库源码在本目录；云服务器运行时 URL `/tools/vis_3d.html` 继续作为部署兼容路径保留。
- 保持不动：`tools/legacy/`、`tools/legacy_server/`、`tools/backups/`。

## 常用入口

```bash
python tools/thesis_main/analysis/analyze_quality.py export_label/project-export.json --output_dir analysis_results
python tools/thesis_main/analysis/audit_active_log_quality.py active_logs --summary-json analysis_results/active_log_audit_summary.json
python tools/thesis_main/analysis/aggregate_analysis.py --csv main:analysis_results/quality_report.csv --output-dir analysis_results

python tools/thesis_main/registry/build_registry_suite.py --help
python tools/thesis_main/registry/compute_dt_score.py --help
python tools/thesis_main/registry/compute_g_t_diagnostics.py --help

python tools/label_studio/prepare_labelstudio_docker.py --help
python tools/label_studio/build_stage1_prescreen_imports.py --help
python tools/label_studio/cors_server.py

python tools/paper_a_manhattan/render_manhattan_geometry_review_sheet.py --help
python tools/paper_a_manhattan/summarize_manhattan_geometry_manual_review.py --help
python tools/paper_b/validate_b0_relabel_audit.py --help
```

## Python imports

```python
from tools.thesis_main.analysis.analyze_quality import extract_data
from tools.thesis_main.registry.compute_dt_score import DtScoreComputer
from tools.label_studio.build_stage1_prescreen_imports import build_import_payloads
from tools.paper_a_manhattan.manhattan_constrained_fit import fit_manhattan_layout
from tools.paper_a_manhattan.manhattan_candidate_gate import gate_manhattan_candidate
from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state
from tools.paper_a_manhattan.manhattan_pair_assist import propose_align_pair_x
from tools.paper_b.validate_b0_relabel_audit import validate_csv
```

## 边界

- 不从 `tools/` 根目录 import 脚本模块。
- 不把 Paper A Manhattan 工具接入正式 routing、formal `g_t`、worker tier 或 Label Studio 正式 UI。
- 不把 Paper B 训练、审计、cue、bilayout 工具回流到主线目录。
- 不写 `export_label/`；该目录仍是 Label Studio 运行时导出真源。
- 不改变 protocol、schema、routing 或 SOP 语义；本次迁移只改变源码组织和引用路径。
