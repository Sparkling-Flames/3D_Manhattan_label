# 全历史标注区域与质心复核

双击 [index.html](index.html) 在 Chrome 或 Edge 打开；保持本目录位于仓库内，因为原图及现有仪表盘样式通过仓库相对路径读取。无需服务器或网络。

- 3019份当前起点、259图；质心散点保持全量。默认队列为角点数量、现有配对环3D诊断、原始点号顺序线索、单人/二人簇、配对/墙带失败、既有错标与IoU辅助通道的去重并集。通道数与覆盖见MANIFEST.json。目标是筛查非墙角、乱标等明显无效标注，范围不同、单人簇与机器失败不能自动排除。未命中也不等于正确。Manual、OOS、Semi可分开筛。
- screening字段合同：cues为可重叠通道，details为说明，clusters记录历史shared_x完整链接/亲近度的簇大小与图内N；仅在有效点逐点匹配时复用。cluster_coverage明确缺失，geometry为既有Studio原始射线重建（不运行曼哈顿优化），order_basis表明真实环序未验证。角点数量在同图同条件至少3份时比较非众数；单人簇和至少6份图中的二人小簇独立召回。顺序线索只比较无向环边，不把点击次序当真实连接。
- 墙带及质心预览由 `consensus_region_20260923.wall_mask/centroid` 生成，1024×512等效像素。原始点、既有裁决后的点、共享x配对分开显示。圆周方向及R单列，不把低R方向差读作整体平移。
- `joint_distance_rank`、垂直/圆周/近质心专题只用于安排审核。既有case14明确错标单列；同图提及与作答裁决分开。人工选择不会改原始导出、3019份计算起点或正式资格。
- 裁决先保存在此浏览器的localStorage。请用“导出本轮裁决JSON”备份；导入前检查合同版本与canonical ID。换浏览器或清理站点数据前先导出。
- 导出字段合同：顶层 `schema=consensus_visual_review_decisions_v1`、`contract_version`、`exported_at`、`source`、`decisions`；后者以 canonical ID 为键，每项保存 `verdict`（retain/invalid/gt_scope/representation/pending）、`comment`、`image_id`、`worker_id`、`condition`、`code`、`updated_at`。导入只接受本合同版本、已知 canonical ID 与合法结论。
- 页面依赖仓库内259张原图，不能单独复制本目录当作便携包。本轮没有生成ZIP。

复建：`python -m tools.thesis_main.analysis.build_consensus_visual_review_20260923`。来源数值与方法边界见 `../consensus_research_20260923/README.md`。

## 本轮核对与同步范围

- 1529份去重候选覆盖239图；91份命中几何/配对/表示异常或既有错标。单人簇726、二人小簇255、角点数量698、顺序线索806、3D诊断47、配对41、墙带失败89、IoU辅助37、既有错标2；通道可重叠，不可相加作分母。分簇证据覆盖2444份，另外575份未据旧分簇判断。
- 56项相关pytest通过；离线Chromium验证原图、筛选、图层、裁决保存/重载/导出/导入通过，截图排版核验完成且临时截图已删除。当前及旧v23合同边界保留；未运行整个仓库测试，因为本轮不改采集运营和其他历史算法。
- Git同步当前合同/SOP、当前研究输入与数值、审核页、直接依赖及既有审核证据。Project93较新09:42快照原样纳入版本管理，旧04:34快照的本地删除不提交。原图259张原本已在Git中。历史结果不改写；其他采集、仪表盘和探索工作区改动保留，不批量删除。Pro压缩包不纳入本次同步。
- 历史分簇仅同步本页用到的成员表与点集及说明；这不声称重发全部旧研究运行产物。完整历史分簇重跑还依赖既有Pro返回和运行材料。
- 地图与README已登记当前入口。归档原文保留原字节，因此两份历史文档的空尾行检查提示保留；当前改动无新增实质空白错误。
