#!/usr/bin/env python3
"""Fetch only explicitly named Release PNG members with the archived extractor.

No ZIP-wide fallback and no search-based substitute image is permitted.  The
original bytes, indexed ZIP member CRC and the retrieved SHA are retained.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCES = ROOT / "research/workers/personnel_composition_study_20261019/analysis/visual_sources"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image-id", action="append", required=True)
    p.add_argument("--out", type=Path, default=HERE / "originals")
    args = p.parse_args()
    ids = sorted(set(args.image_id))
    if len(ids) > 8:
        raise ValueError("This small-case extractor accepts at most 8 selected images per call")
    spec = importlib.util.spec_from_file_location("archived_range_zip", SOURCES / "range_zip.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    meta = json.loads((SOURCES / "release_metadata.json").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    module.extract(meta, SOURCES / "zip_directories.json", SOURCES / "release_IMAGE_INDEX.csv", ids, args.out)
    extracted = json.loads((args.out / "extraction_manifest.json").read_text())
    receipt = {
        "schema": "selected_original_photos_20261021_v1",
        "requested_image_ids": ids,
        "release_tag": meta["tag_name"], "release_url": meta["html_url"],
        "extractor_source": str((SOURCES / "range_zip.py").relative_to(ROOT)),
        "extractor_sha256": hashlib.sha256((SOURCES / "range_zip.py").read_bytes()).hexdigest(),
        "index_sha256": hashlib.sha256((SOURCES / "release_IMAGE_INDEX.csv").read_bytes()).hexdigest(),
        "members": extracted,
        "images_edited": False,
        "verification": "Member CRC32 and original size checked; local SHA receipt is not an independent publisher checksum unless indexed_sha256_verified is true",
    }
    (args.out / "PHOTO_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
