# Portable reproduction

Extract this bundle and work in its root. Python 3.12 is recommended; the recorded run used 3.12.14. The original source tree is preserved under `lee-audit-original/`.

Create two independent virtual environments if both stacks are needed. The following old-stack command recreates the numerical dependency versions used for the reproduced 97 warnings, not the original Windows system:

```bash
python3.12 -m venv .venv-old
.venv-old/bin/python -m pip install numpy==1.26.4 shapely==2.0.4 scipy==1.17.0 pandas==2.2.3 matplotlib==3.10.8 pytest==9.1.1
python3.12 -m venv .venv-new
.venv-new/bin/python -m pip install numpy==2.3.5 shapely==2.1.2 scipy==1.17.0 pandas==2.2.3 matplotlib==3.10.8 pytest==9.1.1
```

On Windows use each environment's `Scripts/python.exe` instead of `bin/python`.

Verify immutable files before execution:

```bash
python lee-audit-helper/verify_source_hashes.py
```

Run unchanged upstream tests and program from the source root, with the selected environment's absolute Python path:

```bash
cd lee-audit-original
../.venv-old/bin/python -B -m pytest tests/test_lee_tile_stage1_20261002.py tests/test_supervisor_gt_sensitivity_20260922.py tests/test_consensus_contract_20260923.py -q -p no:cacheprovider
../.venv-old/bin/python -B -m tools.thesis_main.analysis.lee_tile_stage1_20261002 --out ../lee-audit-recomputed-old
../.venv-new/bin/python -B -m tools.thesis_main.analysis.lee_tile_stage1_20261002 --out ../lee-audit-recomputed
cd ..
python lee-audit-helper/compare_audit.py
.venv-old/bin/python -B lee-audit-helper/isolate_warnings.py
.venv-new/bin/python -B lee-audit-helper/check_warning_overlays.py
```

In a restricted environment set MPLCONFIGDIR and XDG_CACHE_HOME to writable temporary folders before plotting. Such font/cache warnings are distinct from the 97 numerical RuntimeWarnings.

`compare_audit.py` also checks the bound quality snapshot and returned independent excerpt included in their original relative paths. It does not access the network. `isolate_warnings.py` wraps unchanged upstream functions to retain WKB operands, re-emits warnings to the original collector, and suppresses only repeated plotting/report output. `check_warning_overlays.py` uses independent coverage-count layers without coordinate snapping or geometry repair.

The supplied result files were produced before packaging, with exact environments recorded in JSON. New operating systems/platform libraries may have roundoff differences; do not overwrite the evidence bundle if you need to retain those files. Copy the bundle before a fresh run.
