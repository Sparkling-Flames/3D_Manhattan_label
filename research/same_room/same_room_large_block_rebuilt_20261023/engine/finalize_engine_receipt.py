"""Close out exact-team execution, including saved attempts and duplicate calls."""
from pathlib import Path
import gzip
import hashlib
import json
import pandas as pd

ENGINE = Path(__file__).resolve().parent
BASE = ENGINE.parent


def read(path):
    return json.loads(Path(path).read_text())


def truth(series):
    return series.astype(str).str.lower().eq("true")


def geometry_from_pointers(root, wanted):
    result = {}
    for shard, rows in wanted.groupby("geometry_shard"):
        own = set(rows.team_key)
        with gzip.open(root / shard, "rt", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if record["team_key"] in own:
                    result[record["team_key"]] = record
    return result


def main():
    native = BASE / "native_endpoints"
    geometry = BASE / "geometry"
    run = read(native / "RUN_RECEIPT.json")
    validated = read(native / "OUTPUT_VALIDATION.json")
    comparison = read(geometry / "COMPLETION.json")
    event_columns = ["event_id", "pool_id_a", "pool_id_b"] + [
        f"team_key_{arm}_{view}" for view in ("a", "b") for arm in ("A", "B", "C")]
    events = pd.read_csv(BASE / "design/STRICT_ABC_EVENTS.csv.gz", usecols=event_columns)
    event_count = len(events)
    if run["endpoint_rows"] != run["requests"] or validated["geometry_rows"] != run["requests"]:
        raise ValueError("Not all native requests have complete saved scalar/geometry rows")
    if comparison["event_results"]["rows"] != event_count * 6:
        raise ValueError("Missing exact event geometry comparisons")
    fields = ["team_key", "pool_id", "image", "building", "condition", "layer", "k", "B8L2", "D10", "score_status", "geometry_status", "score_available",
              "complete_evaluable", "score_failure_nonpolicy", "recorded_time_eligible", "repository_commit",
              "underlying_data_version", "geometry_shard", "member_workers", "member_object_ids", "time_source_kinds"]
    frame = pd.read_csv(native / "ENDPOINT_SCALARS.csv.gz", usecols=fields, low_memory=False)
    if frame.team_key.duplicated().any() or len(frame) != run["requests"]:
        raise ValueError("Native final scalar team keys/count differ")
    pool_by_team = frame.set_index("team_key").pool_id
    linked = set()
    for view in ("a", "b"):
        for arm in ("A", "B", "C"):
            keys = events[f"team_key_{arm}_{view}"]
            if not keys.map(pool_by_team).eq(events[f"pool_id_{view}"]).all():
                raise ValueError("An exact ABC event arm does not resolve to its registered pool")
            linked.update(keys)
    if linked != set(frame.team_key):
        raise ValueError("ABC team references and saved native exact teams differ")
    frame["Q_evaluable"] = frame.B8L2.notna()
    status_fields = ["score_status", "geometry_status", "complete_evaluable", "Q_evaluable", "recorded_time_eligible", "time_source_kinds"]
    counts = frame.groupby(["condition", "layer"] + status_fields, dropna=False).size().reset_index(name="endpoints")
    counts["all_attempts_denominator"] = len(frame)
    counts["fraction_of_all_attempts"] = counts.endpoints / len(frame)
    counts.to_csv(native / "ENDPOINT_STATUS_COUNTS.csv", index=False)
    marginal_tables = []
    for field in status_fields:
        part = frame.groupby(["condition", "layer", field], dropna=False).size().reset_index(name="endpoints")
        part = part.rename(columns={field: "state"})
        part.insert(2, "dimension", field)
        part["all_attempts_denominator"] = len(frame)
        part["fraction_of_all_attempts"] = part.endpoints / len(frame)
        marginal_tables.append(part)
    pd.concat(marginal_tables, ignore_index=True).to_csv(native / "ENDPOINT_STATUS_MARGINALS.csv", index=False)
    pool_frame = frame.assign(complete_flag=truth(frame.complete_evaluable),
                              nonpolicy_failure_flag=truth(frame.score_failure_nonpolicy),
                              recorded_time_flag=truth(frame.recorded_time_eligible))
    pool_counts = pool_frame.groupby(["pool_id", "image", "building", "condition", "layer"], dropna=False).agg(
        all_attempts=("team_key", "size"), Q_evaluable=("Q_evaluable", "sum"),
        complete_evaluable=("complete_flag", "sum"), score_failure_nonpolicy=("nonpolicy_failure_flag", "sum"),
        recorded_time_eligible=("recorded_time_flag", "sum")).reset_index()
    pool_counts["incomplete"] = pool_counts.all_attempts - pool_counts.complete_evaluable
    pool_counts["Q_evaluable_fraction"] = pool_counts.Q_evaluable / pool_counts.all_attempts
    pool_counts["incomplete_fraction"] = pool_counts.incomplete / pool_counts.all_attempts
    for field in ("score_status", "geometry_status"):
        detail = frame.groupby(["pool_id", field], dropna=False).size().unstack(fill_value=0)
        detail.columns = [field + "__" + ("MISSING" if pd.isna(value) else str(value)) for value in detail.columns]
        pool_counts = pool_counts.merge(detail.reset_index(), on="pool_id", validate="one_to_one")
    pool_counts.to_csv(native / "POOL_STATUS_COUNTS.csv", index=False)
    first = ENGINE / "first_complete_event"
    first_run = read(first / "native/RUN_RECEIPT.json")
    early = pd.read_csv(first / "native/ENDPOINT_SCALARS.csv.gz", low_memory=False)
    final_six = frame[frame.team_key.isin(early.team_key)]
    joined = early.merge(final_six, on="team_key", suffixes=("_early", "_formal"), validate="one_to_one")
    if len(joined) != 6:
        raise ValueError("Early complete event does not resolve to six formal exact teams")
    formal_geometries = geometry_from_pointers(native, final_six)
    early_geometries = geometry_from_pointers(first / "native", early)
    exact_rows = []
    for row in joined.to_dict("records"):
        key = row["team_key"]
        exact_rows.append(dict(team_key=key, B8L2_abs_difference=abs(row["B8L2_early"]-row["B8L2_formal"]),
            D10_abs_difference=abs(row["D10_early"]-row["D10_formal"]),
            same_geometry=early_geometries[key]["geometry"] == formal_geometries[key]["geometry"],
            same_full_state=early_geometries[key]["full_state"] == formal_geometries[key]["full_state"]))
    pd.DataFrame(exact_rows).to_csv(first / "EARLY_VS_FORMAL_REPETITION_CHECK.csv", index=False)
    smoke_run = read(ENGINE / "smoke/native_run/RUN_RECEIPT.json")
    standalone_calls = 1 if (ENGINE / "smoke/ONE_NATIVE_ENDPOINT.json.gz").exists() else 0
    compatibility_calls = smoke_run["new_native"] + standalone_calls
    formal_calls = run["new_native"]
    duplicate_advance_calls = first_run["new_native"]
    wrapper_hashes = {name: hashlib.sha256((ENGINE / name).read_bytes()).hexdigest() for name in (
        "native_team_runner.py", "compare_event_geometry.py", "finalize_engine_receipt.py", "read_exact_team.py")}
    if wrapper_hashes["native_team_runner.py"] != run["runner_sha256"]:
        raise ValueError("The saved native runner differs from the executed request manifest")
    receipt = dict(status="complete_actual_new_design_execution_not_restored_original",
        input_commit=run["repository_commit"], strict_abc_events=event_count, native_unique_requests=run["requests"],
        native_saved_attempts=len(frame), native_saved_geometry_state_rows=validated["geometry_rows"],
        native_pools=run["pools"], formal_native_calls_this_uninterrupted_run=formal_calls,
        compatibility_validation_native_calls=compatibility_calls, early_complete_event_duplicate_calls=duplicate_advance_calls,
        early_complete_event_additional_formal_unique_teams=0,
        total_recorded_native_calls=formal_calls + compatibility_calls + duplicate_advance_calls,
        scored=int(frame.B8L2.notna().sum()), complete=int(truth(frame.complete_evaluable).sum()),
        score_failures_nonpolicy=int(truth(frame.score_failure_nonpolicy).sum()),
        recorded_time_eligible=int(truth(frame.recorded_time_eligible).sum()),
        endpoint_state_count_table="native_endpoints/ENDPOINT_STATUS_COUNTS.csv",
        endpoint_state_marginal_table="native_endpoints/ENDPOINT_STATUS_MARGINALS.csv",
        pool_state_count_table="native_endpoints/POOL_STATUS_COUNTS.csv",
        endpoint_state_denominator="all unique native attempts in this frozen design; not event references",
        orchestration_code_sha256=wrapper_hashes,
        event_geometry_comparison_rows=comparison["event_results"]["rows"],
        unique_ordered_geometry_comparisons=comparison["unique_pairs"]["rows"],
        scalar_fields=validated["scalar_fields"], native_geometry_shards=validated["shards"],
        all_native_and_geometry_csv_gzip_read_to_eof=validated["all_gzip_read_to_eof"] and comparison["event_results"]["all_gzip_read_to_eof"] and comparison["unique_pairs"]["all_gzip_read_to_eof"],
        exact_requests_members_object_ids_geometry_associations_checked=validated["exact_requests_members_object_ids_geometry_associations_checked"],
        all_six_abc_team_references_and_registered_pools_checked=True,
        unreferenced_native_unique_teams=0,
        early_vs_formal_same_geometry=all(r["same_geometry"] for r in exact_rows),
        early_vs_formal_same_full_state=all(r["same_full_state"] for r in exact_rows),
        early_vs_formal_max_score_abs_difference=max(max(r["B8L2_abs_difference"], r["D10_abs_difference"]) for r in exact_rows),
        scientific_main_data_unique_scope="unique exact requests in this new design, not a claim that all keys were absent from all historical repository tables",
        final_zip_validation="The delivery packager must also read the archive's internal gzip members to EOF; these receipts cover the actual generated gzip files.")
    (BASE / "EXECUTION_COMPLETION.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
