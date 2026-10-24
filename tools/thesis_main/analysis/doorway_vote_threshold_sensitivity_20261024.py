"""One-vote threshold sensitivity on all 17 frozen v2 doorway full pools."""

from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.consensus_delivery_20261008 import WORKING_GAP, fuse
from tools.thesis_main.analysis.ring_correspondence_20261007 import assemble_fusion
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.wall_consensus_b8l2_20261016 import COMPONENTS, finite
from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching


ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / "research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz"
SAVED = ROOT / "research/workers/personnel_population_curves_v2_20261023/cases/doorway_full_pool_20261024/DOORWAY_FULL_POOL_STATUS.csv"
ENGINE = ROOT / "research/statistics/b8l2_shared_v6_20261016/inputs"
OUT = ROOT / "research/fusion/doorway_vote_sensitivity_20261024"
ZS_CASES = ROOT / "research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/positive_cases/cases"


def score(state, reference, engine, models):
    raw = measured(engine, state, dict(floor=reference["floor_xz_h"], points=reference["points_1024x512"]))
    raw.update(dual_scores(raw, models) if finite(raw, COMPONENTS) else dict(B8L2=None, D10=None))
    return raw


def adjacent_zs16(engine, models) -> None:
    rows = []
    for n in (20, 21):
        case = json.loads((ZS_CASES / f"E20261022_zs16_n{n}_m6.json").read_text(encoding="utf-8"))
        for team in case["teams"]:
            if team["label"] not in ("B", "C"):
                continue
            original = team["full_state"]
            official = (n + 1) // 2
            assert original["minimum_support"] == official
            for threshold in (10, 11):
                variant = copy.deepcopy(original)
                for group in variant["identity_groups"]:
                    group["selected"] = group["support"] >= threshold
                variant.update(assemble_fusion(variant["identity_groups"], variant["assignments"]))
                raw = score(variant, case["reference"], engine, models)
                nodes = len(variant["node_consensus"]["nodes"])
                complete = nodes >= 4 and variant["candidate"].get("geometry_status") == "ok"
                q = raw.get("B8L2") if complete else None
                if threshold == official:
                    assert nodes == team["nodes"] and complete == team["complete_evaluable"]
                    assert abs(q - team["B8L2"]) < 1e-7
                rows.append(dict(case_id=case["case_id"], image=team["image"], n=n, arm=team["label"],
                                 team_key=team["team_key"], threshold=threshold, official=threshold == official,
                                 identity_groups=len(variant["identity_groups"]), selected_nodes=nodes,
                                 selected_supports="|".join(str(g["support"]) for g in variant["identity_groups"] if g["selected"]),
                                 complete_evaluable=complete, geometry_status=variant["candidate"].get("geometry_status"),
                                 order_status=variant["candidate"].get("order_status"),
                                 B8L2=q, D10=raw.get("D10") if complete else None,
                                 iou_2d=raw.get("iou_2d") if complete else None,
                                 dir=raw.get("dir") if complete else None))
    result = pd.DataFrame(rows)
    assert len(result) == 8
    result.to_csv(OUT / "ZS16_20_21_FIXED_TEAM_THRESHOLD.csv", index=False)
    print(result[["n", "arm", "threshold", "selected_nodes", "B8L2"]].to_string(index=False), flush=True)


def main() -> None:
    pools = [p for p in json.load(gzip.open(INPUT, "rt", encoding="utf-8"))["images"]
             if p["meta"]["layer"] == "doorway_manual"]
    saved = pd.read_csv(SAVED).set_index("pool_id")
    assert len(pools) == len(saved) == 17
    OUT.mkdir(parents=True, exist_ok=True)
    rows, ledgers = [], []
    with cached_matching(), scoring_engine(ENGINE / "measurement_engine.zip", ENGINE / "working_models.py") as (engine, models):
        for pool in pools:
            meta, records, reference = pool["meta"], pool["records"], pool["reference"]
            n = len(records)
            official = (n + 1) // 2
            state = fuse(records, gap=WORKING_GAP)["automatic"]
            assert state["minimum_support"] == official
            assert n == len({r["worker"] for r in records}) == int(saved.loc[pool["pool_id"], "pool_n"])
            for group in state["identity_groups"]:
                ledgers.append(dict(image=meta["image"], pool_id=pool["pool_id"],
                                    group_id=group["feature_id"], support=group["support"],
                                    workers="|".join(sorted(m["worker"] for m in group["members"])),
                                    center_known=group["center"] is not None,
                                    selected_minus_one=group["support"] >= official - 1,
                                    selected_official=group["support"] >= official,
                                    selected_plus_one=group["support"] >= official + 1))
            for arm, threshold in (("minus_one", official - 1), ("official", official), ("plus_one", official + 1)):
                variant = copy.deepcopy(state)
                for group in variant["identity_groups"]:
                    group["selected"] = group["support"] >= threshold
                variant.update(assemble_fusion(variant["identity_groups"], variant["assignments"]))
                candidate = variant["candidate"]
                values = score(variant, reference, engine, models)
                nodes = len(variant["node_consensus"]["nodes"])
                complete = nodes >= 4 and candidate.get("geometry_status") == "ok"
                row = dict(image=meta["image"], building=meta["building"], pool_id=pool["pool_id"],
                           n=n, arm=arm, threshold=threshold, identity_groups=len(variant["identity_groups"]),
                           selected_nodes=nodes, unselected_groups=len(variant["identity_groups"]) - nodes,
                           below_four=nodes < 4, connection_available=candidate["points"] is not None,
                           geometry_status=candidate.get("geometry_status"), order_status=candidate["order_status"],
                           candidate_reason=candidate.get("reason"), complete_evaluable=complete)
                for field in ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean",
                              "Hcenter", "omission", "extension"):
                    value = values.get(field)
                    row[field] = float(value) if complete and value is not None and np.isfinite(value) else None
                rows.append(row)
            baseline = rows[-2]
            known = saved.loc[pool["pool_id"]]
            assert baseline["selected_nodes"] == int(known.nodes)
            assert baseline["complete_evaluable"] == bool(known.complete_evaluable)
            assert (baseline["B8L2"] is None) == pd.isna(known.B8L2)
            if baseline["B8L2"] is not None:
                assert abs(baseline["B8L2"] - known.B8L2) < 1e-7, (meta["image"], baseline["B8L2"], known.B8L2)
            print(meta["image"], n, [r["selected_nodes"] for r in rows[-3:]], flush=True)
        adjacent_zs16(engine, models)
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "ALL_17_THRESHOLD_ARMS.csv", index=False)
    pd.DataFrame(ledgers).to_csv(OUT / "ALL_17_IDENTITY_GROUPS.csv", index=False)
    paired = result.pivot(index=["image", "building", "pool_id", "n"], columns="arm",
                          values=["selected_nodes", "complete_evaluable", "B8L2", "D10", "iou_2d", "IoU3D100"])
    paired.columns = [f"{field}_{arm}" for field, arm in paired.columns]
    paired = paired.reset_index()
    for arm in ("minus_one", "plus_one"):
        paired[f"{arm}_Q_delta"] = paired[f"B8L2_{arm}"] - paired["B8L2_official"]
    paired.to_csv(OUT / "ALL_17_PAIRED.csv", index=False)
    print(paired[["image", "complete_evaluable_official", "complete_evaluable_minus_one",
                  "complete_evaluable_plus_one", "minus_one_Q_delta", "plus_one_Q_delta"]].to_string(index=False))


if __name__ == "__main__":
    main()
