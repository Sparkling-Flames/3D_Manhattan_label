# 同房大块严格匹配重建终稿（20261023）

入口：[中文综合报告](REPORT_ZH.md) · [主张索引](CLAIM_INDEX_ZH.csv) · [方法支持](METHODS_AND_SCOPE_ZH.md) · [复算](REPRODUCE.md) · [字段接口](FIELD_CONTRACT.md)。

实际main：`e92abe8631d7f01dc192ee796b46f295ece37a6d`。旧大块设计和111,054端点未恢复；这里是用户授权后的独立重建设计，62,676唯一ABC、311,333正式去重端点均已执行完成。不是旧包编号的改名，也不是以旧报告数字为目标的重演。

普通Manual结构主域78图对9楼；联合Q/T、其它范围和门洞分开。Semi无m>4严格容量；已有人数路径的Semi结果在独立R03中保留。

解压R01、R04A、R04B、R05及所需R06到同一仓库根，目录为`research/same_room/same_room_large_block_rebuilt_20261023/`。R02提供首个案例完整输入；R04A提供第二个案例。R03解压到独立人数专题；R00是`recovery/`原件档案。新大表以team_key/event_id/path_transition_id连接，原有main大表只按依赖引用。

方向和成员：[方向小表](direction_tables/DIRECTION_READABLE_ZH.csv)、[楼外角色](direction_tables/FOLD_DIRECTION_ROLES_MEMBERS.csv)、[精确背景索引](direction_tables/DIRECTION_BACKGROUND_MEMBER_INDEX.csv.gz)。几何按`ENDPOINT_ARCHIVE_LOCATOR.csv.gz`找到R06分包与JSONL行号。所有失败、未知与缺时间均保留。

报告修订与旧研究衔接在[integration](integration/README_ZH.md)。本轮有限研究已完成，不再扩展分类或融合实验。
