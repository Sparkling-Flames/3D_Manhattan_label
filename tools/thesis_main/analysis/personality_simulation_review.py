"""Run a local, provenance-preserving personnel simulation trial, not a data import."""
from __future__ import annotations

import argparse
import collections
import copy
import importlib
import json
from pathlib import Path
import sys
import time
import zipfile

import numpy as np

from tools.thesis_main.analysis import simulate_annotators as base
from tools.thesis_main.analysis import simulate_annotators_opt as old
from tools.thesis_main.analysis.simulate_annotators_pilot import PILOT_IMAGES
from tools.thesis_main.analysis.simulator_personality_inputs import load_current, read_csv, QUALITY_VERSION
from tools.thesis_main.analysis.personality_annotator_sampler import fit_personality, generate, sample_time
from tools.thesis_main.analysis.quality_joint_closeout_review_20261015 import scores


class QualityEvaluator:
    def __init__(self, directory, objects):
        directory = Path(directory).resolve()
        archive = base.ROOT / 'research/quality_pro_handoff_20261014/quality_pro_handoff_20261014_READY.zip'
        with zipfile.ZipFile(archive) as source:
            for name in source.namelist():
                if name.startswith('engine/') and name.endswith('.py'):
                    target = directory / name.removeprefix('engine/')
                    if not target.resolve().is_relative_to(directory):
                        raise ValueError('invalid_engine_archive_path')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        target.write_bytes(source.read(name))
                    elif target.read_bytes() != source.read(name):
                        raise ValueError('frozen_engine_modified:' + name)
        sys.path.insert(0, str(directory))
        self.engine = {key: importlib.import_module(module) for key, module in
                       dict(au='audit_geometry', sp='geometric_components', valid='strict_geometry',
                            hm='height_revision', center='centered_height', trad='traditional_metrics', score='score').items()}
        self.convert = importlib.import_module('prepare_inputs').geometry
        self.measure = importlib.import_module('evaluate_geometry').evaluate_geometry
        self.engine['configs'] = {'frozen_baseline': self.engine['score'].BASELINE}
        for module in [*self.engine.values()]:
            if hasattr(module, '__file__') and not Path(module.__file__).resolve().is_relative_to(directory):
                raise ValueError('wrong_metric_module_loaded:' + module.__file__)
        self.objects, self.cache, self.references = objects, {}, {}
        self.archive_sha256 = base.digest(archive)

    def evaluate(self, points, reference_id):
        key = (json.dumps(points, separators=(',', ':'), allow_nan=False), reference_id)
        if key in self.cache:
            return self.cache[key]
        result = dict(status='unavailable', WQ=None, IoU3D100=None, quality_version=QUALITY_VERSION,
                      reference_id=reference_id, metrics=None, reason_codes=[])
        if reference_id not in self.objects:
            result['reason_codes'] = ['current_reference_missing']
        elif not base.parsed(points):
            result['reason_codes'] = ['numeric_invalid_output']
        else:
            try:
                if reference_id not in self.references:
                    self.references[reference_id] = self.convert(self.objects[reference_id]['points_1024x512'])
                measured = self.measure(self.convert(points), self.references[reference_id], self.engine)
                result['reason_codes'] = measured['reason_codes']
                if measured['status'] == 'complete':
                    m = measured['metrics']
                    result.update(status='complete', metrics=m,
                        WQ=float(scores(*(np.asarray(m[k]) for k in ('iou_2d', 'dir', 'S_bottom_deg', 'Hcenter', 'Hmean')))['WQ']),
                        IoU3D100=float(100 * m['iou_3d_corner_mean']) if m['iou_3d_corner_mean'] is not None else None)
            except (ValueError, ArithmeticError) as exc:
                result['reason_codes'] = [str(exc)]
        self.cache[key] = result
        return result


def baseline(bank, fitted, workers, seed, image_id):
    rows = old.simulate_v2(bank, fitted['learned'], workers, 'worker', seed, image_id,
                           cap=8, scale=1, no_x_collapse=False, count_mode=False, tries=1)
    for row in rows:
        worker = row['source_worker_profile_id']
        donor_workers = {r['annotation_id']: r['worker_id'] for r in fitted['records']}
        row['residual_donor_worker_id'] = donor_workers.get(row['residual_donor_annotation_id'])
        profile = fitted['profiles'].get(worker, dict(quality='uncertain', speed='uncertain', axes={}))
        row.update(variant='current_baseline', condition='manual', source_profile=profile,
            source_quality=profile['quality'], source_speed=profile['speed'], quality_version=QUALITY_VERSION,
            held_out_building=fitted['heldout'], generation_status='baseline_output', semi_status='not_applicable')
        row['name'] = f'来源人员质量{dict(higher="较高", lower="较低", uncertain="待定")[profile["quality"]]} / W{int(worker):03d} / 当前输入基线'
        row.update(sample_time(fitted, worker, None, base.seed_for(seed, worker, 'time')))
        row['simulation_id'] += ':current_baseline'
    return rows


def contrast(evaluations, variant='hierarchical'):
    cells = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in evaluations:
        if row['variant'] != variant or row['WQ'] is None:
            continue
        if row['source_quality'] in ('higher', 'lower'):
            cells[(row['image_id'], row['reference_id'], row['building_id'])][row['source_quality']].append(row['WQ'])
    pairs = []
    for (image, reference, building), groups in cells.items():
        if groups['higher'] and groups['lower']:
            pairs.append(dict(image_id=image, reference_id=reference, building_id=building,
                higher_n=len(groups['higher']), lower_n=len(groups['lower']),
                WQ_gap=float(np.mean(groups['higher']) - np.mean(groups['lower']))))
    by_image = collections.defaultdict(list)
    for row in pairs:
        by_image[(row['image_id'], row['building_id'])].append(row['WQ_gap'])
    by_building = collections.defaultdict(list)
    for (_, building), values in by_image.items():
        by_building[building].append(float(np.mean(values)))
    means = np.array([np.mean(v) for _, v in sorted(by_building.items())])
    interval = None
    if len(means) >= 3:
        rng = np.random.default_rng(20261015)
        draws = rng.choice(means, size=(2000, len(means)), replace=True).mean(axis=1)
        interval = np.quantile(draws, [.025, .975]).tolist()
    return pairs, dict(paired_reference_cells=len(pairs), paired_images=len(by_image), buildings=len(means),
        building_equal_WQ_gap=float(means.mean()) if len(means) else None,
        building_bootstrap_interval=interval,
        numerical_quality_signal=bool(interval is not None and interval[0] > 0),
        interpretation='fixed historical pool, paired image/reference contrast; no universal worker grade claim')


def matched_comparison(evaluations):
    grouped = collections.defaultdict(dict)
    for row in evaluations:
        grouped[(row['image_id'], row['reference_id'], row['source_worker_profile_id'])][row['variant']] = row
    rows = []
    for (image, reference, worker), variants in grouped.items():
        if set(variants) != {'current_baseline', 'hierarchical'}:
            raise ValueError('unpaired_simulation_comparison')
        a, b = variants['current_baseline'], variants['hierarchical']
        rows.append(dict(image_id=image, reference_id=reference, worker_id=worker, building_id=a['building_id'],
            source_quality=a['source_quality'], common_evaluable=a['WQ'] is not None and b['WQ'] is not None,
            baseline_WQ=a['WQ'], hierarchical_WQ=b['WQ'],
            delta_WQ=b['WQ'] - a['WQ'] if a['WQ'] is not None and b['WQ'] is not None else None))
    return rows


def calibration_errors(generated, real_records):
    real = {(r['image_id'], r['reference_id'], r['worker_id']): r
            for r in real_records if r['WQ'] is not None}
    rows = []
    for sample in generated:
        for evaluation in sample['evaluation']:
            key = (sample['image_id'], evaluation['reference_id'], sample['source_worker_profile_id'])
            target = real.get(key)
            if target is None:
                continue
            value = evaluation['WQ']
            rows.append(dict(image_id=key[0], reference_id=key[1], worker_id=key[2], building_id=target['building_id'],
                variant=sample['variant'], source_quality=sample['source_quality'], real_WQ=target['WQ'], generated_WQ=value,
                WQ_absolute_error=abs(target['WQ'] - value) if value is not None else None,
                count_absolute_error=abs(len(target['points']) - len(sample['points'])) / 2,
                point_distance_deg=base.distance(target['points'], sample['points'])))
    return rows


def run(output, seed=20261015, pilot_only=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = load_current()
    records, objects, models = [sources[k] for k in ('records', 'objects', 'models')]
    evaluator = QualityEvaluator(output / 'frozen_engine', objects)
    complete_bank = {i for i, bank in models.items() if all(f in bank for f in base.FAMILIES)}
    references = collections.defaultdict(set)
    grouped = collections.defaultdict(list)
    for record in records:
        grouped[record['image_id']].append(record)
        if record['reference_id']:
            references[record['image_id']].add(record['reference_id'])
    pilot_ids = [i for values in PILOT_IMAGES.values() for i in values]
    targets = sorted(set(pilot_ids) | ({i for i in references if i in complete_bank} if not pilot_only else set()))
    buildings = sorted({sources['images'][i]['building_id'] for i in targets})
    old_pilot = json.loads((base.ROOT.parent / 'output/simulator_validation_20261015/pilot_verified/review_cases.json').read_text())
    pilot_rosters = {c['image_id']: sorted({r['source_worker_profile_id'] for r in c['synthetic'] if r['condition'] == 'manual'}, key=int)
                     for c in old_pilot['cases']}
    workers = sorted({r['worker_id'] for r in records}, key=int)
    difficulty = {r['image_id']: r for r in read_csv(base.ROOT / 'research/difficulty_coarse_closeout_20261014/difficulty_targets.csv')}
    base.write_csv(output / 'source_ledger.csv', sources['ledger'])
    input_files = [base.ROOT / p for p in (
        'research/quality_joint_closeout_review_20261015/JOINT_COMPARISON_1145.csv',
        'research/worker_classification_progress_20261014/source_inventory.csv',
        'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json',
        'analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl')]
    base.dump(output / 'input_manifest.json', dict(quality_version=QUALITY_VERSION,
        loader_validation=sources['validation'], loader_manifest=sources['manifest'],
        input_sha256={str(p): base.digest(p) for p in input_files}, engine_archive_sha256=evaluator.archive_sha256,
        current_data_sha256=__import__('hashlib').sha256(json.dumps(list(objects.values()), sort_keys=True).encode()).hexdigest(),
        seed=seed, pilot_only=pilot_only, model_bank='frozen offline proposals', formal_eligibility_changed=False,
        protocol='building exclusion for profiles and donors; shrinkage=8; training empirical p95 residual cap; no heldout tuning'))
    # Verify the numerical adapter on existing frozen records before new scores.
    full = [r for r in records if r['WQ'] is not None]
    parity = []
    for row in full[::max(1, len(full) // 8)][:8]:
        check = evaluator.evaluate(row['points'], row['reference_id'])
        if check['WQ'] is None or abs(check['WQ'] - row['WQ']) > 1e-5:
            raise ValueError('frozen_quality_parity_failed:' + row['record_id'] + ':' + str(check))
        parity.append(dict(record_id=row['record_id'], WQ_abs_error=abs(check['WQ'] - row['WQ']),
                           IoU3D100_abs_error=abs(check['IoU3D100'] - row['IoU3D100'])))
    base.dump(output / 'quality_parity.json', parity)
    cases, all_evaluations, profile_rows, geometry_metrics, status_rows = [], [], [], [], []
    start = time.monotonic()
    with open(output / 'simulations.jsonl', 'w', encoding='utf-8') as stream:
        for building in buildings:
            print('fit', building, flush=True)
            fitted = fit_personality(records, models, building)
            assert building not in fitted['training_buildings']
            base.dump(output / ('fold_' + building + '.json'), dict(held_out_building=building,
                profiles=fitted['profiles'], training_buildings=fitted['training_buildings'],
                training_annotation_ids=fitted['training_annotation_ids'], donors=len(fitted['donors'])))
            profile_rows.extend(dict(held_out_building=building, **p) for p in fitted['profiles'].values())
            for iid in [i for i in targets if sources['images'][i]['building_id'] == building]:
                roster = pilot_rosters[iid] if iid in pilot_ids else workers
                pair_seed = base.seed_for(seed, iid, 'paired_personality_trial')
                generated = baseline(models[iid], fitted, roster, pair_seed, iid) + generate(models[iid], fitted, roster, pair_seed, iid)
                # Targets and their reference objects are first consulted here,
                # after all samples for this image have been generated.
                target_refs = sorted(references[iid])
                for row in generated:
                    assert row.get('residual_donor_building_id') != building and row.get('time_donor_building_id') != building
                    row['evaluation'] = [dict(evaluator.evaluate(row['points'], ref)) for ref in target_refs]
                    row['evaluation_status'] = 'scored_or_explicit_failure' if target_refs else 'no_admitted_full_reference'
                    row['partition'] = 'ordinary_current_evaluation' if target_refs else 'pilot_diagnostic_only'
                    for evaluation in row['evaluation']:
                        all_evaluations.append(dict(image_id=iid, building_id=building, variant=row['variant'],
                            simulation_id=row['simulation_id'], source_worker_profile_id=row['source_worker_profile_id'],
                            source_quality=row['source_quality'], source_speed=row['source_speed'], generation_status=row['generation_status'],
                            active_time_seconds=row.get('active_time_seconds'), **evaluation))
                    status_rows.append(dict(image_id=iid, variant=row['variant'],
                        source_quality=row['source_quality'], source_speed=row['source_speed'],
                        residual_source=row['residual_source'], generation_status=row['generation_status'],
                        model_copy=row['model_copy'], personal_donor=row.get('residual_donor_worker_id') == row['source_worker_profile_id']))
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                if len(grouped[iid]) >= 2:
                    for variant in ('current_baseline', 'hierarchical'):
                        rows = [r for r in generated if r['variant'] == variant]
                        geometry_metrics.append(dict(image_id=iid, building_id=building, variant=variant,
                            **base.comparison([r['points'] for r in grouped[iid]], rows)))
                if iid in pilot_ids:
                    humans = []
                    for gate in sources['gates']:
                        if gate['image_id'] != iid or gate['condition'] != 'manual':
                            continue
                        obj = objects[gate['object_id']]
                        if obj.get('points_1024x512') is None:
                            continue
                        humans.append(dict(name='真人 ' + obj['worker_id'] + ' / ' + gate['role'], points=obj['points_1024x512'],
                            object_id=obj['object_id'], record_id=gate['record_id'], ring_confirmed=obj.get('ring_confirmed', False),
                            pairing_verified=bool(obj.get('links_zero_based')),
                            order_status=obj.get('order_status'), source_pair_indices=obj.get('ordered_source_pair_indices'),
                            source_point_indices=obj.get('ordered_source_point_indices')))
                    photo = next((base.ROOT / 'data/mp3d_layout').glob('*/img/' + iid + '.png'))
                    cases.append(dict(image_id=iid, image_type=difficulty.get(iid, {}).get('current_class', '待核'),
                        building_id=building, image_path=str(photo.resolve()), models=list(models[iid].values()),
                        human=humans, synthetic=generated))
                print('generated', iid, len(generated), 'elapsed', round(time.monotonic() - start), flush=True)
    base.write_csv(output / 'evaluation.csv', all_evaluations)
    base.write_csv(output / 'personnel_profiles.csv', profile_rows)
    base.write_csv(output / 'geometry_evaluation.csv', geometry_metrics)
    base.write_csv(output / 'generation_status.csv', status_rows)
    contrasts, gate = contrast(all_evaluations)
    _, baseline_gate = contrast(all_evaluations, 'current_baseline')
    matched = matched_comparison(all_evaluations)
    base.write_csv(output / 'matched_evaluation.csv', matched)
    common_rows = [dict(image_id=r['image_id'], reference_id=r['reference_id'], building_id=r['building_id'],
        source_quality=r['source_quality'], variant=variant, WQ=r[field])
        for r in matched if r['common_evaluable'] for variant, field in
        [('current_baseline', 'baseline_WQ'), ('hierarchical', 'hierarchical_WQ')]]
    base.dump(output / 'common_quality_contrast.json', {v: contrast(common_rows, v)[1]
              for v in ('current_baseline', 'hierarchical')})
    base.write_csv(output / 'real_worker_calibration.csv', calibration_errors(base.read_jsonl(output / 'simulations.jsonl'), records))
    base.write_csv(output / 'paired_quality_contrasts.csv', contrasts)
    cases.sort(key=lambda c: pilot_ids.index(c['image_id']))
    base.dump(output / 'review_cases.json', dict(cases=cases, default_examples=pilot_ids))
    counts = {variant: dict(collections.Counter(r['generation_status'] for r in status_rows if r['variant'] == variant))
              for variant in ('current_baseline', 'hierarchical')}
    base.dump(output / 'summary.json', dict(schema='personality_simulation_trial_v1', quality_version=QUALITY_VERSION,
        heldout_buildings=len(buildings), generated_images=len(targets), generated_samples=len(status_rows), pilot_images=len(cases),
        manual_training_records=len(records), scored_manual_records=len(full), generation_status=counts,
        evaluation_records=len(all_evaluations), score_unavailable=sum(r['WQ'] is None for r in all_evaluations),
        quality_contrast=gate, baseline_quality_contrast=baseline_gate,
        matched_evaluable=sum(r['common_evaluable'] for r in matched),
        only_local=True, synthetic=True, next_stage='review_trial_results_before_any_expansion',
        semi_scope_export_expansion_started=False, runtime_seconds=time.monotonic() - start))
    from tools.thesis_main.analysis.render_simulated_annotators import main as render
    previous = sys.argv
    try:
        sys.argv = ['render_simulated_annotators', '--run-dir', str(output)]
        render()
    finally:
        sys.argv = previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--pilot-only', action='store_true')
    parser.add_argument('--conditions', nargs='+', choices=['manual', 'semi'], default=None)
    parser.add_argument('--mode', choices=['legacy', 'pilot', 'fill-to-eight', 'fill-to-35-wild', 'fill-144-gallery', 'fill-to-35-anchor-space'], default='legacy')
    parser.add_argument('--semi-mode', choices=['generative', 'strict'], default='generative')
    args = parser.parse_args()
    if args.seed is None:
        args.seed = 20261017 if args.mode in ('fill-to-35-wild', 'fill-144-gallery', 'fill-to-35-anchor-space') else 20261015
    if args.mode == 'fill-to-35-anchor-space':
        if args.conditions and args.conditions != ['manual']:
            raise ValueError('fill-to-35-anchor-space_requires_manual_only')
        from .anchor_space_run import run as run_anchor
        run_anchor(args.output, args.seed, args.pilot_only)
        return
    if args.mode != 'legacy' or args.conditions is not None:
        from .personality_incremental_run import run_incremental
        default_conditions = ['manual'] if args.mode in ('fill-to-35-wild', 'fill-144-gallery', 'fill-to-35-anchor-space') else ['manual', 'semi']
        run_incremental(args.output, args.seed, list(dict.fromkeys(args.conditions or default_conditions)),
                        'pilot' if args.mode == 'legacy' else args.mode, args.pilot_only, args.semi_mode)
    else:
        run(args.output, args.seed, args.pilot_only)


if __name__ == '__main__':
    main()
