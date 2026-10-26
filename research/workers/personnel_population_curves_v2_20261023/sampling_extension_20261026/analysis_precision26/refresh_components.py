#!/usr/bin/env python3
"""Restore named frozen score blocks and refresh only component aggregates.

Uses saved iou_2d/S_bottom_deg/dir/Hmean/Hcenter. Main Q, D10, qualification,
failure and all path-bootstrap arrays are untouched. No fusion or rescoring.
"""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
from precision_core import META, COMP, COHORTS, add_frozen_blocks, save_csv, save_json
from analyze_natural import read_selected

VERSION = "frozen_B8L2_D10_named_blocks_20261023_projected_20261026"


def refresh(root, stage, pid, force=False):
    out = root / "analysis_precision26" / ("results_stage" + str(stage))
    checkpoint = out / "pool_checkpoints"; done_path = checkpoint / (pid + "__DONE.json")
    done = json.loads(done_path.read_text())
    table_path = checkpoint / (pid + "__components.csv.gz")
    if not force:
        existing = pd.read_csv(table_path)
        if ("component_projection_version" in existing and existing.component_projection_version.eq(VERSION).all()
                and set(COMP) <= set(existing.component)):
            return None
    chunks = [pd.read_csv(root / "analysis_precision26/prior_pool_cache" / (pid + ".csv.gz"), low_memory=False)]
    for s in range(1, stage + 1):
        path = root / "new_endpoints26" / ("stage" + str(s)) / "prefix_values" / (pid + ".csv.gz")
        chunks.append(read_selected(path, "new104A" if s == 1 else "new104B"))
    data = add_frozen_blocks(pd.concat(chunks, ignore_index=True), root)
    meta = done["metadata"]; rows = []
    for cohort in done["cohorts"]:
        d = data[data.stratum.isin(COHORTS[cohort])]
        for k, g in d.groupby("k", sort=True):
            for component in COMP:
                values = pd.to_numeric(g[component], errors="coerce").to_numpy(float) if component in g else np.array([])
                values = values[np.isfinite(values)]
                rows.append({**meta, "cohort": cohort, "k": int(k), "component": component,
                             "valid_paths": len(values), "paths_attempted": g.path_id.nunique(),
                             "mean": float(np.mean(values)) if len(values) else np.nan,
                             "sd_ddof1": float(np.std(values, ddof=1)) if len(values) > 1 else np.nan,
                             "MCSE": float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else np.nan,
                             "component_projection_version": VERSION})
    receipt = save_csv(pd.DataFrame(rows), table_path)
    done["files"] = [receipt if Path(item["file"]).name == table_path.name else item for item in done["files"]]
    done["component_projection_version"] = VERSION
    done["main_statistics_and_bootstrap_recomputed"] = False
    save_json(done, done_path)
    return dict(pool_id=pid, stage=stage, component_rows=len(rows), receipt=receipt,
                main_statistics_and_bootstrap_recomputed=False, new_fusion=False)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--stage", type=int, choices=[1, 2], required=True)
    ap.add_argument("--force", action="store_true"); ap.add_argument("--pool", action="append")
    args = ap.parse_args(); root = args.root.resolve()
    out = root / "analysis_precision26" / ("results_stage" + str(args.stage))
    pids = args.pool or [p.name.split("__DONE.json")[0] for p in sorted((out / "pool_checkpoints").glob("*__DONE.json"))]
    changed = []
    for pid in pids:
        r = refresh(root, args.stage, pid, args.force)
        if r:
            changed.append(r)
    save_json(dict(stage=args.stage, checked_completed_pools=len(pids), refreshed_pools=len(changed),
                   projection_version=VERSION, files=changed, main_statistics_and_bootstrap_recomputed=False,
                   new_fusion=False), out / "COMPONENT_REFRESH_RECEIPT.json")
    print(json.dumps(dict(stage=args.stage, checked=len(pids), refreshed=len(changed))), flush=True)


if __name__ == "__main__":
    main()
