"""Index the delivered Semi evidence; no scoring, fusion, or statistical search."""
from pathlib import Path
import hashlib
import json
import os
import pandas as pd

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run():
    requests = pd.read_csv(HERE / "EVENTS_REGISTERED_ALL.csv.gz", dtype=str, keep_default_na=False)
    events = pd.read_csv(HERE / "EVENTS_COMPLETE.csv.gz", dtype=str, keep_default_na=False)
    controls = pd.read_csv(HERE / "CONTINUOUS_QT_COMPLETE.csv.gz", dtype=str, keep_default_na=False)
    assert len(events) == 13882 and events.event_id.is_unique
    assert set(events.event_id) == set(requests.event_id)
    for k in ["pool_id", "team_A", "team_B", "team_C", "common_background", "outgoing_block_X",
              "same_count_block_Y", "changed_count_block_Z"]:
        assert events.set_index("event_id")[k].sort_index().equals(requests.set_index("event_id")[k].sort_index()), k
    keys = set(events.team_A) | set(events.team_B) | set(events.team_C) | set(controls.team_QT)
    source = json.loads((HERE / "ENDPOINT_KEY_RECONCILIATION.json").read_text())
    assert len(keys) == source["necessary_teams"] == 13777
    assert len(controls) == 886
    required = ["REPORT_ZH.md", "FIELD_GUIDE_AND_REPRODUCE_ZH.md", "EFFECTIVE_SEMI_CONDITIONS.csv",
                "EVENTS_COMPLETE.csv.gz", "CONTINUOUS_QT_COMPLETE.csv.gz", "CLASS_ROLES_AND_MEMBERS.csv",
                "FAILURE_AND_QUALITY_TAIL_COUNTS.csv", "METRIC_DENOMINATORS.csv",
                "mechanism_cases/CASE_EXPORT_RECEIPT.json"]
    assert all((HERE / x).exists() for x in required)
    rows = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or "completed_pools" in path.parts:
            continue
        if path.name.endswith(".tmp") or path.name in {"DELIVERY_RECEIPT.json", "FINAL_DELIVERY_FILE_INDEX.csv"}:
            continue
        rows.append(dict(relative_path=str(path.relative_to(HERE)), bytes=path.stat().st_size, sha256=sha(path),
                         role=("reproducible_code" if path.suffix == ".py" else "report_or_field_guide" if path.suffix == ".md"
                               else "scientific_figure" if path.suffix in [".png", ".pdf"] else "evidence_or_data")))
    index = pd.DataFrame(rows)
    index.to_csv(HERE / "FINAL_DELIVERY_FILE_INDEX.csv", index=False, encoding="utf-8-sig")
    receipt = dict(status="complete", underlying_data_version="v2", condition="Semi",
                   classification="inherited own-condition V3_JOINT_QT, outside-building labels",
                   events=len(events), event_columns=len(events.columns), event_ids_unique=True,
                   registered_members_and_teams_preserved=True, controls=len(controls), necessary_unique_endpoints=len(keys),
                   central_endpoints=13775, central_new=13724, central_reused=51, extra_prior_reused=2,
                   actual_total_reused=53, initial_registry_known_cache_hits=45, initial_requested_new=13732,
                   events_sha256=sha(HERE / "EVENTS_COMPLETE.csv.gz"), events_bytes=(HERE / "EVENTS_COMPLETE.csv.gz").stat().st_size,
                   controls_sha256=sha(HERE / "CONTINUOUS_QT_COMPLETE.csv.gz"),
                   file_index_sha256=sha(HERE / "FINAL_DELIVERY_FILE_INDEX.csv"), indexed_files=len(index),
                   main_oriented_events=13000, main_physical_ABC=6500,
                   completion_oriented_events=882, completion_physical_ABC=441,
                   all_class_configurations=631, registered_class_configurations=631,
                   complete_full_member_background_cells=8, theoretical_ordered_ABC=7081487700,
                   all_member_combinations_exhaustive=False,
                   mechanism_receipt=json.loads((HERE / "mechanism_cases/CASE_EXPORT_RECEIPT.json").read_text()),
                   packaging_note="Shared central endpoints and exact two prior compact rows required; no duplicate full old cache or originals. completed_pools are recovery checkpoints, merged complete table is canonical.")
    path = HERE / "DELIVERY_RECEIPT.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, path)
    print(json.dumps({k: receipt[k] for k in ["status", "events", "event_columns", "necessary_unique_endpoints", "indexed_files", "events_sha256"]}))


if __name__ == "__main__":
    run()
