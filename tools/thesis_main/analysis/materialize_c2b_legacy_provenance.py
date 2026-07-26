"""Audit the frozen 20260702 v3.1 legacy reverse set without granting eligibility."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


EXPECTED_SOURCE_SHA256 = "4666C167EC831F3B7B3C045652F64B4ED8878DFFFBB98C9851F561079B795BC7"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def materialize(manifest_csv: Path, inventory_csv: Path, output_dir: Path, *, task_eligibility_csv: Path | None = None) -> dict[str, Any]:
    legacy = _read(manifest_csv)
    if len(legacy) != 13 or {row.get("source_manifest_sha256", "") for row in legacy} != {EXPECTED_SOURCE_SHA256}:
        raise ValueError("legacy reverse manifest must bind the exact 13-row 20260702 v3.1 source")
    if any(str(row.get("formal_selection_priority", "")).lower() not in {"false", "0"} for row in legacy):
        raise ValueError("legacy provenance cannot grant formal selection priority")
    inventory = {(row.get("image_id", ""), row.get("base_task_id", "")): row for row in _read(inventory_csv)}
    eligibility = {(row.get("image_id", ""), row.get("base_task_id", "")): row for row in _read(task_eligibility_csv)} if task_eligibility_csv and task_eligibility_csv.exists() else {}
    rows = []
    for item in legacy:
        key = (item.get("image_id", ""), item.get("base_task_id", ""))
        source, evidence = inventory.get(key), eligibility.get(key, {})
        rows.append({
            **item,
            "inventory_identity_present": source is not None,
            "assignment_eligible": evidence.get("assignment_eligible", "not_evaluated"),
            "eligibility_exclusion_reason": evidence.get("exclusion_reason", ""),
            "history_overlap": evidence.get("history_overlap", ""),
            "audit_status": "matched" if source is not None else "inventory_identity_missing",
            "legacy_priority_used": False,
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "c2_legacy_reverse_candidate_audit.csv"
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary = {
        "n_manifest_rows": len(rows), "n_inventory_matches": sum(row["inventory_identity_present"] for row in rows),
        "legacy_priority_used": False, "source_manifest_sha256": EXPECTED_SOURCE_SHA256,
        "tracked_manifest_sha256": sha256_file(manifest_csv), "audit_sha256": sha256_file(output),
        "formal_ready": all(row["inventory_identity_present"] for row in rows),
    }
    (output_dir / "c2_legacy_reverse_candidate_audit.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
