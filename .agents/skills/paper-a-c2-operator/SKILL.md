---
name: paper-a-c2-operator
description: Audit and operate the HOHONET Paper A C2 workflow, including closed C2-B evidence, C2-A-RP block re-estimation, active-time freezing, GT/scope review, Label Studio import/runtime binding, worker-facing task sheets, and go/no-go decisions. Use for requests mentioning C2-B, C2-A-RP, active time, GT or scope conflicts, the next C2 block, LS import packages, runtime mapping, Project letters, 任务编号, or worker task distribution. Do not use for P1, C1, T1, V1, Paper B, or generic spreadsheet work.
---

# Paper A C2 Operator

Operate Paper A C2 from repository truth without reopening closed stages or inventing deployment state.

## Establish authority and state

1. Run `git status --short` before any task action. Preserve unrelated dirty-worktree changes.
2. Read completely:
   - `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
   - `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md`
   - `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md`
   - `docs/agent/playbooks/protocol_guard.md`
   - `docs/agent/playbooks/statistical_plan_guard.md`
3. Also read `docs/agent/playbooks/label_studio_ce_guard.md` before changing LS imports, runtime binding, distribution, visibility, permissions, GT isolation, or worker-facing files.
4. Determine which stages and blocks are actually closed from frozen closeout/re-estimate artifacts and runtime exports. Treat user statements as context, then verify them against repository evidence.
5. State the current closed stage and the next permitted action before mutating files.

Default to audit-only. Read, test, compare, and report without changing files unless the user explicitly asks to generate, fix, build, update, or proceed. Never import into Label Studio, bind live runtime IDs, message workers, or dispatch tasks without separate explicit authorization.

## Use repository truth

Apply this precedence:

1. `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`: normative method.
2. `export_label/`: Label Studio runtime annotation exports.
3. `active_logs/`: raw active-time logs.
4. `import_json/`: planned imports and splits.
5. Frozen assignment, deployment, registry, and closeout inputs named by the current method chain.
6. `analysis_results/`: generated evidence and audit outputs only; do not silently promote an analysis output into a new input source.

Reject silent schema drift, missing identity fields, stale SHA bindings, and active-time source mismatches. Reuse existing tools under `tools/thesis_main/analysis/`; do not duplicate their statistical logic inside this skill or an ad hoc script.

## Follow the C2 decision workflow

For C2-B review:

- Preserve C2-B as closed once frozen. Use its historical-evidence acceptance artifact when the current contract authorizes later consumption.
- Separate a real implementation/data inconsistency from a request to rerun a closed stage. Fix the shared consumer or provenance guard when necessary; do not rewrite historical outcomes merely to make later results cleaner.
- Treat worker consensus as review triage, not automatic GT or scope truth.
- Treat reference normalization as parseability only. Local GT topology or corner errors can remain even when normalization passes.

For each C2-A-RP block:

1. Confirm the preceding block is closed and its actual submissions are present.
2. Freeze the relevant dated active-time files into a dedicated block folder and audit missing, duplicated, mismatched, or implausible sessions.
3. Resolve planned task, runtime task, worker, project, export, and assignment identities. Do not guess missing runtime IDs.
4. Rebuild eligible risk evidence and run the existing block re-estimate/materializer.
5. Decide whether the precision rule requires another block. Do not modify frozen thresholds to improve significance.
6. Generate the next import/distribution package only when another block is required.
7. Leave the package un-dispatched until manual LS import and runtime binding are complete.

Do not preassign future blocks. Keep each assigned block paired as one ordinary plus one stress task, enforce the contract support cap, and preserve assignment SHA/pairings whenever the requested change is presentation- or deployment-only.

## Guard Label Studio deployment

- Never infer a new LS numeric project ID, Project letter, or Chinese `任务N` label from the previous block.
- If the next round needs newly imported images and its LS projects do not yet exist, preserve the canonical artifact field `project_binding_status=pending_post_import` and report the user-facing state as `pending_new_project_binding`; do not invent a new artifact enum or point the package at an old project.
- Bind deployment labels only from the user's confirmed projects or verifiable LS/repository state.
- Generate display task codes from the current import order within the newly bound project, starting at `001`. Do not expose raw task IDs to workers.
- For example, after the user confirms `Project F` and `任务6`, generate `Project F-001...` and `任务6-001...`; never derive those labels merely because the prior projects were `Project E` and `任务5`.
- Keep import JSON under `import_json/` and preserve the same LS import shape and instruction version required by the current C2-A-RP contract.
- After import, require every worker-task row to have the correct runtime task ID before distribution. Shared tasks may reuse a runtime task ID, but worker-task identity must remain explicit.

## Build worker-facing task sheets

Reuse the immediately preceding block's workbook as the template. Preserve:

- one instruction sheet;
- one private sheet per worker;
- Chinese worker names and English worker IDs;
- `order` and `task_code` columns;
- the established formatting and sheet order.

Replace only the current task codes and round wording. Verify every personal sheet against the frozen assignment and current import order. Reopen the exported `.xlsx`, scan for formula errors, and visually render at least the instruction sheet and one personal sheet per language.

Keep Upwork or worker communication text outside the workbook unless the user explicitly asks to embed it. Do not tell workers about the paper, internal precision logic, worker profiles, availability-based routing, or experimental results.

## Validate and report

For audit-only work, confirm that `git diff` did not change because of the audit.

For generated or repaired work, verify at minimum:

- assignment count and worker roster;
- exactly one ordinary and one stress task per assigned worker;
- no forbidden historical reuse and no excluded GT/scope task;
- support cap and sequential block index;
- method/design/input/output SHA bindings;
- runtime mapping status;
- import JSON shape and destination binding;
- worker-facing workbook mapping and openability;
- relevant targeted pytest tests and `git diff --check`.

Lead the handoff with one of:

- `GO`: safe for the next named manual action;
- `NO-GO`: list only genuine blockers;
- `PENDING PROJECT BINDING`: new LS projects/labels are required;
- `AUDIT COMPLETE`: no mutation was requested.

Then report what changed, what remained frozen, verification results, active-time status, runtime-binding status, and the single next safe action. Do not call a package dispatched until the user has actually imported and assigned it.
