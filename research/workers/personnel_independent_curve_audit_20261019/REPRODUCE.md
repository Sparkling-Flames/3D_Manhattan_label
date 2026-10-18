# Portable reproduction

Use Python 3.12 and POSIX/Linux/WSL (`fcntl` is required). The original numerical environment versions are in tools/thesis_main/analysis/personnel_independent_curve_audit_20261019/requirements-frozen.txt; independent execution versions are in models/AUDIT_MANIFEST.json. Install these into your own virtual environment. No package install or full rerun was performed as part of archive packaging.

1. Retrieve the four Library files identified in ORIGINAL_INPUTS.json. These are private account identities, not public download links. Obtain authorized access from the owner if needed. Independently compare each file's SHA-256 and byte size against that JSON. Extract all four into a new `INPUT_ROOT/extracted/`; they collectively provide `repo_main_20261019` and `work_v2_20261019`. Run the original `work_v2_20261019/REPRODUCE.py --stage verify --full-hash` from `INPUT_ROOT/extracted` before executing research code. The frozen Git commit is a second provenance anchor, not a replacement for the four research-output packages.
2. From the repository root, run:

```sh
python tools/thesis_main/analysis/personnel_independent_curve_audit_20261019/prepare_reproduction.py INPUT_ROOT --evidence research/workers/personnel_independent_curve_audit_20261019
cd INPUT_ROOT
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python independent/verify_source.py
python independent/check_source_evidence.py
python independent/models/independent_model_audit.py
python independent/models/check_time_nested.py
python independent/geometry/run_geometry_replay.py
for s in audit_ledgers replay_registration audit_label_adjustment replay_saved_teams explain_state_roundoff replay_pair_metrics; do python independent/fusion/$s.py; done
```

The launcher creates a new `independent/` and refuses to overwrite one. It copies archived scripts, replacing only the former absolute workspace root in the copies. Frozen input files are not edited. Source metadata copied for verification are archived official responses; the supplied source check rehashes against those responses rather than silently claiming a fresh network query.

3. Reproduce the actual selected model replay (can take substantial time):

```sh
P=extracted/work_v2_20261019/profiles
O=independent/models/replay
python "$P/run_profiles.py" --repo extracted/repo_main_20261019 --out "$O" --skip-v1-validation
for s in augment_type_fines build_nested_features; do python "$P/$s.py" --out "$O"; done
python "$P/audit_profiles.py" --repo extracted/repo_main_20261019 --out "$O"
python "$P/diagnose_class_information.py" --out "$O"
python independent/models/compare_replay.py
```

4. Fresh strict nested curves: the launcher supplies the exact archived DESIGN and REGISTRATION, but deliberately supplies no cached pool states. Run `python independent/curves/study.py run`, then `python independent/curves/supplement.py` and `python independent/models/review_curve_design.py`. All 3,132 selected requests should execute in the new root. Do not unzip raw_curve_pools.zip into this fresh run: the engine may reuse cached teams. For audit-only inspection, extract that ZIP elsewhere. To regenerate selection separately, use `study.py register` in a separate copy, compare DESIGN hashes, and note that new registration timestamps change its receipt hash.

Compare newly produced numerical JSON/CSV against the archived proofs with stated tolerances, not all byte hashes: timestamps, runtime receipts, and gzip metadata can differ. Run logs and large duplicate model tables are omitted; receipts and independent predictions preserve the audit's evidence. The package manifest verifies archived bytes only; it is not a fresh numerical execution claim.
