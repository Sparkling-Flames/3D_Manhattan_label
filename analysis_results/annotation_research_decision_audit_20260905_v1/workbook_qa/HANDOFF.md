# 工作簿交接

## 最终产物

- 工作簿：`../研究数据审计与50张候选审查.xlsx`
- 本目录保留说明页、AI50、复算与曲线三张 PNG 预览，以及 `VALIDATION.json` 和 artifact-tool inspect 记录。

## 验证结果

- inventory：`pass_with_known_gaps`；全量合同测试 `7 passed in 461.44s`。
- 盘点分母：machine 314；预筛中有历史记录的图像 148；无历史记录 166；人工原始 30（in_scope 26 / out_of_scope 4）；remaining 136；old registry 214；旧42 复算子集 42；AI50 50。
- 全历史底座：2501 canonical records、214 images、26 workers、22 buildings；全量严格几何可计算记录 2427。
- 引用审计：43733 links；40801 local exists；2930 remote URL not locally checked；2 条历史临时路径缺失。
- workbook：8 张表，109759 bytes；重读成功；`#REF!/#DIV/0!/#VALUE!/#NAME?/#N/A` 命中 0。

## 限制与边界

- AI50 仅 advisory；人工最终判断与 reference 最终裁决列留空。
- room 映射只有官方 pano→数值 `region_class` 行对齐，不是 room-instance/空间拓扑 ID。
- Bi test manifest 的 2 条 degenerate 保留并标记；HorizonNet 独立权重/覆盖仍未确认。
- 未运行 SHA-256（按用户要求）；未下载、训练或新增推理。
- 完整引用明细入口为 `../inventory/reference_link_audit.csv`；工作簿只放 status/package 汇总与 2 条真实缺失项。
