from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "foreign_recruitment" / "ls_userscript_annotator_https_en.user.js"
DEBUG_SCRIPT = ROOT / "foreign_recruitment" / "ls_userscript_annotator_https_en_debug.user.js"
GUIDE = ROOT / "foreign_recruitment" / "ANNOTATOR_GUIDE_EN.md"
INSTALL = ROOT / "foreign_recruitment" / "INSTALL_USERSCRIPT_HTTPS_EN.md"
CLOUDRESEARCH = ROOT / "foreign_recruitment" / "CLOUDRESEARCH_CONNECT_SETUP_GUIDE.md"
MAIN_XML = ROOT / "tools" / "label_studio_view_config.xml"
MANUAL_XML = ROOT / "tools" / "label_studio_view_config_manual.xml"


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
    assert "@match        https://label.sparkle0825.top/*" in text
    assert "http://175.178.71.217:8000" not in text
    assert 'const SCRIPT_VERSION = "0.26-foreign-https-en-debug";' in text
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
    assert 'const SCRIPT_VERSION = "0.26-foreign-https-en-standalone";' in text
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
    assert 'localStorage.setItem("HOHONET_LOG_TOKEN", "YOUR_LOG_TOKEN");' in install
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
