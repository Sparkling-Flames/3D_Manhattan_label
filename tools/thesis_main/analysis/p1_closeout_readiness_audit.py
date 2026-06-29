from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_CLOSEOUT_DIR = Path("analysis_results/prescreen_closeout")

REQUIRED_ARTIFACTS = [
    "prescreen_canonicalize_summary.json",
    "prescreen_completion_audit.csv",
    "prescreen_worker_roster.csv",
    "prescreen_scope_summary.json",
    "prescreen_scope_response_audit.csv",
    "prescreen_worker_scope_summary.csv",
    "prescreen_geometry_eligibility_audit.csv",
]

OPTIONAL_ARTIFACTS = [
    "prescreen_active_time_source_audit.csv",
    "prescreen_undercoverage_risk_audit.csv",
    "prescreen_consensus_guard_audit.csv",
    "prescreen_worker_screening_summary.json",
]

FORBIDDEN_NAME_TOKENS = (
    "geometry_score",
    "admission",
    "reject",
    "r0",
    "r_u",
    "wmax",
    "w_max",
    "routing",
    "handoff",
    "reliability",
)

C1_TOKEN_RE = re.compile(r"(^|[_\-.])c1($|[_\-.])", re.IGNORECASE)

FORBIDDEN_SUMMARY_KEYS = {
    "admission",
    "reject",
    "r0",
    "r_u",
    "wmax",
    "w_max",
    "routing",
    "c1_handoff",
    "worker_reliability_profile",
}


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return dict(Counter(_safe(row.get("completion_status")) or "missing" for row in rows))


def _manifest_completion_basis(root: Path, canonical_summary: dict[str, Any]) -> str:
    raw = _safe(canonical_summary.get("raw_input_manifest"))
    if not raw:
        return ""
    path = Path(raw)
    if not path.exists():
        path = root / raw
    rows = _load_csv(path)
    return _safe(rows[0].get("completion_basis")) if rows else ""


def _forbidden_artifacts(root: Path) -> list[str]:
    found: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.stem.lower()
        if any(token in name for token in FORBIDDEN_NAME_TOKENS) or C1_TOKEN_RE.search(name):
            found.append(str(path))
    return sorted(found)


def build_readiness_summary(closeout_dir: Path = DEFAULT_CLOSEOUT_DIR) -> dict[str, Any]:
    root = Path(closeout_dir)
    scope = _load_json(root / "prescreen_scope_summary.json")
    canonical = _load_json(root / "prescreen_canonicalize_summary.json")
    screening = _load_json(root / "prescreen_worker_screening_summary.json")
    completion_rows = _load_csv(root / "prescreen_completion_audit.csv")
    roster_rows = _load_csv(root / "prescreen_worker_roster.csv")

    missing_required = [name for name in REQUIRED_ARTIFACTS if not (root / name).exists()]
    missing_optional = [name for name in OPTIONAL_ARTIFACTS if not (root / name).exists()]
    completion_counts = _status_counts(completion_rows)
    pending_count = completion_counts.get("pending_completion", 0)
    dropout_count = completion_counts.get("dropout_no_future", 0)
    incomplete_count = completion_counts.get("incomplete_excluded", 0)
    known_bad_count = sum(_truthy(row.get("known_bad_or_process_risk")) for row in completion_rows) or sum(
        _truthy(row.get("known_bad_or_process_risk")) for row in roster_rows
    )
    forbidden = _forbidden_artifacts(root)

    data_complete = bool(scope.get("data_complete")) if "data_complete" in scope else False
    unknown_gold = int(scope.get("unknown_gold_tasks") or scope.get("unknown_gold_task_rows_total") or 0)
    allowlisted = int(scope.get("n_unknown_gold_allowlisted") or 0)
    blockers: list[str] = []
    if missing_required:
        blockers.append("missing_required_dry_run_artifacts")
    if data_complete is False:
        blockers.append("data_complete_false")
    if unknown_gold > allowlisted:
        blockers.append("unknown_gold_unresolved")
    if forbidden:
        blockers.append("forbidden_artifacts_present")
    if pending_count:
        blockers.append("pending_completion_present")
    if scope.get("geometry_score_fields_present") is True:
        blockers.append("geometry_score_fields_present")

    status = "blocked" if blockers else "ready_for_materialization_review"
    summary = {
        "dry_run": True,
        "formal_materialization_allowed": False,
        "data_complete": data_complete,
        "completion_basis": scope.get("completion_basis") or canonical.get("completion_basis") or _manifest_completion_basis(root, canonical),
        "base_image_count": scope.get("base_image_count"),
        "runtime_task_rows": scope.get("runtime_task_rows") or scope.get("n_tasks"),
        "worker_completion_status_counts": completion_counts,
        "known_bad_or_process_risk_count": known_bad_count,
        "dropout_count": dropout_count,
        "pending_completion_count": pending_count,
        "incomplete_excluded_count": incomplete_count,
        "unknown_gold_count": unknown_gold,
        "unknown_gold_allowlisted_count": allowlisted,
        "mixed_scope_count": int(scope.get("mixed_scope_tasks") or scope.get("n_mixed_task_audit_rows") or 0),
        "source_export_snapshot_count": int(scope.get("source_export_snapshot_count") or 0),
        "final_gold_source_snapshot_sha256_match": scope.get("final_gold_source_snapshot_sha256_match"),
        "export_gt_source_snapshot_sha256_match": scope.get("export_gt_source_snapshot_sha256_match"),
        "source_export_source_snapshot_sha256_mismatch_count": int(scope.get("source_export_source_snapshot_sha256_mismatch_count") or 0),
        "geometry_score_fields_present": bool(scope.get("geometry_score_fields_present")),
        "forbidden_artifact_count": len(forbidden),
        "forbidden_artifacts": forbidden,
        "missing_required_artifacts": missing_required,
        "missing_optional_artifacts": missing_optional,
        "optional_audit_status": "missing_optional" if missing_optional else "available",
        "screening_status": screening.get("screening_status", "missing_optional"),
        "readiness_status": status,
        "blockers": blockers,
    }
    if set(summary) & FORBIDDEN_SUMMARY_KEYS:
        raise AssertionError("readiness summary contains forbidden formal materialization keys")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--closeout-dir", default=str(DEFAULT_CLOSEOUT_DIR))
    args = parser.parse_args(argv)
    root = Path(args.closeout_dir)
    summary = build_readiness_summary(root)
    out = root / "p1_closeout_readiness_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
