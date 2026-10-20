import numpy as np
import pandas as pd
from tools.thesis_main.analysis.personnel_marking_patterns_20261020 import geometry_features, primary_observations, v


def points(floor):
    floor = np.asarray(floor, dtype=float)
    bottom = np.column_stack((floor[:, 0], -np.ones(len(floor)), floor[:, 1]))
    top = bottom.copy()
    top[:, 1] = 1
    return np.stack([v._project(top), v._project(bottom)], axis=1).reshape(-1, 2)


def test_collinear_node_is_not_a_short_structural_turn():
    f, _ = geometry_features(points([[-1, -1], [0, -1], [1, -1], [1, 1], [-1, 1]]))
    assert f["near_straight_nodes_5deg"] == 1
    assert f["short_turn_edges"] == 0
    assert abs(f["area_camera_height_sq"] - 4) < 1e-10


def test_real_step_short_edge_and_invalid_floor():
    f, _ = geometry_features(points([[-1, -1], [1, -1], [1, 1], [.1, 1], [.1, .9], [-1, .9]]))
    assert f["short_turn_edges"] == 1
    f, _ = geometry_features(points([[-1, -1], [1, 1], [1, -1], [-1, 1]]))
    assert f["feature_status"] == "invalid_or_degenerate_floor"


def test_repeat_submission_does_not_double_weight_person():
    rows = [dict(worker_id="W1", image_id="I", condition="manual", reference_id="R", layer="ordinary",
                 object_id=str(i), independent_vote_eligible=flag) for i, flag in enumerate([False, True])]
    rows.append({**rows[0], "worker_id": "W2", "object_id": "2"})
    assert primary_observations(pd.DataFrame(rows)).tolist() == [False, True, True]
