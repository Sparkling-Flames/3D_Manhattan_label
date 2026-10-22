"""Common-ABC signed effects, with exact linear closure and no new scoring."""
from __future__ import annotations

import math
import json
import numpy as np
import pandas as pd
from register_design import HERE, write, save, sha

CORNER = ["corner_angle_deg", "corner_bev_mean_h", "corner_bev_max_h", "corner_top_mean_h", "corner_top_max_h"]


def read(folder):
    ids = ["event_id", "panel_id", "image", "building", "training_QT_direction", "n", "m_AB", "target_class", "all_scored", "recorded_time_single_source"]
    metrics = [pre + "_" + f for pre in ["same", "cross", "net", "sym"] for f in ["B8L2", "D10", "recorded_time_logratio"]]
    metrics += [pre + "_" + f for pre in ["within", "cross", "net"] for f in CORNER]
    return pd.read_csv(folder / "EVENTS_COMPLETE.csv.gz", usecols=ids + metrics, low_memory=False)


def main():
    a, b = read(HERE), read(HERE / "phase_b_highq_slower")
    centers = pd.read_csv(HERE / "TRAINING_CLASS_CENTERS.csv")
    maximum = centers.loc[centers.groupby("heldout_building").q_history.idxmax()].set_index("heldout_building").coarse_label
    specs = []
    for (direction, n, m), g in a.groupby(["training_QT_direction", "n", "m_AB"]):
        specs.append(("A", f"{direction};n{n};m{m}", "exact_n_m", g))
    g = a[(a.training_QT_direction == "q_up__slower") & a.n.eq(20) & a.m_AB.eq(4) & a.target_class.eq(a.building.map(maximum))]
    specs.append(("A", "q_up__slower;n20;m4;exploratory_target_top_training_Q", "exploratory_target_top_training_Q", g))
    specs.append(("B", "q_up__slower;n20;m4", "new_background_check_after_selection", b))
    rows, image_rows, building_rows, corner_rows = [], [], [], []
    for stage, view, scope, g in specs:
        common = g[g.all_scored & g[[p + "_B8L2" for p in ["same", "cross", "net", "sym"]]].notna().all(axis=1)].copy()
        metrics = [pre + "_" + f for pre in ["same", "cross", "net", "sym"] for f in ["B8L2", "D10", "recorded_time_logratio"]]
        panels = common.groupby(["panel_id", "building", "image"])[metrics].mean().reset_index()
        images = panels.groupby(["building", "image"])[metrics].mean().reset_index()
        buildings = images.groupby("building")[metrics].mean().reset_index()
        row = dict(stage=stage, view=view, scope=scope, direction=g.training_QT_direction.iloc[0], n=int(g.n.iloc[0]), m=int(g.m_AB.iloc[0]),
                   registered_events=len(g), common_scored_events=len(common), registered_panels=g.panel_id.nunique(),
                   common_scored_panels=len(panels), registered_images=g.image.nunique(), images=len(images),
                   registered_buildings=g.building.nunique(), buildings=len(buildings),
                   estimand="same common-ABC rows; panel -> image -> building means")
        for f in metrics:
            row[f] = buildings[f].mean()
            row[f + "_image_equal"] = images[f].mean()
        for f in ["B8L2", "D10"]:
            row[f + "_symmetry_closure_error"] = row["sym_" + f] - (row["cross_" + f] + row["net_" + f]) / 2
            row[f + "_signed_closure_error"] = row["cross_" + f] - row["net_" + f] - row["same_" + f]
            assert abs(row[f + "_symmetry_closure_error"]) < 1e-10
            assert abs(row[f + "_signed_closure_error"]) < 1e-10
        for pre in ["same", "cross", "net", "sym"]:
            row[pre + "_recorded_time_geomean_pct"] = 100 * math.expm1(row[pre + "_recorded_time_logratio"])
        for level, frame in [("image", images), ("building", buildings), ("panel", panels)]:
            for pre in ["same", "cross", "net", "sym"]:
                row[level + "_" + pre + "_Q_positive"] = int(frame[pre + "_B8L2"].gt(0).sum())
                row[level + "_" + pre + "_Q_known"] = int(frame[pre + "_B8L2"].notna().sum())
        rows.append(row)
        # Correspondence distances are compared only when all three pair
        # measurements exist.  They describe changed geometry, not GT error.
        for metric in CORNER:
            keys = [p + "_" + metric for p in ["within", "cross", "net"]]
            cg = g[g[keys].notna().all(axis=1)].copy()
            cg["across_mean"] = (cg[keys[1]] + cg[keys[2]]) / 2
            cg["advantage"] = cg.across_mean - cg[keys[0]]
            fields = keys + ["across_mean", "advantage"]
            cp = cg.groupby(["panel_id", "building", "image"])[fields].mean().reset_index()
            cim = cp.groupby(["building", "image"])[fields].mean().reset_index()
            cbu = cim.groupby("building")[fields].mean().reset_index()
            corner_rows.append(dict(stage=stage, view=view, metric=metric, known_events=len(cg), known_panels=len(cp),
                images=len(cim), buildings=len(cbu), within=cbu[keys[0]].mean(), across_sym=cbu.across_mean.mean(),
                across_minus_within=cbu.advantage.mean(), larger_images=int(cim.advantage.gt(0).sum()),
                larger_buildings=int(cbu.advantage.gt(0).sum()), interpretation="pair distances; all three correspondences available; not a quality-direction score"))
        for frame, dest in [(images, image_rows), (buildings, building_rows)]:
            frame.insert(0, "view", view)
            frame.insert(0, "stage", stage)
            dest.append(frame)
    write(HERE / "COMMON_ABC_SIGNED_EFFECTS.csv", pd.DataFrame(rows))
    write(HERE / "COMMON_ABC_SIGNED_IMAGES.csv", pd.concat(image_rows, ignore_index=True))
    write(HERE / "COMMON_ABC_SIGNED_BUILDINGS.csv", pd.concat(building_rows, ignore_index=True))
    write(HERE / "CORNER_COMMON_TRIPLET_COMPARISON.csv", pd.DataFrame(corner_rows))
    save(HERE / "COMMON_ABC_SIGNED_RECEIPT.json", dict(native_scoring_calls=0, event_files={
        "A": sha(HERE / "EVENTS_COMPLETE.csv.gz"), "B": sha(HERE / "phase_b_highq_slower/EVENTS_COMPLETE.csv.gz")},
        rows=len(rows), maximum_linear_closure_error=max(abs(r[k]) for r in rows for k in r if k.endswith("closure_error")),
        failure_events_retained_in_original_tables=True,
        note="Time sym uses C / arithmetic mean(A,B) times. Its log is not the average of cross/net logs and has no asserted linear closure."))
    out = pd.DataFrame(rows)
    print(out[((out.stage == "A") & out.direction.eq("q_up__faster") & out.n.eq(20) & out.m.ge(3)) | out.stage.eq("B")][
        ["stage", "view", "common_scored_events", "same_B8L2", "cross_B8L2", "net_B8L2", "sym_B8L2", "B8L2_symmetry_closure_error"]].to_string(index=False))


if __name__ == "__main__":
    main()
