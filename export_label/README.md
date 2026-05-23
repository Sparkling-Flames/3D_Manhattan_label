Ground Truth个别task有两个版本的export label,一般是一个原作者的标注,一个是我修改后的标注.出现这种情况一般是:
1.我修改标注后,也没有觉得特别好,但是原作者标的也不好的情况
2.原作者是标了一种情况(一般是extended),但是我又标了enclosed的,两者呈现的效果都很好

# `export_label/` README

This directory stores Label Studio export JSON snapshots.

## What stays at the root

Only keep the small set of exports that still have a live role in the current repo:

- `人工精标/`
  - Verified `project-20` exports.
  - Keep all current snapshots here because tests and truth-layer/final-gold provenance still reference multiple versions.
  - The current authoritative verified snapshot is:
    - `人工精标/project-20-at-2026-03-27-14-57-e66c6481.json`

- `project-2-at-2026-02-22-11-22-ee6c4607.json`
  - Legacy-server compatibility / pilot audit reference.
  - Still referenced by older analysis manifests, docs, and helper scripts.

- `project-2-at-2026-03-25-10-52-c04c6496.json`
  - Current project-2 comparison export used by overlap / side-analysis utilities.

- `project-11-at-2026-03-07-17-05-1b4f93f3.json`
  - New-server single-image semi smoke export.

- `project-12-at-2026-03-07-17-05-72d96094.json`
  - New-server single-image manual smoke export.

## What belongs in `legacy/`

Archive exports that are clearly outdated, ad-hoc, or superseded:

- older project-2 snapshots before `2026-02-22`
- ad-hoc files such as `test1.json`

These files remain useful for historical audit, but they should not clutter the root or be mistaken for current working inputs.

## Directory contract

1. `export_label/` is the runtime export source directory, not the planned import source.
2. Root-level files should be a curated working set, not a dump of every historical export.
3. `legacy/` is archival only and should not be treated as a default input location.
4. If a script truly depends on an archived export, either restore that file to root or update the script/document explicitly instead of relying on memory.
