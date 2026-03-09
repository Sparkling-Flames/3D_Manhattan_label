"""Deprecated entrypoint.

The original implementation has been archived to:
  - tools/legacy/viz_quality_report.py

Prefer the notebook-first workflow:
  - tools/viz_quality_analysis.ipynb
  - tools/viz_quality_utils.py
  - tools/save_quality_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv=None) -> int:
    # Ensure repo root is importable when running:
    #   python tools/viz_quality_report.py ...
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from tools.legacy.viz_quality_report import main as legacy_main

    return legacy_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
