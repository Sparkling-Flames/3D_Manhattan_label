# Pro v2 portable replay audit

## Recommended layout

`research/workers/pro_personnel_v2_archive_20261019/` contains the bootstrap, retained `work_v2_20261019/` tree, compact storage manifest, frozen-source manifest, and a complete archive-member disposition map. Original research scripts remain byte-identical. The bootstrap expands compressed/split storage into a new writable workspace with sibling `work_v2_20261019/` and `repo_main_20261019/` directories; this layout is required by multiple original scripts.

Pinned source: `82c6164b0d4630de5316199c92aa405930973168`. All 824 delivered source-snapshot files are already present byte-identically on the repository main checked by the inventory task. The bootstrap first reuses matching clone bytes, then falls back to `git show` at the pinned commit. It never silently accepts a changed current source file. A shallow clone missing both matching current bytes and the pinned object must fetch the pinned commit.

## Essential retained inputs

- All 62 original Python files, original requirements, registrations, amendment records, seeds, source/measurement hash manifests.
- `fusion/INPUT_SNAPSHOT.json.gz`, exact `REQUESTS_INITIAL.json.gz` and `REQUESTS_EXTENSION.json.gz`, all profile/fold and selection registrations. Do not replace exact saved requests with a seed-only description.
- `fusion/V1_PARITY_INPUT_FIXTURE.json.gz`: replay's cross-version check needs this fixture when original v1 working directories are absent.
- Existing exclusion comments, evidence joins and explicit ambiguity decisions; these are documentary inputs, not newly adjudicated labels.
- Exact profiles, compact aggregate tables, reports and source/receipt indexes, including source-license files.
- Original Noto font and its OFL license: `make_figures.py` loads this exact local path unconditionally. It is compressed and may be split in storage, then restored exactly; a generic system font is not an equivalent replay dependency.

## Geometry-cache interpretation

Static code audit: `fusion_engine.run_pool` computes each state as `compact(fuse(selected, gap=WORKING_GAP)['automatic'])`, where selected members come from frozen input records sorted by worker ID. There is no manual annotation read or editing step in state generation. The exact union of initial requests (77,942) and extension requests (89,639) equals all 167,581 recorded requests, including full request values. Therefore no extra request families occur only in pool caches.

The 229 saved state files are unique historical computational outputs. Their scientific values have a documented regeneration route, but they are NOT byte-identical duplicates of the input records. Keep their original archive names, member paths and SHA256s in the complete archive map. Runtime receipts/timings cannot be reproduced byte-for-byte, and floating-point/platform differences may affect newly generated values. Full native regeneration of all 144,253 unique teams has not been run in this curation task.

Do not hydrate pool `context.json` when states, request_results and requests were omitted: original code interprets a context file as an existing complete cache and unconditionally opens those three files. Pool run receipts belong in provenance-only storage if the full caches are omitted.

## Verification and limitations

Completed: new isolated workspace hydration; SHA256 checks of all 824 sources and 519 retained logical files; original forward-profile `--verify-inputs-only` smoke check; original all-stage command-plan generation. Fresh native smoke also recomputed nine complete compact geometry states across ordinary-manual, doorway-manual and ordinary-semi pools at k=4, 8 and 16. All nine matched saved states exactly: zero structural mismatches and zero numeric difference. This limited check is not a full statistical fit or replay of all 144,253 teams. The final 519-file core includes split-gzip font storage and split-identity validation-prediction storage, both reconstructed and hash-verified.

The curated bootstrap intentionally does not call original `REPRODUCE.py --stage verify --full-hash`: that command validates the complete original four-ZIP payload, including intentionally omitted derived caches. The original manifest remains unchanged as provenance. A fresh scientific replay records its own new receipts rather than claiming original full-payload byte identity.

One-command numerical/full replay after cloning, with Git, Python and network access to install pinned public packages:

`python research/workers/pro_personnel_v2_archive_20261019/bootstrap.py --workspace /tmp/pro-v2-replay --install-deps --stage all --execute`

The workspace must not exist. To verify retained data and frozen input hashes without model fitting, use `--smoke` and omit `--execute`; omit `--install-deps` if only verifying.

The original full replay is computationally substantial. Image acquisition is separate and optional: viewer regeneration may require `--fetch-originals` and available source Releases. Saved reports remain readable without fetching images. Recreating collection/export history is not claimed.
