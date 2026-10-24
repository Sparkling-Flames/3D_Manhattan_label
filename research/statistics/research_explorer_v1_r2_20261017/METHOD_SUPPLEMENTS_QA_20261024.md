# 2026-10-24 已验收方法补充：离线研究台接入回执

入口：[D10 人员形成](index.html#release=v2&module=method_supplements&tab=0)、[同队三法融合](index.html#release=v2&module=method_supplements&tab=1)、[25题人工质量判断](index.html#release=v2&module=method_supplements&tab=2)。人员六步、融合过程、个体质量原阅读路径均有直达链接。页面只读已保存结果，不在浏览时重新分型、评分或融合。

## 来源与身份

- 构建器写入本地忽略资源 `v2-resources/method_supplements.json`，schema `method_supplements_display_20261024_v1`。人员 8 张表、融合 7 张表加 414 条几何、质量 25 对人工题及 3 组控制表均保留源字段与缺失值。
- 构建时核对融合 138 队各自原答对象集合和绑定参考，以及 25 对人工题左右原答和绑定参考。历史 Q 为中心化值；选队表的六人名单只是所选块，其余背景固定。ALL 分区仅用于描述名单，楼外选队依目标建筑各自计算。
- 融合页面共同完整布局可评 130 队、共同底面可评 131 队、全部尝试 138 队。Lee 完整布局与完整 Q 显示“不适用”，底面真实计数照录。人工题区分 20 题新批候选与 5 题已曝光机制题，后者不并作独立新题。

## 实际验证

- `python -m tools.thesis_main.analysis.build_research_workbench_v2_20261019`：完成，输出 10,439 库存作答、261 图、7,302 正式质量、172 表。
- `python -m pytest tests/test_research_workbench_v2_20261019.py tests/test_workbench_method_evidence_20261020.py tests/test_method_validation_20261024.py -q`：24 项通过。
- `node --test tests/method_supplements.test.cjs`：Polygon 洞环、MultiPolygon 多分量与空输入测试通过。`node --check` 检查新脚本及改动的现有脚本通过；`git -c core.whitespace=cr-at-eol,-blank-at-eol diff --check` 通过。
- Edge 无服务器 `file://` 实测：Manual↔Semi 自动切到各自普通层并保留实际团队；Semi 常数面板明确显示 η² 不适用；Lee MultiPolygon 两条底面环均可见，墙线无连接队不画虚假闭合几何；QV015 左右两张原图和完整原答可见，原始选择译为“各有问题或无法判断”；工具提示可键盘聚焦。390px 视口整页宽度为 390px，无横向溢出；无页面脚本异常。

本地截图（原始人工文字仅留本机，目录被 Git 忽略）：`v2-resources/qa/method_personnel_eta2.png`、`v2-resources/qa/method_fusion_multi.png`、`v2-resources/qa/method_quality_qv015.png`。浏览器已关闭，没有常驻服务或临时调试文件。

本轮新展示代码和测试在已有研究台与 `tests/` 下；项目地图和 README 索引已有研究台入口，未改动统筹线程正在修订的共享文档。源 CSV/JSON、协议、资格、参考、融合及研究采用状态均未改；没有做全量团队原生重放。首次拉取或源结果更新后需运行上述构建命令生成被忽略的本地资源。未提交或推送。
