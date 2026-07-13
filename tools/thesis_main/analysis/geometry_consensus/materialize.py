from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows

from .loo import leave_one_out
from .pairwise import pairwise_similarity
from .representation import normalize_geometry
from .stability import stability_summary


RULE_VERSION = "geometry_loo_candidate_v2"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def materialize_geometry_consensus(
    geometry_jsonl: Path,
    output_dir: Path,
    *,
    input_status: str = "dry_run",
    width: int = 1024,
    height: int = 512,
) -> dict[str, Any]:
    source_sha = sha256_file(geometry_jsonl)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    normalized_rows = []
    for row in _read_jsonl(geometry_jsonl):
        geometry = normalize_geometry(row.get("corners_px") or [], width=width, height=height)
        record = {**row, "geometry": geometry}
        if str(row.get("canonical_eligibility_status", "valid")) != "valid" or not str(row.get("base_task_id", "")).strip():
            record["geometry"]["valid"] = False
            record["geometry"]["reason"] = "canonical_or_base_task_invalid"
        provenance_context = str(row.get("provenance_context") or row.get("initialization_artifact_id") or row.get("reference_semantics_version") or "").strip()
        key = (str(row.get("base_task_id", "")), str(row.get("condition", "")), str(row.get("schema_version", "")), provenance_context)
        grouped[key].append(record)
        normalized_rows.append(record)
    pairwise_rows = []
    loo_rows = []
    stability_rows = []
    coverage_rows = []
    for (base_task_id, condition, schema_version, provenance_context), records in sorted(grouped.items()):
        valid = [row for row in records if row["geometry"].get("valid")]
        task_pairwise_count = 0
        for index, left in enumerate(valid):
            for right in valid[index + 1 :]:
                metrics = pairwise_similarity(left["geometry"], right["geometry"])
                task_pairwise_count += 1
                pairwise_rows.append(
                    {
                        **metrics,
                        **sidecar_common(source_artifact=str(geometry_jsonl), source_sha256=source_sha, condition=condition, pool=left.get("pool", ""), validity_status="dry_run" if input_status != "formal" else metrics["validity_status"], rule_version=RULE_VERSION),
                        "base_task_id": base_task_id, "geometry_context_schema_version": schema_version, "geometry_context_provenance": provenance_context,
                        "worker_id_left": left.get("worker_id", ""),
                        "worker_id_right": right.get("worker_id", ""),
                    }
                )
        loo = leave_one_out(records)
        for row in loo:
            loo_rows.append(
                {
                        **row,
                        **sidecar_common(source_artifact=str(geometry_jsonl), source_sha256=source_sha, condition=condition, pool="", validity_status="dry_run" if input_status != "formal" else row["validity_status"], rule_version=RULE_VERSION),
                        "base_task_id": base_task_id, "geometry_context_schema_version": schema_version, "geometry_context_provenance": provenance_context,
                }
            )
        summary = stability_summary(records)
        stability_rows.append(
            {
                **sidecar_common(source_artifact=str(geometry_jsonl), source_sha256=source_sha, condition=condition, validity_status="dry_run" if input_status != "formal" else summary["stability_status"], rule_version=RULE_VERSION),
                "base_task_id": base_task_id, "geometry_context_schema_version": schema_version, "geometry_context_provenance": provenance_context,
                **summary,
            }
        )
        coverage_rows.append(
            {
                **sidecar_common(source_artifact=str(geometry_jsonl), source_sha256=source_sha, condition=condition, validity_status="dry_run" if input_status != "formal" else "valid", rule_version=RULE_VERSION),
                "base_task_id": base_task_id, "geometry_context_schema_version": schema_version, "geometry_context_provenance": provenance_context,
                "n_observations": len(records),
                "valid_geometry_k": len(valid),
                "invalid_geometry_k": len(records) - len(valid),
                "pairwise_metric_coverage": f"{task_pairwise_count}/{max(1, len(records) * (len(records) - 1) // 2)}",
                "interpretation_allowed": "false",
            }
        )
    fields = COMMON_SIDEcar_FIELDS
    write_csv_rows(output_dir / "geometry_pairwise_similarity_C1.csv", pairwise_rows, fields + ["base_task_id", "geometry_context_schema_version", "geometry_context_provenance", "worker_id_left", "worker_id_right", "metric_compatible", "order_compatible", "boundary_similarity", "wallwall_similarity", "q_boundary", "q_wallwall", "left_pair_count", "right_pair_count"])
    write_csv_rows(output_dir / "geometry_worker_task_loo_C1.csv", loo_rows, fields + ["base_task_id", "geometry_context_schema_version", "geometry_context_provenance", "task_id", "worker_id", "held_out_valid", "peer_count_excluding_self", "valid_k", "loo_boundary_median", "loo_wallwall_median", "q_boundary_median", "q_wallwall_median", "loo_boundary_values_json", "loo_wallwall_values_json"])
    write_csv_rows(output_dir / "geometry_stability_C1.csv", stability_rows, fields + ["base_task_id", "geometry_context_schema_version", "geometry_context_provenance", "valid_k", "boundary_similarity_mean", "boundary_similarity_min", "wallwall_similarity_mean", "wallwall_similarity_min", "q_boundary_mean", "q_boundary_min", "q_wallwall_mean", "q_wallwall_min", "boundary_mode_count", "wallwall_mode_count", "boundary_largest_gap", "wallwall_largest_gap", "medoid_margin_boundary", "medoid_margin_wallwall", "leave_two_out_status", "medoid_worker_id", "stability_status", "interpretation_allowed"])
    write_csv_rows(output_dir / "geometry_metric_coverage_C1.csv", coverage_rows, fields + ["base_task_id", "geometry_context_schema_version", "geometry_context_provenance", "n_observations", "valid_geometry_k", "invalid_geometry_k", "pairwise_metric_coverage"])
    return {"n_geometry_rows": len(normalized_rows), "n_tasks": len(grouped), "n_pairwise_rows": len(pairwise_rows), "dry_run": input_status != "formal", "interpretation_allowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize candidate-only Geometry LOO sidecars.")
    parser.add_argument("--geometry-jsonl", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_geometry_consensus(args.geometry_jsonl, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
