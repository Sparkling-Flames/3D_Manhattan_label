"""Exploratory handoff audit; alternate readings never replace source annotations.

Reuses the received metric implementation. Historical pairing is only an
explicit sensitivity hypothesis, not evidence of author-intended adjacency.
"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
import json
from math import comb
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers, write_json
from tools.thesis_main.analysis.uncertainty_handoff_errata import corrected_initialization

INPUT = ROOT / "analysis_results/uncertainty_cloud_inputs_20260906_v1"
REVIEW = ROOT / "analysis_results/uncertainty_visual_review_20260907_v1"
HUMAN = ROOT / "analysis_results/human_review_reconciliation_20260907_v1"
OUTPUT = ROOT / "analysis_results/uncertainty_followup_analysis_20260908_v1"


def historical_pair_ids(points):
    """Historical stable-x/5%-width greedy pairing; retain individual x/y values.

    The real viewer averages pair x and may clip or apply local overrides.
    Those extra transformations are deliberately not emulated by this reading.
    Unlike the viewer, reject incomplete matching instead of silently dropping.
    """
    a = np.asarray(points, float)
    if a.ndim != 2 or a.shape[1] != 2 or len(a) < 6 or len(a) % 2:
        raise ValueError("unpaired_or_insufficient_points")
    if not np.isfinite(a).all():
        raise ValueError("coordinate_nonfinite")
    order = sorted(range(len(a)), key=lambda i: a[i, 0])
    used, result = set(), []
    for i, raw_i in enumerate(order):
        if raw_i in used:
            continue
        choices = [j for j in order[i + 1:] if j not in used and abs(a[j, 0] - a[raw_i, 0]) < 51.2]
        if not choices:
            raise ValueError("unpaired_point_historical_threshold")
        j = min(choices, key=lambda j: abs(a[j, 0] - a[raw_i, 0]))
        used.update((raw_i, j))
        result.extend(sorted((raw_i, j), key=lambda k: a[k, 1]))
    assert sorted(result) == list(range(len(a)))
    return result


def expected_clusters(sizes, k):
    """Exact expected observed clusters in a uniform subset of a FIXED partition."""
    n = sum(sizes)
    if k > n or k < 1:
        return None
    return sum(1 - (comb(n - m, k) / comb(n, k) if n - m >= k else 0) for m in sizes if m)


def user_bottom_order(points, bottoms):
    """Resolve only the user's same-x pairs; never guess missing corners."""
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=2 or not np.isfinite(p).all():
        raise ValueError('invalid_points')
    if len(bottoms)*2!=len(p) or len(set(bottoms))!=len(bottoms):
        raise ValueError('complete_unique_bottom_list_required')
    order=[]
    for b in bottoms:
        if not isinstance(b,int) or not 0<=b<len(p) or p[b,1]<=256:
            raise ValueError('invalid_bottom_point')
        tops=np.flatnonzero((abs(p[:,0]-p[b,0])<1e-7)&(p[:,1]<256)).tolist()
        if len(tops)!=1:raise ValueError('nonunique_same_x_top')
        order.extend([tops[0],b])
    if sorted(order)!=list(range(len(p))):raise ValueError('complete_point_coverage_required')
    return order


def distribution_recovery(groups, draws, target_sizes):
    """Exact fixed-partition recovery under disjoint finite roster sampling.

    Each cluster's marginal is a convolution of hypergeometrics. Linearity of
    expectation suffices; no independence assumption between clusters is made.
    """
    target=np.asarray(target_sizes,float)
    if len(groups)!=len(draws) or target.sum()<=0 or (target<0).any():
        raise ValueError('invalid_distribution_request')
    target=target/target.sum();k=sum(draws)
    if k<=0:raise ValueError('empty_sample')
    expected_tv=missing=seen=0.
    for j,p in enumerate(target):
        mass=np.array([1.])
        for sizes,s in zip(groups,draws):
            if len(sizes)!=len(target) or any(int(x)!=x or x<0 for x in sizes):raise ValueError('invalid_sizes')
            n=int(sum(sizes));m=int(sizes[j])
            if int(s)!=s or not 0<=s<=n:raise ValueError('draw_exceeds_pool')
            q=np.zeros(s+1)
            for x in range(max(0,s-(n-m)),min(m,s)+1):
                q[x]=comb(m,x)*comb(n-m,s-x)/comb(n,s)
            mass=np.convolve(mass,q)
        assert abs(mass.sum()-1)<1e-10
        expected_tv+=.5*float(np.dot(mass,abs(np.arange(len(mass))/k-p)))
        missing+=p*mass[0];seen+=1-mass[0]
    return dict(expected_tv=expected_tv,expected_missing_mass=missing,
                expected_cluster_fraction=seen/len(target))


def rho(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return np.nan
    return float(spearmanr(x[ok], y[ok]).statistic)


def csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def save(out, name, rows):
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False)
    return frame


def run(out=OUTPUT):
    out.mkdir(parents=True, exist_ok=True)
    audit, _ = helpers()
    a, images, partitions, members, versions, models, refs, raw, norm = audit.load()
    assert len(a) == 2501 and not a.duplicated(["context_key", "worker_id"]).any()
    ids_by_context = a.groupby("context_key").canonical_annotation_id.agg(list).to_dict()
    current = set(a[a.current20_member.map(audit.yes)].canonical_annotation_id)
    metadata = a.set_index("canonical_annotation_id")
    ext = partitions[partitions.version == "extended73"]
    ext_keys = set(ext.context_key)
    old_context = pd.read_csv(REVIEW / "reproduced_numerical/analysis/contexts.csv")
    corrected, changes = corrected_initialization(old_context, csv(INPUT / "facts/proposal_fact.csv.gz"), csv(INPUT / "facts/proposal_response.csv.gz"))
    save(out, "initialization_join_changes.csv", changes)
    initialization = corrected.set_index("context_key").initialization_source_kind.to_dict()
    layouts = {i: r["points_1024x512"] for i, r in raw.items()}
    layout_meta = {}
    for r in models:
        if r["model_family"] == "Bi-Layout":
            layouts[r["layout_id"]] = r["points_1024x512"]
            layout_meta[(r["image_id"], r["head"])] = r["layout_id"]
    methods = ("serialized_adjacency", "historical_pairmap_unaveraged")
    cache = {m: {"floor": {}, "band": {}, "linear": {}} for m in methods}
    readings = []
    for i, points in layouts.items():
        for method in methods:
            is_human = i in raw
            mapping = list(range(len(points)))
            mapping_failure = ""
            if is_human and method == methods[1]:
                try:
                    mapping = historical_pair_ids(points)
                except ValueError as e:
                    mapping_failure = str(e)
            p = np.asarray(points, float)[mapping] if len(points) else points
            row = dict(layout_id=i, human=is_human, method=method,
                       raw_point_ids_json=json.dumps(mapping), mapping_failure=mapping_failure,
                       coordinate_values_changed=False, author_adjacency_verified=False)
            for metric, fn in [("floor", audit.footprint), ("band", audit.band)]:
                try:
                    if mapping_failure:
                        raise ValueError(mapping_failure)
                    cache[method][metric][i] = fn(p)
                    row[metric + "_status"] = "computable"
                except (ValueError, IndexError, TypeError) as e:
                    row[metric + "_status"] = str(e)
            if i in cache[method]["band"]:
                cache[method]["linear"][i] = audit.band(p, linear=True)
            if is_human:
                row.update(metadata.loc[i, ["context_key", "worker_id", "stage", "raw_condition", "building_id"]].to_dict())
            readings.append(row)
    reading = save(out, "reading_status.csv.gz", readings)
    print("readings", reading[reading.human].groupby(["method", "floor_status"]).size().to_dict(), flush=True)

    def distance(method, metric, i, j):
        table = cache[method]["band" if metric == "solid" else metric]
        if i not in table or j not in table:
            return np.nan
        return audit.dp(table[i], table[j]) if metric == "floor" else audit.db(table[i], table[j], metric == "solid")

    metrics = ("floor", "band", "linear", "solid")
    pairs, model_rows = [], []
    for image in images.image_id:
        e, x = (layout_meta[(image, head)] for head in ("enclosed", "extended"))
        model_rows.append(dict(image_id=image, **{m: distance(methods[0], m, e, x) for m in metrics}))
    model_frame = save(out, "model_distances.csv", model_rows).set_index("image_id")
    ctx_rows = []
    for context, ids in ids_by_context.items():
        meta = metadata.loc[ids[0]]
        per_method = {}
        for method in methods:
            pp = []
            for i, j in combinations(ids, 2):
                row = dict(context_key=context, method=method, left=i, right=j,
                           **{m: distance(method, m, i, j) for m in metrics})
                pp.append(row)
                pairs.append(row)
            per_method[method] = pp
        for method in methods:
            for pool in ("all_historical", "current20_only"):
                pool_ids = set(ids) if pool == "all_historical" else set(ids) & current
                for cohort in ("method_available", "common_responses"):
                    for metric in metrics:
                        key = "band" if metric == "solid" else metric
                        available = pool_ids & set(cache[method][key])
                        if cohort == "common_responses":
                            available &= set(cache[methods[0]][key]) & set(cache[methods[1]][key])
                        vals = [p[metric] for p in per_method[method] if p["left"] in available and p["right"] in available]
                        assert all(np.isfinite(v) for v in vals)
                        ctx_rows.append(dict(context_key=context, image_id=meta.image_id, building_id=meta.building_id,
                            stage=meta.stage, condition=meta.raw_condition, initialization=initialization[context],
                            extended73=context in ext_keys, method=method, pool=pool, cohort=cohort, metric=metric,
                            raw_support=len(pool_ids), calculable_support=len(available), pair_count=len(vals),
                            human_distance=np.mean(vals) if vals else np.nan, bi_distance=model_frame.loc[meta.image_id, metric]))
    pair_frame = save(out, "pair_distances.csv.gz", pairs)
    ctx = save(out, "context_distances.csv", ctx_rows)
    assoc = []
    for (method, pool, cohort, metric), g in ctx.groupby(["method", "pool", "cohort", "metric"]):
        scopes = [("extended73", g[g.extended73 & (g.calculable_support >= 2)]),
                  ("all_metric_n3", g[g.calculable_support >= 3])]
        for scope, gg in scopes:
            strata = [("all", gg), ("without_synthetic", gg[gg.initialization != "trap_synthetic_disjoint_source"])]
            strata += [(s + "|" + c, z) for (s, c), z in gg.groupby(["stage", "condition"])]
            for stratum, data in strata:
                data = data.dropna(subset=["bi_distance", "human_distance"])
                bs = sorted(data.building_id.unique())
                leave = [rho(z.bi_distance, z.human_distance) for b in bs if len(z := data[data.building_id != b]) >= 4]
                finite = [x for x in leave if np.isfinite(x)]
                bm = data.groupby("building_id")[["bi_distance", "human_distance"]].mean()
                im = data.groupby("image_id")[["bi_distance", "human_distance"]].mean()
                ranks = data[["bi_distance", "human_distance"]].rank()
                ranks = ranks - ranks.groupby(data.building_id).transform("mean")
                within = ranks.corr().iloc[0, 1] if len(ranks) > 3 else np.nan
                assoc.append(dict(method=method, pool=pool, cohort=cohort, metric=metric, scope=scope, stratum=stratum,
                    contexts=len(data), images=len(im), buildings=len(bs), rho=rho(data.bi_distance, data.human_distance),
                    image_mean_rho=rho(im.bi_distance, im.human_distance), building_mean_rho=rho(bm.bi_distance, bm.human_distance),
                    building_centered_rank_correlation=within, leave_building_min=min(finite) if finite else np.nan,
                    leave_building_max=max(finite) if finite else np.nan, leave_building_evaluable=len(finite),
                    interval="none_LOBO_range_is_not_confidence_interval"))
    associations = save(out, "associations.csv", assoc)

    cluster_rows, capture, support = [], [], []
    for p in ext.to_dict("records"):
        mm = members[members.partition_id == p["partition_id"]]
        assert not mm.worker_id.duplicated().any() and (mm.mapping_status == "matched").all()
        sizes = mm.groupby("cluster_id", sort=True).size()
        assert len(mm) == int(p["member_count"])
        cur = mm[mm.canonical_annotation_id.isin(current)]
        sizes_cur = cur.groupby("cluster_id").size().reindex(sizes.index, fill_value=0)
        support.append(dict(partition_id=p["partition_id"], context_key=p["context_key"], building_id=p["image_id"].split('_')[0],
            stage=p["stage"], condition=p["condition"], partition_status=p["partition_status"],
            top_support_tie=p["top_support_tie"], second_support_tie=p["second_support_tie"],
            raw_context_N=len(ids_by_context[p["context_key"]]), archived_member_N=len(mm), current20_archived_N=len(cur),
            original_clusters=len(sizes), current20_represented_clusters=int((sizes_cur > 0).sum())))
        for pool, ss in [("all_archived_members", sizes), ("current20_archived_members", sizes_cur)]:
            for k in range(1, 21):
                expected = expected_clusters(list(ss), k)
                capture.append(dict(partition_id=p["partition_id"], context_key=p["context_key"], pool=pool, k=k,
                    N=int(sum(ss)), original_cluster_count=len(sizes), expected_observed_clusters=expected,
                    expected_fraction_of_original_clusters=expected / len(sizes) if expected is not None else None,
                    fixed_partition=True, quality_estimate=False, subset_reclustering=False))
        for cluster, group in mm.groupby("cluster_id"):
            for method in methods:
                ids = sorted(set(group.canonical_annotation_id) & set(cache[method]["floor"]))
                row = dict(partition_id=p["partition_id"], context_key=p["context_key"], cluster_id=cluster, method=method,
                    rank=group.iloc[0]["rank"], original_support=len(group), calculable_support=len(ids),
                    representative_id="", medoid_enclosed=np.nan, medoid_extended=np.nan,
                    semantic_label="", representative_role="sensitivity_display_medoid_not_semantic_cluster")
                if ids:
                    d = np.zeros((len(ids), len(ids)))
                    for i, j in combinations(range(len(ids)), 2):
                        d[i, j] = d[j, i] = distance(method, "floor", ids[i], ids[j])
                    best = min(range(len(ids)), key=lambda k: (round(float(d[k].sum()), 12), ids[k]))
                    row["representative_id"] = ids[best]
                    for head in ("enclosed", "extended"):
                        row["medoid_" + head] = distance(method, "floor", ids[best], layout_meta[(p["image_id"], head)])
                cluster_rows.append(row)
    cluster_frame = save(out, "cluster_reading_sensitivity.csv", cluster_rows)
    save(out, "fixed_partition_capture.csv", capture)
    save(out, "partition_support.csv", support)
    # Preserve the exact displayed response identities; "rank2" is a display rank,
    # not a new semantic category or a claim that all cluster members were viewed.
    displayed = []
    selected = csv(REVIEW / "selection.csv").set_index("case_id")
    for case in selected.index:
        for path in sorted((REVIEW / "cases" / case).glob("*_source.json")):
            d = json.loads(path.read_text(encoding="utf-8-sig"))
            row = dict(case_id=case, image_id=selected.loc[case, "image_id"], variant=d["name"], source_id=d["source_id"],
                       geometry_role=d["geometry_role"], source_file=str(path.relative_to(ROOT)),
                       cluster_id=d.get("cluster_id", ""), worker_id="", raw_annotation_id="", context_key=d.get("context_key", ""))
            if d["source_id"] in raw:
                m = metadata.loc[d["source_id"]]
                row.update(worker_id=m.worker_id, raw_annotation_id=m.raw_annotation_id,
                           raw_export_path=m.raw_export_path, annotation_identity=m.annotation_identity)
                assert np.array_equal(d["points"], raw[d["source_id"]]["points_1024x512"])
            displayed.append(row)
    save(out, "display_identity_links.csv", displayed)
    # Reproduce the old serialized metric outputs, independent of their labels.
    old = pd.read_csv(REVIEW / "reproduced_numerical/analysis/contexts.csv").set_index("context_key")
    diffs = {}
    for m in metrics:
        sub = ctx[(ctx.method == methods[0]) & (ctx.pool == "all_historical") & (ctx.cohort == "method_available") & (ctx.metric == m)].set_index("context_key")
        left, right = sub.human_distance, old.loc[sub.index, "d_" + m]
        assert np.array_equal(left.isna(), right.isna())
        delta = (left - right).abs().max()
        assert delta < 1e-10
        diffs[m] = float(delta)
    qa = dict(canonical_annotations=len(a), historical_images=a.image_id.nunique(), historical_workers=a.worker_id.nunique(),
              contexts=len(ids_by_context), extended_partitions=len(ext), archived_clusters=len(cluster_frame) // 2,
              reading_human_rows=len(reading[reading.human]), original_context_distance_max_abs_diff=diffs,
              source_annotations_modified=False, old_clusters_modified=False, new_semantic_labels=False,
              hypotheses=list(methods), raw_only_historical42_not_replaced=True)
    write_json(out / "NUMERICAL_QA.json", qa)
    print(json.dumps(qa), flush=True)
    print(associations[(associations.stratum == "all") & (associations.pool == "all_historical") & (associations.metric == "floor")].to_string(index=False), flush=True)


def evidence(out=OUTPUT):
    """Read current GT and preserve candidates, never infer a remembered revision."""
    from PIL import Image, ImageDraw, ImageFont
    from scipy.optimize import linear_sum_assignment
    from urllib.parse import urlparse
    out.mkdir(parents=True, exist_ok=True)
    visual = out / "evidence"
    visual.mkdir(exist_ok=True)
    selection = csv(REVIEW / "selection.csv")
    image_to_case = dict(zip(selection.image_id, selection.case_id))
    image_to_case.update({
        "X7HyMhZNoso_a60fbec046b04e5bb256d4a665219f35": "V01_other_view",
        "X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9": "V33_other_view",
    })
    refs, exports, inventory = [], [], []
    gt_paths = sorted(set((ROOT / "export_label").glob("groudTruth*.json")) |
                      set((ROOT / "export_label/人工精标").glob("*.json")))
    for path in gt_paths:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        inventory.append(dict(path=str(path.relative_to(ROOT)), tasks=len(data), role="GT_source_snapshot_not_automatically_latest"))
        for task in data:
            im = Path(urlparse(task.get("data", {}).get("image", "")).path).stem
            if im not in image_to_case:
                continue
            for annotation in task.get("annotations", []):
                points = [[r["value"]["x"] * 10.24, r["value"]["y"] * 5.12]
                          for r in annotation.get("result", []) if r.get("type") == "keypointlabels"]
                exports.append(dict(case_id=image_to_case[im], image_id=im, source=str(path.relative_to(ROOT)),
                    task_id=task.get("id"), annotation_id=annotation.get("id"), completed_by=annotation.get("completed_by"),
                    point_count=len(points), points_1024x512=points,
                    current_gt_file=path == ROOT / "export_label/groudTruth.json"))
    for row in selection.to_dict("records"):
        for file in sorted((REVIEW / "cases" / row["case_id"]).glob("*reference*source.json")):
            r = json.loads(file.read_text(encoding="utf-8-sig"))
            for source in [x for x in exports if x["image_id"] == row["image_id"]]:
                p, q = np.asarray(r["points"], float), np.asarray(source["points_1024x512"], float)
                same_shape = p.shape == q.shape and len(p) > 0
                delta = np.nan
                if same_shape:
                    dx = (p[:, None, 0] - q[None, :, 0] + 512) % 1024 - 512
                    dy = p[:, None, 1] - q[None, :, 1]
                    distances = np.hypot(dx, dy)
                    ii, jj = linear_sum_assignment(distances)
                    delta = float(distances[ii, jj].max())
                refs.append(dict(case_id=row["case_id"], image_id=row["image_id"], displayed_variant=r["name"],
                    displayed_source_id=r["source_id"], gt_source=source["source"], gt_task_id=source["task_id"],
                    gt_annotation_id=source["annotation_id"], current_gt_file=source["current_gt_file"],
                    displayed_points=len(p), source_points=len(q),
                    raw_coordinate_sequence_equal=bool(same_shape and np.allclose(p, q, atol=1e-8, rtol=0)),
                    max_distance_in_min_sum_point_assignment_px=delta,
                    source_identity_does_not_establish_geometric_correctness=True))
    save(out, "reference_source_links.csv", refs)
    save(out, "searched_gt_sources.csv", inventory)
    write_json(out / "gt_source_snapshots.json", exports)

    # Point-only evidence: no invented edges when pairing fails.
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    case = "V06"
    source_file = next((REVIEW / "cases" / case).glob("*human_individual_W10_source.json"))
    source = json.loads(source_file.read_text())
    pano = Image.open(REVIEW / "cases" / case / "hd/panorama.png").convert("RGB")
    annotated = pano.copy()
    draw = ImageDraw.Draw(annotated)
    draw.line((0, pano.height // 2, pano.width, pano.height // 2), fill="yellow", width=2)
    point_rows = []
    for i, (x, y) in enumerate(source["points"]):
        xx, yy = x * pano.width / 1024, y * pano.height / 512
        draw.ellipse((xx - 4, yy - 4, xx + 4, yy + 4), fill="red")
        label_x, label_y = xx + 12 + (35 if i % 2 else 0), yy - 25 + (45 if i % 2 else 0)
        draw.line((xx, yy, label_x, label_y), fill="red", width=1)
        draw.text((label_x, label_y), str(i), font=font, fill="white", stroke_width=2, stroke_fill="black")
        point_rows.append(dict(case_id=case, source_id=source["source_id"], raw_point_id=i, x_1024=x, y_512=y,
                               signed_vertical_degrees=(256-y)*180/512))
    annotated.save(visual / "V06_original_point_ids.png")
    # The two near-horizon points are precisely why small pixel changes imply
    # large planar distances; magnify their actual pixels without moving points.
    first = np.asarray(source["points"][:2]) * np.array([pano.width / 1024, pano.height / 512])
    cx, cy = first.mean(axis=0)
    box = (max(0, int(cx)-180), max(0, int(cy)-130), min(pano.width, int(cx)+180), min(pano.height, int(cy)+180))
    annotated.crop(box).resize((720,620)).save(visual / "V06_far_end_point_crop.png")
    save(out, "V06_point_roles.csv", point_rows)
    # Same-building contact sheets are a search aid, not a room-ID assignment.
    files = sorted((ROOT / "data/mp3d_layout/img_v").glob("X7HyMhZNoso*.jpg"))
    contacts = []
    for offset in range(0, len(files), 10):
        batch = files[offset:offset+10]
        sheet = Image.new("RGB", (1280, ((len(batch)+1)//2)*350), "white")
        for j, file in enumerate(batch):
            x, y = (j % 2)*640, (j//2)*350
            im = Image.open(file).convert("RGB").resize((640,320))
            sheet.paste(im, (x,y+30))
            ImageDraw.Draw(sheet).text((x+5,y+4), f"{offset+j+1:02d} {file.stem.split('_')[1][:12]}", font=font, fill="black")
            contacts.append(dict(contact_number=offset+j+1, image_id=file.stem, source=str(file.relative_to(ROOT)),
                                 sheet=f"evidence/X7_contact_{offset//10+1}.jpg", room_identity_verified=False))
        sheet.save(visual / f"X7_contact_{offset//10+1}.jpg", quality=93)
    save(out, "multiview_search_index.csv", contacts)
    # Archived reading-sensitivity displays, not proposals to reorder normal previews.
    audit, renderer = helpers()
    render_rows = []
    for case in ("V03", "V07", "V10", "V13", "V16", "V21", "V22", "V23", "V31"):
        tex = np.asarray(Image.open(REVIEW / "cases" / case / "hd/panorama.png").convert("RGB"))
        for file in sorted((REVIEW / "cases" / case).glob("*source.json")):
            d = json.loads(file.read_text())
            if not (d["name"].startswith("human") or (case in ("V07", "V31") and d["name"].startswith("reference"))):
                continue
            record = dict(case_id=case, variant=d["name"], source_id=d["source_id"], reading="historical_pairmap_unaveraged",
                          artifact="", status="", author_intent_verified=False)
            try:
                ids = historical_pair_ids(d["points"])
                q = np.asarray(d["points"])[ids]
                audit.footprint(q)
                f, t, _ = audit.lift(q)
                im1 = renderer.render(tex, f, t, top=True, size=350)
                im2 = renderer.render(tex, f, t, size=350)
                sheet = Image.new("RGB", (700, 380), "white")
                sheet.paste(im1,(0,30));sheet.paste(im2,(350,30))
                ImageDraw.Draw(sheet).text((5,4), case+" "+d["name"]+" / reading sensitivity", font=ImageFont.load_default(size=17), fill="black")
                name = case+"_"+d["name"]+"_historical_reading.jpg"
                sheet.save(visual/name, quality=92)
                record.update(artifact="evidence/"+name,status="rendered_not_adjudicated",raw_point_ids_json=json.dumps(ids))
            except (ValueError, IndexError, TypeError) as e:
                record["status"] = str(e)
            render_rows.append(record)
    save(out,"targeted_render_log.csv",render_rows)
    rendered = [r for r in render_rows if r["artifact"]]
    for offset in range(0, len(rendered), 6):
        batch = rendered[offset:offset+6]
        sheet = Image.new("RGB", (1400, ((len(batch)+1)//2)*380), "white")
        for i, r in enumerate(batch):
            sheet.paste(Image.open(out/r["artifact"]), ((i%2)*700, (i//2)*380))
        sheet.save(visual/f"reading_previews_{offset//6+1}.jpg", quality=94)
    print(json.dumps(dict(gt_snapshots=len(exports),reference_comparisons=len(refs),search_images=len(contacts),
                         targeted_render_status=dict(Counter(r['status'] for r in render_rows)))),flush=True)


def summarize(out=OUTPUT):
    """Derived tables/figures only; no model selection or new semantic adjudication."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ctx = pd.read_csv(out/"context_distances.csv")
    part = csv(INPUT/"clusters/partitions.csv.gz")
    ext = part[part.version=="extended73"].copy()
    ext.cluster_count = ext.cluster_count.astype(int)
    # Zero is a placeholder for not_evaluable, not zero human structural modes.
    cluster_assoc=[]
    for method in ctx.method.unique():
        d=ctx[(ctx.method==method)&(ctx.pool=="all_historical")&(ctx.cohort=="method_available")&(ctx.metric=="floor")]
        d=d.merge(ext[["context_key","cluster_count","partition_status"]],on="context_key",validate="one_to_one")
        for valid in [False,True]:
            z=d[d.partition_status=="unique"] if valid else d
            z=z.dropna(subset=["bi_distance"])
            cluster_assoc.append(dict(method=method,invalid_partition_placeholders_excluded=valid,
                contexts=len(z),buildings=z.building_id.nunique(),rho=rho(z.bi_distance,z.cluster_count),
                zero_placeholder_rows=int((z.partition_status!="unique").sum())))
    save(out,"cluster_count_validity_sensitivity.csv",cluster_assoc)
    f=pd.read_csv(out/"fixed_partition_capture.csv")
    support=pd.read_csv(out/"partition_support.csv")
    cohorts={"all_archived_N20":set(support[support.archived_member_N>=20].partition_id),
             "same_partitions_current20_N20":set(support[support.current20_archived_N>=20].partition_id)}
    summaries=[]
    for name,ids in cohorts.items():
        for (pool,k),g in f[f.partition_id.isin(ids)].groupby(["pool","k"]):
            v=g.dropna(subset=["expected_fraction_of_original_clusters"])
            summaries.append(dict(cohort=name,pool=pool,k=int(k),partitions=len(v),
                expected_clusters_mean=v.expected_observed_clusters.mean(),
                expected_fraction_mean=v.expected_fraction_of_original_clusters.mean(),
                weighting=("equal_partition_available_at_k" if name=='all_archived_N20' and pool=='current20_archived_members'
                           else "equal_partition_fixed_cohort")))
    sums=save(out,"fixed_partition_capture_summary.csv",summaries)
    # Correlations across plots use identical definitions but transparently different domains.
    fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout="constrained")
    for ax,(scope,label) in zip(axes,[("extended73","High-coverage 73-unit frame"),("all","All contexts with >=3 computable people")]):
        z=ctx[(ctx.method=="historical_pairmap_unaveraged")&(ctx.pool=="all_historical")&(ctx.cohort=="method_available")&(ctx.metric=="floor")]
        z=z[(z.extended73)&(z.calculable_support>=2)] if scope=="extended73" else z[z.calculable_support>=3]
        z=z.dropna(subset=["bi_distance","human_distance"])
        for condition,color in [("manual","#377eb8"),("semi","#e68632"),("oos","#757575")]:
            q=z[z.condition==condition]
            ax.scatter(q.bi_distance,q.human_distance,s=25,alpha=.7,label=f"{condition} ({len(q)})",color=color)
        ax.set(title=f"{label}\nn={len(z)}, Spearman rho={rho(z.bi_distance,z.human_distance):.3f}",
               xlabel="Bi E-X footprint distance (1-IoU)",ylabel="Mean human-human footprint distance")
        ax.legend(frameon=False,fontsize=8);ax.grid(alpha=.15)
    fig.savefig(out/"association_domains.png",dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5),layout="constrained")
    for pool,label in [("all_archived_members","All archived people"),("current20_archived_members","Current 20 only")]:
        g=sums[(sums.cohort=="same_partitions_current20_N20")&(sums.pool==pool)]
        ax.plot(g.k,g.expected_fraction_mean,marker=".",label=label)
    ax.set(xlabel="Number sampled without replacement",ylabel="Expected fraction of archived clusters seen",
           title="Fixed archived partitions; same 51 units\nCluster discovery, not quality or new-person prediction",ylim=(0,1.03))
    ax.axvline(15,color="#888888",linestyle="--",linewidth=.8)
    ax.legend(frameon=False);ax.grid(alpha=.2)
    fig.savefig(out/"fixed_partition_capture.png",dpi=170);plt.close(fig)
    status=pd.read_csv(out/"reading_status.csv.gz")
    h=status[status.human].copy()
    h["floor_computable"]=h.floor_status=="computable"
    h["band_computable"]=h.band_status=="computable"
    save(out,"reading_coverage_by_condition.csv",h.groupby(["method","stage","raw_condition"]).agg(
        responses=("layout_id","size"),floor_computable=("floor_computable","sum"),band_computable=("band_computable","sum")).reset_index())
    changes=h.pivot(index="layout_id",columns="method",values="floor_computable")
    write_json(out/"READING_TRANSITIONS.json",dict(
        both=int(changes.all(axis=1).sum()),neither=int((~changes.any(axis=1)).sum()),
        gained_historical=int((changes.historical_pairmap_unaveraged&~changes.serialized_adjacency).sum()),
        lost_historical=int((~changes.historical_pairmap_unaveraged&changes.serialized_adjacency).sum()),
        conclusion="Computability sensitivity, not repaired annotations or worker quality"))
    selection=csv(REVIEW/"selection.csv")[["case_id","image_id"]]
    save(out,"reviewed_case_context_metrics.csv",ctx.merge(selection,on="image_id",validate="many_to_one"))
    display=csv(out/"display_identity_links.csv")
    readings=json.loads((HUMAN/"scope_comment_readings.json").read_text(encoding="utf-8-sig"))
    human={r['case_id']:r for r in json.loads((HUMAN/'reconciled_records.json').read_text(encoding='utf-8-sig'))}
    # Manually read targets with unambiguous display identities. Set expressions
    # such as 'others' and references without a unique displayed version stay open.
    explicit={
        "V07-S1":["human_rank2"], "V09-S1":["human_individual_W2"],
        "V09-S2":["reference_0"], "V11-S1":["reference_0"],
        "V13-S1":["HoHoNet_single","reference_0"],
        "V17-S1":["Bi-Layout_enclosed"], "V21-S2":["reference_0"],
        "V29-S1":["Bi-Layout_extended","HoHoNet_single"],
        "V31-S1":["reference_0"], "V35-S1":["reference_0","reference_1"],
        "V36-S1":["Bi-Layout_enclosed"], "V36-S2":["HoHoNet_single"],
        "V44-S1":["Bi-Layout_extended"],
    }
    bindings=[]
    for case in readings:
        for st in case['scope_statements']:
            if st['kind']!='semantic_assignment':continue
            assert st['quote'] in human[case['case_id']]['human_record']['answers'][st['source_field']]
            matched=[]
            for name in explicit.get(st['statement_id'],[]):
                rows=display[(display.case_id==case['case_id'])&(display.variant==name)]
                assert len(rows)==1
                matched.extend(rows.to_dict('records'))
            bindings.append(dict(statement_id=st['statement_id'],case_id=case['case_id'],quote=st['quote'],
                original_target=st['target'],human_scope_word=st['scope_label'],qualification=st['qualification'],
                matched_display_objects=matched,whole_cluster_semantics_verified=False,
                identity_status=('partially_resolved_reference_version_open' if st['statement_id'] in ['V17-S1','V36-S1','V44-S1'] else
                                 'current_gt_source_matched' if st['statement_id']=='V31-S1' else
                                 'displayed_objects_resolved' if matched else 'collective_target_kept_unexpanded'),
                final_geometry_adjudication=None))
    # Supplements are copied as authored, separate from old questionnaire readings.
    supplements=json.loads((HUMAN/'human_supplements_20260908.json').read_text(encoding='utf-8-sig'))
    write_json(out/'human_scope_identity_bindings.json',dict(
        source='human_review_reconciliation_20260907_v1/scope_comment_readings.json',
        bindings=bindings,latest_supplements=supplements,
        V04_latest_enclosed_display_objects=display[(display.case_id=='V04')&display.variant.isin(
            ['reference_0','human_individual_W11','human_individual_W15'])].to_dict('records'),
        interpretations_are_not_new_human_adjudications=True))


def local_export_search(out=OUTPUT):
    """Search only current local export_label JSON, per the user's correction."""
    from PIL import Image,ImageDraw,ImageFont
    selection=csv(REVIEW/'selection.csv')
    targets=dict(zip(selection[selection.case_id.isin(['V07','V10','V20','V31','V33'])].image_id,
                     selection[selection.case_id.isin(['V07','V10','V20','V31','V33'])].case_id))
    alt='X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9'
    targets[alt]='V33_other_view'
    rows,scan=[] ,[]
    for path in sorted((ROOT/'export_label').rglob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        record=dict(path=path.relative_to(ROOT).as_posix(),task_list=isinstance(data,list),matched_tasks=0,matched_annotations=0)
        if isinstance(data,list):
            for task in data:
                if not isinstance(task,dict):continue
                serialized=json.dumps(task.get('data',{}),ensure_ascii=False)
                matched=[image for image in targets if image in serialized]
                if not matched:continue
                assert len(matched)==1
                image=matched[0];record['matched_tasks']+=1
                for ann in task.get('annotations',[]):
                    kp=[r for r in ann.get('result',[]) if r.get('type')=='keypointlabels']
                    pts=[[r['value']['x']*10.24,r['value']['y']*5.12] for r in kp]
                    rows.append(dict(case_id=targets[image],image_id=image,source=path.relative_to(ROOT).as_posix(),
                        project=task.get('project'),task_id=task.get('id'),annotation_id=ann.get('id'),
                        completed_by=ann.get('completed_by'),ground_truth=ann.get('ground_truth'),
                        was_cancelled=ann.get('was_cancelled'),created_at=ann.get('created_at'),updated_at=ann.get('updated_at'),
                        parent_annotation=ann.get('parent_annotation'),parent_prediction=ann.get('parent_prediction'),
                        point_count=len(pts),points_1024x512=pts,raw_keypoint_ids=[r.get('id') for r in kp],
                        point_origins=[r.get('origin') for r in kp]))
                    record['matched_annotations']+=1
        scan.append(record)
    spine=csv(INPUT/'facts/annotation_spine.csv.gz')
    for r in rows:
        match=spine[(spine.image_id==r['image_id']) & (spine.project_id==str(r['project'])) &
                    (spine.runtime_task_id==str(r['task_id'])) &
                    (spine.raw_annotation_id==str(r['annotation_id'])) &
                    (spine.raw_worker_id==str(r['completed_by']))]
        assert len(match)<=1
        r['canonical_annotation_id']=match.iloc[0].canonical_annotation_id if len(match) else None
        r['annotation_identity']=match.iloc[0].annotation_identity if len(match) else None
        r['condition']=match.iloc[0].raw_condition if len(match) else None
        r['canonical_link_status']='exact_image_project_task_author_annotation' if len(match) else 'outside_spine_or_unresolved'
    save(out,'local_export_search_inventory.csv',scan)
    write_json(out/'local_export_annotation_matches.json',rows)
    save(out,'local_export_annotation_matches.csv',[{k:v for k,v in r.items() if k not in ['points_1024x512','raw_keypoint_ids','point_origins']} for r in rows])
    # No new order proposals. Show source points over the actual pixels, without
    # manufacturing red walls from the serialization list.
    visual=out/'evidence';visual.mkdir(exist_ok=True)
    wanted=[r for r in rows if r['image_id']==alt and (
        (r['source']=='export_label/groudTruth.json') or
        (r['source'].startswith('export_label/stage2_Chinese/') and r['annotation_id']==6154))]
    assert len(wanted)==2
    wanted += [r for r in rows if (r['case_id'],r['annotation_id']) in [('V10',6676),('V20',6329)]
               and '/groudTruth' not in r['source']]
    assert len(wanted)==4
    point_records=[]
    for r in wanted:
        texture=Image.open(ROOT/f'data/mp3d_layout/test/img/{alt}.png' if r['image_id']==alt else
                           REVIEW/'cases'/r['case_id']/'hd/panorama.png').convert('RGB')
        panel=texture.copy();d=ImageDraw.Draw(panel)
        for i,(x,y) in enumerate(r['points_1024x512']):
            xx=x*texture.width/1024;yy=y*texture.height/512
            d.ellipse((xx-5,yy-5,xx+5,yy+5),fill='#ff3060')
            dx=18 if i%2==0 else -42
            if r['annotation_id']==6154 and i in [10,13]:dx=-55 if i==10 else 25
            d.line((xx,yy,xx+dx,yy-20),fill='white',width=1)
            d.text((xx+dx,yy-35),str(i),font=ImageFont.load_default(size=24),fill='white',stroke_width=2,stroke_fill='black')
            point_records.append(dict(case_id=r['case_id'],annotation_id=r['annotation_id'],raw_point_index=i,raw_keypoint_id=r['raw_keypoint_ids'][i],x=x,y=y))
        panel.save(visual/f"{r['case_id']}_ann{r['annotation_id']}_points.png")
    save(out,'local_export_candidate_point_ids.csv',point_records)
    save(out,'V33_other_view_point_ids.csv',[r for r in point_records if r['case_id']=='V33_other_view'])
    # Only these previews were visually found severely malformed. This list is
    # not inferred from parser failure and contains no proposed correct order.
    requests=[]
    for case in ['V07','V31']:
        r=next(r for r in rows if r['case_id']==case and r['source']=='export_label/groudTruth.json')
        source=json.loads(next((REVIEW/'cases'/case).glob('*reference_0_source.json')).read_text(encoding='utf-8'))
        assert np.allclose(r['points_1024x512'],source['points'],rtol=0,atol=1e-8)
        panel=Image.open(REVIEW/'cases'/case/'hd/panorama.png').convert('RGB');d=ImageDraw.Draw(panel)
        for i,(x,y) in enumerate(r['points_1024x512']):
            xx=x*panel.width/1024;yy=y*panel.height/512
            dx=22 if i%2==0 else -40;dy=-38 if i%4<2 else 25
            d.ellipse((xx-4,yy-4,xx+4,yy+4),fill='red')
            d.line((xx,yy,xx+dx,yy+dy),fill='white',width=1)
            d.text((xx+dx,yy+dy),str(i),font=ImageFont.load_default(size=23),fill='white',stroke_width=2,stroke_fill='black')
        panel.save(visual/f'{case}_current_GT_raw_point_ids.png')
        requests.append(dict(case_id=case,source=r['source'],task_id=r['task_id'],annotation_id=r['annotation_id'],
            points_1024x512=r['points_1024x512'],raw_keypoint_ids=r['raw_keypoint_ids'],
            point_index_base=0,trigger='visually_severely_malformed_preview',
            current_preview=f'evidence/{case}_reference_0_historical_reading.jpg',
            numbered_panorama=f'evidence/{case}_current_GT_raw_point_ids.png',
            user_corner_pairs_in_boundary_order=None,agent_proposed_order=None,
            original_coordinates_modified=False))
    confirmation_file=out/'confirmed_20260908/user_confirmations.json'
    if confirmation_file.exists():
        confirmed=json.loads(confirmation_file.read_text(encoding='utf-8'))
        for r in requests:
            c=next((c for c in confirmed if c['case_id']==r['case_id'] and c['annotation_id']==r['annotation_id']),None)
            if c:
                assert c['raw_points']==r['points_1024x512']
                r['user_corner_pairs_in_boundary_order']=np.array(c['raw_point_ids']).reshape(-1,2).tolist()
                r['user_confirmation_source']='confirmed_20260908/user_confirmations.json'
    write_json(out/'targeted_order_review.json',requests)
    write_json(out/'LOCAL_EXPORT_SEARCH_QA.json',dict(scope='local export_label/**/*.json only',
        git_history_searched=False,json_files=len(scan),matched_annotations=len(rows),
        matched_sources=sum(r['matched_tasks']>0 for r in scan),source_files_modified=False,
        other_view_new_C1_annotation=6154,authorship_of_user_not_assumed=True))
    print(json.dumps(dict(local_json_files=len(scan),matched_annotations=len(rows),
                         C1_record=[{k:v for k,v in r.items() if k not in ['points_1024x512','raw_keypoint_ids','point_origins']} for r in wanted if r['annotation_id']==6154])),flush=True)


def confirmed_analysis(out=OUTPUT):
    """User-confirmed preview derivatives and finite empirical distribution audit."""
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    dest=out/'confirmed_20260908';dest.mkdir(exist_ok=True)
    records=json.loads((out/'local_export_annotation_matches.json').read_text(encoding='utf-8'))
    orders={'V33_other_view':[1,3,9,11,12,15,5,7],
            'V07':[5,16,18,7,9,11,13,15,1,3], 'V31':[15,13,9,11,1,3,5,7]}
    audit,renderer=helpers()
    a,images,partitions,members,versions,models,refs,raw,norm=audit.load()
    current=set(a[a.current20_member.map(audit.yes)].canonical_annotation_id)
    confirmed=[];geometry=[];distances=[];reference_comparisons=[]
    for case,bottoms in orders.items():
        r=next(r for r in records if r['case_id']==case and
               (r['annotation_id']==6154 if case=='V33_other_view' else r['source']=='export_label/groudTruth.json'))
        # Recheck against actual local export, not only the prior search result.
        task=next(t for t in json.loads((ROOT/r['source']).read_text(encoding='utf-8-sig')) if t['id']==r['task_id'])
        ann=next(t for t in task['annotations'] if t['id']==r['annotation_id'])
        kp=[t for t in ann['result'] if t['type']=='keypointlabels']
        p=np.array([[t['value']['x']*10.24,t['value']['y']*5.12] for t in kp])
        assert np.array_equal(p,r['points_1024x512'])
        ids=user_bottom_order(p,bottoms);q=p[ids]
        confirmed.append(dict(case_id=case,image_id=r['image_id'],source=r['source'],task_id=r['task_id'],
            annotation_id=r['annotation_id'],canonical_annotation_id=r['canonical_annotation_id'],
            user_bottom_order=bottoms,raw_point_ids=ids,raw_keypoint_ids=[t['id'] for t in kp],
            raw_points=p.tolist(),derived_points=q.tolist(),user_order_confirmed=True,
            user_version_identity_confirmed=case=='V33_other_view',coordinates_changed=False,
            omitted_points=[],is_final_geometry_adjudication=False,
            supersedes='V07 initial response omitted 11; subsequent user reply restores it' if case=='V07' else None))
        tex=ROOT/f"data/mp3d_layout/test/img/{r['image_id']}.png" if case=='V33_other_view' else REVIEW/'cases'/case/'hd/panorama.png'
        tex=np.asarray(Image.open(tex).convert('RGB'))
        for method,points in [('serialized_adjacency',p),('historical_pairmap_unaveraged',p[historical_pair_ids(p)]),('user_confirmed_order',q)]:
            row=dict(case_id=case,method=method,point_count=len(points),floor_status='',band_status='',preview='',
                     floor_area=None,axis_residual_degrees=None,ceiling_height_range=None,multi_hit_ray_fraction_720=None)
            try:
                poly=audit.footprint(points);f,t,_=audit.lift(points)
                edges=np.roll(f[:,[0,2]],-1,axis=0)-f[:,[0,2]]
                angles=np.rad2deg(np.arctan2(edges[:,1],edges[:,0]));weights=np.linalg.norm(edges,axis=1)
                # Diagnostic orientation fit only; no point movement or snapping.
                residuals=abs((angles[None,:]-np.arange(0,90,.05)[:,None]+45)%90-45)
                row.update(floor_status='computable',floor_area=poly.area,
                    axis_residual_degrees=float(np.average(residuals,axis=1,weights=weights).min()),
                    ceiling_height_range=float(np.ptp(t[:,1])))
                from shapely.geometry import LineString
                radius=float(np.linalg.norm(f[:,[0,2]],axis=1).max()*2)
                hits=[]
                for angle in (np.arange(720)+.37)*2*np.pi/720:
                    intersection=poly.boundary.intersection(LineString([(0,0),(radius*np.cos(angle),radius*np.sin(angle))]))
                    assert intersection.geom_type in ['Point','MultiPoint']
                    hits.append(1 if intersection.geom_type=='Point' else len(intersection.geoms))
                row['multi_hit_ray_fraction_720']=float(np.mean(np.array(hits)>1))
                if method=='user_confirmed_order':
                    panel=Image.new('RGB',(1200,632),'white')
                    panel.paste(renderer.title(renderer.render(tex,f,t,top=True,size=600),case+' / user order / top'),(0,0))
                    panel.paste(renderer.title(renderer.render(tex,f,t,size=600),case+' / user order / perspective'),(600,0))
                    name=f'{case}_user_order_preview.png';panel.save(dest/name);row['preview']=name
                    overlay,_=renderer.overlay(tex,points,True,point_ids=ids)
                    overlay.save(dest/f'{case}_user_order_overlay.png')
                    fig,axes=plt.subplots(1,2,figsize=(9,5),layout='constrained')
                    for ax,reading,mapping in zip(axes,['Historical x-pair reading','User-confirmed boundary'],[historical_pair_ids(p),ids]):
                        ff,_,_=audit.lift(p[mapping]);ring=ff[:,[0,2]]
                        ax.plot(*np.vstack([ring,ring[0]]).T,marker='.',color='#236eab')
                        for j,(x,z) in enumerate(ring):ax.annotate(str(mapping[j*2+1]),(x,z),xytext=(4,4),textcoords='offset points',fontsize=8)
                        ax.plot(0,0,'r+',label='camera');ax.set_aspect('equal');ax.set_title(reading)
                        ax.set(xlabel='x / camera height',ylabel='z / camera height');ax.grid(alpha=.2)
                    fig.suptitle(case+' / same source coordinates; bottom-point IDs')
                    fig.savefig(dest/f'{case}_adjacency_comparison.png',dpi=160);plt.close(fig)
            except (ValueError,IndexError,TypeError) as e:row['floor_status']=str(e)
            try:audit.band(points);row['band_status']='computable'
            except (ValueError,IndexError,TypeError) as e:row['band_status']=str(e)
            geometry.append(row)
        try:poly=audit.footprint(q)
        except ValueError:continue
        fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
        matched_models=[m for m in models if m['image_id']==r['image_id']]
        assert len(matched_models)==3
        uf,_,_=audit.lift(q);user_ring=uf[:,[0,2]]
        for ax,m in zip(axes,matched_models):
            if m['image_id']!=r['image_id']:continue
            row=dict(case_id=case,model=m['model_family'],head=m['head'],distance=None,status='')
            ax.plot(*np.vstack([user_ring,user_ring[0]]).T,color='#333333',label='user-confirmed order')
            try:
                row.update(distance=audit.dp(poly,audit.footprint(m['points_1024x512'])),status='computable')
                ff,_,_=audit.lift(m['points_1024x512']);rr=ff[:,[0,2]]
                ax.plot(*np.vstack([rr,rr[0]]).T,'--',color='#e67f22',label='model')
            except ValueError as e:
                row['status']=str(e)
                ax.text(.03,.95,'Model unavailable: '+str(e),transform=ax.transAxes,va='top',fontsize=8,color='#a00000')
            ax.plot(0,0,'r+');ax.set_aspect('equal');ax.set_title(m['model_family']+' '+m['head']);ax.grid(alpha=.2)
            distances.append(row)
        axes[0].legend(fontsize=8);fig.suptitle(case+' / footprint comparison; same camera-height scale')
        fig.savefig(dest/f'{case}_model_comparison.png',dpi=160);plt.close(fig)
        if case=='V33_other_view':
            gt=next(x for x in records if x['image_id']==r['image_id'] and x['source']=='export_label/groudTruth.json')
            gtpoly=audit.footprint(gt['points_1024x512'])
            reference_comparisons.append(dict(case_id=case,confirmed_annotation=r['annotation_id'],reference_annotation=gt['annotation_id'],
                confirmed_area=poly.area,reference_area=gtpoly.area,added_area=poly.difference(gtpoly).area,
                removed_area=gtpoly.difference(poly).area,iou=poly.intersection(gtpoly).area/poly.union(gtpoly).area,
                units='squared_camera_height_not_square_meters',reference_not_overwritten=True))
    write_json(dest/'user_confirmations.json',confirmed)
    requests=json.loads((out/'targeted_order_review.json').read_text(encoding='utf-8'))
    for request in requests:
        c=next(c for c in confirmed if c['case_id']==request['case_id'])
        assert c['raw_points']==request['points_1024x512'] and c['annotation_id']==request['annotation_id']
        request['user_corner_pairs_in_boundary_order']=np.array(c['raw_point_ids']).reshape(-1,2).tolist()
        request['user_confirmation_source']='confirmed_20260908/user_confirmations.json'
    write_json(out/'targeted_order_review.json',requests)
    save(dest,'confirmed_geometry.csv',geometry);save(dest,'confirmed_model_distances.csv',distances)
    save(dest,'confirmed_reference_comparison.csv',reference_comparisons)
    # Only one confirmed object is a historical response. Preserve the old global
    # analysis and explicitly compare this context with a single replacement.
    r=next(r for r in confirmed if r['case_id']=='V33_other_view')
    identity=r['canonical_annotation_id'];context=a[a.canonical_annotation_id==identity].iloc[0].context_key
    changes=[]
    for pool in ['all_historical','current20_only']:
        ids=a[a.context_key==context].canonical_annotation_id.tolist()
        if pool=='current20_only':ids=[i for i in ids if i in current]
        for replacement in [False,True]:
            polys={}
            for i in ids:
                try:
                    p=raw[i]['points_1024x512'];q=r['derived_points'] if replacement and i==identity else np.asarray(p)[historical_pair_ids(p)]
                    polys[i]=audit.footprint(q)
                except ValueError:continue
            values=[audit.dp(x,y) for x,y in combinations(polys.values(),2)]
            changes.append(dict(context_key=context,pool=pool,user_order_applied=replacement,
                raw_support=len(ids),computable_support=len(polys),human_mean_distance=np.mean(values) if values else None))
    save(dest,'single_response_context_sensitivity.csv',changes)
    # Reuse memberships as archived; no new semantic names or reclustering.
    recover=[];mixtures=[]
    for p in partitions[(partitions.version=='extended73')&(partitions.partition_status=='unique')].to_dict('records'):
        mm=members[members.partition_id==p['partition_id']]
        assert len(mm)==int(p['member_count']) and not mm.worker_id.duplicated().any()
        assert (mm.mapping_status=='matched').all()
        sizes=mm.groupby('cluster_id').size()
        assert len(sizes)==int(p['cluster_count'])
        inside=mm[mm.canonical_annotation_id.isin(current)].groupby('cluster_id').size().reindex(sizes.index,fill_value=0)
        outside=sizes-inside
        meta={k:p[k] for k in ['partition_id','context_key','image_id','stage','condition']}
        meta['building_id']=p['image_id'].split('_')[0]
        meta['current20_complete']=int(inside.sum())==20
        for pool,ss in [('all_archived',sizes),('current20',inside)]:
            for k in range(1,min(20,int(ss.sum()))+1):
                recover.append(dict(**meta,pool=pool,k=k,N=int(ss.sum()),
                    **distribution_recovery([ss.tolist()],[k],sizes.tolist())))
        if inside.sum()==20:
            for n_other in range(min(5,int(outside.sum()))+1):
                mixtures.append(dict(**meta,total_k=20,outside_current20_draws=n_other,
                    outside_available=int(outside.sum()),
                    **distribution_recovery([inside.tolist(),outside.tolist()],[20-n_other,n_other],sizes.tolist())))
    rec=save(dest,'distribution_recovery.csv',recover);mix=save(dest,'roster_mixture.csv',mixtures)
    fixed=rec[rec.current20_complete]
    metrics=['expected_tv','expected_missing_mass','expected_cluster_fraction']
    summary=fixed.groupby(['pool','k']).agg(partitions=('partition_id','nunique'),**{m:(m,'mean') for m in metrics}).reset_index()
    assert set(summary.partitions)=={51}
    save(dest,'distribution_summary_fixed51.csv',summary)
    building=fixed[fixed.k.isin([15,20])].groupby(['building_id','pool','k']).agg(
        partitions=('partition_id','nunique'),**{m:(m,'mean') for m in metrics}).reset_index()
    save(dest,'building_distribution_fixed51.csv',building)
    # Same fixed subset across all six compositions; a logistical roster split,
    # not an inferred careful/careless split and not a prescription to recruit.
    eligible=set(mix[mix.outside_available>=5].partition_id)
    ms=mix[mix.partition_id.isin(eligible)].groupby('outside_current20_draws').agg(
        partitions=('partition_id','nunique'),**{m:(m,'mean') for m in metrics}).reset_index()
    save(dest,'roster_mixture_fixed_cohort.csv',ms)
    predictions=[]
    for (pool,k),g in fixed[fixed.k.isin([15,20])].groupby(['pool','k']):
        for row in g.to_dict('records'):
            for conditioning in ['unstratified','same_stage_condition']:
                train=g[g.image_id!=row['image_id']]
                if conditioning=='same_stage_condition':train=train[(train.stage==row['stage'])&(train.condition==row['condition'])]
                same=train[train.building_id==row['building_id']]
                if len(same)<2:continue
                for m in ['expected_tv','expected_cluster_fraction']:
                    predictions.append(dict(partition_id=row['partition_id'],building_id=row['building_id'],pool=pool,k=k,metric=m,
                        conditioning=conditioning,observed=row[m],same_building_prediction=same[m].mean(),global_prediction=train[m].mean(),
                        same_building_training_images=same.image_id.nunique(),global_training_images=train.image_id.nunique()))
    pred=save(dest,'building_leave_image_out.csv',predictions)
    ps=[]
    for (pool,k,m,conditioning),g in pred.groupby(['pool','k','metric','conditioning']):
        ps.append(dict(pool=pool,k=k,metric=m,conditioning=conditioning,images=len(g),buildings=g.building_id.nunique(),
            same_building_MAE=abs(g.observed-g.same_building_prediction).mean(),
            global_MAE=abs(g.observed-g.global_prediction).mean(),validation='internal_same_building_shared_workers_not_new_building'))
    save(dest,'building_prediction_summary.csv',ps)
    spine=csv(INPUT/'facts/annotation_spine.csv.gz')
    repeated=spine.groupby(['image_id','worker_id']).filter(lambda g:len(g)>1)
    save(dest,'repeated_image_worker_records.csv',repeated[['annotation_identity','image_id','worker_id','stage','block_index','raw_condition','raw_annotation_id']])
    paired=[]
    for (stage,image),g in spine.groupby(['stage','image_id']):
        if {'manual','semi'}<=set(g.raw_condition):
            paired.append(dict(stage=stage,image_id=image,building_id=image.split('_')[0],
                manual_rows=int((g.raw_condition=='manual').sum()),semi_rows=int((g.raw_condition=='semi').sum())))
    save(dest,'manual_semi_same_image_support.csv',paired)
    write_json(dest/'REPEATED_MEASURES_QA.json',dict(canonical_rows=len(spine),
        repeated_image_worker_pairs=repeated.groupby(['image_id','worker_id']).ngroups,
        repeated_rows=len(repeated),repeated_images=repeated.image_id.nunique(),
        same_image_stage_manual_semi_units=len(paired),
        longitudinal_revision_learning_not_established=True,versions_are_not_independent_people=True))
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    for ax,m,label in zip(axes,metrics,['Expected TV to historical distribution','Expected missed historical mass','Expected archived cluster fraction']):
        for pool,g in summary.groupby('pool'):ax.plot(g.k,g[m],label=pool)
        ax.set(xlabel='People sampled without replacement',ylabel=label);ax.grid(alpha=.2)
    axes[0].legend();fig.suptitle('Same 51 fixed partitions; empirical recovery, not quality or repeated-round learning')
    fig.savefig(dest/'distribution_recovery.png',dpi=160);plt.close(fig)
    write_json(dest/'CONFIRMED_QA.json',dict(confirmed_layouts=len(confirmed),raw_coordinates_unchanged=True,
        original_spine_unchanged=True,partition_definitions_unchanged=True,distribution_reference='full archived empirical partition',
        fixed_cohort=51,mixture_fixed_cohort=len(eligible),new_worker_prediction=False,quality_ceiling_estimated=False))
    print(json.dumps(geometry),flush=True)
    print(summary[summary.k.isin([15,20])].to_string(index=False),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--evidence-only", action="store_true")
    parser.add_argument("--local-export-search", action="store_true")
    parser.add_argument("--confirmed-analysis", action="store_true")
    args = parser.parse_args()
    if args.confirmed_analysis:
        confirmed_analysis(args.out)
    elif args.local_export_search:
        local_export_search(args.out)
    else:
        if not args.evidence_only:
            run(args.out)
        evidence(args.out)
        summarize(args.out)
    write_json(args.out/'FILE_MANIFEST.json',dict(schema='uncertainty_followup_analysis_v1',
        files=[dict(path=p.relative_to(args.out).as_posix(),bytes=p.stat().st_size,
                    columns=list(pd.read_csv(p,nrows=0).columns) if p.name.endswith(('.csv','.csv.gz')) else None)
               for p in sorted(args.out.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.json'],
        published=False,original_annotations_modified=False))
