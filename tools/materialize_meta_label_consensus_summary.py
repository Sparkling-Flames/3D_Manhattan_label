from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd


CONSENSUS_METHOD = "majority_token_presence_demote_default_after_task_annotator_dedup"
CONSENSUS_VERSION = "v2"


def _as_string(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _unique_nonempty(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _normalize_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    tokens: list[str] = []
    for token in text.replace(",", ";").split(";"):
        token_str = str(token).strip()
        if token_str and token_str.lower() not in {"na", "nan", "none"}:
            tokens.append(token_str)
    return tokens


def _collapse_vote_unit_values(values: Iterable[Any]) -> tuple[str, bool]:
    token_sets = {tuple(sorted(set(_normalize_tokens(value)))) for value in values}
    if not token_sets:
        return "", False
    if len(token_sets) > 1:
        return "", True
    only = next(iter(token_sets))
    return ";".join(only), False


def _annotation_token_counts(values: Iterable[Any]) -> tuple[Dict[str, int], int]:
    counts: Dict[str, int] = {}
    n_nonempty = 0
    for value in values:
        tokens = set(_normalize_tokens(value))
        if not tokens:
            continue
        n_nonempty += 1
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
    return counts, n_nonempty


def _resolve_consensus(
    values: Iterable[Any],
    *,
    default: str,
    demote_token: str | None = None,
) -> dict[str, Any]:
    raw_counts, n_nonempty = _annotation_token_counts(values)
    if not raw_counts:
        return {
            "consensus": default,
            "confidence": 0.0,
            "secondary_labels": "",
            "defaulted": True,
            "n_nonempty": 0,
            "vote_counts_json": json.dumps({}, ensure_ascii=False),
        }

    effective_counts = dict(raw_counts)
    if demote_token and demote_token in effective_counts and len(effective_counts) > 1:
        effective_counts.pop(demote_token, None)
        if not effective_counts:
            effective_counts = dict(raw_counts)

    ordered = sorted(effective_counts.items(), key=lambda item: (-item[1], item[0]))
    primary, primary_count = ordered[0]
    secondary = ";".join(label for label, _ in ordered[1:])
    confidence = round(primary_count / n_nonempty, 6) if n_nonempty else 0.0

    return {
        "consensus": primary,
        "confidence": confidence,
        "secondary_labels": secondary,
        "defaulted": False,
        "n_nonempty": n_nonempty,
        "vote_counts_json": json.dumps(dict(sorted(raw_counts.items())), ensure_ascii=False),
    }


def _load_registry_sidecar(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(columns=["task_id", "base_task_id", "dataset_group"])
    registry = pd.read_csv(path, dtype=str).fillna("")
    needed = [col for col in ("task_id", "base_task_id", "dataset_group") if col in registry.columns]
    if "task_id" not in needed:
        raise ValueError("registry csv must contain task_id")
    return registry[needed].drop_duplicates(subset=["task_id"])


def build_summary(
    quality_df: pd.DataFrame,
    registry_df: pd.DataFrame | None = None,
    *,
    fail_on_conflict: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    quality = quality_df.copy()
    quality["task_id"] = _as_string(quality["task_id"])
    if "annotator_id" in quality.columns:
        quality["annotator_id"] = _as_string(quality["annotator_id"])
    if "dataset_group" not in quality.columns:
        quality["dataset_group"] = ""
    if "dataset_group" in quality.columns:
        quality["dataset_group"] = _as_string(quality["dataset_group"])
    if "export_dataset_group" in quality.columns:
        quality["export_dataset_group"] = _as_string(quality["export_dataset_group"])
    if "base_task_id" not in quality.columns:
        quality["base_task_id"] = ""
    if "base_task_id" in quality.columns:
        quality["base_task_id"] = _as_string(quality["base_task_id"])
    if "difficulty" not in quality.columns:
        quality["difficulty"] = ""
    if "model_issue_primary" not in quality.columns:
        quality["model_issue_primary"] = quality.get("model_issue", "")
    if "model_issue" not in quality.columns:
        quality["model_issue"] = ""

    if registry_df is not None and not registry_df.empty:
        registry = registry_df.copy()
        registry["task_id"] = _as_string(registry["task_id"])
        if "base_task_id" in registry.columns:
            registry["base_task_id"] = _as_string(registry["base_task_id"])
        if "dataset_group" in registry.columns:
            registry["dataset_group"] = _as_string(registry["dataset_group"])
        quality = quality.merge(
            registry,
            on="task_id",
            how="left",
            suffixes=("", "_registry"),
        )
    else:
        quality["base_task_id_registry"] = ""
        quality["dataset_group_registry"] = ""

    records: list[dict[str, Any]] = []
    dataset_group_defaulted = 0
    base_task_defaulted = 0
    dataset_group_conflict_tasks: list[str] = []
    base_task_conflict_tasks: list[str] = []
    duplicate_annotator_tasks: list[str] = []
    difficulty_conflict_tasks: list[str] = []
    model_issue_conflict_tasks: list[str] = []

    for task_id, group in quality.groupby("task_id", dropna=False):
        group = group.copy()
        export_dataset_group = _as_string(group.get("export_dataset_group", pd.Series(dtype=object)))
        dataset_group = _as_string(group.get("dataset_group", pd.Series(dtype=object)))
        dataset_group_registry = _as_string(group.get("dataset_group_registry", pd.Series(dtype=object)))
        base_task_id = _as_string(group.get("base_task_id", pd.Series(dtype=object)))
        base_task_id_registry = _as_string(group.get("base_task_id_registry", pd.Series(dtype=object)))
        annotator_ids = _unique_nonempty(group.get("annotator_id", pd.Series(dtype=object)))

        export_dataset_group_values = _unique_nonempty(export_dataset_group)
        dataset_group_values = _unique_nonempty(dataset_group)
        dataset_group_registry_values = _unique_nonempty(dataset_group_registry)
        dataset_group_conflict_values = _unique_nonempty(
            export_dataset_group_values + dataset_group_values + dataset_group_registry_values
        )
        dataset_group_conflict = len(dataset_group_conflict_values) > 1
        if dataset_group_conflict:
            dataset_group_conflict_tasks.append(str(task_id))

        resolved_dataset_group = next(
            iter(
                values[0]
                for values in [
                    export_dataset_group_values,
                    dataset_group_values,
                    dataset_group_registry_values,
                ]
                if values
            ),
            "",
        )
        resolved_dataset_group_source = next(
            iter(
                source
                for source, values in [
                    ("export_dataset_group", export_dataset_group_values),
                    ("dataset_group", dataset_group_values),
                    ("dataset_group_registry", dataset_group_registry_values),
                ]
                if values
            ),
            "missing",
        )
        if not resolved_dataset_group:
            dataset_group_defaulted += 1

        base_task_id_values = _unique_nonempty(base_task_id)
        base_task_id_registry_values = _unique_nonempty(base_task_id_registry)
        base_task_conflict_values = _unique_nonempty(
            base_task_id_values + base_task_id_registry_values
        )
        base_task_id_conflict = len(base_task_conflict_values) > 1
        if base_task_id_conflict:
            base_task_conflict_tasks.append(str(task_id))

        resolved_base_task_id = next(
            iter(
                value
                for value in [
                    base_task_id_values[0] if base_task_id_values else "",
                    base_task_id_registry_values[0] if base_task_id_registry_values else "",
                    str(task_id),
                ]
                if value
            ),
            str(task_id),
        )
        resolved_base_task_id_source = next(
            iter(
                source
                for source, value in [
                    ("base_task_id", base_task_id_values[0] if base_task_id_values else ""),
                    ("base_task_id_registry", base_task_id_registry_values[0] if base_task_id_registry_values else ""),
                    ("task_id_fallback", str(task_id)),
                ]
                if value
            ),
            "task_id_fallback",
        )
        if resolved_base_task_id == str(task_id):
            base_task_defaulted += 1

        duplicate_annotator_rows = max(0, int(len(group)) - len(annotator_ids))
        if duplicate_annotator_rows > 0:
            duplicate_annotator_tasks.append(str(task_id))

        difficulty_vote_units: list[str] = []
        model_issue_vote_units: list[str] = []
        n_difficulty_conflicted_annotators = 0
        n_model_issue_conflicted_annotators = 0

        if "annotator_id" in group.columns and _as_string(group["annotator_id"]).ne("").any():
            vote_unit_groups: list[pd.DataFrame] = []
            seen_annotators: set[str] = set()
            annotator_series = _as_string(group["annotator_id"])
            for annotator_id, annotator_group in group.groupby(annotator_series, dropna=False, sort=False):
                if annotator_id:
                    vote_unit_groups.append(annotator_group)
                    seen_annotators.add(str(annotator_id))
            missing_rows = group.loc[annotator_series.eq("")]
            if not missing_rows.empty:
                for _, missing_row in missing_rows.iterrows():
                    vote_unit_groups.append(pd.DataFrame([missing_row]))
            for vote_group in vote_unit_groups:
                collapsed_difficulty, difficulty_conflict = _collapse_vote_unit_values(
                    vote_group.get("difficulty", pd.Series(dtype=object))
                )
                difficulty_vote_units.append(collapsed_difficulty)
                if difficulty_conflict:
                    n_difficulty_conflicted_annotators += 1

                collapsed_model_issue, model_issue_conflict = _collapse_vote_unit_values(
                    vote_group.get("model_issue", pd.Series(dtype=object))
                )
                model_issue_vote_units.append(collapsed_model_issue)
                if model_issue_conflict:
                    n_model_issue_conflicted_annotators += 1
        else:
            difficulty_vote_units = [str(value) for value in group.get("difficulty", pd.Series(dtype=object))]
            model_issue_vote_units = [str(value) for value in group.get("model_issue", pd.Series(dtype=object))]

        if n_difficulty_conflicted_annotators > 0:
            difficulty_conflict_tasks.append(str(task_id))
        if n_model_issue_conflicted_annotators > 0:
            model_issue_conflict_tasks.append(str(task_id))

        difficulty_summary = _resolve_consensus(
            difficulty_vote_units,
            default="none",
            demote_token="trivial",
        )
        model_issue_summary = _resolve_consensus(
            model_issue_vote_units,
            default="acceptable",
            demote_token="acceptable",
        )

        records.append(
            {
                "task_id": str(task_id),
                "base_task_id": resolved_base_task_id,
                "base_task_id_source": resolved_base_task_id_source,
                "dataset_group": resolved_dataset_group,
                "dataset_group_source": resolved_dataset_group_source,
                "n_annotations": int(len(group)),
                "n_unique_annotators": int(len(annotator_ids)),
                "n_duplicate_annotator_rows": int(duplicate_annotator_rows),
                "n_difficulty_conflicted_annotators": int(n_difficulty_conflicted_annotators),
                "n_model_issue_conflicted_annotators": int(n_model_issue_conflicted_annotators),
                "difficulty_consensus": difficulty_summary["consensus"],
                "difficulty_consensus_confidence": difficulty_summary["confidence"],
                "model_issue_consensus": model_issue_summary["consensus"],
                "model_issue_consensus_confidence": model_issue_summary["confidence"],
                "consensus_method": CONSENSUS_METHOD,
                "consensus_version": CONSENSUS_VERSION,
                "secondary_difficulty_labels": difficulty_summary["secondary_labels"],
                "secondary_model_issue_labels": model_issue_summary["secondary_labels"],
                "consensus_notes": "",
                "n_difficulty_nonempty": int(difficulty_summary["n_nonempty"]),
                "n_model_issue_nonempty": int(model_issue_summary["n_nonempty"]),
                "difficulty_defaulted": bool(difficulty_summary["defaulted"]),
                "model_issue_defaulted": bool(model_issue_summary["defaulted"]),
                "dataset_group_conflict": bool(dataset_group_conflict),
                "dataset_group_conflict_values": ";".join(dataset_group_conflict_values),
                "base_task_id_conflict": bool(base_task_id_conflict),
                "base_task_id_conflict_values": ";".join(base_task_conflict_values),
                "difficulty_vote_counts_json": difficulty_summary["vote_counts_json"],
                "model_issue_vote_counts_json": model_issue_summary["vote_counts_json"],
            }
        )

    summary = pd.DataFrame.from_records(records).sort_values(["dataset_group", "task_id"]).reset_index(drop=True)
    audit = {
        "consensus_method": CONSENSUS_METHOD,
        "consensus_version": CONSENSUS_VERSION,
        "n_tasks": int(len(summary)),
        "n_tasks_difficulty_defaulted": int(summary["difficulty_defaulted"].sum()) if not summary.empty else 0,
        "n_tasks_model_issue_defaulted": int(summary["model_issue_defaulted"].sum()) if not summary.empty else 0,
        "n_tasks_dataset_group_defaulted": dataset_group_defaulted,
        "n_tasks_base_task_id_fallback_to_task_id": base_task_defaulted,
        "n_tasks_dataset_group_conflict": len(dataset_group_conflict_tasks),
        "n_tasks_base_task_id_conflict": len(base_task_conflict_tasks),
        "n_tasks_duplicate_annotator_rows": len(duplicate_annotator_tasks),
        "n_tasks_difficulty_conflicted_annotators": len(difficulty_conflict_tasks),
        "n_tasks_model_issue_conflicted_annotators": len(model_issue_conflict_tasks),
        "dataset_group_conflict_task_ids": dataset_group_conflict_tasks,
        "base_task_id_conflict_task_ids": base_task_conflict_tasks,
        "duplicate_annotator_task_ids": duplicate_annotator_tasks,
        "difficulty_conflict_task_ids": difficulty_conflict_tasks,
        "model_issue_conflict_task_ids": model_issue_conflict_tasks,
    }
    if fail_on_conflict and (dataset_group_conflict_tasks or base_task_conflict_tasks):
        raise ValueError(
            "conflicts detected in meta-label consensus sidecar: "
            f"dataset_group={dataset_group_conflict_tasks}, "
            f"base_task_id={base_task_conflict_tasks}"
        )
    return summary, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize meta_label_consensus_summary_v1.csv from quality csv.")
    parser.add_argument("--quality-csv", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--registry-csv", type=Path, default=None)
    parser.add_argument("--output-audit-json", type=Path, default=None)
    parser.add_argument(
        "--fail-on-conflict",
        action="store_true",
        help="Abort if any task_id resolves to conflicting dataset_group or base_task_id values.",
    )
    args = parser.parse_args()

    quality = pd.read_csv(args.quality_csv, dtype=str).fillna("")
    registry = _load_registry_sidecar(args.registry_csv)
    summary, audit = build_summary(
        quality,
        registry if not registry.empty else None,
        fail_on_conflict=args.fail_on_conflict,
    )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output_csv, index=False, encoding="utf-8")

    if args.output_audit_json is not None:
        args.output_audit_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_audit_json.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
