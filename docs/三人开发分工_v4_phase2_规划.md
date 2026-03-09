# 三人开发分工 v4 — Phase 2 粗略规划（系统演进阶段）

> 生成日期：2026-03-01  
> 前置依赖：Phase 1 全部交付物完成（`merged_all.csv` + `perturbation_operators.py` + `visualize_output_v2.ipynb` 补全 + `offline_replay.py`）  
> 外部阻塞点：**PreScreen 专家参考数据收集完毕**（`PreScreen_manual` 锚点子集，$n_{anchor}=12$）有助于独立 sanity check，但\textbf{不应作为权重校准的唯一数据源}（样本过小会导致不稳定/过拟合争议）。模块 A 的主校准推荐基于 `Calibration_manual` 固定池（N≈100），PreScreen 锚点仅用于独立验证与事后不可更改的对照披露。

> 口径锁定：Label Studio 标注界面的 `difficulty`/`model_issue`（见 `tools/label_studio_view_config.xml`）作为**唯一真源**；论文附录算子库（`A1_扰动算子库.tex`）与工程实现（`perturbation_operators.py`、`analyze_quality.py` 的解析/统计）必须使用同一组 alias 命名，Phase 2 不再引入新命名。

---

## Phase 2 定位

导师语音原意：将 Phase 1 的**静态离线分析系统**演进为「**自演化人机交互系统**」——动态识别可靠标注员共识、实时路由任务、闭环更新工人可信度。

对应论文 RQ3 从"离线回放验证"升级为"在线部署证据"。

**责任澄清（与 Phase 1 Workstream 对齐）**：
按 WS‑P / WS‑E / WS‑R 的划分，**WS‑P（Protocol & Audit）Owner 为 Dev B**，负责采集协议、审计链路与自动化 gate 的实现与验收；**Dev C 仅负责 Engine / 路由（Module B）实现并配合集成测试，不承担采集协议的主导实现**；**Dev A 负责 Module A（Calibration / Release & Verification）并持有最终验收签字**。此澄清与 Phase 1 的 Workstream 划分保持一致，避免责任重叠。

## Phase 2 团队化分工（按六大设计维度）

> 目的：将“按脚本分工”升级为“按设计维度 + RACI + 验收门槛”的工程化协作方式，保证模块并行开发时接口稳定、职责清晰、证据可审计。

### 2.6 六大核心设计维度与责任矩阵

| 设计维度       | 主要职责                                                                     | Owner | Reviewer     | 核心交付物                                                           |
| -------------- | ---------------------------------------------------------------------------- | ----- | ------------ | -------------------------------------------------------------------- |
| 架构设计       | 定义在线路由系统边界、运行拓扑、故障退化策略（离线回放兜底）                 | Dev A | Dev B, Dev C | `docs/phase2_architecture.md`（C4 Context/Container + 时序图）       |
| 模块与组件设计 | 拆分 `routing_service`/`audit_pipeline`/`counterexample_flow` 内部组件与依赖 | Dev C | Dev A        | `tools/routing_service/*.py` 组件图与模块 README                     |
| 接口设计       | 统一 `POST /assign`、`POST /stop_check`、webhook payload、错误码、幂等键     | Dev B | Dev C        | `docs/phase2_api_contract.yaml`（OpenAPI + webhook schema）          |
| 数据设计       | 冻结 `merged_all.csv` 下游只读口径、在线状态库 schema、审计报表字段          | Dev A | Dev B        | `docs/phase2_data_contract.md` + `db.py` migration 说明              |
| 算法设计       | 路由策略、权重校准、序贯停止判定与 OOD 触发逻辑                              | Dev C | Dev A        | `strategies.py` + `calibration_pipeline.py` + 策略评估报告           |
| UI 设计        | Label Studio 交互入口、审计报告可视化、反例复核配置可用性                    | Dev B | Dev A        | `audit_report_template.html.j2` + `counterexample_review_config.xml` |

### 2.7 统一工程约束（Definition of Done）

| Gate        | 必须满足的门槛                                                                               | 失败处理                              |
| ----------- | -------------------------------------------------------------------------------------------- | ------------------------------------- |
| G0 合约冻结 | `phase2_api_contract.yaml`、`phase2_data_contract.md`、alias 映射三方一致（XML/附录A1/代码） | 未通过不得进入实现分支                |
| G1 单测门槛 | 新增核心模块单测覆盖率 ≥ 80%，关键策略路径必须有回归测试                                     | 阻断合并                              |
| G2 集成门槛 | 本地 docker 联调通过：Label Studio webhook → routing_service → DB 写入 → 审计输出            | 保留在 `integration/*` 分支，不进主线 |
| G3 审计门槛 | `meta_label_guard.py --fail-on-reject` 通过；审计报告含 reject rate 与 reason distribution   | 自动生成阻断报告                      |
| G4 发布门槛 | 端到端演练完成且产出 RQ3 证据包（日志、配置、指标图）                                        | 延后发布，进入风险清单                |

### 2.8 迭代节奏与协作机制（软件团队实践）

- 迭代节奏：1 周 1 Sprint，周一计划会（30min）+ 周三风险同步（15min）+ 周五评审（30min）。
- 需求入口：只接受 issue 模板（背景/输入输出/验收标准/回滚方案）。
- 分支策略：`main`（稳定）/`develop`（集成）/`feature/*`（模块开发）/`hotfix/*`（紧急修复）。
- 评审规则：跨维度至少 1 名 reviewer（例如“算法改动”必须含“数据或接口 reviewer”）。
- 变更审计：任何字段与接口变更必须同步更新 contract 文档与变更日志，否则 CI 失败。

### 2.9 Phase 2 角色映射（执行层）

- Dev A：架构与数据 Owner（Architecture + Data + Release Gate）。
- Dev B：接口与 UI/审计 Owner（API Contract + Audit/UI + Protocol continuity）。
- Dev C：算法与服务实现 Owner（Routing Engine + Strategy + Runtime Integration）。
- 该映射不改变你已确认的 Phase 1 分工，只用于 Phase 2 工程化落地。

## 模块 A：加权共识精化（Weighted Consensus Calibration）

**论文依据**：§3.3 RQ2b，方案 A（交叉拟合/交叉验证选 $w_{\max}$）；`03_实验设置.tex` PreScreen 锚点子集（独立验证）。

**目标**：将 Phase 1 的 3 类功能组（Stable/Vulnerable/Noise）与 `r_u_lcb`、`S_u`、风险桶失效信息转化为可信共识加权与路由约束，实现 $\Delta\kappa \geq 0.05$ 的工程有意义提升。

### 交付物

| 模块         | 文件                                                     | 核心内容                                                           |
| ------------ | -------------------------------------------------------- | ------------------------------------------------------------------ |
| 权重校准     | `tools/calibration_pipeline.py`                          | K 折交叉验证选 $w_{\max}$；防数据泄露（每折不含验证折标签）        |
| 加权共识计算 | `analyze_quality.py` 扩展 `compute_weighted_consensus()` | 输入 `r_u_lcb` + `S_u`，输出加权 tag/corner 共识                   |
| 对比实验     | `tools/consensus_comparison.py`                          | uniform 共识 vs. weighted 共识 $\Delta$IoU；Wilcoxon 检验 + BCa CI |
| 预注册输出   | `data/prescreen/w_max_locked.json`                       | 冻结 $w_{\max}$ 阈值映射，Main 阶段只读                            |

### 技术方案

```
Calibration_manual 固定池（N≈100）
         │
         ├── LOO 可靠度 r_u（避免自我影响）
         ├── 交叉拟合/交叉验证（默认 K=5；样本不足时降级 K=2）
         │    └── 枚举 w_max ∈ [1.0, 1.5, 2.0, 3.0, 5.0]
         └── 选最佳 w_max → freeze → w_max_locked.json

PreScreen_manual 锚点（n_anchor=12）
         └── 独立 sanity check：冻结后仅做对照披露，不再用于选择/调参
```

**统计**：`scipy.stats.wilcoxon`（非参数配对检验）+ `numpy` BCa bootstrap（按任务重采样）  
**效应量门槛**：$\Delta\kappa \geq 0.05$（论文预注册 MDE）  
**框架**：`scikit-learn` KFold；`pandas` 数据流  
**工时估计**：5–7 人天

---

## 模块 B：实时路由服务（Live Routing Plugin）

**论文依据**：§3.1 RQ3，策略 3（场景感知路由）在线部署。

**目标**：将 Phase 1 `offline_replay.py` 的三种策略上线为 Label Studio 可调用的实时接口，实现序贯派单与停止。

### 交付物

| 模块              | 文件                                  | 核心内容                                                                                   |
| ----------------- | ------------------------------------- | ------------------------------------------------------------------------------------------ |
| REST API          | `tools/routing_service/app.py`        | FastAPI + Uvicorn；接口：`POST /assign`，`POST /stop_check`，`GET /worker_state`           |
| Label Studio 集成 | `tools/routing_service/ls_backend.py` | Label Studio ML Backend 协议（`/predict` endpoint）；webhook callback 处理                 |
| 策略热插拔        | `tools/routing_service/strategies.py` | 沿用 Phase 1 `offline_replay.py` 算子接口；JSON 配置注入策略参数                           |
| 状态持久化        | `tools/routing_service/db.py`         | SQLite 存 `worker_state`（`r_u_lcb`、`S_u`、`k_used_cumulative`）；后期可升 PostgreSQL     |
| 部署配置          | `docker-compose.routing.yml`          | 基于现有 `nginx.conf` 草稿扩展；服务：`routing_service` + `nginx` + `label_studio`（可选） |

### 技术方案

```
Label Studio (webhook: task_submitted)
         │
         ▼
FastAPI /predict  ──→  策略选择器（JSON 配置）
         │                   ├── Random（baseline）
         │                   ├── GlobalReliability（r_u_lcb 排序）
         │                   └── Stratified（场景感知 + OOD 触发，k←3）
         ▼
SQLite worker_state（r_u, S_u, 历史分配记录）
         │
         ▼
返回 worker_list + stop_flag（序贯停止判断）
```

**框架**：`FastAPI`（异步）、`Uvicorn`、`Pydantic`（request/response schema）  
**部署**：`Docker` + `docker-compose`；CI 用 GitHub Actions 做健康检查  
**序贯停止**：复用 Phase 1 `compute_iaa` 判断是否达到 `IAA_t ≥ τ`  
**工时估计**：8–10 人天

---

## 模块 C：自动质量监控（Auto Audit CI）

**论文依据**：口径 T/I/M 可审计输出，导师语音"process evidence 全链路"。

**目标**：每次新批次数据入库时，自动检测异常并输出 HTML 报告，不再依赖人工逐次运行 notebook。

### 交付物

| 模块                           | 文件                                            | 核心内容                                                                                                                                                                        |
| ------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 审计 CLI                       | `tools/auto_audit.py`                           | `python tools/auto_audit.py --batch-id <id> --out reports/`                                                                                                                     |
| 检测规则引擎                   | 复用 Phase 1 `analyze_quality.py` Type 1–4 flag | 新增：`active_time` P99 阈值报警；门控失败率突增检测（滑动窗口）                                                                                                                |
| 元标签合规兜底                 | `tools/meta_label_guard.py`（集成到 audit）     | 对导出 JSON 执行与 UI 一致的 hard rules（空选/互斥/条件必填），输出 `meta_guard_accepted.csv`/`meta_guard_rejected.csv` 与原因分布；审计报告中披露 reject rate 与示例任务       |
| 过程证据汇总                   | （读取 userscript 审计导出）                    | 汇总提交时被拦截次数与原因分布（`n_rejected_empty` / `n_rejected_conflict` / per-worker reject rate / retries），与最终数据中的残余 Type4/NA 交叉核对，避免“挡在门外就当没发生” |
| HTML 报告生成                  | `tools/audit_report_template.html.j2`           | `Jinja2` 模板；含图表、字段审计表、异常摘要                                                                                                                                     |
| CI/CD                          | `.github/workflows/audit.yml`                   | `push to data/` → 触发审计 → 报告上传 artifact                                                                                                                                  |
| `save_quality_figures.py` 重构 | `tools/save_quality_figures_v2.py`              | 重写为 CLI 工具，依赖 v1/v2 notebook 已验证函数，彻底去除对不存在模块的依赖                                                                                                     |

**框架**：`Jinja2`（报告）、GitHub Actions、`argparse`（CLI）  
**工时估计**：4–6 人天

---

## 模块 D：反例库人工复核工作流

**论文依据**：§4.3 反例库（Table A1）；Type 1–4 候选集的最终人工确认。

**目标**：将 Phase 1 自动检测到的反例候选（`type4_process_failures.csv` 等）流转为 Label Studio 人工复核工单，形成高质量标注闭环。

### 交付物

| 模块         | 文件                                                | 核心内容                                                                                             |
| ------------ | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 工单导入     | `tools/import_counterexample_tasks.py`              | `label-studio-sdk`：将 `counterexample_candidates.csv` → Label Studio 任务                           |
| 复核界面模板 | `import_json/counterexample_review_config.xml`      | Label Studio XML 标注配置：`is_valid_counterexample`（Y/N）+ `correction_note`（文本）+ 原始图像预览 |
| 结果回写     | `analyze_quality.py` 扩展 `ingest_review_results()` | 将复核结果写入 `merged_all.csv` 的 `counterexample_confirmed` / `correction` 列                      |
| 统计报告     | `tools/counterexample_summary.py`                   | 输出每类（Type 1–4）的确认率、打回率、修正说明词云（可选）                                           |

**框架**：`label-studio-sdk`（Python SDK）  
**工时估计**：3–5 人天

---

## 技术栈汇总

| 方向              | 主要库 / 框架                                         | Phase 1 中的前驱                         |
| ----------------- | ----------------------------------------------------- | ---------------------------------------- |
| API 服务          | `FastAPI`、`Uvicorn`、`Pydantic`                      | `offline_replay.py`（策略接口）          |
| Label Studio 集成 | `label-studio-sdk`、webhook                           | `create_labelstudio_split_by_outline.py` |
| 统计              | `scipy`（Wilcoxon/BCa）、`scikit-learn`（KFold）      | `analyze_quality.py` LOO 统计            |
| 部署              | `Docker`、`docker-compose`、`nginx`（已有 conf 草稿） | `nginx.conf`（已有）                     |
| 自动化报告        | `Jinja2` HTML 模板                                    | v1/v2 notebook 图表函数                  |
| CI                | GitHub Actions                                        | —                                        |
| 持久化            | `SQLite` → 可升 `PostgreSQL`                          | `merged_all.csv`（离线版）               |

---

## Phase 2 里程碑（以 PreScreen 数据到位为时间轴）

```
PreScreen 专家参考数据到位（n_anchor=12，w_max 可计算）
     │
     W1–W2: 模块 A — K折校准跑通，w_max_locked.json 生成，对比实验输出 Δκ
     │
     W3–W4: 模块 B — FastAPI skeleton + /assign 接口本地联调成功
     │
     W5:    模块 C — auto_audit CLI + Jinja2 HTML 报告可运行
     │
     W6:    模块 D — Label Studio 工单导入 + 复核结果回写通过测试
     │
     W7:    集成测试 — routing_service + Label Studio webhook 端到端联调
     │
     W8:    论文 RQ3 证据固化 — 部署日志导出 replay_results + 路由收益图
```

---

## 各模块阻塞点与风险

| 模块       | 关键阻塞点                                                 | 风险缓解                                                        |
| ---------- | ---------------------------------------------------------- | --------------------------------------------------------------- |
| **模块 A** | PreScreen 锚点数据（$n_{anchor}=12$）必须先收集            | 用 Calibration_manual 已有数据做预演，正式锁定等 PreScreen 完成 |
| **模块 B** | Label Studio webhook 部署环境（需服务器或 ngrok 内网穿透） | 本地 Docker 先跑通逻辑，webhook 环境配置独立                    |
| **模块 C** | GitHub Actions 触发依赖 data/ 推送权限配置                 | 先用本地 CLI 验证逻辑，Actions 为可选加速                       |
| **模块 D** | 反例库候选质量依赖 Phase 1 Type 1–4 检测精度               | Phase 1 `detect_type4_failures` 测试覆盖率需 >80%               |

---

## 与 Phase 1 的接口依赖关系

```
Phase 1 输出                        Phase 2 使用
─────────────────────────────────────────────────────────
merged_all.csv (r_u, r_u_lcb, S_u) → 模块A: K折选w_max
                                     → 模块B: /worker_state 初始化
offline_replay.py (三策略接口)      → 模块B: routing_service/strategies.py
perturbation_plan_frozen.json       → 模块A/B: PreScreen_semi 误导初始化复现
counterexample_candidates.csv       → 模块D: 工单导入
visualize_output_v1.ipynb（诊断图） → 模块C: save_quality_figures_v2 重构基础
```

---

_Phase 2 各模块可**并行**开发（A + C + D 不依赖部署环境；B 依赖 Docker 但可本地先跑）。推荐 Dev A 负责模块 A，Dev B 负责模块 C + D，Dev C 负责模块 B。_

_（工作量更均衡的分配备选）Dev A：模块 A；Dev B：模块 B；Dev C：模块 C + 模块 D。_

## 9. Phase 2 风险导向的协作补充说明

为配合 Phase 1 的“交付导向-接口冻结”调整，Phase 2 保持风险管理视角，建议在当前架构基础上补充下列协作要点：

1. **审计/协议链路延续**：WS-P 的审计链路（UI 拦截、本地 schema、导出拒收）要以 pipeline 方式挂在 Phase 2 的 `auto_audit.py`、`meta_label_guard.py` 与 `audit_report_template.html.j2` 上，保证任何新模块（A/B/C/D）都能拿到相同的审计 evidence（reject counts、reason categories、per-worker rates）。
2. **Workstream 责任保持**：Phase 2 确认 Dev B 同时负责模块 C/D 以保持审计与反例收敛；Dev A 主驱模块 A（加权共识）；Dev C 承担模块 B（路由服务）并与 Dev B 协调 webhook 接入。这样 Phase 1 的 WS-P/WS-E/WS-R 易于自然过渡为 Phase 2 的 A/B/C 分工。
3. **Gate checklist 延伸**：Phase 2 的每个模块也需借鉴 WS-R 的 gate checklist（字段冻结、alias 对齐、审计报告），并在 `module_*` 的 README 或 `docs/README_INDEX.md` 中登记当前状态，避免 Phase 2 产生的 alias/weight/route 配置漂移。

此补充说明可作为 Phase 2 文档末尾的“风险闭环”段落，供三人对齐与项目审查参考。
