import hashlib
from pathlib import Path

import numpy as np
import pytest

from tools.thesis_main.analysis.build_a4_image_evidence_alignment_substrate import (
    DENY_COLUMNS,
    alignment_features,
    normalize_geometry,
    parse_candidate_geometry,
    model_readiness,
    readiness_status,
    read_allowlisted_csv,
    write_deterministic_npz,
)


def test_point_count_is_not_layout_corner_count():
    parsed = parse_candidate_geometry("[[100,100],[100,400],[500,100],[500,400]]", 1024, 512)
    assert parsed["point_count"] == 4
    assert parsed["layout_corner_count"] == 2


def test_duplicate_x_fails_closed():
    parsed = parse_candidate_geometry("[[100,100],[100,400],[100,120],[100,420]]", 1024, 512)
    assert parsed["parse_status"] == "failed"


def test_known_vertical_and_boundary_alignment_beats_shifted_candidate():
    evidence = {"vertical_profile": np.zeros(64, dtype=np.float32), "dy": np.zeros((32, 64), dtype=np.float32)}
    evidence["vertical_profile"][16] = 1.0
    evidence["dy"][4, 16] = 1.0
    evidence["dy"][23, 16] = 1.0
    good = normalize_geometry([[256, 64], [256, 384], [768, 64], [768, 384]])
    shifted = normalize_geometry([[400, 100], [400, 350], [900, 100], [900, 350]])
    good_score = alignment_features(good, evidence)
    shifted_score = alignment_features(shifted, evidence)
    assert good_score["vertical_edge_support"] > shifted_score["vertical_edge_support"]
    assert good_score["ceiling_boundary_support"] > shifted_score["ceiling_boundary_support"]
    assert good_score["floor_boundary_support"] > shifted_score["floor_boundary_support"]


def test_piecewise_segment_alignment_distinguishes_middle_boundary():
    evidence = {"vertical_profile": np.zeros(64, dtype=np.float32), "dy": np.zeros((64, 64), dtype=np.float32)}
    evidence["dy"][24, :] = 1.0
    good = normalize_geometry([[128, 192], [128, 384], [512, 192], [512, 384], [896, 192], [896, 384]])
    shifted_middle = normalize_geometry([[128, 192], [128, 384], [512, 320], [512, 384], [896, 192], [896, 384]])
    assert good["pairs"][0]["x"] == shifted_middle["pairs"][0]["x"]
    assert good["pairs"][1]["x"] == shifted_middle["pairs"][1]["x"]
    assert alignment_features(good, evidence)["ceiling_boundary_support"] > alignment_features(shifted_middle, evidence)["ceiling_boundary_support"]


def test_seam_segment_samples_both_sides_of_wrap():
    evidence = {"vertical_profile": np.zeros(64, dtype=np.float32), "dy": np.zeros((64, 256), dtype=np.float32)}
    evidence["dy"][24, :] = 1.0
    parsed = normalize_geometry([[100, 192], [100, 384], [900, 192], [900, 384]])
    score = alignment_features(parsed, evidence)
    assert score["seam_segment_count"] == 1
    assert score["seam_sample_count"] > 2
    assert score["seam_segment_boundary_support"] > 0


def test_seam_score_is_candidate_specific():
    evidence = {"vertical_profile": np.zeros(64, dtype=np.float32), "dy": np.zeros((64, 256), dtype=np.float32)}
    evidence["dy"][24, :] = 1.0
    aligned = normalize_geometry([[100, 192], [100, 384], [900, 192], [900, 384]])
    misaligned = normalize_geometry([[100, 320], [100, 384], [900, 320], [900, 384]])
    assert alignment_features(aligned, evidence)["seam_segment_boundary_support"] > alignment_features(misaligned, evidence)["seam_segment_boundary_support"]


def test_alignment_features_handles_unwrapped_and_wrapped_pair_x_equivalently():
    evidence = {"vertical_profile": np.arange(128, dtype=np.float32), "dy": np.zeros((64, 256), dtype=np.float32)}
    base = normalize_geometry([[100, 64], [100, 384], [320, 80], [320, 400], [540, 90], [540, 410], [760, 70], [760, 390]], width=1024, height=512)
    shifted = {
        "parse_status": "valid",
        "width": base["width"],
        "height": base["height"],
        "pairs": [{**pair, "x": float(pair["x"]) + float(base["width"])} for pair in base["pairs"]],
    }
    base_score = alignment_features(base, evidence)
    shifted_score = alignment_features(shifted, evidence)
    assert base_score["vertical_edge_support"] == pytest.approx(shifted_score["vertical_edge_support"])
    assert base_score["seam_event_count"] == shifted_score["seam_event_count"] == 0


def test_model_source_absent_does_not_gate_raw_readiness():
    assert readiness_status([], [], [{"candidate": "ok"}]) == "A4_ALIGNMENT_SUBSTRATE_READY"
    assert model_readiness([{ "layout_prediction_exists": "True", "formal_model_binding": "False" }]) == ("source_absent", False)


def test_geometry_rejection_without_policy_is_partial():
    assert readiness_status([], [{"reason": "odd_keypoint_count"}], [{"candidate": "ok"}]) == "A4_ALIGNMENT_SUBSTRATE_PARTIAL"


def test_allowlisted_projection_records_trace(tmp_path):
    path = tmp_path / "allowed.csv"
    path.write_text("allowed,quality\nvalue,hidden\n", encoding="utf-8")
    trace = []
    assert read_allowlisted_csv(path, ["allowed"], trace) == [{"allowed": "value"}]
    assert trace[0]["projected_columns"] == ["allowed"]
    assert not set(trace[0]["projected_columns"]) & set(DENY_COLUMNS)


def test_denied_projection_fails_before_consumption(tmp_path):
    path = tmp_path / "allowed.csv"
    path.write_text("quality\nhidden\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        read_allowlisted_csv(path, ["quality"], [])


def test_denied_path_fails_before_open():
    with pytest.raises(PermissionError):
        read_allowlisted_csv(Path("export_label/blocked.csv"), ["allowed"], [])


def test_deterministic_npz_hash_is_stable(tmp_path):
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    arrays = {"dy": np.arange(6, dtype=np.float32).reshape(2, 3), "dx": np.ones((2, 3), dtype=np.float32)}
    write_deterministic_npz(first, arrays)
    write_deterministic_npz(second, arrays)
    assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(second.read_bytes()).hexdigest()
