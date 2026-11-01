#!/usr/bin/env python3
"""Complete the compact reproduction inputs and package standalone ZIPs.

No scientific input or result is modified. Existing projected path tables and
their portable indices remain unchanged. Missing frozen geometry, exact source
links, k=2 supplements, reference definitions and small audit files are copied.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import time
import zipfile

from package_path_events import HashingReader, atomic_json, sha256_file, CHUNK, MAX_ARCHIVE_BYTES

csv.field_size_limit(256 * 1024 * 1024)


def atomic_csv(path: Path, rows: list[dict]) -> None:
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def complete_inputs(root: Path):
    out = root / 'reproduction_inputs'
    scope_before = json.loads((out / 'INPUT_SCOPE.json').read_text())
    selected = {}

    def add(relative: str, purpose: str):
        source = root / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        selected[relative] = purpose

    for p in sorted((root / 'stage02_normalized/doorway_enriched/geometry').glob('*.csv.gz')):
        add(p.relative_to(root).as_posix(), 'Frozen doorway geometry catalog for exact endpoint-source lookup and geometric pair distances')
    assert sum('/geometry/' in p for p in selected) == 17
    for p in sorted((root / 'stage02_normalized/manual/k2_overlay').glob('*.csv.gz')):
        add(p.relative_to(root).as_posix(), 'Independent k=2 supplement; original main path rows are not overwritten')
    assert sum('/k2_overlay/' in p for p in selected) == 206

    for relative in ('stage02_normalized/manual', 'stage02_normalized/doorway', 'stage02_normalized/doorway_enriched'):
        for p in sorted((root / relative).iterdir()):
            if p.is_file() and p.suffix in ('.csv', '.json', '.md') and p.name != 'POOL_INDEX.csv':
                add(p.relative_to(root).as_posix(), 'Original small source/index/audit metadata; historical hashes refer to unprojected upstream files')
    add('stage02_normalized/doorway/ENDPOINT_SOURCES.csv.gz', 'Exact source-key, team-member and physical endpoint linkage')
    for rel, purpose in [
        ('source/repo/research/fusion/doorway_population_v21_20261031/HOHONET_doorway_v21_20261031/stage04_computation/recovered_reference_scores/FINAL_REFERENCES.json', 'Adopted final full doorway references: 17 images by three targets'),
        ('source/repo/research/fusion/doorway_population_v21_20261031/HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz', 'Frozen complete original doorway annotations'),
        ('source/repo/research/data/doorway_review_20261030/screen439_results_20261031/POOLS.json', 'Adopted current 584/439 and target-specific pool identities'),
        ('stage00_doorway_sources/source/research/data/doorway_review_20261030/expanded_visual_review_20261031/FINAL_SCREENING_LEDGER.json', 'Final manual screening and scope attribution ledger'),
        ('stage00_doorway_sources/DOWNSTREAM_HANDOFF_ZH.md', 'Source adoption, frozen-score mapping and diagnostic replay scope'),
        ('stage00_manual_sources/repo/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/engine26/derive_frozen_blocks.py', 'Frozen quality component formula source used by analyze_response_components.py'),
    ]:
        add(rel, purpose)

    copied = []
    for rel, purpose in selected.items():
        src, dst = root / rel, out / rel
        h = sha256_file(src)
        if dst.exists():
            assert sha256_file(dst) == h, f'Existing input differs; refusing to overwrite: {rel}'
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            temp = dst.with_name(dst.name + '.tmp')
            shutil.copy2(src, temp)
            assert sha256_file(temp) == h
            os.replace(temp, dst)
        copied.append(dict(path=rel, bytes=src.stat().st_size, source_sha256=h, copy_sha256=sha256_file(dst), purpose=purpose))
    atomic_csv(out / 'INPUT_ADDITIONS_MANIFEST.csv', copied)

    dependencies = []
    for mode in ('manual', 'doorway', 'doorway_enriched'):
        index_path = f'stage02_normalized/{mode}/POOL_INDEX.csv'
        rows = load_csv(out / index_path)
        assert all('absolute_file' not in r and 'absolute_path' not in r for r in rows)
        for row in rows:
            rel = row.get('normalized_file') or row.get('path')
            assert rel and (out / rel).is_file(), (index_path, row['pool_id'], rel)
            dependencies.append(dict(index=index_path, identifier=row['pool_id'], dependency=rel, exists=True, type='projected_exact_path_table'))
            overlay = row.get('k2_overlay_file')
            if overlay:
                assert (out / overlay).is_file(), overlay
                dependencies.append(dict(index=index_path, identifier=row['pool_id'], dependency=overlay, exists=True, type='independent_k2_overlay'))
    for index_rel, path_column, id_column, kind in [
        ('stage02_normalized/doorway_enriched/GEOMETRY_CATALOG_INDEX.csv', 'path', 'image', 'doorway_geometry_catalog'),
        ('stage02_normalized/manual/K2_OVERLAY_INDEX.csv', 'normalized_file', 'pool_id', 'independent_k2_overlay'),
    ]:
        for row in load_csv(out / index_rel):
            rel = row[path_column]
            assert (out / rel).is_file(), rel
            if row.get('sha256'):
                assert sha256_file(out / rel) == row['sha256'], rel
            dependencies.append(dict(index=index_rel, identifier=row[id_column], dependency=rel, exists=True, type=kind))

    # Direct non-index inputs of the downstream scripts.
    direct = [
        'source/repo/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/analysis_geometry26/results_stage2/GEOMETRY_PATH_PRECISION.csv.gz',
        'source/repo/research/data/releases/v2.1/new_space_geometry/NEW_SPACE_GEOMETRY_CURVES.csv.gz',
        'source/repo/research/data/releases/v2.1/natural_results/NATURAL_CURVE_BANDS.csv.gz',
        'source/repo/research/data/doorway_review_20261030/screen439_results_20261031/BASE_256_ORDERS.csv.gz',
    ]
    for rel in direct:
        assert (out / rel).is_file(), rel
        dependencies.append(dict(index='script_direct_input', identifier=Path(rel).name, dependency=rel, exists=True, type='frozen_source_table'))
    atomic_csv(out / 'INPUT_DEPENDENCY_CHECKS.csv', dependencies)
    additions_scope = {
        'original_projection_scope_unchanged': scope_before,
        'copied_additional_files': len(copied),
        'copied_additional_bytes': sum(r['bytes'] for r in copied),
        'all_additional_source_hashes_match': True,
        'doorway_geometry_catalog_files': 17,
        'ordinary_k2_overlay_files': 206,
        'checked_index_or_direct_dependencies': len(dependencies),
        'all_checked_dependencies_present': True,
        'projected_pool_indices_preserved': True,
        'current_reference_and_original_annotation_definitions_included': True,
        'source_scope': 'Fixed repo e1873bfadc1d0e61499809c91fba9dc39c717f83; current 584/439 doorway pools',
        'research_sources_modified': False,
        'note': 'Original audit hashes refer to upstream unprojected files. INPUT_PROJECTION_MANIFEST.csv maps projected tables to upstream hashes. This bundle supports downstream analyses from existing endpoints; it does not contain all source geometry ZIPs, all panoramas, or all full fusion states.',
    }
    atomic_json(out / 'INPUT_ADDITIONS_SCOPE.json', additions_scope)
    return copied, dependencies


def inventory(root: Path):
    out = root / 'reproduction_inputs'
    projections = {r['path']: r for r in load_csv(out / 'INPUT_PROJECTION_MANIFEST.csv')}
    additions = {r['path']: r for r in load_csv(out / 'INPUT_ADDITIONS_MANIFEST.csv')}
    expected = {p: int(r['rows']) for p, r in projections.items()}
    for row in load_csv(out / 'stage02_normalized/manual/K2_OVERLAY_INDEX.csv'):
        expected[row['normalized_file']] = int(row['paths'])
    for row in load_csv(out / 'stage02_normalized/doorway_enriched/GEOMETRY_CATALOG_INDEX.csv'):
        expected[row['path']] = int(row['geometry_states'])
    records = []
    for path in sorted(out.rglob('*')):
        if not path.is_file():
            continue
        if any(part.endswith(('.tmp', '.writing', '.pyc')) or part == '__pycache__' for part in path.parts):
            raise RuntimeError(f'Temporary file found in inputs: {path}')
        rel = path.relative_to(out).as_posix()
        stat = path.stat()
        upstream = projections.get(rel, {}).get('upstream_normalized_sha256') or additions.get(rel, {}).get('source_sha256') or ''
        known_hash = projections.get(rel, {}).get('sha256') or additions.get(rel, {}).get('copy_sha256') or ''
        records.append(dict(input_path=rel, archive_member=root.name + '/' + rel, source_bytes=stat.st_size,
                            source_mtime_ns=stat.st_mtime_ns, expected_sha256=known_hash,
                            upstream_unprojected_sha256=upstream,
                            projected_endpoint_table=rel in projections,
                            expected_csv_data_rows=expected.get(rel)))
    return records


def partition(records):
    parts, current, estimated = [], [], 22
    for record in records:
        allowance = record['source_bytes'] + 1024 + 2 * len(record['archive_member'].encode())
        if allowance + 22 > MAX_ARCHIVE_BYTES:
            raise RuntimeError(f'Input too large for one ordinary ZIP: {record["input_path"]}')
        if current and estimated + allowance > MAX_ARCHIVE_BYTES:
            parts.append(current)
            current, estimated = [], 22
        current.append(record)
        estimated += allowance
    if current:
        parts.append(current)
    return parts


def package_part(root, number, records):
    started = time.monotonic()
    name = f'04_Reproduction_Inputs_Part{number:02d}.zip'
    path = root / 'delivery' / name
    temp = path.with_name(path.name + '.tmp')
    if path.exists():
        raise FileExistsError(path)
    source_hashes = {}
    with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_STORED, allowZip64=False) as z:
        for r in records:
            src = root / 'reproduction_inputs' / r['input_path']
            stat = src.stat()
            assert (stat.st_size, stat.st_mtime_ns) == (r['source_bytes'], r['source_mtime_ns'])
            info = zipfile.ZipInfo(r['archive_member'], date_time=(2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.file_size = stat.st_size
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            h = hashlib.sha256()
            with src.open('rb') as f, z.open(info, 'w', force_zip64=False) as dst:
                while block := f.read(CHUNK):
                    h.update(block)
                    dst.write(block)
            source_hashes[r['archive_member']] = h.hexdigest()
            if r['expected_sha256']:
                assert h.hexdigest() == r['expected_sha256'], r['input_path']
            after = src.stat()
            assert (after.st_size, after.st_mtime_ns) == (stat.st_size, stat.st_mtime_ns)
    assert temp.stat().st_size <= MAX_ARCHIVE_BYTES
    results = []
    with zipfile.ZipFile(temp, 'r') as z:
        assert z.namelist() == [r['archive_member'] for r in records]
        assert z.testzip() is None
        for r in records:
            compressed = HashingReader(z.open(r['archive_member'], 'r'))
            b = io.BufferedReader(compressed, buffer_size=CHUNK)
            is_gz = r['input_path'].endswith('.gz')
            content = gzip.GzipFile(fileobj=b, mode='rb') if is_gz else b
            plain = HashingReader(content)
            pb = io.BufferedReader(plain, buffer_size=CHUNK)
            csv_rows, csv_columns, identity_columns = None, None, None
            suffix = r['input_path'][:-3] if is_gz else r['input_path']
            if suffix.endswith('.csv'):
                with io.TextIOWrapper(pb, encoding='utf-8-sig', newline='') as text:
                    reader = csv.reader(text)
                    header = next(reader, None)
                    assert header is not None, r['input_path']
                    csv_columns = len(header)
                    csv_rows = 0
                    for row in reader:
                        assert len(row) == len(header), (r['input_path'], csv_rows)
                        csv_rows += 1
                    if r['projected_endpoint_table']:
                        required = {'pool_id','image','target_id','reference_id','reference_version','N','k','replicate_id','team_key','member_object_ids','member_workers','B8L2','D10','IoU3D100','complete_evaluable'}
                        assert required <= set(header), (r['input_path'], required - set(header))
                        identity_columns = True
                if r['expected_csv_data_rows'] is not None:
                    assert csv_rows == r['expected_csv_data_rows'], (r['input_path'], csv_rows, r['expected_csv_data_rows'])
            elif suffix.endswith('.json'):
                with io.TextIOWrapper(pb, encoding='utf-8-sig') as text:
                    json.load(text)
            else:
                with pb:
                    while pb.read(CHUNK):
                        pass
            b.close()
            assert compressed.bytes_read == r['source_bytes'], r['input_path']
            assert compressed.hash.hexdigest() == source_hashes[r['archive_member']], r['input_path']
            results.append({**r, 'package_name': name, 'source_sha256': source_hashes[r['archive_member']],
                            'archive_member_sha256': compressed.hash.hexdigest(),
                            'uncompressed_sha256': plain.hash.hexdigest(), 'uncompressed_bytes': plain.bytes_read,
                            'csv_data_rows': csv_rows, 'csv_columns': csv_columns,
                            'exact_identity_and_reference_columns_retained': identity_columns,
                            'inner_gzip_read_to_eof': True if is_gz else None,
                            'source_equals_archive_member': True, 'parse_or_read_to_eof': True})
    package_hash = sha256_file(temp)
    os.replace(temp, path)
    summary = dict(package_name=name, bytes=path.stat().st_size, MiB=path.stat().st_size/(1024*1024),
                   sha256=package_hash, files=len(results), gzip_files=sum(r['input_path'].endswith('.gz') for r in results),
                   csv_files=sum(r['csv_data_rows'] is not None for r in results),
                   csv_data_rows=sum(r['csv_data_rows'] or 0 for r in results),
                   uncompressed_bytes=sum(r['uncompressed_bytes'] for r in results),
                   zip_testzip='passed', all_gzip_eof=True, all_source_hashes_match=True,
                   all_required_identity_columns_retained=True, standalone_ordinary_zip=True,
                   no_reproduction_inputs_middle_layer=True, within_250_MiB=True,
                   elapsed_seconds=round(time.monotonic()-started,3))
    for r in results:
        r['package_bytes'] = summary['bytes']
        r['package_sha256'] = package_hash
    atomic_json(root/'stage09_delivery'/f'REPRODUCTION_INPUT_PART{number:02d}_VALIDATION.json', dict(summary=summary, files=results))
    print(json.dumps(summary), flush=True)
    return summary, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--workers', type=int, choices=(1,2), default=2)
    args = ap.parse_args()
    root = args.root.resolve()
    copied, dependencies = complete_inputs(root)
    records = inventory(root)
    parts = partition(records)
    atomic_json(root/'stage09_delivery/REPRODUCTION_INPUT_PACKAGING_PLAN.json', dict(files=len(records),
        source_bytes=sum(r['source_bytes'] for r in records), packages=len(parts),
        maximum_archive_bytes=MAX_ARCHIVE_BYTES, parts=[dict(number=i, files=p) for i,p in enumerate(parts,1)]))
    print(json.dumps(dict(files=len(records), source_bytes=sum(r['source_bytes'] for r in records), packages=len(parts), copied_additions=len(copied))), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(package_part, root, i, p) for i,p in enumerate(parts,1)]
        results = [f.result() for f in futures]
    summaries = [x[0] for x in results]
    files = [r for _, rows in results for r in rows]
    assert len(files) == len(records) == len({r['archive_member'] for r in files})
    assert {r['archive_member'] for r in files} == {r['archive_member'] for r in records}
    assert inventory(root) == records
    manifest = root/'stage09_delivery/REPRODUCTION_INPUT_PACKAGE_MANIFEST.csv'
    atomic_csv(manifest, files)
    receipt = dict(status='passed', files=len(files), gzip_files=sum(r['input_path'].endswith('.gz') for r in files),
        csv_files=sum(r['csv_data_rows'] is not None for r in files), csv_data_rows=sum(r['csv_data_rows'] or 0 for r in files),
        source_bytes=sum(r['source_bytes'] for r in files), package_bytes=sum(s['bytes'] for s in summaries),
        uncompressed_bytes=sum(r['uncompressed_bytes'] for r in files), packages=summaries,
        added_files=len(copied), checked_dependencies=len(dependencies),
        projected_endpoint_tables=sum(r['projected_endpoint_table'] for r in files),
        exact_identity_and_reference_columns_retained_in_all_projected_endpoint_tables=True,
        no_reproduction_inputs_middle_layer=True, prefix=root.name+'/',
        all_archives_standalone_not_split=True, all_archives_at_most_250_MiB=True,
        no_duplicate_members=True, all_input_files_included_once=True, no_temporary_files=True,
        all_zip_crc_tests_passed=True, all_gzip_completely_decompressed=True,
        all_source_and_archive_hashes_match=True, all_expected_csv_rows_match=True,
        research_sources_modified=False, input_projection_tables_and_indices_modified=False,
        manifest=manifest.relative_to(root).as_posix(), manifest_sha256=sha256_file(manifest),
        code=Path(__file__).resolve().relative_to(root).as_posix(), code_sha256=sha256_file(Path(__file__).resolve()))
    atomic_json(root/'stage09_delivery/REPRODUCTION_INPUT_PACKAGE_VALIDATION.json', receipt)
    print(json.dumps({k:receipt[k] for k in ['status','files','gzip_files','csv_files','csv_data_rows','package_bytes']}), flush=True)


if __name__ == '__main__':
    main()
