# HoHoNet Foreign Recruitment Notes

This folder contains recruitment, installation, and private deployment notes
for foreign annotators. It is not the runtime home of Label Studio assets.

## Runtime assets

The active English Label Studio XML files and HTTPS userscripts are maintained
under:

```text
tools/label_studio/localized/en/
```

Use the normal userscript for annotation. The debug userscript is only for
troubleshooting and must not run at the same time as the normal userscript.

## Recruitment documents

Historical P1/PreScreen guides remain under `legacy/`. `Private Setup Note.md`
remains private operational documentation and must not be copied into shared
runtime directories.

## Operation boundary

Label Studio Community Edition is not a permission or distribution system.
The external assignment manifest and researcher-issued project/task list remain
authoritative. Scope choice aliases are stable export identifiers; localized
worker-facing text may change only through a versioned XML freeze.
