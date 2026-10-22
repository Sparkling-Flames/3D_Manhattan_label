#!/usr/bin/env python3
"""Assemble the fixed study, then reproduce it offline in a fresh directory.

No fusion, label editing, new parameter selection, network access, or automatic
dependency installation occurs here. 20261012 is a study identifier, not a date
claim; all run timestamps are read from the actual UTC clock.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

STUDY = 'top_structure_20261012'
DELIVERY = 'quality_top_structure_research_20261012'
PREVIOUS = 'previous_research/quality_calibration_research_20261011'
MAIN_SHA = '38e259c043fed0817307dbc3d21c6dba06bd6662'
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff'}
FOUNDATION_INPUTS = {
    'study_severe/results/ledger_115.json': 'Prior qualification ledger, independently rechecked against raw receipts.',
    'study_severe/results/scorable_records.json': 'Historical complete-geometry eligibility, not new labels.',
    'study_severe/source/raw_project28_selected_annotations.json': 'Untouched historical raw source evidence.',
    'study_severe/source/raw_project39_selected_annotations.json': 'Untouched historical raw source evidence.',
    'study_severe/source/SOURCE_MANIFEST.json': 'Raw source byte provenance.',
    'study_quality/results/candidate_scores.json': 'Frozen prior 39-row component/score input; carried, not claimed newly recomputed.',
    'study_quality/candidates.json': 'Historical candidate definition.',
    'study_quality/scoring_candidates.py': 'Historical candidate implementation.',
    'study_quality/run_real_candidates.py': 'Optional reconstruction of the historical 39-row scalar table.',
    'study_borderline/results/old24_evidence.json': 'Historical uncertain 24 quality judgments, with raw receipt separately carried.',
    'study_borderline/results/screen_evidence_115.json': 'All 115 received states, including unreviewed and missing geometry.',
    'study_borderline/results/allowed_screen_numerical_ids.json': 'Previously audited numerical comparison IDs.',
    'study_borderline/scripts/compare_candidates.py': 'Shared exact two-cutpoint calibration and borderline sensitivity implementation.',
    'study_borderline/analysis_protocol.json': 'Historical uncertainty/calibration protocol.',
    'study_x/audit_representation.py': 'Current executed four-layer representation audit source.',
    'study_x/raw_boundary_experiment.py': 'Current executed raw spherical-boundary recomputation source.',
    'study_x/controlled_x.py': 'Fixed 12-case input-representation controls.',
    'study_x/results/representation_signals_all3152.csv': 'Historical membership of the fixed 907 development pool.',
    'study_x/results/raw_boundary_cases.csv': 'Historical raw boundary input for optional prior scalar replay.',
    'study_data/current_archive_inventory.json': 'Archive provenance only; complete ZIP bytes are not included.',
    'study_data/original_image_index.json': 'Original 261-image metadata; runtime builds a separate six-image local index.',
}
NUMERIC_DIRS = [
    f'{STUDY}/evidence/results', f'{STUDY}/representation/results',
    f'{STUDY}/mechanisms/results', f'{STUDY}/analysis/results',
    f'{STUDY}/analysis/fair_comparison', f'{STUDY}/analysis/sensitivity',
    f'{STUDY}/analysis/representation_and_pool', f'{STUDY}/exploration/results',
]
VOLATILE_KEYS = {
    'elapsed_seconds', 'free_exploration_actual_execution_utc',
    'actual_compute_seconds_for_109_profiles_excluding_io_and_verification',
}
ENVIRONMENT_KEYS = {'python', 'platform', 'numpy'}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def file_walk(root):
    return [p for p in sorted(Path(root).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']


def image_subset(study_root):
    rows = read(study_root / 'review/inputs/selected_original_images.json')
    assert len(rows) == len({r['image_id'] for r in rows}) == len({r['sha256'] for r in rows}) == 6
    for row in rows:
        photo = study_root / 'review' / row['relative_path']
        assert photo.is_file() and sha(photo) == row['sha256'], row['image_code']
        assert photo.stat().st_size == row['bytes']
    return rows


def build_copy_plan(source, foundation):
    """Use the previous portable package as an explicit dependency catalog.

    Its previous_research tree is already a numerical subset. Source bytes come
    from the actual executed workspace and are compared with the older package
    when present, so a changed reusable script is not silently downgraded.
    """
    if not (foundation / PREVIOUS).is_dir():
        raise FileNotFoundError('Portable foundation is required for its bounded dependency inventory: ' + str(foundation))
    plan = {}

    def add(rel, role, reason):
        rel = Path(rel).as_posix()
        source_file = source / rel
        if not source_file.is_file():
            raise FileNotFoundError('Missing exact dependency: ' + str(source_file))
        reference = foundation / rel
        item = dict(path=rel, source_relative_path=rel, role=role, reason=reason,
                    bytes=source_file.stat().st_size, sha256=sha(source_file))
        if reference.is_file():
            item['foundation_reference_sha256'] = sha(reference)
            item['same_as_previous_portable_foundation'] = item['foundation_reference_sha256'] == item['sha256']
        plan[rel] = item

    for path in file_walk(foundation / PREVIOUS):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            add(path.relative_to(foundation), 'frozen_numerical_foundation', 'Bounded prior portable numerical/code/receipt subset; no old panorama bytes.')
    for path in file_walk(source / 'new_main_snapshot'):
        add(path.relative_to(source), 'exact_current_main_snapshot', 'Exact twelve main files and their source manifest.')
    for rel, reason in FOUNDATION_INPUTS.items():
        add(rel, 'historical_dependency', reason)
    # Source material documenting pairing/editing flow is small and retained.
    for path in file_walk(source / 'study_x/source'):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            add(path.relative_to(source), 'historical_pipeline_source', 'Versioned representation/edit pipeline evidence; not executed to alter current input.')
    for path in file_walk(source / STUDY):
        if path.name in {'COPY_PLAN.json', 'ASSEMBLY_CHECKS.json'} and path.parent.name == 'delivery_tools':
            continue  # Avoid self-referential manifests.
        add(path.relative_to(source), 'new_study', 'All current study code, configuration, results, review materials and six selected original panoramas.')
    images = image_subset(source / STUDY)
    return dict(schema='quality_top_structure_copy_plan_v1', actual_utc=utc(), study_id=STUDY,
                study_suffix_is_round_identifier=True, actual_main_sha=MAIN_SHA,
                source_root=str(source), foundation_inventory_root=str(foundation),
                original_panorama_count=6, original_images=images,
                complete_archives_bundled=False, old_visualizations_bundled=False,
                files=[plan[k] for k in sorted(plan)])


def assemble(args):
    source = args.source_root.resolve()
    foundation = (args.foundation_root or source / 'delivery/quality_representation_severe_research_20261011').resolve()
    package = (args.package_root or source / 'delivery' / DELIVERY).resolve()
    if package == foundation or package == source or foundation in package.parents or package in foundation.parents:
        raise ValueError('The new package must be separate from the original workspace and prior package.')
    marker = package / 'provenance/PACKAGE_SCOPE.json'
    if package.exists():
        if not args.refresh or not marker.is_file() or read(marker).get('study_id') != STUDY:
            raise FileExistsError('Choose a fresh package directory, or --refresh the package created by this tool.')
        old_manifest = read(package / 'provenance/COPY_MANIFEST.json')
        for row in old_manifest['files']:
            if row['role'] != 'new_study' and sha(package / row['path']) != row['sha256']:
                raise AssertionError('Previously copied dependency was edited: ' + row['path'])
    plan = build_copy_plan(source, foundation)
    dump(source / STUDY / 'delivery_tools/COPY_PLAN.json', plan)
    package.mkdir(parents=True, exist_ok=True)
    for row in plan['files']:
        src, dst = source / row['path'], package / row['path']
        data = src.read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise AssertionError('Source changed while copying; rerun assembly after the writer finishes: ' + row['path'])
        if row['role'] != 'new_study' and dst.exists() and sha(dst) != row['sha256']:
            raise AssertionError('Refusing to replace a carried historical input: ' + row['path'])
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    dump(package / 'provenance/COPY_MANIFEST.json', plan)
    dump(marker, dict(study_id=STUDY, assembled_actual_utc=utc(), actual_main_sha=MAIN_SHA,
                     date_semantics='20261012 identifies the study round; timestamps record the real UTC date.',
                     original_panorama_count=6, known_full_original_library_count=261,
                     full_original_library_bundled=False, originals_outside_delivered_subset=255,
                     full_zip_archives_included=False, new_study_included=True,
                     previous_results_are_historical_inputs=True, immutable_original_receipts_preserved=True,
                     old_24_panorama_library_or_old_visualizations_included=False,
                     source_files=len(plan['files']), copied_bytes=sum(x['bytes'] for x in plan['files']),
                     archive_reverification_limit='verify_sources.py preserves the original archive audit code; its full-archive mode requires the separately held two research ZIPs and four base ZIPs. It is intentionally not called by offline subset reproduction.'))
    versions = foundation / 'requirements.txt'
    shutil.copyfile(versions, package / 'requirements.txt')
    # A standalone root entry has no logic of its own; all implementation is in
    # the requested delivery_tools script.
    (package / 'REPRODUCE_ZH.md').write_text((source / STUDY / 'delivery_tools/README_ZH.md').read_text(), encoding='utf-8')
    (package / 'README_ZH.md').write_text((source / STUDY / 'delivery_tools/PACKAGE_README_ZH.md').read_text(), encoding='utf-8')
    shutil.copyfile(source / STUDY / 'delivery_tools/run_reproduction_entry.py', package / 'run_reproduction.py')
    result = verify_package(package)
    dump(source / STUDY / 'delivery_tools/ASSEMBLY_CHECKS.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def verify_package(package):
    manifest = read(package / 'provenance/COPY_MANIFEST.json')
    for row in manifest['files']:
        path = package / row['path']
        if not path.is_file() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise AssertionError('Package bytes differ from copied source: ' + row['path'])
    main = read(package / 'new_main_snapshot/SOURCE_MANIFEST.json')
    assert main['main_sha'] == MAIN_SHA and len(main['files']) == 12
    for row in main['files']:
        b = (package / 'new_main_snapshot' / row['path']).read_bytes()
        assert hashlib.sha256(b).hexdigest() == row['sha256']
        assert hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest() == row['git_blob']
    images = image_subset(package / STUDY)
    return dict(status='passed', actual_utc=utc(), package=str(package),
                copied_files_verified=len(manifest['files']), exact_main_files_verified=12,
                original_panorama_bytes_verified=len(images), copied_source_files_unchanged=True,
                full_original_archives_reverified=False,
                numerical_reproduction_executed=False)


def compare_values(expected, actual, path='', stats=None):
    """Compare existing output values; report environment/runtime separately."""
    if stats is None:
        stats = dict(numeric_values=0, max_absolute_error=0., metadata_differences=[], differences=[])
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            stats['differences'].append(dict(path=path, reason='keys', expected=sorted(expected), actual=sorted(actual)))
            return stats
        for key in expected:
            here = path + '/' + key
            if key in VOLATILE_KEYS | ENVIRONMENT_KEYS:
                if expected[key] != actual[key]:
                    stats['metadata_differences'].append(dict(path=here, expected=expected[key], actual=actual[key]))
                continue
            compare_values(expected[key], actual[key], here, stats)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            stats['differences'].append(dict(path=path, reason='length', expected=len(expected), actual=len(actual)))
        else:
            for i, (a, b) in enumerate(zip(expected, actual)):
                compare_values(a, b, path + '/' + str(i), stats)
    elif expected == actual:
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            stats['numeric_values'] += 1
    else:
        def number(x):
            if isinstance(x, bool) or x is None:
                return None
            try:
                val = float(x)
                return val if math.isfinite(val) else None
            except (TypeError, ValueError):
                return None
        a, b = number(expected), number(actual)
        if a is not None and b is not None:
            error = abs(a - b)
            stats['numeric_values'] += 1
            stats['max_absolute_error'] = max(error, stats['max_absolute_error'])
            if not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10):
                stats['differences'].append(dict(path=path, reason='numeric', expected=expected, actual=actual))
        else:
            stats['differences'].append(dict(path=path, reason='value', expected=expected, actual=actual))
    return stats


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def prepare_fresh_work(package, output):
    if output.exists() or output == package or package in output.parents:
        raise FileExistsError('The reproduction directory must be new and outside the immutable package.')
    verify_package(package)
    output.mkdir(parents=True)
    for name in [STUDY, 'previous_research', 'new_main_snapshot', 'study_severe', 'study_quality', 'study_borderline', 'study_x', 'study_data']:
        if (package / name).is_dir():
            shutil.copytree(package / name, output / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for relative in NUMERIC_DIRS:
        target = output / relative
        if target.exists():
            shutil.rmtree(target)  # Only the newly made working copy.
        target.mkdir(parents=True)
    photos = image_subset(package / STUDY)
    local_index = []
    for photo in photos:
        destination = output / 'assets/originals' / (photo['image_code'] + '.png')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(package / STUDY / 'review' / photo['relative_path'], destination)
        local_index.append(dict(image_id=photo['image_id'], image_code=photo['image_code'],
                                local_path=str(destination), sha256=photo['sha256'],
                                image_zip=photo['source_library_zip'], internal_path=photo['archive_internal_path']))
    # Preserve the original metadata before rebasing the six available images.
    original_index = output / 'study_data/original_image_index.json'
    shutil.copyfile(original_index, original_index.with_name('source_original_image_index_261.json'))
    dump(original_index, local_index)
    dump(output / 'reproduction/START.json', dict(actual_utc=utc(), study_id=STUDY,
         package=str(package), output=str(output), original_panorama_count=6,
         fresh_numeric_directories=NUMERIC_DIRS, original_archives_not_reopened=True,
         carried_historical_data_not_claimed_recomputed=True,
         new_visual_review_or_human_label=False, command_line=sys.argv))


def reproduction_steps(workers, with_figures):
    p = STUDY
    steps = [
        ('01_qualification', [f'{p}/evidence/audit_qualification.py']),
        ('02_prior_ranking', [f'{p}/evidence/prior_ranking_audit.py']),
        ('03_fixed_development_membership', [f'{p}/evidence/development_filter.py']),
        ('04_current_representation', ['study_x/audit_representation.py', '--previous', PREVIOUS, '--new-main', 'new_main_snapshot', '--severe-ledger', 'study_severe/results/ledger_115.json', '--out', f'{p}/representation/results']),
        ('05_raw_boundary_922', ['study_x/raw_boundary_experiment.py', '--previous', PREVIOUS, '--signals', f'{p}/representation/results/representation_signals_all3152.csv', '--out', f'{p}/representation/results', '--workers', str(workers)]),
        ('06_x_controls_12', ['study_x/controlled_x.py', '--previous', PREVIOUS, '--out', f'{p}/representation/results']),
        ('07_height_mechanisms', [f'{p}/mechanisms/run_mechanisms.py']),
        ('08_centered_height', [f'{p}/mechanisms/add_centered_components.py']),
        ('09_centered_invariants', [f'{p}/mechanisms/verify_centered_invariants.py']),
        ('10_mechanism_summary', [f'{p}/mechanisms/summarize_mechanisms.py']),
        ('11_candidate_scores', [f'{p}/analysis/run_candidates.py']),
        ('12_fair_grouped_calibration', ['study_borderline/scripts/compare_candidates.py', '--scores', f'{p}/analysis/results/candidate_scores_39.csv', '--old-evidence', 'study_borderline/results/old24_evidence.json', '--screen-evidence', 'study_borderline/results/screen_evidence_115.json', '--allowed-screen-ids', 'study_borderline/results/allowed_screen_numerical_ids.json', '--methods', '@FROZEN_METHODS@', '--out', f'{p}/analysis/fair_comparison']),
        ('13_sensitivity', [f'{p}/analysis/sensitivity.py']),
        ('14_unlabeled_pool', [f'{p}/analysis/analyze_representation_and_pool.py']),
        ('15_fixed_fusion_inputs', [f'{p}/evidence/prepare_fixed_fusion.py']),
        ('16_fixed_fusion_scores', [f'{p}/evidence/score_fixed_fusion.py']),
        ('17_fixed_free_exploration', [f'{p}/exploration/run_exact_height_support.py']),
    ]
    if with_figures:
        steps.extend([
            ('18_exploration_figures', [f'{p}/exploration/render_support_evidence.py']),
            ('19_review_source_subset', [f'{p}/review/prepare_review_inputs.py']),
            ('20_review_figures', [f'{p}/review/render_user_figures.py']),
            ('21_review_documents', [f'{p}/review/build_review_documents.py', '--candidate-json', f'{p}/analysis/results/candidate_scores_39.json']),
            ('22_fixed_endpoint_figures', [f'{p}/evidence/render_fixed_endpoint_figures.py']),
        ])
    return steps


def reproduce(args):
    package = args.package_root.resolve()
    timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = (args.output_root or package.parent / ('reproduction_top_structure_' + timestamp)).resolve()
    required = ['numpy', 'scipy', 'shapely', 'PIL', 'matplotlib']
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError('Install the pinned requirements in the environment before offline reproduction; missing: ' + ', '.join(missing))
    prepare_fresh_work(package, output)
    steps = reproduction_steps(args.workers, args.with_figures)
    dump(output / 'reproduction/PLANNED_STEPS.json', steps)
    if args.prepare_only:
        print(json.dumps(dict(status='prepared_only_not_reproduced', output=str(output), planned_steps=len(steps)), ensure_ascii=False))
        return
    config = read(package / f'{STUDY}/analysis/results/run_manifest.json')
    methods = config['primary_methods'] + config['diagnostic_methods']
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', MPLBACKEND='Agg')
    executed = []
    for name, command in steps:
        if '@FROZEN_METHODS@' in command:
            at = command.index('@FROZEN_METHODS@')
            command = command[:at] + methods + command[at + 1:]
        log = output / 'reproduction/logs' / (name + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        print('START ' + name, flush=True)
        start = time.perf_counter()
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run([sys.executable, *command], cwd=output, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        entry = dict(name=name, command=command, returncode=result.returncode,
                     elapsed_seconds=time.perf_counter() - start, log=str(log.relative_to(output)))
        executed.append(entry)
        dump(output / 'reproduction/EXECUTED_STEPS.json', executed)
        if result.returncode:
            print(log.read_text()[-6000:], flush=True)
            raise RuntimeError(name + ' failed; see ' + str(log))
        print('DONE ' + name, flush=True)
    comparisons = []
    for relative in NUMERIC_DIRS:
        for expected in sorted((package / relative).glob('*')):
            if expected.suffix not in {'.json', '.csv'}:
                continue
            actual = output / expected.relative_to(package)
            if not actual.is_file():
                raise AssertionError('Expected numerical output was not regenerated: ' + str(actual.relative_to(output)))
            a, b = (csv_rows(expected), csv_rows(actual)) if expected.suffix == '.csv' else (read(expected), read(actual))
            comparisons.append(dict(path=str(expected.relative_to(package)), **compare_values(a, b)))
    failed = [row for row in comparisons if row['differences']]
    dump(output / 'reproduction/NUMERICAL_COMPARISON.json', dict(tolerance={'absolute':1e-10, 'relative':1e-10},
         runtime_fields_reported_separately=sorted(VOLATILE_KEYS), environment_fields_reported_separately=sorted(ENVIRONMENT_KEYS),
         compared_files=len(comparisons), failed_files=len(failed), files=comparisons))
    unchanged = verify_package(package)
    result = dict(status='passed' if not failed else 'differences', actual_utc=utc(), output=str(output),
                  executed_steps=len(executed), new_numerical_output_files=len(comparisons), failed_files=len(failed),
                  numeric_values_compared=sum(row['numeric_values'] for row in comparisons),
                  maximum_numeric_error=max(row['max_absolute_error'] for row in comparisons),
                  package_source_files_unchanged=unchanged['copied_source_files_unchanged'],
                  figure_rendering_executed=args.with_figures, carried_original_panorama_count=6,
                  new_human_review_or_independent_scientific_validation=False,
                  new_parameters_or_fusion=False,
                  note='Fixed development engineering reproduction; original receipts, reference eligibility and holdout exposure remain unchanged.')
    dump(output / 'reproduction/REPRODUCTION_VERIFICATION.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failed:
        raise AssertionError('Numerical/semantic output differences: ' + ', '.join(row['path'] for row in failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    default_package = Path(__file__).resolve().parents[2]
    assembly = actions.add_parser('assemble', help='Create the new delivery beside, never over, the old delivery.')
    assembly.add_argument('--source-root', type=Path, default=Path.cwd())
    assembly.add_argument('--foundation-root', type=Path)
    assembly.add_argument('--package-root', type=Path)
    assembly.add_argument('--refresh', action='store_true', help='Refresh only this tool-owned package; carried historical bytes may not change.')
    check = actions.add_parser('verify', help='Verify copied bytes, twelve exact main files and six originals, without numerical reruns.')
    check.add_argument('--package-root', type=Path, default=default_package)
    reproduction = actions.add_parser('reproduce', help='Run the already fixed study in a new output directory, offline.')
    reproduction.add_argument('--package-root', type=Path, default=default_package)
    reproduction.add_argument('--output-root', type=Path)
    reproduction.add_argument('--workers', type=int, default=2)
    reproduction.add_argument('--with-figures', action='store_true')
    reproduction.add_argument('--prepare-only', action='store_true', help='Verify and create a fresh workspace, but do not claim numerical reproduction.')
    args = parser.parse_args()
    if args.action == 'assemble':
        assemble(args)
    elif args.action == 'verify':
        print(json.dumps(verify_package(args.package_root.resolve()), ensure_ascii=False, indent=2))
    else:
        if args.workers < 1:
            parser.error('--workers must be positive')
        reproduce(args)


if __name__ == '__main__':
    main()
