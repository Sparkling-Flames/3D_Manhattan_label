# 人员类别组合与融合结果研究｜2026-10-19

先读 `output/personnel_composition_report_zh.pdf`（27页中文报告）。本包保留两条实际分类路线、完整候选筛查、具名构成与比例比较、失败和反例，以及可直接重放的7个代表案例；不包含逐队全流程缓存或原图全集。

## 本轮最有用的结果

| 发现 | 建筑留出验证结果（B8L2，建筑等权） | 使用边界 |
|---|---:|---|
| 历史质量高类替换低类，纯类各9人 | +7.98；35图、6楼 | 可作基础选人信号；仍有同图反例 |
| 历史几何关系反向类 G2 对 G1，各9人 | +6.40；42图、6楼 | 整体有效；同来源、近Q控制后独立增量弱 |
| 反向角色 R5 对 R2，各5人 | +10.11；28图、6楼 | R5仅6人，不能据此承诺新人员泛化 |
| 困难条件 H2 占比，9人中由3人增至6人 | +13.71；5图、4楼 | 条件规律，支持范围小；不要与全体难图混同 |
| 固定4名H2，加入H1使总人数8→9 | −6.51；5图、4楼 | 有实际阈值与节点身份机制；增加人数并不总改善 |
| 混合相对较好纯类 | 多数冻结候选未维持优势 | 保留局部复现正例与更强反例，不建议一律混类 |

589,990条主请求、583,261个不同实际团队覆盖126池、106张图、12栋非历史建筑、59人。分组为10栋历史楼、6栋发现楼、6栋验证楼。既有v2已被多轮研究：本轮验证是固定规则下的建筑留出和新成员组合复查，**不是全新外部盲测**；团队数量不等于独立图片数量。

## 阅读与证据索引

| 内容 | 路径 |
|---|---|
| 中文报告、主要结论与局限 | `output/personnel_composition_report_zh.pdf` |
| 主表（6条）及完整成员类别映射 | `analysis/report_tables/`；`analysis/SELECTED_WORKER_CLASSES.csv` |
| 简要搜索台账、覆盖与遗漏 | `analysis/SEARCH_LEDGER.csv`；`analysis/SEARCH_COVERAGE_NOTES.json` |
| 全部候选、历史特征与两路类别 | `analysis/forward/`；`analysis/reverse/` |
| 固定构成逐图／逐楼小表、稳定性、低尾和失败 | `analysis/composition/frozen_grid_results/` |
| 具体方向、同背景块替换、Q／来源和删人敏感性 | `analysis/composition/compact_block_evidence/`；`block_fixed_highlights_compact.csv`；`block_source_Q_control_comparison.csv` |
| 固定成员加入链与投票阈值 | `analysis/composition/nested_discovery/`；`nested_validation/` |
| 7例精确成员、完整冻结记录、参考和最终几何 | `analysis/representative_cases/cases/` |
| ERP／BEV／3D、成员叠图、结构局部放大 | `analysis/representative_cases/figures/` |
| 人数／比例／效用曲线和绘图小数据 | `analysis/figures_summary/` |
| 原图精确Release索引与6图核验清单 | `analysis/visual_sources/` |
| 复现入口、依赖、源码与独立审查 | `analysis/reproduce.py`；`analysis/REPRODUCE_ZH.md`；`analysis/independent/` |
| 文件完整性 | `MANIFEST.json`；`SHA256SUMS` |

## 优先人工看这几例

1. **C05／Uw-09**：相同3人背景、同样换2人，换入困难角色类后遗漏显著减少；A/B只是分数接近，结构不满足主稳定条件。
2. **C03／Uw-22**：固定4名H2，8→9人时同一4票节点因门槛4→5失选。看局部放大及原生身份组。
3. **C04／X7-07**：12→13人总分提高，但三个6票结构组失选、转角覆盖下降。需人工确认参考中的细碎转折与范围语义。
4. **C06／q9-03**：保持同来源和人数，高历史Q成员换入后B8L2下降23.42，是基础选人规则的重要反例。
5. **C07／yqst-25**：混合在新实际成员中仍优于较好纯类均值11.51，但内部波动大，只支持局部互补。
6. **C01＋C02／yqst-27**：混合早期优势在新成员中消失；同构成既可能稳定但错，也可能总分相似而结构相差很大。两个案例是同一张图。

## 最短复现路径

1. 按 `analysis/REPRODUCE_ZH.md` 第1–2节安装固定依赖，并从两个固定Git提交恢复原生融合和评分代码。
2. `python analysis/reproduce.py quick --restored /绝对路径/personnel-restored --out /tmp/personnel-quick`：只凭案例内记录重放21队，检查B8L2、D10、最终几何和机制。
3. `python analysis/reproduce.py requests --restored /绝对路径/personnel-restored --out /tmp/personnel-requests`：生成13份主请求和派生FINAL，逐文件SHA与每个实际成员签名校验。
4. `full` 入口生成全量重算脚本；运行脚本才执行全量融合。报告与5张汇总图可直接从包内小表重绘，无需全量重算，命令见复现说明。

本包不重复封装原图或大型冻结输入。案例图已经使用Release原字节制作；若需要重新画图，可按精确图号执行第5节的部分提取命令，仅取6图。字体子集及其OFL许可已附，字体栅格化可能影响少量边缘像素，不改变数值或几何。

在解压目录执行 `sha256sum -c SHA256SUMS` 可逐项校验文件。`output/DELIVERY_QA.json` 记录实际交付目录的重放与排版核验，`analysis/independent/ENTRY_PORTABILITY_AUDIT.json` 记录全部请求的物理重建。包中不含虚拟环境、仓库副本、全体距离矩阵、逐折模型或逐队状态缓存。
