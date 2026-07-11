"""Preserve partial M4.1.2 artifacts and materialize its closure review."""
from __future__ import annotations

import json
from pathlib import Path

from tools.paper_a_manhattan import run_m_anchor_4_1_2_visible_range_footprint_sensitivity_review as base
from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_m_anchor_1_3741 import _anchor_constraints, _load_anchor_sidecar, _write_text_lf
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import M1_AUDIT_PATH

OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1_2_1")
REVIEW_OUT_DIR = Path("analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4_1_2_1")


def run(out_dir: Path = OUT_DIR, review_out_dir: Path = REVIEW_OUT_DIR):
    paths = base.run(out_dir, review_out_dir)
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    stage_d = [row for row in audit["review_candidates"] if row["search_stage"] == "D"]
    audit["review_candidates"] = [row for row in audit["review_candidates"] if row["search_stage"] != "D"]
    doc = base.m._load(base.CONSTRAINTS_PATH)
    before = json.loads(M1_AUDIT_PATH.read_text(encoding="utf-8"))
    before = next(row for row in before["solver_prototypes"] if row["candidate_id"] == audit["baseline_candidate"])["corrected_coordinates"]
    anchors = _anchor_constraints(_load_anchor_sidecar())
    cores = [("s4", value, {4: {"x": value, "bottom_y": 0}, 9: {"x": 0, "bottom_y": 0}, 10: {"x": 0, "bottom_y": 0}}) for value in (-0.15, -0.30, -0.40)]
    cores += [("s9", value, {4: {"x": 0, "bottom_y": 0}, 9: {"x": value, "bottom_y": 0}, 10: {"x": 0, "bottom_y": 0}}) for value in (-0.15, -0.30, -0.50, -1.00)]
    visibility = []
    for index, (pair, value, core) in enumerate(cores, start=1):
        row = base._candidate(9000 + index, "D", doc, core, (), before, anchors)
        row["candidate_id"] = f"m_anchor_4_1_2_1_visibility_{pair}_{abs(value):.2f}".replace(".", "_")
        row.update(candidate_kind="directional_visibility_slice", visibility_slice=True, review_bucket="visibility_only", sensitivity_only=True, final_refinement_eligible=False, m_anchor_4_2_input_eligible=False)
        visibility.append(row)
    for row in stage_d:
        row.update(candidate_kind="stage_d_search_sensitivity", visibility_slice=False, review_bucket="stage_d_sensitivity_only", sensitivity_only=True, final_refinement_eligible=False, m_anchor_4_2_input_eligible=False)
    visibility = [*stage_d, *visibility]
    audit.update(schema_version="m_anchor_4_1_2_1_closure_audit_v1", stage_id="M-Anchor.4.1.2.1", source_stage="M-Anchor.4.1.2", preserves_source_artifacts=True, visibility_candidates=visibility)
    _write_text_lf(paths["audit"], json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(paths["cards"], "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in [*audit["review_candidates"], *visibility]))
    _write_text_lf(paths["summary"], "# M-Anchor.4.1.2.1\n\nStage D and directional visibility slices are sensitivity-only, not final refinements, and cannot enter M4.2.\n")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8")); manifest["candidates"] = [row for row in manifest["candidates"] if not row.get("sensitivity_only")]
    manifest.update(schema_version="m_anchor_4_1_2_1_closure_review_bridge_v1", case_name="task218_ann3741_m_anchor_4_1_2_1", stage_id="M-Anchor.4.1.2.1", source_stage="M-Anchor.4.1.2", preserves_source_artifacts=True)
    manifest["visibility_candidates"] = [{"candidate_id": row["candidate_id"], "family": "m_anchor_4_1_2_visible_range" if row["candidate_kind"] == "stage_d_search_sensitivity" else "m_anchor_4_1_2_1_directional_visibility", "candidate_kind": row["candidate_kind"], "visibility_slice": row["visibility_slice"], "review_bucket": row["review_bucket"], "decision_class": row["candidate_class"], "coordinate_changes": row["coordinate_changes"], "sensitivity_only": True, "final_refinement_eligible": False, "requires_explicit_human_visual_verdict": True, "direct_ls_trial_allowed": False, "m_anchor_4_2_input_eligible": False, "accepted": False, "annotation_writeback": False} for row in visibility]
    _write_text_lf(paths["manifest"], json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    paths.update({f"review_{key}": value for key, value in run_local_review(input_path=paths["manifest"], candidate_json=paths["manifest"], candidate_limit=len(manifest["candidates"]) + len(visibility), out_dir=review_out_dir, image_root=Path("data/mp3d_layout/img_v"), case_name=manifest["case_name"], width=1024, height=512, coordinate_mode="ls_percent", local_server_root=base.m._local_server_root(review_out_dir)).items()})
    slices = {"schema_version": "m_anchor_4_1_2_1_directional_visibility_slices_v1", "stage_id": "M-Anchor.4.1.2.1", "audit_only": True, "not_solver_candidates": True, "m_anchor_4_2_input_eligible": False, "slice_mode": "pure_single_variable", "s4_x": [-0.15, -0.30, -0.40], "s9_x": [-0.15, -0.30, -0.50, -1.00], "directional_visibility_candidate_ids": [row["candidate_id"] for row in visibility if row["visibility_slice"]], "stage_d_candidate_ids": [row["candidate_id"] for row in visibility if not row["visibility_slice"]], "same_baseline": audit["baseline_candidate"]}
    slice_path = out_dir / "m_anchor_4_1_2_1_directional_visibility_slices.json"
    _write_text_lf(slice_path, json.dumps(slices, ensure_ascii=False, indent=2) + "\n")
    return {**paths, "visibility_slices": slice_path}


if __name__ == "__main__": print(run()["audit"])
