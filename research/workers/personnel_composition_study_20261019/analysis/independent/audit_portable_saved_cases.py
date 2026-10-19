#!/usr/bin/env python3
"""Run the portable replay while actively blocking full-input/result-cache reads.

Pass replay_saved_cases.py arguments after `--`. The guard is local to this
short-lived audit process and never renames or modifies the shared inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "analysis/composition/replay_saved_cases.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=ROOT / "analysis/independent/PORTABLE_REPLAY_READ_AUDIT.json")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    if not argv:
        raise ValueError("Provide explicit saved-case replay arguments after --")
    blocked = []
    opens = set()
    forbidden_basenames = {"INPUT_SNAPSHOT.json.gz", "records.json.gz", "states.json.gz", "scores.json.gz", "request_results.json.gz", "team_results.csv"}

    def read_guard(event, values):
        if event != "open" or not values or not isinstance(values[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(values[0])).absolute()
        mode = values[1] if len(values) > 1 else None
        flags = values[2] if len(values) > 2 and isinstance(values[2], int) else 0
        writing_only = isinstance(mode, str) and not ("r" in mode or "+" in mode) and any(x in mode for x in ("w", "a", "x"))
        if writing_only or (mode is None and flags & os.O_WRONLY):
            return
        opens.add(str(path))
        parts = path.parts
        from_run_cache = any(p.startswith("runs") for p in parts) and "pools" in parts
        forbidden = path.name in forbidden_basenames or path.name.endswith("REQUESTS.json.gz") or from_run_cache
        if forbidden:
            blocked.append(str(path))
            raise PermissionError("Portable replay audit forbids full inventory/request/result-cache reads: " + str(path))

    sys.addaudithook(read_guard)
    sys.path.insert(0, str(SCRIPT.parent))
    sys.argv = [str(SCRIPT), *argv]
    started, error = time.monotonic(), None
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except BaseException as exc:
        error = type(exc).__name__ + ": " + str(exc)
    result = {
        "schema": "portable_saved_case_no_full_input_dependency_audit_v1",
        "script": str(SCRIPT), "script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        "guard_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "arguments": argv,
        "forbidden_full_input_and_result_read_attempts": blocked,
        "observed_read_path_n": len(opens), "full_snapshot_or_cached_fusion_read": bool(blocked),
        "replay_succeeded": error is None, "all_passed": error is None and not blocked,
        "elapsed_seconds": time.monotonic() - started, "error": error,
        "guard_scope": "Python open audit events: frozen full snapshot/evidence records, request manifests, old full states/scores/request-results and runs*/pools result caches are forbidden; source code and pinned measurement-engine assets remain allowed.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not result["all_passed"]:
        raise SystemExit("Portable replay independence audit failed")


if __name__ == "__main__":
    main()
