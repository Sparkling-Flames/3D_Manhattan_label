#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="${1:?Usage: run_replay.sh /path/to/extracted-handoff [/path/to/output]}"
OUT="${2:-$HERE/fresh-run}"
mkdir -p "$OUT/mplconfig"
export PYTHONDONTWRITEBYTECODE=1
export MPLCONFIGDIR="$OUT/mplconfig"
export NUMBA_CACHE_DIR="$OUT/numba_cache"
python -B "$HERE/reproduce.py" --source "$SOURCE" --out "$OUT"

python -B "$HERE/build_report.py" --out "$OUT"
