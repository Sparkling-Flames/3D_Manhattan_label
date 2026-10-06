# Independent reproduction audit

Read `VERDICT_ZH.md` for the verdict and scope. The original source package was not edited.

## Reproduce

Use Python with NumPy >=1.24, SciPy >=1.10, Shapely >=2.0, Numba >=0.59 and pytest >=7.
The checked environment is recorded in `checks/environment.json` (Python3.12.14; NumPy2.3.5; SciPy1.17.0; Shapely2.1.2; Numba0.65.1; pytest9.1.1).

```bash
bash scripts/run_reproduction.sh /absolute/path/to/structure_paths_20261006 /absolute/path/to/NEW_results /absolute/path/to/NEW_evidence
```

Both output paths must not exist. The third argument is optional and defaults to `NEW_results.audit`. Inputs remain in the supplied original package; no duplicate source data is needed. The runner looks for optional dependency folders beside this audit, but normally installed dependencies work too. It disables Python bytecode writes and pytest's cache.

The scripts independently verify full-roster counts, candidate sets, membership/vote invariants, all raw source points and path order, candidate construction, and metadata hashes. They do not provide missing local data or semantic truth.

Published-vs-rerun byte equality is checked separately from numeric/content equality. The known cross-filesystem JSON key-order difference is documented rather than silently normalized. Final packaging should omit `deps/` and the duplicate `replay_results/`; logs and the replay comparison retain the verification evidence.
