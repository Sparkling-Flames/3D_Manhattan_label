import csv

from tools.thesis_main.analysis.materialize_routing_component_evidence import materialize


def _csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def test_missing_c2b_is_explicitly_pending_and_cannot_enter_full(tmp_path):
    raw, integrity, c1 = (tmp_path / name for name in ("raw.csv", "integrity.csv", "c1.csv"))
    key = {"worker_id": "w1", "component_family": "undercoverage"}
    _csv(raw, [{**key, "effect": ".2"}])
    _csv(integrity, [{**key, "p1_integrity_eligible": "true", "support_count": "4"}])
    _csv(c1, [{**key, "c1_predictive_validated": "true", "direction_consistent": "true",
               "leave_one_task_out_stable": "true", "leave_one_block_out_stable": "true",
               "routing_activation_allowed": "true", "effect": ".1"}])
    audit = materialize(raw, integrity, c1, tmp_path / "out", profile_version="p1")
    with (tmp_path / "out" / "routing_component_evidence.csv").open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert audit["n_full_component_eligible"] == 0
    assert row["evidence_status"] == "pending_c2b_confirmation"
    assert row["full_component_eligible"] == "False"
