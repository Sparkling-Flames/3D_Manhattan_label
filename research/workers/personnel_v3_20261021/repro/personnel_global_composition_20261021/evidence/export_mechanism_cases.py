#!/usr/bin/env python3
"""Export a few exact new endpoints and recover their unretained vote ledgers.

Only selected existing member sets are replayed for full internal state.  Native
scores and final points remain those of the original new-study endpoint cache;
the state candidate must exactly reproduce that geometry before export.
"""
from __future__ import annotations
import collections
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(STUDY / "composition"))
import global_study as gs


def main():
    selection = gs.read(HERE / "CASE_SELECTION.json")
    pools = gs.pool_lookup()
    labels = gs.method_rows()
    fe, fr, sg, corner = gs.setup_engine()
    out = HERE / "cases"
    out.mkdir(exist_ok=True)
    all_receipts = []
    with fe.cached_matching():
        for spec in selection["cases"]:
            pool = pools[spec["pool_id"]]
            nativepath = STUDY / "composition/runtime/endpoints" / (pool["pool_id"] + ".json.gz")
            native = {t["team_key"]: t for t in gs.read(nativepath)["teams"]}
            byworker = {r["worker_id"]: r for r in pool["records"]}
            labelset = labels[(labels.method_id == spec["method_id"]) & (labels.tier == spec["tier"]) &
                              (labels.condition == pool["meta"]["condition"]) &
                              (labels.heldout_building == pool["meta"]["building"])]
            bylabel = dict(zip(labelset.worker_id, labelset.class_id))
            case = dict(spec, image_id=pool["meta"]["image_id"], pool_meta=pool["meta"],
                        reference=dict(pool["reference"], reference_id=pool["meta"]["reference_id"]),
                        selection=selection["selection"], teams=[])
            kept = set()
            cachedpath = out / (spec["case_id"] + ".json.gz")
            previous = gs.read(cachedpath) if cachedpath.exists() else None
            previous_states = {t["team_key"]: t.get("full_state") for t in previous["teams"]} if previous else {}
            replayed = 0
            for arm in spec["teams"]:
                key = gs.team_key(pool["pool_id"], sorted(byworker)) if arm.get("all_pool") else pool["pool_id"] + "__" + arm["team_suffix"]
                t = dict(native[key])
                kept.update(t["member_workers"])
                state = previous_states.get(key)
                if state is None:
                    state = fe.clean(fe.compact(fe.fuse([byworker[w] for w in sorted(t["member_workers"])], gap=fe.WORKING_GAP)["automatic"]))
                    replayed += 1
                assert gs.digest(state["candidate"]) == gs.digest(t["geometry"]), (key, "candidate geometry differs")
                assert state["n"] == t["k"]
                assert len(state["node_consensus"]["nodes"]) == t["nodes"]
                assert state["minimum_support"] == t["minimum_support"]
                assert sorted({m["id"] for g in state["identity_groups"] for m in g["members"]}) == sorted(byworker[w]["id"] for w in t["member_workers"])
                t.update(label=arm["label"], full_state=state,
                         counts=dict(collections.Counter(bylabel.get(w, "unknown") for w in t["member_workers"])))
                case["teams"].append(t)
            case["members"] = [dict(byworker[w], class_id=bylabel.get(w, "unknown")) for w in sorted(kept)]
            case["member_scope"] = "exact union of displayed new-study team members"
            case["member_overlay_title"] = spec["title"] + "：完整成员按楼外类别叠加"
            case["label_scope"] = "target-building-excluded; exact condition; current method/tier"
            case["source_pool_sha256"] = gs.digest(pool)
            case["source_native_path"] = str(nativepath.relative_to(ROOT))
            gs.save(cachedpath, case)
            all_receipts.append(dict(case_id=case["case_id"], pool_id=pool["pool_id"],
                new_endpoint_count=0, full_state_replays_now=replayed, scores_recomputed=False,
                native_geometry_exact=True, input_pool_sha256=gs.digest(pool),
                cases_sha256=hashlib.sha256(cachedpath.read_bytes()).hexdigest(),
                native_endpoint_source=str(nativepath.relative_to(ROOT)),
                method_id=spec["method_id"], tier=spec["tier"],
                team_keys=[t["team_key"] for t in case["teams"]]))
            print(json.dumps({"case_id": case["case_id"], "teams": [(t["label"],t["k"],t["B8L2"],t["nodes"],t["minimum_support"]) for t in case["teams"]], "full_state_replays_now": replayed},ensure_ascii=False),flush=True)
    gs.save(HERE / "CASE_EXPORT_RECEIPT.json", dict(schema="selected_new_endpoint_case_export_v1", cases=all_receipts,
          source_selection_sha256=hashlib.sha256((HERE/"CASE_SELECTION.json").read_bytes()).hexdigest(),
          source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          scoring_and_fusion_contract_unchanged=True, existing_endpoint_geometry_exact=True))


if __name__ == "__main__":
    main()
