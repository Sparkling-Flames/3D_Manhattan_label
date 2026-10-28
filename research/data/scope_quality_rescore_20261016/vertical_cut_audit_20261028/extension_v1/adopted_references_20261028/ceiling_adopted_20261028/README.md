# 顶面人工判断采用：30份当前有效参考

2026-10-28。依据用户导出的30条判断，以及“代表点号”“如果有微小的误差,你就平均一下”的后续澄清完成修正。不再要求用户重复视觉验收。

- 24份采用复核页展示的全点三维顶高均值。
- 6份以用户指定点对为代表，取该点所在近同高组的三维顶高均值，固定为水平顶面；不要求组内点数严格过半。
- 代表点组为：q9-13的1—8、11；X7-05的1—3；UwV-09的2—8；uNb-47的1、2、3、5、7；yqst-31的全部10点；yqst-04的全部4点。
- 近同高阈值为相机高度的0.0002倍，组成员在0.00015至0.001的容差范围内不变。这是本批代表点分组规则，不是正式难度标准或普适几何阈值。

## 几何与误差解释

当前水平地面和相机高度归一化模型中，三维顶高由top y与bottom y共同决定。先从bottom求水平距离，再结合top仰角求顶高；不直接平均ERP的top y。本轮固定底面，仅更新top y，所有bottom坐标和全部x数值逐值保持。不能把原来的同高残差归因于top单方错误；bottom误差同样会传播到高度和残差。

30份新顶面均水平且底面正交。wc2-14的GT暂停、7y-16与wc2-23的历史身份、wc2-26的非当前旧版本均保持；未评审参考与所有资格字段保持原样。原始GT、人员作答及冻结v1/v2不变。

## 文件与字段

- USER_REVIEW.json：用户导出原件内容，保存点号、备注和审核时几何。
- USER_ADOPTION_RECEIPT.json：后续澄清、分组容差及采用口径。
- ADOPTED_REFERENCES.json：本次30份采用几何，保留target_id，以reference_version区分新版本。
- REFERENCE_CATALOG.json：完整合并目录；上级extension_v1/CURRENT_REFERENCES.json已指向本版。
- HEIGHT_CHANGES.csv：逐参考decision、representative_pair_1based（全点均高为空）、averaged_pairs_1based（一基点对编号列表）、adopted_height_h（相机以上顶高/相机高度）、group_height_range_h、max_top_y_move_px（1024×512坐标）及身份。
- CHECKS.json：几何、资格保留检查和旧评分失效目标列表。

新参考增加ceiling_adoption、previous_reference_version及score_status_for_reference_version字段，旧字段语义不变。6份代表点方案最大顶部移动分别为q9-13 7.002217px、X7-05 5.710991px、UwV-09 1.703636px、uNb-47 0.552296px、yqst-31 0.012729px、yqst-04 0.000534px。

## 验证与接续

`python -B -m pytest tests/test_ceiling_adoption_20261028.py -q`：3项通过，覆盖上下射线共同决定高度、组内平均、无效点号/容差敏感拒绝、底部原值、未评审对象及排除状态保留。六张代表点方案的静态叠线已检查；用户明确无需再展示修正结果。不新增浏览器页面。

复现：`python -B -m tools.thesis_main.analysis.adopt_ceiling_review_20261028`，默认读取本包USER_REVIEW.json。

本轮未重跑质量评分或融合。旧BOUND_SCORE_REUSE.json属于修正前参考，不能作为这30份新顶面版本的分数；新目录已明确标记not_recomputed。后续计算必须按新reference_version区分缓存。协议、难度标签和人员分类不变。

本包位于既有多空间参考专题；目录登记采用此入口，不把每个支撑文件升格为独立主题。
