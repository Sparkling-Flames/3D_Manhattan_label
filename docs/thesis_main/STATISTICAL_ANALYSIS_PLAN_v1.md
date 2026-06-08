# Statistical Analysis Plan v1

## 0. Scope

This document only records statistical planning details that are already compatible with the current thesis outline and the round-based execution protocol.

It does not:

- change the four-stage main line
- change `P1 / C1 / C2 / T1 / V1` freeze boundaries
- rewrite the thesis-facing framework
- use Main/Test/Validation results to redefine admission, `w_max`, routing freeze, or protocol core

The expected execution path assumes `18-20` workers pass `P1` and continue through `C1 / C2 / T1 / V1`.

---

## 1. General Principles

### 1.1 Separation of roles across rounds

- `P1 / PreScreen` provides admission, `r_u^(0)`, `w_max`, blind-trust pre-evidence, and prescreen audit outputs.
- `C1 / C2` provide the main quality, reliability, worker-scene support, and routing-side evidence needed for `RQ2` and `RQ3`.
- `T1 / Main-Test` is primarily an efficiency round for `RQ1`.
- `V1 / Main-Validation` reports the frozen deployment strategy under the locked protocol.

### 1.2 MDE policy

- MDE values must not be set using Main/Test/Validation outcomes.
- MDE inputs should come from Pilot, smoke-test evidence, historical exports, or engineering-interpretability thresholds.
- If a post-`P1` amendment is needed, it must be logged as a protocol amendment and must not flow back to change admission, `w_max`, routing freeze, or the protocol boundary.

### 1.3 Missingness and logging

- `lead_time` is not part of the primary estimand for `RQ1`.
- Any fallback from `active_time` to `lead_time` must be reported as sensitivity support, not as a silent merge into the primary estimand.

---

## 2. RQ1 Plan

### 2.1 Design

`RQ1` targets efficiency under the `Main-Test` round.

Planned design:

- `Manual_Test` and `SemiAuto_Test` use a same-image dual-condition design
- `Nimg = 100`
- each base image appears exactly twice at the task-instance level:
  - one `Manual` task instance
  - one `SemiAuto` task instance
- total task instances are approximately `200`
- `k = 1` per condition at the task-instance level

### 2.2 Allocation constraints

- the same worker must not see both conditions of the same base image
- each worker's Manual and Semi task counts should be kept as balanced as possible
- task order should be randomized
- worker allocation and condition assignment should be retained in the analysis object, not discarded after export

### 2.3 Primary estimand

The primary estimand is active-time efficiency under the same-image dual-condition design.

Primary outcome:

- `active_time`

Primary contrast:

- Manual versus SemiAuto active-time difference on the same base-image pool

### 2.4 Primary inference

Primary inference should use a design-respecting procedure:

- restricted permutation, or
- cluster-aware bootstrap

The resampling or permutation procedure must preserve:

- image pairing
- worker allocation structure
- condition assignment structure

This is the main inferential path.

### 2.5 Auxiliary model

As a model-based secondary analysis, fit a crossed mixed-effects model with:

- fixed effect: `condition`
- random intercept: `worker`
- random intercept: `image`

This model is supplementary and should be interpreted as a supporting analysis rather than the only inferential basis.

### 2.6 Effect reporting

Report:

- median difference in `active_time`
- proportional time saving
- bootstrap confidence interval

`Mann-Whitney U` may be reported only as supplementary or descriptive analysis. It must not serve as the sole primary test.

### 2.7 Why `k = 1` is acceptable for RQ1

`k = 1` is acceptable for `RQ1` because the target is efficiency, not the full quality/reliability evidence chain.

The main quality and reliability evidence does not rely on `Main-Test k = 1`. Instead, those responsibilities are carried by:

- `Calibration_manual`
- `Calibration_semi` paired subset
- Validation-side audit outputs

### 2.8 Active-log downgrade rule

If either condition below occurs:

- active-log coverage `< 90%`, or
- Manual and Semi coverage differ by more than `5` percentage points

then the `RQ1` primary conclusion must be downgraded to a sensitivity-supported conclusion.

In that case, report at minimum:

- `lead_time` fallback summary
- coverage bias audit
- unknown / missing rate
- missing-reason distribution

`lead_time` must not be merged into the primary estimand.

---

## 3. RQ2 Plan

### 3.1 Core design

`RQ2` keeps the thesis-outline main design:

- a same-image paired subset with `Nimg = 25`
- comparison between Manual and SemiAuto on that paired subset

### 3.2 Primary inference

Primary inference should remain:

- paired permutation, or
- paired bootstrap

### 3.3 Interpretation scope

This subset is primarily powered to detect moderate-to-large effects.

Therefore:

- it is suitable for identifying meaningful shifts in quality, agreement, or failure behavior
- it is not suitable for making a strong "no difference" claim when only very small differences are observed

### 3.4 Counterexample / failure-type distribution

Counterexample-type or failure-type distributions should not use ordinary `chi-square` as the main test.

Main reporting should use:

- descriptive summaries
- paired/bootstrap summaries, or
- exact paired summaries when appropriate

If `chi-square` is included at all, it should be appendix-only sensitivity material rather than the main inferential claim.

---

## 4. RQ3 Interpretation Contract

### 4.1 Expected execution path

If `18-20` workers pass `PreScreen`, the expected path is full execution of:

- `P1`
- `C1`
- `C2`
- `T1`
- `V1`

### 4.2 What still governs scene-specific routing

Even with sufficient worker count, scene-specific routing still depends on post-`C1/C2` support conditions, including:

- `(worker, scene)` support
- `N_{u,s}`
- CI precision
- activation support

### 4.3 Evidence-source contract

- the primary comparative evidence for `Random / Global / Full` comes from `Calibration_manual` offline replay
- `V1` normally reports only the frozen main strategy, typically the `Full` policy
- if `Random / Global` are reported in `V1`, they must be support-set shadow or replay outputs, and support rate must be reported explicitly

### 4.4 Interpretation rule

Interpretation is fixed as follows:

- global reliability plus OOD/stress sequential redundancy is the robust backbone
- scene-specific routing is a conditional module
- scene-specific routing is only credited as a main implementation mechanism when activation support is sufficient
- otherwise it must be reported as an audit / explanatory mechanism rather than a global main claim

---

## 5. Contingency and Downgrade Notes

### 5.1 Worker pass-count contingency

Worker pass-count downgrade is a contingency rule for attrition, unexpected admission failure, or coverage failure.

It does not alter the planned protocol and does not replace the expected path of full participation.

预期路径假设 pass count `>= 18`。

Contingency 阈值：

- `pass >= 16`：完整执行 `RQ1 / RQ2 / RQ3` 计划。
- `12 <= pass <= 15`：保留 `RQ1 / RQ2`；`RQ3` scene-specific 只在 activation support 达标场景报告。
- `pass < 12`：`RQ3` 降级为 global / stress audit，不做稳定 worker subtype 或 scene-specific 主张。

这是 contingency 解释规则，不代表预期失败。

### 5.2 Protocol boundary

Any contingency-triggered downgrade affects interpretation scope and claim strength only.

It does not authorize:

- changing four-stage structure
- changing `P1 / C1 / C2 / T1 / V1` freeze boundaries
- redefining admission
- redefining `w_max`
- rewriting the routing contract after the fact
