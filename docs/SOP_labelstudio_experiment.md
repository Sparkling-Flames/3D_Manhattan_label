# Label Studio 标注 SOP（Pilot / PreScreen）

这份 SOP 只覆盖当前要跑的两段：`Pilot` 和 `PreScreen / P1`。  
`Calibration` 和 `Main` 以后另有 SOP，这里不再沿用旧的 5 项目写法。

## 0. 先认清当前主线

当前 thesis-facing 主线是：

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

这份文档目前只管前两段。

如果你手头还看到旧项目名：

- `Manual_Test`
- `SemiAuto_Test`
- `calibration_manual`
- `validation_manual`
- `validation_semi`

就把它们当成 legacy 记法，不要再拿来当当前主 SOP。

## 1. 进入 Label Studio 前先核对

- 界面 XML：使用同一份 [label_studio_view_config.xml](label_studio_view_config.xml)。
- 分析模式：后续正式分析统一用 `--quality_mode v2`。
- 如果这轮需要 active log，就先把浏览器脚本装好，并确认能写入 `active_logs/`。

当前页面里应能看到的核心字段是：

- `scope`：必填，决定是否进主指标
- `difficulty`：多选，解释这张图为什么难
- `model_issue`：只在 `semi` 任务里填

## 2. 这一轮会看到哪些任务

### 2.1 Pilot

Pilot 只做流程验证，不做最终结论。

你要看的是：

- 导入/导出有没有 schema 问题
- `quality_report` 能不能正常生成
- 3D 视图和审计包能不能正常落地

### 2.2 PreScreen / P1

PreScreen 是正式 Stage 1 的第一轮。

这一轮固定分三池：

- `PreScreen_manual`
- `PreScreen_semi`
- `PreScreen_oos`

当前冻结对照值是：

- `PreScreen_manual = 30`
- `PreScreen_semi = 18`
- `PreScreen_oos = 9`

这几个数是对照值，不是让你临时改规则。

## 3. 导入任务

### 3.1 Pilot

Pilot 直接用你这次试跑的导出 JSON。

常见形式是：

- `export_label/pilot_YYYYMMDD.json`

如果这轮有日志，就把 `active_logs/` 一起准备好。

### 3.2 PreScreen

PreScreen 这一轮，导入要和当前冻结文件对齐：

- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_manual_import_v2.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_import_v2.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_import_summary_v4.json`

如果你之后跑的是新一轮，就把文件名替换成这次实际导出的版本。

导入后先核对：

- `manual` 里不要有 prediction
- `semi` 里应该有 prediction
- `oos` 先看 `scope`，不要把它硬塞进几何主指标

## 4. 标注规则

### 4.1 只标主房间

只标相机所在的主房间，不跨门洞，不并房。

### 4.2 `scope`

`scope` 必填，先判断它。

- `In-scope`：能稳定闭合当前主房间
- `OOS`：几何假设不成立、边界不可判定、错层/多平面、证据不足

门洞规则很简单：

- 门框和墙垛清楚，就停在门框处
- 真的没有停止点、必须靠猜才闭合，就选 OOS

### 4.3 `difficulty`

`difficulty` 用来说明为什么难标，不是用来决定是否 OOS。

常见情况：

- 遮挡
- 低纹理
- 拼接缝
- 反光
- 画质差或被遮罩影响
- 调整后 3D 仍不佳

### 4.4 `model_issue`

`model_issue` 只在 `semi` 任务里填。

如果初始化还不错，只改真正有问题的地方就行，不用整张重画。

常见问题包括：

- 跨门扩张
- 漏标
- 角点漂移
- 角点重复
- 配对异常
- 预标注失效

## 5. 导出

每个项目完成后都单独导出一次 JSON。

文件名建议带项目名和日期，例如：

- `export_label/pilot_YYYYMMDD.json`
- `export_label/prescreen_manual_YYYYMMDD.json`
- `export_label/prescreen_semi_YYYYMMDD.json`
- `export_label/prescreen_oos_YYYYMMDD.json`

导出时要确认：

- 任务数对得上
- `annotations` 没少
- `predictions` 的保留情况和项目类型一致

## 6. 分析、查看和保存

这部分按 [analysis_results/README.md](../analysis_results/README.md) 的口径来。

### 6.1 怎么存

- 原始导出放 `export_label/`
- 日志放 `active_logs/`
- 分析输出放 `analysis_results/<round_tag>/`
- 可视化审计包放 `analysis_results/experiment_visual_audit/<round_tag>/`
- 旧结果、示例结果、试跑结果放 `analysis_results/legacy/<tag>/`

不要把新结果散到根目录。

### 6.2 怎么看

先看正式分析，再看审计包：

- `quality_report_*.csv`
- `reliability_report_*.csv`
- `active_log_audit_summary.json`
- `active_log_audit_per_file.csv`
- `SUMMARY.md`
- `summary.json`
- `table_schema_alignment.csv`
- `table_field_audit.csv`
- `table_active_time_row_audit.csv`

Pilot 先看：

- 导入量是不是对得上
- `quality_report` 能不能落地
- 图表和审计包有没有缺文件

PreScreen 再看：

- `PreScreen_manual / PreScreen_semi / PreScreen_oos` 的行数是不是对得上
- 合规字段有没有按正式口径落到 `quality_report`
- active log 里有没有大量缺失、unknown 或 multi-session 问题

### 6.3 正式分析入口

Pilot 示例：

```bash
python tools/analyze_quality.py export_label/pilot_YYYYMMDD.json \
  --dataset_group Pilot_Manual \
  --project_version pilot_YYYYMMDD \
  --output_dir analysis_results/pilot_YYYYMMDD \
  --output analysis_results/pilot_YYYYMMDD/quality_report_YYYYMMDD.csv \
  --metric corner \
  --quality_mode v2
```

PreScreen 示例：

```bash
python tools/analyze_quality.py export_label/stage1_prescreen_manual_YYYYMMDD.json \
  --dataset_group PreScreen_manual \
  --project_version stage1_YYYYMMDD \
  --output_dir analysis_results/prescreen_YYYYMMDD \
  --output analysis_results/prescreen_YYYYMMDD/quality_report_YYYYMMDD.csv \
  --metric corner \
  --quality_mode v2

python tools/analyze_quality.py export_label/stage1_prescreen_semi_YYYYMMDD.json \
  --dataset_group PreScreen_semi \
  --project_version stage1_YYYYMMDD \
  --output_dir analysis_results/prescreen_YYYYMMDD \
  --output analysis_results/prescreen_YYYYMMDD/quality_report_YYYYMMDD.csv \
  --append \
  --metric corner \
  --quality_mode v2

python tools/analyze_quality.py export_label/stage1_prescreen_oos_YYYYMMDD.json \
  --dataset_group PreScreen_oos \
  --project_version stage1_YYYYMMDD \
  --output_dir analysis_results/prescreen_YYYYMMDD \
  --output analysis_results/prescreen_YYYYMMDD/quality_report_YYYYMMDD.csv \
  --append \
  --metric corner \
  --quality_mode v2
```

如果这轮有日志，就在命令里加上：

```bash
--active-logs active_logs
```

## 7. active log 审计

如果这批数据有 active logs，就单独跑一次：

```bash
python tools/audit_active_log_quality.py active_logs \
  --summary-json analysis_results/prescreen_YYYYMMDD/active_log_audit_summary.json \
  --per-file-csv analysis_results/prescreen_YYYYMMDD/active_log_audit_per_file.csv
```

重点看这些：

- `parse_error_count`
- `unknown_task_count`
- `unknown_annotator_count`
- `unknown_project_count`
- `unknown_session_count`
- `missing_script_version_count`
- `multi_session_pair_count`

## 8. 可视化审计包

如果你想每次都保留一份实验级图表包，就再跑：

```bash
python tools/build_experiment_visual_audit.py \
  --quality-csv analysis_results/prescreen_YYYYMMDD/quality_report_YYYYMMDD.csv \
  --out-dir analysis_results/experiment_visual_audit \
  --tag prescreen_YYYYMMDD \
  --active-log-summary-json analysis_results/prescreen_YYYYMMDD/active_log_audit_summary.json \
  --active-log-per-file-csv analysis_results/prescreen_YYYYMMDD/active_log_audit_per_file.csv
```

这一步主要看：

- `SUMMARY.md`
- `summary.json`
- `table_schema_alignment.csv`
- `table_field_audit.csv`
- `table_active_time_row_audit.csv`

## 9. 常见问题

- 看不到 3D 窗口：先检查浏览器脚本，再刷新页面。
- `semi` 里没有 prediction：先检查导入文件是不是导错了。
- `OOS` 混进主指标：先停，别继续往后堆结果。
- active time 全是 0：说明日志链路没通，先查脚本和服务。

## 10. 什么时候跑测试

如果你改了分析脚本，就跑：

```bash
pytest tests/test_audit_active_log_quality.py tests/test_build_experiment_visual_audit.py -q
```

如果你改了更靠后的分析逻辑，再补：

```bash
pytest tests/test_analyze_stage_aware.py -q
```

如果只是跑数据、没改代码，这组测试不是每次都必须跑。
