"""Extract, without rescoring, the frozen TARGET rows from original AC shards.

Run from any directory. With --download-missing only missing immutable source
shards are fetched. Existing source files must match the recorded Git blob.
The repository-relative source and original method/event IDs are retained.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import gzip
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = HERE / "raw_target_metrics"


def blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def one(meta: dict, download: bool) -> dict:
    path = REPO / meta["path"]
    data = path.read_bytes() if path.exists() else None
    origin = "existing_pinned_source"
    if data is None:
        if not download:
            raise FileNotFoundError(f"Missing source: {path}; use --download-missing")
        url = "https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/" + meta["commit"] + "/" + urllib.parse.quote(meta["path"], safe="/")
        for attempt in range(4):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "HOHONET-current-DSTRUCT-AC"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = response.read()
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)
        if blob(data) != meta["git_blob_sha1"]:
            raise ValueError("Downloaded source blob mismatch: " + meta["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".ac-final-download")
        temporary.write_bytes(data)
        temporary.replace(path)
        origin = "immutable_GitHub_source"
    if blob(data) != meta["git_blob_sha1"]:
        raise ValueError("Existing source blob mismatch; refusing replacement: " + meta["path"])
    target = OUT / (meta["pool_id"] + ".csv.gz")
    raw = pd.read_csv(path, low_memory=False)
    subset = raw.loc[raw["method"].eq("TARGET_DSTRUCT_K3")].copy()
    if subset["event_id"].duplicated().any():
        raise ValueError("Duplicate method event in source shard: " + meta["path"])
    subset["metric_source_path"] = meta["path"]
    subset["metric_source_commit"] = meta["commit"]
    compressed = gzip.compress(subset.to_csv(index=False).encode("utf-8"), mtime=0)
    temporary = target.with_name(target.name + ".writing")
    temporary.write_bytes(compressed)
    temporary.replace(target)
    return {**meta, "source_sha256": hashlib.sha256(data).hexdigest(),
            "source_rows": len(raw), "retained_target_rows": len(subset),
            "extract_path": str(target.relative_to(REPO)),
            "extract_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "retrieval": origin, "rescored_endpoints": 0, "new_fusions": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-missing", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "METRIC_SOURCE_MANIFEST.json").read_text())
    receipts = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(one, m, args.download_missing): m for m in manifest}
        for i, future in enumerate(cf.as_completed(futures), 1):
            receipts.append(future.result())
            if i % 10 == 0 or i == len(manifest):
                print(json.dumps({"completed_shards": i, "total_shards": len(manifest),
                                  "extracted_target_rows": sum(r["retained_target_rows"] for r in receipts)}), flush=True)
    receipts.sort(key=lambda r: r["pool_id"])
    pd.DataFrame(receipts).to_csv(HERE / "METRIC_EXTRACTION_RECEIPT.csv", index=False)
    combined = pd.concat([pd.read_csv(REPO / r["extract_path"], low_memory=False) for r in receipts], ignore_index=True)
    if combined["event_id"].duplicated().any():
        raise ValueError("Duplicate event across metric shards")
    target = HERE / "LEGACY_TARGET_METRICS_AUTOMATIC.csv.gz"
    temporary = target.with_name(target.name + ".writing")
    temporary.write_bytes(gzip.compress(combined.to_csv(index=False).encode("utf-8"), mtime=0))
    temporary.replace(target)
    check = {"status": "passed", "source_commit": manifest[0]["commit"],
             "shards": len(receipts), "source_bytes": sum(r["bytes"] for r in receipts),
             "retained_target_events": len(combined), "unique_event_ids": combined["event_id"].nunique(),
             "new_fusions": 0, "new_scores": 0}
    (HERE / "METRIC_EXTRACTION_CHECKS.json").write_text(json.dumps(check, indent=2))
    print(json.dumps(check), flush=True)


if __name__ == "__main__":
    main()
