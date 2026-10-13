# 多空间路由接口

本模块只负责已经人工准入的参考选择和对每个参考的几何量计算。未批准的人员小空间不自动变成候选。任何路由结果都不构成质量合格或正式人员资格。

## 可直接消费的文件

- `inputs/prepared_input.json`：35图候选、429份当前作答及原始上下角点/均x后坐标、当前资格、5条明确人工路由、2条仅结构族指令、原回执和版本绑定。
- `results/reference_candidates.json`：逐图参考清单；`candidate_id` 仅是稳定显示标识，必须和 `reference_version`、`points_sha256_canonical_v1`、`floor_sha256_canonical_v1` 一同使用。
- `results/routes.json` 的 `rows`：逐作答主协议。`selected_candidate_id` 是最终路由，`automatic_without_manual` 保存无人工override的算法输出，`effective_local_routing` 保存实际采用的局部证据及兜底原因。
- `results/all_candidate_metrics.json` 的 `rows`：每个可算作答×每个参考（含明确标记的受限原GT诊断）。主键 `record_id,candidate_id`，不要仅按 `image_code` 或点数连接。
- `results/image_manifest.json`、同名CSV：35图计数与完整性缺口。
- `results/raw_x_diagnostics.json`：在原始上下x上计算的 `X_rms_deg` 和 `Eperp_deg=X_rms_deg/2`。它们没有改变或额外处罚几何分。

## 指标字段

|字段|含义/单位|
|---|---|
|`I`|底面交集面积/并集面积，0至1|
|`Sb_deg`|底边球面曲线对称平均距离，度；2048等弧长采样/方向，目标弧距离解析计算|
|`D_deg`|长度加权、相对优化共同正交轴的RMS方向残差，度|
|`Hm`|周长加权平均墙高相对误差，无量纲|
|`Hc`|移除两者各自均高差后，双向最近底边位置的高度残差RMS/参考均高，无量纲；4096/方向|
|`IoU3D_corner_mean`|冻结HoHoNet口径的角点均高棱柱IoU，0至1；不是非平顶体积积分|
|`IoU3D_perimeter_mean`|周长均高棱柱诊断口径，0至1|
|`Q_floor_baseline`|仅底面子评分 `100I/[1+Sb²/32+1.5D²/(D²+37.5)]`，不能称完整Q|
|`Q_full_baseline`|题设基线完整Q，仅原有完整参考且严格可算时可用|

新确认只含底面的候选：`top_status=top_pending`、`Hm/Hc/IoU3D_corner_mean/Q_full_baseline=null`。不得把这些null当0。35份底面确认不认证任何顶面；仅几何与既有完整GT完全相同的候选保留既有顶面身份，不进行拼接。

`previous_fixed_candidate_id` 表示原本选择的固定参考（wc2-26为已有人工修订B）；`historical_original_candidate_id` 表示原始数据集GT（A）。四路比较须明确选择哪个作为“旧参考”。推荐用实际旧固定参考做主对照，并补充历史原始A，避免把已经采用人工修订B误写成此次新增改善。

`current_formal_gate`、`original_conditional_personnel_eligible`、`original_use_barriers` 原样保留。`full_primary_use_permitted` 只是几何与当前gate允许的必要条件，未把未知OOS/门洞状态或研究暴露升级为完整资格认证。798个候选几何行是影响分析，不是798个人工标签。

## 复现

在结果包根目录运行（`baseline`采用随包冻结质量引擎目录结构）：

```bash
python routing/run_routing.py --baseline baseline --out routing_replay/results
python routing/verify_routing.py --baseline baseline --results routing_replay/results --out routing_replay/validation
python routing/numerical_spot_check.py --baseline baseline --results routing_replay/results --out routing_replay/validation/numerical_spot_check.json
```

`run_routing.py` 默认读取随包 `routing/inputs/prepared_input.json`，不要求原36MB loader。原提取命令另为 `python routing/prepare_inputs.py --source <quality_parameter_calibration_20261012解压目录>`，提取依赖以及原文件SHA在 `inputs/source_extraction_manifest.json`。

方法入口 `router.prepare_reference_set(candidates,config)` 只接收已批准底面；`router.route_floor(annotation_floor,prepared)` 不接受图ID、作答ID、人员、D、最终Q或任何高度。人工指令在外层单独应用。

## 使用边界

这次恢复并使用了35图和429份几何，均应登记为已暴露的开发/影响分析资料；不能以后声称它们在这次路由开发中未被查看。既有6例空间盲审及T30/W031/W034属于开发证据。新的不变性与删点反例是生成控制实验，不是独立人工泛化标签。

## 冻结交付校验

在包根目录执行 `python routing/check_delivery.py`，核验模块文件及其原始来源、冻结引擎依赖的 SHA-256，并检查 417 条有效路由与 798 条候选指标使用同一坐标及参考版本。`delivery_manifest.json` 不包含其自身；它是 Task A 模块清单，不替代根目录压缩包清单。

已实际使用包内相对路径 `baseline` 重跑全部 429 条输入，除运行时长和命令路径记录外，全部 15 份科学结果文件逐字节一致。详见 `validation/packaged_baseline_replay.json`。
