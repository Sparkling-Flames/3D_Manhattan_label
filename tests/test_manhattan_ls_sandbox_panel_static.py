import json
from pathlib import Path


DEBUG_SCRIPT = Path("tools/paper_a_manhattan/dev_only/manhattan_ls_sandbox_panel_debug.user.js")
TIMED_SCRIPT = Path("tools/paper_a_manhattan/dev_only/manhattan_ls_sandbox_panel_timed.user.js")
LEGACY_PROTOTYPE = Path("tools/paper_a_manhattan/dev_only/manhattan_ls_sandbox_panel.user.js")
SANDBOX_IMPORT = Path(
    "import_json/sandbox/manhattan_m8/manhattan_m8_sandbox_smoke_import_2026-05-07.json"
)
ALL_USER_SCRIPTS = [LEGACY_PROTOTYPE, DEBUG_SCRIPT, TIMED_SCRIPT]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_debug_and_timed_scripts_are_dev_only_paths():
    assert DEBUG_SCRIPT.as_posix() == "tools/paper_a_manhattan/dev_only/manhattan_ls_sandbox_panel_debug.user.js"
    assert TIMED_SCRIPT.as_posix() == "tools/paper_a_manhattan/dev_only/manhattan_ls_sandbox_panel_timed.user.js"
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
            "stage1_helper_ordercache_hotfix_20260617_v1",
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
    for forbidden in [
        "fetch(",
        "XMLHttpRequest",
        "/log_time",
        'method: "POST"',
        'method: "PUT"',
        'method: "PATCH"',
        'method: "DELETE"',
    ]:
        assert forbidden not in text


def test_timed_script_only_posts_sandbox_log_time_payload():
    text = read(TIMED_SCRIPT)
    assert "http://175.178.71.217:8000" in text
    assert "function logTimeUrl()" in text
    assert "fetch(logTimeUrl()" in text
    assert 'method: "POST"' in text
    assert "}/log_time`" in text
    assert "X-HOHONET-TOKEN" in text
    assert "@version      stage1_helper_ordercache_hotfix_20260617_v1" in text
    assert 'const PANEL_VERSION = "stage1_helper_ordercache_hotfix_20260617_v1";' in text
    assert "HEARTBEAT_INTERVAL_MS = 15000" in text
    assert "sendSandboxTelemetryIfActive(\"heartbeat\")" in text
    assert "skipped_no_active_seconds" in text
    assert "visibilitychange" in text
    assert "visibility_hidden" in text
    assert "pagehide" in text
    assert "panel_unloaded" in text
    assert "XMLHttpRequest" not in text
    assert 'method: "PUT"' not in text
    assert 'method: "PATCH"' not in text
    assert 'method: "DELETE"' not in text

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
        "let isWindowFocused = document.hasFocus()",
        "let pageHiddenTime = null",
        "nowMs - lastActivityTime < IDLE_THRESHOLD_MS",
        "isLikelyAnnotationPage()",
        "function isActiveTimeCountingPage()",
        "return isPageVisible && isWindowFocused && isLikelyAnnotationPage()",
        "lastActivityTime > 0",
        "isPageVisible &&",
        "isWindowFocused",
        "activeSeconds += 1",
        "lastActivityTime = 0",
        'window.addEventListener("blur"',
        'window.addEventListener("focus"',
        "Keep blur network-free",
        "window_focus_status",
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
            "No axis snapping",
            "No corner prediction",
            "No writeback",
        ]:
            assert required in text


def test_both_scripts_include_m10_direction_only_diagnosis_panel():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "Manhattan diagnosis",
            "computeDirectionOnlyDiagnosis",
            "primary_issue_type",
            "primary_issue_severity",
            "primary_issue_explanation",
            "affected_pair_index",
            "affected_wall_index",
            "pair_x_alignment_summary",
            "ceiling_alignment_summary",
            "floor_alignment_summary",
            "wall_height_summary",
            "Direction-only preview diagnosis",
            "Not a correction",
            "No target x/y",
            "pair_x_alignment",
            "ceiling_alignment",
            "floor_alignment",
            "wall_height_consistency",
            "top point is left of bottom point",
            "top point is right of bottom point",
            "median ceiling band",
            "median floor band",
            "median wall height",
        ]:
            assert required in text


def test_both_scripts_include_m12_direction_only_hint_panel():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "Direction-only hint",
            "hint_status",
            "hint_component",
            "affected_pair_index",
            "direction_hint",
            "alternative_anchor_hint",
            "hint_guardrail",
            "highlight_status",
            "highlight_affected_pair_index",
            "diagnosis_affected_pair_index",
            "manual_selected_pair_index",
            "highlight_mode",
            "diagnosis_highlight_status",
            "manual_highlight_status",
            "highlight_row_found",
            "highlight_overlay_labels_found",
            "Highlight scope: Preview order pair row and 2D panorama order labels only",
            "Highlight affected pair",
            "Scroll to affected pair",
            'highlightButton.addEventListener("click", () => highlightAffectedPair())',
            'scrollButton.addEventListener("click", () => scrollToAffectedPair())',
            "manual-selected-pair",
            "diagnosis-affected-pair",
            "manual-and-diagnosis-pair",
            "dual_state_visible",
            "manual_and_diagnosis_same_pair",
            "Blue: manual selected",
            "Orange: diagnosis affected",
            "Purple: both",
            "setHighlightState",
            "diagnosis_highlight_applied",
            "directionOnlyHint",
            "would reduce this residual",
            "Choose by visual evidence",
            "Inspect top point",
            "Inspect ceiling",
            "Floor point is",
            "Direction-only hint. Inspect visually",
        ]:
            assert required in text

        highlight_start = text.index("function highlightAffectedPair")
        highlight_end = text.index("function scrollToAffectedPair")
        highlight_text = text[highlight_start:highlight_end]
        assert "hint-status" not in highlight_text
        assert "unavailable_no_valid_pair" in highlight_text
        assert "unavailable_pair_not_in_order" in highlight_text
        assert "currentPreviewSelectedPairIndex = displayIndex" not in highlight_text
        assert "scrollIntoView" not in highlight_text
        assert "state.manhattan_deviation" not in highlight_text
        assert '${index + 1}${isManualSelected ? "S" : ""}${isAffected ? "A" : ""}' not in text
        assert "badge.textContent = String(index + 1)" in text
        assert 'return "manual_and_diagnosis"' not in text
        assert 'badge.style.background = "rgba(255,138,0,0.62)"' in text
        assert 'badge.style.background = "rgba(47,92,255,0.58)"' in text
        assert 'badge.style.background = "rgba(168,85,247,0.62)"' in text

        scroll_start = text.index("function scrollToAffectedPair")
        scroll_end = text.index("function swapPreviewPairs")
        scroll_text = text[scroll_start:scroll_end]
        assert "scrollIntoView" in scroll_text
        assert "currentPreviewSelectedPairIndex" not in scroll_text


def test_both_scripts_include_sandbox_meta_guard_and_preview_order_controls():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "Sandbox meta-label guard",
            "validateMetaChoices",
            "difficulty_conflict_trivial_with_non_trivial",
            "model_issue_conflict_acceptable_with_issue",
            "Sandbox meta-label guard blocked action",
            "Preview order",
            "Current order",
            "Active pair",
            "Swap order",
            "Pair rows",
            "active-pair",
            "manual-selected-pair",
            "diagnosis-affected-pair",
            "manual-and-diagnosis-pair",
            "Blue: manual selected",
            "Orange: diagnosis affected",
            "Purple: both",
            "clearPreviewOrderOnTaskChange",
            "clearPreviewOrderRuntime",
            "page_signature",
            "dataset.activePair",
            "dataset.manualSelectedPair",
            "dataset.diagnosisAffectedPair",
            "base_pair_index",
            "display_pair_index",
            "dataset.basePairIndex",
            "dataset.displayPairIndex",
            "top: x=",
            "bottom: x=",
            "formatLsCoord",
            "pairLsCoordSummary",
            "Label Studio 0-100 scale",
            "Hide corner order",
            "Show corner order",
            "hp-title",
            "hp-slot",
            "hp-toggle",
            "renderPreviewOverlayPairs",
            "toggleCornerOrderLabels",
            "installPreviewOrderPanelDrag",
            "Swap",
            "Reset preview order",
            "Preview-only order controls",
            "previewOrderActive: true",
            "No annotation writeback",
        ]:
            assert required in text


def test_hide_labels_unifies_2d_and_3d_preview_visibility_without_writeback():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "function setLabelVisibility(visible)",
            "function applyLabelVisibilityState()",
            "function set2DLabelsVisible(visible)",
            "function set3DPreviewLabelsVisible(visible)",
            '{ type: "set_label_visibility", visible: Boolean(visible) }',
            'iframe.addEventListener("load", scheduleLabelVisibilityStateApply)',
            "function scheduleLabelVisibilityStateApply()",
        ]:
            assert required in text

        apply_start = text.index("function applyLabelVisibilityState")
        apply_end = text.index("function setLabelVisibility", apply_start)
        apply_text = text[apply_start:apply_end]
        assert "set2DLabelsVisible(visible)" in apply_text
        assert "set3DPreviewLabelsVisible(visible)" in apply_text

        toggle_start = text.index("function toggleCornerOrderLabels")
        toggle_end = text.index("function toggleGuideBands", toggle_start)
        toggle_text = text[toggle_start:toggle_end]
        assert "setLabelVisibility(visible)" in toggle_text
        assert "setLabelsVisible(visible)" not in toggle_text

        send_start = text.index("function sendPreviewOrderToIframe")
        send_end = text.index("function setPreviewBasePairs", send_start)
        assert "scheduleLabelVisibilityStateApply()" in text[send_start:send_end]

        update_start = text.index("function updatePreviewIframe")
        update_end = text.index("function performRefresh3DPreview", update_start)
        assert "scheduleLabelVisibilityStateApply()" in text[update_start:update_end]

        visibility_start = text.index("function set2DLabelsVisible")
        visibility_end = text.index("function getGuideBandsVisible", visibility_start)
        visibility_text = text[visibility_start:visibility_end]
        assert "contentWindow.eval" not in visibility_text
        assert "contentDocument" not in visibility_text
        for forbidden in [
            "annotation",
            "writeback",
            "submit",
            "save",
            "routing",
            "formal_g_t",
            "P1/C1/C2/T1/V1",
        ]:
            assert forbidden not in visibility_text


def test_vis_3d_handles_label_visibility_messages_and_preserves_state_on_rebuild():
    text = read(Path("tools/label_studio/vis_3d.html"))
    for required in [
        "let cornerLabelsVisible = true;",
        "sprite.userData.hohonetCornerLabel = true;",
        "sprite.visible = cornerLabelsVisible;",
        "function setCornerLabelVisibility(visible)",
        "object?.userData?.hohonetCornerLabel === true",
        'data.type === "set_label_visibility"',
        "setCornerLabelVisibility(data.visible)",
    ]:
        assert required in text


def test_vis_3d_reports_texture_load_status_to_parent():
    text = read(Path("tools/label_studio/vis_3d.html"))
    for required in [
        'type: "hohonet_texture_status"',
        'reportTextureStatus("loading", false, imageUrl, "texture_load_requested")',
        'reportTextureStatus("loaded", true, imageUrl, "texture_load_succeeded")',
        'reportTextureStatus("failed", false, imageUrl, "texture_load_failed")',
        'reportTextureStatus("unavailable", false, null, "image_url_unavailable")',
    ]:
        assert required in text


def test_vis_3d_gates_read_only_inspection_and_reports_selections():
    text = read(Path("tools/label_studio/vis_3d.html"))
    for required in [
        "inspectionState.enabled = data.inspectionMode === true",
        'type: "hohonet_viewer_ready"',
        'type: "hohonet_geometry_selection"',
        'type: "hohonet_measurement_status"',
        'data.type === "hohonet_inspection_command"',
        'data.command === "set_measure_mode"',
        'data.command === "camera_preset"',
        'data.command === "select_issue"',
        "raycaster.intersectObjects(interactiveObjects, false)",
        'hit.object.userData.hohonetInspectionType === "corner"',
        "inspectionState.displayOptions.ghost",
        "inspectionState.enabled && !inspectionState.displayOptions.texture",
        "inspectionState.enabled && changedWallSet.size",
        "changedWallLine.computeLineDistances()",
        "focusInspectionPoint",
        "function addCornerAngleGuide(pairIndex, endpoint)",
        "wall-to-wall angle:",
        "heading (global XZ):",
        "deviation from axis:",
        'heading_reference: "global_xz_counterclockwise_from_positive_x"',
        "junction_residual_to_90_deg",
    ]:
        assert required in text

    load_start = text.index("function loadPreviewFromMessage")
    load_end = text.index("try {", load_start)
    load_text = text[load_start:load_end]
    assert "inspectionMode === true" in load_text
    assert "data.inspectionMetadata" in load_text

    wall_start = text.index("function selectWall")
    wall_end = text.index("function focusInspectionPoint", wall_start)
    wall_text = text[wall_start:wall_end]
    assert "wall_heading_deg" in wall_text
    assert "axis_deviation_deg" in wall_text
    assert "adjacent_corner_angles" not in wall_text

    for forbidden in [
        "writeback",
        "annotation patch",
        "annotation_patch",
        "routing",
        "formal_g_t",
        "formal g_t",
        "p1/c1/c2/t1/v1",
    ]:
        assert forbidden not in text.lower()

    post_start = text.index("function postGeometrySelection")
    post_end = text.index("function addCornerAngleGuide", post_start)
    post_text = text[post_start:post_end]
    assert "window.parent.postMessage" in post_text
    assert 'type: "hohonet_geometry_selection"' in post_text
    for forbidden in ["fetch(", "xmlhttprequest", "submit", "save", "patch"]:
        assert forbidden not in post_text.lower()


def test_vis_3d_wall_picking_uses_explicit_per_wall_metadata():
    text = read(Path("tools/label_studio/vis_3d.html"))

    assert "faceIndex" not in text
    assert 'pickingMesh.userData.hohonetInspectionType = "wall"' in text
    assert "pickingMesh.userData.wallIndex = i + 1" in text
    assert "interactiveObjects.push(pickingMesh)" in text

    wall_mesh_start = text.index("const wallMesh = new THREE.Mesh")
    floor_start = text.index("const floorGeo", wall_mesh_start)
    picking_block = text[wall_mesh_start:floor_start]
    assert "if (inspectionState.enabled)" in picking_block
    assert "opacity: 0" in picking_block
    assert "pickingMaterial.colorWrite = false" in picking_block
    assert "interactiveObjects.push(wallMesh)" not in picking_block

    hit_start = text.index("function handleInspectionHit")
    hit_end = text.index('renderer.domElement.addEventListener("pointerdown"', hit_start)
    hit_text = text[hit_start:hit_end]
    assert 'kind === "wall"' in hit_text
    assert "selectWall(Number(hit.object.userData.wallIndex))" in hit_text
    assert "Math.floor" not in hit_text


def test_pre_m15192_vis_3d_backup_is_not_the_runtime_entrypoint():
    active = read(Path("tools/label_studio/vis_3d.html"))
    backup_path = Path("tools/label_studio/vis_3d_pre_m15_19_2_backup.html")
    backup = read(backup_path)

    assert backup_path.is_file()
    assert 'version: "m15.19.2"' in active
    assert 'version: "m15.19.2"' not in backup
    assert 'type: "hohonet_viewer_ready"' not in backup


def test_both_scripts_include_m13_guide_bands_and_transparent_badges():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for required in [
            "stage1_helper_ordercache_hotfix_20260617_v1",
            "hohonet-m13-primary-toolbar",
            "Manhattan tools",
            "Refresh 3D",
            "Corner order",
            "Guide lines",
            "Highlight affected",
            "Scroll affected",
            "Reset preview order",
            "Debug drawer",
            "Show debug details",
            'panel.dataset.collapsed = "1"',
            "Show guide bands",
            "Hide guide bands",
            "2D guide bands",
            "GUIDE_MODE = \"issue_only\"",
            "guide_status",
            "guide_mode",
            "guide_component",
            "guide_affected_pair_index",
            "guide_visible_items",
            "guide_explanation",
            "guide_scope",
            "guide_guardrail",
            "Guide bands are visual references only",
            "visual reference lines",
            "Ceiling reference",
            "Floor reference",
            "Affected pair axis",
            "Height check",
            "median ceiling band",
            "median floor band",
            "affected pair guide",
            "height check bracket",
            "renderGuideBands",
            "drawGuideLegend",
            "drawHeightBracket",
            "pair_x_alignment",
            "ceiling_alignment",
            "floor_alignment",
            "wall_height_consistency",
            "affected_ceiling_point",
            "affected_floor_point",
            "low_opacity_context_bands",
            "getGuideBandsVisible",
            "setGuideBandsVisible",
            "GUIDE_BANDS_VISIBLE_KEY",
            "rgba(255,255,255,0.56)",
            "rgba(255,138,0,0.62)",
            "rgba(47,92,255,0.58)",
            "rgba(168,85,247,0.62)",
        ]:
            assert required in text

        assert 'const GUIDE_MODE = "issue_only"' in text
        assert "all_references" not in text
        assert '${index + 1}${isManualSelected ? "S" : ""}${isAffected ? "A" : ""}' not in text
        assert "badge.textContent = String(index + 1)" in text


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


def test_pair_rows_use_label_studio_scale_without_percent_suffix():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        assert "x%=" not in text
        assert "c%=" not in text
        assert "f%=" not in text
        assert "formatPercent" not in text
        assert "pairPercentSummary" not in text
        assert "top: x=" in text
        assert "bottom: x=" in text
        assert "Label Studio 0-100 scale" in text
        assert "vertical_pair_x_residual_px" in text
        assert "ceiling_y_range_px" in text
        assert "floor_y_range_px" in text
        assert "wall_height_range_px" in text
        assert "3D highlight" not in text


def test_timed_telemetry_sends_deviation_score_without_coordinates():
    text = read(TIMED_SCRIPT)
    for required in [
        "preview_only_manhattan_deviation_score",
        "preview_only_manhattan_deviation_level",
        "preview_only_manhattan_compatibility_status",
        "preview_only_primary_issue_type",
        "preview_only_primary_issue_severity",
        "preview_only_hint_component",
        "preview_only_affected_pair_index",
        "preview_only_direction_hint_type",
        "preview_only_diagnosis_affected_pair_index",
        "preview_only_manual_selected_pair_index",
        "preview_only_highlight_mode",
        "preview_only_guide_visible",
        "preview_only_guide_component",
        "preview_only_guide_affected_pair_index",
        "preview_order_visible",
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
    assert "\n      affected_pair_index:" not in payload_text
    assert "affected_wall_index:" not in payload_text


def test_scripts_have_no_active_annotation_or_navigation_triggers():
    for script in [DEBUG_SCRIPT, TIMED_SCRIPT]:
        text = read(script)
        for forbidden in [".submit(", "requestSubmit(", ".click("]:
            assert forbidden not in text

        lowered = text.lower()
        for forbidden in [
            "snap_to_axis",
            "snap coordinate",
            "adjustment_vector",
            "target coordinate",
            "target_x",
            "target_y",
            "delta_x",
            "delta_y",
            "next-corner",
            "next_corner",
            "predict next",
            "move this point",
            "automatic correction",
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
        assert "Python parity checker is not embedded" in text
        assert "Python residual calculator is not embedded" in text
        assert "Compatibility placeholder only" not in text
        assert "Residual placeholder only" not in text
        assert "placeholder only; no residual calculator is embedded" not in text
        assert "placeholder only; no Python logic is ported" not in text
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
