# Paper A C1→C2-B 根因收口方法修订 v1

状态：2026-07-26 dry run 冻结；适用于正式 C1 closeout 后、任何 C2-B candidate enumeration 前。

## 1. 边界与优先级

本修订只澄清 vFinal、Protocol、SOP 与 SAP 已定义主线的可执行统计和审计行为，不改变轮次、
assignment、admission、routing、estimand 或 `Pilot -> P1 -> C1 -> C2-B -> C2-A-RP -> T1 -> V1`
顺序。若本修订与上述真源冲突，以真源为准并 fail-closed。dry-run 产物不是正式证据。

## 2. C1 task-adjusted Q_GT bootstrap

- 点估计仍由唯一的 worker fixed effect + task random intercept estimator 生成；不在本阶段生成排名。
- building 完整时按 building 后 task 重采样，否则按 task 重采样；每个副本仍要求至少两个外层 cluster。
- 单个副本缺少原始 worker level、未收敛、奇异或产生非有限值时，只丢弃该副本并按原因计数，
  不得以 `KeyError` 终止整个 Q_GT 模型。
- 正式成功门槛维持 requested replicates 的 75%，且绝对成功数不少于 20；低于门槛整体
  `not_evaluable`，不得用 OLS 或零方差替代。

## 3. C1 risk mixed model 与数值边界链

正式模型为：worker fixed intercept、群体 fixed risk slope、worker random risk slope、building random
intercept、task-within-building random intercept。worker fixed intercept 仅控制 C1 outcome level，绝不替代
独立的 task-adjusted Q_GT estimator。

优化器顺序固定为 `lbfgs -> powell`。方差边界按 residual variance 的 `max(1e-10, 1e-6 × residual variance)`
判断，且只允许一次预注册 nested refit：

1. 只有 worker-slope variance 在边界：移除 worker random slope，改为 common slope；
2. 只有 task variance 在边界：只移除 task component；
3. 只有 building variance 在边界：只移除 building component；
4. 同时出现多个边界、nested refit 出现新边界、所有优化器不收敛或参数不可识别：整体 fail-closed。

移除 task 或 building component 时，其 downstream simulation variance 固定为已识别的零；另一 cluster
component 和后续 building→task 分层重采样保持不变。

## 4. 唯一 worker-slope simulation 真源

- random-slope 模型中，C1 可识别 worker 使用 `risk_slope_for_simulation` 与个体 posterior SE；总尺度为
  个体 posterior variance 与共享 group fixed-slope variance 之和的平方根。
- 个体斜率不可识别时，使用 group mean、group fixed-slope SE 与 between-worker SD 构成群体先验。
- common-slope 模型中，同一 simulation draw 的所有 worker 共享同一个 group slope draw。
- projection 与 empirical bootstrap 必须调用同一 resolver；不得各自定义斜率真源。

## 5. C1/C2 联合 posterior 排名

rank score 是 risk-adjusted C2 observations 对完整 C1 worker baseline 多元正态 posterior 的更新均值。
C1 worker contrast covariance 必须完整保留；C2 likelihood covariance 同时包含 residual、task、building、
共享 group-slope 与 worker-specific slope uncertainty。没有 C2 delivery 时 posterior 等于 C1 prior；一条或少量
C2 observation 只能按精度部分拉动，不能整体替换 C1 baseline。Q_GT 为 higher-is-better，更新不使用反向符号。

## 6. P1 retrospective integrity

- 从原始 P1 export 恢复 `base_task_id` 与 `image_id`；history overlap 必须消费恢复后的身份。
- Manual 无 parent 且同一真实 task 出现跨 worker 精确几何：`non_independent_suspected`，等待审核；
  不自动确认为 copy。
- Semi 跨 worker 精确几何若等于 SHA 绑定的初始预标注：`shared_initialization_match`，不判 copy；若初始
  预标注缺失则 `not_evaluable`，若不相同则 `non_independent_suspected`。
- explicit parent 且时间先后、owner 与精确几何均成立时，仍可自动确认为 non-independent。
- 所有修正只进入 retrospective evidence；不回写 P1 admission 或 C1 assignment。
- `P1_INTEGRITY_BUNDLE_FROZEN` 与 `P1_PREDICTIVE_EVIDENCE_READY` 分开报告。后者为 false 时只禁用
  P1 predictive component，不阻断 risk-only C2-B。

## 7. 两层阈值合同

Layer 1 在 C1 closeout 前以不读取 crowd outcome 或 candidate feasibility 的 GPU engineering dry run 冻结
feature robustness 数值阈值、最小 audited support 和 missing/nonfinite fail-closed 规则；阈值合同记录 reference
与 candidate 的观测上界及机械上取整 margin。两侧 audit 都必须通过。Layer 2 在同一时点冻结 design
threshold 的公式 ID、常数、输入字段与方向。

正式 C1 后，代码先物化 `c1_c2_design_parameters.csv` 和 capacity 输入审核请求。reviewer 只核对并批准：

- formula contract SHA；
- C1 design parameters SHA；
- capacity manifest SHA。

机械派生器只允许白名单公式，输出 `paper_a_c2b_design_selection_thresholds_v2`。它不读取 candidate、
simulation 或 feasibility 产物；任一 SHA stale、输入缺失、公式未知或派生值非有限时，candidate enumeration
必须为 0。最终 derived threshold SHA 同时绑定 candidate manifest、risk summary 和 build gate。

## 8. 最小正式审计字段

- Q_GT：requested/successful replicates、successful fraction、minimum successful count、failure reason counts；
- risk model：formula、optimizer attempts、boundary components、removed components、nested model form；
- simulation：每个 worker 的 slope source、完整 C1 covariance、joint posterior rank method；
- P1：初始化 import SHA、无 parent exact count、两个独立 P1 状态；
- threshold：formula/C1/capacity/reviewer approval SHA、formula IDs、输入字段、
  `derived_before_candidate_enumeration=true`、`post_feasibility_inputs_consumed=false`。

## 9. 2026-07-26 dry-run 事实记录

- 运行环境：Python 3.11.7、PyTorch 2.11.0+cu128、CUDA 12.8、RTX 4060 Laptop GPU、
  float32、physical batch size 4；未发生 CPU、AMP 或 batch 自动回退。
- feature audit：reference 1647 张、candidate 458 张；reference/candidate 文件泄漏数为 0。
  reference/candidate 的 off-grid circular relative-L2 max 分别为
  `0.2362096905708313` / `0.2786831557750702`；seam relative-L2 q95 分别为
  `0.03246062193065881` / `0.048300980962812885`；两侧 audited support 均为 32，
  均通过冻结阈值。
- P1 retrospective correction：1481 条记录中 independent 1105、confirmed 129、suspected 247、
  not-evaluable parent 0；214 条属于无 parent 跨 worker 精确几何审计。suspected/confirmed 记录继续逐条排除，
  不回写 admission 或 C1 assignment。完整几何评分后有 19 名 worker 同时满足 integrity eligibility、
  数值组件和 sufficient support，因此 `P1_INTEGRITY_BUNDLE_FROZEN=true` 且
  `P1_PREDICTIVE_EVIDENCE_READY=true`。
- resolved P1/C1 history 在 458 个 C2 候选中识别 144 个 overlap，其中 57 个来自恢复后的 P1 identity；
  旧 canonical 空 identity 不再漏掉这 57 个任务。
- 当前 C1 rehearsal 没有 `global_analysis_eligible=true` 的正式 Q_GT risk-model records，故真实 risk mixed
  model dry run 正确返回 insufficient support；这不是 optimizer 或 boundary fallback 失败，只能由最终 C1
  closeout 数据验证。
- 当前 preflight 的剩余 blocker 仅为 `missing:split_proposals` 与 `static_evidence_not_frozen`；其共同根因是
  尚无人工批准的 authoritative building registry，因而尚不能生成并批准 source/holdout split proposal。
  dry run 未生成 C2-B assignment。
