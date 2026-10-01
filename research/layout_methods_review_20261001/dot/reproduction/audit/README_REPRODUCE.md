# Reproduce this audit

This directory contains the audit code and evidence. `returned_package/` in the companion reproduction bundle is the original received package, preserved byte for byte. The audit writes only to a separate work directory and checks the original manifest again at the end.

Python 3.12 is recommended. Install the recorded dependencies into your own virtual environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r audit/requirements.lock.txt
bash audit/run_all.sh returned_package audit-work
```

Paths may be absolute or relative. If the original package is elsewhere, pass that directory as the first argument. The second argument is a disposable audit work directory; its `returned_copy/` subdirectory is cleared and recreated by `--rerun`. Do not point it at your source package. No internet access is needed once dependencies are installed.

The harness executes all six numerical/check/figure programs, compares every numeric/input output, independently verifies counts and sums, replays the seeded noise experiment again, probes error handling, and compares all figures. It does not run `build_bundle.py`: rebuilding HTML/archive is not needed to reproduce numerical/figure results and would rewrite the copied package manifest.

Generated evidence is in `audit-work/audit/`; rerun results are in `audit-work/returned_copy/`. `mismatches.csv` contains only its header when there are no mismatches. SVG normalization changes only the generation timestamp and consistently renamed internal IDs, not coordinates, paths, styles, or labels.

`REPRODUCTION_REVIEW_zh.md` explains the evidence and scope in Chinese. Passing these checks does not certify general algorithm correctness or replace the original repository validator.
