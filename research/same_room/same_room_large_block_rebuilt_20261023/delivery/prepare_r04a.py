"""Prepare the R04A report/code manifest; this program never creates a ZIP.

Run again after the report is finalized.  Packaging is a separate explicit call
to pack_and_verify.py, which reads every actual ZIP member through EOF.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
WORKSPACE = BASE.parents[1]
OUT = WORKSPACE / "deliverables/HOHONET_rebuilt_20261023"
PREFIX = "research/same_room/same_room_large_block_rebuilt_20261023/"


def digest(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main(final: bool = False, root_extra: list[str] | None = None):
    entries: dict[str, dict] = {}

    def add(path: Path, group: str, archive_path: str | None = None):
        if not path.is_file():
            raise FileNotFoundError(path)
        archive_path = archive_path or PREFIX + str(path.relative_to(BASE))
        if archive_path in entries:
            if Path(entries[archive_path]["source"]) != path:
                raise ValueError((archive_path, path))
            return
        entries[archive_path] = {"source": str(path), "archive_path": archive_path,
                                 "group": group}

    # Final report pages may still be edited by the report owner.  This is an
    # inventory snapshot until the owner explicitly authorizes packaging.
    for pattern in ("*.md", "*.html", "*.csv"):
        for path in sorted(BASE.glob(pattern)):
            if path.name != "R05_README_ZH.md":
                add(path, "report")
    for name in ("EXECUTION_COMPLETION.json", "REPORT_BUILD_RECEIPT.json"):
        add(BASE / name, "report")
    for name in root_extra or []:
        add(BASE / name, "report")

    for path in sorted((BASE / "analysis").iterdir()):
        if path.is_file() and path.suffix in {".py", ".md"}:
            add(path, "analysis_code")

    for folder in ("results", "sensitivity", "history_q", "geometry_summary",
                   "anchor_paths", "direction_tables"):
        for path in sorted((BASE / folder).iterdir()):
            if path.is_file() and path.suffix in {".csv", ".json", ".md"}:
                if path.name == "DIRECTION_DISPLAY_RECEIPT.json":
                    # The exact baseline receipt was preserved in R04B.  The
                    # newly joined small tables have a separate receipt here.
                    continue
                add(path, folder + "_small")

    for path in sorted((BASE / "reader_tables").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            add(path, "reader_tables")

    for path in sorted((BASE / "engine").iterdir()):
        if path.is_file() and path.suffix in {".py", ".md", ".json", ".txt"}:
            add(path, "engine_code_manifest")

    for path in sorted((BASE / "integration").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".log":
            add(path, "integration")
    patched = (BASE / "integration/patched_repo/research/same_room/"
               "same_room_current_classes_v2_20261023/REPORT_ZH.md")
    old_receipt = json.loads((BASE / "integration/HISTORICAL_PATCH_RECEIPT.json").read_text())
    if digest(patched) != old_receipt["patched_sha256"]:
        raise ValueError("Corrected historical report does not match its receipt")
    add(patched, "historical_report_apply_copy",
        "research/same_room/same_room_current_classes_v2_20261023/REPORT_ZH.md")

    for path in sorted((BASE / "figures").iterdir()):
        if path.is_file() and path.suffix in {".png", ".pdf", ".json"}:
            add(path, "main_figures")

    first = BASE / "cases/first_event"
    for name in ("README_ZH.md", "CASE_RECEIPT.json", "CASE_READ_RECEIPT.json",
                 "DEPENDENCIES.json", "requirements.txt"):
        add(first / name, "first_case_readable")
    for folder in ("tables", "figures"):
        for path in sorted((first / folder).rglob("*")):
            if path.is_file():
                add(path, "first_case_readable")

    case_list = BASE / "cases/structure_mechanism/PACKAGE_FILES.csv"
    with case_list.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 57:
        raise ValueError("Unexpected second-case file list; obtain owner confirmation")
    for row in rows:
        path = BASE / row["package_relative_path"]
        if path.stat().st_size != int(row["bytes"]) or digest(path) != row["sha256"]:
            raise ValueError("Second-case file differs from verified list: " + str(path))
        add(path, "second_case_complete")
    add(case_list, "second_case_complete")
    add(BASE / "cases/structure_mechanism/CASE_READ_RECEIPT.json", "second_case_complete")

    # Actual closed archive receipts only.  Do not include upload requests,
    # incomplete .writing files, runtime logs, or an R04A receipt that would
    # recursively refer to itself.
    for path in sorted(OUT.glob("HOHONET_*_包内通读回执.json")):
        if "R04A" not in path.name:
            add(path, "closed_package_eof_receipts", PREFIX + "delivery/receipts/" + path.name)
    for path in sorted(HERE.iterdir()):
        if not path.is_file():
            continue
        include = path.suffix == ".py"
        include |= path.name in {
            "CROSS_PACKAGE_LINK_CONFIG.json", "CROSS_PACKAGE_LINK_VALIDATION.json",
            "GEOMETRY_PACKAGE_ASSIGNMENTS.json", "R04B_ACTUAL_CONTENT_INDEX.csv",
            "REPORT_HTML_RECEIPT.json", "report_style.css",
        }
        include |= (path.name.startswith("GEOMETRY_PART_") and
                    path.name.endswith("_INDEX.csv"))
        if include:
            add(path, "delivery_verification")

    expected_rows = {}
    index = []
    counts = defaultdict(lambda: {"files": 0, "bytes": 0})
    for archive_path, entry in sorted(entries.items()):
        path = Path(entry["source"])
        item = {"archive_path": archive_path, "source": str(path),
                "group": entry["group"], "bytes": path.stat().st_size,
                "sha256": digest(path), "csv_rows": "", "csv_fields": ""}
        if path.suffix == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                count = 0
                for row in reader:
                    count += 1
                    if len(row) != len(header):
                        raise ValueError((path, "wrong CSV row width", count))
            item.update(csv_rows=count, csv_fields=len(header))
            expected_rows[archive_path] = count
        index.append(item)
        counts[entry["group"]]["files"] += 1
        counts[entry["group"]]["bytes"] += item["bytes"]
    pending = []
    if not (BASE / "REPORT_ZH.html").is_file():
        pending.append("REPORT_ZH.html")
    if not root_extra:
        pending.append("Parent-authored new/old comparison: final filename and content")
    if final and pending:
        raise ValueError({"finalization_pending": pending})
    config = {
        "output": str(OUT / "HOHONET_R04A_综合报告图表与完整分析代码.zip"),
        "receipt": str(OUT / "HOHONET_R04A_包内通读回执.json"),
        "entries": [{k: e[k] for k in ("source", "archive_path")} for e in sorted(entries.values(), key=lambda x:x["archive_path"])],
        "expected_rows": expected_rows,
        "status": "final_manifest_authorized_for_separate_packaging" if final else "draft_inventory_only_do_not_package",
        "identity": "new rebuilt study and explicit historical report corrections; not recovery of the missing original 111054-endpoint study",
        "historical_report_copy": "research/same_room/same_room_current_classes_v2_20261023/REPORT_ZH.md is the corrected OLD report, distinct from the new large-block report",
        "omitted": "R01 frozen inputs, R02 complete first-case inputs, R03 population tables, R04B large analyses, R05 scalars, R06 geometry, environments, caches, logs",
    }
    (HERE / "R04A_PACK_MANIFEST.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    with (HERE / "R04A_ACTUAL_CONTENT_INDEX.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(index[0]))
        writer.writeheader()
        writer.writerows(index)
    status = {"status": config["status"], "zip_created": False,
              "files": len(index), "source_bytes": sum(x["bytes"] for x in index),
              "groups": dict(counts), "pending": pending,
              "second_case_listed_files": len(rows), "second_case_sha_checks_passed": True,
              "historical_report_receipt_matched": True,
              "manifest": str(HERE / "R04A_PACK_MANIFEST.json"),
              "note": "Re-run after the report owner finalizes files; no draft snapshot is claimed to be a final deliverable."}
    (HERE / "R04A_PREPARATION_STATUS.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--root-extra", action="append", default=[])
    args = parser.parse_args()
    main(args.final, args.root_extra)
