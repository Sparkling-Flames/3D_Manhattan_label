#!/usr/bin/env python3
"""Compare two exact finite-catalogue P10 targets; no endpoint/bootstrap work."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd


KIND_MAP = {
    "all_singletons": "singletons",
    "all_leave_one_out": "leave_one_out",
    "full_pool_singleton": "full_pool",
    "small_pool_all_subsets": "all_small_pool_subsets",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    """Publish fully materialized bytes only after file fsync, then fsync dir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_table(frame: pd.DataFrame, path: Path) -> dict:
    raw = frame.to_csv(index=False, float_format="%.17g").encode("utf-8")
    payload = gzip.compress(raw, compresslevel=6, mtime=0) if path.suffix == ".gz" else raw
    atomic_bytes(path, payload)
    if path.suffix == ".gz":
        # Reading the entire decompressed stream verifies the gzip footer/CRC.
        with gzip.open(path, "rb") as handle:
            verified = handle.read()
    else:
        verified = path.read_bytes()
    assert verified == raw, path
    restored = pd.read_csv(io.BytesIO(verified), low_memory=False)
    assert len(restored) == len(frame), path
    assert list(restored.columns) == list(frame.columns), path
    return {
        "file": path.name, "rows": len(frame), "columns": list(frame.columns),
        "bytes": path.stat().st_size, "sha256": sha(path),
        "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
        "gzip_eof_or_plain_full_read_verified": True,
    }


def num_summary(values: pd.Series) -> dict:
    x = values.dropna().to_numpy(dtype=float)
    return {
        "n": len(x),
        "mean": float(np.mean(x)) if len(x) else np.nan,
        "median": float(np.median(x)) if len(x) else np.nan,
        "p90": float(np.quantile(x, .9, method="linear")) if len(x) else np.nan,
        "max": float(np.max(x)) if len(x) else np.nan,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[2])
    args = p.parse_args()
    base = args.base.resolve()
    out = base / "analysis_precision/p10_definition_sensitivity"
    marginal_path = base / "new_endpoints/EXACT_MARGINAL_VALUES.csv.gz"
    anchor_path = base / "analysis_precision/new_results/EXACT_ANCHOR_BATCH_ACCURACY.csv.gz"
    # pandas consumes the full gzip to EOF. This raises on a truncated input.
    marginal = pd.read_csv(marginal_path, low_memory=False)
    all_anchor = pd.read_csv(anchor_path, low_memory=False)
    anchor = all_anchor.loc[all_anchor.metric.eq("Q_p10")].copy()
    assert not marginal.duplicated(["pool_id", "k", "team_key"]).any()
    assert not anchor.duplicated(["pool_id", "k", "version"]).any()
    assert set(anchor.version) == {"old24", "new24", "pooled48", "focus96"}
    meta = ["pool_id", "k", "image", "image_id", "building", "condition", "layer",
            "difficulty", "pool_n", "reference_id", "reference_version"]
    refs = []
    for (pool_id, k), g in marginal.groupby(["pool_id", "k"], sort=True):
        assert g.exact_kind.nunique() == 1
        assert g.finite_team_space.nunique() == 1
        assert len(g) == int(g.finite_team_space.iloc[0])
        assert np.allclose(g.marginal_weight, 1 / len(g))
        quality = pd.to_numeric(g.B8L2, errors="raise")
        assert not np.isinf(quality).any()
        q = np.sort(quality.dropna().to_numpy(dtype=float))
        row = {name: g.iloc[0][name] for name in meta}
        row.update({
            "exact_kind": KIND_MAP[g.exact_kind.iloc[0]],
            "source_exact_kind": g.exact_kind.iloc[0],
            "finite_catalogue_team_n": len(g),
            "finite_catalogue_Q_valid_team_n": len(q),
            "finite_catalogue_Q_missing_team_n": len(g) - len(q),
            "reference_is_Q_conditional_on_score_available": True,
            "exact_linear_p10": float(np.quantile(q, .1, method="linear")) if len(q) else np.nan,
            "exact_inverted_cdf_p10": float(np.quantile(q, .1, method="inverted_cdf")) if len(q) else np.nan,
            "cdf_rank_1based": math.ceil(.1 * len(q)) if len(q) else np.nan,
            "reference_state": "Q_available" if len(q) else "no_scorable_team",
        })
        if len(q):
            assert row["exact_inverted_cdf_p10"] == q[math.ceil(.1 * len(q)) - 1]
        row["linear_minus_cdf_p10"] = row["exact_linear_p10"] - row["exact_inverted_cdf_p10"]
        row["absolute_definition_difference"] = abs(row["linear_minus_cdf_p10"])
        refs.append(row)
    ref = pd.DataFrame(refs)
    joined = anchor.merge(ref.drop(columns=[x for x in meta if x not in ["pool_id", "k"]]),
                          on=["pool_id", "k", "exact_kind"], how="left", validate="many_to_one", indicator=True)
    assert joined._merge.eq("both").all()
    joined = joined.drop(columns="_merge")
    assert np.allclose(joined.exact_value, joined.exact_linear_p10, rtol=0, atol=1e-10, equal_nan=True)
    assert (joined.finite_population_teams == joined.finite_catalogue_team_n).all()
    for method in ["linear", "inverted_cdf"]:
        joined[f"error_vs_{method}"] = joined.estimate - joined[f"exact_{method}_p10"]
        joined[f"absolute_error_vs_{method}"] = joined[f"error_vs_{method}"].abs()
        joined[f"reference_available_{method}"] = joined[f"exact_{method}_p10"].notna()
        valid = joined.estimate.notna() & joined[f"reference_available_{method}"]
        joined[f"within_2_vs_{method}"] = np.where(valid, joined[f"absolute_error_vs_{method}"].le(2).astype(float), np.nan)
    joined["estimate_definition"] = "existing sample linear P10; unchanged"
    joined["absolute_error_change_cdf_minus_linear"] = joined.absolute_error_vs_inverted_cdf - joined.absolute_error_vs_linear
    joined["within_2_classification_changed"] = np.where(joined.estimate.notna() & joined.exact_linear_p10.notna(),
        joined.within_2_vs_linear.ne(joined.within_2_vs_inverted_cdf).astype(float), np.nan)
    summaries = []
    for keys, g in joined.groupby(["layer", "version", "exact_kind"], sort=True):
        for method in ["linear", "inverted_cdf"]:
            valid = g.estimate.notna() & g[f"exact_{method}_p10"].notna()
            z = g.loc[valid]
            stat = num_summary(z[f"absolute_error_vs_{method}"])
            summaries.append(dict(zip(["layer", "version", "exact_kind"], keys)) | {
                "reference_definition": method, "catalogue_cells": len(g),
                "images_total": g.image.nunique(), "buildings_total": g.building.nunique(),
                "paired_evaluable_cells": len(z), "paired_evaluable_images": z.image.nunique(),
                "paired_evaluable_buildings": z.building.nunique(),
                "reference_missing_cells": int(g[f"exact_{method}_p10"].isna().sum()),
                "estimate_missing_with_reference_cells": int((g.estimate.isna() & g[f"exact_{method}_p10"].notna()).sum()),
                "mean_signed_error": z[f"error_vs_{method}"].mean(),
                "MAE": stat["mean"], "median_absolute_error": stat["median"],
                "P90_absolute_error": stat["p90"], "maximum_absolute_error": stat["max"],
                "absolute_error_le_2_fraction": z[f"absolute_error_vs_{method}"].le(2).mean() if len(z) else np.nan,
                "definition_changes_within_2_n": int(z.within_2_classification_changed.sum()),
                "weighting": "one equally weighted pool/k cell within layer/version/exact_kind",
            })
    definition_summary = []
    for keys, g in ref.groupby(["layer", "exact_kind"], sort=True):
        z = g.loc[g.exact_linear_p10.notna()]
        stat = num_summary(z.absolute_definition_difference)
        definition_summary.append(dict(zip(["layer", "exact_kind"], keys)) | {
            "catalogue_cells": len(g), "evaluable_catalogue_cells": len(z),
            "images": g.image.nunique(), "buildings": g.building.nunique(),
            "mean_linear_minus_cdf": z.linear_minus_cdf_p10.mean(),
            "mean_absolute_definition_difference": stat["mean"],
            "median_absolute_definition_difference": stat["median"],
            "P90_absolute_definition_difference": stat["p90"],
            "maximum_absolute_definition_difference": stat["max"],
            "definition_difference_gt_2_n": int(z.absolute_definition_difference.gt(2).sum()),
        })
    paired = []
    pairs = [("old24", "new24"), ("old24", "pooled48"), ("new24", "pooled48"), ("pooled48", "focus96")]
    for left, right in pairs:
        a = joined.loc[joined.version.eq(left)]
        b = joined.loc[joined.version.eq(right)]
        z = a.merge(b, on=["pool_id", "k", "exact_kind", "layer", "building", "image"], suffixes=("_left", "_right"), validate="one_to_one")
        for keys, g in z.groupby(["layer", "exact_kind"], sort=True):
            for method in ["linear", "inverted_cdf"]:
                lc = f"absolute_error_vs_{method}_left"
                rc = f"absolute_error_vs_{method}_right"
                v = g.loc[g[lc].notna() & g[rc].notna()]
                diff = v[rc] - v[lc]
                paired.append(dict(zip(["layer", "exact_kind"], keys)) | {
                    "version_left": left, "version_right": right, "reference_definition": method,
                    "matched_catalogue_cells": len(g), "joint_evaluable_cells": len(v),
                    "joint_images": v.image.nunique(), "joint_buildings": v.building.nunique(),
                    "left_MAE": v[lc].mean(), "right_MAE": v[rc].mean(),
                    "MAE_right_minus_left": diff.mean(),
                    "left_P90_absolute_error": v[lc].quantile(.9), "right_P90_absolute_error": v[rc].quantile(.9),
                    "left_absolute_error_le_2_fraction": v[lc].le(2).mean() if len(v) else np.nan,
                    "right_absolute_error_le_2_fraction": v[rc].le(2).mean() if len(v) else np.nan,
                    "right_lower_absolute_error_fraction": diff.lt(-1e-10).mean() if len(v) else np.nan,
                    "right_higher_absolute_error_fraction": diff.gt(1e-10).mean() if len(v) else np.nan,
                    "weighting": "same evaluable pool/k cells, equal weight; focus96 uses its matched subset only",
                })
    outputs = []
    for name, data in [
        ("EXACT_P10_REFERENCES.csv.gz", ref),
        ("P10_BATCH_REFERENCE_COMPARISON.csv.gz", joined),
        ("P10_ACCURACY_BY_LAYER_VERSION_KIND.csv", pd.DataFrame(summaries)),
        ("P10_DEFINITION_REFERENCE_SUMMARY.csv", pd.DataFrame(definition_summary)),
        ("P10_PAIRED_VERSION_COMPARISON.csv", pd.DataFrame(paired)),
        ("WC2_46_P10_DEFINITION_CASE.csv", joined.loc[joined.image.eq("wc2JMjhGNzB-46")]),
    ]:
        outputs.append(write_table(data, out / name))
    receipt = {
        "study": "existing finite P10 reference definition sensitivity only",
        "repository_commit": "40d0fe62dc62f6f6c12723af10195b7abb7bc9fe",
        "numpy_version": np.__version__, "pandas_version": pd.__version__,
        "inputs": [{"path": str(x.relative_to(base)), "bytes": x.stat().st_size, "sha256": sha(x)} for x in [marginal_path, anchor_path]],
        "input_marginal_rows": len(marginal), "input_anchor_rows_all_metrics": len(all_anchor),
        "input_Q_p10_rows": len(anchor), "exact_pool_k_catalogues": len(ref),
        "all_anchor_linear_reference_reproduced_tolerance": 1e-10,
        "all_requested_p10_rows_joined": True, "source_estimates_unchanged": True,
        "new_endpoint_evaluations": 0, "new_bootstrap_replicates": 0,
        "write_method": "CSV in memory, full gzip.compress, fsync temp file, atomic replace, fsync directory, full EOF read and parsed row/column checks",
        "outputs": outputs,
    }
    atomic_bytes(out / "VALIDATION_RECEIPT.json", (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"reference_rows": len(ref), "comparison_rows": len(joined), "outputs": [{"file": x["file"], "rows": x["rows"]} for x in outputs]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
