# A4 deployment pool identity C1 v1

- Identity status: **A4_POOL_IDENTITY_READY**
- Eligibility status: **A4_ELIGIBILITY_SPEC_INCOMPLETE**
- Candidates: 580; identity mapped: 580; identity fail-closed: 0.
- Development eligibility is **not defined** in this identity layer; `eligibility_spec_not_frozen` is emitted for every candidate.
- Observed geometry-valid candidates: 577; pool support: {1: 18, 2: 41, 3: 32, 4: 15, 5: 9, 11: 12, 12: 12}; pools meeting k=3: 80 / 139.
- Strict realization-matched geometry-valid sensitivity: 547; pool support: {0: 2, 1: 19, 2: 42, 3: 34, 4: 12, 5: 6, 11: 24}; pools meeting k=3: 76 / 139.
- Formal appears_in_internal_distribution values: {'false': 580}; role: not_an_eligibility_source.
- Assignment realization status: {'matched': 549, 'missing': 31}; assignment status does not gate identity and is reported as provenance sensitivity.
- Formal duplicate status: {'keep_selected_version': 5, 'none': 575}; keep_selected_version does not gate identity.
- Formal canonical join: 580 candidate rows were processed against the SHA-bound formal canonical sidecar.
- Identity deployment pools: 139; all identity pools, including zero strict-sensitivity pools, are retained.
- Condition distribution: {'manual': 516, 'semi': 64}.
- Role distribution: {'Calibration_anchor': 276, 'Calibration_core': 240, 'Calibration_semi': 64}.
- Pool key: SHA-256(stage, round_id, condition, base_task_id, task_id, project_id, ls_runtime_task_id); source export SHA is provenance only.
- No GT/reference/quality/outcome/holdout values were consumed; deny paths and deny columns are enforced at the input layer.
- No selector, performance estimate, contract, SAP, routing, or frozen input was changed.
