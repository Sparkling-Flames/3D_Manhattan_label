"""Materialize the one authorized C2-A-RP Block 2 package."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import (
    C2A_ASSIGNMENT_FIELDS,
    PRECISION_FIELDS,
    build_assignments_with_capacity_fallback,
    build_precision_plan,
)
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.run_c2b_c2a_rp_chain import _package_c2a_rp
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


ROOT = Path(__file__).resolve().parents[3]
PROFILE = ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v2/post_c2a_rp_block1_worker_profile.csv"
REESTIMATE = ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v2/c2a_rp_block1_reestimate_summary.json"
BLOCK1 = ROOT / "analysis_results/c2a_rp_block1_distribution_20260807_v7/c2a_rp/assignment_manifest_C2A_RP.csv"
POOL = ROOT / "analysis_results/c2a_rp_capacity_power_amendment_20260807_v1/c2a_rp_task_pool_amended.csv"
RESERVE = ROOT / "analysis_results/c2a_rp_capacity_power_amendment_20260807_v1/c2a_rp_new_stress_candidate_registry.csv"
HISTORY = ROOT / "analysis_results/c2b_closeout_20260806_inputs/c2a_rp_seen_history_through_c2b.csv"
C2B = ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/c2b_closeout_v2.json"
THRESHOLD = ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2b_derived_threshold_manifest.json"
AMENDMENT = ROOT / "docs/thesis_main/C2A_RP_BLOCK2_CAPACITY_AMENDMENT_20260810_v2.json"
DEPLOYMENTS = ROOT / "analysis_results/c2b_runtime_binding_20260806_v18_d8/c2b_worker_deployment_manifest_v1.json"
MODEL_LAYOUTS = ROOT / "analysis_results/c2b_validation_static_20260802_v16/inputs/model_layout_json"
DEFAULT_OUTPUT = ROOT / "analysis_results/c2a_rp_block2_distribution_20260810_v1"
DEFAULT_IMPORTS = ROOT / "import_json/c2a_rp"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _block2_deployments(worker_ids: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    payload = json.loads(DEPLOYMENTS.read_text(encoding="utf-8"))
    deployments = {row["deployment_id"]: dict(row) for row in payload["deployments"]}
    # Block 1 was actually collected in Projects 78/79; Block 2 must preserve
    # that runtime identity even though the older C2-B manifest names 76/77.
    deployments["c2b_en"]["project_id"] = "78"
    deployments["c2b_zh"]["project_id"] = "79"
    worker_to_deployment = {
        str(worker): deployment_id
        for deployment_id, deployment in deployments.items()
        for worker in deployment["worker_ids"]
        if str(worker) in worker_ids
    }
    if set(worker_to_deployment) != worker_ids:
        raise ValueError("Block 2 deployment map does not cover the assigned workers")
    return deployments, worker_to_deployment


def materialize(output_dir: Path = DEFAULT_OUTPUT, import_dir: Path = DEFAULT_IMPORTS) -> dict[str, Any]:
    required = (PROFILE, REESTIMATE, BLOCK1, POOL, RESERVE, HISTORY, C2B, THRESHOLD, AMENDMENT, DEPLOYMENTS, MODEL_LAYOUTS)
    if any(not path.exists() for path in required):
        raise ValueError("C2-A-RP Block 2 input is missing")
    if output_dir.exists():
        raise ValueError(f"output directory already exists:{output_dir}")

    amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    if amendment.get("status") != "normative" or amendment.get("change", {}).get("effective_from_block") != 2 or amendment.get("change", {}).get("effective_through_block") != 5:
        raise ValueError("Block 2 capacity amendment is not approved")
    reestimate = json.loads(REESTIMATE.read_text(encoding="utf-8"))
    if not (reestimate.get("formal_ready") is True
            and reestimate.get("artifact_role") == "C2A_RP_BLOCK1_REESTIMATE_FROZEN"
            and reestimate.get("c2b_collection_status") == "closed_historical_collection"
            and reestimate.get("c2b_input_acceptance_scope") == "C2A_RP_reestimate_only"
            and reestimate.get("corrected_c2b_evidence_frozen") is True):
        raise ValueError("Block 2 requires the terminal corrected post-Block1 reestimate")
    if amendment.get("block1_reestimate", {}).get("sha256") != sha256_file(REESTIMATE):
        raise ValueError("Block 2 amendment does not bind the current reestimate")
    if reestimate.get("input_sha256", {}).get(C2B.name) != sha256_file(C2B):
        raise ValueError("Historical C2-B closeout binding changed")
    max_support = int(amendment["change"]["max_task_support_after"])
    seed = int(amendment["unchanged_rules"]["selection_seed"])
    excluded = {row["task_id"] for row in amendment["reference_exclusions"]}

    profile_rows = read_csv(PROFILE)
    block1_rows = read_csv(BLOCK1)
    pool_rows = [row for row in read_csv(POOL) if row.get("task_id") not in excluded]
    activated_backup_ids = set(amendment["change"].get("activated_validation_stress_backup_task_ids", []))
    reserve_rows = {row["task_id"]: row for row in read_csv(RESERVE)}
    if activated_backup_ids - reserve_rows.keys():
        raise ValueError("Authorized Block 2 backup is missing from the frozen reserve")
    pool_rows.extend(reserve_rows[task_id] for task_id in sorted(activated_backup_ids))
    amendment_sha = sha256_file(AMENDMENT)
    threshold_sha = sha256_file(THRESHOLD)
    plan_rows = build_precision_plan(
        profile_rows,
        target_half_width=float(json.loads(THRESHOLD.read_text(encoding="utf-8"))["thresholds"]["risk_slope_ci_half_width"]),
        max_additional_blocks=4,
        manifest_sha=amendment_sha,
        threshold_sha=threshold_sha,
        formal=True,
    )
    history_rows = [*read_csv(HISTORY), *block1_rows]
    block2_rows, fallback_workers = build_assignments_with_capacity_fallback(
        plan_rows,
        pool_rows,
        manifest_sha=amendment_sha,
        c2b_sha=sha256_file(C2B),
        profile_sha=sha256_file(PROFILE),
        history_rows=history_rows,
        max_task_support=max_support,
        selection_seed=seed,
        require_explicit_eligibility=True,
        formal=True,
        dispatch_block_index=2,
    )
    candidate_workers = {row["worker_id"] for row in plan_rows if int(row["additional_blocks"]) > 0}
    target_met_workers = {str(value) for value in amendment["block2_roster_rule"]["expected_target_met_worker_ids"]}
    if target_met_workers & candidate_workers or len(candidate_workers) != int(amendment["block2_roster_rule"]["expected_block2_worker_count"]):
        raise ValueError("Block 2 roster disagrees with the frozen precision rule")
    expected_workers = int(amendment["block2_roster_rule"]["expected_block2_worker_count"])
    if fallback_workers or len(candidate_workers) != expected_workers or len(block2_rows) != 2 * expected_workers:
        raise ValueError("Block 2 is not a complete paired assignment for the frozen roster")
    by_worker = Counter(row["worker_id"] for row in block2_rows)
    strata = defaultdict(set)
    for row in block2_rows:
        strata[row["worker_id"]].add(row["task_stratum"])
    if any(by_worker[worker] != 2 or strata[worker] != {"ordinary", "stress"} for worker in candidate_workers):
        raise ValueError("Block 2 violates the ordinary/stress pair rule")
    if excluded & {row["task_id"] for row in block2_rows}:
        raise ValueError("Block 2 contains a reference-excluded task")
    cumulative_support = Counter(row["task_id"] for row in [*block1_rows, *block2_rows])
    if max(cumulative_support.values()) > max_support:
        raise ValueError("Block 2 exceeds the one-time task support cap")

    c2a_dir = output_dir / "c2a_rp"
    operational_dir = output_dir / "c2a_rp_operational"
    release_dir = output_dir / "worker_facing_release"
    c2a_dir.mkdir(parents=True)
    release_dir.mkdir()
    pool_path = output_dir / "c2a_rp_task_pool_block2.csv"
    block_path = output_dir / "assignment_manifest_C2A_RP_block_2.csv"
    write_csv(pool_path, pool_rows)
    write_csv(block_path, block2_rows, C2A_ASSIGNMENT_FIELDS)
    write_csv(c2a_dir / "precision_plan_C2A_RP.csv", plan_rows, PRECISION_FIELDS)
    write_csv(c2a_dir / "assignment_manifest_C2A_RP.csv", [*block1_rows, *block2_rows], C2A_ASSIGNMENT_FIELDS)
    summary_path = c2a_dir / "precision_plan_C2A_RP.summary.json"
    write_json(summary_path, {
        "schema_version": "c2a_rp_precision_plan_summary_v2",
        "status": "block2_ready_for_manual_import",
        "dispatch_mode": "append_only_sequential",
        "dispatch_block_index": 2,
        "design_manifest_sha256": amendment_sha,
        "c2b_summary_sha256": sha256_file(C2B),
        "worker_profile_sha256": sha256_file(PROFILE),
        "threshold_manifest_sha256": threshold_sha,
        "existing_assignment_manifest_sha256": sha256_file(BLOCK1),
        "max_additional_blocks": 4,
        "max_task_support": max_support,
        "n_workers": len(plan_rows),
        "n_workers_at_target": 0,
        "n_workers_not_evaluable": 2,
        "n_workers_with_block2": expected_workers,
        "capacity_fallback_workers": [],
    })

    deployments, worker_to_deployment = _block2_deployments(candidate_workers)
    package = _package_c2a_rp(
        operational_dir,
        block_path,
        pool_path,
        deployments,
        worker_to_deployment,
        block_index=2,
        c2a_summary_path=summary_path,
        model_layout_dir=MODEL_LAYOUTS,
    )
    package["status"] = "planned_not_imported_not_dispatched"
    package["active_time_freeze_required_after_collection"] = True
    package["active_time_expected_project_ids"] = ["78", "79"]

    import_dir.mkdir(parents=True, exist_ok=True)
    import_names = {
        "c2b_en": "c2a_rp_block_2_import_foreign_https.json",
        "c2b_zh": "c2a_rp_block_2_import_zh.json",
    }
    import_outputs = {}
    for deployment_id, filename in import_names.items():
        source = Path(package["deployments"][deployment_id]["planned_import_path"])
        target = import_dir / filename
        shutil.copyfile(source, target)
        import_outputs[deployment_id] = {"path": str(target.resolve()), "sha256": sha256_file(target)}
    _write_text(import_dir / "README.md", """# C2-A-RP planned imports

- Block 1: `c2a_rp_block_1_import_foreign_https.json` / `c2a_rp_block_1_import_zh.json`
- Block 2: `c2a_rp_block_2_import_foreign_https.json` -> Project 78 (Project E); `c2a_rp_block_2_import_zh.json` -> Project 79 (任务5)
- C2-A-RP Block 1--5 保持同一套 `scope_instruction_v1`；不要在 Project 78/79 部署本地 v2 XML。导入后回填 runtime task ID，再通知工人。
""")

    worker_rows = []
    for worker in sorted(candidate_workers, key=int):
        rows = sorted((row for row in block2_rows if row["worker_id"] == worker), key=lambda row: int(row["assignment_sequence"]))
        worker_rows.append({
            "worker_id": worker,
            "language_group": deployments[worker_to_deployment[worker]]["language_group"],
            "task_1": rows[0]["task_id"],
            "task_2": rows[1]["task_id"],
        })
    write_csv(release_dir / "block2_worker_assignments.csv", worker_rows)

    manifest = {
        "schema_version": "c2a_rp_block2_distribution_manifest_v1",
        "status": "ready_for_manual_import_not_dispatched",
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "block2_capacity_amendment_path": str(AMENDMENT.resolve()),
        "block2_capacity_amendment_sha256": amendment_sha,
        "amendment_scope": "Blocks2_to_5",
        "block1_closed": True,
        "block1_assignment_sha256": sha256_file(BLOCK1),
        "post_block1_profile_sha256": sha256_file(PROFILE),
        "worker_count": expected_workers,
        "assignment_count": 2 * expected_workers,
        "target_met_not_assigned_workers": [],
        "not_evaluable_not_assigned_workers": ["18", "27"],
        "max_task_support_blocks2_to_5": max_support,
        "reference_excluded_task_ids": sorted(excluded),
        "activated_validation_stress_backup_task_ids": sorted(activated_backup_ids),
        "retired_from_future_t1_task_ids": sorted(activated_backup_ids),
        "future_blocks_preassigned": False,
        "operational_package": package,
        "import_json_outputs": import_outputs,
        "task_support_histogram_cumulative": dict(sorted(Counter(cumulative_support.values()).items())),
        "private_list_sha256": {
            path.name: sha256_file(path)
            for path in sorted((operational_dir / "private_lists").glob("*.csv"))
        },
    }
    write_json(output_dir / "C2A_RP_BLOCK2_DISTRIBUTION_MANIFEST.json", manifest)
    _write_text(output_dir / "READY_FOR_MANUAL_IMPORT.md", """# C2-A-RP Block 2

状态：20 人、40 个 worker-task assignment 已冻结，尚未导入、尚未发放。

1. Project 78 / 79 继续使用 Block 1 的 `scope_instruction_v1`；不要部署本地 v2 XML。
2. 英文 JSON 导入 Project 78（Project E），中文 JSON 导入 Project 79（任务5）。
3. 从 Label Studio task list 回填 40 行 runtime mapping，核对 private list 后再通知工人。
4. 收轮后按实际日期冻结 `active_logs/c2a_rp_block2_<date>`；Block 3 不得预分配。
""")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--import-dir", type=Path, default=DEFAULT_IMPORTS)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output_dir, args.import_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
