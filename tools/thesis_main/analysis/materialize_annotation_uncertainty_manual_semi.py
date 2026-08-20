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
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry_for_c1_calculation


C1_ROOT = ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
DEFAULT_OUTPUT = ROOT / "analysis_results/annotation_uncertainty_manual_semi_20260820_v2"
SEED = 20260820
THRESHOLDS = (0.93, 0.95, 0.97)
PRIMARY_THRESHOLD = 0.95
EXPECTED_HEAD = "259e96fac31defd60364c865cbfbf2890c9edb05"
CORRECTED_TASK_ID = "yqstnuAEVhm_08e2145b15fc4d2497c084af41dc7089"
BAD_TASK_ID = "yqstnuAEVhm_08e0f49a89c34f82b23d5f46bb930b5c"
PARTITION_METRICS = (
    "shannon_entropy",
    "gini_simpson",
    "largest_mode_share",
    "supported_multimodality",
    "mode_count",
)
PAIRWISE_METRICS = ("pairwise_correspondence_disagreement", "pairwise_metric_dissimilarity_all")
METRICS = (*PARTITION_METRICS, *PAIRWISE_METRICS)


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
    "gt_quality_analysis": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_gt_quality_analysis.csv",
        693_757,
        "68c6d64cad77e09a21e5689d5bc20b26ad6484ba1fd63e1fbf00466ab9b23e5e",
        ("base_task_id", "condition", "iou_to_gt", "gt_primary_analysis_eligible", "semi_correction_analysis_eligible"),
    ),
    "row_eligibility": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_row_analysis_eligibility.csv",
        360_868,
        "09d02115e6320d558d56b84eda9dbd850e4b29759e4708463c5eec9848ca6aaf",
        ("base_task_id", "condition", "worker_id", "formal_assignment_eligible", "scope_eligible"),
    ),
    "scope_final": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_scope_final_disposition.csv",
        41_142,
        "8c79e753e9cdd27ac8c64f0ef74485ffacaeae9616424c6ecd38bfac48ef3734",
        ("base_task_id", "task_final_scope", "worker_scope_direction", "scope_resolution_status"),
    ),
    "active_time_table": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_worker_active_time.csv",
        243_375,
        "4292a464f879423efc82c3ab213d0e77594bf7a0e4bdda3320416f7195d5cb99",
        ("base_task_id", "condition", "worker_id", "task_worker_active_seconds", "task_worker_time_analysis_eligible"),
    ),
    "active_time_manifest": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_worker_active_time.summary.json",
        650,
        "ed0d59259d46d4c6e634d8a5b9e52485caa5c75a95e8f5b1c08dd7c062c83cca",
        ("schema_version", "output_sha256", "eligible_context_count"),
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
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_preannotation_task_features_manifest.json",
        380,
        "4f98b081aef5cefb53c4999b7bcc034ee28c18251d539d058eeda75f6855b54e",
        ("schema_version", "n_tasks", "n_ready", "human_geometry_used"),
    ),
    "preassignment_features": (
        "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_preannotation_task_features.csv",
        17_997,
        "17d2cb16b77681f1c863bc822c2dcef447699b88582e9871ebb84b522794c70f",
        ("base_task_id", "preannotation_feature_ready", "exclusion_reason"),
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
        return {metric: None for metric in PARTITION_METRICS}
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
    metric_dissimilarities = []
    correspondence_dissimilarities = []
    for left, right in itertools.combinations(workers, 2):
        item = pair_map.get((task, condition, *sorted((left, right))))
        if item and item["metric_compatible"] and item["q_boundary"] is not None and item["q_wallwall"] is not None:
            dissimilarity = 1.0 - min(item["q_boundary"], item["q_wallwall"])
            metric_dissimilarities.append(dissimilarity)
            if item["correspondence"]:
                correspondence_dissimilarities.append(dissimilarity)
    metrics = _partition_metrics(result)
    metrics["pairwise_correspondence_disagreement"] = float(np.mean(correspondence_dissimilarities)) if correspondence_dissimilarities else None
    metrics["pairwise_metric_dissimilarity_all"] = float(np.mean(metric_dissimilarities)) if metric_dissimilarities else None
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
        "pairwise_metric_eligible_count": len(metric_dissimilarities),
        "pairwise_correspondence_eligible_count": len(correspondence_dissimilarities),
        "pairwise_correspondence_incompatible_count": len(metric_dissimilarities) - len(correspondence_dissimilarities),
        "included_in_partition_metric_average": result["partition_status"] == "unique",
        **metrics,
    }


def exhaustive_reclustering(
    tasks: Sequence[str],
    nodes: dict[tuple[str, str], list[str]],
    pair_map: dict[tuple[str, str, str, str], dict[str, Any]],
    *,
    expected_rows: int | None = None,
) -> pd.DataFrame:
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
    if expected_rows is not None and len(result) != expected_rows:
        raise AssertionError(f"exhaustive subset row drift: {len(result)} != {expected_rows}")
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
    for metric in PARTITION_METRICS:
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
    quality = read("gt_quality_analysis")
    quality["condition"] = quality["condition"].map(clean_condition)
    quality = quality[quality["base_task_id"].isin(tasks)].copy()
    quality = pd.concat([
        quality[quality["condition"].eq("manual") & quality["gt_primary_analysis_eligible"].map(truth)],
        quality[quality["condition"].eq("semi") & quality["semi_correction_analysis_eligible"].map(truth)],
    ], ignore_index=True)
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
            "semi_correction_n": int(counts.loc[task, "semi"]) if task in counts.index and "semi" in counts else 0,
            "manual_iou_to_gt_mean": manual,
            "semi_iou_to_gt_mean": semi,
            "delta_iou_to_gt": semi - manual if manual is not None and semi is not None else None,
            "manual_eligibility": "gt_primary_analysis_eligible",
            "semi_eligibility": "semi_correction_analysis_eligible",
            "quality_estimand": "condition_specific_auxiliary_same_image_contrast",
        })
    frame = pd.DataFrame(rows)
    inference = clustered_inference(frame, "delta_iou_to_gt", bootstrap_replicates=bootstrap_replicates, seed_offset=8000)
    summary = pd.DataFrame([{
        "outcome": "iou_to_gt",
        "status": "auxiliary_condition_specific_eligibility" if inference["n_tasks"] else "not_evaluable_no_condition_specific_pairs",
        "legacy_mixed_eligibility_p_0_000145_status": "not_formal_evidence",
        **inference,
    }])
    return frame, summary


def quality_data_mining_inclusive(
    all_tasks: Sequence[str],
    planned_tasks: Sequence[str],
    buildings: dict[str, str],
    bootstrap_replicates: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    contexts = read("gt_quality_analysis")
    contexts["condition"] = contexts["condition"].map(clean_condition)
    contexts["worker_id"] = contexts["worker_id"].map(norm_worker)
    contexts["quality_data_mining_included"] = contexts["gt_score_computable"].map(truth) & pd.to_numeric(contexts["iou_to_gt"], errors="coerce").notna()
    contexts["quality_data_mining_role"] = np.where(
        contexts["quality_data_mining_included"],
        "all_computable_including_formally_excluded_workers",
        "not_computable_retained_for_missingness_audit",
    )
    included = contexts[contexts["quality_data_mining_included"]]
    grouped = included.groupby(["base_task_id", "condition"])["iou_to_gt"].agg(["size", "mean"])
    task_rows = []
    for task in sorted(all_tasks):
        row: dict[str, Any] = {"base_task_id": task, "building_id": buildings[task]}
        for condition in ("manual", "semi"):
            key = (task, condition)
            row[f"{condition}_all_computable_n"] = int(grouped.loc[key, "size"]) if key in grouped.index else 0
            row[f"{condition}_all_computable_iou_mean"] = float(grouped.loc[key, "mean"]) if key in grouped.index else None
        manual, semi = row["manual_all_computable_iou_mean"], row["semi_all_computable_iou_mean"]
        row["delta_all_computable_iou"] = semi - manual if manual is not None and semi is not None else None
        row["analysis_role"] = "inclusive_quality_data_mining_not_formal_estimand"
        task_rows.append(row)
    task_metrics = pd.DataFrame(task_rows)
    planned = task_metrics[task_metrics["base_task_id"].isin(planned_tasks)]
    inference = clustered_inference(planned, "delta_all_computable_iou", bootstrap_replicates=bootstrap_replicates, seed_offset=8800)
    summary = pd.DataFrame([{
        "population": "planned_paired_all_computable",
        "status": "primary_data_mining_inclusive_descriptive",
        "eligibility_filter_applied": False,
        **inference,
    }])
    return contexts.sort_values(["base_task_id", "condition", "worker_id"]).reset_index(drop=True), task_metrics, summary


def _difficulty_choices(value: Any) -> list[str]:
    try:
        return [choice for item in json.loads(str(value)) if item.get("from_name") == "difficulty" for choice in item.get("value", {}).get("choices", [])]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def difficulty_coverage(tasks: Sequence[str], primary_metrics: pd.DataFrame, nodes: dict[tuple[str, str], list[str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = json.loads((ROOT / INPUTS["preassignment_feature_manifest"][0]).read_text(encoding="utf-8"))
    n_ready = int(manifest["n_ready"])
    if manifest.get("schema_version") != "paper_a_preannotation_task_features_v1" or n_ready:
        raise AssertionError("unexpected C1 pre-assignment feature manifest")
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
            "frozen_preassignment_n_ready": n_ready,
            "frozen_feature_manifest_schema_version": manifest["schema_version"],
            "frozen_feature_manifest_n_tasks": int(manifest["n_tasks"]),
            "frozen_feature_manifest_human_geometry_used": truth(manifest.get("human_geometry_used")),
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
        "coverage_tasks": n_ready,
        "status": "not_evaluable",
        "reason": "c1_frozen_preassignment_n_ready_0",
        "spearman_rho_with_delta_entropy": None,
        "p_value": None,
    }]
    for proxy in ("gt_pair_count", "manual_difficulty_nonempty_votes", "proposal_initial_quality_mean"):
        data = frame[[proxy, "delta_shannon_entropy_q095"]].apply(pd.to_numeric, errors="coerce").dropna()
        rho = float(stats.spearmanr(data[proxy], data["delta_shannon_entropy_q095"]).statistic) if len(data) >= 6 and data[proxy].nunique() > 1 else None
        status = "not_evaluable_zero_variance" if data[proxy].nunique() <= 1 else "exploratory_descriptive_only"
        reason = "zero_variance" if status.startswith("not_evaluable") else "not_algebraically_coupled_to_manual_final_entropy"
        summary.append({"proxy": proxy, "coverage_tasks": len(data), "status": status, "reason": reason, "spearman_rho_with_delta_entropy": rho, "p_value": None})
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


def active_time_analysis(
    primary_tasks: Sequence[str],
    all_tasks: Sequence[str],
    planned_tasks: Sequence[str],
    buildings: dict[str, str],
    bootstrap_replicates: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    table = ROOT / INPUTS["active_time_table"][0]
    manifest = ROOT / INPUTS["active_time_manifest"][0]
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
    frame["condition"] = frame["condition"].map(clean_condition)
    frame["worker_id"] = frame["worker_id"].map(norm_worker)
    frame["task_worker_time_analysis_eligible"] = frame["task_worker_time_analysis_eligible"].map(truth)
    if len(frame) != 780 or frame["base_task_id"].nunique() != 87:
        raise AssertionError("frozen C1 active-time coverage drift")
    eligible = frame[frame["task_worker_time_analysis_eligible"]]
    if int(summary.get("context_count", -1)) != len(frame) or int(summary.get("eligible_context_count", -1)) != len(eligible):
        raise AssertionError("frozen C1 active-time summary count drift")
    primary_eligible = eligible[eligible["base_task_id"].isin(primary_tasks)]
    audit = pd.DataFrame([{
        "status": "auxiliary_frozen_active_time",
        "reason": "sha_bound_task_worker_table",
        "source_table": table.relative_to(ROOT).as_posix(),
        "source_table_sha256": table_sha,
        "source_manifest": manifest.relative_to(ROOT).as_posix(),
        "source_manifest_sha256": sha256(manifest),
        "task_count": primary_eligible["base_task_id"].nunique(),
        "eligible_context_count": len(primary_eligible),
        "manual_eligible_context_count": int(primary_eligible["condition"].eq("manual").sum()),
        "semi_eligible_context_count": int(primary_eligible["condition"].eq("semi").sum()),
        "lead_time_used": False,
    }])

    grouped = frame.groupby(["base_task_id", "condition"], sort=True)
    task_rows = []
    for task in sorted(all_tasks):
        row: dict[str, Any] = {"base_task_id": task, "building_id": buildings[task]}
        for condition in ("manual", "semi"):
            key = (task, condition)
            group = grouped.get_group(key) if key in grouped.groups else frame.iloc[0:0]
            valid = group[group["task_worker_time_analysis_eligible"]]
            values = pd.to_numeric(valid["task_worker_active_seconds"], errors="coerce").dropna()
            observed = pd.to_numeric(group["task_worker_active_seconds"], errors="coerce").dropna()
            row[f"{condition}_context_count"] = len(group)
            row[f"{condition}_eligible_context_count"] = len(values)
            row[f"{condition}_active_seconds_mean"] = float(values.mean()) if len(values) else None
            row[f"{condition}_active_seconds_median"] = float(values.median()) if len(values) else None
            row[f"{condition}_observed_active_seconds_count"] = len(observed)
            row[f"{condition}_observed_active_seconds_mean"] = float(observed.mean()) if len(observed) else None
            row[f"{condition}_observed_active_seconds_median"] = float(observed.median()) if len(observed) else None
            row[f"{condition}_time_exclusion_reasons"] = ";".join(sorted(set(group.loc[~group["task_worker_time_analysis_eligible"], "timing_exclusion_reason"].dropna().astype(str)) - {""}))
        for statistic in ("mean", "median"):
            manual, semi = row[f"manual_active_seconds_{statistic}"], row[f"semi_active_seconds_{statistic}"]
            row[f"delta_active_seconds_{statistic}"] = semi - manual if manual is not None and semi is not None else None
            observed_manual, observed_semi = row[f"manual_observed_active_seconds_{statistic}"], row[f"semi_observed_active_seconds_{statistic}"]
            row[f"delta_observed_active_seconds_{statistic}"] = observed_semi - observed_manual if observed_manual is not None and observed_semi is not None else None
        task_rows.append(row)
    task_metrics = pd.DataFrame(task_rows)

    summary_rows = []
    populations = {
        "formal_primary_22": (set(primary_tasks), "delta_active_seconds", "protocol_reference_eligible_only"),
        "planned_paired_25": (set(planned_tasks), "delta_observed_active_seconds", "primary_data_mining_inclusive_observed_frozen_time"),
        "oos_paired_3": (set(planned_tasks) - set(primary_tasks), "delta_observed_active_seconds", "exploratory_oos_only"),
    }
    for index, (population, (task_set, column_prefix, role)) in enumerate(populations.items()):
        subset = task_metrics[task_metrics["base_task_id"].isin(task_set)]
        for statistic in ("mean", "median"):
            result = clustered_inference(subset, f"{column_prefix}_{statistic}", bootstrap_replicates=bootstrap_replicates, seed_offset=9000 + index * 10 + (statistic == "median"))
            summary_rows.append({"population": population, "statistic": f"task_worker_{statistic}_seconds", "status": role, "eligibility_filter_applied": column_prefix == "delta_active_seconds", **result})
    return audit, frame.sort_values(["base_task_id", "condition", "worker_id"]).reset_index(drop=True), task_metrics, pd.DataFrame(summary_rows)


def geometry_contexts() -> tuple[pd.DataFrame, list[dict[str, Any]], dict[tuple[str, str], list[str]], dict[tuple[str, str], list[str]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    eligibility = read("gt_quality_analysis")
    eligibility["condition"] = eligibility["condition"].map(clean_condition)
    eligibility["worker_id"] = eligibility["worker_id"].map(norm_worker)
    eligibility_contract = read("row_eligibility")
    eligibility_contract["condition"] = eligibility_contract["condition"].map(clean_condition)
    eligibility_contract["worker_id"] = eligibility_contract["worker_id"].map(norm_worker)
    keys = ["canonical_annotation_id", "base_task_id", "condition", "worker_id"]
    observed_keys = set(map(tuple, eligibility[keys].astype(str).to_numpy()))
    contract_keys = set(map(tuple, eligibility_contract[keys].astype(str).to_numpy()))
    if len(eligibility) != 780 or len(eligibility_contract) != 780 or observed_keys != contract_keys:
        raise AssertionError("quality/eligibility canonical identity drift")
    eligibility_index = eligibility.set_index("canonical_annotation_id")
    contract_index = eligibility_contract.set_index("canonical_annotation_id")
    for column in ("formal_assignment_eligible", "process_eligible", "independence_eligible", "scope_eligible", "geometry_structurally_computable"):
        if not eligibility_index[column].map(truth).equals(contract_index.loc[eligibility_index.index, column].map(truth)):
            raise AssertionError(f"quality/eligibility field drift: {column}")
    geometry_rows = [
        json.loads(line)
        for line in (ROOT / INPUTS["canonical_geometry"][0]).read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    geometry_by_id = {str(row["canonical_annotation_id"]): row for row in geometry_rows}
    if len(geometry_by_id) != len(geometry_rows):
        raise AssertionError("duplicate canonical geometry identity")

    records = []
    normalization_valid = {}
    for row in eligibility.to_dict("records"):
        identity = str(row["canonical_annotation_id"])
        raw = geometry_by_id.get(identity)
        normalized = normalize_geometry_for_c1_calculation(
            raw.get("corners_px") if raw else [],
            width=int(raw.get("width") or 1024) if raw else 1024,
            height=int(raw.get("height") or 512) if raw else 512,
        )
        normalization_valid[identity] = bool(normalized["valid"])
        records.append({
            "canonical_annotation_id": identity,
            "base_task_id": str(row["base_task_id"]),
            "condition": clean_condition(row["condition"]),
            "worker_id": norm_worker(row["worker_id"]),
            "building_id": str(row["building_id"]),
            "formal_assignment_eligible": truth(row["formal_assignment_eligible"]),
            "process_eligible": truth(row["process_eligible"]),
            "independence_eligible": truth(row["independence_eligible"]),
            "scope_eligible": truth(row["scope_eligible"]),
            "geometry_structurally_computable": truth(row["geometry_structurally_computable"]),
            "_geometry": normalized,
        })
    eligibility["geometry_normalization_valid"] = eligibility["canonical_annotation_id"].astype(str).map(normalization_valid).fillna(False)

    all_nodes: dict[tuple[str, str], list[str]] = {}
    gate_without_scope_nodes: dict[tuple[str, str], list[str]] = {}
    pair_map: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        if record["_geometry"]["valid"]:
            grouped.setdefault((record["base_task_id"], record["condition"]), []).append(record)
    for key, group in grouped.items():
        workers = [record["worker_id"] for record in group]
        if len(workers) != len(set(workers)):
            raise AssertionError(f"duplicate worker geometry context: {key}")
        all_nodes[key] = sorted(workers)
        gate_without_scope_nodes[key] = sorted(
            record["worker_id"]
            for record in group
            if record["formal_assignment_eligible"]
            and record["process_eligible"]
            and record["independence_eligible"]
            and record["geometry_structurally_computable"]
        )
        for left, right in itertools.combinations(group, 2):
            item = pairwise_similarity(left["_geometry"], right["_geometry"])
            pair_map[(key[0], key[1], *sorted((left["worker_id"], right["worker_id"])))] = {
                "q_boundary": item.get("q_boundary", item.get("boundary_similarity")),
                "q_wallwall": item.get("q_wallwall", item.get("wallwall_similarity")),
                "metric_compatible": truth(item.get("metric_compatible", True)),
                "correspondence": truth(item.get("pointwise_correspondence_compatible")),
            }
    return eligibility, records, all_nodes, gate_without_scope_nodes, pair_map


def population_sensitivity(
    primary_tasks: Sequence[str],
    planned_tasks: Sequence[str],
    buildings: dict[str, str],
    primary_task_metrics: pd.DataFrame,
    primary_summary: pd.DataFrame,
    formal_nodes: dict[tuple[str, str], list[str]],
    all_nodes: dict[tuple[str, str], list[str]],
    all_pair_map: dict[tuple[str, str, str, str], dict[str, Any]],
    bootstrap_replicates: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    primary_set, planned_set = set(primary_tasks), set(planned_tasks)
    oos_tasks = sorted(planned_set - primary_set)
    if len(oos_tasks) != 3:
        raise AssertionError("paired OOS task count drift")
    for task in primary_tasks:
        for condition in ("manual", "semi"):
            if formal_nodes.get((task, condition), []) != formal_nodes[task, condition]:
                raise AssertionError("formal node lookup drift")

    oos_reclustered = exhaustive_reclustering(oos_tasks, all_nodes, all_pair_map)
    oos_metrics = aggregate_task_metrics(oos_reclustered, buildings)
    formal_plus_oos = pd.concat([primary_task_metrics, oos_metrics], ignore_index=True).sort_values(["threshold", "base_task_id"])
    all_in_scope = aggregate_task_metrics(exhaustive_reclustering(primary_tasks, all_nodes, all_pair_map), buildings)
    all_planned = aggregate_task_metrics(exhaustive_reclustering(planned_tasks, all_nodes, all_pair_map), buildings)

    frames = {
        "formal_primary": (primary_task_metrics.copy(), "protocol_reference_only"),
        "formal_plus_oos_tasks": (formal_plus_oos, "scope_sensitivity"),
        "all_canonical_in_scope": (all_in_scope, "inclusive_worker_sensitivity"),
        "all_canonical_planned": (all_planned, "primary_data_mining_inclusive_descriptive"),
    }
    task_frames = []
    summaries = []
    for population_index, (population, (frame, role)) in enumerate(frames.items()):
        current = frame.copy()
        current.insert(0, "population", population)
        current.insert(1, "inference_role", role)
        task_frames.append(current)
        if population == "formal_primary":
            summary = primary_summary.copy()
        else:
            summary = threshold_summary(frame, bootstrap_replicates)
        summary.insert(0, "population", population)
        summary.insert(1, "inference_role", role)
        summary["primary_metric"] = summary["primary_metric"].map(truth) & (population == "all_canonical_planned")
        summaries.append(summary)
    population_tasks = pd.concat(task_frames, ignore_index=True)
    population_summary = pd.concat(summaries, ignore_index=True)

    impact_rows = []
    metric_index = population_tasks.set_index(["population", "threshold", "base_task_id"])
    for task in sorted(planned_tasks):
        baseline_population = "formal_primary" if task in primary_set else "formal_plus_oos_tasks"
        all_population = "all_canonical_in_scope" if task in primary_set else "all_canonical_planned"
        for threshold in THRESHOLDS:
            baseline = metric_index.loc[baseline_population, threshold, task]
            inclusive = metric_index.loc[all_population, threshold, task]
            formal_manual_n = len(formal_nodes.get((task, "manual"), [])) if task in primary_set else len(all_nodes.get((task, "manual"), []))
            formal_semi_n = len(formal_nodes.get((task, "semi"), [])) if task in primary_set else len(all_nodes.get((task, "semi"), []))
            all_manual_n, all_semi_n = len(all_nodes.get((task, "manual"), [])), len(all_nodes.get((task, "semi"), []))
            impact_rows.append({
                "threshold": threshold,
                "base_task_id": task,
                "building_id": buildings[task],
                "baseline_population": baseline_population,
                "inclusive_population": all_population,
                "formal_manual_valid_k": formal_manual_n,
                "formal_semi_valid_k": formal_semi_n,
                "all_canonical_manual_valid_k": all_manual_n,
                "all_canonical_semi_valid_k": all_semi_n,
                "excluded_context_added_n": all_manual_n + all_semi_n - formal_manual_n - formal_semi_n,
                "baseline_manual_entropy": baseline["manual_shannon_entropy"],
                "inclusive_manual_entropy": inclusive["manual_shannon_entropy"],
                "excluded_context_shift_manual_entropy": inclusive["manual_shannon_entropy"] - baseline["manual_shannon_entropy"],
                "baseline_semi_entropy": baseline["semi_shannon_entropy"],
                "inclusive_semi_entropy": inclusive["semi_shannon_entropy"],
                "excluded_context_shift_semi_entropy": inclusive["semi_shannon_entropy"] - baseline["semi_shannon_entropy"],
                "baseline_delta_entropy": baseline["delta_shannon_entropy"],
                "inclusive_delta_entropy": inclusive["delta_shannon_entropy"],
                "excluded_context_shift_delta_entropy": inclusive["delta_shannon_entropy"] - baseline["delta_shannon_entropy"],
                "analysis_role": "excluded_context_sensitivity_not_primary",
            })
    return population_tasks, population_summary, pd.DataFrame(impact_rows)


def manual_uncertainty_catalog(
    all_tasks: Sequence[str],
    planned_tasks: Sequence[str],
    primary_tasks: Sequence[str],
    scope: pd.DataFrame,
    buildings: dict[str, str],
    all_nodes: dict[tuple[str, str], list[str]],
    gate_without_scope_nodes: dict[tuple[str, str], list[str]],
    pair_map: dict[tuple[str, str, str, str], dict[str, Any]],
) -> pd.DataFrame:
    scope_index = scope.set_index("base_task_id")
    planned_set, primary_set = set(planned_tasks), set(primary_tasks)
    rows = []
    for threshold in THRESHOLDS:
        for task in sorted(all_tasks):
            formal_workers = gate_without_scope_nodes.get((task, "manual"), [])
            all_workers = all_nodes.get((task, "manual"), [])
            formal = recluster_subset(task, "manual", formal_workers, threshold, pair_map) if formal_workers else {}
            inclusive = recluster_subset(task, "manual", all_workers, threshold, pair_map) if all_workers else {}
            final_scope = str(scope_index.loc[task, "task_final_scope"])
            has_semi = task in planned_set
            task_class = "paired_primary" if task in primary_set else "paired_oos" if has_semi else "manual_only_oos" if final_scope == "oos" else "manual_only_in_scope"
            rows.append({
                "threshold": threshold,
                "base_task_id": task,
                "building_id": buildings[task],
                "task_analysis_class": task_class,
                "task_final_scope": final_scope,
                "has_semi_candidate": has_semi,
                "gate_without_scope_valid_k": len(formal_workers),
                "all_canonical_valid_k": len(all_workers),
                "gate_without_scope_partition_status": formal.get("partition_status"),
                "all_canonical_partition_status": inclusive.get("partition_status"),
                "gate_without_scope_shannon_entropy": formal.get("shannon_entropy"),
                "all_canonical_shannon_entropy": inclusive.get("shannon_entropy"),
                "gate_without_scope_mode_count": formal.get("mode_count"),
                "all_canonical_mode_count": inclusive.get("mode_count"),
                "excluded_context_shift_manual_entropy": (
                    inclusive.get("shannon_entropy") - formal.get("shannon_entropy")
                    if inclusive.get("shannon_entropy") is not None and formal.get("shannon_entropy") is not None else None
                ),
                "analysis_role": "manual_ambiguity_catalog_not_semi_effect",
            })
    return pd.DataFrame(rows)


def inclusion_classification(
    eligibility: pd.DataFrame,
    primary_tasks: Sequence[str],
    planned_tasks: Sequence[str],
    all_tasks: Sequence[str],
    formal_nodes: dict[tuple[str, str], list[str]],
    all_nodes: dict[tuple[str, str], list[str]],
    scope: pd.DataFrame,
    active_time_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    primary_set, planned_set = set(primary_tasks), set(planned_tasks)
    scope_columns = [
        "base_task_id", "initial_researcher_scope", "n_worker_in_scope", "n_worker_oos", "n_worker_missing",
        "worker_scope_direction", "worker_scope_margin", "mixed_scope_response", "secondary_scope",
        "task_final_scope", "scope_resolution_status", "final_scope_source", "secondary_notes",
    ]
    scope_small = scope[[column for column in scope_columns if column in scope]].copy()
    ledger = eligibility.merge(scope_small, how="left", on="base_task_id", validate="many_to_one")
    ledger["worker_id"] = ledger["worker_id"].map(norm_worker)
    ledger["condition"] = ledger["condition"].map(clean_condition)
    timing = active_time_rows[[
        "base_task_id", "condition", "worker_id", "task_worker_active_seconds", "task_worker_time_analysis_eligible",
        "timing_status", "timing_exclusion_reason",
    ]]
    ledger = ledger.merge(timing, how="left", on=["base_task_id", "condition", "worker_id"], validate="one_to_one")
    ledger["has_semi_candidate"] = ledger["base_task_id"].isin(planned_set)
    ledger["in_primary_entropy_sample"] = ledger["base_task_id"].isin(primary_set)
    ledger["primary_entropy_eligible"] = [
        row.worker_id in formal_nodes.get((row.base_task_id, row.condition), []) and row.base_task_id in primary_set
        for row in ledger.itertuples(index=False)
    ]
    ledger["secondary_uncertainty_eligible"] = ledger["geometry_normalization_valid"].map(truth)
    ledger["worker_process_class"] = [
        "administratively_excluded_worker"
        if "administrative_exclusion" in str(row.process_exclusion_reason)
        else "outside_assignment"
        if "outside_assignment" in str(row.process_exclusion_reason) or str(row.assignment_provenance) == "outside_assignment"
        else "standard_assignment"
        for row in ledger.itertuples(index=False)
    ]

    def primary_class(row: Any) -> str:
        if str(row.task_final_scope) == "oos":
            return "oos_scope_task"
        if row.base_task_id not in planned_set:
            return "manual_only_no_semi_candidate"
        if row.worker_process_class != "standard_assignment":
            return row.worker_process_class
        if not truth(row.geometry_structurally_computable) or not truth(row.geometry_normalization_valid):
            return "geometry_not_computable"
        if truth(row.primary_entropy_eligible):
            return "formal_primary_geometry"
        return "other_estimand_ineligible"

    ledger["primary_exclusion_class"] = [primary_class(row) for row in ledger.itertuples(index=False)]
    ledger["primary_exclusion_class_definition"] = "mutually_exclusive_analysis_priority_not_complete_reason_set"
    ledger["excluded_from_primary_entropy"] = ~ledger["primary_entropy_eligible"]
    ledger["manual_quality_eligible"] = ledger["condition"].eq("manual") & ledger["gt_primary_analysis_eligible"].map(truth)
    ledger["semi_correction_eligible"] = ledger["condition"].eq("semi") & ledger["semi_correction_analysis_eligible"].map(truth)

    def exclusion_flags(row: Any) -> str:
        flags = []
        if row.worker_process_class != "standard_assignment":
            flags.append(f"worker_process:{row.worker_process_class}")
        if not truth(row.formal_assignment_eligible):
            flags.append("formal_assignment:not_eligible")
        if not truth(row.independence_eligible):
            flags.append(f"independence:{row.independence_exclusion_reason}")
        if not truth(row.scope_eligible):
            flags.append(f"scope:{row.scope_exclusion_reason}")
        if not truth(row.geometry_structurally_computable):
            flags.append("geometry:structurally_not_computable")
        if not truth(row.geometry_normalization_valid):
            flags.append("geometry:normalization_invalid")
        if not truth(row.gt_score_computable):
            flags.append("quality:gt_score_not_computable")
        if not truth(row.task_worker_time_analysis_eligible):
            flags.append("active_time:not_evaluable")
        return json.dumps(flags, ensure_ascii=False)

    ledger["secondary_exclusion_flags"] = [exclusion_flags(row) for row in ledger.itertuples(index=False)]

    def lanes(row: Any) -> str:
        values = []
        if truth(row.secondary_uncertainty_eligible):
            values.append("inclusive_all_canonical_uncertainty")
        if truth(row.has_semi_candidate) and truth(row.secondary_uncertainty_eligible):
            values.append("paired_manual_semi_data_mining")
        if truth(row.primary_entropy_eligible):
            values.append("formal_geometry_uncertainty")
        if str(row.task_final_scope) == "oos" and truth(row.secondary_uncertainty_eligible):
            values.append("oos_scope_semantic_uncertainty")
        if row.base_task_id not in planned_set and truth(row.secondary_uncertainty_eligible):
            values.append("manual_only_ambiguity")
        if row.worker_process_class != "standard_assignment" and truth(row.secondary_uncertainty_eligible):
            values.append("process_contamination_sensitivity")
        if truth(row.task_worker_time_analysis_eligible):
            values.append("frozen_time_auxiliary")
        if truth(row.manual_quality_eligible) or truth(row.semi_correction_eligible):
            values.append("quality_auxiliary")
        if not truth(row.secondary_uncertainty_eligible):
            values.append("not_computable_audit")
        return ";".join(values)

    ledger["secondary_analysis_lanes"] = [lanes(row) for row in ledger.itertuples(index=False)]
    paired_counts = ledger[ledger["has_semi_candidate"]]["primary_exclusion_class"].value_counts().to_dict()
    expected = {
        "formal_primary_geometry": 197,
        "oos_scope_task": 28,
        "administratively_excluded_worker": 9,
        "outside_assignment": 6,
        "geometry_not_computable": 1,
    }
    if paired_counts != expected:
        raise AssertionError(f"paired row inclusion classification drift: {paired_counts}")

    features = read("preassignment_features").set_index("base_task_id")
    semi_review = read("semi_review")
    semi_review = semi_review[semi_review["stage"].eq("C1")]
    semi_counts = semi_review.groupby("base_task_id").agg(
        semi_review_rows=("worker_id", "size"),
        semi_review_analysis_eligible_rows=("analysis_eligible", lambda values: sum(truth(value) for value in values)),
        semi_review_edit_rate=("edited_binary", "mean"),
    )
    scope_index = scope.set_index("base_task_id")
    task_rows = []
    for task in sorted(all_tasks):
        task_ledger = ledger[ledger["base_task_id"].eq(task)]
        final_scope = str(scope_index.loc[task, "task_final_scope"])
        has_semi = task in planned_set
        task_class = "paired_primary" if task in primary_set else "paired_oos" if has_semi else "manual_only_oos" if final_scope == "oos" else "manual_only_in_scope"
        task_rows.append({
            "base_task_id": task,
            "building_id": str(task_ledger["building_id"].iloc[0]),
            "task_analysis_class": task_class,
            "has_semi_candidate": has_semi,
            "in_primary_entropy_sample": task in primary_set,
            "primary_exclusion_reason": "" if task in primary_set else "task_final_scope_oos" if final_scope == "oos" else "no_semi_candidate",
            "task_final_scope": final_scope,
            "scope_resolution_status": scope_index.loc[task, "scope_resolution_status"],
            "worker_scope_direction": scope_index.loc[task, "worker_scope_direction"],
            "n_worker_in_scope": scope_index.loc[task, "n_worker_in_scope"],
            "n_worker_oos": scope_index.loc[task, "n_worker_oos"],
            "n_worker_missing": scope_index.loc[task, "n_worker_missing"],
            "mixed_scope_response": scope_index.loc[task, "mixed_scope_response"],
            "manual_canonical_context_count": int(task_ledger["condition"].eq("manual").sum()),
            "semi_canonical_context_count": int(task_ledger["condition"].eq("semi").sum()),
            "manual_formal_geometry_k": len(formal_nodes.get((task, "manual"), [])),
            "semi_formal_geometry_k": len(formal_nodes.get((task, "semi"), [])),
            "manual_all_canonical_valid_k": len(all_nodes.get((task, "manual"), [])),
            "semi_all_canonical_valid_k": len(all_nodes.get((task, "semi"), [])),
            "semi_review_rows": int(semi_counts.loc[task, "semi_review_rows"]) if task in semi_counts.index else 0,
            "semi_review_analysis_eligible_rows": int(semi_counts.loc[task, "semi_review_analysis_eligible_rows"]) if task in semi_counts.index else 0,
            "semi_review_edit_rate": semi_counts.loc[task, "semi_review_edit_rate"] if task in semi_counts.index else None,
            "preannotation_feature_ready": truth(features.loc[task, "preannotation_feature_ready"]) if task in features.index else False,
            "preannotation_feature_exclusion_reason": features.loc[task, "exclusion_reason"] if task in features.index else "missing_task_feature_row",
            "secondary_analysis_lanes": "formal_geometry_uncertainty;excluded_context_sensitivity" if task in primary_set else "oos_scope_semantic_uncertainty" if final_scope == "oos" else "manual_only_ambiguity",
        })
    task_frame = pd.DataFrame(task_rows)
    if len(task_frame) != 87 or task_frame["has_semi_candidate"].sum() != 25 or task_frame["in_primary_entropy_sample"].sum() != 22 or task_frame["task_final_scope"].eq("oos").sum() != 8:
        raise AssertionError("task inclusion waterfall drift")

    worker_rows = []
    for worker, group in ledger.groupby("worker_id", sort=True):
        primary_n = int(group["primary_entropy_eligible"].sum())
        excluded_n = int((~group["primary_entropy_eligible"]).sum())
        admin_n = int(group["worker_process_class"].eq("administratively_excluded_worker").sum())
        secondary_n = int(group["secondary_uncertainty_eligible"].sum())
        status = "primary_with_excluded_contexts" if primary_n and excluded_n else "primary_only" if primary_n else "administratively_excluded_secondary_only" if admin_n else "secondary_only" if secondary_n else "no_evaluable_context"
        worker_rows.append({
            "worker_id": worker,
            "all_context_count": len(group),
            "primary_entropy_context_count": primary_n,
            "excluded_context_count": excluded_n,
            "secondary_uncertainty_context_count": secondary_n,
            "manual_quality_eligible_count": int(group["manual_quality_eligible"].sum()),
            "semi_correction_eligible_count": int(group["semi_correction_eligible"].sum()),
            "time_eligible_count": int(group["task_worker_time_analysis_eligible"].map(truth).sum()),
            "formal_assignment_ineligible_count": int((~group["formal_assignment_eligible"].map(truth)).sum()),
            "scope_ineligible_count": int((~group["scope_eligible"].map(truth)).sum()),
            "geometry_noncomputable_count": int((~group["geometry_normalization_valid"].map(truth)).sum()),
            "administratively_excluded_context_count": admin_n,
            "outside_assignment_context_count": int(group["worker_process_class"].eq("outside_assignment").sum()),
            "worker_coverage_status": status,
        })
    return task_frame, ledger.sort_values(["base_task_id", "condition", "worker_id"]).reset_index(drop=True), pd.DataFrame(worker_rows)


def exclusion_reason_audit(row_classification: pd.DataFrame) -> pd.DataFrame:
    entries: list[tuple[str, str, pd.Series]] = []
    for value in ("administratively_excluded_worker", "outside_assignment"):
        entries.append(("worker_process", value, row_classification["worker_process_class"].eq(value)))
    for dimension, column in (("process", "process_exclusion_reason"), ("independence", "independence_exclusion_reason"), ("scope", "scope_exclusion_reason")):
        values = row_classification[column].fillna("").astype(str)
        for value in sorted(set(values) - {""}):
            entries.append((dimension, value, values.eq(value)))
    entries.extend([
        ("geometry", "structurally_not_computable", ~row_classification["geometry_structurally_computable"].map(truth)),
        ("geometry", "normalization_invalid", ~row_classification["geometry_normalization_valid"].map(truth)),
        ("quality", "gt_score_not_computable", ~row_classification["gt_score_computable"].map(truth)),
        ("active_time", "not_evaluable", ~row_classification["task_worker_time_analysis_eligible"].map(truth)),
    ])
    rows = []
    for dimension, value, mask in entries:
        subset = row_classification[mask]
        if subset.empty:
            continue
        rows.append({
            "reason_dimension": dimension,
            "reason_value": value,
            "context_count": len(subset),
            "task_count": subset["base_task_id"].nunique(),
            "worker_count": subset["worker_id"].nunique(),
            "condition_counts_json": json.dumps(subset["condition"].value_counts().sort_index().to_dict(), ensure_ascii=False, sort_keys=True),
            "primary_class_distribution_json": json.dumps(subset["primary_exclusion_class"].value_counts().sort_index().to_dict(), ensure_ascii=False, sort_keys=True),
            "analysis_role": "orthogonal_exclusion_reason_audit_no_row_deletion",
        })
    return pd.DataFrame(rows).sort_values(["reason_dimension", "reason_value"]).reset_index(drop=True)


def excluded_worker_peer_audit(
    row_classification: pd.DataFrame,
    pair_map: dict[tuple[str, str, str, str], dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    excluded = row_classification[
        row_classification["secondary_uncertainty_eligible"].map(truth)
        & row_classification["worker_process_class"].isin({"administratively_excluded_worker", "outside_assignment"})
    ]
    reference_nodes = row_classification[
        row_classification["secondary_uncertainty_eligible"].map(truth)
        & row_classification["worker_process_class"].eq("standard_assignment")
    ].groupby(["base_task_id", "condition"])["worker_id"].agg(lambda values: sorted(set(values)))
    rows = []
    for item in excluded.itertuples(index=False):
        peers = reference_nodes.get((item.base_task_id, item.condition), [])
        for peer in peers:
            if peer == item.worker_id:
                continue
            pair = pair_map.get((item.base_task_id, item.condition, *sorted((item.worker_id, peer))))
            rows.append({
                "base_task_id": item.base_task_id,
                "condition": item.condition,
                "excluded_worker_id": item.worker_id,
                "formal_peer_worker_id": peer,
                "worker_process_class": item.worker_process_class,
                "primary_exclusion_class": item.primary_exclusion_class,
                "metric_compatible": bool(pair and pair["metric_compatible"]),
                "pointwise_correspondence_compatible": bool(pair and pair["correspondence"]),
                "q_boundary": pair["q_boundary"] if pair else None,
                "q_wallwall": pair["q_wallwall"] if pair else None,
                "passes_q095": bool(pair and pair["correspondence"] and pair["q_boundary"] is not None and pair["q_wallwall"] is not None and pair["q_boundary"] >= PRIMARY_THRESHOLD and pair["q_wallwall"] >= PRIMARY_THRESHOLD),
                "analysis_role": "excluded_worker_descriptive_only",
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame, pd.DataFrame()
    summary = frame.groupby(["excluded_worker_id", "worker_process_class"], as_index=False).agg(
        task_count=("base_task_id", "nunique"),
        peer_comparison_count=("formal_peer_worker_id", "size"),
        metric_compatible_count=("metric_compatible", "sum"),
        correspondence_compatible_count=("pointwise_correspondence_compatible", "sum"),
        passes_q095_count=("passes_q095", "sum"),
        q_boundary_mean=("q_boundary", "mean"),
        q_wallwall_mean=("q_wallwall", "mean"),
    )
    summary["analysis_role"] = "excluded_worker_descriptive_only"
    return frame, summary


def excluded_task_uncertainty(
    manual_catalog: pd.DataFrame,
    population_tasks: pd.DataFrame,
    scope: pd.DataFrame,
    planned_tasks: Sequence[str],
    active_time_tasks: pd.DataFrame,
) -> pd.DataFrame:
    scope_oos = scope[scope["task_final_scope"].eq("oos")].copy()
    if len(scope_oos) != 8:
        raise AssertionError("C1 OOS task count drift")
    planned_set = set(planned_tasks)
    catalog_index = manual_catalog.set_index(["threshold", "base_task_id"])
    inclusive = population_tasks[population_tasks["population"].eq("all_canonical_planned")].set_index(["threshold", "base_task_id"])
    protocol = population_tasks[population_tasks["population"].eq("formal_plus_oos_tasks")].set_index(["threshold", "base_task_id"])
    scope_index = scope_oos.set_index("base_task_id")
    time_index = active_time_tasks.set_index("base_task_id")
    semi = read("semi_review")
    semi = semi[semi["stage"].eq("C1")]
    semi_edit = semi.groupby("base_task_id").agg(
        semi_review_rows=("worker_id", "size"),
        semi_review_edited_count=("edited_binary", "sum"),
        semi_review_edit_rate=("edited_binary", "mean"),
    )
    rows = []
    for threshold in THRESHOLDS:
        for task in sorted(scope_oos["base_task_id"]):
            has_semi = task in planned_set
            manual = catalog_index.loc[threshold, task]
            data_mining = inclusive.loc[threshold, task] if has_semi else None
            reference = protocol.loc[threshold, task] if has_semi else None
            timing = time_index.loc[task]
            scope_row = scope_index.loc[task]
            rows.append({
                "threshold": threshold,
                "base_task_id": task,
                "building_id": manual["building_id"],
                "has_semi_candidate": has_semi,
                "task_analysis_class": "paired_oos" if has_semi else "manual_only_oos",
                "task_final_scope": "oos",
                "initial_researcher_scope": scope_row.get("initial_researcher_scope"),
                "worker_scope_direction": scope_row.get("worker_scope_direction"),
                "n_worker_in_scope": scope_row.get("n_worker_in_scope"),
                "n_worker_oos": scope_row.get("n_worker_oos"),
                "n_worker_missing": scope_row.get("n_worker_missing"),
                "mixed_scope_response": scope_row.get("mixed_scope_response"),
                "secondary_scope": scope_row.get("secondary_scope"),
                "secondary_notes": scope_row.get("secondary_notes"),
                "manual_all_canonical_valid_k": manual["all_canonical_valid_k"],
                "semi_all_canonical_valid_k": int(data_mining["common_k"]) if has_semi else 0,
                "manual_data_mining_entropy": data_mining["manual_shannon_entropy"] if has_semi else manual["all_canonical_shannon_entropy"],
                "semi_data_mining_entropy": data_mining["semi_shannon_entropy"] if has_semi else None,
                "delta_data_mining_entropy": data_mining["delta_shannon_entropy"] if has_semi else None,
                "protocol_reference_manual_entropy": reference["manual_shannon_entropy"] if has_semi else None,
                "protocol_reference_semi_entropy": reference["semi_shannon_entropy"] if has_semi else None,
                "protocol_reference_delta_entropy": reference["delta_shannon_entropy"] if has_semi else None,
                "manual_observed_active_seconds_mean": timing["manual_observed_active_seconds_mean"],
                "semi_observed_active_seconds_mean": timing["semi_observed_active_seconds_mean"],
                "delta_observed_active_seconds_mean": timing["delta_observed_active_seconds_mean"],
                "semi_review_rows": int(semi_edit.loc[task, "semi_review_rows"]) if task in semi_edit.index else 0,
                "semi_review_edited_count": int(semi_edit.loc[task, "semi_review_edited_count"]) if task in semi_edit.index else 0,
                "semi_review_edit_rate": semi_edit.loc[task, "semi_review_edit_rate"] if task in semi_edit.index else None,
                "analysis_role": "oos_scope_semantic_uncertainty_data_mining",
                "formal_inference_allowed": False,
            })
    return pd.DataFrame(rows)


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


def report(
    summary: pd.DataFrame,
    task_metrics: pd.DataFrame,
    population_summary: pd.DataFrame,
    assignment: pd.DataFrame,
    difficulty_summary: pd.DataFrame,
    time_audit: pd.DataFrame,
    time_summary: pd.DataFrame,
    quality_summary: pd.DataFrame,
    quality_inclusive_summary: pd.DataFrame,
    task_classification: pd.DataFrame,
    row_classification: pd.DataFrame,
    worker_coverage: pd.DataFrame,
    excluded_tasks: pd.DataFrame,
    pairwise_summary: pd.DataFrame,
    fixed_summary: pd.DataFrame,
) -> str:
    formal = summary[(summary["threshold"].eq(PRIMARY_THRESHOLD)) & summary["metric"].eq("shannon_entropy")].iloc[0]
    inclusive = population_summary[
        population_summary["population"].eq("all_canonical_planned")
        & population_summary["threshold"].eq(PRIMARY_THRESHOLD)
        & population_summary["metric"].eq("shannon_entropy")
    ].iloc[0]
    formal_plus_oos = population_summary[
        population_summary["population"].eq("formal_plus_oos_tasks")
        & population_summary["threshold"].eq(PRIMARY_THRESHOLD)
        & population_summary["metric"].eq("shannon_entropy")
    ].iloc[0]
    primary_tasks = task_metrics[task_metrics["threshold"].eq(PRIMARY_THRESHOLD)]
    paired_rows = row_classification[row_classification["has_semi_candidate"].map(truth)]
    classes = paired_rows["primary_exclusion_class"].value_counts()
    q95_oos = excluded_tasks[excluded_tasks["threshold"].eq(PRIMARY_THRESHOLD) & excluded_tasks["has_semi_candidate"].map(truth)]
    time_formal = time_summary[
        time_summary["population"].eq("formal_primary_22") & time_summary["statistic"].eq("task_worker_mean_seconds")
    ].iloc[0]
    time_inclusive = time_summary[
        time_summary["population"].eq("planned_paired_25") & time_summary["statistic"].eq("task_worker_mean_seconds")
    ].iloc[0]
    quality_formal = quality_summary.iloc[0]
    quality_inclusive = quality_inclusive_summary.iloc[0]
    pair_total = pairwise_summary[pairwise_summary["condition"].eq("all")].iloc[0]
    w14 = worker_coverage[worker_coverage["worker_id"].astype(str).eq("14")].iloc[0]
    population_table = population_summary[
        population_summary["threshold"].eq(PRIMARY_THRESHOLD) & population_summary["metric"].eq("shannon_entropy")
    ][["population", "inference_role", "n_tasks", "n_buildings", "mean_difference", "ci_lower", "ci_upper", "building_exact_sign_flip_p"]]
    lines = [
        "# C1 Manual / Semi-Auto 标注不确定性全量数据挖掘报告（修复版）",
        "",
        "## 数据挖掘主结果",
        "",
        "- 本报告的主数据挖掘总体是 25 个已有 Manual/Semi 候选的同图任务，使用全部几何可计算 canonical 标注；中途退出、行政排除、外部分配和不进入后续阶段的工人没有因这些身份被删除。",
        f"- q=.95 时，全量 25-task 总体的任务等权 Shannon entropy 差（Semi−Manual）为 {inclusive['mean_difference']:.6f}，"
        f"building-cluster bootstrap 95% CI [{inclusive['ci_lower']:.6f}, {inclusive['ci_upper']:.6f}]，"
        f"building exact sign-flip p={inclusive['building_exact_sign_flip_p']:.6f}。这是全量描述性数据挖掘结果，不是随机化因果效应。",
        f"- 22-task 正式资格样本仅保留为协议参照：差值 {formal['mean_difference']:.6f}，95% CI [{formal['ci_lower']:.6f}, {formal['ci_upper']:.6f}]，"
        f"building p={formal['building_exact_sign_flip_p']:.6f}；该参照未检出总体不确定性降低。加入 3 个 paired OOS 任务但保持其全量几何后，25-task 差值为 {formal_plus_oos['mean_difference']:.6f}。",
        "- 上述区间不是预设等效性区间；不能把‘未检出降低’解释成‘两种方法相同’。",
        "- q=.95 的四个总体不可互换，完整对照如下：",
        "",
        population_table.to_markdown(index=False),
        "",
        "## 全量数据分类",
        "",
        f"- 任务层：87 个 C1 任务；25 个有 Semi 候选，其中 22 个协议参照任务、3 个 paired OOS；其余 62 个为 Manual-only。最终 OOS 共 {int(task_classification['task_final_scope'].eq('oos').sum())} 个。",
        f"- 标注层：780 个 canonical task-worker-condition context、23 名工人。25 个 paired 任务共有 {len(paired_rows)} 个 context："
        f"协议参照几何 {int(classes.get('formal_primary_geometry', 0))}、OOS {int(classes.get('oos_scope_task', 0))}、"
        f"行政排除 {int(classes.get('administratively_excluded_worker', 0))}、外部分配 {int(classes.get('outside_assignment', 0))}、"
        f"几何不可计算 {int(classes.get('geometry_not_computable', 0))}。最后一类只进入缺失性审计，其余可计算行进入相应全量/敏感性分析。",
        f"- 工人 14 的 32 个 C1 context 全部保留；其中 {int(w14['secondary_uncertainty_context_count'])} 个几何可用于全量不确定性分析。工人是否继续后续阶段不作为本报告的删除条件。",
        f"- 25 个 paired 任务中有 {int(paired_rows['excluded_from_primary_entropy'].sum())} 个 context 处于‘非正式参照但保留’状态；逐行原因见 `ROW_INCLUSION_CLASSIFICATION.csv`。",
        "- `primary_exclusion_class` 是按分析优先级生成的互斥主分类，不是完整原因集合；每行的正交原因保存在 `secondary_exclusion_flags`，机械汇总见 `EXCLUSION_REASON_AUDIT.csv`。",
        "",
        "## 被排除任务与工人的信息",
        "",
        "- 8 个 OOS 任务没有删除：3 个 paired OOS 同时给出 Manual/Semi 熵差，5 个 Manual-only OOS 给出图像自身的 Manual 多解性目录；结果见 `EXCLUDED_TASK_UNCERTAINTY.csv`。",
        "- q=.95 的 3 个 paired OOS 任务差值（Semi−Manual）为："
        + "；".join(f"`{row.base_task_id}` {row.delta_data_mining_entropy:+.6f}" for row in q95_oos.itertuples(index=False)) + "。",
        "- 行政排除、外部分配等工人与同任务中标准分配且几何可计算工人的逐对一致性另列于 `EXCLUDED_WORKER_PEER_COMPARISONS.csv`；它用于观察这些数据是否改变分布，不用于恢复正式资格。",
        "",
        "## 几何指标与兼容性",
        "",
        "- 每个阈值同时输出 Shannon entropy、Gini-Simpson、最大模态占比、支持型多模态、模态数，以及两种含义不同的 pairwise 距离。",
        f"- 正式参照原始配对中，metric-compatible 对为 {int(pair_total['metric_compatible_count'])}，其中 pointwise-correspondence-compatible 为 {int(pair_total['correspondence_compatible_count'])}，"
        f"另有 {int(pair_total['correspondence_incompatible_count'])} 对只能用于通用 metric dissimilarity，不能混入逐点对应差异。",
        f"- q=.95 中非唯一或不可评价的任务-条件子集记录数为 {int(primary_tasks['manual_nonunique_or_not_evaluable_count'].sum() + primary_tasks['semi_nonunique_or_not_evaluable_count'].sum())}；没有填零后混入 partition 指标。",
        "",
        "## 质量、时间和难度",
        "",
        f"- 质量的条件特异资格对比覆盖 {int(quality_formal['n_tasks'])} 个任务，Semi−Manual IoU={quality_formal['mean_difference']:.6f}，building p={quality_formal['building_exact_sign_flip_p']:.6f}；"
        "这是不同条件各自资格口径下的辅助关联。",
        f"- 另将全部 IoU 可计算 context（不按后续资格删除）组成质量挖掘总体；25 个候选任务中有 {int(quality_inclusive['n_tasks'])} 个形成可评价配对，差值为 {quality_inclusive['mean_difference']:.6f}，"
        f"building p={quality_inclusive['building_exact_sign_flip_p']:.6f}；完整 780 行及不可计算原因仍保留在 `QUALITY_DATA_MINING_CONTEXTS.csv`。",
        f"- active time 只使用冻结 task-worker 文件：780 个 context 中 {int(worker_coverage['time_eligible_count'].sum())} 个满足冻结时间资格，"
        f"其中 {int(time_audit.iloc[0]['eligible_context_count'])} 个属于 22-task 正式时间参照。"
        f"正式参照的任务均值差为 {time_formal['mean_difference']:.6f} 秒；25-task 全量 observed frozen-time 差为 {time_inclusive['mean_difference']:.6f} 秒。没有使用 Label Studio `lead_time` 或 raw event 回填。",
        f"- 冻结 pre-assignment 难度特征 `n_ready=0`（{difficulty_summary.iloc[0]['reason']}），因此‘高难度图像上是否更有优势’仍不可评价；没有用最终 Manual 熵反向定义高难度。",
        "",
        "## 推断边界与文件导航",
        "",
        f"- 同图跨条件 worker overlap 为 {int(assignment['realized_overlap_count'].sum())}。分配并非标准随机试验，所以所有 Manual/Semi 差异只报告为分布差异或关联。",
        "- `TASK_INCLUSION_CLASSIFICATION.csv`、`ROW_INCLUSION_CLASSIFICATION.csv`、`WORKER_COVERAGE.csv` 给出任务—标注—工人三级盘点；`POPULATION_SENSITIVITY.csv` 给出正式参照、加入 OOS、加入非正式工人和全量计划任务四个总体。",
        "- `MANUAL_TASK_UNCERTAINTY_CATALOG.csv` 覆盖全部 87 个任务，用于发现图像自身歧义；不能把 Manual-only 任务误写成 Semi 的效果。",
        "- 旧固定分区结果仅作可复现审计基线：",
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
    reclustered = exhaustive_reclustering(tasks, nodes, pair_map, expected_rows=411)
    task_metrics = aggregate_task_metrics(reclustered, buildings)
    summary = threshold_summary(task_metrics, bootstrap_replicates)
    fixed_tasks, fixed_summary = fixed_partition_audit(crowd, tasks, buildings)
    assignment_tasks, assignment_loads, assignment_balance = assignment_audit(tasks, nodes)
    initialization, mechanisms = initialization_audit(tasks)
    eligibility, _, all_nodes, gate_without_scope_nodes, all_pair_map = geometry_contexts()
    all_tasks = sorted(eligibility["base_task_id"].astype(str).unique())
    planned_tasks = sorted(read("assignment_semi")["base_task_id"].astype(str).unique())
    all_buildings = eligibility.groupby("base_task_id")["building_id"].first().astype(str).to_dict()
    if len(all_tasks) != 87 or len(planned_tasks) != 25 or set(tasks) - set(planned_tasks):
        raise AssertionError("C1 all-task/planned-task coverage drift")
    for task in tasks:
        for condition in ("manual", "semi"):
            if gate_without_scope_nodes.get((task, condition), []) != nodes[task, condition]:
                raise AssertionError(f"formal geometry gate reconstruction drift: {task}/{condition}")
    reconstructed_formal = aggregate_task_metrics(
        exhaustive_reclustering(tasks, nodes, all_pair_map, expected_rows=411), buildings
    )
    metric_columns = [
        column for column in task_metrics
        if column.startswith(("manual_", "semi_", "delta_")) and pd.api.types.is_numeric_dtype(task_metrics[column])
    ]
    if any(not np.allclose(task_metrics[column], reconstructed_formal[column], equal_nan=True) for column in metric_columns):
        raise AssertionError("canonical geometry reconstruction differs from frozen formal pairwise input")
    scope = read("scope_final")
    time_audit, time_rows, time_tasks, time_summary = active_time_analysis(
        tasks, all_tasks, planned_tasks, all_buildings, bootstrap_replicates
    )
    population_tasks, population_summary, excluded_context_impact = population_sensitivity(
        tasks,
        planned_tasks,
        all_buildings,
        task_metrics,
        summary,
        nodes,
        all_nodes,
        all_pair_map,
        bootstrap_replicates,
    )
    manual_catalog = manual_uncertainty_catalog(
        all_tasks, planned_tasks, tasks, scope, all_buildings, all_nodes, gate_without_scope_nodes, all_pair_map
    )
    task_classification, row_classification, worker_coverage = inclusion_classification(
        eligibility, tasks, planned_tasks, all_tasks, nodes, all_nodes, scope, time_rows
    )
    excluded_worker_pairs, excluded_worker_summary = excluded_worker_peer_audit(
        row_classification, all_pair_map
    )
    exclusion_reasons = exclusion_reason_audit(row_classification)
    excluded_tasks = excluded_task_uncertainty(
        manual_catalog, population_tasks, scope, planned_tasks, time_tasks
    )
    quality_tasks, quality_summary = quality_auxiliary(tasks, buildings, bootstrap_replicates)
    quality_contexts, quality_inclusive_tasks, quality_inclusive_summary = quality_data_mining_inclusive(
        all_tasks, planned_tasks, all_buildings, bootstrap_replicates
    )
    primary_metrics = task_metrics[task_metrics["threshold"].eq(PRIMARY_THRESHOLD)]
    difficulty_tasks, difficulty_summary = difficulty_coverage(tasks, primary_metrics, nodes)
    freeze_refs = freeze_reference_audit()
    pair_rows = pd.DataFrame([
        {"condition": key[1], **value} for key, value in pair_map.items()
    ])
    pairwise_summary_rows = []
    for condition in ("manual", "semi", "all"):
        subset = pair_rows if condition == "all" else pair_rows[pair_rows["condition"].eq(condition)]
        metric = subset["metric_compatible"].map(truth)
        correspondence = subset["correspondence"].map(truth)
        pairwise_summary_rows.append({
            "condition": condition,
            "pair_count": len(subset),
            "metric_compatible_count": int(metric.sum()),
            "correspondence_compatible_count": int((metric & correspondence).sum()),
            "correspondence_incompatible_count": int((metric & ~correspondence).sum()),
            "analysis_role": "pairwise_metric_semantics_audit",
        })
    pairwise_summary = pd.DataFrame(pairwise_summary_rows)

    outputs = {
        "INPUT_MANIFEST.csv": input_manifest,
        "TASK_SUBSET_RECLUSTERING.csv": reclustered,
        "TASK_METRICS.csv": task_metrics,
        "THRESHOLD_ROBUSTNESS.csv": summary,
        "POPULATION_TASK_METRICS.csv": population_tasks,
        "POPULATION_SENSITIVITY.csv": population_summary,
        "EXCLUDED_CONTEXT_IMPACT.csv": excluded_context_impact,
        "MANUAL_TASK_UNCERTAINTY_CATALOG.csv": manual_catalog,
        "TASK_INCLUSION_CLASSIFICATION.csv": task_classification,
        "ROW_INCLUSION_CLASSIFICATION.csv": row_classification,
        "WORKER_COVERAGE.csv": worker_coverage,
        "EXCLUSION_REASON_AUDIT.csv": exclusion_reasons,
        "EXCLUDED_WORKER_PEER_COMPARISONS.csv": excluded_worker_pairs,
        "EXCLUDED_WORKER_PEER_SUMMARY.csv": excluded_worker_summary,
        "EXCLUDED_TASK_UNCERTAINTY.csv": excluded_tasks,
        "PAIRWISE_COMPATIBILITY_SUMMARY.csv": pairwise_summary,
        "LEGACY_FIXED_PARTITION_TASK_AUDIT.csv": fixed_tasks,
        "LEGACY_FIXED_PARTITION_SUMMARY.csv": fixed_summary,
        "ASSIGNMENT_TASK_AUDIT.csv": assignment_tasks,
        "ASSIGNMENT_WORKER_LOAD.csv": assignment_loads,
        "ASSIGNMENT_PROFILE_BALANCE.csv": assignment_balance,
        "SEMI_INITIALIZATION_AUDIT.csv": initialization,
        "MECHANISM_AUXILIARY.csv": mechanisms,
        "QUALITY_AUXILIARY.csv": quality_tasks,
        "QUALITY_AUXILIARY_SUMMARY.csv": quality_summary,
        "QUALITY_DATA_MINING_CONTEXTS.csv": quality_contexts,
        "QUALITY_DATA_MINING_TASK_METRICS.csv": quality_inclusive_tasks,
        "QUALITY_DATA_MINING_SUMMARY.csv": quality_inclusive_summary,
        "DIFFICULTY_PROXY_COVERAGE.csv": difficulty_tasks,
        "DIFFICULTY_PROXY_SUMMARY.csv": difficulty_summary,
        "FREEZE_REFERENCE_AUDIT.csv": freeze_refs,
        "FROZEN_TIME_AUXILIARY.csv": time_audit,
        "ACTIVE_TIME_TASK_WORKER.csv": time_rows,
        "ACTIVE_TIME_TASK_METRICS.csv": time_tasks,
        "ACTIVE_TIME_SUMMARY.csv": time_summary,
    }
    for name, frame in outputs.items():
        write_csv(output / name, frame)
    plots(task_metrics, summary, output)
    (output / "ANNOTATION_UNCERTAINTY_MANUAL_SEMI_REPORT_ZH.md").write_bytes(
        report(
            summary,
            task_metrics,
            population_summary,
            assignment_tasks,
            difficulty_summary,
            time_audit,
            time_summary,
            quality_summary,
            quality_inclusive_summary,
            task_classification,
            row_classification,
            worker_coverage,
            excluded_tasks,
            pairwise_summary,
            fixed_summary,
        ).encode("utf-8")
    )

    generated = sorted(path for path in output.iterdir() if path.is_file() and path.name not in {"OUTPUT_MANIFEST.csv", "analysis_manifest.json"})
    output_manifest = pd.DataFrame([{"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in generated])
    write_csv(output / "OUTPUT_MANIFEST.csv", output_manifest)
    script = Path(__file__)
    test = ROOT / "tests/test_materialize_annotation_uncertainty_manual_semi.py"
    manifest = {
        "schema_version": "annotation_uncertainty_manual_semi_manifest_v3",
        "rule_version": "annotation_uncertainty_manual_semi_inclusive_data_mining_v3",
        "source_branch_base_head": EXPECTED_HEAD,
        "script_path": script.relative_to(ROOT).as_posix(),
        "script_sha256": sha256(script),
        "test_path": test.relative_to(ROOT).as_posix(),
        "test_sha256": sha256(test) if test.is_file() else None,
        "thresholds": list(THRESHOLDS),
        "primary_threshold": PRIMARY_THRESHOLD,
        "bootstrap_seed": SEED,
        "bootstrap_replicates": bootstrap_replicates,
        "all_c1_task_count": len(all_tasks),
        "planned_paired_task_count": len(planned_tasks),
        "protocol_reference_task_count": len(tasks),
        "all_c1_context_count": len(row_classification),
        "all_c1_worker_count": row_classification["worker_id"].nunique(),
        "building_count": len(set(all_buildings.values())),
        "input_manifest_sha256": sha256(output / "INPUT_MANIFEST.csv"),
        "output_manifest_sha256": sha256(output / "OUTPUT_MANIFEST.csv"),
        "active_time_policy": "frozen_c1_task_worker_table_and_sha_manifest_only_no_raw_or_lead_time_fallback",
        "worker_retention_policy": "retain_midway_exit_administratively_excluded_and_outside_assignment_workers_in_inclusive_data_mining_when_outcome_computable",
        "primary_data_mining_population": "all_canonical_planned_25_tasks",
        "protocol_eligibility_role": "reference_and_sensitivity_not_global_deletion_rule",
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
