import argparse
import csv
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


DEFAULT_IMAGE_BASE_URL = os.environ.get(
    "HOHONET_IMAGE_BASE_URL",
    "https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/img_v",
)
DEFAULT_VIS_BASE_URL = os.environ.get("HOHONET_VIS_BASE_URL", "http://175.178.71.217:8000")
DEFAULT_MODEL_VERSION = "HoHoNet_smoke_test"
DEFAULT_DATASET_GROUP = "MP3D_TXT_SMOKE"
DEFAULT_PROJECT_VERSION = "smoke_v1"
W = 1024
H = 512


@dataclass(frozen=True)
class Candidate:
    base_task_id: str
    split_name: str
    gold_txt_path: Path
    model_txt_path: Path
    image_path: Path


def _load_prescreen_base_ids(registry_csv: Path) -> set[str]:
    with registry_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return {
            str(row.get("base_task_id", "")).strip()
            for row in reader
            if str(row.get("base_task_id", "")).strip()
        }


def _discover_candidates(
    repo_root: Path,
    exclude_base_ids: set[str],
    model_txt_dir: Path,
) -> list[Candidate]:
    gold_root = repo_root / "data" / "mp3d_layout"
    image_root = gold_root / "img_v"

    candidates: list[Candidate] = []
    for gold_txt in gold_root.glob("*/*/*.txt"):
        if gold_txt.parent.name != "label_cor":
            continue
        base_task_id = gold_txt.stem
        if base_task_id in exclude_base_ids:
            continue

        split_name = gold_txt.parent.parent.name
        model_txt = model_txt_dir / f"{base_task_id}.txt"
        image_path = image_root / f"{base_task_id}.jpg"
        if not model_txt.exists() or not image_path.exists():
            continue

        candidates.append(
            Candidate(
                base_task_id=base_task_id,
                split_name=split_name,
                gold_txt_path=gold_txt,
                model_txt_path=model_txt,
                image_path=image_path,
            )
        )

    candidates.sort(key=lambda c: c.base_task_id)
    return candidates


def _load_layout_txt(txt_path: Path) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    with txt_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            coords.append((float(parts[0]), float(parts[1])))
    if not coords:
        raise ValueError(f"Empty layout txt: {txt_path}")
    return coords


def _interpolate_points(p1, p2, num_steps=10):
    def to_3d(p):
        u, v = p[0], p[1]
        lon = (u / W - 0.5) * 2 * np.pi
        lat = -(v / H - 0.5) * np.pi
        x = np.cos(lat) * np.sin(lon)
        y = np.sin(lat)
        z = np.cos(lat) * np.cos(lon)
        return np.array([x, y, z])

    def to_uv(vec):
        x, y, z = vec
        norm = np.sqrt(x * x + y * y + z * z)
        if norm == 0:
            return [0.0, 0.0]
        x, y, z = x / norm, y / norm, z / norm
        lat = np.arcsin(y)
        lon = np.arctan2(x, z)
        u = (lon / (2 * np.pi) + 0.5) * W
        v = (-lat / np.pi + 0.5) * H
        return [u, v]

    vec1 = to_3d(p1)
    vec2 = to_3d(p2)
    if abs(vec1[1]) < 1e-6 or abs(vec2[1]) < 1e-6:
        return np.linspace(p1, p2, num_steps, endpoint=False).tolist()

    p1_plane = vec1 / abs(vec1[1])
    p2_plane = vec2 / abs(vec2[1])

    new_points = []
    for t in np.linspace(0, 1, num_steps, endpoint=False):
        pt = p1_plane * (1 - t) + p2_plane * t
        new_points.append(to_uv(pt))
    return new_points


def _build_polygon_from_pairs(coords: list[tuple[float, float]]) -> list[list[float]]:
    ceil_pts = coords[0::2]
    floor_pts = coords[1::2]
    pairs = list(zip(ceil_pts, floor_pts))
    pairs.sort(key=lambda p: p[0][0])
    sorted_ceil = [p[0] for p in pairs]
    sorted_floor = [p[1] for p in pairs]

    dense_poly_points: list[list[float]] = []

    for i in range(len(sorted_ceil)):
        p_curr = sorted_ceil[i]
        p_next = sorted_ceil[(i + 1) % len(sorted_ceil)]
        if abs(p_curr[0] - p_next[0]) > W / 2:
            dense_poly_points.append([p_curr[0], p_curr[1]])
        else:
            if i < len(sorted_ceil) - 1 or abs(p_curr[0] - p_next[0]) < W / 2:
                dense_poly_points.extend(_interpolate_points(p_curr, p_next))
            else:
                dense_poly_points.append([p_curr[0], p_curr[1]])

    reversed_floor = sorted_floor[::-1]
    for i in range(len(reversed_floor)):
        p_curr = reversed_floor[i]
        p_next = reversed_floor[(i + 1) % len(reversed_floor)]
        if abs(p_curr[0] - p_next[0]) > W / 2:
            dense_poly_points.append([p_curr[0], p_curr[1]])
        else:
            if i < len(reversed_floor) - 1 or abs(p_curr[0] - p_next[0]) < W / 2:
                dense_poly_points.extend(_interpolate_points(p_curr, p_next))
            else:
                dense_poly_points.append([p_curr[0], p_curr[1]])

    return [[p[0] / W * 100, p[1] / H * 100] for p in dense_poly_points]


def _layout_to_ls_result(coords: list[tuple[float, float]]) -> list[dict]:
    result: list[dict] = []
    for i, (x, y) in enumerate(coords):
        result.append(
            {
                "id": f"kp_{i}",
                "from_name": "kp",
                "to_name": "img",
                "type": "keypointlabels",
                "original_width": W,
                "original_height": H,
                "value": {
                    "x": x / W * 100,
                    "y": y / H * 100,
                    "width": 0.5,
                    "keypointlabels": ["Corner"],
                },
            }
        )

    result.append(
        {
            "id": "poly_1",
            "from_name": "poly",
            "to_name": "img",
            "type": "polygonlabels",
            "original_width": W,
            "original_height": H,
            "value": {
                "points": _build_polygon_from_pairs(coords),
                "polygonlabels": ["Wall"],
            },
        }
    )
    return result


def _append_scope_choice(result: list[dict], scope_value: str = "normal") -> list[dict]:
    out = list(result)
    out.append(
        {
            "id": "scope_0",
            "from_name": "scope",
            "to_name": "img",
            "type": "choices",
            "value": {"choices": [scope_value]},
        }
    )
    return out


def _make_prediction(result: list[dict]) -> dict:
    return {
        "model_version": DEFAULT_MODEL_VERSION,
        "score": 0.99,
        "result": result,
    }


def _make_annotation(result: list[dict], completed_by: int) -> dict:
    return {
        "result": result,
        "ground_truth": False,
        "was_cancelled": False,
        "completed_by": completed_by,
        "lead_time": 0.0,
    }


def _build_task(candidate: Candidate, task_index: int, image_base_url: str, completed_by: int) -> dict:
    pred_result = _layout_to_ls_result(_load_layout_txt(candidate.model_txt_path))
    ann_result = _append_scope_choice(_layout_to_ls_result(_load_layout_txt(candidate.gold_txt_path)))

    return {
        "id": task_index,
        "project": 999001,
        "predictions": [_make_prediction(pred_result)],
        "annotations": [_make_annotation(ann_result, completed_by=completed_by)],
        "data": {
            "image": f"{image_base_url.rstrip('/')}/{candidate.base_task_id}.jpg",
            "title": f"{candidate.base_task_id}.jpg",
            "dataset_group": DEFAULT_DATASET_GROUP,
            "init_type": "model_output_txt_smoke",
            "smoke_test": True,
            "gold_source": "mp3d_label_cor_txt",
            "prediction_source": "model_output_txt",
            "split_name": candidate.split_name,
            "base_task_id": candidate.base_task_id,
        },
    }


def build_vis_3d_url(coords: list[tuple[float, float]], vis_base_url: str = DEFAULT_VIS_BASE_URL) -> str:
    pairs = list(zip(coords[0::2], coords[1::2]))
    pairs.sort(key=lambda p: p[0][0])
    vis_corners = [
        {
            "x": c[0],
            "y_ceiling": c[1],
            "y_floor": f[1],
        }
        for c, f in pairs
    ]
    encoded = json.dumps(vis_corners, ensure_ascii=False)
    from urllib.parse import quote

    return f"{vis_base_url.rstrip('/')}/tools/vis_3d.html?w={W}&h={H}&data={quote(encoded)}"


def build_smoke_test_payload(
    repo_root: Path,
    sample_count: int = 5,
    random_seed: int = 20260328,
    image_base_url: str = DEFAULT_IMAGE_BASE_URL,
    completed_by: int = 999,
) -> dict:
    registry_csv = repo_root / "analysis_results" / "truth_layer_extraction_20260324" / "trap_task_registry_v1.csv"
    model_txt_dir = repo_root / "output" / "mp3d_layout" / "HOHO_layout_aug_efficienthc_Transen1_resnet34"
    exclude_base_ids = _load_prescreen_base_ids(registry_csv)
    candidates = _discover_candidates(repo_root, exclude_base_ids=exclude_base_ids, model_txt_dir=model_txt_dir)
    if len(candidates) < sample_count:
        raise ValueError(f"Not enough eligible candidates: need {sample_count}, got {len(candidates)}")

    rng = random.Random(random_seed)
    chosen = sorted(rng.sample(candidates, sample_count), key=lambda c: c.base_task_id)
    tasks = [
        _build_task(candidate, task_index=i + 1, image_base_url=image_base_url, completed_by=completed_by)
        for i, candidate in enumerate(chosen)
    ]

    return {
        "tasks": tasks,
        "summary": {
            "sample_count": len(tasks),
            "random_seed": random_seed,
            "completed_by": completed_by,
            "dataset_group": DEFAULT_DATASET_GROUP,
            "project_version": DEFAULT_PROJECT_VERSION,
            "excluded_prescreen_base_id_count": len(exclude_base_ids),
            "candidate_pool_size": len(candidates),
            "sampled_base_task_ids": [c.base_task_id for c in chosen],
            "sampled_split_names": {c.base_task_id: c.split_name for c in chosen},
        },
        "selected_candidates": chosen,
    }


def _write_manifest_csv(path: Path, candidates: Iterable[Candidate]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "base_task_id",
                "split_name",
                "gold_txt_path",
                "model_txt_path",
                "image_path",
            ],
        )
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "base_task_id": candidate.base_task_id,
                    "split_name": candidate.split_name,
                    "gold_txt_path": str(candidate.gold_txt_path),
                    "model_txt_path": str(candidate.model_txt_path),
                    "image_path": str(candidate.image_path),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a small MP3D txt-based pseudo-gold smoke test.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--random-seed", type=int, default=20260328)
    parser.add_argument("--completed-by", type=int, default=999)
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Default: analysis_results/mp3d_txt_smoke_test_20260328",
    )
    parser.add_argument("--image-base-url", default=DEFAULT_IMAGE_BASE_URL)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (
        repo_root / "analysis_results" / "mp3d_txt_smoke_test_20260328"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = build_smoke_test_payload(
        repo_root=repo_root,
        sample_count=args.sample_count,
        random_seed=args.random_seed,
        image_base_url=args.image_base_url,
        completed_by=args.completed_by,
    )

    export_path = output_dir / "mp3d_txt_smoke_export_v1.json"
    summary_path = output_dir / "mp3d_txt_smoke_summary_v1.json"
    manifest_path = output_dir / "mp3d_txt_smoke_manifest_v1.csv"

    with export_path.open("w", encoding="utf-8") as f:
        json.dump(payload["tasks"], f, ensure_ascii=False, indent=2)

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(payload["summary"], f, ensure_ascii=False, indent=2)

    _write_manifest_csv(manifest_path, payload["selected_candidates"])

    print(f"[OK] wrote pseudo export: {export_path}")
    print(f"[OK] wrote summary: {summary_path}")
    print(f"[OK] wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
