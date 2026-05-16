# Manhattan LS Sandbox Readiness Spec v1

## 1. Current LS Operation Testing Decision

After M6, the Manhattan toolchain is ready only for offline sidecar, report, contact-sheet, and validation checks.

Actual Label Studio operation testing must not start in the current formal Manual or Semi-Auto worker-facing projects. The earliest allowed Label Studio operation test is after an M8 dev-only sandbox prototype exists.

Current allowed work:

- Run probe summaries from exported smoke data.
- Render Markdown reports and standalone HTML contact sheets.
- Validate probe summary JSON sidecars.
- Review outputs as experiment-outside / post-hoc evidence only.

Current forbidden work:

- No testing in current formal Manual or Semi-Auto worker-facing Label Studio projects.
- No production userscript edit.
- No current experiment UI deployment.
- No routing, formal `g_t`, or formal artifact integration.

## 2. Sandbox Principles

M8 and later Label Studio operation tests must use a separate Label Studio sandbox project.

Sandbox requirements:

- Use an independent Label Studio sandbox project.
- Use copies of the 2026-05-07 smoke tasks or a dedicated sandbox import.
- Do not use current formal experiment projects.
- Do not invite ordinary workers.
- Allow only developer / expert testers.
- Keep sandbox exports separate from formal `export_label/` data.
- Do not mix sandbox output into `P1/C1/C2/T1/V1` artifacts.
- Do not treat sandbox active_time or behavior as thesis experiment data.
- Do not use sandbox behavior to update admission, worker tier, routing, stop rules, or any formal protocol parameter.

## 3. M8 Dev-Only Prototype Boundary

The M8 prototype may be a developer-only browser helper, but it must remain separate from official Label Studio code.

Suggested path:

- `tools/dev_only/manhattan_ls_sandbox_panel.user.js`

Allowed behavior:

- Read current page keypoints.
- Display compatibility status.
- Display residual summary.
- Display preview-only suggestion type.
- Display guardrails.

Forbidden behavior:

- Do not automatically move points.
- Do not write back annotation data.
- Do not submit annotations.
- Do not change Label Studio config.
- Do not modify `tools/official/ls_userscript_annotator.js`.
- Do not modify `tools/label_studio_view_config.xml`.
- Do not modify `tools/vis_3d.html`.
- Do not modify `tools/ls_3d_logic.js`.
- Do not enter any current worker-facing experiment.

## 4. Hard Prohibitions

- No snap coordinates.
- No adjustment vector.
- No auto-correction.
- No worker-facing deployment.
- No routing.
- No formal `g_t`.
- No worker tier.
- No correctness label.
- No `P1/C1/C2/T1/V1` artifact.
- No writeback instruction.
- No corrected annotation payload.

## 5. Pre-Operation Checklist

All checklist items must be true before any Label Studio sandbox operation test:

- M6 validation output exists.
- M6 validation output has no errors.
- Sandbox project exists.
- Sandbox tasks are copied tasks or dedicated sandbox import tasks, not production tasks.
- Dev-only script path is separate from official userscript.
- Tester understands every output is preview-only.
- Sandbox export is kept separate from formal `export_label/` data.
- Rollback path exists: disable the dev-only script and delete the sandbox project if needed.
- No ordinary worker has access to the sandbox test.
- No project setting, import, export, or script from the formal experiment is modified.

## 6. M8 Acceptance Criteria

M8 can be considered ready for a limited sandbox operation test only if:

- One sandbox task can be opened.
- The panel reads keypoints from the current page.
- The panel reports compatibility status.
- The panel reports residual summary.
- The panel reports preview-only suggestion type.
- The panel displays guardrails.
- No annotation is modified.
- No network writeback occurs except normal Label Studio behavior.
- Official userscript is unchanged.
- Label Studio view config is unchanged.
- `vis_3d.html` and `ls_3d_logic.js` are unchanged.

## 7. Output Handling

Sandbox outputs, if produced later, must be labelled as sandbox-only.

They must not be used as:

- correctness labels;
- worker quality labels;
- routing input;
- formal `g_t`;
- `P1/C1/C2/T1/V1` artifacts;
- current worker-facing experiment material;
- thesis experiment active_time / behavior evidence.
