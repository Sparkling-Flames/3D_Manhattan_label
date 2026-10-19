#!/usr/bin/env python3
"""Inventory exact validation-block support for discovery illustration strata.

Reads frozen requests and historical features only, never validation fusion.
"""
import argparse
import collections
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fusion_runner import read
from summarize_grid import canonical_counts, sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--definitions", type=Path, required=True)
    ap.add_argument("--requests", type=Path, required=True)
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    definitions, manifest = read(a.definitions)["definitions"], read(a.requests)
    assert manifest["spec"]["phase"] == "validation"
    features = pd.read_csv(a.features).set_index("worker_id").to_dict("index")
    index = collections.defaultdict(list)
    for event in manifest["events"]:
        key = (event["method_id"], event["domain"], canonical_counts(event["outgoing_counts"]), canonical_counts(event["incoming_counts"]), event["k"], event["m"])
        index[key].append(event)
    rows = []
    for d in definitions:
        key = tuple(d[c] for c in ("method_id", "domain", "outgoing_counts", "incoming_counts", "k", "m"))
        group = index[key]
        source = qclose = source_q = new_blocks = old_blocks = new_teams = 0
        for e in group:
            blocks = [e[name] for name in ("outgoing_workers", "within_incoming", "cross_incoming")]
            origins = [collections.Counter(features[w]["person_origin"] for w in ws) for ws in blocks]
            same_source = origins[0] == origins[1] == origins[2]
            source += same_source
            new_blocks += same_source and origins[0].get("new", 0) == e["m"]
            old_blocks += same_source and origins[0].get("v1", 0) == e["m"]
            column = "theta_hard" if d["domain"] == "hard" else "q_beta"
            means = [np.mean([features[w].get(column, np.nan) for w in ws]) for ws in blocks]
            close = bool(np.isfinite(means[1:]).all() and abs(means[2] - means[1]) <= 3)
            qclose += close
            source_q += same_source and close
            new_teams += all(features[w]["person_origin"] == "new" for arm in "ABC" for w in e[arm + "_workers"])
        rows.append(dict(d, validation_events=len(group), validation_images=len({e["image"] for e in group}),
                         validation_buildings=len({e["building"] for e in group}),
                         validation_workers=len({w for e in group for arm in "ABC" for w in e[arm + "_workers"]}),
                         validation_unique_teams=len({e[arm + "_team_key"] for e in group for arm in "ABC"}),
                         source_matched_events=source, new_source_blocks=new_blocks, old_source_blocks=old_blocks,
                         all_new_teams_events=new_teams, incoming_Q_close_3_events=qclose, source_and_Q_close_3_events=source_q,
                         status="exact_frozen_count_stratum_present" if group else "no_sampled_exact_stratum", validation_outcome_read=False))
    pd.DataFrame(rows).to_csv(a.out, index=False)
    a.out.with_suffix(".json").write_text(json.dumps(dict(validation_outcome_read=False, label_or_comparison_changes=False,
        input_hashes={str(p): sha(p) for p in (a.definitions, a.requests, a.features)}), ensure_ascii=False, indent=2) + "\n")
    print(pd.DataFrame(rows)[["highlight_id", "validation_events", "validation_images", "validation_buildings", "source_matched_events", "incoming_Q_close_3_events"]].to_string(index=False))


if __name__ == "__main__":
    main()
