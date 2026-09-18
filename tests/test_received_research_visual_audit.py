"""Guard received evidence identity and condition links; no semantic-gold assertion."""
import csv
import gzip
import json
from pathlib import Path


def test_received_research_visual_audit():
    root = Path(__file__).resolve().parents[1]
    received = root / "analysis_results/full_corpus_research_received_20260918"
    audit = json.loads((received / "当前视觉复核.json").read_text(encoding="utf-8"))
    source = json.loads((root / "analysis_results/pro_cluster_review_20260918/data.json").read_text(encoding="utf-8"))
    cases = {c["code"]: c for c in source["cases"]}
    assert {c["code"] for c in audit["images"]} == set(cases)
    assert len(audit["images"]) == 39 and len(audit["pairs"]) == 29
    assert not audit["user_decisions_changed"] and not audit["pending_export_applied"]
    tables = {
        "key39": root / "analysis_results/cluster_visual_20260918_v2/results/memberships.csv",
        "full_corpus": received / "full_study_20260918/results/memberships.csv",
    }
    for name, path in tables.items():
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        lookup = {(r["code"], r["condition"], r["method"], r["worker"]): r for r in rows}
        assert len(lookup) == len(rows)
        for pair in audit["pairs"]:
            for worker, cid in zip(pair["workers"], pair["canonical_ids"]):
                matches = [r for r in cases[pair["code"]]["responses"] if r["worker_id"] == worker and r["raw_condition"] == pair["condition"]]
                assert len(matches) == 1 and matches[0]["canonical_annotation_id"] == cid
            for method, observed in pair["memberships_read_back"][name].items():
                a, b = [lookup[(pair["code"], pair["condition"], method, w)] for w in pair["workers"]]
                assert [a["id"], b["id"]] == pair["canonical_ids"]
                assert observed == {"same_cluster": a["cluster"] == b["cluster"], "cluster_a": a["cluster"], "cluster_b": b["cluster"]}
    b6 = audit["b6_22"]
    expected = [r for r in cases["B6ByNegPMKs-22"]["responses"] if r["main_worker_included"] and r["raw_condition"] == "semi"]
    assert b6["condition"] == "semi" and len(expected) == 24
    assert b6["canonical_ids"] == [r["canonical_annotation_id"] for r in expected]
    base = received / "full_study_20260918"
    def records(path):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return {r["canonical_annotation_id"]: r for r in map(json.loads, handle)}
    actual = records(base / "inputs/frozen/human/responses.jsonl.gz")
    approved = records(base / "model_snapshot/sop_sources/analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz")
    assert actual.keys() == approved.keys() and len(actual) == 2501
    for cid in actual:
        for field in ("effective_points_1024x512", "processing_status", "calculation_included", "imputed_point"):
            assert actual[cid][field] == approved[cid][field]
