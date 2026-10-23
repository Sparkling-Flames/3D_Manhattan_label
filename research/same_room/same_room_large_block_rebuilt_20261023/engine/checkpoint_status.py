"""Summarize actual committed native shards without loading geometry caches."""
import argparse
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    args = parser.parse_args()
    output = Path(args.output)
    manifest_path = output / "REQUEST_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    rows = [json.loads(p.read_text()) for p in (output / "parts").glob("*/part_*.receipt.json")]
    pools = [json.loads(p.read_text()) for p in (output / "parts").glob("*/POOL_RECEIPT.json")]
    elapsed = time.time() - manifest_path.stat().st_mtime
    completed = sum(r["rows"] for r in rows)
    result = dict(requests=manifest["requests"], checkpointed=completed,
        fraction=completed / manifest["requests"], pools_complete=len(pools), pools_requested=manifest["pools"],
        shards=len(rows), score_available=sum(r["score_available"] for r in rows),
        failures_nonpolicy=sum(r["failures_nonpolicy"] for r in rows),
        complete=sum(r["complete"] for r in rows), scalar_bytes=sum(r["scalar_bytes"] for r in rows),
        geometry_bytes=sum(r["geometry_bytes"] for r in rows), wall_seconds_since_request_manifest=elapsed,
        completed_per_wall_second=completed / elapsed if elapsed > 0 else None,
        native_evaluation_seconds=sum(r["native_evaluation_seconds"] for r in rows),
        memory_current_bytes=int(Path("/sys/fs/cgroup/memory.current").read_text()),
        memory_limit_bytes=int(Path("/sys/fs/cgroup/memory.max").read_text()),
        status="completed_shards_only_not_partial_in_memory_teams")
    print(json.dumps(result, indent=2))
    (output / "CHECKPOINT_STATUS.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
