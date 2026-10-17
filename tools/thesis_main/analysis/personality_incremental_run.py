"""Local pilot and fill-to-eight runs, with synthetic-only coverage and export."""
from __future__ import annotations

import collections
import html
import json
import os
from pathlib import Path
import sys

import numpy as np

from . import simulate_annotators as base
from .simulator_personality_inputs import load_current, QUALITY_VERSION
from .personality_annotator_sampler import fit_personality, generate
from .personality_response_channels import load_channels, fit_channels, normal_semi, VERSION
from .export_synthetic_label_studio import export_samples, synthetic_worker
from .simulate_annotators_pilot import PILOT_IMAGES
from .semi_edit_distribution import SUCCESS

PRESCREEN = base.ROOT / 'analysis_results/annotation_uncertainty_prescreen_20260903_v1/machine_manifest.json'


def target_panel(sources, channels, conditions, mode, pilot_only):
    candidate = {r['image_id'] for r in json.loads(PRESCREEN.read_text())['items']
                 if r['history_layer'] == 'no_existing_annotation_record'}
    if len(candidate) != 166:
        raise ValueError('candidate_166_snapshot_changed')
    counts = collections.defaultdict(set)
    for row in sources['records']:
        counts[(row['image_id'], 'manual')].add(row['worker_id'])
    for row in channels['semi']:
        counts[(row['image_id'], 'semi')].add(row['worker_id'])
    pilot = [iid for ids in PILOT_IMAGES.values() for iid in ids]
    all_images = candidate | {g['image_id'] for g in sources['gates']}
    selected = set(pilot) if pilot_only else (all_images if mode == 'fill-to-eight' else set(pilot))
    result = []
    # Freeze all requested rows, including absent models and zero-needed arms.
    for iid in sorted(selected):
        for condition in conditions:
            n = len(counts[(iid, condition)])
            need = 8 if pilot_only or mode == 'pilot' or iid in candidate else max(0, 8 - n)
            result.append(dict(image_id=iid, condition=condition, current_allowed_real_people=n,
                candidate_166=iid in candidate, requested_synthetic=need,
                selection_basis='frozen_candidate_166' if iid in candidate else 'current_under_eight',
                model_available=all(f in sources['models'].get(iid, {}) for f in base.FAMILIES)))
    return result


def run_incremental(output, seed, conditions, mode='pilot', pilot_only=False, semi_mode='generative'):
    if mode == 'fill-144-gallery':
        if conditions != ['manual']:
            raise ValueError('fill-144-gallery_requires_manual_only')
        from .difficulty_wild_round2 import run
        return run(output, seed, pilot_only)
    if mode == 'fill-to-35-wild':
        if conditions != ['manual']:
            raise ValueError('fill-to-35-wild_requires_manual_only')
        from .difficulty_wild_run import run
        return run(output, seed, pilot_only)
    from .personality_simulation_review import QualityEvaluator
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = load_current(); channels = load_channels(sources)
    panel = target_panel(sources, channels, conditions, mode, pilot_only)
    base.write_csv(output / 'target_manifest.csv', panel)
    base.write_csv(output / 'semi_evidence_inventory.csv', channels['semi_ledger'])
    input_paths = [PRESCREEN,
        base.ROOT / 'analysis_results/research_input_20260929/preprocessed_source.json',
        base.ROOT / 'analysis_results/research_input_20260929/manifest.json',
        base.ROOT / 'research/quality_joint_closeout_review_20261015/JOINT_COMPARISON_1145.csv',
        base.ROOT / 'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json',
        base.ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl']
    input_paths.append(base.ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1/images.csv')
    # Freeze all protected raw source files before the run and verify at the end.
    for directory in ('export_label', 'import_json', 'active_logs'):
        input_paths.extend(p for p in (base.ROOT / directory).rglob('*') if p.is_file())
    input_paths.extend(p for p in (base.ROOT / 'analysis_results').glob('research_input_20260929/**/manifest.json'))
    hashes = dict(channels['source_sha256'])
    hashes.update({str(p): base.digest(p) for p in input_paths})
    code_hashes = {str(p.relative_to(base.ROOT)): base.digest(p) for p in Path(__file__).parent.glob('*.py')
                   if p.name.startswith(('personality_', 'semi_edit_distribution', 'simulator_personality', 'export_synthetic'))}
    data_hash = __import__('hashlib').sha256(json.dumps(list(sources['objects'].values()), sort_keys=True).encode()).hexdigest()
    manifest = dict(schema='synthetic_channels_run_v1', generator_version=VERSION, seed=seed, mode=mode,
        conditions=conditions, semi_mode=semi_mode, source_sha256=hashes, code_sha256=code_hashes, current_data_sha256=data_hash,
        synthetic=True, local_only=True, quality_version=QUALITY_VERSION, quality_acceptance='not_established',
        scope_target_image_access='scope_fields_only; excluded_from_geometry_and_personnel_fitting',
        formal_eligibility_changed=False)
    base.dump(output / 'source_manifest.json', manifest)
    evaluator = QualityEvaluator(output / 'frozen_engine', sources['objects'])
    refs = collections.defaultdict(set)
    for row in sources['records']:
        if row['reference_id']:
            refs[row['image_id']].add(row['reference_id'])
    workers = sorted({r['worker_id'] for r in sources['records']} - {'19', '26'}, key=int)
    if len(workers) < 8:
        raise ValueError('insufficient_distinct_allowed_templates')
    pilot = [iid for ids in PILOT_IMAGES.values() for iid in ids]
    samples, cases, folds, skipped, calibration = [], [], [], [], []
    buildings = {sources['images'].get(r['image_id'], {}).get('building_id', r['image_id'].split('_')[0])
        for r in panel if r['requested_synthetic'] and r['model_available']}
    if 'semi' in conditions:
        buildings.update(r['building_id'] for r in channels['semi']
            if r.get('WQ') is not None and r.get('reference_id'))
    buildings = sorted(buildings)
    for building in buildings:
        print('fit', building, flush=True)
        fitted = fit_channels(channels, fit_personality(sources['records'], sources['models'], building))
        base.dump(output / ('fold_' + building + '.json'), dict(held_out_building=building,
            profiles=fitted['profiles'], training_buildings=fitted['training_buildings'],
            semi_training_ids=[d['annotation_id'] for d in fitted['channels']['semi']],
            time_training_ids=[d['annotation_id'] for d in fitted['channels']['times']],
            lead_effects=fitted['channels']['lead_effects']))
        base.dump(output / ('semi_distribution_' + building + '.json'), fitted['channels']['semi_distribution'])
        folds.append(building)
        # Freeze a same-person, same-image, same-reference evaluation panel. Its
        # geometry and score enter only the post-generation comparison below.
        if 'semi' in conditions:
            for evidence in [r for r in channels['semi'] if r['building_id'] == building
                    and r.get('WQ') is not None and r.get('reference_id')]:
                bank = sources['models'].get(evidence['image_id'], {})
                if not bank or not all(f in bank for f in base.FAMILIES):
                    calibration.append(dict(annotation_id=evidence['annotation_id'], building_id=building,
                        image_id=evidence['image_id'], worker_id=evidence['worker_id'],
                        reference_id=evidence['reference_id'], observed_WQ=evidence['WQ'],
                        generation_status='missing_frozen_model_bank', generated_WQ=None,
                        WQ_absolute_error=None, geometry_status=None, model_copy=None))
                    continue
                # Both conditions start from the exact frozen initialization used
                # by this real Semi response. The outcome score is not passed in.
                eval_bank = {family: dict(entry, points=evidence['initial_points'])
                    for family, entry in bank.items()}
                eval_seed = base.seed_for(seed, evidence['annotation_id'], 'same_person_image_reference')
                generated = generate(eval_bank, fitted, [evidence['worker_id']], eval_seed,
                    evidence['image_id'], condition='semi', semi_mode=semi_mode)[0]
                metric = evaluator.evaluate(generated['points'], evidence['reference_id'])
                generated_wq = metric.get('WQ')
                calibration.append(dict(annotation_id=evidence['annotation_id'], building_id=building,
                    image_id=evidence['image_id'], worker_id=evidence['worker_id'],
                    reference_id=evidence['reference_id'], observed_WQ=evidence['WQ'],
                    generated_WQ=generated_wq,
                    WQ_absolute_error=abs(generated_wq - evidence['WQ']) if generated_wq is not None else None,
                    generation_status=generated['semi_status'], geometry_status=base.geometry_status(generated['points']),
                    model_copy=bool(np.array_equal(np.asarray(generated['points']), np.asarray(evidence['initial_points']))),
                    source_purpose=evidence['purpose'], quality_version=evidence.get('quality_version')))
        for iid in sorted({r['image_id'] for r in panel if r['model_available'] and
                sources['images'].get(r['image_id'], {}).get('building_id') == building}):
            generated = []
            for target in [r for r in panel if r['image_id'] == iid and r['requested_synthetic']]:
                condition = target['condition']; need = target['requested_synthetic']
                rng = np.random.default_rng(base.seed_for(seed, iid, condition, 'roster'))
                roster = rng.permutation(workers).tolist()[:need]
                pair_seed = base.seed_for(seed, iid, 'paired_personality_trial') if condition == 'manual' else base.seed_for(seed, iid, 'semi_trial')
                rows = generate(sources['models'][iid], fitted, roster, pair_seed, iid, condition=condition, semi_mode=semi_mode)
                for row in rows:
                    for key in ('residual_donor_building_id', 'semi_donor_building_id', 'time_donor_building_id', 'lead_time_donor_building_id'):
                        if row.get(key) == building:
                            raise ValueError('target_building_donor_leak:' + key)
                    row.update(simulated_worker_id=synthetic_worker(row['source_worker_profile_id'], condition),
                        generation_parameters=dict(seed=seed, image_seed=pair_seed, cap=row.get('source_delta_cap_px') if condition == 'manual' else row.get('semi_delta_cap_normalized', 'observed_semi_delta_unscaled'),
                            scale=1., count_mode='learned_addition_no_deletion' if condition == 'semi' and semi_mode == 'generative' else 'observed_deletions_addition_unsupported', condition=condition,
                            semi_mode=semi_mode if condition == 'semi' else None,
                            generator_version=VERSION), source_hashes=dict(manifest='source_manifest.json', current_data_sha256=data_hash),
                        final_points=row['points'], evaluation_status='scored_or_explicit_failure' if refs[iid] else 'no_admitted_full_reference')
                    row['evaluation'] = [evaluator.evaluate(row['points'], ref) for ref in sorted(refs[iid])]
                    generated.append(row)
            samples.extend(generated)
            if iid in pilot:
                humans = []
                for g in sources['gates']:
                    if g['image_id'] != iid:
                        continue
                    obj = sources['objects'][g['object_id']]
                    if obj.get('points_1024x512') is not None:
                        humans.append(dict(name='真人 ' + obj['worker_id'] + ' / ' + obj['condition'],
                            points=obj['points_1024x512'], pairing_verified=bool(obj.get('links_zero_based')),
                            ring_confirmed=obj.get('ring_confirmed', False)))
                # Show both endpoints of Semi edits using the existing model overlay group.
                models = list(sources['models'][iid].values())
                models += [dict(name='Semi 初始 / ' + s['simulated_worker_id'], points=s['initial_points'],
                    ring_confirmed=False, initialization_trace=s['initialization_trace']) for s in generated if s['condition'] == 'semi']
                path = next((base.ROOT / 'data/mp3d_layout').glob('*/img/' + iid + '.png'))
                cases.append(dict(image_id=iid, building_id=building, image_path=str(path), image_type='增量试点',
                    models=models, human=humans, synthetic=generated))
            print('generated', iid, len(generated), flush=True)
    for row in panel:
        if row['requested_synthetic'] and not row['model_available']:
            skipped.append(dict(image_id=row['image_id'], condition=row['condition'], reason='frozen_model_bank_missing', requested=row['requested_synthetic']))
    base.write_csv(output / 'generation_skips.csv', skipped)
    base.write_csv(output / 'personal_semi_calibration.csv', calibration)
    with (output / 'simulations.jsonl').open('w') as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + '\n')
    exported, export_summary = export_samples(samples, sources['images'], output)
    coverage = []
    for target in panel:
        group = [s for s in samples if s['image_id'] == target['image_id'] and s['condition'] == target['condition']]
        valid = sum(s['simulation_id'] in exported for s in group)
        coverage.append(dict(**target, synthetic_generated=len(group), format_readable=valid,
            experiment_people=target['current_allowed_real_people'] + valid,
            geometry_evaluable=sum(any(e['WQ'] is not None for e in s['evaluation']) for s in group),
            scope_valid=sum(s.get('worker_scope_response') in ('in_scope', 'oos') for s in group),
            unsupported_or_missing=sum(s['condition'] == 'semi' and s['semi_status'] not in SUCCESS for s in group),
            unfilled=max(0, target['requested_synthetic'] - valid)))
    base.write_csv(output / 'coverage_panel.csv', coverage)
    columns = list(coverage[0])
    table = '<tr>' + ''.join('<th>' + html.escape(k) + '</th>' for k in columns) + '</tr>'
    table += ''.join('<tr>' + ''.join('<td>' + html.escape(str(r[k])) + '</td>' for k in columns) + '</tr>' for r in coverage)
    (output / 'coverage_panel.html').write_text('<!doctype html><meta charset="utf-8"><title>合成实验覆盖</title><h1>真实人数与合成实验覆盖</h1><p>真实资格保持原值。组合数量仅用于实验，未连接 GT 或正式融合参数。未支持的 Semi 不计入可交付补足人数。</p><table border="1">' + table + '</table>')
    base.dump(output / 'trial_acceptance.json', dict(overall_trial_passed=False,
        quality_acceptance='previous_personality_quality_failure_retained', functional_acceptance='see validation',
        decision='experimental_only_no_formal_admission'))
    base.dump(output / 'review_cases.json', dict(cases=sorted(cases, key=lambda c: pilot.index(c['image_id']))))
    if cases:
        from .render_simulated_annotators import main as render
        argv = sys.argv
        try:
            sys.argv = ['render', '--run-dir', str(output)]
            render()
        finally:
            sys.argv = argv
    unchanged = {p: base.digest(Path(p)) == digest for p, digest in hashes.items()}
    if not all(unchanged.values()):
        raise ValueError('source_file_changed_during_run')
    summary = dict(schema='synthetic_channels_run_v1', synthetic=True, only_local=True, generator_version=VERSION,
        mode=mode, conditions=conditions, seed=seed, candidate_snapshot_images=166, target_images=len({r['image_id'] for r in panel}),
        requested=sum(r['requested_synthetic'] for r in panel), generated=len(samples), **export_summary,
        by_condition=dict(collections.Counter(s['condition'] for s in samples)),
        semi_status=dict(collections.Counter(s['semi_status'] for s in samples if s['condition'] == 'semi')),
        lead_time_status=dict(collections.Counter(s['lead_time_status'] for s in samples)),
        active_time_status=dict(collections.Counter(s['timing_status'] for s in samples)),
        scope_pools=dict(collections.Counter(s['scope_pool'] for s in samples)),
        quality_acceptance=False, formal_qualification_updated=False,
        remaining_exportable_deficit=sum(r['unfilled'] for r in coverage), protected_files_verified=len(unchanged),
        source_files_unchanged=all(unchanged.values()))
    semi_rows = [r for r in samples if r['condition'] == 'semi']
    behavior_pools = collections.defaultdict(collections.Counter)
    source_pools_by_behavior = collections.defaultdict(collections.Counter)
    requested_behaviors = collections.Counter()
    for row in semi_rows:
        actual = row.get('semi_actual_behavior') or row.get('semi_behavior') or 'unavailable'
        requested_behaviors[row.get('semi_requested_behavior') or actual] += 1
        behavior_pools[actual][row.get('semi_behavior_pool') or row.get('semi_pool') or 'unavailable'] += 1
        for source in ([row.get('semi_global_source')] + (row.get('semi_local_sources') or [])
                + ([row.get('semi_addition_source')] if row.get('semi_addition_source') else [])):
            if source:
                source_pools_by_behavior[actual][source.get('pool', 'unavailable')] += 1
    source_pool_counts = dict(collections.Counter(
        source.get('pool', 'unavailable') for row in semi_rows
        for source in ([row.get('semi_global_source')] + (row.get('semi_local_sources') or [])
            + ([row.get('semi_addition_source')] if row.get('semi_addition_source') else [])) if source))
    base.dump(output / 'semi_edit_source_summary.json', dict(
        behavior_pool_counts={k: dict(v) for k, v in behavior_pools.items()},
        source_pools_by_actual_behavior={k: dict(v) for k, v in source_pools_by_behavior.items()},
        requested_behavior_counts=dict(requested_behaviors),
        actual_behavior_counts=dict(collections.Counter(row.get('semi_actual_behavior') or 'unavailable' for row in semi_rows)),
        source_pool_counts=source_pool_counts,
        training_purpose_counts=dict(collections.Counter(
            source.get('purpose', 'unavailable') for row in semi_rows
            for source in ([row.get('semi_global_source')] + (row.get('semi_local_sources') or [])
                + ([row.get('semi_addition_source')] if row.get('semi_addition_source') else [])) if source)),
        fallback_reasons=dict(collections.Counter(row.get('semi_edit_fallback_reason') for row in semi_rows
            if row.get('semi_edit_fallback_reason'))),
        interpretation='Training source records are normal_candidate only. Addition examples are weakly supported and excluded when their building is held out.'))
    calibration_success = [r for r in calibration if r.get('generation_status') in SUCCESS]
    scored_calibration = [r for r in calibration_success if r.get('WQ_absolute_error') is not None]
    attempted_scored_calibration = [r for r in calibration if r.get('WQ_absolute_error') is not None]
    geometry_success = [r for r in calibration_success if r.get('geometry_status')]
    copy_success = [r for r in calibration_success if r.get('model_copy') is not None]
    summary['personal_semi_calibration'] = dict(
        rows=len(calibration), successful=len(calibration_success), scored=len(scored_calibration),
        buildings=len({r['building_id'] for r in calibration}),
        mean_absolute_WQ_error=(float(np.mean([r['WQ_absolute_error'] for r in scored_calibration])) if scored_calibration else None),
        geometry_issue_rate=(sum(r['geometry_status'] != 'basic_checks_passed_not_certified' for r in geometry_success) /
            len(geometry_success) if geometry_success else None),
        model_copy_rate=(sum(bool(r['model_copy']) for r in copy_success) / len(copy_success) if copy_success else None),
        attempted_mean_absolute_WQ_error=(float(np.mean([r['WQ_absolute_error'] for r in attempted_scored_calibration]))
            if attempted_scored_calibration else None),
        attempted_model_copy_rate=(sum(bool(r.get('model_copy')) for r in calibration if r.get('model_copy') is not None) /
            sum(r.get('model_copy') is not None for r in calibration) if any(r.get('model_copy') is not None for r in calibration) else None),
        quality_acceptance=False, scope='exploratory same-person, same-image, same-reference panel; 3-building support only')
    base.dump(output / 'summary.json', summary)
    base.dump(output / 'source_integrity.json', unchanged)
    for name in ('private_worker_ledger.csv', 'source_manifest.json'):
        os.chmod(output / name, 0o600)
    return summary
