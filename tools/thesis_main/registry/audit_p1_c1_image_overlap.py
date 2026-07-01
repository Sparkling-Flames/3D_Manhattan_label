from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

try:
    from tools.thesis_main.registry.calibration_launch_common import (
        load_calibration_manifest_tasks,
        load_ls_import_tasks,
        safe,
        write_csv,
        write_json,
    )
except ModuleNotFoundError:  # direct `python tools/...py`
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from tools.thesis_main.registry.calibration_launch_common import (
        load_calibration_manifest_tasks,
        load_ls_import_tasks,
        safe,
        write_csv,
        write_json,
    )


OVERLAP_KEYS = ["task_id", "base_task_id", "image_id", "title_stem", "image_stem", "image_hash"]


def _index(rows: list[dict[str, str]]) -> dict[str, dict[str, set[str]]]:
    index: dict[str, dict[str, set[str]]] = {key: defaultdict(set) for key in OVERLAP_KEYS}
    for row in rows:
        label = f"{safe(row.get('dataset_group'))}:{safe(row.get('task_id'))}"
        for key in OVERLAP_KEYS:
            value = safe(row.get(key))
            if value:
                index[key][value].add(label)
    return index


def _task_count(rows: list[dict[str, str]]) -> int:
    return len({f"{safe(row.get('dataset_group'))}:{safe(row.get('task_id'))}" for row in rows if safe(row.get("task_id"))})


def audit_overlap(prescreen_imports: list[Path], calibration_manifest: Path) -> dict:
    p1_rows: list[dict[str, str]] = []
    for path in prescreen_imports:
        p1_rows.extend(load_ls_import_tasks(path))
    c1_sets = load_calibration_manifest_tasks(calibration_manifest)
    c1_rows = [row for group in ("Calibration_anchor", "Calibration_core", "Calibration_reserve") for row in c1_sets.get(group, [])]
    source_imports = {safe(row.get("source_import_json")) for row in c1_rows if safe(row.get("source_import_json"))}
    for source in sorted(source_imports):
        path = Path(source)
        if not path.exists():
            path = calibration_manifest.parent / source
        if path.exists():
            c1_rows.extend(load_ls_import_tasks(path))

    p1_index = _index(p1_rows)
    c1_index = _index(c1_rows)
    overlap_rows: list[dict[str, object]] = []
    for key in OVERLAP_KEYS:
        for value in sorted(set(p1_index[key]).intersection(c1_index[key])):
            overlap_rows.append(
                {
                    "overlap_key": key,
                    "overlap_value": value,
                    "p1_tasks": "|".join(sorted(p1_index[key][value])),
                    "calibration_tasks": "|".join(sorted(c1_index[key][value])),
                }
            )

    blockers = ["p1_calibration_overlap"] if overlap_rows else []
    warnings = []
    if not any(safe(row.get("image_hash")) for row in p1_rows + c1_rows):
        warnings.append("source_image_hash_not_available")
    return {
        "passed": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "counts": {
            "prescreen_tasks": _task_count(p1_rows),
            "calibration_tasks": _task_count(c1_rows),
            "overlap_rows": len(overlap_rows),
        },
        "overlap_counts": {key: sum(1 for row in overlap_rows if row["overlap_key"] == key) for key in OVERLAP_KEYS},
        "overlaps": overlap_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit PreScreen vs Calibration task/image overlap before C1 launch.")
    parser.add_argument("--prescreen-import", action="append", required=True, type=Path)
    parser.add_argument("--calibration-manifest", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()

    summary = audit_overlap(args.prescreen_import, args.calibration_manifest)
    if args.output_json:
        write_json(args.output_json, summary)
    else:
        print(summary)
    if args.output_csv:
        write_csv(args.output_csv, ["overlap_key", "overlap_value", "p1_tasks", "calibration_tasks"], summary["overlaps"])
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
