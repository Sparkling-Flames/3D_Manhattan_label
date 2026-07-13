"""Small shared helpers for Paper A vFinal additive sidecars.

The helpers deliberately keep the sidecar layer stdlib-only.  They make the
dry-run status explicit instead of letting an empty or synthetic input look
like a formal C1 artifact.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


COMMON_SIDECAR_FIELDS = [
    "schema_version",
    "rule_version",
    "source_artifact",
    "source_sha256",
    "dependency_bundle_id",
    "stage",
    "pool",
    "condition",
    "validity_status",
    "interpretation_allowed",
]
# Backward-compatible internal spelling used by the first migration patch.
COMMON_SIDEcar_FIELDS = COMMON_SIDECAR_FIELDS


def sha256_file(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sidecar_common(
    *,
    source_artifact: str,
    source_sha256: str,
    stage: str = "C1",
    pool: str = "",
    condition: str = "",
    validity_status: str = "dry_run",
    schema_version: str = "paper_a_vfinal_sidecar_v1",
    rule_version: str = "paper_a_vfinal_v1",
    interpretation_allowed: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "rule_version": rule_version,
        "source_artifact": source_artifact,
        "source_sha256": source_sha256,
        "dependency_bundle_id": hashlib.sha256(f"{source_artifact}|{source_sha256}|{stage}|{rule_version}".encode("utf-8")).hexdigest(),
        "stage": stage,
        "pool": pool,
        "condition": condition,
        "validity_status": validity_status,
        "interpretation_allowed": str(bool(interpretation_allowed)).lower(),
    }


def write_csv_rows(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in materialized:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fieldnames} for row in materialized)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def formal_status(input_status: str, *, valid: bool = True) -> tuple[str, bool]:
    """Return a safe status/interpretation pair for sidecar rows."""
    if str(input_status).strip().lower() != "formal":
        return "dry_run" if valid else "not_evaluable", False
    return ("valid" if valid else "not_evaluable"), bool(valid)
