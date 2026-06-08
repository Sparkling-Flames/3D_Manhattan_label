# CloudResearch Connect Setup Guide For HoHoNet P1

## 1. Recommended Setup

Use a normal CloudResearch Connect project for Stage 1 / P1 screening.

Do not use Connect Waves as the mechanism for selecting only P1 passers into
later rounds. The official Waves feature invites participants who completed
previous waves in the series, and the current Waves workflow does not support
pasting a subset of previous participant IDs for a later wave.

For follow-up sessions, create separate Connect projects and use Included
Participants / Connect IDs to target only the participants who passed P1.

## 2. P1 Project

Internal project name:

```text
3D Indoor Layout Annotation - Screening
```

Short description:

```text
Annotate indoor panoramic images using a web-based annotation tool. No prior experience required. A step-by-step guide and helper script are provided.
```

Participant instructions:

```text
This is the screening stage of a multi-session annotation project.

If your annotations are complete and pass our quality checks, you may be invited to follow-up annotation sessions with additional payment.

Requirements:
1. Use Chrome or Edge on a desktop/laptop.
2. Do not use incognito/private mode.
3. Install the provided Tampermonkey helper script.
4. Use only the project/task assigned to you.
5. Do not open unrelated Label Studio projects or tasks, because we record active annotation time.
6. Before starting, confirm that active-time logging is working.
7. Return to CloudResearch and submit the completion code after finishing.

Completion code:
ANNOTATION_P1_DONE

If you have questions, contact the researcher through CloudResearch.
```

## 3. Device And Content Settings

Use desktop/laptop only.

Do not allow mobile devices.

If asked whether the project collects personally identifiable information, use
your approved ethics / platform policy. The HoHoNet annotation system itself
uses platform IDs for study reconciliation rather than asking workers to enter
personal identifying information.

## 4. Project URL

Use HTTPS without `:8080`:

```text
https://label.sparkle0825.top/?participantId=<CONNECT_PARTICIPANT_ID>
```

If the CloudResearch UI provides an "Insert URL Variable" button, use the
official inserted variable for `participantId` rather than manually guessing a
template string.

Optional fields can also be passed if CloudResearch exposes them:

```text
https://label.sparkle0825.top/?participantId=<CONNECT_PARTICIPANT_ID>&assignmentId=<ASSIGNMENT_ID>&projectId=<PROJECT_ID>
```

The HoHoNet HTTPS helper script accepts several worker-id aliases for
compatibility, but `participantId` is the preferred Connect ID field.

## 5. Payment And Review

P1 is a real screening annotation task, not only a two-task practice task.

Approve and pay participants who completed the assigned work with reasonable
effort. Do not reject a participant solely because of a researcher-side link,
script, or completion-code problem.

Use rejection only for confirmed data quality failures such as clearly
nonsensical work or clear non-attempt.

Set a review reminder. Connect submissions can be auto-approved after the
platform's review window if left pending.

## 6. Follow-Up Projects

After P1:

1. Export Label Studio annotations and active logs.
2. Build the P1 pass list.
3. Map passers to Connect participant IDs.
4. Create a new Connect follow-up project.
5. Use Included Participants / Connect IDs to target the passers.
6. Use a new HTTPS Label Studio link for that round.

CloudResearch is the recruitment and payment layer. The thesis-facing protocol
boundaries remain defined by the repository round-based protocol and assignment
manifests.
