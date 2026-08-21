from tools.thesis_main.analysis.materialize_persistent_disagreement_diagnostic import (
    classify_persistence,
    robustness_rows,
    summarize,
)


def test_persistence_requires_supported_second_mode_and_less_than_80_percent_dominance():
    strong = classify_persistence({
        "task_crowd_structure_status": "supported_multimodal",
        "largest_cluster_share": 0.50,
        "second_cluster_support": 8,
    })
    weak = classify_persistence({
        "task_crowd_structure_status": "supported_multimodal",
        "largest_cluster_share": 0.91,
        "second_cluster_support": 2,
    })
    assert strong == {
        "supported_multimodal": True,
        "strong_persistent_split": True,
        "severe_persistent_split": True,
        "not_evaluable_partition": False,
    }
    assert weak["supported_multimodal"] is True
    assert weak["strong_persistent_split"] is False


def test_summary_keeps_not_evaluable_as_uncertainty_not_persistent_disagreement():
    rows = [
        {"supported_multimodal": True, "strong_persistent_split": True, "severe_persistent_split": False, "not_evaluable_partition": False},
        {"supported_multimodal": False, "strong_persistent_split": False, "severe_persistent_split": False, "not_evaluable_partition": True},
        {"supported_multimodal": False, "strong_persistent_split": False, "severe_persistent_split": False, "not_evaluable_partition": False},
    ]
    result = summarize(rows)
    assert result["task_count"] == 3
    assert result["strong_persistent_split_count"] == 1
    assert result["not_evaluable_count"] == 1
    assert result["strong_persistent_lower_bound"] == 1 / 3
    assert result["strong_persistent_upper_bound_if_all_not_evaluable"] == 2 / 3


def test_robustness_requires_same_task_to_be_strong_at_every_threshold():
    rows = [
        {"stage": "C", "scenario": "s", "base_task_id": "t1", "building_id": "b", "support_band": "high", "valid_k": 22, "similarity_threshold": 0.90, "strong_persistent_split": True, "supported_multimodal": True, "not_evaluable_partition": False},
        {"stage": "C", "scenario": "s", "base_task_id": "t1", "building_id": "b", "support_band": "high", "valid_k": 22, "similarity_threshold": 0.95, "strong_persistent_split": True, "supported_multimodal": True, "not_evaluable_partition": False},
        {"stage": "C", "scenario": "s", "base_task_id": "t2", "building_id": "b", "support_band": "high", "valid_k": 22, "similarity_threshold": 0.90, "strong_persistent_split": True, "supported_multimodal": True, "not_evaluable_partition": False},
        {"stage": "C", "scenario": "s", "base_task_id": "t2", "building_id": "b", "support_band": "high", "valid_k": 22, "similarity_threshold": 0.95, "strong_persistent_split": False, "supported_multimodal": False, "not_evaluable_partition": True},
    ]
    result = {row["base_task_id"]: row for row in robustness_rows(rows, (0.90, 0.95))}
    assert result["t1"]["strong_at_all_thresholds"] is True
    assert result["t2"]["strong_at_all_thresholds"] is False
    assert result["t2"]["strong_at_any_threshold"] is True
    assert result["t2"]["not_evaluable_at_any_threshold"] is True
