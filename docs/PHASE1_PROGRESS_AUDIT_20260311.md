# Phase 1 进度审查与口径校验（2026-03-11）

## 1. 这份审查回答什么

这份文档只回答 3 个问题：

1. 当前论文提纲与附录在阶段流程上到底是怎样定义的。
2. `docs/他人修改建议.txt` 里的流程分析，哪些判断成立，哪些需要保留条件。
3. 按当前仓库实际产物看，Phase 1 已进行到哪里，哪些地方仍未与提纲目标对齐。

## 2. 当前应固定的主线口径

按 [docs/overleaf*project/sections/02*方法.tex](overleaf_project/sections/02_方法.tex)、[docs/overleaf*project/sections/03*实验设置.tex](overleaf_project/sections/03_实验设置.tex)、[docs/实验集设定与用途.md](实验集设定与用途.md) 当前写法，主线应固定为：

1. `Pilot`
   - 流程验证与协议边界冻结。
2. `PreScreen`
   - 独立真值锚定、admission、`r_u^(0)` 与 `w_max` 锁定、盲信风险早期筛查。
3. `Calibration`
   - 正式 worker statistics 估计，包括 `r_u`、`LCB(r_u)`、`r_u^(s)`、`C_u`，以及 calibration-only `d_t` 参考库与阈值协议。
4. `Main`
   - `Test` 服务 RQ1。
   - `Validation` 服务 RQ3。

因此，严谨表述不是“PreScreen / Calibration / Test / Validation 四个并列阶段”，而是：

- `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

## 3. 对“他人修改建议”的严格评估

### 3.1 总体判断

`docs/他人修改建议.txt` 的主判断总体正确，尤其是以下三点：

1. 把主流程改读成 `PreScreen -> Calibration -> Main(Test + Validation)` 是对的。
2. 把 `Calibration_anchor` 解释为 common-item anchor，而不是 expert-reference anchor，是对的。
3. 认为 `d_t` 的正式部署性使用发生在 Calibration 参考库冻结之后，也是对的。

### 3.2 对“微调 1”的审查

文中“微调 1”主张：

- `PreScreen` 输出：admission、`r_u^(0)`、`T_u`、`w_max`、初步风险筛查。
- `Calibration` 输出：`r_u`、`LCB(r_u)`、`r_u^(s)`、`C_u`、最终 risk tier、`d_t` 参考库与阈值协议。
- `Main` 输出：RQ1 的 Test 与 RQ3 的 Validation 结果。

这个归纳作为“主产物摘要”是基本正确的，但如果照字面理解得太死，也有两个必须补上的限定：

1. `PreScreen` 不是只有 admission。
   - 它除了产生 admission 与 `r_u^(0)` 外，还承担 Stage 1 协议的一部分正式冻结职责：manual/semi/OOS 三池边界、manual anchor 与 trap 的抽样框架、`w_max` 锁定协议、OOS gate 的计分边界。
   - 所以它不是“只做粗筛的前菜”，而是整篇论文能否避免循环论证的结构性前提。

2. `Calibration` 的“最终 risk tier”要理解为“主统计层正式估计”。
   - 这不意味着 Calibration 一结束，所有 scene-routing 细节就一定已经有足够覆盖度完全稳定。
   - 在当前提纲里，`Calibration_reserve`、核心场景覆盖补齐、activation/degeneration rate 仍然是后续要审计的对象。

因此，对“微调 1”的审稿式结论应写成：

- 作为主产物摘要，它是正确的。
- 但在正式论文措辞上，不能把 `PreScreen` 写得像“只负责 admission”，也不能把 `Calibration` 写得像“所有路由细节都已无条件冻结完成”。

### 3.3 对 `Calibration_anchor` 角色判断的审查

这一点判断是正确的，而且应当保留。

当前文本下：

1. 打破 weighted-consensus 循环依赖的独立真值锚点，来自 `PreScreen_manual` 的 20--22 个 manual anchors。
2. `Calibration_anchor` 的 12 张，是全员公共比较子集，用于提高 worker 间可比性并稳定 LOO 共识。

所以：

- `Calibration_anchor` 不应再被写成另一套 expert-reference anchors。
- 若现实中给其中少量样本额外做专家复核，也只能作为附加审计证据，不能改变其主协议身份。

### 3.4 对 `d_t` 时间顺序判断的审查

这一点也是正确的。

更严谨的说法应是：

- `d_t` 对 `Main` 阶段任务而言是“标注前可得”的代理信号；
- 但对整条研究流水线而言，它并不是在 `PreScreen` 之前就正式可用，而是建立在 `Calibration` 参考库冻结之后。

如果不加这层时间限定，容易被审稿人追问“你所谓标注前可得，到底是对任务时间轴，还是对整个实验流程时间轴”。

## 4. 当前仓库与提纲目标的真实对表

详见 [analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json](../analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json)。

当前最重要的事实是：

1. 提纲当前写的是：
   - `PreScreen_manual` 总数 30；
   - 其中 manual expert anchors 为 `20--22`；
   - `PreScreen_semi` 约 `18`；
   - `Calibration_anchor` 为 `12`。

2. 当前仓库实际 planned split 仍是：
   - `stage1_prescreen_manual = 30`；
   - `stage1_prescreen_manual_anchor = 12`；
   - `stage1_prescreen_semi = 30`；
   - `stage2_calibration_anchor = 12`。

3. 当前 C 线已结构化的 manual anchor bank 现状是：
   - `prescreen_manual = 12` 个唯一 base-task；
   - `calibration_manual = 12` 个唯一 base-task。

因此必须明确：

- 目前提纲和仓库在 `Calibration_anchor=12` 上是一致的；
- 但在 `PreScreen_manual anchors=20--22` 与 `PreScreen_semi~18` 上还没有对齐；
- 当前仓库仍停留在“旧 split 计划 + 新提纲口径并存”的状态。

这意味着：

1. `manual_anchor_bank_index_v1.csv` 是“当前可 join 现状快照”，不是“Stage 1 manual anchors 已完成到 20--22”的证明。
2. 当前 `trap_manifest_draft_v1.csv` 虽已给出 15 行草案，但其中只有 2 行 realized，13 行仍是 frozen-rule，因此也不能说 `PreScreen_semi` 已按提纲目标 materialize 完成。

## 5. 当前 Phase 1 进行到哪里

### A 线

已进入 Phase 1 后段：

- planned/runtime/compat/active-time registry 已建立；
- provenance 规则和 export inventory 已冻结为审计产物；
- pooled QA 已能读取这些层进行 schema/source 级审计。

### B 线

处于 Phase 1 前中段到中段：

- pooled QA / provenance audit 已补强；
- 但 stage-aware 主分析入口、Worker×Scene 矩阵、图 D 工人画像、T/I/M 正文级展示尚未闭环。

### C 线

处于 Phase 1 前段到中段：

- manifest schema、natural bank、embedding protocol、manual anchor snapshot 已结构化；
- 但 perturbation operator 仍未 materialize；
- revised Stage 1 target counts 也尚未和当前 split 实际对齐。

## 6. 按当前现状应如何继续推进

### 步骤 1：先锁 target-vs-realized coverage

已落盘：

- [analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json](../analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json)

用途：后续所有“Phase 1 完成度”讨论，都应以这份清单为基准，而不是把 revised thesis target、current split plan、current joinable snapshot 混成一句话。

### 步骤 2：C 线优先把 `PreScreen_semi` 从 frozen-rule 推进到可生成

当前最优先的，不是继续补 bank，而是：

1. 实现 perturbation operator；
2. 把 `trap_manifest_draft` 中的 synthetic rows materialize；
3. 再对照 revised target 讨论是否把 `PreScreen_semi` 从当前 30-image split 收缩为 thesis-facing 的约 18-image 主集合。

### 步骤 3：B 线从 pooled QA 进入 stage-aware analysis

当前 pooled QA 是合格的基础审计包，但还不是正文主图层。下一步应切换到：

1. T/I/M 三级口径；
2. Worker×Scene；
3. 工人画像图；
4. Type 4 过程性证据。

### 步骤 4：A 线最后做 split / registry / formal 的统一回写

在 Stage 1 revised target 真正落成前，不应把旧 split 直接当成新提纲已经实现。A 线后续需要做的是：

1. 统一 split truth 与 revised target；
2. 确保 formal / registry / manifest 的字段口径同步；
3. 避免 `condition`、`dataset_group`、anchor 身份在不同层出现新一轮漂移。

## 7. 一句话结论

“他人修改建议”里的主判断总体正确，尤其是 `Calibration_anchor` 不应被再写成 expert-reference anchors，以及“主线应读成 `PreScreen -> Calibration -> Main(Test + Validation)`”。

但从严苛审稿人视角，`微调 1` 只能作为主产物摘要，不能进一步简化成“PreScreen 只做 admission、Calibration 已完全定型”。更关键的是，当前 revised thesis target 与仓库实际 split / manifest 还没有完全对齐，这一点必须显式承认，不能用现有 12+12 anchor snapshot 代替 Stage 1 target 完成度。
