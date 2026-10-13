# 联合公式校准模块

主方案和具体参数以 [recommended_parameters.json](recommended_parameters.json) 为准；中文结论见 [CALIBRATION_REPORT_ZH.md](CALIBRATION_REPORT_ZH.md)。本模块只计算已选定合法参考下的分数，空间路由在上级模块完成。

## 运行

在交付根目录执行以下命令。Python 依赖为 numpy、scipy、shapely、matplotlib、Pillow；实际版本记录在 inputs/environment.json。

```bash
python calibration/run_search.py
python calibration/analyze_candidates.py
python calibration/verify_calibration.py
python calibration/render_calibration.py
```

上述命令使用已经冻结的 inputs/search_inputs.json 和上级 experiments/results 中已验证的控制指标。每一条指标都有来源、资格与点坐标身份，没有隐含网络下载。

重新构造 96 个几何控制，并在空目录运行完整模块：

```bash
python calibration/reproduce_calibration.py --source baseline --out replay_calibration
```

如果上级几何模块也重放到了新目录，添加 --experiment-results 指向新生成的 experiments/results，避免只复用原控制指标。重放脚本拒绝写入非空输出目录或冻结来源，逐步骤记录真实退出码，重算 21,744 个配置、96 个几何控制、922×3 个候选分数、27 种响应政策与留组敏感性，核对逐条分数、身份和搜索计数，并实际解码两张新绘图。

本轮已经实际完成一次空目录冷重放：六个步骤均退出 0，总耗时 38.30 秒；922×3 分数相对交付结果的最大差为 0，搜索计数完全一致，受保护来源文件未改变。记录见 results/COLD_REPLAY_VERIFICATION.json，逐步原始输出见 results/cold_replay_logs/。这是数值复现验证，不是新增人评。

## 数值入口

```python
from calibration.score import load_config, score_metrics

cfg = load_config("calibration/recommended_parameters.json")
result = score_metrics(
    {"I": 0.92, "Sb": 0.79, "D": 2.17, "Hm": 0.234, "Hc": 0.011},
    cfg,
    reference_height_available=True,
)
floor_only = score_metrics(
    {"I": 0.92, "Sb": 0.79, "D": 2.17},
    cfg,
    reference_height_available=False,
)
```

reference_height_available=False 时完整 score 为 null，floor_score 保留。不要把 floor_score 与完整 Q 当作相同量表直接合表。局部联合 hinge 备选需要 descriptor.joint_hinge["t10_g2"]，其数值由 experiments/structural_features.py 中 jointly_optimized_hinge 对同一作答底面计算；不能用固定 L2 轴的尾量替代。

I/Sb/D 非法、缺失或非有限时返回 unavailable；高度不可用单列原因。仅浮点舍入导致的 I>1 在 64ε 容差内被夹到 1 并记录；大的越界不会被静默修补。score_metrics 不选择参考、不发放人员资格、不输出人类质量等级、不认证原始上下点的语义配对。

## 文件

|文件|内容|
|---|---|
|inputs/search_inputs.json|922 条固定参考指标、当前点/参考点 SHA、143 条资格桥接、全部开发人工层|
|inputs/INPUT_CONTRACT.json|精确来源文件 SHA、指标单位与版本说明|
|inputs/evidence/|逐字保留的人工澄清，额外来源清单随目录保存|
|results/all_search_configs.json.gz|每一个联合配置，可直接独立解压读取 JSON|
|results/all_search_results.csv.gz|每一个配置的方向约束、弱序数、响应与分差结果|
|results/response_policy_sensitivity.json|27 种人为响应政策；含不使用旧24门槛的有效区|
|results/selected_scores_922.json|推荐、两备选、旧基线与公平 3D IoU 的逐条分数、身份、原资格与分项|
|results/selected_components_long.csv|逐作答×算法的损失分解|
|results/ablation_summary.json|去结构/边界/区域/高度项、去尾部与组合方式消融|
|results/physical_controls.json|96 个实际可运行几何，解析匹配沿边界三维位移预算|
|results/all_controls_rescored.json|本模块与上级定向实验的逐例候选重评分|
|results/leave_group_sensitivity.json|12 建筑+23 图片的删组敏感性，非独立验证|
|results/grade_cut_identification.json|所有最优开发切点区间；没有生产等级阈值|
|results/SCALAR_VERIFICATION.json|独立标量计算与缺失、非法配置、溢出、单调性等合同检查|
|results/COLD_REPLAY_VERIFICATION.json|空目录完整重放的实际退出码、分数/搜索计数比较和两张 PNG 解码|
|SOURCE_DEPENDENCIES.json|14 个 baseline 文件及 5 个交付根依赖的精确清单和 SHA|
|figures/|实际数值绘图，不是生成式示意图|

## 来源依赖

prepare_inputs.py 需要 baseline 中 inputs/calibration_records.json、inputs/old24_labels_preserved.json、evidence_audit/results/constraints.json，以及上级 sources/main 的 record_results.json/U05_CHAT_FEEDBACK.json 和 experiments/results 两份方向描述。输入合同列出全部精确 SHA。

physical_controls.py 调用冻结几何引擎，使用 config/frozen_selected_candidates.json 的原几何参数；实际导入的来源模块和 SHA 见 results/physical_control_dependencies.json。它没有把新 Q 送入几何构造或参考路由。

SOURCE_DEPENDENCIES.json 中的 14 个 baseline 文件已逐项检查，均存在于根交付的紧凑 baseline；原始人工逐字澄清另保存于 inputs/evidence，附来源校验清单。

不要把旧 24/22 开发证据、922 条分数、143 条人员条件记录、60 个融合版本混成同一种“样本量”；融合比较由上级 integration 负责。W019 不在本模块 922 条中，没有为无配对的原点自动造几何。
