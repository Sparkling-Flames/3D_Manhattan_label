"""Select completed deliverables; omit caches and already archived main inputs.

This writes selections only. package_and_verify.py builds the ZIPs and validates
their actual members. The same validator must then read downloaded ZIP bytes.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import re


def main(base):
    base = base.resolve()
    prerequisites = [
        "new_endpoints26/POSTEXEC_RECEIPT.json",
        "analysis_precision26/results_stage2/NATURAL_FINALIZATION_COMPLETE.json",
        "analysis_policy26/results/RECEIPT.json",
        "analysis_geometry26/results_stage2/RUN_RECEIPT.json",
        "analysis_geometry26/results_stage2/SUMMARY_RECEIPT.json",
        "analysis_reporting26/ROOT_ANALYSES_COMPLETE.json",
        "delivery26/FINAL_PATH_LINK_VALIDATION.json",
    ]
    for name in prerequisites:
        if not (base / name).is_file():
            raise FileNotFoundError(name)
    report = base / "REPORT_ZH.md"
    text = report.read_text()
    assert not re.search(r"\{\{[A-Z_]+\}\}", text), "Unfilled report result field"
    assert "编辑整合稿，不是全量完成回执" not in text
    execution = json.loads((base / prerequisites[0]).read_text())
    assert execution["complete"] and execution["new_unique_endpoints"] == 1356657
    geometry = json.loads((base / prerequisites[3]).read_text())
    assert geometry["pools"] == 194 and geometry["uncomputed_links"] == 0

    report_code = set()
    analysis_data = set()

    def add(target, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        target.add(str(path.relative_to(base)))

    for name in ["REPORT_ZH.md", "README.md", "FROZEN_EXTENSION_DESIGN.json",
                 "INPUT_VERSION.json", "FINAL_SOURCE_CHECK.json", "CURRENT_BASELINE_ADOPTION_ZH.md",
                 "SOURCE_ADOPTION26.json", "report26/REPRODUCE.md",
                 "report26/RESEARCH_DESK_FIELDS_ZH.md", "report26/requirements.txt",
                 "report26/DELIVERY_REPRO_NOTES_ZH.md", "report26/DELIVERY_REPRO_CHECK.json",
                 "report26/assemble_key_tables.py", "report26/KEY_TABLES_REPRODUCE_ZH.md",
                 "report26/KEY_TABLE_SCHEMA_CONTRACT.json",
                 "report26/render_integrated_report.mjs", "assets/FONT_SOURCE.json",
                 "design26/POOL_SAMPLING_PLAN.csv", "design26/REGISTRATION_RECEIPT.json",
                 "design26/FAILED_EXPORTS_EXCLUDED.json"]:
        add(report_code, base / name)
    for directory in ["engine26", "analysis_precision26", "analysis_policy26",
                      "analysis_geometry26", "analysis_shape26", "analysis_reporting26"]:
        for file in (base / directory).iterdir():
            if file.is_file() and file.suffix in (".py", ".md"):
                add(report_code, file)
    for file in (base / "analysis_geometry26/quantile_boundary_note").glob("*.py"):
        add(report_code, file)
    for file in (base / "report26").glob("*.py"):
        add(report_code, file)
    if (base / "report26/POLICY32_COMPLETED_FINDINGS_ZH.md").exists():
        add(report_code, base / "report26/POLICY32_COMPLETED_FINDINGS_ZH.md")
    for name in ["engine26/FIELD_CONTRACT.json", "engine26/FROZEN_BLOCK_PROJECTION_CHECK.json",
                 "engine26/INTERRUPTION_RECOVERY_EVIDENCE.json",
                 "delivery26/package_and_verify.py", "delivery26/validate_final_path_links.py",
                 "delivery26/FINAL_INDEX_MODE_ZH.md", "delivery26/FINAL_INDIVIDUAL_DELIVERIES.template.json",
                 "delivery26/update_delivery_index.py",
                 "delivery26/prepare_final_packages.py", "delivery26/finalize_root_analyses.py", "delivery26/finalize_geometry_after_native.py"]:
        add(report_code, base / name)
    for directory in ["report26/key_tables", "report26/figures", "report26/final_integration"]:
        if (base / directory).exists():
            for file in (base / directory).rglob("*"):
                if file.is_file() and not {"__pycache__", ".matplotlib_cache"}.intersection(file.parts):
                    add(report_code, file)
    for name in ["report26/REPORT.html", "report26/CLAIMS_INDEX_ZH.csv",
                 "report26/OLD_NEW_CONCLUSIONS.csv", "report26/FINAL_REPORT_RECEIPT.json",
                 "report26/HTML_RENDER_RECEIPT.json"]:
        add(report_code, base / name)

    result_dirs = [
        "analysis_precision26/results_stage2", "analysis_precision26/figures_stage2",
        "analysis_precision26/design_diagnostics",
        "analysis_policy26/results", "analysis_policy26/presentation",
        "analysis_policy26/restored_components", "analysis_geometry26/results_stage2",
        "analysis_geometry26/figures",
        "analysis_geometry26/low_k_cases", "analysis_geometry26/final_handoff26",
        "analysis_geometry26/quantile_boundary_note",
        "analysis_shape26/results", "analysis_reporting26/results", "analysis_reporting26/thresholds",
        "report26/policy32_evidence",
    ]
    excluded = {"pool_checkpoints", "bootstrap_cache", "parts", "checkpoints",
                "cache", "__pycache__", "inputs_old16"}
    allowed = (".csv", ".csv.gz", ".json", ".json.gz", ".jsonl.gz", ".md", ".png", ".pdf")
    for directory in result_dirs:
        folder = base / directory
        if not folder.exists():
            raise FileNotFoundError(folder)
        for file in folder.rglob("*"):
            if (file.is_file() and file.name.endswith(allowed)
                    and not set(file.relative_to(folder).parts) & excluded
                    and "PRIVATE" not in file.name
                    and not file.name.startswith(("WATCH_", "PROGRESS_"))):
                add(analysis_data, file)
    for name in prerequisites + [
        "new_endpoints26/COMPLETE_EXECUTION_VALIDATION.json",
        "new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz",
        "new_endpoints26/FINAL_EXECUTION_LEDGER.json",
        "new_endpoints26/FINAL_POOL_EXECUTION_LEDGER.csv.gz",
        "new_endpoints26/FINAL_EXECUTION_STATUS_COUNTS.csv.gz",
        "analysis_policy26/COMMON_IMAGES.csv",
        "analysis_geometry26/POOL_META.csv",
        "analysis_precision26/SEED_EXPORT_CORRECTION.json",
        "analysis_geometry26/BASELINE_NONCOMPLETE_WITHOUT_GEOMETRY.csv",
        "assets/NotoSansCJKsc-Regular.otf", "assets/NotoCJK_OFL.txt", "assets/FONT_SOURCE.json",
    ]:
        add(analysis_data, base / name)
    for name in ["analysis_geometry26/PARALLEL_FINISH_RESUME.json",
                 "analysis_geometry26/OWNED_OLD_WORKER_CLOSEOUT.json",
                 "analysis_geometry26/GEOMETRY_FINALIZATION_COMPLETE.json"]:
        if (base / name).exists():
            add(analysis_data, base / name)
    for stage in (1, 2):
        for name in ["RUN_RECEIPT.json", "PREFIX_COMPILE_RECEIPT.json"]:
            add(analysis_data, base / f"new_endpoints26/stage{stage}" / name)

    deliver = base / "delivery26"
    packages = {"S10_report_code": sorted(report_code), "S11_analysis_results": sorted(analysis_data)}
    manifest = []
    for package, paths in packages.items():
        selection = dict(package=package, paths=paths,
            repository_root_prefix="research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026",
            old_large_inputs_included=False, rebuildable_bootstrap_cache_included=False,
            exact_design_package="HOHONET_20261026_S01_exact_design.zip",
            new_endpoint_packages="HOHONET_20261026_DATA_S1_* and DATA_S2_*; all listed parts required")
        target = deliver / (package + "_SELECTION.json")
        target.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n")
        for name in paths:
            file = base / name
            with file.open("rb") as handle:
                sha = hashlib.file_digest(handle, "sha256").hexdigest()
            manifest.append(dict(package=package, relative_path=name, bytes=file.stat().st_size, sha256=sha))
    table = io.StringIO(newline="")
    writer = csv.DictWriter(table, fieldnames=["package", "relative_path", "bytes", "sha256"])
    writer.writeheader()
    writer.writerows(manifest)
    (deliver / "FINAL_SELECTED_FILE_MANIFEST.csv").write_text(table.getvalue())
    print(json.dumps({key: len(value) for key, value in packages.items()}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    main(parser.parse_args().base)
