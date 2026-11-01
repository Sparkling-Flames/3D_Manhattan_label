#!/usr/bin/env python3
"""Normalize the adopted screen439 natural paths without refusion or reweighting.

All 256 saved permutations retain their frequency, replicate identity and strata.
Zero-capacity pools remain in POOL_INDEX. Geometry and score components are left
missing until an exact endpoint join supplies them. The complete_output column
means complete *and evaluable*, matching the source complete_evaluable flag;
it is not a statement that every False is a geometrical fusion failure.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

COMMIT = "e1873bfadc1d0e61499809c91fba9dc39c717f83"
REPO = "Sparkling-Flames/3D_Manhattan_label"
SCREEN = "research/data/doorway_review_20261030/screen439_results_20261031"
BASE = "research/data/doorway_review_20261030"
PRO = "research/fusion/doorway_population_v21_20261031/HOHONET_doorway_v21_20261031"
DOMAIN = {
    "overall_before": "doorway_before",
    "overall_after": "doorway_after",
    "space1": "doorway_space1",
    "space2": "doorway_space2",
    "whole_compatible": "doorway_whole",
}
GEOM_COLUMNS = [
    "geometry_formed", "nodes", "turns", "short_turn_edges", "floor_area_h2",
    "height_mean_h", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pipe(s: str) -> list[str]:
    return str(s).split("|") if pd.notna(s) and str(s) else []


def exact_team(image: str, member_ids: list[str]) -> str:
    key = image + "\n" + "\n".join(sorted(member_ids))
    return image + "__membersha256_" + hashlib.sha256(key.encode()).hexdigest()[:24]


def atomic_gzip_csv(frame: pd.DataFrame, dest: Path) -> None:
    """Write a complete gzip member, then validate it before publishing the file."""
    raw = frame.to_csv(index=False).encode("utf-8")
    encoded = gzip.compress(raw, compresslevel=6, mtime=0)
    temp = dest.with_name(dest.name + ".writing")
    temp.write_bytes(encoded)
    reread = temp.read_bytes()
    assert reread == encoded
    assert gzip.decompress(reread) == raw
    temp.replace(dest)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--repair-only", nargs="*", default=None,
                   help="Only rewrite named pool IDs; endpoint index is always rebuilt.")
    args = p.parse_args()
    root = args.root.resolve()
    repo = root / "source/repo"
    out = root / "stage02_normalized/doorway"
    out.mkdir(parents=True, exist_ok=True)
    src = repo / SCREEN
    files = {
        "path_values": src / "PAIRED_PATH_VALUES.csv.gz",
        "orders": src / "BASE_256_ORDERS.csv.gz",
        "pools": src / "POOLS.json",
        "records": repo / PRO / "stage04_computation/design/FROZEN_RECORDS.json.gz",
        "references": repo / PRO / "stage04_computation/recovered_reference_scores/FINAL_REFERENCES.json",
        "endpoint_index": repo / PRO / "stage04_computation/PHYSICAL_ENDPOINT_INDEX.csv.gz",
    }
    pools = json.loads(files["pools"].read_text())
    pool_by_id = {p["pool_id"]: p for p in pools}
    with gzip.open(files["records"], "rt") as f:
        records = json.load(f)
    refs = json.loads(files["references"].read_text())
    refs = {(r["image"], r["target"]): r for r in refs}
    paths = pd.read_csv(files["path_values"])
    orders = pd.read_csv(files["orders"])
    endpoint_index = pd.read_csv(files["endpoint_index"])
    assert not endpoint_index.physical_team_key.duplicated().any()
    endpoint_index = endpoint_index.set_index("physical_team_key")
    assert len(pools) == len(pool_by_id) == 85
    assert set(paths.pool_id) == {p["pool_id"] for p in pools if p["n"] > 0}
    assert not paths.duplicated(["pool_id", "base_replicate", "k"]).any()
    assert not orders.duplicated(["image", "base_replicate"]).any()
    assert all(set(g.base_replicate) == set(range(256)) for _, g in orders.groupby("image"))
    order_lookup = {
        (r.image, int(r.base_replicate)): pipe(r.base_member_object_ids)
        for r in orders.itertuples(index=False)
    }
    stratum_lookup = {
        (r.image, int(r.base_replicate)): r.origin_stratum
        for r in orders.itertuples(index=False)
    }
    # Resolve each saved endpoint source without changing physical identity.
    source_rows = []
    lookup = {}
    paths["_canonical_members"] = paths.member_object_ids.map(lambda s: "|".join(sorted(pipe(s))))
    source_groups = paths.groupby("physical_team_key", sort=False)
    assert source_groups[["image", "_canonical_members", "k"]].nunique().eq(1).all().all()
    source_counts = source_groups.agg(path_rows=("k", "size"), pool_count=("pool_id", "nunique"),
                                      target_count=("target", "nunique")).to_dict(orient="index")
    for row in paths.drop_duplicates("physical_team_key").itertuples(index=False):
        key = row.physical_team_key
        member_ids = sorted(pipe(row.member_object_ids))
        identity = exact_team(row.image, member_ids)
        normalized_key = key.replace("\\", "/")
        if ".jsonl:" in normalized_key:
            rel, line = normalized_key.rsplit(":", 1)
            source_path = BASE + "/" + rel
            source_line = int(line)
            source_kind = "native_jsonl_line"
        elif key in endpoint_index.index:
            er = endpoint_index.loc[key]
            assert er.image == row.image and int(er.k) == int(row.k)
            assert set(pipe(er.member_object_ids)) == set(member_ids)
            source_path = PRO + "/" + str(er.endpoint_file).replace("\\", "/")
            source_line = None
            source_kind = "pro_shard_key"
        elif int(row.k) == 1 and "::" in key:
            assert key.split("::", 1) == [row.image, member_ids[0]]
            source_path = PRO + "/stage04_computation/design/FROZEN_RECORDS.json.gz"
            source_line = None
            source_kind = "single_original_added_target"
        else:
            raise ValueError(f"Unresolved endpoint source: {key}")
        workers = [records[m]["worker"] for m in member_ids]
        assert len(workers) == len(set(workers)) == int(row.k)
        assert not (set(workers) & {"W019", "W026"})
        info = {
            "team_key": identity,
            "endpoint_source_key": key,
            "endpoint_source_path": source_path,
            "endpoint_source_line": source_line,
            "endpoint_source_kind": source_kind,
            "member_workers": "|".join(workers),
        }
        lookup[key] = info
        source_rows.append({
            **info, "image": row.image, "k": int(row.k),
            "member_object_ids": "|".join(member_ids),
            **source_counts[key],
        })
    paths = paths.drop(columns="_canonical_members")
    source_maps = {c: {key: value[c] for key, value in lookup.items()} for c in [
        "team_key", "endpoint_source_key", "endpoint_source_path", "endpoint_source_line",
        "endpoint_source_kind"]}
    workers_by_serialized_members = {
        s: "|".join(records[m]["worker"] for m in pipe(s)) for s in paths.member_object_ids.unique()
    }
    endpoint_sources = pd.DataFrame(source_rows)
    atomic_gzip_csv(endpoint_sources, out / "ENDPOINT_SOURCES.csv.gz")

    index_rows = []
    pool_checks = []
    expected_strata = {"old24": 24, "balanced_new24": 24,
                       "extension_stage1_104": 104, "extension_stage2_104": 104}
    for pool in pools:
        pid = pool["pool_id"]
        n = int(pool["n"])
        d = paths[paths.pool_id == pid].copy()
        ref = refs[(pool["image"], pool["target"])]
        assert ref["B8L2_available_from_reference"] and ref["D10_available_from_reference"]
        assert ref["IoU3D100_available_from_reference"]
        assert len(set(pool["records"])) == len(set(pool["workers"])) == n
        assert {records[m]["worker"] for m in pool["records"]} == set(pool["workers"])
        expected_rows = n * 256
        assert len(d) == expected_rows, (pid, len(d), expected_rows)
        entries = {}
        if n:
            assert d.pool_n.eq(n).all() and d.image.eq(pool["image"]).all()
            assert d.family.eq(pool["family"]).all() and d.target.eq(pool["target"]).all()
            assert set(d.k) == set(range(1, n + 1))
            assert d.groupby("k").size().eq(256).all()
            assert d.groupby("base_replicate").size().eq(n).all()
            for rid, gd in d.groupby("base_replicate"):
                ordered = [m for m in order_lookup[(pool["image"], int(rid))]
                           if m in set(pool["records"])]
                assert len(ordered) == n and set(ordered) == set(pool["records"])
                assert gd.origin_stratum.eq(stratum_lookup[(pool["image"], int(rid))]).all()
                for row in gd.itertuples(index=False):
                    assert set(pipe(row.member_object_ids)) == set(ordered[:int(row.k)])
                    assert len(pipe(row.member_object_ids)) == int(row.k)
                    entries[(int(rid), int(row.k))] = ordered[int(row.k) - 1]
            strata = d[d.k == 1].origin_stratum.value_counts().to_dict()
            assert strata == expected_strata, (pid, strata)
        else:
            strata = {}
        d = d.rename(columns={"pool_n": "N", "base_replicate": "replicate_id"})
        d["condition"] = "manual"
        d["domain"] = DOMAIN[pool["family"]]
        d["target_id"] = ref["target_id"]
        d["reference_id"] = ref["target_id"]
        d["reference_version"] = "doorway_final_full_reference_20261031"
        d["parent_reference_id"] = ref["parent_reference_id"]
        d["parent_reference_version"] = ref["parent_reference_version"]
        d["screening_version"] = "screen439_final_20261031"
        d["k_fraction"] = d.k / n if n else np.nan
        for c, mapper in source_maps.items():
            d[c] = d.physical_team_key.map(mapper)
        d["member_workers"] = d.member_object_ids.map(workers_by_serialized_members)
        d["entry_object_id"] = [entries[(int(r), int(k))]
                                 for r, k in zip(d.replicate_id, d.k)]
        d["entry_worker"] = d.entry_object_id.map({m: r["worker"] for m, r in records.items()})
        d["quality_valid"] = np.isfinite(d[["B8L2", "D10", "IoU3D100"]]).all(axis=1)
        d["B8L2_valid"] = np.isfinite(d.B8L2)
        d["D10_valid"] = np.isfinite(d.D10)
        d["IoU3D100_valid"] = np.isfinite(d.IoU3D100)
        d["complete_output"] = d.complete_evaluable
        d["stage"] = np.select([d.k.eq(1), d.k.eq(2)],
                                ["raw_original", "two_person_supplement"], default="fusion_main")
        d["primary_analysis"] = d.k.ge(3)
        d["n2_heterogeneous_source_convention"] = d.k.eq(2)
        d["status_class"] = np.where(d.complete_evaluable,
                                      "complete_evaluable",
                                      "incomplete_or_unscoreable_pending_geometry")
        d.loc[d.k.eq(1), "status_class"] = np.where(
            d.loc[d.k.eq(1), "quality_valid"], "raw_original_scoreable", "raw_original_unscoreable")
        d.loc[d.k.eq(2), "status_class"] = np.where(
            d.loc[d.k.eq(2), "complete_evaluable"],
            "two_person_complete_evaluable_legacy_supplement",
            "two_person_unscoreable_supplement_convention_or_geometry")
        for c in GEOM_COLUMNS:
            d[c] = np.nan
        d["geometry_component_join_status"] = "not_yet_joined_exact_endpoint"
        d = d.sort_values(["replicate_id", "k"])
        dest = out / (pid + ".csv.gz")
        if args.repair_only is None or pid in args.repair_only:
            atomic_gzip_csv(d, dest)
        index_rows.append({
            "pool_id": pid, "image": pool["image"], "building": pool["building"],
            "condition": "manual", "domain": DOMAIN[pool["family"]],
            "family": pool["family"], "target": pool["target"],
            "target_id": ref["target_id"], "reference_id": ref["target_id"],
            "reference_version": "doorway_final_full_reference_20261031",
            "parent_reference_id": ref["parent_reference_id"],
            "parent_reference_version": ref["parent_reference_version"],
            "screening_version": "screen439_final_20261031",
            "N": n, "row_count": len(d), "replicates": 256 if n else 0,
            "first_main_k": 3 if n >= 3 else None, "last_k": n,
            "path": str(dest.relative_to(root)), "absolute_path": str(dest),
            "capacity_status": "available" if n else "no_capacity",
            "source_commit": COMMIT,
        })
        pool_checks.append({
            "pool_id": pid, "N": n, "rows": len(d), "expected_rows": expected_rows,
            "all_k_256": True if n else None,
            "exact_saved_permutation_prefix": True if n else None,
            "full_pool_unique_teams": d[d.k.eq(n)].team_key.nunique() if n else 0,
            "distinct_physical_endpoints": d.team_key.nunique(),
            "finite_B8L2": int(d.B8L2_valid.sum()),
            "source_complete_evaluable": int(d.complete_evaluable.sum()),
            "geometry_not_joined_rows": len(d), "strata": strata,
        })
    pd.DataFrame(index_rows).to_csv(out / "POOL_INDEX.csv", index=False)
    pd.DataFrame(pool_checks).drop(columns="strata").to_csv(out / "POOL_VALIDATION.csv", index=False)

    # Useful compact download plan, with source usage preserved. Metadata absent
    # from GitHub tree stays null rather than an inferred size.
    metadata = {}
    for name in ["REMOTE_FILES.json", "LEGACY_CORE_REMOTE_FILES.json", "LEGACY_DELTA_REMOTE_FILES.json"]:
        f = root / "stage00_doorway_sources" / name
        if f.exists():
            metadata.update({x["path"]: x for x in json.loads(f.read_text()) if x.get("type") == "file"})
    tree = repo / "__metadata__/TREE.json"
    if tree.exists():
        payload = json.loads(tree.read_text())
        items = payload.get("tree", payload) if isinstance(payload, dict) else payload
        for item in items:
            if item.get("type") == "blob":
                metadata[item["path"]] = {"size": item.get("size"), "git_blob_sha": item.get("sha")}
    source_files = []
    for source_path, ds in endpoint_sources.groupby("endpoint_source_path"):
        meta = metadata.get(source_path, {})
        source_files.append({
            "path": source_path, "size": meta.get("size"),
            "git_blob_sha": meta.get("git_blob_sha"),
            "url": f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{source_path}",
            "endpoint_keys": len(ds), "path_rows": int(ds.path_rows.sum()),
            "images": "|".join(sorted(ds.image.unique())),
            "source_kind": "|".join(sorted(ds.endpoint_source_kind.unique())),
            "priority": 1 if "screen439_results" in source_path else 2,
        })
    sf = pd.DataFrame(source_files).sort_values(["priority", "path_rows"], ascending=[True, False])
    sf.to_csv(out / "ENDPOINT_SOURCE_FILES.csv", index=False)
    plan = {"source_commit": COMMIT, "identity": "exact image+object_ids, never scope-quality selection",
            "source_key_rows": len(endpoint_sources), "path_rows": len(paths),
            "files": sf.replace({np.nan: None}).to_dict(orient="records")}
    (out / "ENDPOINT_SOURCE_DOWNLOAD_PLAN.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    validation = {
        "source_commit": COMMIT, "rows": len(paths), "pools": len(pools),
        "nonempty_pools": paths.pool_id.nunique(), "no_capacity_pools": sum(p["n"] == 0 for p in pools),
        "physical_source_keys": paths.physical_team_key.nunique(),
        "exact_member_teams": endpoint_sources.team_key.nunique(),
        "all_prefix_members_verified": True, "all_nonempty_pool_k_have_256_rows": True,
        "all_source_images_members_k_verified_for_pro_index": True,
        "all_workers_available_and_no_W019_W026": True,
        "all_51_final_references_quality_available": len(refs) == 51,
        "source_files": {key: {"path": str(value.relative_to(root)), "size": value.stat().st_size,
                               "sha256": sha256(value)} for key, value in files.items()},
        "pool_checks": pool_checks,
        "complete_output_definition": "source complete_evaluable: complete AND score-evaluable; False needs geometry join",
        "singletons": "raw original answers, not multi-person fusion",
        "n2_policy": "heterogeneous historical scoring convention, supplementary only",
        "new_fusion_runs": 0, "new_quality_runs": 0,
    }
    (out / "NORMALIZATION_VALIDATION.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2))
    print(json.dumps({k: validation[k] for k in ["rows", "pools", "nonempty_pools", "no_capacity_pools",
                                               "physical_source_keys", "exact_member_teams"]}))


if __name__ == "__main__":
    main()
