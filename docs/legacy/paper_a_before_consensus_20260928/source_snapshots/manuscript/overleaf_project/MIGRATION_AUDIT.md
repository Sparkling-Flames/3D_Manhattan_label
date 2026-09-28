# Paper A vFinal → Overleaf 迁移审计

## 内容真源与双层结构

- 唯一完整内容真源：
  `docs/thesis_main/Paper_A_新版完整论文提纲_vFinal_Draft.md`
- 第一层“简洁主文叙事”：
  `sections/00_研究总览.tex` 原样引用此前短稿的 01--08 节。
- 第二层“完整方法与分析合同”：
  vFinal 第 1--18 节逐节对应新的 01--18 `.tex` 文件。
- 完整附录：
  vFinal Appendix A--I 逐项对应 `appendix/A_*.tex` 至
  `appendix/I_*.tex`。

旧短稿没有删除，也不再承担完整方法合同。旧 A1--A4 文件未进入新的
`main.tex`，以免用历史附录替代 vFinal 的 A--I 合同。

## 完整正文映射

| vFinal | Overleaf 文件 |
|---|---|
| 1 引言 | `sections/01_引言与研究问题.tex` |
| 2 相关工作 | `sections/02_相关工作_完整.tex` |
| 3 总体协议与数据生命周期 | `sections/03_总体协议与数据生命周期_完整.tex` |
| 4 数据来源与单一 operational reference | `sections/04_数据来源与OperationalReference.tex` |
| 5 四类证据与三类共识 | `sections/05_证据共识与三状态观测.tex` |
| 6 P1 | `sections/06_P1高信息诊断与预测.tex` |
| 7 C1 | `sections/07_C1三轨工人测量.tex` |
| 8 HoHoNet/HorizonNet 任务风险 | `sections/08_HoHoNet任务风险.tex` |
| 9 C2 | `sections/09_C2桥接收缩与精度补齐.tex` |
| 10 强 Global 与 Full-Integrated | `sections/10_StrongGlobal与FullIntegrated.tex` |
| 11 T1 | `sections/11_T1条件效应.tex` |
| 12 V1 | `sections/12_V1政策试验.tex` |
| 13 试验分布与生产标准化 | `sections/13_试验分布与生产标准化.tex` |
| 14 V2（可选） | `sections/14_V2外部支持审计.tex` |
| 15 统计分析与功效 | `sections/15_统计分析与功效.tex` |
| 16 结果章节结构 | `sections/16_结果章节结构.tex` |
| 17 讨论 | `sections/17_讨论_完整.tex` |
| 18 结论 | `sections/18_结论_完整.tex` |

## 验证记录

- 18/18 个顶层正文节已进入 `main.tex`。
- Appendix A--I 共 9/9 个附录已进入 `main.tex`。
- vFinal 正文的二级、三级标题数量逐节与 LaTeX 完全一致。
- 递归解析 `main.tex` 得到 37 个活动 TeX 文件，缺失 `input` 为 0。
- 活动文件的花括号、环境栈和未转义 `$` 静态配对错误为 0。
- 未发现 Markdown 标题、代码围栏、粗体或 Markdown 链接残留。
- 已尝试 Codex 自带 Tectonic 烟雾编译；首次受到 Windows 编码包装器影响，
  修正编码后确认 Tectonic 可用，但资源访问/下载在本机环境超时，未生成 PDF。
  最终 PDF 仍需按 README 在 Overleaf 使用 XeLaTeX 编译。

## 冻结边界

- 未修改 C1 原始 export、assignment、正在进行的标注或 Label Studio 配置。
- 未把尚未产生的 C1/T1/V1 数据写成结果。
- T1/V1 的工人失败、政策失败、外部系统事故、重跑与行政删失按 vFinal
  原文迁移，没有用旧短稿覆盖。
