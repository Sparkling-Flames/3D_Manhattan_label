"""Fixed v2 member panel: saved automatic wall line, no-GT medoid, Lee MV50."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from shapely.errors import GEOSException
from shapely.geometry import LineString, Polygon, mapping

from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores
from tools.thesis_main.analysis.research_round_20260929 import reconstruct
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research/workers/personnel_population_curves_v2_20261023"
OUT = ROOT / "research/fusion/fusion_common_panel_20261024"
ENGINE = ROOT / "research/statistics/b8l2_shared_v6_20261016/inputs"
TARGETS = {
    ("ordinary_manual", "简单"): 8,
    ("ordinary_manual", "中等"): 8,
    ("ordinary_manual", "困难"): 8,
    ("ordinary_semi", "简单"): 8,
    ("ordinary_semi", "中等"): 4,
    ("ordinary_semi", "困难"): 1,
    ("doorway_manual", "单列"): 8,
    ("special_manual", "简单"): 1,
    ("special_manual", "困难"): 1,
    ("special_semi", "简单"): 1,
}
SIZES = (4, 8, 16)
METRICS = ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter")
DIAGNOSTICS = ("corner_bottom_precision_9", "corner_bottom_recall_9", "corner_assignment_mean_deg",
               "diagnostic_turn5_n", "diagnostic_short_edge_005_n", "centroid_distance_h")


def read_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def serial(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def stable(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_pools(pool: pd.DataFrame, count: int) -> pd.DataFrame:
    by_building = {b: g.sort_values("pool_id", key=lambda s: s.map(stable)).to_dict("records")
                   for b, g in pool.groupby("building")}
    order = sorted(by_building, key=stable)
    chosen = []
    for rank in range(max(map(len, by_building.values()))):
        chosen.extend(by_building[b][rank] for b in order if len(by_building[b]) > rank)
        if len(chosen) >= count:
            break
    return pd.DataFrame(chosen[:count])


def register() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pools = pd.read_csv(SOURCE / "design/ACTUAL_POOLS.csv")
    requests = read_gz(SOURCE / "inputs/REQUESTS_INITIAL.json.gz")["requests"]
    members = {p["pool_id"]:{r["worker_id"]:r["object_id"] for r in p["records"]}
               for p in read_gz(SOURCE / "inputs/INPUT_SNAPSHOT.json.gz")["images"]}
    request = {(r["pool_id"], r["k"]): r for r in requests
               if r.get("request_family") == "uniform_prefix" and r.get("draw_id") == 0
               and r["k"] in SIZES}
    chosen = []
    for key, count in TARGETS.items():
        candidates = pools[pools.layer.eq(key[0]) & pools.difficulty.eq(key[1]) & pools.pool_n.ge(4)]
        assert len(candidates) >= count, (key, len(candidates))
        subset = select_pools(candidates, count)
        subset["registration_stratum"] = "/".join(key)
        chosen.append(subset)
    panel = pd.concat(chosen, ignore_index=True)
    assert len(panel) == sum(TARGETS.values()) and panel.pool_id.is_unique
    panel[["pool_id", "image", "image_id", "building", "condition", "layer", "difficulty", "scene", "pool_n",
           "reference_id", "reference_version", "registration_stratum"]].to_csv(OUT / "POOL_REGISTRATION.csv", index=False)
    teams = []
    for p in panel.itertuples(index=False):
        for n in SIZES:
            if n > p.pool_n:
                continue
            r = request[p.pool_id, n]
            teams.append(dict(pool_id=p.pool_id, image=p.image, image_id=p.image_id, building=p.building,
                              condition=p.condition, layer=p.layer, difficulty=p.difficulty, scene=p.scene,
                              reference_id=p.reference_id, reference_version=p.reference_version,
                              n=n, request_id=r["request_id"], member_workers="|".join(sorted(r["worker_ids"])),
                              member_object_ids="|".join(sorted(members[p.pool_id][w] for w in r["worker_ids"])),
                              source_policy="uniform_prefix_draw0_preexisting"))
    pd.DataFrame(teams).to_csv(OUT / "TEAM_REGISTRATION.csv", index=False)
    (OUT / "DESIGN.json").write_text(json.dumps(dict(
        schema="fusion_common_panel_registration_20261024_v1", method_versions=dict(
            wall="MV50_gap7.5_automatic_saved_v2", medoid="valid_complete_source_min_mean_pairwise_1_minus_BEV_IoU",
            lee="lee_tile_stage1_20261002_mv50"),
        selection="building_round_robin_then_SHA256_pool_id; existing_uniform_prefix_draw0",
        strata={"/".join(k): v for k, v in TARGETS.items()}, sizes=SIZES,
        no_target_gt_or_score_in_panel_selection=True,
        medoid_tie="minimum_mean_distance_rounded_12_decimals_then_object_id",
        lee_capability="floor_only", oos="not_in_this_v2_source_snapshot"),
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("registered", len(panel), len(teams), flush=True)


def polygon(points):
    if points is None or len(points) < 3:
        return None
    p = Polygon(points)
    return p if p.is_valid and p.area > 0 and np.isfinite(p.area) else None


def floor_metrics(poly, ref):
    if poly is None:
        return {}
    intersection = poly.intersection(ref).area
    union = poly.area + ref.area - intersection
    return dict(iou_2d=intersection / union if union > 0 else None,
                omission=(ref.area - intersection) / ref.area,
                extension=(poly.area - intersection) / ref.area,
                symdiff_over_ref=poly.symmetric_difference(ref).area / ref.area,
                area_h2=poly.area, centroid_distance_h=poly.centroid.distance(ref.centroid))


def corner_diagnostics(points, reference):
    a,b=np.asarray(points,float),np.asarray(reference,float)
    if np.allclose(a[0],a[-1]):
        a=a[:-1]
    va=np.column_stack((a[:,0],-np.ones(len(a)),a[:,1]))
    vb=np.column_stack((b[:,0],-np.ones(len(b)),b[:,1]))
    va/=np.linalg.norm(va,axis=1)[:,None]
    vb/=np.linalg.norm(vb,axis=1)[:,None]
    distance=np.degrees(np.arccos(np.clip(va@vb.T,-1,1)))
    i,j=linear_sum_assignment(distance)
    matches=distance[i,j]<=9
    edges=np.roll(a,-1,axis=0)-a
    lengths=np.linalg.norm(edges,axis=1)
    turn=np.degrees(np.arccos(np.clip(np.sum(edges*np.roll(edges,1,axis=0),axis=1)/
                                    (lengths*np.roll(lengths,1)),-1,1)))
    return dict(corner_bottom_precision_9=float(matches.sum()/len(a)),corner_bottom_recall_9=float(matches.sum()/len(b)),
                corner_assignment_mean_deg=float(distance[i,j].mean()),diagnostic_turn5_n=int((turn>5).sum()),
                diagnostic_short_edge_005_n=int((lengths<.05).sum()))


def medoid(records):
    legal, exclusions = [], []
    for r in records:
        v = reconstruct(r, coordinate_convention="continuous")
        p = polygon(v.get("floor")) if v["status"] == "ok" else None
        if p is None or not r.get("points") or len(r["points"]) < 8:
            exclusions.append(dict(worker_id=r["worker_id"], object_id=r["object_id"],
                                   reason=v.get("reason") or "invalid_or_under_four_pairs"))
        else:
            legal.append((r, p))
    if not legal:
        return None, None, exclusions, None
    means = []
    for i, (r, p) in enumerate(legal):
        distances = []
        for j, (_, other) in enumerate(legal):
            if i != j:
                distances.append(1 - p.intersection(other).area / p.union(other).area)
        means.append((round(float(np.mean(distances)), 12) if distances else 0.0, str(r["object_id"]), i))
    chosen = min(means)
    return *legal[chosen[2]], exclusions, chosen[0]


def run() -> None:
    assert (OUT / "DESIGN.json").exists(), "register_first"
    registration = pd.read_csv(OUT / "TEAM_REGISTRATION.csv").fillna("")
    snapshot = {p["pool_id"]: p for p in read_gz(SOURCE / "inputs/INPUT_SNAPSHOT.json.gz")["images"]}
    cols = ["team_key", "pool_id", "member_workers", "k", "reference_id", "reference_version", "score_status",
            "geometry_status", "complete_evaluable", "floor_evaluable", "nodes", "reference_nodes", "fusion_turn_n",
            "fusion_short_turn_edges", "failure", "score_available", "iou_2d", "IoU3D100", "S_bottom_deg",
            "dir", "Hmean", "Hcenter", "B8L2", "D10", "omission", "extension"]
    # The scalar export stores failure as score_status/geometry_status rather than a failure column.
    cols.remove("failure")
    scalar = pd.read_csv(SOURCE / "results/ENDPOINT_SCALARS.csv.gz", usecols=cols)
    scalar = scalar.rename(columns={"k": "n"})
    assert not scalar.duplicated(["pool_id", "member_workers"]).any()
    registered = registration.merge(scalar, on=["pool_id", "member_workers", "n"], how="left",
                                    suffixes=("_registered", "_saved"), validate="one_to_one", indicator=True)
    assert registered._merge.eq("both").all(), registered._merge.value_counts().to_dict()
    assert registered.reference_id_registered.eq(registered.reference_id_saved).all()
    assert registered.reference_version_registered.eq(registered.reference_version_saved).all()
    keys = set(registered.team_key)
    geometry = {r["team_key"]: r for r in read_gz(SOURCE / "results/ENDPOINT_GEOMETRY.json.gz") if r["team_key"] in keys}
    assert len(geometry) == len(keys)
    outputs, geoms, exclusions = [], [], []
    with scoring_engine(ENGINE / "measurement_engine.zip", ENGINE / "working_models.py") as (engine, models):
        for row in registered.itertuples(index=False):
            pool = snapshot[row.pool_id]
            assert pool["meta"]["reference_id"] == row.reference_id_saved
            workers = row.member_workers.split("|")
            lookup = {r["worker_id"]: r for r in pool["records"]}
            selected = [lookup[w] for w in workers]
            assert len({r["object_id"] for r in selected}) == row.n
            assert row.member_object_ids == "|".join(sorted(r["object_id"] for r in selected))
            ref = polygon(pool["reference"]["floor_xz_h"])
            assert ref is not None
            base = dict(team_key=row.team_key, pool_id=row.pool_id, image=row.image, building=row.building,
                        condition=row.condition, layer=row.layer, difficulty=row.difficulty, scene=row.scene,
                        n=row.n, member_workers=row.member_workers, reference_id=row.reference_id_saved,
                        reference_version=row.reference_version_saved,request_id=row.request_id,
                        member_object_ids=row.member_object_ids,source_all_quality_usable=all(r["quality_usable"] for r in selected))
            wall = geometry[row.team_key]["geometry"]
            assert geometry[row.team_key]["pool_id"] == row.pool_id
            wall_poly = polygon(wall.get("footprint"))
            wall_values = {metric: getattr(row, metric) for metric in METRICS}
            outputs.append(dict(base, method="wall_auto", method_version="MV50_gap7.5_automatic_saved_v2",
                                full_output=bool(row.complete_evaluable), floor_output=wall_poly is not None,
                                output_status=row.score_status, geometry_status=row.geometry_status,
                                source_record_id="", eligible_source_n=row.n, excluded_source_n=0,
                                selected_distance=None, nodes=row.nodes, reference_nodes=row.reference_nodes,
                                turn_n=row.fusion_turn_n, short_turn_edges=row.fusion_short_turn_edges,
                                **floor_metrics(wall_poly, ref), **{k: v for k, v in wall_values.items() if k != "iou_2d"}))
            geoms.append(dict(team_key=row.team_key, method="wall_auto", points=wall.get("points"),
                              footprint=wall.get("footprint"), status=wall.get("status")))

            mr, mp, omitted, distance = medoid(selected)
            exclusions.extend(dict(base, **e) for e in omitted)
            measured = {}
            status = "no_valid_complete_representative"
            if mr is not None:
                try:
                    m = engine.measure(engine.geometry(mr["points"]),
                                       engine.geometry(pool["reference"]["points_1024x512"]))
                    if m["status"] == "complete":
                        measured = {k: m["metrics"].get(k) for k in METRICS if k not in ("B8L2", "D10", "IoU3D100")}
                        measured.update(dual_scores(m["metrics"], models))
                        measured["IoU3D100"] = 100 * m["metrics"]["iou_3d_corner_mean"]
                        if mr.get("B8L2") is not None:
                            assert abs(measured["B8L2"]-mr["B8L2"]) < 1e-7, "source_score_changed"
                        status = "complete"
                    else:
                        status = "measurement_" + str(m["status"])
                except (ValueError, ArithmeticError, TypeError) as error:
                    status = "measurement_" + type(error).__name__
            outputs.append(dict(base, method="medoid", method_version="mean_pairwise_BEV_Jaccard_no_GT",
                                full_output=mr is not None, floor_output=mp is not None,
                                output_status=status, geometry_status=mr.get("geometry_status") if mr else "missing",
                                source_record_id=mr["object_id"] if mr else "", eligible_source_n=row.n-len(omitted),
                                excluded_source_n=len(omitted), selected_distance=distance,
                                nodes=len(mr["points"])//2 if mr else None,
                                reference_nodes=len(pool["reference"]["points_1024x512"])//2,
                                turn_n=None, short_turn_edges=None,
                                **{**floor_metrics(mp, ref), **{k: v for k, v in measured.items() if k != "iou_2d"}}))
            geoms.append(dict(team_key=row.team_key, method="medoid", points=mr["points"] if mr else None,
                              footprint=list(map(list, mp.exterior.coords)) if mp is not None else None, status=status))

            lee_inputs = []
            for r in selected:
                shape = reconstruct(r, coordinate_convention="continuous")
                lee_inputs.append(dict(id=r["object_id"], worker=r["worker_id"], footprint=shape.get("floor")))
            try:
                vote = tile_consensus(lee_inputs)
                lp = vote["regions"]["mv50"]
                lee_status = "ok" if not lp.is_empty and lp.is_valid and lp.area > 0 else "empty_or_invalid_region"
            except (ValueError, GEOSException) as error:
                lp, lee_status = None, type(error).__name__ + ":" + str(error)
            outputs.append(dict(base, method="lee_mv50", method_version="lee_tile_stage1_20261002_mv50",
                                full_output=False, floor_output=lee_status == "ok", output_status=lee_status,
                                geometry_status="floor_only" if lee_status == "ok" else "unavailable",
                                source_record_id="", eligible_source_n=row.n, excluded_source_n=0,
                                selected_distance=None, nodes=None,
                                reference_nodes=len(pool["reference"]["points_1024x512"])//2,
                                turn_n=None, short_turn_edges=None,
                                **floor_metrics(lp, ref)))
            geoms.append(dict(team_key=row.team_key, method="lee_mv50", points=None,
                              footprint=mapping(lp) if lee_status == "ok" else None, status=lee_status))
            print("evaluated", row.pool_id, row.n, flush=True)
    frame = pd.DataFrame(outputs)
    assert frame.groupby("team_key").method.nunique().eq(3).all()
    frame["declared_capability"] = np.where(frame.method.eq("lee_mv50"), "floor_region", "complete_layout")
    frame["full_evaluable"] = frame[list(METRICS)].notna().all(axis=1)
    frame["below_four"] = frame.nodes.lt(4).where(frame.nodes.notna())
    geometry_by = {(g["team_key"],g["method"]):g for g in geoms}
    frame["missing_connection"] = [geometry_by[r.team_key,r.method]["points"] is None
                                    if r.method != "lee_mv50" else None for r in frame.itertuples()]
    frame["self_intersection"] = [not LineString([*g["footprint"],g["footprint"][0]]).is_simple
                                   if isinstance(g["footprint"],list) and len(g["footprint"]) >= 3 else None
                                   for g in (geometry_by[r.team_key,r.method] for r in frame.itertuples())]
    diagnostics=[]
    for r in frame.itertuples():
        g=geometry_by[r.team_key,r.method]
        diagnostics.append(corner_diagnostics(g["footprint"],snapshot[r.pool_id]["reference"]["floor_xz_h"])
                           if isinstance(g["footprint"],list) and len(g["footprint"])>=3 else {})
    frame=pd.concat([frame,pd.DataFrame(diagnostics)],axis=1)
    frame.to_csv(OUT / "METHOD_ENDPOINTS.csv", index=False)
    pd.DataFrame(exclusions,columns=[*base.keys(),"worker_id","object_id","reason"]).to_csv(OUT / "MEDOID_EXCLUSIONS.csv", index=False)
    (OUT / "METHOD_GEOMETRY.json").write_text(json.dumps(serial(geoms), ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print("complete", len(frame), flush=True)


def summarize() -> None:
    frame = pd.read_csv(OUT / "METHOD_ENDPOINTS.csv")
    groups = ["condition","layer","difficulty","n","method","declared_capability"]
    status=frame.groupby(groups, dropna=False).agg(attempts=("team_key","size"), images=("image","nunique"),
        buildings=("building","nunique"), full_outputs=("full_output","sum"), floor_outputs=("floor_output","sum"),
        full_evaluable=("full_evaluable","sum"), missing_connections=("missing_connection","sum"),
        below_four=("below_four","sum"), self_intersections=("self_intersection","sum")).reset_index()
    for column in ("attempts","images","buildings","full_outputs","floor_outputs","full_evaluable",
                   "missing_connections","below_four","self_intersections"):
        status[column]=status[column].astype(int)
    status.to_csv(OUT / "ALL_ATTEMPT_STATUS.csv", index=False)
    meta = ["team_key","pool_id","image","building","condition","layer","difficulty","n"]
    wide = {method:g.set_index("team_key",verify_integrity=True).sort_index() for method,g in frame.groupby("method")}
    shared_floor=np.logical_and.reduce([g.floor_output & g.iou_2d.notna() for g in wide.values()])
    floor_rows=[]
    for method,g in wide.items():
        here=g.loc[shared_floor,meta[1:]+["iou_2d"]].reset_index()
        here["method"]=method
        floor_rows.append(here)
    floor_common=pd.concat(floor_rows,ignore_index=True)
    assert floor_common.groupby("team_key").method.nunique().eq(3).all()
    floor_common.to_csv(OUT / "THREE_METHOD_COMMON_FLOOR.csv",index=False)
    floor_common.groupby(["condition","layer","difficulty","n","method"]).agg(
        teams=("team_key","size"),images=("image","nunique"),buildings=("building","nunique"),
        iou_mean=("iou_2d","mean"),iou_p10=("iou_2d",lambda x:x.quantile(.1))).reset_index().to_csv(
            OUT / "THREE_METHOD_FLOOR_SUMMARY.csv",index=False)
    pairs = []
    for left,right,domain in (("wall_auto","medoid","complete_layout"),("wall_auto","medoid","floor_region"),
                              ("lee_mv50","medoid","floor_region"),("wall_auto","lee_mv50","floor_region")):
        a,b = wide[left],wide[right]
        assert set(a.index)==set(b.index)
        for metric in METRICS+DIAGNOSTICS if domain == "complete_layout" else ("iou_2d",):
            valid = a[metric].notna() & b[metric].notna()
            if domain == "complete_layout":
                valid &= a.full_evaluable & b.full_evaluable
            pair = a.loc[valid,meta[1:]].reset_index()
            pair["comparison"],pair["metric"] = left+"_minus_"+right,metric
            pair["support_domain"] = domain
            pair["left_value"],pair["right_value"] = a.loc[valid,metric].to_numpy(),b.loc[valid,metric].to_numpy()
            pair["delta"] = pair.left_value-pair.right_value
            pairs.append(pair)
    pairs = pd.concat(pairs,ignore_index=True)
    pairs.to_csv(OUT / "COMMON_TEAM_METRICS.csv",index=False)
    keys=["condition","layer","difficulty","n","comparison","support_domain","metric"]
    image=pairs.groupby(keys+["image","building"]).agg(teams=("team_key","size"),
        left_value=("left_value","mean"),right_value=("right_value","mean"),delta=("delta","mean")).reset_index()
    image.to_csv(OUT / "COMMON_IMAGE_METRICS.csv",index=False)
    image.groupby(keys).agg(images=("image","nunique"),buildings=("building","nunique"),teams=("teams","sum"),
        left_mean=("left_value","mean"),right_mean=("right_value","mean"),left_p10=("left_value",lambda x:x.quantile(.1)),
        right_p10=("right_value",lambda x:x.quantile(.1)),mean_delta=("delta","mean"),
        positive_images=("delta",lambda x:int((x>1e-9).sum())),negative_images=("delta",lambda x:int((x< -1e-9).sum()))).reset_index().to_csv(
            OUT / "COMMON_SCENE_SUMMARY.csv",index=False)
    building=image.groupby(keys+["building"]).agg(images=("image","nunique"),left_value=("left_value","mean"),
        right_value=("right_value","mean"),delta=("delta","mean")).reset_index()
    building.to_csv(OUT / "COMMON_BUILDING_METRICS.csv",index=False)
    print("summarized",len(pairs),len(image),len(building),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "run", "summarize"))
    action = parser.parse_args().action
    {"register":register,"run":run,"summarize":summarize}[action]()
