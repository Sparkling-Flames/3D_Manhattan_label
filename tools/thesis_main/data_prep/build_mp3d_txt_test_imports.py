import argparse
import csv
import json
import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thesis_main.data_prep.build_mp3d_txt_smoke_test import (
    DEFAULT_DATASET_GROUP,
    DEFAULT_IMAGE_BASE_URL,
    DEFAULT_VIS_BASE_URL,
    Candidate,
    _layout_to_ls_result,
    _load_layout_txt,
    _make_prediction,
    build_smoke_test_payload,
    build_vis_3d_url,
)


def _relpath_str(path: Path, repo_root: Path) -> str:
    return str(path.resolve().relative_to(repo_root.resolve()))


def _build_manual_task(repo_root: Path, candidate: Candidate, image_base_url: str, vis_base_url: str) -> dict:
    return {
        "data": {
            "image": f"{image_base_url.rstrip('/')}/{candidate.base_task_id}.jpg",
            "vis_3d": f"{vis_base_url.rstrip('/')}/tools/vis_3d.html",
            "title": f"{candidate.base_task_id}.jpg",
            "dataset_group": f"{DEFAULT_DATASET_GROUP}_manual",
            "condition": "manual",
            "smoke_test": True,
            "base_task_id": candidate.base_task_id,
            "split_name": candidate.split_name,
            "pseudo_gold_source": "mp3d_label_cor_txt",
            "pseudo_gold_txt_path": _relpath_str(candidate.gold_txt_path, repo_root),
        }
    }


def _build_semi_task(repo_root: Path, candidate: Candidate, image_base_url: str, vis_base_url: str) -> dict:
    proposal_coords = _load_layout_txt(candidate.model_txt_path)
    return {
        "data": {
            "image": f"{image_base_url.rstrip('/')}/{candidate.base_task_id}.jpg",
            "vis_3d": build_vis_3d_url(proposal_coords, vis_base_url=vis_base_url),
            "title": f"{candidate.base_task_id}.jpg",
            "dataset_group": f"{DEFAULT_DATASET_GROUP}_semi",
            "condition": "semi",
            "smoke_test": True,
            "base_task_id": candidate.base_task_id,
            "split_name": candidate.split_name,
            "init_type": "model_output_txt_smoke",
            "pseudo_gold_source": "mp3d_label_cor_txt",
            "pseudo_gold_txt_path": _relpath_str(candidate.gold_txt_path, repo_root),
            "proposal_source_kind": "model_output_txt",
            "proposal_source_path": _relpath_str(candidate.model_txt_path, repo_root),
            "proposal_coord_contract": "hohonet_model_output_layout_txt@1024x512",
        },
        "predictions": [
            _make_prediction(_layout_to_ls_result(proposal_coords))
        ],
    }


def _write_manifest_csv(path: Path, repo_root: Path, candidates: list[Candidate]) -> None:
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
                    "gold_txt_path": _relpath_str(candidate.gold_txt_path, repo_root),
                    "model_txt_path": _relpath_str(candidate.model_txt_path, repo_root),
                    "image_path": _relpath_str(candidate.image_path, repo_root),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build manual/semi Label Studio smoke-test import JSON files.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--random-seed", type=int, default=20260328)
    parser.add_argument("--image-base-url", default=DEFAULT_IMAGE_BASE_URL)
    parser.add_argument("--vis-base-url", default=DEFAULT_VIS_BASE_URL)
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Default: import_json/mp3d_txt_smoke_test_20260328",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (
        repo_root / "import_json" / "mp3d_txt_smoke_test_20260328"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = build_smoke_test_payload(
        repo_root=repo_root,
        sample_count=args.sample_count,
        random_seed=args.random_seed,
    )
    candidates = payload["selected_candidates"]

    manual_tasks = [
        _build_manual_task(repo_root, candidate, args.image_base_url, args.vis_base_url)
        for candidate in candidates
    ]
    semi_tasks = [
        _build_semi_task(repo_root, candidate, args.image_base_url, args.vis_base_url)
        for candidate in candidates
    ]

    manual_path = output_dir / "mp3d_txt_manual_smoke_import_v1.json"
    semi_path = output_dir / "mp3d_txt_semi_smoke_import_v1.json"
    summary_path = output_dir / "mp3d_txt_test_import_summary_v1.json"
    manifest_path = output_dir / "mp3d_txt_test_manifest_v1.csv"

    with manual_path.open("w", encoding="utf-8") as f:
        json.dump(manual_tasks, f, ensure_ascii=False, indent=2)
    with semi_path.open("w", encoding="utf-8") as f:
        json.dump(semi_tasks, f, ensure_ascii=False, indent=2)

    summary = {
        "sample_count": len(candidates),
        "random_seed": args.random_seed,
        "sampled_base_task_ids": [c.base_task_id for c in candidates],
        "manual_import_file": str(manual_path),
        "semi_import_file": str(semi_path),
        "manifest_file": str(manifest_path),
        "manual_has_predictions": False,
        "semi_has_predictions": True,
        "pseudo_gold_source": "mp3d_label_cor_txt",
        "proposal_source": "output_model_txt",
    }
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    _write_manifest_csv(manifest_path, repo_root, candidates)

    print(f"[OK] wrote manual import: {manual_path}")
    print(f"[OK] wrote semi import: {semi_path}")
    print(f"[OK] wrote summary: {summary_path}")
    print(f"[OK] wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
