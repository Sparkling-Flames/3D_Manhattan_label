"""Read-only audit of the five downloaded Pro packages. Run with python -X utf8.

CRC/format and cache identities are independently checked. The 32-condition
rerun executes the author's shipped calculations, intercepting only table saves.
No SHA calculation or native fusion replay is performed.
"""
import argparse
import collections
import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import zipfile
import numpy as np
import pandas as pd


def frame(z, name):
    return pd.read_csv(io.BytesIO(z.read(name)), compression='gzip' if name.endswith('.gz') else None, low_memory=False)


def normalized(value):
    return value if isinstance(value, list) else value.split('|')


def audit(args):
    files = {}
    for part in ('06', '07A', '07B', '07C', '07D'):
        found = list(args.downloads.glob(f'HOHONET_v21_*{part}_*20261029.zip'))
        assert len(found) == 1, (part, found)
        files[part] = found[0]
    archives = {part: zipfile.ZipFile(path) for part, path in files.items()}
    counts = {}; errors = []; blanks = []; duplicates = collections.defaultdict(list)
    for part, z in archives.items():
        count = collections.Counter()
        for info in z.infolist():
            if info.is_dir():
                continue
            content = z.read(info)  # ZipFile verifies each entry's CRC.
            count['files'] += 1
            duplicates[info.filename].append((part, info.file_size, info.CRC))
            name = info.filename
            try:
                if name.endswith('.gz'):
                    content = gzip.decompress(content); name = name[:-3]; count['gzip'] += 1
                if name.endswith('.json'):
                    json.loads(content); count['json'] += 1
                elif name.endswith('.jsonl'):
                    for line in content.splitlines():
                        if line.strip():
                            json.loads(line)
                    count['jsonl'] += 1
                elif name.endswith('.csv'):
                    reader = csv.reader(io.StringIO(content.decode('utf-8-sig'), newline=''))
                    header = next(reader, [])
                    for row_number, row in enumerate(reader, 2):
                        if not row:
                            blanks.append([part, info.filename, row_number]); continue
                        assert len(row) == len(header), (row_number, len(row), len(header))
                    count['csv'] += 1
            except Exception as exc:
                errors.append([part, info.filename, repr(exc)])
        counts[part] = dict(count)
    different = []
    for name, entries in duplicates.items():
        if len(entries) > 1:
            first = archives[entries[0][0]].read(name)
            if any(archives[part].read(name) != first for part, _, _ in entries[1:]):
                different.append(name)
    assert not errors, errors
    all_names = set(duplicates)
    index = frame(archives['07A'], 'DOWNLOAD_INDEX.csv')
    report = {'scope': 'five downloaded v2.1 Pro packages only; source files read-only',
              'sha_calculated': False, 'native_fusion_replayed': False,
              'package_files': {k: str(v) for k, v in files.items()},
              'zip_read_check': {'per_package': counts, 'all_entries_crc_read_passed': True,
                                'nonblank_format_errors': errors, 'blank_csv_rows': blanks,
                                'different_duplicate_files': different},
              'index_counts': index.kind.value_counts().to_dict(),
              'final_receipt_present': 'FINAL_DELIVERY_READ_CHECK.json' in all_names,
              'screen_frame_present': 'experiment/global_screen_capacity/SCREEN_POOL_FRAME.csv' in all_names,
              'screen_exact_events_present': 'experiment/global_screen_design/EVENTS_EXACT.csv.gz' in all_names}

    historical = []
    stage_counts = {}
    for stage, part in [('focused','07B'),('member_sensitivity','07B'),('refinement','07B'),('fixed_A_m','07C'),('direct_AC','07C')]:
        d = frame(archives[part], f'endpoint_delivery/{stage}/TEAM_GEOMETRY_SOURCES.csv.gz')
        h = d[d.geometry_resolution.eq('historical_cache_recompute_exact_request')]
        historical.append(h)
        stage_counts[stage] = {'all_rows': len(d), 'historical_rows': len(h), 'pools': h.pool_id.nunique()}
    h = pd.concat(historical).drop_duplicates('team_key')
    pool_files = ['targets/source/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
                  'targets/source/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']
    pools = {p['pool_id']: p for name in pool_files for p in json.loads(archives['07A'].read(name))['images']}
    found = set(); failures = []; object_types = collections.Counter(); source_files = []; geometry_fields = 0
    cache_objects = {}
    for src, group in h.groupby('cache_source'):
        path = args.repo / src.split('/HOHONET_v21_20261029/', 1)[1]
        source_files.append({'path': str(path), 'exists': path.is_file(), 'compressed_bytes': path.stat().st_size if path.is_file() else None})
        if not path.is_file():
            continue
        wanted = {r.team_key: r for r in group.itertuples()}
        with gzip.open(path, 'rt', encoding='utf-8-sig') as stream:
            for line in stream:
                row = json.loads(line); key = row.get('team_key')
                if key not in wanted:
                    continue
                req = wanted[key]; found.add(key); geometry_fields += int('geometry' in row)
                for field, actual, expected in [('pool_id', row.get('pool_id'), req.pool_id),
                        ('k', row.get('k'), req.n), ('reference_id', row.get('reference_id'), req.reference_id),
                        ('reference_version', row.get('reference_version'), req.reference_version),
                        ('member_workers', sorted(normalized(row['member_workers'])), sorted(req.member_workers.split('|')))]:
                    if actual != expected:
                        failures.append([key, field])
                ids = normalized(row['member_object_ids']); object_types[type(row['member_object_ids']).__name__] += 1
                workers = normalized(row['member_workers'])
                lookup = {r['worker_id']: r['object_id'] for r in pools[row['pool_id']]['records']}
                expected = [lookup[w] for w in workers]
                if ids != expected:
                    failures.append([key, 'member_object_ids_vs_pool_worker_mapping'])
                cache_objects[key] = ids
    focused_scalar = frame(archives['07B'], 'experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz')
    focus_old = focused_scalar[focused_scalar.team_key.isin(cache_objects)]
    bad_scalar = []
    for r in focus_old.itertuples():
        if r.member_object_ids.split('|') != cache_objects[r.team_key]:
            bad_scalar.append(r.team_key)
    report['historical_cache'] = {'stage_counts': stage_counts, 'unique_teams': len(h), 'pools': h.pool_id.nunique(),
            'source_files': source_files, 'found_team_keys': len(found), 'missing_team_keys': sorted(set(h.team_key)-found),
            'source_identity_errors': failures, 'source_object_id_types': dict(object_types),
            'geometry_field_present': geometry_fields,
            'focused_scalar_historical_rows': len(focus_old), 'focused_scalar_object_serialization_mismatch_count': len(bad_scalar),
            'focused_scalar_object_serialization_mismatch_keys': bad_scalar}
    assert len(found) == len(h) and not failures

    inputs = ['analysis/focused_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz',
              'analysis/focused_contexts/MEMBER_BACKGROUND_STABILITY_BY_POOL.csv.gz',
              'experiment/focused_design/REGISTERED_COVERAGE.csv.gz',
              'analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz',
              'experiment/focused_design/EVENTS_EXACT.csv.gz',
              'analysis/focused_summary/EVENT_ROLE_LINKS.csv.gz',
              'analysis/focused_summary/DIRECTION_IMAGE_RESULTS.csv.gz']
    comparisons = []
    with tempfile.TemporaryDirectory(prefix='adoption_inputs_', dir=args.output.parent) as temporary:
        root = Path(temporary)
        for name in inputs + ['stage07_adoption/code/summarize_adoption_conditions.py']:
            z = archives['07A'] if name in archives['07A'].namelist() else archives['07B']
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(z.read(name))
        script = root / 'stage07_adoption/code/summarize_adoption_conditions.py'
        namespace = {'__name__': 'audit_adoption', '__file__': str(script)}
        exec(compile(script.read_text(encoding='utf-8-sig'), str(script), 'exec'), namespace)
        captured = {}
        namespace['save'] = lambda df, name: captured.update({name: df.copy()})
        namespace['main']()
        for name, actual in captured.items():
            expected = frame(archives['07A'], 'stage07_adoption/' + name)
            assert expected.shape == actual.shape and list(expected.columns) == list(actual.columns)
            issues = []; max_error = 0
            for col in expected:
                if pd.api.types.is_numeric_dtype(expected[col]) and pd.api.types.is_numeric_dtype(actual[col]):
                    a = expected[col].to_numpy(dtype=float); b = actual[col].to_numpy(dtype=float)
                    finite = np.isfinite(a) & np.isfinite(b)
                    if finite.any():
                        max_error = max(max_error, float(abs(a[finite]-b[finite]).max()))
                    if not np.allclose(a,b,rtol=1e-12,atol=1e-10,equal_nan=True):
                        issues.append(col)
                elif not expected[col].fillna('').astype(str).reset_index(drop=True).equals(actual[col].fillna('').astype(str).reset_index(drop=True)):
                    issues.append(col)
            comparisons.append({'file': name, 'rows': len(expected), 'columns': len(expected.columns), 'issues': issues, 'max_abs_numeric_error': max_error})
            assert not issues, (name, issues)
        for name in ['CONDITION_TABLE_FRAGMENT.md','CONDITION_TABLE_READ_CHECK.json']:
            expected = archives['07A'].read('stage07_adoption/'+name).decode('utf-8-sig')
            actual = (root/'stage07_adoption'/name).read_text(encoding='utf-8')
            equal = json.loads(expected)==json.loads(actual) if name.endswith('.json') else expected==actual
            comparisons.append({'file': name, 'equal': equal}); assert equal
    report['adoption_rerun'] = {'method': 'author shipped calculation functions, table-save interception only; not independently reimplemented formulas',
            'windows_notes': 'Run python -X utf8. Default GBK cannot write minus sign U+2212. TEMP subprocess os.replace previously returned WinError 5.',
            'inputs': inputs, 'comparisons': comparisons}
    report['minimal_missing_inputs'] = {'stage05B': 'experiment/global_screen_capacity/SCREEN_POOL_FRAME.csv',
            'stage05A': 'experiment/global_screen_design/EVENTS_EXACT.csv.gz'}
    for z in archives.values():
        z.close()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(args.output), 'zip_files': sum(x['files'] for x in counts.values()),
        'old_cache_teams': len(h), 'old_cache_identity_errors': len(failures),
        'focused_scalar_object_mismatches': len(bad_scalar), 'adoption_tables_passed': len(comparisons)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--downloads', type=Path, default=Path.home()/'Downloads')
    parser.add_argument('--repo', type=Path, default=Path('D:/Work/HOHONET'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('DELIVERY_AUDIT_RESULT.json'))
    audit(parser.parse_args())
