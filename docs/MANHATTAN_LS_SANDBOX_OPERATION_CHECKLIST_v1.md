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

## 3. During-Test Checklist

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

## 4. Hard Prohibitions

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

## 5. Post-Test Checklist

- Confirm no annotation was modified by the panel.
- Confirm no annotation was submitted by the panel.
- Confirm no sandbox export is stored under formal `export_label/` data.
- Store sandbox exports, if any, in a clearly separated sandbox-only location.
- Record tester, sandbox project name, smoke task source, and panel version.
- If any unexpected behavior appears, disable the dev-only script and delete the sandbox project.

## 6. M8 Acceptance

M8 is ready only for limited sandbox operation testing if:

- A sandbox task can be opened.
- The panel appears in the sandbox context.
- The panel reports keypoint read status and keypoint count.
- The panel shows compatibility / residual / preview-only suggestion placeholder sections.
- The panel displays guardrails.
- No annotation is modified.
- No annotation is submitted.
- No official userscript, view config, `vis_3d.html`, or `ls_3d_logic.js` file is changed.
