"""Restore the complete published event data, without rerunning research.

Canonical source rows are copied as strings to preserve the original scalar
representation and missing values. Every output is validated before an atomic
rename. Run ``--phase key`` for the first checkpoint; ``--phase full`` also
exports all event fields and absolute A/B/C endpoint measurements.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
EXPECTED = 12953
EVENT_SOURCE = STUDY / "analysis/ABC_ALL_COMPONENT_EVENTS.csv.gz"
DESIGN_SOURCE = STUDY / "composition/ABC_EVENTS.csv.gz"
SCALAR_SOURCE = STUDY / "composition/TEAMS_SCALARS.csv.gz"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def reader(path):
    op = gzip.open if str(path).endswith(".gz") else open
    return op(path, "rt", encoding="utf-8-sig", newline="")


def read_rows(path):
    with reader(path) as f:
        rows = csv.DictReader(f)
        fields = rows.fieldnames
        data = list(rows)
    assert len(fields) == len(set(fields)), (path, "duplicate header")
    assert all(None not in row and None not in row.values() for row in data), (path, "malformed row")
    return fields, data


def validate_csv(path, fields, expected_keys, key="event_id"):
    got = []
    with reader(path) as f:
        rows = csv.reader(f)
        assert next(rows) == fields, (str(path), "header mismatch")
        ki = fields.index(key)
        for line, row in enumerate(rows, 2):
            assert len(row) == len(fields), (str(path), line, len(row), len(fields))
            got.append(row[ki])
    assert got == expected_keys, (str(path), "ordered key mismatch", len(got), len(expected_keys))
    assert len(got) == len(set(got)), (str(path), "duplicate key")
    return {"path": str(path.relative_to(HERE)), "rows": len(got), "columns": len(fields),
            "bytes": Path(path).stat().st_size, "sha256": sha(path),
            "row_widths_valid": True, "ordered_keys_complete": True, "unique_keys": True}


def atomic_csv(path, fields, rows, expected_keys, key="event_id"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".pending")
    compressed = path.name.endswith(".gz")
    op = gzip.open if compressed else open
    with op(tmp, "wt", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    # Detection of compression uses the final suffix in reader().
    check_path = tmp
    if compressed:
        check_path = path.with_name(path.name + ".pending.gz")
        os.replace(tmp, check_path)
    result = validate_csv(check_path, fields, expected_keys, key)
    with check_path.open("rb") as f:
        os.fsync(f.fileno())
    os.replace(check_path, path)
    result["path"] = str(path.relative_to(HERE))
    return result


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".pending")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def members(text):
    return set(text.split("|")) if text else set()


def equal_scalar(a, b):
    if a == b:
        return True
    try:
        af, bf = float(a), float(b)
        return (math.isnan(af) and math.isnan(bf)) or math.isclose(af, bf, rel_tol=1e-12, abs_tol=1e-12)
    except ValueError:
        return False


def source_data():
    fields, rows = read_rows(EVENT_SOURCE)
    dfields, design = read_rows(DESIGN_SOURCE)
    assert len(rows) == EXPECTED and len({r["event_id"] for r in rows}) == EXPECTED
    assert [r["event_id"] for r in rows] == [r["event_id"] for r in design]
    for row, req in zip(rows, design):
        for field in dfields:
            assert row[field] == req[field], (row["event_id"], field, "design/source mismatch")
        s = members(row["common_background"])
        x, y, z = [members(row[f]) for f in ("outgoing_block_X", "same_count_block_Y", "changed_count_block_Z")]
        assert not (s & x or s & y or s & z)
        a, b, c = s | x, s | y, s | z
        assert len(a) == len(b) == len(c) == int(row["n"])
        assert len(a - b) == int(row["m_AB"])
        assert len(a - c) == int(row["m_AC"])
        assert len(b - c) == int(row["m_BC"])
        for arm, team in zip("ABC", (a, b, c)):
            row[f"{arm}_member_workers"] = "|".join(sorted(team))
        for pair, aa, bb in (("AB", a, b), ("AC", a, c), ("BC", b, c)):
            assert len(aa & bb) == int(row[f"overlap_{pair}"])
        assert row["composition_A"] == row["composition_B"]
        assert row["computed_all_arms"] == "True"
    return fields, rows


def key_phase(fields, rows):
    oldpath = STUDY / "report/ABC_EVENT_RESULTS_KEY.csv"
    oldfields, oldrows = read_rows(oldpath)
    ids = [r["event_id"] for r in rows]
    oldids = [r["event_id"] for r in oldrows]
    ix = {r["event_id"]: r for r in rows}
    mismatches = [(r["event_id"], c) for r in oldrows for c in oldfields
                  if not equal_scalar(r[c], ix[r["event_id"]][c])]
    assert not mismatches, mismatches[:10]
    extra = ["image_id", "reference_id", "reference_version", "registration_stage", "ABC_sampling",
             "labelled_pool_n", "formal_pool_n", "class_capacities", "composition_B",
             "overlap_AB", "overlap_AC", "overlap_BC", "new_block_YZ_overlap", "composition_turnover_AC",
             "A_member_workers", "B_member_workers", "C_member_workers",
             "A_score_status", "B_score_status", "C_score_status"]
    outfields = oldfields + [f for f in extra if f not in oldfields]
    result = atomic_csv(HERE / "ABC_EVENT_RESULTS_KEY_REPAIRED.csv", outfields, rows, ids)
    omitted = [r for r in rows if r["event_id"] not in set(oldids)]
    receipt = {
        "repair_stage": "key_table_complete",
        "source_event_rows": len(rows), "source_columns": len(fields),
        "old_published_rows": len(oldrows), "old_published_columns": len(oldfields),
        "old_is_exact_source_prefix": oldids == ids[:len(oldids)],
        "old_last_row_has_all_columns": True,
        "old_values_unchanged_with_float_serialization_tolerance_1e_12": True,
        "missing_rows_restored": len(omitted),
        "restored_by_layer": dict(Counter(r["layer"] for r in omitted)),
        "root_cause_evidence": "Published CSV was a complete-row prefix. Export directly wrote the final path and checked only source rows; no atomic publication or output row/event-set check existed. The specific historical interruption is not proven by available logs.",
        "no_fusion_or_scoring_rerun": True, "no_unknown_value_imputation": True,
        "sources": [{"path": str(p.relative_to(STUDY)), "sha256": sha(p)} for p in (EVENT_SOURCE, DESIGN_SOURCE, oldpath)],
        "outputs": [result],
    }
    atomic_json(HERE / "KEY_REPAIR_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    return receipt


def load_endpoints(rows):
    needed = {r[f"team_{a}"] for r in rows for a in "ABC"}
    found = {}
    with reader(SCALAR_SOURCE) as f:
        rd = csv.DictReader(f)
        scalar_fields = rd.fieldnames
        for r in rd:
            if r["team_key"] in needed:
                assert r["team_key"] not in found
                found[r["team_key"]] = r
    assert set(found) == needed, ("missing endpoints", len(needed - set(found)))
    for row in rows:
        for arm in "ABC":
            ep = found[row[f"team_{arm}"]]
            assert ep["member_workers"] == row[f"{arm}_member_workers"]
            assert ep["pool_id"] == row["pool_id"] and ep["k"] == row["n"]
            for f in ("B8L2", "D10", "nodes", "score_status"):
                assert equal_scalar(ep[f], row[f"{arm}_{f}"]), (row["event_id"], arm, f)
    return scalar_fields, found


def full_phase(fields, rows, receipt):
    scalar_fields, endpoints = load_endpoints(rows)
    ids = [r["event_id"] for r in rows]
    # Complete native endpoint records live in one normalized table. Every
    # endpoint scalar is also available inline in the full event table.
    eprows = [endpoints[k] for k in sorted(endpoints)]
    outputs = [atomic_csv(HERE / "ABC_ENDPOINTS_REFERENCED.csv.gz", scalar_fields, eprows,
                          [r["team_key"] for r in eprows], "team_key")]
    fullfields = fields + [f"{a}_member_workers" for a in "ABC"]
    fullfields += [f"endpoint_{a}__{f}" for a in "ABC" for f in scalar_fields]
    def enriched(selection):
        for row in selection:
            result = dict(row)
            for arm in "ABC":
                result.update({f"endpoint_{arm}__{f}": v for f, v in endpoints[row[f"team_{arm}"]].items()})
            yield result
    outputs.append(atomic_csv(HERE / "ABC_EVENT_RESULTS_COMPLETE.csv.gz", fullfields, enriched(rows), ids))
    shard_specs = [("MANUAL_ORDINARY", "ordinary_manual"), ("SEMI_ORDINARY", "ordinary_semi"),
                   ("MANUAL_DOORWAY", "doorway_manual")]
    for title, layer in shard_specs:
        subset = [r for r in rows if r["layer"] == layer]
        for i in range(0,len(subset),4000):
            shard=subset[i:i+4000]
            suffix=f"_PART{i//4000+1:02d}" if len(subset)>4000 else ""
            outputs.append(atomic_csv(HERE / f"ABC_EVENTS_{title}{suffix}_COMPLETE.csv", fullfields, enriched(shard),
                                      [r["event_id"] for r in shard]))
    assert sum(o["rows"] for o in outputs[2:]) == EXPECTED
    receipt.update({"repair_stage": "full_tables_complete", "complete_event_columns": len(fullfields),
                    "referenced_distinct_endpoints": len(endpoints),
                    "endpoint_join_all_arms_complete": True,
                    "endpoint_member_sets_and_scores_verified": True,
                    "outputs": receipt["outputs"] + outputs})
    receipt["sources"].append({"path": str(SCALAR_SOURCE.relative_to(STUDY)), "sha256": sha(SCALAR_SOURCE)})
    atomic_json(HERE / "FULL_REPAIR_RECEIPT.json", receipt)
    print(json.dumps({"phase": "full", "outputs": outputs, "endpoints": len(endpoints)}, ensure_ascii=False), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["key", "full"], default="key")
    args = ap.parse_args()
    fields, rows = source_data()
    initial=HERE/'ORIGINAL_INCOMPLETE_EXPORT_DIAGNOSIS.json'
    if initial.exists() and args.phase=='full':
        # The first batch may already be saved. Never overwrite it while
        # producing later independent batches, and preserve the initial fault.
        receipt=json.loads(initial.read_text(encoding='utf-8'))
        key_path=HERE/'ABC_EVENT_RESULTS_KEY_REPAIRED.csv'
        key_fields,_=read_rows(key_path)
        validate_csv(key_path,key_fields,[r['event_id'] for r in rows])
    else:
        receipt = key_phase(fields, rows)
    if args.phase == "full":
        full_phase(fields, rows, receipt)


if __name__ == "__main__":
    main()
