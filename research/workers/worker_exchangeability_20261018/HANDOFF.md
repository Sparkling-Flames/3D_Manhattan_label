# 扩大人数与单人交换交付

2026-10-18。本代理负责设计与统计；融合和本图原答结构诊断由另两个代理完成，实际来源在INPUTS.json和各自文档中保留。

## 已改内容

- 新增`tools/thesis_main/analysis/worker_exchangeability_20261018.py`和`tests/test_worker_exchangeability_20261018.py`；本目录交付绝对／相对Q、效率类别、3840请求设计、2560替换结果与配对汇总。
- 先冻结8图×6/8/12/16人数、同ABC和嵌套背景，随后才消费融合结果。先按同块共同可用两臂比较，后图等权；人数曲线进一步固定4个k共同可用背景链。
- 主质量仅绝对Q和相对Q，T另作效率，Semi/scope不进入。绝对Q从真实1048训练楼外重算原尺度均值，不伪装成任务标准化质量。
- 支持高Q快2–4人时的大背景替换席位，不制造纯大队。明确类内／类间、严格相同／节点内容／仅节点数／连续变化的区别。
- 接入当前图原答连续距离与两种不同语义簇；追加背景0发现、背景1复核及跨图同人员对支持。不把高度重叠的背景称独立样本。
- 修正上一轮README“8图都不足4名高快”的文字：实际2–4，恰好4人只有一个四人集合，不满足至少2替换集合规则；旧设计／结果未改。

## 验证与边界

- TDD首次缺模块失败；实现后定向验证5项通过，与之前人员分类测试合计15项通过。
- 首次导出因未知T效应产生NaN而明确失败，随后未知变化写null，未补成0；最终请求为严格JSON。
- 3840请求、2560对完整返回；1280背景迁移配对均校验相同image/k/人员对/三元组，保持背景0→1方向。
- 新README的相对链接已检查。原始标注、GT、评分、资格及历史包未改；没有截图遗留；未执行全库无关测试。
- 公共docs/catalog/UI由统筹主代理维护，本代理未并发改它们。已检查地图／索引规则，新增正式研究入口需由统筹统一登记。

## 给统筹和展示的稳定接口

`summary.json`、`exchange_analysis.csv`、`matched_block_analysis.csv`、`by_image_k_class.csv`、`summary_by_k.csv`、`fixed_chain_curve_summary.csv`、`high_fast_summary.csv`、`background_transfer_summary.csv`及`review_cases.json`已经可直接消费。

固定所有k共同链：V为AbsQ3 76／8图、RelQ3 77／8图、RelQT4 104／8图；Q为62／7图、61／6图、83／6图。实际原答字段名为`annotation_floor_jaccard_distance`；两个本图簇字段为`annotation_same_range_cluster_020`和`annotation_same_structure_cluster_9deg`。

剩余限制是8图、每类2套人员三元组和2背景；归纳的可互换关系未获独立新图确认。16人时间完整为0，不能给成本最优结论。当前可交付阶段研究，无需等待v2。
