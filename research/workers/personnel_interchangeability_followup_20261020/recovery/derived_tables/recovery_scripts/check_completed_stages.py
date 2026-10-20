"""Incrementally verify frozen replay outputs and retain a publication manifest."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess
import time

import pandas as pd

R = Path(__file__).resolve().parent
OLD = R.parent / "publication_stage_recovered"
O = R / "verification"
O.mkdir(exist_ok=True)
TARGETS = json.loads((R.parent / "UNAVAILABLE_FILES.json").read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


frozen = json.loads((R / "FROZEN_RECOVERY_INPUTS.json").read_text())
for item in frozen["science_scripts_and_saved_labels"] + frozen["requests"]:
    assert sha(R / item["path"]) == item["sha256"], item["path"]
assert sha(R / "audit_statistics/block_tolerance_cdf.py") == frozen["cdf_path_only_change"]["local_sha256"]

files = []
stages = []
definitions = [
    ("history_block_metrics", "COMMON_LIBRARY_RECEIPT.json"),
    ("common_library", "COMMON_LIBRARY_RECEIPT.json"),
    ("fresh_blocks", "CORNER_CHECKS.json"),
    ("core", "CORNER_CHECKS.json"),
    ("direct_block_assessment/B_direct_m2_composition_K2", "COMMON_LIBRARY_RECEIPT.json"),
    ("direct_block_assessment/B_direct_m2_composition_K3", "COMMON_LIBRARY_RECEIPT.json"),
]
for name, marker in definitions:
    new = R / "recomputed" / name
    old = OLD / "research/workers/personnel_interchangeability_followup_20261020/audit_corner" / name
    if not (new / marker).exists():
        continue
    result_path = O / (name.replace("/", "_") + ".json")
    subprocess.run(
        [str(R / "venv/bin/python"), str(R / "compare_recomputed.py"),
         "--new", str(new), "--old", str(old), "--out", str(result_path)],
        check=True, stdout=subprocess.DEVNULL,
    )
    checks = json.loads(result_path.read_text())
    # The history pairs-only stage has no retained overlapping CSV outputs.
    assert checks or name == "history_block_metrics", name
    assert all(x["semantic_pass"] for x in checks), (name, checks)
    for receipt in ("CORNER_CHECKS.json", "EVENT_DESIGN_COVERAGE.json"):
        if (old / receipt).exists():
            assert json.loads((old / receipt).read_text()) == json.loads((new / receipt).read_text()), (name, receipt)
    if (old / "COMMON_LIBRARY_RECEIPT.json").exists():
        a = json.loads((old / "COMMON_LIBRARY_RECEIPT.json").read_text())
        b = json.loads((new / "COMMON_LIBRARY_RECEIPT.json").read_text())
        for key in ("request_sha256", "frozen_anchors", "endpoint_pairs", "pools",
                    "images", "buildings", "mode", "methods", "failures", "phase",
                    "labels_override_sha256"):
            if key in a:
                assert a[key] == b[key], (name, key, a[key], b[key])
    stages.append({"stage": name, "status": "verified", "retained_tables_checked": len(checks),
                   "retained_rows_checked": sum(x["rows_old"] for x in checks)})
    for target in TARGETS:
        if "/audit_corner/" not in target["path"]:
            continue
        suffix = target["path"].split("/audit_corner/", 1)[1]
        if str(Path(suffix).parent) != name:
            continue
        path = R / "recomputed" / suffix
        rows = sum(len(chunk) for chunk in pd.read_csv(path, chunksize=100000, low_memory=False))
        digest = sha(path)
        files.append({"publication_path": target["path"], "local_path": str(path),
                      "bytes": path.stat().st_size, "sha256": digest, "rows": rows,
                      "original_expected_bytes": target["bytes"],
                      "original_expected_sha256": target["sha256"],
                      "original_byte_identity": digest == target["sha256"],
                      "verification_stage": name})

mixed = R.parent / "mixed_pair_recovery/MIXED_PAIRED_RECOVERY_RECEIPT.json"
if mixed.exists():
    receipt = json.loads(mixed.read_text())
    assert receipt["frozen_inputs_unchanged"] and receipt["no_model_refit"]
    assert all(x["passed"] for x in receipt["retained_summary_checks"])
    path = mixed.parent / "paired_random_building.csv.gz"
    target = next(x for x in TARGETS if "/corner_fit_mixed/" in x["path"])
    digest = sha(path)
    assert digest == receipt["rebuilt_sha256"]
    files.append({"publication_path": target["path"], "local_path": str(path),
                  "bytes": path.stat().st_size, "sha256": digest, "rows": receipt["rows"],
                  "original_expected_bytes": target["bytes"],
                  "original_expected_sha256": target["sha256"],
                  "original_byte_identity": digest == target["sha256"],
                  "verification_stage": "corner_fit_mixed"})
    stages.append({"stage": "corner_fit_mixed", "status": "verified",
                   "retained_tables_checked": len(receipt["retained_summary_checks"]),
                   "retained_rows_checked": sum(x["rows"] for x in receipt["retained_summary_checks"])})

cdf = R / "audit_statistics/block_fit/tolerance"
if (cdf / "RECEIPT.json").exists():
    subprocess.run([str(R / "venv/bin/python"), str(R / "verify_cdf_outputs.py")],
                   check=True, stdout=subprocess.DEVNULL)
    receipt = json.loads((O / "cdf_integrity.json").read_text())
    target = next(x for x in TARGETS if "/statistics/block_fit/tolerance/" in x["path"])
    path = cdf / "EMPIRICAL_CDF.csv.gz"
    digest = sha(path)
    files.append({"publication_path": target["path"], "local_path": str(path),
                  "bytes": path.stat().st_size, "sha256": digest, "rows": receipt["rows"],
                  "original_expected_bytes": target["bytes"],
                  "original_expected_sha256": target["sha256"],
                  "original_byte_identity": digest == target["sha256"],
                  "verification_stage": "block_fit/tolerance"})
    stages.append({"stage": "block_fit/tolerance", "status": "verified",
                   "retained_tables_checked": receipt["retained_tables_checked"],
                   "retained_rows_checked": receipt["retained_rows_checked"]})

manifest = {"recovered_verified_tables": len(files), "files": files, "stages": stages,
            "no_model_refit": True, "no_reselection": True,
            "frozen_source_inputs_unchanged": True,
            "note": "Regenerated numerical outputs checked against available retained evidence. "
                    "Original absent tables are unavailable for full-cell or byte comparison.",
            "remaining_tables": 10 - len(files)}
tmp = R / "VERIFIED_TABLES_IN_PROGRESS.json.tmp"
tmp.write_text(json.dumps(manifest, indent=2))
tmp.replace(R / "VERIFIED_TABLES_IN_PROGRESS.json")
(R / "RECOVERY_PROGRESS.json").write_text(json.dumps({
    "stage": "frozen_replay_in_progress", "completed_verified_stages": stages,
    "recovered_verified_tables": len(files), "no_refit": True, "no_reselection": True,
}, indent=2))
print(json.dumps({"verified_tables": len(files), "stages": [x["stage"] for x in stages],
                  "bytes": sum(x["bytes"] for x in files)}, indent=2))
