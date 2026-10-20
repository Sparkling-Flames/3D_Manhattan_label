"""Diagnose top and bottom contributions to the frozen Semi height candidate.

Only same-count annotations are compared. Bottom-ray Hungarian correspondence
is diagnostic, with 9/12 degree maximum matched-angle reporting. Counterfactual
top/bottom combinations decompose the existing viewer height formula; they are
never used as edited annotations or as fusion inputs.
"""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from run_classification import HERE, ROOT, load_expression

OUT = HERE / "semi_new_candidate"


def ray(p):
    u, v = 2 * np.pi * (p[:, 0] / 1024 - .5), np.pi * (.5 - p[:, 1] / 512)
    return np.column_stack([np.cos(v) * np.sin(u), np.sin(v), -np.cos(v) * np.cos(u)])


def height(top_y, bottom_y):
    top = np.pi * (.5 - top_y / 512)
    bottom = np.pi * (bottom_y / 512 - .5)
    return 1 + np.mean(np.tan(top) / np.tan(bottom))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, default=ROOT)
    args = ap.parse_args()
    records = json.load(gzip.open(args.source_root / "research/statistics/v2_evidence_audit_20261019/records.json.gz", "rt", encoding="utf8"))["records"]
    records = {r["object_id"]: r for r in records if r["condition"] == "semi" and not r["is_oos"]}
    x = load_expression(ROOT)
    x = x[x.classification_observation & x.condition.eq("semi")]
    labels = pd.read_csv(OUT / "lobo_labels.csv").query("candidate=='semi_position_scale'")
    d = x.merge(labels[["worker_id", "heldout_building", "class_id"]],
        left_on=["worker_id", "building_id"], right_on=["worker_id", "heldout_building"])
    rows = []
    for (image, ref), group in d.groupby(["image_id", "reference_id"], dropna=False):
        low, normal = group[group.class_id.eq("SP_L")], group[group.class_id.eq("SP_T")]
        for _, a in low.iterrows():
            for _, b in normal.iterrows():
                if a.pair_n != b.pair_n or not np.isfinite(a.log_height + b.log_height):
                    continue
                ra, rb = records[a.object_id], records[b.object_id]
                pa, pb = np.asarray(ra["points_1024x512"]), np.asarray(rb["points_1024x512"])
                angles = np.degrees(np.arccos(np.clip(ray(pa[1::2]) @ ray(pb[1::2]).T, -1, 1)))
                ia, ib = linear_sum_assignment(angles)
                matched = angles[ia, ib]
                if matched.max() > 12:
                    continue
                ta, ba, tb, bb = pa[::2][ia, 1], pa[1::2][ia, 1], pb[::2][ib, 1], pb[1::2][ib, 1]
                h_a, h_b = height(ta, ba), height(tb, bb)
                h_top, h_bottom = height(ta, bb), height(tb, ba)
                top_component = .5 * (np.log(h_top / h_b) + np.log(h_a / h_bottom))
                bottom_component = .5 * (np.log(h_bottom / h_b) + np.log(h_a / h_top))
                qa, qb = ra.get("B8L2"), rb.get("B8L2")
                if not ra["quality_usable"]:
                    qa = None
                if not rb["quality_usable"]:
                    qb = None
                rows.append(dict(image_id=image, image_code=a.image_code, reference_id=ref, building_id=a.building_id,
                    worker_low=a.worker_id, worker_typical=b.worker_id, object_low=a.object_id, object_typical=b.object_id,
                    origin_low=a.origin, origin_typical=b.origin, same_origin=a.origin == b.origin,
                    source=a.origin if a.origin == b.origin else "cross_origin", pair_n=a.pair_n,
                    max_bottom_match_deg=matched.max(), mean_bottom_match_deg=matched.mean(),
                    top_y_low_minus_typical=(ta - tb).mean(), bottom_y_low_minus_typical=(ba - bb).mean(),
                    top_log_height_component=top_component, bottom_log_height_component=bottom_component,
                    log_height_low_minus_typical=np.log(h_a / h_b),
                    log_area_low_minus_typical=a.log_area - b.log_area,
                    quality_low=qa, quality_typical=qb,
                    quality_difference=qa - qb if qa is not None and qb is not None else np.nan))
    pairs = pd.DataFrame(rows)
    pairs.to_csv(OUT / "height_same_count_pairs.csv.gz", index=False)
    metrics = ["top_y_low_minus_typical", "bottom_y_low_minus_typical", "top_log_height_component", "bottom_log_height_component", "log_height_low_minus_typical", "log_area_low_minus_typical", "quality_difference"]
    panels, summary = [], []
    for cutoff in [9, 12]:
        for source in ["all", "v1", "new"]:
            selected = pairs[pairs.max_bottom_match_deg.le(cutoff)]
            if source != "all":
                selected = selected[selected.source.eq(source)]
            for minimum in [1, 2]:
                ps = []
                for (image, ref), g in selected.groupby(["image_id", "reference_id"]):
                    nlow, nnorm = g.worker_low.nunique(), g.worker_typical.nunique()
                    if min(nlow, nnorm) < minimum:
                        continue
                    r = dict(cutoff=cutoff, source=source, min_members=minimum,
                             image_id=image, image_code=g.iloc[0].image_code, reference_id=ref,
                             building_id=g.iloc[0].building_id, n_pairs=len(g), n_low=nlow, n_typical=nnorm)
                    r.update(g[metrics].mean().to_dict())
                    panels.append(r)
                    ps.append(r)
                if not ps:
                    continue
                ps = pd.DataFrame(ps)
                bs = ps.groupby("building_id")[metrics].mean()
                row = dict(cutoff=cutoff, source=source, min_members=minimum,
                           images=ps.image_id.nunique(), buildings=ps.building_id.nunique(), pairs=int(ps.n_pairs.sum()))
                row.update(bs.mean().to_dict())
                row.update({m + "_positive_buildings": int(bs[m].gt(1e-10).sum()) for m in metrics})
                row.update({m + "_negative_buildings": int(bs[m].lt(-1e-10).sum()) for m in metrics})
                summary.append(row)
    pd.DataFrame(panels).to_csv(OUT / "height_same_count_panels.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "height_same_count_summary.csv", index=False)
    # Same observations enter both components, so this identity tests the stated diagnostic only.
    assert np.max(np.abs(pairs.top_log_height_component + pairs.bottom_log_height_component - pairs.log_height_low_minus_typical)) < 1e-10
    notes = {
        "candidate": "semi_position_scale:SP_L", "comparison": "SP_L minus SP_T; frozen LOBO labels",
        "geometry": "camera-height-normalized mean paired-ray height, exactly the existing continuous-coordinate viewer formula",
        "same_count": True, "bottom_matching": "one-to-one angular assignment, all matched rays within9/12 degrees",
        "decomposition": "symmetric two-order contribution decomposition on log mean height; solely an explanation, never new annotations",
        "interpretation": "positive top y means lower image top; positive bottom y means lower image floor ray and shorter normalized floor range; angular matching is not verified semantic wall identity",
        "quality": "existing B8L2 only where quality_usable; no new reference or score",
    }
    (OUT / "HEIGHT_DIAGNOSTIC_CONTRACT.json").write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf8")
    print(pd.DataFrame(summary).query("cutoff==9 and min_members==2").round(5).to_string(index=False))
    print(pairs[(pairs.image_code == "7y3sRwLe3Va-13") & (pairs.worker_low.isin(["W030", "W119"])) & (pairs.worker_typical.isin(["W013", "W123"]))][["image_code", "worker_low", "worker_typical", "quality_low", "quality_typical", "top_y_low_minus_typical", "bottom_y_low_minus_typical", "log_height_low_minus_typical"]].round(5).to_string(index=False))


if __name__ == "__main__":
    main()
