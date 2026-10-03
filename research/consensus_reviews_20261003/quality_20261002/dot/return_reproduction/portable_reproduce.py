#!/usr/bin/env python3
"""Non-destructive independent reproduction wrapper for the returned Oct-2 package.

Usage:
  python portable_reproduce.py --source /path/layout_quality_audit_20261002 --out /new/output
  # Optional: --dependency-path /path/containing/shapely

Inspect the source package before execution. This script verifies all delivered
hashes, copies the package, executes only the copy, compares every saved output,
and proves that all source bytes remain unchanged. No network calls or installs.
The input directory must be the received, unmodified package.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, re, shutil, subprocess, sys
from pathlib import Path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def files(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')

def normalized_svg(path):
    s = re.sub(r'<dc:date>.*?</dc:date>', '<dc:date>IGNORED_DATE</dc:date>', path.read_text())
    ids = {}
    def replace(m):
        value = m.group(0)
        if value not in ids:
            ids[value] = 'normalized_id_' + str(len(ids))
        return ids[value]
    return re.sub(r'\b[mp][0-9a-f]{10}\b', replace, s)

def scalar_comparison(a, b, label, rows):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            rows.append({'field': label, 'status': 'key_mismatch'})
        for k in a.keys() & b.keys():
            scalar_comparison(a[k], b[k], label + '/' + str(k), rows)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            rows.append({'field': label, 'status': 'length_mismatch'})
        for i, (x, y) in enumerate(zip(a, b)):
            scalar_comparison(x, y, label + '/' + str(i), rows)
    elif isinstance(a, bool) or isinstance(b, bool):
        rows.append({'field': label, 'status': 'exact' if a == b else 'different'})
    else:
        try:
            x, y = float(a), float(b)
            numeric = math.isfinite(x) and math.isfinite(y)
        except (TypeError, ValueError):
            numeric = False
        if numeric:
            rows.append({'field': label, 'status': 'close' if math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-10) else 'different',
                         'received': x, 'rerun': y, 'absolute_difference': abs(x-y), 'exact': x == y})
        else:
            rows.append({'field': label, 'status': 'exact' if a == b else 'different'})

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--dependency-path', type=Path)
    args = p.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    if source == out or source in out.parents:
        p.error('Output must be outside the received source directory')
    if out.exists():
        p.error('Output must not exist; existing evidence is never overwritten')
    out.mkdir(parents=True)
    before = files(source)
    manifest = json.loads((source / 'FILE_HASHES.json').read_text())
    manifest_paths = [r['path'] for r in manifest]
    checks = []
    for r in manifest:
        target = (source / r['path']).resolve()
        if source not in target.parents:
            raise ValueError('Unsafe manifest path')
        checks.append(dict(path=r['path'], exists=target.is_file(),
                           size_match=target.is_file() and target.stat().st_size == r['bytes'],
                           sha256_match=target.is_file() and sha(target) == r['sha256']))
    manifest_result = {'entries': len(manifest), 'actual_files': len(before),
                       'duplicates': len(manifest_paths)-len(set(manifest_paths)),
                       'unlisted': sorted(set(before)-set(manifest_paths)),
                       'missing': sorted(set(manifest_paths)-set(before)), 'checks': checks}
    save(out / 'manifest_verification.json', manifest_result)
    save(out / 'received_hashes_before.json', before)
    assert all(c['exists'] and c['size_match'] and c['sha256_match'] for c in checks)
    assert not manifest_result['duplicates'] and not manifest_result['missing']
    assert manifest_result['unlisted'] == ['FILE_HASHES.json']
    copy = out / 'returned_package'
    shutil.copytree(source, copy)
    env = os.environ.copy()
    env.update(MPLBACKEND='Agg', MPLCONFIGDIR=str(out/'matplotlib_cache'), XDG_CACHE_HOME=str(out/'cache'), PYTHONDONTWRITEBYTECODE='1')
    if args.dependency_path:
        env['PYTHONPATH'] = str(args.dependency_path.resolve()) + os.pathsep + env.get('PYTHONPATH', '')
    depcode = "import sys,numpy,scipy,shapely,pandas,matplotlib;print(sys.version);print([(x.__name__,x.__version__,x.__file__) for x in (numpy,scipy,shapely,pandas,matplotlib)])"
    with (out/'dependencies.log').open('w') as log:
        subprocess.run([sys.executable, '-c', depcode], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    with (out/'reproduce.log').open('w') as log:
        run = subprocess.run([sys.executable, str(copy/'reproduce.py')], cwd=copy, env=env, stdout=log, stderr=subprocess.STDOUT)
    result_files, values = [], []
    for src in sorted((source/'results').iterdir()):
        dst = copy/'results'/src.name
        row = {'file': str(src.relative_to(source)), 'bytes_equal': src.read_bytes() == dst.read_bytes(),
               'received_sha256': sha(src), 'rerun_sha256': sha(dst)}
        result_files.append(row)
        if src.name == 'environment.json':
            a, b = json.loads(src.read_text()), json.loads(dst.read_text())
            row['changed_environment_fields'] = {k: {'received': a.get(k), 'rerun': b.get(k)} for k in set(a)|set(b) if a.get(k) != b.get(k)}
        elif src.suffix == '.json':
            scalar_comparison(json.loads(src.read_text()), json.loads(dst.read_text()), src.name, values)
        elif src.suffix == '.csv':
            with src.open(encoding='utf-8-sig', newline='') as f, dst.open(encoding='utf-8-sig', newline='') as g:
                scalar_comparison(list(csv.DictReader(f)), list(csv.DictReader(g)), src.name, values)
    figures = []
    for src in sorted((source/'figures').iterdir()):
        dst = copy/'figures'/src.name
        figures.append({'file': src.name, 'bytes_equal': src.read_bytes() == dst.read_bytes(),
                        'svg_equal_after_date_and_random_id_normalization': normalized_svg(src) == normalized_svg(dst) if src.suffix == '.svg' else None})
    after = files(source)
    save(out/'received_hashes_after.json', after)
    numeric = [r for r in values if 'absolute_difference' in r]
    machine = {'command': [sys.executable, 'returned_package/reproduce.py'], 'returncode': run.returncode,
               'source_bytes_unchanged': before == after, 'saved_results': result_files,
               'numeric_scalar_comparisons': len(numeric),
               'max_saved_result_numeric_difference': max((r['absolute_difference'] for r in numeric), default=0),
               'all_saved_results_semantically_equal_at_tolerance': all(r['status'] in ('exact','close') for r in values),
               'generated_controlled_input_bytes_equal': (source/'inputs/controlled_inputs.json').read_bytes() == (copy/'inputs/controlled_inputs.json').read_bytes(),
               'numeric_excerpt_bytes_unchanged': sha(source/'inputs/current_numeric_subset.json') == sha(copy/'inputs/current_numeric_subset.json'),
               'figures': figures, 'scalar_comparisons': values}
    save(out/'machine_comparison.json', machine)
    assert run.returncode == 0 and machine['source_bytes_unchanged']
    assert machine['all_saved_results_semantically_equal_at_tolerance']
    print(json.dumps({k: v for k,v in machine.items() if k not in ('saved_results', 'scalar_comparisons', 'figures')}, indent=2))
    print('Complete machine comparison:', out/'machine_comparison.json')

if __name__ == '__main__':
    main()
