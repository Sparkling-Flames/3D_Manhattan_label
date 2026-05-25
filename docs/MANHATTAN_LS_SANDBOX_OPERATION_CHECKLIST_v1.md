# Manhattan LS Sandbox Operation Checklist v1

This checklist governs the first M8 dev-only Label Studio sandbox operation test for the Manhattan toolchain.

The M8 panel is an experiment-outside prototype. It is not an official userscript, not worker-facing, not a formal Label Studio integration, and not part of the current Manual or Semi-Auto experiment.

## 1. Allowed Sandbox Scope

- Test only in an independent Label Studio sandbox project.
- Use copies of the 2026-05-07 smoke tasks or a dedicated sandbox import.
- Do not use any current formal experiment project.
- Do not invite ordinary workers.
- Allow only developer / expert testers.
- Do not record sandbox active_time or behavior as thesis experiment evidence.
- Do not mix sandbox output into `P1/C1/C2/T1/V1` artifacts.
- Keep sandbox exports separate from formal `export_label/` data.

## 2. Pre-Test Checklist

All items must be checked before enabling the M8 dev-only panel:

- M6 validation output exists.
- M6 validation output has no errors.
- The sandbox import uses copied 2026-05-07 smoke tasks or a dedicated sandbox import.
- The sandbox import is stored under `import_json/sandbox/`, not under formal `P1/C1/C2/T1/V1` import directories.
- The sandbox import tasks include `sandbox_only=true` and `manhattan_m8_sandbox=true`.
- The sandbox project exists and is clearly named as sandbox / developer-only.
- Sandbox tasks are copied tasks or dedicated sandbox import tasks, not production tasks.
- The tester understands that panel output is preview-only.
- The tester understands that compatibility failure is not correctness.
- The tester understands that residual output is not worker quality.
- The tester understands that suggestion text is only a preview-only review prompt.
- `tools/official/ls_userscript_annotator.js` is unchanged.
- `tools/official/ls_userscript_debug.js` is unchanged.
- `tools/label_studio_view_config.xml` is unchanged.
- `tools/vis_3d.html` is unchanged.
- `tools/ls_3d_logic.js` is unchanged.
- The dev-only script path is separate from the official userscript path.
- The rollback path is known: disable the dev-only script and delete the sandbox project if needed.

## 3. Script Variant Test Order

Run the sandbox test in this order:

1. Install only `tools/dev_only/manhattan_ls_sandbox_panel_debug.user.js`.
2. Open one sandbox task and confirm the panel appears.
3. Confirm `keypoint_read_status` and `keypoint_count`.
4. Disable the debug script.
5. Install only `tools/dev_only/manhattan_ls_sandbox_panel_timed.user.js`.
6. Run 1-2 short sandbox tasks.
7. Confirm `/log_time` receives sandbox active_time payloads with exclusion tags:
   - `log_context="manhattan_ls_sandbox"`
   - `tool_stage="M8"`
   - `script_variant="timed"`
   - `is_sandbox=true`
   - `sandbox_project=true`
   - `exclude_from_primary_active_time=true`
   - `exclude_from_thesis_evidence=true`
   - `not_worker_facing=true`
   - `not_p1_c1_c2_t1_v1_artifact=true`
   - `manhattan_panel_version`

Do not run the debug and timed scripts at the same time. Both use `window.__HOHONET_M8_SANDBOX_PANEL_ACTIVE__` as a runtime guard.

Do not install either script in a formal Label Studio project.

## 4. During-Test Checklist

- Open one sandbox task.
- Confirm the panel appears only in the sandbox browser profile.
- Confirm the panel reads current page keypoints or reports `keypoint_read_status=unavailable`.
- Confirm the panel displays keypoint count.
- Confirm compatibility and residual sections explain that Python parity/residual code is not embedded while sandbox JS preview compatibility/residuals feed the Manhattan deviation section.
- Confirm the panel displays guardrails.
- Do not move points because of the panel.
- Do not treat any panel text as correctness.
- Do not treat any panel text as worker quality.
- Do not use panel output for routing.
- Do not use panel output as formal `g_t`.
- Do not use panel output as a `P1/C1/C2/T1/V1` artifact.

## 5. Hard Prohibitions

- No worker-facing deployment.
- No official userscript modification.
- No view config modification.
- No writeback.
- No submit action.
- No snap coordinates.
- No adjustment vector.
- No auto-correction.
- No corrected annotation payload.
- No routing.
- No formal `g_t`.
- No worker tier.
- No correctness label.
- No thesis active_time / behavior evidence.

## 6. Post-Test Checklist

- Confirm no annotation was modified by the panel.
- Confirm no annotation was submitted by the panel.
- Confirm no sandbox export is stored under formal `export_label/` data.
- Store sandbox exports, if any, in a clearly separated sandbox-only location.
- Record tester, sandbox project name, smoke task source, and panel version.
- If any unexpected behavior appears, disable the dev-only script and delete the sandbox project.

## 7. M8 Acceptance

M8 is ready only for limited sandbox operation testing if:

- A sandbox task can be opened.
- The panel appears in the sandbox context.
- The panel reports keypoint read status and keypoint count.
- The panel shows compatibility / residual notes plus preview-only suggestion placeholder sections.
- The panel displays guardrails.
- No annotation is modified.
- No annotation is submitted.
- No official userscript, view config, `vis_3d.html`, or `ls_3d_logic.js` file is changed.

## 8. M8.2 Active-Log Audit

After timed sandbox testing, run the read-only M8.2 active-log audit before using any sandbox telemetry for debugging notes:

```bash
python tools/audit_m8_sandbox_active_log.py --input active_logs/<active_time_log>.jsonl
```

Use `--output analysis_results/manhattan_geometry_diagnostic/m8_sandbox_active_log_audit_<date>.json` only when a saved smoke/probe audit sidecar is needed.

The audit checks only whether M8 sandbox telemetry is correctly isolated from primary active_time. It does not validate the RQ1 primary estimand, does not modify logs, and does not read or modify `export_label/`.

Treat any exclusion-tag failure as a blocker:

- `exclude_from_primary_active_time=true`
- `exclude_from_thesis_evidence=true`
- `not_worker_facing=true`
- `not_p1_c1_c2_t1_v1_artifact=true`

Warnings such as missing legacy `session_id`, unknown identity fields, or heartbeat interval drift should be investigated, but they do not by themselves make sandbox telemetry part of thesis evidence.

## 9. M8.3 Timed Sandbox Active-State Parity

The timed sandbox script must keep sandbox telemetry excluded from primary active_time while matching the official active-state counting rule as closely as possible:

- Count sandbox `active_seconds` only when the page is visible.
- Count only on an annotation page.
- Require a real interaction within the last 15 seconds: `mousemove`, `keydown`, `click`, `scroll`, or `wheel`.
- Stop counting while the page is hidden.
- If the page is hidden for at least 6 seconds, require a new real interaction before counting resumes.
- Continue sending heartbeat telemetry every 15 seconds, but report activity-gated `active_seconds` and `active_seconds_fragment`, not wall-clock page time.
- Keep `telemetry_elapsed_seconds` as a separate wall-clock diagnostic field for sandbox telemetry only.

M8.3 still does not authorize snap coordinates, adjustment vectors, auto-correction, correctness labels, worker-tier labels, routing decisions, formal `g_t`, or `P1/C1/C2/T1/V1` artifacts.

## 10. M9 Manhattan Deviation Display

The dev-only sandbox panel may display a conservative Manhattan deviation section for expert / developer testing only.

Allowed M9 fields:

- `compatibility_status`
- `n_keypoints`
- `n_pairs`
- `vertical_pair_x_residual`
- `ceiling_y_range`
- `floor_y_range`
- `wall_height_range`
- `manhattan_deviation_score`
- `deviation_level`
- explicit unavailable / exclusion reason

M9 scores are preview-only geometry diagnostics. They are not correctness labels, not worker quality labels, not snap coordinates, not next corner prediction, not annotation writeback, not routing inputs, not formal `g_t`, and not `P1/C1/C2/T1/V1` artifacts.

## 11. M10 Direction-Only Manhattan Diagnosis

The dev-only sandbox panel may display a `Manhattan diagnosis` section for expert / developer testing only.

Allowed M10 fields:

- `primary_issue_type`
- `primary_issue_severity`
- `primary_issue_explanation`
- `affected_pair_index`
- `affected_wall_index`
- `pair_x_alignment_summary`
- `ceiling_alignment_summary`
- `floor_alignment_summary`
- `wall_height_summary`

`primary_issue_type` is selected from the largest normalized preview residual component:

- `pair_x_alignment = vertical_pair_x_residual / width`
- `ceiling_alignment = ceiling_y_range / height`
- `floor_alignment = floor_y_range / height`
- `wall_height_consistency = wall_height_range / height`

The explanation must be direction-only. It may say which pair or wall is most likely responsible for visible preview distortion and may use words such as left/right, above/below, or larger/smaller. It must not output target coordinates, delta-x / delta-y adjustment instructions, snap coordinates, next-corner prediction, automatic correction, annotation writeback, correctness labels, worker-tier labels, routing decisions, formal `g_t`, or `P1/C1/C2/T1/V1` artifacts.

Timed sandbox telemetry may include only `preview_only_primary_issue_type` and `preview_only_primary_issue_severity` for M10 diagnosis. It must not send keypoint coordinates, target coordinates, or adjustment vectors.

## 12. Sandbox-Only Meta Guard And Preview-Order Controls

For sandbox operation only, the dev-only scripts may mirror the official helper's operational ergonomics:

- A best-effort sandbox meta-label guard checks the same mutually exclusive rules: `trivial` must not coexist with non-trivial difficulty labels, and `acceptable` must not coexist with other `model_issue` labels.
- The guard may block an invalid sandbox submit/update attempt, but it must not submit anything itself and must not write annotation payloads.
- A draggable preview-order panel may reorder only the current 3D preview and corner-order overlay.
- A show/hide corner-order button may toggle the overlay labels only.
- Preview-order controls are local sandbox UI aids. They are not annotation edits, not saved formal artifacts, not routing inputs, not formal `g_t`, and not `P1/C1/C2/T1/V1` artifacts.

## 13. M10.1 Official-Style Preview-Order Panel

M10.1 aligns the sandbox preview-order panel visually with the official userscript preview-order panel while keeping sandbox-only behavior:

- Use an official-style compact floating panel with a draggable header, high-contrast dark background, `Preview order` title, active pair slot, status line, compact rows, and consistent button styling.
- Show current pair order, selected / active pair index, previous / next pair controls, swap control, and reset preview order control.
- Keep the show / hide order overlay button next to the 3D preview controls rather than inside the diagnostic panel.
- The panel may reorder only the sandbox 3D preview and local corner-order overlay.
- The panel must not write annotations, submit tasks, modify official userscripts, modify view config, emit target coordinates, emit snap coordinates, or create any routing / formal `g_t` / `P1/C1/C2/T1/V1` artifact.

## 14. M11 Preview-Order Usability Pass

M11 keeps the same sandbox-only behavior and improves only readability / usability of the preview-order panel:

- Show compact pair rows with pair index and coarse preview values.
- Highlight the active pair row.
- Keep previous / next, swap, reset, and show / hide overlay controls visible and legible.
- Do not add geometry algorithms, coordinate suggestions, next-corner prediction, snap, auto-correction, annotation writeback, routing, worker-tier labels, correctness labels, formal `g_t`, or `P1/C1/C2/T1/V1` artifacts.
