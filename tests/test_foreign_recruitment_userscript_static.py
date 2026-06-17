from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
FOREIGN_DIR = ROOT / "tools" / "thesis_main" / "foreign_recruitment"
SCRIPT = FOREIGN_DIR / "ls_userscript_annotator_https_en.user.js"
DEBUG_SCRIPT = FOREIGN_DIR / "ls_userscript_annotator_https_en_debug.user.js"
OFFICIAL_SCRIPT = ROOT / "tools" / "label_studio" / "official" / "ls_userscript_annotator.js"
OFFICIAL_DEBUG_SCRIPT = ROOT / "tools" / "label_studio" / "official" / "ls_userscript_debug.js"
MANHATTAN_DEBUG_SCRIPT = ROOT / "tools" / "paper_a_manhattan" / "dev_only" / "manhattan_ls_sandbox_panel_debug.user.js"
MANHATTAN_TIMED_SCRIPT = ROOT / "tools" / "paper_a_manhattan" / "dev_only" / "manhattan_ls_sandbox_panel_timed.user.js"
MANHATTAN_PROTO_SCRIPT = ROOT / "tools" / "paper_a_manhattan" / "dev_only" / "manhattan_ls_sandbox_panel.user.js"
VIS_3D = ROOT / "tools" / "label_studio" / "vis_3d.html"
GUIDE = FOREIGN_DIR / "ANNOTATOR_GUIDE_EN.md"
INSTALL = FOREIGN_DIR / "INSTALL_USERSCRIPT_HTTPS_EN.md"
CLOUDRESEARCH = FOREIGN_DIR / "CLOUDRESEARCH_CONNECT_SETUP_GUIDE.md"
MAIN_XML = ROOT / "tools" / "label_studio" / "label_studio_view_config.xml"
MANUAL_XML = ROOT / "tools" / "label_studio" / "label_studio_view_config_manual.xml"
FOREIGN_MAIN_XML = FOREIGN_DIR / "label_studio_view_config_en.xml"
FOREIGN_MANUAL_XML = FOREIGN_DIR / "label_studio_view_config_manual_en.xml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_https_foreign_userscript_is_isolated_from_current_http_path():
    text = read(SCRIPT)

    assert "@match        https://label.sparkle0825.top/*" in text
    assert "http://175.178.71.217:8000" not in text
    assert "window.location.origin" in text
    assert 'window.localStorage.getItem("HOHONET_HELPER_BASE_URL") || window.location.origin' in text


def test_https_foreign_debug_userscript_uses_same_https_path_and_debug_flavor():
    text = read(DEBUG_SCRIPT)

    assert "HoHoNet Helper Official Annotator HTTPS EN DEBUG" in text
    assert "@version      stage1_helper_ordercache_hotfix_20260617_v1" in text
    assert "@match        https://label.sparkle0825.top/*" in text
    assert "http://175.178.71.217:8000" not in text
    assert 'const SCRIPT_VERSION = "stage1_helper_ordercache_hotfix_20260617_v1";' in text
    assert 'window.__HOHONET_HELPER_SCRIPT_FLAVOR__ = "foreign_https_en_debug";' in text
    assert 'window.localStorage.getItem("HOHONET_DEBUG_PANEL") !== "0"' in text


def test_https_foreign_userscript_captures_cloudresearch_ids():
    text = read(SCRIPT)

    for token in [
        "participantId",
        "workerId",
        "worker_id",
        "hohonet_worker_id",
        "wid",
        "assignmentId",
        "projectId",
    ]:
        assert token in text

    for field in [
        "external_worker_id",
        "connect_participant_id",
        "connect_assignment_id",
        "connect_project_id",
        "foreign_https_script_version",
    ]:
        assert field in text


def test_https_foreign_userscript_is_self_contained_not_remote_loader():
    text = read(SCRIPT)

    assert "fetchFirstAvailableHelper" not in text
    assert "/tools/official/ls_userscript_annotator.js" not in text
    assert "/tools/ls_userscript.js?foreign_https_en" not in text
    assert "@version      stage1_helper_ordercache_hotfix_20260617_v1" in text
    assert 'const SCRIPT_VERSION = "stage1_helper_ordercache_hotfix_20260617_v1";' in text
    assert "...getForeignRecruitmentMetadataForPayload()," in text
    assert "Missing HOHONET_LOG_TOKEN" in text
    assert "window.__HOHONET_HELPER_SCRIPT_VERSION__ = SCRIPT_VERSION;" in text
    assert 'window.__HOHONET_HELPER_SCRIPT_FLAVOR__ = "foreign_https_en";' in text
    assert "getQueryValueByKeys([\"logToken\"" not in text
    assert '"hohonet_log_token"' not in text
    assert "Refresh 3D View" in text
    assert "Preview Order" in text
    assert "Hide Labels" in text
    assert "Show Labels" in text
    assert "Submission blocked: inconsistent meta labels were detected." in text
    assert "提交被拦截：检测到元标签不合规。" in text
    assert "Difficulty conflict: `trivial` cannot be selected together" in text
    assert "Local saved order: no" in text
    assert "Current preview: default order" in text
    assert "HoHoNet Debug" in text


def test_https_foreign_active_time_requires_visible_annotation_page():
    text = read(SCRIPT)

    assert "function isActiveTimeCountingPage()" in text
    assert "return isPageVisible && isWindowFocused && isLikelyAnnotationPage();" in text
    assert "let isWindowFocused = document.hasFocus();" in text
    assert 'window.addEventListener("blur"' in text
    assert 'window.addEventListener("focus"' in text
    assert "if (isActiveTimeCountingPage())" in text
    assert "lastPostedSecondsByTask" in text
    assert "report.reportSeconds <= lastPostedSeconds" in text
    assert "shouldFlushActiveTimeOnCountingStop" in text
    assert 'closeActiveTimeSegment("BLUR")' not in text
    assert 'closeActiveTimeSegment("LEAVE_ANNOTATION_PAGE")' in text
    assert 'closeActiveTimeSegment("VISIBILITY_HIDDEN", { keepalive: true })' in text
    assert text.count("if (!isActiveTimeCountingPage())") >= 2


def test_https_foreign_debug_active_time_matches_focus_and_delta_gates():
    text = read(DEBUG_SCRIPT)

    assert "function isActiveTimeCountingPage()" in text
    assert "return isPageVisible && isWindowFocused && isLikelyAnnotationPage();" in text
    assert "let isWindowFocused = document.hasFocus();" in text
    assert 'window.addEventListener("blur"' in text
    assert 'window.addEventListener("focus"' in text
    assert "lastPostedSecondsByTask" in text
    assert "report.reportSeconds <= lastPostedSeconds" in text
    assert "shouldFlushActiveTimeOnCountingStop" in text
    assert 'closeActiveTimeSegment("BLUR")' not in text
    assert 'closeActiveTimeSegment("VISIBILITY_HIDDEN", { keepalive: true })' in text


def test_official_active_time_uses_focus_and_delta_gates():
    text = read(OFFICIAL_SCRIPT)

    assert "@version      stage1_helper_ordercache_hotfix_20260617_v1" in text
    assert 'const SCRIPT_VERSION = "stage1_helper_ordercache_hotfix_20260617_v1";' in text
    assert "function isActiveTimeCountingPage()" in text
    assert "return isPageVisible && isWindowFocused && isLikelyAnnotationPage();" in text
    assert "let isWindowFocused = document.hasFocus();" in text
    assert 'window.addEventListener("blur"' in text
    assert 'window.addEventListener("focus"' in text
    assert "lastPostedSecondsByTask" in text
    assert "report.reportSeconds <= lastPostedSeconds" in text
    assert "shouldFlushActiveTimeOnCountingStop" in text
    assert 'closeActiveTimeSegment("BLUR")' not in text
    assert 'closeActiveTimeSegment("VISIBILITY_HIDDEN", { keepalive: true })' in text


def test_preview_order_cache_ack_text_is_not_mojibake():
    text = read(VIS_3D)

    assert "保存成功：本地缓存已更新" in text
    assert "删除成功：已恢复默认顺序" in text
    assert "本地缓存操作失败" in text
    for mojibake in [
        "宸蹭繚",
        "宸插垹",
        "鏈湴",
        "绻氱€",
        "閺堫",
    ]:
        assert mojibake not in text


def test_preview_order_message_listener_is_robust_to_iframe_recreation():
    for path in [OFFICIAL_SCRIPT, SCRIPT, DEBUG_SCRIPT]:
        text = read(path)
        assert "function isPreviewOrderMessage(data)" in text
        assert '\"hohonet_preview_order_save\"' in text
        assert "event.source !== iframe.contentWindow" not in text
        assert "currentPreviewDefaultCount ||" in text
        assert "Array.isArray(data.previewOrder) ? data.previewOrder.length : 0" in text
        assert "postPreviewOrderAck(iframe, \"save\", false, \"invalid_payload\")" in text


def test_corner_order_cache_hotfix_is_inline_and_task_scoped():
    for path in [OFFICIAL_SCRIPT, OFFICIAL_DEBUG_SCRIPT, SCRIPT, DEBUG_SCRIPT]:
        text = read(path)
        assert 'const CORNER_ORDER_CACHE_SCHEMA = "corner_order_cache_v1";' in text
        assert 'const SCRIPT_VERSION = "stage1_helper_ordercache_hotfix_20260617_v1";' in text
        assert "`project:${context.project_id}::task:${context.task_id}::user:${context.user_id}`" in text
        assert "schema: CORNER_ORDER_CACHE_SCHEMA" in text
        assert "entries[taskKey]" in text
        assert "project_id: context.project_id" in text
        assert "task_id: context.task_id" in text
        assert "user_id: context.user_id" in text
        assert "corner_count: order.length" in text
        assert "validateCornerOrderCacheRecord" in text
        assert "corner_count_mismatch" in text
        assert "invalid_order_missing_duplicate_or_out_of_range" in text
        assert "persistAdjustedPreviewOrder(" in text
        assert '"preview_order_state"' in text
        assert "loadValidatedPreviewOrderOverride(previewTaskKey" in text
        assert text.index("applyPreviewRuntimeFromLayout(\n            previewTaskKey") < text.index(
            "loadValidatedPreviewOrderOverride(previewTaskKey"
        )
        assert "window.__HOHONET_CLEAR_CORNER_ORDER_CACHE_FOR_CURRENT_TASK__" in text
        assert "@require" not in text
        assert "ls_corner_order_state.js" not in text


def test_manhattan_corner_order_cache_hotfix_is_inline_and_task_scoped():
    for path in [MANHATTAN_DEBUG_SCRIPT, MANHATTAN_TIMED_SCRIPT]:
        text = read(path)
        assert "@version      stage1_helper_ordercache_hotfix_20260617_v1" in text
        assert 'const PANEL_VERSION = "stage1_helper_ordercache_hotfix_20260617_v1";' in text
        assert 'const CORNER_ORDER_CACHE_SCHEMA = "corner_order_cache_v1";' in text
        assert "`project:${context.project_id}::task:${context.task_id}::user:${context.user_id}`" in text
        assert "loadValidatedCornerOrderCache(cacheKey" in text
        assert "persistOrClearCurrentPreviewOrder(\"manhattan_preview_order_update\")" in text
        assert "clearCornerOrderCache(getCornerOrderCacheKey())" in text
        assert "window.__HOHONET_CLEAR_CORNER_ORDER_CACHE_FOR_CURRENT_TASK__" in text
        assert "invalid_order_missing_duplicate_or_out_of_range" in text
        assert "corner_count_mismatch" in text
        assert "@require" not in text
        assert "ls_corner_order_state.js" not in text

    prototype_text = read(MANHATTAN_PROTO_SCRIPT)
    assert "currentPreviewOrder" not in prototype_text
    assert "corner_order_cache_v1" not in prototype_text


def test_foreign_preview_order_status_translates_current_viewer_messages():
    for path in [SCRIPT, DEBUG_SCRIPT]:
        text = read(path)
        assert '["保存成功：本地缓存已更新", "Save successful: local cache updated"]' in text
        assert '["删除成功：已恢复默认顺序", "Delete successful: default order restored"]' in text
        assert '["本地缓存操作失败", "Local cache operation failed"]' in text


def test_foreign_worker_docs_include_required_timing_and_scope_warnings():
    guide = read(GUIDE)
    install = read(INSTALL)

    assert "Do not browse other Label" in guide
    assert "projects or tasks" in guide
    assert "Open unrelated projects or tasks" in guide
    assert "confirm that active-time logging is working" in guide
    assert "Before each annotation session" in guide
    assert "current Label Studio form may still require geometry fields" in guide
    assert "Check Active-Time Logging" in install
    assert "https://label.sparkle0825.top" in install
    assert 'localStorage.setItem("HOHONET_LOG_TOKEN",' in install
    assert 'console.log(localStorage.getItem("HOHONET_LOG_TOKEN"));' not in install
    assert 'console.log((localStorage.getItem("HOHONET_LOG_TOKEN") || "").length);' in install
    assert 'localStorage.setItem("HOHONET_HELPER_BASE_URL", "https://label.sparkle0825.top");' in install
    assert "successful" in install
    assert "`200` or `204`" in install
    assert "logToken=" not in install
    assert "foreign_https_en" in install
    assert "ls_userscript_annotator_https_en_debug.user.js" in install
    assert "foreign_https_en_debug" in install


def test_cloudresearch_guide_does_not_recommend_waves_for_passer_selection():
    text = read(CLOUDRESEARCH)

    assert "Do not use Connect Waves" in text
    assert "Included Participants / Connect IDs" in text
    assert "participantId" in text
    assert "https://label.sparkle0825.top:8080" not in text


def test_existing_xml_has_bilingual_rule_text_without_adding_new_export_fields():
    main = read(MAIN_XML)
    manual = read(MANUAL_XML)

    assert 'name="scope_rule_text_en"' not in main
    assert 'name="difficulty_rule_text_en"' not in main
    assert 'name="model_issue_rule_text_en"' not in main
    assert "General rule: first decide whether the camera room" in main
    assert "Rule: select the difficulty factors" in main
    assert "Rule: select at least one model-issue label" in main
    assert 'alias="overextend_adjacent" hint=' in main
    assert 'alias="corner_duplicate" hint=' in main

    assert 'name="scope_rule_text_en"' not in manual
    assert 'name="difficulty_rule_text_en"' not in manual
    assert 'name="model_issue_rule_text_en"' not in manual
    assert "General rule: first decide whether the camera room" in manual
    assert "Rule: select at least one option" in manual
    assert 'alias="occlusion" hint=' in manual


def test_foreign_english_xml_configs_are_parseable_and_schema_compatible():
    for path in [FOREIGN_MAIN_XML, FOREIGN_MANUAL_XML]:
        text = read(path)
        ET.fromstring(text)
        assert not any("\u4e00" <= char <= "\u9fff" for char in text)
        assert 'Image name="img" value="$image"' in text
        assert 'KeyPointLabels name="kp" toName="img"' in text
        assert 'BrushLabels name="wall_brush" toName="img"' in text
        assert 'HyperText name="vis_3d" value="$vis_3d"' in text
        assert 'Choices name="scope" toName="img"' in text
        assert 'Choices name="difficulty" toName="img"' in text
        assert 'name="scope_rule_text"' in text
        assert 'name="difficulty_rule_text"' in text
        assert 'alias="normal"' in text
        assert 'alias="oos_geometry"' in text
        assert 'alias="oos_open_boundary"' in text
        assert 'alias="oos_split_level"' in text
        assert 'alias="oos_insufficient"' in text
        assert 'alias="trivial"' in text
        assert 'alias="occlusion"' in text
        assert 'alias="low_texture"' in text
        assert 'alias="seam"' in text
        assert 'alias="reflection"' in text
        assert 'alias="low_quality"' in text
        assert "Annotation Feedback and Stratification" in text

    main = read(FOREIGN_MAIN_XML)
    assert 'Choices name="model_issue" toName="img"' in main
    assert 'name="model_issue_rule_text"' in main
    for alias in [
        "acceptable",
        "overextend_adjacent",
        "underextend",
        "over_parsing",
        "corner_drift",
        "corner_duplicate",
        "topology_failure",
        "fail",
    ]:
        assert f'alias="{alias}"' in main

    manual = read(FOREIGN_MANUAL_XML)
    assert 'Choices name="model_issue"' not in manual
    assert 'name="model_issue_rule_text"' not in manual
