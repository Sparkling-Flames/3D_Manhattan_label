"""Shared fail-closed loaders for the normative Paper A v2 contracts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS = PROJECT_ROOT / "docs" / "thesis_main"
METHOD_CONTRACT = DOCS / "PAPER_A_METHOD_CONTRACT_CURRENT.json"

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_method_contract(path: Path = METHOD_CONTRACT) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "paper_a_method_contract_v2":
        raise ValueError("Paper A method contract is not v2")
    if payload.get("status") != "current_normative_source":
        raise ValueError("Paper A method contract is not normative")
    return payload


def load_record_schema(name: str) -> dict[str, Any]:
    path = DOCS / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "paper_a_record_schema_v1" or payload.get("record_schema") != name:
        raise ValueError(f"invalid record schema:{name}")
    return payload


def validate_record(name: str, row: dict[str, Any]) -> None:
    schema = load_record_schema(name)
    version_field = str(schema.get("record_version_field", "schema_version"))
    if row.get(version_field) != schema.get("record_version_value"):
        raise ValueError(f"{name} record schema_version mismatch")
    forbidden = [field for field in schema.get("forbidden", []) if field in row]
    if forbidden:
        raise ValueError(f"{name} forbids legacy fields:{','.join(forbidden)}")
    nullable = set(schema.get("nullable", []))
    missing = [field for field in schema.get("required", []) if field not in row or (str(row[field]).strip() == "" and field not in nullable)]
    if missing:
        raise ValueError(f"{name} missing fields:{','.join(missing)}")
    invalid_booleans = [field for field in schema.get("boolean", []) if field in row and type(row[field]) is not bool]
    if invalid_booleans:
        raise ValueError(f"{name} boolean fields must be bool:{','.join(sorted(invalid_booleans))}")
    nonfinite = []
    for field in schema.get("finite", []):
        if field in nullable and row.get(field) in {None, ""}:
            continue
        try:
            value = float(row[field])
        except (TypeError, ValueError):
            nonfinite.append(field)
            continue
        if not math.isfinite(value):
            nonfinite.append(field)
    if nonfinite:
        raise ValueError(f"{name} non-finite fields:{','.join(nonfinite)}")


def validate_records(name: str, rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows):
        try:
            validate_record(name, row)
        except ValueError as exc:
            raise ValueError(f"{name} row {index}: {exc}") from exc


def validate_serialized_record(name: str, row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    schema = load_record_schema(name)
    for field in schema.get("boolean", []):
        if field not in normalized:
            continue
        value = normalized.get(field)
        if type(value) is bool:
            continue
        token = str(value).strip().lower()
        if token not in {"true", "false"}:
            raise ValueError(f"{name} boolean field is not canonical:{field}")
        normalized[field] = token == "true"
    validate_record(name, normalized)
    return normalized
