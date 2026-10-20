"""Describe frozen v2 markings; no refitting, scoring, fusion or point repair."""
from __future__ import annotations

import base64
import gzip
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research/workers/personnel_marking_patterns_20261020"
SOURCE = ROOT / "research/statistics/v2_evidence_audit_20261019/records.json.gz"
VIS = ROOT / "research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py"
spec = importlib.util.spec_from_file_location("marking_case_visuals", VIS)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
plt = v.plt
METHOD = "R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1"
R5 = {"W109", "W112", "W115", "W122", "W126", "W130"}
H2 = R5 | {"W102"}
CASES = [
    ("M01", "pRbA3pwrgk9-12", "manual", "参考省略的局部凸起", (70, 220, 60, 420)),
    ("M02", "yqstnuAEVhm-01", "manual", "短墙与不显眼的转折", (820, 1024, 60, 450)),
    ("M03", "UwV83HsGsw3-22", "manual", "同一转折的保留与简化", (430, 610, 100, 420)),
    ("M04", "7y3sRwLe3Va-13", "semi", "走廊停止范围与初始化修改", (140, 390, 150, 380)),
    ("M05", "jtcxE69GiFV-12", "manual", "门洞交界的范围选择", (0, 1024, 0, 512)),
    ("M06", "yqstnuAEVhm-29", "manual", "局部结构与节点支持", (0, 1024, 0, 512)),
    ("M07", "yqstnuAEVhm-01", "semi", "同图 Semi 的结构表达", (820, 1024, 60, 450)),
    ("M08", "B6ByNegPMKs-18", "manual", "近共线节点与结构转折不同", (300, 760, 60, 440)),
    ("M09", "B6ByNegPMKs-50", "manual", "顶界选择与推导高度差异", (250, 850, 20, 440)),
]
REPRESENTATIVES = {
    "M01": ["W115", "W130"], "M02": ["W130", "W100"], "M03": ["W122", "W126"],
    "M04": ["W008", "W001"], "M05": ["W108", "W115"], "M06": ["W122", "W101"],
    "M07": ["W034", "W028"], "M08": ["W037", "W130"], "M09": ["W030", "W122"],
}


def geometry_features(points):
    """Dimensionless floor geometry; no validity repair or reference comparison."""
    g = v.viewer_geometry(points)
    floor = g["floor"]
    if floor is None or len(floor) < 3:
        return {"feature_status": g["reason"]}, g
    poly = Polygon(floor)
    edges = np.roll(floor, -1, axis=0) - floor
    lengths = np.linalg.norm(edges, axis=1)
    if not poly.is_valid or poly.area <= 0 or np.any(lengths < 1e-8):
        return {"feature_status": "invalid_or_degenerate_floor"}, g
    previous = np.roll(edges, 1, axis=0)
    turn = np.degrees(np.arccos(np.clip(
        (previous * edges).sum(axis=1) / (np.roll(lengths, 1) * lengths), -1, 1)))
    # These thresholds describe geometry, never semantic correctness.
    short = (lengths / lengths.sum() < .04) & (turn >= 15) & (np.roll(turn, -1) >= 15)
    ceiling = g["ceiling_xyz"]
    height = float(np.mean(ceiling[:, 1]) + 1) if ceiling is not None else np.nan
    return {
        "feature_status": "valid_floor",
        "pair_n": len(floor), "area_camera_height_sq": poly.area,
        "log_area": float(np.log(poly.area)),
        "height_camera_height": height,
        "log_height": float(np.log(height)) if height > 0 else np.nan,
        "near_straight_nodes_5deg": int((turn <= 5).sum()),
        "near_straight_nodes_3deg": int((turn <= 3).sum()),
        "near_straight_nodes_10deg": int((turn <= 10).sum()),
        "short_turn_edges": int(short.sum()),
        "min_edge_fraction": float(min(lengths) / lengths.sum()),
    }, g


def load_labels():
    oldpath = ROOT / "research/workers/personnel_composition_study_20261019/analysis/reverse/class_roles.csv"
    roles = pd.read_csv(oldpath)
    assert set(roles.query("method_id == 'R_role_ward_K5' and class_id == 'C05'").iloc[0].members.split("|")) == R5
    assert set(roles.query("method_id == 'R_role_ward_difficulty_K2' and domain == 'hard' and class_id == 'C02'").iloc[0].members.split("|")) == H2
    newpath = ROOT / "research/workers/personnel_interchangeability_20261020/interchangeability_20261020/reverse/mixed_fit/worker_labels.csv.gz"
    labels = pd.read_csv(newpath)
    labels = labels[(labels.method_id == METHOD) & labels.known]
    assert len(labels) == 35 and labels.worker_id.is_unique
    return dict(zip(labels.worker_id, labels.class_id)), [oldpath, newpath]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")


def primary_observations(df):
    """Prefer the existing retained vote among repeat submissions, never scores."""
    keys = ["worker_id", "image_id", "condition", "reference_id", "layer"]
    sizes = df.groupby(keys, dropna=False).object_id.transform("size")
    votes = df.groupby(keys, dropna=False).independent_vote_eligible.transform("sum")
    return sizes.eq(1) | (votes.eq(1) & df.independent_vote_eligible)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    v._configure_font(Path("C:/Windows/Fonts/msyh.ttc"))
    records = json.load(gzip.open(SOURCE, "rt", encoding="utf8"))["records"]
    labels, label_paths = load_labels()
    selected = [r for r in records if r["is_oos"] is False]
    assert len({r["object_id"] for r in records}) == len(records)
    rows = []
    for r in selected:
        row = {k: r[k] for k in ["object_id", "worker_id", "image_id", "image_code",
               "building_id", "condition", "origin", "quality_usable", "quality_use",
               "cleaning_disposition", "reference_id", "reference_version", "raw_original_available"]}
        row.update(layer="doorway" if r["is_doorway"] else "ordinary",
                   R5=r["worker_id"] in R5, H2=r["worker_id"] in H2,
                   Rnew2=labels.get(r["worker_id"], "unclassified"),
                   difficulty=r["current_class"], ring_confirmed=r["ring_confirmed"])
        row["coordinate_repair_evidence_present"] = bool(r["coordinate_evidence"].get("repair_evidence"))
        row["independent_vote_eligible"] = r["independent_vote_eligible"]
        f, _ = geometry_features(r["points_1024x512"])
        row.update(f)
        s = r["semi_evidence"]
        row.update(semi_exact_initialization=s.get("exact_initialization_bound", False),
                   semi_edited=s.get("edited"), semi_error_confirmed=s.get("confirmed_error_opportunity", False),
                   semi_error_reported=s.get("reported_error_opportunity", False),
                   semi_known_error_unchanged=s.get("known_error_unchanged"),
                   semi_reported_error_unchanged=s.get("reported_known_error_unchanged"),
                   semantic_correction_confirmed=s.get("corrected_confirmed"))
        initial, final = s.get("initialization_points"), s.get("raw_final_points")
        row["semi_raw_pair_delta"] = (len(final) - len(initial)) / 2 if initial and final else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    key = ["image_id", "condition", "layer", "reference_id"]
    valid = df.feature_status.eq("valid_floor")
    df["primary_expression"] = primary_observations(df)
    df["personal_comparison"] = df.primary_expression & ~df.coordinate_repair_evidence_present & valid
    comparable = df.personal_comparison
    df["peer_n"] = df.loc[comparable].groupby(key, dropna=False).object_id.transform("count")
    for col in ["pair_n", "short_turn_edges", "near_straight_nodes_5deg", "log_area", "log_height"]:
        med = df.loc[comparable].groupby(key, dropna=False)[col].transform("median")
        df[col + "_peer_delta"] = (df[col] - med).where(df.peer_n >= 3)
    df.to_csv(OUT / "record_expression.csv", index=False, encoding="utf-8-sig")
    summaries = []
    for (worker, condition, layer), group in df.groupby(["worker_id", "condition", "layer"]):
        row = dict(worker_id=worker, condition=condition, layer=layer, records=len(group),
                   images=group.image_id.nunique(), buildings=group.building_id.nunique(),
                   R5=worker in R5, H2=worker in H2, Rnew2=labels.get(worker, "unclassified"),
                   geometry_available=int(group.feature_status.eq("valid_floor").sum()),
                   semi_bound=int(group.semi_exact_initialization.sum()),
                   semi_edited=int(group.semi_edited.eq(True).sum()),
                   semi_edit_known=int(group.semi_edited.notna().sum()),
                   semi_remove_pairs=int(group.semi_raw_pair_delta.lt(0).sum()),
                   semi_add_pairs=int(group.semi_raw_pair_delta.gt(0).sum()))
        for col in ["pair_n", "short_turn_edges", "near_straight_nodes_5deg", "log_area", "log_height"]:
            s = group[col + "_peer_delta"]
            row[col + "_opportunities"] = int(s.notna().sum())
            row[col + "_mean_peer_delta"] = s.mean()
            row[col + "_above_n"] = int(s.gt(0).sum())
            row[col + "_below_n"] = int(s.lt(0).sum())
            building = group.assign(delta=s).groupby("building_id").delta.mean()
            row[col + "_positive_buildings"] = int(building.gt(0).sum())
            row[col + "_negative_buildings"] = int(building.lt(0).sum())
        summaries.append(row)
    pd.DataFrame(summaries).to_csv(OUT / "person_condition_expression.csv", index=False, encoding="utf-8-sig")
    contrasts = []
    for group_key, group in df[comparable].groupby(key, dropna=False):
        for partition, positive in [("R5", True), ("H2", True), ("Rnew2", "C01")]:
            eligible = group if partition != "Rnew2" else group[group.Rnew2.ne("unclassified")]
            a, b = eligible[eligible[partition].eq(positive)], eligible[~eligible[partition].eq(positive)]
            if len(a) < 2 or len(b) < 2:
                continue
            row = dict(zip(key, group_key))
            row.update(image_code=group.iloc[0].image_code, building_id=group.iloc[0].building_id,
                       partition=partition, a_n=len(a), b_n=len(b))
            for col in ["pair_n", "short_turn_edges", "near_straight_nodes_5deg", "log_area", "log_height"]:
                row[col + "_difference"] = a[col].mean() - b[col].mean()
            contrasts.append(row)
    contrast = pd.DataFrame(contrasts)
    contrast.to_csv(OUT / "matched_image_class_contrasts.csv", index=False, encoding="utf-8-sig")
    aggregate = []
    for keys, group in contrast.groupby(["partition", "condition", "layer"]):
        row = dict(zip(["partition", "condition", "layer"], keys))
        row.update(target_panels=len(group), images=group.image_id.nunique(), buildings=group.building_id.nunique())
        for col in [c for c in group if c.endswith("_difference")]:
            row[col + "_image_mean"] = group.groupby("image_id")[col].mean().mean()
            row[col + "_building_mean"] = group.groupby("building_id")[col].mean().mean()
        aggregate.append(row)
    pd.DataFrame(aggregate).to_csv(OUT / "class_condition_distribution.csv", index=False, encoding="utf-8-sig")
    paired_key = ["worker_id", "image_id", "reference_id", "layer"]
    manual, semi = df[df.condition.eq("manual") & comparable], df[df.condition.eq("semi") & comparable]
    assert not manual.duplicated(paired_key).any() and not semi.duplicated(paired_key).any()
    paired = manual.merge(semi, on=paired_key, suffixes=("_manual", "_semi"))
    paired.to_csv(OUT / "same_person_manual_semi.csv", index=False, encoding="utf-8-sig")
    condition_contrasts = []
    for keys, group in paired.groupby(["image_id", "reference_id", "layer"]):
        if group.R5_manual.sum() < 2 or (~group.R5_manual).sum() < 2:
            continue
        row = dict(image_id=keys[0], reference_id=keys[1], layer=keys[2], people=len(group), r5=int(group.R5_manual.sum()))
        for cond in ["manual", "semi"]:
            for metric in ["pair_n", "short_turn_edges"]:
                row[cond + "_" + metric] = group[group.R5_manual][metric + "_" + cond].mean() - group[~group.R5_manual][metric + "_" + cond].mean()
        condition_contrasts.append(row)
    pd.DataFrame(condition_contrasts).to_csv(OUT / "same_people_condition_class_contrasts.csv", index=False, encoding="utf-8-sig")
    image_list = df.groupby(["image_id", "image_code", "layer", "condition"], dropna=False).agg(
        records=("object_id", "size"), people=("worker_id", "nunique"),
        quality_usable=("quality_usable", "sum"), geometry_available=("feature_status", lambda s: s.eq("valid_floor").sum()))
    image_list.to_csv(OUT / "image_inventory.csv", encoding="utf-8-sig")
    cases, case_rows = [], []
    for case_id, code, condition, title, zoom in CASES:
        pool = [r for r in selected if r["image_code"] == code and r["condition"] == condition]
        first = pool[0]
        photo_path = ROOT / "data/mp3d_layout/img_v" / (first["image_id"] + ".jpg")
        photo = np.asarray(Image.open(photo_path).convert("RGB"))
        ref = first["reference_evidence"]
        c = dict(case_id=case_id, image_code=code, condition=condition, title=title,
                 image_id=first["image_id"], is_doorway=first["is_doorway"],
                 photo_path=photo_path.relative_to(ROOT).as_posix(), zoom=zoom,
                 image_comments=first["image_comments"], records=pool,
                 reference=ref, photo="data:image/jpeg;base64," + base64.b64encode(photo_path.read_bytes()).decode())
        cases.append(c)
        fig, ax = plt.subplots(3, 2, figsize=(14, 12))
        for j, is_member in enumerate([True, False]):
            members = [r for r in pool if (r["worker_id"] in R5) == is_member]
            title_group = "R5 历史候选" if is_member else "其余人员（并非同一类）"
            for i in [0, 1]:
                v._erp_background(ax[i, j], photo, None if i == 0 else zoom)
                v._erp_edges(ax[i, j], ref.get("points_1024x512"), v.REF_ERP_COLOR, reference=True)
                for r in members:
                    v._erp_edges(ax[i, j], r["points_1024x512"], "#00d5ff" if is_member else "#ff62b6",
                                 linewidth=.7, alpha=.45 if is_member else .20)
                ax[i, j].set_title(title_group + f" | {len(members)} 份" + (" | 局部" if i else ""))
            for r in members:
                g = v.viewer_geometry(r["points_1024x512"])
                if g["floor"] is not None:
                    v._bev_ring(ax[2, j], g["floor"], "#007caa" if is_member else "#c03b83", alpha=.45)
            v._bev_ring(ax[2, j], ref.get("floor_xz_h"), "#222222", reference=True)
            ax[2, j].set_aspect("equal")
            ax[2, j].set_title("底面推导；相机高度 = 1")
        limits = [a.get_xlim() + a.get_ylim() for a in ax[2]]
        for a in ax[2]:
            a.set_xlim(min(x[0] for x in limits), max(x[1] for x in limits))
            a.set_ylim(min(x[2] for x in limits), max(x[3] for x in limits))
        fig.suptitle(f"{case_id} {code} {condition} | {title}\n黄色/黑虚线 = 当前绑定参考（不保证正确）；逐条线 = 处理后原作答，非融合", fontsize=13)
        fig.tight_layout(rect=(0, 0, 1, .95))
        fig.savefig(OUT / f"figures/{case_id}.png", dpi=120)
        plt.close(fig)
        representative_figure(c)
        for r in pool:
            case_rows.append(dict(case_id=case_id, image_code=code, condition=condition,
                                  object_id=r["object_id"], worker_id=r["worker_id"],
                                  R5=r["worker_id"] in R5, H2=r["worker_id"] in H2,
                                  Rnew2=labels.get(r["worker_id"], "unclassified"),
                                  reference_id=r["reference_id"], reference_version=r["reference_version"],
                                  quality_usable=r["quality_usable"], raw_original_available=r["raw_original_available"],
                                  detail_semantics="see_CASE_NOTES_not_inferred_from_node_count"))
    pd.DataFrame(case_rows).to_csv(OUT / "case_records.csv", index=False, encoding="utf-8-sig")
    write_json(OUT / "cases.json", [{k: value for k, value in c.items() if k != "photo"} for c in cases])
    local_rows = []
    windows = {"M01": [("left_projection", 90, 190)],
               "M02": [("left_wall_step", 140, 215), ("seam_wall_step", 990, 1040)],
               "M03": [("near_bathroom_wall_step", 440, 600)],
               "M07": [("left_wall_step", 140, 215), ("seam_wall_step", 990, 1040)]}
    for c in cases:
        for feature, low, high in windows.get(c["case_id"], []):
            for r in c["records"]:
                p = np.asarray(r["points_1024x512"])[::2]
                xs = p[:, 0] % 1024
                if high > 1024:
                    xs = np.where(xs < high - 1024, xs + 1024, xs)
                indices = np.flatnonzero((xs >= low) & (xs <= high))
                required = 2 if feature == "seam_wall_step" else 3
                local_rows.append(dict(case_id=c["case_id"], feature_id=feature,
                    image_code=c["image_code"], condition=c["condition"],
                    worker_id=r["worker_id"], object_id=r["object_id"],
                    R5=r["worker_id"] in R5, Rnew2=labels.get(r["worker_id"], "unclassified"),
                    x_window_start=low, x_window_end=high, pairs_in_window=len(indices),
                    required_local_pairs=required,
                    pair_indices_1based="|".join(str(i+1) for i in indices),
                    expression="multiple_local_pairs" if len(indices) >= required else "partial_or_simplified",
                    semantics="location_descriptor_see_CASE_NOTES_not_automatic_correctness"))
    pd.DataFrame(local_rows).to_csv(OUT / "local_feature_observations.csv", index=False, encoding="utf-8-sig")
    build_view(cases, labels)
    summary_figure(df, contrast)
    write_json(OUT / "MANIFEST.json", dict(
        data_release="v2", input=SOURCE.relative_to(ROOT).as_posix(), inventory_n=len(records),
        non_oos_n=len(selected), non_oos_images=len({r["image_id"] for r in selected}),
        ordinary_n=int(df.layer.eq("ordinary").sum()), doorway_n=int(df.layer.eq("doorway").sum()),
        feature_valid_n=int(valid.sum()), feature_missing_n=int((~valid).sum()),
        personal_comparison_n=int(comparable.sum()), repeat_submission_secondary_n=int((~df.primary_expression).sum()),
        coordinate_repair_evidence_n=int(df.coordinate_repair_evidence_present.sum()),
        non_oos_quality_usable=int(df.quality_usable.sum()), cases=len(cases), case_records=len(case_rows),
        class_sources=[p.relative_to(ROOT).as_posix() for p in label_paths],
        rnew2_method=METHOD, new_classification_fit=False, new_fusion=False, new_quality_score=False,
        point_repair=False, comparisons="descriptive_existing_labels_not_independent_validation",
        geometry_helper=VIS.relative_to(ROOT).as_posix()))
    write_json(OUT / "FIELD_CONTRACT.json", {
        "record_expression": "one row per non-OOS object, exclusions retained; comparison uses unique primary expression without repair evidence, peer median within image+condition+layer+reference, at least 3 computable personal observations",
        "primary_expression": "sole observation or, among repeated submissions, the one existing independent-vote-eligible object; no quality-score selection. Sole historical exclusions retained for behavior, not requalified",
        "person_condition_expression": "one worker+condition+layer; opportunities and building directions retained, not stable trait certification",
        "matched_image_class_contrasts": "at least 2 records each side within same image+condition+reference; R5/H2 versus rest, Rnew2 C01 versus C02 only",
        "class_condition_distribution": "within-image target panels averaged, then image equal; building mean averages target panels within building",
        "case_records": "one displayed original annotation per case; no quality selection",
        "same_person_manual_semi": "same worker+image+reference+layer, both computable floors; observational comparison, no randomized condition-effect claim",
        "local_feature_observations": "visual-anchor angular windows, declared top-x and pair indices; seam step needs >=2 local pairs, other anchors >=3; not correctness or full feature matching",
        "thresholds": {"short_edge_perimeter_fraction": .04, "short_edge_endpoint_turn_min_deg": 15, "near_straight_deg": [3, 5, 10]},
        "semantics": "short edges and collinearity are descriptors, not truth labels; log area/height are dimensionless and not automatic scope/height errors",
        "raw": "original_points available only for inherited batch; new batch received_processed_points never called original export",
        "unknown": "missing metrics remain empty, no zero substitution"})
    print(json.dumps(json.loads((OUT / "MANIFEST.json").read_text("utf8")), ensure_ascii=False))


def representative_figure(c):
    chosen = [next(r for r in c["records"] if r["worker_id"] == worker) for worker in REPRESENTATIVES[c["case_id"]]]
    photo = np.asarray(Image.open(ROOT / c["photo_path"]).convert("RGB"))
    fig, axes = plt.subplots(3, 2, figsize=(13, 11))
    colors = ["#00d5ff", "#ff62b6"]
    for j, r in enumerate(chosen):
        for i in [0, 1]:
            a = axes[i, j]
            v._erp_background(a, photo, None if i == 0 else c["zoom"])
            v._erp_edges(a, c["reference"].get("points_1024x512"), v.REF_ERP_COLOR, reference=True)
            v._erp_edges(a, r["points_1024x512"], colors[j], markers=True, linewidth=1.5)
            initial = r["semi_evidence"].get("initialization_points")
            if initial:
                v._erp_edges(a, initial, "#59ff59", linewidth=.8, alpha=.7)
            a.set_title(f'{r["worker_id"]} | {len(r["points_1024x512"])//2} 个上下点对' + (" | 局部" if i else ""))
        floor = v.viewer_geometry(r["points_1024x512"])["floor"]
        v._bev_ring(axes[2, j], floor, colors[j], linewidth=2)
        v._bev_ring(axes[2, j], c["reference"].get("floor_xz_h"), "#222222", reference=True)
        if floor is not None:
            for k, xy in enumerate(floor):
                axes[2, j].annotate(str(k+1), xy, fontsize=9)
        axes[2, j].set_aspect("equal")
        axes[2, j].set_title(r["object_id"], fontsize=8)
    limits = [a.get_xlim() + a.get_ylim() for a in axes[2]]
    for a in axes[2]:
        a.set_xlim(min(x[0] for x in limits), max(x[1] for x in limits))
        a.set_ylim(min(x[2] for x in limits), max(x[3] for x in limits))
    fig.suptitle(f'{c["case_id"]} {c["image_code"]} {c["condition"]} | {c["title"]}\n黄色/黑虚线：参考；蓝/粉：个人；绿色：有逐份绑定的初始化', fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(OUT / f'figures/{c["case_id"]}_individuals.png', dpi=120)
    plt.close(fig)


def summary_figure(df, contrast):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    subset = df[df.R5 & df.condition.eq("manual") & df.layer.eq("ordinary")]
    for col, marker, label in [("pair_n", "o", "上下点对数"), ("short_turn_edges", "s", "短转折边数")]:
        means = subset.groupby("worker_id")[col + "_peer_delta"].mean()
        axes[0].plot(means.index, means.values, marker=marker, label=label)
    axes[0].axhline(0, color="gray", linewidth=.8)
    axes[0].set_ylabel("相对同图/条件/参考的人员中位数")
    axes[0].set_title("六人的重复表达倾向（普通 Manual）")
    axes[0].legend()
    group = contrast[contrast.partition.eq("R5") & contrast.condition.eq("manual")]
    for i, layer in enumerate(["ordinary", "doorway"]):
        g = group[group.layer.eq(layer)].groupby("building_id").log_area_difference.mean()
        axes[1].scatter(np.full(len(g), i), g, alpha=.65)
        axes[1].scatter([i], [g.mean()], marker="_", s=500, color="black")
    axes[1].axhline(0, color="gray", linewidth=.8)
    axes[1].set_xticks([0, 1], ["普通", "门洞交界"])
    axes[1].set_ylabel("R5 − 其余人员：log 底面面积")
    axes[1].set_title("范围差随场景改变；每点一栋建筑")
    fig.suptitle("描述性结果：历史候选标签，未作新留出验证；面积变化也可能含定位偏移")
    fig.tight_layout()
    fig.savefig(OUT / "figures/pattern_summary.png", dpi=150)
    plt.close(fig)


def build_view(cases, labels):
    # Precompute spherical curves using the existing viewer, keep browser code simple.
    def curves(points):
        p = np.asarray(points if points is not None else [], dtype=float)
        if p.ndim != 2 or len(p) < 6 or len(p) % 2:
            return []
        out = [pair.tolist() for pair in p.reshape(-1, 2, 2)]
        for side in [0, 1]:
            for a, b in zip(p[side::2], np.roll(p[side::2], -1, axis=0)):
                curve = v._curve_between(a, b)
                if curve is not None:
                    out.append(curve.tolist())
        return out
    payload = []
    for c in cases:
        records = []
        for r in c["records"]:
            records.append(dict(id=r["object_id"], worker=r["worker_id"], r5=r["worker_id"] in R5,
                                h2=r["worker_id"] in H2, rnew2=labels.get(r["worker_id"], "unclassified"),
                                curves=curves(r["points_1024x512"]),
                                points=r["points_1024x512"],
                                raw=r["original_points"], received=r["received_processed_points"],
                                initial=curves(r["semi_evidence"].get("initialization_points")),
                                raw_available=r["raw_original_available"], quality=r["quality_usable"],
                                reference_id=r["reference_id"]))
        payload.append(dict(id=c["case_id"], code=c["image_code"], title=c["title"], condition=c["condition"],
                            photo=c["photo"], zoom=c["zoom"], records=records,
                            ref=curves(c["reference"].get("points_1024x512")),
                            comment=[x["text"] for x in c["image_comments"] if x["text_role"] == "recorded_text"]))
    template = Path(__file__).with_suffix(".html").read_text("utf8")
    (OUT / "index.html").write_text(template.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")), encoding="utf8")


if __name__ == "__main__":
    main()
