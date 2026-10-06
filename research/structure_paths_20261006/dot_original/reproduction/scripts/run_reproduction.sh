#!/usr/bin/env bash
# Portable runner: source package stays read-only; OUT must not exist.
set -uo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
SOURCE=${1:-"$HERE/../oct6-structure-intake/extracted/structure_paths_20261006"}
OUT=${2:-"$HERE/rerun_results"}
SOURCE=$(cd "$SOURCE" && pwd)
EVIDENCE=${3:-"${OUT}.audit"}
test -f "$HERE/scripts/check_results.py" && test -f "$HERE/scripts/check_invariants.py" || { echo 'Audit scripts missing'; exit 2; }
test ! -e "$OUT" || { echo 'OUT must not exist'; exit 2; }
test ! -e "$EVIDENCE" || { echo 'EVIDENCE must not exist'; exit 2; }
mkdir -p "$EVIDENCE/logs" "$EVIDENCE/checks"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export PYTHONPATH="$HERE/deps:$HERE/../audit-oct1-deps:$HERE/../audit-oct1-testdeps${PYTHONPATH:+:$PYTHONPATH}"
python "$HERE/scripts/source_snapshot.py" "$SOURCE" "$EVIDENCE/checks/source_before.json"
python - <<'PY' > "$EVIDENCE/checks/environment.json"
import json,sys,platform,importlib
d={'python':sys.version,'platform':platform.platform(),'modules':{}}
for name in ['numpy','scipy','shapely','numba','pytest']:
    try:
        m=importlib.import_module(name);d['modules'][name]={'version':m.__version__,'file':m.__file__}
    except Exception as e:d['modules'][name]={'error':repr(e)}
print(json.dumps(d,indent=2))
PY
printf 'stage\texit_code\tstart_utc\tend_utc\n' > "$EVIDENCE/checks/stage_status.tsv"
START=$(date -u +%FT%TZ)
python -m pytest "$SOURCE/tests" -q -p no:cacheprovider > "$EVIDENCE/logs/pytest.log" 2>&1
TEST_STATUS=$?
printf 'pytest\t%s\t%s\t%s\n' "$TEST_STATUS" "$START" "$(date -u +%FT%TZ)" >> "$EVIDENCE/checks/stage_status.tsv"
cat "$EVIDENCE/logs/pytest.log"
START=$(date -u +%FT%TZ)
python -u "$SOURCE/reproduce.py" --out "$OUT" > "$EVIDENCE/logs/reproduce.log" 2>&1
RUN_STATUS=$?
printf 'reproduce\t%s\t%s\t%s\n' "$RUN_STATUS" "$START" "$(date -u +%FT%TZ)" >> "$EVIDENCE/checks/stage_status.tsv"
tail -4 "$EVIDENCE/logs/reproduce.log"
python "$HERE/scripts/source_snapshot.py" "$SOURCE" "$EVIDENCE/checks/source_after.json"
cmp "$EVIDENCE/checks/source_before.json" "$EVIDENCE/checks/source_after.json"
SOURCE_STATUS=$?
printf 'source_unchanged\t%s\tNA\t%s\n' "$SOURCE_STATUS" "$(date -u +%FT%TZ)" >> "$EVIDENCE/checks/stage_status.tsv"
if [ "$RUN_STATUS" -eq 0 ]; then
  python "$HERE/scripts/check_results.py" "$SOURCE" "$OUT" "$EVIDENCE/checks" > "$EVIDENCE/logs/check_results.log" 2>&1
  CHECK_STATUS=$?
  printf 'check_results\t%s\tNA\t%s\n' "$CHECK_STATUS" "$(date -u +%FT%TZ)" >> "$EVIDENCE/checks/stage_status.tsv"
  cat "$EVIDENCE/logs/check_results.log"
  if [ "$CHECK_STATUS" -eq 0 ]; then
    python "$HERE/scripts/check_invariants.py" "$SOURCE" "$OUT" "$EVIDENCE/checks" > "$EVIDENCE/logs/check_invariants.log" 2>&1
    INVARIANT_STATUS=$?
    printf 'independent_invariant_checks\t%s\tNA\t%s\n' "$INVARIANT_STATUS" "$(date -u +%FT%TZ)" >> "$EVIDENCE/checks/stage_status.tsv"
    cat "$EVIDENCE/logs/check_invariants.log"
    if [ "$INVARIANT_STATUS" -ne 0 ]; then CHECK_STATUS=$INVARIANT_STATUS; fi
  fi
else
  CHECK_STATUS=99
  printf 'check_results\tNOT_RUN\tNA\tNA\n' >> "$EVIDENCE/checks/stage_status.tsv"
fi
if [ "$TEST_STATUS" -ne 0 ] || [ "$RUN_STATUS" -ne 0 ] || [ "$SOURCE_STATUS" -ne 0 ] || [ "$CHECK_STATUS" -ne 0 ]; then exit 1; fi
