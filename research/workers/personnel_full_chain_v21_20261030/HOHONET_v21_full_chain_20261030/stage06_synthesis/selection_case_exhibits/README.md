# Q / QT 选队四案例：直接人工查看补充

本目录仅补充已有案例的原图及完整几何查看，不运行新选队、评分、融合或机制实验；不修改已冻结的 stage05。

## 入口

- [四案例总入口](index.html)：独立离线 HTML，原图、冻结案例 JSON、当前完整目标原答池均内嵌。
- [uNb-01 降质尾部](case_uNb9QFRL6hY-01.html)：重点检查 x≈905 的底部角点和相邻墙段。
- [uNb-43 降质尾部](case_uNb9QFRL6hY-43.html)：重点检查 x≈73–84 的短墙段附近；保存的方向损失变大，不以此代替人工判断。
- [uNb-12 升质但劳动增加](case_uNb9QFRL6hY-12.html)。
- [S9h-10 成员改变、融合几乎不变](case_S9hNv5qa7GM-10.html)。

浏览器打开即可；不依赖服务器或外部资源。点击“重点墙段”放大已有几何差异；两个团队与原答视口同步，可选择全部当前合法图池中的单人原答。原图 2048×1024，所有标注坐标为 1024×512；三维直墙段经 ERP 投影显示，接缝分段。底面使用冻结 footprint，保留点顺序。

## 证据及边界

`source_cases/` 为 4 份已选案例的逐字节副本；其中保留全部团队成员目标原答及历史来源原答、参考、完整两端点。`full_target_pools/` 增补从当前固定 INPUT 精确提取的 4 个合法目标池，共 138 份完整目标原答；只是供查看的上下文，不加入团队。`EXHIBIT_INDEX.csv` 可回连团队键、原图、案例 SHA 与数值；`Q_QT_FROZEN_METRICS.csv` 为已有端点分项的摘录，没有重评分。

本页仅对 `complete_conditional` 融合端点闭合显示；这 8 个端点均符合该条件。`ring_confirmed=false` 与顺序待人工确认状态原样保留。参考和原答保持其声明的完整记录顺序，不追加排序或人工确认。未取得专用完整候选轨迹，不能以总分或入选票数推断未入选节点、身份合并或连接机制。

原图来源为冻结发布 `quality-original-images-20261015`。1 张复用已验证本地原图，3 张只下载其 ZIP member 所需 byte ranges；CRC32、SHA256、归档 URL、成员路径及传输范围见 `originals/ORIGINALS_RECEIPT.json`。当前冻结提交为 `13a7861334749805a86dc19e9ea79fcaa71020c0`。

## 验证与复现

- `BUILD_VALIDATION.json`：成员、原答、参考、劳动合计、几何点数及 HTML 内嵌数据读回。
- `BROWSER_VALIDATION.json`：真实 Chromium 浏览器的离线打开、4 案切换、放大及原答选择检查。
- `browser_checks/`：验收截图。
- 脚本：研究根 `scripts/build_selection_case_exhibits.py`；运行 `python scripts/build_selection_case_exhibits.py` 只用已保存原图重新构建。仅当原图缺失时 `--fetch-images` 才会做冻结发布的有界获取。

这些是完整策略结果之后的解释案例，不是总体效果的分母或重新选型依据。总体均值、多数图与坏尾仍以冻结 `stage05_selection_stop/README.md`、报告及逐图表为准。
