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
- Confirm compatibility, residual, and preview-only suggestion sections are placeholder-only in M8.
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
- The panel shows compatibility / residual / preview-only suggestion placeholder sections.
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
