"""Materialize the static T1 assignment and CE-only operator package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.analysis.worker_identity import normalize_worker_id
from tools.thesis_main.analysis.run_c2b_c2a_rp_chain import _load_deployments, _parse_bindings, _write_csv, _write_json


SCHEMA = "paper_a_t1_static_assignment_v1"
SLOTS = (("Manual", 1), ("Manual", 2), ("Semi", 1), ("Semi", 2))


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truth(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "approved", "eligible"}


def _sha(path: Path) -> str:
    return sha256_file(path)


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _valid_sha(value: Any) -> bool:
    text = _text(value).lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


_T1_EXPOSURE_AUDIT_SHA_FIELDS = (
    "source_validation_inventory_sha256", "t1_candidate_pool_sha256", "audited_image_ids_sha256",
    "P1_manifest_sha256", "C1_manifest_sha256", "C2B_assignment_sha256", "C2A_RP_assignment_sha256",
)


def _t1_pool_identity_sha(rows: list[dict[str, str]]) -> str:
    records = []
    for row in rows:
        records.append({
            "image_id": _text(row.get("image_id")),
            "task_id": _text(row.get("task_id")),
            "building_id": _text(row.get("building_id")),
            "risk_assist": _text(row.get("risk_assist")),
            "image": _text(row.get("image") or row.get("image_path") or row.get("image_url")),
            "image_sha256": _text(row.get("image_sha256")).lower(),
            "vis_3d": _text(row.get("vis_3d")),
            "model_layout_sha256": _text(row.get("model_layout_sha256")).lower(),
            "model_layout_source_sha256": _text(row.get("model_layout_source_sha256")).lower(),
        })
    records.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return _canonical_sha(records)


def _t1_image_ids_sha(rows: list[dict[str, str]]) -> str:
    return _canonical_sha(sorted({_text(row.get("image_id")) for row in rows}))


def _model_payload(row: dict[str, str], pool_path: Path) -> tuple[list[dict[str, Any]], str, str]:
    source_path_value = _text(row.get("model_layout_path") or row.get("model_layout_source_path") or row.get("preannotation_source_path"))
    source_sha = ""
    raw_sha = ""
    if source_path_value:
        source_path = Path(source_path_value)
        if not source_path.is_absolute():
            source_path = (pool_path.parent / source_path).resolve()
        if not source_path.is_file():
            raise ValueError(f"T1 model/preannotation source is missing:{source_path}")
        value = json.loads(source_path.read_text(encoding="utf-8"))
        source_sha = _sha(source_path)
    else:
        raw = row.get("model_layout") or row.get("preannotation") or row.get("predictions")
        if raw in {None, ""}:
            raise ValueError("T1 task pool requires frozen Semi preannotation")
        if isinstance(raw, str):
            raw_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        value = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(value, dict) and isinstance(value.get("predictions"), list):
        value = value["predictions"]
    elif isinstance(value, dict) and "result" in value:
        value = [value]
    if not isinstance(value, list) or not value or any(not isinstance(item, dict) for item in value):
        raise ValueError("T1 Semi preannotation must be a non-empty prediction list")
    payload_sha = _canonical_sha(value)
    declared_payload_sha = _text(row.get("model_layout_sha256"))
    if not _valid_sha(declared_payload_sha) or declared_payload_sha.lower() not in {payload_sha, source_sha, raw_sha}:
        raise ValueError("T1 task pool model_layout_sha256 is missing or stale")
    declared_source_sha = _text(row.get("model_layout_source_sha256"))
    if declared_source_sha:
        if not _valid_sha(declared_source_sha):
            raise ValueError("T1 task pool model_layout_source_sha256 is invalid")
        if not source_sha:
            source_sha = raw_sha or payload_sha
        if declared_source_sha.lower() != source_sha:
            raise ValueError("T1 task pool model_layout_source_sha256 is stale")
    return value, payload_sha, source_sha or payload_sha


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _method_identity() -> dict[str, str]:
    method = load_method_contract()
    return {"method_contract_version": str(method["contract_version"]), "method_contract_sha256": _sha(METHOD_CONTRACT)}


def _load_sap(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = payload.get("t1_randomization", payload)
    if not isinstance(config, dict):
        raise ValueError("T1 SAP randomization configuration must be an object")
    cap = config.get("workload_cap", config.get("max_workload_per_worker"))
    if cap in {None, ""}:
        raise ValueError("T1 SAP must declare workload_cap")
    try:
        cap = int(cap)
    except (TypeError, ValueError) as exc:
        raise ValueError("T1 SAP workload_cap must be an integer") from exc
    if cap <= 0:
        raise ValueError("T1 SAP workload_cap must be positive")
    mode_imbalance = int(config.get("max_mode_imbalance", 1))
    risk_imbalance = int(config.get("max_risk_imbalance", 1))
    if mode_imbalance < 0 or risk_imbalance < 0:
        raise ValueError("T1 SAP balance tolerances must be nonnegative")
    return {
        **config,
        "workload_cap": cap,
        "max_mode_imbalance": mode_imbalance,
        "max_risk_imbalance": risk_imbalance,
        "randomization_rule": "seeded_uniform_over_minimum_balance_candidate_set_v1",
    }


def _validate_formal_pool_provenance(rows: list[dict[str, str]], path: Path) -> None:
    required_flags = ("P1_exposed", "C1_exposed", "C2B_exposed", "C2A_RP_exposed", "T1_exposed")
    for row in rows:
        if _text(row.get("source_split")).lower() != "validation":
            raise ValueError("formal T1 task pool requires source_split=validation")
        if _text(row.get("pool_role")) != "t1_validation_remainder":
            raise ValueError("formal T1 task pool requires pool_role=t1_validation_remainder")
        candidate_only = _text(row.get("candidate_only")).lower()
        if _truth(row.get("candidate_only")):
            raise ValueError("formal T1 task pool rejects candidate_only input")
        if candidate_only not in {"false", "0", "no"}:
            raise ValueError("formal T1 task pool requires candidate_only=false")
        if any(_text(row.get(field)).lower() not in {"false", "0", "no"} for field in required_flags):
            raise ValueError(f"formal T1 task pool has non-clear exposure:{path}")
    bindings: set[tuple[str, str]] = set()
    audited: dict[Path, str] = {}
    image_ids = [_text(row.get("image_id")) for row in rows]
    if any(not image_id for image_id in image_ids):
        raise ValueError("formal T1 task pool requires image_id for exposure audit binding")
    if len(set(image_ids)) != len(image_ids):
        raise ValueError("formal T1 task pool has duplicate image_id")
    for row in rows:
        audit_path_value = _text(row.get("exposure_audit_path"))
        if not audit_path_value:
            raise ValueError("formal T1 task pool requires exposure_audit_path")
        audit_path = Path(audit_path_value)
        audit_path = audit_path.resolve() if audit_path.is_absolute() else (path.parent / audit_path).resolve()
        if not audit_path.is_file():
            raise ValueError(f"formal T1 exposure audit is missing:{audit_path}")
        declared_sha = _text(row.get("exposure_audit_sha256")).lower()
        if not _valid_sha(declared_sha):
            raise ValueError("formal T1 task pool requires exposure_audit_sha256")
        actual_sha = audited.setdefault(audit_path, _sha(audit_path))
        if declared_sha != actual_sha:
            raise ValueError(f"formal T1 exposure audit SHA is stale:{audit_path}")
        bindings.add((audit_path.as_posix(), actual_sha))
    if len(bindings) != 1:
        raise ValueError("formal T1 task pool requires one consistent exposure audit binding")
    audit_path, _audit_sha = next(iter(bindings))
    audit_file = Path(audit_path)
    try:
        audit = json.loads(audit_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"formal T1 exposure audit is not valid JSON:{audit_file}") from exc
    if not isinstance(audit, dict):
        raise ValueError("formal T1 exposure audit must be a JSON object")
    if _text(audit.get("schema_version")) != "stage3_exposure_audit_v1":
        raise ValueError("formal T1 exposure audit has unsupported schema_version")
    if _text(audit.get("status")) != "clear":
        raise ValueError("formal T1 exposure audit status must be clear")
    for field in _T1_EXPOSURE_AUDIT_SHA_FIELDS:
        if not _valid_sha(audit.get(field)):
            raise ValueError(f"formal T1 exposure audit requires valid {field}")
    try:
        audited_image_count = int(audit.get("audited_image_count"))
        overlap_count = int(audit.get("overlap_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("formal T1 exposure audit counts must be integers") from exc
    if audited_image_count != len(image_ids):
        raise ValueError("formal T1 exposure audit image count does not cover task pool")
    if audit["audited_image_ids_sha256"].lower() != _t1_image_ids_sha(rows):
        raise ValueError("formal T1 exposure audit image IDs do not cover task pool")
    if audit["t1_candidate_pool_sha256"].lower() != _t1_pool_identity_sha(rows):
        raise ValueError("formal T1 exposure audit task pool binding is stale")
    if overlap_count != 0:
        raise ValueError("formal T1 exposure audit reports overlap")


def _load_task_pool(path: Path, *, formal: bool = False) -> dict[str, dict[str, Any]]:
    rows = _read_csv(path)
    if not rows:
        raise ValueError("T1 frozen task pool is empty")
    if formal:
        _validate_formal_pool_provenance(rows, path)
    by_image: dict[str, dict[str, Any]] = {}
    for row in rows:
        image = _text(row.get("image_id"))
        risk = _text(row.get("risk_assist"))
        if not image or risk not in {"ordinary", "stress_assist"}:
            raise ValueError("T1 task pool requires image_id and risk_assist ordinary/stress_assist")
        image_ref = _text(row.get("image") or row.get("image_path") or row.get("image_url"))
        image_sha = _text(row.get("image_sha256"))
        if not image_ref or not _valid_sha(image_sha):
            raise ValueError("T1 task pool requires image and image_sha256")
        image_path = Path(image_ref)
        if not image_path.is_absolute():
            image_path = (path.parent / image_path).resolve()
        if image_path.is_file() and _sha(image_path) != image_sha.lower():
            raise ValueError(f"T1 image_sha256 is stale:{image}")
        predictions, model_sha, model_source_sha = _model_payload(row, path)
        normalized = {
            **row,
            "_image": image_ref,
            "_image_sha256": image_sha.lower(),
            "_semi_predictions": predictions,
            "_model_layout_sha256": model_sha,
            "_model_layout_source_sha256": model_source_sha,
        }
        if image in by_image and any(
            _text(by_image[image].get(field)) != _text(normalized.get(field))
            for field in ("risk_assist", "building_id", "task_id", "image_path", "vis_3d", "_image", "_image_sha256", "_model_layout_sha256", "_model_layout_source_sha256")
        ):
            raise ValueError(f"T1 task pool has conflicting rows for image:{image}")
        by_image.setdefault(image, normalized)
    return dict(sorted(by_image.items()))


def _load_roster(path: Path, deployment_manifest: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]], dict[str, str]]:
    rows = _read_csv(path)
    if not rows:
        raise ValueError("T1 roster is empty")
    normalized: list[dict[str, str]] = []
    for row in rows:
        worker = normalize_worker_id(row.get("worker_id", ""))
        if not worker or any(key in row and not _truth(row.get(key)) for key in ("assignment_eligible", "t1_eligible")):
            raise ValueError(f"T1 roster contains an ineligible or empty worker:{worker}")
        normalized.append({**row, "worker_id": worker})
    if len({row["worker_id"] for row in normalized}) != len(normalized):
        raise ValueError("T1 roster has duplicate worker_id")
    pseudo_assignment = [{"worker_id": row["worker_id"]} for row in normalized]
    deployments, worker_to_deployment = _load_deployments(deployment_manifest, pseudo_assignment)
    declared = {row["worker_id"]: _text(row.get("deployment_id")) for row in normalized if _text(row.get("deployment_id"))}
    if declared and any(declared.get(worker) != deployment for worker, deployment in worker_to_deployment.items()):
        raise ValueError("T1 roster deployment_id disagrees with deployment manifest")
    return normalized, deployments, worker_to_deployment


def _candidate_set(
    workers: list[str],
    used_for_image: set[str],
    stats: dict[str, Counter[str]],
    *,
    mode: str,
    risk: str,
    workload_cap: int,
) -> list[str]:
    feasible = [worker for worker in workers if worker not in used_for_image and stats[worker]["total"] < workload_cap]
    if not feasible:
        return []
    def balance_key(worker: str) -> tuple[int, int, int]:
        # Prioritize the count of the condition being assigned.  This keeps
        # the two-condition totals balanced even though each image is emitted
        # in the fixed Manual, Manual, Semi, Semi slot order.
        return stats[worker][mode], stats[worker][risk], stats[worker]["total"]
    best = min(balance_key(worker) for worker in feasible)
    return sorted(worker for worker in feasible if balance_key(worker) == best)


def _validate_assignment(rows: list[dict[str, Any]], workers: list[str], sap: dict[str, Any]) -> None:
    by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_worker_image: set[tuple[str, str]] = set()
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        image, worker = _text(row.get("image_id")), normalize_worker_id(row.get("worker_id", ""))
        if (worker, image) in by_worker_image:
            raise ValueError("T1 worker-image isolation failed")
        by_worker_image.add((worker, image))
        by_image[image].append(row)
        stats[worker]["total"] += 1
        stats[worker][_text(row.get("condition"))] += 1
        stats[worker][_text(row.get("risk_assist"))] += 1
    for image, members in by_image.items():
        if len(members) != 4 or Counter(_text(row.get("condition")) for row in members) != Counter({"Manual": 2, "Semi": 2}):
            raise ValueError(f"T1 image must have exactly 2 Manual + 2 Semi:{image}")
        if len({normalize_worker_id(row.get("worker_id", "")) for row in members}) != 4:
            raise ValueError(f"T1 image must use four distinct workers:{image}")
        if len({_text(row.get("risk_assist")) for row in members}) != 1:
            raise ValueError(f"T1 image has inconsistent risk_assist:{image}")
    if any(stats[worker]["total"] > int(sap["workload_cap"]) for worker in workers):
        raise ValueError("T1 workload cap failed")
    if any(abs(stats[worker]["Manual"] - stats[worker]["Semi"]) > int(sap["max_mode_imbalance"]) for worker in workers):
        raise ValueError("T1 Manual/Semi balance failed")
    if any(abs(stats[worker]["ordinary"] - stats[worker]["stress_assist"]) > int(sap["max_risk_imbalance"]) for worker in workers):
        raise ValueError("T1 ordinary/stress balance failed")


def _artifact(
    role: str,
    source: Path,
    *,
    mode: str,
    dependencies: list[dict[str, Any]],
    seed: int,
    profile_version: str,
    cohort_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "paper_a_t1_static_artifact_v1",
        "artifact_role": role,
        "contract_role": "generated_subordinate",
        **_method_identity(),
        "profile_version": profile_version,
        "cohort_id": cohort_id,
        "formal_ready": mode == "formal",
        "frozen": mode == "formal",
        "artifact_status": "frozen" if mode == "formal" else "mock_dry_run",
        "seed": seed,
        "source_path": str(source.resolve()),
        "source_sha256": _sha(source),
        "dependencies": dependencies,
        "blockers": [] if mode == "formal" else ["mock_dry_run_not_formal"],
    }


def materialize(
    task_pool_csv: Path,
    roster_csv: Path,
    deployment_manifest: Path,
    sap_json: Path,
    output_dir: Path,
    *,
    seed: int,
    mode: str = "mock_dry_run",
    stage3_state_json: Path | None = None,
    enrollment_registry_csv: Path | None = None,
) -> dict[str, Any]:
    if mode not in {"mock_dry_run", "formal"}:
        raise ValueError(f"unsupported T1 materialization mode:{mode}")
    if mode == "formal" and (stage3_state_json is None or enrollment_registry_csv is None):
        raise ValueError("formal T1 materialization requires stage3_state_json and enrollment_registry_csv")
    inputs = (task_pool_csv, roster_csv, deployment_manifest, sap_json)
    if any(not path.is_file() for path in inputs):
        raise ValueError("T1 static input is missing")
    if output_dir.exists():
        raise ValueError(f"T1 output directory already exists:{output_dir}")
    sap = _load_sap(sap_json)
    task_pool = _load_task_pool(task_pool_csv, formal=mode == "formal")
    roster, deployments, worker_to_deployment = _load_roster(roster_csv, deployment_manifest)
    workers = sorted(row["worker_id"] for row in roster)
    if len(workers) < 4:
        raise ValueError("T1 requires at least four eligible workers")
    rng = random.Random(seed)
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    assignments: list[dict[str, Any]] = []
    randomization_rows: list[dict[str, Any]] = []
    for image_id, task in task_pool.items():
        risk = _text(task.get("risk_assist"))
        used_for_image: set[str] = set()
        for slot_index, (condition, duplicate_index) in enumerate(SLOTS, start=1):
            candidates = _candidate_set(workers, used_for_image, stats, mode=condition, risk=risk, workload_cap=int(sap["workload_cap"]))
            if not candidates:
                raise ValueError(f"T1 has no feasible worker candidate:{image_id}/{condition}/{duplicate_index}")
            selected = rng.choice(candidates)
            planned = f"T1:{image_id}:{condition}:{duplicate_index}"
            used_for_image.add(selected)
            stats[selected]["total"] += 1
            stats[selected][condition] += 1
            stats[selected][risk] += 1
            probability = 1.0 / len(candidates)
            randomization_rows.append({
                "schema_version": "t1_randomization_record_v1", "image_id": image_id, "planned_task_id": planned,
                "worker_id": selected, "condition": condition, "risk_assist": risk, "slot_index": slot_index,
                "selection_seed": seed, "selection_draw_id": f"{seed}:{image_id}:{slot_index}",
                "candidate_set_at_decision": json.dumps(candidates, ensure_ascii=False, separators=(",", ":")),
                "candidate_count": len(candidates), "assignment_probability": probability,
            })
            assignments.append({
                "schema_version": SCHEMA, "round_id": "T1", "image_id": image_id,
                "task_id": _text(task.get("task_id")) or image_id, "planned_task_id": planned,
                "worker_id": selected, "deployment_id": worker_to_deployment[selected],
                "condition": condition, "risk_assist": risk, "building_id": _text(task.get("building_id")),
                "block_id": _text(task.get("block_id")) or "T1_BLOCK_1", "slot_index": slot_index,
                "selection_seed": seed, "assignment_probability": probability,
            })
    _validate_assignment(assignments, workers, sap)

    parent = output_dir.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(parent)))
    try:
        assignment_path = staging / "assignment_manifest_T1.csv"
        randomization_path = staging / "t1_randomization_plan.csv"
        _write_csv(assignment_path, assignments)
        _write_csv(randomization_path, randomization_rows)
        identity = {
            **_method_identity(),
            "assignment_sha256": _sha(assignment_path),
            "task_pool_sha256": _sha(task_pool_csv),
            "roster_sha256": _sha(roster_csv),
            "sap_sha256": _sha(sap_json),
            "deployment_manifest_sha256": _sha(deployment_manifest),
            "randomization_plan_sha256": _sha(randomization_path),
        }
        imports_dir = staging / "imports"
        private_dir = staging / "private_lists"
        imports_dir.mkdir(); private_dir.mkdir()
        by_deployment: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in assignments:
            by_deployment[row["deployment_id"]].append(row)
            by_worker[row["worker_id"]].append(row)
        import_outputs: dict[str, Any] = {}
        mapping_rows: list[dict[str, Any]] = []
        for deployment_id, deployment in deployments.items():
            payload = []
            for row in by_deployment.get(deployment_id, []):
                task = task_pool[row["image_id"]]
                data = {
                    **identity,
                    "planned_task_id": row["planned_task_id"], "task_id": row["task_id"], "image_id": row["image_id"],
                    "image": task["_image"], "image_sha256": task["_image_sha256"],
                    "model_layout_sha256": task["_model_layout_sha256"],
                    "model_layout_source_sha256": task["_model_layout_source_sha256"],
                    "vis_3d": task.get("vis_3d", task.get("image_path", task["_image"])), "round_id": "T1", "block_id": row["block_id"],
                    "condition": row["condition"], "risk_assist": row["risk_assist"], "deployment_id": deployment_id,
                    "language_group": deployment["language_group"], "server_instance_id": deployment["server_instance_id"],
                    "server_url": deployment["server_url"], "project_id": deployment["project_id"],
                    "preannotation_policy": "frozen_model_prediction" if row["condition"] == "Semi" else "manual_no_preannotation",
                }
                entry: dict[str, Any] = {"data": data}
                if row["condition"] == "Semi":
                    entry["predictions"] = json.loads(json.dumps(task["_semi_predictions"], ensure_ascii=False))
                payload.append(entry)
                mapping_rows.append({
                    **identity,
                    "round_id": "T1", "block_id": row["block_id"], "worker_id": row["worker_id"],
                    "deployment_id": deployment_id, "language_group": deployment["language_group"],
                    "server_instance_id": deployment["server_instance_id"], "server_url": deployment["server_url"],
                    "project_id": deployment["project_id"], "planned_task_id": row["planned_task_id"],
                    "runtime_task_id": "", "runtime_binding_status": "pending_manual_runtime_binding",
                    "image": task["_image"], "image_sha256": task["_image_sha256"],
                    "model_layout_sha256": task["_model_layout_sha256"], "condition": row["condition"],
                })
            import_path = imports_dir / f"t1_import_{deployment_id}.json"
            _write_json(import_path, payload)
            import_outputs[deployment_id] = {
                **{key: deployment[key] for key in ("deployment_id", "language_group", "server_instance_id", "server_url", "project_id")},
                **identity,
                "planned_import_path": str((output_dir / "imports" / import_path.name).resolve()),
                "planned_import_sha256": _sha(import_path), "task_count": len(payload),
            }
        private_outputs = {}
        for worker in workers:
            path = private_dir / f"worker_{worker}_T1.csv"
            _write_csv(path, by_worker.get(worker, []))
            private_outputs[worker] = {"path": str(path.resolve()), "sha256": _sha(path), "task_count": len(by_worker.get(worker, []))}
        mapping_path = staging / "t1_runtime_mapping.csv"
        _write_csv(mapping_path, mapping_rows)

        profile_version = _text(sap.get("profile_version")) or "t1_mock_profile"
        cohort_id = _text(sap.get("cohort_id")) or "t1_mock_cohort"
        deps = [{"role": "METHOD_CONTRACT", "path": str(METHOD_CONTRACT.resolve()), "sha256": _sha(METHOD_CONTRACT)}]
        artifacts = {}
        artifact_sources = {
            "T1_ROSTER_FROZEN": roster_csv,
            "T1_TASK_POOL_FROZEN": task_pool_csv,
            "T1_RANDOMIZATION_PLAN_FROZEN": randomization_path,
            "T1_SAP_FROZEN": sap_json,
        }
        for role, source in artifact_sources.items():
            payload = _artifact(role, source, mode="formal" if mode == "formal" else "mock_dry_run", dependencies=deps, seed=seed, profile_version=profile_version, cohort_id=cohort_id)
            if role == "T1_RANDOMIZATION_PLAN_FROZEN":
                payload["source_path"] = str((output_dir / randomization_path.name).resolve())
                payload["source_sha256"] = _sha(randomization_path)
            path = staging / f"{role.lower()}.json"
            _write_json(path, payload)
            artifacts[role] = {"path": str((output_dir / path.name).resolve()), "staging_path": str(path.resolve()), "sha256": _sha(path), "payload": payload}
        state_path = staging / "t1_gate_inputs.json"
        _write_json(state_path, {"schema_version": "paper_a_t1_gate_inputs_v1", "artifact_role": "T1_GATE_INPUTS", "method_contract_sha256": _sha(METHOD_CONTRACT), "dependencies": {role: value["payload"] for role, value in artifacts.items()}, "formal_ready": mode == "formal"})

        result = {
            "schema_version": SCHEMA, "artifact_role": "T1_STATIC_ASSIGNMENT_CHAIN", "contract_role": "generated_subordinate", **_method_identity(),
            "mode": mode, "formal_ready": False, "launch_ready": False,
            "mock_provenance": mode != "formal", "seed": seed, "task_count": len(task_pool), "assignment_count": len(assignments),
            "worker_count": len(workers), "assignment_sha256": _sha(assignment_path), "task_pool_sha256": _sha(task_pool_csv),
            "roster_sha256": _sha(roster_csv), "sap_sha256": _sha(sap_json), "deployment_manifest_sha256": _sha(deployment_manifest),
            "randomization_plan_sha256": _sha(randomization_path),
            "input_identity": identity,
            "assignment_path": str((output_dir / assignment_path.name).resolve()), "randomization_plan_path": str((output_dir / randomization_path.name).resolve()),
            "runtime_mapping_path": str((output_dir / mapping_path.name).resolve()), "runtime_mapping_sha256": _sha(mapping_path),
            "deployments": import_outputs, "private_lists": private_outputs, "artifacts": artifacts,
            "gate_inputs_path": str((output_dir / state_path.name).resolve()), "gate_inputs_sha256": _sha(state_path),
            "balance_summary": {worker: dict(stats[worker]) for worker in workers},
        }
        if stage3_state_json is not None:
            if enrollment_registry_csv is None or not enrollment_registry_csv.is_file():
                raise ValueError("T1 Stage 3 gate materialization requires enrollment_registry_csv")
            state = json.loads(stage3_state_json.read_text(encoding="utf-8"))
            gate_state = state.get("gates", state)
            for role, item in artifacts.items():
                gate_state[role] = {
                    "role": role, "path": item["staging_path"],
                    "sha256": item["sha256"], "expected_schema": "paper_a_t1_static_artifact_v1",
                    "required_status_field": "formal_ready", "required_status_value": True,
                    "profile_version": profile_version, "cohort_id": cohort_id, "frozen": mode == "formal",
                }
            updated_state = {"gates": gate_state} if "gates" in state else gate_state
            updated_state_path = staging / "t1_gate_state.json"
            _write_json(updated_state_path, updated_state)
            from tools.thesis_main.analysis.materialize_stage3_freeze_gate import materialize as materialize_gate
            gate_path = staging / "t1_stage3_freeze_gate.json"
            gate = materialize_gate(updated_state_path, roster_csv, enrollment_registry_csv, gate_path, gate_kind="T1")
            gate_payload = json.loads(gate_path.read_text(encoding="utf-8"))
            staging_root = str(staging.resolve())
            output_root = str(output_dir.resolve())

            def relocate_paths(value: Any) -> Any:
                if isinstance(value, dict):
                    return {key: relocate_paths(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [relocate_paths(item) for item in value]
                if isinstance(value, str) and value.startswith(staging_root):
                    return output_root + value[len(staging_root):]
                return value

            gate_path.write_text(json.dumps(relocate_paths(gate_payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result["stage3_gate"] = {"path": str((output_dir / gate_path.name).resolve()), "sha256": _sha(gate_path), "formal_ready": gate["formal_ready"]}
            result["formal_ready"] = bool(mode == "formal" and gate["formal_ready"])
            result["launch_ready"] = result["formal_ready"]
            if mode == "formal" and not gate["formal_ready"]:
                raise ValueError("T1 Stage 3 gate remains blocked:" + ";".join(gate["blockers"]))
        _write_json(staging / "t1_static_chain_manifest.json", result)
        staging.rename(output_dir)
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _runtime_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("tasks", payload.get("data", []))
    else:
        rows = []
    if not isinstance(rows, list):
        raise ValueError(f"T1 runtime export must contain a task list:{path}")
    return [row for row in rows if isinstance(row, dict)]


def bind_t1_runtime(
    assignment_manifest: Path,
    deployment_manifest: Path,
    planned_imports: dict[str, Path],
    runtime_exports: dict[str, Path],
    output_dir: Path,
    *,
    private_lists_dir: Path | None = None,
) -> dict[str, Any]:
    """Bind manually exported T1 tasks to the frozen static assignment."""
    assignment_rows = _read_csv(assignment_manifest)
    if not assignment_rows:
        raise ValueError("T1 assignment manifest is empty")
    deployments, worker_to_deployment = _load_deployments(deployment_manifest, assignment_rows)
    method = _method_identity()
    manifest = json.loads(deployment_manifest.read_text(encoding="utf-8"))
    if any(manifest.get(field) != value for field, value in method.items()):
        raise ValueError("T1 deployment manifest method contract is stale")
    if set(planned_imports) != set(deployments) or set(runtime_exports) != set(deployments):
        raise ValueError("T1 runtime binding requires exactly one import and export per deployment")
    if any(not path.is_file() for path in [*planned_imports.values(), *runtime_exports.values()]):
        raise ValueError("T1 runtime import/export is missing")
    expected_by_deployment: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in assignment_rows:
        planned = _text(row.get("planned_task_id"))
        worker = normalize_worker_id(row.get("worker_id", ""))
        deployment_id = _text(row.get("deployment_id")) or worker_to_deployment.get(worker, "")
        if not planned or not worker or deployment_id not in deployments or planned in expected_by_deployment[deployment_id]:
            raise ValueError("T1 assignment has empty or duplicate runtime identity")
        expected_by_deployment[deployment_id][planned] = {**row, "worker_id": worker, "deployment_id": deployment_id}
    seen_project_runtime: set[tuple[str, str]] = set()
    mapping_rows: list[dict[str, Any]] = []
    import_shas: dict[str, str] = {}
    export_shas: dict[str, str] = {}
    for deployment_id, deployment in deployments.items():
        planned_path = planned_imports[deployment_id]
        runtime_path = runtime_exports[deployment_id]
        import_shas[deployment_id] = _sha(planned_path)
        export_shas[deployment_id] = _sha(runtime_path)
        planned_rows = _runtime_tasks(planned_path)
        planned_by_id: dict[str, dict[str, Any]] = {}
        for item in planned_rows:
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            planned = _text(data.get("planned_task_id"))
            if not planned or planned in planned_by_id:
                raise ValueError(f"T1 planned import has duplicate task identity:{deployment_id}")
            if any(_text(data.get(field)) != _text(deployment.get(field)) for field in ("project_id", "server_instance_id", "server_url", "language_group")):
                raise ValueError(f"T1 planned import deployment identity mismatch:{deployment_id}")
            if _text(data.get("method_contract_sha256")) != method["method_contract_sha256"]:
                raise ValueError(f"T1 planned import method contract is stale:{deployment_id}")
            if planned not in expected_by_deployment[deployment_id]:
                raise ValueError(f"T1 planned import contains an unassigned task:{planned}")
            planned_by_id[planned] = item
        if set(planned_by_id) != set(expected_by_deployment[deployment_id]):
            raise ValueError(f"T1 planned import does not cover the frozen assignment:{deployment_id}")
        runtime_rows = _runtime_tasks(runtime_path)
        bound_planned: set[str] = set()
        bound_runtime: set[str] = set()
        for item in runtime_rows:
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            planned = _text(data.get("planned_task_id"))
            runtime_id = _text(item.get("id") or item.get("task_id"))
            project = _text(item.get("project") or item.get("project_id") or data.get("project_id"))
            if not planned or planned in bound_planned or not runtime_id or runtime_id in bound_runtime:
                raise ValueError(f"T1 runtime export has duplicate identity:{deployment_id}")
            if planned not in planned_by_id or project != _text(deployment.get("project_id")):
                raise ValueError(f"T1 runtime export has wrong project or planned task:{deployment_id}")
            planned_data = planned_by_id[planned].get("data", {})
            if any(_text(data.get(field)) != _text(planned_data.get(field)) for field in ("deployment_id", "language_group", "server_instance_id", "server_url", "condition", "image_id", "image_sha256", "model_layout_sha256")):
                raise ValueError(f"T1 runtime export task identity disagrees with planned import:{planned}")
            project_runtime = (project, runtime_id)
            if project_runtime in seen_project_runtime:
                raise ValueError("T1 runtime export has a cross-server project/runtime collision")
            seen_project_runtime.add(project_runtime)
            bound_planned.add(planned)
            bound_runtime.add(runtime_id)
            expected = expected_by_deployment[deployment_id][planned]
            mapping_rows.append({
                "schema_version": "t1_runtime_mapping_v1", **method,
                "assignment_sha256": _sha(assignment_manifest), "deployment_manifest_sha256": _sha(deployment_manifest),
                "deployment_id": deployment_id, "language_group": deployment["language_group"],
                "server_instance_id": deployment["server_instance_id"], "server_url": deployment["server_url"],
                "project_id": project, "worker_id": expected["worker_id"], "planned_task_id": planned,
                "task_id": _text(expected.get("task_id")), "image_id": _text(expected.get("image_id")),
                "condition": _text(expected.get("condition")), "runtime_task_id": runtime_id,
                "runtime_binding_status": "bound",
            })
        if bound_planned != set(planned_by_id):
            raise ValueError(f"T1 runtime export is missing or adds planned tasks:{deployment_id}")
    if private_lists_dir is not None:
        private_ids: set[tuple[str, str]] = set()
        for worker in sorted(worker_to_deployment):
            path = private_lists_dir / f"worker_{worker}_T1.csv"
            if not path.is_file():
                raise ValueError(f"T1 private worker list is missing:{worker}")
            private_ids.update((normalize_worker_id(row.get("worker_id", "")), _text(row.get("planned_task_id"))) for row in _read_csv(path))
        expected_ids = {(normalize_worker_id(row.get("worker_id", "")), _text(row.get("planned_task_id"))) for row in assignment_rows}
        if private_ids != expected_ids:
            raise ValueError("T1 private worker lists do not cover the frozen assignment")
    mapping_path = output_dir / "t1_runtime_mapping_bound.csv"
    evidence_path = output_dir / "t1_runtime_evidence_v1.json"
    if mapping_path.exists() or evidence_path.exists():
        raise ValueError("T1 runtime evidence target already exists")
    _write_csv(mapping_path, mapping_rows)
    evidence = {
        "schema_version": "t1_runtime_evidence_v1", "artifact_role": "T1_RUNTIME_EVIDENCE",
        "contract_role": "generated_subordinate", **method, "formal_ready": True,
        "runtime_binding_status": "bound", "assignment_sha256": _sha(assignment_manifest),
        "deployment_manifest_sha256": _sha(deployment_manifest), "deployment_ids": sorted(deployments),
        "planned_import_sha256": import_shas, "runtime_export_sha256": export_shas,
        "runtime_mapping_path": str(mapping_path.resolve()), "runtime_mapping_sha256": _sha(mapping_path),
        "worker_task_binding_count": len(mapping_rows), "one_to_one": True,
        "dependencies": [
            {"role": "ASSIGNMENT_MANIFEST", "path": str(assignment_manifest.resolve()), "sha256": _sha(assignment_manifest)},
            {"role": "DEPLOYMENT_MANIFEST", "path": str(deployment_manifest.resolve()), "sha256": _sha(deployment_manifest)},
            {"role": "RUNTIME_MAPPING", "path": str(mapping_path.resolve()), "sha256": _sha(mapping_path)},
            *[{"role": f"PLANNED_IMPORT_{key}", "path": str(planned_imports[key].resolve()), "sha256": import_shas[key]} for key in sorted(planned_imports)],
            *[{"role": f"RUNTIME_EXPORT_{key}", "path": str(runtime_exports[key].resolve()), "sha256": export_shas[key]} for key in sorted(runtime_exports)],
        ],
    }
    _write_json(evidence_path, evidence)
    return {"formal_ready": True, "runtime_mapping_path": str(mapping_path.resolve()), "runtime_evidence_path": str(evidence_path.resolve()), "runtime_mapping_sha256": _sha(mapping_path), "runtime_evidence_sha256": _sha(evidence_path), "worker_task_binding_count": len(mapping_rows)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize the static T1 assignment and CE-only operator package.")
    parser.add_argument("--task-pool", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--deployment-manifest", type=Path, required=True)
    parser.add_argument("--sap", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--mode", choices=("mock_dry_run", "formal"), default="mock_dry_run")
    parser.add_argument("--stage3-state", type=Path)
    parser.add_argument("--enrollment-registry", type=Path)
    return parser


def _binding_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bind manually exported T1 runtime tasks to the frozen assignment.")
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--deployment-manifest", type=Path, required=True)
    parser.add_argument("--planned-import", action="append", default=[], metavar="DEPLOYMENT_ID=PATH")
    parser.add_argument("--runtime-export", action="append", default=[], metavar="DEPLOYMENT_ID=PATH")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--private-lists-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "bind-runtime":
        args = _binding_parser().parse_args(argv[1:])
        try:
            result = bind_t1_runtime(
                args.assignment, args.deployment_manifest,
                _parse_bindings(args.planned_import, option="--planned-import"),
                _parse_bindings(args.runtime_export, option="--runtime-export"),
                args.output_dir, private_lists_dir=args.private_lists_dir,
            )
        except Exception as exc:
            print(json.dumps({"formal_ready": False, "reason_code": f"blocked:{type(exc).__name__}", "reason": str(exc)}, ensure_ascii=False, indent=2))
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    args = _parser().parse_args(argv)
    try:
        result = materialize(args.task_pool, args.roster, args.deployment_manifest, args.sap, args.output_dir, seed=args.seed, mode=args.mode, stage3_state_json=args.stage3_state, enrollment_registry_csv=args.enrollment_registry)
    except Exception as exc:
        print(json.dumps({"schema_version": SCHEMA, "formal_ready": False, "launch_ready": False, "reason_code": f"blocked:{type(exc).__name__}", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
