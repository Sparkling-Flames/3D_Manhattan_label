from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_CLOSEOUT_DIR = Path("analysis_results/prescreen_closeout")

FIELDS = [
    "annotator_id",
    "language",
    "completion_status",
    "expected_manual",
    "expected_semi",
    "expected_oos",
    "expected_total",
    "observed_canonical_rows",
    "observed_manual_rows",
    "observed_semi_rows",
    "observed_oos_rows",
    "missing_total",
    "will_continue",
    "dropout",
    "known_bad_or_process_risk",
    "exclude_from_primary_candidate",
    "suggested_closeout_action",
]


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _action(row: dict[str, str]) -> str:
    will_continue = _truthy(row.get("will_continue"))
    dropout = _truthy(row.get("dropout"))
    known_bad = _truthy(row.get("known_bad_or_process_risk"))
    excluded = _truthy(row.get("exclude_from_primary_candidate"))
    if will_continue and dropout:
        return "manual_decision_required"
    if dropout:
        return "mark_dropout_no_future_if_confirmed"
    if known_bad or excluded:
        return "mark_incomplete_excluded_if_confirmed"
    if will_continue and not dropout and not known_bad:
        return "wait_for_completion"
    return "manual_decision_required"


def build_pending_completion_audit(closeout_dir: Path = DEFAULT_CLOSEOUT_DIR) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(closeout_dir)
    completion = _load_csv(root / "prescreen_completion_audit.csv")
    roster = {row["annotator_id"]: row for row in _load_csv(root / "prescreen_worker_roster.csv")}
    canonical = _load_csv(root / "prescreen_canonical_annotations.csv")
    _load_json(root / "prescreen_canonicalize_summary.json")
    _load_json(root / "p1_closeout_readiness_summary.json")

    by_worker = Counter(_safe(row.get("annotator_id")) for row in canonical)
    by_worker_group = Counter((_safe(row.get("annotator_id")), _safe(row.get("dataset_group"))) for row in canonical)
    rows: list[dict[str, Any]] = []
    for comp in completion:
        if _safe(comp.get("completion_status")) != "pending_completion":
            continue
        aid = _safe(comp.get("annotator_id"))
        rr = roster.get(aid, {})
        merged = {**comp, **rr}
        out = {
            "annotator_id": aid,
            "language": _safe(merged.get("language")),
            "completion_status": _safe(comp.get("completion_status")),
            "expected_manual": _safe(rr.get("expected_manual") or comp.get("manual_expected")),
            "expected_semi": _safe(rr.get("expected_semi") or comp.get("semi_expected")),
            "expected_oos": _safe(rr.get("expected_oos") or comp.get("oos_expected")),
            "expected_total": _safe(rr.get("expected_total") or comp.get("total_expected")),
            "observed_canonical_rows": by_worker[aid],
            "observed_manual_rows": by_worker_group[(aid, "PreScreen_manual")],
            "observed_semi_rows": by_worker_group[(aid, "PreScreen_semi")],
            "observed_oos_rows": by_worker_group[(aid, "PreScreen_oos")],
            "missing_total": _safe(comp.get("total_missing")),
            "will_continue": _safe(merged.get("will_continue")),
            "dropout": _safe(merged.get("dropout")),
            "known_bad_or_process_risk": _safe(merged.get("known_bad_or_process_risk")),
            "exclude_from_primary_candidate": _safe(merged.get("exclude_from_primary_candidate")),
        }
        out["suggested_closeout_action"] = _action(out)
        rows.append(out)

    counts = Counter(str(row["suggested_closeout_action"]) for row in rows)
    summary = {
        "dry_run": True,
        "pending_completion_count": len(rows),
        "pending_worker_ids": [str(row["annotator_id"]) for row in rows],
        "n_wait_for_completion": counts.get("wait_for_completion", 0),
        "n_manual_decision_required": counts.get("manual_decision_required", 0),
        "n_mark_dropout_no_future_if_confirmed": counts.get("mark_dropout_no_future_if_confirmed", 0),
        "n_mark_incomplete_excluded_if_confirmed": counts.get("mark_incomplete_excluded_if_confirmed", 0),
        "readiness_blocker_cleared": False,
        "notes": "pending workers must be resolved before formal P1 materialization; this audit does not modify roster or completion status",
    }
    return rows, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--closeout-dir", default=str(DEFAULT_CLOSEOUT_DIR))
    args = parser.parse_args(argv)
    root = Path(args.closeout_dir)
    rows, summary = build_pending_completion_audit(root)
    audit = root / "p1_pending_completion_audit.csv"
    out = root / "p1_pending_completion_summary.json"
    _write_csv(audit, rows)
    summary.update({"pending_completion_audit_csv": str(audit), "pending_completion_summary_json": str(out)})
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
