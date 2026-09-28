# Paper A manuscript migration audit v2

> 版本日期：2026-07-16  
> 状态：v4 active manuscript 限域迁移审计；不代表 LaTeX 编译或实验结果完成。  
> 编译事实：本机未发现 XeLaTeX、LuaLaTeX、PDFLaTeX、latexmk 或完整 manuscript PDF；Overleaf 是下一步编译环境。  
> 不回写：protocol、assignment、C1 XML、tools、tests、数据、raw export、active logs、analysis_results、GT、Paper B、Manhattan。

## 1. 当前工作树与证据范围

迁移开始时已存在未提交的 `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md/.tex`，本轮未覆盖。`docs/thesis_main/manuscript/` 与本审计文件按仓库规则为 ignored local source；未执行 `git add -f`、commit 或 push。

主动输入链为 `main.tex`、八个主章节和 A1—A4 附录。旧 `01_研究问题.tex`、`02_方法.tex`、`03_实验设置.tex`、`04_报告与可审计输出.tex`、`05_标注数据重训练.tex`、`06_讨论与局限性.tex`、`07_与审稿员预期批评的预设回答.tex`、`08_预期贡献总结.tex` 不被当前 `main.tex` 输入，保留为 legacy source。

## 2. 修改前 SHA-256

以下为上一轮 v4 migration 的编辑前主动 manuscript 快照；本次定向收口开始时这些 ignored 文件已经包含先前未提交的 v4 修改，因此不伪造一个不存在的“本轮前”基线。legacy section 也已单独读取但不纳入 active PDF 链。

```text
main.tex                                      25491A7DC162586C4FE3DB29B73025D78302F2049BB14721C512B61810FCD83F
sections/01_引言.tex                           0D8290595B1E5B0B2F6451267FA6A9D03FC2D896D3C3264CBD289C3F27BF6AE2
sections/02_相关工作.tex                       E1CE3D5F4EC87AEA8445D79A0FA1BFA7AD4A8EA803428DEE0B9551317A218BFC
sections/03_研究协议与数据生命周期.tex         75B8CC2704DDD8B458151A9482B578CA93C4D66B9AC3FD4FA36E8C1DB20690C3
sections/04_测量模型与双链路工人画像.tex       AD25FD06FF6EAF328F40BA27966E32BEAF1BA543BE697E5D803F4383B0A25575
sections/05_路由策略与统计分析.tex             299D6B6B99EC84D790E73E2F316B180922EBC488D91131BADCAF814CD822457C
sections/06_实验结果.tex                       F2F760B34CA6D194AFC0D4D86E4B759129B004E4A9E95B555884FA9A2D01D282
sections/07_讨论与局限.tex                     8E96433CD2A29570AB9E4A3B1D258B093996FF3A578D736E517FCB8C6C8B634E
sections/08_结论.tex                           912B8D614D7BAE6C17F2A4C7A8D59E0DA4F313CDB517C6D3244768F6AC4FDE92
sections/A2_数据集汇总表.tex                   38B65624F3D1BB36F7EE472390B673E6F9171C3C9014C86E509AF57920A90C43
sections/A4_测度与统计方法速查.tex             DC9F9ACF1A12A66CB07CB49375746790A48901547DAFE928DB6253AA528F76E9
```

当前目录没有可确认的 compiled manuscript PDF。`docs/thesis_main/HOHONET Paper A 方法路线说明.pdf` 是方法路线说明，不作为 manuscript PDF baseline。
该方法路线说明 PDF 当前 SHA-256 为 `97C9553373747974CB010F3535B793CF8370F66CCAAE8D5756AA944ACA6C23D0`；它不代表 v4 manuscript 编译结果。

## 3. 兼容性审计

### 3.1 与冻结 protocol 完全兼容

- `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)` 与 `P1 -> C1 -> C2 -> T1 -> V1` 不变。
- P1 admission、`w_max`、C1/C2 pool/assignment、C2 两种合法补派理由不变。
- `R_u` 仍只由 eligible C1/C2 `Calibration_manual` 形成；P1、semi、T1、V1 不回流。
- T1 仍服务效率，V1 仍服务冻结 policy 部署与审计；Random/Global/Full 主比较仍来自 Calibration replay。
- RQ3b 使用 image-level cross-fitting，evaluation fold 不参与 worker state 或 policy 参数估计。

### 3.2 仅属于 analysis clarification

- task-tag `+/-/0/NA` 与 `a/e/u/k` 三状态统计；旧多数产物只作 legacy descriptive proxy。
- Difficulty 的 `trivial`、Model Issue acceptable harmonization、issue recognition/correction 分离。
- worker-scene broad/strict candidate、support/fallback、LOO pivotality sidecar。
- Geometry LOO、reference-gated compatibility 与 convex-hull medoid 的 legacy 降级。
- active-time identity、system collection issue 与 worker process failure 分离。
- failure-family、counterexample review、weighted consensus 的辅助定位。

### 3.3 C1 closeout 前 pending implementation

- 三状态 task-tag sidecar 与五类 machine-readable analysis tables。
- seam-aware `y_ceil/y_floor/w` metric、stability sidecar 与 metric compatibility gate。
- formal RQ3a predictive artifact；当前只允许描述性/方向性状态。
- online routing evidence table、arrival snapshot、conflict/stop/escalation event materialization。
- C1 valid/completed、C2 freeze、正式 RQ3b replay 结果与所有结果数值。

工作树另有未提交的 vFinal candidate sidecar/code/test 变更；它们不是本轮 docs-only 迁移的写入对象，也未进入正式 C1 closeout、C2 freeze 或 thesis-facing result。故 v4 仍将三状态 sidecar、seam-aware geometry 和 online routing evidence 标为 pending implementation，而不是把候选代码视为已完成证据。

### 3.4 Requires explicit protocol/statistical amendment

- 将 v4 的 `k_dispatch_initial/k_min_for_stop/standard_cap/escalation_cap` 候选直接写入当前冻结 V1 执行。
- 把场景 profile 作为首次 worker selection 或新增 C2 assignment reason。
- 改写 `STATISTICAL_ANALYSIS_PLAN_v1.md` 已冻结 primary estimand、检验集合、MDE 或 missingness 解释。
- 以 V1 结果反推 C2、routing、worker tier 或历史 admission。

## 4. 实现状态与冲突

| 项目 | 当前状态 | v4 写法 |
|---|---|---|
| 旧 meta-label materializer | 已实现旧 majority method | `legacy descriptive proxy`，不改名为三状态 |
| 三状态 sidecar | 正式链未完成；工作树另有未提交 candidate | `pending implementation`，不视为正式 closeout artifact |
| Geometry seam-aware metric | 未实现 | `C1 closeout 前拟冻结 candidate` |
| convex-hull medoid | 旧 agreement proxy | `legacy agreement proxy`，不作 geometry truth |
| C1 | ongoing；launched/valid/completed 分开 | 不写成 closeout 完成 |
| C2 | 未冻结 | 不写成正式 routing freeze |
| RQ3a | 当前无 formal predictive result | `not_evaluable`/`pending`，不写成结果 |
| RQ3b | 无正式 replay result | 只固定 replay contract，不填数字 |
| local compile | engine missing | 不声称 compile；Overleaf 编译 |

## 5. 修改后 SHA-256

以下为本次定向收口完成后的主动 manuscript SHA-256；它们不包含 compiled PDF。若需要严格的逐轮差分，应以本节第2部分的上一轮基线和本节新增的 closure audit 为两个审计点。

```powershell
Get-FileHash docs/thesis_main/manuscript/overleaf_project/main.tex -Algorithm SHA256
Get-ChildItem docs/thesis_main/manuscript/overleaf_project/sections -Filter '*.tex' |
  Sort-Object Name | ForEach-Object { Get-FileHash $_.FullName -Algorithm SHA256 }
```

```text
main.tex                                      7D873A2EC1F093F88C9026024BC8773ED8776B6C3D29B59BF51763F0B581177A
refs/references.bib                           760F906AB6C91542432C5E38363EE000840EC330B9607C5625581738C208506C
sections/01_引言.tex                           8F426196C50D4B4B78A2B68F6303D86C6A47E8CBBCCCFA7D9C7CFAD4DF73E310
sections/02_相关工作.tex                       F3D2F80C03205244DD191B4014DB8E3F80845DB7EEE45445B7E07AD10D6265A9
sections/03_研究协议与数据生命周期.tex         D457D46358034D3EF3C57FF2AC1FEE5D2B7ED75A757B6B3C89A94BE26E94C066
sections/04_测量模型与双链路工人画像.tex       B70DF80A6148D7DB08AD2FD27DA9377869A3EC6942FEA735A831544DD65AEF75
sections/05_路由策略与统计分析.tex             91D906F0471BD3B169226C6DD5A0196EDF1EC342B6E743954A9B7B24740E9D70
sections/06_实验结果.tex                       E8F619B6BE742C7A129BEFEFE353234019A73D8E9DB9C73B9A611D160D0CC1CF
sections/07_讨论与局限.tex                     D00EEF0CBAC07F4C94EB1F128F1744513BEDA0577319587ADBCEE7A397E39502
sections/08_结论.tex                           63C20808B6477FB4D4C35811DE7ABBD5FAB6F3344CD8738E742D7009389C223A
sections/A1_扰动算子库.tex                      EF6D0B6BFB376E5E3D0A0CB1B0F46A5F48D77051BACE6CE303A528F035AEE5BA
sections/A2_数据集汇总表.tex                   9C199421D388D037180539E87B7CD268239B83F7E625809D5988EF9AB29B2CC8
sections/A3_启用门槛保守估计表.tex             A07F4B838DBB0078952ACD67E14B04F66C44FB48C421FDC5EF4615AE78C023EC
sections/A4_测度与统计方法速查.tex             1159010216F877210B60D0BE0C986FB56EF863080E2A2DC1DBA09D561D7819B7
sections/A4_测度与统计方法速查.tex             008CE9F4B1F22139CC38443EDB28ECF5619241B85A2BBC341787E3E997E46CF1
```

本轮同步的 ignored display/bridge 文件最终 SHA：

```text
WORKER_PROFILE_THESIS_DISPLAY_CONTRACT_v1.md       E63EDCDB8F12B871F14F1E79BD760ACE81AF0B5757CBD2E250C6925F66F319FC
WORKER_PROFILE_AMENDMENT_COMPATIBILITY_BRIDGE_v1.md 9AF08D05D16284D836FAD80A62598BFE1B48D316DC12359E35693B1DF84D8096
```

Overleaf 编译后的 PDF SHA、页数、目录层级、broken reference 与 warnings 由 Overleaf 下载后追加；本地不生成 PDF。

## 6. 审计结论

本轮未新增 `v4.tex`：v4 的独立用途是 Markdown 审计合同，实际正文继续以 active Overleaf `main.tex + sections/*.tex` 为唯一 LaTeX 真源。v4 migration 只完成写作主轴、active source 口径、迁移映射和兼容性记录；不宣称正文全面迁移、C1 closeout、C2 freeze、三状态 sidecar、seam-aware metric、online routing 或正式 predictive/replay 结果已完成。

## 7. 2026-07-16 final closure

- Formal `R_u` is aligned to the validated code contract: `iou_to_consensus_loo`, worker-specific `worker_excluded_loo_consensus`, minimum peer support 2, Calibration-only C1/C2 eligibility, task-level median aggregation, and code-consistent CI/LCB semantics.
- `D_u^{P1}` is diagnostic/predictive precursor only; `D_u^{C2}` is the operational profile namespace and is routing-eligible only after C2 freeze and support/provenance/reference gates.
- C2 reasons remain the two SOP reasons. Common/core discrepancy and geometry-evaluability gaps are diagnostic unless mapped to an existing reason.
- Active-time now binds to selected annotation identity; multiple annotation IDs require adjudication before primary timing eligibility.
- Three-state sidecar, seam-aware Geometry LOO, event replay, and formal predictive artifacts remain candidate-only/pending until formal closeout artifacts exist.
- No protocol, assignment, P1 admission, reserve pool, raw data, GT, tools, tests, or Label Studio project was modified by this closure.

## 8. 定向收口审计（review closure）

### 8.1 已闭合的正文/合同冲突

- RQ1 active-time identity 固定为 `project_id + ls_runtime_task_id + worker_id + annotation_id`；同 annotation/session 的 max 与跨 session 非重叠累加规则分开；多 annotation worker-task 在 adjudication 前不进入 primary time；geometry/quality 与 selected annotation identity 对齐。
- 同 trusted timestamp 且无更高精度服务器顺序的 annotation 采用 simultaneous atomic batch；批次共享 pre-state、批次内不 stop/不选下一 worker、批次后只决策一次；annotation ID 只作 sensitivity order，不作真实 arrival order。
- terminal snapshot 后到达的 annotation/tag/geometry 只写 `post_terminal_audit_only=true`，不改变 selected workers、`k_used`、stop reason、formal aggregate 或 policy outcome。
- stop 规则统一为 family-specific matrix；Scope-only、resolved OOS、Difficulty、Model Issue recognition 不被 Geometry 阻塞，correction/Geometry/scene-profile/whole-task in-scope completion 才要求 Geometry gate。
- `trivial` 统一为“未有因素达到本次角点实质困难报告阈值”的 explicit negative，不解释为物理不存在。

### 8.2 与实现状态一致的三态口径

全文只允许以下状态：`code_or_scaffold_implemented`、`candidate_dryrun_artifact_generated`、`formal_thesis_artifact_generated`。当前代码/脚手架可证明前一状态；正式 C1 closeout 前不把 candidate dry-run、formal sidecar、frozen worker state 或 thesis-facing result 写成已生成。旧 `majority_token_presence_demote_default_after_task_annotator_dedup` 继续标为 legacy descriptive proxy。

### 8.3 R_u、Geometry 与 reference 审计

`R_u` primary 仍是 `iou_to_consensus_loo` 的 worker-level median；当前实现是排除被评价 worker 后的 peer medoid，peer support=2；混合/未知 scope、peer 不足、geometry/reference 不可计算或 compatibility gate 失败均为 `not_evaluable`。`N_{R,min}` 由命令参数传入，当前未冻结为论文常数，标为 prospective pending；bootstrap 默认 1000、95% percentile、seed=0，实际覆盖值以 manifest 为准。seam-aware `q_boundary/q_wallwall` 只作 `G_u` diagnostic/alternative components；无 prospective fusion contract 时不生成 integrated `G_u^{C2}`。

`task_outcome_reference` 与 `r_u_worker_specific_loo_reference` 已在正文和附录字段索引中分列。`task_final_scope` 权威来源仅为 final-gold、expert adjudication 或 review/unresolved；crowd majority/weighted consensus 不覆盖权威 scope。

### 8.4 统计与协议兼容分类

**compatible：**主线阶段/冻结边界、P1 admission、C2 两种合法 reason、Calibration-only `R_u`、LOO exclusion、T1/V1 隔离、RQ3b task unit 与 image-level cross-fitting。

**clarification-only：**三状态历史 harmonization、trivial、reference 分层、active-time identity、family stop matrix、scope final-state provenance、failure-family 与 weighted consensus 降级。

**pending implementation / artifact：**formal three-state sidecar、formal seam-aware metric/stability、online routing evidence、formal RQ3a predictive artifact、C1 closeout、C2 freeze 与正式 replay 结果。

**requires explicit amendment：**把四个动态冗余参数写入当前冻结 V1 执行、改变 C2 assignment reason、改写 SAP v1 primary/MDE/multiplicity/missingness 口径。若 SAP 未给出 MDE、quality floor 或 RQ2 multiplicity，论文只提出 additive prospective amendment，不覆盖 SAP v1。

### 8.5 排版与来源事实

active `main.tex` 默认显式使用 `a4paper`；若学校/期刊模板强制 Letter，应在 Overleaf 项目层回退并记录。`acceptable` 已从 perturbation operator 语义中移出为 control。A3 交叉引用改指向 scene-support/fallback 合同。占位 bibliography 已替换为经核验的 HorizonNet、CrowdTruth 2.0 与 sequential stopping/worker selection 一手条目。当前没有本地 LaTeX engine 或 active manuscript PDF；Overleaf 编译结果、PDF SHA、页数、目录与 broken-reference 检查必须由 Overleaf 下载后补入本审计。
