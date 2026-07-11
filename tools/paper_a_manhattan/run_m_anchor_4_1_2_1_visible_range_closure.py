"""Preserve partial M4.1.2 artifacts and materialize its closure review."""
from __future__ import annotations

import json
from pathlib import Path

from tools.paper_a_manhattan import run_m_anchor_4_1_2_visible_range_footprint_sensitivity_review as base
from tools.paper_a_manhattan.run_m_anchor_1_3741 import _write_text_lf

OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1_2_1")
REVIEW_OUT_DIR = Path("analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4_1_2_1")


def run(out_dir: Path = OUT_DIR, review_out_dir: Path = REVIEW_OUT_DIR):
    paths = base.run(out_dir, review_out_dir)
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    slices = {"schema_version": "m_anchor_4_1_2_1_directional_visibility_slices_v1", "audit_only": True, "not_solver_candidates": True, "m_anchor_4_2_input_eligible": False, "s4_x": [-0.15, -0.30, -0.40], "s9_x": [-0.15, -0.30, -0.50, -1.00], "same_baseline": audit["baseline_candidate"]}
    slice_path = out_dir / "m_anchor_4_1_2_directional_visibility_slices.json"
    _write_text_lf(slice_path, json.dumps(slices, ensure_ascii=False, indent=2) + "\n")
    return {**paths, "visibility_slices": slice_path}


if __name__ == "__main__": print(run()["audit"])
