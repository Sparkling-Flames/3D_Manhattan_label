"""Targeted manual-order sensitivity for existing same-room experiments.

No team selection, classification fitting or fusion is performed here.  Endpoint
updates are joined by team/reference/version.  Original results remain intact.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
REL = ROOT / "research/data/releases/v2.1"
UP = REL / "admitted_space_extension/image_difficulty_20261030"
BASE = ROOT / "research/fusion/manual_order_impact_20261104"
OUT = BASE / "same_room"
SOURCE = ROOT / "research/fusion/missing_ring_review_20261104/user_order_return"
SCALARS = REL / "same_room_current_results/large/native/ENDPOINT_SCALARS.csv.gz"
ARCHIVE = ROOT / "research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage02_same_room/EXISTING_VALID_EVENT_SOURCE.csv.gz"
FULL_REGISTERED_SOURCE=REL/"same_room_current_results/large/results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz"
GROUP = ["method_updated", "n", "m", "updated_direction"]
PAIR = ["method_updated", "building", "pair_key", "n", "m", "updated_direction"]
ROLES = ("A", "B", "C")
SIDES = ("a", "b")
METRICS = [
    "B8L2", "D10", "IoU3D100", "S_bottom_deg", "dir", "Hmean",
    "omission", "extension", "fusion_turn_n", "fusion_short_turn_edges",
    "fusion_redundancy_n", "geometry_area_h2", "height_mean_h",
    "boundary_loss", "direction_loss", "height_loss",
    "ref_node_recall_5", "ref_edge_recall_5",
    "nodes", "Hcenter", "height_mean_ratio", "iou_2d", "diag_corner_recall_05",
    "diag_wall_coverage_05", "top_y_mean_px", "bottom_y_mean_px", "centroid_x_h",
    "centroid_z_h", "reference_node_shortfall", "identity_groups_n", "minimum_support",
    "recorded_time_total_seconds",
]


def read_csv(path, **kwargs):
    return pd.read_csv(path, low_memory=False, **kwargs)


def save(frame, name):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    if path.suffix == ".gz":
        payload = gzip.compress(payload, mtime=0)
    path.write_bytes(payload)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def write_json(name, value):
    (OUT / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def boolean(series):
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "1.0"])


def text_key(value):
    return "" if pd.isna(value) else str(value)


def team_column(frame, role, side):
    choices = [f"team_key_{role}_{side}", f"team_{role}_{side}", f"{role}_{side}_team_key", f"team_key_{side}_{role}"]
    present = [c for c in choices if c in frame]
    if not present:
        raise ValueError(f"Missing explicit team identity: {role}/{side}")
    for c in present[1:]:
        assert frame[c].equals(frame[present[0]]), (role, side, present)
    return present[0]


def all_team_columns(frame):
    return [team_column(frame, r, v) for v in SIDES for r in ROLES]


def assert_numeric_equal(a, b, name, tolerance=1e-7):
    aa = np.asarray(pd.to_numeric(a, errors="coerce"), dtype=float)
    bb = np.asarray(pd.to_numeric(b, errors="coerce"), dtype=float)
    assert np.array_equal(np.isfinite(aa), np.isfinite(bb)), (name, "finite support mismatch", int(np.sum(np.isfinite(aa) != np.isfinite(bb))))
    finite = np.isfinite(aa)
    error = float(np.max(np.abs(aa[finite] - bb[finite]))) if finite.any() else 0.0
    assert error <= tolerance, (name, error)
    return error


def merge_manual_endpoints(original, updates):
    """Use the authoritative original endpoint reference, never image matching."""
    assert original.team_key.is_unique
    identity = ["team_key", "reference_id", "reference_version"]
    assert not updates.duplicated(identity).any()
    source = original.set_index("team_key", drop=False)
    target = source.copy()
    ledger = []
    for _, row in updates.iterrows():
        key = row.team_key
        if key not in source.index:
            continue
        old = source.loc[key]
        for field in identity[1:]:
            assert text_key(old[field]) == text_key(row[field]), (key, field, old[field], row[field])
        for field in ["nodes", "minimum_support", "k", "pool_id", "building", "condition"]:
            if field in old and field in row and pd.notna(old[field]) and pd.notna(row[field]):
                assert old[field] == row[field], (key, field, old[field], row[field])
        if "automatic_B8L2" in row:
            assert_numeric_equal(pd.Series([old.B8L2]), pd.Series([row.automatic_B8L2]), key + ":automatic_B8L2")
        changed = []
        allowed = (set(METRICS) - {"recorded_time_total_seconds", "identity_groups_n", "minimum_support", "nodes"}) | {"complete_evaluable", "score_status", "geometry_status", "score_available", "connection_available", "below_four", "candidate_status", "output_status", "floor_evaluable", "complete_floor_evaluable", "location_unresolved", "order_status", "order_tied", "geometry_reason"}
        for column in allowed & set(updates.columns):
            if column not in target:
                target[column] = np.nan
            target.at[key, column] = row[column]
            changed.append(column)
        ledger.append({"team_key": key, "reference_id": old.reference_id, "reference_version": old.reference_version,
                       "automatic_B8L2": old.B8L2, "assisted_B8L2": row.B8L2,
                       "automatic_score_status": old.score_status, "assisted_score_status": row.score_status,
                       "columns_applied": "|".join(sorted(changed)), "reference_binding": "team_and_reference_and_version_exact"})
    return target.reset_index(drop=True), pd.DataFrame(ledger)


def endpoint_values(events, endpoints, metric):
    index = endpoints.set_index("team_key")
    arrays = {}
    for side in SIDES:
        values = []
        for role in ROLES:
            key = events[team_column(events, role, side)]
            assert key.isin(index.index).all(), (metric, role, side, list(key[~key.isin(index.index)].head()))
            got = index.loc[key]
            for field in ["reference_id", "reference_version", "pool_id"]:
                expected = f"{field}_{side}"
                if expected in events and field in got:
                    valid = events[expected].notna().to_numpy()
                    assert (got[field].fillna("").astype(str).to_numpy()[valid] == events[expected].fillna("").astype(str).to_numpy()[valid]).all(), (field, role, side)
            values.append(pd.to_numeric(got[metric], errors="coerce").to_numpy(float))
        arrays[side] = np.column_stack(values)
    return arrays


def derive_events(events, endpoints):
    result = events.copy()
    for metric in METRICS:
        if metric not in endpoints:
            continue
        values = endpoint_values(result, endpoints, metric)
        finite6 = np.isfinite(np.column_stack([values[s] for s in SIDES])).all(axis=1)
        result[metric + "_common6"] = finite6
        for side, matrix in values.items():
            a, b, c = matrix.T
            if metric == "B8L2":
                for role, scores in zip(ROLES, matrix.T):
                    result[f"Q_{role}_{side}"] = scores
            for contrast, delta in [("BA", b-a), ("CA", c-a), ("CB", c-b)]:
                result[f"{metric}_{side}_{contrast}"] = delta
            for label, delta in [("GA", np.abs(c-a)-np.abs(b-a)),
                                 ("GS", (np.abs(c-a)+np.abs(c-b))/2-np.abs(b-a)),
                                 ("CB", c-b), ("within", np.abs(b-a)),
                                 ("cross", (np.abs(c-a)+np.abs(c-b))/2)]:
                result[f"{metric}_{label}_{side}"] = np.where(finite6, delta, np.nan)
                if metric == "B8L2" and label in ["GA", "GS", "CB"]:
                    result[f"{label}_{side}"] = np.where(finite6, delta, np.nan)
        for contrast in ["BA", "CA", "CB"]:
            result[f"{metric}_{contrast}"] = np.where(finite6, (result[f"{metric}_a_{contrast}"]+result[f"{metric}_b_{contrast}"])/2, np.nan)
        for label in ["within", "cross", "GA", "GS"]:
            result[f"{metric}_{label}"] = (result[f"{metric}_{label}_a"]+result[f"{metric}_{label}_b"])/2
        result[f"{metric}_extra"] = result[f"{metric}_cross"]-result[f"{metric}_within"]
    result["Q_common6"] = result.B8L2_common6
    result["score_failure_fraction"] = 1 - result[[f"Q_{r}_{s}" for s in SIDES for r in ROLES]].notna().mean(axis=1)
    index = endpoints.set_index("team_key")
    complete = np.column_stack([boolean(index.loc[result[team_column(result, r, s)], "complete_evaluable"]).to_numpy() for s in SIDES for r in ROLES])
    result["complete6"] = complete.all(axis=1)
    result["incomplete_fraction"] = 1-complete.mean(axis=1)
    return result


def compare_baseline(derived, stored):
    checks = []
    fields = [f"{m}_{s}_{c}" for m in METRICS for s in SIDES for c in ["BA", "CA", "CB"]]
    fields += [f"{c}_{s}" for c in ["GA", "GS", "CB"] for s in SIDES]
    for field in fields:
        if field in derived and field in stored:
            error = assert_numeric_equal(derived[field], stored[field], "baseline:" + field)
            checks.append({"field": field, "rows": len(stored), "maximum_absolute_error": error, "finite_support_equal": True})
    return pd.DataFrame(checks)


def pair_aggregate(events, columns):
    frame = events.copy()
    if "aggregation_contract" in frame and frame.aggregation_contract.eq("frozen_configuration").all():
        configuration = [*PAIR, *[c for c in ["groups", "method", "condition", "source_class", "target_class", "source_role", "target_role"] if c in frame]]
        return frame.groupby(configuration, dropna=False)[columns].mean().groupby(level=PAIR).mean().reset_index()
    if "block" not in frame:
        frame["block"] = frame.X_members + " / " + frame.Y_members + " / " + frame.Z_members
    return frame.groupby(PAIR+["block"], dropna=False)[columns].mean().groupby(level=PAIR).mean().reset_index()


def repetition_state(a, b, eps):
    sa = np.where(a > eps, 1, np.where(a < -eps, -1, 0))
    sb = np.where(b > eps, 1, np.where(b < -eps, -1, 0))
    return np.select([(sa == 0) & (sb == 0), sa*sb == -1, (sa == 1) & (sb == 1), (sa == -1) & (sb == -1)],
                     ["both_near_zero", "opposite", "both_gain", "both_loss"], default="one_response")


def summarize_versions(automatic, assisted, scope):
    oldmask = automatic.Q_common6.to_numpy()
    newmask = assisted.Q_common6.to_numpy()
    assert not np.any(oldmask & ~newmask), "Human auxiliary intervention removed a previously scored event"
    versions = {"automatic_original": automatic,
                "assisted_original_event_support": assisted.loc[oldmask].copy(),
                "assisted_expanded_support": assisted,
                "newly_scoreable_events_only": assisted.loc[newmask & ~oldmask].copy()}
    summaries, pair_frames, building_frames, direction_frames = [], [], [], []
    measures = [("B8L2", k, f"{k}_a", f"{k}_b") for k in ["GA", "GS", "CB"]]
    measures += [(m, k, f"{m}_{k}_a", f"{m}_{k}_b") for m in METRICS if m != "B8L2" for k in ["GA", "GS", "CB"] if f"{m}_{k}_a" in automatic]
    valuecols = list(dict.fromkeys([c for _, _, a, b in measures for c in [a,b]]))
    for version, frame in versions.items():
        if frame.empty:
            continue
        paired = pair_aggregate(frame, valuecols)
        paired.insert(0, "version", version)
        paired.insert(0, "scope", scope)
        pair_frames.append(paired)
        buildings = paired.groupby(["scope", "version", *GROUP, "building"], dropna=False)[valuecols].mean().reset_index()
        building_frames.append(buildings)
        for group, event_group in frame.groupby(GROUP, dropna=False):
            subset = paired
            for column, value in zip(GROUP, group):
                subset = subset[subset[column].eq(value)]
            meta = dict(zip(GROUP, group))
            meta.update(scope=scope, version=version, events=len(event_group), common6_events=int(event_group.Q_common6.sum()),
                        touched_events=int(event_group.manual_endpoint_touched.sum()), registered_pairs=event_group.pair_key.nunique(),
                        registered_buildings=event_group.building.nunique(),
                        distinct_endpoint_keys=len(set(event_group[all_team_columns(event_group)].to_numpy().ravel())))
            for metric, contrast, a, b in measures:
                valid = subset.dropna(subset=[a, b])
                x, y = valid[a], valid[b]
                z = (x+y)/2
                row = meta | dict(metric=metric, contrast=contrast, valid_pairs=len(valid), valid_buildings=valid.building.nunique(),
                                  view_a_mean=x.mean(), view_b_mean=y.mean(), pair_mean=z.mean(), pair_median=z.median(),
                                  pair_p10=z.quantile(.1), pair_p90=z.quantile(.9), pair_sd=z.std(ddof=1),
                                  positive_pairs=int(z.gt(0).sum()), negative_pairs=int(z.lt(0).sum()),
                                  both_positive_pairs=int((x.gt(0)&y.gt(0)).sum()), both_negative_pairs=int((x.lt(0)&y.lt(0)).sum()),
                                  pearson_r=x.corr(y) if len(valid)>=3 and x.nunique()>1 and y.nunique()>1 else np.nan,
                                  spearman_r=x.corr(y, method="spearman") if len(valid)>=3 and x.nunique()>1 and y.nunique()>1 else np.nan,
                                  correlation_scope="descriptive_physical_pairs_share_rooms_no_independent_room_inference",
                                  weighting=("event_then_frozen_configuration_then_physical_pair_equal" if "aggregation_contract" in frame and frame.aggregation_contract.eq("frozen_configuration").all() else "event_then_XYZ_block_then_physical_pair_equal"))
                summaries.append(row)
                if metric == "B8L2":
                    for eps in [0., 2.]:
                        states = repetition_state(x, y, eps)
                        direction_frames.extend([meta | dict(metric=metric, contrast=contrast, epsilon=eps,
                                                            state=state, pairs=int((states==state).sum()), valid_pairs=len(valid),
                                                            fraction=float((states==state).mean()) if len(valid) else np.nan)
                                                 for state in ["both_near_zero", "opposite", "both_gain", "both_loss", "one_response"]])
    return pd.DataFrame(summaries), pd.concat(pair_frames, ignore_index=True), pd.concat(building_frames, ignore_index=True), pd.DataFrame(direction_frames)


def support_table(automatic, assisted, scope):
    rows = []
    for group, old in automatic.groupby(GROUP, dropna=False):
        new = assisted.loc[old.index]
        keys = old[all_team_columns(old)].to_numpy().ravel()
        rows.append(dict(zip(GROUP, group)) | dict(scope=scope, events=len(old),
                    physical_events=len(old[all_team_columns(old)].drop_duplicates()), distinct_teams=len(set(keys)),
                    registered_pairs=old.pair_key.nunique(), buildings=old.building.nunique(),
                    automatic_common6=int(old.Q_common6.sum()), assisted_common6=int(new.Q_common6.sum()),
                    newly_common6=int((~old.Q_common6 & new.Q_common6).sum()),
                    still_unscoreable_events=int((~new.Q_common6).sum()), touched_events=int(old.manual_endpoint_touched.sum()),
                    touched_pairs=old.loc[old.manual_endpoint_touched,"pair_key"].nunique(),
                    conclusion="保持（端点未命中）" if not old.manual_endpoint_touched.any() else "按新增六端共同支持评估幅度与方向"))
    return pd.DataFrame(rows)


def pair_counterexamples(pairs):
    key = ["scope", *PAIR]
    old = pairs[pairs.version.eq("automatic_original")].drop(columns="version")
    new = pairs[pairs.version.eq("assisted_expanded_support")].drop(columns="version")
    joined = old.merge(new, on=key, suffixes=("_automatic", "_assisted"), validate="one_to_one")
    for label in ["automatic", "assisted"]:
        x, y = joined["CB_a_"+label], joined["CB_b_"+label]
        joined["CB_pair_mean_"+label] = (x+y)/2
        joined["CB_two_view_state_"+label] = repetition_state(x, y, 0.)
        joined.loc[x.isna() | y.isna(), "CB_two_view_state_"+label] = "no_common_six_event_support"
        joined["diagnostic_"+label] = (x.isna() | y.isna() | x.le(0) | y.le(0) |
            ((joined["GS_a_"+label]+joined["GS_b_"+label])/2).le(0) |
            ((joined["GA_a_"+label]+joined["GA_b_"+label])/2).le(0))
    joined["membership_transition"] = np.select([
        ~joined.diagnostic_automatic & joined.diagnostic_assisted,
        joined.diagnostic_automatic & ~joined.diagnostic_assisted,
        joined.diagnostic_automatic & joined.diagnostic_assisted], ["entered", "exited", "retained"], default="neither")
    return joined


def dependency_inventory(keys):
    rows = []
    for label, path in [
        ("finite_composition_and_member_repetition", REL/"same_room_current_extended_design/PANEL_TEAM_LINKS.csv.gz"),
        ("registered_large_frozen_working_labels", REL/"same_room_current_large_design/STRICT_ABC_EVENTS.csv.gz"),
    ]:
        frame = read_csv(path)
        columns = all_team_columns(frame) if label == "registered_large_frozen_working_labels" else [c for c in frame if "team_key" in c]
        hit = frame[columns].isin(keys)
        rows.append(dict(module=label, source=path.relative_to(ROOT).as_posix(), source_rows=len(frame),
                         key_columns="|".join(columns), matched_rows=int(hit.any(axis=1).sum()),
                         matched_references=int(hit.to_numpy().sum()), matched_teams=len(set(frame[columns].where(hit).stack())),
                         action="recompute_affected_results" if hit.to_numpy().any() else "unchanged_exact_endpoint_key_intersection_zero"))
    return pd.DataFrame(rows)


def native_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_saved_frozen_events(frame, frozen=True):
    """Add view-specific magnitudes with the original six-endpoint masks."""
    result = frame.copy()
    added = {}
    for metric in METRICS:
        if metric+"_within" not in result:
            continue
        mask = result[metric+"_within"].notna()
        added[metric+"_common6"] = mask
        for side in SIDES:
            ba, ca, cb = [pd.to_numeric(result[f"{metric}_{side}_{c}"], errors="coerce") for c in ["BA", "CA", "CB"]]
            values = {"GA": ca.abs()-ba.abs(), "GS": (ca.abs()+cb.abs())/2-ba.abs(),
                      "CB": cb, "within": ba.abs(), "cross": (ca.abs()+cb.abs())/2}
            for name, value in values.items():
                added[f"{metric}_{name}_{side}"] = value.where(mask)
                if metric == "B8L2" and name in ["GA", "GS", "CB"]:
                    added[f"{name}_{side}"] = value.where(mask)
    result = pd.concat([result.drop(columns=list(set(added)&set(result.columns))), pd.DataFrame(added, index=result.index)], axis=1)
    if frozen:
        result["method_updated"] = "frozen_working:"+result.method.astype(str)
        result["updated_direction"] = result.source_class.astype(str)+"→"+result.target_class.astype(str)
        result["aggregation_contract"] = "frozen_configuration"
    result["Q_common6"] = boolean(result.Q_common6)
    return result


def recover_automatic_endpoints(current_events):
    """Recover only missing current scalars, from frozen geometry and current refs.

    This is measurement recovery, not fusion.  Old-release quality is never used
    as the current quality.  Every recovered B8L2 is checked against the saved
    v2.1 arm score before the result can enter downstream calculations.
    """
    from . import apply_manual_ring_orders_20261104 as app
    from .scope_quality_scoring_20261016 import scoring_engine
    requested = read_csv(OUT/"REQUESTED_ARCHIVE_LOCATIONS.csv")
    requested=requested.rename(columns={"pool_id_x":"pool_id","reference_id_x":"reference_id_current"})
    requested_keys = set(requested.team_key)
    cache = OUT/"RECOVERED_AUTOMATIC_ENDPOINTS.jsonl.gz"
    if cache.exists():
        with gzip.open(cache, "rt", encoding="utf8") as f:
            records = {r["team_key"]: r for r in map(json.loads, f)}
        assert set(records) == requested_keys
    else:
        raw_records = {}
        archive_root = ROOT/"research/same_room/same_room_large_block_rebuilt_20261023/native_endpoints"
        for shard, group in requested.dropna(subset=["geometry_shard"]).groupby("geometry_shard"):
            path = archive_root/shard
            assert path.exists(), path
            locations = {int(r.geometry_line_1based): r.team_key for r in group.itertuples()}
            with gzip.open(path, "rt", encoding="utf8") as f:
                for line_number, line in enumerate(f, 1):
                    if line_number not in locations:
                        continue
                    raw = json.loads(line)
                    assert raw["team_key"] == locations[line_number]
                    raw["recovery_source"] = path.relative_to(ROOT).as_posix()+f"#L{line_number}"
                    raw_records[raw["team_key"]] = raw
        remaining = requested_keys-set(raw_records)
        for pool_id in sorted(set(requested.loc[requested.team_key.isin(remaining),"pool_id"])):
            for path in sorted((REL/"current_same_room_endpoints"/pool_id).glob("part_*.jsonl.gz")):
                with gzip.open(path,"rt",encoding="utf8") as f:
                    for line_number,line in enumerate(f,1):
                        raw=json.loads(line)
                        if raw["team_key"] in remaining:
                            raw["recovery_source"]=path.relative_to(ROOT).as_posix()+f"#L{line_number}"
                            raw_records[raw["team_key"]]=raw
        assert set(raw_records)==requested_keys, requested_keys-set(raw_records)
        pools=app.load_current_pools()
        helpers=app.diagnostic_modules()
        records={}
        with scoring_engine() as (engine,models):
            for i,(key,raw) in enumerate(sorted(raw_records.items()),1):
                pool,poolpath=pools[raw["pool_id"]]
                reference=pool["reference"]
                own={r["worker_id"]:r for r in pool["records"]}
                workers=raw["member_workers"]
                if isinstance(workers,str):workers=workers.split("|")
                assert sorted(raw["member_object_ids"])==sorted(own[w]["object_id"] for w in workers)
                if "full_state" in raw:
                    identity={k:v for k,v in raw.items() if k not in ["full_state","geometry"]}
                    identity.update(reference_id=reference["target_id"],reference_version=reference["reference_version"],data_release="v2.1")
                    row=app.evaluate(raw["full_state"],reference,engine,models,helpers,identity)
                    assert row["geometry"]==raw["geometry"], (key,"Frozen geometry changed")
                    row["identity_groups_n"]=len(raw["full_state"]["identity_groups"])
                    row["recovery_method"]="remeasure_frozen_geometry_under_exact_current_reference_no_fusion"
                else:
                    assert raw["reference_id"]==reference["target_id"] and raw["reference_version"]==reference["reference_version"]
                    row=deepcopy(raw)
                    row["recovery_method"]="reuse_saved_current_v21_endpoint_no_fusion_no_measurement"
                # Frozen pool records contain the actual recorded labor and its
                # semantics.  No human ordering duration is imputed.
                values=[own[w].get("source_time_seconds") for w in workers]
                known=[float(v) for v in values if v is not None and np.isfinite(float(v))]
                kinds="|".join(sorted({str(own[w].get("time_source_kind","unknown")) for w in workers}))
                row.update(source_time_known_n=len(known),source_time_total_seconds=sum(known) if len(known)==len(workers) else None,time_source_kinds=kinds)
                eligible=len(known)==len(workers) and sum(known)>0 and bool(kinds) and "|" not in kinds
                row.update(recorded_time_eligible=eligible,recorded_time_total_seconds=sum(known) if eligible else None,
                           recovery_current_pool_source=poolpath.relative_to(ROOT).as_posix(),
                           reference_nodes=len(reference["points_1024x512"])//2)
                row["reference_node_shortfall"]=max(0,row["reference_nodes"]-row["nodes"])
                records[key]=app.clean(row)
                if i%40==0: print("same-room frozen endpoint measurements",i,"/",len(raw_records),flush=True)
        cache.write_bytes(gzip.compress(("".join(json.dumps(clean(v),ensure_ascii=False,allow_nan=False)+"\n" for v in records.values())).encode(),mtime=0))
    scalar=[]
    for row in records.values():
        s={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
        for field in ["member_workers","member_object_ids","node_supports"]:
            s[field]="|".join(map(str,row[field]))
        scalar.append(s)
    frame=pd.DataFrame(scalar)
    save(frame,"RECOVERED_AUTOMATIC_ENDPOINT_SCALARS.csv.gz")
    reference_checks=[]
    for side in SIDES:
        for role in ROLES:
            keycol=team_column(current_events,role,side)
            found=current_events[current_events[keycol].isin(records)]
            recovered=frame.set_index("team_key").loc[found[keycol]]
            error=assert_numeric_equal(found[f"Q_{role}_{side}"],recovered.B8L2,f"recovery_Q:{role}:{side}")
            assert (found[f"reference_id_{side}"].to_numpy()==recovered.reference_id.to_numpy()).all()
            assert np.array_equal(boolean(found[f"complete_{role}_{side}"]),boolean(recovered.complete_evaluable))
            reference_checks.append(dict(role=role,view=side,event_references=len(found),maximum_B8L2_error=error,
                                         reference_exact=True,complete_state_equal=True))
    save(pd.DataFrame(reference_checks),"CURRENT_ENDPOINT_RECOVERY_PARITY.csv")
    write_json("SCALAR_RECOVERY_CHECKS.json",dict(requested_endpoints=len(frame),
               current_geometry_reused=sum(r["recovery_method"].startswith("reuse_saved") for r in records.values()),
               frozen_geometry_remeasured=sum(r["recovery_method"].startswith("remeasure") for r in records.values()),
               fusion_calls=0,current_reference_metadata_exact=True,geometry_unchanged=True,
               saved_v21_Q_and_complete_support_parity=True,
               maximum_B8L2_error=max(r["maximum_B8L2_error"] for r in reference_checks),
               labor_source="exact_current_pool_member_recorded_time_and_semantics",human_duration_imputed=False))
    return frame,records


def load_affected_registered_source(design, requested):
    """Read real v2.1 saved event rows, selecting only affected strata."""
    dimensions=["method","source_class","target_class","n","m"]
    strata=requested[dimensions].drop_duplicates()
    cache=OUT/"frozen_registered/AUTOMATIC_FULL_REGISTERED_SOURCE_AFFECTED_STRATA.csv.gz"
    cache.parent.mkdir(exist_ok=True)
    if cache.exists():
        source=read_csv(cache)
    else:
        parts=[]
        for chunk in pd.read_csv(FULL_REGISTERED_SOURCE,chunksize=2000,low_memory=False):
            matched=chunk.merge(strata,on=dimensions,validate="many_to_one")
            if not matched.empty:parts.append(matched)
        source=pd.concat(parts,ignore_index=True)
        save(source,"frozen_registered/AUTOMATIC_FULL_REGISTERED_SOURCE_AFFECTED_STRATA.csv.gz")
    assert source.event_id.is_unique
    expected=design.merge(strata,on=dimensions,validate="many_to_one")
    assert set(source.event_id)==set(expected.event_id)
    assert set(requested.event_id)<=set(source.event_id)
    write_json("frozen_registered/SOURCE_COVERAGE.json",dict(source=FULL_REGISTERED_SOURCE.relative_to(ROOT).as_posix(),
        registered_rows_in_affected_strata=len(expected),saved_source_rows=len(source),
        touched_registered_events=len(requested),touched_present_in_source=int(requested.event_id.isin(source.event_id).sum()),
        missing_touched_event_ids=[],full_registered_denominator_preserved=True,
        discarded_incomplete_alternative=ARCHIVE.relative_to(ROOT).as_posix(),
        restored_source_sha256="75eb59f204a529c49a757b9e5d54b95fa6b0eafc2021fcfb26a9da0209491296"))
    return source


def rebuild_affected_native(automatic_endpoints, assisted_endpoints, updated_keys):
    """Run the unchanged event builder on the 31 genuinely affected events."""
    directory = OUT/"frozen_registered"
    directory.mkdir(exist_ok=True)
    design_path = REL/"same_room_current_large_design/STRICT_ABC_EVENTS.csv.gz"
    design = read_csv(design_path)
    assert design.event_id.is_unique
    touched = design[all_team_columns(design)].isin(updated_keys).any(axis=1)
    requested = design.loc[touched].copy()
    if requested.empty:
        return None
    stored=load_affected_registered_source(design,requested)
    # The frozen native engine predates explicit team_key aliases.
    for side in SIDES:
        for role in ROLES:
            requested[f"team_{role}_{side}"] = requested[team_column(requested,role,side)]
    requested.to_csv(directory/"AFFECTED_DESIGN.csv", index=False)
    needed = set(requested[all_team_columns(requested)].to_numpy().ravel())
    builder = native_module("manual_order_original_same_room_event_builder", ROOT/"research/same_room/same_room_large_block_rebuilt_20261023/analysis/build_events.py")
    native_results = {}
    for name, endpoints in [("automatic", automatic_endpoints), ("assisted", assisted_endpoints)]:
        endpoint_path = directory/(name.upper()+"_AFFECTED_ENDPOINTS.csv.gz")
        endpoints[endpoints.team_key.isin(needed)].to_csv(endpoint_path, index=False, compression="gzip")
        builder.main(directory/"AFFECTED_DESIGN.csv", endpoint_path, directory/name)
        native_results[name] = read_csv(directory/name/"EVENT_Q_STRUCTURE_EFFECTS.csv.gz").set_index("event_id")
    source = stored.set_index("event_id")
    auto = native_results["automatic"]
    matched=auto.index.intersection(source.index)
    compare = source.loc[matched]
    numeric = [c for c in auto if c in compare and pd.api.types.is_numeric_dtype(auto[c])]
    checks = [{"field": c, "rows": len(matched), "maximum_absolute_error": assert_numeric_equal(auto.loc[matched,c], compare[c], "frozen_native:"+c)} for c in numeric]
    status=read_csv(REL/"same_room_current_results/large/results/EVENT_ENDPOINT_STATUS.csv.gz").set_index("event_id").loc[auto.index]
    for c in status:
        if pd.api.types.is_numeric_dtype(status[c]):
            checks.append(dict(field="full_status:"+c,rows=len(auto),maximum_absolute_error=assert_numeric_equal(auto[c],status[c],"registered_status:"+c)))
        else:
            assert auto[c].fillna("").astype(str).equals(status[c].fillna("").astype(str)),c
    save(pd.DataFrame(checks), "frozen_registered/BASELINE_NATIVE_EVENT_PARITY.csv")
    return design, requested, stored, native_results, checks


def frozen_registered(design,requested,stored,native_results,updated_keys):
    """Retain old working labels and original configuration/pair weighting."""
    source=stored.set_index("event_id")
    new = source.copy()
    matched=native_results["assisted"].index.intersection(new.index)
    for column in native_results["assisted"]:
        if column in new:
            new.loc[matched, column] = native_results["assisted"].loc[matched,column]
    original = derive_saved_frozen_events(source.reset_index())
    assisted = derive_saved_frozen_events(new.reset_index())
    hit = original.event_id.isin(requested.event_id)
    original["manual_endpoint_touched"] = hit
    assisted["manual_endpoint_touched"] = hit
    # Only strata with a true endpoint dependency are reaggregated here.
    affected_groups = original.loc[hit,GROUP].drop_duplicates()
    original = original.merge(affected_groups, on=GROUP, validate="many_to_one")
    assisted = assisted.merge(affected_groups, on=GROUP, validate="many_to_one")
    assert original.event_id.equals(assisted.event_id)
    support = support_table(original, assisted, "registered_frozen_working_labels")
    result = summarize_versions(original, assisted, "registered_frozen_working_labels")
    for name, frame in zip(["SUMMARY.csv", "PAIR_EFFECTS.csv.gz", "BUILDING_EFFECTS.csv.gz", "DIRECTION_STATES.csv"], result):
        save(frame, "frozen_registered/"+name)
    save(support, "frozen_registered/SUPPORT_CHANGES.csv")
    save(pair_counterexamples(result[1]), "frozen_registered/COUNTEREXAMPLE_TRANSITIONS.csv")
    save(original.loc[original.manual_endpoint_touched], "frozen_registered/TOUCHED_AUTOMATIC_EVENTS.csv.gz")
    save(assisted.loc[assisted.manual_endpoint_touched], "frozen_registered/TOUCHED_ASSISTED_EVENTS.csv.gz")
    save(original,"frozen_registered/AUTOMATIC_EVENTS.csv.gz")
    save(assisted,"frozen_registered/ASSISTED_EVENTS.csv.gz")
    write_json("frozen_registered/CHECKS.json", dict(registered_events=len(design), touched_event_rows=len(requested),
        affected_method_direction_size_groups=len(affected_groups), reaggregated_events=len(original),
        used_unchanged_companion_endpoints=len(set(requested[all_team_columns(requested)].to_numpy().ravel())-updated_keys),
        frozen_labels_not_renamed_to_current_labels=True, old_event_numeric_parity=True,
        new_fusion=0, new_scores=0, method="original_native_event_builder_then_original_configuration_weighting"))
    return result, support,original,assisted


def prepare_baseline():
    OUT.mkdir(parents=True, exist_ok=True)
    original = read_csv(UP/"SAME_ROOM_HALF_EVENTS.csv.gz")
    old_endpoints = read_csv(SCALARS) if SCALARS.exists() else None
    derived = derive_events(original, old_endpoints) if old_endpoints is not None else derive_saved_frozen_events(original, frozen=False)
    # The complete current scalar artifact is not tracked in this repository.
    # Independently reconstruct Q differences from saved arm scores and then
    # reproduce the full current hierarchy; never substitute older-release Q.
    q6 = original[[f"Q_{r}_{s}" for s in SIDES for r in ROLES]].notna().all(axis=1)
    assert np.array_equal(q6, boolean(original.Q_common6))
    for side in SIDES:
        a,b,c = [pd.to_numeric(original[f"Q_{r}_{side}"], errors="coerce") for r in ROLES]
        for name,values in [("BA",b-a),("CA",c-a),("CB",c-b)]:
            derived[f"B8L2_{side}_{name}"] = values
        for name,values in [("GA",(c-a).abs()-(b-a).abs()),("GS",((c-a).abs()+(c-b).abs())/2-(b-a).abs()),("CB",c-b)]:
            derived[f"{name}_{side}"] = values.where(q6)
    checks = compare_baseline(derived, original)
    save(checks, "BASELINE_REPRODUCTION.csv")
    values = [f"{k}_{s}" for k in ["GA", "GS", "CB"] for s in SIDES]
    pairs = pair_aggregate(derived, values)
    expected = read_csv(UP/"SAME_ROOM_HALF_PAIRS.csv")
    matched = pairs.merge(expected, on=PAIR, suffixes=("_actual", "_stored"), validate="one_to_one", indicator=True)
    assert len(pairs) == len(expected) == len(matched) and matched._merge.eq("both").all()
    errors = {c: assert_numeric_equal(matched[c+"_actual"], matched[c+"_stored"], "stored_pair:"+c) for c in values}
    write_json("BASELINE_CHECKS.json", dict(events=len(original), pairs=len(pairs), endpoint_rows=len(old_endpoints) if old_endpoints is not None else None,
               checked_metric_fields=len(checks), pair_field_errors=errors,
               maximum_absolute_error=max([*errors.values(), *checks.maximum_absolute_error.to_list()]),
               original_files_untouched=True, weighting="event_then_XYZ_block_then_physical_pair_equal",
               source_validation="native_scalars" if old_endpoints is not None else "saved_v21_arm_Q_independent_contrasts_and_full_saved_event_hierarchy",
               not_a_full_fusion_replay=True))
    return original, derived, old_endpoints


GEOMETRY_METRICS=["bev_mean_h","top_mean_h","bev_max_h","top_max_h","angle_deg","matched_reflex_disagreement_n"]
GEOMETRY_ORDER=["a_AB","a_AC","a_BC","b_AB","b_AC","b_BC"]


def geometry_common(events, comparisons):
    """Use exactly the frozen six-comparison correspondence gate."""
    g=comparisons.copy()
    g["view_comparison"]=g.view+"_"+g.comparison
    assert not g.duplicated(["event_id","view_comparison"]).any()
    def matrix(field):
        return g.pivot(index="event_id",columns="view_comparison",values=field).reindex(index=events.event_id,columns=GEOMETRY_ORDER).to_numpy()
    status=matrix("status")
    assert not pd.isna(status).any(), "Missing geometry comparison cannot be manufactured as a failed result"
    unique=status=="unique_cyclic_candidate"
    extra={"geometry_all_unique6":unique.all(axis=1),
           "Q_geometry_joint6":boolean(events.Q_common6).to_numpy()&unique.all(axis=1)}
    for metric in GEOMETRY_METRICS:
        x=matrix(metric).astype(float)
        valid=np.isfinite(x).all(axis=1)&unique.all(axis=1)
        extra["geometry_common6_"+metric]=valid
        for side,offset in [("a",0),("b",3)]:
            extra[f"geometry_{metric}_within_{side}"]=np.where(valid,x[:,offset],np.nan)
            extra[f"geometry_{metric}_cross_{side}"]=np.where(valid,x[:,offset+1:offset+3].mean(axis=1),np.nan)
            extra[f"geometry_{metric}_extra_{side}"]=extra[f"geometry_{metric}_cross_{side}"]-extra[f"geometry_{metric}_within_{side}"]
        for label in ["within","cross","extra"]:
            extra[f"geometry_{metric}_{label}"]=(extra[f"geometry_{metric}_{label}_a"]+extra[f"geometry_{metric}_{label}_b"])/2
    for value in sorted(set(status.ravel())-{"unique_cyclic_candidate"}):
        mask=status==value
        extra[f"geometry_{value}_within"]=mask[:,[0,3]].mean(axis=1)
        extra[f"geometry_{value}_cross"]=mask[:,[1,2,4,5]].mean(axis=1)
        extra[f"geometry_{value}_extra"]=extra[f"geometry_{value}_cross"]-extra[f"geometry_{value}_within"]
    warn=matrix("high_angle_correspondence_warning")
    warn=np.vectorize(lambda v:str(v).lower() in ["true","1","1.0"])(warn)
    extra["geometry_any_high_angle_warning"]=np.where(unique.all(axis=1),warn.any(axis=1).astype(float),np.nan)
    return pd.concat([events.reset_index(drop=True),pd.DataFrame(extra)],axis=1)


def summarize_geometry_impact(automatic,assisted,scope):
    rows=[];supports=[]
    metrics=[f"geometry_{m}_{l}" for m in GEOMETRY_METRICS for l in ["within","cross","extra"]]
    for keys,old in automatic.groupby(GROUP,dropna=False):
        new=assisted.loc[old.index]
        metadata=dict(zip(GROUP,keys))|dict(scope=scope)
        supports.append(metadata|dict(events=len(old),automatic_unique6=int(old.geometry_all_unique6.sum()),
            assisted_unique6=int(new.geometry_all_unique6.sum()),automatic_joint_Q_geometry6=int(old.Q_geometry_joint6.sum()),
            assisted_joint_Q_geometry6=int(new.Q_geometry_joint6.sum()),
            newly_unique6=int((~old.geometry_all_unique6&new.geometry_all_unique6).sum()),
            still_without_unique6=int((~new.geometry_all_unique6).sum())))
        for support,oldmask,newmask in [
            ("six_geometry_comparisons",old.geometry_all_unique6,new.geometry_all_unique6),
            ("joint_six_quality_and_geometry",old.Q_geometry_joint6,new.Q_geometry_joint6)]:
            for version,selected in [
                ("automatic_original",old.loc[oldmask]),
                ("assisted_original_common_support",new.loc[oldmask]),
                ("assisted_expanded_support",new.loc[newmask]),
                ("newly_available_support_only",new.loc[newmask&~oldmask])]:
                if selected.empty:continue
                paired=pair_aggregate(selected,metrics)
                for metric in metrics:
                    x=paired[metric].dropna()
                    rows.append(metadata|dict(support=support,version=version,metric=metric,events=len(selected),
                        pairs=len(x),buildings=selected.building.nunique(),pair_equal_mean=x.mean(),
                        pair_equal_median=x.median(),pair_p10=x.quantile(.1),pair_p90=x.quantile(.9),
                        positive_pairs=int(x.gt(0).sum()),distance_unit="camera height h; angles in degrees; reflex disagreement is a count"))
    return pd.DataFrame(rows),pd.DataFrame(supports)


def geometry_impact(current_automatic,current_assisted,frozen_automatic,frozen_assisted):
    directory=OUT/"geometry";directory.mkdir(exist_ok=True)
    with gzip.open(OUT/"RECOVERED_AUTOMATIC_ENDPOINTS.jsonl.gz","rt",encoding="utf8") as f:
        originals={r["team_key"]:r for r in map(json.loads,f)}
    with gzip.open(BASE/"endpoints/ENDPOINTS.jsonl.gz","rt",encoding="utf8") as f:
        updates={r["team_key"]:r for r in map(json.loads,f)}
    requested=read_csv(OUT/"REQUESTED_GEOMETRY_COMPARISONS.csv")
    ids=set(current_automatic.event_id)|set(frozen_automatic.event_id)|set(requested.event_id)
    cache=directory/"AUTOMATIC_RELEVANT_COMPARISONS.csv.gz"
    if cache.exists():
        geometry=read_csv(cache)
        if set(geometry.event_id)!=ids:cache=None
    if not cache or not cache.exists():
        path=REL/"same_room_current_results/large/geometry/EVENT_GEOMETRY_RESULTS.csv.gz"
        frames=[]
        for chunk in pd.read_csv(path,chunksize=15000,low_memory=False):
            got=chunk[chunk.event_id.isin(ids)]
            if not got.empty:frames.append(got)
        geometry=pd.concat(frames,ignore_index=True)
        save(geometry,"geometry/AUTOMATIC_RELEVANT_COMPARISONS.csv.gz")
    assert len(geometry)==6*len(ids) and set(geometry.event_id)==ids
    corner=native_module("manual_order_frozen_corner",ROOT/"research/same_room/same_room_large_block_rebuilt_20261023/engine/frozen_repo/research/workers/personnel_interchangeability_followup_20261020/audit_corner/corner_distance.py")
    pairs=requested[["team_key_from","team_key_to"]].drop_duplicates()
    computed={};checks=[];pair_rows=[];details=[]
    for left,right in pairs.itertuples(index=False,name=None):
        a,b=originals[left],originals[right]
        old,_=corner.corner_compare(a,b)
        new,detail=corner.corner_compare(updates.get(left,a),updates.get(right,b))
        saved=geometry[geometry.team_key_from.eq(left)&geometry.team_key_to.eq(right)]
        assert len(saved)>0 and saved.status.eq(old["status"]).all(),(left,right,"old geometry status differs")
        checks.append(dict(team_key_from=left,team_key_to=right,field="status",rows=len(saved),maximum_absolute_error=0.0))
        for field,value in old.items():
            if field in saved and isinstance(value,(int,float)) and not isinstance(value,bool):
                error=assert_numeric_equal(saved[field],pd.Series([value]*len(saved)),f"geometry:{field}")
                checks.append(dict(team_key_from=left,team_key_to=right,field=field,rows=len(saved),maximum_absolute_error=error))
        computed[left,right]=new
        pair_rows.append(dict(team_key_from=left,team_key_to=right,automatic_status=old["status"],assisted_status=new["status"],
                             automatic_complete=old["complete"],assisted_complete=new["complete"],
                             automatic_same_count=old["same_count"],assisted_same_count=new["same_count"],
                             **{"assisted_"+k:v for k,v in new.items() if k not in ["status","complete","same_count"]}))
        details.extend(dict(team_key_from=left,team_key_to=right,**d) for d in detail)
    new_geometry=geometry.copy()
    diagnostic_fields=set().union(*(set(v) for v in computed.values()))|set(GEOMETRY_METRICS)
    fixed_fields={"event_id","view","comparison","pool_id","pair_key","config_id","building","condition","method","n","m",
                  "geometry_pair_key","team_key_from","team_key_to","reference_id","reference_version",
                  "geometry_state_pointer_from","geometry_state_pointer_to"}
    diagnostic_fields=set(geometry.columns)-fixed_fields
    hit=new_geometry.apply(lambda r:(r.team_key_from,r.team_key_to) in computed,axis=1)
    for index,row in new_geometry.loc[hit].iterrows():
        changed=computed[row.team_key_from,row.team_key_to]
        for field in diagnostic_fields:
            new_geometry.at[index,field]=changed.get(field,np.nan)
        for field in ["geometry_state_pointer_from","geometry_state_pointer_to"]:
            role="team_key_from" if field.endswith("from") else "team_key_to"
            if row[role] in updates:new_geometry.at[index,field]="research/fusion/manual_order_impact_20261104/endpoints/ENDPOINTS.jsonl.gz#"+row[role]
    save(pd.DataFrame(checks),"geometry/ORIGINAL_GEOMETRY_PARITY.csv")
    save(pd.DataFrame(pair_rows),"geometry/ORDERED_PAIR_TRANSITIONS.csv")
    save(pd.DataFrame(details),"geometry/ASSISTED_PER_CORNER_DISTANCES.csv.gz")
    save(new_geometry.loc[hit],"geometry/CHANGED_EVENT_COMPARISONS.csv.gz")
    save(new_geometry,"geometry/ASSISTED_RELEVANT_COMPARISONS.csv.gz")
    outputs={}
    for scope,old,new in [("current_image_difficulty_labels",current_automatic,current_assisted),
                          ("registered_frozen_working_labels",frozen_automatic,frozen_assisted)]:
        ga=geometry_common(old,geometry[geometry.event_id.isin(old.event_id)])
        gh=geometry_common(new,new_geometry[new_geometry.event_id.isin(new.event_id)])
        summary,support=summarize_geometry_impact(ga,gh,scope)
        prefix="current" if scope.startswith("current") else "frozen_registered"
        save(summary,"geometry/"+prefix.upper()+"_SUMMARY.csv")
        save(support,"geometry/"+prefix.upper()+"_SUPPORT.csv")
        save(ga,"geometry/"+prefix.upper()+"_AUTOMATIC_EVENTS.csv.gz")
        save(gh,"geometry/"+prefix.upper()+"_ASSISTED_EVENTS.csv.gz")
        outputs[prefix]=(ga,gh)
    write_json("geometry/CHECKS.json",dict(unique_changed_ordered_pairs=len(computed),requested_event_comparison_rows=len(requested),
        actual_updated_event_comparison_rows=int(hit.sum()),relevant_events=len(ids),six_comparisons_per_event=True,
        original_correspondence_status_and_available_distances_reproduced=True,
        distance_unit="camera height h, not metres",new_fusion=0,new_alignment_or_geometric_repair=0,
        correspondence="frozen unique cyclic candidate; not proof of semantic structural equivalence"))
    return outputs


def labor_and_history_dependents(automatic,assisted,scope,prefix):
    """Update actual joint-support consumers without changing recorded labor."""
    unchanged=[c for c in automatic if c.startswith(("recorded_time_total_seconds_","time_ratio_","time_logratio_"))]
    errors={c:assert_numeric_equal(automatic[c],assisted[c],"recorded_labor:"+c) for c in unchanged}
    assert np.array_equal(boolean(automatic.time_common6),boolean(assisted.time_common6))
    labor=[]
    for key,old in automatic.groupby(GROUP,dropna=False):
        new=assisted.loc[old.index]
        meta=dict(zip(GROUP,key))|dict(scope=scope)
        for version,frame in [("automatic_original",old),("assisted_original_Q_support",new.loc[boolean(old.Q_common6)]),("assisted_expanded_support",new)]:
            row=meta|dict(version=version,events=len(frame),time_common6_events=int(boolean(frame.time_common6).sum()),
                Q_common6_events=int(boolean(frame.Q_common6).sum()),joint_QT6_events=int(boolean(frame.QT_common6).sum()),
                human_ordering_duration="not_recorded_not_imputed",recorded_annotation_labor_changed=False)
            for contrast in ["BA","CA","CB"]:
                row["QT4_common_"+contrast]=int(boolean(frame["QT4_common_"+contrast]).sum())
            columns=[f"{start}_{contrast}" for start in ["QT_Q","QT_time_ratio","QT_time_logratio","QT4_Q","QT4_time_ratio","QT4_time_logratio"] for contrast in ["BA","CA","CB"]]
            means=pair_aggregate(frame,columns) if len(frame) else pd.DataFrame(columns=columns)
            row.update({"pair_equal__"+c:means[c].mean() for c in columns})
            labor.append(row)
    save(pd.DataFrame(labor),prefix+"JOINT_RECORDED_LABOR_SUPPORT.csv")
    write_json(prefix+"LABOR_PARITY.json",dict(time_fields_checked=len(errors),maximum_absolute_error=max(errors.values(),default=0.),
        recorded_labor_unchanged=True,time_semantics_and_missingness_preserved=True,human_ordering_duration_imputed=False,
        interpretation="Only the joint score/labor support expands. Manual ordering cost is unmeasured, so this is not the total cost-benefit of assisted fusion."))
    histories=[]
    measures=[f"{m}_{x}" for m in METRICS for x in ["within","cross","extra","CA","CB"] if f"{m}_{x}" in automatic]
    measures += [c for c in automatic if c.startswith("geometry_") and c.endswith(("_within","_cross","_extra")) and "common" not in c]
    for key,old in automatic.groupby(GROUP,dropna=False):
        new=assisted.loc[old.index]
        assert_numeric_equal(old.history_Q_block_range,new.history_Q_block_range,"historical_Q_selector")
        meta=dict(zip(GROUP,key))|dict(scope=scope)
        for threshold in [2.,5.]:
            for matching in ["same_configuration","same_configuration_exact_D"]:
                matchcols=PAIR.copy()
                if "aggregation_contract" in old and old.aggregation_contract.eq("frozen_configuration").all():
                    matchcols += [c for c in ["groups","method","condition","source_class","target_class","source_role","target_role"] if c in old]
                if matching.endswith("exact_D"):matchcols.append("D_members")
                old=old.copy();new=new.copy()
                old["D_members"]=old.D_members.fillna("");new["D_members"]=new.D_members.fillna("")
                near_identity=old.loc[old.history_Q_block_range.le(threshold),matchcols].drop_duplicates()
                if near_identity.empty:continue
                for version,frame in [("automatic_original",old),("assisted_expanded_support",new)]:
                    broad=frame.merge(near_identity,on=matchcols,validate="many_to_one")
                    near=broad[broad.history_Q_block_range.le(threshold)]
                    def historical_pairs(data):
                        data=data.copy()
                        frozen="aggregation_contract" in data and data.aggregation_contract.eq("frozen_configuration").all()
                        if frozen:
                            config=[*PAIR,*[c for c in ["groups","method","condition","source_class","target_class","source_role","target_role"] if c in data]]
                        else:
                            if "block" not in data:data["block"]=data.X_members+" / "+data.Y_members+" / "+data.Z_members
                            config=[*PAIR,"block"]
                        strata=config+(["D_members"] if matching.endswith("exact_D") else [])
                        means=data.groupby(strata,dropna=False)[measures].mean()
                        if matching.endswith("exact_D"):means=means.groupby(level=config).mean()
                        return means.groupby(level=PAIR).mean().reset_index()
                    npair=historical_pairs(near)
                    bpair=historical_pairs(broad)
                    joined=npair.merge(bpair,on=PAIR,suffixes=("_near","_all"),validate="one_to_one")
                    for metric in measures:
                        valid=joined.dropna(subset=[metric+"_near",metric+"_all"])
                        histories.append(meta|dict(version=version,threshold=threshold,matching=matching,metric=metric,
                            near_events=len(near),all_on_support_events=len(broad),near_Q6_events=int(near.Q_common6.sum()),
                            all_on_support_Q6_events=int(broad.Q_common6.sum()),valid_pairs=len(valid),valid_buildings=valid.building.nunique(),
                            near_pair_equal=valid[metric+"_near"].mean(),all_on_support_pair_equal=valid[metric+"_all"].mean(),
                            conditional_difference=(valid[metric+"_near"]-valid[metric+"_all"]).mean(),
                            interpretation="nested conditional comparison on the same registered strata; not causal or an explained share"))
    save(pd.DataFrame(histories),prefix+"HISTORICAL_Q_COMMON_SUPPORT.csv")


def full_registered_summary_update(design,automatic,assisted):
    """Patch the full registered hierarchy using exact recomputed cell means.

    Only the eight method/direction/n/m strata containing an affected endpoint
    are read at event resolution.  Every unaffected configuration stays in the
    full original hierarchy.  This preserves the 62,964-event denominator.
    """
    analysis=ROOT/"research/same_room/same_room_large_block_rebuilt_20261023/analysis"
    sys.path.insert(0,str(analysis))
    native=native_module("manual_order_native_conditions",analysis/"summarize_conditions.py")
    source=REL/"same_room_current_results/large/results"
    directory="frozen_registered/native_results/"
    cfgcols=["subset",*native.CFG]
    original_cfg=read_csv(source/"CONFIGURATION_METRICS.csv.gz")
    patched_cfg=original_cfg.copy()
    metriccols=native.analysis_columns(automatic)
    original_cfg_index=original_cfg.set_index(cfgcols)
    patched_cfg=patched_cfg.set_index(cfgcols)
    checks=[];changed_cells=[]
    for subset,method,condition,old in native.subsets(automatic):
        new=assisted.loc[old.index]
        a,*_=native.hierarchy(old,metriccols)
        b,*_=native.hierarchy(new,metriccols)
        a.insert(0,"subset",subset);b.insert(0,"subset",subset)
        a=a.set_index(cfgcols);b=b.set_index(cfgcols)
        expected=original_cfg_index.loc[a.index]
        for field in a:
            if field in expected:
                checks.append(dict(subset=subset,method=method,condition=condition,field=field,configurations=len(a),
                    maximum_absolute_error=assert_numeric_equal(a[field],expected[field],"full_configuration_baseline:"+field)))
                patched_cfg.loc[b.index,field]=b[field]
        changed_cells.extend(dict(zip(cfgcols,index))|dict(old_Q_events=int(a.loc[index,"common6_Q_events"]),
                                new_Q_events=int(b.loc[index,"common6_Q_events"])) for index in a.index
                             if a.loc[index,"common6_Q_events"]!=b.loc[index,"common6_Q_events"])
    patched_cfg=patched_cfg.reset_index()
    save(patched_cfg,directory+"CONFIGURATION_METRICS.csv.gz")
    save(pd.DataFrame(checks),directory+"CONFIGURATION_BASELINE_PARITY.csv")
    save(pd.DataFrame(changed_cells),directory+"CHANGED_CONFIGURATION_SUPPORT.csv")
    countcols=["attempted_events","common6_Q_events","complete6_events","joint_QT_events"]
    pairkey=["subset","pair_key","building","groups","method","condition"]
    def aggregate_cfg(frame):
        pair=frame.groupby(pairkey,dropna=False)[metriccols].mean().reset_index()
        counts=frame.groupby(pairkey,dropna=False)[countcols].sum().reset_index()
        counts["configurations"]=frame.groupby(pairkey,dropna=False).size().to_numpy()
        pair=pair.merge(counts,on=pairkey,validate="one_to_one")
        exploded=pair.assign(group_id=pair.groups.fillna("unknown").astype(str).str.split("|")).explode("group_id")
        declaration=exploded.groupby(["subset","building","group_id","method","condition"],dropna=False)[metriccols].mean().reset_index()
        bdecl=declaration.groupby(["subset","building","method","condition"],dropna=False)[metriccols].mean().reset_index()
        bpair=pair.groupby(["subset","building","method","condition"],dropna=False)[metriccols].mean().reset_index()
        return pair,declaration,bdecl,bpair
    oldpair,olddecl,oldbd,oldbp=aggregate_cfg(original_cfg)
    newpair,newdecl,newbd,newbp=aggregate_cfg(patched_cfg)
    expected_pair=read_csv(source/"PAIR_METRICS.csv.gz").set_index(pairkey)
    actual_pair=oldpair.set_index(pairkey).reindex(expected_pair.index)
    pairchecks=[dict(field=c,rows=len(oldpair),maximum_absolute_error=assert_numeric_equal(actual_pair[c],expected_pair[c],"full_pair_baseline:"+c)) for c in actual_pair if c in expected_pair]
    save(pd.DataFrame(pairchecks),directory+"PAIR_BASELINE_PARITY.csv")
    save(newpair,directory+"PAIR_METRICS.csv.gz")
    save(newdecl,directory+"DECLARATION_GROUP_METRICS.csv.gz")
    save(pd.concat([newbd.assign(weighting="declaration_then_building"),newbp.assign(weighting="pair_then_building")],ignore_index=True),directory+"BUILDING_METRICS.csv.gz")

    # The original event counts/people inventories are retained.  Only fields
    # mathematically depending on changed endpoint outcomes are recomputed.
    metadata=design.copy()
    metadata["difficulty_pair"]=metadata.difficulty_a.astype(str)+" / "+metadata.difficulty_b.astype(str)
    mapping=metadata[native.CFG+["source_role_key","target_role_key","difficulty_pair"]].drop_duplicates()
    assert not mapping.duplicated(native.CFG).any()
    oldmeta=original_cfg.merge(mapping,on=native.CFG,validate="many_to_one")
    newmeta=patched_cfg.merge(mapping,on=native.CFG,validate="many_to_one")
    affected_old=automatic[automatic.manual_endpoint_touched]
    affected_new=assisted.loc[affected_old.index]
    old_subsets={(s,m,c):e for s,m,c,e in native.subsets(affected_old)}
    new_subsets={(s,m,c):e for s,m,c,e in native.subsets(affected_new)}
    def filtered(frame,row,kind):
        z=frame
        for field in ["method","condition"]:
            z=z[z[field].eq(row[field])]
        if "subset" in z:z=z[z.subset.eq(row["subset"])]
        if kind=="N_M_CONDITIONS.csv":
            z=z[z.n.eq(row.n)&z.m.eq(row.m)]
        if kind=="DIRECTION_RESULTS.csv":
            z=z[z.source_role_key.eq(row.source_role_key)&z.target_role_key.eq(row.target_role_key)]
        if kind in ["LEAVE_ONE_BUILDING_OUT.csv","EXCLUDE_UNB_SPECIFIC.csv"]:
            z=z[~z.building.eq(row.excluded_building)]
        if kind=="DIFFICULTY_PAIR_CONDITIONS.csv":
            z=z[z.difficulty_pair.eq(row.difficulty_pair)]
        return z
    def infer_summary(cfg):
        pair,decl,bd,bp=aggregate_cfg(cfg)
        answer={}
        for metric in metriccols:
            answer["pair_equal__"+metric]=pair[metric].mean()
            answer["building_equal__"+metric]=bp[metric].mean()
            answer["declaration_building__"+metric]=bd[metric].mean()
        q=pair.B8L2_extra.dropna()
        answer.update(Q_pairs=len(q),Q_buildings=pair.loc[pair.B8L2_extra.notna(),"building"].nunique(),
            positive_Q_extra_pairs=int(q.gt(0).sum()),positive_Q_extra_pair_fraction=q.gt(0).mean(),
            positive_Q_extra_building_fraction=bp.B8L2_extra.dropna().gt(0).mean(),
            Q_extra_pair_p10=q.quantile(.1),Q_extra_pair_p50=q.quantile(.5),Q_extra_pair_p90=q.quantile(.9))
        for metric in native.METRICS:
            valid=pair[metric+"_within"].notna()
            answer[metric+"_common6_pairs"]=int(valid.sum())
            answer[metric+"_common6_buildings"]=pair.loc[valid,"building"].nunique()
        for contrast in ["BA","CA","CB"]:
            valid=pair["QT4_common_"+contrast].gt(0)
            answer["joint_QT4_"+contrast+"_pairs"]=int(valid.sum())
            answer["joint_QT4_"+contrast+"_buildings"]=pair.loc[valid,"building"].nunique()
        for eps in ["eps0","eps2"]:
            for contrast in ["BA","CA","CB"]:
                prefix=eps+"_"+contrast
                sn,tn=prefix+"_source_same_n",prefix+"_source_trigger_n"
                same,both=prefix+"_same_nonzero",prefix+"_both_response"
                numerator=(cfg[sn]*cfg.attempted_events).sum()
                denominator=(cfg[tn]*cfg.attempted_events).sum()
                two=(cfg[both]*cfg.common6_Q_events).sum()
                twosame=(cfg[same]*cfg.common6_Q_events).sum()
                answer["event_weight_"+prefix+"_source_only_same"]=numerator/denominator if denominator else np.nan
                answer["event_weight_"+prefix+"_source_triggers"]=int(round(denominator))
                answer["event_weight_"+prefix+"_both_trigger_same"]=twosame/two if two else np.nan
                answer["event_weight_"+prefix+"_both_response_events"]=int(round(two))
                trigger=cfg[["pair_key","building"]].copy()
                trigger[sn]=cfg[sn]*cfg.attempted_events
                trigger[tn]=cfg[tn]*cfg.attempted_events
                trigger=trigger.groupby(["pair_key","building"])[[sn,tn]].sum()
                ratio=trigger[sn]/trigger[tn].replace(0,np.nan)
                answer["pair_equal_event_trigger_weight_"+prefix+"_source_only_same"]=ratio.mean()
                quality_cfg=cfg[cfg.common6_Q_events.gt(0)].copy()
                for field in [sn,tn]:
                    quality_cfg[field]=quality_cfg[field]*quality_cfg.attempted_events/quality_cfg.common6_Q_events
                qp=quality_cfg.groupby(["pair_key","building"])[[sn,tn,same,both]].mean()
                sr=qp[sn]/qp[tn].replace(0,np.nan)
                br=qp[same]/qp[both].replace(0,np.nan)
                answer["pair_equal_"+prefix+"_source_only_same"]=sr.mean()
                answer["building_equal_"+prefix+"_source_only_same"]=sr.groupby("building").mean().mean()
                answer["pair_equal_"+prefix+"_both_trigger_same"]=br.mean()
                answer["building_equal_"+prefix+"_both_trigger_same"]=br.groupby("building").mean().mean()
                answer[prefix+"_source_triggered_pairs"]=int(sr.notna().sum())
        return answer
    summarychecks=[];updated_rows=[]
    for name in ["OVERALL_CONDITIONS.csv","N_M_CONDITIONS.csv","DIRECTION_RESULTS.csv","LEAVE_ONE_BUILDING_OUT.csv","EXCLUDE_UNB_SPECIFIC.csv","DIFFICULTY_PAIR_CONDITIONS.csv"]:
        before=read_csv(source/name);after=before.copy()
        for index,row in before.iterrows():
            subset="ordinary_all" if name=="DIFFICULTY_PAIR_CONDITIONS.csv" else row["subset"]
            key=(subset,row.method,row.condition)
            if key not in old_subsets:continue
            keyrow=row.copy();keyrow["subset"]=subset
            olde=filtered(old_subsets[key],keyrow,name)
            newe=filtered(new_subsets[key],keyrow,name)
            if olde.empty:continue
            ac=filtered(oldmeta,keyrow,name);bc=filtered(newmeta,keyrow,name)
            expected=infer_summary(ac);replacement=infer_summary(bc)
            maximum=0.
            for field,value in expected.items():
                if field not in before:continue
                error=assert_numeric_equal(pd.Series([value]),pd.Series([row[field]]),name+":"+field)
                maximum=max(maximum,error)
                after.at[index,field]=replacement[field]
            for field,column in [("common6_Q_events","Q_common6"),("joint_QT_events","QT_common6")]:
                after.at[index,field]=row[field]+int(boolean(newe[column]).sum())-int(boolean(olde[column]).sum())
            for metric in native.METRICS:
                ov=olde[metric+"_within"].notna();nv=newe[metric+"_within"].notna()
                for suffix,delta in [("_common6_events",int(nv.sum()-ov.sum())),("_common6_Q_events",int((nv&boolean(newe.Q_common6)).sum()-(ov&boolean(olde.Q_common6)).sum()))]:
                    after.at[index,metric+suffix]=row[metric+suffix]+delta
            for contrast in ["BA","CA","CB"]:
                field="joint_QT4_"+contrast+"_events";column="QT4_common_"+contrast
                after.at[index,field]=row[field]+int(boolean(newe[column]).sum())-int(boolean(olde[column]).sum())
            summarychecks.append(dict(file=name,row=index,subset=row["subset"],method=row.method,condition=row.condition,
                                      fields_reproduced=len(expected),maximum_absolute_error=maximum))
            updated_rows.append(dict(file=name,row=index,subset=row["subset"],method=row.method,condition=row.condition,affected_events=len(olde)))
        save(after,directory+name)
    save(pd.DataFrame(summarychecks),directory+"FULL_SUMMARY_BASELINE_PARITY.csv")
    save(pd.DataFrame(updated_rows),directory+"UPDATED_SUMMARY_ROWS.csv")
    write_json(directory+"CHECKS.json",dict(registered_events=len(design),configuration_rows=len(patched_cfg),
        pair_rows=len(newpair),affected_stratum_events=len(automatic),touched_events=len(affected_old),
        actual_changed_configuration_support_rows=len(changed_cells),affected_summary_rows=len(updated_rows),
        baseline_configuration_metrics_reproduced=True,baseline_all_pair_metrics_reproduced=True,
        baseline_updated_summary_rows_reproduced=True,full_registered_denominator_preserved=True,
        unchanged_configurations_retained=True,automatic_results_preserved=True,original_files_modified=False))


def compare_saved_table(expected_path,actual_path):
    expected=read_csv(expected_path);actual=read_csv(actual_path)
    assert expected.shape==actual.shape,(str(expected_path),expected.shape,actual.shape)
    assert set(expected)==set(actual),(str(expected_path),"columns")
    checks=[]
    for field in expected:
        if pd.api.types.is_numeric_dtype(expected[field]) and pd.api.types.is_numeric_dtype(actual[field]):
            err=assert_numeric_equal(expected[field],actual[field],str(expected_path)+":"+field)
        else:
            assert expected[field].fillna("").astype(str).equals(actual[field].fillna("").astype(str)),(str(expected_path),field)
            err=0.
        checks.append(dict(file=expected_path.name,field=field,rows=len(expected),maximum_absolute_error=err))
    return checks


def full_geometry_and_native_dependents():
    """Propagate real geometry/history/member consumers on original support."""
    analysis=ROOT/"research/same_room/same_room_large_block_rebuilt_20261023/analysis"
    sys.path.insert(0,str(analysis))
    conditions=native_module("manual_order_full_geometry_conditions",analysis/"summarize_conditions.py")
    history=native_module("manual_order_full_history",analysis/"history_q_common_support.py")
    members=native_module("manual_order_full_members",analysis/"member_sensitivity.py")
    root=REL/"same_room_current_results/large"
    prefix="frozen_registered/native_geometry_summary/"
    original=read_csv(root/"geometry_summary/EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz")
    assisted=original.copy().set_index("event_id")
    original_index=original.set_index("event_id")
    old=read_csv(OUT/"geometry/FROZEN_REGISTERED_AUTOMATIC_EVENTS.csv.gz")
    new=read_csv(OUT/"geometry/FROZEN_REGISTERED_ASSISTED_EVENTS.csv.gz")
    hit=old.manual_endpoint_touched
    old=old.loc[hit].set_index("event_id");new=new.loc[hit].set_index("event_id")
    checks=[]
    for c in original:
        if c=="event_id" or c not in old:continue
        if pd.api.types.is_numeric_dtype(original[c]):
            err=assert_numeric_equal(original_index.loc[old.index,c],old[c],"geometry_common_baseline:"+c)
            checks.append(dict(file="EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz",field=c,rows=len(old),maximum_absolute_error=err))
        else:
            assert original_index.loc[old.index,c].fillna("").astype(str).equals(old[c].fillna("").astype(str)),c
        assisted.loc[new.index,c]=new[c]
    assisted=assisted.reset_index()
    save(assisted,prefix+"EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz")
    cols=[c for c in original if c.startswith("geometry_") and c.endswith(("_within","_cross","_extra"))]
    cols+=['geometry_any_high_angle_warning','geometry_all_unique6','Q_geometry_joint6']
    cols=list(dict.fromkeys(cols))
    def calculate(frame):
        pair_rows=[];overall=[]
        for subset,method,condition,dd in conditions.subsets(frame):
            for support in ["all_geometry_diagnostics","joint_Q_and_geometry"]:
                dz=dd if support=="all_geometry_diagnostics" else dd[boolean(dd.Q_geometry_joint6)]
                if dz.empty:continue
                cfg=dz.groupby(conditions.CFG,dropna=False)[cols+["B8L2_extra"]].mean().reset_index()
                pair=cfg.groupby(["pair_key","building","groups"],dropna=False)[cols+["B8L2_extra"]].mean().reset_index()
                pair["subset"]=subset;pair["method"]=method;pair["condition"]=condition;pair["support"]=support
                pair_rows.append(pair)
                buildings=pair.groupby("building")[cols+["B8L2_extra"]].mean()
                row=dict(subset=subset,method=method,condition=condition,support=support,events=len(dz),
                    pairs=dz.pair_key.nunique(),buildings=dz.building.nunique(),
                    six_unique_geometry_events=int(dz.geometry_all_unique6.sum()),six_Q_and_geometry_events=int(dz.Q_geometry_joint6.sum()))
                for c in cols+["B8L2_extra"]:
                    row["pair_equal__"+c]=pair[c].mean();row["building_equal__"+c]=buildings[c].mean()
                for c in ["geometry_bev_mean_h_extra","geometry_top_mean_h_extra"]:
                    row["positive_pair_fraction__"+c]=pair[c].dropna().gt(0).mean();row["valid_pairs__"+c]=int(pair[c].notna().sum())
                overall.append(row)
        return pd.concat(pair_rows,ignore_index=True),pd.DataFrame(overall)
    with tempfile.TemporaryDirectory(prefix="manual_order_same_room_") as temporary:
        temporary=Path(temporary)
        for label,frame in [("automatic",original),("assisted",assisted)]:
            pairs,summary=calculate(frame)
            if label=="automatic":
                for name,result in [("GEOMETRY_PAIR_METRICS.csv.gz",pairs),("GEOMETRY_CONDITIONS.csv",summary)]:
                    path=temporary/name;result.to_csv(path,index=False)
                    checks+=compare_saved_table(root/"geometry_summary"/name,path)
            else:
                save(pairs,prefix+"GEOMETRY_PAIR_METRICS.csv.gz");save(summary,prefix+"GEOMETRY_CONDITIONS.csv")
        save(pd.DataFrame(checks),prefix+"BASELINE_PARITY.csv")
        # Full original event universe, projected to only fields actually read
        # by these two downstream scripts.  There is no endpoint re-evaluation.
        columns=set(conditions.CFG+history.METRICS+members.MET+members.KEY+[
            "event_id","ordinary_comparable","D_members","D_class_counts","X_members","Y_members","Z_members",
            "source_role_key","target_role_key","history_Q_block_range","Q_common6","target_n"])
        parts=[]
        for chunk in pd.read_csv(FULL_REGISTERED_SOURCE,usecols=lambda c:c in columns,chunksize=12000,low_memory=False):parts.append(chunk)
        full=pd.concat(parts,ignore_index=True)
        assert full.event_id.is_unique and len(full)==len(original)
        new_full=full.copy().set_index("event_id")
        replacements=read_csv(OUT/"frozen_registered/assisted/EVENT_Q_STRUCTURE_EFFECTS.csv.gz").set_index("event_id")
        for c in new_full:
            if c in replacements:new_full.loc[replacements.index,c]=replacements[c]
        new_full=new_full.reset_index()
        baseline_input=temporary/"automatic_events.csv.gz";full.to_csv(baseline_input,index=False)
        assisted_input=temporary/"assisted_events.csv.gz";new_full.to_csv(assisted_input,index=False)
        baseline_geometry=root/"geometry_summary/EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz"
        assisted_geometry=OUT/prefix/"EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz"
        baseline_history=temporary/"history";assisted_history=OUT/"frozen_registered/native_history_q"
        history.main(baseline_input,baseline_geometry,baseline_history)
        history.main(assisted_input,assisted_geometry,assisted_history)
        history_checks=[]
        for filename in ["HISTORY_Q_COMMON_SUPPORT_RESULTS.csv","HISTORY_Q_DOMAIN_SUPPORT.csv","HISTORY_Q_MATCHED_STRATA.csv.gz"]:
            history_checks+=compare_saved_table(root/"history_q"/filename,baseline_history/filename)
        save(pd.DataFrame(history_checks),"frozen_registered/native_history_q/BASELINE_PARITY.csv")
        baseline_members=temporary/"members";assisted_members=OUT/"frozen_registered/native_member_sensitivity"
        members.main(baseline_input,baseline_members)
        members.main(assisted_input,assisted_members)
        member_checks=[]
        for filename in ["MEMBER_SELECTION_AND_CAPACITY.csv","MEMBER_FOLD_ROLES.csv","MEMBER_MATCHED_STRATA.csv.gz","MEMBER_MATCHED_SUMMARY.csv"]:
            member_checks+=compare_saved_table(root/"sensitivity"/filename,baseline_members/filename)
        save(pd.DataFrame(member_checks),"frozen_registered/native_member_sensitivity/BASELINE_PARITY.csv")
    write_json("frozen_registered/INDIRECT_DEPENDENT_CHECKS.json",dict(full_registered_events=len(original),
        touched_registered_events=len(new),geometry_summary_reproduced=True,historical_Q_summary_reproduced=True,
        member_sensitivity_reproduced=True,source_history_and_candidate_worker_selection_unchanged=True,
        same_six_corner_support_preserved=bool(np.array_equal(boolean(original.geometry_all_unique6),boolean(assisted.geometry_all_unique6))),
        no_new_teams_or_fusion=True,no_classification_selection=True,original_sources_untouched=True))


def finalize_delivery():
    """Write reviewable conclusions, provenance and complete artifact checks."""
    source=REL/"same_room_current_results/large"
    summary=read_csv(OUT/"QUALITY_COMPONENT_REPETITION_SUMMARY.csv")
    support=read_csv(OUT/"SUPPORT_CHANGES.csv")
    geometry=read_csv(OUT/"geometry/CURRENT_SUPPORT.csv")
    labor=read_csv(OUT/"JOINT_RECORDED_LABOR_SUPPORT.csv")
    counterexamples=read_csv(OUT/"PAIR_COUNTEREXAMPLE_TRANSITIONS.csv")
    actual=read_csv(OUT/"ASSISTED_CURRENT_EVENTS.csv.gz")
    native_checks=json.loads((OUT/"frozen_registered/native_results/CHECKS.json").read_text())
    assert json.loads((OUT/"frozen_registered/INDIRECT_DEPENDENT_CHECKS.json").read_text())["full_registered_events"]==62964
    key_fields=["method_updated","n","m","updated_direction"]
    def result(method,contrast,version,n=10,direction="C2→C3"):
        z=summary[(summary.method_updated==method)&summary.n.eq(n)&summary.updated_direction.eq(direction)&summary.metric.eq("B8L2")&summary.contrast.eq(contrast)&summary.version.eq(version)]
        assert len(z)==1
        return z.iloc[0]
    k3_old={c:result("TARGET_DSTRUCT_K3",c,"automatic_original") for c in ["GA","GS","CB"]}
    k3_new={c:result("TARGET_DSTRUCT_K3",c,"assisted_expanded_support") for c in ["GA","GS","CB"]}
    allchanges=[]
    def changes(module,oldpath,newpath,keys):
        old=read_csv(oldpath);new=read_csv(newpath)
        assert not old.duplicated(keys).any() and not new.duplicated(keys).any()
        joined=old.merge(new,on=keys,suffixes=("_automatic","_assisted"),how="outer",validate="one_to_one")
        changed_rows=set()
        for field in old:
            if field in keys or field not in new or not pd.api.types.is_numeric_dtype(old[field]):continue
            a=pd.to_numeric(joined[field+"_automatic"],errors="coerce");b=pd.to_numeric(joined[field+"_assisted"],errors="coerce")
            changed=a.notna().ne(b.notna())|(a-b).abs().gt(1e-9)
            for index in joined.index[changed]:
                changed_rows.add(index)
                oldvalue,newvalue=a.loc[index],b.loc[index]
                allchanges.append(dict(module=module,keys=json.dumps(clean(joined.loc[index,keys].to_dict()),ensure_ascii=False,sort_keys=True),
                    field=field,automatic=oldvalue,assisted=newvalue,
                    difference_on_both_finite=(newvalue-oldvalue) if np.isfinite(oldvalue) and np.isfinite(newvalue) else np.nan,
                    support_transition="both_finite" if np.isfinite(oldvalue) and np.isfinite(newvalue) else "availability_changed",
                    original_source=oldpath.relative_to(ROOT).as_posix(),assisted_source=newpath.relative_to(ROOT).as_posix()))
        return old,new,joined,len(changed_rows)
    for name in ["OVERALL_CONDITIONS.csv","N_M_CONDITIONS.csv","DIRECTION_RESULTS.csv","LEAVE_ONE_BUILDING_OUT.csv","EXCLUDE_UNB_SPECIFIC.csv","DIFFICULTY_PAIR_CONDITIONS.csv"]:
        keys=["subset","method","condition"]
        if name=="N_M_CONDITIONS.csv":keys +=["n","m"]
        if name=="DIRECTION_RESULTS.csv":keys +=["source_role_key","target_role_key"]
        if name in ["LEAVE_ONE_BUILDING_OUT.csv","EXCLUDE_UNB_SPECIFIC.csv"]:keys +=["excluded_building"]
        if name=="DIFFICULTY_PAIR_CONDITIONS.csv":keys +=["difficulty_pair"]
        changes("registered_native:"+name,source/"results"/name,OUT/"frozen_registered/native_results"/name,keys)
    histories=changes("historical_Q_condition",source/"history_q/HISTORY_Q_COMMON_SUPPORT_RESULTS.csv",
        OUT/"frozen_registered/native_history_q/HISTORY_Q_COMMON_SUPPORT_RESULTS.csv",["method","condition","threshold","matching","metric"])
    members=changes("member_presence_absence",source/"sensitivity/MEMBER_MATCHED_SUMMARY.csv",
        OUT/"frozen_registered/native_member_sensitivity/MEMBER_MATCHED_SUMMARY.csv",["worker_id","matching"])
    changes("six_corner_geometry",source/"geometry_summary/GEOMETRY_CONDITIONS.csv",
        OUT/"frozen_registered/native_geometry_summary/GEOMETRY_CONDITIONS.csv",["subset","method","condition","support"])
    save(pd.DataFrame(allchanges),"DOWNSTREAM_NUMERIC_CHANGES.csv.gz")
    # Historical-Q domains are fixed by original historical Q, not outcome Q.
    histstrata=read_csv(source/"history_q/HISTORY_Q_MATCHED_STRATA.csv.gz")
    touched=read_csv(OUT/"frozen_registered/automatic/EVENT_Q_STRUCTURE_EFFECTS.csv.gz")
    cfg=["pair_key","building","groups","method","condition","source_class","target_class","source_role","target_role","n","m"]
    intersections=[]
    for keys,z in histstrata.groupby(["method","condition","threshold","matching"],dropna=False):
        joincols=cfg+(["D_members"] if keys[3]=="same_configuration_exact_D" else [])
        domain=z[joincols].drop_duplicates()
        hit=touched.merge(domain,on=joincols,validate="many_to_one")
        intersections.append(dict(zip(["method","condition","threshold","matching"],keys))|dict(
            matched_strata=len(domain),affected_registered_events=len(hit),event_ids="|".join(hit.event_id)))
    save(pd.DataFrame(intersections),"frozen_registered/native_history_q/AFFECTED_DOMAIN_INTERSECTION.csv")
    mjoin=members[2]
    qs=["matched_Q_strata","matched_Q_pairs","matched_Q_buildings","relevant_Q_events","Q_events_retained"]
    changed_support=np.any(np.column_stack([mjoin[c+"_automatic"].ne(mjoin[c+"_assisted"]) for c in qs]),axis=1)
    member_support=mjoin.loc[changed_support,["worker_id","matching",*[c+s for c in qs for s in ["_automatic","_assisted"]]]]
    save(member_support,"frozen_registered/native_member_sensitivity/SUPPORT_CHANGES.csv")
    member_sign_flips={}
    for field in ["matched_present_pair_equal__B8L2_extra","matched_absent_pair_equal__B8L2_extra"]:
        member_sign_flips[field]=int((mjoin[field+"_automatic"]*mjoin[field+"_assisted"]<0).sum())
    conclusions=[]
    def add(topic,judgment,old,new,claim,files,scope="current_same_room"):
        conclusions.append(dict(topic=topic,judgment=judgment,automatic=old,assisted=new,conclusion=claim,
            scope=scope,source_files="|".join(files),analysis_version="manual_order_same_room_auxiliary_20261104_v1"))
    add("24个同房端点的人工辅助连接","条件变化","24个原自动端点无Q","24个辅助端点均可评分",
        "仅固定节点后的连接方式改变；原自动失败结果保留。此为定向人工辅助条件，不代表一般自动修复能力。",
        ["ENDPOINT_BINDINGS_AND_SCORE_STATUS.csv","../endpoints/FIXED_INPUT_CHECKS.csv"])
    add("原共同支持上的质量变化","保持","1335个method行有六端Q","原支持1335个method行逐字段不变",
        "原可评事件没有获得逐事件Q改善；自动缺Q不按0分处理。所有扩展支持的均值差均为条件样本构成变化。",
        ["ORIGINAL_COMMON_SUPPORT_PARITY.csv","SUPPORT_CHANGES.csv"])
    add("K3 C2→C3 10/5六端质量支持","条件变化","295/322","318/322",
        "增加23个既有事件的六端共同Q支持，仍4个事件不可六端评分；19物理图对、7栋建筑的注册设计不变。",
        ["SUPPORT_CHANGES.csv","EVENT_SUPPORT_TRANSITIONS.csv.gz"])
    for contrast in ["GA","GS","CB"]:
        a,b=k3_old[contrast],k3_new[contrast]
        add("K3 C2→C3 10/5 "+contrast,"幅度变化",f"{a.pair_mean:.9f}",f"{b.pair_mean:.9f}",
            f"事件→XYZ块→物理图对等权；正均值图对仍为{int(b.positive_pairs)}/19。原共同支持上保持原值。",
            ["QUALITY_COMPONENT_REPETITION_SUMMARY.csv","PAIR_EFFECTS_BY_VERSION.csv.gz"])
    add("K3优势方向的同房重复","保持","CB正图对19/19；双视角同正18/19","CB正图对19/19；双视角同正18/19",
        "主要方向重复性结论保持；并非每个图对、每个视角和每个事件都改善。",
        ["PAIR_DIRECTION_STATES.csv","PAIR_COUNTEREXAMPLE_TRANSITIONS.csv"])
    add("K3跨视角幅度相关","幅度变化",f"Pearson {k3_old['CB'].pearson_r:.6f}; Spearman {k3_old['CB'].spearman_r:.6f}",
        f"Pearson {k3_new['CB'].pearson_r:.6f}; Spearman {k3_new['CB'].spearman_r:.6f}",
        "两种相关统计的变化方向不同；相关为共享房间的物理图对描述量，不作为独立房间推断或精确跨视角预测能力。",
        ["QUALITY_COMPONENT_REPETITION_SUMMARY.csv"])
    for method in ["TARGET_DSTRUCT_K2","RFUSE_GEOM_K2"]:
        a=result(method,"CB","automatic_original",direction="C1→C2");b=result(method,"CB","assisted_expanded_support",direction="C1→C2")
        s=support[support.method_updated.eq(method)&support.n.eq(10)].iloc[0]
        add(method+" 10/5","幅度变化",f"Q6 {s.automatic_common6}/{s.events}; CB {a.pair_mean:.9f}",f"Q6 {s.assisted_common6}/{s.events}; CB {b.pair_mean:.9f}",
            "沿用冻结分类与原图对权重。各方法支持不同，此结果不构成方法优劣的共同支持比较。",
            ["SUPPORT_CHANGES.csv","QUALITY_COMPONENT_REPETITION_SUMMARY.csv"])
    add("12/6与14/7人数条件","保持","人工端点命中0","人工端点命中0",
        "所有现有方法/方向中的12/6和14/7结果保持；不能把不同n/m图对集合的均值差解释为纯人数效应。",
        ["SUPPORT_CHANGES.csv","frozen_registered/native_results/N_M_CONDITIONS.csv"])
    add("K3 10/5共同几何可比支持","保持","240/322","240/322",
        "新增Q没有增加两视角六个AB/AC/BC全部唯一循环对应的事件。该支持上的角点距离数值保持；单位为相机高度h。",
        ["geometry/CURRENT_SUPPORT.csv","geometry/CURRENT_SUMMARY.csv"])
    add("局部角点对应状态","条件变化","61个有向端点对均缺连接","7个唯一循环候选；53个角点数不同；1个仍缺连接",
        "67条实际事件比较引用更新；局部获得对应不等同于六比较共同支持或语义结构完全对应。",
        ["geometry/ORDERED_PAIR_TRANSITIONS.csv","geometry/CHANGED_EVENT_COMPARISONS.csv.gz"])
    add("有限配比与成员重复性面板","保持","92342行精确键扫描，命中0","命中0，无重算",
        "PANEL_TEAM_LINKS没有实际端点交集，原有限配比面板及其成员重复性结果保持。",
        ["EXACT_DEPENDENCY_INTERSECTIONS.csv"])
    add("旧注册large原生全分母","幅度变化","62964事件；8198配置；744配对行","相同分母；39配置支持行、70汇总行更新",
        "8个实际受影响method/direction/n/m层共2646事件完整重聚合；其余配置原样保留。旧工作标签没有改称当前分类标签。",
        ["frozen_registered/native_results/CHECKS.json","frozen_registered/SOURCE_COVERAGE.json"],"registered_frozen_working_labels")
    add("历史Q接近条件比较","保持",f"{len(histories[0])}条结果",f"{len(histories[1])}条结果全部不变",
        "已真实回放原history_q消费者；受影响事件没有进入原近Q匹配条件域，近Q结论与其分母保持。",
        ["frozen_registered/native_history_q/HISTORY_Q_COMMON_SUPPORT_RESULTS.csv","frozen_registered/native_history_q/AFFECTED_DOMAIN_INTERSECTION.csv"],"registered_frozen_working_labels")
    add("注册成员出现/缺席敏感性","幅度变化","28名候选成员、56个匹配方式结果","8名成员相关16行数值/支持变化",
        "3个宽匹配成员行各增加1个可评匹配层；配对等权Q_extra在出现与缺席条件下均无正负号翻转。仍仅描述合法匹配子域，不能升级为普遍删人稳健性。",
        ["frozen_registered/native_member_sensitivity/MEMBER_MATCHED_SUMMARY.csv","frozen_registered/native_member_sensitivity/SUPPORT_CHANGES.csv"],"registered_frozen_working_labels")
    add("K3原反例集合","保持","4个诊断图对；S9h 10/19跨视角异号","原4个诊断图对仍在，异号图对保持",
        "原自动反例没有因辅助分支而删除。新增支持改变部分图对均值，但未消除主要K3方向反例。",
        ["PAIR_COUNTEREXAMPLE_TRANSITIONS.csv"])
    add("RFUSE VFua 01/04反例条件","条件变化","GA图对均值 -1.173653","GA图对均值 1.740118",
        "在辅助扩展支持中退出GA≤0诊断集；自动原支持上的反例仍保留，不能写作自动机制已修好。",
        ["PAIR_COUNTEREXAMPLE_TRANSITIONS.csv"])
    add("K3既有记录劳动联合支持","条件变化","时间六端226/322；QT六端201/322","时间六端226/322；QT六端222/322",
        "实际标注时间和语义不变，联合Q/时间样本扩大。共同原QT支持数值保持；扩展条件下时间比均值变化来自支持构成。",
        ["JOINT_RECORDED_LABOR_SUPPORT.csv","LABOR_PARITY.json"])
    add("人工辅助后的总成本效益","尚不能判断","人工排序用时未记录","不作0秒补值",
        "保留原记录劳动，人工排序耗时未知，因此不能据此声称人工辅助后的总劳动效率提高。",
        ["LABOR_PARITY.json","../endpoints/ENDPOINT_SCORES.csv"])
    save(pd.DataFrame(conclusions),"CONCLUSIONS.csv")

    source_paths=[BASE/"endpoints/ENDPOINT_SCORES.csv",BASE/"endpoints/ENDPOINTS.jsonl.gz",UP/"SAME_ROOM_HALF_EVENTS.csv.gz",
                  UP/"SAME_ROOM_HALF_PAIRS.csv",FULL_REGISTERED_SOURCE,REL/"same_room_current_large_design/STRICT_ABC_EVENTS.csv.gz",
                  REL/"same_room_current_extended_design/PANEL_TEAM_LINKS.csv.gz",REL/"pools/INPUT_SNAPSHOT.json"]
    source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    write_json("INPUTS_AND_VERSIONS.json",dict(analysis_version="manual_order_same_room_auxiliary_20261104_v1",data_release="v2.1",
        method_relation="original automatic experiment retained; fixed-node human-order auxiliary sensitivity branch",
        same_room_formula_version="SRLB_REBUILT_20261023_v1",current_label_context="image_difficulty_20261030 frozen labels; no refitting",
        reference_identity="team_key + reference_id + reference_version, checked against current pool",
        source_sha256=source_hashes,source_record_coordinates_modified=False,human_sorting_repeated=False))
    validations=[]
    for path in sorted(OUT.rglob("*.gz")):
        if path.name.endswith(".jsonl.gz"):
            count=0
            with gzip.open(path,"rt",encoding="utf8") as f:
                for line in f:
                    json.loads(line);count+=1
            columns=None;parser="JSONL all records + gzip EOF/CRC"
        else:
            count=0;columns=None
            for chunk in pd.read_csv(path,chunksize=10000,low_memory=False):
                count+=len(chunk)
                if columns is None:columns=len(chunk.columns)
                else:assert columns==len(chunk.columns)
            parser="CSV all rows + gzip EOF/CRC"
        validations.append(dict(file=path.relative_to(OUT).as_posix(),bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),records=count,columns=columns,parser=parser,complete_read=True))
    save(pd.DataFrame(validations),"ARTIFACT_VALIDATION.csv")
    checks=json.loads((OUT/"CHECKS.json").read_text())
    checks.update(analysis_version="manual_order_same_room_auxiliary_20261104_v1",complete=True,
        touched_current_physical_events=int(actual.loc[actual.manual_endpoint_touched,"event_id"].nunique()),
        registered_events=62964,full_registered_configuration_rows=8198,full_registered_summary_rows_updated=70,
        all_actual_same_room_consumers_completed=True,history_Q_results_unchanged=histories[3]==0,
        historical_Q_result_rows=len(histories[0]),member_candidate_workers=int(members[0].worker_id.nunique()),
        member_result_rows=len(members[0]),member_result_rows_changed=members[3],member_Q_extra_sign_flips=member_sign_flips,
        geometry_common_six_K3_10_5_automatic=240,geometry_common_six_K3_10_5_assisted=240,
        gzip_artifacts_fully_read=len(validations),all_gzip_crc_and_parsing_passed=True,
        original_automatic_and_human_auxiliary_distinguished=True,unavailable_automatic_Q_not_zero_imputed=True,
        directional_case_sample_not_general_automatic_repair_claim=True)
    write_json("CHECKS.json",checks)
    table="\n".join(f"| {c} | {k3_old[c].pair_mean:.6f} | {k3_new[c].pair_mean:.6f} | {int(k3_old[c].positive_pairs)}/19 → {int(k3_new[c].positive_pairs)}/19 |" for c in ["GA","GS","CB"])
    report=f'''# HOHONET v2.1 人工节点顺序：同房全链影响交付

## 结论

**当前主口径 TARGET_DSTRUCT_K3、C2→C3、n=10/m=5 的主要方向结论保持，但幅度与可评条件改变。** 六端Q共同支持从 **295/322 增至318/322**；19个物理图对的CB均值均为正、其中18个双视角同正，均保持。原来已经有六端Q的事件逐字段不变；下面的均值差来自原缺Q事件进入扩展支持，不是把原缺Q按0分算出的改善。六个角点比较全部可比的几何共同支持仍为 **240/322**，没有扩大。

这是一条单列的“固定节点、人工连接顺序辅助”敏感性分支。原自动实验、原自动失败和原工作分类标签全部保留。57组是定向案例；本同房分支实际命中24个端点，不能外推所有无环端点都可修复。

## 一、范围、绑定与方法关系

- 当前同房表有1621个按method/direction/n/m分开的记录行。人工端点命中54个方法行，但只涉及**23个实际物理事件**，不能把54当独立案例。K2、K3与RFUSE各用自身既有支持，不合并为一个方法排名。
- 原注册large设计完整保留**62964事件、8198配置、744个分层配对行**；24个端点被31事件引用34次。8个真正受影响的旧工作标签层共2646事件完整重聚合，39个配置支持行及70个原生总表、方向、n/m、留一建筑和难度行更新。
- 162个必要事件端点中，156个由原保存几何在精确v2.1参考下重新测量，6个复用保存的当前端点；不重新融合、不重新选队、不调整坐标。所有恢复Q、complete状态和参考绑定与当前保存事件相符，Q最大差为1.42×10⁻¹⁴。人工端点按`team_key + reference_id + reference_version`接入，未仅按图片名匹配。
- 完整原事件表曾因Git大文件分片未合成而缺少。最终使用19分片恢复并逐分片/总哈希验证的完整原文件，SHA-256为`75eb59f204a529c49a757b9e5d54b95fa6b0eafc2021fcfb26a9da0209491296`。`EXISTING_VALID_EVENT_SOURCE`只是较窄有效事件来源，不能替代完整注册分母；最终冻结表没有采用这个缩小分母。

来源：[端点绑定与状态](ENDPOINT_BINDINGS_AND_SCORE_STATUS.csv)、[恢复核查](SCALAR_RECOVERY_CHECKS.json)、[完整来源覆盖](frozen_registered/SOURCE_COVERAGE.json)、[版本与输入哈希](INPUTS_AND_VERSIONS.json)。

## 二、当前K3主结果：幅度变化，主要方向保持

当前权重严格沿用“事件→XYZ成员块→物理图对等权”。GA是相对于A的跨类绝对变化超出同类绝对变化的量；GS使用两条跨类边的平均绝对变化再减同类边；CB为C相对B的有符号质量差。表中Q为既有B8L2分数。

| 指标 | 原自动、原支持 | 辅助、扩展支持 | 正均值物理图对 |
|---|---:|---:|---:|
{table}

CB双视角同正仍为18/19。跨视角CB的Pearson相关由{k3_old['CB'].pearson_r:.6f}变为{k3_new['CB'].pearson_r:.6f}，Spearman由{k3_old['CB'].spearman_r:.6f}变为{k3_new['CB'].spearman_r:.6f}；两者变化方向不同。19图对覆盖7栋建筑，部分图对共享房间，故这些是描述相关，不能作为19个独立房间的推断或精确幅度预测证据。

新增23个可评事件分布于6个既有图对；没有新增图对。VFua 04/10的配对等权CB由25.215093变为17.414147，说明支持扩展甚至会降低已有图对的条件均值。它不构成任一原已可评事件Q下降。

其他当前条件中，K2的10/5支持630→653/738，CB均值9.985523→9.858661；RFUSE支持43→51/76，CB均值16.949216→17.569379。**12/6和14/7在全部已有方法/方向中均0命中，数值与支持保持。** 不用不同图对集合间的均值差推断纯人数效应。

来源：[各方法支持](SUPPORT_CHANGES.csv)、[质量和分项](QUALITY_COMPONENT_REPETITION_SUMMARY.csv)、[配对逐版本结果](PAIR_EFFECTS_BY_VERSION.csv.gz)、[原共同支持核验](ORIGINAL_COMMON_SUPPORT_PARITY.csv)。

## 三、连接可用、质量可评、几何可比是三个层次

同房24个辅助端点均能评分。原注册31个受影响事件的六端Q支持由0增至30；剩余1事件还含未在本次人工处理中的失败端点。当前主层新增23个Q完整事件，而几何共同支持240→240。跨视角六个AB/AC/BC比较要求全部获得原规则定义的唯一循环对应，不能只凭Q可评就填入距离。

实际只重算61个有向端点对，回接67条事件比较引用。原来它们均缺连接；辅助后7个有唯一循环对应候选、53个角点数不同、1个仍缺连接。这7个局部成功没有形成新的六比较完整事件。原几何共同支持上的距离结果保持；几何失败状态频率已更新。距离单位是相机高度**h**，不是米；唯一循环候选也不是语义结构完全一致的证明。

来源：[几何支持](geometry/CURRENT_SUPPORT.csv)、[有向对状态](geometry/ORDERED_PAIR_TRANSITIONS.csv)、[完整注册几何总表](frozen_registered/native_geometry_summary/GEOMETRY_CONDITIONS.csv)。

## 四、配比、成员、历史Q及劳动的实际下游

有限配比/成员重复性面板的`PANEL_TEAM_LINKS`共92342行，精确团队键交集为0，保留原结果。旧large注册成员出现/缺席消费者则有真实依赖，已按原代码、原候选名单和合法匹配域补算：仍为28名候选成员、56个“成员×匹配方式”结果，8名成员相关16行数值或支持改变；W104、W122、W126的宽匹配可评层数各增加1。出现与缺席条件下的配对等权Q_extra均无正负号翻转。严格exact-D匹配的主要条件对照保持，不能把宽匹配变化提升为普遍删人稳健性。

历史Q接近条件的原`history_q`消费者已经实际回放并对照原表；472条结果全部保持。人工受影响事件未进入原近Q匹配域。其历史Q选择变量及阈值2/5没有改变，近Q嵌套比较也不能解释为历史Q的因果贡献率。

K3主层记录劳动六端共同支持仍226/322；Q与记录劳动的六端联合支持201→222/322。原时间值、记录语义和缺失掩码保持。扩展支持上的CB记录时间比均值1.089381→1.084488，属于条件样本构成变化。**人工排序耗时没有记录，不填0秒，尚不能判断计入辅助劳动后的总成本效益。**

来源：[精确依赖交集](EXACT_DEPENDENCY_INTERSECTIONS.csv)、[成员支持变化](frozen_registered/native_member_sensitivity/SUPPORT_CHANGES.csv)、[成员完整结果](frozen_registered/native_member_sensitivity/MEMBER_MATCHED_SUMMARY.csv)、[历史Q域交集](frozen_registered/native_history_q/AFFECTED_DOMAIN_INTERSECTION.csv)、[劳动联合支持](JOINT_RECORDED_LABOR_SUPPORT.csv)。

## 五、反例与结论边界

K3主层的4个诊断图对仍保留；S9h 10/19的CB跨视角异号保持。RFUSE的VFua 01/04在辅助扩展支持中GA均值由-1.173653变为1.740118，退出GA≤0诊断集合；原自动、原支持的反例仍保留。这属于反例适用条件改变，不是删除原失败证据。

逐条判断见[CONCLUSIONS.csv](CONCLUSIONS.csv)，其中“保持、幅度变化、条件变化、尚不能判断”均附来源。需更新的原生精确数值集中在[下游数值变化](DOWNSTREAM_NUMERIC_CHANGES.csv.gz)。本分支不重新训练或选分类，不变更原团队成员、投票门槛、历史Q和记录劳动，不声称57个定向案例代表全部无环结果。

## 六、验证与复现

原当前主表的180个分项字段及64个分层配对行复现，最大误差1.42×10⁻¹⁴。31个受影响原生事件完整回放，相关数值最大误差1.85×10⁻¹²；原8198配置的受影响单元、744配对行及70个需更新汇总行均先复现再更新。原几何、历史Q和成员消费者也分别复现原表后才写辅助分支。全部{len(validations)}个gzip产物已读到EOF并完成CSV/JSONL解析与CRC核查，详见[ARTIFACT_VALIDATION.csv](ARTIFACT_VALIDATION.csv)。

复现入口：`python -m tools.thesis_main.analysis.evaluate_manual_order_same_room_20261104`。只重做交付核验与报告可用`--finalize-only`。首次从Git克隆时须先按v2.1 `LARGE_FILES.json`恢复完整原生事件表，并准备清单中已保存的原几何分片；脚本不会重新运行融合来替代这些冻结输入。所有新结果均位于本目录，原实验文件未覆盖。原native标签和公式版本在辅助产物中原样保留，方法关系由目录、[输入与版本清单](INPUTS_AND_VERSIONS.json)及本报告明确；这些产物不得无标记覆盖原自动结果。
'''
    (OUT/"REPORT_ZH.md").write_text(report,encoding="utf8")
    print(json.dumps(checks,ensure_ascii=False,indent=2),flush=True)


def main(prepare_only=False):
    original, automatic, old_endpoints = prepare_baseline()
    if prepare_only:
        print((OUT/"BASELINE_CHECKS.json").read_text())
        return
    updates = read_csv(BASE/"endpoints/ENDPOINT_SCORES.csv")
    old_endpoints, original_geometry = recover_automatic_endpoints(original)
    new_endpoints, ledger = merge_manual_endpoints(old_endpoints, updates)
    save(ledger, "ENDPOINT_BINDINGS_AND_SCORE_STATUS.csv")
    updated_keys = set(ledger.team_key)
    touched = original[all_team_columns(original)].isin(updated_keys).any(axis=1)
    design,requested,stored,native_results,native_checks=rebuild_affected_native(old_endpoints,new_endpoints,updated_keys)
    assert original.loc[touched,"event_id"].isin(requested.event_id).all(), "Affected current event absent from registered event rebuild"
    assisted_source=original.copy()
    outcome_columns=[c for c in native_results["assisted"] if c in original and c not in design]
    ids=original.loc[touched,"event_id"]
    for c in outcome_columns:
        assisted_source.loc[touched,c]=native_results["assisted"].loc[ids,c].to_numpy()
    assisted=derive_saved_frozen_events(assisted_source,frozen=False)
    automatic["manual_endpoint_touched"] = touched
    assisted["manual_endpoint_touched"] = touched
    for name, frame in [("automatic", automatic), ("assisted", assisted)]:
        frame["analysis_method_identity"] = "original_automatic" if name == "automatic" else "fixed_nodes_human_order_auxiliary"
        frame["data_release"] = "v2.1"
    common = automatic.Q_common6
    fields = [c for c in automatic if c in assisted and (c.startswith(tuple(METRICS)) or c in ["GA_a", "GA_b", "GS_a", "GS_b", "CB_a", "CB_b"]) and pd.api.types.is_numeric_dtype(automatic[c])]
    checks = [{"field": c, "events": int(common.sum()), "maximum_absolute_error": assert_numeric_equal(automatic.loc[common,c], assisted.loc[common,c], "common_support:"+c)} for c in fields]
    save(pd.DataFrame(checks), "ORIGINAL_COMMON_SUPPORT_PARITY.csv")
    scope = "current_image_difficulty_labels"
    support = support_table(automatic, assisted, scope)
    summary, pairs, buildings, directions = summarize_versions(automatic, assisted, scope)
    save(support, "SUPPORT_CHANGES.csv")
    save(summary, "QUALITY_COMPONENT_REPETITION_SUMMARY.csv")
    save(pairs, "PAIR_EFFECTS_BY_VERSION.csv.gz")
    save(buildings, "BUILDING_EFFECTS_BY_VERSION.csv.gz")
    save(directions, "PAIR_DIRECTION_STATES.csv")
    save(pair_counterexamples(pairs), "PAIR_COUNTEREXAMPLE_TRANSITIONS.csv")
    save(automatic, "AUTOMATIC_CURRENT_EVENTS.csv.gz")
    save(assisted, "ASSISTED_CURRENT_EVENTS.csv.gz")
    support_columns = [*GROUP, "building", "pair_key", "event_id", "manual_endpoint_touched", "Q_common6", "score_failure_fraction", "incomplete_fraction", *all_team_columns(automatic)]
    event_support = automatic[support_columns].rename(columns={"Q_common6":"automatic_common6", "score_failure_fraction":"automatic_score_failure_fraction", "incomplete_fraction":"automatic_incomplete_fraction"})
    event_support["assisted_common6"] = assisted.Q_common6
    event_support["assisted_score_failure_fraction"] = assisted.score_failure_fraction
    event_support["assisted_incomplete_fraction"] = assisted.incomplete_fraction
    event_support["newly_common6"] = ~automatic.Q_common6 & assisted.Q_common6
    save(event_support, "EVENT_SUPPORT_TRANSITIONS.csv.gz")
    frozen_result,frozen_support,frozen_automatic,frozen_assisted=frozen_registered(design,requested,stored,native_results,updated_keys)
    full_registered_summary_update(design,frozen_automatic,frozen_assisted)
    geometry_outputs=geometry_impact(automatic,assisted,frozen_automatic,frozen_assisted)
    for label,(ga,gh) in geometry_outputs.items():
        labor_and_history_dependents(ga,gh,"current_image_difficulty_labels" if label=="current" else "registered_frozen_working_labels", "" if label=="current" else "frozen_registered/")
    full_geometry_and_native_dependents()
    dependencies = dependency_inventory(set(updates.team_key))
    save(dependencies, "EXACT_DEPENDENCY_INTERSECTIONS.csv")
    if dependencies.loc[dependencies.module.eq("finite_composition_and_member_repetition"), "matched_rows"].iloc[0]:
        raise AssertionError("Unexpected finite-composition dependency requires actual recomputation")
    write_json("CHECKS.json", dict(current_events=len(original), current_method_direction_size_groups=len(support),
               applied_same_room_endpoints=len(ledger), touched_event_rows=int(touched.sum()),
               original_common_support_rows=int(common.sum()), original_common_support_values_unchanged=True,
               newly_common6_rows=int((~automatic.Q_common6 & assisted.Q_common6).sum()),
               endpoint_reference_and_version_exact=True, finite_composition_endpoint_intersection=0,
               methods_not_refit=True, original_data_not_modified=True,
               labor_unchanged_no_human_duration_imputed=True,
               note="Counts over working methods are not independent physical events; see method-specific support tables."))
    finalize_delivery()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--finalize-only", action="store_true")
    args=parser.parse_args()
    if args.finalize_only:finalize_delivery()
    else:main(args.prepare_only)
