import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tools.thesis_main.analysis.run_c1_closeout_launch import _c2_source_images, _final_risk_pool_gate, _future_heldout_images, _materialize_static_evidence_review_queues, _source_identity_aggregate, _write_c2b_import, audit_c1, bind_c2b_runtime_mapping, build_c2b, finalize_c1, freeze_c1, main, preflight_calibration, prepare_stage3_test_candidate, rehearse_c1, repackage_c2b_v17_to_v18, validate_runbook_command_contract
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _aggregate_sha, _c1_closeout_blockers
from tools.thesis_main.analysis.derive_c2b_design_thresholds import derive_threshold_manifest


def test_rehearsal_can_read_live_logs_but_cannot_be_formal(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        "tools.thesis_main.analysis.run_c1_closeout_launch.materialize_c1",
        lambda *args, **kwargs: captured.update(kwargs) or {"output_dir": str(tmp_path)},
    )
    monkeypatch.setattr(
        "tools.thesis_main.analysis.run_c1_closeout_launch._materialize_rehearsal_root_cause_report",
        lambda _summary: {"state": {"formal_closeout_ready": False}},
    )
    args = argparse.Namespace(
        export_dir=[], active_log=tmp_path / "new_server", manual_assignment=tmp_path / "m.csv",
        semi_assignment=tmp_path / "s.csv", worker_distribution=tmp_path / "w.csv",
        gt_export=tmp_path / "gt.json", p1_closeout_dir=tmp_path / "p1",
        output_root=tmp_path, c1_preannotation_feature_csv=None,
    )
    result = rehearse_c1(args)
    assert captured["input_status"] == "precloseout_rehearsal"
    assert result["formal_closeout_ready"] is False


def test_formal_audit_allows_missing_w034_timing_manifest_without_relaxing_other_inputs(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch.validate_active_log_freeze_manifest", lambda *_: None)
    monkeypatch.setattr(
        "tools.thesis_main.analysis.run_c1_closeout_launch.materialize_c1",
        lambda *args, **kwargs: captured.update(kwargs) or {
            "output_dir": str(tmp_path), "formal_closeout_ready": True, "blockers": [],
        },
    )
    args = argparse.Namespace(
        authorized_reassignment_manifest=tmp_path / "authorized.csv",
        building_registry=tmp_path / "building.csv",
        calibration_enrollment_registry=tmp_path / "enrollment.csv",
        w034_active_time_validation_manifest=None,
        c1_active_log_freeze_manifest=tmp_path / "active-freeze.json",
        export_dir=[], active_log=tmp_path / "logs", manual_assignment=tmp_path / "manual.csv",
        semi_assignment=tmp_path / "semi.csv", worker_distribution=tmp_path / "workers.csv",
        gt_export=tmp_path / "gt.json", p1_closeout_dir=tmp_path / "p1", output_root=tmp_path,
        independence_disposition=None, project_independence_disposition=None,
        structural_disposition=None, duplicate_adjudication=None, scope_initial_review=None,
        scope_adjudication=None, reference_amendment=None, outside_assignment_disposition=None,
        completion_disposition=None, collection_closure_manifest=None,
        c1_preannotation_feature_csv=None, p1_integrity_dir=None, late_entry_assignment_manifest=None,
    )
    assert audit_c1(args)["formal_closeout_ready"] is True
    assert captured["w034_active_time_validation_manifest"] is None


def test_public_cli_exposes_the_auditable_and_thin_entry_commands(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = capsys.readouterr().out
    for command in (
        "rehearse-c1", "prepare-c2b-static", "preflight-calibration", "freeze-c1",
        "audit-c1", "finalize-c1", "design-c2b", "build-c2b",
        "expand-building-registry", "repackage-c2b-v17-to-v18", "prepare-stage3-test-candidate", "check-command-contract",
    ):
        assert command in help_text
    for removed in ("day1-canonical-audit", "day1-formal-audit", "day2-c2b-build", "freeze-c1-active-log"):
        assert removed not in help_text


def test_stage3_test_candidate_preserves_rows_records_exposure_and_is_candidate_only(monkeypatch, tmp_path):
    test_list = tmp_path / "test.txt"
    test_list.write_text("scene-a image-0\nscene-b image-1\n", encoding="utf-8")
    image_dir = tmp_path / "test_img"; image_dir.mkdir()
    gt_dir = tmp_path / "test_gt"; gt_dir.mkdir()
    layout_dir = tmp_path / "layouts"; layout_dir.mkdir()
    for index in range(2):
        (image_dir / f"image-{index}.png").write_bytes(f"image-{index}".encode())
        (gt_dir / f"image-{index}.txt").write_text("gt", encoding="utf-8")
        (layout_dir / f"image-{index}.json").write_text(json.dumps({"layout": {"corners": [
            {"x": 10, "y_ceiling": 100, "y_floor": 400}, {"x": 180, "y_ceiling": 100, "y_floor": 400},
            {"x": 350, "y_ceiling": 100, "y_floor": 400}, {"x": 520, "y_ceiling": 100, "y_floor": 400},
            {"x": 690, "y_ceiling": 100, "y_floor": 400}, {"x": 860, "y_ceiling": 100, "y_floor": 400},
        ]}}), encoding="utf-8")
    validation_dir = tmp_path / "valid_img"; validation_dir.mkdir(); (validation_dir / "validation-only.png").write_bytes(b"validation")

    registry = tmp_path / "building.csv"
    registry.write_text("image_id,building_id,registry_status,reviewed_by,reviewed_at\nimage-0,scene-a,approved,researcher,2026-08-04\n", encoding="utf-8")
    reference = tmp_path / "c1_reference.csv"
    reference.write_text(
        "base_task_id,d_model_feat,d_model_feat_local_max,g_model_struct,d_cal_A\n"
        "r0,1,1,0.1,0.1\n"
        "r1,2,2,0.2,0.2\n"
        "r2,3,3,0.3,0.3\n"
        "r3,4,4,0.4,0.4\n", encoding="utf-8",
    )
    source_summary = tmp_path / "c1_risk.summary.json"
    source_summary.write_text(json.dumps({
        "method_contract_version": "paper_a_method_20260802_v17",
        "method_contract_sha256": "5068e08ade8d1f2013b5ed66af04761c210acf74ef522229ffd39ad8f6b17b4c",
        "c1_task_risk_reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    checkpoint = tmp_path / "checkpoint.pth"; checkpoint.write_bytes(b"checkpoint")
    config = tmp_path / "config.yaml"; config.write_text("model: test\n", encoding="utf-8")
    reference_cache = tmp_path / "reference.npz"
    np.savez_compressed(
        reference_cache,
        global_mean=np.zeros(2), global_components=np.eye(2), global_scale=np.ones(2),
        local_mean=np.zeros(2), local_components=np.eye(2), local_scale=np.ones(2),
        reference_global=np.asarray([[0., 0.], [1., 1.], [2., 2.]]),
        reference_local=np.asarray([[0., 0.], [1., 1.], [2., 2.]]),
    )
    thresholds = tmp_path / "feature_thresholds.json"
    thresholds.write_text(json.dumps({
        "status": "approved", "formal_feature_freeze_allowed": True, "approved_by": "researcher", "approved_at": "2026-08-04",
        "thresholds": {"circular_relative_l2_max": 1, "seam_relative_l2_q95": 1, "minimum_circular_audited_image_count": 1, "minimum_seam_audited_image_count": 1},
    }), encoding="utf-8")
    feature_manifest = tmp_path / "feature.json"
    feature_manifest.write_text(json.dumps({
        "schema_version": "paper_a_c2_feature_freeze_v2", "feature_audit_status": "approved",
        "pca_frozen": True, "whitening_frozen": True, "circular_shift_invariant": True, "seam_invariant": True,
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "feature_cache_path": str(reference_cache), "reference_feature_sha256": hashlib.sha256(reference_cache.read_bytes()).hexdigest(),
        "feature_audit_threshold_manifest_sha256": hashlib.sha256(thresholds.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    p1 = tmp_path / "p1.csv"; p1.write_text("image_id,used_in_prescreen\nimage-0,true\nimage-1,false\n", encoding="utf-8")
    c1 = tmp_path / "c1.csv"; c1.write_text("image_id,used_in_random_c1_deprecated\nimage-0,false\nimage-1,true\n", encoding="utf-8")
    c2b = tmp_path / "c2b.csv"; c2b.write_text("image_id\nimage-1\n", encoding="utf-8")

    def fake_extract(paths, _checkpoint, _config, *, device, batch_size, audit_seam):
        descriptors = {path.resolve().as_posix(): (np.asarray([float(index + 1), float(index + 1)]), np.asarray([float(index + 1), float(index + 1)])) for index, path in enumerate(paths)}
        return descriptors, {"circular_relative_l2_max": .1, "circular_audited_image_count": len(paths), "seam_relative_l2_q95": .1, "seam_audited_image_count": len(paths)}

    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch.extract_orbit_descriptors", fake_extract)
    output = tmp_path / "stage3"
    result = prepare_stage3_test_candidate(argparse.Namespace(
        test_list=test_list, image_dir=image_dir, gt_dir=gt_dir, layout_dir=layout_dir,
        validation_image_dir=validation_dir, building_registry=registry, c1_risk_reference=reference,
        c1_risk_summary=source_summary, feature_freeze_manifest=feature_manifest,
        feature_audit_threshold_manifest=thresholds, risk_contract=Path("docs/thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json"),
        checkpoint=checkpoint, config=config, exposure_source=[f"P1={p1}", f"C1={c1}", f"C2B={c2b}"],
        output_dir=output, device="cpu",
    ))

    inventory = list(csv.DictReader((output / "stage3_test_inventory_candidate.csv").open(encoding="utf-8")))
    risk = list(csv.DictReader((output / "test_task_risk_candidate.csv").open(encoding="utf-8")))
    summary = json.loads((output / "test_task_risk_candidate.summary.json").read_text(encoding="utf-8"))
    assert result["candidate_only"] is True and result["formal_ready"] is False
    assert len(inventory) == len(risk) == 2
    assert "P1_exposed" in inventory[0] and "candidate_blockers_json" in inventory[0]
    assert all("img_v" not in row["image_path"] for row in inventory)
    assert inventory[0]["P1_exposed"] == "true" and inventory[1]["C1_exposed"] == "true"
    assert all(row["risk_design_stratum"] in {"ordinary", "stress"} for row in risk)
    assert all(row["risk_route"] == "" and row["candidate_only"] == "true" for row in risk)
    assert summary["source_method_binding"]["source_method_contract_version"] == "paper_a_method_20260802_v17"
    assert summary["source_method_binding"]["target_method_contract_version"] == "paper_a_method_20260810_v20"
    assert summary["feature_audit_threshold_manifest_sha256"] == hashlib.sha256(thresholds.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="target artifact already exists"):
        prepare_stage3_test_candidate(argparse.Namespace(
            test_list=test_list, image_dir=image_dir, gt_dir=gt_dir, layout_dir=layout_dir,
            validation_image_dir=validation_dir, building_registry=registry, c1_risk_reference=reference,
            c1_risk_summary=source_summary, feature_freeze_manifest=feature_manifest,
            feature_audit_threshold_manifest=thresholds, risk_contract=Path("docs/thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json"),
            checkpoint=checkpoint, config=config, exposure_source=[f"P1={p1}"], output_dir=output, device="cpu",
        ))


def test_c2b_import_matches_prior_formal_import_shape(monkeypatch, tmp_path):
    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch._PROJECT_ROOT", tmp_path)
    layouts = tmp_path / "layouts"; layouts.mkdir()
    (layouts / "base-1.json").write_text(json.dumps({"layout": {"corners": [
        {"x": 1, "y_ceiling": 2, "y_floor": 3, "id": 0},
        {"x": 4, "y_ceiling": 5, "y_floor": 6, "id": 1},
    ]}}), encoding="utf-8")
    output = tmp_path / "analysis"; output.mkdir()
    path = _write_c2b_import(output, [{
        "task_id": "task-1", "base_task_id": "base-1", "image_id": "image-1",
        "image_path": "https://example.test/valid_no_occ/img/base-1.png",
    }], batch_id="C2B_BATCH_A", selected_design_id="D8", selected_design_sha="abc", layout_dir=layouts)

    zh = json.loads(path.read_text(encoding="utf-8"))
    foreign = json.loads((tmp_path / "import_json/c2b/c2b_D8_batch_a_import_foreign_https.json").read_text(encoding="utf-8"))
    assert set(zh[0]) == {"data"}
    assert zh[0]["data"]["title"] == "base-1.jpg"
    assert zh[0]["data"]["image"] == "https://example.test/img_v/base-1.jpg"
    assert zh[0]["data"]["planned_task_id"] == "task-1"
    assert zh[0]["data"]["vis_3d"].startswith("http://175.178.71.217:8000/tools/vis_3d.html?")
    assert foreign[0]["data"]["vis_3d"].startswith("https://label.sparkle0825.top/tools/vis_3d.html?")
    assert "predictions" not in zh[0]


def test_d8_v17_to_v18_repackage_preserves_assignment_and_records_dual_deployment_sha(tmp_path):
    legacy = Path("analysis_results/c2b_build_20260802_v17_d8")
    zh_import = Path("import_json/c2b/c2b_D8_batch_a_import_zh.json")
    foreign_import = Path("import_json/c2b/c2b_D8_batch_a_import_foreign_https.json")
    config = tmp_path / "deployment_config.json"
    config.write_text(json.dumps({
        "schema_version": "c2b_migration_deployment_config_v1",
        "deployments": [
            {
                "deployment_id": "c2b_zh",
                "language_group": "Chinese",
                "server_instance_id": "labelstudio_http_175_178_71_217",
                "server_url": "http://175.178.71.217:8000",
                "project_id": "project-zh",
                "source_import_path": str(zh_import),
                "planned_import_filename": "c2b_D8_batch_a_import_zh_v18.json",
            },
            {
                "deployment_id": "c2b_en",
                "language_group": "English",
                "server_instance_id": "labelstudio_https_sparkle0825",
                "server_url": "https://label.sparkle0825.top",
                "project_id": "project-en",
                "source_import_path": str(foreign_import),
                "planned_import_filename": "c2b_D8_batch_a_import_foreign_https_v18.json",
            },
        ],
    }), encoding="utf-8")
    args = argparse.Namespace(
        legacy_root=legacy,
        legacy_launch_report=legacy / "c2b_launch_ready_report.json",
        legacy_assignment=legacy / "assignment_manifest_C2B.csv",
        legacy_selected_design_manifest=legacy / "inputs/c2b_selected_design_manifest_D8.json",
        legacy_import_zh=zh_import,
        legacy_import_foreign=foreign_import,
        worker_language_source=legacy / "worker_facing_release_C2B_D8/internal/worker_facing_distribution_index_C2B_D8.csv",
        deployment_config=config,
        output_dir=tmp_path / "migration",
        target_import_dir=tmp_path / "target_imports",
        target_method_contract=None,
    )

    result = repackage_c2b_v17_to_v18(args)

    assert result["launch_ready"] is True
    assert result["formal_ready"] is False
    assert result["selected_design_id"] == "D8"
    assert result["n_assignments"] == 176
    assert result["n_workers"] == 22
    assert result["n_tasks"] == 46
    assert "import_sha256" not in result
    assert result["method_contract_version"] == "paper_a_method_20260810_v20"
    assert len(result["deployments"]) == 2

    assignment = args.output_dir / "assignment_manifest_C2B.csv"
    mapping = args.output_dir / "c2b_v17_to_v18_assignment_mapping.csv"
    registry = json.loads((args.output_dir / "c2b_worker_language_registry_v1.json").read_text(encoding="utf-8"))
    envelope = json.loads((args.output_dir / "c2b_v17_to_v18_repackage_envelope_v1.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(assignment.read_bytes()).hexdigest() == "5e43e682a46211fb35ed5588b0f22b2853997236bff814f14f1306246907a07c"
    assert len(list(csv.DictReader(mapping.open(encoding="utf-8", newline="")))) == 176
    assert {row["language_group"] for row in registry["workers"]} == {"Chinese", "English"}
    assert len(registry["workers"]) == 22
    assert envelope["source_method_contract_sha256"] == "5068e08ade8d1f2013b5ed66af04761c210acf74ef522229ffd39ad8f6b17b4c"
    assert envelope["target_method_contract_sha256"] == "085fd9ec0f14a93c986e9f7dda7883173d9ec64959188139a25012d0e6d36b9d"
    assert envelope["runtime_binding_status"] == "not_bound"

    for deployment in result["deployments"]:
        planned = Path(deployment["planned_import_path"])
        tasks = json.loads(planned.read_text(encoding="utf-8"))
        assert len(tasks) == 46
        assert {item["data"]["calibration_version"] for item in tasks} == {"C2-B_v18"}
        assert {item["data"]["deployment_id"] for item in tasks} == {deployment["deployment_id"]}
        assert {item["data"]["project_id"] for item in tasks} == {deployment["project_id"]}

    with pytest.raises(ValueError, match="target artifact already exists"):
        repackage_c2b_v17_to_v18(args)


def test_d8_v18_repackage_binds_runtime_by_content_and_writes_formal_evidence(tmp_path):
    legacy = Path("analysis_results/c2b_build_20260802_v17_d8")
    zh_import = Path("import_json/c2b/c2b_D8_batch_a_import_zh.json")
    foreign_import = Path("import_json/c2b/c2b_D8_batch_a_import_foreign_https.json")
    config = tmp_path / "deployment_config.json"
    config.write_text(json.dumps({
        "schema_version": "c2b_migration_deployment_config_v1",
        "deployments": [
            {"deployment_id": "c2b_zh", "language_group": "Chinese", "server_instance_id": "http-server", "server_url": "http://175.178.71.217:8000", "project_id": "project-zh", "source_import_path": str(zh_import), "planned_import_filename": "d8_v18_zh.json"},
            {"deployment_id": "c2b_en", "language_group": "English", "server_instance_id": "https-server", "server_url": "https://label.sparkle0825.top", "project_id": "project-en", "source_import_path": str(foreign_import), "planned_import_filename": "d8_v18_en.json"},
        ],
    }), encoding="utf-8")
    output_dir = tmp_path / "migration"
    repackage_c2b_v17_to_v18(argparse.Namespace(
        legacy_root=legacy, legacy_launch_report=legacy / "c2b_launch_ready_report.json",
        legacy_assignment=legacy / "assignment_manifest_C2B.csv",
        legacy_selected_design_manifest=legacy / "inputs/c2b_selected_design_manifest_D8.json",
        legacy_import_zh=zh_import, legacy_import_foreign=foreign_import,
        worker_language_source=legacy / "worker_facing_release_C2B_D8/internal/worker_facing_distribution_index_C2B_D8.csv",
        deployment_config=config, output_dir=output_dir, target_import_dir=tmp_path / "imports", target_method_contract=None,
    ))
    runtime_paths = []
    for deployment in json.loads((output_dir / "c2b_launch_ready_report.json").read_text(encoding="utf-8"))["deployments"]:
        planned = Path(deployment["planned_import_path"])
        tasks = json.loads(planned.read_text(encoding="utf-8"))
        runtime = tmp_path / f"runtime_export_{len(runtime_paths)}_arbitrary_name.json"
        runtime.write_text(json.dumps([
            {"id": f"runtime-{deployment['deployment_id']}-{index}", "data": item["data"]}
            for index, item in enumerate(tasks)
        ]), encoding="utf-8")
        runtime_paths.append(runtime)
    audit = bind_c2b_runtime_mapping(argparse.Namespace(
        launch_report=output_dir / "c2b_launch_ready_report.json",
        assignment_manifest=output_dir / "assignment_manifest_C2B.csv",
        worker_distribution=output_dir / "worker_distribution_C2B.csv",
        deployment_manifest=output_dir / "c2b_worker_deployment_manifest_v1.json",
        planned_import=[Path(item["planned_import_path"]) for item in json.loads((output_dir / "c2b_launch_ready_report.json").read_text(encoding="utf-8"))["deployments"]],
        runtime_export=runtime_paths, output_dir=output_dir,
    ))
    evidence = json.loads((output_dir / "c2b_v17_to_v18_runtime_evidence_v1.json").read_text(encoding="utf-8"))
    assert audit["formal_ready"] is True
    assert audit["runtime_task_count"] == 92
    assert audit["worker_task_binding_count"] == 176
    assert evidence["formal_ready"] is True
    assert evidence["runtime_binding_status"] == "bound"
    assert json.loads((output_dir / "c2b_worker_task_binding_audit.json").read_text(encoding="utf-8"))["runtime_evidence_sha256"] == hashlib.sha256((output_dir / "c2b_v17_to_v18_runtime_evidence_v1.json").read_bytes()).hexdigest()


def test_runner_materializes_geometry_once_after_final_pool_gate():
    runner = Path("tools/thesis_main/analysis/run_c1_precloseout_rehearsal.py").read_text(encoding="utf-8")
    canonicalizer = Path("tools/thesis_main/analysis/c1_canonicalize_exports.py").read_text(encoding="utf-8")
    assert runner.count("materialize_geometry_consensus(") == 1
    assert "excluded_worker_ids=administratively_excluded_workers" in runner
    assert "eligible_annotation_ids=eligible_geometry_ids" in runner
    assert runner.index("materialize_geometry_pool_eligibility(") < runner.index("materialize_geometry_consensus(")
    assert "materialize_canonical_evidence(" not in runner
    assert canonicalizer.count("materialize_geometry_consensus(") == 0
    assert canonicalizer.count("materialize_canonical_evidence(") == 1


def test_formal_runner_does_not_require_an_empty_reference_amendment_file():
    runner = Path("tools/thesis_main/analysis/run_c1_precloseout_rehearsal.py").read_text(encoding="utf-8")
    assert "reference_amendment is None or" not in runner
    assert "formal C1 requires frozen reference approval" not in runner


def test_formal_stage_outputs_are_ignored_so_the_next_clean_git_gate_can_run():
    for path in (
        "analysis_results/c1_formal_audit_sha/result.csv",
        "analysis_results/c1_reviews_sha/disposition.csv",
        "analysis_results/c2b_design_sha/result.csv",
        "analysis_results/c2b_build_sha/result.csv",
    ):
        assert subprocess.run(["git", "check-ignore", "-q", path]).returncode == 0


def test_fresh_checkout_keeps_both_numeric_threshold_contracts():
    for path in (
        "docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json",
        "docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json",
    ):
        assert subprocess.run(["git", "check-ignore", "-q", path]).returncode != 0


def test_c2b_threshold_formula_contract_keeps_v18_binding_through_capacity_only_amendments():
    path = Path("docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    method_path = Path("docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json")
    method = json.loads(method_path.read_text(encoding="utf-8"))
    extension_path = Path(method["c2a_rp_precision_cap_extension"]["path"])
    extension = json.loads(extension_path.read_text(encoding="utf-8"))
    assert payload["method_contract_version"] == extension["previous_method_contract_version"]
    assert payload["method_contract_sha256"] == extension["previous_method_contract_sha256"]
    assert method["c2a_rp_precision_cap_extension"]["significance_seeking"] is False
    assert payload["compatibility_rebind"]["semantic_change"] is True
    assert payload["gate_roles"]["maximum_mean_rank_displacement"] == "post_C2_diagnostic_not_dispatch_gate"
    assert payload["gate_roles"]["minimum_worker_support"] == "deterministic_assignment_manifest_dispatch_hard_gate"
    assert [(row["design_id"], row["common_anchor_count"], row["bridge_per_worker"]) for row in payload["candidate_designs"]] == [
        ("D8", 4, 4), ("D10", 6, 4), ("D12", 6, 6),
    ]


def test_design_thresholds_are_mechanically_derived_from_sha_bound_c1_and_capacity(tmp_path):
    contract = tmp_path / "formula.json"
    contract.write_text(json.dumps({
        "schema_version": "paper_a_c2b_design_threshold_formula_contract_v1",
        "status": "frozen_before_c1_closeout", "formula_contract_frozen": True,
        "frozen_by": "reviewer", "frozen_at": "2026-07-26T00:00:00Z",
        "constants": {"normal_95_multiplier": 1.96, "minimum_worker_support_cap": 4},
        "threshold_rules": {
            "q_gt_ci_half_width": {"formula_id": "normal_95_max_worker_se", "direction": "maximum"},
            "risk_slope_ci_half_width": {"formula_id": "normal_95_max_unified_slope_sd", "direction": "maximum"},
            "minimum_worker_support": {"formula_id": "min_constant_and_min_capacity", "constant_key": "minimum_worker_support_cap", "direction": "minimum"},
            **{
                name: {"formula_id": "frozen_constant", "constant_key": name, "direction": direction}
                for name, direction in {
                    "minimum_worker_rank_spearman": "minimum", "minimum_top_k_overlap": "minimum",
                    "maximum_mean_rank_displacement": "maximum", "minimum_task_support": "minimum",
                    "graph_connectivity_probability": "minimum", "minimum_building_coverage": "minimum",
                    "building_coverage_probability": "minimum", "ordinary_coverage_probability": "minimum",
                    "stress_coverage_probability": "minimum", "minimum_eligible_task_count": "minimum",
                    "minimum_eligible_building_count": "minimum", "minimum_ordinary_task_count": "minimum",
                    "minimum_stress_task_count": "minimum",
                }.items()
            },
        },
        "common_anchor_requirements": {"minimum_count": 2, "required_strata": ["ordinary", "stress"]},
    } | {"constants": {
        "normal_95_multiplier": 1.96, "minimum_worker_support_cap": 4,
        "minimum_worker_rank_spearman": .8, "minimum_top_k_overlap": 2 / 3,
        "maximum_mean_rank_displacement": 1, "minimum_task_support": 2,
        "graph_connectivity_probability": .9, "minimum_building_coverage": 2,
        "building_coverage_probability": .9, "ordinary_coverage_probability": .9,
        "stress_coverage_probability": .9, "minimum_eligible_task_count": 8,
        "minimum_eligible_building_count": 3, "minimum_ordinary_task_count": 4,
        "minimum_stress_task_count": 4,
    }}), encoding="utf-8")
    c1 = tmp_path / "c1.csv"
    with c1.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "worker_id", "c2b_baseline_eligible", "Q_GT_baseline_se", "risk_slope_for_simulation",
            "risk_slope_se", "risk_support", "group_slope_mean", "group_slope_se",
            "between_worker_slope_sd", "slope_model_form",
        ])
        writer.writeheader(); writer.writerows([
            {"worker_id": "w1", "c2b_baseline_eligible": "true", "Q_GT_baseline_se": .05, "risk_slope_for_simulation": -.2, "risk_slope_se": .04, "risk_support": 6, "group_slope_mean": -.1, "group_slope_se": .03, "between_worker_slope_sd": .2, "slope_model_form": "crossed_random_worker_slope"},
            {"worker_id": "w2", "c2b_baseline_eligible": "true", "Q_GT_baseline_se": .06, "risk_slope_for_simulation": -.1, "risk_slope_se": .02, "risk_support": 6, "group_slope_mean": -.1, "group_slope_se": .03, "between_worker_slope_sd": .2, "slope_model_form": "crossed_random_worker_slope"},
        ])
    capacity = tmp_path / "capacity.csv"
    capacity.write_text("worker_id,c2b_capacity\nw1,5\nw2,4\n", encoding="utf-8")
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "schema_version": "paper_a_c2b_threshold_input_approval_v1", "approved": True,
        "formula_contract_sha256": hashlib.sha256(contract.read_bytes()).hexdigest(),
        "c1_design_parameters_sha256": hashlib.sha256(c1.read_bytes()).hexdigest(),
        "capacity_manifest_sha256": hashlib.sha256(capacity.read_bytes()).hexdigest(),
        "reviewed_by": "reviewer", "reviewed_at": "2026-07-27T00:00:00Z",
    }), encoding="utf-8")
    output = tmp_path / "derived.json"

    result = derive_threshold_manifest(contract, c1, capacity, approval, output)

    assert result["status"] == "approved" and result["formal_selection_allowed"] is True
    assert result["thresholds"]["q_gt_ci_half_width"] == pytest.approx(1.96 * .06)
    assert result["thresholds"]["risk_slope_ci_half_width"] == pytest.approx(1.96 * .05)
    assert result["thresholds"]["minimum_worker_support"] == 4
    assert result["derivation"]["post_feasibility_inputs_consumed"] is False
    rows = list(csv.DictReader(c1.open(encoding="utf-8")))
    rows[0]["Q_GT_baseline_se"] = "nan"
    with c1.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    approval_payload = json.loads(approval.read_text(encoding="utf-8"))
    approval_payload["c1_design_parameters_sha256"] = hashlib.sha256(c1.read_bytes()).hexdigest()
    approval.write_text(json.dumps(approval_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Q_GT baseline SE"):
        derive_threshold_manifest(contract, c1, capacity, approval, output)
    c1.write_text(c1.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        derive_threshold_manifest(contract, c1, capacity, approval, output)


def test_final_risk_pool_freezes_only_after_building_and_both_strata_gates(tmp_path):
    threshold = tmp_path / "threshold.json"
    threshold.write_text(json.dumps({
        "status": "approved", "formal_selection_allowed": True,
        "thresholds": {
            "minimum_eligible_task_count": 2, "minimum_eligible_building_count": 2,
            "minimum_ordinary_task_count": 1, "minimum_stress_task_count": 1,
        },
    }), encoding="utf-8")
    ordinary_only = [
        {"assignment_eligible": "true", "building_id": "b1", "risk_design_stratum": "ordinary"},
        {"assignment_eligible": "true", "building_id": "b2", "risk_design_stratum": "ordinary"},
    ]
    assert _final_risk_pool_gate(ordinary_only, threshold)["frozen"] is False
    ordinary_only[1]["risk_design_stratum"] = "stress"
    gate = _final_risk_pool_gate(ordinary_only, threshold)
    assert gate["frozen"] is True
    assert gate["observed"] == {
        "minimum_eligible_task_count": 2, "minimum_eligible_building_count": 2,
        "minimum_ordinary_task_count": 1, "minimum_stress_task_count": 1,
    }


def test_preflight_rejects_null_thresholds_and_unapproved_feature_freeze(tmp_path):
    static = tmp_path / "static"; (static / "p1_integrity").mkdir(parents=True)
    (static / "paper_a_analysis_environment_manifest.json").write_text(json.dumps({
        "python": "3.11.7", "packages": {"torch": "2.11.0+cu128", "torchvision": "0.26.0+cu128"},
        "cuda_available": True, "cuda_build": "12.8", "physical_batch_size": 4,
        "nvidia_driver_version": "610.62", "dependency_lock_sha256": {"analysis": "a", "torch": "b"},
    }), encoding="utf-8")
    (static / "c2_feature_freeze_manifest.json").write_text(json.dumps({"feature_audit_status": "pending_threshold_approval_or_failed"}), encoding="utf-8")
    for path in (
        static / "p1_integrity" / "p1_post_closeout_correction_summary_v1.json",
        static / "p1_integrity" / "p1_geometry_score_summary_v1.json",
        static / "c2_legacy_reverse_candidate_audit.summary.json",
        static / "c2b_static_evidence_review_queues.summary.json",
    ):
        path.write_text("{}", encoding="utf-8")
    design = tmp_path / "design.json"; feature = tmp_path / "feature.json"
    design.write_text(json.dumps({"status": "pending", "formal_selection_allowed": False, "thresholds": {}}), encoding="utf-8")
    feature.write_text(json.dumps({"status": "pending", "formal_feature_freeze_allowed": False, "thresholds": {}}), encoding="utf-8")
    result = preflight_calibration(argparse.Namespace(
        static_dir=static, threshold_manifest=design, feature_audit_threshold_manifest=feature,
        output=tmp_path / "preflight.json",
    ))
    assert result["ready"] is False
    assert {
        "unapproved_or_incomplete:design_thresholds",
        "unapproved_or_incomplete:feature_thresholds",
        "feature_freeze_not_approved",
        "missing:p1_integrity_bundle", "missing:leakage_audit",
        "missing:split_proposals", "missing:static_freeze",
    }.issubset(result["blockers"])


def test_static_evidence_queues_do_not_promote_inventory_hints(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text(
        "task_id,base_task_id,image_id,source_path,source_pool,building_id,used_in_prescreen,scope_gold_ready\n"
        "t1,b1,scene_uuid,image.jpg,pool,guessed_building,true,true\n",
        encoding="utf-8",
    )
    legacy = tmp_path / "legacy.csv"
    legacy.write_text("image_id,base_task_id\nscene_uuid,b1\n", encoding="utf-8")

    result = _materialize_static_evidence_review_queues(inventory, legacy, tmp_path / "out")

    assert result["formal_evidence_ready"] is False
    queue = (tmp_path / "out" / "authoritative_building_scene_mapping_pilot.review_queue.csv").read_text(encoding="utf-8")
    assert "guessed_building" not in queue
    assert "pending_scene_mapping_review" in queue
    assert result["building_scene_pilot_count"] <= 15


def test_runbook_command_contract_matches_real_artifact_names() -> None:
    result = validate_runbook_command_contract(Path("docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md"))
    assert result["valid"] is True
    assert result["violations"] == []
    runbook = Path("docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md").read_text(encoding="utf-8")
    assert "close-c1-and-plan-c2b" not in runbook


def test_freeze_c1_atomically_creates_active_log_and_collection_contracts(tmp_path):
    live, frozen, exports = tmp_path / "new_server", tmp_path / "c1", tmp_path / "exports"
    live.mkdir(); exports.mkdir()
    (live / "active_times_2026-07-25.jsonl").write_text(
        json.dumps({"server_received_at": "2026-07-25T01:00:00Z", "task_id": "1"}) + "\n",
        encoding="utf-8",
    )
    (exports / "c1.json").write_text("[]", encoding="utf-8")
    manual, semi = tmp_path / "manual.csv", tmp_path / "semi.csv"
    manual.write_text("worker_id,task_id\nW001,1\n", encoding="utf-8")
    semi.write_text("worker_id,task_id\nW001,2\n", encoding="utf-8")
    active_manifest, closure_manifest = tmp_path / "active.json", tmp_path / "closure.json"

    result = freeze_c1(argparse.Namespace(
        source_live_root=live, frozen_root=frozen,
        collection_cutoff_server_time="2026-07-25T02:00:00Z", operator="operator",
        late_submission_policy="exclude_after_cutoff", active_log_freeze_manifest=active_manifest,
        collection_closure_manifest=closure_manifest, export_dir=[exports],
        manual_assignment=manual, semi_assignment=semi,
    ))

    assert result["active_log"]["source_aggregate_sha256"] == result["active_log"]["frozen_aggregate_sha256"]
    assert result["collection_closure"]["collection_window_closed"] is True
    assert result["collection_closure"]["c1_active_log_freeze_manifest_sha256"]


def test_day2_fails_closed_before_materializing_assignments(tmp_path, monkeypatch):
    closeout = tmp_path / "closeout.json"
    risk = tmp_path / "risk.json"
    closeout.write_text(json.dumps({"formal_closeout_ready": False}), encoding="utf-8")
    risk.write_text(json.dumps({"formal_ready": False}), encoding="utf-8")
    args = argparse.Namespace(c1_closeout_summary=closeout, risk_summary=risk)
    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch.formal_git_state", lambda _root: {"clean": True})
    with pytest.raises(ValueError, match="not formally frozen"):
        build_c2b(args)


def _write_c1_dependency_closure(tmp_path):
    from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, sha256_file
    profile = tmp_path / "c1_three_track_worker_state_formal.csv"
    profile.write_text(
        "schema_version,worker_id,profile_version,cohort_id,enrollment_batch,administratively_eligible,process_eligible,independence_eligible,Q_GT_estimable,reference_evaluable,Q_GT_profile_status,R_peer_profile_status,peer_task_support,F_struct_profile_status,LOO_medoid_status,LOO_strict_status,global_policy_eligible,c2_risk_model_eligible,peer_tiebreak_eligible,structural_gate_eligible,F_struct_raw,F_struct_EB,F_struct_interval_lower,F_struct_interval_upper,completion_status\n"
        "worker_profile_v2,w1,p,c,original,true,true,true,true,true,estimated,estimated,5,estimated,not_evaluable,not_evaluable,true,true,true,true,0,0,0,.1,completed\n",
        encoding="utf-8",
    )
    enrollment = tmp_path / "calibration_enrollment_registry.csv"
    enrollment.write_text("worker_id,enrollment_batch,rolling_activated,admission_status,terminal_status,enrolled_at\nw1,original,false,admitted,completed,2026-07-01\n", encoding="utf-8")
    enrollment_summary = tmp_path / "calibration_enrollment_registry.summary.json"
    enrollment_summary.write_text(json.dumps({"schema_version": "calibration_enrollment_registry_v1", "status": "validated", "rolling_activated": False, "N_total": 1, "N_late": 0, "all_registered_workers_terminal": True, "registry_sha256": sha256_file(enrollment)}), encoding="utf-8")
    method_dependency = {"role": "METHOD_CONTRACT", "path": str(METHOD_CONTRACT.resolve()), "sha256": sha256_file(METHOD_CONTRACT)}
    frozen_dependencies = []
    for role, name in (
        ("REFERENCE_REGISTRY", "reference_registry.csv"),
        ("BUILDING_REGISTRY", "building_registry.csv"),
        ("TASK_BUILDING_BINDING", "task_building_binding.csv"),
    ):
        path = tmp_path / name
        path.write_text("evidence\nfrozen\n", encoding="utf-8")
        frozen_dependencies.append({"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)})
    (tmp_path / "c1_three_track_worker_state_manifest.json").write_text(json.dumps({
        "schema_version": "c1_three_track_worker_state_manifest_v1", "profile_version": "p", "cohort_id": "c",
        "worker_state_sha256": sha256_file(profile), "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "dependencies": [method_dependency, {"role": "ENROLLMENT_REGISTRY", "path": str(enrollment.resolve()), "sha256": sha256_file(enrollment)}, *frozen_dependencies],
    }), encoding="utf-8")
    (tmp_path / "w034_original_vs_authorized_sensitivity.json").write_text(json.dumps({
        "schema_version": "w034_authorized_extension_sensitivity_freeze_v1", "status": "frozen",
        "profile_version": "p", "cohort_id": "c", "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "dependencies": [method_dependency],
    }), encoding="utf-8")


def test_day1_finalize_freezes_c1_evidence_but_not_routing_profile(tmp_path):
    _write_c1_dependency_closure(tmp_path)
    (tmp_path / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_MEASUREMENT_FROZEN": True, "C1_EVIDENCE_BUNDLE_FROZEN": True, "C2B_BASELINE_INPUT_FROZEN": True, "collection_window_closed": True, "Q_GT_FREEZE_STATUS": "frozen", "R_PEER_FREEZE_STATUS": "frozen", "F_STRUCT_FREEZE_STATUS": "frozen", "R_LOO_MEDOID_STATUS": "support_limited", "R_LOO_STRICT_STATUS": "support_limited"}), encoding="utf-8")
    (tmp_path / "c1_final_canonical_closeout_summary.json").write_text(json.dumps({"blockers": [], "formal_closeout_ready": True}), encoding="utf-8")
    (tmp_path / "formal_audit_summary.json").write_text(json.dumps({"input_status": "formal", "formal_closeout_ready": True, "blockers": [], "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1", "git_commit_sha": "a" * 40, "worktree_clean": True, "full_dependency_bundle_sha256": "bundle", "C1_CANONICAL_CLOSED": True, "collection_closure": {"status": "validated"}}), encoding="utf-8")
    adjudication = tmp_path / "adjudication.json"; adjudication.write_text(json.dumps({"approved": True, "input_bundle_sha256": "bundle"}), encoding="utf-8")
    result = finalize_c1(argparse.Namespace(output_dir=tmp_path, adjudication_manifest=adjudication))
    assert result["formal_closeout_ready"] is True
    assert result["C1_MEASUREMENT_FROZEN"] is True
    assert result["routing_profile_frozen"] is False


def test_collection_stays_closed_when_qgt_is_support_limited_and_only_c2b_is_blocked(tmp_path):
    _write_c1_dependency_closure(tmp_path)
    (tmp_path / "c1_measurement_freeze_manifest.json").write_text(json.dumps({
        "C1_EVIDENCE_BUNDLE_FROZEN": True, "C2B_BASELINE_INPUT_FROZEN": False,
        "collection_window_closed": True, "Q_GT_FREEZE_STATUS": "support_limited",
        "R_PEER_FREEZE_STATUS": "frozen", "F_STRUCT_FREEZE_STATUS": "frozen", "R_LOO_MEDOID_STATUS": "frozen", "R_LOO_STRICT_STATUS": "frozen",
    }), encoding="utf-8")
    (tmp_path / "c1_final_canonical_closeout_summary.json").write_text(json.dumps({"blockers": [], "formal_closeout_ready": True, "C1_CANONICAL_CLOSED": True}), encoding="utf-8")
    (tmp_path / "formal_audit_summary.json").write_text(json.dumps({
        "input_status": "formal", "formal_closeout_ready": True, "blockers": [],
        "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1", "git_commit_sha": "a" * 40,
        "worktree_clean": True, "full_dependency_bundle_sha256": "bundle", "C1_CANONICAL_CLOSED": True,
        "collection_closure": {"status": "validated"},
    }), encoding="utf-8")
    adjudication = tmp_path / "adjudication.json"
    adjudication.write_text(json.dumps({"approved": True, "input_bundle_sha256": "bundle"}), encoding="utf-8")
    result = finalize_c1(argparse.Namespace(output_dir=tmp_path, adjudication_manifest=adjudication))
    freeze = json.loads((tmp_path / "c1_evidence_freeze_manifest.json").read_text(encoding="utf-8"))
    assert result["formal_closeout_ready"] is True
    assert freeze["C1_COLLECTION_INCOMPLETE"] is False and freeze["C1_EVIDENCE_BUNDLE_FROZEN"] is True
    assert result["C2B_DESIGN_READY"] is False
    assert result["c2b_baseline_blockers"] == ["q_gt_baseline_support_limited_or_not_frozen"]


def test_day1_finalize_refuses_unresolved_formal_blockers(tmp_path):
    (tmp_path / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_MEASUREMENT_FROZEN": True, "C2B_DESIGN_READY": True}), encoding="utf-8")
    (tmp_path / "c1_final_canonical_closeout_summary.json").write_text(json.dumps({"blockers": ["unreviewed_structural_rows"], "formal_closeout_ready": False}), encoding="utf-8")
    (tmp_path / "formal_audit_summary.json").write_text(json.dumps({"input_status": "formal", "formal_closeout_ready": False, "blockers": ["unreviewed_structural_rows"], "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1", "git_commit_sha": "a" * 40, "worktree_clean": True, "full_dependency_bundle_sha256": "bundle", "C1_CANONICAL_CLOSED": True, "collection_closure": {"status": "validated"}}), encoding="utf-8")
    adjudication = tmp_path / "adjudication.json"; adjudication.write_text(json.dumps({"approved": True, "input_bundle_sha256": "bundle"}), encoding="utf-8")
    result = finalize_c1(argparse.Namespace(output_dir=tmp_path, adjudication_manifest=adjudication))
    assert result["formal_closeout_ready"] is False
    assert "formal_audit_or_closeout_blocked" in result["blockers"]


def test_future_c2_confirmation_never_blocks_c1_closeout_owner():
    assert _c1_closeout_blockers(True, []) == []
    assert "c2b_not_confirmed" not in _c1_closeout_blockers(True, [])


def test_holdout_clear_evidence_row_is_not_misread_as_a_heldout_image():
    source = [{"image_id": "i1", "allocation": "C2_SOURCE"}]
    holdout = [{"image_id": "i1", "future_holdout_clear": "true"}, {"image_id": "i2", "allocation": "future_holdout"}]
    assert _c2_source_images(source) == {"i1"}
    assert _future_heldout_images(holdout) == {"i2"}


def test_raw_snapshot_metadata_does_not_change_source_assignment_identity():
    source = [{"path": "D:/inputs/manual.csv", "size": 12, "sha256": "a" * 64}]
    snapshot = [{**source[0], "input_role": "manual_assignment", "snapshot_path": "D:/snapshot/manual.csv", "snapshot_sha256": "a" * 64}]
    assert _source_identity_aggregate(snapshot) == _aggregate_sha(source)
