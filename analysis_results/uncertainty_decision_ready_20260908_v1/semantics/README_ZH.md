# 人工评论与响应对象连接

本目录是已有审查记录的整理，不是新增 50 图视觉审查。保留 50 图完整原问卷，45 图有非空评语；逐条核对与原始 JSON 备份一致。4 条后续直接补充优先用于解释，原选项和原评论保留。完成状态不表示确定，空白最终裁决保持空白。

## 已经可以复用什么

- 50 条已有范围陈述（来自旧 AI 阅读提取，包含逐字引文及其解释）加上 V04 后续补充的显式对象连接，共 51 条。引文是人工原文；解释、范围词提取和目标解析仍是 AI 整理，不能伪装为逐条人工确认。
- 280 个既有显示对象的身份索引：54 份真人响应全部连接到唯一 canonical 身份，226 个是模型或参考。它们只说明显示过什么，不能把全图评语自动赋给这些对象。
- 37 条“陈述—显示对象”关系，其中 4 条连接到明确真人响应：V04 的 W11、W15，V07 所谓“真人簇2”实际显示代表 W8，以及 V09 的 W2。其余为模型／参考关系。4 条是保守完成连接的证据子集，并不意味着只有 4 份标注有价值。
- V07 对显示代表的 enclosed 描述同时带有“缺失一部分房间”；V09 的 enclosed 描述同时带有“不特别准确”。范围解释与质量必须分开。
- V04 的两位工人指当时页面明确显示的 W11、W15；只连接这两份响应，不推广为两个人跨图的稳定倾向。

## 四条补充怎样使用

| 图 | 复用的人工信息 | 不应推断 |
|---|---|---|
| V15 | 门旁是拐角还是连续墙面无法判断；用户认为拼接扭曲并尝试正交失败 | 已证实场景非曼哈顿；必须让用户重新给确定答案 |
| V27 | 纳入右侧内部空间涉及分层天花，用户仍不知道如何完整处理 | 整图已最终判 OOS 或应统一删除 |
| V48 | 原本期待跨玻璃门，但按本图任务约束认为不应跨门 | 用户认可跨门为另一合规答案；所有曼哈顿布局都禁止跨门 |
| V04 | 天花下凸处截断可解释为 enclosed；扩展需忽略该处，GT 和两位工人属于前者 | extended 在当前规则下已获认可；这两位工人属于稳定 enclosed 类 |

## 剩余连接限制，而非重审清单

`unresolved_scope_targets.jsonl` 有 29 条记录，包括整图／潜在范围描述、含糊的“其余”集合，以及 V17、V36、V44 尚未充分定位的参考版本。这些陈述仍可用于解释场景和提出问题；在身份不够明确时，不进入响应级语义分类。

本轮没有发现需要现在重复询问用户的新问题，因此 `needs_user_now` 为 false。它不等于问题已经解决：只有后续分析确实依赖某条未连接陈述时，先定位旧页面或参考版本，再提出具体问题。不要要求用户把 50 图全部重做，也不要为形成训练标签逼迫 V15、V27 给确定答案。

V07、V31 和 V33 另一视角的已有点序确认另存 `prior_user_geometry_confirmations.json`，不能重新列为尚待用户给出点序。V33 另一视角的旧响应版本按原始 annotation/task/source 验证，保留精确版本身份；不能用同组当前 canonical 坐标替换。点序确认不表示所有坐标与范围已最终裁决。

## 文件与字段合同

| 文件 | 粒度及用途 |
|---|---|
| `case_evidence.jsonl` | 每图一行，完整人工记录、后续补充、旧 AI 阅读和旧待办分开保存 |
| `scope_statements.jsonl` | 每条陈述一行；`source_kind` 区分原引文加 AI 提取和直接补充；`later_supplement_takes_precedence` 标记后续优先 |
| `response_semantic_links.jsonl` | 每个已连接显示对象一行；`scope_of_claim=displayed_object_only`，绝不覆盖全簇或工人 |
| `display_identity_index.jsonl` | 全部显示对象；`annotation_identity` 包括阶段、block、项目、任务、工人、标注ID |
| `unresolved_scope_targets.jsonl` | 无法完全连接到具体响应的陈述及原因，保留原目标和引文 |
| `prior_user_geometry_confirmations.json` | 上游用户点序确认及具体旧版本连接验证，不产生新几何裁决 |
| `QA.json` | 覆盖数量和原问卷保持一致的检查结果 |

`canonical_annotation_id` 只表明身份或谱系归属。`raw_annotation_version_id` 指向具体版本；仅 `geometry_can_use_current_canonical=true` 时，显示对象就是当前 canonical 版本。旧版本仅保留身份关联，禁止替换其几何。

连接表的 `semantic_label_provenance` 区分 `human_quote_with_existing_ai_extraction`（人工原文、既有 AI 提取标签）和 `direct_user_supplement_with_ai_target_binding`（直接人工补充、AI 连接对象）。`semantic_label_is_final_human_adjudication` 一律为 false。通过 `statement_id` 回查逐字引文；机器可读 `scope_label` 不能被当作用户逐项确认的最终标签。

来源为仓库内三个已整理资料包：`human_review_reconciliation_20260907_v1`、`uncertainty_followup_analysis_20260908_v1`、`uncertainty_cloud_inputs_20260906_v1`。这是对已有来源的连接，没有宣称再次从所有原始导出重建历史数据库。

复现：`python tools/thesis_main/data_prep/prepare_scope_evidence_20260908.py --repo <仓库根目录>`。

验证：`python -m pytest tests/test_prepare_scope_evidence_20260908.py -q`，2 项通过；覆盖跨 block 不混同、旧版本不替换、非真人空身份，以及真实资料的 50 图原文保持、后续补充优先和集合评语不扩展。
