"""Describe full-support persistent geometry disagreement in PreScreen and C1.

Development diagnostic only.  Finite historical support cannot establish that
an unlimited number of additional annotations would never resolve a task.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "analysis_results" / "persistent_disagreement_diagnostic_20260819_v1"
DEFAULT_THRESHOLDS = (0.90, 0.925, 0.95)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis import audit_prescreen_topology_support as prescreen
from tools.thesis_main.analysis import run_topology_sequential_preflight as topology
from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_persistence(cluster: dict[str, Any]) -> dict[str, bool]:
    status = str(cluster.get("task_crowd_structure_status") or "")
    share = _number(cluster.get("largest_cluster_share"))
    second = int(_number(cluster.get("second_cluster_support")) or 0)
    multimodal = status == "supported_multimodal" and second >= 2
    return {
        "supported_multimodal": multimodal,
        # 4:1 is the existing conservative k=5 resolved boundary; this is its
        # proportional full-support diagnostic, not a new formal stop rule.
        "strong_persistent_split": multimodal and share is not None and share < 0.80,
        "severe_persistent_split": multimodal and share is not None and share < 2 / 3,
        "not_evaluable_partition": status == "not_evaluable",
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    count = lambda field: sum(bool(row.get(field)) for row in rows)
    multimodal = count("supported_multimodal")
    strong = count("strong_persistent_split")
    severe = count("severe_persistent_split")
    not_evaluable = count("not_evaluable_partition")
    return {
        "task_count": n,
        "supported_multimodal_count": multimodal,
        "supported_multimodal_rate": multimodal / n if n else None,
        "strong_persistent_split_count": strong,
        "strong_persistent_split_rate": strong / n if n else None,
        "severe_persistent_split_count": severe,
        "severe_persistent_split_rate": severe / n if n else None,
        "not_evaluable_count": not_evaluable,
        "not_evaluable_rate": not_evaluable / n if n else None,
        "strong_persistent_lower_bound": strong / n if n else None,
        "strong_persistent_upper_bound_if_all_not_evaluable": (strong + not_evaluable) / n if n else None,
    }


def robustness_rows(task_rows: list[dict[str, Any]], thresholds: Iterable[float]) -> list[dict[str, Any]]:
    expected = set(float(value) for value in thresholds)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        groups[(row["stage"], row["scenario"], row["base_task_id"])].append(row)
    output = []
    for (stage, scenario, task), rows in sorted(groups.items()):
        observed = {float(row["similarity_threshold"]) for row in rows}
        if observed != expected:
            raise AssertionError(f"threshold support drifted for {stage}/{scenario}/{task}")
        output.append({
            "stage": stage,
            "scenario": scenario,
            "base_task_id": task,
            "building_id": rows[0]["building_id"],
            "support_band": rows[0]["support_band"],
            "valid_k": rows[0]["valid_k"],
            "thresholds": ";".join(f"{value:g}" for value in sorted(expected)),
            "supported_multimodal_at_all_thresholds": all(row["supported_multimodal"] for row in rows),
            "supported_multimodal_at_any_threshold": any(row["supported_multimodal"] for row in rows),
            "strong_at_all_thresholds": all(row["strong_persistent_split"] for row in rows),
            "strong_at_any_threshold": any(row["strong_persistent_split"] for row in rows),
            "not_evaluable_at_any_threshold": any(row["not_evaluable_partition"] for row in rows),
            "status": "development_threshold_robustness",
        })
    return output


def _robustness_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["stage"], row["scenario"], row["support_band"])].append(row)
        groups[(row["stage"], row["scenario"], "all_k_ge_5")].append(row)
    output = []
    for (stage, scenario, band), values in sorted(groups.items()):
        n = len(values)
        count = lambda field: sum(bool(row[field]) for row in values)
        output.append({
            "stage": stage,
            "scenario": scenario,
            "support_band": band,
            "task_count": n,
            "strong_at_all_thresholds_count": count("strong_at_all_thresholds"),
            "strong_at_all_thresholds_rate": count("strong_at_all_thresholds") / n,
            "strong_at_any_threshold_count": count("strong_at_any_threshold"),
            "strong_at_any_threshold_rate": count("strong_at_any_threshold") / n,
            "not_evaluable_at_any_threshold_count": count("not_evaluable_at_any_threshold"),
            "not_evaluable_at_any_threshold_rate": count("not_evaluable_at_any_threshold") / n,
            "status": "development_threshold_robustness",
        })
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _support_band(k: int) -> str:
    return "cap5_only" if k == 5 else "high_support_k_ge_20" if k >= 20 else "intermediate_k6_to_19"


def _cluster(candidates: list[dict[str, Any]], task: str, threshold: float) -> dict[str, Any]:
    return cluster_geometry_records(
        candidates,
        min_q_boundary=threshold,
        min_q_wallwall=threshold,
        base_task_id=task,
        condition="manual",
        minimum_valid_k=3,
        pairwise_fn=topology._pairwise_metric,
    )


def _task_row(stage: str, scenario: str, task: str, threshold: float, cluster: dict[str, Any]) -> dict[str, Any]:
    k = int(cluster.get("valid_k") or 0)
    return {
        "stage": stage,
        "scenario": scenario,
        "base_task_id": task,
        "building_id": task.split("_", 1)[0],
        "similarity_threshold": threshold,
        "valid_k": k,
        "support_band": _support_band(k),
        "partition_status": cluster.get("partition_status", ""),
        "cluster_count": cluster.get("cluster_count", ""),
        "largest_cluster_support": cluster.get("largest_cluster_support", ""),
        "second_cluster_support": cluster.get("second_cluster_support", ""),
        "largest_cluster_share": cluster.get("largest_cluster_share", ""),
        "second_cluster_share": cluster.get("second_cluster_share", ""),
        "cluster_margin_all": cluster.get("cluster_margin_all", ""),
        "cluster_margin_top2": cluster.get("cluster_margin_top2", ""),
        "task_crowd_structure_status": cluster.get("task_crowd_structure_status", ""),
        "structure_reason": cluster.get("structure_reason", ""),
        **classify_persistence(cluster),
        "interpretation": "finite_full_support_development_diagnostic",
    }


def _attach_pair_cache(candidates: list[dict[str, Any]]) -> None:
    valid = [row for row in candidates if row["replay_geometry_admissible"]]
    cache = {int(row["worker_id"]): {} for row in valid}
    for index, left in enumerate(valid):
        for right in valid[index + 1 :]:
            metric = topology._pairwise_metric(left["_geometry"], right["_geometry"])
            cache[int(left["worker_id"])][int(right["worker_id"])] = metric
            cache[int(right["worker_id"])][int(left["worker_id"])] = metric
    for row in valid:
        row["_geometry"]["_frozen_pairwise_by_worker"] = cache[int(row["worker_id"])]


def _prescreen_rows(root: Path, thresholds: Iterable[float]) -> tuple[list[dict[str, Any]], list[Path]]:
    data = prescreen.prepare(root, prescreen.DEFAULT_INPUT)
    source = [row for row in data["manual"] if row["_scope"] == "in_scope"]
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source:
        parsed = dict(row["_normalized"], worker_id=row["_worker"])
        by_task[row["_image"]].append({
            "canonical_annotation_id": row["canonical_annotation_id"],
            "base_task_id": row["_image"],
            "worker_id": row["_worker"],
            "project_id": row["project_id"],
            "c1_eligible": row["_c1_eligible"],
            "geometry_metric_evaluable": row["_normalizer_valid"],
            "replay_geometry_admissible": row["_normalizer_valid"],
            "structurally_valid": row["_normalizer_valid"],
            "_geometry": parsed,
        })
    for candidates in by_task.values():
        _attach_pair_cache(candidates)

    filters = {
        "c1_eligible_combined": lambda row: row["c1_eligible"],
        "c1_eligible_chinese": lambda row: row["c1_eligible"] and row["project_id"] == "28",
        "c1_eligible_english": lambda row: row["c1_eligible"] and row["project_id"] == "39",
        "current20_combined": lambda row: int(row["worker_id"]) in topology.LIVE_WORKERS,
        "c1_eligible_excluding_copy_risk": lambda row: row["c1_eligible"] and int(row["worker_id"]) not in prescreen.COPY_RISK_WORKERS,
    }
    output = []
    for scenario, keep in filters.items():
        for task, candidates in sorted(by_task.items()):
            admitted = [row for row in candidates if keep(row) and row["replay_geometry_admissible"]]
            if len(admitted) < 5:
                continue
            for threshold in thresholds:
                output.append(_task_row("PreScreen", scenario, task, threshold, _cluster(admitted, task, threshold)))
    return output, data["inputs"]


def _calibration_rows(root: Path, thresholds: Iterable[float]) -> tuple[list[dict[str, Any]], list[Path]]:
    data = topology.load_frozen_inputs(root)
    structure_path = topology.c1_root(root) / "geometry_task_crowd_structure_C1.csv"
    formal = {
        row["base_task_id"]: row for row in _read_csv(structure_path)
        if row.get("condition") == "manual" and int(float(row.get("valid_k") or 0)) >= 5
    }
    output = []
    scenarios = {
        "frozen_geometry_pool": data["historical_candidates"],
        "current20_frozen_geometry_pool": {
            task: [row for row in candidates if int(row["worker_id"]) in topology.LIVE_WORKERS]
            for task, candidates in data["historical_candidates"].items()
        },
    }
    for scenario, tasks in scenarios.items():
        for task, candidates in sorted(tasks.items()):
            admitted = [row for row in candidates if row.get("historical_replay_admitted")]
            if len(admitted) < 5:
                continue
            for threshold in thresholds:
                cluster = _cluster(admitted, task, threshold)
                output.append(_task_row("Calibration", scenario, task, threshold, cluster))
                if scenario == "frozen_geometry_pool" and abs(threshold - 0.95) < 1e-12:
                    expected = formal[task]
                    observed = (
                        int(cluster["valid_k"]), str(cluster["task_crowd_structure_status"]),
                        int(cluster.get("largest_cluster_support") or 0), int(cluster.get("second_cluster_support") or 0),
                    )
                    declared = (
                        int(float(expected["valid_k"])), expected["task_crowd_structure_status"],
                        int(float(expected.get("largest_cluster_support") or 0)), int(float(expected.get("second_cluster_support") or 0)),
                    )
                    if observed != declared:
                        raise AssertionError(f"frozen C1 full-support clustering drifted for {task}: {observed} != {declared}")
    if len(formal) != 78:
        raise AssertionError("frozen C1 high-k denominator drifted")
    return output, [structure_path]


def _summary_rows(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, float, str], list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        key = (row["stage"], row["scenario"], float(row["similarity_threshold"]), row["support_band"])
        groups[key].append(row)
        groups[(key[0], key[1], key[2], "all_k_ge_5")].append(row)
    output = []
    for (stage, scenario, threshold, band), rows in sorted(groups.items()):
        output.append({
            "stage": stage,
            "scenario": scenario,
            "similarity_threshold": threshold,
            "support_band": band,
            "min_valid_k": min(row["valid_k"] for row in rows),
            "max_valid_k": max(row["valid_k"] for row in rows),
            **summarize(rows),
            "inference_unit": "base_task_id",
            "status": "development_descriptive_only",
        })
    return output


def _report(task_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], robustness_summary: list[dict[str, Any]]) -> str:
    index = {(row["stage"], row["scenario"], row["similarity_threshold"], row["support_band"]): row for row in summary_rows}
    cal = index[("Calibration", "frozen_geometry_pool", 0.95, "high_support_k_ge_20")]
    cap5 = index[("Calibration", "frozen_geometry_pool", 0.95, "cap5_only")]
    pre = index[("PreScreen", "c1_eligible_combined", 0.95, "high_support_k_ge_20")]
    combined = [
        row for row in task_rows
        if row["similarity_threshold"] == 0.95 and row["support_band"] == "high_support_k_ge_20"
        and ((row["stage"], row["scenario"]) in {
            ("Calibration", "frozen_geometry_pool"), ("PreScreen", "c1_eligible_combined")
        })
    ]
    total = summarize(combined)
    robust_index = {(row["stage"], row["scenario"], row["support_band"]): row for row in robustness_summary}
    pre_robust = robust_index[("PreScreen", "c1_eligible_combined", "high_support_k_ge_20")]
    cal_robust = robust_index[("Calibration", "frozen_geometry_pool", "high_support_k_ge_20")]
    robust_total = pre_robust["strong_at_all_thresholds_count"] + cal_robust["strong_at_all_thresholds_count"]
    return f"""# Persistent disagreement diagnostic v1

Development-only, task-level description. “Persistent” means disagreement remains at the largest observed eligible support; it does not mean infinitely many additional workers could never resolve the task.

## Formal 0.95 geometry threshold

- PreScreen C1-eligible combined: {pre['task_count']} tasks, k={pre['min_valid_k']}–{pre['max_valid_k']}; supported multimodal {pre['supported_multimodal_count']}/{pre['task_count']} ({pre['supported_multimodal_rate']:.1%}), strong persistent split {pre['strong_persistent_split_count']}/{pre['task_count']} ({pre['strong_persistent_split_rate']:.1%}), non-evaluable partition {pre['not_evaluable_count']}/{pre['task_count']} ({pre['not_evaluable_rate']:.1%}).
- Calibration high-support subset: {cal['task_count']} tasks, k={cal['min_valid_k']}–{cal['max_valid_k']}; supported multimodal {cal['supported_multimodal_count']}/{cal['task_count']} ({cal['supported_multimodal_rate']:.1%}), strong persistent split {cal['strong_persistent_split_count']}/{cal['task_count']} ({cal['strong_persistent_split_rate']:.1%}), non-evaluable partition {cal['not_evaluable_count']}/{cal['task_count']} ({cal['not_evaluable_rate']:.1%}).
- Stage-stratified descriptive total: {total['task_count']} disjoint tasks; strong persistent lower bound {total['strong_persistent_lower_bound']:.1%}, upper bound if every non-evaluable partition were persistent {total['strong_persistent_upper_bound_if_all_not_evaluable']:.1%}.
- Threshold-robust subset: PreScreen {pre_robust['strong_at_all_thresholds_count']}/{pre_robust['task_count']}, Calibration {cal_robust['strong_at_all_thresholds_count']}/{cal_robust['task_count']}; combined {robust_total}/{total['task_count']} ({robust_total / total['task_count']:.1%}) remain strong splits at all three thresholds.
- Calibration cap-5-only subset: {cap5['task_count']} tasks. Its {cap5['strong_persistent_split_count']} strong splits are “unresolved at five,” not evidence that additional workers would fail to resolve them.

## Definitions

- `supported_multimodal`: frozen complete-link geometry partition has a second cluster with support at least two.
- `strong_persistent_split`: supported multimodal and the largest cluster contains less than 80% of the full eligible support. The 80% boundary is a proportional diagnostic derived from the existing 4:1 k=5 rule; it is not a new formal stop rule.
- `severe_persistent_split`: supported multimodal and the largest cluster contains less than two thirds of support; sensitivity only.
- `not_evaluable_partition`: the frozen complete-link partition is non-unique or otherwise not evaluable. It is uncertainty, not silently counted as either resolved or persistent.

Thresholds 0.90 and 0.925 are reported as lenient clustering sensitivities. PreScreen and Calibration remain separate strata because they have different recruitment/selection roles and overlapping buildings.

No protocol, worker profile, routing policy, or Main-launch state is changed.
"""


def run(root: Path, output_dir: Path, thresholds: Iterable[float] = DEFAULT_THRESHOLDS) -> dict[str, Any]:
    thresholds = tuple(sorted(set(float(value) for value in thresholds)))
    if not thresholds or any(value <= 0 or value > 1 for value in thresholds):
        raise ValueError("similarity thresholds must be in (0, 1]")
    if output_dir.exists():
        raise ValueError(f"output directory already exists: {output_dir}")
    calibration, calibration_inputs = _calibration_rows(root, thresholds)
    pre, prescreen_inputs = _prescreen_rows(root, thresholds)
    task_rows = calibration + pre
    summary_rows = _summary_rows(task_rows)
    robust_rows = robustness_rows(task_rows, thresholds)
    robust_summary = _robustness_summary(robust_rows)
    output_dir.mkdir(parents=True)
    task_path = output_dir / "PERSISTENT_DISAGREEMENT_TASKS.csv"
    summary_path = output_dir / "PERSISTENT_DISAGREEMENT_SUMMARY.csv"
    robust_path = output_dir / "PERSISTENT_DISAGREEMENT_THRESHOLD_ROBUSTNESS.csv"
    robust_summary_path = output_dir / "PERSISTENT_DISAGREEMENT_THRESHOLD_ROBUSTNESS_SUMMARY.csv"
    report_path = output_dir / "PERSISTENT_DISAGREEMENT_REPORT.md"
    _write_csv(task_path, task_rows)
    _write_csv(summary_path, summary_rows)
    _write_csv(robust_path, robust_rows)
    _write_csv(robust_summary_path, robust_summary)
    report_path.write_text(_report(task_rows, summary_rows, robust_summary), encoding="utf-8", newline="\n")
    inputs = list(dict.fromkeys([*calibration_inputs, *prescreen_inputs]))
    manifest = {
        "schema_version": "persistent_disagreement_diagnostic_v1",
        "development_only": True,
        "diagnostic_pre_stage3": True,
        "scientific_conclusion_prohibited": True,
        "formal_policy_frozen": False,
        "main_launch_authorized": False,
        "inference_unit": "base_task_id",
        "stage_pooling": "reported_separately; disjoint-task total descriptive only",
        "thresholds": list(thresholds),
        "input_sha256": {str(path.relative_to(root)): _sha256(path) for path in inputs},
        "code_sha256": _sha256(Path(__file__)),
        "output_sha256": {path.name: _sha256(path) for path in (task_path, summary_path, robust_path, robust_summary_path, report_path)},
        "statistical_guard": "pass_replay_is_development_only_missing_not_evaluable_not_recoded",
    }
    manifest_path = output_dir / "analysis_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, action="append")
    args = parser.parse_args()
    run(ROOT, args.output_dir, args.threshold or DEFAULT_THRESHOLDS)


if __name__ == "__main__":
    main()
