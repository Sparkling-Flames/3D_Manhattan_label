"""Build the corrected post-Block2 pack with authoritative building identities."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.data_prep import build_post_block2_analysis_pack_v3 as builder


if __name__ == "__main__":
    builder.OUT = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v4"
    builder.PACK_VERSION = "post_block2_analysis_pack_20260817_v4"
    builder.PACK_LABEL = "2026-08-17 v4"
    builder.PROVENANCE_SCHEMA = "post_block2_analysis_pack_provenance_v4"
    builder.MANIFEST_SCHEMA = "post_block2_artifact_hash_manifest_v4"
    raise SystemExit(builder.main())
