from pathlib import Path

from tools.paper_a_manhattan.manhattan_column_evidence import (
    compute_column_evidence,
    inventory_hohonet_source,
    parse_hohonet_layout_txt,
)


def _pairs(offset=0.0):
    return [
        {
            "effective_pair_index": index,
            "top": {"x": x + offset, "y": 20.0},
            "bottom": {"x": x + offset, "y": 80.0},
        }
        for index, x in enumerate((10.0, 35.0, 60.0, 85.0), 1)
    ]


def _write_source(root: Path, stem="case") -> Path:
    path = root / "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34" / f"{stem}.txt"
    path.parent.mkdir(parents=True)
    path.write_text(
        "102 102\n102 410\n358 102\n358 410\n614 102\n614 410\n870 102\n870 410\n",
        encoding="utf-8",
    )
    return path


def test_source_inventory_and_parser_fail_closed(tmp_path):
    assert inventory_hohonet_source(
        {"source_image_basename": "missing.jpg"}, repo_root=tmp_path
    )["evidence_status"] == "unavailable"

    source_path = _write_source(tmp_path)
    source = inventory_hohonet_source(
        {"source_image_basename": "case.jpg"}, repo_root=tmp_path
    )
    assert source["evidence_status"] == "available"
    assert source["coordinate_contract"] == "hohonet_model_output_layout_txt@1024x512"

    second = tmp_path / "output/mp3d_layout/other/case.txt"
    second.parent.mkdir(parents=True)
    second.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    ambiguous = inventory_hohonet_source(
        {"source_image_basename": "case.jpg"}, repo_root=tmp_path
    )
    assert ambiguous["unavailable_reason"] == "ambiguous_hohonet_sources"

    uncontracted = tmp_path / "uncontracted.txt"
    uncontracted.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    invalid_contract = inventory_hohonet_source(
        {
            "source_image_basename": "uncontracted.jpg",
            "proposal_source_path": str(uncontracted.relative_to(tmp_path)),
        },
        repo_root=tmp_path,
    )
    assert invalid_contract["unavailable_reason"] == "missing_explicit_1024x512_coordinate_contract"

    invalid = tmp_path / "invalid.txt"
    invalid.write_text("1 2\n3 4\n", encoding="utf-8")
    assert parse_hohonet_layout_txt(invalid, width=1024, height=512)[
        "evidence_status"
    ] == "unavailable"


def test_column_evidence_delta_uses_candidate_minus_baseline(tmp_path):
    source = parse_hohonet_layout_txt(_write_source(tmp_path), width=1024, height=512)
    unchanged = compute_column_evidence(
        source, _pairs(), _pairs(), coordinate_mode="ls_percent"
    )
    moved = compute_column_evidence(
        source, _pairs(), _pairs(offset=1.0), coordinate_mode="ls_percent"
    )
    assert unchanged["evidence_status"] == "available"
    assert unchanged["candidate_corner_column_delta"] == 0.0
    assert moved["candidate_corner_column_delta"] > 0.0
    assert moved["source_provenance"]["source_sha256"]
