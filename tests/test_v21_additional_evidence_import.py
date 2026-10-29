import csv
import io
import json
import stat
import zipfile

import pytest

from tools.thesis_main.analysis.import_v21_additional_evidence_20261029 import (
    MAP_FIELDS, import_packages, safe_destination,
)


def make_zip(path, rows):
    with zipfile.ZipFile(path, 'w') as archive:
        for name, content in rows:
            archive.writestr(name, content)
    return path


@pytest.mark.parametrize('member', ['../escape', '/absolute', 'x/../../escape',
                                  'x\\escape', 'D:/escape', 'x:ads', 'x//y',
                                  'NUL.txt', 'x/CON', 'x/trailing.', 'x/trailing '])
def test_rejects_unsafe_windows_zip_paths(tmp_path, member):
    with pytest.raises(ValueError):
        safe_destination(tmp_path, member)


def test_preserves_versions_primary_archive_and_exact_cells_idempotently(tmp_path):
    primary = tmp_path / 'primary'
    primary.mkdir()
    (primary / 'engine.py').write_bytes(b'approved_07A_with_repair\n')
    first = make_zip(tmp_path / 'first.zip', [('engine.py', b'old_source\n'),
                     ('results.csv', b'team,Q,object\r\na,81.000000000001,o1|o2\r\n')])
    second = make_zip(tmp_path / 'second.zip', [('engine.py', b'other_source\n'),
                      ('results.csv', b'team,Q,object\r\na,81.000000000001,o1|o2\r\n')])
    target = primary / 'additional_delivery'
    packages = {'03A': first, '03B_core': second}
    receipt = import_packages(packages, target, primary)
    before = {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}
    assert import_packages(packages, target, primary) == receipt
    assert {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()} == before
    assert (primary / 'engine.py').read_bytes() == b'approved_07A_with_repair\n'
    assert (target / 'packages/03A/engine.py').read_bytes() == b'old_source\n'
    assert (target / 'packages/03B_core/engine.py').read_bytes() == b'other_source\n'
    assert receipt['source_file_entries'] == 4
    assert receipt['distinct_member_paths'] == 2
    assert receipt['different_comparisons'] == 3
    assert receipt['identical_comparisons'] == 1
    rows = csv.DictReader(io.StringIO((target / 'PATH_MAP.csv').read_text(encoding='utf-8-sig')))
    assert tuple(rows.fieldnames) == MAP_FIELDS
    assert len(list(rows)) == 4
    assert json.loads((target / 'IMPORT_RECEIPT.json').read_text()) == receipt


def test_existing_difference_prevents_new_files(tmp_path):
    source = make_zip(tmp_path / 'source.zip', [('new.txt', b'new'), ('old.txt', b'source')])
    target = tmp_path / 'dest'
    (target / 'packages/03A').mkdir(parents=True)
    (target / 'packages/03A/old.txt').write_bytes(b'user content')
    with pytest.raises(ValueError, match='existing_content_differs'):
        import_packages({'03A': source}, target)
    assert not (target / 'packages/03A/new.txt').exists()
    assert (target / 'packages/03A/old.txt').read_bytes() == b'user content'


def test_rejects_case_collision_and_symlink_before_writing(tmp_path):
    source = make_zip(tmp_path / 'case.zip', [('A.txt', b'a'), ('a.txt', b'b')])
    with pytest.raises(ValueError, match='duplicate_package_path'):
        import_packages({'03A': source}, tmp_path / 'case_dest')
    assert not (tmp_path / 'case_dest').exists()
    link = zipfile.ZipInfo('escape')
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    source = make_zip(tmp_path / 'link.zip', [(link, b'../outside')])
    with pytest.raises(ValueError, match='package_symlink'):
        import_packages({'03A': source}, tmp_path / 'link_dest')


def test_crc_failure_does_not_leave_corrupt_file_or_success_receipt(tmp_path):
    source = make_zip(tmp_path / 'bad.zip', [('data.txt', b'known_payload')])
    data = source.read_bytes().replace(b'known_payload', b'wrong_payload', 1)
    source.write_bytes(data)
    target = tmp_path / 'dest'
    with pytest.raises(zipfile.BadZipFile):
        import_packages({'03A': source}, target)
    assert not (target / 'packages/03A/data.txt').exists()
    assert not (target / 'IMPORT_RECEIPT.json').exists()
