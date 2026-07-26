"""Freeze the one-time HoHoNet PCA/whitening reference cache for Paper A C2-B."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.materialize_c2_task_risk import freeze_feature_reference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audit-threshold-manifest", type=Path, required=True)
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, or a torch device such as cuda:0")
    args = parser.parse_args()
    print(json.dumps(freeze_feature_reference(
        args.reference_dir, args.checkpoint, args.config, args.cache, args.manifest,
        device=args.device, audit_threshold_manifest=args.audit_threshold_manifest,
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
