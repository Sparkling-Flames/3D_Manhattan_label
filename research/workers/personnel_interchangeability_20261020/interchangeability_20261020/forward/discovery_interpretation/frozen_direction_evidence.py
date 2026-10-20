#!/usr/bin/env python3
"""Document discovery evidence for the parent's already frozen F directions.

This adds exact m2 and fixed-n summaries and metadata-only capacity. It cannot
alter the frozen portfolio and never reads assessment outcome files.
"""
from pathlib import Path
import sys
import json
import gzip
import collections
import numpy as np
import pandas as pd
from analyze_discovery import ROOT, KEY_METRICS, SUPPORT_METRICS, stream_events, summarize, write_csv, write_json, read, sha

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "interchangeability_20261020/code"))
import design_blocks as design

def plain(obj):
    return json.loads(pd.DataFrame([obj]).to_json(orient="records"))[0]

def main():
    freeze_path = ROOT / "interchangeability_20261020/assessment/ASSESSMENT_FREEZE.json"
    spec_path = ROOT / "interchangeability_20261020/assessment/DIRECTION_SPEC.json"
    freeze, spec = read(freeze_path), read(spec_path)
    assert sha(spec_path) == freeze["file_sha256"]["assessment/DIRECTION_SPEC.json"]
    templates = [m for m in spec["methods"] if m["method_id"].startswith("F20_") and m["context_id"].startswith("fixed_")]
    route_map = {}
    for i, m in enumerate(templates, 1):
        assert len(m["directions"]) == len(m["n_values"]) == len(m["m_values"]) == 1
        route_map[(m["method_id"], m["domain"], *m["directions"][0])] = (f"F{i:02d}", m)
    assert len(route_map) == freeze["forward_directions"] == 11
    labels_path = HERE.parent / "worker_labels.csv.gz"
    assert sha(labels_path) == freeze["file_sha256"]["forward/worker_labels.csv.gz"]
    mapping = design.labels_from([labels_path])
    feature_ids = pd.read_csv(HERE.parent / "features_train.csv.gz", usecols=["worker_id"]).worker_id.tolist()
    bits = {w: 1 << i for i, w in enumerate(sorted(feature_ids))}
    request_path = ROOT / "interchangeability_20261020/discovery/forward_requests.json.gz"
    attrs = {}
    for e in stream_events(request_path):
        key = (e["method_id"], e["domain"], e["outgoing_class"], e["incoming_class"])
        if key not in route_map or e["n"] < 3 or e["m"] < 2:
            continue
        rid, template = route_map[key]
        blocks = [set(e[k]) for k in ("outgoing_workers", "within_incoming", "cross_incoming")]
        allpeople = set(e["A_workers"]) | set(e["B_workers"]) | set(e["C_workers"])
        assert len(set(e["A_workers"]) - set(e["B_workers"])) == len(set(e["A_workers"]) - set(e["C_workers"])) == e["m"]
        values = [sum(bits[w] for w in allpeople), sum(bits[w] for w in set.union(*blocks))] + [sum(bits[w] for w in b) for b in blocks]
        attrs[e["event_id"]] = [rid, template["n_values"][0], template["m_values"][0]] + values
    needed = set(KEY_METRICS) | set(SUPPORT_METRICS) | {
        "event_id", "phase", "method_id", "domain", "pool_id", "building", "image", "difficulty", "n", "m", "outgoing_class", "incoming_class",
        "replacement_fraction", "A_team_key", "B_team_key", "C_team_key", "A_B8L2", "B_B8L2", "C_B8L2", "within_B8L2_change", "cross_B8L2_change",
        "within_bad_Q_gt5", "cross_bad_Q_gt5", "within_source_block_seconds", "cross_source_block_seconds", "within_target_block_seconds", "cross_target_block_seconds",
        "cross_over_within_source_block_time", "net_geometry_noQ_main"}
    pieces = []
    for p in sorted((ROOT / "interchangeability_20261020/discovery/forward_metrics/event_parts").glob("*.csv.gz")):
        d = pd.read_csv(p, usecols=lambda c: c in needed)
        pieces.append(d.loc[d.event_id.isin(attrs)])
    df = pd.concat(pieces, ignore_index=True)
    assert set(df.event_id) == set(attrs) and not df.event_id.duplicated().any() and (df.phase == "discovery").all()
    attr = pd.DataFrame.from_dict(attrs, orient="index", columns=["route_id", "fixed_n", "fixed_m", "all_worker_mask", "block_worker_mask", "out_worker_mask", "within_worker_mask", "cross_worker_mask"])
    for c in [x for x in attr if x.endswith("_mask")]:
        attr[c] = attr[c].astype(np.uint64)
    df = df.join(attr, on="event_id", validate="one_to_one")
    for arm in "ABC":
        df[arm + "_score_missing"] = df[arm + "_B8L2"].isna()
    for kind in ("within", "cross"):
        q = df[kind + "_B8L2_change"]
        df[kind + "_Q_drop_gt5"] = (q < -5).astype(float).where(q.notna())
        df[kind + "_absQ_gt5"] = df[kind + "_bad_Q_gt5"]
    df["net_Q_worsen_gt5"] = (df.net_B8L2_change < -5).astype(float).where(df.net_B8L2_change.notna())
    for kind in ("source", "target"):
        x, y = df["within_" + kind + "_block_seconds"], df["cross_" + kind + "_block_seconds"]
        ok = (x > 0) & (y > 0) & x.notna() & y.notna()
        df[kind + "_time_comparable"] = ok
        df[kind + "_block_log_ratio"] = np.log((y / x).where(ok))
    df["within_source_seconds_per_replaced_person"] = df.within_source_block_seconds / df.m
    df["cross_source_seconds_per_replaced_person"] = df.cross_source_block_seconds / df.m
    df["source_seconds_change_per_replaced_person"] = df.net_source_block_seconds / df.m
    save = df.cross_over_within_source_block_time <= .8
    df["source_save20"] = save.astype(float).where(df.source_time_comparable)
    good = df.B_complete & df.C_complete & df.net_B8L2_change.notna() & (df.net_B8L2_change >= -2)
    df["source_save20_Q_not_worse2"] = (save & good).astype(float).where(df.source_time_comparable)
    df["source_save20_Q_not_worse2_same_noQ_geometry"] = (save & good & df.net_geometry_noQ_main).astype(float).where(df.source_time_comparable)
    tables = [[], [], []]
    coverage = []
    for nview, d in (("all_registered_nge3_mge2", df), ("m2_all_n", df.loc[df.m == 2]),
                     ("frozen_fixed_n_m", df.loc[(df.n == df.fixed_n) & (df.m == df.fixed_m)])):
        for control, z in (("overall", d), ("source_matched", d.loc[d.actual_source_match]),
                           ("source_Qclose3", d.loc[d.actual_source_match & d.all_blocks_history_Q_close3])):
            z = z.copy()
            z["view"], z["control"] = nview, control
            for key, (rid, _) in route_map.items():
                g = z.loc[z.route_id == rid]
                coverage.append(dict(route_id=rid, method_id=key[0], domain=key[1], outgoing_class=key[2], incoming_class=key[3], view=nview,
                                     control=control, events=len(g), pools=g.pool_id.nunique(), images=g.image.nunique(), buildings=g.building.nunique(),
                                     missing_not_imputed=len(g) == 0))
            result = summarize(z, ["route_id", "method_id", "domain", "outgoing_class", "incoming_class", "view", "control"])
            for target, part in zip(tables, result):
                target.append(part)
    for name, pieces in zip(("per_image", "per_building", "aggregate"), tables):
        write_csv(HERE / ("frozen_directions_" + name + ".csv.gz"), pd.concat(pieces, ignore_index=True))
    write_csv(HERE / "frozen_directions_discovery_coverage.csv.gz", pd.DataFrame(coverage))
    snapshot = read(ROOT / "repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz")["images"]
    split = read(ROOT / "analysis/composition/SPLIT.json")
    capacities = []
    for phase, buildings in (("discovery", split["discovery_buildings"]), ("assessment", split["validation_buildings"])):
        for key, (rid, template) in route_map.items():
            for pool in snapshot:
                if pool["meta"]["building"] not in buildings or not design.applicable(pool, template):
                    continue
                frame, excludes, sizes = design.candidate_frame(pool, template, mapping[key[0], key[1]])
                capacities.append(dict(route_id=rid, phase=phase, method_id=key[0], domain=key[1], outgoing_class=key[2], incoming_class=key[3],
                                       pool_id=pool["pool_id"], image=pool["meta"]["image"], building=pool["meta"]["building"],
                                       fixed_n=template["n_values"][0], fixed_m=template["m_values"][0],
                                       allowed_people=len(design.allowed_workers(pool, template)), outgoing_capacity=sizes.get(key[2], 0), incoming_capacity=sizes.get(key[3], 0),
                                       feasible_contexts=len(frame), source_matched_contexts=sum(x[-1] == "source_matched" for x in frame),
                                       capacity_exclusions=json.dumps(excludes, sort_keys=True)))
    caps = pd.DataFrame(capacities)
    write_csv(HERE / "frozen_directions_metadata_capacity.csv.gz", caps)
    existing = pd.read_csv(HERE / "direction_aggregate.csv.gz")
    manifests = read(HERE.parent / "method_manifest.json")["methods"]
    definitions = []
    for key, (rid, template) in route_map.items():
        g = existing.loc[(existing.method_id == key[0]) & (existing.domain == key[1]) & (existing.outgoing_class == key[2]) & (existing.incoming_class == key[3])]
        cap = caps.loc[caps.route_id == rid]
        support = {}
        for phase in ("discovery", "assessment"):
            z = cap.loc[(cap.phase == phase) & (cap.feasible_contexts > 0)]
            sz = z.loc[z.source_matched_contexts > 0]
            support[phase] = dict(feasible_pools=z.pool_id.nunique(), feasible_images=z.image.nunique(), feasible_buildings=z.building.nunique(),
                                  source_matched_pools=sz.pool_id.nunique(), source_matched_images=sz.image.nunique(), source_matched_buildings=sz.building.nunique())
        definitions.append(dict(route_id=rid, method_id=key[0], domain=key[1], outgoing_class=key[2], incoming_class=key[3],
                                fixed_generator_template=template, history_definition=manifests[key[0]], metadata_capacity=support,
                                discovery_evidence=json.loads(g.to_json(orient="records")),
                                status="Already frozen by root; this file documents discovery support and does not select or amend assessment directions"))
    evidence = dict(schema="frozen_forward_directions_discovery_evidence_v1", root_freeze_sha256=sha(freeze_path), root_frozen_utc=freeze["frozen_utc"],
                    direction_spec_sha256=sha(spec_path), labels_sha256=sha(labels_path), direction_count=len(definitions), directions=definitions,
                    assessment_outcomes_read=False, source_time="Source-task reported seconds only; new target time known_n=0/all null. Incoming block time is distinct from full-team total/elapsed maximum and from any target redo cost.",
                    Q_control="Overall classification utility first. Source+Qclose requires all three replacement blocks pairwise historical condition-Q difference<=3. Tiny remaining incoming-person counts remain explicit.",
                    scope="Scope classes describe OUT-answer propensity, not adjudication correctness. New reported-error nonediting and editing classes do not establish verified error correction or net geometry improvement.",
                    difficulty="Hard image rating was adopted after nonblind panorama/reference geometry review; this is a conditional rule, not new-image automatic precollection prediction.",
                    image_unit="Pool IDs and physical image IDs are distinct; ordinary Manual and Semi pools can share an image. Within each frozen route one pool per image is verified.")
    write_json(HERE / "FROZEN_DIRECTION_DISCOVERY_EVIDENCE.json", evidence)
    case = pd.read_csv(HERE / "case_search_index.csv.gz")
    rframe = pd.DataFrame([dict(method_id=k[0], domain=k[1], outgoing_class=k[2], incoming_class=k[3], route_id=v[0]) for k, v in route_map.items()])
    case = case.merge(rframe, on=["method_id", "domain", "outgoing_class", "incoming_class"], validate="many_to_one")
    write_csv(HERE / "frozen_direction_representative_events.csv.gz", case)
    print(json.dumps({"frozen_directions": len(definitions), "discovery_events": len(df), "metadata_pool_rows": len(caps), "representative_event_rows": len(case),
                      "fixed_assessment_capacity": {r["route_id"]: r["metadata_capacity"]["assessment"] for r in definitions}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
