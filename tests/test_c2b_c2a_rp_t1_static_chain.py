from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis import run_c2b_c2a_rp_chain as chain
from tools.thesis_main.analysis.materialize_t1_static_assignment import bind_t1_runtime, materialize as materialize_t1
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
            stream.write(json.dumps({"project_id": row["project_id"], "task_id": row["runtime_task_id"], "annotator_id": row["worker_id"], "annotation_id": f"ann-{row['deployment_id']}-{row['worker_id']}-{row['planned_task_id']}", "session_id": "s1", "active_seconds": 12}) + "\n")

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
    design_summary = tmp_path / "design_summary.json"
    _write_json(design_summary, {"c2b_design_ready": True, "launch_ready": True, "candidate_only": False})
    return {"assignment": assignment_path, "exports_zh": export_paths["zh"], "exports_foreign": export_paths["foreign"], "active": active_log, "deployment": manifest, "launch": launch, "mapping": mapping, "private": private_audit, "profile": profile, "c1": c1_snapshot, "roster": roster, "rule": rule, "eligibility": TASK_EVIDENCE, "reference": REFERENCE, "design": c2a_design, "threshold": threshold, "c2a_pool": c2a_pool, "design_summary": design_summary}


def test_d8_identity_is_unchanged_and_c2b_to_c2a_rehearsal_is_replaceable(monkeypatch, tmp_path: Path) -> None:
    rows = list(csv.DictReader((D8 / "assignment_manifest_C2B.csv").open(encoding="utf-8")))
    identity, tasks, workers = chain._validate_assignment_identity(D8 / "assignment_manifest_C2B.csv", rows)
    assert len(identity) == 176 and len(tasks) == 46 and len(workers) == 22
    fixture = _make_c2b_fixture(tmp_path)
    monkeypatch.setattr(chain, "_fit_crossed_model", lambda records: {"status": "estimated", "support": {"worker_id": 22, "base_task_id": 46, "building_id": 10, "risk": 20}, "worker_slopes": {worker: 0.1 for worker in workers}, "worker_slope_ses": {worker: 0.01 for worker in workers}, "group_slope_se": 0.01, "between_worker_slope_sd": 0.01})
    monkeypatch.setattr(chain, "compute_layout_mask_iou_from_normalized_pairs", lambda _pred, _ref: (0.8, {}))

    kwargs = dict(zh_export=fixture["exports_zh"], foreign_export=fixture["exports_foreign"], exports={}, active_log=fixture["active"], deployment_active_logs={}, assignment=fixture["assignment"], deployment_manifest=fixture["deployment"], launch_report=fixture["launch"], runtime_mapping=fixture["mapping"], private_assignment_audit=fixture["private"], worker_profile=fixture["profile"], design_summary=fixture["design_summary"], c1_snapshot=fixture["c1"], worker_roster=fixture["roster"], rule_config=fixture["rule"], task_eligibility=fixture["eligibility"], reference_registry=fixture["reference"], c2a_design_manifest=fixture["design"], threshold_manifest=fixture["threshold"], c2a_task_pool=fixture["c2a_pool"], input_status="precloseout_rehearsal")
    first = chain.run_chain(output_dir=tmp_path / "chain_1", **kwargs)
    assert first["formal_ready"] is False
    assert first["assignment_count"] == 176 and first["task_count"] == 46 and first["worker_count"] == 22
    assert first["risk_slope_summary"]["n_estimand_eligible"] == 176
    bound = json.loads((tmp_path / "chain_1" / "c2a_decision_manifest_bound.json").read_text(encoding="utf-8"))
    assert bound["source_manifest_sha256"] == _sha(fixture["design"])
    assert bound["binding_map"]["worker_profile_csv"]["target_sha256"] == _sha(tmp_path / "chain_1" / "post_c2b_worker_profile.csv")
    assert first["c2a_operational_package"]["assignment_count"] > 0
    assert first["task_pool_sha256"] == "211ea4260415918104685440b07ce72fc17113b1764913c9215c554df901c067"
    assert first["c2a_operational_package"]["append_only"]["block_index"] == 1
    assert (tmp_path / "chain_1" / "c2a_rp_operational" / "imports" / "c2a_rp_block_1_zh.json").is_file()
    import_payload = json.loads((tmp_path / "chain_1" / "c2a_rp_operational" / "imports" / "c2a_rp_block_1_zh.json").read_text(encoding="utf-8"))
    assert import_payload[0]["data"]["method_contract_sha256"] == _sha(METHOD_CONTRACT)
    assert import_payload[0]["data"]["c2a_block_assignment_sha256"] == _sha(tmp_path / "chain_1" / "assignment_manifest_C2A_RP_block_1.csv")
    assert import_payload[0]["data"]["vis_3d"]

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
