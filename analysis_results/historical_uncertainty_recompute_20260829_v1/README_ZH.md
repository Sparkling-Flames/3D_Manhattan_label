# 历史标注不确定性复算（讨论用）

## 口径

- 中英文项目在同一图像内合并；语言仅保留为项目/人群敏感性字段。
- 历史高密度集合为 42 图、1,055 条规范标注，42 图均来自 HoHoNet test split。
- 无 reference 曲线以 42 图为主；P1/C1 只作阶段敏感性。
- reference-relative 聚合质量曲线固定为 C1 12 图主分析、P1 29 图敏感性、P1 排除 task 564 后 28 图敏感性，以及显式图像等权的 41/40 图合并敏感性；配对边际变化曲线报告前述前三层与 41 图合并层。
- 质量聚合器不读取 reference：0.95 complete-link、唯一 partition、最大簇 medoid；supported multimodal 与 not-evaluable 均不强制交付。
- 所有 k 前缀来自同一确定性随机排列，因而 k→k+1 为配对嵌套比较。
- 置信区间按 building 聚类 bootstrap；曲线推断仍限于历史 worker roster。

## 当前可直接读出的事实

- reference-ready：41/42；C1=12，P1=29；P1 task 696 因 oos_insufficient 排除。
- 共同 reference-quality 风险集最大为 k=13；不能把图上 k=20 点写成 41 图共同实测。
- pooled 41 图在 k=13 的 GT-blind 自主交付率为 0.519，resolved-only quality 为 0.940，delivery-adjusted sensitivity 为 0.493。
- `delivery_adjusted_quality` 将不交付编码为 0，只是明确标注的交付敏感性，不代表真实几何 IoU 为 0。
- oracle best-of-k 未计算，也不得作为主质量曲线。
- 没有把“有害错误率”写入结果，因为实际 harm 与严重错误阈值尚未冻结。
- 成本只允许解释为“每新增一条有效 eligible 标注的边际变化”；不声称 production cost 或节省。
- `generic_multimodality_status_reproduction_rate` 只表示再次出现某种多模态；它不再被命名为“少数模式捕获”。
- 少数结构另用全 strict-valid roster 在 0.95 阈值冻结的确定性第二排序模式计算：精确抽样可见、同一模式纯恢复、完整分区限制恢复和条件恢复。3/21 个多模态任务存在第一/第二或第二/第三支持数并列，另报排除这些排序并列任务的敏感性；该模式不是外部真值。
- 42 图的整体分歧分布按任务等权汇总；mask、boundary、wall、角点数分歧和无效提交通道分别报告，不合成单一分数。
- 当前 reference 相对共同质量支持只到 k=13；没有预设 SESOI，因此不能从本包确认“12–15 人质量平台”。

## 复算参数

- prefix replay：每图 200 次。
- 同一少数结构 replay：每图 500 次，k=5/8/12/16/20。
- building bootstrap：20000 次。
- k_valid：3–13；所有 41 张 reference-ready 图共同支持。
- 固定 seed：20260829。

CSV 均以 UTF-8 BOM 写出，可直接用中文 Excel 打开。完整简体中文汇总见同目录工作簿。
