# 平均 x 与原始输入：评价对象复核

2026-10-13；只核实研究定义和调用关系，不改变算法、坐标、资格或人工回执。

## 结论

用户记忆正确：**当前 Pro 主 Q 评价已平均 x、沿用既定上下配对和环序的处理后几何**。保留原始输入诊断并不意味着改用未经处理的点计算主 Q，也不意味着本轮要再拟合一个原始 x 罚项。

需要补充一个历史限定：旧 Pro 探索曾包含原始 X 分量候选敏感性，不能说“从未考虑过”。但最新主式没有采用 X/E 罚项，P05也没有给出固定等级、罚分或新的配对修复授权。

## 可定位证据

| 证据 | 位置与实际含义 |
|---|---|
| 几何输入 | [routing/prepare_inputs.py](../quality_pro_joint_archive_20261013/source/routing/prepare_inputs.py)，第150行：几何使用已提供的 ordered pair-mean-x points，不实施新修复。 |
| 主分真实依赖 | [calibration/score.py](../quality_pro_joint_archive_20261013/source/calibration/score.py)，第22–31、92–179行：主指标只有 I、Sb、D、Hm、Hc，以及部分候选的方向分布描述；无 X/E 参数。返回 `raw_input_quality_certified=False`。 |
| 最新研究解释 | [CALIBRATION_REPORT_ZH.md](../quality_pro_joint_archive_20261013/source/calibration/CALIBRATION_REPORT_ZH.md)，第41行；[RESEARCH_REPORT_ZH.md](../quality_pro_joint_archive_20261013/source/RESEARCH_REPORT_ZH.md)，第60–66行：原始 X 为上下端点周期经度差 RMS，X=2E；未以统一权重强行合入 Q。 |
| P05原始证据身份 | [constraints_original.json](../quality_pro_joint_archive_20261013/source/calibration/inputs/evidence/constraints_original.json)，第288–315行：R00678，`current_input_pair_semantics`，`specific_mechanism_observation_no_grade`；等级和数值margin均为空，没有独立视觉认证，没有自动修对。用户报告不同墙角的上下点被配成一对，平均后落在中间。 |
| P05是否参与主分排序拟合 | [run_search.py](../quality_pro_joint_archive_20261013/source/calibration/run_search.py)，第80–93行：收取处理后总体、底面、顶部高度约束；未把上述输入语义维度加入数值目标。保留在输入JSON不等于参与优化。 |
| 既有本地任务边界 | [PRO_TASK.md](../quality_parameter_audit_20261012/PRO_TASK.md)，第15行：允许研究原始/处理后两对象怎样服务人员画像，要求验证并避免重复处罚，不是已决定加权合分。 |
| 历史探索限定 | Downloads中的 `quality_top_structure_research_20261012_repaired_v1.zip`：`quality_top_structure_research_20261012/top_structure_20261012/review/README_ZH.md` 第22行称P05在X分量候选敏感性后追加；同包 `evidence/REPORT_ZH.md` 第118行称融合端点没有独立平均前输入，原始X候选保持None。 |

## 对推进方向的修正

1. 后续冻结候选仍使用同一处理后输入与明确参考。没有证据要求撤销平均 x，也不应把本轮工作变成重新定义原始点评分。
2. 原始配对、上下 x 差与预处理移动旁列，用于解释“处理后几何较好，但不能据此认证原始操作正确”。无原始层时标缺失，不写成零，也不因此自动否定可用的处理后几何评价。
3. **大 X 不是错配的充分证据，小 X 也不是正确配对的证明。** P05是带具体观察的单例线索，不能用它给所有 x 差统一罚分。语义配对复核与几何对齐不是同一件事。
4. 标准化 x 不一致与缺少可信上下配对应分开：前者允许按既定预处理评分，后者不能自行猜配对后产出完整 Q。对人员的解释还受来源、参考、曝光和资格约束，不能把几何总分直接命名为完整人员能力。
5. 现阶段优先扩展合资格manual覆盖、核实参考和比较少数冻结候选；原始层沿用已有诊断，不新增自由参数或大规模实验。

建议主计划把“保留两个层次”明确改写为“**主 Q 仍评价处理后几何；原始层作为旁列诊断，不在本轮新增罚项**”。这属于说明评价对象，并非修改正式合同。

## 核验范围

已交叉阅读最新归档报告、评分及优化调用关系、P05原始约束和旧包历史说明；未重跑评分或大规模测试，因为本次没有代码变化。未逐张重新判断点对语义。旧包证据仍依赖Downloads归档，其成员路径已记录以便复核。入口索引由主线程与并行成果统一同步。
