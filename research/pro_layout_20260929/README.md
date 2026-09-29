# 2026-09-29 全量复核后数值研究包

入口：[完整 Pro 提示词](PROMPT.md)。这是新的全量快照；旧八图包和旧 Release 只用于历史对照。

已执行结果：[首轮报告](baseline/REPORT.md)、[固定图片面板曲线](baseline/fixed_panel_replay.png)。

本目录可独立运行。包含 3152 份历史人员记录、259 张人员研究图片、259 份原始 GT 和 30 份人工修订 GT；其中 2 份修订 GT 属于人员样本之外的图片，因此目录含 261 个图片条目。人员重新编号，跨图一致；不包含真实编号映射、原图、原始任务 ID 或自由文本评语。

接入依据是 2026-09-29 完成的复核汇总和数据接入。原始导出、人工裁决、点对平均 x 和明确环序已在上游整理；本包只是字段白名单投影，不新增排除，也不宣称所有默认环序都经过人工确认。照片不可用，因此几何一致性不能替代视觉真实性判断。

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
- `quality_candidate` 仅表示上游 candidate_pending_geometry，不代表已经适合某一指标。`consensus_eligible` 包括 main_candidate、oos_doorway_exploratory、stable_nonorthogonal_separate 三层；报告必须拆层，不能把它们全部当成正式主分析样本。
- `independent=false` 的历史、排除、待定和借用点记录仍保留，但不进入本轮独立投票；两份借用点记录不能重复给其供体增票。人员和条件分开，不能把不同条件的同一人当作同组的两票。
- `scene.not_recorded`、未穷尽收集的空间/细节信息不能解释为“普通、无差异、简单”。此公共版本不发布自由文本评语及其人工解释。
- `baseline/`：本地实际执行的数值结果与报告，供核对，不是 Pro 本轮新增实验日志。
- `tools/`、`lib/`、`tests/`：运行依赖的最小源码副本；`MANIFEST.json` 给出文件大小，`VALIDATION.json` 记录本地验证边界。

## 本轮实现与限制

显式邻接方法从上下点构造地面轮廓，以最近正向射线与墙交点渲染可见墙带，墙顶按相邻角点高度线性插值；不强制全局水平天花板。BEV 保留遮挡后的整个轮廓；可见 mask 本身不能观察被遮挡的范围差异。

旧方法按 x 排序，用既有全景曲线构成包络。它采用历史 +0.5 像素中心约定，新方法采用复核 viewer 的连续 x/W 约定。两者同时改变了表示和坐标约定，本轮差值不能全部归因于环序；严格归因需 Pro 做控制变量实验。

不删除 180° 节点，不优化坐标，不修复自交。相机不在多边形内、错误半球等表示失败单独报告，不直接解释为标注者错误。三维棱柱 IoU 使用各自中位墙高，明确叫 `prism_surrogate_iou`，不是任意真实房间的精确体积 IoU。边界距离采用每侧 512 个弧长采样，是近似量；接近地平线的深度误差需要额外敏感性研究。

当前共识是**区域 mask 聚合基线**，不是点级共识或最终可折叠房间。重放为 100 个固定随机排列，k 是抽到的独立人员数，used_k 是可渲染数；两者均报告。尾部所有人员相同时，确定性算法结果相同是数学事实，不能据此宣布达到真实共识。p05/p95 是排列分布区间，不是总体置信区间。不同 k 直接跨图平均会改变图片构成，报告须用固定图片面板。

本包与结果均为探索性交接，不改变正式协议、人员等级、GT、排除、OOS 裁决或合同资格。
