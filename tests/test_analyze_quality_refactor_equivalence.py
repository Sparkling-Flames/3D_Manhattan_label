import csv
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYZE_QUALITY = REPO_ROOT / "tools" / "thesis_main" / "analysis" / "analyze_quality.py"
ANALYZE_QUALITY_FORMAL = REPO_ROOT / "tools" / "label_studio" / "official" / "analyze_quality_formal.py"


EXPECTED_ANALYZE_QUALITY_HEADER = [
    "dataset_group",
    "dataset_group_source",
    "export_dataset_group",
    "project_version",
    "task_id",
    "title",
    "image_url",
    "export_project_id",
    "export_source_file",
    "export_source_path",
    "export_init_type",
    "export_is_anchor",
    "export_has_expert_ref",
    "condition",
    "runtime_condition_source",
    "annotator_id",
    "active_time",
    "active_time_source",
    "active_time_source_file",
    "active_time_project_ids",
    "active_time_match_status",
    "active_time_session_count",
    "active_time_event_count",
    "lead_time_seconds",
    "iou",
    "iou_manual",
    "iou_corner",
    "rmse_px",
    "layout_2d_iou",
    "layout_3d_iou",
    "layout_depth_rmse",
    "layout_delta1",
    "layout_used",
    "layout_gate_reason",
    "reliability_used",
    "reliability_gate_reason",
    "pointwise_rmse_px",
    "pointwise_rmse_used",
    "pointwise_best_shift",
    "pointwise_gate_reason",
    "boundary_mse",
    "boundary_rmse_px",
    "pred_n_points",
    "pred_n_pairs",
    "pred_pair_coverage",
    "pred_odd_points",
    "ann_n_points",
    "ann_n_pairs",
    "ann_pair_coverage",
    "ann_odd_points",
    "pairing_warning",
    "pairing_failure_reason",
    "boundary_method_used",
    "consensus_uid",
    "iou_to_consensus",
    "consensus_uid_loo",
    "iou_to_consensus_loo",
    "iou_to_others_median",
    "quality",
    "scope",
    "difficulty",
    "model_issue",
    "tool_issue",
    "scope_filled",
    "difficulty_filled",
    "difficulty_has_trivial",
    "difficulty_conflict",
    "model_issue_required",
    "model_issue_filled",
    "model_issue_has_acceptable",
    "model_issue_conflict",
    "model_issue_missing_required",
    "has_model_issue",
    "model_issue_types",
    "model_issue_primary",
    "scope_missing",
    "difficulty_missing",
    "model_issue_missing",
    "difficulty_conflict_v2",
    "model_issue_conflict_v2",
    "is_oos",
    "is_occlusion",
    "is_fail",
    "is_residual",
    "is_normal",
    "n_corners",
    "has_manual_poly",
    "task_scope_n_total",
    "task_scope_n_in_scope",
    "task_scope_n_oos",
    "task_scope_n_unknown",
    "task_scope_oos_rate",
    "task_scope_unknown_rate",
    "task_scope_majority",
    "task_scope_is_mixed",
    "task_scope_has_unknown",
    "analysis_role",
]


KEY_FIELDS = [
    "task_id",
    "annotator_id",
    "dataset_group",
    "project_version",
    "analysis_role",
    "condition",
    "active_time",
    "active_time_source",
    "active_time_match_status",
    "scope",
    "difficulty",
    "model_issue",
    "is_oos",
    "is_normal",
    "iou",
    "iou_corner",
    "rmse_px",
    "boundary_rmse_px",
    "reliability_used",
    "reliability_gate_reason",
]


FORMAL_STAGE_FIELDS = {
    "formal_p1",
    "formal_c1",
    "formal_c2",
    "formal_t1",
    "formal_v1",
    "admission",
    "routing",
    "tau_d",
    "wmax",
    "w_max",
    "dt_reference",
    "ood_activation",
}


CLI_HELP_TOKENS = [
    "export_json",
    "--active-logs",
    "--active-log-start",
    "--active-log-end",
    "--output_dir",
    "--metric",
    "--no_smooth",
    "--pair_warn_min_coverage",
    "--boundary_method",
    "--no_pointwise",
    "--pointwise_min_coverage",
    "--ru_min_tasks",
    "--ru_bootstrap_iters",
    "--ru_ci",
    "--ru_seed",
    "--dataset_group",
    "--project_version",
    "--analysis_role",
    "--output",
    "--append",
    "--quality_mode",
]


FORMAL_DROPPED_COLUMNS = {
    "scope_missing",
    "difficulty_missing",
    "model_issue_missing",
    "model_issue_types",
    "difficulty_conflict_v2",
    "model_issue_conflict_v2",
    "is_normal",
}


def _corner(x, y):
    return {"type": "keypointlabels", "value": {"x": x, "y": y, "keypointlabels": ["Corner"]}}


def _choices(name, values):
    return {"type": "choices", "from_name": name, "value": {"choices": values}}


def _geometry(offset=0):
    return [
        _corner(10 + offset, 20),
        _corner(10 + offset, 80),
        _corner(50 + offset, 20),
        _corner(50 + offset, 80),
        _corner(90 + offset, 20),
        _corner(90 + offset, 80),
    ]


def _annotation(user_id, *, scope=None, difficulty=None, model_issue=None, lead_time=3, offset=0):
    result = _geometry(offset=offset)
    if scope is not None:
        result.append(_choices("scope", [scope]))
    if difficulty is not None:
        result.append(_choices("difficulty", difficulty))
    if model_issue is not None:
        result.append(_choices("model_issue", model_issue))
    return {
        "id": int(user_id) * 100,
        "completed_by": {"id": int(user_id)},
        "lead_time": lead_time,
        "result": result,
    }


def _prediction():
    return {"result": _geometry(offset=0)}


def _write_fixture(tmp_path):
    export_path = tmp_path / "export.json"
    logs_dir = tmp_path / "active_logs"
    logs_dir.mkdir()

    tasks = [
        {
            "id": 101,
            "project": 55,
            "data": {"title": "mixed", "image": "mixed.jpg", "dataset_group": "Synthetic"},
            "prediction": _prediction(),
            "annotations": [
                _annotation(
                    1,
                    scope="normal",
                    difficulty=["trivial"],
                    model_issue=["acceptable"],
                    lead_time=30,
                    offset=0,
                ),
                _annotation(
                    2,
                    scope="oos_geometry",
                    difficulty=["occlusion"],
                    model_issue=["fail"],
                    lead_time=4,
                    offset=3,
                ),
            ],
        },
        {
            "id": 102,
            "project": 55,
            "data": {"title": "unknown", "image": "unknown.jpg", "dataset_group": "Synthetic"},
            "annotations": [
                _annotation(
                    3,
                    scope=None,
                    difficulty=None,
                    model_issue=None,
                    lead_time=6,
                    offset=1,
                )
            ],
        },
    ]
    export_path.write_text(json.dumps(tasks), encoding="utf-8")

    events = [
        {"project_id": 55, "task_id": 101, "annotator_id": 1, "session_id": "a", "active_seconds": 3, "server_received_at": "2026-01-01T10:00:00"},
        {"project_id": 55, "task_id": 101, "annotator_id": 1, "session_id": "a", "active_seconds": 5, "server_received_at": "2026-01-01T10:00:01"},
        {"project_id": 55, "task_id": 101, "annotator_id": 1, "session_id": "b", "active_seconds": 7, "server_received_at": "2026-01-01T10:01:00"},
    ]
    (logs_dir / "active_times_unit.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return export_path, logs_dir


def _run_cli(tmp_path):
    export_path, logs_dir = _write_fixture(tmp_path)
    output_csv = tmp_path / "quality.csv"
    result = subprocess.run(
        [
            sys.executable,
            str(ANALYZE_QUALITY),
            str(export_path),
            "--active-logs",
            str(logs_dir),
            "--output_dir",
            str(tmp_path / "out"),
            "--output",
            str(output_csv),
            "--dataset_group",
            "UnitFixture",
            "--project_version",
            "unit-v1",
            "--ru_min_tasks",
            "1",
            "--ru_bootstrap_iters",
            "5",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    with output_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        header = rows[0].keys() if rows else []
    return list(header), rows, result


def test_quality_core_exposes_migrated_functions():
    from tools.thesis_main.analysis.quality_core import active_time, choice_parser, consensus_reliability, geometry_metrics

    assert hasattr(choice_parser, "parse_quality_flags_v2")
    assert hasattr(choice_parser, "_normalize_choice_values")
    assert hasattr(active_time, "load_active_logs")
    assert hasattr(active_time, "lookup_active_log_entry")
    assert hasattr(geometry_metrics, "compute_iou")
    assert hasattr(geometry_metrics, "compute_boundary_mse_rmse")
    assert hasattr(consensus_reliability, "_bootstrap_ci")
    assert hasattr(consensus_reliability, "compute_consistency")


def test_analyze_quality_legacy_api_imports_remain_available():
    from tools.thesis_main.analysis.analyze_quality import (
        _bootstrap_ci,
        _pair_keypoints_to_layout,
        _scope_is_oos,
        _split_choice_values,
        compute_boundary_mse_rmse,
        compute_iou,
        compute_layout_standard_metrics,
        compute_pointwise_rmse_cyclic,
        compute_rmse,
        extract_data,
        load_active_logs,
        lookup_active_log_entry,
        parse_quality_flags_v2,
    )

    assert extract_data
    assert load_active_logs
    assert lookup_active_log_entry
    assert parse_quality_flags_v2
    assert compute_iou
    assert compute_boundary_mse_rmse
    assert compute_rmse
    assert compute_layout_standard_metrics
    assert compute_pointwise_rmse_cyclic
    assert _pair_keypoints_to_layout
    assert _bootstrap_ci
    assert _split_choice_values
    assert _scope_is_oos


def test_analyze_quality_full_csv_header_is_frozen(tmp_path):
    header, _rows, _result = _run_cli(tmp_path)

    assert header == EXPECTED_ANALYZE_QUALITY_HEADER


def test_analyze_quality_cli_help_is_compatible():
    result = subprocess.run(
        [sys.executable, str(ANALYZE_QUALITY), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    for token in CLI_HELP_TOKENS:
        assert token in result.stdout


def test_analyze_quality_formal_wrapper_still_calls_legacy_analyzer(tmp_path):
    export_path, logs_dir = _write_fixture(tmp_path)
    output_dir = tmp_path / "formal_out"

    subprocess.run(
        [
            sys.executable,
            str(ANALYZE_QUALITY_FORMAL),
            str(export_path),
            "--active-logs",
            str(logs_dir),
            "--output_dir",
            str(output_dir),
            "--project_version",
            "unit-formal",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    quality_csvs = list(output_dir.glob("quality_report_formal_*.csv"))
    manifests = list(output_dir.glob("formal_analysis_manifest_*.json"))
    assert len(quality_csvs) == 1
    assert len(manifests) == 1

    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert str(ANALYZE_QUALITY) in manifest["base_command"]

    with quality_csvs[0].open(newline="", encoding="utf-8") as f:
        header = list(csv.DictReader(f).fieldnames or [])
    assert not (FORMAL_DROPPED_COLUMNS & set(header))


def test_analyze_quality_cli_behavior_is_frozen_on_synthetic_fixture(tmp_path):
    header, rows, result = _run_cli(tmp_path)

    assert len(rows) == 3
    for field in KEY_FIELDS:
        assert field in header
    assert not (FORMAL_STAGE_FIELDS & set(header))

    by_user_task = {(r["annotator_id"], r["task_id"]): r for r in rows}
    row_1 = by_user_task[("1", "101")]
    assert float(row_1["active_time"]) == 12.0
    assert row_1["active_time_source"] == "log"
    assert row_1["active_time_match_status"] == "project+task+annotator"
    assert row_1["model_issue_required"] == "True"

    row_2 = by_user_task[("2", "101")]
    assert row_2["is_oos"] == "True"
    assert row_2["layout_used"] == "False"
    assert row_2["layout_gate_reason"] == "out_of_scope"
    assert row_2["reliability_used"] == "False"

    row_3 = by_user_task[("3", "102")]
    assert row_3["scope_missing"] == "True"
    assert row_3["is_normal"] == ""
    assert row_3["active_time_source"] == "lead_time_fallback"
    assert row_3["model_issue_required"] == "False"

    assert row_1["task_scope_is_mixed"] == "True"
    assert row_1["reliability_gate_reason"] == "excluded_from_consensus"
    assert row_1["iou_to_consensus_loo"] == ""

    assert "Analysis saved to" in result.stdout
    assert not (REPO_ROOT / "analysis_results" / "quality.csv").exists()
