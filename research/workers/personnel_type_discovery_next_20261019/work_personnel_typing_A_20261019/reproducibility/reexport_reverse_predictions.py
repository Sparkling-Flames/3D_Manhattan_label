#!/usr/bin/env python3
"""Re-export any frozen Part A reverse prediction fold, without type discovery.

The original predictions (including any former damaged prefix) are not inputs.
Classes, candidate selection and relation-specific calibration remain frozen.
Only global/k fallbacks omitted from calibration.csv.gz are re-aggregated from
the registered training panel; saved k/difficulty baselines must match them.
Default: print a plan. Execution writes to a new, separate output directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
from itertools import zip_longest
import json
import os
from pathlib import Path
import sys
import time
import uuid


HERE = Path(__file__).resolve().parent
PREDICTION_COLUMNS = [
    'event_id', 'method_id', 'fold_id', 'relation', 'predicted_stability',
    'probability', 'training_key', 'source_candidate_id',
]
IDENTITY_COLUMNS = [
    'event_id', 'method_id', 'fold_id', 'relation', 'training_key',
    'source_candidate_id',
]
DIFFICULTY_MAP = {'简单': 'easy', '中等': 'medium', '困难': 'hard'}
TOLERANCE = 1e-12
CHUNK_ROWS = 25000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path, value):
    path = Path(path)
    require(not path.exists(), f'Refusing to overwrite {path}')
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.writing')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    with temporary.open(encoding='utf-8') as handle:
        json.load(handle)
    os.replace(temporary, path)
    sync_directory(path.parent)


def full_gzip_crc(path):
    """Read through the footer, rather than accepting only a readable prefix."""
    uncompressed_bytes = 0
    with gzip.open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            uncompressed_bytes += len(block)
    return uncompressed_bytes


def make_plan(args):
    source = args.source_root.resolve()
    results = source / 'reverse/results'
    available = {}
    for path in sorted((results / 'folds').glob('*/COMPLETE.json')):
        complete = json.loads(path.read_text(encoding='utf-8'))
        if int(complete.get('n_test_events', 0)) > 0:
            available[path.parent.name] = complete
    require(available, f'No completed outer folds under {results / "folds"}')
    requested = list(dict.fromkeys(args.fold or sorted(available)))
    missing_folds = sorted(set(requested) - set(available))
    require(not missing_folds,
            f'Unknown or non-evaluation fold(s): {missing_folds}; FULL has no test predictions')
    output = args.output_dir.resolve() if args.output_dir else None
    compare = args.compare_dir.resolve() if args.compare_dir else None
    required = [source / 'events/common_events.csv.gz',
                source / 'reverse/selection_common.py']
    folds = []
    for fold in requested:
        complete = available[fold]
        require(complete['fold_id'] == fold and complete['heldout_building'] == fold,
                f'COMPLETE fold identity mismatch: {fold}')
        require(fold not in complete['train_buildings'], f'Heldout fold in training: {fold}')
        training_key = hashlib.sha256(
            '|'.join(sorted(complete['train_buildings'])).encode()
        ).hexdigest()[:16]
        require(training_key == complete['training_key'], f'Training key mismatch: {fold}')
        paths = [results / 'folds' / fold / filename for filename in
                 ['classes.csv.gz', 'calibration.csv.gz', 'COMPLETE.json']]
        required.extend(paths)
        method_count = int(complete['candidate_count']) + len(complete['selected_candidates'])
        folds.append({
            'fold_id': fold,
            'events': int(complete['n_test_events']),
            'candidate_methods': int(complete['candidate_count']),
            'selector_aliases': len(complete['selected_candidates']),
            'methods': method_count,
            'prediction_rows': int(complete['n_test_events']) * method_count,
            'output_relative_path': f'folds/{fold}/predictions.csv.gz',
            'optional_comparison_available':
                (compare / 'folds' / fold / 'predictions.csv.gz').is_file()
                if compare else None,
        })
    plan = {
        'mode': 'execute' if args.execute else 'plan_only',
        'source_root': str(source),
        'output_dir': str(output) if output else None,
        'comparison_directory': str(compare) if compare else None,
        'original_prediction_cache_required': False,
        'damaged_prefix_or_repair_audit_required': False,
        'personnel_relation_or_partition_refits': 0,
        'candidate_or_K_selection_reruns': 0,
        'new_fusion_calls': 0,
        'class_specific_calibration_rates': 'read from frozen calibration.csv.gz',
        'fallback_reaggregation':
            'global/k only, from COMPLETE train_buildings and training_panel; '
            'saved k/difficulty baselines must agree within 1e-12',
        'required_inputs': [str(path.relative_to(source)) for path in required],
        'missing_inputs': [str(path) for path in required if not path.is_file()],
        'folds': folds,
        'total_prediction_rows': sum(row['prediction_rows'] for row in folds),
        'execute_requires_new_separate_output_directory': True,
    }
    return plan, available, required


def load_events(path, pd, np):
    # Read only the frozen interface columns, in chunks; no geometry-wide parse.
    needed = ['event_id', 'panel_id', 'image_id', 'building', 'difficulty', 'k',
              'worker_a', 'worker_b', 'stable_main']
    header = set(pd.read_csv(path, nrows=0).columns)
    require(set(needed) <= header, f'Missing event columns: {set(needed) - header}')
    columns = needed + (['layer'] if 'layer' in header else [])
    parts = list(pd.read_csv(path, usecols=columns, chunksize=CHUNK_ROWS))
    events = pd.concat(parts, ignore_index=True)
    require(events.event_id.notna().all() and events.event_id.is_unique,
            'event_id must be present and unique')
    if 'layer' in events:
        require(events.layer.eq('ordinary_manual').all(), 'Unexpected event layer')
        events = events.drop(columns='layer')
    require(events[needed[:-1]].notna().all().all(), 'Missing event identity/context')
    if events.stable_main.dtype == object:
        raw = events.stable_main.astype(str).str.lower()
        converted = raw.map({'true': 1., 'false': 0., '1': 1., '0': 0.,
                             '1.0': 1., '0.0': 0.})
        require(converted.notna().eq(events.stable_main.notna()).all(),
                'Unrecognized stable_main value')
        events['stable_main'] = converted
    else:
        events['stable_main'] = pd.to_numeric(events.stable_main, errors='raise').astype(float)
    require(set(events.stable_main.dropna().unique()) <= {0., 1.}, 'Invalid stability outcome')
    events['difficulty'] = events.difficulty.replace(DIFFICULTY_MAP)
    events['k'] = events.k.astype(int)
    return events


def prepare_fold(source, fold, complete, events, selection, pd, np):
    folder = source / 'reverse/results/folds' / fold
    classes = pd.read_csv(folder / 'classes.csv.gz', keep_default_na=False)
    rates = pd.read_csv(folder / 'calibration.csv.gz', keep_default_na=False)
    require(classes.fold_id.eq(fold).all() and rates.fold_id.eq(fold).all(),
            f'Input table fold mismatch: {fold}')
    require(classes.training_key.eq(complete['training_key']).all(),
            f'Class training key mismatch: {fold}')
    require(not classes.duplicated(['method_id', 'domain', 'worker_id']).any(),
            f'Duplicate class keys: {fold}')
    require(not rates.duplicated(['method_id', 'k', 'difficulty', 'relation']).any(),
            f'Duplicate calibration keys: {fold}')
    require(rates.probability.between(0, 1).all(), f'Invalid calibration probability: {fold}')
    require(set(rates.relation) <= {'unknown', 'within', 'between'},
            f'Invalid calibration relation: {fold}')
    aliases = complete['selected_candidates']
    method_order = list(classes.method_id.drop_duplicates())
    candidate_order = [method for method in method_order if method not in aliases]
    ordered = candidate_order + list(aliases)
    require(len(candidate_order) == complete['candidate_count'], f'Candidate count mismatch: {fold}')
    require(set(rates.method_id) == set(candidate_order), f'Calibration method mismatch: {fold}')
    require(set(ordered) == set(method_order) and len(ordered) == len(method_order),
            f'Alias/method mismatch: {fold}')
    test = events[events.building.eq(fold)].copy()
    train = events[events.panel_id.eq(complete['training_panel']) &
                   events.building.isin(complete['train_buildings'])].copy()
    require(len(test) == complete['n_test_events'], f'Test count mismatch: {fold}')
    require(len(train) == complete['n_train_events'], f'Training count mismatch: {fold}')
    require(not train.building.eq(fold).any(), f'Heldout outcome in fallback aggregation: {fold}')
    # The original export saved cells/rates but not its global/k fallbacks.
    # Passing only unknown relations does not fit any class-specific rate.
    baseline = selection.fit_calibrator(train, pd.Series('unknown', index=train.index))
    require(not baseline['rates'], 'Unexpected class-specific fallback fit')
    specs = {}
    baseline_difference = 0.
    for method in ordered:
        source_method = aliases.get(method, method)
        group = classes[classes.method_id.eq(method)].copy()
        group['class_id'] = group.class_id.replace('', 'unknown')
        domains = set(group.domain)
        require(domains == {'global'} or domains == {'easy', 'medium', 'hard'},
                f'Unexpected domains for {fold}/{method}: {domains}')
        is_global = domains == {'global'}
        labels = (group.set_index('worker_id').class_id.to_dict() if is_global else
                  group.set_index(['domain', 'worker_id']).class_id.to_dict())
        if method in aliases:
            original = classes[classes.method_id.eq(source_method)]
            left = group.set_index(['domain', 'worker_id']).class_id.sort_index()
            right = original.set_index(['domain', 'worker_id']).class_id.sort_index()
            require(left.equals(right), f'Alias labels differ from selected candidate: {fold}/{method}')
            require(group.source_candidate_id.eq(source_method).all(),
                    f'Alias source mismatch: {fold}/{method}')
        saved = rates[rates.method_id.eq(source_method)]
        cells = {(int(row.k), str(row.difficulty)): float(row.probability)
                 for row in saved[saved.relation.eq('unknown')].itertuples()}
        require(set(cells) == set(baseline['cells']), f'Saved baseline cell mismatch: {fold}/{method}')
        difference = max((abs(value - baseline['cells'][key]) for key, value in cells.items()), default=0.)
        baseline_difference = max(baseline_difference, difference)
        require(difference <= TOLERANCE, f'Saved baseline numerical mismatch: {fold}/{method}')
        calibrator = dict(baseline)
        calibrator['cells'] = cells
        calibrator['rates'] = {
            (int(row.k), str(row.difficulty), str(row.relation)): float(row.probability)
            for row in saved[~saved.relation.eq('unknown')].itertuples()
        }
        specs[method] = {'labels': labels, 'domain': 'global' if is_global else 'difficulty',
                         'calibrator': calibrator,
                         'source_candidate_id': source_method if method in aliases else ''}
    return test, ordered, specs, baseline_difference


def method_values(test, spec, selection):
    relation = selection.attach_relation(test, spec['labels'], spec['domain'])
    probability = selection.predict_calibrator(spec['calibrator'], test, relation)
    return relation.to_numpy(), probability


def verify_written(path, test, ordered, specs, fold, training_key, selection, pd, np):
    n_test = len(test)
    expected_count = n_test * len(ordered)
    observed = 0
    maximum_difference = 0.
    event_ids = test.event_id.to_numpy()
    current_method = None
    for chunk in pd.read_csv(path, compression='gzip', dtype=str,
                             keep_default_na=False, chunksize=CHUNK_ROWS):
        require(list(chunk.columns) == PREDICTION_COLUMNS, 'Prediction column mismatch')
        cursor = 0
        while cursor < len(chunk):
            method_index, event_offset = divmod(observed, n_test)
            require(method_index < len(ordered), 'Unexpected extra prediction rows')
            method = ordered[method_index]
            if current_method != method:
                relation, probability = method_values(test, specs[method], selection)
                current_method = method
            length = min(len(chunk) - cursor, n_test - event_offset)
            block = chunk.iloc[cursor:cursor + length]
            section = slice(event_offset, event_offset + length)
            expected_identity = {
                'event_id': event_ids[section],
                'method_id': method,
                'fold_id': fold,
                'relation': relation[section],
                'training_key': training_key,
                'source_candidate_id': specs[method]['source_candidate_id'],
            }
            for column, expected in expected_identity.items():
                agrees = (block[column].eq(expected).all() if isinstance(expected, str)
                          else np.array_equal(block[column].to_numpy(), expected))
                require(agrees, f'Prediction identity/relationship mismatch: {fold}/{method}/{column}')
            values = block[['predicted_stability', 'probability']].astype(float).to_numpy()
            require(np.isfinite(values).all() and ((values >= 0) & (values <= 1)).all(),
                    f'Invalid exported probability: {fold}/{method}')
            require(np.array_equal(values[:, 0], values[:, 1]), 'Probability alias columns differ')
            difference = float(np.max(np.abs(values - probability[section, None])))
            maximum_difference = max(maximum_difference, difference)
            require(difference <= TOLERANCE, f'Probability read-back mismatch: {fold}/{method}')
            cursor += length
            observed += length
    require(observed == expected_count, f'Prediction row count {observed} != {expected_count}')
    uncompressed_bytes = full_gzip_crc(path)
    return {'rows': observed, 'methods': len(ordered), 'events_per_method': n_test,
            'identity_relationship_training_key_and_alias_source_exact': True,
            'unique_event_method_key': True,
            'method_counts': {method: n_test for method in ordered},
            'maximum_probability_readback_difference': maximum_difference,
            'full_csv_readback_pass': True, 'full_gzip_crc_pass': True,
            'uncompressed_bytes': uncompressed_bytes}


def compare_complete_predictions(original, rebuilt, pd, np):
    original_hash = sha256(original)
    rows = 0
    maximum = 0.
    kwargs = {'compression': 'gzip', 'dtype': str, 'keep_default_na': False,
              'chunksize': CHUNK_ROWS}
    with pd.read_csv(original, **kwargs) as left, pd.read_csv(rebuilt, **kwargs) as right:
        for old, new in zip_longest(left, right):
            require(old is not None and new is not None, 'Reference/export lengths differ')
            require(len(old) == len(new), 'Reference/export chunk lengths differ')
            require(list(old.columns) == list(new.columns) == PREDICTION_COLUMNS,
                    'Reference/export column mismatch')
            for column in IDENTITY_COLUMNS:
                require(np.array_equal(old[column].to_numpy(), new[column].to_numpy()),
                        f'Reference/export identity mismatch: {column}, offset {rows}')
            for column in ['predicted_stability', 'probability']:
                a = old[column].astype(float).to_numpy()
                b = new[column].astype(float).to_numpy()
                require(np.isfinite(a).all() and np.isfinite(b).all(), 'Non-finite comparison value')
                maximum = max(maximum, float(np.max(np.abs(a - b))))
            require(maximum <= TOLERANCE, 'Reference/export probability tolerance exceeded')
            rows += len(old)
    full_gzip_crc(original)
    require(sha256(original) == original_hash, 'Comparison input changed during read')
    return {'reference_path': str(original), 'reference_sha256': original_hash,
            'rows_compared': rows, 'all_identity_columns_exact': True,
            'maximum_probability_difference': maximum, 'tolerance': TOLERANCE,
            'entire_reference_crc_pass': True, 'reference_unchanged': True,
            'comparison_scope': 'entire completed file; not a damaged/readable prefix'}


def export_fold(source, output, compare, fold, complete, events, selection, pd, np):
    started = time.time()
    test, ordered, specs, baseline_difference = prepare_fold(
        source, fold, complete, events, selection, pd, np)
    directory = output / 'folds' / fold
    directory.mkdir(parents=True, exist_ok=False)
    destination = directory / 'predictions.csv.gz'
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.writing')
    with temporary.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding='utf-8', newline='') as handle:
                for index, method in enumerate(ordered):
                    relation, probability = method_values(test, specs[method], selection)
                    frame = pd.DataFrame({
                        'event_id': test.event_id.to_numpy(), 'method_id': method,
                        'fold_id': fold, 'relation': relation,
                        'predicted_stability': probability, 'probability': probability,
                        'training_key': complete['training_key'],
                        'source_candidate_id': specs[method]['source_candidate_id'],
                    }, columns=PREDICTION_COLUMNS)
                    frame.to_csv(handle, index=False, header=index == 0)
        raw.flush()
        os.fsync(raw.fileno())
    verification = verify_written(temporary, test, ordered, specs, fold,
                                  complete['training_key'], selection, pd, np)
    comparison = None
    if compare:
        reference = compare / 'folds' / fold / 'predictions.csv.gz'
        comparison = compare_complete_predictions(reference, temporary, pd, np)
        require(comparison['rows_compared'] == verification['rows'], 'Incomplete reference comparison')
    digest = sha256(temporary)
    os.replace(temporary, destination)
    sync_directory(directory)
    receipt = {
        'fold_id': fold, 'training_key': complete['training_key'],
        'training_buildings': complete['train_buildings'],
        'training_panel': complete['training_panel'],
        'test_images': int(test.image_id.nunique()),
        'test_buildings': int(test.building.nunique()),
        'test_events_by_panel': {str(k): int(v) for k, v in test.panel_id.value_counts().items()},
        'output_relative_path': str(destination.relative_to(output)),
        'output_sha256': digest,
        'maximum_saved_cell_baseline_difference': baseline_difference,
        'k_or_global_fallback_event_count_per_method':
            sum((int(k), str(d)) not in specs[ordered[0]]['calibrator']['cells']
                for k, d in zip(test.k, test.difficulty)),
        'verification': verification,
        'optional_complete_reference_comparison': comparison,
        'seconds': time.time() - started,
    }
    atomic_json(directory / 'REEXPORT_RECEIPT.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=HERE.parent,
                        help='Frozen work_personnel_typing_A_20261019 directory')
    parser.add_argument('--fold', action='append', metavar='BUILDING',
                        help='Outer fold to export; repeat for several; default all completed outer folds')
    parser.add_argument('--output-dir', type=Path,
                        help='New output directory outside the frozen source tree; required with --execute')
    parser.add_argument('--compare-dir', type=Path,
                        help='Optional existing results directory containing folds/<fold>/predictions.csv.gz')
    parser.add_argument('--execute', action='store_true', help='Execute the plan; otherwise read-only plan')
    args = parser.parse_args()
    plan, available, inputs = make_plan(args)
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        return 0
    require(args.output_dir is not None, '--execute requires --output-dir')
    source = args.source_root.resolve()
    output = args.output_dir.resolve()
    require(not output.exists(), f'Output directory already exists: {output}')
    require(source != output and source not in output.parents and output not in source.parents,
            'Output and frozen source trees must be separate')
    require(not plan['missing_inputs'], f'Missing required frozen inputs: {plan["missing_inputs"]}')
    require(all(row['optional_comparison_available'] is not False for row in plan['folds']),
            'A requested complete reference prediction is missing; omit --compare-dir to reconstruct without it')
    before = {str(path.relative_to(source)): sha256(path) for path in inputs}
    for row in plan['folds']:
        complete = available[row['fold_id']]
        require(before['events/common_events.csv.gz'] == complete['event_sha256'],
                f'Frozen event SHA mismatch: {row["fold_id"]}')
        require(before['reverse/selection_common.py'] == complete['selection_code_sha256'],
                f'Frozen calibration function SHA mismatch: {row["fold_id"]}')
    # Dynamic loading avoids importing any discovery/fusion entrypoint. Prevent
    # Python from adding bytecode files to the frozen input tree.
    sys.dont_write_bytecode = True
    import numpy as np
    import pandas as pd
    module_spec = importlib.util.spec_from_file_location(
        'frozen_part_a_prediction_utilities', source / 'reverse/selection_common.py')
    selection = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(selection)
    events = load_events(source / 'events/common_events.csv.gz', pd, np)
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    atomic_json(output / 'REEXPORT_PLAN.json', plan)
    receipts = []
    try:
        for row in plan['folds']:
            fold = row['fold_id']
            receipt = export_fold(source, output, args.compare_dir.resolve() if args.compare_dir else None,
                                  fold, available[fold], events, selection, pd, np)
            receipts.append(receipt)
            print(json.dumps({'fold_complete': fold, 'rows': receipt['verification']['rows'],
                              'methods': receipt['verification']['methods'],
                              'seconds': receipt['seconds']}, ensure_ascii=False), flush=True)
        after = {str(path.relative_to(source)): sha256(path) for path in inputs}
        require(before == after, 'A frozen input changed while predictions were exported')
        result = {
            'pass_all': True, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'source_root': str(source), 'output_dir': str(output),
            'code_sha256': sha256(__file__),
            'input_sha256': before, 'frozen_inputs_unchanged': True,
            'personnel_relation_or_partition_refits': 0,
            'candidate_or_K_selection_reruns': 0, 'new_fusion_calls': 0,
            'class_specific_calibration_refits': 0,
            'global_and_k_fallback_reaggregations': len(receipts),
            'training_scope': 'only COMPLETE train_buildings and training_panel',
            'original_prediction_cache_required': False,
            'original_bad_prefix_or_fault_audit_used': False,
            'total_prediction_rows': sum(r['verification']['rows'] for r in receipts),
            'writer': 'UUID temporary file, close/fsync, complete CSV/key/value/CRC verification, '
                      'optional full reference comparison, atomic rename, directory fsync',
            'environment': {'python': sys.version, 'numpy': np.__version__, 'pandas': pd.__version__},
            'folds': receipts, 'seconds': time.time() - started,
        }
        atomic_json(output / 'REEXPORT_RECEIPT.json', result)
        print(json.dumps({'pass_all': True, 'folds': len(receipts),
                          'rows': result['total_prediction_rows'],
                          'receipt': str(output / 'REEXPORT_RECEIPT.json')}, ensure_ascii=False), flush=True)
    except Exception as error:
        atomic_json(output / 'REEXPORT_ERROR.json', {
            'pass_all': False, 'error_type': type(error).__name__, 'message': str(error),
            'completed_folds': [r['fold_id'] for r in receipts],
            'note': 'Partial files retained in the new output directory; frozen inputs were not written.',
        })
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
