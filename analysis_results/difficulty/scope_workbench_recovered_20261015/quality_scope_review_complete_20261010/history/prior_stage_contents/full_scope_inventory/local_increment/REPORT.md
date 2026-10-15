# 本地返回包独立核验

## 可直接接入
- `integration_verified69.json` / `.csv`：69条云端1648 unique comments 中未见的精确图片+原文绑定；36条近期原记录，另33条历史原评语/上下文。约124 KB JSON。
- 这69条不是69个“范围不同”的判定，也不是69个独立投票。36条包含同范围、更正、细节/可见性；另33条中12条是跨图关系上下文，7条是双标注比较。
- 原始记录证据分别保存在 `verified_recent36.json` 和 `additional_current_user_comments.json`；接入版保留文件、指针、记录SHA256、原始created/updated与报告updated字段，避免混用时间。

## 36条近期记录
36条原文全部与返回包内嵌raw_record对应字段逐字一致，36个 image_id/image_code 全部符合259图库存。22条 record_id+object_id+image_id 与3152几何记录完全一致，14条为图片或墙组层级，不应人工补造单一record_id。
LOCAL36_30的两个墙组issue created_at分别为2026-10-07T15:04:26.909Z、15:04:52.188Z，而父决策updated_at为15:05:53.139Z；LOCAL36_32 issue created_at为15:07:07.919Z，父决策updated_at为15:08:17.534Z。二者并非来源冲突，应保留时间层级。
所有验证均针对返回包保存的raw_record，不声称重新打开或鉴定了用户电脑上的原文件。

## 额外独立来源
在全量候选的原评语字段与945条补充记录中，核对出33条当前259图内新增绑定：
- 21条用户原评语，包括7条精确成对对象比较、早期研究者审核、候选图选择、相机/空间交界评论。
- 12条跨图同房/拍摄重点讨论上下文。这些跨图文本在多个图片下出现，不能作为逐图独立范围错误票。
- 另19条基集外的用户评论绑定分列在 `additional_outside259_user_comments.json`，不混入259图工作台。
对于traits/annotation、traits/image、issue_decisions等导出未填image_id的记录，先从结构化指针恢复精确身份再比较；18条恢复后已在云端，未误算成新增。
全部7组成对对象ID均能在3152记录中精确映射同一图片，映射record_id已写入pair_bindings。

## 暂不能作为已核实原评语直接接入
- `point109_provenance_pending4.json`：4条点审核reviewer_note在多个镜像中出现，身份与几何库存匹配，但本包没有对应109审核原始raw_record及审核时间。保留待核，不能把文件mtime当审核时间。
- `group_history_provenance_pending.json`：35个图片绑定实际上只有9段不同的组级历史文字；完整候选虽给raw_current/note指针，却未嵌入原记录，组级指向不能逐图摊作真实范围差。
- `all11705_coverage_audit.csv` 对全部11705候选做了覆盖/来源层级清点：1962候选已有云端同图原文，88对应已审阅本地原评语/上下文（含19基集外），35组历史待核，4点审核待核，其余9616暂不升级为用户原评语。后者含AI派生视觉解释、同房关联、待核来源；这不是逐条判定它们全部无用。

## 123条读文件缺口
`search_errors123_audit.csv` 保留每条路径及错误。119条来自早期C1分配/预筛/审计存档，但其中有scope审计命名，未读到内容就不能证明与范围评论绝对无关。
剩余4条为 confirmed_processing_audit.csv、confirmed_user_decisions.json、USER_DECISIONS.json、same_room_selection_registry_v2_20260912.json，可能包含审核或同房原记录。最后一个文件在别处读取到3个同名来源，但未做字节等同性核验；另外3个在complete candidates没有同名来源命中。这是仍待核实的覆盖缺口，不是已证明漏掉了特定范围评论。
本次是完整候选清点加有限原评语来源核验，不是全磁盘无遗漏证明，也没有完整逐条裁定11705段文字语义。

uNb9QFRL6hY-88的“就是记忆中的图”按用户最新确认处理；不代表新polygon、GT、资格或分数获得批准。未修改任何GT、资格、分数或输入库存，未执行返回包脚本。
