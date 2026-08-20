"""Build a self-contained, SHA-verified Paper A data-mining directory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RAW_MANIFEST = ROOT / "export_label" / "RAW_DATA_PACKAGE_MANIFEST_20260817.json"
CURATED = ROOT / "analysis_results" / "paper_a_data_discovery_20260820_v1"
DEFAULT_OUTPUT = ROOT / "analysis_results" / "paper_a_data_mining_package_20260820_v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def collect_entries() -> list[dict[str, Any]]:
    raw_manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8-sig"))
    if raw_manifest.get("real_name_spreadsheets_included") or raw_manifest.get("legacy_included"):
        raise ValueError("raw manifest unexpectedly includes real-name or legacy data")
    current_raw_shas = {
        row["sha256"] for row in read_csv(CURATED / "data_catalog.csv")
        if row.get("included") == "true" and row.get("role") in {"raw_label_studio_export", "raw_active_log"}
    }
    entries: list[dict[str, Any]] = []
    for item in raw_manifest["files"]:
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT.resolve()) or not source.is_file():
            raise FileNotFoundError(f"unsafe or missing raw source: {item['path']}")
        observed = sha256_file(source)
        if source.stat().st_size != item["size_bytes"] or observed != item["sha256"]:
            raise ValueError(f"raw source drift: {item['path']}")
        entries.append({
            "package_path": f"raw/{item['path']}", "source_path": item["path"], "source": source,
            "category": item["category"], "role": "original_raw_data",
            "included_in_current_materialization": str(observed in current_raw_shas).lower(),
        })

    for source in sorted(path for path in CURATED.iterdir() if path.is_file()):
        entries.append({
            "package_path": f"curated/{source.name}", "source_path": source.relative_to(ROOT).as_posix(), "source": source,
            "category": "curated_output", "role": "materialized_fact_or_audit",
            "included_in_current_materialization": "true",
        })

    support = [
        (RAW_MANIFEST, "source_manifests/RAW_DATA_PACKAGE_MANIFEST_20260817.json", "source_manifest"),
        (ROOT / "docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json", "contracts/PAPER_A_METHOD_CONTRACT_CURRENT.json", "method_contract"),
        (ROOT / "docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.md", "contracts/PAPER_A_METHOD_CONTRACT_CURRENT.md", "method_contract_render"),
        (ROOT / "docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md", "contracts/STATISTICAL_ANALYSIS_PLAN_v1.md", "statistical_plan"),
        (Path(__file__), "reproduction/build_paper_a_data_mining_package.py", "package_builder"),
        (ROOT / "tools/thesis_main/analysis/materialize_paper_a_data_discovery.py", "reproduction/materialize_paper_a_data_discovery.py", "materializer"),
        (ROOT / "tests/test_materialize_paper_a_data_discovery.py", "reproduction/test_materialize_paper_a_data_discovery.py", "regression_test"),
    ]
    for source, package_path, role in support:
        if not source.is_file():
            raise FileNotFoundError(source)
        entries.append({
            "package_path": package_path, "source_path": source.relative_to(ROOT).as_posix(), "source": source,
            "category": "documentation_or_reproduction", "role": role,
            "included_in_current_materialization": "not_applicable",
        })
    names = [entry["package_path"] for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError("duplicate package path")
    return sorted(entries, key=lambda entry: entry["package_path"])


def readme(entries: list[dict[str, Any]]) -> bytes:
    categories = Counter(entry["category"] for entry in entries)
    text = f"""# Paper A 数据查阅与挖掘包

本包同时保留原始数据与客观物化结果，不包含 Paper B，不构造 T1/V1 outcome，也不提供主观价值或证据等级排序。

## 内容

- `raw/`：{sum(value for key, value in categories.items() if key in {'frozen_active_time', 'label_studio_export', 'ground_truth_export'})} 个原始文件；来源为冻结 raw package manifest。
  - 29 个 Label Studio export：正式分析使用其中 18 个（2,513 条 annotation）；其余 11 个历史/非正式 export 只供追溯。
  - 104 个 active-time 文件：其中 99 个 JSONL 共 34,417 条 event，另 5 个为 audit JSON。
  - 9 个 ground-truth export；本次关联扫描未静默把它们当作 worker outcome。
- `curated/`：{categories['curated_output']} 个整理结果，包括 submission/task/worker/review facts、2,513 条 raw annotation、34,417 条 raw event、3,735 个 session context、3,668 条字段账本、关系矩阵及审计 manifest。
- `contracts/`：方法合同与统计分析计划。
- `reproduction/`：物化脚本、打包脚本和回归测试。
- `PACKAGE_MANIFEST.csv`：包内每个文件的来源、大小和 SHA-256。

## 查阅顺序

1. 先读 `curated/PAPER_A_DATA_DISCOVERY_REPORT_ZH.md`。
2. 用 `curated/raw_field_usage_ledger.csv` 查字段覆盖。
3. 用 `curated/raw_annotation_fact.csv`、`raw_active_event_fact.csv` 和 `raw_active_session_fact.csv` 做数据挖掘。
4. 需要核对原记录时，再按 `source_path` 回到 `raw/`。

## 关键边界

- canonical submission 为 2,501；另外保留 P1 4 条、C1 8 条 raw-only 版本记录。
- C1 raw join 使用 `project + ls_runtime_task_id + worker_id + annotation_id`。
- 6,546 条阶段外日志事件已显式标记，不能按所在目录静默归入阶段。
- Label Studio `lead_time`、event fragment 与正式 owner-valid active time 相互独立。
- 缺失值不是零；`analysis_results/` 是输出，不是输入真源。

## 数据访问

包内含 worker/annotation ID、session、时间戳、任务数据和原始回答。仅向获授权的研究协作者提供；二次共享前应按实际伦理与隐私要求处理。
"""
    return text.encode("utf-8")


def build_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"package directory already exists: {output}")
    entries = collect_entries()
    readme_bytes = readme(entries)
    rows = [{
        "package_path": "README_ZH.md", "source_path": "generated", "category": "documentation",
        "role": "package_guide", "included_in_current_materialization": "not_applicable",
        "size_bytes": len(readme_bytes), "sha256": sha256_bytes(readme_bytes),
    }]
    for entry in entries:
        rows.append({key: entry[key] for key in ("package_path", "source_path", "category", "role", "included_in_current_materialization")} | {
            "size_bytes": entry["source"].stat().st_size, "sha256": sha256_file(entry["source"]),
        })

    output.mkdir(parents=True)
    (output / "README_ZH.md").write_bytes(readme_bytes)
    for entry in entries:
        destination = output / entry["package_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry["source"], destination)
    with (output / "PACKAGE_MANIFEST.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, rows[0].keys(), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)

    expected = {row["package_path"]: row["sha256"] for row in rows}
    for name, expected_sha in expected.items():
        if sha256_file(output / name) != expected_sha: raise AssertionError(f"package hash mismatch: {name}")
    actual_files = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    if actual_files != set(expected) | {"PACKAGE_MANIFEST.csv"}:
        raise AssertionError("package member set mismatch")
    return {"path": str(output), "files": len(actual_files), "bytes": sum(path.stat().st_size for path in output.rglob("*") if path.is_file())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    print(json.dumps(build_package(parser.parse_args().output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
