from __future__ import annotations

import math
import json
from pathlib import Path

import pandas as pd
import pytest

from tools.paper_a_manhattan.full_uncertainty import materialize_full_uncertainty_data_mining_v5 as v5


def test_default_output_and_overwrite_guard(tmp_path: Path) -> None:
    assert v5.DEFAULT_OUTPUT.name == "full_uncertainty_data_mining_20260821_v5"
    target = tmp_path / "existing"
    target.mkdir()
    with pytest.raises(FileExistsError):
        v5.materialize(target)


def test_terminal_227_support_distribution() -> None:
    evidence, support, distribution, workers = v5._c2_terminal_tables()
    assert len(evidence[evidence["eligibility_status"].eq("eligible")]) == 227
    assert distribution["support_bin"].tolist() == ["1", "2", "3", "4", "5_plus"]
    assert distribution["task_count"].tolist() == [18, 23, 11, 5, 10]
    assert len(support) == 67
    assert len(workers) == 22


def test_axis_aggregation_is_invariant_to_simple_row_replication() -> None:
    frame = pd.DataFrame([
        {"base_task_id": "t1", "worker_id": "w1", "building_id": "b1", "x": 1, "y": 2},
        {"base_task_id": "t1", "worker_id": "w2", "building_id": "b1", "x": 2, "y": 1},
        {"base_task_id": "t2", "worker_id": "w1", "building_id": "b2", "x": 3, "y": 4},
        {"base_task_id": "t2", "worker_id": "w2", "building_id": "b2", "x": 4, "y": 3},
        {"base_task_id": "t3", "worker_id": "w1", "building_id": "b3", "x": 5, "y": 8},
        {"base_task_id": "t3", "worker_id": "w2", "building_id": "b3", "x": 8, "y": 5},
    ])
    replicated = pd.concat([frame, frame], ignore_index=True)
    for axis in ("task", "worker"):
        left = v5._axis_association(frame, axis, "x", "y", repetitions=20)
        right = v5._axis_association(replicated, axis, "x", "y", repetitions=20)
        if pd.isna(left["spearman_rho"]):
            assert pd.isna(right["spearman_rho"])
        else:
            assert left["spearman_rho"] == pytest.approx(right["spearman_rho"])


def test_v5_generator_has_no_restricted_delivery_terms() -> None:
    source = Path(v5.__file__).read_text(encoding="utf-8").lower()
    restricted = ("ad" + "visor", "\u5bfc\u5e08", "har" + "mful", "har" + "med")
    assert all(token not in source for token in restricted)


def test_table_spec_covers_every_field() -> None:
    frame = pd.DataFrame([{"stage": "C1", "value": math.nan}])
    bilingual = v5._bilingual(frame)
    spec = v5._table_spec("sample.csv", bilingual)
    assert [row["field"] for row in spec["fields"]] == list(bilingual.columns)
    assert all(row["meaning_zh"] and row["source_or_formula"] and row["missing_meaning"] for row in spec["fields"])


def test_existing_semi_mechanism_does_not_turn_missing_rmse_into_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pd.DataFrame([
        {"base_task_id": "t1", "worker_id": "w1", "geometry_edit_rmse_px": None, "U_initial": 0.2, "delta_U": 0},
        {"base_task_id": "t1", "worker_id": "w2", "geometry_edit_rmse_px": 0, "U_initial": 0.2, "delta_U": None},
        {"base_task_id": "t2", "worker_id": "w1", "geometry_edit_rmse_px": 0, "U_initial": 0.3, "delta_U": 0},
        {"base_task_id": "t2", "worker_id": "w2", "geometry_edit_rmse_px": 1, "U_initial": 0.4, "delta_U": 0.1},
        {"base_task_id": "t3", "worker_id": "w3", "geometry_edit_rmse_px": 2, "U_initial": 0.5, "delta_U": -0.1},
    ]).to_csv(tmp_path / "semi_review_fact.csv", index=False)
    monkeypatch.setattr(v5.base, "PACKAGE", tmp_path)
    summary, _ = v5.base.semi_mechanism_analysis()
    counts = summary.set_index("population")["row_count"].to_dict()
    assert counts == {"all_delta_u_computable": 3, "exclude_structural_zero": 2, "edited_only": 2}


def test_segmented_workbook_payload_keeps_all_rows_and_json_fields(tmp_path: Path) -> None:
    frame = pd.DataFrame({"row_id": range(501), "task_data_json": [f'{{"i":{i}}}' for i in range(501)]})
    frames = {"LONG_TABLE.csv": frame}
    payload_dir = v5._write_workbook_payload(tmp_path, frames, {"LONG_TABLE.csv": v5._table_spec("LONG_TABLE.csv", frame)}, batch_bytes=1000)
    manifest = json.loads((payload_dir / "manifest.json").read_text(encoding="utf-8"))
    payload = json.loads((payload_dir / manifest["batches"][0]["file"]).read_text(encoding="utf-8"))
    table = payload["tables"][0]
    assert table["fullRowCount"] == 501
    assert table["rowsOmitted"] == 0
    assert "task_data_json" in table["workbookColumns"]
    assert len(table["rows"]) == 501


def test_supplement_workbook_payload_uses_nonconflicting_global_indexes(tmp_path: Path) -> None:
    frame = pd.DataFrame([{"value": 1}])
    payload_dir = v5._write_workbook_payload(
        tmp_path,
        {"SUPPLEMENT.csv": frame},
        {"SUPPLEMENT.csv": v5._table_spec("SUPPLEMENT.csv", frame)},
        start_index=127,
    )
    manifest = json.loads((payload_dir / "manifest.json").read_text(encoding="utf-8"))
    payload = json.loads((payload_dir / manifest["batches"][0]["file"]).read_text(encoding="utf-8"))
    table = payload["tables"][0]
    assert manifest["start_index"] == 127
    assert table["globalIndex"] == 127
    assert table["tableName"] == "T128"
    assert table["sheetName"].startswith("128_")


def test_bilingual_is_idempotent_for_existing_translation_columns() -> None:
    frame = pd.DataFrame([{"stage": "C1", "stage_zh": "校准一阶段"}])
    result = v5._bilingual(frame)
    assert list(result.columns) == ["stage", "stage_zh"]
    assert result.loc[0, "stage_zh"] == "校准一阶段"
