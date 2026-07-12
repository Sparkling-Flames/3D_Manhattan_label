# 论文主提纲 v3：阶段化协议、双链路画像与冻结路由

> 状态：2026-07-12 版本化写作修正；不回写原预注册或执行工件。

## 核心主张

本文提出一套可审计的阶段化半自动全景布局标注协议，通过将 Calibration-only 协议可靠度与 P1-informed failure-family 诊断画像分离，在不污染正式可靠度估计的前提下，评价半自动标注的效率、质量和冻结路由的预算效益。

## 贡献层级

一级贡献仅包括：阶段化可审计协议；由 Calibration-only 协议可靠度与 P1-informed 诊断画像组成的双链路工人建模；Validation 前冻结 worker state 后的预算感知路由评价。

二级创新包括：加权共识消融；support-aware 场景特异可靠度及 Global fallback；反例库与 failure-family 审计。模型重训练、规模化扩展和 A-line Manhattan 专家工具移入讨论、附录或未来工作，不作为 Paper A 主实验贡献。

## 研究问题

- RQ1 效率：半自动初始化是否降低 owner-valid exact active time，同时不以低质量或盲信为代价？
- RQ2 质量与纠错：半自动初始化是否改变最终几何质量、一致性、纠错、blind trust、undercoverage 和失败类型？加权共识仅作为辅助消融。
- RQ3a 画像效度：P1-informed diagnostic profile 是否能解释或预测独立 Calibration/Main 行为，同时保持与 $R_u$ 的概念边界？
- RQ3b 路由效用：固定预算下，冻结后的 Full worker state 是否优于 Random 和 Calibration-only Global policy？场景特异可靠度仅为满足 support 后的条件扩展。

## 目录

1. 引言：背景、缺口、方法概览、RQ、三级贡献层级与边界。
2. 相关工作：全景布局、模型辅助标注、众包可靠度、自动化偏差、自适应冗余、可审计 provenance。
3. 研究协议与数据生命周期：Pilot→P1→C1→C2→T1→V1、任务池、界面、active time、scope/reference、evidence validity、冻结边界。
4. 测量模型与双链路工人画像：几何指标、LOO/加权共识、链路 A $R_u$、链路 B $D_u$、support、证据用途矩阵、predictive validity、P1 amendment。
5. 路由与统计分析：标注前风险、Global/scene reliability、Random/Global/Full、停止规则、数据泄漏防护、按 RQ 的统计与敏感性分析。
6. 结果：完整性审计、RQ1、RQ2、RQ3a、RQ3b、二级创新消融、反例与敏感性。
7. 讨论与局限：主要发现、双链路意义、P1 amendment、内外部效度、二级创新价值、未来工作。
8. 结论。

附录容纳 artifact field contract、文件/CLI/版本、完整 subfamily、场景定义、额外反例与工程复现。

## 统一符号

- $A_u^{P1}$：P1 operational admission proxy。
- $R_u$：Calibration-only protocol reliability；代码兼容字段为 `r_u_calib`。
- $D_u=(G_u,S_u,C_u,V_u,P_u)$：geometry、scope、correction、coverage、process reliability，均为越高越好。
- $R_{u,s}$：满足 activation support 后的场景特异协议可靠度；不足时退化为 Global。

原始 blind-trust、undercoverage 和 failure rate 保留在 failure-family 表，不与 reliability 指标混用。

## 必备图表

- 图 1：阶段流程与冻结点。
- 图 2：P1/C1/C2 evidence → validity gate → $R_u$ 与 $D_u$ → frozen state → routing。
- 图 3：Random/Global/Full 与 T1/V1 数据隔离。
- 表 1：阶段—证据用途矩阵，覆盖 P1 manual/semi/OOS、C1/C2 manual、C1 semi、C2b、T1/V1，以及 admission、$R_u$、diagnostic、routing、primary/sensitivity/audit。
- 表 2：指标字典，列出符号、定义、方向、来源、inclusion gate、阶段和证据口径。
- 表 3：RQ—数据—估计量—统计方法映射。

## P1 Post-Closeout Integrity Amendment

该修正发现于 P1 closeout 后，只修正分析证据资格，不回写 admission 或冻结的 C1 assignment。跨工人、同任务、parent 早于 child 且 exact geometry 相同的行标为 confirmed non-independent：不进入 capability dimensions，但保留为 process-integrity failure。证据不完整的 cross-owner parent 行标为 suspected，等待人工裁决，不自动记失败。

P1 exact active time 仅接受 annotation identity 完整且 raw owner 一致的 browser log；task-level 和 `lead_time` 仅用于 sensitivity/audit。parent-derived timing 不解释为空白开始工作时间。独立的 C1/C2 evidence 仍可重新建立该工人的 $R_u$ 与诊断画像。

