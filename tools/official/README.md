# tools/official

本目录收纳正式实验阶段的推荐入口，目标是把“正式标注链”与“调试/兼容/历史链”明确分开。

## 当前入口

- ls_userscript_annotator.js：正式标注员脚本。强制记录 active_time，不提供本地停计时开关。
- ls_userscript_debug.js：调试/巡检脚本。仅供开发者或管理员使用，保留 HOHONET_DISABLE_ACTIVE_TIME 开关。
- analyze_quality_formal.py：正式分析入口。先调用上游 analyze_quality.py，再剔除兼容字段并输出 formal CSV。
- start_log_server.sh：正式日志服务启动脚本，已改为按仓库相对路径启动 cors_server.py。

## 使用原则

1. 正式标注员只使用 ls_userscript_annotator.js。
2. 调试/巡检人员才使用 ls_userscript_debug.js。
3. 正式实验主分析优先使用 analyze_quality_formal.py，而不是直接把兼容字段暴露给下游。
4. 旧版/分叉/不再推荐的脚本放入 tools/legacy/。
5. 若 export JSON 内的 data.dataset_group 唯一，analyze_quality_formal.py 会自动推断 dataset_group；只有混合导出或缺失该字段时才需要手动传 --dataset_group。

## 最小命令示例

```bash
python tools/official/analyze_quality_formal.py export_label/project-11-at-2026-03-07-17-05-1b4f93f3.json --project_version v1.0 --analysis_role performance --active-logs active_logs --output_dir analysis_results
```

如果你传入的是混合导出，或者 export 本身没有 data.dataset_group，则再补：

```bash
python tools/official/analyze_quality_formal.py export_label/mixed_export.json --dataset_group Manual_Test --project_version v1.0 --analysis_role performance --active-logs active_logs --output_dir analysis_results
```

该命令会输出：

- quality_report_formal_YYYYMMDD.csv
- reliability_report_formal_YYYYMMDD.csv（若上游产生）
- formal_analysis_manifest_YYYYMMDD.json

manifest 现在还会记录：

- dataset_group 是自动推断还是 CLI 指定
- export 内的 project_ids / dataset_groups / task_count / annotation_count

## 关于 ls_userscript_updated.js

它不是“默认给调试人员、不计时”的正式约定版本。它已归档到 tools/legacy/ls_userscript_updated.js，避免继续作为正式入口被误用。
