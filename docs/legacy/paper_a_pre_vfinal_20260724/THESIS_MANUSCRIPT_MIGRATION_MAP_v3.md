# Paper A manuscript migration map v3

版本日期：2026-07-16  
状态：v5 positioning migration map；不表示正文或 PDF 已全面迁移。  
边界：保留 v3/v4 历史提纲和 inactive legacy sections；不回写 protocol、assignment、SAP、routing、XML、代码、测试、数据或原始工件。

| 当前材料 | v5 目标位置 | 动作 | 说明 |
|---|---|---|---|
| `main.tex` 标题/摘要 | 引言总纲 | 重写 | 改为“可审计的自适应全景布局标注”，加入四项资产和实现状态 |
| `01_引言.tex` | 第1章 | 重写 | Manual/Semi 识别设计、基础设施定位、三项一级贡献；RQ 不变 |
| `02_相关工作.tex` | 第2章 | 扩展 | 增加 dataset audit、challenge bank、worker lifecycle 定位 |
| `03_研究协议与数据生命周期.tex` | 第3章 | 重写/合并 | 增加 Manual/Semi 角色、三层生命周期和 C2b amendment 边界 |
| `04_测量模型与双链路工人画像.tex` | 第4章 | 重写 | 三层 task-condition map、model-bound Semi profile、四层 bank |
| `05_路由策略与统计分析.tex` | 第5章 | 保留并澄清 | 强化 Semi component 版本绑定和 fallback；不改时序合同 |
| `06_实验结果.tex` | 第6章 | 重写 | 只报告 closeout registry 计数；不把 planned `23×18` 当独立样本 |
| `07_讨论与局限.tex` | 第7章 | 重写 | worker-state refresh/失效、Paper B 边界、challenge bank future layers |
| `08_结论.tex` | 第8章 | 重写 | 三项一级贡献和证据边界收口 |
| `A2_数据集汇总表.tex` | 附录 | 扩展 | machine-readable artifact、condition map、四层 bank、lifecycle fields |
| `A4_测度与统计方法速查.tex` | 附录 | 扩展 | 新指标、artifact 字段、动态冗余参数和生命周期状态 |
| inactive `02_方法.tex`、`03_实验设置.tex` 等 | legacy | 暂不改动 | 不被 `main.tex` 输入，仅由本迁移图登记 |
| v3/v4 提纲与 v3.tex | 历史审计 | 保留 | 不覆盖、不追加 amendment |

## 必须删除或降级的旧叙事

- “论文已经完整验证 Semi-Auto 生产和 Semi-specific routing”；
- `23×18=414` 作为正式独立样本量；
- worker-specific scene LOO 改变正式 task set；
- weighted consensus 作为主干；
- counterexample 自动成为 GT 或 retraining data；
- refresh/re-admission 已经得到长期部署验证；
- C2b-Semi 是当前正式执行阶段。

## 正文尚未迁移的内容

正文迁移只覆盖 active `main.tex` 输入链。没有正式 C1 export、C2 freeze 或 thesis-facing replay 结果，因此结果数值、生命周期效果、challenge bank 冻结结果和正式 Semi-specific routing 仍未填入。
