"""Audit PreScreen high-k support and replay the conservative topology gate.

Development diagnostic only.  This does not amend P1/C1 eligibility, freeze a
policy, or authorize a Main launch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry_for_c1_calculation
from tools.thesis_main.analysis import run_topology_sequential_preflight as topology


DEFAULT_INPUT = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701"
DEFAULT_OUTPUT = ROOT / "analysis_results" / "prescreen_topology_support_audit_20260819_v1"
COPY_RISK_WORKERS = {6, 13, 33}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, value: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_key(path: Path, root: Path, output_dir: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(Path(output_dir.name) / path.relative_to(output_dir))


def truth(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def image_id(row: dict[str, str]) -> str:
    return Path(row["task_label"]).stem


def prepare(root: Path, input_dir: Path) -> dict[str, Any]:
    canonical_path = input_dir / "prescreen_canonical_annotations.csv"
    admission_path = input_dir / "prescreen_worker_admission.csv"
    scope_path = input_dir / "prescreen_gold_status_audit.csv"
    rows = read_csv(canonical_path)
    admission = {int(row["worker_id"]): row for row in read_csv(admission_path)}
    scope = {(row["project_id"], row["task_id"]): row for row in read_csv(scope_path)}

    identities = [(row["project_id"], row["task_id"], row["annotator_id"]) for row in rows]
    if len(identities) != len(set(identities)):
        raise AssertionError("canonical project-task-worker identity is not unique")

    for row in rows:
        row["_worker"] = int(row["annotator_id"])
        row["_image"] = image_id(row)
        row["_scope"] = scope[(row["project_id"], row["task_id"])]["task_final_scope"]
        row["_c1_eligible"] = truth(admission[row["_worker"]]["eligible_for_C1"])
        corners = json.loads(row["canonical_geometry"] or "[]")
        normalized = normalize_geometry_for_c1_calculation(corners)
        row["_normalized"] = normalized
        row["_normalizer_valid"] = normalized["valid"] is True

    manual = [row for row in rows if row["condition"] == "manual"]
    project_images = {project: {row["_image"] for row in manual if row["project_id"] == project} for project in {"28", "39"}}
    if project_images["28"] != project_images["39"] or len(project_images["28"]) != 30:
        raise AssertionError("Chinese and English manual task image sets do not match at 30 images")

    c1_structure_path = topology.c1_root(root) / "geometry_task_crowd_structure_C1.csv"
    c1_tasks = {
        row["base_task_id"]
        for row in read_csv(c1_structure_path)
        if row.get("condition") == "manual" and int(row.get("valid_k") or 0) >= 5
    }
    prescreen_in_scope = {row["_image"] for row in manual if row["_scope"] == "in_scope"}
    if len(c1_tasks) != 78 or len(prescreen_in_scope) != 29 or c1_tasks & prescreen_in_scope:
        raise AssertionError("C1/PreScreen task inventories drifted or are not disjoint")
    c1_buildings = {task.split("_", 1)[0] for task in c1_tasks}
    prescreen_buildings = {task.split("_", 1)[0] for task in prescreen_in_scope}
    if len(prescreen_buildings) != 11 or not prescreen_buildings <= c1_buildings:
        raise AssertionError("PreScreen in-scope building overlap with C1 drifted")

    return {
        "rows": rows,
        "manual": manual,
        "admission": admission,
        "inputs": [canonical_path, admission_path, scope_path, c1_structure_path],
        "c1_tasks": c1_tasks,
        "prescreen_in_scope": prescreen_in_scope,
    }


def audit_rows(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = data["rows"]
    lane_rows = []
    for (condition, scope), group in sorted(_groups(rows, lambda row: (row["condition"], row["_scope"])).items()):
        lane_rows.append({
            "condition": condition,
            "final_scope": scope,
            "runtime_contexts": len({(row["project_id"], row["task_id"]) for row in group}),
            "unique_images": len({row["_image"] for row in group}),
            "canonical_rows": len(group),
            "unique_workers": len({row["_worker"] for row in group}),
            "topology_replay_role": "primary_development_lane" if condition == "manual" and scope == "in_scope" else "separate_sensitivity_or_scope_lane",
        })

    manual = [row for row in data["manual"] if row["_scope"] == "in_scope"]
    scenarios = scenario_rows(manual)
    support_rows = []
    inventory_rows = []
    for name, group in scenarios.items():
        by_task = _groups(group, lambda row: row["_image"])
        counts = [sum(row["_normalizer_valid"] for row in task_rows) for task_rows in by_task.values()]
        support_rows.append({
            "scenario": name,
            "canonical_rows": len(group),
            "normalizer_valid_rows": sum(counts),
            "normalizer_invalid_rows": len(group) - sum(counts),
            "unique_images": len(by_task),
            "min_valid_k": min(counts),
            "max_valid_k": max(counts),
            "tasks_k_ge_5": sum(count >= 5 for count in counts),
            "selection_role": "eligible_replay" if name.startswith("c1_eligible") else "roster_or_inadmissible_sensitivity",
        })
        for task, task_rows in sorted(by_task.items()):
            valid = sum(row["_normalizer_valid"] for row in task_rows)
            inventory_rows.append({
                "scenario": name,
                "base_task_id": task,
                "building_id": task.split("_", 1)[0],
                "candidate_rows": len(task_rows),
                "unique_workers": len({row["_worker"] for row in task_rows}),
                "normalizer_valid_k": valid,
                "normalizer_invalid_k": len(task_rows) - valid,
                "support_k_ge_5": str(valid >= 5).lower(),
            })

    invalid_rows = []
    for row in manual:
        if row["_normalizer_valid"] or not row["_c1_eligible"]:
            continue
        parsed = row["_normalized"]
        invalid_rows.append({
            "project_id": row["project_id"],
            "runtime_task_id": row["task_id"],
            "base_task_id": row["_image"],
            "worker_id": row["_worker"],
            "canonical_annotation_id": row["canonical_annotation_id"],
            "raw_point_count": parsed["raw_point_count"],
            "raw_failure_reason": parsed["reason"],
            "repair_status": parsed["geometry_repair_status"],
            "orphan_candidate_count": parsed["orphan_candidate_count"],
            "repair_applied": str(parsed["geometry_repair_applied"]).lower(),
            "analysis_disposition": "excluded_from_geometry_metric; raw structural evidence_retained",
        })
    return lane_rows, support_rows, inventory_rows + invalid_rows


def scenario_rows(manual_in_scope: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "all_completed_combined": list(manual_in_scope),
        "c1_eligible_chinese": [row for row in manual_in_scope if row["_c1_eligible"] and row["project_id"] == "28"],
        "c1_eligible_english": [row for row in manual_in_scope if row["_c1_eligible"] and row["project_id"] == "39"],
        "c1_eligible_combined": [row for row in manual_in_scope if row["_c1_eligible"]],
        "current20_combined": [row for row in manual_in_scope if row["_worker"] in topology.LIVE_WORKERS],
        "c1_eligible_excluding_copy_risk": [row for row in manual_in_scope if row["_c1_eligible"] and row["_worker"] not in COPY_RISK_WORKERS],
    }


def _groups(rows: list[dict[str, Any]], key) -> dict[Any, list[dict[str, Any]]]:
    result: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return result


def replay(manual_in_scope: list[dict[str, Any]], replicates: int, seed: int) -> list[dict[str, Any]]:
    output = []
    for scenario, source_rows in scenario_rows(manual_in_scope).items():
        tasks = _groups(source_rows, lambda row: row["_image"])
        task_metrics: dict[str, list[dict[str, float]]] = defaultdict(list)
        for task, rows in tasks.items():
            candidates = []
            for row in rows:
                parsed = dict(row["_normalized"], worker_id=row["_worker"])
                candidate = {
                    "canonical_annotation_id": row["canonical_annotation_id"],
                    "base_task_id": task,
                    "worker_id": row["_worker"],
                    "geometry_metric_evaluable": row["_normalizer_valid"],
                    "replay_geometry_admissible": row["_normalizer_valid"],
                    "structurally_valid": row["_normalizer_valid"],
                    "_geometry": parsed,
                }
                candidates.append(candidate)
            valid_candidates = [row for row in candidates if row["replay_geometry_admissible"]]
            pair_cache = {row["worker_id"]: {} for row in valid_candidates}
            for left_index, left in enumerate(valid_candidates):
                for right in valid_candidates[left_index + 1 :]:
                    metric = topology._pairwise_metric(left["_geometry"], right["_geometry"])
                    pair_cache[left["worker_id"]][right["worker_id"]] = metric
                    pair_cache[right["worker_id"]][left["worker_id"]] = metric
            for row in valid_candidates:
                row["_geometry"]["_frozen_pairwise_by_worker"] = pair_cache[row["worker_id"]]
            if sum(row["replay_geometry_admissible"] for row in candidates) < 5:
                raise AssertionError(f"{scenario}/{task} unexpectedly lacks five valid candidates")
            for replicate in range(replicates):
                order = topology._stable_order(candidates, task, replicate, seed)
                f0 = topology.run_f0(order, task)
                m1 = topology.run_m1(order, task)
                task_metrics[task].append({
                    "stop_at_3": float(m1["stop_at_3"] is True),
                    "stop_at_4": float(m1["incremental_stop_at_4"] is True),
                    "reach5": float(m1["reach5"] is True),
                    "unresolved": float(m1["status"] == "unresolved_expert_escalation_required"),
                    "m1_valid_k": float(m1["K_valid"]),
                    "m1_paid_attempts": float(m1["K_attempts"]),
                    "f0_paid_attempts": float(f0["K_attempts"]),
                    "selected_output_mismatch": float(
                        m1.get("selected") is not None
                        and f0.get("selected") is not None
                        and topology._key(m1["selected"]) != topology._key(f0["selected"])
                    ),
                    "selected_output_comparable": float(m1.get("selected") is not None and f0.get("selected") is not None),
                })
        metrics = {}
        for name in next(iter(task_metrics.values()))[0]:
            per_task = [statistics.mean(row[name] for row in values) for values in task_metrics.values()]
            metrics[name] = statistics.mean(per_task)
        comparable = sum(sum(row["selected_output_comparable"] for row in values) for values in task_metrics.values())
        mismatch = sum(sum(row["selected_output_mismatch"] for row in values) for values in task_metrics.values())
        output.append({
            "scenario": scenario,
            "tasks": len(task_metrics),
            "replicates_per_task": replicates,
            "stop_at_3": metrics["stop_at_3"],
            "incremental_stop_at_4": metrics["stop_at_4"],
            "reach5": metrics["reach5"],
            "unresolved_expert_escalation": metrics["unresolved"],
            "mean_valid_k_m1": metrics["m1_valid_k"],
            "mean_paid_attempts_m1": metrics["m1_paid_attempts"],
            "mean_paid_attempts_f0": metrics["f0_paid_attempts"],
            "selected_output_mismatch_given_m1_output": mismatch / comparable if comparable else "",
            "estimand_status": "development_replay_not_safety_or_quality_evidence",
        })
    return output


def report(output_dir: Path, support_rows: list[dict[str, Any]], invalid_rows: list[dict[str, Any]], replay_rows: list[dict[str, Any]], replicates: int) -> None:
    support = {row["scenario"]: row for row in support_rows}
    replay_by = {row["scenario"]: row for row in replay_rows}
    invalid = [row for row in invalid_rows if "repair_status" in row]
    text = f"""# PreScreen topology support audit v1

Development-only diagnostic. It does not change P1/C1 eligibility, repair raw submissions, freeze a policy, or authorize Main.

## Denominator finding

- Frozen C1 manual high-k inventory remains 78 images. PreScreen contributes 29 additional, disjoint, final-in-scope manual images; the two stages must remain separate analysis strata.
- C1-admitted PreScreen support: {support['c1_eligible_combined']['normalizer_valid_rows']} valid rows across 29 images, valid k={support['c1_eligible_combined']['min_valid_k']}–{support['c1_eligible_combined']['max_valid_k']}; all 29 reach k>=5.
- Current-20 sensitivity: {support['current20_combined']['normalizer_valid_rows']} valid rows, valid k={support['current20_combined']['min_valid_k']}–{support['current20_combined']['max_valid_k']}; all 29 reach k>=5.
- Therefore the earlier 47-task figure is not the total historical high-k inventory. It is a C1-only current-roster/dual-validity sensitivity denominator.

## Filter audit

- Exactly {len(invalid)} C1-admitted in-scope manual rows fail the current calculation normalizer.
- No row satisfies the unique-orphan repair rule. Ambiguous single-point deletions remain invalid; two out-of-range rows contain the same raw y=761.1879% source artifact and cannot be silently decimal-corrected.
- Restoring all five rows would not add a k>=5 task because every affected task already has much more than five valid candidates.
- The 86 in-scope rows from workers 19, 21 and 26 are excluded by frozen worker admission, not by geometry filtering. The all-completed result is retained only as an inadmissible sensitivity.
- Semi and OOS records are retained in separate lanes; they are not discarded, but are not pooled into the manual topology replay.

## Conservative M1 replay ({replicates:,} permutations per image)

- C1-admitted combined: stop@3={replay_by['c1_eligible_combined']['stop_at_3']:.4f}, incremental stop@4={replay_by['c1_eligible_combined']['incremental_stop_at_4']:.4f}, reach5={replay_by['c1_eligible_combined']['reach5']:.4f}, mean valid k={replay_by['c1_eligible_combined']['mean_valid_k_m1']:.4f}.
- Current-20: stop@3={replay_by['current20_combined']['stop_at_3']:.4f}, incremental stop@4={replay_by['current20_combined']['incremental_stop_at_4']:.4f}, reach5={replay_by['current20_combined']['reach5']:.4f}, mean valid k={replay_by['current20_combined']['mean_valid_k_m1']:.4f}.
- Chinese and English cohorts are reported separately because they differ materially; pooling without a cohort stratum would conceal transportability risk.
- Prefix/full-k5 selected annotation mismatch is a stability diagnostic, not delivery harm. No expert-acceptable topology or actual delivery-harm label exists here, so safety and quality remain unidentified.

## Valid interpretation

The audit supports using the 29 PreScreen images as a stage-stratified development sensitivity alongside, not merged into, the 78-image frozen C1 replay. PreScreen selected the workers, so it is resubstitution evidence and cannot independently validate the policy. The 29 images span 11 buildings, all already represented in C1, so they add image-level support but no new building domain.
"""
    write_text(output_dir / "PRESCREEN_TOPOLOGY_SUPPORT_AUDIT.md", text)


def run(root: Path, input_dir: Path, output_dir: Path, replicates: int, seed: int) -> None:
    data = prepare(root, input_dir)
    lane_rows, support_rows, combined_rows = audit_rows(data)
    inventory_rows = [row for row in combined_rows if "scenario" in row]
    invalid_rows = [row for row in combined_rows if "repair_status" in row]
    manual_in_scope = [row for row in data["manual"] if row["_scope"] == "in_scope"]
    replay_rows = replay(manual_in_scope, replicates, seed)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "PRESCREEN_DATA_LANES.csv": lane_rows,
        "PRESCREEN_SUPPORT_FLOW.csv": support_rows,
        "PRESCREEN_TASK_INVENTORY.csv": inventory_rows,
        "PRESCREEN_NORMALIZER_DISPOSITION.csv": invalid_rows,
        "PRESCREEN_M1_REPLAY_SUMMARY.csv": replay_rows,
    }
    for name, rows in outputs.items():
        write_csv(output_dir / name, rows)
    report(output_dir, support_rows, invalid_rows, replay_rows, replicates)

    files = data["inputs"] + [Path(__file__)] + [output_dir / name for name in outputs] + [output_dir / "PRESCREEN_TOPOLOGY_SUPPORT_AUDIT.md"]
    manifest = {
        "analysis_id": output_dir.name,
        "development_only": True,
        "diagnostic_pre_stage3": True,
        "scientific_conclusion_prohibited": True,
        "formal_policy_frozen": False,
        "main_launch_authorized": False,
        "seed": seed,
        "replicates_per_task": replicates,
        "files_sha256": {manifest_key(path, root, output_dir): sha256(path) for path in files},
    }
    write_text(output_dir / "analysis_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()
    run(ROOT, args.input_dir, args.output_dir, args.replicates, args.seed)


if __name__ == "__main__":
    main()
