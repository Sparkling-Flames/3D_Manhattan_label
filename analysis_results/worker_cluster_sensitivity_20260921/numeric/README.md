# 人员移除数值敏感性

本目录是探索性分析，不改变任何人的资格、原始标注或正式 T1/V1 协议。使用已独立复算的 20260921 冻结资料包，共 240 图、2444 份标注、25 人；方法与距离保持原设置（complete / representative，25.6 px）。

`plan.json` 在读取并分析数据前写入。全体人员均计算单独移除端点；较昂贵的重放预先按原 N≥8 图上的 complete 单人簇率选前三名、至少出现 20 图，结果为 W037、W034、W032。这不是质量资格判定。

- `worker_ranking.csv`：全部图和原 N≥8 图上的单人簇率、同图单人簇率差值。后者是简单描述性同图中心化，不是校正所有混杂的模型。
- `endpoint_per_image.csv` / `endpoint_summary.csv`：在目标人员实际出现的同一组图上，分别比较原池、移除目标、等概率移除另一名人员的精确平均。每次均重新分簇。K 和单人簇占比用原 N≥8 图；U8 用原 N≥10 图，确保删人后仍可定义。
- `replay_per_image.csv` / `replay_summary.json`：固定原 N≥8 的 110 图，200 个相同全局人员顺序投影到各图及删人后的池，epsilon=.1，tail=3，稳定概率门 .8，仅复算 uncapped 和 cap3_s20。不含目标的图原样保留。每个目标的对照在其出现的每图用固定种子随机删除另一人；这是一个随机删人实现，而不是随机删人效应的精确期望。
- `joint_endpoint_per_image.csv` / `joint_endpoint_summary.csv`：追加同时移除上述三人的敏感性。每图按实际删人数，从原人员池中均匀抽至多 200 个不同删除子集作等数量对照；全部可能子集≤200时精确枚举。对照可包含目标人员，与逐人比较的“另一人”对照口径不同。U8 在联合移除后仍有定义的共同图上汇总。
- `joint_scope.csv`：逐图样本量和 U8 / tail 可定义性损失，防止把删人后失去评估资格视为稳定。
- `baseline_verification.json`：4888 条原端点成员单人簇标记和 440 条原重放设置逐项一致性检查。

各图等权汇总。U8 是固定有限池中随机取 8 人后，第 9 人无阈值内已见近邻的精确概率，不是真实总体新模式概率。重放末端也随删人缩短，因此不能将重放起点解释成前瞻性“第几个人后永远稳定”。200 个顺序不是 200 份独立研究样本；本报告没有据此构造显著性检验或人员优劣结论。

运行：`python tools/thesis_main/analysis/worker_cluster_sensitivity_20260921.py`。联合端点：`python -c "from tools.thesis_main.analysis.worker_cluster_sensitivity_20260921 import joint; joint()"`。测试：`python -m pytest tests/test_worker_cluster_sensitivity_20260921.py -q`。
