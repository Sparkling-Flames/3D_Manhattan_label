from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.build_calibration_smoke_import_v3_1 import build


def _csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_build_calibration_smoke_import_v3_1(tmp_path: Path) -> None:
    base_rows = [{"task_id": str(i), "base_task_id": f"img_{i}", "image_id": f"img_{i}", "image_stem": f"img_{i}", "calibration_split": "x"} for i in range(1, 8)]
    out = tmp_path / "analysis_results/calibration_rebuild_20260702"
    _csv(out / "calibration_anchor_draft_v2.csv", base_rows[:2])
    _csv(out / "calibration_core_draft_v3_1.csv", base_rows[2:4])
    _csv(out / "calibration_semi_selection_draft_v3_1.csv", base_rows[4:7])
    export = [
        {
            "data": {
                "title": f"img_{i}.jpg",
                "image": f"https://cos/img_{i}.jpg",
                "vis_3d": "http://175.178.71.217:8000/tools/vis_3d.html?w=1024&h=512&data=%5B%7B%22x%22%3A1%2C%22y_ceiling%22%3A2%2C%22y_floor%22%3A3%7D%5D",
            }
        }
        for i in range(1, 8)
    ]
    export_dir = tmp_path / "export_label"
    export_dir.mkdir()
    (export_dir / "groudTruth.json").write_text(json.dumps(export), encoding="utf-8")

    summary = build(tmp_path)

    assert summary["status"] == "draft_not_imported"
    semi = json.loads((tmp_path / "import_json/calibration_c1_v3_1_smoke/c1_v3_1_semi_smoke_import_foreign_https.json").read_text(encoding="utf-8"))
    manual = json.loads((tmp_path / "import_json/calibration_c1_v3_1_smoke/c1_v3_1_manual_smoke_import_zh.json").read_text(encoding="utf-8"))
    assert len(manual) == 4
    assert len(semi) == 3
    assert semi[0]["data"]["vis_3d"].startswith("https://label.sparkle0825.top/")
    assert semi[0]["predictions"][0]["result"]
    assert "polygonlabels" in {row["type"] for row in semi[0]["predictions"][0]["result"]}
    assert summary["service_compatibility"]["do_not_mix_entries"] is True
    assert summary["service_compatibility"]["zh_175_http"]["vis_3d_base"] == "http://175.178.71.217:8000"
    assert (tmp_path / "import_json/calibration_c1_v3_1_smoke/README.md").exists()
