# OpenSpec: Foreign HTTPS P1 Annotation Package

## 1. Purpose

This package provides an isolated HTTPS + English onboarding path for foreign
participants recruited through CloudResearch Connect.

It supports the current `P1 / PreScreen` collection without changing the
existing Chinese annotator path, HTTP path, Label Studio XML, Nginx, Docker, or
frozen Stage 1 import JSON files.

## 2. In Scope

- English worker-facing instructions for Stage 1 prescreen annotation.
- Extra English instruction text in the existing Label Studio XML, without changing choice values, aliases, or hints.
- HTTPS-only helper userscript for `https://label.sparkle0825.top/*`.
- HTTPS-only debug helper userscript for troubleshooting the same path.
- Optional CloudResearch identifier capture from URL query parameters.
- Active-time payload enrichment with optional external recruitment IDs.
- CloudResearch setup notes aligned with the official Connect documentation.

## 3. Out of Scope

- No changes to current Chinese annotator documentation.
- No changes to `tools/label_studio/official/ls_userscript_annotator.js`.
- No changes to `import_json/stage1_prescreen_final_20260325/*`.
- No replacement Label Studio XML for a separate foreign-only project.
- No change to existing `Choice value`, `alias`, or `hint` semantics.
- No Nginx, Docker, or Label Studio server changes.
- No per-worker tab switching or task hiding in Label Studio CE.
- No protocol-stage change to `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`.

## 4. Entry URL Contract

The worker-facing HTTPS entry is:

```text
https://label.sparkle0825.top/
```

CloudResearch links should append at least one participant identifier:

```text
https://label.sparkle0825.top/?participantId=<CONNECT_PARTICIPANT_ID>
```

The userscript accepts these aliases:

- `participantId`
- `workerId`
- `worker_id`
- `hohonet_worker_id`
- `wid`

Optional aliases:

- `assignmentId`
- `projectId`

The active-time logging token is not part of the URL contract. Label Studio
navigation can drop URL query parameters after a worker enters a project, so
workers must set `HOHONET_LOG_TOKEN` in browser `localStorage` once before
annotation.

## 5. Active-Time Metadata Contract

The existing Label Studio-derived identifiers remain primary:

- `task_id`
- `project_id`
- `project_name`
- `annotator_id`
- `session_id`

The foreign HTTPS userscript may add optional recruitment metadata:

- `external_worker_id`
- `connect_participant_id`
- `connect_assignment_id`
- `connect_project_id`

These fields are audit and reconciliation aids only. They do not replace Label
Studio user IDs and do not alter the `active_time` primary estimand.

## 6. CloudResearch Contract

Use a normal P1 screening project for recruitment. Do not use CloudResearch
Waves as the mechanism for selecting only P1 passers into C1/C2, because Waves
invite all participants who completed prior waves in the series.

For follow-up rounds, create separate Connect projects and use Included
Participants / Connect IDs for the subset that passed P1.

## 7. Acceptance Criteria

- Foreign userscript matches only `https://label.sparkle0825.top/*`.
- Foreign userscript defaults helper/viewer/log endpoints to `window.location.origin`.
- Foreign userscript captures CloudResearch IDs when present in URL parameters.
- Foreign userscript reads `HOHONET_LOG_TOKEN` only from browser `localStorage`.
- Foreign userscript enriches `/log_time` POST bodies without modifying current Chinese script.
- Debug foreign userscript uses the same logic as the normal foreign userscript
  but enables the debug panel by default; workers must not enable both scripts
  at the same time.
- English documents warn workers not to open unrelated projects or tasks.
- English documents require checking active-time logging before annotation.
- Current Stage 1 import JSON files remain unchanged.
- Existing Label Studio XML keeps the same choice values, aliases, and hints;
  English text is added only as explanatory `Text` blocks.
