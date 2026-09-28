import json
import sys

import pytest

from tools.thesis_main.analysis import paper_a_contracts as legacy
from tools.thesis_main.analysis import render_paper_a_method_contract as renderer


def test_current_and_historical_contracts_have_separate_semantics():
    current = json.loads(renderer.CURRENT_METHOD_CONTRACT.read_text(encoding="utf-8"))
    old = legacy.load_method_contract()
    assert old["schema_version"] == "paper_a_method_contract_v9"
    assert current["schema_version"] == "consensus_research_contract_v1"
    assert legacy.METHOD_CONTRACT != renderer.CURRENT_METHOD_CONTRACT
    with pytest.raises(ValueError, match="not v9"):
        legacy.load_method_contract(renderer.CURRENT_METHOD_CONTRACT)
    text = renderer.render()
    assert "https://ceur-ws.org/Vol-2173/paper10.pdf" in text
    assert "目标GT仅评价" in text
    assert "不为AABC复制真人" in text
    assert "pending_manual_review_only" in text
    assert "SimpleITK" not in text  # 合同不把某台机器的依赖状态误当研究规范。
    assert old["contract_version"] in renderer.render(legacy.METHOD_CONTRACT)
    assert "Stage 3 gate separation" not in text


def test_reference_check_is_scoped_and_rejects_stale_research(tmp_path, monkeypatch):
    reference = tmp_path / "SOP.md"
    current = json.loads(renderer.CURRENT_METHOD_CONTRACT.read_text(encoding="utf-8"))
    reference.write_text(current["contract_version"], encoding="utf-8")
    monkeypatch.setattr(renderer, "RESEARCH_REFERENCES", (reference,))
    with pytest.raises(ValueError, match="stale"):
        renderer.check_references()
    reference.write_text(current["contract_version"] + " " + renderer.CURRENT_METHOD_CONTRACT.name,
                         encoding="utf-8")
    renderer.check_references()
    archive = tmp_path / "historical.json"
    archive.write_bytes(legacy.METHOD_CONTRACT.read_bytes())
    archive.with_suffix(".md").write_text(renderer.render(archive), encoding="utf-8")
    reference.unlink()
    renderer.check_references(archive)  # 历史检查不依赖新规范参考。
    archive.with_suffix(".md").write_text("stale", encoding="utf-8")
    with pytest.raises(ValueError, match="Historical"):
        renderer.check_references(archive)


def test_cli_defaults_output_to_selected_contract_and_protects_current(tmp_path, monkeypatch):
    archive = tmp_path / "historical.json"
    archive.write_bytes(legacy.METHOD_CONTRACT.read_bytes())
    monkeypatch.setattr(sys, "argv", ["render", "--contract", str(archive), "--render"])
    renderer.main()
    assert archive.with_suffix(".md").read_text(encoding="utf-8") == renderer.render(archive)
    monkeypatch.setattr(sys, "argv", ["render", "--contract", str(archive), "--output",
                                     str(renderer.CURRENT_METHOD_CONTRACT.with_suffix(".md"))])
    with pytest.raises(SystemExit):
        renderer.main()
