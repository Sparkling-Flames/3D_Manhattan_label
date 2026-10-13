"""Check the frozen Task A module inventory and route/metric identities."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    module = args.root / "routing"
    manifest = load(module / "delivery_manifest.json")
    failures = []
    for entry in manifest["files"]:
        path = args.root / entry["path"]
        if not path.is_file():
            failures.append({"path": entry["path"], "error": "missing"})
            continue
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            failures.append({"path": entry["path"], "error": "content_changed"})
    if failures:
        print(json.dumps({"status": "failed", "failures": failures}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    routes = load(module / "results/routes.json")["rows"]
    metrics = load(module / "results/all_candidate_metrics.json")["rows"]
    lookup = {(row["record_id"], row["candidate_id"]): row for row in metrics}
    assert len(lookup) == len(metrics) == 798
    assert len(routes) == 429
    available = [row for row in routes if row["status"] == "available"]
    assert len(available) == 417
    for row in available:
        metric = lookup[row["record_id"], row["selected_candidate_id"]]
        for route_key, metric_key in [
            ("I_selected", "I"),
            ("Q_floor_selected", "Q_floor_baseline"),
            ("Q_full_selected", "Q_full_baseline"),
            ("selected_reference_version", "reference_version"),
            ("selected_reference_floor_sha256_canonical_v1", "reference_floor_sha256_canonical_v1"),
            ("current_points_sha256_canonical_v1", "current_points_sha256_canonical_v1"),
            ("input_version", "input_version"),
        ]:
            assert row[route_key] == metric[metric_key], (row["record_id"], route_key)
    assert all(row["selected_candidate_id"] is None for row in routes if row["status"] != "available")
    provenance = load(module / "results/run_provenance.json")
    assert provenance["input_sha256"] == hashlib.sha256((module / "inputs/prepared_input.json").read_bytes()).hexdigest()
    assert provenance["config_sha256"] == hashlib.sha256((module / "config.json").read_bytes()).hexdigest()
    print(json.dumps({
        "status": "passed", "manifest_files_verified": len(manifest["files"]),
        "records": len(routes), "routes_available": len(available),
        "routes_unavailable": len(routes) - len(available),
        "candidate_metrics": len(metrics), "route_metric_identity_check": "passed",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
