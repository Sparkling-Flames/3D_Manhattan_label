# 全历史标注研究统计前置 v2

## 结论边界

本包是审计/敏感性统计，不产生正式 worker taxonomy，不改变任何 eligibility、C2、T1/V1 或 Stage 3 gate。候选 H/L/U 仅表示指定连续特征在给定 stage×condition×reference-source 分层中的方向证据；它不是人格或能力类型。三轴只作解释，不拟合场景预测。

## 数据与分层

- 输入为 v1 已实算的 2,501 条 canonical 全历史底座；没有复用 CURRENT20 或旧 eligibility 作为新主分母。
- 共物化 12023 条特征长表记录，按 stage、condition、reference source/version、feature 分开。单图 reference identity/reference SHA 逐行保留，但不把每张图的 identity 错当成跨图建模分层。
- 先审计 worker--task 二部图，共 108 个 component；只有单 building 的 component 明示不能估计跨 building 稳定性。
- Luna 证据合同状态：`validated`。若仍为 pending，本次计算明确使用 v1 substrate 临时映射，不把缺失证据视为零或可用。

## 任务调整与重采样

每个可估计 component 拟合 `value ~ worker fixed effect + task fixed effect`，worker effect 在 component 内中心化。质量包括已核验 D_mask（取负后“越高越好”）及其他 reference-relative quality；时间仅纳入正值、owner-valid、historical timing eligible 的 task-worker 累计日志，绝不混入 lead_time；Semi 修改/保留、参照角点 RMSE 与可对应的有符号横向偏移作为习惯特征单列。

每个可估计 component 固定执行 1,000 次 building→task 重采样，不拒绝也不重抽。状态计数为：`{"disconnected_graph": 3763, "missing_workers": 18409, "usable": 46828}`。缺工人、断图、任务支持不足均留在分母；同时报告可用 draw 的条件方向概率和全部 1000 次下的保守概率界，标签使用后者。近零并列按半权记录；只有一个 building 的人员不形成跨建筑稳定标签。

方向阈值报告 0.8，并并列 0.7/0.9 敏感性。quality×time 只并排描述共存轴，不合成新类型；连续波动用 std、MAD、IQR 报告。

## 留出评价与反例

任务使用确定性最多五折 held-out task；building 使用逐 building 留出。训练与评价 task overlap 全部为 0。`continuous_vs_classified_summary.csv` 同时报连续训练效应与 held-out 关联、离散 H/L/U 计数和反例数；`holdout_evaluation.csv` 保留逐 worker 反例。离散标签若掩盖连续方向反转，应优先报告连续结果与反例，而不是强化标签。

## 回放与结构敏感性

- strict-geometry support >20 的固定 image set 上，k=15..20 使用同一批 200 个 permutation 的嵌套前缀；medoid 只在 selected workers 内按平均 D_mask 选择，之后才对 remaining workers 评价，并逐 k 报 remaining count。
- H/L 组内和两组混合回放使用任务留出训练得到的标签，坚持一人一票；小规模 k=2/3/5/10 按实际支持描述，k15–20 单独核对资源缺口。不同方案须共同图集，不补虚拟工人。
- q=0.93/0.95/0.97 在所有 strict support≥15 新高支持 stage×condition 上保持同一 annotation support，分别给 task equal 与 building equal 汇总。
- 旧 42 回归：检查 42 图，mismatch=0。

## 护栏

统计 guard：PASS。primary estimand、缺失/失败与 reference 版本均分轨；replay 仅用于审计/设计，不替代 V1；原始 `export_label/`、`import_json/`、`active_logs/` 和协议均未修改。
