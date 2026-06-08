"""Validate Manhattan probe summary JSON sidecars.

This M6 validator reads only the probe summary JSON supplied by --input. It
does not open source_export, does not read Label Studio exports, does not write
back annotations, and does not connect to UI, formal g_t, routing, or
P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


REQUIRED_FIELDS = (
    "source_export",
    "probe_version",
    "n_tasks",
    "n_annotations",
    "n_keypoint_results",
    "compatibility_status_counts",
    "residual_enabled",
    "audit_eligibility_enabled",
    "n_audit_eligible",
    "n_audit_ineligible",
    "n_audit_residual_valid",
    "n_audit_residual_excluded",
    "suggestions_enabled",
)

FORBIDDEN_PAYLOAD_TERMS = (
    "snap",
    "adjustment",
    "writeback",
    "routing decision",
    "worker tier",
)


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a probe summary JSON object")
    return payload


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_nonnegative_number(value: Any, field: str, errors: list[str]) -> float | None:
    if not _is_number(value):
        errors.append(f"{field} must be numeric")
        return None
    if value < 0:
        errors.append(f"{field} must be nonnegative")
        return None
    return float(value)


def _walk_items(value: Any, path: str = "$"):
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk_items(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_items(child, f"{path}[{index}]")


def _check_forbidden_terms(summary: Mapping[str, Any], errors: list[str], warnings: list[str]) -> None:
    for path, key, value in _walk_items(summary):
        key_lower = key.lower()
        for term in FORBIDDEN_PAYLOAD_TERMS:
            if term in key_lower:
                errors.append(f"forbidden payload term in key at {path}: {term}")
        if isinstance(value, str):
            value_lower = value.lower()
            for term in FORBIDDEN_PAYLOAD_TERMS:
                if term in value_lower:
                    warnings.append(f"forbidden payload term in string value at {path}: {term}")


def validate_summary(summary: Mapping[str, Any], summary_path: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked_fields: list[str] = []

    for field in REQUIRED_FIELDS:
        checked_fields.append(field)
        if field not in summary:
            errors.append(f"missing required field: {field}")

    source_export = summary.get("source_export")
    if "source_export" in summary and not isinstance(source_export, str):
        warnings.append("source_export is present but is not a string")

    n_annotations = _as_nonnegative_number(
        summary.get("n_annotations"),
        "n_annotations",
        errors,
    )

    residual_enabled = summary.get("residual_enabled")
    if residual_enabled is True:
        checked_fields.extend(
            [
                "residual_numeric_summary",
                "n_residual_valid",
                "n_residual_excluded",
                "audit_residual_numeric_summary",
            ]
        )
        if "residual_numeric_summary" not in summary:
            errors.append("missing residual_numeric_summary when residual_enabled=true")
        if "audit_residual_numeric_summary" not in summary:
            errors.append("missing audit_residual_numeric_summary when residual_enabled=true")

        n_residual_valid = _as_nonnegative_number(
            summary.get("n_residual_valid"),
            "n_residual_valid",
            errors,
        )
        n_residual_excluded = _as_nonnegative_number(
            summary.get("n_residual_excluded"),
            "n_residual_excluded",
            errors,
        )
        if (
            n_annotations is not None
            and n_residual_valid is not None
            and n_residual_excluded is not None
            and n_residual_valid + n_residual_excluded > n_annotations
        ):
            errors.append("n_residual_valid + n_residual_excluded exceeds n_annotations")

        n_audit_eligible = _as_nonnegative_number(
            summary.get("n_audit_eligible"),
            "n_audit_eligible",
            errors,
        )
        n_audit_residual_valid = _as_nonnegative_number(
            summary.get("n_audit_residual_valid"),
            "n_audit_residual_valid",
            errors,
        )
        n_audit_residual_excluded = _as_nonnegative_number(
            summary.get("n_audit_residual_excluded"),
            "n_audit_residual_excluded",
            errors,
        )
        if (
            n_audit_eligible is not None
            and n_audit_residual_valid is not None
            and n_audit_residual_excluded is not None
            and n_audit_residual_valid + n_audit_residual_excluded > n_audit_eligible
        ):
            errors.append(
                "n_audit_residual_valid + n_audit_residual_excluded exceeds n_audit_eligible"
            )

    suggestions_enabled = summary.get("suggestions_enabled")
    if suggestions_enabled is True:
        checked_fields.extend(["suggestion_type_counts", "n_suggestion_annotations"])
        if "suggestion_type_counts" not in summary:
            errors.append("missing suggestion_type_counts when suggestions_enabled=true")
            suggestion_type_counts = {}
        else:
            suggestion_type_counts = summary.get("suggestion_type_counts")

        n_suggestion_annotations = _as_nonnegative_number(
            summary.get("n_suggestion_annotations"),
            "n_suggestion_annotations",
            errors,
        )
        n_audit_residual_valid = _as_nonnegative_number(
            summary.get("n_audit_residual_valid"),
            "n_audit_residual_valid",
            errors,
        )
        if (
            n_suggestion_annotations is not None
            and n_audit_residual_valid is not None
            and n_suggestion_annotations > n_audit_residual_valid
        ):
            errors.append("n_suggestion_annotations exceeds n_audit_residual_valid")

        if isinstance(suggestion_type_counts, Mapping) and n_suggestion_annotations is not None:
            event_count = sum(
                value for value in suggestion_type_counts.values() if isinstance(value, int)
            )
            checked_fields.append("sum(suggestion_type_counts)")
            if event_count > n_suggestion_annotations:
                warnings.append(
                    "sum(suggestion_type_counts) exceeds n_suggestion_annotations; "
                    "multiple suggestion events per annotation are allowed"
                )

    _check_forbidden_terms(summary, errors, warnings)

    status = "fail" if errors else ("warning" if warnings else "pass")
    return {
        "validation_status": status,
        "summary_path": summary_path,
        "probe_version": summary.get("probe_version"),
        "source_export": source_export,
        "errors": errors,
        "warnings": warnings,
        "checked_fields": sorted(set(checked_fields)),
    }


def validate_file(input_path: Path) -> dict[str, Any]:
    return validate_summary(load_summary(input_path), summary_path=str(input_path))


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Probe summary JSON path.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional validation report JSON path. If omitted, the report is printed to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = validate_file(args.input)
    if args.output:
        write_report(args.output, report)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
