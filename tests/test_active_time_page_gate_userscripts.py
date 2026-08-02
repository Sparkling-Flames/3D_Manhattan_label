from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "tools" / "label_studio" / "official" / "ls_userscript_annotator.js"
FOREIGN = ROOT / "tools" / "thesis_main" / "foreign_recruitment" / "ls_userscript_annotator_https_en.user.js"
VERSION = "c2plus_task_worker_active_time_20260802_v1"


def _script(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_formal_userscripts_use_the_c2plus_task_worker_version():
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
        assert "route_store_task_mismatch" not in gate
        assert "dom_task_identity_not_ready" in gate
        assert "findMainImage" not in gate


def test_store_is_audit_only_and_page_context_is_captured_in_the_gate():
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
        assert "gate.reason = \"route_store_task_mismatch\"" not in gate
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


def test_v3_uses_task_worker_identity_without_annotation_ids():
    official = _script(OFFICIAL)
    foreign = _script(FOREIGN)

    for source in (official, foreign):
        key = source[source.index("function buildActiveTimeKey("):source.index("function resolveActiveTimeMetadata(")]
        for field in ("projectId", "taskId", "annotatorId"):
            assert field in key
        assert "annotationId" not in key

        payload = source[source.index("function buildActiveTimePayload("):source.index("function loadActiveTimeRetryQueue(")]
        assert 'active_time_schema_version: "c2plus_task_worker_v1"' in payload
        assert 'active_time_identity_level: "project_runtime_task_worker"' in payload
        for field in (
            "annotation_id:",
            "annotation_id_source:",
            "selected_annotation_id:",
            "selected_annotation_owner_id:",
            "selected_annotation_owner_source:",
            "annotation_match_status:",
            "late_binding_status:",
        ):
            assert field not in payload

        capture = source[source.index("function captureCurrentActiveTimeMetadata("):source.index("function buildActiveTimeKey(")]
        assert "getAnnotationIdentity()" not in capture
        assert "annotationId" not in capture
        assert "session_id: sessionId" in source
        assert "server_annotation_id" not in source
        assert "Math.round(seconds)" in source
        assert "lastActiveTimeUploadStatus" in source
        assert 'const ACTIVE_TIME_RETRY_QUEUE_KEY = "HOHONET_ACTIVE_TIME_RETRY_QUEUE_V2_TASK_WORKER";' in source

    assert "Active-Time：计时中" in official
    assert "Active-Time: Counting" in foreign
