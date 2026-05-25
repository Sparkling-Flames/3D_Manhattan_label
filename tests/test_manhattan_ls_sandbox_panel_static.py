import json
from pathlib import Path


DEBUG_SCRIPT = Path("tools/dev_only/manhattan_ls_sandbox_panel_debug.user.js")
TIMED_SCRIPT = Path("tools/dev_only/manhattan_ls_sandbox_panel_timed.user.js")
LEGACY_PROTOTYPE = Path("tools/dev_only/manhattan_ls_sandbox_panel.user.js")
SANDBOX_IMPORT = Path(
    "import_json/sandbox/manhattan_m8/manhattan_m8_sandbox_smoke_import_2026-05-07.json"
)
ALL_USER_SCRIPTS = [LEGACY_PROTOTYPE, DEBUG_SCRIPT, TIMED_SCRIPT]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_debug_and_timed_scripts_are_dev_only_paths():
    assert DEBUG_SCRIPT.as_posix() == "tools/dev_only/manhattan_ls_sandbox_panel_debug.user.js"
    assert TIMED_SCRIPT.as_posix() == "tools/dev_only/manhattan_ls_sandbox_panel_timed.user.js"
    assert LEGACY_PROTOTYPE.exists()


def test_server_scoped_matches_only():
    for script in ALL_USER_SCRIPTS:
        text = read(script)
        assert "@match        http://175.178.71.217:8080/*" in text
        assert "@match        https://175.178.71.217:8080/*" in text
        assert "@match        *://*/*" not in text
        assert "@match        http://localhost" not in text
        assert "@match        https://localhost" not in text


def test_both_scripts_have_required_guard_text():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "dev-only",
            "sandbox-only",
            "expert/developer tester only",
            "not official userscript",
            "not worker-facing",
            "no annotation writeback",
            "no submit",
            "no routing",
            "no formal g_t",
            "no P1/C1/C2/T1/V1 artifact",
            "__HOHONET_M8_SANDBOX_PANEL_ACTIVE__",
            "window.top !== window.self",
            "keypoint_read_status",
            "keypoint_count",
            "store_status",
            "result_count",
            "keypoint_sources",
            "preview_url_status",
            "native_preview_status",
            "preview_update_status",
            "telemetry_status" if script == TIMED_SCRIPT else "keypoint_read_status",
            "Compatibility",
            "Residual",
            "Preview-only suggestion",
            "Guardrails",
            "Refresh 3D Preview",
            "hohonet-iframe",
            "hohonet-wrapper",
            "hohonet-refresh-btn",
            "update_layout",
            "label-studio-store",
            "findSectionContainer",
            "ensureNativePreviewArea",
        ]:
            assert required in text


def test_debug_script_has_no_network_logging():
    text = read(DEBUG_SCRIPT)
    for forbidden in ["fetch(", "XMLHttpRequest", "/log_time", "POST", "PUT", "PATCH", "DELETE"]:
        assert forbidden not in text


def test_timed_script_only_posts_sandbox_log_time_payload():
    text = read(TIMED_SCRIPT)
    assert "http://175.178.71.217:8000" in text
    assert "function logTimeUrl()" in text
    assert "fetch(logTimeUrl()" in text
    assert 'method: "POST"' in text
    assert "}/log_time`" in text
    assert "X-HOHONET-TOKEN" in text
    assert "HEARTBEAT_INTERVAL_MS = 15000" in text
    assert "sendSandboxTelemetry(\"heartbeat\")" in text
    assert "visibilitychange" in text
    assert "visibility_hidden" in text
    assert "pagehide" in text
    assert "panel_unloaded" in text
    assert "XMLHttpRequest" not in text
    assert "PUT" not in text
    assert "PATCH" not in text
    assert "DELETE" not in text

    for required in [
        'log_context: "manhattan_ls_sandbox"',
        'tool_stage: "M8"',
        'script_variant: "timed"',
        "is_sandbox: true",
        "sandbox_project: true",
        "exclude_from_primary_active_time: true",
        "exclude_from_thesis_evidence: true",
        "not_worker_facing: true",
        "not_p1_c1_c2_t1_v1_artifact: true",
        "manhattan_panel_version: PANEL_VERSION",
        "task_id: getTaskId()",
        "project_id: getProjectId()",
        "project_name: getProjectName()",
        "annotator_id: getAnnotatorId()",
        "session_id: sessionId",
        "page_type: getPageType()",
        "active_seconds: activeSeconds",
        "active_seconds_fragment: activeSecondsFragment",
        "telemetry_elapsed_seconds: telemetryElapsedSeconds",
        "timestamp: nowMs",
        'event: eventName',
    ]:
        assert required in text


def test_timed_script_uses_official_active_state_rules():
    text = read(TIMED_SCRIPT)
    for required in [
        "IDLE_THRESHOLD_MS = 15000",
        "PAGE_HIDDEN_THRESHOLD_MS = 6000",
        "let lastActivityTime = 0",
        "let isPageVisible = !document.hidden",
        "let pageHiddenTime = null",
        "nowMs - lastActivityTime < IDLE_THRESHOLD_MS",
        "isLikelyAnnotationPage()",
        "lastActivityTime > 0",
        "isPageVisible &&",
        "activeSeconds += 1",
        "lastActivityTime = 0",
    ]:
        assert required in text

    for event_name in ["mousemove", "keydown", "click", "scroll", "wheel"]:
        assert f'"{event_name}"' in text


def test_timed_script_has_sandbox_telemetry_panel_diagnostics():
    text = read(TIMED_SCRIPT)
    for required in [
        "telemetry_status",
        "last_telemetry_event",
        "last_telemetry_http_status",
        "last_telemetry_error",
        "heartbeat_interval_ms",
        "telemetryState.status",
        "telemetryState.lastHttpStatus",
        "non_2xx_response",
        "network_error",
        "hohonet_m8_sandbox_session_id",
        "active_timer_status",
        "active_seconds",
        "active_seconds_fragment",
        "last_activity_age_ms",
        "page_visible_status",
        "last_hidden_duration_ms",
        "activeTimerStatus",
        "updateActivityTimerPanel",
    ]:
        assert required in text


def test_both_scripts_include_m9_manhattan_deviation_panel():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "Manhattan deviation",
            "computeManhattanDeviation",
            "buildPreviewPairDiagnostics",
            "manhattan_deviation_score",
            "vertical_pair_x_residual",
            "ceiling_y_range",
            "floor_y_range",
            "wall_height_range",
            "compatibility_status",
            "deviation_level",
            "exclusion_reason",
            "missing_keypoints",
            "compatibility_failure_odd_keypoint",
            "compatibility_failure_duplicate",
            "compatibility_failure_no_valid_vertical_pairs",
            "compatibility_failure_unpaired_keypoints",
            "Preview-only geometry diagnostic",
            "Not correctness",
            "Not snap",
            "Not next corner prediction",
            "Not writeback",
        ]:
            assert required in text


def test_both_scripts_use_preview_pairing_and_fixed_deviation_thresholds():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "points.slice().sort((a, b) => a.x - b.x)",
            "const threshold = width * 0.05",
            "diff < threshold && diff < minDiff",
            "bestJ",
            "score < 5",
            "score < 15",
            "clamp(",
            "DUPLICATE_KEYPOINT_THRESHOLD_RATIO = 0.01",
        ]:
            assert required in text


def test_timed_telemetry_sends_deviation_score_without_coordinates():
    text = read(TIMED_SCRIPT)
    for required in [
        "preview_only_manhattan_deviation_score",
        "preview_only_manhattan_deviation_level",
        "preview_only_manhattan_compatibility_status",
        "not_correctness: true",
        "no_writeback: true",
    ]:
        assert required in text

    payload_start = text.index("function sandboxTelemetryPayload")
    payload_end = text.index("function sendSandboxTelemetry")
    payload_text = text[payload_start:payload_end]
    assert "keypoints:" not in payload_text
    assert "pairs:" not in payload_text
    assert "corners:" not in payload_text


def test_scripts_have_no_active_annotation_or_navigation_triggers():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for forbidden in [".submit(", "requestSubmit(", ".click("]:
            assert forbidden not in text

        lowered = text.lower()
        for forbidden in [
            "snap_to_axis",
            "adjustment_vector",
            "next-corner",
            "next_corner",
            "predict next",
            "corrected annotation payload",
            "routing decision",
            "worker tier label",
            "correctness label:",
        ]:
            assert forbidden not in lowered


def test_scripts_include_preview_refresh_without_porting_residual_logic():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        assert "Refresh 3D Preview" in text
        assert "panel.innerHTML" not in text
        assert "hohonet-manhattan-sandbox-preview" not in text
        assert "makeMutableRow" in text
        assert "setText" in text
        assert "getStore()" in text
        assert "collectSelectedResults" in text
        assert "buildPreviewPairs" in text
        assert "getViewerBaseUrl()" in text
        assert "tools/vis_3d.html" in text
        assert "findExistingPreviewUrl" in text
        assert "findNativePreviewIframe" in text
        assert "ensureNativePreviewArea" in text
        assert "hohonet-refresh-btn" in text
        assert "hohonet-wrapper" in text
        assert "extractPairsFromPreviewUrl" in text
        assert "native_preview_update_sent" in text
        assert "Uses the existing page 3D Layout Preview only" in text
        assert "placeholder only; no residual calculator is embedded" in text
        assert "snap_to_axis" not in text
        assert "adjustment_vector" not in text


def test_sandbox_import_has_required_task_tags():
    data = json.loads(SANDBOX_IMPORT.read_text(encoding="utf-8"))
    assert len(data) == 5

    for item in data:
        task_data = item["data"]
        assert task_data["sandbox_only"] is True
        assert task_data["sandbox_source"] == "2026-05-07 smoke export"
        assert task_data["manhattan_m8_sandbox"] is True
        assert task_data["condition"] == "semi"
