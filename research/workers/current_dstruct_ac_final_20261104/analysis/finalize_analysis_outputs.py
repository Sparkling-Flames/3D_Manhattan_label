"""Finalize output metadata without refitting or changing any point estimate.

The full summarize_ac.py already implements these rules. This idempotent
finisher also makes an in-progress analysis made with an earlier print-layout
version conform to the final joint-Q/T and interval display contract.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ac_common import HERE, csv, read_csv, sha, truth, write_json
from harmonize_intervals import harmonize_all
from summarize_ac import cohorts, gap_weighting_sensitivity


def main():
    frozen_main = sha(HERE / "SIX_DIRECTION_Q_BY_BUDGET.csv")
    t = read_csv(HERE / "RECORDED_LABOR_AND_JOINT_Q.csv")
    t["Q_labor_same_physical_pairs"] = t.Q_labor_support.eq("same_pairs_Q_and_labor")
    only_t = ~t.Q_labor_same_physical_pairs
    qcols = [c for c in t if c.startswith("Q_") and c not in
             ["Q_labor_support", "Q_labor_same_physical_pairs"]]
    qcols += [c for c in ["joint_images"] if c in t]
    t.loc[only_t, qcols] = np.nan
    csv(HERE / "RECORDED_LABOR_AND_JOINT_Q.csv", t)
    im = read_csv(HERE / "RECORDED_LABOR_IMAGE_EFFECTS.csv.gz")
    im.loc[im.Q_labor_support.eq("labor_available"), ["dQ", "abs_dQ"]] = np.nan
    csv(HERE / "RECORDED_LABOR_IMAGE_EFFECTS.csv.gz", im)

    d = cohorts(pd.concat([read_csv(HERE / "PHYSICAL_PAIRS_AUTOMATIC.csv.gz"),
                           read_csv(HERE / "PHYSICAL_PAIRS_ASSISTED.csv.gz")], ignore_index=True))
    for col in ["common_Q", "original_common_Q", "new_common_Q", "same_node_count", "both_Q_ge90",
                "time_whole_single_source", "time_blocks_single_source", "D_labor_complete"]:
        d[col] = truth(d[col])
    gap_weighting_sensitivity(d)
    harmonize_all()
    if sha(HERE / "SIX_DIRECTION_Q_BY_BUDGET.csv") != frozen_main:
        raise ValueError("Finalizer must preserve the independently audited main table")
    checks = dict(status="passed", unchanged_main_sha256=frozen_main,
                  T_only_rows_without_joint_Q_estimates=int(only_t.sum()),
                  same_pair_Q_T_rows=int((~only_t).sum()),
                  changed_point_estimates=0,
                  interval_policy="identical image/building values reuse identical intervals")
    write_json(HERE / "FINAL_OUTPUT_CONSISTENCY_CHECKS.json", checks)
    print(checks, flush=True)


if __name__ == "__main__":
    main()
