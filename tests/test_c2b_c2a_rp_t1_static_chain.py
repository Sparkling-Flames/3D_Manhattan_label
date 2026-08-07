from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis import run_c2b_c2a_rp_chain as chain
from tools.thesis_main.analysis.materialize_t1_static_assignment import (
    _load_task_pool,
    _t1_image_ids_sha,
    _t1_pool_identity_sha,
    bind_t1_runtime,
    materialize as materialize_t1,
)
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


ROOT = Path(__file__).resolve().parents[1]
D8 = ROOT / "analysis_results" / "c2b_build_20260802_v17_d8"
REFERENCE = ROOT / "analysis_results" / "c2b_validation_static_20260802_v16" / "inputs" / "reference_registry.csv"
TASK_EVIDENCE = D8 / "compact_audit_bundle" / "c2b_task_eligibility_evidence.csv"


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return sha256_file(path)


def _make_t1_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    workers = ["w1", "w2", "w3", "w4"]
    roster = tmp_path / "t1_roster.csv"
    _write_csv(roster, [{"worker_id": worker, "assignment_eligible": "true"} for worker in workers])
    deployment = tmp_path / "deployment.json"
    _write_json(deployment, {
        "schema_version": "c2b_worker_deployment_manifest_v1",
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": _sha(METHOD_CONTRACT),
        "deployments": [
            {"deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "http-1", "server_url": "http://example/", "project_id": "p-zh", "worker_ids": workers[:2]},
            {"deployment_id": "foreign", "language_group": "English", "server_instance_id": "https-1", "server_url": "https://example/", "project_id": "p-en", "worker_ids": workers[2:]},
        ],
    })
    pool = tmp_path / "t1_task_pool.csv"
    pool_rows = []
    for i in range(8):
        image = f"https://img/{i}.png"
        prediction = [{"model_version": "mock-layout-v1", "result": [{"from_name": "layout", "type": "keypointlabels", "value": {"x": 1, "y": 2}}]}]
        model_sha = hashlib.sha256(json.dumps(prediction, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        pool_rows.append({
            "image_id": f"image-{i}", "task_id": f"task-{i}", "building_id": f"building-{i % 2}",
            "risk_assist": "ordinary" if i % 2 == 0 else "stress_assist", "image": image,
            "image_sha256": hashlib.sha256(image.encode("utf-8")).hexdigest(), "vis_3d": image,
            "model_layout": json.dumps(prediction, ensure_ascii=False, separators=(",", ":")), "model_layout_sha256": model_sha,
        })
    _write_csv(pool, pool_rows)
    sap = tmp_path / "sap.json"
    _write_json(sap, {"t1_randomization": {"workload_cap": 8, "max_mode_imbalance": 1, "max_risk_imbalance": 1, "profile_version": "p1", "cohort_id": "c1"}})
    return pool, roster, deployment, sap


def test_t1_static_assignment_enforces_2x2_isolation_and_records_randomization(tmp_path: Path) -> None:
    pool, roster, deployment, sap = _make_t1_inputs(tmp_path)
    output = tmp_path / "t1_out"
    result = materialize_t1(pool, roster, deployment, sap, output, seed=20260803)

    assert result["formal_ready"] is False
    assert result["mock_provenance"] is True
    rows = list(csv.DictReader((output / "assignment_manifest_T1.csv").open(encoding="utf-8")))
    assert len(rows) == 32
    for image_id in {row["image_id"] for row in rows}:
        members = [row for row in rows if row["image_id"] == image_id]
        assert len(members) == 4
        assert {row["condition"] for row in members} == {"Manual", "Semi"}
        assert len({row["worker_id"] for row in members}) == 4
    assert len({(row["worker_id"], row["image_id"]) for row in rows}) == len(rows)
    randomization = list(csv.DictReader((output / "t1_randomization_plan.csv").open(encoding="utf-8")))
    assert len(randomization) == len(rows)
    assert all(row["candidate_set_at_decision"] and float(row["assignment_probability"]) > 0 for row in randomization)
    assert {item["task_count"] for item in result["deployments"].values()} == {16}
    assert len(result["private_lists"]) == 4
    import_payload = json.loads((output / "imports" / "t1_import_zh.json").read_text(encoding="utf-8"))
    assert import_payload[0]["data"]["assignment_sha256"] == result["assignment_sha256"]
    assert import_payload[0]["data"]["method_contract_sha256"] == _sha(METHOD_CONTRACT)
    all_imports = []
    for item in result["deployments"].values():
        all_imports.extend(json.loads(Path(item["planned_import_path"]).read_text(encoding="utf-8")))
    assert {item["data"]["condition"] for item in all_imports} == {"Manual", "Semi"}
    assert all("predictions" not in item for item in all_imports if item["data"]["condition"] == "Manual")
    assert all(item.get("predictions") for item in all_imports if item["data"]["condition"] == "Semi")
    assert all(item["data"]["image"] and item["data"]["image_sha256"] for item in all_imports)
    assert set(item["payload"]["artifact_role"] for item in result["artifacts"].values()) == {
        "T1_ROSTER_FROZEN", "T1_TASK_POOL_FROZEN", "T1_RANDOMIZATION_PLAN_FROZEN", "T1_SAP_FROZEN"
    }
    assert all(item["payload"]["frozen"] is False for item in result["artifacts"].values())

    with pytest.raises(ValueError, match="stage3_state_json"):
        materialize_t1(pool, roster, deployment, sap, tmp_path / "formal_without_gate", seed=20260803, mode="formal")


def test_formal_t1_pool_rejects_test_candidate_and_accepts_clear_validation_remainder(tmp_path: Path) -> None:
    pool, _roster, _deployment, _sap = _make_t1_inputs(tmp_path)
    with pytest.raises(ValueError, match="source_split=validation"):
        _load_task_pool(pool, formal=True)
    rows = list(csv.DictReader(pool.open(encoding="utf-8")))
    exposure_audit = tmp_path / "exposure_audit.json"
    exposure_audit.write_text(json.dumps({
        "schema_version": "stage3_exposure_audit_v1", "status": "clear",
        "source_validation_inventory_sha256": "a" * 64,
        "t1_candidate_pool_sha256": _t1_pool_identity_sha(rows),
        "audited_image_count": len(rows), "audited_image_ids_sha256": _t1_image_ids_sha(rows),
        "P1_manifest_sha256": "b" * 64, "C1_manifest_sha256": "c" * 64,
        "C2B_assignment_sha256": "d" * 64, "C2A_RP_assignment_sha256": "e" * 64,
        "overlap_count": 0,
    }), encoding="utf-8")
    exposure_sha = _sha(exposure_audit)
    for row in rows:
        row.update({
            "source_split": "validation", "pool_role": "t1_validation_remainder", "candidate_only": "false",
            "exposure_audit_path": str(exposure_audit), "exposure_audit_sha256": exposure_sha,
            "P1_exposed": "false", "C1_exposed": "false",
            "C2B_exposed": "false", "C2A_RP_exposed": "false", "T1_exposed": "false",
        })
    valid_pool = tmp_path / "validation_remainder.csv"
    _write_csv(valid_pool, rows)
    assert len(_load_task_pool(valid_pool, formal=True)) == len(rows)
    dummy_audit = tmp_path / "dummy_exposure_audit.json"
    dummy_audit.write_text(json.dumps({"schema_version": "stage3_exposure_audit_v1", "status": "clear"}), encoding="utf-8")
    dummy_rows = [dict(row) for row in rows]
    dummy_sha = _sha(dummy_audit)
    for row in dummy_rows:
        row.update({"exposure_audit_path": str(dummy_audit), "exposure_audit_sha256": dummy_sha})
    dummy_pool = tmp_path / "dummy_audit_pool.csv"
    _write_csv(dummy_pool, dummy_rows)
    with pytest.raises(ValueError, match="requires valid source_validation_inventory_sha256"):
        _load_task_pool(dummy_pool, formal=True)
    rows[0]["candidate_only"] = "true"
    candidate_pool = tmp_path / "candidate_pool.csv"
    _write_csv(candidate_pool, rows)
    with pytest.raises(ValueError, match="candidate_only"):
        _load_task_pool(candidate_pool, formal=True)
    rows[0]["candidate_only"] = "false"
    rows[0]["exposure_audit_sha256"] = "a" * 64
    stale_pool = tmp_path / "stale_audit.csv"
    _write_csv(stale_pool, rows)
    with pytest.raises(ValueError, match="SHA is stale"):
        _load_task_pool(stale_pool, formal=True)


def test_t1_runtime_binding_uses_deployment_identity_and_private_lists(tmp_path: Path) -> None:
    pool, roster, deployment, sap = _make_t1_inputs(tmp_path)
    output = tmp_path / "t1_out"
    result = materialize_t1(pool, roster, deployment, sap, output, seed=20260803)
    planned: dict[str, Path] = {}
    runtime: dict[str, Path] = {}
    for deployment_id in result["deployments"]:
        planned_path = output / "imports" / f"t1_import_{deployment_id}.json"
        planned[deployment_id] = planned_path
        payload = json.loads(planned_path.read_text(encoding="utf-8"))
        for index, item in enumerate(payload, start=1):
            item["id"] = f"runtime-{deployment_id}-{index}"
            item["project"] = item["data"]["project_id"]
        runtime_path = tmp_path / f"runtime_{deployment_id}.json"
        _write_json(runtime_path, payload)
        runtime[deployment_id] = runtime_path
    evidence = bind_t1_runtime(
        output / "assignment_manifest_T1.csv", deployment, planned, runtime,
        tmp_path / "runtime_evidence", private_lists_dir=output / "private_lists",
    )
    assert evidence["formal_ready"] is True
    assert evidence["worker_task_binding_count"] == 32
    assert len(list(csv.DictReader((tmp_path / "runtime_evidence" / "t1_runtime_mapping_bound.csv").open(encoding="utf-8")))) == 32


def _make_c2b_fixture(tmp_path: Path) -> dict[str, Path]:
    assignment_path = D8 / "assignment_manifest_C2B.csv"
    assignments = list(csv.DictReader(assignment_path.open(encoding="utf-8")))
    task_rows = {row["task_id"]: row for row in assignments}
    reference_rows = {row["base_task_id"]: row for row in csv.DictReader(REFERENCE.open(encoding="utf-8"))}
    workers = sorted({row["worker_id"] for row in assignments})
    deployments = {"zh": workers[: len(workers) // 2], "foreign": workers[len(workers) // 2 :]}
    project_by_deployment = {"zh": "p-c2b-zh", "foreign": "p-c2b-en"}
    server_by_deployment = {"zh": ("http-c2b", "http://c2b-zh/"), "foreign": ("https-c2b", "https://c2b-en/")}

    export_paths: dict[str, Path] = {}
    mapping_rows: list[dict[str, str]] = []
    for deployment_id, deployment_workers in deployments.items():
        project = project_by_deployment[deployment_id]
        tasks = []
        for task_id, assignment in sorted(task_rows.items()):
            reference = reference_rows[assignment["base_task_id"]]
            points = [[float(value) for value in line.split()] for line in Path(reference["reference_path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
            # Rehearsal geometry is synthetic worker output.  Keep each
            # consecutive pair ordered but separate repeated event x-values;
            # duplicate-x public GT is covered by its own reference contract.
            result = []
            for point_index, point in enumerate(points):
                pair_index = point_index // 2
                x = (point[0] + pair_index * 1.25) % 1024
                result.append({"from_name": "layout", "type": "keypointlabels", "value": {"x": x * 100 / 1024, "y": point[1] * 100 / 512}})
            annotations = []
            for row in assignments:
                if row["task_id"] != task_id or row["worker_id"] not in deployment_workers:
                    continue
                annotation_id = f"ann-{deployment_id}-{row['worker_id']}-{task_id}"
                annotations.append({"id": annotation_id, "completed_by": {"id": row["worker_id"]}, "lead_time": 12, "result": result})
                mapping_rows.append({
                    "deployment_id": deployment_id, "project_id": project, "runtime_task_id": f"rt-{task_id}",
                    "planned_task_id": task_id, "worker_id": row["worker_id"], "language_group": "Chinese" if deployment_id == "zh" else "English",
                    "server_instance_id": server_by_deployment[deployment_id][0],
                })
            tasks.append({"id": f"rt-{task_id}", "project": project, "data": {"planned_task_id": task_id, "base_task_id": assignment["base_task_id"], "vis_3d": assignment["image_path"]}, "annotations": annotations})
        export_path = tmp_path / f"export_{deployment_id}.json"
        _write_json(export_path, tasks)
        export_paths[deployment_id] = export_path

    active_log = tmp_path / "active_logs"
    active_log.mkdir()
    with (active_log / "active_times_c2b.jsonl").open("w", encoding="utf-8") as stream:
        for row in mapping_rows:
            stream.write(json.dumps({
                "project_id": row["project_id"], "task_id": row["runtime_task_id"], "annotator_id": row["worker_id"],
                "annotation_id": f"ann-{row['deployment_id']}-{row['worker_id']}-{row['planned_task_id']}", "session_id": "s1", "active_seconds": 12,
                "script_version": chain.C2PLUS_ACTIVE_TIME_SCRIPT_VERSION,
                "active_time_schema_version": chain.C2PLUS_ACTIVE_TIME_SCHEMA_VERSION,
                "active_time_identity_level": chain.C2PLUS_ACTIVE_TIME_IDENTITY_LEVEL,
            }) + "\n")

    manifest = tmp_path / "deployment.json"
    _write_json(manifest, {
        "schema_version": "c2b_worker_deployment_manifest_v1", "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT),
        "assignment_batch_id": "C2B_BATCH_A", "assignment_sha256": _sha(assignment_path), "deployments": [
            {"deployment_id": "zh", "language_group": "Chinese", "server_instance_id": server_by_deployment["zh"][0], "server_url": server_by_deployment["zh"][1], "project_id": project_by_deployment["zh"], "worker_ids": deployments["zh"]},
            {"deployment_id": "foreign", "language_group": "English", "server_instance_id": server_by_deployment["foreign"][0], "server_url": server_by_deployment["foreign"][1], "project_id": project_by_deployment["foreign"], "worker_ids": deployments["foreign"]},
        ],
    })
    launch_deployments = []
    for deployment_id, deployment_workers in deployments.items():
        project = project_by_deployment[deployment_id]
        server, server_url = server_by_deployment[deployment_id]
        planned = tmp_path / f"planned_{deployment_id}.json"
        payload = [{"data": {"planned_task_id": task_id, "deployment_id": deployment_id, "language_group": "Chinese" if deployment_id == "zh" else "English", "server_instance_id": server, "server_url": server_url, "project_id": project, "c2b_batch_id": "C2B_BATCH_A"}} for task_id in sorted(task_rows)]
        _write_json(planned, payload)
        launch_deployments.append({"deployment_id": deployment_id, "language_group": "Chinese" if deployment_id == "zh" else "English", "server_instance_id": server, "server_url": server_url, "project_id": project, "planned_import_path": str(planned), "planned_import_sha256": _sha(planned)})
    launch = tmp_path / "launch.json"
    _write_json(launch, {"schema_version": "paper_a_c2b_launch_ready_report_v4", "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT), "assignment_sha256": _sha(assignment_path), "deployments": launch_deployments, "C2B_LAUNCH_READY": True})
    mapping = tmp_path / "runtime_mapping.csv"
    _write_csv(mapping, mapping_rows)
    private_audit = tmp_path / "private_audit.json"
    _write_json(private_audit, {"schema_version": "paper_a_c2b_private_assignment_list_audit_v2", "formal_ready": True})
    roster = tmp_path / "worker_roster.csv"
    _write_csv(roster, [{"worker_id": worker} for worker in workers])
    profile = tmp_path / "worker_profile.csv"
    _write_csv(profile, [{"schema_version": "worker_profile_v2", "worker_id": worker, "profile_version": "p1", "cohort_id": "c1", "completion_status": "completed", "global_policy_eligible": "true", "Q_GT_profile_status": "estimated", "R_peer_profile_status": "estimated", "F_struct_profile_status": "estimated", "conditional_component_status": "valid", "administratively_eligible": "true", "process_eligible": "true", "independence_eligible": "true", "c2_risk_model_eligible": "true"} for worker in workers])
    c1_snapshot = tmp_path / "c1_snapshot.json"
    _write_json(c1_snapshot, {"schema_version": "paper_a_c1_batch_analysis_snapshot_v1", "status": "formal_design_eligible", "C2B_DESIGN_INPUT_FROZEN_FROM_C1_A": True})
    rule = tmp_path / "rule.json"
    _write_json(rule, {"min_common_anchor_per_worker": 1, "min_bridge_per_worker": 1, "min_task_support": 1})
    threshold = tmp_path / "threshold.json"
    _write_json(threshold, {"status": "approved", "formal_selection_allowed": True, "thresholds": {"risk_slope_ci_half_width": 0.01}, "derivation": {"formula_ids": {"risk_slope_ci_half_width": "normal_95_max_unified_slope_sd"}}})
    c2a_design = tmp_path / "c2a_design.json"
    _write_json(c2a_design, {"manifest_version": "c2_design_v1", "input_sha256": {}, "threshold_manifest_path": str(threshold), "threshold_manifest_sha256": _sha(threshold), "precision": {"target_ci_half_width": 0.01, "max_additional_blocks": 2, "max_task_support": 2}})
    c2a_pool = tmp_path / "c2a_pool.csv"
    _write_csv(c2a_pool, [{"task_id": f"o-{i}", "base_task_id": f"o-{i}", "task_stratum": "ordinary", "c2a_rp_eligible": "true", "vis_3d": f"https://img/o-{i}.png"} for i in range(22)] + [{"task_id": f"s-{i}", "base_task_id": f"s-{i}", "task_stratum": "stress", "c2a_rp_eligible": "true", "vis_3d": f"https://img/s-{i}.png"} for i in range(22)])
    model_layout = tmp_path / "model_layout"
    model_layout.mkdir()
    for task_id in [f"o-{i}" for i in range(22)] + [f"s-{i}" for i in range(22)]:
        _write_json(model_layout / f"{task_id}.json", {"layout": {"corners": [{"x": 1, "y_ceiling": 2, "y_floor": 3}]}})
    design_summary = tmp_path / "design_summary.json"
    _write_json(design_summary, {"c2b_design_ready": True, "launch_ready": True, "candidate_only": False})
    return {"assignment": assignment_path, "exports_zh": export_paths["zh"], "exports_foreign": export_paths["foreign"], "active": active_log, "deployment": manifest, "launch": launch, "mapping": mapping, "private": private_audit, "profile": profile, "c1": c1_snapshot, "roster": roster, "rule": rule, "eligibility": TASK_EVIDENCE, "reference": REFERENCE, "design": c2a_design, "threshold": threshold, "c2a_pool": c2a_pool, "model_layout": model_layout, "design_summary": design_summary}


def _make_formal_c2b_bindings(fixture: dict[str, Path], tmp_path: Path) -> None:
    assignment_sha = _sha(fixture["assignment"])
    method = load_method_contract()
    method_sha = _sha(METHOD_CONTRACT)
    selected_design_sha = "design-sha"
    manifest = json.loads(fixture["deployment"].read_text(encoding="utf-8"))
    launch = json.loads(fixture["launch"].read_text(encoding="utf-8"))
    launch_by_id = {row["deployment_id"]: row for row in launch["deployments"]}
    planned_hashes, runtime_hashes, runtime_counts, dependencies = {}, {}, {}, []
    for deployment in manifest["deployments"]:
        deployment_id = deployment["deployment_id"]
        planned_path = Path(launch_by_id[deployment_id]["planned_import_path"])
        planned = json.loads(planned_path.read_text(encoding="utf-8"))
        for item in planned:
            item["data"]["selected_design_sha"] = selected_design_sha
        _write_json(planned_path, planned)
        planned_sha = _sha(planned_path)
        runtime_path = tmp_path / f"runtime_{deployment_id}.json"
        _write_json(runtime_path, [
            {**item, "id": f"runtime-{deployment_id}-{index}", "project": item["data"]["project_id"]}
            for index, item in enumerate(planned, start=1)
        ])
        worker_registry_sha = hashlib.sha256((deployment_id + "-workers").encode()).hexdigest()
        deployment.update({
            "worker_registry_sha256": worker_registry_sha,
            "method_contract_version": method["contract_version"], "method_contract_sha256": method_sha,
            "assignment_sha256": assignment_sha, "selected_design_sha": selected_design_sha,
            "planned_import_path": str(planned_path), "planned_import_sha256": planned_sha,
        })
        launch_by_id[deployment_id].update({
            **{key: deployment[key] for key in (
                "worker_registry_sha256", "method_contract_version", "method_contract_sha256",
                "assignment_sha256", "selected_design_sha", "planned_import_path", "planned_import_sha256",
            )},
        })
        planned_hashes[deployment_id] = planned_sha
        runtime_hashes[deployment_id] = _sha(runtime_path)
        runtime_counts[deployment_id] = len(planned)
        dependencies.extend([
            {"role": f"PLANNED_IMPORT_{deployment_id}", "path": str(planned_path), "sha256": planned_sha},
            {"role": f"RUNTIME_EXPORT_{deployment_id}", "path": str(runtime_path), "sha256": _sha(runtime_path)},
        ])
    manifest.update({
        "method_contract_version": method["contract_version"], "method_contract_sha256": method_sha,
        "assignment_batch_id": "C2B_BATCH_A", "assignment_sha256": assignment_sha,
    })
    _write_json(fixture["deployment"], manifest)
    launch.update({
        "assignment_batch_id": "C2B_BATCH_A", "selected_design_sha": selected_design_sha,
        "deployment_manifest_path": str(fixture["deployment"]),
        "deployment_manifest_sha256": _sha(fixture["deployment"]),
    })
    _write_json(fixture["launch"], launch)
    mapping_csv = fixture["mapping"]
    runtime_audit = tmp_path / "runtime_audit.json"
    _write_json(runtime_audit, {
        "schema_version": "paper_a_c2b_runtime_mapping_audit_v2",
        "method_contract_version": method["contract_version"], "method_contract_sha256": method_sha,
        "formal_ready": True, "C2B_RUNTIME_BINDING_READY": True,
        "assignment_batch_id": "C2B_BATCH_A", "selected_design_sha": selected_design_sha,
        "deployment_manifest_sha256": _sha(fixture["deployment"]),
        "deployment_ids": sorted(planned_hashes), "planned_import_sha256": planned_hashes,
        "runtime_export_sha256": runtime_hashes, "runtime_mapping_path": str(mapping_csv),
        "runtime_mapping_sha256": _sha(mapping_csv), "runtime_task_count": sum(runtime_counts.values()),
        "runtime_task_count_by_deployment": runtime_counts, "worker_task_binding_count": 176,
        "dependencies": [{"role": "RUNTIME_MAPPING", "path": str(mapping_csv), "sha256": _sha(mapping_csv)}, *dependencies],
    })
    fixture["mapping"] = runtime_audit
    _write_json(fixture["private"], {
        "schema_version": "paper_a_c2b_private_assignment_list_audit_v2",
        "method_contract_version": method["contract_version"], "method_contract_sha256": method_sha,
        "formal_ready": True, "private_assignment_list_audit_passed": True,
        "assignment_batch_id": "C2B_BATCH_A", "assignment_manifest_sha256": assignment_sha,
        "worker_distribution_sha256": assignment_sha,
        "dependencies": [
            {"role": "ASSIGNMENT_MANIFEST", "path": str(fixture["assignment"]), "sha256": assignment_sha},
            {"role": "WORKER_DISTRIBUTION", "path": str(fixture["assignment"]), "sha256": assignment_sha},
        ],
    })
    profile_rows = list(csv.DictReader(fixture["profile"].open(encoding="utf-8")))
    for row in profile_rows:
        row.update({
            "enrollment_batch": "original", "Q_GT_estimable": "true", "reference_evaluable": "true",
            "peer_task_support": "5", "LOO_medoid_status": "not_evaluable", "LOO_strict_status": "not_evaluable",
            "peer_tiebreak_eligible": "true", "structural_gate_eligible": "true",
            "F_struct_raw": "0", "F_struct_EB": "0", "F_struct_interval_lower": "0", "F_struct_interval_upper": "0.1",
        })
    _write_csv(fixture["profile"], profile_rows)


def test_d8_identity_is_unchanged_and_c2b_to_c2a_rehearsal_is_replaceable(monkeypatch, tmp_path: Path) -> None:
    rows = list(csv.DictReader((D8 / "assignment_manifest_C2B.csv").open(encoding="utf-8")))
    identity, tasks, workers = chain._validate_assignment_identity(D8 / "assignment_manifest_C2B.csv", rows)
    assert len(identity) == 176 and len(tasks) == 46 and len(workers) == 22
    assert {"30", "37"} <= workers
    fixture = _make_c2b_fixture(tmp_path)
    monkeypatch.setattr(chain, "_fit_crossed_model", lambda records: {"status": "estimated", "support": {"worker_id": 22, "base_task_id": 46, "building_id": 10, "risk": 20}, "worker_slopes": {worker: 0.1 for worker in workers}, "worker_slope_ses": {worker: 0.01 for worker in workers}, "group_slope_se": 0.01, "between_worker_slope_sd": 0.01})
    monkeypatch.setattr(chain, "compute_layout_mask_iou_from_normalized_pairs", lambda _pred, _ref: (0.8, {}))

    kwargs = dict(zh_export=fixture["exports_zh"], foreign_export=fixture["exports_foreign"], exports={}, active_log=fixture["active"], deployment_active_logs={}, assignment=fixture["assignment"], deployment_manifest=fixture["deployment"], launch_report=fixture["launch"], runtime_mapping=fixture["mapping"], private_assignment_audit=fixture["private"], worker_profile=fixture["profile"], design_summary=fixture["design_summary"], c1_snapshot=fixture["c1"], worker_roster=fixture["roster"], rule_config=fixture["rule"], task_eligibility=fixture["eligibility"], reference_registry=fixture["reference"], c2a_design_manifest=fixture["design"], threshold_manifest=fixture["threshold"], c2a_task_pool=fixture["c2a_pool"], model_layout_dir=fixture["model_layout"], input_status="precloseout_rehearsal")
    first = chain.run_chain(output_dir=tmp_path / "chain_1", **kwargs)
    assert first["formal_ready"] is False
    assert first["assignment_count"] == 176 and first["task_count"] == 46 and first["worker_count"] == 22
    assert first["risk_slope_summary"]["n_estimand_eligible"] == 176
    bound = json.loads((tmp_path / "chain_1" / "c2a_decision_manifest_bound.json").read_text(encoding="utf-8"))
    assert bound["source_manifest_sha256"] == _sha(fixture["design"])
    assert bound["binding_map"]["worker_profile_csv"]["target_sha256"] == _sha(tmp_path / "chain_1" / "post_c2b_worker_profile.csv")
    assert first["c2a_operational_package"]["assignment_count"] > 0
    assert all(item["timing_status"] == "auxiliary_available" for item in first["canonical_summary"].values())
    assert first["input_sha256"]["active_log:zh"] == first["timing_provenance"]["zh"]["source_aggregate_sha256"]
    assert first["input_sha256"]["active_log:zh"]
    assert any(
        item.get("worker_provenance", {}).get("30", {}).get("current_c2plus_event_count", 0) > 0
        for item in first["timing_provenance"].values()
    )
    assert any(
        item.get("worker_provenance", {}).get("37", {}).get("current_c2plus_event_count", 0) > 0
        for item in first["timing_provenance"].values()
    )
    assert first["task_pool_sha256"] == "211ea4260415918104685440b07ce72fc17113b1764913c9215c554df901c067"
    assert first["c2a_operational_package"]["append_only"]["block_index"] == 1
    assert (tmp_path / "chain_1" / "c2a_rp_operational" / "imports" / "c2a_rp_block_1_zh.json").is_file()
    import_payload = json.loads((tmp_path / "chain_1" / "c2a_rp_operational" / "imports" / "c2a_rp_block_1_zh.json").read_text(encoding="utf-8"))
    assert import_payload[0]["data"]["method_contract_sha256"] == _sha(METHOD_CONTRACT)
    assert import_payload[0]["data"]["c2a_block_assignment_sha256"] == _sha(tmp_path / "chain_1" / "assignment_manifest_C2A_RP_block_1.csv")
    assert import_payload[0]["data"]["image"].endswith(".jpg")
    assert import_payload[0]["data"]["vis_3d"].startswith("http://c2b-zh/tools/vis_3d.html?")
    assert import_payload[0]["data"]["model_layout_sha256"]

    replacement = tmp_path / "replacement_zh.json"
    payload = json.loads(fixture["exports_zh"].read_text(encoding="utf-8"))
    payload[0]["annotations"][0]["lead_time"] = 13
    _write_json(replacement, payload)
    second = chain.run_chain(output_dir=tmp_path / "chain_2", **{**kwargs, "zh_export": replacement})
    assert second["assignment_sha256"] == first["assignment_sha256"]
    first_rows = list(csv.DictReader((tmp_path / "chain_1" / "c2b_canonical_submissions.csv").open(encoding="utf-8")))
    second_rows = list(csv.DictReader((tmp_path / "chain_2" / "c2b_canonical_submissions.csv").open(encoding="utf-8")))
    assert all(row["active_time_source"] == "log" and row["active_time"] == "12.0" for row in first_rows)
    assert {row["planned_task_id"] for row in first_rows} == {row["planned_task_id"] for row in second_rows}
    assert first_rows[0]["source_export_sha256"] != second_rows[0]["source_export_sha256"]
    assert chain._resolve_active_logs({"zh": {"language_token": "zh"}, "foreign": {"language_token": "foreign"}}, shared=None, explicit={}) == {"zh": None, "foreign": None}


def test_formal_chain_terminalizes_w027_eight_missing_and_excludes_it_from_block1(monkeypatch, tmp_path: Path) -> None:
    fixture = _make_c2b_fixture(tmp_path)
    _make_formal_c2b_bindings(fixture, tmp_path)
    for key in ("exports_zh", "exports_foreign"):
        payload = json.loads(fixture[key].read_text(encoding="utf-8"))
        for task in payload:
            task["annotations"] = [
                annotation for annotation in task["annotations"]
                if str(annotation.get("completed_by", {}).get("id")) != "27"
            ]
        _write_json(fixture[key], payload)
    disposition = tmp_path / "terminal_disposition.csv"
    _write_csv(disposition, [{
        "worker_id": "27", "task_id": "", "terminal_status": "closed_partial_insufficient",
        "missing_reason": "lost_to_followup_after_C1_before_C2B_completion",
    }])
    review = tmp_path / "reference_review.csv"
    _write_csv(review, [{
        "schema_version": "paper_a_reference_conflict_review_record_v2",
        "base_task_id": "VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d",
        "registry_status_before_review": "approved_by_frozen_reference_policy",
        "reference_status_before_review": "use_existing_public_gt_as_is",
        "reference_normalizer_status_before_review": "passed", "geometry_reference_ready_before_review": "true",
        "review_status": "closed", "review_disposition": "retain_original",
        "reviewer_blinding": "worker_and_analysis_metric_blinded", "review_evidence": "synthetic_test_fixture",
        "reviewed_by": "test-reviewer", "reviewed_at": "2026-08-06T12:00:00Z",
        "original_reference_sha256": "a" * 64, "method_contract_sha256": _sha(METHOD_CONTRACT),
    }])
    workers = {row["worker_id"] for row in csv.DictReader(fixture["profile"].open(encoding="utf-8"))}
    active_workers = workers - {"27"}
    monkeypatch.setattr(chain, "_fit_crossed_model", lambda records: {
        "status": "estimated", "support": {"worker_id": 21, "base_task_id": 46, "building_id": 10, "risk": 20},
        "worker_slopes": {worker: 0.1 for worker in active_workers},
        "worker_slope_ses": {worker: 0.01 for worker in active_workers},
        "group_slope_se": 0.01, "between_worker_slope_sd": 0.01,
    })
    monkeypatch.setattr(chain, "compute_layout_mask_iou_from_normalized_pairs", lambda _pred, _ref: (0.8, {}))

    result = chain.run_chain(
        zh_export=fixture["exports_zh"], foreign_export=fixture["exports_foreign"], exports={},
        active_log=fixture["active"], deployment_active_logs={}, assignment=fixture["assignment"],
        deployment_manifest=fixture["deployment"], launch_report=fixture["launch"], runtime_mapping=fixture["mapping"],
        private_assignment_audit=fixture["private"], worker_profile=fixture["profile"], design_summary=fixture["design_summary"],
        c1_snapshot=fixture["c1"], worker_roster=fixture["roster"], rule_config=fixture["rule"],
        task_eligibility=fixture["eligibility"], reference_registry=fixture["reference"],
        c2a_design_manifest=fixture["design"], threshold_manifest=fixture["threshold"], c2a_task_pool=fixture["c2a_pool"],
        output_dir=tmp_path / "formal_chain", input_status="formal", terminal_disposition=disposition,
        reference_conflict_review_record=review,
    )

    closeout = json.loads((tmp_path / "formal_chain" / "c2b_closeout_v2.json").read_text(encoding="utf-8"))
    plan = {row["worker_id"]: row for row in csv.DictReader((tmp_path / "formal_chain" / "c2a_rp" / "precision_plan_C2A_RP.csv").open(encoding="utf-8"))}
    block1 = list(csv.DictReader((tmp_path / "formal_chain" / "assignment_manifest_C2A_RP_block_1.csv").open(encoding="utf-8")))
    operational = tmp_path / "formal_chain" / "c2a_rp_operational"
    import_paths = list((operational / "imports").glob("*.json"))
    runtime_rows = list(csv.DictReader((operational / "c2a_rp_runtime_mapping.csv").open(encoding="utf-8")))
    w027_private = list(csv.DictReader((operational / "private_lists" / "worker_27_C2A_RP_block_1.csv").open(encoding="utf-8")))
    assert result["formal_ready"] is True
    assert (closeout["assigned_count"], closeout["submitted_count"], closeout["missing_count"]) == (176, 168, 8)
    assert len(plan) == 22 and plan["27"]["terminal_state"] == "not_evaluable" and plan["27"]["additional_blocks"] == "0"
    assert all(row["worker_id"] != "27" for row in block1)
    assert len(import_paths) == 2 and all(json.loads(path.read_text(encoding="utf-8")) for path in import_paths)
    assert all(row["worker_id"] != "27" for row in runtime_rows)
    assert w027_private == []


def test_c2_active_time_provenance_is_auxiliary_and_mixed_legacy_does_not_block(tmp_path: Path) -> None:
    log = tmp_path / "active_times_c2plus.jsonl"
    current = {
        "annotator_id": "W030",
        "script_version": chain.C2PLUS_ACTIVE_TIME_SCRIPT_VERSION,
        "active_time_schema_version": chain.C2PLUS_ACTIVE_TIME_SCHEMA_VERSION,
        "active_time_identity_level": chain.C2PLUS_ACTIVE_TIME_IDENTITY_LEVEL,
    }
    current_37 = {**current, "annotator_id": "37"}
    log.write_text(json.dumps(current) + "\n" + json.dumps(current_37) + "\n", encoding="utf-8")
    available = chain._active_time_provenance(log)
    assert available["status"] == "auxiliary_available"
    assert available["raw_event_count"] == 2
    assert available["worker_provenance"]["30"]["status"] == "auxiliary_available"
    assert available["worker_provenance"]["37"]["status"] == "auxiliary_available"

    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"annotator_id": "37", "script_version": "stage1_legacy"}) + "\n")
    mixed = chain._active_time_provenance(log)
    assert mixed["status"] == "auxiliary_mixed_or_legacy"
    assert mixed["observed"]["active_time_schema_version"]["<missing>"] == 1
    assert mixed["worker_provenance"]["30"]["status"] == "auxiliary_available"
    assert mixed["worker_provenance"]["37"]["status"] == "auxiliary_mixed_or_legacy"
    assert mixed["source_aggregate_sha256"] != available["source_aggregate_sha256"]
    assert chain._active_time_provenance(None)["status"] == "not_evaluable"


def test_c2_active_time_provenance_scopes_to_frozen_worker_task_contexts(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    current = {
        "project_id": "76", "task_id": "3406", "annotator_id": "30",
        "script_version": chain.C2PLUS_ACTIVE_TIME_SCRIPT_VERSION,
        "active_time_schema_version": chain.C2PLUS_ACTIVE_TIME_SCHEMA_VERSION,
        "active_time_identity_level": chain.C2PLUS_ACTIVE_TIME_IDENTITY_LEVEL,
    }
    rows = [
        current,
        {**current, "project_id": "66", "script_version": "legacy", "active_time_schema_version": "", "active_time_identity_level": ""},
        {**current, "task_id": "3407"},
        {**current, "annotator_id": "99"},
    ]
    log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    result = chain._active_time_provenance(log, eligible_contexts={("76", "3406", "30")})

    assert result["status"] == "auxiliary_available"
    assert result["raw_event_count"] == 1
    assert result["forensic_excluded_event_count"] == 3
    assert result["forensic_excluded_reasons"] == {
        "unexpected_project": 1,
        "unexpected_worker": 1,
        "unassigned_worker_task": 1,
    }


def test_post_profile_zero_support_worker_is_not_marked_estimated(monkeypatch, tmp_path: Path) -> None:
    profile = tmp_path / "profile.csv"
    _write_csv(profile, [
        {"schema_version": "worker_profile_v2", "worker_id": "1", "global_policy_eligible": "true"},
        {"schema_version": "worker_profile_v2", "worker_id": "27", "global_policy_eligible": "true"},
    ])
    evidence = [{
        "worker_id": "1", "base_task_id": "t1", "building_id": "b1", "risk": 1,
        "quality": 0.8, "task_stratum": "stress", "risk_slope_estimand_eligible": True,
    }]
    monkeypatch.setattr(chain, "_fit_crossed_model", lambda _records: {
        "status": "estimated", "worker_slopes": {"1": 0.2}, "worker_slope_ses": {"1": 0.05},
        "group_slope_se": 0.04, "between_worker_slope_sd": 0.03,
    })

    _fit, rows = chain._merge_post_profile(profile, evidence, output_path=tmp_path / "post.csv")
    by_worker = {row["worker_id"]: row for row in rows}

    assert by_worker["1"]["risk_slope_status"] == "estimated_crossed_model"
    assert by_worker["27"]["risk_slope_status"] == "not_evaluable"
    assert by_worker["27"]["risk_slope_support"] == 0
    assert by_worker["27"]["risk_slope"] == ""
    assert by_worker["27"]["risk_slope_se"] == ""
    assert by_worker["27"]["risk_slope_ci_half_width"] == ""


def test_observed_support_audit_separates_planned_submitted_valid_and_estimand_support() -> None:
    assignments = [
        {"worker_id": "1", "task_id": "t1", "base_task_id": "b1", "c2_component": "common_anchor", "task_stratum": "ordinary"},
        {"worker_id": "2", "task_id": "t1", "base_task_id": "b1", "c2_component": "common_anchor", "task_stratum": "ordinary"},
        {"worker_id": "1", "task_id": "t2", "base_task_id": "b2", "c2_component": "diverse_bridge", "task_stratum": "stress"},
    ]
    canonical = [
        {"worker_id": "1", "planned_task_id": "t1", "canonical_valid": "true"},
        {"worker_id": "2", "planned_task_id": "t1", "canonical_valid": "false"},
    ]
    evidence = [
        {"worker_id": "1", "planned_task_id": "t1", "risk_slope_estimand_eligible": True},
        {"worker_id": "2", "planned_task_id": "t1", "risk_slope_estimand_eligible": False},
    ]

    rows, summary = chain._build_observed_support_audit(assignments, canonical, evidence)
    by_task = {row["task_id"]: row for row in rows}

    assert by_task["t1"]["planned_worker_support"] == 2
    assert by_task["t1"]["submitted_worker_support"] == 2
    assert by_task["t1"]["canonical_valid_support"] == 1
    assert by_task["t1"]["peer_support_status"] == "support_limited"
    assert by_task["t1"]["risk_slope_eligible_support"] == 1
    assert by_task["t2"]["missing_worker_ids"] == "1"
    assert by_task["t2"]["support_deficit"] == 1
    assert summary["zero_submitted_support_task_count"] == 1


def test_risk_evidence_excludes_oos_before_reference_scoring(tmp_path: Path) -> None:
    canonical = [{
        "planned_task_id": "task-oos", "base_task_id": "task-oos", "worker_id": "1",
        "canonical_annotation_id": "a1", "canonical_valid": "true", "ordered_geometry": "not-json",
    }]
    task = {"task-oos": {"building_id": "b1", "risk_design_score_A": "2", "risk_design_stratum": "stress"}}
    reference = {"task-oos": {"geometry_reference_ready": "false"}}
    rows, summary = chain._risk_slope_evidence(
        canonical, task, reference, reference_registry=tmp_path / "reference.csv",
        scope_index={"task-oos": {"final_scope": "oos"}},
    )

    assert summary["n_estimand_eligible"] == 0
    assert rows[0]["eligibility_status"] == "not_evaluable"
    assert rows[0]["ineligibility_reason"] == "scope_oos"


def test_runtime_mapping_namespaces_planned_tasks_but_rejects_internal_and_cross_server_collisions(tmp_path: Path) -> None:
    fields = ["deployment_id", "project_id", "runtime_task_id", "planned_task_id", "worker_id", "server_instance_id"]
    allowed = tmp_path / "allowed.csv"
    _write_csv(allowed, [
        {**dict(zip(fields, ["zh", "p-zh", "rt-1", "planned-1", "w-zh", "http-1"]))},
        {**dict(zip(fields, ["foreign", "p-en", "rt-1", "planned-1", "w-en", "https-1"]))},
    ])
    assert len(chain._load_runtime_mapping(allowed)) == 2

    duplicate_worker_task = tmp_path / "duplicate_worker_task.csv"
    _write_csv(duplicate_worker_task, [
        {**dict(zip(fields, ["zh", "p-zh", "rt-1", "planned-1", "w-zh", "http-1"]))},
        {**dict(zip(fields, ["zh", "p-zh", "rt-2", "planned-1", "w-zh", "http-1"]))},
    ])
    with pytest.raises(ValueError, match="duplicate identity"):
        chain._load_runtime_mapping(duplicate_worker_task)

    cross_server = tmp_path / "cross_server.csv"
    _write_csv(cross_server, [
        {**dict(zip(fields, ["zh", "same-project", "same-runtime", "planned-1", "w-zh", "http-1"]))},
        {**dict(zip(fields, ["foreign", "same-project", "same-runtime", "planned-1", "w-en", "https-1"]))},
    ])
    with pytest.raises(ValueError, match="cross-server"):
        chain._load_runtime_mapping(cross_server)
