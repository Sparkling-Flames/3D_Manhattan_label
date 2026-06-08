from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PHASE1_DIRNAME = "phase1_progress_20260324"
SEMI_V8_NAME = "prescreen_semi_final_selection_v8.json"
SEMI_V9_NAME = "prescreen_semi_final_selection_v9.json"
STAGE1_AUDIT_V4_NAME = "stage1_final_binding_audit_v4.json"
STAGE1_AUDIT_V5_NAME = "stage1_final_binding_audit_v5.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_inputs(repo_root: Path) -> dict[str, Any]:
    phase1_dir = repo_root / "analysis_results" / PHASE1_DIRNAME
    return {
        "phase1_dir": phase1_dir,
        "semi_v8": _read_json(phase1_dir / SEMI_V8_NAME),
        "stage1_audit_v4": _read_json(phase1_dir / STAGE1_AUDIT_V4_NAME),
    }


def build_semi_v9(inputs: dict[str, Any]) -> dict[str, Any]:
    semi_v8 = dict(inputs["semi_v8"])
    semi_v9 = json.loads(json.dumps(semi_v8, ensure_ascii=False))

    semi_v9["selection_name"] = "prescreen_semi_final_selection_v9"
    semi_v9["parent_selection"] = "prescreen_semi_final_selection_v8"
    semi_v9["audit_stress_candidates"] = {
        "fail_task_ids": [],
        "topology_failure_task_ids": semi_v8.get("audit_stress_candidates", {}).get(
            "topology_failure_task_ids", []
        ),
        "notes": (
            "task475 remains a low-priority fail holdout candidate, but is currently withheld from the "
            "active semi_audit_stress import because curator review judges it not yet strong enough as a "
            "canonical fail stress sample."
        ),
    }
    semi_v9["audit_stress_holdout_candidates"] = {
        "fail_task_ids": ["475"],
        "topology_failure_task_ids": [],
        "notes": (
            "Holdout pool reserved for future semantic strengthening or replacement. "
            "These rows are not part of the active prescreen import."
        ),
    }
    semi_v9["notes"] = list(semi_v8.get("notes", [])) + [
        "task475 is currently removed from the active semi_audit_stress import and retained only as a holdout fail candidate."
    ]

    return semi_v9


def build_stage1_audit_v5(inputs: dict[str, Any], semi_v9: dict[str, Any]) -> dict[str, Any]:
    audit_v4 = dict(inputs["stage1_audit_v4"])
    audit_v5 = json.loads(json.dumps(audit_v4, ensure_ascii=False))
    audit_v5["audit_name"] = "stage1_final_binding_audit_v5"
    audit_v5["selection_freeze_reused"] = True
    audit_v5["rebind_only_no_reselection"] = False
    audit_v5["notes"] = list(audit_v4.get("notes", [])) + [
        "The active semi_audit_stress layer is now empty; task475 is retained only as a holdout fail candidate."
    ]
    return audit_v5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=f"analysis_results/{PHASE1_DIRNAME}")
    args = parser.parse_args()

    repo_root = _repo_root()
    inputs = load_inputs(repo_root)
    semi_v9 = build_semi_v9(inputs)
    audit_v5 = build_stage1_audit_v5(inputs, semi_v9)

    output_dir = repo_root / args.output_dir
    _write_json(output_dir / SEMI_V9_NAME, semi_v9)
    _write_json(output_dir / STAGE1_AUDIT_V5_NAME, audit_v5)


if __name__ == "__main__":
    main()
