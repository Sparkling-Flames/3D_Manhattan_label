"""One actual Manual joint n20/m4 ABC; three metadata replays, zero scoring."""
from __future__ import annotations
import collections
import json
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
ROOT = STUDY.parents[2]
sys.path.insert(0, str(STUDY / "mechanisms"))
import export_new_cases as shared
core, gs, angular = shared.core, shared.gs, shared.angular

EVENT_ID = "a6b1eed8f4c86b3ce2d8c62c"
CASE_ID = "manual_joint_b6_n20_m4"


def main():
    out = HERE / "case.json.gz"
    if out.exists() and (HERE / "CASE_EXPORT_RECEIPT.json").exists():
        print("Saved case already exists; no additional state replay.")
        return
    request = None
    for chunk in pd.read_csv(HERE.parent / "EVENTS_COMPLETE.csv.gz", keep_default_na=False, chunksize=1000):
        found = chunk[chunk.event_id.eq(EVENT_ID)]
        if len(found):
            request = found.iloc[0].to_dict()
            break
    assert request is not None
    e = request
    assert e["n"] == 20 and e["m_AB"] == 4 and e["training_QT_direction"] == "q_up__faster"
    gs.save(HERE / "CASE_SELECTION.json", dict(event_id=EVENT_ID, method="V3_JOINT_QT", phase="A", image=e["image"],
        selection="post-result explanation: positive net quality and source-pair symmetric gain near its panel mean; real B6 photo already available",
        no_new_condition_search=True, planned_metadata_replays=3, planned_score_calls=0))
    pool = gs.pool_lookup()[e["pool_id"]]
    by = {r["worker_id"]: r for r in pool["records"]}
    labels = pd.read_csv(HERE.parent / "INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz", keep_default_na=False)
    ll = labels[labels.heldout_building.eq(e["building"])]
    lm = ll.set_index("worker_id").coarse_label.to_dict()
    needed = {e["team_" + a] for a in "ABC"}
    native = {}
    paths = list((STUDY / "native/runtime").glob("*/" + e["pool_id"] + ".json.gz"))
    paths += list((STUDY / "native/runtime").glob("*/" + e["pool_id"] + ".FINAL_*.json.gz"))
    for p in sorted(paths):
        if not (STUDY / "native/batches" / p.parent.name / "COMPLETION.json").exists():
            continue
        native.update((t["team_key"], t) for t in gs.read(p)["teams"] if t["team_key"] in needed)
        if needed <= native.keys():
            break
    assert needed <= native.keys()
    colors = {cl: ["#3e78a4", "#299678", "#be5d63", "#955f9a", "#c88a3e"][i % 5] for i, cl in enumerate(sorted(set(lm.values())))}
    colors.update(J2="#3e78a4", J5="#bd652a")
    case = dict(case_id=CASE_ID, title="Manual联合类别：结构补充与定位取舍", n=20, method_id="V3_JOINT_QT", tier="coarse",
        event=e, pool_id=e["pool_id"], pool_meta=pool["meta"], image_id=pool["meta"]["image_id"],
        reference=dict(pool["reference"], reference_id=pool["meta"]["reference_id"]),
        subtitle="Manual / n20 / m4；楼外J2→J5；共同背景16人", class_names={cl: cl for cl in colors}, class_colors=colors,
        selection="post_result_explanatory; not an additional group-effect estimator", underlying_data_version="v2", teams=[])
    fe, _, _, _ = gs.setup_engine()
    tables = collections.defaultdict(list)
    ref = np.asarray(pool["reference"]["points_1024x512"])
    bg = set(e["common_background"].split("|"))
    union = set()
    with fe.cached_matching():
        for arm in "ABC":
            t = dict(native[e["team_" + arm]])
            ws = t["member_workers"]
            union.update(ws)
            state = fe.clean(fe.compact(fe.fuse([by[w] for w in sorted(ws)], gap=fe.WORKING_GAP)["automatic"]))
            assert gs.digest(state["candidate"]) == gs.digest(t["geometry"]), (arm, "metadata replay geometry differs")
            t.update(label=arm, counts=dict(collections.Counter(lm[w] for w in ws)), full_state=state)
            case["teams"].append(t)
            tables["ENDPOINT_METRICS"].append(dict(case_id=CASE_ID, arm=arm, **{k: v for k, v in t.items() if not isinstance(v, (list, dict))}))
            for group in state["identity_groups"]:
                center = np.asarray(group["center"])
                distances = np.maximum(angular(center[:1], ref[::2]), angular(center[1:], ref[1::2]))[0]
                j = int(np.argmin(distances))
                mm = group["members"]
                tables["GROUP_VOTES"].append(dict(case_id=CASE_ID, arm=arm, group=group["feature_id"], support=group["support"],
                    threshold=t["minimum_support"], selected=group["selected"], nearest_reference_corner=j, paired_bound_distance_deg=float(distances[j]),
                    background_votes=sum(m["worker"] in bg for m in mm), replacement_votes=sum(m["worker"] not in bg for m in mm),
                    member_workers="|".join(sorted(m["worker"] for m in mm)), class_votes=gs.canonical_counts(collections.Counter(lm[m["worker"]] for m in mm)),
                    top_x=center[0, 0], top_y=center[0, 1], bottom_x=center[1, 0], bottom_y=center[1, 1]))
                for m in mm:
                    tables["OBSERVATION_ASSIGNMENTS"].append(dict(case_id=CASE_ID, arm=arm, group=group["feature_id"], worker=m["worker"],
                        object_id=m["id"], pair_index=m["pair_index"], support=group["support"], selected=group["selected"]))
            for edge in state["ring_diagnostics"]["edges"]:
                tables["EDGE_VOTES"].append(dict(case_id=CASE_ID, arm=arm, node_pair="|".join(edge["feature_ids"]),
                    direct_support=edge["direct_support"], projected_support=edge["projected_support"],
                    direct_workers="|".join(edge["direct_workers"]), projected_workers="|".join(edge["projected_workers"])))
    case["members"] = [dict(by[w], class_id=lm[w], coarse_class=lm[w], fine_class=lm[w]) for w in sorted(union)]
    case["raw_overlay_groups"] = [dict(class_id=e["source_class"], workers=e["outgoing_block_X"].split("|"), label="原队源类块X（J2）"),
        dict(class_id=e["source_class"], workers=e["same_count_block_Y"].split("|"), label="同类替换块Y（J2）"),
        dict(class_id=e["target_class"], workers=e["changed_count_block_Z"].split("|"), label="跨类替换块Z（J5）")]
    for m in case["members"]:
        tables["EXACT_MEMBERS"].append(dict(case_id=CASE_ID, worker_id=m["worker_id"], class_id=m["class_id"], object_id=m["object_id"],
            pair_count=len(m["points"]) // 2, in_background=m["worker_id"] in bg,
            arms="|".join(t["label"] for t in case["teams"] if m["worker_id"] in t["member_workers"])))
    tables["EXACT_EVENT"] = [dict(case_id=CASE_ID, **e)]
    gs.save(out, case)
    for name, rows in tables.items():
        core.frozen.write_csv(HERE / (name + ".csv.gz"), rows)
    core.frozen.write_csv(HERE / "FOLD_MEMBER_HISTORY.csv", ll[ll.worker_id.isin(union)].to_dict("records"))
    gs.save(HERE / "CASE_EXPORT_RECEIPT.json", dict(case_id=CASE_ID, event_id=EVENT_ID, method="V3_JOINT_QT", condition="manual",
        phase="A", n=20, m=4, metadata_state_replays=3, score_calls=0, geometry_equal_to_saved_endpoints=True,
        class_labels_from_target_building_excluded_history=True, case_sha256=core.frozen.prior.sha(out), underlying_data_version="v2"))
    print(json.dumps(dict(case_id=CASE_ID, state_replays=3, score_calls=0, events=1, members=len(union))), flush=True)


if __name__ == "__main__":
    main()
