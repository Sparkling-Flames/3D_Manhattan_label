# 大团队直接 AC 延伸：固定 7 人换类块，原 Y 块逐人进入背景

本登记继续 `design/size_paths/` 的同一组 286 个锚点。严格 ABC 的末端为 n=N−14，此时所有不在 X7/Y7/Z7 内的人已经进入 D。保留 X7/Z7，将原 Y7 按固定 SHA256 排序逐人加入共同背景 D，得到 A=D+X7 与 C=D+Z7。实际换人数始终 m=7；n 从 N−14 增至 N−7，实际最大 n28。

**这是直接 AC。** Y 进入背景后不再存在与 D 不重叠的同类 B 队，因此该延伸不计算同类/跨类幅度差，也不称为 n28 严格 ABC。它回答大背景内固定 7 人换类块的方向、幅度、形状、时间与失败是否继续变化。源类成员逐人进入背景的条件必须保留。

每条路径保留全部 8 个 n，包括引用已有严格末端的 k0。7 个新增步骤都由同一人同时加入 A、C；没有结果参与排序或路径选择。登记 1 条原 Y7 排列/锚点，未声称穷尽全部 7! 顺序。每个 k 的可行具体背景子集数为 C(7,k)，类人数配置因 Y 同源类而只有 1 个；事件表保留这些覆盖数。

`EVENTS_EXACT.csv.gz` 给精确 A/C、D/X/Z、原 Y7、已加入/未加入 Y 成员、类别人数向量、原严格路径与事件、进入者、名义票门槛及历史角色。无 B 成员或 B 端点字段。`REQUESTS.json.gz` 为去重所需端点，`NEW_TAIL_REQUESTS.json.gz` 是 k>0 登记端点，`EXISTING_STRICT_TAIL_REQUESTS.json.gz` 引用严格末端；是否缓存命中须由执行阶段确认。`STRICT_TAIL_LINKS.csv.gz`、`PAIR_LINKS.csv.gz` 分别关联严格末端和前一步。

本目录登记代码只读冻结设计与标签，不读融合结果、不运行融合。各折标签、ALL 描述、历史角色与 phase 原样继承。

运行：`python design/large_team_ac_tail/code/register_large_team_ac_tail.py`（位于研究根目录时）。
