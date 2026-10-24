"""Prepare fixed real A/B review pairs and compact geometry/depth diagnostics."""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Point, Polygon

from tools.thesis_main.analysis.fusion_common_panel_20261024 import serial
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores
from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_standard_metrics
from lib.misc.panostretch import pano_connect_points
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research/quality/quality_independent_validation_20261024"
EVIDENCE = ROOT / "research/statistics/v2_evidence_audit_20261019/records.json.gz"
PRIOR = ROOT / "research/quality/v2_profile_combo_quality_20261021"
ENGINE = ROOT / "research/statistics/b8l2_shared_v6_20261016/inputs"
CATEGORIES = ("range_direction_tradeoff", "structure_regularity", "global_height", "local_height", "near_score_shape")


def load_records():
    with gzip.open(EVIDENCE, "rt", encoding="utf-8") as f:
        return json.load(f)["records"]


def stable(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def metrics(record):
    return record["measurements"]["same_reference_measurements"]


def image_path(record):
    path = ROOT / "data/mp3d_layout/img_v" / (record["image_id"] + ".jpg")
    if path.exists():
        return path
    matches = list((ROOT / "data/mp3d_layout").glob("*/img/" + record["image_id"] + ".png"))
    return sorted(matches)[0] if matches else None


def register():
    OUT.mkdir(parents=True, exist_ok=True)
    records = load_records()
    prior = pd.read_csv(PRIOR / "PAIR_DIAGNOSTICS.csv")
    prior = prior[prior.pair_kind.eq("same_image_individual")]
    exposed_images = set(pd.read_csv(PRIOR / "CASE_ROWS.csv").image)
    groups = {}
    exclusions = Counter()
    for r in records:
        if r["origin"] != "new":
            exclusions["historical_v1_not_new_candidate"] += 1
            continue
        if not r["quality_usable"] or r["is_oos"] or r["is_doorway"] or not r["reference_full_available"]:
            exclusions["quality_scope_or_reference_ineligible"] += 1
            continue
        if r["image_code"] in exposed_images:
            exclusions["image_in_known_quality_case_tables"] += 1
            continue
        if r["geometry_status"] != "surface_valid" or not r["points_1024x512"] or image_path(r) is None:
            exclusions["geometry_or_image_unavailable"] += 1
            continue
        m = metrics(r)
        if not all(m.get(k) is not None for k in ("B8L2", "D10", "iou_2d", "dir", "Hmean", "Hcenter", "IoU3D100")):
            exclusions["metric_missing"] += 1
            continue
        groups.setdefault((r["image_id"], r["condition"], r["reference_id"]), []).append(r)
    candidates = []
    for group in groups.values():
        for a, b in combinations(sorted(group, key=lambda r: r["object_id"]), 2):
            ma, mb = metrics(a), metrics(b)
            delta = {k: mb[k] - ma[k] for k in ("B8L2", "D10", "iou_2d", "dir", "Hmean", "Hcenter", "IoU3D100")}
            count_diff = len(b["points_1024x512"])//2 - len(a["points_1024x512"])//2
            membership = []
            if delta["iou_2d"] * delta["dir"] > 0 and abs(delta["iou_2d"]) >= .015 and abs(delta["dir"]) >= 1:
                membership.append(CATEGORIES[0])
            if abs(count_diff) >= 2 and abs(delta["dir"]) >= 1:
                membership.append(CATEGORIES[1])
            if abs(delta["iou_2d"]) <= .05 and abs(delta["Hmean"]) >= .05:
                membership.append(CATEGORIES[2])
            if abs(delta["iou_2d"]) <= .05 and abs(delta["Hcenter"]) >= .02:
                membership.append(CATEGORIES[3])
            if abs(delta["B8L2"]) <= 3 and (abs(delta["iou_2d"]) >= .06 or abs(count_diff) >= 2):
                membership.append(CATEGORIES[4])
            if not membership:
                continue
            relation = "near" if abs(delta["B8L2"]) <= 3 or abs(delta["IoU3D100"]) <= 2 else \
                "concordant" if delta["B8L2"] * delta["IoU3D100"] > 0 else "discordant"
            key = "|".join((a["object_id"], b["object_id"]))
            for category in membership:
                candidates.append(dict(pair_key=key, category=category, metric_relation=relation,
                                       a_id=a["object_id"], b_id=b["object_id"], image=a["image_code"],
                                       building=a["building_id"], condition=a["condition"], reference_id=a["reference_id"],
                                       count_delta=count_diff, **{"delta_"+k: v for k, v in delta.items()}))
    frame = pd.DataFrame(candidates)
    frame.to_csv(OUT / "PAIR_CANDIDATE_LEDGER.csv.gz", index=False, compression="gzip")
    chosen, used_images, building_count = [], set(exposed_images), Counter()
    for category in CATEGORIES:
        available = frame[frame.category.eq(category)].copy()
        available["priority"] = available.pair_key.map(stable)
        taken = []
        for relation in ("discordant", "concordant", "near", "any"):
            subset = available if relation == "any" else available[available.metric_relation.eq(relation)]
            for r in subset.sort_values("priority").to_dict("records"):
                if r["image"] in used_images or building_count[r["building"]] >= 3:
                    continue
                taken.append(r)
                used_images.add(r["image"])
                building_count[r["building"]] += 1
                if relation != "any" or len(taken) == 4:
                    break
            if len(taken) == 4:
                break
        for row in taken:
            row.update(exposure_group="new_batch_not_in_known_quality_case_tables",
                       independence_status="candidate_new_not_certified_unseen", sampling_reason=category)
        chosen.extend(taken)
    for r in prior.itertuples(index=False):
        chosen.append(dict(pair_key="|".join((r.base_id, r.candidate_id)), category="exposed_mechanism",
                           metric_relation="historical", a_id=r.base_id, b_id=r.candidate_id, image=r.image,
                           exposure_group="previously_exposed_quality_case", independence_status="development_mechanism_only",
                           sampling_reason=r.case_id))
    selected = pd.DataFrame(chosen)
    assert selected.pair_key.is_unique and len(selected) <= 25
    selected["review_id"] = [f"QV{i+1:03d}" for i in range(len(selected))]
    selected["left_is_a"] = selected.pair_key.map(lambda s: int(stable("left|"+s), 16) % 2 == 0)
    selected.to_csv(OUT / "REVIEW_PAIR_REGISTRATION.csv", index=False)
    design = dict(schema="quality_independent_validation_design_20261024_v1",
                  new_candidate_target=20, exposed_mechanism_pairs=len(prior), actual_pairs=len(selected),
                  categories={k:4 for k in CATEGORIES}, candidate_counts=frame.groupby("category").size().to_dict(),
                  exclusions=dict(exclusions), selection="fixed_threshold_strata_then_SHA256_pair_id; one_new_pair_per_image; max3_per_building",
                  relation_priority=["discordant", "concordant", "near", "any"],
                  no_new_parameter_tuning=True, human_answers="pending_not_filled",
                  exposure_sources=["research/quality_parallel_local_20261012/exposure_ledger.json",
                                    "research/quality_holdout_exposure_correction_20261011/exposure_registry.json",
                                    "research/quality/v2_profile_combo_quality_20261021/CASE_ROWS.csv"],
                  independence="new batch excludes known quality-case images; other historical viewing is not certified absent",
                  official_reference="https://github.com/sunset1995/HorizonNet/blob/master/eval_general.py",
                  camera_height="both layouts normalized to camera height1; HorizonNet depth uses1.6m for both",
                  coordinate_conversion="continuous3D_to_HorizonNet_pixel_center; every top vertex preserved",
                  no_population_win_rate_estimation=True)
    (OUT / "DESIGN.json").write_text(json.dumps(serial(design), ensure_ascii=False, indent=2), encoding="utf-8")
    print("registered", len(selected), selected.category.value_counts().to_dict(), flush=True)


def join_human_answers(answers, mapping, frame):
    """Keep comments and non-directional answers intact when revealing metrics."""
    if answers.get("schema") != "quality_independent_human_answers_20261024_v1" or \
            answers.get("review_set") != "hohonet_quality_review_20261024_v1":
        raise ValueError("unexpected human answer schema or review set")
    ids = [m["review_id"] for m in mapping]
    if len(set(ids)) != len(ids) or not set(answers["answers"]).issubset(ids) or \
            answers["question_count"] != len(ids):
        raise ValueError("human answer keys do not match the fixed review mapping")
    if frame.duplicated(["review_id", "object_id"]).any() or len(frame) != 2*len(mapping):
        raise ValueError("expected exactly two distinct original annotations per review")
    measured = frame.set_index(["review_id", "object_id"])
    directions = {"B8L2": 1, "D10": 1, "IoU3D100": 1, "iou_2d": 1,
                  "legacy_iou3d_mean_height": 1, "layout_depth_rmse_m": -1,
                  "layout_depth_delta1": 1, "S_bottom_deg": -1, "dir": -1,
                  "Hmean": -1, "Hcenter": -1}
    rows = []
    for m in mapping:
        key = m["review_id"]
        answer = answers["answers"].get(key, dict(choice=None, reason=""))
        choice = answer["choice"]
        if choice not in (None, "left", "right", "close", "uncertain") or not isinstance(answer["reason"], str):
            raise ValueError(f"invalid choice or comment: {key}")
        left = measured.loc[(key, m["left_object_id"])]
        right = measured.loc[(key, m["right_object_id"])]
        if m["left_object_id"] == m["right_object_id"] or \
                left.reference_id != right.reference_id or left.reference_id != m["reference_id"] or \
                left.image != right.image or left.image != m["image"] or left.condition != right.condition:
            raise ValueError(f"identity, condition or reference mismatch: {key}")
        row = {**m, "condition": left.condition, "human_choice": choice,
               "human_comment": answer["reason"], "human_updated_at": answer.get("updated_at"),
               "directional_human_answer": choice in ("left", "right")}
        for metric, direction in directions.items():
            lv, rv = float(left[metric]), float(right[metric])
            if not np.isfinite([lv, rv]).all():
                raise ValueError(f"missing comparison metric: {key}/{metric}")
            delta = rv-lv
            preference = "equal" if delta == 0 else "right" if direction*delta > 0 else "left"
            row.update({"left_"+metric: lv, "right_"+metric: rv, "delta_right_minus_left_"+metric: delta,
                        "preferred_"+metric: preference,
                        "agrees_human_"+metric: preference == choice if choice in ("left", "right") else None})
        rows.append(row)
    if answers["answered_count"] != sum(r["human_choice"] is not None for r in rows):
        raise ValueError("answered_count is inconsistent with actual choices")
    return pd.DataFrame(rows)


def review():
    answers = json.loads((OUT / "human_review/ANSWERS_ORIGINAL.json").read_text(encoding="utf-8"))
    mapping = json.loads((OUT / "REVIEW_MAPPING_PRIVATE.json").read_text(encoding="utf-8"))
    frame = join_human_answers(answers, mapping, pd.read_csv(OUT / "REVIEW_METRICS_PRIVATE.csv"))
    frame.to_csv(OUT / "human_review/ANSWER_METRIC_COMPARISON.csv", index=False)
    summaries = []
    for (group, condition), part in frame.groupby(["exposure_group", "condition"], sort=False):
        decisive = part[part.directional_human_answer]
        for metric in ("B8L2", "D10", "IoU3D100", "iou_2d", "legacy_iou3d_mean_height",
                       "layout_depth_rmse_m", "layout_depth_delta1"):
            summaries.append(dict(exposure_group=group, condition=condition, metric=metric, received_pairs=len(part),
                                  directional_pairs=len(decisive), directional_images=decisive.image.nunique(),
                                  directional_buildings=decisive.building.nunique(),
                                  same_direction=int(decisive["agrees_human_"+metric].sum()),
                                  opposite_direction=int((decisive["preferred_"+metric] != decisive.human_choice).sum()
                                                         -(decisive["preferred_"+metric] == "equal").sum()),
                                  exact_numeric_tie=int((decisive["preferred_"+metric] == "equal").sum()),
                                  close_answers=int(part.human_choice.eq("close").sum()),
                                  uncertain_answers=int(part.human_choice.eq("uncertain").sum())))
    pd.DataFrame(summaries).to_csv(OUT / "human_review/METRIC_DIRECTION_SUMMARY.csv", index=False)
    print("human answers joined", len(frame), frame.human_choice.value_counts().to_dict(), flush=True)


def geometry_to_cor(geometry):
    top, bottom = np.asarray(geometry["top3d"]), np.asarray(geometry["bottom3d"])
    result = []
    for a, b in zip(top, bottom):
        for point in (a, b):
            norm = np.linalg.norm(point)
            x = ((np.arctan2(point[0], -point[2]) / (2*np.pi) + .5) % 1)*1024-.5
            y = (.5-np.arcsin(np.clip(point[1]/norm, -1, 1))/np.pi)*512-.5
            result.append([float(x), float(y)])
    return np.asarray(result)


def corner_metrics(a, b):
    va = np.asarray(a["bottom3d"], float)
    vb = np.asarray(b["bottom3d"], float)
    va /= np.linalg.norm(va, axis=1)[:, None]
    vb /= np.linalg.norm(vb, axis=1)[:, None]
    distance = np.degrees(np.arccos(np.clip(va @ vb.T, -1, 1)))
    i, j = linear_sum_assignment(distance)
    valid = distance[i, j] <= 9
    return dict(corner_bottom_precision_9=float(valid.sum()/len(va)),
                corner_bottom_recall_9=float(valid.sum()/len(vb)),
                corner_bottom_assignment_mean_deg=float(distance[i, j].mean()),
                candidate_corners=len(va), reference_corners=len(vb))


def evaluate_geometry(geometry, reference):
    for value in (geometry,reference):
        bottom,top=np.asarray(value["bottom3d"],float),np.asarray(value["top3d"],float)
        if bottom.ndim!=2 or bottom.shape!=top.shape or bottom.shape[1:]!=(3,) or len(bottom)<4 or \
                not np.isfinite(bottom).all() or not np.isfinite(top).all():
            return dict(legacy_status="invalid_complete_geometry")
        if not np.allclose(bottom[:,1],-1) or not np.allclose(bottom[:,[0,2]],top[:,[0,2]]):
            return dict(legacy_status="requires_camera_height_or_vertical_pair_normalization")
        floor=Polygon(bottom[:,[0,2]])
        if not floor.is_valid or floor.area<=0 or not floor.contains(Point(0,0)):
            return dict(legacy_status="invalid_floor_or_camera_outside")
    dt, gt = geometry_to_cor(geometry), geometry_to_cor(reference)
    # Preserve the caller's declared ring; reject incompatible hemisphere/ray geometry explicitly.
    if np.any(dt[::2,1] >= 255.5) or np.any(dt[1::2,1] <= 255.5) or \
            np.any(gt[::2,1] >= 255.5) or np.any(gt[1::2,1] <= 255.5):
        return dict(legacy_status="incompatible_top_or_bottom_hemisphere")
    i2, i3, rmse, delta, used, info = compute_layout_standard_metrics(dt, gt, ordered_source=True)
    return dict(legacy_status="ok" if used and rmse is not None else info["gate_reason"],
                legacy_iou2d=i2, legacy_iou3d_mean_height=i3, layout_depth_rmse_m=rmse,
                layout_depth_rmse_camera_h=rmse/1.6 if rmse is not None else None,
                layout_depth_delta1=delta, **corner_metrics(geometry, reference))


def display_layout(points, geometry):
    # Keep every declared edge; a per-column outer envelope can hide concave-ring segments.
    p=np.asarray(points,float)-.5
    segments=[(pano_connect_points(p[i],p[(i+2)%len(p)],z=-50 if i%2==0 else 50,w=1024,h=512)+.5).tolist()
              for i in range(len(p))]
    return dict(points=points, edge_segments=segments,
                floor=[[p[0],p[2]] for p in geometry["bottom3d"]],
                bottom3d=geometry["bottom3d"], top3d=geometry["top3d"])


def saved_mechanisms(engine, models, records):
    snapshot = ROOT / "research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz"
    with gzip.open(snapshot,"rt",encoding="utf-8") as stream:
        pools={p["pool_id"]:p for p in json.load(stream)["images"]}
    path=ROOT / "research/workers/personnel_composition_followup_20261019"
    cases=json.loads((path / "STRUCTURE_CASES.json").read_text(encoding="utf-8"))["cases"]
    with gzip.open(path / "TEAMS.json.gz","rt",encoding="utf-8") as stream:
        teams=json.load(stream)
    sources=[]
    for case in cases:
        for arm,value in case["teams"].items():
            team=teams[value["key"]]
            sources.append((case["case"],arm,team,pools[team["pool_id"]]["reference"]["points_1024x512"]))
    s09=json.loads((ROOT / "research/workers/personnel_interchangeability_20261020/interchangeability_20261020/cases/S09_same_composition_different_shape.json").read_text(encoding="utf-8"))
    sources.extend(("S09",t["label"],t,s09["reference"]["points_1024x512"]) for t in s09["teams"])
    rows=[]
    for case,arm,team,refpoints in sources:
        points=team["geometry"].get("points")
        row=dict(case_id=case,arm=arm,team_key=team["team_key"],image=team["image"],
                 exposure_group="previously_exposed_mechanism",status="missing_connected_geometry")
        if points is not None:
            geom,ref=engine.geometry(points),engine.geometry(refpoints)
            measured=engine.measure(geom,ref)
            row["status"]=measured["status"]
            if measured["status"]=="complete":
                m=measured["metrics"]
                row.update({k:m[k] for k in ("iou_2d","S_bottom_deg","dir","Hmean","Hcenter")},
                           **dual_scores(m,models),**evaluate_geometry(geom,ref))
                assert abs(row["B8L2"]-team["B8L2"])<1e-7
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "EXPOSED_STRUCTURE_AND_NEAR_SCORE_METRICS.csv",index=False)
    point_rows=[]
    for oid,pair in (("v2:new:100738",1),("v2:new:101870",0)):
        r=records[oid]
        ref=engine.geometry(r["reference_evidence"]["points_1024x512"])
        for dy in (-2,0,2):
            points=[p.copy() for p in r["points_1024x512"]]
            points[2*pair+1][1]+=dy
            geom=engine.geometry(points)
            m=engine.measure(geom,ref)
            assert m["status"]=="complete"
            point_rows.append(dict(object_id=oid,image=r["image_code"],pair_index=pair,dy_px=dy,
                                   **dual_scores(m["metrics"],models),**evaluate_geometry(geom,ref)))
    pd.DataFrame(point_rows).to_csv(OUT / "BOTTOM_POINT_CONTROL_METRICS.csv",index=False)


def build():
    pairs = pd.read_csv(OUT / "REVIEW_PAIR_REGISTRATION.csv")
    records = {r["object_id"]:r for r in load_records()}
    rows, review_cases, mapping = [], [], []
    with scoring_engine(ENGINE / "measurement_engine.zip", ENGINE / "working_models.py") as (engine, models):
        for pair in pairs.itertuples(index=False):
            a, b = records[pair.a_id], records[pair.b_id]
            assert a["image_id"] == b["image_id"] and a["reference_id"] == b["reference_id"]
            assert a["quality_usable"] and b["quality_usable"] and not a["is_oos"] and not b["is_oos"]
            refpoints = a["reference_evidence"]["points_1024x512"]
            assert refpoints == b["reference_evidence"]["points_1024x512"]
            refgeom = engine.geometry(refpoints)
            layouts = {}
            for side, record in (("a", a), ("b", b)):
                geom = engine.geometry(record["points_1024x512"])
                m = metrics(record)
                assert max(abs(dual_scores(m,models)[k]-m[k]) for k in ("B8L2","D10"))<1e-7
                numeric = evaluate_geometry(geom, refgeom)
                rows.append(dict(review_id=pair.review_id, canonical_side=side, object_id=record["object_id"],
                                 image=record["image_code"], building=record["building_id"], condition=record["condition"],
                                 reference_id=record["reference_id"], category=pair.category,
                                 exposure_group=pair.exposure_group, independence_status=pair.independence_status,
                                 **{k:m[k] for k in ("B8L2","D10","iou_2d","IoU3D100","S_bottom_deg","dir","Hmean","Hcenter")},
                                 **numeric))
                layouts[side] = display_layout(record["points_1024x512"], geom)
            img = image_path(a)
            mime = "image/jpeg" if img.suffix.lower() == ".jpg" else "image/png"
            image_data = "data:"+mime+";base64,"+base64.b64encode(img.read_bytes()).decode("ascii")
            left, right = ("a", "b") if pair.left_is_a else ("b", "a")
            review_cases.append(dict(id=pair.review_id, image=pair.image, image_data=image_data,
                                     left=layouts[left], right=layouts[right],
                                     reference=display_layout(refpoints, refgeom)))
            mapping.append(dict(review_id=pair.review_id, left_object_id=a["object_id"] if pair.left_is_a else b["object_id"],
                                right_object_id=b["object_id"] if pair.left_is_a else a["object_id"],
                                image=pair.image, building=a["building_id"], category=pair.category,
                                exposure_group=pair.exposure_group, independence_status=pair.independence_status,
                                source_image=img.relative_to(ROOT).as_posix(), reference_id=a["reference_id"]))
        controls = json.loads((ROOT / "research/quality_height_calibration_ready_20261013/CONTROLS.json").read_text(encoding="utf-8"))
        control_rows = []
        for control in controls["records"]:
            metric = control["metrics"]
            if "annotation_geometry" not in control:
                control_rows.append(dict(case_id=control["case_id"],kind=control["kind"],origin=control["origin"],
                                         **{k:metric[k] for k in ("iou_2d","S_bottom_deg","dir","Hmean","Hcenter")},
                                         **dual_scores(metric,models),legacy_status="source_geometry_not_archived"))
                continue
            control_rows.append(dict(case_id=control["case_id"], kind=control["kind"], origin=control["origin"],
                                     **{k:metric[k] for k in ("iou_2d","S_bottom_deg","dir","Hmean","Hcenter")},
                                     **dual_scores(metric, models),
                                     **evaluate_geometry(control["annotation_geometry"], control["reference_geometry"])))
        saved_mechanisms(engine,models,records)
    frame = pd.DataFrame(rows)
    assert len(frame) == 2*len(pairs) and not frame.duplicated(["review_id","canonical_side"]).any()
    frame.to_csv(OUT / "REVIEW_METRICS_PRIVATE.csv", index=False)
    pd.DataFrame(control_rows).to_csv(OUT / "HEIGHT_CONTROL_METRICS.csv", index=False)
    (OUT / "REVIEW_MAPPING_PRIVATE.json").write_text(json.dumps(serial(mapping), ensure_ascii=False, indent=2), encoding="utf-8")
    template = (OUT / "REVIEW_TEMPLATE.html").read_text(encoding="utf-8")
    payload = json.dumps(serial(review_cases), ensure_ascii=False, separators=(",",":"))
    (OUT / "index.html").write_text(template.replace("__CASES_JSON__",payload), encoding="utf-8")
    print("built", len(pairs), "pairs", len(control_rows), "controls", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register", "build", "review"))
    {"register": register, "build": build, "review": review}[parser.parse_args().action]()
