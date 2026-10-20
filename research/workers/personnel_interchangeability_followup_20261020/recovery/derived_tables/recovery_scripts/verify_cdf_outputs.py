"""Verify reconstructed CDF values and retained summaries without model fitting."""
from pathlib import Path
import hashlib
import json
import subprocess

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parent
OLD = R.parent / "publication_stage_recovered/research/statistics/personnel_interchangeability_audit_20261020/statistics/block_fit/tolerance"
NEW = R / "audit_statistics/block_fit/tolerance"
O = R / "verification"
O.mkdir(exist_ok=True)
assert (NEW / "RECEIPT.json").exists()
subprocess.run(
    [str(R / "venv/bin/python"), str(R / "compare_recomputed.py"),
     "--new", str(NEW), "--old", str(OLD), "--out", str(O / "tolerance.json")],
    check=True, stdout=subprocess.DEVNULL,
)
checks = json.loads((O / "tolerance.json").read_text())
assert {x["file"] for x in checks} == {"COVERAGE.csv", "QUANTILES.csv"}
assert all(x["semantic_pass"] for x in checks), checks
old_receipt = json.loads((OLD / "RECEIPT.json").read_text())
new_receipt = json.loads((NEW / "RECEIPT.json").read_text())
for key, value in new_receipt.items():
    assert old_receipt[key] == value, (key, value, old_receipt[key])

series = {}
rows = 0
for chunk in pd.read_csv(NEW / "EMPIRICAL_CDF.csv.gz", chunksize=100000):
    for key, group in chunk.groupby(["method", "gate", "metric", "arm"], sort=False):
        x = group.tolerance.to_numpy()
        y = group.fraction_le.to_numpy()
        previous = series.get(key)
        assert np.isfinite(x).all() and np.isfinite(y).all(), key
        assert (np.diff(x) >= 0).all() and (np.diff(y) >= -1e-12).all(), key
        assert ((y >= -1e-12) & (y <= 1 + 1e-10)).all(), key
        if previous:
            assert x[0] >= previous["last_x"] and y[0] >= previous["last_y"] - 1e-12, key
        series[key] = {
            "last_x": float(x[-1]), "last_y": float(y[-1]),
            "rows": len(group) + (previous["rows"] if previous else 0),
        }
    rows += len(chunk)
assert rows == old_receipt["cdf_validation"]["rows"] == new_receipt["rows"]
assert len(series) == old_receipt["cdf_validation"]["series"]
assert all(abs(group["last_y"] - 1) <= 1e-10 for group in series.values())
for relative, digest in old_receipt["inputs_sha256"].items():
    if relative.startswith("audit_learning/"):
        assert hashlib.sha256((R / relative).read_bytes()).hexdigest() == digest, relative
receipt = {
    "rows": rows, "series": len(series), "monotone_bounded_terminal_one": True,
    "receipt_generation_fields_match": True, "saved_label_hashes_match": True,
    "retained_tables_checked": len(checks),
    "retained_rows_checked": sum(x["rows_old"] for x in checks),
    "retained_summary_checks_passed": True,
}
(O / "cdf_integrity.json").write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2))
