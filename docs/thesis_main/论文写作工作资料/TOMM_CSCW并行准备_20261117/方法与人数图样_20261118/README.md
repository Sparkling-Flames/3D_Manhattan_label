# 方法与人数图样

[六页校样](figure_proofs.pdf)按研究问题分为四张候选图和两张数据解释图。图面来自 Python 绘图、真实全景和论文已有的矢量曲线。英文子标题和图注由 [LaTeX](figure_proofs.tex) 排在图下。

| 图 | 内容和来源 |
|---|---|
| [1](01_quality.png) | 同一受控房间的下端点与上端点各改动一次。下端点按底面径向距离设定 0.50 m，上端点按墙高设定 0.50 m。分数由原稿的受控几何评分脚本计算。 |
| [2](02_consensus.png) | 浴室全景 jtcxE69GiFV-13，第二队的 8 人标出角 A。白框对应同一墙角的顶部与底部放大图，橙色菱形落在各自八份点击的中央，两端共用一个水平位置。人员、点击和共识结果来自原稿 figure_package/dot_fig07/data/consensus_case.json。 |
| [3](03_team_size.png) | 人数四曲线。保留固定 171 图和各难度层、两段阴影及实际曲线，横轴在四幅下方统一标明。 |
| [4](04_supplement.png) | 用补充 A 的 C4 受控数据做图注样式样张。原倾斜顶面以 4 和 16 对端点描绘，两个几何图与三条分数曲线单独导出，下置标题由 LaTeX 编排。 |
| [5](05_two_points.png) | 3 m 高房间的单顶角抬高 0.30 m。右侧另取中等难度图 X7HyMhZNoso-19，其持续阶段起点与 2 分下检出的中等图起点中位数相同。下排仅比较普通全景的三档难度。 |
| [6](06_doorway_counts.png) | 上排左为筛查前后相同的 17 图与共同整空间参考；右为另一具体门洞 7y3sRwLe3Va-18 的三个分目标人员池，各用对应参考。两个面板独立展示整体池与分目标池。 |

**逐图稳定阶段。** 从 3 人开始，找出满足以下条件的最早人数。此后到该图满员的各人数均值极差落在容差内，每个人数至少有 64 条可评分路径，后面至少还有 5 人或满池人数的 15%（向上取整，取较大值）。[每图每档容差的起点及状态](stability_by_image.csv)按原始均值曲线重算，并与已有逐图记录核对。[分组汇总](stability_summary.csv)的起点中位数仅对检出者计算。

**门洞单列表。** [17 图逐图数据](doorway_17_images.csv)给出筛查后 3、6、14 人时各图的平均 Q、完整输出率、可评分路径数和两档容差的起点。空起点表示该规则下未检出。[固定图片面板](doorway_fixed_panel.csv)与[案例的分目标曲线](doorway_target_pools.csv)使用各自的参考和人员池。原始门洞汇总取自 research/data/doorway_review_20261030/screen439_results_20261031；逐图容差数据取自 research/workers/image_response_v21_20261101 的 stage03_response。

仓库根目录运行 `python tools/thesis_main/analysis/draw_journal_evidence_proofs_20261118.py` 可生成图面和数据表。在本目录编译 `figure_proofs.tex` 可生成校样。
