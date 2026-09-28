# 两人审核整理与二次复审

打开 [复审页面](index.html)。原图通过仓库相对路径读取，保持目录结构；不需要网络、不提供ZIP。

当前执行规则：[两人审核归并与二次复核SOP](../../docs/thesis_main/两人审核归并与二次复核SOP_20260925.md)。一正独审69图与双方全部曾选排除126份必须复核；本轮以两份JSON为主，历史材料辅助。

配套报告：[逐图疑问](逐图疑问汇总.md)、[同房疑问](同房疑问汇总.md)、[原始核验与修复](原始核验与修复说明.md)、[人员候选统计](人员候选统计.md)。

## 已核验范围

- 两份审核共1544条记录，对应1529份作答、239图；696条非空评论均有逐条释义。
- 同作答交叠15份，选项代码不同10份，不能解释为意见冲突。两位作者的原选项分别统计，不合并为有效性判断。
- 默认仅197张有具体未决问题的图片、645份相关作答进入复核提示；239张是完整查阅库，不是全部重审任务。
- 当前全部3019份原始导出核验结果见 [source_audit.json](source_audit.json)。当前页面可核验，不代表能还原旧浏览器缓存与当时选择的参考层。
- 同房支持覆盖187图；其余52图不推测房间归属。

## 研究与裁决边界

门洞相关图先全部单列；已有OOS条件或评论线索同样单列，含疑似或反转意见的保持待确认。暂不做这些图的人员GT-IoU／质心评价或3D。图片范围、参考可信性、具体作答执行质量、计算失败分开记录。所有保留都不自动等于符合GT；GT存疑也不自动等于每一种标法都合理。原始及人工修订GT不改。

共识稳定和靠近GT是不同问题；无法形成有效区域时保留失败，不能硬造共识。分簇默认共享x后的全局亲近度，完整链接仅对照；沿现有25.6px阈值和同点数门，属于探索性几何分区，不是合理空间的真值。仅点集匹配者复用。该层不随临时裁决自动重算。

原始／有效／共享x点分层。共享x点的3D仅沿已有配对环，不拟合Manhattan，不代表正确顺序；本轮顺序编辑禁用。修复确认只记录意见，绝不立即补删点；借用补点注明供体，不恢复为独立票。新旧冲突交用户确认，历史结果不追改。

人员统计见 [workers.json](workers.json)，按图片单列状态与manual/oos/semi分层；reviewer_options按作者分别保留原选项，不跨作者合并。你的“待定”表示不确定且想复核；GT问题或不同标法可能选“GT与范围争议”或“保留”（后期保留较多）；门洞/OOS通常选范围争议或待定；部分配对/顺序问题选“配对”。一正的GT与范围争议表示标注本身可接受、只是范围不同，不能解释为GT错误。不能将定向可疑队列比例解释为人员总体错误率。

## 数据与接口

- `evidence/user_review.json`、`evidence/yizheng_review.json`：用户附件原字节；任何构建不会把旧选项导入新最终裁决。
- `commentary.json`：1544审核事件，event_id=reviewer:canonical_id；原评论及逐条释义、对象层次、跨人/同图引用和未决指代。人工整理的释义不是新增标注真值。
- `images.json`、`rooms.json`：每图一次，图级疑问、历史来源及受支持同房映射；`geometry_hold/quality_hold`仅本轮暂缓标志。
- `source_audit.json`、`repair_history.json`：原始task/annotation/region与点坐标对应；已执行、提出未应用的修复及真实配对失败原因。
- 页面数据 `review_reconciliation_v1`；本轮裁决 `review_reconciliation_decisions_v1`，binding.id=`review_reconciliation_20260925_v1`。新image_decisions和annotation_decisions独立保存，初始为空。
- 图级记录status(pending/resolved)、category(doorway/doorway_difficult/doorway_annotatable/oos/reference_concern/ordinary/undetermined)、comment、updated_at；旧doorway保留难度未分。作答记录status、verdict(usable/invalid/repair_needed/undetermined)、comment、repair_confirmation(unreviewed/confirm_existing/needs_followup/reject_proposal)、updated_at、view_context。待修复/未确定保持未解决。
- shared_image_context_event_ids和same_image_links保留同图图片说明与引用候选；含“同图”的引用评论不互相充当背景来源，其原文仍保留，缺失明确记录，不传播个人排除。scene_rule只召回条件核查，不确认OOS或自动排除。
- 新记录导入严格核对版本、ID及字段；旧文件只读查看，不能覆盖新结论。浏览器localStorage独立保存，跨浏览器请导出备份。

## 使用

先按复核任务选择：全部、一正复核、全部排除、补点修复、标准一致性、资料库；再用图片线索筛门洞/OOS/配对/待定。默认队列完整覆盖一正独审图、双方所有排除作答，并保留明确待定、具体评论、相似排除差异、修复询问和场景点数核对。followup_reasons逐条记录入选依据和相关作答，followup_ids是对照对象，不要求全部重新打标签。确认OOS少于8有效点会预选排除建议但不自动保存；跨门槛修复先核验，难标门洞不直接套阈值。图级确认不改成员有效性。新判断独立保存，旧数据不覆盖。

复建：`python -m tools.thesis_main.analysis.build_review_reconciliation_20260925`。首建需Downloads中两份原件；之后优先使用本目录evidence原件，可用--user-review/--yizheng-review显式指定。审核证据与逐条释义不匹配时中止，不猜测继承。
