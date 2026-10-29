"""安全归档五个 v2.1 人员研究包，仅修复已核实的对象 ID 导出。"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
from pathlib import Path
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[3]
DESTINATION = ROOT / 'research/workers/personnel_v21_reselection_20261029'
PACKAGE_ORDER = ('06', '07B', '07C', '07D', '07A')
EXPORT_PATH = 'experiment/run_registered.py'
OLD_EXPORT = "    scalars=[native.native.scalar_row(r) for r in done.values()];sdir=Path(output)/'scalar_shards';sdir.mkdir(exist_ok=True)"
NEW_EXPORT = """    scalars=[]
    for r in done.values():
        scalar_input=dict(r)
        # Historical caches also store these fields as pipe-delimited strings.
        for field in ('member_workers','member_object_ids'):
            if isinstance(scalar_input[field],str):scalar_input[field]=scalar_input[field].split('|')
        scalars.append(native.native.scalar_row(scalar_input))
    sdir=Path(output)/'scalar_shards';sdir.mkdir(exist_ok=True)"""


def safe_destination(root: Path, member: str) -> Path:
    parts = member.split('/')
    if ('\\' in member or ':' in member or any(p in ('', '.', '..') for p in parts)
            or parts[0].casefold() == 'independent_review'):
        raise ValueError(f'unsafe_package_path: {member}')
    target = root.joinpath(*parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'package_path_escapes_destination: {member}')
    return target


def read_repairs(path: Path) -> dict[str, dict[str, dict[str, str]]]:
    repairs = {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['verified_against_local_snapshot'] != 'True':
                raise ValueError(f'unverified_repair: {row["team_key"]}')
            table = repairs.setdefault(row['table'], {})
            if row['team_key'] in table:
                raise ValueError(f'duplicate_repair: {row["team_key"]}')
            table[row['team_key']] = row
    return repairs


def repair_scalar_table(content: bytes, repairs: dict[str, dict[str, str]]) -> bytes:
    reader = csv.DictReader(io.StringIO(gzip.decompress(content).decode('utf-8-sig'), newline=''))
    fields = reader.fieldnames
    required = {'team_key', 'pool_id', 'k', 'member_workers', 'member_object_ids', 'B8L2'}
    if not fields or not required.issubset(fields):
        raise ValueError('scalar_schema_mismatch')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    seen = set()
    for row in reader:
        key = row['team_key']
        if key in repairs:
            fix = repairs[key]
            if key in seen or row['pool_id'] != fix['pool_id'] or row['member_object_ids'] != fix['raw']:
                raise ValueError(f'repair_source_mismatch: {key}')
            objects = fix['repaired'].split('|')
            workers = row['member_workers'].split('|')
            if len(objects) != int(row['k']) or len(set(objects)) != len(objects) or len(workers) != len(objects):
                raise ValueError(f'repair_member_count_mismatch: {key}')
            row['member_object_ids'] = fix['repaired']
            seen.add(key)
        writer.writerow(row)
    if seen != repairs.keys():
        raise ValueError(f'repair_rows_missing: {sorted(repairs.keys() - seen)}')
    return gzip.compress(output.getvalue().encode('utf-8-sig'), mtime=0)


def patch_scalar_export(content: bytes) -> bytes:
    source = content.decode('utf-8')
    if source.count(OLD_EXPORT) != 1:
        raise ValueError('scalar_export_call_site_changed')
    return source.replace(OLD_EXPORT, NEW_EXPORT).encode('utf-8')


def import_packages(packages: dict[str, Path], destination: Path, repair_map: Path) -> dict:
    repairs = read_repairs(repair_map)
    archives = {part: zipfile.ZipFile(path) for part, path in packages.items()}
    try:
        selected = {}; source_counts = {}; source_packages = {}
        for part in PACKAGE_ORDER:
            if part not in archives:
                continue
            archive = archives[part]
            entries = [info for info in archive.infolist() if not info.is_dir()]
            source_counts[part] = len(entries)
            for info in entries:
                safe_destination(destination, info.filename)
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError(f'package_symlink: {info.filename}')
                if info.filename in selected:
                    previous, previous_info = selected[info.filename]
                    if archives[previous].read(previous_info) != archive.read(info):
                        raise ValueError(f'conflicting_package_content: {info.filename}')
                selected[info.filename] = (part, info)
                source_packages.setdefault(info.filename, set()).add(part)
        if not repairs.keys() <= selected.keys():
            raise ValueError('repair_table_not_in_packages')
        modified = {}
        for name, table_repairs in repairs.items():
            if any(r['package'] not in source_packages[name] for r in table_repairs.values()):
                raise ValueError(f'repair_package_mismatch: {name}')
            part, info = selected[name]
            modified[name] = repair_scalar_table(archives[part].read(info), table_repairs)
        if EXPORT_PATH in selected:
            part, info = selected[EXPORT_PATH]
            modified[EXPORT_PATH] = patch_scalar_export(archives[part].read(info))
        receipt = {
            'data_release': 'v2.1', 'source_commit': 'a476461d7ede8db95da43de4139e612c05e618bc',
            'source_packages': [{'stage': part, 'path': str(packages[part]), 'file_entries': source_counts[part]}
                                for part in PACKAGE_ORDER if part in packages],
            'import_order': [part for part in PACKAGE_ORDER if part in packages],
            'source_file_entries': sum(source_counts.values()), 'unique_imported_files': len(selected),
            'repair_map': str(repair_map),
            'repaired_tables': [{'path': name, 'rows': len(rows), 'field': 'member_object_ids'}
                                for name, rows in sorted(repairs.items())],
            'repaired_rows': sum(map(len, repairs.values())),
            'source_raw_values_matched': True, 'all_other_csv_cells_preserved': True,
            'quality_values_changed': False, 'worker_members_changed': False,
            'patched_export': EXPORT_PATH if EXPORT_PATH in selected else None,
            'export_patch': 'Copy cached row; split string member fields before frozen scalar_row.',
            'frozen_repository_engine_changed': False, 'native_fusion_runs': 0, 'sha_calculated': False,
            'source_zips_changed': False, 'independent_review_changed': False,
            'author_reports': 'Original author reports retained as source material; docs main report not overwritten.',
        }
        modified['IMPORT_RECEIPT.json'] = (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        names = list(selected) + ['IMPORT_RECEIPT.json']

        def content(name):
            if name in modified:
                return modified[name]
            part, info = selected[name]
            return archives[part].read(info)

        # Preflight every file before writing any, including existing user content.
        conflicts = []
        for name in names:
            target = safe_destination(destination, name)
            data = content(name)
            if target.exists() and (not target.is_file() or target.read_bytes() != data):
                conflicts.append(name)
        if conflicts:
            raise ValueError(f'existing_content_differs: {conflicts}')
        for name in names:
            target = safe_destination(destination, name)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(content(name))
        return receipt
    finally:
        for archive in archives.values():
            archive.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads', type=Path, default=Path.home() / 'Downloads')
    args = parser.parse_args()
    packages = {}
    for part in PACKAGE_ORDER:
        matches = list(args.downloads.glob(f'HOHONET_v21_*{part}_*20261029.zip'))
        if len(matches) != 1:
            raise ValueError(f'expected_one_package: {part}: {matches}')
        packages[part] = matches[0]
    receipt = import_packages(packages, DESTINATION, DESTINATION / 'independent_review/member_object_id_repair_map.csv')
    print(json.dumps({'files': receipt['unique_imported_files'], 'repaired_rows': receipt['repaired_rows'],
                      'receipt': str(DESTINATION / 'IMPORT_RECEIPT.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
