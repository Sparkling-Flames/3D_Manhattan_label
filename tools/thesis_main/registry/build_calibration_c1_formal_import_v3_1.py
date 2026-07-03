from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.registry.build_calibration_smoke_import_v3_1 import (
    FOREIGN_BASE,
    REBUILD_DIR,
    ZH_BASE,
    _mapping,
    _prediction_from_vis,
    _read_csv,
    _rewrite_vis_base,
    _write_json,
    _write_text,
)


OUT_DIR = Path("import_json/calibration_c1_v3_1_formal")


def _task(row: dict[str, str], mapping: dict[str, dict], dataset_group: str, source_draft: str, base: str, include_prediction: bool) -> dict:
    mapped = mapping[row["base_task_id"]]
    vis_3d = _rewrite_vis_base(mapped["vis_3d"], base)
    data = {
        "image": mapped["image"],
        "vis_3d": vis_3d,
        "title": mapped["title"],
        "dataset_group": dataset_group,
        "condition": "semi" if include_prediction else "manual",
        "task_id": row["task_id"],
        "base_task_id": row["base_task_id"],
        "image_id": row.get("image_id") or row.get("image_stem") or row["base_task_id"],
        "calibration_version": "C1_v3_1",
        "source_draft": source_draft,
        "artifact_status": "formal_c1_import_json",
        "launch_allowed": True,
    }
    task = {"data": data}
    if include_prediction:
        task["predictions"] = _prediction_from_vis(vis_3d)
    return task


def build(root: Path) -> dict:
    mapping = _mapping(root)
    pools = [
        ("anchor", "C1_anchor_all", "calibration_anchor_draft_v2.csv", False),
        ("core", "C1_core_all", "calibration_core_draft_v3_1.csv", False),
        ("semi", "C1_semi", "calibration_semi_selection_draft_v3_1.csv", True),
    ]
    out = root / OUT_DIR
    files = []
    for label, base in [("zh", ZH_BASE), ("foreign_https", FOREIGN_BASE)]:
        for source_draft, dataset_group, filename, include_prediction in pools:
            rows = _read_csv(root / REBUILD_DIR / filename)
            tasks = [_task(row, mapping, dataset_group, source_draft, base, include_prediction) for row in rows]
            path = out / f"c1_v3_1_{source_draft}_import_{label}.json"
            _write_json(path, tasks)
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "project_name": dataset_group,
                    "source_draft": source_draft,
                    "task_count": len(tasks),
                    "condition": "semi" if include_prediction else "manual",
                    "vis_3d_base": base,
                    "all_have_predictions": all("predictions" in task for task in tasks) if include_prediction else False,
                }
            )
    summary = {
        "created_for": "C1_v3_1_formal_import_json",
        "status": "formal_import_json_ready_for_researcher_manual_import",
        "no_label_studio_api_call": True,
        "source": "calibration v3.1 frozen anchor/core/semi drafts + export_label/groudTruth.json mapping",
        "counts": {"anchor": 12, "core": 75, "semi": 25},
        "files": files,
        "service_compatibility": {
            "zh_175_http": {
                "files": ["c1_v3_1_anchor_import_zh.json", "c1_v3_1_core_import_zh.json", "c1_v3_1_semi_import_zh.json"],
                "vis_3d_base": ZH_BASE,
                "intended_label_studio_entry": "175.178/http Chinese entry",
            },
            "foreign_https": {
                "files": [
                    "c1_v3_1_anchor_import_foreign_https.json",
                    "c1_v3_1_core_import_foreign_https.json",
                    "c1_v3_1_semi_import_foreign_https.json",
                ],
                "vis_3d_base": FOREIGN_BASE,
                "intended_label_studio_entry": "https foreign entry",
            },
            "do_not_mix_entries": True,
            "reason": "$vis_3d is fetched by the Label Studio frontend, so scheme/CORS must match the service entry.",
        },
        "reserve_included": False,
        "worker_facing_distribution_generated": False,
    }
    _write_json(out / "c1_v3_1_formal_import_summary.json", summary)
    _write_text(
        out / "README.md",
        "\n".join(
            [
                "# C1 v3.1 formal import JSON",
                "",
                "- `*_zh.json` only for the 175.178/http Chinese Label Studio entry.",
                "- `*_foreign_https.json` only for the https foreign Label Studio entry.",
                "- Import projects separately: `C1_anchor_all`, `C1_core_all`, `C1_semi`.",
                "- Reserve is not included in C1.",
                "- Files were generated locally only; no Label Studio API call was made.",
                "",
            ]
        ),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    build(args.root.resolve())


if __name__ == "__main__":
    main()
