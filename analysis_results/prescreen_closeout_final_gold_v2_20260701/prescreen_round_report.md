# PreScreen Round Report

P1 closeout materializes admission, r_u^(0), w_max handoff, and audit evidence only. It does not freeze formal r_u, tau_d, score, or routing.

- Workers: pass=9, pass_with_watch=14, fail=6, eligible_for_C1=23.
- Active time: userscript logs are primary; lead_time fallback is sensitivity-only and appears as fallback watch.
- Fallback watch workers entering C1: 12, 14, 31, 34, 35.
- Duplicate revision: resolved manual overrides are retained as audit trace and do not block admission.
- Resolved duplicate revision overrides: manual_override_resolved_final_annotation_4595.
- Semi synthetic issue review: 6 mirror pairs from analysis_results\prescreen_closeout_final_gold_v2_20260701\raw_inputs\prescreen_semi_synthetic_trap_issue_review.csv; labels come from manual_review reviewed_* fields, not planned_operator.
- Undercoverage: P1 nonblocking watch; task-majority undercoverage does not become worker-level exclusion.
- Original P1 closeout and GT106-only gtfix run are superseded by the consolidated final-gold v2 closeout. They are retained only as historical snapshots.
- Final-gold v2 corrections: task 564 geometry_contract affected 3065, 3137; task 696 scope_contract affected 3077, 3149.
