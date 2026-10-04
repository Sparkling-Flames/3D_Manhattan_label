#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:?Usage: bash reproduce.sh /absolute/path/to/NEW_output}"
if [[ -e "$OUT" ]]; then echo 'Choose a NEW output directory' >&2; exit 2; fi
mkdir -p "$OUT/audit"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONUTF8=1
python -m unittest discover -s "$ROOT/author_bundle/tests" -v > "$OUT/audit/author_tests.txt" 2>&1
python "$ROOT/author_bundle/run_all.py" --out "$OUT/replay" > "$OUT/audit/replay_stdout.txt" 2>&1
python "$ROOT/audit/audit_personnel.py" --bundle "$ROOT/author_bundle" --archive "$ROOT/archive" --replay "$OUT/replay" --out "$OUT/audit/results" > "$OUT/audit/audit_stdout.txt" 2>&1
python "$ROOT/audit/resolve_overlay.py" --bundle "$ROOT/author_bundle" --out "$OUT/audit" > "$OUT/audit/overlay_stdout.txt" 2>&1
# The frozen old-GEOS result is bundled. Recheck that fixture in a separate NumPy1/Shapely2.0.4
# environment if desired; this script deliberately never reinstalls your dependencies.
python "$ROOT/audit/finalize_audit.py" --bundle "$ROOT/author_bundle" --evidence "$OUT/audit" --old-evidence "$ROOT/audit/overlay-old-geos/overlay_resolution.json"
