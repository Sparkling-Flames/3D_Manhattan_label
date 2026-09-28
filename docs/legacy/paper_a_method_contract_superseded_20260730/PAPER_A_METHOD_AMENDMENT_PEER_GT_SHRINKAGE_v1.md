# Paper A 同行、GT 与收缩估计方法修订 v1

## 状态与边界

本修订登记 C1 派生分析的候选升级：按 estimand 拆分资格，区分同行中位数、medoid LOO 与 strict LOO，并新增 Q_GT 与结构失败率的经验贝叶斯估计。原始 export、assignment、active-time 与 GT 均不可回写；GT 冲突只进入人工审查队列。

本修订涉及正式 Global 与 C2-B 候选集合的协议语义。配套 manifest 在批准前均为 `candidate` 且 `interpretation_allowed=false`；候选状态不得生成正式 policy 或 assignment。正式启用须在 Main outcome 可见前填写批准人与批准时间，并冻结输入及代码 SHA。

## Estimand-specific gates

GT、peer、medoid LOO、strict LOO 与 structural opportunity 分别计算资格。GT reference pending 只关闭 GT estimand，不关闭具备合法过程、独立性、scope 与结构可计算性的 peer/structural estimand。旧 `loo_analysis_eligible` 保持 strict sensitivity 语义。

## 估计与政策角色

- `Q_GT_task_adjusted_FE` 保留为敏感性；normal-normal EB 输出 `Q_GT_EB`。EB 失败时正式 Global fail closed。
- 本历史 amendment 不再定义任何当前同行字段或 eligibility；正式字段、状态与用途仅由 `PAPER_A_METHOD_CONTRACT_CURRENT.json` 定义。
- `F_struct_EB` 与 raw rate 同时报告；先验不可识别时显式使用 Jeffreys Beta(0.5, 0.5)。
- Strong Global 只在阈值 manifest 已批准且 EB 模型有效时物化正式排名。

## 多峰与 GT 冲突

4:1 与 3:1:1 可标为 `dominant_with_dissent`；3:2 保持 `supported_multimodal`，不自动选择多数簇。少数簇更接近 GT 不改变 crowd structure，只生成候选审查事件。任何候选事件不得自动修改 GT、worker profile、C2 设计或 prevalence。
# STATUS: superseded_non_normative; retained only as historical amendment context. Current formal method fields are defined only by PAPER_A_METHOD_CONTRACT_CURRENT.json.
