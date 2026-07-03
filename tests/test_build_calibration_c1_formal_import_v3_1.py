from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.build_calibration_c1_formal_import_v3_1 import build


def _csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _row(task_id: str) -> dict[str, str]:
    return {"task_id": task_id, "base_task_id": f"base_{task_id}", "image_id": f"base_{task_id}", "image_stem": f"base_{task_id}", "calibration_split": "x"}


def test_build_calibration_c1_formal_import_v3_1(tmp_path: Path) -> None:
    out = tmp_path / "analysis_results/calibration_rebuild_20260702"
    _csv(out / "calibration_anchor_draft_v2.csv", [_row(str(i)) for i in range(12)])
    _csv(out / "calibration_core_draft_v3_1.csv", [_row(str(i)) for i in range(100, 175)])
    _csv(out / "calibration_semi_selection_draft_v3_1.csv", [_row(str(i)) for i in range(200, 225)])
    mapping = []
    for task_id in [*map(str, range(12)), *map(str, range(100, 175)), *map(str, range(200, 225))]:
        stem = f"base_{task_id}"
        mapping.append(
            {
                "data": {
                    "title": f"{stem}.jpg",
                    "image": f"https://img/{stem}.jpg",
                    "vis_3d": "http://175.178.71.217:8000/tools/vis_3d.html?w=1024&h=512&data=%5B%7B%22x%22%3A1,%22y_ceiling%22%3A2,%22y_floor%22%3A3%7D%5D",
                }
            }
        )
    export = tmp_path / "export_label"
    export.mkdir()
    (export / "groudTruth.json").write_text(json.dumps(mapping), encoding="utf-8")

    summary = build(tmp_path)

    assert summary["counts"] == {"anchor": 12, "core": 75, "semi": 25}
    assert summary["reserve_included"] is False
    zh_anchor = json.loads((tmp_path / "import_json/calibration_c1_v3_1_formal/c1_v3_1_anchor_import_zh.json").read_text(encoding="utf-8"))
    foreign_core = json.loads((tmp_path / "import_json/calibration_c1_v3_1_formal/c1_v3_1_core_import_foreign_https.json").read_text(encoding="utf-8"))
    zh_semi = json.loads((tmp_path / "import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_zh.json").read_text(encoding="utf-8"))
    assert len(zh_anchor) == 12
    assert len(foreign_core) == 75
    assert len(zh_semi) == 25
    assert zh_anchor[0]["data"]["vis_3d"].startswith("http://175.178.71.217:8000/")
    assert foreign_core[0]["data"]["vis_3d"].startswith("https://label.sparkle0825.top/")
    assert "predictions" not in zh_anchor[0]
    assert "predictions" in zh_semi[0]
