# HoHoNet 纯净仓库地图（2026-03-08）

## 文档目标

这份文档只回答一件事：当前仓库里，和你现在这条服务器标注/分析链真正相关的目录、文件，各自是干什么的。

它刻意不做以下事情：

1. 不写 A/B/C 交接分工。
2. 不展开论文提纲、真源争论、阶段规划。
3. 不把旧 HoHoNet 原始深度/布局训练推理脚本混进当前地图。
4. 不把 `legacy/`、备份、试验原型当成当前入口。

## 本地图的纳入范围

本地图只覆盖当前仍应视为“在用”或“应保留认知”的内容：

1. 服务器标注运行链。
2. Label Studio 导入/导出链。
3. active time 日志链。
4. 正式分析链。
5. registry / manifest / 汇总输出链。
6. 当前仍有效的测试与说明文档。

## 本地图明确排除的内容

以下内容默认不写入“纯净地图”：

1. 根目录中原始 HoHoNet 论文时代的训练、深度推理、布局推理、语义推理、可视化脚本。
2. `tools/legacy/` 下所有旧脚本、旧 notebook、研究原型。
3. `docs/legacy/` 和各种临时审稿意见、语音整理、阶段性讨论稿。
4. 缓存、环境、历史产物目录，例如 `.venv/`、`__pycache__/`、`.pytest_cache/`。

---

## 一、你现在这条主链的总结构

当前仓库里真正构成业务闭环的是下面这几层：

1. `import_json/`：计划导入任务。
2. `tools/prepare_labelstudio_docker.py` 等脚本：生成可导入 Label Studio 的任务 JSON。
3. `tools/official/ls_userscript_annotator.js`：正式标注时浏览器端脚本。
4. `tools/cors_server.py` + `tools/official/start_log_server.sh`：接收 active time 日志。
5. `export_label/`：Label Studio 导出的运行时标注真源。
6. `tools/analyze_quality.py`：上游解析与质量计算。
7. `tools/official/analyze_quality_formal.py`：正式分析入口。
8. `tools/build_task_registry.py` + `tools/build_registry_suite.py`：planned / runtime / active log 多层 registry。
9. `analysis_results/`：所有分析结果、registry、图表、manifest 落盘目录。

---

## 二、根目录里当前真正要关心的文件/目录

### 1. 需要保留认知的根目录文件

- `README.md`
  - 项目总说明。
  - 现在更多是仓库门面，不是当前实验的唯一执行入口。

- `QUICK_START.md`
  - 当前实验链的快速上手说明。
  - 用来快速回忆导入、标注、导出、分析的大致流程。

- `README_reproduction.md`
  - 原始 HoHoNet 复现文档。
  - 保留即可，但不属于你现在的服务器标注分析主链。

- `hohonet_env.example`
  - 服务器环境变量参考模板。
  - 主要用于日志服务、部署配置等环境注入的参考。

- `nginx_fixed.conf`
  - 当前较接近可用版本的 Nginx 代理配置参考。
  - 主要服务于 `log_time` 代理和静态/同源访问链路。

- `nginx.conf.backup`
  - 历史备份配置。
  - 不是当前正式入口。

### 2. 当前真正重要的根目录目录

- `tools/`
  - 当前服务器标注、导入、分析、日志、registry 的主代码目录。

- `tools/official/`
  - 正式运行入口目录。
  - 如果一个人只想知道“正式该跑什么”，优先看这里。

- `docs/`
  - 当前有效说明文档目录。

- `export_label/`
  - Label Studio 导出 JSON 存放目录。
  - 这是运行时标注数据真源目录。

- `import_json/`
  - Label Studio 导入 JSON 存放目录。
  - 这是 planned split / planned task 侧的输入目录。

- `active_logs/`
  - active time 日志归档目录。

- `analysis_results/`
  - 所有分析 CSV、registry、图表、manifest 的输出目录。
  - 当前新增 `analysis_results/c_manifests_20260310/`，用于存放 C 线可 join 的 trap / embedding manifest 交付。

- `tests/`
  - 当前仍有效的自动化测试目录。

- `trap集/`
  - 论文人工锚点集合目录（你手工挑选的 trap 样本）。

- `data/`
  - HoHoNet 原生数据与切分目录（数据资产层）。

- `output/`
  - HoHoNet 推理产物与中间结果目录（模型输出层）。

---

## 三、`tools/` 目录纯净地图

这里按“当前主链必需”和“辅助但仍在用”分开写。

### A. 当前主链必需脚本

- `tools/analyze_quality.py`
  - 当前最核心的上游分析脚本。
  - 负责读取 Label Studio 导出 JSON，解析结构化字段，计算质量指标、门控结果、active time 合并结果，并输出质量 CSV / 可靠性 CSV。
  - `condition` 字段在这条链里是分析脚本根据 prediction presence 派生出来的，不是实验设计真源。

- `tools/build_task_registry.py`
  - 从 `import_json/` 的 split/import 文件构建 planned registry。
  - 它描述的是计划任务，不是运行时 task table。

- `tools/build_registry_suite.py`
  - registry 总装脚本。
  - 把 planned split、export runtime、active log 三类信息拼成多层 registry 和 summary/manifest。

- `tools/audit_export_inventory.py`
  - export 真源审计脚本。
  - 扫描 `export_label/` 全目录，输出每个导出的 schema 概况、pilot/formal relevance、以及 legacy exclusion 候选清单。

- `tools/create_labelstudio_split.py`
  - 把预先生成的任务集合按 seed 切成可重复的 manual / semi / calibration / validation / gold 导入集。
  - 作用是生成可复现实验分池，而不是做运行时分析。

- `tools/create_labelstudio_split_by_outline.py`
  - 按 outline 或更细的阶段设定生成导入分池。
  - 用于更接近当前论文协议的导入构造。

- `tools/prepare_labelstudio_docker.py`
  - 生成 Label Studio 可导入 JSON。
  - 把图片 URL、3D viewer URL、predictions 等组装成可直接导入标注平台的任务格式。

- `tools/prepare_dual_dataset.py`
  - 把标注结果整理成后续模型或结构化训练/评估可消费的数据格式。
  - 是“标注平台结果 → 训练/评估侧格式”的桥接脚本。

- `tools/cors_server.py`
  - 接收浏览器端 active time 上报的轻量日志服务。
  - 配合 Nginx 代理与 userscript 使用。

- `tools/split_active_logs.py`
  - 对 active log 按版本或日期做二次切分。
  - 适合把新旧服务器、不同脚本版本的日志拆出来单独分析。

- `tools/lead_time_stats.py`
  - 对比 Label Studio `lead_time` 与 active log 的统计脚本。
  - 用于检查耗时口径，不是主分析入口。

### B. 正在用的辅助脚本

- `tools/save_quality_figures.py`
  - 从质量 CSV 生成图表和摘要文件。

- `tools/viz_quality_report.py`
  - 质量报告可视化脚本。
  - 属于分析结果展示层。

- `tools/aggregate_analysis.py`
  - 聚合多个分析结果，做更高层汇总。

- `tools/benchmark_cost.py`
  - 成本/效率相关的辅助分析脚本。

- `tools/diagnose_gating_bias.py`
  - 检查门控规则是否引入偏差或异常筛除现象。

- `tools/meta_label_guard.py`
  - 对导出的结构化元标签做合规检查。
  - 用来兜底防止字段互斥冲突或缺失问题漏过前端拦截。

- `tools/label_studio_view_config.xml`
  - 当前主用的 Label Studio 标注界面配置。
  - 结构化字段、alias、required 规则都在这里定义。

- `tools/label_studio_view_config_manual.xml`
  - 手工集或特定条件下使用的界面配置变体。

- `tools/ls_userscript.js`
  - 通用 userscript 版本。
  - 当前正式入口已经迁到 `tools/official/`，这个文件更像共享/过渡版本，不建议作为正式运行入口直接引用。

- `tools/ls_3d_logic.js`
  - 3D 视图交互逻辑辅助文件。

- `tools/vis_3d.html`
  - 标注时使用的 3D 预览页面。

- `tools/three.min.js`
  - 3D 预览依赖库。

- `tools/OrbitControls.js`
  - 3D 预览交互控制依赖。

- `tools/prepare_labelstudio_docker.py`
  - 同时也是服务器导入准备脚本，会生成带服务端 URL 的任务 JSON。

- `tools/sync_img_v_to_cos.py`
  - 把图片版本或资源同步到 COS。

- `tools/upload_mp3d_test_to_cos.py`
  - 上传 MP3D 测试集到 COS。

### C. 当前目录里不应写入纯净地图的内容

- `tools/legacy/`
  - 历史脚本、旧 notebook、旧 userscript、旧可视化、研究原型。
  - 一律不当作当前入口。

- `tools/legacy_server/`
  - 旧服务器链路目录。
  - 不是当前正式运行入口。

- `tools/visualize_output.ipynb`
  - 旧版结果展示 notebook。
  - 仍可参考，但不宜作为当前正式主入口写进纯净地图。

- `tools/visualize_output_v2.ipynb`
  - 展示层 notebook。
  - 不是当前核心产线入口，最多算分析后的辅助查看。

---

## 四、`tools/official/` 目录纯净地图

这个目录是“正式运行入口”，优先级高于 `tools/` 其他同类脚本。

- `tools/official/analyze_quality_formal.py`
  - 正式分析入口。
  - 会先调用上游 `tools/analyze_quality.py`，再做 formal 口径过滤，输出正式 CSV 和 formal manifest。
  - 适合真正用于论文或正式实验汇总的那版分析。

- `tools/official/ls_userscript_annotator.js`
  - 正式标注员脚本。
  - 默认记录 active time，不提供“本地停计时”的宽松开关。

- `tools/official/ls_userscript_debug.js`
  - 调试/巡检脚本。
  - 只给开发者或管理员做排查，不是正式标注入口。

- `tools/official/start_log_server.sh`
  - 正式日志服务启动脚本。
  - 负责读取环境变量、清理旧进程并启动 `tools/cors_server.py`。

- `tools/official/README.md`
  - 正式入口目录说明。
  - 想查“正式该用哪个脚本”时，优先看它。

---

## 五、`export_label/` 目录纯净地图

这个目录只放 Label Studio 导出 JSON。

### 当前目录中需要知道的文件类型

- `project-11-at-2026-03-07-17-05-1b4f93f3.json`
  - 2026-03-07 新服务器下的半自动集测试导出。
  - 属于新字段条件下的单图测试样本。

- `project-12-at-2026-03-07-17-05-72d96094.json`
  - 2026-03-07 新服务器下的手工集测试导出。
  - 同样属于新字段条件下的单图测试样本。

- 其余 `project-*.json`
  - 基本都属于旧导出。
  - 旧导出里有少量更老 schema 的记录，其中你已确认大约有 7 条是更旧字段，当前 `analyze_quality.py` 不应默认假设能无损兼容它们。

- `test1.json`
  - 测试导出文件。
  - 更接近临时检查用途，不应默认混入正式分析。

### 当前目录的职责边界

1. 这里是运行时标注数据真源目录。
2. 它记录“实际发生了什么”，不是 planned split 真源。
3. 旧导出与新导出不能在不标注 schema 差异的情况下直接混讲。
4. 当前仓库里的这些导出按现状都应视为 pilot / 流程验证 / 兼容审计输入，而不是未来正式主结论的直接样本池。

---

## 六、`import_json/` 目录纯净地图

这个目录放 planned import 侧文件，而不是 export 结果。

- `import_json/outline_v2_seed20260228/`
  - 当前最关键的一组分池输入。
  - 这里面是按 seed 和 outline 冻结后的导入任务集合及 split report。

- `import_json/label_studio_import_docker.json`
  - 直接可供 Label Studio 导入的任务 JSON。
  - 通常由导入准备脚本生成或更新。

- `import_json/legacy/`
  - 历史导入文件。
  - 不应作为当前实验主入口。

### 目录职责边界

1. 这里描述的是 planned split / planned task。
2. 它和 `export_label/` 不是一回事。
3. runtime task id 需要后续 join，不是在这里天然存在。

---

## 七、`active_logs/` 目录纯净地图

这个目录保存 active time 日志与说明。

- `active_logs/readme.md`
  - active log 的默认写入位置、本地归档方式、旧/新服务器目录约定说明。

- `active_logs/active_logs/active_times_YYYY-MM-DD.jsonl`
  - 按天滚动的 active time 原始日志。
  - 这是浏览器脚本 + `cors_server.py` 链路真正落盘的原始记录。

### 这个目录里的字段语义

1. active time 来自浏览器活动上报，优先级高于 Label Studio `lead_time`。
2. 如果任务没有 active log 命中，分析时才会退回 `lead_time`。
3. `lead_time` 是 fallback，不够精确，不能和 active log 无来源区分地混成一列解释。

---

## 八、`analysis_results/` 目录纯净地图

这个目录是所有分析产物的落盘区，不是代码目录。

### 当前最需要知道的子目录

- `analysis_results/registry_20260308/`
  - 当前 A 线 registry 主要输出目录。
  - 会包含 task / annotation / compat / active_time / merged_all / summary / manifest 等文件。

- `analysis_results/registry_20260308_march7_check/`
  - 针对 3 月 7 日新服务器样本的专项检查输出。

- `analysis_results/rerun_20260308/`
  - 某次 rerun 的分析结果目录。
  - 其中旧 filtered export 不包含 3 月 7 日新服务器样本。

- `analysis_results/figures/`
  - 分析图表输出目录。

- `analysis_results/formal_march7_check/`
  - 3 月 7 日正式口径检查相关输出。

- `analysis_results/export_inventory_20260309/`
  - export 真源审计输出目录。
  - 包含 `export_inventory_v1.csv`、`export_inventory_summary_v1.json` 与 `legacy_annotation_audit_v1.csv`。

### 目录职责边界

1. 这里是输出，不是唯一真源。
2. `merged_all` 属于 join 产物，不等于底层 planned/runtime 真源本身。
3. registry、manifest、summary 需要与输入源一并解释。

### 当前新增的 C 线 manifest 包

- `analysis_results/c_manifests_20260310/trap_manifest_schema_v1.json`
  - C 线当前 semi trap manifest 的 schema contract。
- `analysis_results/c_manifests_20260310/natural_failure_bank_index_v1.csv`
  - 基于人工复核总表和 A 线 task registry 整理出的自然案例 bank index。
- `analysis_results/c_manifests_20260310/embedding_ood_protocol_v1.json`
  - 当前 `d_t` / `I_t_OOD` procedure 的冻结 manifest。
- `analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv`
  - `PreScreen_semi` trap 草案，显式区分 natural realized rows 与 synthetic frozen-rule rows。

---

## 九、`trap集/` 目录纯净地图

这是你用于论文人工锚点筛选的样本集合目录，属于人工审计与难例归档资产。

- `trap集/readme.md`
  - 目录结构的最小约定：每个 task 应包含原图、模型标注图、对应角点 txt。

- `trap集/manual/`
  - 手工集 trap 子集。
  - 按失效现象细分为 `拼接缝及拉伸/`、`玻璃/`、`遮挡明显/`、`遮罩/`、`非常简单/`。

- `trap集/semi/`
  - 半自动集 trap 子集。
  - 按模型问题细分为 `拓扑崩溃/`、`模型预标注失败/`、`漏标/`、`角点重复/`、`角点错位/`、`跨门扩张/`、`过度解析/`、`模型标注质量好/`。

- `trap集/OOS/`
  - OOS trap 子集。
  - 按 OOS 成因细分为 `几何假设不成立(弧形墙)/`、`证据不足/`、`边界不可判定/`、`错层,天花板下凸/`。

- `trap集/复核总表_20260307.md`
  - trap 复核汇总记录（人工复核追踪）。
  - 当前已被整理为 `analysis_results/c_manifests_20260310/natural_failure_bank_index_v1.csv` 的上游人工依据之一。

---

## 十、`data/` 目录纯净地图

`data/` 是 HoHoNet 原生数据资产目录，虽然不属于你当前主分析入口脚本，但必须在仓库地图里保留职责说明。

- `data/mp3d_layout/`
  - Matterport3D 布局数据主目录。
  - 子目录 `img_v/`、`train/`、`valid/`、`test/` 与 `*_no_occ/` 版本用于训练/验证/测试与无遮挡变体。

- `data/mp3d_train.txt`
  - MP3D 训练集切分索引。

- `data/mp3d_val.txt`
  - MP3D 验证集切分索引。

- `data/mp3d_test.txt`
  - MP3D 测试集切分索引。

- `data/noniid_splits/`
  - 非 IID 切分结果与配置（实验切分资产）。

- `data/s2d3d_sem/`
  - S2D3D 语义任务相关数据。

- `data/stanford2D3D/`
  - Stanford2D3D 数据目录。

- `data/json2txt.py`
  - 数据格式转换脚本（json -> txt）。

- `data/datasplit.py`
  - 数据切分辅助脚本。

---

## 十一、`output/` 目录纯净地图

`output/` 是模型输出与中间结果目录，属于“产物层”。

- `output/mp3d_layout/`
  - MP3D 布局推理输出主目录。

- `output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/`
  - 一组具体模型配置的布局输出。

- `output/mp3d_layout_layout/`
  - 布局输出的历史/并行目录（与主输出目录并存）。

- `output/mp3d_layout_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34_ep350/`
  - 指定 epoch 版本输出。

- `output/layout_json/`
  - 单任务/单图布局 JSON 产物目录（文件名通常为 `<scene>_<uuid>.json`）。

说明：`output/` 里的文件通常是可再生的运行产物，不应与 `export_label/` 的运行时标注真源混淆。

---

## 十二、`docs/` 目录逐项清单

你提到需要一一列举，这里按当前目录实际文件逐项给出用途。

- `docs/README_INDEX.md`
  - 文档总索引（当前入口导航）。

- `docs/README_ANNOTATOR.md`
  - 标注员操作说明。

- `docs/README_DEVELOPER.md`
  - 开发与部署说明。

- `docs/SOP_labelstudio_experiment.md`
  - 实验执行 SOP。

- `docs/ACTIVE_TIME_README.md`
  - active time 收集与日志链路说明。

- `docs/ANALYSIS_DATA_FLOW.md`
  - 分析链路与字段流转说明。

- `docs/GATING_LOGIC_FINAL_SOLUTION.md`
  - 门控逻辑说明。

- `docs/TEST_PLAN_AND_REVIEW.md`
  - 测试计划与审查记录。

- `docs/PROJECT_MAP_AND_HANDOVER_20260308.md`
  - 旧版“地图+交接”综合文档。

- `docs/PROJECT_MAP_CLEAN_20260308.md`
  - 纯净仓库地图（本文件）。

- `docs/实验设置执行细则_20260213.md`
  - 实验执行细则。

- `docs/实验集设定与用途.md`
  - 实验集定义与用途说明。

- `docs/三人开发分工_v4_phase1.md`
  - Phase1 分工文档。

- `docs/三人开发分工_v4_phase2_规划.md`
  - Phase2 规划文档。

- `docs/约束审查意见_20260306.md`
  - 约束文件审查记录。

- `docs/PRESCREEN_PROFILE_FREEZE_REVIEW_20260308.md`
  - 预筛选画像冻结审查记录。

- `docs/DRY_RUN_REVIEW_20260308.md`
  - dry run 审查记录。

- `docs/ABC_NEXT_STEPS_20260308.md`
  - A/B/C 后续事项记录。

- `docs/COS_上传与导入中文说明.md`
  - COS 上传与导入说明。

- `docs/门控失败_实际判定流程.md`
  - 门控失败判定流程说明。

- `docs/顶刊审稿视角_图表清单与分层策略.md`
  - 图表层级与审稿视角清单。

- `docs/跑分设计_审稿员视角.md`
  - 评分/分析设计讨论稿。

- `docs/他人修改建议.txt`
  - 外部修改建议记录。

- `docs/他人改动 文档.txt`
  - 外部改动说明记录。

- `docs/导师语音.txt`
  - 会议语音整理文本。

- `docs/导师最后审稿语音.txt`
  - 审稿语音整理文本。

- `docs/暂存.txt`
  - 临时记录。

- `docs/papers/`
  - 参考论文资料目录。

- `docs/overleaf_project/`
  - 中文/原版 Overleaf 工程目录。

- `docs/overleaf_project.zip`
  - Overleaf 工程打包文件。

- `docs/overleaf_project_en_elsarticle/`
  - 英文 elsarticle 版 Overleaf 工程目录。

- `docs/overleaf_project_en_elsarticle.zip`
  - 英文 Overleaf 工程打包文件。

- `docs/elsarticle/`
  - elsarticle 模板相关目录。

- `docs/Elsevier_Article__elsarticle__Template/`
  - Elsevier 模板目录。

- `docs/legacy/`
  - 历史文档归档目录。

说明：`docs/` 里既有正式入口文档，也有讨论与归档文本。纯净地图默认优先把 `README_INDEX/SOP/README_* /ANALYSIS_* /ACTIVE_TIME_* /PROJECT_MAP_CLEAN_*` 作为执行入口。

---

## 十三、`tests/` 目录纯净地图

- `tests/test_analyze_quality.py`
  - 当前最重要、实际有效的自动化测试文件。
  - 主要覆盖 `analyze_quality.py` 的解析、几何、门控、可靠性核心逻辑。

- `tests/conftest.py`
  - pytest 公共配置与 fixtures 注入。

- `tests/fixtures/`
  - 测试数据样本目录。

- `tests/README.md`
  - 当前测试目录说明与覆盖度现状。

### 当前测试目录的定位

1. 它不是完整端到端验证体系。
2. 但它仍然是当前分析主链最有效的单测入口。
3. 所以 `tests/` 不是摆设，应保留在纯净地图里。

---

## 十四、当前正式入口清单

如果只保留“今天真正该从哪开始”的入口，优先级如下：

1. `tools/official/ls_userscript_annotator.js`
   - 正式标注入口。
2. `tools/official/start_log_server.sh`
   - 正式 active log 服务启动入口。
3. `tools/prepare_labelstudio_docker.py`
   - Label Studio 导入任务生成入口。
4. `tools/create_labelstudio_split.py`
   - 实验分池构造入口。
5. `tools/build_task_registry.py`
   - planned registry 入口。
6. `tools/build_registry_suite.py`
   - registry 总装入口。
7. `tools/analyze_quality.py`
   - 上游分析入口。
8. `tools/official/analyze_quality_formal.py`
   - 正式分析入口。

---

## 十五、纯净地图的一句话结论

你现在这个仓库，如果按“当前服务器标注/分析系统”来理解，核心不是原始 HoHoNet 模型脚本，而是：

`tools/` + `tools/official/` + `export_label/` + `import_json/` + `active_logs/` + `analysis_results/` + `trap集/` + `tests/` + `data/` + `output/`。

其余原始 HoHoNet 深度/布局训练推理文件，可以暂时视为背景资产，不应混进当前纯净仓库地图主干。
