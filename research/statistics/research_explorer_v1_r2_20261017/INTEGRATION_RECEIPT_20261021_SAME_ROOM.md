# 同房独立补算研究台接入回执（2026-10-21）

## 来源与交付范围

- 分支：`research/same-room-review-workbench-20261021`，面向 `main` 提交PR，包含PR #19的41个新增文件。
- 固定源提交：`e83286b7814afc614253aa392050e9a3851ae058`；源包：[同房独立补算](../../same_room/same_room_independent_followup_20261021/README.md)。
- main基线：`51b519f943b2dd3a4fb2f0198133ac5dd17209ab`；合并提交：`7093d1b3`，无冲突。
- UTF-8提交：`d19e169e`；CATALOG提交：`dce723c3`。登记ID为`same_room_independent_followup_20261021_v1`，版本为`research_catalog_20261021_v23_same_room_review`。
- 展示合同：[SAME_ROOM_REVIEW_INTERFACE_20261021.json](SAME_ROOM_REVIEW_INTERFACE_20261021.json)；入口：[同房独立补算 · 10/21](index.html#module=same_room_review)。

## 实测验证

- 基线pytest：8 passed、1 skipped（首次尚无生成的人员结果载荷）；基线构建121表。
- PR原有测试：12 passed。
- 最终定向pytest：26 passed，无跳过。包括研究台、同房接口、校准、人数选择、人员载荷和分类修正六份测试。
- Python缺失的scikit-learn及依赖仅安装于临时目录`/tmp/same-room-review-test-deps`，以`PYTHONPATH`注入测试；仓库依赖文件和研究脚本逻辑未改。
- Node：workbench-core、personnel-results、taxonomy-ui、research-comparison、research-evidence五项通过；research-evidence含12个子测试。
- taxonomy-ui使用临时运行器将`require('playwright')`指向本机已有的`playwright-core`，实际执行原测试源码与断言，浏览器为已安装的Microsoft Edge；没有安装新Playwright。
- 最终构建：`raw_records=10439, images=261, quality_records=7302, retained_people=60, tables=134`。
- 结构校验：`STRUCTURE OK: tables=134, review=13, sections=9`；13/13表的行数、列名顺序和来源路径与源CSV一致，所有表均有分片，概览链接均可解析。
- `index.json`、`overview.json`、`v2-resources/index.json`快照均为`v2_integrated_analysis_20261019`；`data_release=v2`。
- `browser_check: passed`。Edge离线打开新增模块，逐一点击全部13个页签，内容就绪，无pageerror，禁用fetch后仍可读取本地脚本分片；原分类成员与A2修正页签回归通过。浏览器测试后关闭，无常驻服务。
- 保留入口HTML既有CRLF；使用`git -c core.whitespace=cr-at-eol diff --check`检查空白。

复验Python命令（仓库根）：

```bash
PYTHONPATH=/tmp/same-room-review-test-deps /Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python -m pytest tests/test_research_workbench_v2_20261019.py tests/test_same_room_review_workbench_20261021.py tests/test_same_room_calibration_review_20261021.py tests/test_same_room_stopping_review_20261021.py tests/test_workbench_personnel_results_20261021.py tests/test_personnel_taxonomy_corrections_20261021.py -q
python -m tools.thesis_main.analysis.build_research_workbench_v2_20261019
```

临时依赖目录不随仓库分发；其它环境可在已有研究依赖环境中运行同一pytest清单。

## 13表核对

|表ID|源文件（相对源包）|实测行数|
|---|---|---:|
|`same_room_review__calibration_summary`|`calibration/summary.csv`|252|
|`same_room_review__calibration_support`|`calibration/support_checks.csv`|6|
|`same_room_review__calibration_buildings`|`calibration/building_metrics.csv`|1624|
|`same_room_review__calibration_paired`|`calibration/paired_building_comparisons.csv`|232|
|`same_room_review__calibration_lobo`|`calibration/leave_one_building_out_sensitivity.csv`|232|
|`same_room_review__structure_summary`|`structure/summary.csv`|8|
|`same_room_review__structure_buildings`|`structure/building_errors.csv`|56|
|`same_room_review__structure_images`|`structure/image_errors.csv`|352|
|`same_room_review__stopping_summary`|`stopping/summary.csv`|1008|
|`same_room_review__stopping_pareto`|`stopping/pareto.csv`|504|
|`same_room_review__stopping_groups`|`stopping/group_summary.csv`|3360|
|`same_room_review__stopping_d10_summary`|`stopping/d10_sensitivity/summary.csv`|1008|
|`same_room_review__stopping_d10_pareto`|`stopping/d10_sensitivity/pareto.csv`|504|

## 未改项与限制

只读接入保存结果，没有运行校准、人数选择、结构或原生融合全量研究脚本。PR #19原有41文件中，38份文件逐一与固定源提交blob哈希一致；其余三份仅为源包README及两个脚本的显式读取编码。CSV、研究JSON、PNG和gzip数据原样保留。

评分、资格、参考、标签、N1、GT、原答、排名、snapshot_id及融合均未改。G015继续使用现有GT；Manual为主、OOS排除、门洞单列。within-2均值收益不代表低尾或完整率统一改善；Pro 47.1MiB包、新团队及33,953次求值仍未复现。大表、压缩明细和case_manifest留在源包，未展开接入。

生成的`v2-data/`、`v2-resources/`仅本地使用，不提交；两个旧未跟踪残留目录保留且不暂存。没有更改origin URL、全局Git配置、dataset-config.js或CSS。推送按需使用单次SSH重写及禁用LFS hook，不自动合并或关闭PR #19。

用户已明确授权额外修改`research-comparison.test.cjs`，将历史87表断言更新为本次134表验收。其余接入文件保持交接文档允许范围。最终推送结果、提交与新PR地址由完成回报给出；新PR合并后可另行关闭#19。

## 接入改动文件

原PR #19的41文件随分支保留，以下列出本次接入新增或修改的17文件：

- 修改：`"docs/thesis_main/\345\233\233\347\272\277\347\250\213\346\210\220\346\236\234\344\270\216\350\256\272\346\226\207\344\270\273\347\272\277\346\240\270\345\257\271_20261015.md"`
- 修改：`"docs/thesis_main/topics/same_room/\345\220\214\346\210\277\351\242\204\346\265\213\347\240\224\347\251\266\350\256\241\345\210\222_\345\244\232\350\247\206\350\247\222\345\216\206\345\217\262\344\270\216\344\272\272\345\221\230\351\207\215\346\224\276_20261019.md"`
- 修改：`RESEARCH_ANALYSIS_INDEX.md`
- 修改：`docs/README_INDEX.md`
- 修改：`research/catalog/CATALOG.json`
- 修改：`research/same_room/same_room_independent_followup_20261021/README.md`
- 修改：`research/statistics/research_explorer_v1_r2_20261017/COVERAGE.md`
- 新增：`research/statistics/research_explorer_v1_r2_20261017/INTEGRATION_RECEIPT_20261021_SAME_ROOM.md`
- 修改：`research/statistics/research_explorer_v1_r2_20261017/README.md`
- 新增：`research/statistics/research_explorer_v1_r2_20261017/SAME_ROOM_REVIEW_INTERFACE_20261021.json`
- 修改：`research/statistics/research_explorer_v1_r2_20261017/index.html`
- 修改：`research/statistics/research_explorer_v1_r2_20261017/research-comparison.test.cjs`
- 修改：`research/statistics/research_explorer_v1_r2_20261017/workbench.js`
- 新增：`tests/test_same_room_review_workbench_20261021.py`
- 修改：`tools/thesis_main/analysis/build_research_workbench_v2_20261019.py`
- 修改：`tools/thesis_main/analysis/same_room_calibration_review_20261021.py`
- 修改：`tools/thesis_main/analysis/same_room_stopping_review_20261021.py`
