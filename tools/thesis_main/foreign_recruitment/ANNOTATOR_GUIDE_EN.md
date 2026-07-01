# Stage 1 Annotation Guide

## 1. Before You Start

Use a desktop or laptop with Chrome or Edge. Do not use incognito/private mode.

Install the helper script from `INSTALL_USERSCRIPT_HTTPS_EN.md` before starting
real annotation.

Open only the project or task assigned to you. Do not browse other Label Studio
projects or tasks. We record active annotation time, and opening unrelated
projects can contaminate the timing data.

Before each annotation session, confirm that active-time logging is working.
If the helper script shows an error or the researcher tells you logging is not
working, stop and contact the researcher through CloudResearch.

## 2. Platform Link

Use the HTTPS link provided by the researcher, usually in this form:

```text
https://label.sparkle0825.top/?participantId=YOUR_CONNECT_ID
https://label.sparkle0825.top
```

## 3. What You Are Annotating

You will annotate indoor panoramic images. The goal is to mark the visible room
layout as carefully as possible.

Depending on the assigned project, you may see:

- `P1_manual`: draw the layout from scratch.
- `P1_semi`: review and correct an initial layout proposal.
- `P1_oos`: judge whether the scene is in scope, while still completing the
  required fields in Label Studio.

important:When you move the mouse over the options of the element tag, there will be a hint for each option.

## 4. Scope

You must answer the scope question even when the scene looks unusual.

Use `in_scope` when the image is a valid indoor room layout target.

Use `out_of_scope` when the scene is not a valid indoor room layout target, for
example when the main room boundary cannot reasonably be annotated.

Important: the current Label Studio form may still require geometry fields even
for out-of-scope cases. If so, complete the required fields as instructed and
use the scope answer to mark the case.

## 5. Difficulty And Model-Issue Labels

These labels are used for later audit. Choose the labels that best describe the
image or proposal.

Examples:

- `trivial`: very easy scene.
- `occlusion`: important walls or corners are blocked by objects.
- `glass`: glass or mirrors make the boundary ambiguous.
- `weak_texture`: walls are plain or low texture.
- `stitching_or_stretch`: panorama stitching or distortion affects judgment.
- `acceptable`: the proposal is mostly reasonable.
- `overextend`: the proposal extends into a neighboring area.
- `underextend`: the proposal misses part of the room.
- `corner_drift`: corners are shifted from the correct positions.
- `corner_duplicate`: duplicated or redundant corners.

If multiple issues apply, choose all relevant labels if the interface allows it.

## 6. Manual Annotation

For manual tasks, draw the room layout based on the image. Focus on the main
room boundary, not furniture.

Mark corners consistently and avoid adding unnecessary duplicate corners.

If a doorway or connected room is visible, annotate the main room according to
the instructions and do not extend into unrelated neighboring space unless that
space clearly belongs to the same room boundary.

## 7. Semi-Automatic Annotation

For semi-automatic tasks, start from the proposal shown in Label Studio.

Correct real errors, but do not over-edit a proposal that is already reasonable.

The task is not to redraw everything from scratch unless the proposal is clearly
wrong.

## 8. Active-Time And Data Quality

We collect active annotation time to evaluate annotation workflow efficiency.

Do:

- Work normally and carefully.
- Keep the assigned task page open while annotating.
- Stop if the helper script or logging check fails.

Do not:

- Open unrelated projects or tasks.
- Leave tasks open while doing unrelated work.
- Use another browser profile or private browsing session after setup.
- Disable the helper script during annotation.

## 9. Completion Code

After finishing the assigned project, return to CloudResearch and submit the
completion code provided by the researcher.

If you cannot find the code, contact the researcher instead of guessing.
