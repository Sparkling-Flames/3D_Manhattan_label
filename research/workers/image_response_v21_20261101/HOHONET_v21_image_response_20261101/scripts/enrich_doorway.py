#!/usr/bin/env python3
"""Join adopted doorway paths to exact frozen geometry and final target components.

No fusion or quality measurement is run. Shape summaries use the already frozen
v2 geometry_enrich/expression definitions; scalar quality is checked, not replaced.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))
from shapely.geometry import Polygon
from normalize_doorway import atomic_gzip_csv, PRO, SCREEN, COMMIT

PREFIX = "HOHONET_doorway_v21_20261031/"
COMPONENTS = ["iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "height_mean_ratio",
              "omission", "extension", "B8_floor_block", "B8_direction_block", "B8_height_block",
              "D10_direction_block", "boundary_loss", "direction_loss", "global_height_loss",
              "local_height_loss", "height_loss", "floor_WQ", "WQ_no_D", "WQ_no_B", "WQ_no_H"]
Q = ["B8L2", "D10", "IoU3D100"]
GEO_FIELDS = ["geometry_key", "geometry_available", "geometry_formed", "geometry_eligible", "floor_valid",
              "complete_floor_evaluable", "connection_available", "geometry_status", "native_status",
              "geometry_reason", "nodes", "minimum_support", "half_vote_nodes", "node_supports_json",
              "turns", "short_turn_edges", "redundant_turns", "short_edges_03_h", "floor_area_h2",
              "centroid_x_h", "centroid_z_h", "height_mean_h", "candidate_pair_count",
              "below_four", "fusion_error", "selected_nodes_available", "full_state_pointer",
              "full_state_retained", "geometry_component_source"]


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (ValueError, TypeError):
        return False


def compact(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def derive_shape(d, info):
    g = d.get("geometry") or {}
    points = g.get("points")
    floor = g.get("footprint")
    nodes = d.get("nodes")
    status = d.get("geometry_status", g.get("geometry_status"))
    connection = d.get("connection_available", points is not None and len(points) > 0)
    selected = d.get("selected_nodes")
    support = d.get("node_supports")
    formed = bool(status == "ok" and points and len(points) >= 8)
    r = {"team_key": info.team_key, "image": info.image, "k": int(info.k),
         "member_object_ids": info.member_object_ids, "member_workers": info.member_workers,
         "endpoint_source_key": info.endpoint_source_key,
         "endpoint_source_path": info.endpoint_source_path,
         "endpoint_source_line": None if pd.isna(info.endpoint_source_line) else int(info.endpoint_source_line),
         "endpoint_source_kind": info.endpoint_source_kind,
         "footprint_json": compact(floor) if floor is not None else None,
         "points_json": compact(points) if points is not None else None,
         "geometry_available": bool(g), "geometry_formed": formed,
         "geometry_status": status, "native_status": g.get("status"),
         "geometry_reason": d.get("geometry_reason", g.get("reason")),
         "nodes": nodes, "minimum_support": d.get("minimum_support"),
         "below_four": (int(nodes) < 4) if finite(nodes) else None,
         "connection_available": bool(connection),
         "node_supports_json": compact(support) if support is not None else None,
         "half_vote_nodes": sum(float(s) == int(info.k) / 2 for s in support)
                            if support is not None and int(info.k) % 2 == 0 else 0,
         "fusion_error": d.get("fusion_error"),
         "selected_nodes_available": selected is not None,
         "full_state_pointer": d.get("full_state_pointer"),
         "full_state_retained": d.get("full_state_retained"),
         "geometry_component_source": "exact_saved_geometry_frozen_v2_descriptors",
         "floor_valid": False, "geometry_eligible": False, "complete_floor_evaluable": False,
         "candidate_pair_count": len(points) // 2 if points is not None else None}
    for c in ["turns", "short_turn_edges", "redundant_turns", "short_edges_03_h", "floor_area_h2",
              "centroid_x_h", "centroid_z_h", "height_mean_h"]:
        r[c] = None
    # run_prefix_endpoints.py geometry_enrich: normalized camera height, unchanged.
    if points is not None:
        pp = np.asarray(points, dtype=float)
        if pp.ndim == 2 and pp.shape[1] == 2 and len(pp) > 0 and len(pp) % 2 == 0:
            with np.errstate(divide="ignore", invalid="ignore"):
                radius = 1 / np.tan(np.pi * (pp[1::2, 1] / 512 - .5))
                heights = 1 + radius * np.tan(np.pi * (.5 - pp[::2, 1] / 512))
            if np.isfinite(heights).all():
                r["height_mean_h"] = float(heights.mean())
    if floor is not None:
        a = np.asarray(floor, dtype=float)
        if a.ndim == 2 and a.shape[1] == 2 and len(a) >= 3 and np.isfinite(a).all():
            poly = Polygon(a)
            r["floor_valid"] = bool(poly.is_valid and poly.area > 0 and math.isfinite(poly.area))
            if r["floor_valid"]:
                r.update(floor_area_h2=float(poly.area), centroid_x_h=float(poly.centroid.x),
                         centroid_z_h=float(poly.centroid.y))
            # derive_frozen_expression.py: <=5 deg redundancy; short perimeter
            # edge <4% with >=15 deg turns at both ends. This is not <0.3 h.
            e = np.roll(a, -1, axis=0) - a
            lengths = np.linalg.norm(e, axis=1)
            if np.all(lengths >= 1e-10):
                angles = np.degrees(np.arccos(np.clip(
                    np.sum(np.roll(e, 1, axis=0) * e, axis=1) /
                    (np.roll(lengths, 1) * lengths), -1, 1)))
                r.update(turns=int((angles > 5).sum()), redundant_turns=int((angles <= 5).sum()),
                         short_turn_edges=int(((lengths / lengths.sum() < .04) & (angles >= 15) &
                                               (np.roll(angles, -1) >= 15)).sum()),
                         short_edges_03_h=int((lengths < .3).sum()))
    default_complete_floor = bool(r["floor_valid"] and connection and finite(nodes) and nodes >= 4)
    r["complete_floor_evaluable"] = bool(d.get("complete_floor_evaluable", default_complete_floor))
    r["geometry_eligible"] = bool(r["floor_valid"] and r["complete_floor_evaluable"])
    state_signature = compact({"footprint": floor, "points": points, "nodes": nodes,
                               "status": status, "complete_floor": r["complete_floor_evaluable"]})
    r["geometry_key"] = info.team_key + "__geometry_" + hashlib.sha256(state_signature.encode()).hexdigest()[:12]
    # Preserve supplied descriptors and verify compatible reconstructions.
    differences = {}
    for old, new in [("fusion_turn_n", "turns"), ("fusion_short_turn_edges", "short_turn_edges"),
                     ("fusion_redundancy_n", "redundant_turns"), ("floor_area_h2", "floor_area_h2"),
                     ("centroid_x_h", "centroid_x_h"), ("centroid_z_h", "centroid_z_h"),
                     ("height_mean_h", "height_mean_h")]:
        if finite(d.get(old)):
            if finite(r.get(new)):
                differences[new] = abs(float(d[old]) - float(r[new]))
            r[new] = d[old]
    return r, differences


def score_blocks(row):
    v = [row.get(c) for c in ["iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter"]]
    if all(finite(x) for x in v):
        I, S, D, Hm, Hc = map(float, v)
        # Frozen working_models.py terms: these are losses, not causal weights.
        if I > 0:
            row.setdefault("B8_floor_block", 1 / I - 1 + S * S / 32)
        row.setdefault("B8_direction_block", 1.5 * D * D / (D * D + 64))
        row.setdefault("D10_direction_block", 1.5 * D * D / (D * D + 100))
        row.setdefault("B8_height_block", (Hm / .8) ** 2 + (Hc / .25) ** 2)
    return row


def bool_or_none(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return x is True or x == 1 or str(x).lower() == "true"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args()
    root = args.root.resolve()
    src = root / "stage02_normalized/doorway"
    out = root / "stage02_normalized/doorway_enriched"
    (out / "geometry").mkdir(parents=True, exist_ok=True)
    sources = pd.read_csv(src / "ENDPOINT_SOURCES.csv.gz")
    pool_index = pd.read_csv(src / "POOL_INDEX.csv")
    source_map = {r.endpoint_source_key: r for r in sources.itertuples(index=False)}
    zpath = root / "source/cache/DOORWAY_04_PHYSICAL_GEOMETRY.zip"
    archive = zipfile.ZipFile(zpath)
    final_name = PREFIX + "stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz"
    component_cols = ["physical_team_key", "target", "score_status", "complete_evaluable",
                      "reference_status", "reference_full_available", "reference_evaluation_version",
                      "endpoint_state", "actual_consensus_failure", "output_generated_unscorable"] + Q + COMPONENTS
    with archive.open(final_name) as f:
        legacy = pd.read_csv(f, compression="gzip", usecols=component_cols, low_memory=False)
    assert not legacy.duplicated(["physical_team_key", "target"]).any()
    legacy = legacy[legacy.physical_team_key.isin(source_map)].copy()
    legacy["component_source"] = "Pro_final_ENDPOINT_TARGET_SCORES_with_reference_recovery"
    legacy = legacy.rename(columns={"physical_team_key": "endpoint_source_key"})
    added = json.loads((root / "source/repo" / SCREEN / "ADDED_SINGLE_TARGET_SCORES.json").read_text())
    geometry_index = []
    enriched_index = []
    receipts = []
    duplicate_checks = []
    descriptor_max_diff = {}
    max_quality_diff = {q: 0.0 for q in Q}
    for image, si in sources.groupby("image", sort=True):
        print("start_image", image, "sources", len(si), flush=True)
        geom_by_source = {}
        target_rows = []
        for source_path, group in si.groupby("endpoint_source_path", sort=True):
            kind = group.endpoint_source_kind.iloc[0]
            if kind == "single_original_added_target":
                continue
            wanted = set(group.endpoint_source_key)
            if kind == "pro_shard_key":
                member = PREFIX + source_path[len(PRO) + 1:]
                with archive.open(member) as raw:
                    with gzip.open(raw, "rt") as lines:
                        for line in lines:
                            d = json.loads(line)
                            key = d["physical_team_key"]
                            if key not in wanted:
                                continue
                            info = source_map[key]
                            assert d["image"] == info.image and int(d["k"]) == int(info.k)
                            assert set(d["member_object_ids"]) == set(info.member_object_ids.split("|"))
                            geom, differences = derive_shape(d, info)
                            geom_by_source[key] = geom
                            for c, value in differences.items():
                                descriptor_max_diff[c] = max(descriptor_max_diff.get(c, 0.0), value)
            else:
                lines_needed = {int(r.endpoint_source_line): r for r in group.itertuples(index=False)}
                with (root / "source/repo" / source_path).open() as f:
                    for line_no, line in enumerate(f, 1):
                        if line_no not in lines_needed:
                            continue
                        info = lines_needed[line_no]
                        d = json.loads(line)
                        assert d["image"] == info.image and int(d["k"]) == int(info.k)
                        assert set(d["members"]) == set(info.member_object_ids.split("|"))
                        geom, differences = derive_shape(d, info)
                        geom_by_source[info.endpoint_source_key] = geom
                        for target, score in d["scores"].items():
                            row = score_blocks(dict(score))
                            row.update(endpoint_source_key=info.endpoint_source_key, target=target,
                                       component_source="current_exact_native_target_score")
                            target_rows.append(row)
        # Added target of an existing single-person answer uses the exact same
        # raw geometry already retained under a Pro physical key for this member.
        by_team = {d["team_key"]: d for d in geom_by_source.values()}
        for info in si[si.endpoint_source_kind.eq("single_original_added_target")].itertuples(index=False):
            assert info.team_key in by_team
            g = dict(by_team[info.team_key])
            g.update(endpoint_source_key=info.endpoint_source_key,
                     endpoint_source_path=info.endpoint_source_path,
                     endpoint_source_line=None, endpoint_source_kind=info.endpoint_source_kind,
                     geometry_component_source="exact_same_original_answer_geometry")
            geom_by_source[info.endpoint_source_key] = g
            for score in added:
                if score["image"] == image and score["object_id"] == info.member_object_ids:
                    row = dict(score)
                    row.update(endpoint_source_key=info.endpoint_source_key,
                               component_source="added_single_target_only_saved_Q_components_unretained")
                    target_rows.append(row)
        assert set(geom_by_source) == set(si.endpoint_source_key), image
        geom = pd.DataFrame(geom_by_source.values())
        # Target reuse may give more than one cache source for the same members.
        for team, g in geom[geom.team_key.duplicated(keep=False)].groupby("team_key"):
            first = g.iloc[0]
            for row in g.iloc[1:].itertuples(index=False):
                for c in ["footprint_json", "points_json"]:
                    a, b = first[c], getattr(row, c)
                    if pd.isna(a) or pd.isna(b):
                        equal = bool(pd.isna(a) and pd.isna(b))
                    else:
                        av, bv = np.asarray(json.loads(a)), np.asarray(json.loads(b))
                        equal = av.shape == bv.shape and np.allclose(av, bv, atol=1e-9, rtol=0)
                    duplicate_checks.append({"image": image, "team_key": team, "k": int(row.k), "field": c,
                                             "exact_geometry_within_tolerance": equal,
                                             "supplement_n2_convention_difference": not equal and int(row.k) == 2})
                    assert equal or int(row.k) == 2, (image, team, c)
        catalog = geom.drop_duplicates("geometry_key").copy()
        catalog["all_endpoint_source_keys"] = catalog.geometry_key.map(
            geom.groupby("geometry_key").endpoint_source_key.agg(lambda x: "|".join(x)))
        geom_file = out / "geometry" / (image + ".csv.gz")
        atomic_gzip_csv(catalog, geom_file)
        geometry_index.append({"image": image, "teams": catalog.team_key.nunique(), "geometry_states": len(catalog), "source_keys": len(geom),
                               "geometry_eligible": int(catalog.geometry_eligible.sum()),
                               "path": str(geom_file.relative_to(root)), "absolute_path": str(geom_file)})
        pd.DataFrame(geometry_index).to_csv(out / "GEOMETRY_CATALOG_INDEX.csv", index=False)
        print("geometry_ready", image, len(catalog), flush=True)
        scores = pd.concat([legacy[legacy.endpoint_source_key.isin(set(si.endpoint_source_key))],
                            pd.DataFrame(target_rows)], ignore_index=True)
        assert not scores.duplicated(["endpoint_source_key", "target"]).any()
        for c in COMPONENTS:
            if c not in scores:
                scores[c] = np.nan
        score_lookup = scores.set_index(["endpoint_source_key", "target"])
        geom_lookup = geom.set_index("endpoint_source_key")
        for pr in pool_index[pool_index.image.eq(image)].itertuples(index=False):
            d = pd.read_csv(root / pr.path)
            if len(d):
                keys = pd.MultiIndex.from_arrays([d.endpoint_source_key, d.target])
                sc = score_lookup.reindex(keys).reset_index(drop=True)
                assert sc.component_source.notna().all(), pr.pool_id
                for q in Q:
                    assert d[q].isna().reset_index(drop=True).equals(sc[q].isna()), (pr.pool_id, q, "finite mask")
                    err = np.nanmax(np.abs(d[q].to_numpy() - sc[q].to_numpy())) if d[q].notna().any() else 0.0
                    max_quality_diff[q] = max(max_quality_diff[q], float(err))
                    assert err < 1e-7, (pr.pool_id, q, err)
                assert d.complete_evaluable.eq(sc.complete_evaluable).all(), (pr.pool_id, "source state")
                for c in COMPONENTS + ["component_source", "score_status", "reference_status",
                                       "reference_full_available", "reference_evaluation_version"]:
                    d[c] = sc[c].to_numpy() if c in sc else np.nan
                ge = geom_lookup.reindex(d.endpoint_source_key).reset_index(drop=True)
                for c in GEO_FIELDS:
                    d[c] = ge[c].to_numpy()
                d["geometry_component_join_status"] = "exact_identity_join_validated_against_current_Q"
                fail = d.k.ge(3) & ~d.complete_evaluable
                d["actual_consensus_failure"] = False
                d["output_generated_unscoreable"] = False
                d.loc[fail & d.below_four.eq(True), "status_class"] = "below_four_selected_nodes"
                d.loc[fail & ~d.below_four.eq(True) & ~d.connection_available.eq(True), "status_class"] = "no_connection"
                d.loc[fail & d.geometry_formed.eq(True), "status_class"] = "output_generated_unscoreable"
                d.loc[fail & ~d.geometry_formed.eq(True) & d.connection_available.eq(True) &
                      ~d.below_four.eq(True), "status_class"] = "invalid_or_incomplete_geometry"
                d.loc[fail & d.fusion_error.notna(), "status_class"] = "fusion_error"
                d.loc[fail & d.status_class.isin(["below_four_selected_nodes", "no_connection", "fusion_error"]),
                      "actual_consensus_failure"] = True
                d.loc[fail & d.status_class.isin(["output_generated_unscoreable", "invalid_or_incomplete_geometry"]),
                      "output_generated_unscoreable"] = True
                # Explicit final Pro classification wins when supplied.
                for field in ["actual_consensus_failure", "output_generated_unscorable"]:
                    if field in sc:
                        supplied = sc[field].map(bool_or_none)
                        use = supplied.notna() & d.k.ge(3)
                        target = "output_generated_unscoreable" if field.endswith("unscorable") else field
                        d.loc[use, target] = supplied[use].astype(bool).to_numpy()
            dest = out / (pr.pool_id + ".csv.gz")
            atomic_gzip_csv(d, dest)
            ind = pr._asdict()
            ind.update(path=str(dest.relative_to(root)), absolute_path=str(dest),
                       enrichment="exact_frozen_geometry_and_final_components")
            enriched_index.append(ind)
            receipts.append({"pool_id": pr.pool_id, "rows": len(d),
                             "geometry_eligible_rows": int(d.geometry_eligible.sum()) if len(d) else 0,
                             "finite_components": int(d["S_bottom_deg"].notna().sum()) if len(d) else 0,
                             "quality_status_unchanged": True})
        del geom, geom_by_source, catalog, scores
    pd.DataFrame(enriched_index).to_csv(out / "POOL_INDEX.csv", index=False)
    pd.DataFrame(receipts).to_csv(out / "ENRICHMENT_BY_POOL.csv", index=False)
    pd.DataFrame(duplicate_checks).to_csv(out / "DUPLICATE_SOURCE_GEOMETRY_CHECKS.csv", index=False)
    integrity = []
    for f in sorted(out.rglob("*.csv.gz")):
        with gzip.open(f, "rb") as stream:
            size = sum(len(b) for b in iter(lambda: stream.read(1 << 20), b""))
        integrity.append({"path": str(f.relative_to(root)), "bytes": f.stat().st_size,
                          "uncompressed_bytes": size, "full_gzip_read": "passed"})
    receipt = {"source_commit": COMMIT, "source_archive": str(zpath.relative_to(root)),
               "current_scalar_version": "screen439_final_20261031", "pools": len(enriched_index),
               "path_rows": sum(x["rows"] for x in receipts),
               "geometry_teams": sum(x["teams"] for x in geometry_index),
               "geometry_states": sum(x["geometry_states"] for x in geometry_index),
               "geometry_source_keys": sum(x["source_keys"] for x in geometry_index),
               "quality_maximum_absolute_difference": max_quality_diff,
               "preserved_descriptor_reconstruction_max_abs_diff": descriptor_max_diff,
               "duplicate_geometry_comparisons": len(duplicate_checks),
               "new_fusion_runs": 0, "new_quality_measurement_runs": 0,
               "new_computations": "geometry descriptors on cached outputs; algebraic frozen Q loss blocks only",
               "geometry_denominator": "valid polygon and complete_floor_evaluable, independent of target Q",
               "readability": integrity}
    (out / "ENRICHMENT_VALIDATION.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in receipt.items() if k != "readability"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
