#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
if [ $# -lt 1 ]; then echo "Usage: $0 RETURNED_PACKAGE_DIRECTORY [AUDIT_WORK_DIRECTORY]" >&2; exit 2; fi
SOURCE=$(cd "$1" && pwd)
WORK=${2:-"$SCRIPT_DIR/.."}
mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)
PYTHON=${PYTHON:-python}
"$PYTHON" "$SCRIPT_DIR/reproduce_audit.py" --source "$SOURCE" --work "$WORK" --rerun
"$PYTHON" "$SCRIPT_DIR/error_matrix.py" --work "$WORK"
"$PYTHON" "$SCRIPT_DIR/compare_figures.py" --source "$SOURCE" --work "$WORK"
