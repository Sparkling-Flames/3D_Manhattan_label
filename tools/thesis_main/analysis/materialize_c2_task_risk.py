"""Materialize pre-annotation C2 task risk from fixed HoHoNet and layout evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


DEFAULT_RISK_CONTRACT = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_RISK_DESIGN_CONTRACT_v1.json"


def _risk_contract(path: Path | None) -> tuple[dict[str, Any], Path]:
    contract_path = path or DEFAULT_RISK_CONTRACT
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"C2-B risk design contract unavailable: {contract_path}") from exc
    if contract.get("schema_version") != "paper_a_c2b_risk_design_contract_v1":
        raise ValueError("unsupported C2-B risk design contract")
    if contract.get("stratum_rule", {}).get("forbid_legacy_proxies") is None:
        raise ValueError("C2-B risk design contract lacks legacy-proxy guard")
    return contract, contract_path


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["task_id"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _layout_features(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"layout_status": "missing", "g_model_struct": "", "pair_count": "", "postprocess_valid": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    corners = (payload.get("layout") or {}).get("corners") or []
    points = [point for row in corners for point in ([float(row["x"]), float(row["y_ceiling"])], [float(row["x"]), float(row["y_floor"])])]
    normalized = normalize_geometry(points)
    xs = sorted(float(row["x"]) % 1024 for row in corners)
    gaps = [xs[index + 1] - xs[index] for index in range(len(xs) - 1)] + ([xs[0] + 1024 - xs[-1]] if xs else [])
    seam_stability = 1.0 - min(1.0, (gaps[-1] if gaps else 1024) / max(gaps or [1024]))
    pair_count = len(corners)
    duplicate_x = len({round(value, 6) for value in xs}) != len(xs)
    g_score = min(1.0, abs(pair_count - 6) / 8 + (0.35 if duplicate_x else 0) + (0.35 if not normalized["topology_valid"] else 0) + 0.15 * seam_stability)
    return {
        "layout_status": "ready", "g_model_struct": g_score, "pair_count": pair_count,
        "ceiling_floor_curve_present": bool(corners), "wall_peak_count": pair_count,
        "topology_valid": normalized["topology_valid"], "seam_stability": seam_stability,
        "postprocess_valid": normalized["valid"], "duplicate_wall_peak": duplicate_x,
        "layout_sha256": sha256_file(path),
    }


def _lhfeat_descriptors(paths: list[Path], checkpoint: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    try:
        import torch
        from PIL import Image
        from lib.model.hohonet import HoHoNet
    except ImportError as exc:
        raise RuntimeError(f"HoHoNet LHFeat dependencies unavailable: {exc}") from exc
    net = HoHoNet(
        input_hw=[512, 1024], emb_dim=256,
        backbone_config={"module": "Resnet", "kwargs": {"backbone": "resnet34"}},
        decode_config={"module": "EfficientHeightReduction"},
        refine_config={"module": "TransEn", "kwargs": {"position_encode": 256, "nhead": 8, "num_layers": 1, "dim_feedforward": 2048}},
        modalities_config={"LayoutEstimator": {"cor_weight": 1.0, "bon_weight": 1.0, "last_bias": False, "last_ks": 1}},
    )
    net.load_state_dict(torch.load(checkpoint, map_location="cpu")); net.eval()
    output: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    with torch.no_grad():
        for path in paths:
            rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
            tensor = torch.from_numpy(rgb).permute(2, 0, 1)[None]
            feature = net.extract_feat(tensor)["1D"][0].cpu().numpy()
            output[path.resolve().as_posix()] = (np.concatenate([feature.mean(1), feature.std(1)]), feature.max(1))
    return output


def _knn(candidate: np.ndarray, reference: np.ndarray, k: int = 5) -> float:
    distances = np.linalg.norm(reference - candidate[None], axis=1)
    return float(np.mean(np.partition(distances, min(k, len(distances)) - 1)[:min(k, len(distances))]))


def _composite_q75_bucket(
    values: dict[str, float], references: dict[str, list[float]], *, stress_quantile: float = .75,
) -> tuple[str, dict[str, float]]:
    percentiles = {
        name: sum(reference <= values[name] for reference in refs) / len(refs)
        for name, refs in references.items() if refs and name in values
    }
    return ("stress" if len(percentiles) == 4 and max(percentiles.values()) >= stress_quantile else "ordinary"), percentiles


RISK_VECTOR_FIELDS = ("d_model_feat", "d_model_feat_local_max", "g_model_struct", "d_cal_A")


def _frozen_vector(values: dict[str, float], scales: dict[str, float]) -> list[float] | None:
    if any(name not in values for name in RISK_VECTOR_FIELDS):
        return None
    return [float(values[name]) / (float(scales.get(name) or 1.0) or 1.0) for name in RISK_VECTOR_FIELDS]


def _score(vector: list[float] | None) -> float | None:
    return float(np.linalg.norm(np.asarray(vector, dtype=float))) if vector is not None else None


def _feature_freeze_ready(path: Path | None) -> bool:
    if not path or not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return all(bool(payload.get(flag)) and str(payload.get(f"{flag}_sha256", "")).strip() for flag in ("pca_frozen", "whitening_frozen", "circular_shift_invariant", "seam_invariant"))


def materialize(
    inventory_csv: Path, layout_dir: Path, c1_task_feature_csv: Path, output_dir: Path, *,
    input_status: str, checkpoint: Path | None = None, reference_dir: Path | None = None,
    extract_lhfeat: bool = False, c1_risk_reference_csv: Path | None = None,
    risk_contract: Path | None = None, feature_freeze_manifest: Path | None = None,
    c1_freeze_manifest: Path | None = None,
) -> dict[str, Any]:
    contract, contract_path = _risk_contract(risk_contract)
    stress_quantile = float(contract["stratum_rule"]["stress_quantile"])
    inventory = _read(inventory_csv)
    # C1 calibration support is a task-side, pre-annotation feature table.  Do
    # not derive a model-risk channel from crowd canonical geometry.
    c1_channels: dict[str, list[float]] = {name: [] for name in ("d_model_feat", "d_model_feat_local_max", "g_model_struct", "d_cal_A")}
    c1_by_task: dict[str, dict[str, Any]] = {}
    for row in _read(c1_task_feature_csv):
        task = str(row.get("base_task_id") or row.get("task_id") or "")
        if not task or task in c1_by_task or str(row.get("preannotation_feature_ready", "")).lower() not in {"true", "1"}:
            continue
        if any(not str(row.get(field, "")).strip() for field in ("checkpoint_sha256", "inference_config_sha256", "layout_output_sha256")):
            continue
        try:
            pair_count = float(row.get("g_pair_count", ""))
            g_model_struct = min(1.0, abs(pair_count - 6) / 8 + .35 * float(str(row.get("g_topology_invalid", "")).lower() in {"true", "1"}) + .35 * float(str(row.get("g_duplicate_peak", "")).lower() in {"true", "1"}) + .15 * float(row.get("g_seam_instability", "0") or 0) + .15 * float(str(row.get("g_postprocess_invalid", "")).lower() in {"true", "1"}))
            c1_by_task[task] = {"base_task_id": task, "image_id": row.get("image_id", ""), "building_id": row.get("building_id", ""), "g_model_struct": g_model_struct, "d_model_feat": row.get("d_model_feat", ""), "d_model_feat_local_max": row.get("d_model_feat_local", ""), "d_cal_A": row.get("d_cal_A", "")}
        except (TypeError, ValueError):
            continue
    # d_cal_A is a leave-one-C1-task-out distance in the frozen C1 feature
    # space.  It is derived before the reference table is written, so the C1
    # slope fit can never be fed future C2 candidate distances.
    c1_feature_names = ("d_model_feat", "d_model_feat_local_max", "g_model_struct")
    c1_feature_rows = []
    for task, row in c1_by_task.items():
        try:
            c1_feature_rows.append((task, np.asarray([float(row[name]) for name in c1_feature_names], dtype=float)))
        except (KeyError, TypeError, ValueError):
            continue
    if c1_feature_rows:
        c1_matrix = np.stack([vector for _task, vector in c1_feature_rows])
        c1_scale = c1_matrix.std(axis=0); c1_scale[c1_scale == 0] = 1.0
        normalized = c1_matrix / c1_scale
        for index, (task, _vector) in enumerate(c1_feature_rows):
            try:
                float(c1_by_task[task].get("d_cal_A", ""))
            except (TypeError, ValueError):
                peers = np.delete(normalized, index, axis=0)
                c1_by_task[task]["d_cal_A"] = float(np.min(np.linalg.norm(peers - normalized[index], axis=1))) if len(peers) else 0.0
    c1_reference_output = output_dir / "c1_task_risk_reference.csv"
    _write(c1_reference_output, list(c1_by_task.values()))
    (output_dir / "c1_task_risk_reference_manifest.json").write_text(json.dumps({
        "schema_version": "c1_task_risk_reference_v1", "unit": "base_task_id",
        "n_base_tasks": len(c1_by_task), "source_preannotation_feature_sha256": sha256_file(c1_task_feature_csv),
        "reference_sha256": sha256_file(c1_reference_output),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reference_rows = list(c1_by_task.values())
    if c1_risk_reference_csv:
        reference_rows = _read(c1_risk_reference_csv)
    c1_channels = {name: [] for name in c1_channels}
    complete_reference_rows = []
    for row in reference_rows:
        vector = {}
        for name in c1_channels:
            try: vector[name] = float(row[name])
            except (KeyError, TypeError, ValueError): pass
        if len(vector) >= 3:
            complete_reference_rows.append({"base_task_id": row.get("base_task_id", ""), **vector})
            for name, value in vector.items(): c1_channels[name].append(value)
    c1_scores = sorted(row["g_model_struct"] for row in complete_reference_rows if "g_model_struct" in row)
    support_names = ("d_model_feat", "d_model_feat_local_max", "g_model_struct")
    support_matrix = np.asarray(list(zip(*(c1_channels[name] for name in support_names))), dtype=float) if all(c1_channels[name] for name in support_names) and len({len(c1_channels[name]) for name in support_names}) == 1 else np.empty((0, 3))
    support_scale = support_matrix.std(axis=0) if len(support_matrix) else np.ones(3)
    support_scale[support_scale == 0] = 1.0
    if len(support_matrix) and not c1_channels["d_cal_A"]:
        normalized = support_matrix / support_scale
        c1_channels["d_cal_A"] = [float(np.min(np.linalg.norm(np.delete(normalized, index, axis=0) - normalized[index], axis=1))) if len(normalized) > 1 else 0.0 for index in range(len(normalized))]
    feature_status = "not_requested"
    candidate_features: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    reference_features: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if extract_lhfeat:
        if not checkpoint or not reference_dir:
            raise ValueError("checkpoint and reference_dir are required for LHFeat")
        try:
            candidate_paths = [Path(row.get("source_path", "")) for row in inventory if Path(row.get("source_path", "")).exists()]
            reference_paths = sorted(path for path in reference_dir.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
            reference_features = _lhfeat_descriptors(reference_paths, checkpoint)
            candidate_features = _lhfeat_descriptors(candidate_paths, checkpoint)
            feature_status = "ready" if _feature_freeze_ready(feature_freeze_manifest) else "not_ready_feature_freeze_incomplete"
        except RuntimeError:
            if input_status == "formal":
                raise
            feature_status = "dependency_unavailable"
    ref_global = np.stack([value[0] for value in reference_features.values()]) if reference_features else None
    ref_local = np.stack([value[1] for value in reference_features.values()]) if reference_features else None
    channel_scales = {name: (float(np.std(c1_channels[name])) if c1_channels[name] else 1.0) or 1.0 for name in RISK_VECTOR_FIELDS}
    rows = []
    for item in inventory:
        task = item.get("task_id", ""); layout = _layout_features(layout_dir / f"{task}.json")
        g = layout.get("g_model_struct")
        d_cal = ""
        source_path = Path(item.get("source_path", ""))
        feature = candidate_features.get(source_path.resolve().as_posix()) if source_path.exists() else None
        global_distance = _knn(feature[0], ref_global) if feature and ref_global is not None else ""
        local_distance = _knn(feature[1], ref_local) if feature and ref_local is not None else ""
        if global_distance != "" and local_distance != "" and g != "" and len(support_matrix):
            vector = np.asarray([global_distance, local_distance, g], dtype=float) / support_scale
            d_cal = _knn(vector, support_matrix / support_scale)
        channels = {"d_model_feat": global_distance, "d_model_feat_local_max": local_distance, "g_model_struct": g, "d_cal_A": d_cal}
        numeric = {name: float(value) for name, value in channels.items() if value != ""}
        vector = _frozen_vector(numeric, channel_scales)
        score = _score(vector)
        reference_scores = [_score(_frozen_vector({name: float(reference.get(name, "")) for name in RISK_VECTOR_FIELDS}, channel_scales)) for reference in complete_reference_rows]
        reference_scores = [value for value in reference_scores if value is not None]
        score_percentile = sum(value <= score for value in reference_scores) / len(reference_scores) if score is not None and reference_scores else None
        bucket = "stress" if score_percentile is not None and score_percentile >= stress_quantile else "ordinary"
        percentiles = {"risk_design_score_A": score_percentile} if score_percentile is not None else {}
        assist_ready = len(numeric) == 4 and all(c1_channels.values()) and layout.get("postprocess_valid") is True
        route_score = ""  # Requires cross-fitted C1 outcomes; model-only Q75 must never impersonate routing risk.
        source_holdout_ready = all(str(item.get(field, "")).lower() in {"true", "1"} for field in ("source_split_allowed", "history_clear", "future_holdout_clear"))
        reference_ready = str(item.get("reference_status") or item.get("geometry_gold_ready") or "").lower() in {"reference_ready", "true", "1"}
        scope_ready = str(item.get("scope_status") or item.get("final_scope") or "").lower() in {"in_scope", "included", "true", "1"}
        risk_design_ready = vector is not None and score is not None and layout.get("postprocess_valid") is True and source_holdout_ready and reference_ready and scope_ready and bool(item.get("building_id"))
        c1_frozen = False
        if c1_freeze_manifest and c1_freeze_manifest.exists():
            try:
                c1_frozen = bool(json.loads(c1_freeze_manifest.read_text(encoding="utf-8")).get("C1_MEASUREMENT_FROZEN"))
            except (OSError, json.JSONDecodeError):
                c1_frozen = False
        design_frozen = input_status == "formal" and c1_frozen and risk_design_ready and feature_status == "ready"
        rows.append({
            **item, **layout, "d_model_feat": global_distance, "d_model_feat_local_max": local_distance,
            "d_cal_A": d_cal, "d_cal_F": "", "d_cal_F_status": "post_c2_only",
            "risk_design_vector_A": json.dumps(vector, separators=(",", ":")) if vector is not None else "",
            "risk_design_score_A": "" if score is None else score,
            "risk_design_A": "",
            "risk_design_A_status": "frozen_from_C1" if design_frozen else "pending_complete_C1" if input_status != "formal" else "not_evaluable",
            "risk_design_stratum": bucket if design_frozen else "",
            "risk_design_stratum_status": "frozen_from_C1" if design_frozen else "provisional_not_frozen" if input_status != "formal" else "not_evaluable",
            "risk_assist_candidate": bucket if assist_ready else "", "risk_route_candidate": route_score,
            "risk_assist_status": "ready" if assist_ready else "not_evaluable", "risk_route_status": "pending_c2b_confirmation",
            "risk_channel_percentiles_json": json.dumps(percentiles, sort_keys=True), "risk_bucket_rule": contract["stratum_rule"]["name"],
            "assignment_eligible": design_frozen,
            "reference_ready": reference_ready, "scope_ready": scope_ready, "source_holdout_ready": source_holdout_ready,
            "feature_status": feature_status, "checkpoint_sha256": sha256_file(checkpoint) if checkpoint and checkpoint.exists() else "",
            "feature_freeze_manifest_sha256": sha256_file(feature_freeze_manifest) if feature_freeze_manifest and feature_freeze_manifest.exists() else "",
            "risk_contract_sha256": sha256_file(contract_path),
            "risk_status": "candidate_only" if input_status != "formal" else "frozen" if design_frozen else "not_evaluable",
        })
    inventory_output = output_dir / "c2_task_risk_inventory.csv"
    _write(inventory_output, rows)
    eligible_rows = [row for row in rows if row["assignment_eligible"]]
    eligible_buildings = {row.get("building_id") for row in eligible_rows if row.get("building_id")}
    eligible_strata = {row.get("risk_design_stratum") for row in eligible_rows}
    c1_state = {}
    if c1_freeze_manifest and c1_freeze_manifest.exists():
        try: c1_state = json.loads(c1_freeze_manifest.read_text(encoding="utf-8")).get("state_machine", {})
        except (OSError, json.JSONDecodeError): c1_state = {}
    summary = {
        "input_status": input_status, "method_contract": contract["method_contract"], "n_tasks": len(rows), "n_c1_calibration_tasks": len(reference_rows),
        "n_assignment_eligible": len(eligible_rows), "eligible_building_count": len(eligible_buildings),
        "feature_status": feature_status, "formal_ready": input_status == "formal" and bool(c1_state.get("C1_MEASUREMENT_FROZEN")) and feature_status == "ready" and len(eligible_rows) >= 12 and len(eligible_buildings) >= 2 and eligible_strata >= {"ordinary", "stress"},
        "risk_design_A_status": "frozen_from_C1" if input_status == "formal" and feature_status == "ready" else "pending_complete_C1" if input_status != "formal" else "not_evaluable",
        "risk_design_stratum_status": "frozen_from_C1" if input_status == "formal" and feature_status == "ready" else "provisional_not_frozen" if input_status != "formal" else "not_evaluable",
        "risk_contract_path": str(contract_path), "risk_contract_sha256": sha256_file(contract_path),
        "checkpoint_sha256": sha256_file(checkpoint) if checkpoint and checkpoint.exists() else "",
        "feature_freeze_manifest_sha256": sha256_file(feature_freeze_manifest) if feature_freeze_manifest and feature_freeze_manifest.exists() else "",
        "config_sha256": sha256_file(_PROJECT_ROOT / contract["feature_freeze"]["config"]) if (_PROJECT_ROOT / contract["feature_freeze"]["config"]).exists() else "",
        "inventory_sha256": sha256_file(inventory_csv), "c1_preannotation_feature_sha256": sha256_file(c1_task_feature_csv),
        "c1_risk_reference_sha256": sha256_file(c1_risk_reference_csv) if c1_risk_reference_csv else "",
        "output_inventory_sha256": sha256_file(inventory_output),
        "c1_task_risk_reference_path": str(c1_reference_output), "c1_task_risk_reference_sha256": sha256_file(c1_reference_output),
    }
    summary["state_machine"] = {
        "C1_COLLECTION_INCOMPLETE": bool(c1_state.get("C1_COLLECTION_INCOMPLETE", False)),
        "C1_CANONICAL_CLOSED": bool(c1_state.get("C1_CANONICAL_CLOSED", False)),
        "C1_MEASUREMENT_FROZEN": bool(c1_state.get("C1_MEASUREMENT_FROZEN", False)),
        "C2B_RISK_DESIGN_FROZEN": input_status == "formal" and feature_status == "ready",
        "C2B_DESIGN_FROZEN": False,
        "C2B_ASSIGNMENT_MATERIALIZED": False,
        "C2B_LAUNCH_READY": False,
    }
    (output_dir / "c2_task_risk.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory-csv", type=Path, required=True)
    parser.add_argument("--layout-dir", type=Path, required=True)
    parser.add_argument("--c1-task-feature-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-status", choices=("precloseout_rehearsal", "formal"), required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--extract-lhfeat", action="store_true")
    parser.add_argument("--c1-risk-reference-csv", type=Path)
    parser.add_argument("--risk-contract", type=Path)
    parser.add_argument("--feature-freeze-manifest", type=Path)
    parser.add_argument("--c1-freeze-manifest", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.inventory_csv, args.layout_dir, args.c1_task_feature_csv, args.output_dir, input_status=args.input_status, checkpoint=args.checkpoint, reference_dir=args.reference_dir, extract_lhfeat=args.extract_lhfeat, c1_risk_reference_csv=args.c1_risk_reference_csv, risk_contract=args.risk_contract, feature_freeze_manifest=args.feature_freeze_manifest, c1_freeze_manifest=args.c1_freeze_manifest), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
