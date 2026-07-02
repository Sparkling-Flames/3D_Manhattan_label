from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


OUT_DIR = Path("import_json/calibration_c1_v3_1_smoke")
REBUILD_DIR = Path("analysis_results/calibration_rebuild_20260702")
ZH_BASE = "http://175.178.71.217:8000"
FOREIGN_BASE = "https://label.sparkle0825.top"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _stem(value: str) -> str:
    return Path(str(value)).stem


def _mapping(root: Path) -> dict[str, dict]:
    rows = json.loads((root / "export_label/groudTruth.json").read_text(encoding="utf-8"))
    out = {}
    for row in rows:
        data = row.get("data") or {}
        stem = _stem(data.get("title") or data.get("image") or "")
        if stem:
            out[stem] = data
    return out


def _rewrite_vis_base(url: str, base: str) -> str:
    parsed = urlparse(url)
    base_parsed = urlparse(base)
    return urlunparse((base_parsed.scheme, base_parsed.netloc, parsed.path, "", parsed.query, ""))


def _prediction_from_vis(vis_3d: str) -> list[dict]:
    data = parse_qs(urlparse(vis_3d).query).get("data", ["[]"])[0]
    try:
        corners = json.loads(data)
    except json.JSONDecodeError:
        corners = []
    result = []
    ceiling_points = []
    floor_points = []
    idx = 0
    for corner in corners:
        x_pct = float(corner.get("x", 0)) / 1024 * 100
        ceiling_pct = float(corner.get("y_ceiling", 0)) / 512 * 100
        floor_pct = float(corner.get("y_floor", 0)) / 512 * 100
        ceiling_points.append([x_pct, ceiling_pct])
        floor_points.append([x_pct, floor_pct])
        for y_key in ("y_ceiling", "y_floor"):
            result.append(
                {
                    "id": f"kp_{idx}",
                    "from_name": "kp",
                    "to_name": "img",
                    "type": "keypointlabels",
                    "original_width": 1024,
                    "original_height": 512,
                    "value": {
                        "x": x_pct,
                        "y": ceiling_pct if y_key == "y_ceiling" else floor_pct,
                        "width": 0.5,
                        "keypointlabels": ["Corner"],
                    },
                }
            )
            idx += 1
    if ceiling_points and floor_points:
        result.append(
            {
                "id": "poly_1",
                "from_name": "poly",
                "to_name": "img",
                "type": "polygonlabels",
                "original_width": 1024,
                "original_height": 512,
                "value": {"points": ceiling_points + list(reversed(floor_points)), "polygonlabels": ["Wall"]},
            }
        )
    return [{"model_version": "HoHoNet_C1_v3_1_smoke", "score": 0.99, "result": result}]


def _task(row: dict[str, str], mapping: dict[str, dict], group: str, condition: str, base: str, include_prediction: bool) -> dict:
    mapped = mapping[row["base_task_id"]]
    vis_3d = _rewrite_vis_base(mapped["vis_3d"], base)
    data = {
        "image": mapped["image"],
        "vis_3d": vis_3d,
        "title": mapped["title"],
        "dataset_group": group,
        "condition": condition,
        "smoke_test": True,
        "task_id": row["task_id"],
        "base_task_id": row["base_task_id"],
        "image_id": row.get("image_id") or row.get("image_stem") or row["base_task_id"],
        "calibration_version": "C1_v3_1",
        "source_draft": row.get("calibration_split", ""),
    }
    task = {"data": data}
    if include_prediction:
        task["predictions"] = _prediction_from_vis(vis_3d)
    return task


def build(root: Path) -> dict:
    mapping = _mapping(root)
    anchor = _read_csv(root / REBUILD_DIR / "calibration_anchor_draft_v2.csv")[:2]
    core = _read_csv(root / REBUILD_DIR / "calibration_core_draft_v3_1.csv")[:2]
    semi = _read_csv(root / REBUILD_DIR / "calibration_semi_selection_draft_v3_1.csv")[:3]
    manual_rows = anchor + core
    out = root / OUT_DIR
    files = []
    for label, base in [("zh", ZH_BASE), ("foreign_https", FOREIGN_BASE)]:
        manual = [_task(row, mapping, "C1_V3_1_SMOKE_manual", "manual", base, False) for row in manual_rows]
        semi_tasks = [_task(row, mapping, "C1_V3_1_SMOKE_semi", "semi", base, True) for row in semi]
        manual_path = out / f"c1_v3_1_manual_smoke_import_{label}.json"
        semi_path = out / f"c1_v3_1_semi_smoke_import_{label}.json"
        _write_json(manual_path, manual)
        _write_json(semi_path, semi_tasks)
        files.extend(
            [
                {"path": str(manual_path.relative_to(root)), "task_count": len(manual), "condition": "manual", "vis_3d_base": base},
                {"path": str(semi_path.relative_to(root)), "task_count": len(semi_tasks), "condition": "semi", "vis_3d_base": base, "all_have_predictions": all("predictions" in task for task in semi_tasks)},
            ]
        )
    summary = {
        "created_for": "C1_v3_1_smoke_test_import_draft",
        "status": "draft_not_imported",
        "no_label_studio_api_call": True,
        "source": "calibration v3.1 frozen drafts + export_label/groudTruth.json mapping",
        "manual_source_counts": {"anchor": len(anchor), "core": len(core)},
        "semi_count": len(semi),
        "files": files,
        "service_compatibility": {
            "zh_175_http": {
                "files": ["c1_v3_1_manual_smoke_import_zh.json", "c1_v3_1_semi_smoke_import_zh.json"],
                "vis_3d_base": ZH_BASE,
                "intended_label_studio_entry": "175.178/http entry",
            },
            "foreign_https": {
                "files": [
                    "c1_v3_1_manual_smoke_import_foreign_https.json",
                    "c1_v3_1_semi_smoke_import_foreign_https.json",
                ],
                "vis_3d_base": FOREIGN_BASE,
                "intended_label_studio_entry": "https foreign entry",
            },
            "do_not_mix_entries": True,
            "reason": "$vis_3d is fetched by the Label Studio frontend, so scheme/CORS must match the service entry.",
        },
    }
    _write_json(out / "c1_v3_1_smoke_import_summary.json", summary)
    _write_text(
        out / "README.md",
        "\n".join(
            [
                "# C1 v3.1 smoke import drafts",
                "",
                "- `*_zh.json` 只用于 175.178/http 中文入口，`vis_3d` 使用 `http://175.178.71.217:8000`。",
                "- `*_foreign_https.json` 只用于 https 海外入口，`vis_3d` 使用 `https://label.sparkle0825.top`。",
                "- 不要把 `foreign_https` 文件导入 175.178/http 项目；Label Studio 会在前端 fetch `$vis_3d`，scheme/CORS 不匹配时会报 `TypeError: Failed to fetch`。",
                "- 这些文件只用于 smoke test 草案，未调用 Label Studio API，不能视为 launch。",
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
