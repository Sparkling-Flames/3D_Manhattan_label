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
    points = [[float(row["x"]), float(row["y_ceiling"])] for row in corners] + [[float(row["x"]), float(row["y_floor"])] for row in corners]
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
            output[path.stem] = (np.concatenate([feature.mean(1), feature.std(1)]), feature.max(1))
    return output


def _knn(candidate: np.ndarray, reference: np.ndarray, k: int = 5) -> float:
    distances = np.linalg.norm(reference - candidate[None], axis=1)
    return float(np.mean(np.partition(distances, min(k, len(distances)) - 1)[:min(k, len(distances))]))


def materialize(
    inventory_csv: Path, layout_dir: Path, c1_geometry_jsonl: Path, output_dir: Path, *,
    input_status: str, checkpoint: Path | None = None, reference_dir: Path | None = None,
    extract_lhfeat: bool = False,
) -> dict[str, Any]:
    inventory = _read(inventory_csv)
    c1_scores = []
    for line in c1_geometry_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line); geometry = normalize_geometry(row.get("corners_px") or [])
        if geometry["valid"]:
            c1_scores.append(min(1.0, abs(int(geometry["n_pairs"]) - 6) / 8))
    c1_scores.sort()
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
            feature_status = "ready"
        except RuntimeError:
            if input_status == "formal":
                raise
            feature_status = "dependency_unavailable"
    ref_global = np.stack([value[0] for value in reference_features.values()]) if reference_features else None
    ref_local = np.stack([value[1] for value in reference_features.values()]) if reference_features else None
    rows = []
    for item in inventory:
        task = item.get("task_id", ""); layout = _layout_features(layout_dir / f"{task}.json")
        g = layout.get("g_model_struct")
        d_cal = (sum(value <= float(g) for value in c1_scores) / len(c1_scores)) if c1_scores and g != "" else ""
        feature = candidate_features.get(Path(item.get("source_path", "")).stem)
        global_distance = _knn(feature[0], ref_global) if feature and ref_global is not None else ""
        local_distance = _knn(feature[1], ref_local) if feature and ref_local is not None else ""
        route = float(d_cal) if d_cal != "" else ""
        rows.append({
            **item, **layout, "d_model_feat": global_distance, "d_model_feat_local_max": local_distance,
            "d_cal_A": d_cal, "risk_assist_candidate": route, "risk_route_candidate": route,
            "feature_status": feature_status, "checkpoint_sha256": sha256_file(checkpoint) if checkpoint and checkpoint.exists() else "",
            "risk_status": "candidate_only" if input_status != "formal" else "frozen",
        })
    _write(output_dir / "c2_task_risk_inventory.csv", rows)
    summary = {
        "input_status": input_status, "n_tasks": len(rows), "n_c1_calibration_tasks": len(c1_scores),
        "feature_status": feature_status, "formal_ready": input_status == "formal" and feature_status == "ready",
        "checkpoint_sha256": sha256_file(checkpoint) if checkpoint and checkpoint.exists() else "",
        "inventory_sha256": sha256_file(inventory_csv), "c1_geometry_sha256": sha256_file(c1_geometry_jsonl),
    }
    (output_dir / "c2_task_risk.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory-csv", type=Path, required=True)
    parser.add_argument("--layout-dir", type=Path, required=True)
    parser.add_argument("--c1-geometry-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-status", choices=("precloseout_rehearsal", "formal"), required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--extract-lhfeat", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.inventory_csv, args.layout_dir, args.c1_geometry_jsonl, args.output_dir, input_status=args.input_status, checkpoint=args.checkpoint, reference_dir=args.reference_dir, extract_lhfeat=args.extract_lhfeat), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
