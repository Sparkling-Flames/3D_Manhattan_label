"""Local-only, deterministic v1/v6 Manual population completion."""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
import numpy as np

from . import simulate_annotators as base
from .difficulty_wild_inputs import load_inputs, fit_profiles, DEFAULT_INPUT, DIFFICULTY, QUALITY_VERSION, read
from .difficulty_wild_sampler import VERSION, VALID, ERROR_TYPES, wild_count, wild_edit, calibrate, manual_counts
from .difficulty_wild_quality import Evaluator, ARCHIVE
from .personality_annotator_sampler import fit_personality, choose_donor
from .simulate_annotators_opt import apply_residual
from .export_synthetic_label_studio import export_samples
from .personality_response_channels import EVIDENCE


def targets(sources, seed, pilot_only=False):
    selected = sorted(sources['difficulty'])
    if pilot_only:
        chosen = set()
        for label in sorted({r['difficulty_class'] for r in sources['difficulty'].values()}):
            chosen.update([i for i in selected if sources['difficulty'][i]['difficulty_class'] == label][:2])
        # Explicit coverage of pending scope, supplemental bank, and bad GT.
        chosen.update(next(i for i in selected if sources['difficulty'][i]['image'] == code)
                      for code in ('wc2JMjhGNzB-22', 'uNb9QFRL6hY-18', '2t7WUuJeko7-07'))
        selected = sorted(chosen)
    result = []
    for iid in selected:
        d = sources['difficulty'][iid]; n = sources['counts'].get(iid, 0); need = max(0, 35 - n)
        result.append(dict(image_id=iid, image=d['image'], difficulty_class=d['difficulty_class'],
            real_manual_n=n, need=need, wild_budget_k=wild_count(d['difficulty_class'], base.seed_for(seed, iid, 'budget'), need),
            building_id=iid.split('_')[0], available_model_families=sorted(sources['models'][iid])))
    return result


def protected_hashes(sources):
    paths = [sources['directory'] / p for p in sources['manifest']['files']]
    paths += [sources['directory'] / 'frozen_manifest.json', ARCHIVE, EVIDENCE / 'record_evidence.csv',
              base.INPUT / 'models/layouts.jsonl', base.INPUT / 'images.csv',
              base.ROOT / 'analysis_results/research_input_20260929/preprocessed_source.json']
    paths += [base.ROOT / r['source'] for r in sources['supplements']]
    for directory in ('export_label', 'import_json', 'active_logs'):
        paths.extend(p for p in (base.ROOT / directory).rglob('*') if p.is_file())
    return {str(p): base.digest(p) for p in sorted(set(paths))}


def fit_fold(sources, building):
    profiles = fit_profiles(sources['records'], building)
    fitted = fit_personality(sources['records'], sources['models'], building, profiles=profiles)
    by_quality = {q: [d for d in fitted['donors'] if profiles[d['worker_id']]['quality'] == q]
                  for q in ('higher', 'lower')}
    if not all(by_quality.values()):
        raise ValueError('missing_supported_quality_pool:' + building)
    fitted['quality_donors'] = by_quality
    fitted['calibration'] = {q: calibrate(ds) for q, ds in by_quality.items()}
    fitted['times'] = [r for r in sources['times'] if r['building_id'] != building]
    if not fitted['times']:
        raise ValueError('missing_training_time:' + building)
    return fitted


def sample_row(sources, target, fitted, seed, slot, image_index, draw_nonce=0):
    iid = target['image_id']; d = sources['difficulty'][iid]; is_wild = slot < target['wild_budget_k']
    quality = 'lower' if is_wild else 'higher'
    sample_seed = base.seed_for(seed, iid, 'manual', slot)
    if draw_nonce:
        sample_seed = base.seed_for(sample_seed, 'unique_geometry_retry', draw_nonce)
    rng = np.random.default_rng(sample_seed)
    bank = sources['models'][iid]
    families = [f for f in base.FAMILIES if f in bank and base.geometry_status(bank[f]['points']) == VALID]
    if not families:
        raise ValueError('no_geometrically_valid_model_proposal')
    pool = [r for r in fitted['quality_donors'][quality] if r['family'] in families]
    compatible = [r for r in pool if r['base_pairs'] == len(bank[r['family']]['points']) // 2
                  and (is_wild or r['count_offset'] == 0)]
    if compatible:
        pool = compatible
    if not pool:
        raise ValueError('no_matching_family_quality_donor')
    worker = str(rng.choice(sorted({r['worker_id'] for r in pool}, key=int)))
    failures = []
    for attempt in range(96):
        donor, level, mixture = choose_donor(pool, worker, fitted, base.seed_for(sample_seed, attempt, 'geometry'))
        family = donor['family']; model = np.asarray(bank[family]['points'], float)
        severity = dict(fitted['calibration'][quality], delta=donor['delta'])
        try:
            if is_wild:
                points, edit = wild_edit(model, model, rng, severity)
            else:
                # High-quality templates retain the model ring and use observed
                # per-pair residuals; no target-image score guides acceptance.
                delta = np.asarray(donor['delta'], float)
                # Preserve the donor's joint layout residual whenever sizes match.
                sampled = np.arange(len(delta)) if len(delta) == len(model)//2 else rng.integers(len(delta), size=len(model)//2)
                delta = delta[sampled].copy()
                delta[:, :, 0] = delta[:, :, 0].mean(axis=1, keepdims=True)
                amplitude = float(np.sqrt(np.mean(delta**2)))
                if amplitude <= 0:
                    raise ValueError('normal_zero_empirical_residual')
                # Interpolate only inside the observed higher-quality amplitude IQR.
                sampled_amplitude = float(rng.uniform(*severity['amplitude_iqr']))
                scale = sampled_amplitude / amplitude * .5 ** (attempt // 16)
                points = apply_residual(model, {'delta': delta}, np.asarray(severity['cap']), scale, rng)
                if points is None or np.array_equal(points, model):
                    raise ValueError('normal_residual_invalid_or_unchanged')
                edit = dict(wild_error_types=[], kept_pair_indices=list(range(len(model)//2)),
                            residual_scale=scale, residual_sampled_donor_pair_indices=sampled.tolist(),
                            empirical_residual_amplitude=sampled_amplitude)
            break
        except ValueError as exc:
            failures.append(str(exc))
    else:
        raise ValueError('generation_exhausted:' + ','.join(sorted(set(failures))))
    time_pool = [r for r in fitted['times'] if r['worker_id'] == worker] or fitted['times']
    time_donor = next((r for r in time_pool if r['annotation_id'] == donor['annotation_id']), None)
    if time_donor is None:
        time_donor = time_pool[int(rng.integers(len(time_pool)))]
    local_scope = [r for r in sources['scope'] if r['image_id'] == iid]
    scope_pool = local_scope or [r for r in sources['scope'] if r['building_id'] != target['building_id']]
    if not scope_pool:
        raise ValueError('no_scope_evidence')
    scope_donor = scope_pool[int(rng.integers(len(scope_pool)))]
    sid = f'{iid}:{VERSION}:{seed}:{slot}'
    sw = f'S_MANUAL_{100000 + image_index * 35 + slot:06d}'
    pending = sources['pending'].get(d['image'])
    status = 'gt_error_excluded' if d['gt_error_excluded'] else 'confirmed_full' if d['reference_full_available'] else 'confirmed_floor_top_pending'
    return dict(simulation_id=sid, simulated_worker_id=sw, export_worker_id=sw, image_id=iid,
        synthetic=True, condition='manual', seed=sample_seed, generator_version=VERSION,
        method='worker', variant=VERSION, name=sw + (' / wild' if is_wild else ' / higher'),
        source_worker_profile_id=worker, source_profile=fitted['profiles'][worker], source_quality=quality,
        source_speed=fitted['profiles'][worker]['speed'], quality_version=QUALITY_VERSION,
        quality_sensitivity_version='B8L2-D10-20261016',
        model_family=family, model_layout_id=bank[family]['layout_id'], model_copy=False,
        model_source=bank[family].get('source', 'analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl'),
        points=points.tolist(), final_points=points.tolist(), geometry_status=base.geometry_status(points),
        generation_status='empirical_wild' if is_wild else 'empirical_higher',
        generation_attempts=attempt + 1, generation_failures=failures, residual_applied=True,
        duplicate_geometry_retries=draw_nonce,
        residual_source=level, mixture_weights=mixture, residual_donor_annotation_id=donor['annotation_id'],
        residual_donor_worker_id=donor['worker_id'], residual_donor_building_id=donor['building_id'],
        residual_donor_image_id=donor['image_id'], source_count_offset=donor['count_offset'],
        source_delta_cap_px=severity['cap'], held_out_building=fitted['heldout'],
        active_time_seconds=time_donor['active_time_seconds'], lead_time_seconds=time_donor['lead_time_seconds'],
        timing_status='empirical_task_worker_time', lead_time_status='empirical_joint_task_duration',
        lead_time_is_active_time=time_donor['lead_time_is_active_time'],
        time_donor_annotation_id=time_donor['annotation_id'], time_donor_worker_id=time_donor['worker_id'],
        time_donor_building_id=time_donor['building_id'], lead_time_donor_annotation_id=time_donor['annotation_id'],
        lead_time_donor_building_id=time_donor['building_id'],
        worker_scope_response=scope_donor['worker_scope'], scope_status='sampled_response',
        scope_pool='image_response_distribution' if local_scope else 'training_response_prior',
        scope_donor_annotation_id=scope_donor['object_id'], scope_donor_building_id=scope_donor['building_id'],
        scope_geometry_bound=False, semi_status='not_applicable',
        difficulty=d['difficulty_class'], difficulty_version='v6', difficulty_source=DIFFICULTY + '/image_inventory.csv',
        difficulty_snapshot_version=d['difficulty_version'], difficulty_target_id=d['difficulty_target_id'],
        wild=is_wild, wild_budget_k=target['wild_budget_k'], need=target['need'], real_manual_n=target['real_manual_n'],
        gt_error_excluded=d['gt_error_excluded'], pending_review=d['difficulty_class']=='待复核',
        scope_reference_status=status, scope_pending_category=pending['category'] if pending else None,
        scope_issue_flag=bool(pending and pending['category'] != '仅数值/存储误差候选'),
        ring_confirmed=False, order_status='model_ring_empirical_edits',
        generation_parameters=dict(seed=seed, sample_seed=sample_seed, mode='fill-to-35-wild',
            residual_quantile=severity['quantile'], generator_version=VERSION),
        source_hashes=dict(manifest='source_manifest.json', commit=sources['manifest']['commit']), **edit)


def distribution(values):
    values = [v for v in values if v is not None]
    return dict(n=len(values), mean=float(np.mean(values)) if values else None,
                quantiles=np.quantile(values, [0,.1,.25,.5,.75,.9,1]).tolist() if values else None)


def run(output, seed=20261017, pilot_only=False, inputs=DEFAULT_INPUT):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    sources = load_inputs(inputs); hashes = protected_hashes(sources)
    panel = targets(sources, seed, pilot_only)
    base.write_csv(output/'target_manifest.csv', panel)
    from .simulator_personality_inputs import load_current
    old = load_current()
    old_inventory = manual_counts([r for r in old['objects'].values() if r['object_kind'] == 'annotation'])
    old_eligible = collections.defaultdict(set)
    for r in old['records']: old_eligible[r['image_id']].add(r['worker_id'])
    differences = [dict(image_id=i, image=d['image'], real_manual_n=sources['counts'].get(i,0),
        old_inventory_n=old_inventory.get(i,0), old_training_n=len(old_eligible[i]),
        inventory_delta=sources['counts'].get(i,0)-old_inventory.get(i,0)) for i,d in sources['difficulty'].items()]
    extra = sorted({r['image_id'] for r in sources['shared']} - set(sources['difficulty']))
    base.write_csv(output/'real_manual_count_audit.csv', differences)
    base.dump(output/'difficulty_unassigned.json', [dict(image_id=i, image=next(r['image_code'] for r in sources['shared'] if r['image_id']==i),
        status='difficulty_unassigned_v6', real_manual_n=sources['counts'].get(i,0)) for i in extra])
    base.dump(output/'supplemental_model_index.json', sources['supplements'])
    code = [Path(__file__), Path(__file__).with_name('difficulty_wild_inputs.py'), Path(__file__).with_name('difficulty_wild_sampler.py'),
            Path(__file__).with_name('difficulty_wild_quality.py'), Path(__file__).with_name('personality_annotator_sampler.py'),
            Path(__file__).with_name('export_synthetic_label_studio.py'), Path(__file__).with_name('simulate_annotators.py'),
            Path(__file__).with_name('simulate_annotators_opt.py')]
    base.dump(output/'source_manifest.json', dict(commit=sources['manifest']['commit'], input_sha256=hashes,
        code_sha256={str(p.relative_to(base.ROOT)):base.digest(p) for p in code}, seed=seed,
        real_count_rule='all_v1_canonical_manual_distinct_workers', training_rule='approved_quality_panel_building_holdout',
        synthetic=True, local_only=True, versions=dict(difficulty='v6', data='v1', quality=QUALITY_VERSION)))
    samples, failed, audit, real_quality = [], [], [], []
    evaluator = Evaluator(sources); parity = evaluator.parity()
    indices = {iid:j for j,iid in enumerate(sorted(sources['difficulty']))}
    try:
        for building in sorted({t['building_id'] for t in panel}):
            print('fit', building, flush=True)
            fitted = fit_fold(sources, building)
            base.dump(output/f'fold_{building}.json', dict(profiles=fitted['profiles'], held_out_building=building,
                training_buildings=fitted['training_buildings'], training_annotation_ids=fitted['training_annotation_ids'],
                calibration=fitted['calibration']))
            for r in sources['records']:
                if r['building_id'] == building and fitted['profiles'].get(r['worker_id'],{}).get('quality') == 'lower':
                    real_quality.append(dict(object_id=r['annotation_id'], building_id=building, B8L2=r['B8L2'], D10=r['D10']))
            for target in [t for t in panel if t['building_id'] == building]:
                iid=target['image_id']; group=[]; seen_geometry=set()
                for slot in range(target['need']):
                    try:
                        for nonce in range(128):
                            row = sample_row(sources,target,fitted,seed,slot,indices[iid],nonce)
                            fingerprint=json.dumps(row['points'],separators=(',',':'))
                            if fingerprint not in seen_geometry:
                                seen_geometry.add(fingerprint)
                                break
                        else:
                            raise ValueError('unique_geometry_retries_exhausted')
                        for k in ('residual_donor_building_id','time_donor_building_id','lead_time_donor_building_id'):
                            if row[k] == building: raise ValueError('target_building_donor_leak:' + k)
                        row['evaluation'] = evaluator.evaluate(row['points'],sources['difficulty'][iid])
                        group.append(row)
                    except ValueError as exc:
                        failed.append(dict(image_id=iid, slot=slot, reason=str(exc)))
                samples.extend(group)
                counts=collections.Counter(t for r in group for t in r['wild_error_types'])
                audit.append(dict(**target, synthetic_n=len(group), wild_n=sum(r['wild'] for r in group),
                    normal_n=sum(not r['wild'] for r in group), total_n=target['real_manual_n']+len(group),
                    **{t:counts[t] for t in ERROR_TYPES}))
                print('generated',target['image'],len(group),'/',target['need'],flush=True)
    finally:
        evaluator.close()
    samples.sort(key=lambda r:(r['image_id'],r['simulation_id']))
    base.write_jsonl(output/'simulations.jsonl',samples)
    exported, export_summary=export_samples(samples,sources['images'],output)
    base.write_csv(output/'difficulty_wild_audit.csv',sorted(audit,key=lambda r:r['image_id']))
    base.write_csv(output/'generation_failures.csv',failed)
    base.write_csv(output/'real_lower_quality_reference.csv',real_quality)
    integrity={p:base.digest(Path(p))==h for p,h in hashes.items()}
    base.dump(output/'source_integrity.json',integrity)
    comparison={m:dict(wild=distribution([r['evaluation'][m] for r in samples if r['wild']]),
        normal=distribution([r['evaluation'][m] for r in samples if not r['wild']]),
        real_lower_heldout=distribution([r[m] for r in real_quality])) for m in ('B8L2','D10')}
    validation=dict(all_targets_filled=all(r['total_n']==max(35,r['real_manual_n']) for r in audit),
        budgets_passed=all(r['wild_n']==r['wild_budget_k'] for r in audit),
        geometry_issues=sum(r['geometry_status']!=VALID for r in samples),
        model_copies=sum(r['model_copy'] for r in samples), source_integrity=all(integrity.values()),
        within_image_duplicate_geometry_rows=sum(len(rs)-len({json.dumps(r['points']) for r in rs})
            for iid in {r['image_id'] for r in samples} if (rs:=[r for r in samples if r['image_id']==iid])),
        duplicate_geometry_resampled_rows=sum(r['duplicate_geometry_retries']>0 for r in samples),
        donor_building_isolation=all(r['residual_donor_building_id']!=r['held_out_building'] and r['time_donor_building_id']!=r['held_out_building'] for r in samples),
        unique_synthetic_ids=len({r['export_worker_id'] for r in samples})==len(samples),
        quality_formula_parity=parity, quality_comparison=comparison,
        quality_status='descriptive_diagnostic_no_quality_threshold_certification',
        evaluation_status=dict(collections.Counter(r['evaluation']['status'] for r in samples)),
        reproducibility='pending_independent_replay', export=export_summary,
        failures=len(failed), source_files_verified=len(integrity))
    validation['functional_passed']=all(validation[k] for k in ('all_targets_filled','budgets_passed','source_integrity','donor_building_isolation','unique_synthetic_ids')) and not (validation['geometry_issues'] or validation['failures'] or validation['within_image_duplicate_geometry_rows'] or export_summary['rejected'])
    base.dump(output/'VALIDATION.json',validation)
    summary=dict(mode='fill-to-35-wild',seed=seed,synthetic=True,local_only=True,target_images=len(panel),
        requested=sum(t['need'] for t in panel),generated=len(samples),wild=sum(r['wild'] for r in samples),
        normal=sum(not r['wild'] for r in samples),geometry_issue_rate=validation['geometry_issues']/max(1,len(samples)),
        difficulty_counts=dict(collections.Counter(t['difficulty_class'] for t in panel)),
        by_difficulty={label:dict(images=len(rows),wild_min=min(r['wild_n'] for r in rows),wild_max=max(r['wild_n'] for r in rows),wild_mean=float(np.mean([r['wild_n'] for r in rows])))
            for label in sorted({r['difficulty_class'] for r in audit})
            if (rows:=[r for r in audit if r['difficulty_class']==label])},
        source_files_unchanged=all(integrity.values()), functional_passed=validation['functional_passed'], **export_summary)
    base.dump(output/'summary.json',summary)
    if not validation['functional_passed']:
        raise ValueError('run_failed_see_VALIDATION_and_generation_failures')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--inputs',type=Path,default=DEFAULT_INPUT)
    p.add_argument('--seed',type=int,default=20261017);p.add_argument('--pilot-only',action='store_true')
    a=p.parse_args();run(a.output,a.seed,a.pilot_only,a.inputs)


if __name__=='__main__': main()
