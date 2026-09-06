"""Audit whether the current ep300 task-level proxy matches the proposal actually shown in C1.

The current 648-image model audit evaluates the frozen ep300 output.  C1 workers,
however, saw proposals embedded in the historical C1 import artifact.  This script
uses the import JSON itself to recover historical proposal corner-pair counts and
prevents a task-id join from being misread as proposal-artifact identity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "analysis_results" / "proposal_correctness_model_issue_bridge_20260823"
IMPORT_ZH = ROOT / "import_json" / "calibration_c1_v3_1_formal" / "c1_v3_1_semi_import_zh.json"
TASK_JOIN = OUT / "C1_EXISTING_SEMI_TASKS_JOINED_WITH_CURRENT_MODEL_AUDIT.csv"
ROW_JOIN = OUT / "C1_EXISTING_SEMI_RESPONSE_ROWS_JOINED_WITH_CURRENT_MODEL_AUDIT.csv"


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "eligible", "passed"}


def issue_tokens(value: Any) -> set[str]:
    text = str(value or "").lower()
    for sep in (",", "|", ";"):
        text = text.replace(sep, ";")
    return {part.strip() for part in text.split(";") if part.strip() and part.strip() != "acceptable"}


def historical_proposals() -> pd.DataFrame:
    payload = json.loads(IMPORT_ZH.read_text(encoding="utf-8-sig"))
    rows: list[dict[str, Any]] = []
    for task in payload:
        data = task.get("data") or {}
        base = str(data.get("base_task_id") or "").strip()
        predictions = task.get("predictions") or []
        if len(predictions) != 1:
            raise AssertionError(f"{base}: prediction count != 1")
        prediction = predictions[0]
        points: list[tuple[float, float]] = []
        for item in prediction.get("result") or []:
            if item.get("type") != "keypointlabels":
                continue
            value = item.get("value") or {}
            width = float(item.get("original_width") or 1024)
            height = float(item.get("original_height") or 512)
            points.append((float(value["x"]) * width / 100.0, float(value["y"]) * height / 100.0))
        if len(points) < 4 or len(points) % 2:
            raise AssertionError(f"{base}: invalid historical point count {len(points)}")
        x_diffs = [abs(points[index][0] - points[index + 1][0]) for index in range(0, len(points), 2)]
        rows.append(
            {
                "base_task_id": base,
                "historical_model_version": str(prediction.get("model_version") or ""),
                "historical_prediction_point_count": len(points),
                "historical_prediction_pair_count": len(points) // 2,
                "historical_pair_encoding_valid": max(x_diffs) <= 1.0,
                "historical_max_pair_x_difference_px": max(x_diffs),
            }
        )
    result = pd.DataFrame(rows)
    if result["base_task_id"].nunique() != 25:
        raise AssertionError("historical C1 proposal task count drift")
    return result


def relation(delta: int, valid: bool) -> str:
    if not valid:
        return "historical_invalid_pair_encoding"
    if delta > 0:
        return "historical_model_more_pairs"
    if delta < 0:
        return "historical_model_fewer_pairs"
    return "historical_pair_count_exact"


def detection(frame: pd.DataFrame) -> pd.DataFrame:
    evaluable = frame[frame["worker_issue_response_observed"].map(truth)].copy()
    objective = ~evaluable["historical_topology_exact"]
    reported = evaluable["model_issue_choice"].map(lambda value: bool(issue_tokens(value)))
    tp = int((objective & reported).sum())
    fn = int((objective & ~reported).sum())
    fp = int((~objective & reported).sum())
    tn = int((~objective & ~reported).sum())
    return pd.DataFrame(
        [
            {
                "audit_outcome": "historical_proposal_vs_GT_pair_count_mismatch",
                "row_count": len(evaluable),
                "task_count": evaluable["base_task_id"].nunique(),
                "worker_count": evaluable["worker_id"].nunique(),
                "tp": tp,
                "fn": fn,
                "fp": fp,
                "tn": tn,
                "sensitivity": tp / (tp + fn) if tp + fn else np.nan,
                "specificity": tn / (tn + fp) if tn + fp else np.nan,
                "boundary": "pair-count mismatch only; not full topology or continuous correctness",
            }
        ]
    )


def main() -> None:
    hist = historical_proposals()
    task = pd.read_csv(TASK_JOIN, encoding="utf-8-sig", low_memory=False)
    row = pd.read_csv(ROW_JOIN, encoding="utf-8-sig", low_memory=False)

    task = task.merge(hist, on="base_task_id", how="left", validate="one_to_one")
    task["historical_pair_count_delta_vs_GT"] = (
        pd.to_numeric(task["historical_prediction_pair_count"], errors="raise")
        - pd.to_numeric(task["gt_pair_count"], errors="raise")
    ).astype(int)
    task["historical_topology_exact"] = (
        task["historical_pair_encoding_valid"].map(truth)
        & task["historical_pair_count_delta_vs_GT"].eq(0)
    )
    task["historical_proposal_topology_relation"] = task.apply(
        lambda value: relation(
            int(value["historical_pair_count_delta_vs_GT"]),
            truth(value["historical_pair_encoding_valid"]),
        ),
        axis=1,
    )
    task["historical_vs_current_ep300_pair_count_equal"] = (
        pd.to_numeric(task["historical_prediction_pair_count"], errors="raise")
        == pd.to_numeric(task["model_pair_count"], errors="raise")
    )
    task["proposal_artifact_identity_status"] = np.where(
        task["historical_vs_current_ep300_pair_count_equal"],
        "pair_count_equal_geometry_identity_not_proven",
        "different_pair_count_definitely_not_same_proposal_geometry",
    )

    summary = (
        task.groupby("historical_proposal_topology_relation", sort=True)
        .agg(
            task_count=("base_task_id", "nunique"),
            building_count=("building_id", "nunique"),
            mean_delta_shannon_entropy=("delta_shannon_entropy", "mean"),
            mean_delta_iou_to_gt=("delta_iou_to_gt", "mean"),
            mean_edit_rate=("edit_rate", "mean"),
            mean_issue_report_rate=("issue_report_rate", "mean"),
        )
        .reset_index()
    )

    row = row.drop(
        columns=[
            column for column in (
                "historical_model_version", "historical_prediction_point_count",
                "historical_prediction_pair_count", "historical_pair_encoding_valid",
                "historical_max_pair_x_difference_px", "historical_pair_count_delta_vs_GT",
                "historical_topology_exact", "historical_proposal_topology_relation",
                "historical_vs_current_ep300_pair_count_equal", "proposal_artifact_identity_status",
            ) if column in row.columns
        ]
    )
    row = row.merge(
        task[
            [
                "base_task_id", "historical_model_version", "historical_prediction_point_count",
                "historical_prediction_pair_count", "historical_pair_encoding_valid",
                "historical_max_pair_x_difference_px", "historical_pair_count_delta_vs_GT",
                "historical_topology_exact", "historical_proposal_topology_relation",
                "historical_vs_current_ep300_pair_count_equal", "proposal_artifact_identity_status",
            ]
        ],
        on="base_task_id", how="left", validate="many_to_one",
    )
    detect = detection(row)

    task.to_csv(OUT / "C1_HISTORICAL_PROPOSAL_IDENTITY_AND_TOPOLOGY_AUDIT.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUT / "C1_HISTORICAL_PROPOSAL_TOPOLOGY_SUMMARY.csv", index=False, encoding="utf-8-sig")
    detect.to_csv(OUT / "MODEL_ISSUE_PAIR_COUNT_DETECTION_ACTUAL_C1_PROPOSAL.csv", index=False, encoding="utf-8-sig")

    mismatch_n = int((~task["historical_vs_current_ep300_pair_count_equal"]).sum())
    amendment = f"""# Historical C1 proposal identity amendment

The first bridge joined the current ep300 audit to C1 by `base_task_id`. That is useful for
future Test sampling, but it is not sufficient to claim that the current ep300 output is the
proposal workers actually saw.

This audit recovers the proposal shown in the frozen C1 import JSON.

- C1 tasks audited: {len(task)}
- Historical/current ep300 pair-count mismatch: {mismatch_n}/{len(task)}
- Pair-count equality: {len(task)-mismatch_n}/{len(task)}; geometry identity remains unproven even in these rows.

Therefore:

1. `C1_HISTORICAL_PROPOSAL_TOPOLOGY_SUMMARY.csv` supersedes the earlier C1 grouping by current ep300 topology relation.
2. Current ep300 continuous metrics must not be attributed to the historical C1 proposal.
3. Historical `U_initial` remains the available continuous outcome for what workers saw, while the present audit supplies the actual historical proposal-vs-GT pair-count relation.
4. Exact geometry identity would require canonical coordinate comparison to the retained current-output files; pair-count mismatch already proves non-identity for the affected rows.
"""
    (OUT / "HISTORICAL_C1_PROPOSAL_IDENTITY_AMENDMENT.md").write_text(amendment, encoding="utf-8")
    print(amendment)


if __name__ == "__main__":
    main()
