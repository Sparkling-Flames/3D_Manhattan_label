from pathlib import Path


SPEC = Path("docs/paper_a_manhattan/HRC_C6_5_GLOBAL_HYPOTHESIS_PROBE_SPEC_v1.md")


def _text() -> str:
    return SPEC.read_text(encoding="utf-8")


def test_c6_5_spec_contains_shadow_safety_contract():
    text = _text()
    for needle in (
        "shadow-only",
        "audit-only",
        "No active runner role is authorized",
        "accepted=false",
        "downstream_recommendation=false",
        "annotation_writeback=false",
    ):
        assert needle in text


def test_c6_5_spec_lists_allowed_probe_families_and_forbidden_operations():
    text = _text()
    for family in (
        "global_height_reproject",
        "direction_family_azimuth_snap",
        "floor_depth_balance_global",
        "multi_pair_x_alignment",
        "short_wall_preserving_floorprint_balance",
    ):
        assert family in text
    for forbidden in (
        "topology mutation by default",
        "merge/delete/reorder corners",
        "active source replacement",
        "annotation patch/writeback",
        "worker-facing UI",
        "optimizer loop",
        "direct C3 third family implementation",
    ):
        assert forbidden in text


def test_c6_5_spec_schema_and_blocked_status():
    text = _text()
    for field in (
        "schema_version",
        "case_name",
        "probe_family",
        "source_artifacts + sha256",
        "candidate_generation_mode = shadow_only_finite_probe",
        "variables_changed",
        "variables_forbidden",
        "hard_gate_inputs",
        "expected_c2_metrics",
        "expected_c5_metrics",
        "c4_evidence_usage = diagnostic_only",
        "active_runner_role=false",
    ):
        assert field in text
    assert "C3 shadow expansion remains blocked" in text
    assert "C7/C9/C10 remain blocked" in text
    assert "not generator execution" in text


def test_c6_5_spec_does_not_authorize_active_selection_or_optimizer():
    text = _text().lower()
    forbidden_phrases = (
        "active runner selection is allowed",
        "writeback is allowed",
        "optimizer loop is allowed",
        "accepted recommendation",
        "downstream recommendation is allowed",
    )
    for phrase in forbidden_phrases:
        assert phrase not in text
