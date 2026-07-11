"""M-Anchor.4.1.3: occlusion-aware, expert-side footprint diagnostics only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from tools.paper_a_manhattan import run_m_anchor_4_1_1_staged_micro_compensation_probe as geometry
from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_m_anchor_1_3741 import ANCHOR_SIDECAR_PATH, SAFETY, _anchor_audit, _anchor_constraints, _by_source, _load, _load_anchor_sidecar, _sha, _write_text_lf
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import M1_AUDIT_PATH, M2_VERDICT_PATH
from tools.paper_a_manhattan.segment_aware_manhattan_refit import VERIFIED_ORDER_SOURCE_IDS

OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1_3")
REVIEW_DIR = Path("analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4_1_3")
SOURCE_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1_2_1")
SOURCE_CARDS = SOURCE_DIR / "m_anchor_4_1_2_candidate_cards.jsonl"
SOURCE_AUDIT = SOURCE_DIR / "m_anchor_4_1_2_visible_range_audit.json"
SAFETY_413 = {**SAFETY, "final_refinement_eligible": False, "m_anchor_4_2_input_eligible": False, "m_anchor_4_2_height_completion_authorized": False, "requires_explicit_human_visual_verdict": True}


def _variable(evidence="not_reviewed", role="unassigned", *, confidence="not_assessed", reason="not reviewed in M-Anchor.4.1.3", direction=None, bracket=None, sensitivity=None, observations=None, authorized=False):
    return {"evidence": evidence, "solver_role": role, "confidence": confidence, "reason": reason, "preferred_direction": direction, "preferred_delta_range": bracket, "sensitivity_only_range": sensitivity, "sensitivity_observations": observations or [], "exact_target_resolved": False, "current_stage_authorized": authorized}


def _evidence() -> dict[str, Any]:
    pairs = []
    for sid in VERIFIED_ORDER_SOURCE_IDS:
        pair = {"source_pair_id": sid, "solver_position": VERIFIED_ORDER_SOURCE_IDS.index(sid) + 1, "identity_status": "not_reviewed", "existence_status": "not_reviewed", "order_status": "not_reviewed", "keep_distinct": "not_reviewed", "compensation_allowed": False, "top_endpoint_visibility": "not_reviewed", "bottom_endpoint_visibility": "not_reviewed", "variables": {"pair_x": _variable(), "top_y": _variable(), "bottom_y": _variable()}}
        pairs.append(pair)
    by = {row["source_pair_id"]: row for row in pairs}
    for sid in (3, 7):
        row = by[sid]; row.update(identity_status="confirmed", existence_status="confirmed", order_status="confirmed", keep_distinct="confirmed", compensation_allowed=True, top_endpoint_visibility="unobservable", bottom_endpoint_visibility="unobservable")
        row["variables"]["pair_x"] = _variable("unobservable", "latent_completion", confidence="inferred_from_verified_order", reason="both endpoints occluded; identity/order confirmed independently", authorized=sid == 3)
        row["variables"]["bottom_y"] = _variable("unobservable", "latent_completion", confidence="inferred_from_verified_order", reason="both endpoints occluded; constrained footprint completion", authorized=True)
        row["variables"]["top_y"] = _variable("unobservable", "latent_completion_but_future_height_only", confidence="inferred_from_verified_order", reason="future height-only variable; unauthorized in M4.1.3")
    observations = {4: ["-0.15 barely visible", "-0.30 light micro-adjustment", "-0.40 clear micro-adjustment; not automatically more correct"], 9: ["-0.15 barely visible", "-0.30 light micro-adjustment", "-0.50 clear micro-adjustment", "-1.00 strong sensitivity displacement only"], 10: ["+0.50 is the C1976 reasonable reference", "+0.60 to +0.80 require visual review", "+1.00 is overshoot control only"]}
    for sid, direction, bracket, sensitivity in ((4, "left", [-0.40, 0.0], [-0.15, -0.30, -0.40]), (9, "left", [-1.0, 0.0], [-0.15, -0.30, -0.50, -1.0]), (10, "right", [0.50, 0.80], [0.50, 0.60, 0.70, 0.80, 1.0])):
        row = by[sid]; row.update(identity_status="confirmed", existence_status="confirmed", order_status="confirmed", keep_distinct="confirmed", compensation_allowed=sid == 10, top_endpoint_visibility="not_reviewed", bottom_endpoint_visibility="not_reviewed")
        row["variables"]["pair_x"] = _variable("visible_weak", "soft_anchor", confidence="human_review", reason="direction supported; original position already reasonable", direction=direction, bracket=bracket, sensitivity=sensitivity, observations=observations[sid], authorized=sid == 10)
    return {"schema_version": "expert_point_evidence_sidecar_v1", "case_name": "task218_ann3741", "source_annotation_id": 3741, "coordinate_space": "ls_percent", "source_stage": "M-Anchor.4.1.2.1", "reviewer": "human_expert", "review_context": {"width": 1024, "height": 512, "point_radius_at_review": 0.35, "image_evidence_quality": "blurred", "point_size_measurement": "visual_approximation_not_precise_measurement"}, "pairs": pairs}


def _validate_evidence(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != "expert_point_evidence_sidecar_v1" or doc.get("case_name") != "task218_ann3741" or doc.get("source_annotation_id") != 3741 or doc.get("coordinate_space") != "ls_percent": raise ValueError("invalid evidence identity")
    pairs = doc.get("pairs", []); ids = [row.get("source_pair_id") for row in pairs]
    if ids != list(VERIFIED_ORDER_SOURCE_IDS) or len(set(ids)) != len(ids): raise ValueError("evidence order or pair identity mismatch")
    allowed_evidence = {"visible_clear", "visible_weak", "occluded_but_inferred", "unobservable", "not_reviewed"}; allowed_roles = {"hard_anchor", "soft_anchor", "latent_completion", "latent_completion_but_future_height_only", "unresolved", "unassigned"}; allowed_status = {"confirmed", "ambiguous", "not_reviewed"}
    for row in pairs:
        if row["solver_position"] != VERIFIED_ORDER_SOURCE_IDS.index(row["source_pair_id"]) + 1: raise ValueError("solver position is not derived from verified order")
        if any(row[name] not in allowed_status for name in ("identity_status", "existence_status", "order_status", "keep_distinct")): raise ValueError("unknown pair-status enum")
        if row["top_endpoint_visibility"] not in allowed_evidence or row["bottom_endpoint_visibility"] not in allowed_evidence: raise ValueError("unknown endpoint visibility enum")
        if row["identity_status"] != "confirmed" and row["compensation_allowed"]: raise ValueError("unconfirmed identity cannot compensate")
        for name in ("pair_x", "top_y", "bottom_y"):
            value = row["variables"][name]
            if value["evidence"] not in allowed_evidence or value["solver_role"] not in allowed_roles: raise ValueError("unknown evidence enum")
            if value["solver_role"] == "latent_completion" and (row["identity_status"] != "confirmed" or row["order_status"] != "confirmed"): raise ValueError("latent completion lacks confirmed identity/order")
            if value["solver_role"] == "latent_completion" and name == "pair_x" and {row["top_endpoint_visibility"], row["bottom_endpoint_visibility"]} != {"unobservable"}: raise ValueError("pair_x latent completion requires both endpoints unobservable")
            if value["solver_role"] == "latent_completion" and name == "bottom_y" and row["bottom_endpoint_visibility"] != "unobservable": raise ValueError("bottom_y latent completion requires hidden bottom endpoint")
            if name == "top_y" and value["current_stage_authorized"]: raise ValueError("top_y is unauthorized in M4.1.3")
            if value["solver_role"] == "unresolved" and row["compensation_allowed"]: raise ValueError("unresolved variable cannot compensate")
            if value["current_stage_authorized"] and not row["compensation_allowed"]: raise ValueError("unauthorized pair variable")


def _tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8")); digest.update(path.read_bytes())
    return digest.hexdigest()


def _validate_s10_cards(cards: list[Mapping[str, Any]], components: Mapping[tuple[int, str], float]) -> None:
    for row in cards:
        deltas = _deltas_from_changes(row["coordinate_changes"])
        value = deltas.get((10, "pair_x"))
        if value is None or not any(abs(value - allowed) <= 1e-12 for allowed in (.50, .60, .70, .80, 1.00)): raise ValueError("s10 value outside approved bracket")
        if row["candidate_kind"] in {"s10_pure_directional_slice", "s10_overshoot_control"} and set(deltas) != {(10, "pair_x")}: raise ValueError("pure s10 slice changed another variable")
        if row["candidate_kind"] == "c1976_context_s10_refinement":
            expected = dict(components); expected[(10, "pair_x")] = value
            if deltas != expected: raise ValueError("context s10 candidate differs from C1976 outside s10")
        if value == 1.00 and not row["overshoot_control"]: raise ValueError("+1.00 must be overshoot control")


def _deltas_from_changes(changes: list[Mapping[str, Any]]) -> dict[tuple[int, str], float]:
    output: dict[tuple[int, str], float] = {}
    for change in changes:
        sid, fields = int(change["source_pair_id"]), change["fields"]
        xs = [float(fields[key]["delta"]) for key in ("top_x", "bottom_x") if key in fields]
        if xs:
            if len(xs) != 2 or abs(xs[0] - xs[1]) > 1e-12: raise ValueError("pair_x must move both endpoints equally")
            output[(sid, "pair_x")] = xs[0]
        if "bottom_y" in fields: output[(sid, "bottom_y")] = float(fields["bottom_y"]["delta"])
        if "top_y" in fields: raise ValueError("source candidate changed top_y")
    return output


def _rows_from_components(before, components):
    deltas = {sid: {"x": 0.0, "bottom_y": 0.0} for sid, _ in components}
    for (sid, name), value in components.items(): deltas.setdefault(sid, {"x": 0.0, "bottom_y": 0.0})["x" if name == "pair_x" else "bottom_y"] = value
    return geometry._apply(before, deltas), deltas


def _evaluate(candidate_id, before, components, effective_constraints, evidence_by_pair, *, kind, bucket, source_candidate_id, solver_gate_applicable, overshoot=False):
    rows, deltas = _rows_from_components(before, components); before_geo, after_geo = geometry._geometry(before), geometry._geometry(rows)
    anchor = _anchor_audit(_by_source(rows), effective_constraints)
    floor = after_geo["floorprint"]["summary"]; prior = before_geo["floorprint"]["summary"]
    changed = geometry._changes(before, rows); changed_pairs = sorted({int(row["source_pair_id"]) for row in changed})
    latent = {(3, "pair_x"), (3, "bottom_y"), (7, "pair_x"), (7, "bottom_y")}
    latent_items = {f"s{sid}_{axis}": value for (sid, axis), value in components.items() if (sid, axis) in latent}
    gates = {"order_unchanged": [row["source_pair_id"] for row in rows] == list(VERIFIED_ORDER_SOURCE_IDS), "top_y_unchanged": all(a["top"]["y"] == b["top"]["y"] for a, b in zip(before, rows)), "no_self_intersection": not floor["self_intersection"], "no_pair_collapse": floor["minimum_wall_length"] > 0, "keep_distinct": len(rows) == len(before), "effective_hard_anchor_satisfied": not anchor["hard_violations"]}
    evidence = {f"s{sid}": evidence_by_pair[sid] for sid in changed_pairs}
    return {"candidate_id": candidate_id, "source_candidate_id": source_candidate_id, "candidate_kind": kind, "review_bucket": bucket, "solver_gate_applicable": solver_gate_applicable, "not_solver_candidate": not solver_gate_applicable, "sensitivity_only": "s10" in kind, "overshoot_control": overshoot, "coordinate_changes": changed, "changed_pairs": changed_pairs, "corrected_coordinates": rows, "movement_by_semantic_axis": {f"s{sid}_{axis}": value for (sid, axis), value in components.items()}, "hard_gate": gates, "hard_gate_passed": all(gates.values()), "anchor_audit": anchor, "topology_valid": all(gates[k] for k in ("order_unchanged", "no_self_intersection", "no_pair_collapse", "keep_distinct")), "wall_residual_sum_before_deg": prior["wall_residual_sum_deg"], "wall_residual_sum_after_deg": floor["wall_residual_sum_deg"], "wall_residual_max_before_deg": prior["wall_residual_max_deg"], "wall_residual_max_after_deg": floor["wall_residual_max_deg"], "corner_residual_sum_before_deg": before_geo["corner_turns"]["summary"]["corner_residual_sum_deg"], "corner_residual_sum_after_deg": after_geo["corner_turns"]["summary"]["corner_residual_sum_deg"], "height_residual_sum_read_only": after_geo["heights"]["summary"]["height_residual_sum"], "minimum_wall_length": floor["minimum_wall_length"], "short_wall_changes": floor["short_wall_count"] - prior["short_wall_count"], "visible_anchor_max_deviation": max((abs(row["delta"]) for row in anchor["constraints"]), default=0.0), "latent_compensation_magnitude": sum(abs(value) for value in latent_items.values()), "latent_compensation_by_variable": latent_items, "latent_compensation_reason": "occluded identity/order-confirmed variables remain constrained diagnostic compensation", "latent_variables": sorted(latent_items), "protected_visible_variables": ["s4_pair_x", "s9_pair_x"], "soft_visible_variables": ["s10_pair_x"], "unresolved_variables": [], "compensation_allowed": any(evidence_by_pair[sid]["compensation_allowed"] for sid in changed_pairs if sid in (3, 7)), "completion_uniqueness": "not_evaluated", "alternative_hypothesis_count": None, "expert_evidence": evidence, "candidate_class": "display_only_directional_sensitivity" if not solver_gate_applicable else "diagnostic_ablation", "decision": "display_only_directional_sensitivity" if not solver_gate_applicable else "diagnostic_ablation", **SAFETY_413}


def run(out_dir: Path = OUT_DIR, review_dir: Path = REVIEW_DIR) -> dict[str, Path]:
    source_tree_sha_before = _tree_sha(SOURCE_DIR)
    evidence = _evidence(); _validate_evidence(evidence)
    source_cards = [json.loads(line) for line in SOURCE_CARDS.read_text(encoding="utf-8").splitlines() if line]
    c1976 = next(row for row in source_cards if row["candidate_id"].endswith("c_1976"))
    components = _deltas_from_changes(c1976["coordinate_changes"])
    expected = {(3, "pair_x"), (4, "pair_x"), (7, "bottom_y"), (9, "pair_x"), (10, "pair_x")}
    if set(components) != expected: raise ValueError(f"C1976 components changed: {sorted(components)}")
    m1, m2 = _load(M1_AUDIT_PATH), _load(M2_VERDICT_PATH)
    before = next(row for row in m1["solver_prototypes"] if row["candidate_id"] == m2["reviewed_candidate"])["corrected_coordinates"]
    base_doc = _load_anchor_sidecar(); base_constraints = _anchor_constraints(base_doc)
    superseded = [row for row in base_constraints if int(row["source_pair_id"]) == 3]
    effective_constraints = [row for row in base_constraints if int(row["source_pair_id"]) != 3]
    evidence_by = {row["source_pair_id"]: row for row in evidence["pairs"]}
    ablation_specs = {"c1976_full": set(components), "c1976_minus_s3": set(components) - {(3, "pair_x")}, "c1976_minus_s7": set(components) - {(7, "bottom_y")}, "c1976_visible_only": set(components) - {(3, "pair_x"), (7, "bottom_y")}, "c1976_s10_only": {(10, "pair_x")}, "c1976_hidden_compensation_only": {(3, "pair_x"), (7, "bottom_y")}}
    cards = []
    for name, included in ablation_specs.items():
        card = _evaluate(f"m_anchor_4_1_3_{name}", before, {key: components[key] for key in included}, effective_constraints, evidence_by, kind="c1976_component_ablation", bucket="component_ablation", source_candidate_id=c1976["candidate_id"], solver_gate_applicable=False)
        card.update(included_components=sorted(f"s{sid}_{axis}" for sid, axis in included), removed_components=sorted(f"s{sid}_{axis}" for sid, axis in set(components)-included), interpretation="diagnostic only; residual change is not correctness evidence")
        cards.append(card)
    s10_cards = []
    for value in (.50, .60, .70, .80, 1.00):
        key = f"m_anchor_4_1_3_s10_pure_{value:.2f}".replace(".", "_")
        s10_cards.append(_evaluate(key, before, {(10, "pair_x"): value}, effective_constraints, evidence_by, kind="s10_overshoot_control" if value == 1 else "s10_pure_directional_slice", bucket="sensitivity_only", source_candidate_id=m2["reviewed_candidate"], solver_gate_applicable=False, overshoot=value == 1))
    for value in (.50, .60, .70, .80):
        context = dict(components); context[(10, "pair_x")] = value
        key = f"m_anchor_4_1_3_c1976_s10_{value:.2f}".replace(".", "_")
        s10_cards.append(_evaluate(key, before, context, effective_constraints, evidence_by, kind="c1976_context_s10_refinement", bucket="human_review_only", source_candidate_id=c1976["candidate_id"], solver_gate_applicable=False))
    _validate_s10_cards(s10_cards, components)
    all_cards = [*cards, *s10_cards]
    out_dir.mkdir(parents=True, exist_ok=True); review_dir.mkdir(parents=True, exist_ok=True)
    paths = {"evidence": out_dir / "expert_point_evidence_sidecar_v1.json", "contract": out_dir / "effective_point_contract_audit.json", "ledger": out_dir / "human_visual_feedback_ledger_v1.json", "ablation": out_dir / "m_anchor_4_1_3_component_ablation.json", "s10": out_dir / "m_anchor_4_1_3_s10_refinement_candidates.jsonl", "cards": out_dir / "m_anchor_4_1_3_candidate_cards.jsonl", "audit": out_dir / "m_anchor_4_1_3_audit.json", "summary": out_dir / "m_anchor_4_1_3_summary.md"}
    contract = {"effective_contract_schema": "m_anchor_4_1_3_effective_point_contract_v1", "base_sidecar_path": ANCHOR_SIDECAR_PATH.as_posix(), "base_sidecar_sha256": _sha(ANCHOR_SIDECAR_PATH), "evidence_sidecar_path": paths["evidence"].as_posix(), "evidence_sidecar_sha256": None, "inherited_variables": [row["constraint_id"] for row in effective_constraints], "overridden_variables": ["s3_pair_x", "s3_bottom_y", "s3_top_y"], "superseded_constraints": [{"constraint_id": row["constraint_id"], "old_role": "hard_anchor", "new_role": evidence_by[3]["variables"]["pair_x" if row["axis"] == "x" else ("top_y" if row["endpoint"] == "top" else "bottom_y")]["solver_role"], "reason": "current human evidence marks both s3 endpoints unobservable", "source_artifact": ANCHOR_SIDECAR_PATH.as_posix(), "source_sha256": _sha(ANCHOR_SIDECAR_PATH)} for row in superseded], "unresolved_conflicts": [], "fail_closed": False, "current_stage_authorized_variables": ["s3_pair_x", "s3_bottom_y", "s7_bottom_y", "s10_pair_x"], "future_height_only_variables": ["s3_top_y", "s7_top_y"]}
    _write_text_lf(paths["evidence"], json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"); contract["evidence_sidecar_sha256"] = _sha(paths["evidence"]); _write_text_lf(paths["contract"], json.dumps(contract, ensure_ascii=False, indent=2) + "\n")
    ledger = {"schema_version": "human_visual_feedback_ledger_v1", "case_name": "task218_ann3741", "stage_id": "M-Anchor.4.1.3", "source_stage": "M-Anchor.4.1.2.1", "source_candidate_ids": [c1976["candidate_id"], "m_anchor_4_1_2_d_3426", "m_anchor_4_1_2_d_2886"], "review_context": evidence["review_context"], "point_size_calibration": 0.35, "image_evidence_quality": "blurred", "point_evidence_by_pair": evidence["pairs"], "candidate_verdicts": {c1976["candidate_id"]: {"verdict": "shortlist_for_component_ablation", "positive_visual_component": "s10_pair_x", "unresolved_visual_components": ["s3_pair_x", "s7_bottom_y"], "s4_s9_changes": "very_small_and_original_already_reasonable", "accepted_as_final_fix": False}, "m_anchor_4_1_2_d_3426": {"verdict": "reject_as_final_s10_overshoot", "sensitivity_only": True, "accepted_as_final_fix": False}, "m_anchor_4_1_2_d_2886": {"verdict": "reject_as_final_s10_overshoot", "sensitivity_only": True, "accepted_as_final_fix": False}}, "accepted": False, "downstream": False, **SAFETY_413}
    _write_text_lf(paths["ledger"], json.dumps(ledger, ensure_ascii=False, indent=2) + "\n"); _write_text_lf(paths["ablation"], json.dumps({"schema_version": "m_anchor_4_1_3_component_ablation_v1", "source_candidate_id": c1976["candidate_id"], "component_keys": sorted(f"s{sid}_{axis}" for sid, axis in components), "candidates": cards, **SAFETY_413}, ensure_ascii=False, indent=2) + "\n"); _write_text_lf(paths["s10"], "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in s10_cards)); _write_text_lf(paths["cards"], "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_cards))
    selected_ids = ["m_anchor_4_1_3_c1976_full", "m_anchor_4_1_3_c1976_visible_only", "m_anchor_4_1_3_c1976_minus_s3", "m_anchor_4_1_3_c1976_s10_only", "m_anchor_4_1_3_c1976_s10_0_70"]
    selected = [row for row in all_cards if row["candidate_id"] in selected_ids]
    manifest_fields = ("candidate_id", "source_candidate_id", "candidate_kind", "review_bucket", "candidate_class", "decision", "coordinate_changes", "changed_pairs", "movement_by_semantic_axis", "wall_residual_sum_before_deg", "wall_residual_sum_after_deg", "wall_residual_max_before_deg", "wall_residual_max_after_deg", "corner_residual_sum_before_deg", "corner_residual_sum_after_deg", "expert_evidence", "overshoot_control", "solver_gate_applicable", "final_refinement_eligible", "m_anchor_4_2_input_eligible", "m_anchor_4_2_height_completion_authorized", "requires_explicit_human_visual_verdict")
    manifest_candidates = [{key: row[key] for key in manifest_fields if key in row} | {"sensitivity_only": row["sensitivity_only"], "direct_ls_trial_allowed": False, "manual_review_candidate": True, "decision_class": row["candidate_class"]} for row in selected]
    manifest = {"schema_version": "m_anchor_4_1_3_review_bridge_v1", "case_name": "task218_ann3741_m_anchor_4_1_3", "source_image": m1["source_image"], "ordered_pairs": before, "candidates": manifest_candidates, "safety_boundary": {**SAFETY_413, "preview_only": True}}
    paths["manifest"] = review_dir / "hypothesis_review_bridge_manifest.json"; _write_text_lf(paths["manifest"], json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    source_tree_sha_after = _tree_sha(SOURCE_DIR)
    if source_tree_sha_before != source_tree_sha_after: raise RuntimeError("M4.1.2.1 source artifacts changed during M4.1.3")
    audit = {"schema_version": "m_anchor_4_1_3_occlusion_aware_audit_v1", "case_name": "task218_ann3741", "stage_id": "M-Anchor.4.1.3", "input_provenance": {"m_anchor_1_audit": {"path": M1_AUDIT_PATH.as_posix(), "sha256": _sha(M1_AUDIT_PATH)}, "source_cards": {"path": SOURCE_CARDS.as_posix(), "sha256": _sha(SOURCE_CARDS)}, "source_audit": {"path": SOURCE_AUDIT.as_posix(), "sha256": _sha(SOURCE_AUDIT)}, "anchor_sidecar": {"path": ANCHOR_SIDECAR_PATH.as_posix(), "sha256": _sha(ANCHOR_SIDECAR_PATH)}}, "source_artifacts_tree_sha256_before": source_tree_sha_before, "source_artifacts_tree_sha256_after": source_tree_sha_after, "effective_contract": contract, "review_set_candidate_ids": selected_ids, "all_candidate_count": len(all_cards), "candidates": all_cards, **SAFETY_413}
    _write_text_lf(paths["audit"], json.dumps(audit, ensure_ascii=False, indent=2) + "\n"); _write_text_lf(paths["summary"], "# M-Anchor.4.1.3\n\nOcclusion-aware component ablation and s10 sensitivity diagnostics only. No candidate is accepted or eligible for M4.2.\n")
    try:
        review_dir.resolve().relative_to(Path.cwd().resolve()); local_server_root: Path | None = Path.cwd()
    except ValueError:
        local_server_root = None
    review_paths = run_local_review(input_path=paths["manifest"], candidate_json=paths["manifest"], candidate_limit=len(selected), out_dir=review_dir, image_root_2d=Path("data/mp3d_layout/test/img"), image_root_3d=Path("data/mp3d_layout/img_v"), case_name=manifest["case_name"], width=1024, height=512, coordinate_mode="ls_percent", local_server_root=local_server_root)
    return {**paths, **{f"review_{key}": value for key, value in review_paths.items()}}


if __name__ == "__main__": print(run()["audit"])
