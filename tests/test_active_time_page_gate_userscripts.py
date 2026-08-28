from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "tools" / "label_studio" / "official" / "ls_userscript_annotator.js"
OFFICIAL_DEBUG = ROOT / "tools" / "label_studio" / "official" / "ls_userscript_debug.js"
FOREIGN = ROOT / "tools" / "label_studio" / "localized" / "en" / "ls_userscript_annotator_https_en.user.js"
FOREIGN_DEBUG = ROOT / "tools" / "label_studio" / "localized" / "en" / "ls_userscript_annotator_https_en_debug.user.js"
PRECHANGE = ROOT / "tools" / "label_studio" / "config_history" / "uncertainty_meta_v1_prechange_20260824"
PRECHANGE_OFFICIAL = PRECHANGE / "zh" / "userscript" / "ls_userscript_annotator.js"
PRECHANGE_OFFICIAL_DEBUG = PRECHANGE / "zh" / "userscript" / "ls_userscript_debug.js"
PRECHANGE_FOREIGN = PRECHANGE / "en" / "userscript" / "ls_userscript_annotator_https_en.user.js"
PRECHANGE_FOREIGN_DEBUG = PRECHANGE / "en" / "userscript" / "ls_userscript_annotator_https_en_debug.user.js"
INSTRUCTION_MANIFEST = ROOT / "tools" / "label_studio" / "label_studio_xml_instruction_manifest_v2.json"
VERSION = "uncertainty_meta_supervisor_draft_20260828_v9"


def _script(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_prechange_english_userscripts_preserve_the_v2_frozen_sha() -> None:
    manifest = json.loads(INSTRUCTION_MANIFEST.read_text(encoding="utf-8"))["userscript_relocation"]
    assert hashlib.sha256(PRECHANGE_FOREIGN.read_bytes()).hexdigest() == manifest["formal_en_sha256"]
    assert hashlib.sha256(PRECHANGE_FOREIGN_DEBUG.read_bytes()).hexdigest() == manifest["debug_en_sha256"]
    assert manifest["content_changed"] is False


def test_prechange_snapshot_contains_all_four_userscripts() -> None:
    for path in (PRECHANGE_OFFICIAL, PRECHANGE_OFFICIAL_DEBUG, PRECHANGE_FOREIGN, PRECHANGE_FOREIGN_DEBUG):
        assert path.is_file()
        assert VERSION not in _script(path)


def test_formal_userscripts_use_the_uncertainty_meta_version():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        assert f"// @version      {VERSION}" in source
        assert f'const SCRIPT_VERSION = "{VERSION}";' in source


def test_all_current_userscripts_keep_native_validation_and_small_cross_field_guards() -> None:
    for path in (OFFICIAL, OFFICIAL_DEBUG, FOREIGN, FOREIGN_DEBUG):
        source = _script(path)
        guard = source[source.index("function getDifficultyReasonConflict()"):source.index("function installMetaSubmitGuard()")]
        assert 'input[name="no_specific_reason"]' in guard
        assert '.closest(".lsf-choices")' in guard
        assert "if (!group || !noReason.checked) return false;" in guard
        assert 'querySelectorAll("input:checked").length > 1' in guard
        assert "getSelectedChoicesByField" not in source
        assert "collectSelectedResults" not in source
        assert "findMetaSectionContainer" not in source
        assert "normalizeChoiceToken" not in source
        for removed in (
            "difficulty_reason_status",
            "primary_issue_family",
            "no_issue_handling",
            "required_correction",
        ):
            assert removed not in guard
        assert "META_GUARD_REJECT_LOG_KEY" not in source
        assert "META_GUARD_REJECT_STATS_KEY" not in source


def test_material_issue_no_clears_and_fail_closes_stale_hidden_details() -> None:
    detail_names = (
        "boundary_misalignment",
        "current_space_undercoverage",
        "adjacent_space_inclusion",
        "spurious_nonlayout_structure",
        "duplicate_redundant_corner",
        "move_boundary_or_corner",
        "add_missing_boundary_or_corner",
        "remove_adjacent_space_segment",
        "remove_spurious_structure",
        "merge_or_delete_duplicate_corner",
        "local",
        "multi_region",
        "redraw",
    )
    for path in (OFFICIAL, OFFICIAL_DEBUG, FOREIGN, FOREIGN_DEBUG):
        source = _script(path)
        clear = source[source.index("const CONDITIONAL_ISSUE_DETAIL_NAMES"):source.index("function isMetaSubmitButton(")]
        install = source[source.index("function installMetaSubmitGuard()"):source.index("function findSectionContainer()")]

        for name in detail_names:
            assert f'"{name}"' in clear
        assert 'input[name="boundary_misalignment"]' in clear
        assert 'input[name="no"]' in clear
        assert 'input[name="yes"]' in clear
        assert "checked.forEach((input) => input.click())" in clear
        assert 'document.addEventListener(\n      "click"' in install
        assert 'const noIssueLabel = noIssue?.closest("label")' in install
        assert "window.setTimeout(clearConditionalIssueDetailsIfNoSelected, 0)" in install
        assert "clearConditionalIssueDetailsIfNoSelected()" in install
        assert "blocked this submit" in install


def test_preview_order_messages_are_accepted_only_from_the_bound_iframe() -> None:
    for path in (OFFICIAL, OFFICIAL_DEBUG, FOREIGN, FOREIGN_DEBUG):
        source = _script(path)
        listener = source[source.rindex('window.addEventListener("message"'):]

        assert "event.source !== iframe.contentWindow" in listener


def test_no_specific_difficulty_reason_is_mutually_exclusive_at_click_time() -> None:
    for path in (OFFICIAL, OFFICIAL_DEBUG, FOREIGN, FOREIGN_DEBUG):
        source = _script(path)
        helper = source[source.index("function enforceDifficultyReasonExclusivity("):source.index("const CONDITIONAL_ISSUE_DETAIL_NAMES")]

        assert "choice === noReason" in helper
        assert 'group.querySelectorAll("input:checked")' in helper
        assert "toClear.forEach((input) => input.click())" in helper
        assert "window.setTimeout(() => enforceDifficultyReasonExclusivity(choice.name), 0)" in source


def test_meta_guard_only_targets_real_label_studio_submit_controls() -> None:
    for path in (OFFICIAL, OFFICIAL_DEBUG, FOREIGN, FOREIGN_DEBUG):
        source = _script(path)
        start = source.index("function isMetaSubmitButton(target)")
        end = source.index("function installMetaSubmitGuard()", start)
        matcher = source[start:end]
        assert 'button?.closest?.(".lsf-controls")' in matcher
        assert 'button.name === "submit"' in matcher
        assert 'button.name === "update"' in matcher
        assert ".includes(" not in matcher
        assert 'const node = event.target?.closest?.("button")' in source


def test_active_time_panel_is_compact_draggable_and_defaults_above_submit_controls() -> None:
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        panel = source[source.index("function ensureActiveTimePanel("):source.index("function getActiveTimePanelMode(")]
        update = source[source.index("function updateActiveTimePanels("):source.index("function getLabelsVisible()")]

        assert "position: fixed; right: 12px;" in panel
        assert "function enableActiveTimePanelDrag(panel)" in panel
        assert 'panel.style.cursor = "grabbing"' in panel
        assert "ensureActiveTimePanel(ACTIVE_TIME_TOKEN_PANEL_ID, 64)" in update
        assert "⋮⋮ Active-Time" in update
        assert "routeTaskId" not in update[update.index("if (minimized)"):update.index("return;", update.index("if (minimized)"))]


def test_preview_order_is_persisted_only_by_the_explicit_save_action() -> None:
    for path in (OFFICIAL, OFFICIAL_DEBUG, FOREIGN, FOREIGN_DEBUG):
        source = _script(path)
        state_handler = source[source.index("function handlePreviewOrderStateMessage("):source.index("function handlePreviewOrderSaveMessage(")]
        save_handler = source[source.index("function handlePreviewOrderSaveMessage("):source.index("function handlePreviewOrderDeleteMessage(")]

        assert "persistAdjustedPreviewOrder" not in source
        assert "savePreviewOrderOverride" not in state_handler
        assert "savePreviewOrderOverride(taskKey" in save_handler


def test_all_current_userscripts_do_not_implement_phase_lock_or_phase_reporting() -> None:
    for path in (OFFICIAL, OFFICIAL_DEBUG, FOREIGN, FOREIGN_DEBUG):
        source = _script(path)
        for token in (
            "META_PHASE_STORAGE_PREFIX",
            "function applyUncertaintyPhaseUi(",
            "function installUncertaintyPhaseLock(",
            "pre_edit_locked_at",
            "geometry_locked_at",
            "uncertainty_meta_phase_event_v1",
        ):
            assert token not in source


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

    assert "⋮⋮ Active-Time · ${Math.round(seconds)} 秒" in official
    assert "⋮⋮ Active-Time · ${Math.round(seconds)}s" in foreign


def test_active_time_session_id_is_fresh_for_every_page_load():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        session = source[source.index("const sessionId = (() => {"):source.index("setInterval(() => {", source.index("const sessionId = (() => {"))]

        assert "crypto.randomUUID" in session
        assert "sessionStorage" not in session
        assert "SESSION_STORAGE_KEY" not in source


def test_active_time_requires_resolved_task_project_and_worker_identity():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)

        assert "function activeTimeIdentityReady(metadata)" in source
        assert "activeTimeIdentityReady(metadata)" in source
        assert '"identity_not_ready"' in source
        assert "if (!activeTimeIdentityReady(metadata)) return null;" in source


def test_route_task_source_is_audited_and_duplicate_switch_branch_is_removed():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        capture = source[source.index("function captureCurrentActiveTimeMetadata("):source.index("function buildActiveTimeKey(")]

        assert '"page_gate.route+dom"' in capture
        assert "taskCumulativeSeconds.get(currentTaskId)" not in source
        assert "taskId !== currentTaskId" not in source


def test_retry_queue_deletes_entries_after_fourteen_days():
    for path in (OFFICIAL, FOREIGN):
        source = _script(path)
        prune = source[source.index("function pruneActiveTimeRetryQueue("):source.index("function upsertActiveTimeRetryPayload(")]

        assert "14 * 24 * 60 * 60 * 1000" in source
        assert "delete queue[key]" in prune
        assert "expired_orphaned" not in source
