# C2-B researcher scope / GT 审查记录（2026-08-07）

状态：`researcher_scope_adjudication_recorded_unblinded`。

本文件记录研究者当前裁决及 GT 质量判断。研究者在裁决前已经接触过部分 worker direction / geometry 信息，因此本轮**不得表述为独立盲审**。本记录尚未写入正式 scope/reference registry，也尚未触发正式 evidence 重算。

## 研究者当前裁决

| Project 76 task ID | base task | Scope 判断 | GT 判断 | 当前处置 |
| ---: | --- | --- | --- | --- |
| 3416 | `VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d` | 本轮未重新裁决 | 局部 GT 问题；不是整图 GT 失效 | reference disposition 仍待关闭 |
| 3413 | `VFuaQ6m2Qom_109e18c64a614dc49e41a33ae979f98a` | in-scope | 未声明问题 | 保留 |
| 3420 | `jh4fc5c5qoQ_77e6cfabf32d46fc9398ce824843adaa` | **in-scope** | GT 跨门扩张，存在局部错误 | Scope 保留；GT 进入局部 reference review |
| 3422 | `jh4fc5c5qoQ_a59a3a61089343a8ba2834e7d3cd1066` | in-scope | 未声明问题 | 保留 |
| 3423 | `jh4fc5c5qoQ_b000c5baa76b454caa1c58c9aac585f6` | **in-scope** | GT 有小错；相机所在房间边界本身难判断 | Scope 保留；GT 进入局部 reference review |
| 3424 | `jtcxE69GiFV_0aa01000f1934e73b35c348fa8d15040` | in-scope | 未声明问题 | 保留 |
| 3427 | `jtcxE69GiFV_4d7ce55eeb6643079aba3b10360de8d8` | in-scope，优先 | 未声明问题 | 保留 |
| 3430 | `jtcxE69GiFV_9f0e2562fcf447f5a7c5e44e85978148` | in-scope | 未声明问题 | 保留 |
| 3434 | `pRbA3pwrgk9_0350fc96e88c4a52886d4eb50b2d52c6` | **OOS** | 单一房间，但 GT 不可靠 | 退出 primary geometry；GT 只保留审计备注 |
| 3439 | `pRbA3pwrgk9_8b07a4b08cf447abb246769d8dce8494` | **OOS** | GT 不可靠 | 退出 primary geometry；GT 只保留审计备注 |
| 3442 | `pRbA3pwrgk9_bc9ae89832854c19a69741f97291efad` | **OOS** | 单一房间，但 GT 不可靠 | 退出 primary geometry；GT 只保留审计备注 |
| 3446 | `pa4otMbVnkk_48321c1bb20244f1b43b2c41b4dc9657` | in-scope | 未声明问题 | 保留 |
| 3447 | `pa4otMbVnkk_5d1adb544bb14217ba5ded2eb82cd8e3` | in-scope（原始输入写作 `34447`，暂按 3447 记录） | 未声明问题 | 编号仍待确认 |
| 3450 | `zsNo4HB9uLZ_65eefaf93e6249908e6389eb4eabf0f5` | in-scope | 未声明问题 | 保留 |

## 本轮形成的关键边界

1. `3434 / 3439 / 3442` 的 OOS 是研究者 scope 判断；“GT 不可靠”是附带质量发现，两者不得混写成同一个判定理由。
2. `3420 / 3423` 明确为 in-scope；局部 GT 问题不能反向把图片判成 OOS。
3. OOS 任务若写入正式 registry，应整体退出 primary geometry evidence；当前文件本身不执行该修改。
4. 3420、3423、3416 的 GT 问题仍需合法 reference terminal disposition：retain / amend / unavailable。不能只凭 worker 多数自动修订。
5. 本轮不是 blinded review。若正式 review record 必须维持 `worker_and_analysis_metric_blinded`，应由未接触 worker 结果的独立审查者完成第一轮并单独留痕。

## 对外部审查意见的独立评估

### 成立

- 3416 目前首先证明的是 `confirmed candidate-detection blind spot`，不等于已经完成 `confirmed GT error` 的独立终审。
- `reference_normalizer_status=passed` 仅代表机器可消费，不代表局部语义正确。
- 新局部规则只能作为 post-C2 diagnostic / sensitivity audit；不能用已见结果的 46 张图反向校准并宣称为 v18 primary cutoff。
- 46 张图的机器 dry-run 可以并行，但全部候选的人工关闭不应临时升级为 C2-A-RP 新硬门。
- Scope 应在唯一图片层消费，不能把 Project 76/77 副本重复计数，也不能把任务级 OOS 扩张成 worker 或全局 stage gate。
- 第一轮正式独立 review 不应展示 worker 002/036、cluster 或多数模式。

### 需要限定后才能采纳

- “最大匹配 + 局部 fallback”与 `cap_failure_is_fallback=true` 的方向一致，但当前代码是全局 fail-closed；在没有冻结 subordinate operational decision 和验证 assignment schema 前，不能当作已经授权的正式实现。
- 恢复 4 个 runtime ID 只能使用 Label Studio all-tasks list 或其他权威 runtime 真源。若实际未导入，应记 deployment failure，不能按顺序猜 ID。
- 关键任务关闭后可以立即重算并只发 Block 1；但 go 条件取决于正式 registry、evidence 重算和完整 pair assignment，不以“同一天启动”的时间估计代替验证。
- 3439 是高杠杆 stress anchor；3434、3442 也是 stress task但支持较低。三者 OOS 后必须根据实际 eligible rows 重算，不能直接沿用外部审查文本中的约数。

### 不能直接采纳

- 不能把当前研究者审查追认成 blinded independent review。
- 不能因为局部 GT 机制存在缺口，就默认修改 v18 risk threshold、CI threshold 或 worker eligibility。
- 不能为了凑足 stress capacity 选择性改变 Scope；Scope 理由必须独立于 capacity 和 worker performance。

## 下一步安全动作

1. 将上述 scope 判断以明确的 post-C2 / pre-C2A 依据写入正式 scope disposition；
2. 对 3416、3420、3423 分别完成 reference terminal disposition；
3. 从权威 all-tasks source 关闭 4 个 runtime identity；
4. 从真源完整重算 canonical risk evidence、observed support、post-C2 profile、precision plan 和 Block 1 capacity；
5. 根据重算结果，再决定完整 20/20 matching、局部 fallback 或 validation-only stress reserve 扩充。
