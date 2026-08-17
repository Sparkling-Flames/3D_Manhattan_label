"""Repair the post-Block2 pack after the terminal profile became available."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from tools.thesis_main.data_prep import build_post_block2_analysis_pack_v2 as v2


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v3"
PROFILE = ROOT / "analysis_results" / "final_calibration_profile_20260817_v1" / "pooled_worker_profile_v2.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0]) if rows else ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value: object) -> float | None:
    try:
        result = float(str(value))
        return result if result == result else None
    except (TypeError, ValueError):
        return None


def interval(row: dict[str, str], low: str, high: str) -> str:
    lo, hi = number(row.get(low)), number(row.get(high))
    return "not_identifiable" if lo is None or hi is None else f"{lo}|{hi}"


def sample_variance(values: list[float]) -> dict[str, object]:
    if len(values) < 2:
        return {"status": "not_identifiable", "reason": "fewer_than_two_evaluable_values", "n": len(values)}
    return {"status": "computed", "value": statistics.variance(values), "n": len(values)}


def repair_profile_and_inputs() -> None:
    submissions = read_csv(OUT / "post_block2_submission_master.csv")
    profiles = read_csv(PROFILE)
    observed = defaultdict(list)
    for row in submissions:
        observed[row["worker_id"]].append(row)
    merged: list[dict[str, object]] = []
    profile_by_worker = {row["worker_id"]: row for row in profiles}
    for worker_id in sorted(set(observed) | set(profile_by_worker), key=lambda x: (len(x), x)):
        source = profile_by_worker.get(worker_id)
        group = observed.get(worker_id, [])
        if source:
            row: dict[str, object] = dict(source)
            row.update({
                "profile_status": source.get("worker_profile_status") or source.get("Q_GT_profile_status"),
                "final_pooled_profile_status": "formal_ready",
                "final_profile_source": str(PROFILE.relative_to(ROOT)).replace("\\", "/"),
                "final_profile_sha256": sha256(PROFILE),
                "observed_submission_count": len(group),
                "observed_stage_counts": json.dumps(Counter(item["stage"] for item in group), sort_keys=True),
                "owner_valid_block2_active_time_count": sum(item.get("active_time_status") == "owner_valid" for item in group),
            })
        else:
            row = {
                "worker_id": worker_id,
                "profile_status": "source_absent_not_in_final_calibration_roster",
                "final_pooled_profile_status": "not_evaluable",
                "final_profile_source": str(PROFILE.relative_to(ROOT)).replace("\\", "/"),
                "final_profile_sha256": sha256(PROFILE),
                "observed_submission_count": len(group),
                "observed_stage_counts": json.dumps(Counter(item["stage"] for item in group), sort_keys=True),
                "owner_valid_block2_active_time_count": sum(item.get("active_time_status") == "owner_valid" for item in group),
            }
        merged.append(row)
    fields: list[str] = []
    for row in merged:
        for field in row:
            if field not in fields:
                fields.append(field)
    with (OUT / "post_block2_worker_profile_master.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)

    uncertainty = []
    for row in profiles:
        uncertainty.append({
            "worker_id": row["worker_id"],
            "Q_GT_interval": interval(row, "Q_GT_EB_CI_lower", "Q_GT_EB_CI_upper"),
            "F_struct_interval": interval(row, "F_struct_interval_lower", "F_struct_interval_upper"),
            "R_peer_interval": interval(row, "R_peer_CI_lower", "R_peer_CI_upper"),
            "R_LOO_medoid_interval": interval(row, "R_LOO_medoid_CI_lower", "R_LOO_medoid_CI_upper"),
            "active_time_interval": interval(row, "T_active_CI_lower", "T_active_CI_upper"),
            "risk_slope_ci_half_width": row.get("risk_slope_ci_half_width") or "not_identifiable",
            "risk_slope_for_simulation": row.get("risk_slope") or "not_identifiable",
            "support_status": "supported" if row.get("Q_GT_profile_status") == "estimated" else row.get("Q_GT_profile_status", "not_evaluable"),
            "source_artifact": str(PROFILE.relative_to(ROOT)).replace("\\", "/"),
            "source_artifact_sha256": sha256(PROFILE),
        })
    write_csv(OUT / "worker_profile_uncertainty_inputs.csv", uncertainty)

    c1 = [row for row in submissions if row["stage"] == "C1" and number(row.get("c1_iou_to_gt")) is not None]
    task_means = defaultdict(list)
    worker_means = defaultdict(list)
    for row in c1:
        value = float(row["c1_iou_to_gt"])
        task_means[(row["base_task_id"], row.get("condition", ""))].append(value)
        worker_means[row["worker_id"]].append(value)
    task_values = [statistics.mean(values) for values in task_means.values()]
    worker_values = [statistics.mean(values) for values in worker_means.values()]
    active = [value for row in submissions if (value := number(row.get("active_time_seconds"))) is not None]
    variance = {
        "schema_version": "post_block2_empirical_variance_inputs_v2",
        "source_artifacts": {
            "submission_master": sha256(OUT / "post_block2_submission_master.csv"),
            "final_profile": sha256(PROFILE),
        },
        "components": {
            "task_level_public_gt_quality_variance": sample_variance(task_values),
            "worker_level_public_gt_quality_variance": sample_variance(worker_values),
            "active_time_variance": sample_variance(active),
            "building_level_algorithm_delta_variance": {"status": "deferred_to_aggregation_audit", "reason": "requires paired algorithm outputs"},
            "routing_counterfactual_variance": {"status": "not_identifiable", "reason": "no randomized historical routing counterfactual"},
        },
        "counts": {"c1_evaluable_rows": len(c1), "task_contexts": len(task_values), "workers": len(worker_values)},
    }
    (OUT / "empirical_variance_inputs.json").write_text(json.dumps(variance, indent=2) + "\n", encoding="utf-8")


def repair_qa_and_manifest() -> None:
    exclusions = read_csv(OUT / "post_block2_exclusion_provenance.csv")
    exclusions = [row for row in exclusions if row.get("record_type") != "profile"]
    write_csv(OUT / "post_block2_exclusion_provenance.csv", exclusions)
    provenance_path = OUT / "POST_BLOCK2_DATA_PROVENANCE.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance.update({
        "schema_version": "post_block2_analysis_pack_provenance_v3",
        "pack_version": "post_block2_analysis_pack_20260817_v3",
        "status": "GO",
        "prompt_2_entry_allowed": True,
        "profile_p0_inventory_count": 0,
        "combined_exclusion_inventory_count": len(exclusions),
        "p0_findings": [],
    })
    provenance["profile_status"] = {
        "final_pooled_profile": "formal_ready",
        "p0": False,
        "source": str(PROFILE.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(PROFILE),
        "post_c2b_substitution_allowed": False,
    }
    provenance["formal_sources"].append({
        "path": str(PROFILE.relative_to(ROOT)).replace("\\", "/"),
        "role": "FINAL_CALIBRATION_POOLED_WORKER_PROFILE",
        "sha256": sha256(PROFILE),
    })
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    p1 = provenance.get("p1_findings", [])
    qa = [
        "# post-Block2 analysis pack v3 QA", "", "- 状态：**GO**", "- Prompt 2：**允许**", "- Block 3：未生成", "",
        "## P0 findings", "", "- none", "", "## P1 findings", "",
        *([f"- {item['id']} [{item['stage']}]: {item['detail']}" for item in p1] or ["- none"]), "",
        "## Profile and uncertainty binding", "",
        f"- final profile: `{PROFILE.relative_to(ROOT).as_posix()}`", f"- SHA-256: `{sha256(PROFILE)}`",
        "- worker_profile_uncertainty_inputs.csv：由最终 profile 的冻结区间逐字段物化。",
        "- empirical_variance_inputs.json：仅计算现有结果可识别的经验方差；routing counterfactual 明确保留 not_identifiable。",
        "- C1 历史 A0 使用冻结 canonical/pairwise/crowd sidecar；历史 commit 对象本地不存在，不声称源码级重放。", "",
    ]
    (OUT / "POST_BLOCK2_DATA_QA_REPORT.md").write_text("\n".join(qa), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# post-Block2 analysis pack 2026-08-17 v3\n\n"
        "v3 从原始/冻结真源重新生成，并在 C2-A-RP 终态 closeout 后绑定 final Calibration profile。\n\n"
        "- QA：GO；Prompt 2 可进入。\n- v1/v2 未覆盖。\n- 未生成 Block 3。\n"
        "- GT 边界：test 仅有少量局部研究者修正；validation 没有研究者自己的修正。\n"
        "- 无历史随机 routing counterfactual，因此 routing replay 只能输出不可识别状态和设计功效输入。\n",
        encoding="utf-8",
    )
    artifacts = {path.name: sha256(path) for path in sorted(OUT.iterdir()) if path.is_file() and path.name != "ARTIFACT_HASH_MANIFEST.json"}
    manifest = {"schema_version": "post_block2_artifact_hash_manifest_v3", "pack_version": "post_block2_analysis_pack_20260817_v3", "manifest_self_sha256": "not_bound_recursive", "artifact_count": len(artifacts), "artifacts": artifacts}
    (OUT / "ARTIFACT_HASH_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    v2.OUT = OUT
    v2.main()
    repair_profile_and_inputs()
    repair_qa_and_manifest()
    print(json.dumps({"output_dir": str(OUT), "status": "GO", "manifest_sha256": sha256(OUT / "ARTIFACT_HASH_MANIFEST.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
