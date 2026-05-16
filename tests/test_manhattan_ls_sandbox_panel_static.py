from pathlib import Path


SCRIPT_PATH = Path("tools/dev_only/manhattan_ls_sandbox_panel.user.js")


def read_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_script_is_dev_only_path_and_has_guard_text():
    assert SCRIPT_PATH.as_posix() == "tools/dev_only/manhattan_ls_sandbox_panel.user.js"
    text = read_script()

    for required in [
        "dev-only",
        "sandbox-only",
        "expert/developer tester only",
        "not official userscript",
        "not worker-facing",
        "no writeback",
        "no submit",
        "no routing",
        "no formal g_t",
        "no P1/C1/C2/T1/V1 artifact",
    ]:
        assert required in text


def test_script_has_no_network_write_methods_or_submit_trigger():
    text = read_script()

    for forbidden in ["POST", "PUT", "PATCH", "DELETE", "fetch(", "XMLHttpRequest"]:
        assert forbidden not in text

    for forbidden in [".submit(", "requestSubmit(", ".click("]:
        assert forbidden not in text


def test_script_does_not_contain_annotation_change_payload_terms():
    text = read_script().lower()

    for forbidden in [
        "snap_to_axis",
        "adjustment_vector",
        "corrected annotation",
        "worker tier label",
        "routing decision",
    ]:
        assert forbidden not in text


def test_script_contains_panel_guardrails_and_placeholders():
    text = read_script()

    for expected in [
        "keypoint_read_status",
        "keypoint_count",
        "Compatibility",
        "Residual",
        "Preview-only suggestion",
        "Guardrails",
        "placeholder only",
        "no correctness label",
        "no worker tier",
        "no snap coordinates",
        "no adjustment vector",
        "no auto-correction",
    ]:
        assert expected in text
