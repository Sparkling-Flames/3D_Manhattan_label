"""Two explanatory Semi cases: state replay + exact geometry check, zero scoring.

The second case includes the already evaluated continuous-QT endpoint as a fourth
team.  It is a same-class one-member repair, not a fourth arm of the ABC design.
"""
from pathlib import Path
import collections
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[2]
OUT = HERE / "mechanism_cases"
sys.path.insert(0, str(STUDY))
import run_native_closure as core
core.configure()
gs = core.gs

SPECS = [
    ("semi_pure_efficiency", "b3ea1be32dde2004e09bb43f", None,
     "Semi：相同结构与定位，记录时间减少"),
    ("semi_member_loss_qt_repair", "6b08426576f01bdfebc4009c",
     "aa5276f319b87e6c1c113f28", "Semi：跨类定位损失与同类单成员修复"),
]


def angular(a, b):
    def ray(p):
        p = np.asarray(p, float)
        u = 2 * np.pi * (p[:, 0] / 1024 - .5)
        v = np.pi * (.5 - p[:, 1] / 512)
        return np.c_[np.cos(v) * np.sin(u), np.sin(v), -np.cos(v) * np.cos(u)]
    return np.rad2deg(np.arccos(np.clip(ray(a) @ ray(b).T, -1, 1)))


def main():
    events = pd.read_csv(HERE / "EVENTS_COMPLETE.csv.gz", keep_default_na=False, low_memory=False)
    controls = pd.read_csv(HERE / "CONTINUOUS_QT_COMPLETE.csv.gz", keep_default_na=False)
    labels = pd.read_csv(HERE / "INHERITED_LABELS_LOBO.csv.gz", keep_default_na=False)
    pools = gs.pool_lookup()
    fe, _, _, _ = gs.setup_engine()
    tables, receipts = collections.defaultdict(list), []
    total_replays = 0
    with fe.cached_matching():
        for cid, eid, qid, title in SPECS:
            e = events.loc[events.event_id.eq(eid)].iloc[0].to_dict()
            q = controls.loc[controls.control_id.eq(qid)].iloc[0].to_dict() if qid else None
            pool = pools[e["pool_id"]]
            by = {r["worker_id"]: r for r in pool["records"]}
            lm = labels.loc[labels.heldout_building.eq(e["building"])].set_index("worker_id").coarse_label.to_dict()
            keys = {e["team_" + arm] for arm in "ABC"}
            if q:
                keys.add(q["team_QT"])
                assert q["common_background"] == e["common_background"]
                assert q["team_C"] == e["team_C"]
            native = core.reused_rows(e["pool_id"], keys)
            classes = sorted(set(lm.values()))
            colors = {cl: ["#3e78a4", "#299678", "#be5d63", "#955f9a", "#c88a3e"][i % 5]
                      for i, cl in enumerate(classes)}
            case = dict(case_id=cid, title=title, n=int(e["n"]), method_id="V3_JOINT_QT",
                        tier="coarse", event=e, pool_id=e["pool_id"], pool_meta=pool["meta"],
                        image_id=pool["meta"]["image_id"],
                        reference=dict(pool["reference"], reference_id=pool["meta"]["reference_id"]),
                        subtitle=f"Semi / n={e['n']} / m={e['m_AB']}",
                        class_names={cl: cl for cl in classes}, class_colors=colors,
                        selection="Post-result explanatory case; not a separate effect estimator",
                        underlying_data_version="v2", teams=[])
            if q:
                case["continuous_qt_control"] = q
                case["fourth_team_interpretation"] = (
                    "QT shares D and replaces one C member with another member of the same target class; "
                    "its actual C-QT m is 1, separate from ABC m=3")
            bg, union = set(e["common_background"].split("|")), set()
            ref = np.asarray(pool["reference"]["points_1024x512"])
            arms = [(a, e["team_" + a]) for a in "ABC"]
            if q:
                arms.append(("QT", q["team_QT"]))
            for arm, key in arms:
                t = dict(native[key])
                ws = t["member_workers"]
                if isinstance(ws, str):
                    ws = ws.split("|")
                union.update(ws)
                state = fe.clean(fe.compact(fe.fuse([by[w] for w in sorted(ws)], gap=fe.WORKING_GAP)["automatic"]))
                assert gs.digest(state["candidate"]) == gs.digest(t["geometry"]), (cid, arm, "geometry mismatch")
                total_replays += 1
                t.update(label=arm, member_workers=ws,
                         counts=dict(collections.Counter(lm[w] for w in ws)), full_state=state)
                case["teams"].append(t)
                tables["ENDPOINT_METRICS"].append(dict(case_id=cid, arm=arm, **{
                    k: v for k, v in t.items() if not isinstance(v, (list, dict))}))
                for g in state["identity_groups"]:
                    center = np.asarray(g["center"])
                    dist = np.maximum(angular(center[:1], ref[::2]), angular(center[1:], ref[1::2]))[0]
                    j, mm = int(np.argmin(dist)), g["members"]
                    tables["GROUP_VOTES"].append(dict(
                        case_id=cid, arm=arm, group=g["feature_id"], support=g["support"],
                        threshold=t["minimum_support"], selected=g["selected"], nearest_reference_corner=j,
                        paired_bound_distance_deg=float(dist[j]), background_votes=sum(m["worker"] in bg for m in mm),
                        member_workers="|".join(sorted(m["worker"] for m in mm)),
                        class_votes=gs.canonical_counts(collections.Counter(lm[m["worker"]] for m in mm)),
                        top_x=center[0, 0], top_y=center[0, 1], bottom_x=center[1, 0], bottom_y=center[1, 1]))
                    for m in mm:
                        tables["OBSERVATION_ASSIGNMENTS"].append(dict(
                            case_id=cid, arm=arm, group=g["feature_id"], worker=m["worker"],
                            object_id=m["id"], pair_index=m["pair_index"], support=g["support"], selected=g["selected"]))
                for ed in state["ring_diagnostics"]["edges"]:
                    tables["EDGE_VOTES"].append(dict(case_id=cid, arm=arm, node_pair="|".join(ed["feature_ids"]),
                                                    direct_support=ed["direct_support"], projected_support=ed["projected_support"],
                                                    direct_workers="|".join(ed["direct_workers"]),
                                                    projected_workers="|".join(ed["projected_workers"])))
            case["members"] = [dict(by[w], class_id=lm[w], coarse_class=lm[w], fine_class=lm[w]) for w in sorted(union)]
            case["raw_overlay_groups"] = [
                dict(class_id=e["source_class"], workers=e["outgoing_block_X"].split("|"), label="原队源类块X"),
                dict(class_id=e["source_class"], workers=e["same_count_block_Y"].split("|"), label="同类替换块Y"),
                dict(class_id=e["target_class"], workers=e["changed_count_block_Z"].split("|"), label="跨类替换块Z"),
            ]
            if q:
                case["raw_overlay_groups"].append(dict(class_id=e["target_class"], workers=q["qt_workers"].split("|"),
                                                       label="同D连续QT块：W127换成同类W109"))
            for m in case["members"]:
                tables["EXACT_MEMBERS"].append(dict(case_id=cid, worker_id=m["worker_id"], class_id=m["class_id"],
                                                      object_id=m["object_id"], pair_count=len(m["points"]) // 2,
                                                      in_background=m["worker_id"] in bg,
                                                      arms="|".join(t["label"] for t in case["teams"] if m["worker_id"] in t["member_workers"])))
            path = OUT / "cases" / (cid + ".json.gz")
            gs.save(path, case)
            tables["EXACT_EVENTS"].append(dict(case_id=cid, **e))
            if q:
                tables["EXACT_QT_CONTROLS"].append(dict(case_id=cid, **q))
            receipts.append(dict(case_id=cid, event_id=eid, qt_control_id=qid, arms=len(arms),
                                 geometry_equal_to_saved_endpoint=True, score_calls=0,
                                 state_replays=len(arms), sha256=core.frozen.prior.sha(path)))
            # Persist each completed case and the current receipt immediately.
            gs.save(OUT / "CASE_EXPORT_RECEIPT.json", dict(cases=receipts, score_calls=0,
                    total_state_replays=total_replays, selection="post_result_explanation"))
            print(cid, flush=True)
    for name, rows in tables.items():
        core.frozen.write_csv(OUT / (name + ".csv.gz"), rows)


if __name__ == "__main__":
    main()
