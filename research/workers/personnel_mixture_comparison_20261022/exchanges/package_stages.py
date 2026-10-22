#!/usr/bin/env python3
"""Package actual, frozen exchange results with byte hashes; no recomputation."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
COMMIT = "ef148c82df18582228b2d23837faa2659e79eba7"
PREFIX = "research/workers/personnel_mixture_comparison_20261022"


def available_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file()
                  and not any(part == "__pycache__" or part == ".cache" for part in p.relative_to(ROOT).parts)
                  and not p.name.endswith((".tmp", ".pyc", ".pyo"))
                  and p.name != "FILE_INDEX.csv")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def package(label, paths, target, coverage, dependencies):
    members = [{"path": p.relative_to(REPO).as_posix(), "bytes": p.stat().st_size,
                "sha256": sha256(p)} for p in paths]
    manifest = {
        "package": label, "source_commit": COMMIT, "bottom_data": "real_v2",
        "version_note": "v3 in historical package names is research round, not a different dataset",
        "new_fusion_calls": 0, "coverage": coverage, "dependencies": dependencies,
        "packaged_file_count_excluding_manifest": len(members),
        "uncompressed_member_bytes_excluding_manifest": sum(m["bytes"] for m in members),
        "excluded": ["*.tmp", "*.pyc", "*.pyo", "__pycache__", ".cache"],
        "members": members,
    }
    manifest_name = f"{PREFIX}/DELIVERY_{label}_MANIFEST.json"
    tmp = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", allowZip64=True) as z:
        for p, m in zip(paths, members):
            z.write(p, arcname=m["path"], compress_type=zipfile.ZIP_STORED if p.suffix == ".gz" else zipfile.ZIP_DEFLATED,
                    compresslevel=None if p.suffix == ".gz" else 6)
        z.writestr(manifest_name, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                   compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    tmp.replace(target)
    with zipfile.ZipFile(target) as z:
        error = z.testzip()
        assert error is None, (target, error)
        assert set(z.namelist()) == {m["path"] for m in members} | {manifest_name}
    return {"file": str(target), "bytes": target.stat().st_size, "sha256": sha256(target),
            "content_files": len(members), "manifest": manifest_name, "zip_crc": "all_members_passed",
            "coverage": coverage}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    files = available_files()
    with (ROOT / "FILE_INDEX.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "bytes"])
        writer.writeheader()
        writer.writerows({"file": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size} for p in files)
    indexed = list(csv.DictReader((ROOT / "FILE_INDEX.csv").open(encoding="utf-8-sig")))
    assert {r["file"] for r in indexed} == {p.relative_to(ROOT).as_posix() for p in files}
    assert all((ROOT / r["file"]).stat().st_size == int(r["bytes"]) for r in indexed)

    stage_a = [p for p in files if p.relative_to(ROOT).parts[0] != "finite_pair_comparison"]
    stage_a.append(ROOT / "FILE_INDEX.csv")
    stage_b = [p for p in files if p.relative_to(ROOT).parts[0] == "finite_pair_comparison"]
    # Intentional small code duplication lets both packages use the same repo-relative paths.
    stage_b += [ROOT / "compare_finite_panel_pairs.py", ROOT / "make_selected_pair_table.py"]
    assert set(files).issubset(set(stage_a) | set(stage_b))

    coverage_a = {
        "strict_ABC_registered_rows": 146031, "strict_ABC_unique_physical_triples": 138244,
        "strict_ABC_conditions": 85, "strict_ABC_batches": ["manual_joint_A", "manual_joint_B", "manual_structure", "semi_joint"],
        "strict_ABC_used_unique_endpoint_keys": 100530,
        "legacy_n20_rows": 271331, "legacy_manual_rows": 269814, "legacy_semi_rows": 1517,
        "legacy_source_shards": 165, "legacy_fine_parent_m_conditions": 76,
        "contents": "exact A/B/C/D/X/Y/Z + scalar contrasts and quality/time/structure expressions, all directions and registered scales, global/image/building/background aggregates, full failure/negative/null rows, code/readme/receipts and historical reuse indices",
        "finite_pair_statistics": "in STAGE03B, not duplicated here",
        "gzip_integrity": "existing GZIP_INTEGRITY_CHECK.json reports 89 complete streams, no errors; packaging does not rerun research",
    }
    coverage_b = {
        "finite_panels": 336, "teams_per_panel": 924,
        "unique_saved_endpoints": 310458,
        "unordered_panel_pair_exposures_before_label_masks": 143279136,
        "actual_m": [1, 2, 3, 4, 5, 6], "conditions": ["Manual", "Semi"],
        "classification_views": ["coarse", "fine_all_changes", "fine_parent_fixed"],
        "fine_parent_stratification_version": 2,
        "contents": "all available n/m/metric summaries, exact D/m and parent-vector background strata in complete batches, panel/image/building results, pair and label coverage, m/r response, code/readme and 12-row Chinese selected table",
        "not_included": "143 million explicit repeated pair rows; regenerate deterministically from exact panel members and saved endpoints in configurations package; no full-pool exhaustion claim",
    }
    results = [
        package("STAGE03A", sorted(stage_a), args.dest / "HOHONET_personnel_stage03A_exchanges_v2data_20261022.zip",
                coverage_a, [
                    f"{PREFIX}/inputs/CLOSURE_ENDPOINT_EXPRESSIONS.csv.gz and its source manifest (root-managed input package)",
                    "frozen source labels, registration requests and closure endpoint archives referenced by exact file/row keys in each README",
                    "legacy_n20/SOURCE_SHARDS.csv references restored historical source shards; exact narrow event links and outcomes are included here",
                ]),
        package("STAGE03B", sorted(stage_b), args.dest / "HOHONET_personnel_stage03B_finite_pairs_v2data_20261022.zip",
                coverage_b, [
                    f"{PREFIX}/configurations/PANELS_USED.csv",
                    f"{PREFIX}/configurations/TEAM_MEMBERS.csv.gz and PANEL_TEAMS.csv.gz",
                    f"{PREFIX}/configurations/TEAM_CONFIGURATION_LINKS.csv.gz and PANEL_CONFIGURATION_CENSUS.csv.gz",
                    f"{PREFIX}/configurations/ENDPOINT_OUTCOMES_manual.csv.gz and ENDPOINT_OUTCOMES_semi.csv.gz",
                ]),
    ]
    receipt = {"source_commit": COMMIT, "indexed_source_files": len(indexed),
               "indexed_bytes": sum(int(r["bytes"]) for r in indexed),
               "all_indexed_files_packaged": True, "packages": results}
    (args.dest / "HOHONET_personnel_stage03_delivery_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
