from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "thesis_main" / "registry" / "build_calibration_round_input_manifest.py"


def write_import(path: Path, dataset_group: str, names: list[str]) -> None:
    payload = [
        {
            "data": {
                "image": f"https://example.test/{name}.jpg",
                "title": f"{name}.jpg",
                "dataset_group": dataset_group,
            }
        }
        for name in names
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_calibration_round_input_manifest_from_imports(tmp_path: Path) -> None:
    anchor = tmp_path / "anchor.json"
    core = tmp_path / "core.json"
    reserve = tmp_path / "reserve.json"
    semi = tmp_path / "semi.json"
    write_import(anchor, "Calibration_anchor", ["anchor_01"])
    write_import(core, "Calibration_core", ["core_01", "core_02"])
    write_import(reserve, "Calibration_reserve", ["reserve_01"])
    write_import(semi, "Calibration_semi", ["semi_01"])

    output = tmp_path / "calibration_round_input_manifest_v1.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--anchor-import",
            str(anchor),
            "--core-import",
            str(core),
            "--reserve-import",
            str(reserve),
            "--semi-import",
            str(semi),
            "--output",
            str(output),
        ],
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["meta"]["c1_core_operational_target_k"] == 5
    assert payload["meta"]["c1_core_preregistered_min_k"] == 4
    assert payload["meta"]["reserve_policy"] == "unchanged_C2_only"
    assert [task["task_id"] for task in payload["task_sets"]["Calibration_anchor"]] == ["anchor_01"]
    assert [task["task_id"] for task in payload["task_sets"]["Calibration_core"]] == ["core_01", "core_02"]
    assert [task["task_id"] for task in payload["task_sets"]["Calibration_reserve"]] == ["reserve_01"]
    assert [task["task_id"] for task in payload["task_sets"]["Calibration_semi"]] == ["semi_01"]
