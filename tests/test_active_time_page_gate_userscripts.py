from pathlib import Path

import pytest

from tools.label_studio.cors_server import validate_log_payload


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "tools" / "label_studio" / "official" / "ls_userscript_annotator.js"
FOREIGN = ROOT / "tools" / "thesis_main" / "foreign_recruitment" / "ls_userscript_annotator_https_en.user.js"
VERSION = "stage3_active_time_identity_20260725_v3"


def _script(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_formal_userscripts_use_the_stage3_page_gate_version():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        assert f"// @version      {VERSION}" in source
        assert f'const SCRIPT_VERSION = "{VERSION}";' in source


def test_page_gate_requires_route_labeling_editor_main_view_and_task_identity():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        start = source.index("function resolveAnnotationPageGate()")
        end = source.index("function isLikelyAnnotationPage()", start)
        gate = source[start:end]

        assert 'params.get("task")' in gate
        assert "window.location.pathname.match(/\\/tasks\\/" in gate
        assert ".lsf-root.lsf-root_mode_labeling" in gate
        assert ".lsf-label-view" in gate
        assert "#label-studio-dm.lsf-label-view__lsf-container > .lsf-editor" in gate
        assert ".lsf-current-task__task-id" in gate
        assert ".lsf-main-content > .lsf-main-view" in gate
        assert "route_dom_task_mismatch" in gate
        assert "task_route_conflict" in gate
        assert "route_store_task_mismatch" in gate
        assert "dom_task_identity_not_ready" in gate
        assert "findMainImage" not in gate


def test_store_mismatch_is_rejected_and_page_context_is_captured_in_the_gate():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        start = source.index("function resolveAnnotationPageGate()")
        end = source.index("function isLikelyAnnotationPage()", start)
        gate = source[start:end]

        for field in (
            "storeTaskIds",
            "storeTaskMatchStatus",
            "storeMismatchPresent",
            "locationPath",
            "sanitizedLocationSearch",
            "capturedAt",
            "matches_route",
            "mixed_with_route_match",
            "mismatch_only",
        ):
            assert field in gate
        assert "gate.reason = \"route_store_task_mismatch\"" in gate
        assert "queryTaskId && pathTaskId && queryTaskId !== pathTaskId" in gate
        assert "location_path: report.pageGate?.locationPath || \"\"" in source
        assert "location_search: report.pageGate?.sanitizedLocationSearch || \"\"" in source


def test_page_gate_payload_audits_without_uploading_full_query_string():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        for field in (
            "location_path",
            "location_search",
            "page_gate_captured_at",
            "page_gate_eligible",
            "page_gate_reason",
            "page_gate_sources",
            "resolved_route_task_id",
            "resolved_dom_task_id",
            "resolved_store_task_id",
            "labeling_root_present",
            "annotation_editor_dom_present",
            "annotation_main_view_dom_present",
        ):
            assert field in source
        assert "location_search: report.pageGate?.sanitizedLocationSearch || \"\"" in source


def test_formal_scripts_keep_deployment_and_localized_non_counting_ui():
    official = _script(OFFICIAL)
    foreign = _script(FOREIGN)

    assert "175.178.71.217" in official
    assert "175.178.71.217" not in foreign
    assert "Active-Time：未计时" in official
    assert "Active-Time: Not counting" in foreign
    assert "currentActiveTimeMetadata = null" in official
    assert "currentActiveTimeMetadata = null" in foreign


def test_formal_scripts_prefer_server_annotation_identity_and_bind_unknown_time_after_save():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        identity = source[source.index("function getAnnotationIdentity()"):source.index("function getCurrentAnnotationId()")]
        assert identity.index("selected?.pk") < identity.index("selected?.id")
        assert "server_annotation_id: report.serverAnnotationId" in source
        assert "client_annotation_id: report.clientAnnotationId" in source
        assert 'activeTimeAliasReason: "unknown_annotation_late_bound"' in source
        assert 'lateBindingStatus: "single_actual_annotation"' in source
        assert "unknownCumulativeSeconds <= 5" not in source


def test_active_time_backend_validates_payload_without_discarding_legacy_audit_rows():
    row = validate_log_payload({"project_id": "69", "task_id": "1", "annotator_id": "2", "session_id": "s", "active_seconds": 3})
    assert row["server_validation_status"] == "legacy_or_unverified_page_gate"
    with pytest.raises(ValueError):
        validate_log_payload({"project_id": "69", "task_id": "1", "annotator_id": "2", "session_id": "s", "active_seconds": -1})
