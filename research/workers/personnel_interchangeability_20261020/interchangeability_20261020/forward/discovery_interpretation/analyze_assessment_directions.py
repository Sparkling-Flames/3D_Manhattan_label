#!/usr/bin/env python3
"""Interpret all 11 frozen forward directions after root metric receipt.

Separate fixed-n/m and sampled stress settings, with whole utility then source
and historical-Q controls. Only existing metrics are read; no new fusion runs.
"""
from pathlib import Path
from datetime import datetime, timezone
import collections
import json
import math
import numpy as np
import pandas as pd
from analyze_discovery import ROOT, KEY_METRICS, SUPPORT_METRICS, stream_events, summarize, write_csv, write_json, sha, read
from block_interpretation_utils import NEEDED, augment

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "assessment_interpretation"
LOOW_METRICS = ["within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main", "gap_geometry_noQ_main", "gap_geometry_shape_main",
                "net_B8L2_change", "net_D10_change", "within_Q_drop_gt5", "cross_Q_drop_gt5", "B_complete", "C_complete", "source_block_log_ratio"]

def means(frame):
    if frame.empty:
        return {}
    return frame.groupby(["building", "pool_id"])[LOOW_METRICS].mean().groupby("building").mean().mean().to_dict()

def main():
    OUT.mkdir(exist_ok=True)
    apath = ROOT / "interchangeability_20261020/assessment"
    freeze_path = apath / "ASSESSMENT_FREEZE.json"
    spec_path = apath / "DIRECTION_SPEC.json"
    request_path = apath / "direction_requests.json.gz"
    receipt_path = apath / "direction_metrics/SUMMARY_RECEIPT.json"
    freeze, spec = read(freeze_path), read(spec_path)
    assert sha(spec_path) == freeze["file_sha256"]["assessment/DIRECTION_SPEC.json"]
    assert sha(HERE.parent / "worker_labels.csv.gz") == freeze["file_sha256"]["forward/worker_labels.csv.gz"]
    plan_path = OUT / "INTERPRETATION_PLAN.json"
    if not plan_path.exists():
        write_json(plan_path, dict(schema="frozen_F11_interpretation_v1", registered_utc=datetime.now(timezone.utc).isoformat(),
            root_freeze_sha256=sha(freeze_path), direction_spec_sha256=sha(spec_path),
            scope="All11 existing F directions, fixed n13/m2 (Semi n7/m2) versus sampled stress n3..25/m2..6 separately. No reclassification or outcome-based rule changes.",
            controls=["overall", "source_matched", "source_Qclose3"],
            metrics="Existing joint main/strict/wide, noQ and rich shape diagnostics, continuous geometry and signed Q/D10, complete/score failure, source vs target block cost; no metric substitution.",
            persons="Exact A/B/C and block counts. Fixed-setting leave-one-worker-out sensitivity deletes any event involving that worker in A/B/C, repeats building-equal descriptive estimates; empty or reduced image support explicit, not new-person validation.",
            cases="For every fixed/stress route retain quality gain, quality loss, best observed source saving with Q not worse than2, same-class floor counterexample, and complete loss where available. These are illustrations of frozen routes, not new assessment-selected hypotheses."))
    assert read(plan_path)["root_freeze_sha256"] == sha(freeze_path)
    assert receipt_path.exists(), "Wait for root's complete direction_metrics/SUMMARY_RECEIPT.json; no partial outcome analysis"
    receipt = read(receipt_path)
    assert receipt["request_sha256"] == sha(request_path)
    templates = [m for m in spec["methods"] if m["method_id"].startswith("F20_") and m["context_id"].startswith("fixed_")]
    routes = {(m["method_id"], m["domain"], *m["directions"][0]): (f"F{i:02d}", m) for i, m in enumerate(templates, 1)}
    assert len(routes) == 11
    universe = pd.read_csv(HERE.parent / "features_train.csv.gz", usecols=["worker_id"]).worker_id.tolist()
    bits = {w: 1 << i for i, w in enumerate(sorted(universe))}
    attrs, event_exact, all_pools, all_ids = {}, {}, set(), set()
    for e in stream_events(request_path):
        assert e["phase"] == "assessment" and e["building"] in freeze["assessment_buildings"]
        all_pools.add(e["pool_id"]); all_ids.add(e["event_id"])
        key = (e["method_id"], e["domain"], e["outgoing_class"], e["incoming_class"])
        if key not in routes:
            continue
        rid, template = routes[key]
        A, B, C, core = [set(e[k]) for k in ("A_workers", "B_workers", "C_workers", "core_workers")]
        assert A & B == A & C == core and len(A) == len(B) == len(C) == e["n"]
        assert len(A - B) == len(A - C) == e["m"] >= 2 and e["n"] >= 3
        blocks = [set(e[k]) for k in ("outgoing_workers", "within_incoming", "cross_incoming")]
        assert blocks[0] == A - core and blocks[1] == B - core and blocks[2] == C - core
        setting = "fixed_n_m" if e["context_id"].startswith("fixed_") else "sampled_stress_integer_n_m"
        if setting == "fixed_n_m":
            assert e["n"] == template["n_values"][0] and e["m"] == template["m_values"][0]
        else:
            assert e["context_id"] == "stress_integer_n_m" and 3 <= e["n"] <= 25 and 2 <= e["m"] <= 6
        masks = [sum(bits[w] for w in A | B | C), sum(bits[w] for w in set.union(*blocks))] + [sum(bits[w] for w in b) for b in blocks]
        attrs[e["event_id"]] = [rid, setting] + masks
        event_exact[e["event_id"]] = e
    assert len(all_ids) == receipt["events"] and len(all_pools) == receipt["pools"]
    parts = apath / "direction_metrics/event_parts"
    frames = []
    observed_all = set()
    for pid in sorted(all_pools):
        frame = pd.read_csv(parts / (pid + ".csv.gz"), usecols=lambda c: c in NEEDED)
        observed_all.update(frame.event_id)
        frames.append(frame.loc[frame.event_id.isin(attrs)])
    assert observed_all == all_ids
    frame = pd.concat(frames, ignore_index=True)
    assert not frame.event_id.duplicated().any() and set(frame.event_id) == set(attrs)
    am = pd.DataFrame.from_dict(attrs, orient="index", columns=["route_id", "setting", "all_worker_mask", "block_worker_mask", "out_worker_mask", "within_worker_mask", "cross_worker_mask"])
    for c in [k for k in am if k.endswith("_mask")]:
        am[c] = am[c].astype(np.uint64)
    frame = augment(frame.join(am, on="event_id", validate="one_to_one"))
    tables, cov, loow = [[], [], []], [], []
    for control, data in (("overall", frame), ("source_matched", frame.loc[frame.actual_source_match]),
                           ("source_Qclose3", frame.loc[frame.actual_source_match & frame.all_blocks_history_Q_close3])):
        data = data.copy(); data["control"] = control
        keys = ["route_id", "method_id", "domain", "outgoing_class", "incoming_class", "setting", "control"]
        result = summarize(data, keys)
        for dest, part in zip(tables, result):
            dest.append(part)
        for key, (rid, template) in routes.items():
            for setting in ("fixed_n_m", "sampled_stress_integer_n_m"):
                g = data.loc[(data.route_id == rid) & (data.setting == setting)]
                row = dict(route_id=rid, method_id=key[0], domain=key[1], outgoing_class=key[2], incoming_class=key[3], setting=setting, control=control,
                           events=len(g), pools=g.pool_id.nunique(), images=g.image.nunique(), buildings=g.building.nunique(), unknown_no_imputation=len(g) == 0)
                for arm in "ABC":
                    fail = g.loc[~g[arm + "_complete"]]
                    row[arm + "_incomplete_events"] = len(fail); row[arm + "_incomplete_unique_teams"] = fail[arm + "_team_key"].nunique()
                    row[arm + "_score_missing_events"] = int(g[arm + "_score_missing"].sum())
                cov.append(row)
                if setting != "fixed_n_m" or g.empty:
                    continue
                baseline = means(g)
                for worker, bit in bits.items():
                    involvement = (g.all_worker_mask.to_numpy(dtype=np.uint64) & np.uint64(bit)) != 0
                    if not involvement.any():
                        continue
                    kept = g.loc[~involvement]
                    r = dict(route_id=rid, control=control, removed_worker=worker, events_before=len(g), events_after=len(kept),
                             images_before=g.image.nunique(), images_after=kept.image.nunique(), buildings_before=g.building.nunique(), buildings_after=kept.building.nunique(),
                             class_support_lost=kept.empty, retained_event_fraction=len(kept) / len(g))
                    point = means(kept)
                    for m in LOOW_METRICS:
                        r[m] = point.get(m, np.nan)
                        r["minus_full_" + m] = point.get(m, np.nan) - baseline[m]
                    loow.append(r)
    for name, parts in zip(("per_image", "per_building", "aggregate"), tables):
        write_csv(OUT / ("F11_" + name + ".csv.gz"), pd.concat(parts, ignore_index=True))
    write_csv(OUT / "F11_coverage_and_failures.csv.gz", pd.DataFrame(cov))
    lw = pd.DataFrame(loow)
    write_csv(OUT / "F11_leave_one_worker_out.csv.gz", lw)
    lrows = []
    for (rid, control), g in lw.groupby(["route_id", "control"]):
        r = dict(route_id=rid, control=control, removed_workers=len(g), zero_support_removals=int(g.class_support_lost.sum()),
                 events_after_min=int(g.events_after.min()), images_after_min=int(g.images_after.min()), buildings_after_min=int(g.buildings_after.min()))
        for m in LOOW_METRICS:
            x = g[m].dropna()
            r[m + "_min"] = x.min() if len(x) else np.nan
            r[m + "_max"] = x.max() if len(x) else np.nan
            r[m + "_positive_removals"] = int((x > 0).sum())
            r[m + "_negative_removals"] = int((x < 0).sum())
        lrows.append(r)
    write_csv(OUT / "F11_leave_one_worker_out_summary.csv.gz", pd.DataFrame(lrows))
    cases = []
    for (rid, setting), g in frame.groupby(["route_id", "setting"]):
        choices = [("quality_gain", g.dropna(subset=["net_B8L2_change"]).sort_values("net_B8L2_change", ascending=False)),
                   ("quality_loss", g.dropna(subset=["net_B8L2_change"]).sort_values("net_B8L2_change")),
                   ("source_saving_Q_not_worse2", g.loc[g.source_time_comparable & g.B_complete & g.C_complete & (g.net_B8L2_change >= -2)].sort_values("source_block_log_ratio")),
                   ("same_class_floor_counterexample", g.dropna(subset=["within_floor_jaccard_difference"]).sort_values("within_floor_jaccard_difference", ascending=False)),
                   ("cross_complete_loss", g.loc[g.net_complete_lost].sort_values("event_id"))]
        for reason, candidates in choices:
            if candidates.empty:
                continue
            r = candidates.iloc[0]
            e = event_exact[r.event_id]
            record = {k: r[k] for k in ["route_id", "setting", "method_id", "domain", "outgoing_class", "incoming_class", "event_id", "pool_id", "image", "building", "n", "m", "reference_id",
                      "actual_source_match", "all_blocks_history_Q_close3", "A_team_key", "B_team_key", "C_team_key", "A_B8L2", "B_B8L2", "C_B8L2", "A_complete", "B_complete", "C_complete",
                      "within_B8L2_change", "cross_B8L2_change", "net_B8L2_change", "net_D10_change", "within_joint_stable_main", "cross_joint_stable_main", "within_geometry_noQ_main", "cross_geometry_noQ_main",
                      "within_floor_jaccard_difference", "cross_floor_jaccard_difference", "within_structure_bound_cyclic_deg", "cross_structure_bound_cyclic_deg", "within_node_count_difference", "cross_node_count_difference",
                      "within_source_block_seconds", "cross_source_block_seconds", "source_block_log_ratio", "cross_minus_within_history_Q"]}
            record["selection_reason"] = reason
            record.update({k: "|".join(e[k]) for k in ("A_workers", "B_workers", "C_workers", "core_workers", "outgoing_workers", "within_incoming", "cross_incoming")})
            cases.append(record)
    write_csv(OUT / "F11_representative_events.csv.gz", pd.DataFrame(cases))
    failures = frame.loc[~frame.A_complete | ~frame.B_complete | ~frame.C_complete]
    failure_cols = ["route_id", "setting", "event_id", "pool_id", "image", "building", "n", "m", "A_team_key", "B_team_key", "C_team_key"] + [arm + tail for arm in "ABC" for tail in ("_complete", "_B8L2", "_score_status", "_geometry_reason")]
    write_csv(OUT / "F11_all_incomplete_events.csv.gz", failures[failure_cols])
    write_json(OUT / "ASSESSMENT_INTERPRETATION_RECEIPT.json", dict(schema="assessment_all11_forward_fixed_directions_v1", root_summary_sha256=sha(receipt_path), root_freeze_sha256=sha(freeze_path),
               interpretation_plan_sha256=sha(plan_path), request_sha256=sha(request_path), script_sha256=sha(Path(__file__)), helper_sha256=sha(HERE / "block_interpretation_utils.py"),
               requested_direction_events=len(all_ids), forward_events=len(frame), forward_pools=frame.pool_id.nunique(), forward_images=frame.image.nunique(), forward_buildings=frame.building.nunique(),
               directions=11, fixed_events=int((frame.setting == "fixed_n_m").sum()), stress_events=int((frame.setting == "sampled_stress_integer_n_m").sum()),
               exact_requests_rebuilt=True, labels_changed=False, new_fusion_or_scoring=False,
               fixed_vs_stress="Separate settings, no pooled headline masking n/m sampling. Empty controls and capacity failures retained.",
               quality_tail="Signed within/cross_Q_drop_gt5 contrasts decline, inherited bad_Q fields are separately labeled absolute change.",
               time="Source-task report block sums/ratios; positive observed costs required. New target time null remains missing. Whole-team time or redo costs are not inferred.",
               personnel_sensitivity="Delete each observed worker's A/B/C events from the fixed setting. Descriptive sensitivity on existing images/members, not independent new-worker validation; changed image/building support retained."))
    print(json.dumps({"events": len(frame), "fixed_events": int((frame.setting == "fixed_n_m").sum()), "stress_events": int((frame.setting == "sampled_stress_integer_n_m").sum()),
                      "pools": int(frame.pool_id.nunique()), "images": int(frame.image.nunique()), "case_rows": len(cases)}))

if __name__ == "__main__":
    main()
