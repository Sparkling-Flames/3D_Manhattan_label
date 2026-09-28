# Paper A manuscript migration audit v1

> 版本日期：2026-07-13
> 状态：本地 Overleaf 源迁移与限域修正审计；八章输入骨架已建立但尚未编译，不是最终论文冻结证明。
> 不回写：未修改 Python analysis code、tests、数据、analysis_results、export_label、active_logs、import_json、protocol、assignment、routing、server、userscript 或正式实验工件。

## 1. 工程身份

- 实际 manuscript root：`docs/thesis_main/manuscript/overleaf_project/`
- main entry：`main.tex`
- document class：`IEEEtran`，one-column journal
- 声明编译器：XeLaTeX（`main.tex` 的 `!TeX program = xelatex` 和 PDFTeX guard）
- bibliography：`refs/references.bib`，`IEEEtran` bibliography style，当前使用 `\nocite{kara2018,liu2018}`
- 本地旧 PDF 对照材料：`docs/thesis_main/HOHONET Paper A 方法路线说明.pdf`
- 旧 PDF SHA-256：`97C9553373747974CB010F3535B793CF8370F66CCAAE8D5756AA944ACA6C23D0`

该 PDF 是方法路线说明，不是当前 Overleaf 编译产物；本地未找到整篇 manuscript PDF。PDF 文本已通过 bundled `pypdf` 提取核对；Poppler `pdftoppm` 的 native executable 不可用，因此没有完成视觉 PNG 渲染。

## 2. Active input chain

`main.tex` 当前按以下顺序输入：

```text
01_引言.tex
02_相关工作.tex
03_研究协议与数据生命周期.tex
04_测量模型与双链路工人画像.tex
05_路由策略与统计分析.tex
06_实验结果.tex
07_讨论与局限.tex
08_结论.tex
A1_扰动算子库.tex
A2_数据集汇总表.tex
A3_启用门槛保守估计表.tex
A4_测度与统计方法速查.tex
```

旧 `01_研究问题.tex`—`08_预期贡献总结.tex` 保留为本地 legacy source，但不再被 main 输入。旧内容已按 migration map 拆分、合并或降级；没有静默删除。

## 3. Source SHA-256 snapshot before migration

```text
29898085477940709B7FD588CA5DAFF1817D5A6440DA273697FDE39DD9077DA9  main.tex
258891FC4081BB39F7550E378F636E92098507A99CBDB943EACF79A1F5E9D5CC  refs/references.bib
1D57981D3B87F45AD3B70AE6641A5B1B52A65EB84D291547B84F3A295B7D65E2  sections/01_研究问题.tex
0999E4CEB55F90B34CFBBC81464F434993A852AB3D3AC0AF0585F591CDB9FE57  sections/02_方法.tex
F6A6A541C78E51DCFC45945BD64FC403B58B9961FD60E2545EA9041B664E2FAB  sections/03_实验设置.tex
9C5423616D4BC455AE2773FF99F37961E31EE9D456994581CDB0130FFBAF7A04  sections/04_报告与可审计输出.tex
FFFEAC83A30BA7007C95EB23A1DD5A4FF8B04956459811D487F1341106D2A49F  sections/05_标注数据重训练.tex
FCD32368B01ACFEE4A05C417B8C0B909C90F37780E08E3D0B169D85C1B06E857  sections/06_讨论与局限性.tex
856D5428AC238FC8AA40C7813388CD744F462CCE6E531EC76A337F0DEB0DAA0B  sections/07_与审稿员预期批评的预设回答.tex
0A86CE5F07BDFE3C77B3B0C20F2BC87C005D8EF5673B32BA59D146B45A8B94E8  sections/08_预期贡献总结.tex
```

## 4. Target SHA-256 snapshot after migration

```text
25491A7DC162586C4FE3DB29B73025D78302F2049BB14721C512B61810FCD83F  main.tex
258891FC4081BB39F7550E378F636E92098507A99CBDB943EACF79A1F5E9D5CC  refs/references.bib
0D8290595B1E5B0B2F6451267FA6A9D03FC2D896D3C3264CBD289C3F27BF6AE2  sections/01_引言.tex
E1CE3D5F4EC87AEA8445D79A0FA1BFA7AD4A8EA803428DEE0B9551317A218BFC  sections/02_相关工作.tex
75B8CC2704DDD8B458151A9482B578CA93C4D66B9AC3FD4FA36E8C1DB20690C3  sections/03_研究协议与数据生命周期.tex
AD25FD06FF6EAF328F40BA27966E32BEAF1BA543BE697E5D803F4383B0A25575  sections/04_测量模型与双链路工人画像.tex
299D6B6B99EC84D790E73E2F316B180922EBC488D91131BADCAF814CD822457C  sections/05_路由策略与统计分析.tex
F2F760B34CA6D194AFC0D4D86E4B759129B004E4A9E95B555884FA9A2D01D282  sections/06_实验结果.tex
8E96433CD2A29570AB9E4A3B1D258B093996FF3A578D736E517FCB8C6C8B634E  sections/07_讨论与局限.tex
912B8D614D7BAE6C17F2A4C7A8D59E0DA4F313CDB517C6D3244768F6AC4FDE92  sections/08_结论.tex
```

附录 `A1`、`A3` 和 bibliography 未修改；`A2` 与 `A4` 在本次限域修正中同步了图像 accounting、4-vs-4 paired design、符号方向和统计降级合同。

## 5. Migration actions

| Source | Target | Action | Status | Notes |
|---|---|---|---|---|
| `01_研究问题.tex` | `01_引言.tex` | rewrite/copy | migrated | RQ 改为三个一级 RQ，RQ3 下设 RQ3a/RQ3b。 |
| 无独立旧 section | `02_相关工作.tex` | add | migrated | 增加 related work，不编造引用结果。 |
| `02_方法.tex` protocol/meta/OOS/P1 chunks | `03_研究协议与数据生命周期.tex` | split/merge | migrated | 加入 estimand-specific gate、P1 retrospective integrity、C1 state gates。 |
| `02_方法.tex` metric/consensus/profile/counterexample chunks | `04_测量模型与双链路工人画像.tex` | split/merge | migrated | 保留 LOO、IAA、geometry、scene、profile 和 counterexample 实质内容。 |
| `02_方法.tex` routing chunk + `03_实验设置.tex` | `05_路由策略与统计分析.tex` | split/merge | migrated | 加入 offline replay leakage control；保留 paired design、MDE、统计细节。 |
| `04_报告与可审计输出.tex` | `06_实验结果.tex` | merge/reframe | migrated | 原报告与 audit 输出保留，结果章节增加 TODO/CLAIM-BLOCKED 防虚构标记。 |
| `05_标注数据重训练.tex` + `06_讨论与局限性.tex` | `07_讨论与局限.tex` | downgrade/merge | migrated | 重训练、Manhattan 等明确降级；局限正文保留。 |
| `07_与审稿员预期批评的预设回答.tex` | `01/07/附录` | absorb | deferred audit | 原文件保留 legacy，未激活。 |
| `08_预期贡献总结.tex` | `01/08` | absorb | deferred audit | 原文件保留 legacy，未激活。 |

## 6. Static verification

已执行：

- `main.tex` 的 12 个 `\input` 文件全部存在；
- active input chain 的 environment `begin/end` 数量逐文件匹配；
- active input chain 未发现重复 label；
- active input chain 未发现 unresolved `\ref`/`\autoref`；
- active input chain 的 brace delta 为 0；
- bibliography key 与当前 `\nocite` 一致；
- 新 section 中未发现误生成的双反斜杠 command escape；
- `git diff --check` 通过（以可纳入 Git 的文档变更为准）。

旧 legacy section 因保留历史内容会含重复 label，但不再被 `main.tex` 输入，不进入实际编译链；迁移审计按 active input chain 判定。

## 7. Compilation and PDF comparison

本机探测结果：

```text
xelatex: MISSING
lualatex: MISSING
pdflatex: MISSING
latexmk: MISSING
bibtex: MISSING
biber: MISSING
docker: MISSING
```

因此未执行 `xelatex`/`latexmk`，没有新 PDF、编译日志、warnings、undefined citation/reference、overfull/underfull box 或 output PDF SHA 可报告。Overleaf 是正确的下一步编译环境；上传后应使用工程声明的 XeLaTeX，完成 bibliography 和多轮编译，再记录新 PDF SHA 与视觉对照。

旧方法路线 PDF 已记录 SHA，但不能作为新正文编译结果或源码替代。

## 8. Current completion state

`partially_migrated`：实际 LaTeX 章节输入和主轴已建立，旧实质内容按 section 复制保留；本次限域修正同步了 $R_u/D_u$ 与 $B_u/F_u/Q_u$ 方向、RQ3a descriptive artifact、RQ3b image-level cross-fitting、active-time identity、RQ2 4-vs-4 paired design、C1 当前状态和唯一图像 accounting。由于本地缺少编译环境，compile/PDF visual QA 未完成；结果章节无虚构数值，未完成 evidence 统一以 pending/not\_evaluable 表示。

## 9. 本次限域修正记录

- `R_u` 只来自 C1/C2 `Calibration_manual` eligible LOO；P1、semi、C2b、Main/Test/Validation 不回流。
- `D_u=(G_u,S_u,C_u,V_u,P_u)` 五维均 higher-is-better；`B_u/F_u/Q_u` 为独立 lower-is-better risk signatures；`T_u/U_u` 仅 legacy aliases。
- RQ3a 只保留三组小 worker 描述性 predictor-target 关联，artifact 名称为 `p1_to_c1_descriptive_directional_check.csv` 与 `p1_to_c1_descriptive_directional_check_report.md`，当前 `formal_predictive_validity_status=not_run_blocked`，不进入 Bonferroni 六个主检验。
- RQ3b 固定 image-level cross-fitting（按 `base_task_id/image_id`，同图同 fold）；区分 operational frozen state 与 replay-only cross-fitted shadow state；RQ3b-1/2 分别报告首选 worker 条件性质量与序贯预算/最终 medoid/LOO-compatible consensus。无独立 reference 时最终聚合仅 descriptive。
- active-time primary 单位为 worker-task-annotation，`eligible_for_RQ1_time` 必须满足 exact/owner-valid/independent/legal-version/non-parent/non-task-fallback；lead/task fallback 只 sensitivity/audit。
- RQ2 主设计为 manual 有效标注固定种子抽 4 份 vs semi 4 份，并要求 worker-image 隔离。
- 当前状态：C1 launched=23、每人约至少 33 张、每图目标 $k\geq5$；C1 valid/completed 待 closeout artifact。PreScreen_oos 主包 9，audit-only 1 不计入主包；主运行 unique=352，含 audit-only touched unique=353，剩余=105。
