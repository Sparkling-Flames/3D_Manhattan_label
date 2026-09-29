# 2026-09-29 全量复核后数值研究包

入口：[当前研究方向](../../docs/thesis_main/研究方向_空间差异与共识_20260930.md)、[简要说明](RESEARCH_ALIGNMENT_20260930.md)。当前先核验连线、空间表示及其对IoU的影响；提示词由对话提供，不再随包保存。旧八图包和旧Release只用于历史对照。

已执行结果：[首轮报告](baseline/REPORT.md)、[固定图片面板曲线](baseline/fixed_panel_replay.png)。

本目录可独立运行。包含 3152 份历史人员记录、259 张人员研究图片、259 份原始 GT 和 30 份人工修订 GT；其中 2 份修订 GT 属于人员样本之外的图片，因此目录含 261 个图片条目。人员重新编号，跨图一致；不包含真实编号映射、原图、原始任务 ID 或自由文本评语。

接入统一从本地 `analysis_results/research_input_20260929/manifest.json` 及其校验读取函数进入，包含坐标、研究表、评论和最终统计。公开面板使用白名单投影，已有原始数据与裁决不改写。2026-09-30 补入结构化范围/细节、GT既有标记、模型及改序上下文；原始评论和内部身份只在本地读取。明显GT错误沿用用户已有处理，研究重心是标注空间范围、细节表达和定位偏差如何影响分簇、共识和人员质量。GT细节省略的自动发现是次次要探索。

## 取得与执行

先将**本目录的实际文件**放入你的执行环境，再进入此目录运行：

```sh
python -m pip install -r requirements.txt
python -B verify_bundle.py
python -B -m pytest -q -p no:cacheprovider tests
python -B -m tools.thesis_main.analysis.research_round_20260929 --input inputs/panel.json --out your_results --seeds 100 --width 512
python -B -m tools.thesis_main.analysis.summarize_research_round_20260929 --input inputs/panel.json --results your_results
```

已安装依赖时无需重复安装。SimpleITK 是 STAPLE 的可选依赖；本地本轮未安装，结果明确记为 unavailable。Pro 可自行安装并开展新增实验，但不能将自定义单正确率 EM 称作 STAPLE 或 Lee 原论文的完整复现。

GitHub 阅读接口能显示文本不代表 Python 能加载文件。如果执行环境 DNS/网络不可用，先说明具体失败并请求用户上传**当前目录**的压缩包；不要要求用户替你搭 Python 环境，不要凭仓库历史结果声称本轮实验已运行。仓库主体交付始终是展开目录，压缩包仅用于绕过运行环境的传输限制。

## 文件与字段

- `inputs/panel.json`：完整数值面板。图片键 `code/building/room/population/scene`；`room` 空值为缺失，不是独立新房间。
- `annotations`：`id/worker/condition/points`，清洗、顺序、几何状态，以及上游质量/共识 gate、独立投票资格。`points` 为 1024×512 连续坐标，按显式环序交替排列 top、bottom；不可配对时为 null。`source_point_indices/labels` 保留本条标注内点身份，不提供跨人员语义对应。
- `references`：`version=original/manual_revision`。两个版本并列评价，不选更接近结果的一版充当真值。人工修订缺失不补造；原始 GT 不是绝对正确性证明。
- 图片及人员记录的 `review`：既有结构化证据，包含不同层级的范围/细节标记、GT处理标记、模型和改序状态。图片外参考的review为null。所有false标记只表示未记录该项，不能解释为核验不存在。尤其20图GT细节省略是部分复核留下的案例，不能将其余239图当负例。顶层 `review_context` 保存覆盖与研究优先级说明。
- `quality_candidate` 仅表示上游 candidate_pending_geometry，不代表已经适合某一指标。`consensus_eligible` 包括 main_candidate、oos_doorway_exploratory、stable_nonorthogonal_separate 三层；报告必须拆层，不能把它们全部当成正式主分析样本。
- `independent=false` 的历史、排除、待定和借用点记录仍保留，但不进入本轮独立投票；两份借用点记录不能重复给其供体增票。人员和条件分开，不能把不同条件的同一人当作同组的两票。
- `scene.not_recorded`、未穷尽收集的空间/细节信息不能解释为“普通、无差异、简单”。此公共版本不发布自由文本评语及其人工解释。
- `baseline/`：此前实际执行的数值结果。该次只消费坐标/资格，未消费完整评论解释；复读后核对数值输入未变，不重复运行。研究解释以9/30方向修正为准，不用这批数值声称已分离范围、细节与定位误差。
- `tools/`、`lib/`、`tests/`：运行依赖的最小源码副本；`MANIFEST.json` 给出文件大小，`VALIDATION.json` 记录本地验证边界。投影脚本的CLI是本地生产入口，依赖未公开的完整manifest；Pro直接读取inputs/panel.json即可，不需要重建私人源数据。

## 本轮实现与限制

显式邻接方法从上下点构造地面轮廓，以最近正向射线与墙交点渲染可见墙带，墙顶按相邻角点高度线性插值；不强制全局水平天花板。BEV 保留遮挡后的整个轮廓；可见 mask 本身不能观察被遮挡的范围差异。

旧方法按 x 排序，用既有全景曲线构成包络。它采用历史 +0.5 像素中心约定，新方法采用复核 viewer 的连续 x/W 约定。两者同时改变了表示和坐标约定，本轮差值不能全部归因于环序；严格归因需 Pro 做控制变量实验。

不删除 180° 节点，不优化坐标，不修复自交。相机不在多边形内、错误半球等表示失败单独报告，不直接解释为标注者错误。三维棱柱 IoU 使用各自中位墙高，明确叫 `prism_surrogate_iou`，不是任意真实房间的精确体积 IoU。边界距离采用每侧 512 个弧长采样，是近似量；接近地平线的深度误差需要额外敏感性研究。

当前共识是**区域 mask 聚合基线**，不是点级共识或最终可折叠房间。重放为 100 个固定随机排列，k 是抽到的独立人员数，used_k 是可渲染数；两者均报告。尾部所有人员相同时，确定性算法结果相同是数学事实，不能据此宣布达到真实共识。p05/p95 是排列分布区间，不是总体置信区间。不同 k 直接跨图平均会改变图片构成，报告须用固定图片面板。

本包与结果均为探索性交接，不改变正式协议、人员等级、GT、排除、OOS 裁决或合同资格。
