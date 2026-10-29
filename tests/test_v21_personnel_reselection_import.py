import ast
import copy
import csv
import gzip
import io
from types import SimpleNamespace
import zipfile

import pytest

from tools.thesis_main.analysis.import_v21_personnel_reselection_20261029 import (
    NEW_EXPORT, OLD_EXPORT, import_packages, patch_scalar_export, repair_scalar_table,
    safe_destination,
)


@pytest.mark.parametrize('name', ['../outside.txt', '/outside.txt', 'x/../../bad',
                                 'C:/outside', 'x\\outside', 'x:stream',
                                 'independent_review/README.md'])
def test_rejects_unsafe_or_protected_paths(tmp_path, name):
    with pytest.raises(ValueError):
        safe_destination(tmp_path, name)


def scalar_fixture():
    fields = ['team_key', 'pool_id', 'k', 'member_workers', 'member_object_ids', 'B8L2', 'D10']
    row = dict(zip(fields, ['team', 'pool', '2', 'W1|W2', 'o|n|e|||t|w|o', '81.000000000001', '']))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerow(row)
    repair = {'team': {'package': '07B', 'table': 'results.csv.gz', 'team_key': 'team',
                      'pool_id': 'pool', 'raw': row['member_object_ids'], 'repaired': 'one|two',
                      'verified_against_local_snapshot': 'True'}}
    return gzip.compress(stream.getvalue().encode()), row, repair


def test_repairs_only_object_cell_and_rejects_stale_map():
    data, original, repairs = scalar_fixture()
    repaired = repair_scalar_table(data, repairs)
    row = next(csv.DictReader(io.StringIO(gzip.decompress(repaired).decode('utf-8-sig'))))
    assert row == dict(original, member_object_ids='one|two')
    repairs['team']['raw'] = 'different'
    with pytest.raises(ValueError, match='repair_source_mismatch'):
        repair_scalar_table(data, repairs)


def test_import_is_idempotent_and_refuses_conflicting_existing_content(tmp_path):
    data, _, repairs = scalar_fixture()
    package = tmp_path / 'source.zip'
    with zipfile.ZipFile(package, 'w') as archive:
        archive.writestr('results.csv.gz', data)
        archive.writestr('README.md', 'author source')
    repair_map = tmp_path / 'repairs.csv'
    with repair_map.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(repairs['team']))
        writer.writeheader(); writer.writerows(repairs.values())
    destination = tmp_path / 'imported'
    first = import_packages({'07B': package}, destination, repair_map)
    before = {p.name: p.read_bytes() for p in destination.iterdir()}
    assert import_packages({'07B': package}, destination, repair_map) == first
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == before
    (destination / 'README.md').write_text('user edits')
    with pytest.raises(ValueError, match='existing_content_differs'):
        import_packages({'07B': package}, destination, repair_map)
    assert (destination / 'README.md').read_text() == 'user edits'


@pytest.mark.parametrize('objects_as_string', [False, True])
@pytest.mark.parametrize('workers_as_string', [False, True])
def test_scalar_call_normalizes_strings_without_mutating_cache(objects_as_string, workers_as_string):
    source = 'def export(done, native, Path, output):\n' + OLD_EXPORT + '\n    return scalars\n'
    patched = patch_scalar_export(source.encode()).decode()
    assert NEW_EXPORT in patched
    ast.parse(patched)
    namespace = {}
    exec(patched, namespace)
    row = {'member_workers': 'W1|W2' if workers_as_string else ['W1', 'W2'],
           'member_object_ids': 'one|two' if objects_as_string else ['one', 'two'], 'B8L2': 81.25}
    before = copy.deepcopy(row)
    native = SimpleNamespace(native=SimpleNamespace(scalar_row=lambda r: dict(
        r, member_workers='|'.join(r['member_workers']), member_object_ids='|'.join(r['member_object_ids']))))
    class NoWritePath:
        def __truediv__(self, name):
            return self

        def mkdir(self, **kwargs):
            pass

    result = namespace['export']({'team': row}, native, lambda _: NoWritePath(), 'unused')
    assert result == [{'member_workers': 'W1|W2', 'member_object_ids': 'one|two', 'B8L2': 81.25}]
    assert row == before
