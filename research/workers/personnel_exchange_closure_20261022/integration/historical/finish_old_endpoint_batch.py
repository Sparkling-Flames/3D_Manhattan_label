"""Restore downloaded prior endpoint names after matching original SHA, per batch.

Only local bytes are handled. No remote writes, decompression, or scientific calls.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
WORK = ROOT.parent
HELPER_RUN = Path("/tmp/hohonet_closure_library_20261022")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", type=int)
    args = ap.parse_args()
    plan = pd.read_csv(HERE / "OLD_ENDPOINT_RESTORE_PLAN.csv", keep_default_na=False)
    current = plan.iloc[(args.batch - 1) * 20:args.batch * 20]
    receipt_path = HELPER_RUN / f"previous_endpoints_download_{args.batch:03d}_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    downloaded = {Path(p).name: Path(p) for p in receipt["files"]}
    assert len(downloaded) == len(current)
    restored = []
    for p in current.to_dict("records"):
        source = downloaded[p["library_name"]]
        manifest = json.loads(Path(p["archive_completion"]).read_text())
        kind = "scalars" if "SCALARS" in p["original_relative_path"] else "geometry"
        d = manifest[kind]
        assert source.stat().st_size == int(d["bytes"]) == int(p["archived_bytes"])
        got_sha = sha(source)
        assert got_sha == d["sha256"], (p["original_relative_path"], "SHA mismatch")
        dest = WORK / "source_recovery/previous_endpoints" / p["original_relative_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            assert sha(dest) == got_sha
        else:
            # Preserve the downloaded inode and Library identity without another
            # physical copy. The stable historical path has no collision suffix.
            os.link(source, dest)
        restored.append(dict(original_relative_path=p["original_relative_path"], batch_id=manifest["batch_id"],
                             local_path=str(dest), download_link=f"sandbox:{dest}", bytes=d["bytes"],
                             sha256=got_sha, rows=d["rows"], columns=d["columns"],
                             rows_source=p["archive_completion"], library_file_id=p["library_file_id"],
                             original_library_name=p["library_name"], original_library_path=p["library_path"],
                             downloaded_local_path=str(source), restoration_batch=args.batch,
                             compressed_bytes_match_original=True, scientific_calls=0))
    out = HERE / "OLD_ENDPOINT_RESTORED_FILES.csv"
    old = pd.read_csv(out, keep_default_na=False) if out.exists() else pd.DataFrame()
    result = pd.concat([old, pd.DataFrame(restored)], ignore_index=True).drop_duplicates("original_relative_path", keep="last").sort_values("original_relative_path")
    tmp = out.with_name(out.name + ".tmp")
    result.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, out)
    batch = dict(restoration_batch=args.batch, files=len(restored), bytes=sum(x["bytes"] for x in restored),
                 sha_matches=len(restored), decompressions=0, fusion_calls=0, scoring_calls=0,
                 remote_mutations=0, files_total_restored=len(result), bytes_total_restored=int(result.bytes.sum()))
    (HERE / f"OLD_ENDPOINT_RESTORE_BATCH_{args.batch:03d}.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(batch))


if __name__ == "__main__":
    main()
