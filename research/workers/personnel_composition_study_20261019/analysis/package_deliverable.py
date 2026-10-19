#!/usr/bin/env python3
"""Stage and seal the compact personnel-composition evidence package.

No whole-study inputs, original images, team caches, request files or environments
are copied. Frozen dependencies are checked against their scientific receipts.
`stage` copies the explicit evidence allowlist; `seal` packages that allowlist after
the final PDF/plot/quick-replay review. Python standard library only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'personnel_composition_study_20261019'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def selection(root):
    chosen = {}

    def add(relative, category):
        p = root / relative
        if not p.is_file():
            raise FileNotFoundError(p)
        chosen[str(Path(relative))] = category

    def glob(folder, patterns, category, omit=()):
        for pattern in patterns:
            for path in sorted((root / folder).glob(pattern)):
                if path.is_file() and path.name not in omit:
                    add(str(path.relative_to(root)), category)

    for name in ['reproduce.py', 'REPRODUCE_ZH.md', 'requirements.txt',
                 'report_requirements.txt', 'build_report.py', 'prepare_fonts.py',
                 'package_deliverable.py', 'SEARCH_LEDGER.csv',
                 'SEARCH_COVERAGE_NOTES.json', 'SELECTED_WORKER_CLASSES.csv',
                 'POOL_INVENTORY_metadata.csv']:
        add('analysis/' + name, 'entry_and_search')
    glob('analysis/report_tables', ['*.csv'], 'report_small_tables')
    glob('analysis/composition', ['*.py', '*.json'], 'frozen_design_and_code')
    for name in ['block_fixed_highlights_compact.csv', 'block_source_Q_control_comparison.csv']:
        add('analysis/composition/' + name, 'block_core')

    core = 'analysis/composition/frozen_grid_results'
    add(core + '/FINAL_GRID_TABLE_INVENTORY.json', 'frozen_core_tables')
    for row in read(root / core / 'FINAL_GRID_TABLE_INVENTORY.json')['files']:
        add(core + '/' + row['file'], 'frozen_core_tables')
        assert digest(root / core / row['file']) == row['sha256'], row['file']
    for folder in ['compact_block_evidence', 'coverage', 'nested_discovery',
                   'nested_validation', 'scene_analysis']:
        glob('analysis/composition/' + folder, ['*'], folder)
    for phase in ['discovery', 'validation']:
        folder = 'analysis/composition/block_' + phase + '_specific'
        for name in ['HIGHLIGHT_DEFINITIONS.json', 'BLOCK_SPECIFIC_RECEIPT.json']:
            add(folder + '/' + name, 'fixed_highlight_design')
        add('analysis/composition/block_' + phase + '/BLOCK_SUMMARY_RECEIPT.json', 'stage_receipts')
    for folder in ['grid_discovery', 'grid_condition_discovery', 'grid_condition_validation',
                   'grid_confirm_discovery', 'grid_confirm_validation',
                   'grid_curves_discovery', 'grid_curves_validation']:
        add('analysis/composition/' + folder + '/GRID_SUMMARY_RECEIPT.json', 'stage_receipts')
    for folder in ['grid_discovery_findings', 'grid_condition_findings']:
        glob('analysis/composition/' + folder, ['*.csv', '*.csv.gz', '*.json'],
             'broad_search_outcomes', omit=['discovery_pair_aggregate.csv.gz'])

    glob('analysis/forward', ['*.py', '*.json', '*.csv'], 'forward_classification')
    glob('analysis/forward/results', ['*'], 'forward_classification')
    glob('analysis/forward/screen_final', ['*'], 'all_screen_candidates')
    add('analysis/forward/screen/screen_baseline_labels.csv.gz', 'screen_baselines')
    add('analysis/forward/FORWARD_METHODS_ZH.md', 'forward_classification')
    glob('analysis/reverse', ['*.py', '*.json', '*.csv', 'worker_labels.csv.gz',
                             'historical_roles.csv.gz', '*.txt'], 'reverse_classification')

    glob('analysis/independent', ['*.py', '*.json', '*.csv', '*.md'], 'independent_checks', omit=[
        'fusion_runner_audited_snapshot.py', 'missing_original_probe_case.json',
        'PORTABLE_REPLAY_READ_AUDIT_INITIAL.json', 'PORTABLE_REPLAY_READ_AUDIT_THRESHOLDS.json',
        'REPRESENTATIVE_CASE_PARITY_INITIAL.json', 'REPRESENTATIVE_CASE_PARITY_THRESHOLDS.json',
        'CACHE_PROBE.json', 'VISUAL_INTERFACE_QA.json'])
    glob('analysis/representative_cases/cases', ['*.json'], 'exact_cases')
    glob('analysis/representative_cases/figures', ['*/*.png', '*/render_manifest.json'], 'case_figures')
    glob('analysis/figures_summary', ['*.png', '*.csv', '*.gz', '*.json', '*.py', '*.md'], 'summary_figures')
    for name in ['range_zip.py', 'release_metadata.json', 'zip_directories.json',
                 'release_IMAGE_INDEX.csv', 'pro_personnel_v2_IMAGE_INDEX.csv',
                 'release_MANIFEST.json', 'coverage_checks.json', 'verified_references.json',
                 'method_references.json', 'SELECTED_ORIGINALS.json',
                 'SELECTED_ORIGINALS_NOTE.md']:
        add('analysis/visual_sources/' + name, 'exact_original_image_sources')
    for name in ['personnel_composition_report_zh.pdf', 'REPORT_BUILD_RECEIPT.json']:
        add('output/' + name, 'chinese_report')

    # These are the authoritative checks, not a guessed set of transitive paths.
    frozen = read(root / 'analysis/composition/VALIDATION_FREEZE.json')['file_sha256']
    source = read(root / 'analysis/independent/REPRODUCTION_AUDIT.json')['source_sha256']
    for relative, expected in dict(frozen, **source).items():
        if relative.startswith('restored/'):
            continue
        assert digest(root / relative) == expected, 'Frozen dependency changed: ' + relative
        add(relative, chosen.get(relative, 'frozen_dependency'))
    return chosen


def stage(args):
    root, dest = args.source.resolve(), args.dest.resolve()
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('Stage directory must be empty; never overwrite an existing reviewed package')
    chosen = selection(root)
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for relative, category in sorted(chosen.items()):
        src, target = root / relative, dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        rows.append({'path': relative, 'category': category, 'staged_source_sha256': digest(src)})
    for name in ['NotoSansSC-Regular.ttf', 'NotoSansSC-Bold.ttf', 'CHARACTERS.txt', 'FONT_PROVENANCE.json']:
        src = args.font_dir.resolve() / name
        relative = 'analysis/fonts/' + name
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        rows.append({'path': relative, 'category': 'licensed_font_subset', 'staged_source_sha256': digest(src)})
    src = root / 'analysis/fonts/OFL.txt'
    shutil.copy2(src, dest / 'analysis/fonts/OFL.txt')
    rows.append({'path': 'analysis/fonts/OFL.txt', 'category': 'font_license', 'staged_source_sha256': digest(src)})
    index_source = root / 'analysis/PACKAGE_README_ZH.md'
    if not index_source.is_file():
        index_source = root / 'README_ZH.md'
    shutil.copy2(index_source, dest / 'README_ZH.md')
    rows.append({'path': 'README_ZH.md', 'category': 'package_index',
                 'staged_source_sha256': digest(index_source)})
    save(dest / 'analysis/PACKAGE_SELECTION.json', {
        'schema': 'lean_composition_package_allowlist_v1', 'files': rows,
        'policy': 'Explicit small-evidence allowlist; all listed frozen scientific bytes checked before copying.',
        'omitted_rebuildable': ['complete input snapshots and repository copies', 'original image PNGs and image archives',
            'all whole-study team caches and state histories', 'all large request manifests',
            'full distance matrices and fold-model caches', 'raw pair tables and intermediate partial files',
            'virtual environments, bytecode, rendering caches and long logs'],
        'final_review_additions': ['output/DELIVERY_QA.json', 'analysis/independent/PACKAGE_QUICK_REPLAY.json',
                                   'analysis/independent/PACKAGE_DEPENDENCY_AUDIT.json'],
        'edits_permitted_after_staging': 'Only rendering outputs, their receipts, report source tables and final review receipts; frozen dependency hashes still mandatory at seal.'})
    print(json.dumps({'staged_files': len(rows) + 1, 'dest': str(dest),
                      'staged_bytes': sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())}))


def seal(args):
    dest = args.dest.resolve()
    selected = read(dest / 'analysis/PACKAGE_SELECTION.json')
    expected = {r['path']: r['category'] for r in selected['files']}
    expected['analysis/PACKAGE_SELECTION.json'] = 'package_allowlist'
    for name in selected['final_review_additions']:
        if not (dest / name).is_file():
            raise FileNotFoundError('Final QA missing: ' + name)
        expected[name] = 'final_delivery_checks'
    frozen = read(dest / 'analysis/composition/VALIDATION_FREEZE.json')['file_sha256']
    source = read(dest / 'analysis/independent/REPRODUCTION_AUDIT.json')['source_sha256']
    for relative, value in dict(frozen, **source).items():
        if not relative.startswith('restored/'):
            assert digest(dest / relative) == value, 'Frozen scientific byte mismatch: ' + relative
    quick = read(dest / 'analysis/independent/PACKAGE_QUICK_REPLAY.json')
    assert quick['all_passed'], 'Quick replay must pass before sealing'
    qa = read(dest / 'output/DELIVERY_QA.json')
    assert qa['all_passed'], 'Final review must pass before sealing'
    bad = []
    for relative in expected:
        pieces = Path(relative).parts
        if any(s in pieces for s in ['restored', 'repo', '.git', 'replay', '__pycache__', 'mplconfig', 'input_cache']):
            bad.append(relative)
        if any(s.startswith('runs') or s.startswith('runtime_env') for s in pieces):
            bad.append(relative)
        if relative.endswith('_REQUESTS.json.gz') or '.writing.' in relative or '.parts.' in relative:
            bad.append(relative)
        if '/selected_originals/' in relative or 'historical_pair_relations' in relative:
            bad.append(relative)
    assert not bad, bad
    rows = [{'path': p, 'category': expected[p], 'bytes': (dest / p).stat().st_size,
             'sha256': digest(dest / p)} for p in sorted(expected)]
    manifest = {
        'schema': 'personnel_composition_lean_delivery_v1', 'package': NAME,
        'source_main': 'e572eb73bedc4fe9056df838e458bab83c3fa423',
        'scientific_source': '82c6164b0d4630de5316199c92aa405930973168',
        'frozen_spec_sha256': digest(dest / 'analysis/composition/VALIDATION_FREEZE.json'),
        'files_excluding_manifest_and_checksums': len(rows),
        'bytes_excluding_manifest_and_checksums': sum(r['bytes'] for r in rows),
        'all_frozen_scientific_dependencies_match': True,
        'large_rebuildable_outputs_excluded': True,
        'independent_sample_units': {'history_buildings': 10, 'discovery_buildings': 6,
            'validation_buildings': 6, 'research_images_excluding_history': 106,
            'research_unique_actual_teams': 583261, 'research_workers': 59,
            'representative_images': 6, 'representative_buildings': 4, 'representative_teams': 21},
        'files': rows}
    save(dest / 'MANIFEST.json', manifest)
    files = sorted(expected) + ['MANIFEST.json']
    (dest / 'SHA256SUMS').write_text(''.join(digest(dest / p) + '  ' + p + '\n' for p in sorted(files)), encoding='utf-8')
    files.append('SHA256SUMS')
    archive = args.zip.resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for relative in sorted(files):
            info = zipfile.ZipInfo(NAME + '/' + relative, date_time=(2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, (dest / relative).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.infolist()) == len(files)
        for relative in files:
            assert hashlib.sha256(z.read(NAME + '/' + relative)).hexdigest() == digest(dest / relative)
        largest = sorted([{'path': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size}
                          for i in z.infolist()], key=lambda v: v['bytes'], reverse=True)[:12]
    receipt = {'archive': str(archive), 'bytes': archive.stat().st_size,
               'MiB': round(archive.stat().st_size / 1048576, 3), 'sha256': digest(archive),
               'zip_entries': len(files), 'all_zip_crc_checked': True,
               'every_zipped_file_sha_matches_staged_file': True,
               'uncompressed_bytes': sum((dest / p).stat().st_size for p in files),
               'all_required_files_present': True, 'forbidden_large_outputs_present': False,
               'largest_entries': largest}
    save(args.receipt.resolve(), receipt)
    print(json.dumps(receipt, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('stage')
    p.add_argument('--source', type=Path, default=ROOT)
    p.add_argument('--dest', type=Path, default=ROOT / 'delivery' / NAME)
    p.add_argument('--font-dir', type=Path, default=(ROOT / 'packaging/font_subset'
        if (ROOT / 'packaging/font_subset').is_dir() else ROOT / 'analysis/fonts'))
    p = sub.add_parser('seal')
    p.add_argument('--dest', type=Path, default=ROOT / 'delivery' / NAME)
    p.add_argument('--zip', type=Path, default=ROOT / 'output' / (NAME + '.zip'))
    p.add_argument('--receipt', type=Path, default=ROOT / 'output/ZIP_DELIVERY_CHECK.json')
    args = parser.parse_args()
    {'stage': stage, 'seal': seal}[args.mode](args)


if __name__ == '__main__':
    main()
