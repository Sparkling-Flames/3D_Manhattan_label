# HoHoNet Foreign Annotator Package

This folder is the English HTTPS package for foreign annotators recruited for
Stage 1 / PreScreen.

Use this package only for workers who access Label Studio through:

```text
https://label.sparkle0825.top/
```

## Files

- `OPEN_SPEC_FOREIGN_HTTPS_P1.md`: implementation contract and boundaries.
- `ANNOTATOR_GUIDE_EN.md`: detailed worker-facing annotation guide.
- `INSTALL_USERSCRIPT_HTTPS_EN.md`: browser helper installation instructions.
- `CLOUDRESEARCH_CONNECT_SETUP_GUIDE.md`: CloudResearch setup notes.
- `ls_userscript_annotator_https_en.user.js`: HTTPS English helper userscript.
- `ls_userscript_annotator_https_en_debug.user.js`: HTTPS English helper with the
  debug panel enabled by default. Use it only for troubleshooting, and do not
  enable it at the same time as the normal English helper.

## What Workers Must Do

1. Use Chrome or Edge on a desktop or laptop.
2. Do not use incognito/private browsing mode.
3. Install the HTTPS English helper userscript.
4. Open only the Label Studio project/task assigned to them.
5. Confirm active-time logging works before annotation.
6. Submit only after completing the assigned Stage 1 project(s).

## Important Boundary

Label Studio Community Edition is not used as a permission system. The assigned
project link and external researcher manifest define what each worker should do.
If a worker can see unrelated projects, they must not open them.

The active Label Studio XML should remain based on the existing project
configuration. English guidance is added as extra text blocks in that XML; the
choice values, aliases, and hints should not be changed because they are part of
the export and analysis contract.
