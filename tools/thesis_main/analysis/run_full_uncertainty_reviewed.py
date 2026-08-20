"""Run the reviewed materializer with bounded deterministic resampling."""
from __future__ import annotations

import argparse
from pathlib import Path

from tools.thesis_main.analysis import full_uncertainty_reviewed as reviewed
from tools.thesis_main.analysis.materialize_full_uncertainty_data_mining_v2 import DEFAULT_OUT, materialize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    reviewed.worker_viewpoint_stability.__kwdefaults__["permutations"] = 2000
    reviewed._permutation_variance.__kwdefaults__["permutations"] = 2000
    reviewed._split_half_reliability.__kwdefaults__["repetitions"] = 1000
    materialize(args.output_dir.resolve())


if __name__ == "__main__":
    main()
