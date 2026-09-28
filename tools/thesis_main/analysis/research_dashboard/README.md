# 离线研究仪表盘

1. 完整解压 ZIP，双击 `index.html`。无需联网、安装 Python 或启动服务。
2. 左侧切换六个模块；顶部筛选只显示当前结果支持的组合。变更上游筛选会更新下游范围，完整条件会显示在筛选下方。
3. 图表可悬停、切换图例、拖拽或滚轮缩放，双击恢复；展开“底层表格”核对数值、单位、分母、成员与来源。
4. 点击图片进入详情。仅精选案例携带图像、点集和 3D；其他图片保留统计。“重置详情”恢复案例视图，“重置筛选”恢复发布初始范围，Esc 关闭详情。
5. 版本或方法对照需要勾选并主动选中另一结果切片。两组独立展示，不混算。缺失不等于零；未计算、人数不足、未达标、未决分别标记。

`structure-20260921` 是历史空结构；`research-20260922` 接入终审真人数据、分簇、人员敏感性、有限池重放、同房预测及模型／GT／特征覆盖。以页面发布标识为准。Semi只作独立描述；新候选持续起点未计算，本次未接入当前版本的特征关系分析，缺失不画成零。DA3同房辅助316对是全资产库数量，不随当前图片筛选缩减。

真实包默认打开全部条件描述覆盖。分簇与重放位于“Manual/OOS · 无辅助计算”条件；空模块上的“查看…”按钮可明确切换。图片详情首先呈现完整全景；“全部簇成员与完整点集”列出全部参与者，可逐个选择或叠加两人。

## 换数（制作端）

分析线程按包内 `数据接口.md` 提供结果 JSON，另准备精选图片与展示清单。页面不训练分类、重算分簇、拟合几何或选择阈值。只读取清单明确指定的输入。

在仓库根目录运行；以下输出目录必须尚不存在：

```powershell
python -m tools.thesis_main.analysis.research_dashboard.build --manifest tools/thesis_main/analysis/research_dashboard/empty_manifest.json --out analysis_results/research_dashboard_structure_20260921
```

真实接入时把 `--manifest` 换成新展示清单路径，`--out` 换成新的版本目录。制作端使用本机已有 Python、Plotly、Pillow；阅读者不需要这些环境。

2026-09-22已核实结果接入入口（不重算研究）：

```powershell
python -m tools.thesis_main.analysis.research_dashboard.connect_20260922 --coverage analysis_results/presentation_inventory_20260922/asset_coverage.json --out analysis_results/research_dashboard_20260922
```

`INPUT_AUDIT.json`记录范围与完整点集一致性；`PRESENTATION_CHECKS.json`列出各条件／方法全局切片的指标、图表和表格清单。高维模型特征仅发布覆盖信息，不携带原张量。

同一入口也读取`history.py`列明的历史分类／组成／同场景／模型特征研究结果，分为独立历史版本。历史特征预测使用已修正外层隔离的数值，不携带模型张量，也不重算模型。模块上方可明确切换历史版本；大表支持搜索及每页100行。最新历史增补只作Python、Node函数桩及静态打包校验，受既有浏览器访问限制未作新视觉验收。

发送新生成的整个 ZIP；收件方解压为新目录，避免混用旧资源。不需要改页面源码。输入结构、精选资源和发布版本不一致时，打包器拒绝发布。

开发端完整接口与验证说明：`docs/thesis_main/OFFLINE_RESEARCH_DASHBOARD.md`。
