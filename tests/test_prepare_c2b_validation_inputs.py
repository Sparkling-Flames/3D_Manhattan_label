import csv
import json
from pathlib import Path

from tools.thesis_main.data_prep.prepare_c2b_validation_inputs import prepare


def _csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_validation_only_bundle_keeps_support_tasks_out_of_worker_facing_registries(tmp_path: Path) -> None:
    full, c1, legacy, buildings = (tmp_path / name for name in ("full.csv", "c1.csv", "legacy.csv", "buildings.csv"))
    images, references, predictions, layouts = (tmp_path / name for name in ("images", "references", "predictions", "layouts"))
    for directory in (images, references, predictions, layouts):
        directory.mkdir()
    _csv(full, [
        {"task_id": "c1", "base_task_id": "c1", "image_id": "c1", "source_path": str(tmp_path / "c1.png")},
        {"task_id": "legacy", "base_task_id": "legacy", "image_id": "legacy", "source_path": str(tmp_path / "legacy.png")},
    ])
    for name in ("c1", "legacy"):
        (tmp_path / f"{name}.png").write_bytes(b"image")
        (layouts / f"{name}.json").write_text('{"layout":{"corners":[]}}', encoding="utf-8")
    _csv(c1, [{"base_task_id": "c1"}])
    _csv(legacy, [{"base_task_id": "legacy"}])
    _csv(buildings, [{"base_task_id": "c1", "building_id": "scene-c1", "scene_mapping_key": "scene-c1", "registry_status": "approved", "reviewed_by": "researcher", "reviewed_at": "2026-08-01"}])
    for stem in ("sceneA_one", "sceneB_two"):
        (images / f"{stem}.png").write_bytes(b"image")
        (references / f"{stem}.txt").write_text("1 1\n1 2\n2 1\n2 2\n", encoding="utf-8")
        (predictions / f"{stem}.txt").write_text("10 100\n10 400\n500 120\n500 390\n", encoding="utf-8")

    summary = prepare(
        full_inventory=full, c1_assignments=[c1], legacy_manifest=legacy,
        c1_building_registry=buildings, validation_image_dir=images,
        validation_reference_dir=references, validation_prediction_dir=predictions,
        existing_layout_dir=layouts, output_dir=tmp_path / "out",
        image_base_url="https://example.invalid/validation", reviewed_at="2026-08-02T00:00:00+08:00",
    )

    assert summary["inventory_role_counts"] == {"c1_risk_reference_support_only": 1, "formal_c2b_validation_candidate": 2, "legacy_provenance_support_only": 1}
    scope = list(csv.DictReader((tmp_path / "out/scope_registry.csv").open(encoding="utf-8")))
    assert {row["base_task_id"] for row in scope} == {"sceneA_one", "sceneB_two"}
    building = list(csv.DictReader((tmp_path / "out/authoritative_building_registry.csv").open(encoding="utf-8")))
    assert {row["base_task_id"] for row in building} == {"c1", "sceneA_one", "sceneB_two"}
    layout = json.loads((tmp_path / "out/model_layout_json/sceneA_one.json").read_text(encoding="utf-8"))
    assert layout["layout"]["corners"] == [
        {"x": 10.0, "y_ceiling": 100.0, "y_floor": 400.0, "id": 0},
        {"x": 500.0, "y_ceiling": 120.0, "y_floor": 390.0, "id": 1},
    ]
