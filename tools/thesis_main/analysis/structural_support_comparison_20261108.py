"""Describe structural support in every frozen comparison team; no reference quality ranking."""
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import shape

from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse
from tools.thesis_main.analysis.fusion_common_panel_20261024 import medoid

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research/fusion/fusion_common_panel_20261024"
INPUT = ROOT / "research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz"
OUT = ROOT / "research/fusion/structural_support_comparison_20261108"


def support_rows(groups, n, medoid_id, output_ids):
    """Support labels describe current correspondence identities, not semantic correctness."""
    rows = []
    for g in groups:
        workers = [m["worker"] for m in g["members"]]
        assert len(set(workers)) == len(workers) == g["support"]
        support = len(workers)
        kind = "strict_majority" if 2 * support > n else "tie" if 2 * support == n else "minority"
        assert g["selected"] == (kind != "minority")
        rows.append(dict(
            feature_id=g["feature_id"], support=support, team_n=n,
            support_kind=kind, selected=g["selected"],
            in_medoid=any(m["id"] == medoid_id for m in g["members"]),
            in_complete_output=None if output_ids is None else g["feature_id"] in output_ids,
            workers="|".join(sorted(workers)),
            source_pairs=json.dumps([[m["id"], m["pair_index"]] for m in g["members"]]),
        ))
    return rows


def team_counts(nodes):
    out = {}
    for kind in ("strict_majority", "tie", "minority"):
        subset = [r for r in nodes if r["support_kind"] == kind]
        out[kind + "_identities"] = len(subset)
        out[kind + "_in_medoid"] = sum(r["in_medoid"] for r in subset)
    out["misses_strict_majority"] = out["strict_majority_in_medoid"] < out["strict_majority_identities"]
    out["includes_minority"] = out["minority_in_medoid"] > 0
    out["either_event"] = out["misses_strict_majority"] or out["includes_minority"]
    return out


def aggregate(rows):
    result = dict(teams=len(rows), images=len({r["image"] for r in rows}),
                  buildings=len({r["building"] for r in rows}))
    for flag in ("misses_strict_majority", "includes_minority", "either_event", "full_evaluable", "full_output"):
        selected = [r for r in rows if r[flag]]
        result[flag + "_teams"] = len(selected)
        result[flag + "_percent"] = 100 * len(selected) / len(rows) if rows else None
        result[flag + "_images"] = len({r["image"] for r in selected})
    for kind in ("strict_majority", "tie", "minority"):
        for suffix in ("identities", "in_medoid"):
            key = kind + "_" + suffix
            result[key] = sum(r[key] for r in rows)
    result["strict_majority_missed"] = result["strict_majority_identities"] - result["strict_majority_in_medoid"]
    return result


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    with (SOURCE / "METHOD_ENDPOINTS.csv").open(encoding="utf-8-sig", newline="") as f:
        methods = list(csv.DictReader(f))
    by_team = {}
    for row in methods:
        by_team.setdefault(row["team_key"], {})[row["method"]] = row
    with gzip.open(INPUT, "rt", encoding="utf-8") as f:
        pools = {p["pool_id"]: p for p in json.load(f)["images"]}
    geometries = {(g["team_key"], g["method"]): g for g in json.loads((SOURCE / "METHOD_GEOMETRY.json").read_text(encoding="utf-8"))}
    assert len(by_team) == 138 and len(methods) == 414
    teams, nodes, checks = [], [], []
    for index, (key, endpoints) in enumerate(by_team.items(), 1):
        wall, med = endpoints["wall_auto"], endpoints["medoid"]
        requested = set(wall["member_workers"].split("|"))
        records = [r for r in pools[wall["pool_id"]]["records"] if r["worker_id"] in requested]
        assert len(records) == int(wall["n"]) == len(requested)
        assert {r["object_id"] for r in records} == set(wall["member_object_ids"].split("|"))
        chosen, _, exclusions, _ = medoid(records)
        assert chosen is not None and chosen["object_id"] == med["source_record_id"]
        rebuilt = fuse(records, gap=7.5)["automatic"]
        expected = geometries[key, "wall_auto"]["points"]
        actual = rebuilt["candidate"].get("points")
        assert (actual is None) == (expected is None), key
        error = None
        if expected is not None:
            a, b = np.asarray(actual), np.asarray(expected)
            assert a.shape == b.shape
            error = float(np.max(np.abs(a - b)))
            assert error < 1e-8, (key, error)
        assert np.array_equal(chosen["points"], geometries[key, "medoid"]["points"])
        output_ids = None if actual is None else set(rebuilt["candidate"]["feature_ids"])
        node_rows = support_rows(rebuilt["identity_groups"], len(records), chosen["id"], output_ids)
        assert sum(r["in_medoid"] for r in node_rows) == len(chosen["points"]) // 2
        if output_ids is not None:
            assert all(r["selected"] == r["in_complete_output"] for r in node_rows)
        metadata = {k: wall[k] for k in ("team_key", "pool_id", "image", "building", "condition", "layer", "difficulty", "member_workers")}
        region = shape(geometries[key, "lee_mv50"]["footprint"])
        parts = list(region.geoms) if region.geom_type == "MultiPolygon" else [region]
        row = dict(**metadata, n=len(records), medoid_object=chosen["object_id"],
                   medoid_worker=chosen["worker_id"], medoid_corner_pairs=len(chosen["points"]) // 2,
                   selected_identities=sum(r["selected"] for r in node_rows),
                   full_output=wall["full_output"] == "True", full_evaluable=wall["full_evaluable"] == "True",
                   output_status=wall["output_status"], excluded_medoid_candidates=len(exclusions),
                   bev_components=len(parts), bev_holes=sum(len(p.interiors) for p in parts),
                   bev_boundary_vertices=sum(len(p.exterior.coords) - 1 + sum(len(h.coords)-1 for h in p.interiors) for p in parts),
                   **team_counts(node_rows))
        teams.append(row)
        nodes.extend(dict(**metadata, **r) for r in node_rows)
        checks.append(dict(team_key=key, coordinate_max_abs_error=error, geometry_available=actual is not None))
        if index % 24 == 0:
            print(f"checked {index}/138 teams", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "TEAM_SUPPORT.csv", teams)
    write_csv(OUT / "NODE_SUPPORT.csv", nodes)
    write_csv(OUT / "REPLAY_CHECKS.csv", checks)
    summary = {}
    for layer in sorted({r["layer"] for r in teams}):
        subset = [r for r in teams if r["layer"] == layer]
        summary[layer] = {"all": aggregate(subset)}
        for n in (4, 8, 16):
            summary[layer][str(n)] = aggregate([r for r in subset if r["n"] == n])
        summary[layer]["complete_scorable"] = aggregate([r for r in subset if r["full_evaluable"]])
        summary[layer]["by_difficulty"] = {d: aggregate([r for r in subset if r["difficulty"] == d]) for d in sorted({r["difficulty"] for r in subset})}
    payload = dict(source="frozen_v2_common_panel_20261024", teams=len(teams), nodes=len(nodes),
                   interpretation="Support is conditional on current correspondence; minority is not a semantic error label. Nested teams are not independent images.",
                   summary=summary)
    (OUT / "SUMMARY.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["ordinary_manual"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
