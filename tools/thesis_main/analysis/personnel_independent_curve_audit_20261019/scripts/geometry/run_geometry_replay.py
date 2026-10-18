"""Replay Pro's frozen geometry audit into a separate output directory.

Run with PYTHONPATH pointing to the request-local runtime_deps (Shapely 2.1.2).
This re-executes the original scoring code; it is not an independent scoring
implementation and does not recreate acquisition or prior human decisions.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "extracted/work_v2_20261019/audit"))
import replay_geometry

replay_geometry.OUT = Path(__file__).resolve().parent
if __name__ == "__main__":
    replay_geometry.run()
