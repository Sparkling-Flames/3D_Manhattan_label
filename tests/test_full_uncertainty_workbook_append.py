import os
import subprocess
import zipfile
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "tools/thesis_main/analysis/full_uncertainty/build_full_uncertainty_v5_workbook.mjs"
NODE_PATH = Path(r"C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules")


def _workbook_xml(sheet_name: str) -> str:
    return (
        '<?xml version="1.0"?><x:workbook xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<x:sheets><x:sheet name="{sheet_name}" sheetId="1" r:id="rId1" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" /></x:sheets></x:workbook>'
    )


def _content_types(part_number: int = 1) -> str:
    return (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml" />'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml" />'
        '<Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml" />'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml" />'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml" />'
        f'<Override PartName="/xl/worksheets/sheet{part_number}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" />'
        f'<Override PartName="/xl/tables/table{part_number}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml" />'
        '</Types>'
    )


def _write_fixture(path: Path, sheet_name: str, table_name: str, *, part_number: int = 1) -> None:
    files = {
        "[Content_Types].xml": _content_types(part_number),
        "xl/workbook.xml": _workbook_xml(sheet_name),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/xl/worksheets/sheet{part_number}.xml" Id="rId1" />'
            '<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="/xl/theme/theme1.xml" Id="rId2" />'
            '<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="/xl/styles.xml" Id="rId3" />'
            '<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="/xl/sharedStrings.xml" Id="rId4" />'
            '</Relationships>'
        ),
        f"xl/worksheets/sheet{part_number}.xml": (
            '<x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<x:sheetData><x:row r="1"><x:c r="A1" s="0"><x:v>1</x:v></x:c></x:row></x:sheetData></x:worksheet>'
        ),
        f"xl/worksheets/_rels/sheet{part_number}.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="/xl/tables/table{part_number}.xml" Id="rId1" />'
            '</Relationships>'
        ),
        f"xl/tables/table{part_number}.xml": (
            '<x:table xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'id="{part_number}" name="{table_name}" displayName="{table_name}"><x:autoFilter ref="A1:A2" />'
            '<x:tableColumns count="1"><x:tableColumn id="1" name="value" /></x:tableColumns></x:table>'
        ),
        "xl/theme/theme1.xml": '<x:theme xmlns:x="http://schemas.openxmlformats.org/drawingml/2006/main" name="test" />',
        "xl/styles.xml": (
            '<x:styleSheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<x:fonts count="1"><x:font><x:sz val="10" /></x:font></x:fonts>'
            '<x:cellXfs count="1"><x:xf numFmtId="0" fontId="0" fillId="0" borderId="0" /></x:cellXfs>'
            '</x:styleSheet>'
        ),
        "xl/sharedStrings.xml": '<x:sst xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main" />',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    if not NODE_PATH.is_dir():
        pytest.skip("Codex Node runtime dependencies are unavailable")
    env = os.environ.copy()
    env["NODE_PATH"] = str(NODE_PATH)
    return subprocess.run(["node", str(SCRIPT), *args], text=True, capture_output=True, env=env)


def test_append_existing_success_and_sheet_count(tmp_path: Path) -> None:
    base = tmp_path / "base.xlsx"
    supplement = tmp_path / "supplement.xlsx"
    output = tmp_path / "output.xlsx"
    _write_fixture(base, "base", "TableBase")
    _write_fixture(supplement, "supplement", "TableSupplement")

    result = _run("--append-existing", str(base), str(supplement), str(output), "2")

    assert result.returncode == 0, result.stderr
    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
        assert workbook.count("<x:sheet ") == 2
        assert "xl/worksheets/sheet2.xml" in archive.namelist()
        assert "xl/tables/table2.xml" in archive.namelist()


def test_append_existing_uses_max_part_number_not_sheet_count(tmp_path: Path) -> None:
    base = tmp_path / "base.xlsx"
    supplement = tmp_path / "supplement.xlsx"
    output = tmp_path / "output.xlsx"
    _write_fixture(base, "base", "TableBase", part_number=8)
    _write_fixture(supplement, "supplement", "TableSupplement")

    result = _run("--append-existing", str(base), str(supplement), str(output), "2")

    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert "xl/worksheets/sheet8.xml" in names
        assert "xl/worksheets/sheet9.xml" in names
        assert "xl/tables/table8.xml" in names
        assert "xl/tables/table9.xml" in names


@pytest.mark.parametrize("duplicate_kind", ["sheet", "table"])
def test_append_existing_rejects_duplicate_names(tmp_path: Path, duplicate_kind: str) -> None:
    base = tmp_path / "base.xlsx"
    supplement = tmp_path / "supplement.xlsx"
    output = tmp_path / "output.xlsx"
    _write_fixture(base, "same-sheet" if duplicate_kind == "sheet" else "base", "same-table" if duplicate_kind == "table" else "TableBase")
    _write_fixture(supplement, "same-sheet" if duplicate_kind == "sheet" else "supplement", "same-table" if duplicate_kind == "table" else "TableSupplement")

    result = _run("--append-existing", str(base), str(supplement), str(output), "2")

    assert result.returncode != 0
    assert "duplicate" in result.stderr.lower()
    assert not output.exists()
