from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


INTERNAL_FIELDS = [
    "worker_id", "public_worker_code", "task_id", "task_code", "zh_task_code",
    "inner_id", "planned_project_code", "assignment_batch_id",
    "expected_completion_order", "selected_design_sha", "source_assignment_sha256",
    "source_import_sha256", "internal_only",
]
ZH_FIELDS = ["public_worker_code", "worker_name", "task_code"]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public(worker_id: str) -> str:
    return f"W{int(worker_id):03d}"


def build_release(assignment: Path, planned_import: Path, c1_release: Path, output: Path) -> dict:
    assignments = _read_csv(assignment)
    imports = json.loads(planned_import.read_text(encoding="utf-8"))
    import_rows = [item.get("data", {}) for item in imports if isinstance(item, dict)]
    task_order = {str(row.get("planned_task_id", "")): index for index, row in enumerate(import_rows, 1)}
    if len(task_order) != len(import_rows) or not task_order:
        raise ValueError("planned import task IDs must be complete and unique")
    if any(row.get("task_id", "") not in task_order for row in assignments):
        raise ValueError("assignment contains a task outside the planned import")
    design_shas = {str(row.get("selected_design_sha", "")) for row in import_rows} - {""}
    batch_ids = {str(row.get("c2b_batch_id", "")) for row in import_rows} - {""}
    if len(design_shas) != 1 or batch_ids != {"C2B_BATCH_A"}:
        raise ValueError("planned import lacks one frozen D8 design/batch identity")

    overseas = {path.stem.removeprefix("worker_W") for path in c1_release.glob("worker_W*.csv")}
    zh_source = _read_csv(c1_release / "worker_facing_distribution_zh_merged_v3_1.csv")
    zh_names = {row["public_worker_code"]: row["worker_name"] for row in zh_source}
    workers = {_public(row["worker_id"]) for row in assignments}
    if any((worker[1:] in overseas) == (worker in zh_names) for worker in workers):
        raise ValueError("every assigned worker must map to exactly one C1 language release group")

    assignment_sha, import_sha = _sha(assignment), _sha(planned_import)
    per_worker_order: dict[str, int] = {}
    internal: list[dict[str, str]] = []
    for row in assignments:
        worker_id = str(int(row["worker_id"]))
        public = _public(worker_id)
        per_worker_order[public] = per_worker_order.get(public, 0) + 1
        inner = task_order[row["task_id"]]
        internal.append({
            "worker_id": worker_id,
            "public_worker_code": public,
            "task_id": row["task_id"],
            "task_code": f"D-{inner:03d}",
            "zh_task_code": f"任务4-{inner:03d}",
            "inner_id": str(inner),
            "planned_project_code": "D",
            "assignment_batch_id": row.get("assignment_batch_id", "C2B_BATCH_A"),
            "expected_completion_order": str(per_worker_order[public]),
            "selected_design_sha": next(iter(design_shas)),
            "source_assignment_sha256": assignment_sha,
            "source_import_sha256": import_sha,
            "internal_only": "true",
        })

    output.mkdir(parents=True, exist_ok=True)
    internal_dir = output / "internal"
    _write_csv(internal_dir / "worker_distribution_internal_C2B_D8.csv", INTERNAL_FIELDS, internal)
    zh_rows: list[dict[str, str]] = []
    index_rows: list[dict[str, str]] = []
    for public in sorted(workers, key=lambda value: int(value[1:])):
        rows = [row for row in internal if row["public_worker_code"] == public]
        if public[1:] in overseas:
            filename = f"worker_{public}.csv"
            _write_csv(output / filename, ["task_code"], [{"task_code": row["task_code"]} for row in rows])
            language = "English"
        else:
            filename = "任务分发表_C2B_D8.xlsx"
            zh_rows.extend({"public_worker_code": public, "worker_name": zh_names[public], "task_code": row["zh_task_code"]} for row in rows)
            language = "Chinese"
        index_rows.append({"public_worker_code": public, "language_group": language, "task_count": str(len(rows)), "release_file": filename})
    _write_csv(internal_dir / "worker_facing_distribution_zh_merged_C2B_D8.csv", ZH_FIELDS, zh_rows)
    _write_csv(internal_dir / "worker_facing_distribution_index_C2B_D8.csv", ["public_worker_code", "language_group", "task_count", "release_file"], index_rows)

    public_pairs = {(row["public_worker_code"], row["task_code"]) for row in internal}
    zh_backlinks = {(row["public_worker_code"], row["task_code"].replace("任务4", "D", 1)) for row in zh_rows}
    overseas_backlinks = set()
    for public in workers:
        if public[1:] in overseas:
            overseas_backlinks.update((public, row["task_code"]) for row in _read_csv(output / f"worker_{public}.csv"))
    audit = {
        "schema_version": "paper_a_c2b_worker_facing_distribution_audit_v1",
        "passed": public_pairs == zh_backlinks | overseas_backlinks and len(internal) == len(assignments),
        "entry_mapping": {"D": "C2B_BATCH_A", "任务4": "C2B_BATCH_A"},
        "display_mapping_rule": "A=1,B=2,C=3,D=4; current C2-B uses D/任务4 only",
        "assignment_row_count": len(assignments),
        "internal_row_count": len(internal),
        "worker_count": len(workers),
        "zh_worker_count": sum(worker in zh_names for worker in workers),
        "overseas_worker_count": sum(worker[1:] in overseas for worker in workers),
        "task_count_per_worker": sorted({sum(row["public_worker_code"] == worker for row in internal) for worker in workers}),
        "assignment_sha256": assignment_sha,
        "planned_import_sha256": import_sha,
        "selected_design_sha": next(iter(design_shas)),
        "worker_facing_fields": {"Chinese_workbook": ["order", "task_code"], "English": ["task_code"]},
        "internal_chinese_workbook_source_fields": ZH_FIELDS,
        "assignment_truth_source": "assignment_manifest_C2B.csv",
        "worker_facing_release_is_display_only": True,
    }
    (internal_dir / "worker_facing_distribution_audit_C2B_D8.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not audit["passed"]:
        raise ValueError("worker-facing release failed backlink audit")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--planned-import", type=Path, required=True)
    parser.add_argument("--c1-release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_release(args.assignment, args.planned_import, args.c1_release, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
