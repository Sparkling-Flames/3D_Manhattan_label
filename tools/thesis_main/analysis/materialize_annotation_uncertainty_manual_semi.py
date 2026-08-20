"""C1 Manual/Semi-Auto uncertainty diagnostic with exhaustive equal-k reclustering."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib
import numpy as np
import pandas as pd
from scipy import stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records


C1_ROOT = ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
DEFAULT_OUTPUT = ROOT / "analysis_results/annotation_uncertainty_manual_semi_20260820_v2"
SEED = 20260820
THRESHOLDS = (0.93, 0.95, 0.97)
PRIMARY_THRESHOLD = 0.95
EXPECTED_HEAD = "59e697aa8dcc3d3c037ccfa6c5da47c102608c48"
CORRECTED_TASK_ID = "yqstnuAEVhm_08e2145b15fc4d2497c084af41dc7089"
BAD_TASK_ID = "yqstnuAEVhm_08e0f49a89c34f82b23d5f46bb930b5c"
METRICS = (
    "shannon_entropy",
    "gini_simpson",
    "largest_mode_share",
    "supported_multimodality",
    "mode_count",
    "pairwise_disagreement",
)


INPUTS = {
    "canonical_geometry": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_canonical_geometry.jsonl",
        1_891_449,
        "d3054e9c1fb9869a8a0a7ad114de16e6c30952ab4948261cfac58df25ef82799",
        ("base_task_id", "condition", "worker_id"),
    ),
    "canonical_annotations": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_canonical_annotations.csv",
        845_213,
        "c6160151a1be468d16f83bb4397e7d09f8e8d43a2ce8725d35bb19d5c1bea724",
        ("base_task_id", "condition", "worker_id", "canonical_annotation_id"),
    ),
    "pairwise_geometry": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/geometry_pairwise_similarity_C1.csv",
        3_115_238,
        "997860626fdf50ea5667986a8f04df0183c8f78f617c49fd5682394c7092f1a7",
        ("base_task_id", "condition", "worker_id_left", "worker_id_right", "q_boundary", "q_wallwall"),
    ),
    "crowd_structure": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/geometry_task_crowd_structure_C1.csv",
        103_147,
        "5aa04db57efd9606a27d94d7718a62df52302854d5bc5de7d89d5edca0c2f090",
        ("base_task_id", "condition", "valid_k", "cluster_membership_json"),
    ),
    "building_binding": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_building_binding.csv",
        15_853,
        "e95af0b12db496ad3f1cfdf4e6edef22597f550a51822a3a95103f0dc44cfa4b",
        ("base_task_id", "building_id", "binding_status"),
    ),
    "gt_quality": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_gt_quality_evidence.csv",
        395_269,
        "7b32a7f4a273b26064c3308368cef45aa2c71efb8bde390abf75a92634a3da3a",
        ("base_task_id", "condition", "iou_to_gt", "gt_primary_analysis_eligible"),
    ),
    "evidence_freeze": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_evidence_freeze_manifest.json",
        8_128,
        "9ca7fee87cd07b2cdb4193a2c11916595b72409c6517e959c8f9ec206dc3a248",
        ("schema_version", "C1_EVIDENCE_FROZEN", "dependencies"),
    ),
    "assignment_manual": (
        "analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv",
        99_958,
        "2953929d2ded1e7600fc35c46f805d8c61fdbe76a98a9f218e1777b141cfaa52",
        ("base_task_id", "worker_id", "round_id"),
    ),
    "assignment_semi": (
        "analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv",
        16_844,
        "82c9a778c8852adf55cb27b3dff75b673668d75c83a7e9b87718f69ffb3abbc9",
        ("base_task_id", "worker_id", "round_id"),
    ),
    "assignment_overlap_audit": (
        "analysis_results/calibration_rebuild_20260702/manual_semi_same_image_overlap_audit_v3_1.csv",
        6_440,
        "6b7eaa93ca27ad2b60f33da1438bb1609ad913e11053415cbfc95eb08da7fd95",
        ("base_task_id", "worker_id", "manual_semi_same_image_overlap"),
    ),
    "legacy_difficulty": (
        "analysis_results/calibration_rebuild_20260702/calibration_core_draft_v3_1.csv",
        65_239,
        "3d55e9d71aa594fae85843020c97a7ea47deee05307b813a0371151854c20874",
        ("base_task_id", "gt_pair_count", "old_manual_difficulty_raw", "proxy_confidence"),
    ),
    "semi_review": (
        "analysis_results/paper_a_data_mining_package_20260820_v1/curated/semi_review_fact.csv",
        579_521,
        "bd9523c917aada4a4026a7cf49ab28ba7d9b5199c6f72ebdb610c2d1a92390cf",
        ("stage", "base_task_id", "analysis_eligible", "initialization_artifact_id", "U_initial"),
    ),
    "raw_annotation": (
        "analysis_results/paper_a_data_mining_package_20260820_v1/curated/raw_annotation_fact.csv",
        24_647_192,
        "ebb2a89181479188a9ee289c389369e5f4f743e27c927b197dd8d11d01d84415",
        ("stage", "base_task_id", "condition", "worker_id", "result_json"),
    ),
    "legacy_association_matrix": (
        "analysis_results/paper_a_data_mining_package_20260820_v1/curated/association_matrix.csv",
        8_655,
        "f87c9ab65a02e3643ed1e56fa34a03752fe64cfd55c5d1889a76a4eecb29a308",
        ("analysis_lane", "predictor", "outcome", "population", "support", "p"),
    ),
    "prescreen_profile": (
        "analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_r0_snapshot.csv",
        8_969,
        "68dde2b5f4ebf09515956e0e99198b43107e223e84795e875c4f0c9383955c35",
        ("worker_id", "admission_status", "r_u_0"),
    ),
    "preassignment_feature_manifest": (
        "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_feature_candidate_manifest.json",
        2_572,
        "53babcd5fa88adb71b547db41941838472f9287e3774e91653a7b2bd06e00e86",
        ("schema_version", "formal_ready", "candidate_only"),
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "passed", "valid", "eligible", "matched"}


def norm_worker(value: Any) -> str:
    text = str(value).strip().upper()
    if text.startswith("W"):
        text = text[1:]
    return str(int(text)) if text.isdigit() else text


def clean_condition(value: Any) -> str:
    return "semi" if "semi" in str(value).lower() else "manual" if "manual" in str(value).lower() else str(value).lower()


def write_csv(path: Path, rows: pd.DataFrame | Iterable[dict[str, Any]]) -> None:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n").encode("utf-8"))


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(type(value).__name__)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def validate_source_branch() -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_HEAD, "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"analysis branch does not descend from frozen source HEAD {EXPECTED_HEAD}")


def _schema(path: Path, required: Sequence[str]) -> tuple[int, str]:
    if path.suffix == ".csv":
        frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
        missing = sorted(set(required) - set(frame.columns))
        if missing:
            raise AssertionError(f"{path}: missing columns {missing}")
        versions = []
        for column in ("schema_version", "rule_version", "manifest_version"):
            if column in frame:
                versions.append(f"{column}={'|'.join(sorted(frame[column].dropna().astype(str).unique()))}")
        return len(frame), ";".join(versions) or "csv_columns_validated"
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        missing = sorted(set(required) - set(rows[0])) if rows else list(required)
        if missing:
            raise AssertionError(f"{path}: missing fields {missing}")
        return len(rows), "jsonl_fields_validated"
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    missing = sorted(set(required) - set(value))
    if missing:
        raise AssertionError(f"{path}: missing fields {missing}")
    return 1, str(value.get("schema_version", "json_fields_validated"))


def validate_inputs() -> pd.DataFrame:
    rows = []
    for role, (relative, expected_size, expected_sha, required) in INPUTS.items():
        path = ROOT / relative
        if not path.is_file():
            raise AssertionError(f"missing frozen input: {relative}")
        actual_size, actual_sha = path.stat().st_size, sha256(path)
        if (actual_size, actual_sha) != (expected_size, expected_sha):
            raise AssertionError(f"frozen input drift: {relative}")
        record_count, schema = _schema(path, required)
        rows.append({
            "role": role,
            "path": relative,
            "size_bytes": actual_size,
            "sha256": actual_sha,
            "expected_size_bytes": expected_size,
            "expected_sha256": expected_sha,
            "record_count": record_count,
            "schema_observed": schema,
            "status": "pass",
        })
    return pd.DataFrame(rows)


def read(role: str, **kwargs: Any) -> pd.DataFrame:
    path = ROOT / INPUTS[role][0]
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)


def sample_and_pairs() -> tuple[list[str], dict[str, str], pd.DataFrame, dict[tuple[str, str], list[str]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    crowd = read("crowd_structure")
    crowd["condition"] = crowd["condition"].map(clean_condition)
    manual = set(crowd.loc[crowd["condition"].eq("manual"), "base_task_id"])
    semi = set(crowd.loc[crowd["condition"].eq("semi"), "base_task_id"])
    tasks = sorted(manual & semi)
    eligible_semi = read("semi_review")
    eligible_semi = eligible_semi[
        eligible_semi["stage"].eq("C1") & eligible_semi["analysis_eligible"].map(truth)
    ]
    if set(tasks) != set(eligible_semi["base_task_id"]):
        raise AssertionError("crowd/semi-review formal sample mismatch")
    binding = read("building_binding")
    binding = binding[binding["base_task_id"].isin(tasks)]
    if binding.groupby("base_task_id")["building_id"].nunique().max() != 1:
        raise AssertionError("non-unique task-building binding")
    buildings = binding.drop_duplicates("base_task_id").set_index("base_task_id")["building_id"].astype(str).to_dict()
    if len(tasks) != 22 or len(set(buildings.values())) != 9:
        raise AssertionError("formal design drift: expected 22 tasks and 9 buildings")
    if CORRECTED_TASK_ID not in tasks or BAD_TASK_ID in tasks:
        raise AssertionError("formal task-id correction drift")

    pairwise = read("pairwise_geometry")
    pairwise["condition"] = pairwise["condition"].map(clean_condition)
    pairwise = pairwise[pairwise["base_task_id"].isin(tasks)].copy()
    nodes: dict[tuple[str, str], set[str]] = {}
    pair_map: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in pairwise.itertuples(index=False):
        task, condition = str(row.base_task_id), str(row.condition)
        left, right = norm_worker(row.worker_id_left), norm_worker(row.worker_id_right)
        nodes.setdefault((task, condition), set()).update((left, right))
        pair_map[(task, condition, *sorted((left, right)))] = {
            "q_boundary": float(row.q_boundary) if pd.notna(row.q_boundary) else None,
            "q_wallwall": float(row.q_wallwall) if pd.notna(row.q_wallwall) else None,
            "metric_compatible": truth(row.metric_compatible),
            "correspondence": truth(row.pointwise_correspondence_compatible),
        }
    final_nodes = {key: sorted(value) for key, value in nodes.items()}
    support = [
        (len(final_nodes[task, "manual"]), len(final_nodes[task, "semi"]))
        for task in tasks
    ]
    if support.count((5, 4)) != 21 or support.count((5, 3)) != 1:
        raise AssertionError(f"formal support drift: {support}")
    return tasks, buildings, crowd, final_nodes, pair_map


def _partition_metrics(result: dict[str, Any]) -> dict[str, float | None]:
    if result["partition_status"] != "unique":
        return {metric: None for metric in METRICS if metric != "pairwise_disagreement"}
    clusters = json.loads(result["cluster_membership_json"])
    sizes = np.asarray([len(group) for group in clusters if group], dtype=float)
    shares = sizes / sizes.sum()
    return {
        "shannon_entropy": float(-(shares * np.log(shares)).sum()),
        "gini_simpson": float(1.0 - np.square(shares).sum()),
        "largest_mode_share": float(shares.max()),
        "supported_multimodality": float(result["task_crowd_structure_status"] == "supported_multimodal"),
        "mode_count": float(len(sizes)),
    }


def recluster_subset(task: str, condition: str, workers: Sequence[str], threshold: float, pair_map: dict[tuple[str, str, str, str], dict[str, Any]]) -> dict[str, Any]:
    workers = tuple(sorted(workers))
    records = [
        {"canonical_annotation_id": f"{task}:{condition}:{worker}", "worker_id": worker, "_geometry": {"valid": True, "node_id": worker}}
        for worker in workers
    ]

    def pairwise_fn(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        item = pair_map.get((task, condition, *sorted((str(left["node_id"]), str(right["node_id"])))))
        if not item:
            return {"metric_compatible": False, "pointwise_correspondence_compatible": False, "q_boundary": None, "q_wallwall": None}
        return {
            "metric_compatible": item["metric_compatible"],
            "pointwise_correspondence_compatible": item["correspondence"],
            "q_boundary": item["q_boundary"],
            "q_wallwall": item["q_wallwall"],
        }

    result = cluster_geometry_records(
        records,
        min_q_boundary=threshold,
        min_q_wallwall=threshold,
        base_task_id=task,
        condition=condition,
        minimum_valid_k=3,
        pairwise_fn=pairwise_fn,
    )
    eligible_dissimilarities = []
    for left, right in itertools.combinations(workers, 2):
        item = pair_map.get((task, condition, *sorted((left, right))))
        if item and item["metric_compatible"] and item["q_boundary"] is not None and item["q_wallwall"] is not None:
            eligible_dissimilarities.append(1.0 - min(item["q_boundary"], item["q_wallwall"]))
    metrics = _partition_metrics(result)
    metrics["pairwise_disagreement"] = float(np.mean(eligible_dissimilarities)) if eligible_dissimilarities else None
    return {
        "base_task_id": task,
        "condition": condition,
        "threshold": threshold,
        "subset_worker_ids": ";".join(workers),
        "valid_k": len(workers),
        "partition_status": result["partition_status"],
        "task_crowd_structure_status": result["task_crowd_structure_status"],
        "structure_reason": result["structure_reason"],
        "enumeration_truncated": result["enumeration_truncated"],
        "cluster_membership_json": result["cluster_membership_json"],
        "candidate_partitions_json": result["candidate_partitions_json"],
        "pairwise_eligible_count": len(eligible_dissimilarities),
        "included_in_partition_metric_average": result["partition_status"] == "unique",
        **metrics,
    }


def exhaustive_reclustering(tasks: Sequence[str], nodes: dict[tuple[str, str], list[str]], pair_map: dict[tuple[str, str, str, str], dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for threshold in THRESHOLDS:
        for task in tasks:
            common_k = min(len(nodes[task, "manual"]), len(nodes[task, "semi"]))
            for condition in ("manual", "semi"):
                for subset_index, workers in enumerate(itertools.combinations(nodes[task, condition], common_k), 1):
                    row = recluster_subset(task, condition, workers, threshold, pair_map)
                    row["subset_index"] = subset_index
                    row["common_k"] = common_k
                    rows.append(row)
    result = pd.DataFrame(rows).sort_values(["threshold", "base_task_id", "condition", "subset_index"]).reset_index(drop=True)
    if len(result) != 411:
        raise AssertionError(f"exhaustive subset row drift: {len(result)} != 411")
    return result


def aggregate_task_metrics(reclustered: pd.DataFrame, buildings: dict[str, str]) -> pd.DataFrame:
    rows = []
    for (threshold, task), task_group in reclustered.groupby(["threshold", "base_task_id"], sort=True):
        row: dict[str, Any] = {"threshold": threshold, "base_task_id": task, "building_id": buildings[task], "common_k": int(task_group["common_k"].iloc[0])}
        for condition in ("manual", "semi"):
            group = task_group[task_group["condition"].eq(condition)]
            row[f"{condition}_subset_count"] = len(group)
            row[f"{condition}_unique_partition_count"] = int(group["included_in_partition_metric_average"].sum())
            row[f"{condition}_nonunique_or_not_evaluable_count"] = int((~group["included_in_partition_metric_average"]).sum())
            for metric in METRICS:
                values = pd.to_numeric(group[metric], errors="coerce")
                row[f"{condition}_{metric}"] = float(values.mean()) if values.notna().any() else None
        for metric in METRICS:
            manual, semi = row[f"manual_{metric}"], row[f"semi_{metric}"]
            row[f"delta_{metric}"] = semi - manual if manual is not None and semi is not None else None
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["threshold", "base_task_id"]).reset_index(drop=True)


def holm_adjust(values: Sequence[float | None]) -> list[float | None]:
    valid = sorted((float(value), index) for index, value in enumerate(values) if value is not None and math.isfinite(float(value)))
    output: list[float | None] = [None] * len(values)
    running = 0.0
    count = len(valid)
    for rank, (value, index) in enumerate(valid):
        running = max(running, min(1.0, value * (count - rank)))
        output[index] = running
    return output


def exact_sign_flip(values: Sequence[float]) -> float | None:
    x = np.asarray([float(value) for value in values if pd.notna(value)], dtype=float)
    if len(x) < 3:
        return None
    observed = abs(float(x.mean()))
    sums = np.array([0.0])
    for value in x:
        sums = np.concatenate((sums + value, sums - value))
    return float(np.mean(np.abs(sums / len(x)) >= observed - 1e-15))


def clustered_inference(frame: pd.DataFrame, value_column: str, *, bootstrap_replicates: int, seed_offset: int = 0) -> dict[str, Any]:
    data = frame[["building_id", value_column]].dropna().copy()
    if len(data) < 3:
        return {"n_tasks": len(data), "n_buildings": data["building_id"].nunique(), "mean_difference": None, "ci_lower": None, "ci_upper": None, "building_exact_sign_flip_p": None, "task_exact_sign_flip_p_sensitivity": None}
    buildings = sorted(data["building_id"].unique())
    observed = float(data[value_column].mean())
    rng = np.random.default_rng(SEED + seed_offset)
    draws = []
    groups = {building: data.loc[data["building_id"].eq(building), value_column].to_numpy(float) for building in buildings}
    for _ in range(bootstrap_replicates):
        sampled = rng.choice(buildings, len(buildings), replace=True)
        draws.append(float(np.concatenate([groups[building] for building in sampled]).mean()))
    permuted = []
    for mask in range(1 << len(buildings)):
        signed = data[value_column].to_numpy(float).copy()
        for index, building in enumerate(buildings):
            signed[data["building_id"].eq(building).to_numpy()] *= 1.0 if (mask >> index) & 1 else -1.0
        permuted.append(abs(float(signed.mean())))
    return {
        "n_tasks": len(data),
        "n_buildings": len(buildings),
        "mean_difference": observed,
        "ci_lower": float(np.quantile(draws, 0.025)),
        "ci_upper": float(np.quantile(draws, 0.975)),
        "building_exact_sign_flip_p": float(np.mean(np.asarray(permuted) >= abs(observed) - 1e-15)),
        "task_exact_sign_flip_p_sensitivity": exact_sign_flip(data[value_column]),
    }


def threshold_summary(task_metrics: pd.DataFrame, bootstrap_replicates: int) -> pd.DataFrame:
    rows = []
    for threshold in THRESHOLDS:
        subset = task_metrics[task_metrics["threshold"].eq(threshold)]
        current = []
        for metric_index, metric in enumerate(METRICS):
            current.append({
                "threshold": threshold,
                "metric": metric,
                "estimand": "semi_minus_manual_task_equal",
                "primary_metric": threshold == PRIMARY_THRESHOLD and metric == "shannon_entropy",
                "inference_unit": "building_cluster",
                **clustered_inference(subset, f"delta_{metric}", bootstrap_replicates=bootstrap_replicates, seed_offset=int(threshold * 1000) + metric_index),
            })
        adjusted = holm_adjust([row["building_exact_sign_flip_p"] for row in current])
        for row, value in zip(current, adjusted):
            row["holm_adjusted_p_within_threshold"] = value
        rows.extend(current)
    return pd.DataFrame(rows)


def fixed_partition_audit(crowd: pd.DataFrame, tasks: Sequence[str], buildings: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for task in tasks:
        task_rows = crowd[crowd["base_task_id"].eq(task)].set_index("condition")
        semi_clusters = json.loads(task_rows.loc["semi", "cluster_membership_json"])
        common_k = int(task_rows.loc["semi", "valid_k"])
        manual_clusters = json.loads(task_rows.loc["manual", "cluster_membership_json"])
        nodes = [node for cluster in manual_clusters for node in cluster]

        def metrics(clusters: Sequence[Sequence[str]]) -> dict[str, float]:
            sizes = np.asarray([len(cluster) for cluster in clusters if cluster], dtype=float)
            shares = sizes / sizes.sum()
            return {
                "shannon_entropy": float(-(shares * np.log(shares)).sum()),
                "gini_simpson": float(1.0 - np.square(shares).sum()),
                "largest_mode_share": float(shares.max()),
                "supported_multimodality": float(len(sizes) > 1 and sorted(sizes, reverse=True)[1] >= 2),
                "mode_count": float(len(sizes)),
            }

        semi_metrics = metrics(semi_clusters)
        manual_metrics = []
        for subset in itertools.combinations(nodes, common_k):
            keep = set(subset)
            manual_metrics.append(metrics([[node for node in cluster if node in keep] for cluster in manual_clusters]))
        row = {"base_task_id": task, "building_id": buildings[task], "common_k": common_k, "manual_subset_count": len(manual_metrics)}
        for metric in semi_metrics:
            manual = float(np.mean([item[metric] for item in manual_metrics]))
            row[f"manual_{metric}"] = manual
            row[f"semi_{metric}"] = semi_metrics[metric]
            row[f"delta_{metric}"] = semi_metrics[metric] - manual
        rows.append(row)
    tasks_frame = pd.DataFrame(rows)
    summary = []
    for metric in METRICS[:-1]:
        values = tasks_frame[f"delta_{metric}"]
        summary.append({"metric": metric, "mean_difference": float(values.mean()), "task_exact_sign_flip_p": exact_sign_flip(values), "status": "legacy_fixed_partition_audit_only"})
    return tasks_frame, pd.DataFrame(summary)


def assignment_audit(tasks: Sequence[str], nodes: dict[tuple[str, str], list[str]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manual, semi = read("assignment_manual"), read("assignment_semi")
    for frame in (manual, semi):
        frame["worker_id"] = frame["worker_id"].map(norm_worker)
    canonical = read("canonical_annotations")
    canonical["worker_id"] = canonical["worker_id"].map(norm_worker)
    canonical["condition"] = canonical["condition"].map(clean_condition)

    def formally_authorized(task: str, condition: str, workers: set[str]) -> bool:
        if not workers:
            return True
        rows = canonical[
            canonical["base_task_id"].eq(task)
            & canonical["condition"].eq(condition)
            & canonical["worker_id"].isin(workers)
        ]
        return set(rows["worker_id"]) == workers and rows["assigned_expected"].map(truth).all()

    task_rows = []
    for task in tasks:
        planned_manual = set(manual.loc[manual["base_task_id"].eq(task), "worker_id"])
        planned_semi = set(semi.loc[semi["base_task_id"].eq(task), "worker_id"])
        realized_manual, realized_semi = set(nodes[task, "manual"]), set(nodes[task, "semi"])
        manual_outside, semi_outside = realized_manual - planned_manual, realized_semi - planned_semi
        authorization_pass = formally_authorized(task, "manual", manual_outside) and formally_authorized(task, "semi", semi_outside)
        task_rows.append({
            "base_task_id": task,
            "planned_manual_workers": ";".join(sorted(planned_manual)),
            "planned_semi_workers": ";".join(sorted(planned_semi)),
            "planned_overlap_count": len(planned_manual & planned_semi),
            "realized_manual_workers": ";".join(sorted(realized_manual)),
            "realized_semi_workers": ";".join(sorted(realized_semi)),
            "realized_overlap_count": len(realized_manual & realized_semi),
            "manual_realized_outside_base_manifest": ";".join(sorted(manual_outside)),
            "semi_realized_outside_base_manifest": ";".join(sorted(semi_outside)),
            "outside_base_manifest_formally_authorized": authorization_pass,
            "status": "pass" if not (planned_manual & planned_semi or realized_manual & realized_semi) and authorization_pass else "fail",
        })
    task_frame = pd.DataFrame(task_rows)
    if task_frame["planned_overlap_count"].sum() or task_frame["realized_overlap_count"].sum() or not task_frame["status"].eq("pass").all():
        raise AssertionError("formal same-image overlap or unauthorized realized assignment")

    worker_ids = sorted({worker for task in tasks for condition in ("manual", "semi") for worker in nodes[task, condition]})
    load_rows = []
    for worker in worker_ids:
        load_rows.append({
            "worker_id": worker,
            "planned_manual_load": int(((manual["base_task_id"].isin(tasks)) & manual["worker_id"].eq(worker)).sum()),
            "planned_semi_load": int(((semi["base_task_id"].isin(tasks)) & semi["worker_id"].eq(worker)).sum()),
            "realized_manual_load": sum(worker in nodes[task, "manual"] for task in tasks),
            "realized_semi_load": sum(worker in nodes[task, "semi"] for task in tasks),
        })
    loads = pd.DataFrame(load_rows)
    profile = read("prescreen_profile")
    profile["worker_id"] = profile["worker_id"].map(norm_worker)
    slots = []
    for task in tasks:
        for condition in ("manual", "semi"):
            slots.extend({"base_task_id": task, "condition": condition, "worker_id": worker} for worker in nodes[task, condition])
    slots = pd.DataFrame(slots).merge(profile, how="left", on="worker_id")
    profile_rows = []
    for condition, group in slots.groupby("condition", sort=True):
        r_u = pd.to_numeric(group["r_u_0"], errors="coerce")
        profile_rows.append({
            "condition": condition,
            "assignment_slot_count": len(group),
            "unique_worker_count": group["worker_id"].nunique(),
            "prescreen_profile_covered_slots": int(r_u.notna().sum()),
            "r_u_0_mean_slot_weighted": float(r_u.mean()),
            "r_u_0_median_slot_weighted": float(r_u.median()),
            "admission_pass_rate_slot_weighted": float(group["admission_status"].astype(str).str.lower().eq("pass").mean()),
            "interpretation": "descriptive_nonrandom_assignment",
        })
    return task_frame, loads, pd.DataFrame(profile_rows)


def initialization_audit(tasks: Sequence[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    semi = read("semi_review")
    semi = semi[semi["stage"].eq("C1") & semi["analysis_eligible"].map(truth) & semi["base_task_id"].isin(tasks)].copy()
    rows = []
    for task, group in semi.groupby("base_task_id", sort=True):
        cohort_import_unique = group.groupby("language_cohort")["initialization_import_sha256"].nunique(dropna=False)
        row = {
            "base_task_id": task,
            "eligible_rows": len(group),
            "initialization_artifact_id_unique": group["initialization_artifact_id"].nunique(dropna=False),
            "initialization_prediction_sha256_unique": group["initialization_prediction_sha256"].nunique(dropna=False),
            "initial_geometry_hash_unique": group["initial_geometry_hash"].nunique(dropna=False),
            "language_cohort_count": group["language_cohort"].nunique(),
            "max_import_sha256_unique_within_language": int(cohort_import_unique.max()),
        }
        row["status"] = "pass" if all(row[key] == 1 for key in ("initialization_artifact_id_unique", "initialization_prediction_sha256_unique", "initial_geometry_hash_unique", "max_import_sha256_unique_within_language")) else "fail"
        rows.append(row)
    frame = pd.DataFrame(rows)
    if len(frame) != 22 or not frame["status"].eq("pass").all():
        raise AssertionError("Semi initialization is not task/cohort unique")
    mechanism = semi.groupby("base_task_id", as_index=False).agg(
        eligible_rows=("worker_id", "size"),
        U_initial_mean=("U_initial", "mean"),
        U_final_mean=("U_final", "mean"),
        delta_U_mean=("delta_U", "mean"),
        edited_rate=("edited_binary", "mean"),
        improved_rate=("improved_binary", "mean"),
        harmed_rate=("harmed_binary", "mean"),
        geometry_edit_rmse_mean=("geometry_edit_rmse_panorama_diagonal_normalized", "mean"),
    )
    mechanism["status"] = "auxiliary_descriptive_only"
    return frame, mechanism


def quality_auxiliary(tasks: Sequence[str], buildings: dict[str, str], bootstrap_replicates: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    quality = read("gt_quality")
    quality["condition"] = quality["condition"].map(clean_condition)
    quality = quality[quality["base_task_id"].isin(tasks) & quality["gt_primary_analysis_eligible"].map(truth)].copy()
    grouped = quality.groupby(["base_task_id", "condition"])["iou_to_gt"].agg(["size", "mean"]).reset_index()
    means = grouped.pivot(index="base_task_id", columns="condition", values="mean")
    counts = grouped.pivot(index="base_task_id", columns="condition", values="size")
    rows = []
    for task in tasks:
        manual = float(means.loc[task, "manual"]) if task in means.index and "manual" in means else None
        semi = float(means.loc[task, "semi"]) if task in means.index and "semi" in means else None
        rows.append({
            "base_task_id": task,
            "building_id": buildings[task],
            "manual_gt_primary_n": int(counts.loc[task, "manual"]) if task in counts.index and "manual" in counts else 0,
            "semi_gt_primary_n": int(counts.loc[task, "semi"]) if task in counts.index and "semi" in counts else 0,
            "manual_iou_to_gt_mean": manual,
            "semi_iou_to_gt_mean": semi,
            "delta_iou_to_gt": semi - manual if manual is not None and semi is not None else None,
            "eligibility": "gt_primary_analysis_eligible_only",
        })
    frame = pd.DataFrame(rows)
    inference = clustered_inference(frame, "delta_iou_to_gt", bootstrap_replicates=bootstrap_replicates, seed_offset=8000)
    summary = pd.DataFrame([{
        "outcome": "iou_to_gt",
        "status": "auxiliary_gt_primary_only" if inference["n_tasks"] else "not_evaluable_no_semi_gt_primary_rows",
        "legacy_mixed_eligibility_p_0_000145_status": "not_formal_evidence",
        **inference,
    }])
    return frame, summary


def _difficulty_choices(value: Any) -> list[str]:
    try:
        return [choice for item in json.loads(str(value)) if item.get("from_name") == "difficulty" for choice in item.get("value", {}).get("choices", [])]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def difficulty_coverage(tasks: Sequence[str], primary_metrics: pd.DataFrame, nodes: dict[tuple[str, str], list[str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = json.loads((ROOT / INPUTS["preassignment_feature_manifest"][0]).read_text(encoding="utf-8"))
    if truth(manifest.get("formal_ready")):
        raise AssertionError("unexpected formal-ready pre-assignment feature manifest")
    legacy = read("legacy_difficulty").set_index("base_task_id")
    semi = read("semi_review")
    semi = semi[semi["stage"].eq("C1") & semi["analysis_eligible"].map(truth) & semi["base_task_id"].isin(tasks)]
    proposal = semi.groupby("base_task_id")["U_initial"].mean()
    raw = read("raw_annotation", usecols=["stage", "base_task_id", "condition", "worker_id", "canonical_join_status", "result_json"])
    raw["worker_id"] = raw["worker_id"].map(norm_worker)
    raw = raw[raw["stage"].eq("C1") & raw["condition"].map(clean_condition).eq("manual") & raw["base_task_id"].isin(tasks) & raw["canonical_join_status"].map(truth)].copy()
    raw = raw[[row.worker_id in nodes[row.base_task_id, "manual"] for row in raw.itertuples(index=False)]]
    raw["difficulty_choices"] = raw["result_json"].map(_difficulty_choices)
    raw = raw.sort_values(["base_task_id", "worker_id"]).drop_duplicates(["base_task_id", "worker_id"], keep="last")
    votes = raw.groupby("base_task_id")["difficulty_choices"].agg(
        manual_difficulty_vote_rows="size",
        manual_difficulty_nonempty_votes=lambda values: sum(bool(value) for value in values),
        manual_difficulty_choices_json=lambda values: json.dumps(sorted({choice for value in values for choice in value}), ensure_ascii=False),
    )
    delta = primary_metrics.set_index("base_task_id")["delta_shannon_entropy"]
    rows = []
    for task in tasks:
        item = legacy.loc[task]
        rows.append({
            "base_task_id": task,
            "confirmatory_status": "not_evaluable",
            "frozen_preassignment_n_ready": 0,
            "frozen_feature_manifest_formal_ready": False,
            "legacy_difficulty_label": item.get("old_manual_difficulty_raw"),
            "legacy_label_status": item.get("legacy_label_status"),
            "legacy_proxy_confidence": item.get("proxy_confidence"),
            "gt_keypoint_count": item.get("gt_keypoint_count"),
            "gt_pair_count": item.get("gt_pair_count"),
            "manual_difficulty_vote_rows": votes.loc[task, "manual_difficulty_vote_rows"] if task in votes.index else 0,
            "manual_difficulty_nonempty_votes": votes.loc[task, "manual_difficulty_nonempty_votes"] if task in votes.index else 0,
            "manual_difficulty_choices_json": votes.loc[task, "manual_difficulty_choices_json"] if task in votes.index else "[]",
            "proposal_initial_quality_mean": proposal.get(task),
            "delta_shannon_entropy_q095": delta.get(task),
            "analysis_role": "exploratory_uncoupled_proxy_description",
        })
    frame = pd.DataFrame(rows)
    summary = [{
        "proxy": "frozen_preassignment_feature",
        "coverage_tasks": 0,
        "status": "not_evaluable",
        "reason": "formal_ready_false_n_ready_0",
        "spearman_rho_with_delta_entropy": None,
        "p_value": None,
    }]
    for proxy in ("gt_pair_count", "manual_difficulty_nonempty_votes", "proposal_initial_quality_mean"):
        data = frame[[proxy, "delta_shannon_entropy_q095"]].apply(pd.to_numeric, errors="coerce").dropna()
        rho = float(stats.spearmanr(data[proxy], data["delta_shannon_entropy_q095"]).statistic) if len(data) >= 6 and data[proxy].nunique() > 1 else None
        summary.append({"proxy": proxy, "coverage_tasks": len(data), "status": "exploratory_descriptive_only", "reason": "not_algebraically_coupled_to_manual_final_entropy", "spearman_rho_with_delta_entropy": rho, "p_value": None})
    return frame, pd.DataFrame(summary)


def freeze_reference_audit() -> pd.DataFrame:
    manifest = json.loads((ROOT / INPUTS["evidence_freeze"][0]).read_text(encoding="utf-8"))
    rows = []
    for item in manifest["dependencies"]:
        raw_path = str(item.get("path", "")).replace("\\", "/")
        relative = raw_path.split("/analysis_results/", 1)[-1] if "/analysis_results/" in raw_path else raw_path.split("/docs/", 1)[-1] if "/docs/" in raw_path else ""
        if "/analysis_results/" in raw_path:
            path = ROOT / "analysis_results" / relative
        elif "/docs/" in raw_path:
            path = ROOT / "docs" / relative
        else:
            path = Path(raw_path)
        exists = path.is_file()
        actual = sha256(path) if exists else None
        rows.append({"role": item.get("role"), "declared_path": raw_path, "repository_path": path.relative_to(ROOT).as_posix() if exists and path.is_relative_to(ROOT) else "", "declared_sha256": item.get("sha256"), "actual_sha256": actual, "status": "pass" if exists and actual == item.get("sha256") else "missing_or_sha_mismatch"})
    return pd.DataFrame(rows)


def frozen_time_auxiliary(tasks: Sequence[str]) -> pd.DataFrame:
    table = C1_ROOT / "c1_task_worker_active_time.csv"
    manifest = C1_ROOT / "c1_task_worker_active_time.summary.json"
    columns = ["status", "reason", "source_table", "source_table_sha256", "source_manifest", "source_manifest_sha256", "task_count", "eligible_context_count", "lead_time_used"]
    if not table.is_file() or not manifest.is_file():
        return pd.DataFrame([["not_evaluable", "frozen_task_worker_table_or_manifest_missing", table.relative_to(ROOT).as_posix(), None, manifest.relative_to(ROOT).as_posix(), None, 0, 0, False]], columns=columns)
    summary = json.loads(manifest.read_text(encoding="utf-8"))
    table_sha = sha256(table)
    if summary.get("schema_version") != "c1_task_worker_active_time_summary_v1" or summary.get("output_sha256") != table_sha:
        raise AssertionError("frozen C1 task-worker active-time SHA/schema mismatch")
    frame = pd.read_csv(table, encoding="utf-8-sig", low_memory=False)
    if "lead_time" in " ".join(frame.columns).lower():
        raise AssertionError("lead_time field found in frozen task-worker timing table")
    required = {"base_task_id", "condition", "task_worker_active_seconds", "task_worker_time_analysis_eligible"}
    if not required.issubset(frame.columns):
        raise AssertionError("frozen task-worker timing schema drift")
    eligible = frame[frame["base_task_id"].isin(tasks) & frame["task_worker_time_analysis_eligible"].map(truth)]
    return pd.DataFrame([["auxiliary_frozen_active_time", "sha_bound_task_worker_table", table.relative_to(ROOT).as_posix(), table_sha, manifest.relative_to(ROOT).as_posix(), sha256(manifest), eligible["base_task_id"].nunique(), len(eligible), False]], columns=columns)


def plots(task_metrics: pd.DataFrame, summary: pd.DataFrame, output: Path) -> None:
    primary = task_metrics[task_metrics["threshold"].eq(PRIMARY_THRESHOLD)].sort_values("base_task_id")
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ax.scatter(primary["manual_shannon_entropy"], primary["semi_shannon_entropy"], color="#2563eb", alpha=0.85)
    limit = max(primary[["manual_shannon_entropy", "semi_shannon_entropy"]].max()) * 1.05
    ax.plot([0, limit], [0, limit], linestyle="--", color="#6b7280", linewidth=1)
    ax.set(xlabel="Manual equal-k entropy", ylabel="Semi-Auto equal-k entropy", title="C1 task-level entropy, q=.95")
    fig.tight_layout()
    fig.savefig(output / "ENTROPY_PAIRED_Q095.png", dpi=160, metadata={"Software": "matplotlib"})
    plt.close(fig)

    entropy = summary[summary["metric"].eq("shannon_entropy")].sort_values("threshold")
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    ax.errorbar(entropy["threshold"], entropy["mean_difference"], yerr=[entropy["mean_difference"] - entropy["ci_lower"], entropy["ci_upper"] - entropy["mean_difference"]], fmt="o-", color="#0f766e", capsize=4)
    ax.axhline(0, color="#6b7280", linewidth=1)
    ax.set(xlabel="Geometry threshold", ylabel="Semi − Manual entropy", title="Building-cluster bootstrap sensitivity")
    ax.set_xticks(list(THRESHOLDS))
    fig.tight_layout()
    fig.savefig(output / "ENTROPY_THRESHOLD_SENSITIVITY.png", dpi=160, metadata={"Software": "matplotlib"})
    plt.close(fig)


def report(summary: pd.DataFrame, task_metrics: pd.DataFrame, assignment: pd.DataFrame, difficulty_summary: pd.DataFrame, time_aux: pd.DataFrame, fixed_summary: pd.DataFrame, freeze_refs: pd.DataFrame) -> str:
    primary = summary[(summary["threshold"].eq(PRIMARY_THRESHOLD)) & summary["metric"].eq("shannon_entropy")].iloc[0]
    primary_tasks = task_metrics[task_metrics["threshold"].eq(PRIMARY_THRESHOLD)]
    manual_median = primary_tasks["manual_shannon_entropy"].median()
    withdrawn_groups = primary_tasks.groupby(primary_tasks["manual_shannon_entropy"].gt(manual_median))["semi_shannon_entropy"].mean()
    missing_refs = int(freeze_refs["status"].ne("pass").sum())
    lines = [
        "# Manual / Semi-Auto 标注不确定性复核与重算（v2）",
        "",
        "## 最终回答",
        "",
        "- **[可复现事实]** 在 22 个 C1 配对任务中，q=.95 的任务等权 Shannon entropy 差（Semi−Manual）为 "
        f"{primary['mean_difference']:.6f}，9-building 整组 bootstrap 95% CI [{primary['ci_lower']:.6f}, {primary['ci_upper']:.6f}]，"
        f"building exact sign-flip p={primary['building_exact_sign_flip_p']:.6f}。未检出总体不确定性降低。",
        "- **[不可评价]** 该区间不是预设等效性区间，不能证明‘没有降低’或支持等效性。",
        "- **[不可评价]** 冻结 pre-assignment feature manifest 的 `formal_ready=false`、`n_ready=0`；高难度优势目前无法确认。",
        "",
        "## 可复现事实",
        "",
        "- 主样本固定为 22 个任务、9 个 building；21 个公共支持量 k=4，1 个 k=3。完整 equal-k 重聚类共 411 行（q=.93/.95/.97）。",
        f"- q=.95 中非唯一或不可评价的任务-条件子集记录数：{int(primary_tasks['manual_nonunique_or_not_evaluable_count'].sum() + primary_tasks['semi_nonunique_or_not_evaluable_count'].sum())}；这些记录未被静默填值或混入 partition 指标平均。",
        f"- 正式同图跨条件 worker overlap 总数为 {int(assignment['realized_overlap_count'].sum())}。分配是事前确定但不是标准随机试验，结果仅描述关联/差异。",
        "- 主推断按任务等权；置信区间按 building 整组 bootstrap；p 值按 9 个 building exact sign-flip；任务级 exact sign-flip 仅列为敏感性；同阈值多指标采用 Holm 校正。",
        "- 旧固定分区/task-level 结果已从冻结 sidecar 精确重算，仅作为审计基线，不作为 v2 正式结论。",
        "- 旧 `p=0.578` 来自 `association_matrix.csv` 的 `all_observed` C1 IoU 扫描（207 rows、22 support units、overlap denominator=25），不是本 22-task entropy 结论；旧混合 eligibility 的 `p=0.000145` 不作为正式质量证据。",
        f"- 冻结 evidence manifest 的 16 个依赖引用中有 {missing_refs} 个缺失或 SHA 不匹配；直接分析输入 SHA 均通过，但 manifest 闭环不足，因此本包仍是诊断包。",
        "",
        "## 探索性线索",
        "",
        "- 仅保留 legacy difficulty、GT 角点数、Manual-only difficulty 票和 proposal 初始质量等不与 Manual 最终熵代数耦合的描述；不发布显著性 p 值。",
        "- 原先按 Manual 最终熵二分的 high/low 交互已撤回，未进入任何 inferential 输出。",
        f"- 作为撤回理由的复算事实：旧分组中所谓高/低 Manual 熵组的 Semi 熵均值分别为 {withdrawn_groups.get(True):.6f} 与 {withdrawn_groups.get(False):.6f}，未呈现同向分层。该分组不再用于推断。",
        "",
        "## 不可评价与辅助结局",
        "",
        f"- 确认性难度状态：{difficulty_summary.iloc[0]['status']}（{difficulty_summary.iloc[0]['reason']}）。",
        f"- 冻结 active-time 状态：{time_aux.iloc[0]['status']}（{time_aux.iloc[0]['reason']}）；`lead_time_used=false`，未读取 raw event fragment 回填。",
        "- 质量仅使用 `gt_primary_analysis_eligible=true`；Semi 在该正式 eligibility 下为 0 行，因此 Manual/Semi 质量差不可评价。编辑机制与时间均为独立辅助结局。",
        "",
        "## 审计边界",
        "",
        f"- 代码基线 HEAD：`{EXPECTED_HEAD}`。输入逐文件路径、大小、SHA 与 schema 见 `INPUT_MANIFEST.csv`；代码/测试 SHA 见 `analysis_manifest.json`。",
        "- 本报告只给出差异与关联，不作因果解释，不用于冻结 reviewer 画像或筛选专家。",
        "",
        "## 旧固定分区基线摘要",
        "",
        fixed_summary.to_markdown(index=False),
        "",
    ]
    return "\n".join(lines)


def materialize(output: Path, *, bootstrap_replicates: int = 10_000) -> dict[str, Any]:
    validate_source_branch()
    output.mkdir(parents=True, exist_ok=True)
    input_manifest = validate_inputs()
    tasks, buildings, crowd, nodes, pair_map = sample_and_pairs()
    reclustered = exhaustive_reclustering(tasks, nodes, pair_map)
    task_metrics = aggregate_task_metrics(reclustered, buildings)
    summary = threshold_summary(task_metrics, bootstrap_replicates)
    fixed_tasks, fixed_summary = fixed_partition_audit(crowd, tasks, buildings)
    assignment_tasks, assignment_loads, assignment_balance = assignment_audit(tasks, nodes)
    initialization, mechanisms = initialization_audit(tasks)
    quality_tasks, quality_summary = quality_auxiliary(tasks, buildings, bootstrap_replicates)
    primary_metrics = task_metrics[task_metrics["threshold"].eq(PRIMARY_THRESHOLD)]
    difficulty_tasks, difficulty_summary = difficulty_coverage(tasks, primary_metrics, nodes)
    freeze_refs = freeze_reference_audit()
    time_aux = frozen_time_auxiliary(tasks)

    outputs = {
        "INPUT_MANIFEST.csv": input_manifest,
        "TASK_SUBSET_RECLUSTERING.csv": reclustered,
        "TASK_METRICS.csv": task_metrics,
        "THRESHOLD_ROBUSTNESS.csv": summary,
        "LEGACY_FIXED_PARTITION_TASK_AUDIT.csv": fixed_tasks,
        "LEGACY_FIXED_PARTITION_SUMMARY.csv": fixed_summary,
        "ASSIGNMENT_TASK_AUDIT.csv": assignment_tasks,
        "ASSIGNMENT_WORKER_LOAD.csv": assignment_loads,
        "ASSIGNMENT_PROFILE_BALANCE.csv": assignment_balance,
        "SEMI_INITIALIZATION_AUDIT.csv": initialization,
        "MECHANISM_AUXILIARY.csv": mechanisms,
        "QUALITY_AUXILIARY.csv": quality_tasks,
        "QUALITY_AUXILIARY_SUMMARY.csv": quality_summary,
        "DIFFICULTY_PROXY_COVERAGE.csv": difficulty_tasks,
        "DIFFICULTY_PROXY_SUMMARY.csv": difficulty_summary,
        "FREEZE_REFERENCE_AUDIT.csv": freeze_refs,
        "FROZEN_TIME_AUXILIARY.csv": time_aux,
    }
    for name, frame in outputs.items():
        write_csv(output / name, frame)
    plots(task_metrics, summary, output)
    (output / "ANNOTATION_UNCERTAINTY_MANUAL_SEMI_REPORT_ZH.md").write_bytes(
        report(summary, task_metrics, assignment_tasks, difficulty_summary, time_aux, fixed_summary, freeze_refs).encode("utf-8")
    )

    generated = sorted(path for path in output.iterdir() if path.is_file() and path.name not in {"OUTPUT_MANIFEST.csv", "analysis_manifest.json"})
    output_manifest = pd.DataFrame([{"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in generated])
    write_csv(output / "OUTPUT_MANIFEST.csv", output_manifest)
    script = Path(__file__)
    test = ROOT / "tests/test_materialize_annotation_uncertainty_manual_semi.py"
    manifest = {
        "schema_version": "annotation_uncertainty_manual_semi_manifest_v2",
        "rule_version": "annotation_uncertainty_manual_semi_building_cluster_v2",
        "source_branch_base_head": EXPECTED_HEAD,
        "script_path": script.relative_to(ROOT).as_posix(),
        "script_sha256": sha256(script),
        "test_path": test.relative_to(ROOT).as_posix(),
        "test_sha256": sha256(test) if test.is_file() else None,
        "thresholds": list(THRESHOLDS),
        "primary_threshold": PRIMARY_THRESHOLD,
        "bootstrap_seed": SEED,
        "bootstrap_replicates": bootstrap_replicates,
        "task_count": len(tasks),
        "building_count": len(set(buildings.values())),
        "input_manifest_sha256": sha256(output / "INPUT_MANIFEST.csv"),
        "output_manifest_sha256": sha256(output / "OUTPUT_MANIFEST.csv"),
        "active_time_policy": "frozen_c1_task_worker_table_and_sha_manifest_only_no_raw_or_lead_time_fallback",
        "confirmatory_difficulty_status": "not_evaluable",
        "causal_claim_allowed": False,
    }
    write_json(output / "analysis_manifest.json", manifest)
    if any(BAD_TASK_ID in path.read_text(encoding="utf-8", errors="ignore") for path in output.iterdir() if path.suffix in {".csv", ".json", ".md"}):
        raise AssertionError("obsolete task id leaked into v2 outputs")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output_dir.resolve(), bootstrap_replicates=args.bootstrap_replicates), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
