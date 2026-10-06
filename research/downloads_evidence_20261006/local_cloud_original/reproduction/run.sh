#!/usr/bin/env bash
# Portable convenience wrapper; numerical implementation remains in SOURCE_ROOT.
set -euo pipefail
usage() {
  echo 'Usage: bash run.sh --source PACKAGE_ROOT --work NEW_WORK_DIRECTORY'
  echo 'Alternatively set SOURCE_ROOT (or ROOT) and WORK environment variables.'
  echo 'Use PYTHON to select an interpreter and PYTHONPATH for existing dependencies.'
}
SOURCE_ROOT=${SOURCE_ROOT:-${ROOT:-}}
WORK=${WORK:-}
PYTHON=${PYTHON:-python}
while (($#)); do
  case "$1" in
    --source) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; SOURCE_ROOT=$2; shift 2 ;;
    --work) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; WORK=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
if [[ -z "$SOURCE_ROOT" || -z "$WORK" ]]; then usage >&2; exit 2; fi
if [[ ! -f "$SOURCE_ROOT/reproduce.py" || ! -f "$SOURCE_ROOT/src/summarize.py" || ! -d "$SOURCE_ROOT/tests" ]]; then
  echo 'Source must be the extracted point_correspondence_20261006 package root' >&2; exit 2
fi
ROOT=$(cd "$SOURCE_ROOT" && pwd)
if [[ -e "$WORK/results" ]]; then echo 'Refusing existing results; pass a new work directory' >&2; exit 2; fi
mkdir -p "$WORK/logs"
WORK=$(cd "$WORK" && pwd)
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd "$WORK"
"$PYTHON" - <<'PY' > "$WORK/logs/environment.json"
import sys,platform,json,numpy,scipy,pytest,os
print(json.dumps(dict(python=sys.version,platform=platform.platform(),numpy=numpy.__version__,scipy=scipy.__version__,pytest=pytest.__version__,OPENBLAS_NUM_THREADS=os.environ['OPENBLAS_NUM_THREADS'],OMP_NUM_THREADS=os.environ['OMP_NUM_THREADS']),indent=2))
PY
{ time "$PYTHON" -m pytest -p no:cacheprovider "$ROOT/tests" -q; } 2>&1 | tee "$WORK/logs/pytest.log"
{ time "$PYTHON" "$ROOT/reproduce.py" --out "$WORK/results"; } > "$WORK/logs/reproduce.log" 2>&1
{ time "$PYTHON" "$ROOT/src/summarize.py" --root "$ROOT" --out "$WORK/results/summary"; } > "$WORK/logs/summarize.log" 2>&1
printf '\nALL_STAGES_COMPLETED\n'
