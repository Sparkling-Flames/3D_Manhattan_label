import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.worker_classification_progress_20261014 import (
    bind_time, fit_training_effects, metric_cells, time_class,
)


def test_building_isolation_and_task_adjustment_with_unequal_coverage():
    rows = []
    effects = {"W001": -1., "W002": 0., "W003": 1.}
    for b in range(5):
        for t in range(3):
            for worker in (effects if t != 2 else ["W001", "W002"]):
                rows.append(dict(worker_id=worker, building_id=str(b),
                    context_key=f"{b}:{t}", value=100*b+10*t+effects[worker]))
    data = pd.DataFrame(rows)
    p = fit_training_effects(data, "4").set_index("worker_id")
    assert np.allclose(p.effect, [-1, 0, 1])
    changed = data.copy()
    changed.loc[changed.building_id == "4", "value"] = -99999
    pd.testing.assert_frame_equal(p, fit_training_effects(changed, "4").set_index("worker_id"))
    assert all("4" not in x for x in p.training_buildings)


def test_disconnected_people_are_not_ranked_and_missing_support_is_unclassified():
    data = pd.DataFrame([dict(worker_id=w, building_id=str(b), context_key=f"{g}:{b}:{t}",
        value=float(j)) for g, workers in enumerate([["a", "b"], ["c", "d"]])
        for b in range(3) for t in range(2) for j, w in enumerate(workers)])
    p = fit_training_effects(data)
    assert set(p.fit_status) == {"disconnected_graph"}
    assert p.effect.isna().all()
    assert time_class(-1, False) == "unclassified"
    assert time_class(0, True) == "unclassified"


def test_time_binding_rejects_identity_mismatch_and_does_not_backfill():
    obj = dict(worker_id="W008", image_id="im", building_id="building")
    row = dict(worker_id="8", worker_id_timing="8", image_id="im", building_id="building",
        canonical_annotation_id="c", time_ok=True, time=np.log1p(20), active_time_seconds=20,
        active_time_source="log", active_time_source_file="f.jsonl", timing_status="eligible",
        original_context_key="manual:im", stage="P1")
    assert bind_time(obj, row)["time_value"] == pytest.approx(np.log1p(20))
    with pytest.raises(ValueError, match="identity"):
        bind_time(obj, {**row, "image_id": "another"})
    with pytest.raises(ValueError, match="source"):
        bind_time(obj, {**row, "active_time_source": "lead_time_fallback"})
    assert bind_time(obj, {**row, "time_ok": False, "time": ""})["time_value"] is None
    assert bind_time(obj, None)["time_value"] is None


def test_reference_cells_and_missing_metrics_are_separate():
    rows = [dict(record_id="r1",worker_id="a",image_id="im",building_id="b",
                 reference_object_id="ref1", metrics={"Hmean": .1}),
            dict(record_id="r2",worker_id="b",image_id="im",building_id="b",
                 reference_object_id="ref1", metrics={"Hmean": .3}),
            dict(record_id="r3",worker_id="c",image_id="im",building_id="b",
                 reference_object_id="ref2", metrics={"Hmean": 10}),
            dict(record_id="r4",worker_id="d",image_id="im",building_id="b",
                 reference_object_id="ref1", metrics={"Hmean": None})]
    cells = metric_cells(rows, ("Hmean",)).set_index("record_id")
    assert cells.loc["r1", "centered_value"] == pytest.approx(-.1)
    assert cells.loc["r2", "centered_value"] == pytest.approx(.1)
    assert cells.loc["r3", "peer_n"] == 1
    assert "r4" not in cells.index
