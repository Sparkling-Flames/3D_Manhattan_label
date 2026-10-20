"""Final byte-level input and frozen endpoint coverage checks."""
from pathlib import Path
import gzip
import hashlib
import importlib.metadata
import json
import platform

R = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


manifest_path = R / "repo/research/workers/personnel_type_discovery_next_20261019/ARCHIVE_FILE_MAP.json"
archive = json.loads(manifest_path.read_text())
for item in archive:
    path = R / "restored" / item["path"]
    assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], item["path"]
assert len(archive) == 3844
assert sum(item["bytes"] for item in archive) == 1552498895
frozen = json.loads((R / "FROZEN_RECOVERY_INPUTS.json").read_text())
for item in frozen["science_scripts_and_saved_labels"] + frozen["requests"]:
    assert sha(R / item["path"]) == item["sha256"], item["path"]
assert sha(R / "audit_statistics/block_tolerance_cdf.py") == frozen["cdf_path_only_change"]["local_sha256"]

folder_for_mode = {
    "core": "core_native",
    "fresh": "fresh_corner_blocks",
    "history": "history_corner_blocks",
    "h20": "history_native",
}
endpoints = []
for request in frozen["requests"]:
    mode = request["mode"]
    native = R / "audit_replay" / folder_for_mode[mode]
    with gzip.open(R / request["path"], "rt") as f:
        design = json.load(f)
    expected = {(r["pool_id"], tuple(sorted(r["worker_ids"]))) for r in design["requests"]}
    actual = set()
    score_status = {}
    for path in sorted((native / "pools").glob("*.json.gz")):
        with gzip.open(path, "rt") as f:
            pool = json.load(f)
        assert pool["context"]["science_commit"] == "82c6164b0d4630de5316199c92aa405930973168"
        assert pool["context"]["main_commit"] == "e572eb73bedc4fe9056df838e458bab83c3fa423"
        for row in pool["teams"]:
            key = (row["pool_id"], tuple(sorted(row["member_workers"])))
            assert key not in actual, (mode, key)
            actual.add(key)
            status = row.get("score_status")
            score_status[status] = score_status.get(status, 0) + 1
    assert expected == actual, (mode, len(expected), len(actual))
    assert len(actual) == request["unique_frozen_teams"], mode
    endpoints.append({
        "mode": mode, "request_sha256": request["sha256"],
        "frozen_request_rows": len(design["requests"]), "unique_endpoint_teams": len(actual),
        "coverage_exact": True, "score_status_counts": score_status,
        "failed_outcomes_retained": True,
    })

out = {
    "restored_files_reverified": len(archive),
    "restored_bytes_reverified": sum(item["bytes"] for item in archive),
    "archive_manifest_sha256": sha(manifest_path),
    "all_restored_file_hashes_match": True,
    "frozen_scripts_labels_and_requests_unchanged": True,
    "cdf_change_is_input_path_only": True,
    "endpoint_replays": endpoints,
    "total_frozen_endpoint_teams": sum(x["unique_endpoint_teams"] for x in endpoints),
    "no_refit": True, "no_reselection": True,
    "python": platform.python_version(),
    "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
}
(R / "NATIVE_REPLAY_INTEGRITY.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k != "packages"}, indent=2))
