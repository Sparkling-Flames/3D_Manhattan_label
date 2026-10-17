"""Gallery-only Manual completion with empirical tiers and no GT scoring."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

import numpy as np

from . import simulate_annotators as base
from .difficulty_wild_gallery import (BASIS, VERSION, DEFAULT_OUTPUT, GALLERY, load_gallery,
                                     source_hashes, image_calibration, disagreement)
from .difficulty_wild_sampler import VALID, ERROR_TYPES, wild_count, wild_edit
from .personality_annotator_sampler import fit_personality, choose_donor
from .simulate_annotators_opt import apply_residual
from .export_synthetic_label_studio import export_samples

GENERATOR = 'gallery_manual_35_round2_v1'


def fit_fold(sources, building):
    training = [r for r in sources['usable'] if r['building_id'] != building]
    if not training:
        raise ValueError('no_cross_building_donors')
    profiles = {w: dict(worker_id=w, quality='uncertain', speed='uncertain', axes={},
        prototype='gallery_unscored', quality_reason='no_gt_reference', quality_version=None,
        training_buildings=sorted({r['building_id'] for r in training if r['worker_id'] == w}))
        for w in sorted({r['worker_id'] for r in training}, key=int)}
    fitted = fit_personality(training, sources['models'], building, profiles=profiles)
    by_id = {r['annotation_id']: r for r in training}
    for donor in fitted['donors']:
        r = by_id[donor['annotation_id']]
        donor.update(lead_time_seconds=r['lead_time_seconds'], source_condition=r['source_condition'],
                     submitted_at=r['submitted_at'])
    fitted['times'] = [r for r in training if r['lead_time_seconds'] is not None]
    if not fitted['donors'] or not fitted['times']:
        raise ValueError('fold_evidence_missing')
    return fitted


def synthetic_id(image_index, slot):
    if image_index < 0 or not 0 <= slot < 35:
        raise ValueError('invalid_synthetic_slot')
    return f'S_MANUAL_{200000 + image_index*35 + slot:06d}'


def make_row(target, bank, fitted, calibration, seed, slot, index, nonce=0):
    iid = target['image_id']
    row_seed = base.seed_for(seed, GENERATOR, iid, slot, nonce)
    rng = np.random.default_rng(row_seed)
    worker = str(rng.choice(sorted(fitted['profiles'], key=int)))
    affinities = fitted['learned']['profiles'].get(worker, fitted['learned']['pooled'])
    families = [f for f in base.FAMILIES if base.geometry_status(bank[f]['points']) == VALID]
    if not families:
        raise ValueError('no_valid_model_family')
    weights = np.asarray([affinities[base.FAMILIES.index(f)] for f in families])
    weights /= weights.sum()
    family = str(rng.choice(families, p=weights))
    model = np.asarray(bank[family]['points'], float)
    k = target['wild_budget_k']; is_wild = slot < k
    local = calibration['families'][family]
    pool = [d for d in fitted['donors'] if d['family'] == family]
    compatible = [d for d in pool if d['base_pairs'] == len(model)//2 and (is_wild or d['count_offset'] == 0)]
    if compatible:
        pool = compatible
    if not pool:
        raise ValueError('no_family_donor_pool')
    failures = []
    for attempt in range(96):
        donor, level, mixture = choose_donor(pool, worker, fitted, base.seed_for(row_seed, 'donor', attempt))
        delta = np.asarray(donor['delta'], float)
        delta[:, :, 0] = delta[:, :, 0].mean(axis=1, keepdims=True)
        amplitude = float(np.sqrt(np.mean(delta**2)))
        if amplitude <= 0:
            failures.append('zero_donor_residual'); continue
        bounds = local['wild_amplitude'] if is_wild else local['normal_amplitude']
        sampled_amplitude = float(rng.uniform(*bounds))
        gain = sampled_amplitude / amplitude
        try:
            if is_wild:
                severity = dict(delta=delta.tolist(), cap=local['cap'], scale=gain,
                    deletion_counts=local['deletion_counts'], missing_frequency=local['missing_frequency'])
                points, edit = wild_edit(model, model, rng, severity)
            else:
                pair_indices = (np.arange(len(delta)) if len(delta) == len(model)//2 else
                                rng.integers(len(delta), size=len(model)//2))
                scale = gain * .5**(attempt//16)
                points = apply_residual(model, {'delta': delta[pair_indices]}, np.asarray(local['cap']), scale, rng)
                if points is None or np.array_equal(points, model):
                    raise ValueError('normal_edit_invalid_or_model_copy')
                edit = dict(wild_error_types=[], residual_scale=scale,
                    donor_pair_indices=pair_indices.tolist(), kept_pair_indices=list(range(len(model)//2)))
            break
        except ValueError as exc:
            failures.append(str(exc))
    else:
        raise ValueError('gallery_generation_exhausted')
    time_donor = next((r for r in fitted['times'] if r['annotation_id'] == donor['annotation_id']), None)
    if time_donor is None:
        personal = [r for r in fitted['times'] if r['worker_id'] == worker] or fitted['times']
        time_donor = personal[int(rng.integers(len(personal)))]
    votes = target['scope_votes']
    probability = votes['in_scope'] / sum(votes.values())
    response = 'in_scope' if rng.random() < probability else 'oos'
    identity = synthetic_id(index, slot)
    return dict(simulation_id=f'{iid}:{GENERATOR}:{seed}:{slot}', image_id=iid,
        synthetic=True, condition='manual', simulated_worker_id=identity, export_worker_id=identity,
        source_worker_profile_id=worker, source_worker_namespace='gallery_project98',
        source_profile=fitted['profiles'][worker], source_quality='not_assessed_no_gt',
        source_condition=donor['source_condition'], source_submitted_at=donor['submitted_at'],
        generator_version=GENERATOR, seed=row_seed, method='worker', variant=GENERATOR,
        model_family=family, model_layout_id=bank[family]['layout_id'], model_copy=False,
        model_family_affinities={f: float(p) for f, p in zip(families, weights)},
        points=points.tolist(), final_points=points.tolist(), geometry_status=base.geometry_status(points),
        generation_status='empirical_wild' if is_wild else 'empirical_normal',
        generation_attempts=attempt+1, generation_failures=failures, duplicate_geometry_retries=nonce,
        donor_pool='same_family_same_pair_count' if compatible else 'same_family_pair_resampling',
        residual_source=level, mixture_weights=mixture, residual_applied=True,
        residual_donor_annotation_id=donor['annotation_id'], residual_donor_worker_id=donor['worker_id'],
        residual_donor_building_id=donor['building_id'], residual_donor_image_id=donor['image_id'],
        held_out_building=fitted['heldout'], source_count_offset=donor['count_offset'],
        calibration_image_id=iid, calibration_building_id=target['building_id'],
        calibration_usage='target_image_scalar_statistics_only', calibration_source='image_calibration.json',
        empirical_residual_amplitude=sampled_amplitude, amplitude_quantiles=[.75,.95] if is_wild else [.25,.50],
        source_delta_cap_px=local['cap'],
        active_time_seconds=None, timing_status='not_simulated_no_active_time_evidence',
        lead_time_seconds=time_donor['lead_time_seconds'], lead_time_status='empirical_gallery_lead_time',
        lead_time_is_active_time=False, lead_time_donor_annotation_id=time_donor['annotation_id'],
        lead_time_donor_worker_id=time_donor['worker_id'], lead_time_donor_building_id=time_donor['building_id'],
        lead_time_source_submitted_at=time_donor['submitted_at'], time_donor_annotation_id=None,
        time_donor_building_id=None, worker_scope_response=response, scope_status='sampled_response',
        scope_sampling_probabilities=dict(in_scope=probability, oos=1-probability),
        scope_votes=votes, scope_geometry_bound=False, scope_pool='target_image_aggregate_votes',
        scope_majority=calibration['scope_majority'], scope_oos_majority=calibration['scope_oos_majority'],
        scope_reference_status='no_gt_reference', gt_none=True, gt_error_excluded=False, pending_review=False,
        difficulty=target['difficulty'], difficulty_basis=BASIS, difficulty_version=VERSION,
        difficulty_source=str(GALLERY), disagreement_px=target['disagreement_px'],
        difficulty_thresholds=target['difficulty_thresholds'], wild=is_wild, wild_budget_k=k,
        need=target['need'], real_manual_n=target['real_manual_n'],
        real_count_basis='gallery_annCount_all_observed_conditions',
        evaluation=None, evaluation_status='no_gt_reference', evaluation_reason='no_gt_reference',
        semi_status='not_applicable', ring_confirmed=False, order_status='model_ring_with_empirical_edits',
        generation_parameters=dict(seed=seed, sample_seed=row_seed, mode='fill-144-gallery', generator_version=GENERATOR),
        source_hashes=dict(manifest='source_manifest.json'), **edit)


def pick_targets(targets, pilot):
    if not pilot:
        return targets
    ids = set()
    for label in ('简单', '中等', '困难'):
        ids.update(t['image_id'] for t in [t for t in targets if t['difficulty'] == label][:2])
    ids.update(t['image_id'] for t in targets if t['scope_votes']['out_of_scope'] >= t['scope_votes']['in_scope'])
    return [t for t in targets if t['image_id'] in ids]


def slim_target(t):
    return {k: v for k, v in t.items() if k != 'workers'}


def run(output=DEFAULT_OUTPUT, seed=20261017, pilot_only=False, preflight_only=False):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('output_directory_already_exists:' + str(output))
    sources = load_gallery()
    hashes = source_hashes(sources)
    output.mkdir(parents=True, exist_ok=False)
    code = [Path(__file__), Path(__file__).with_name('difficulty_wild_gallery.py'),
        Path(__file__).with_name('difficulty_wild_sampler.py'), Path(__file__).with_name('simulate_annotators.py'),
        Path(__file__).with_name('simulate_annotators_opt.py'), Path(__file__).with_name('personality_annotator_sampler.py'),
        Path(__file__).with_name('export_synthetic_label_studio.py')]
    base.dump(output/'source_manifest.json', dict(source_sha256=hashes, seed=seed,
        code_sha256={str(p.relative_to(base.ROOT)): base.digest(p) for p in code},
        mode='fill-144-gallery', generator_version=GENERATOR,
        difficulty_basis=BASIS, difficulty_version=VERSION, gt_reference=None,
        difficulty_distance='ordered_prefix_periodic_x_euclidean_mean_all_unordered_worker_pairs',
        ring_start_dependence=True, donor_policy='exclude_target_building_vectors_and_lead_times',
        target_access='disagreement_scalar_calibration_count_range_and_scope_statistics_only'))
    all_targets = [dict(t, wild_budget_k=wild_count(t['difficulty'], base.seed_for(seed,t['image_id'],'round2_budget'),t['need']))
                   for t in sources['targets']]
    base.dump(output/'full_target_manifest.json', [slim_target(t) for t in all_targets])
    thresholds = all_targets[0]['difficulty_thresholds']
    base.dump(output/'difficulty_thresholds.json', dict(thresholds=thresholds, quantile_method='linear',
        difficulty_basis=BASIS, population=144, sorted_image_ids=[t['image_id'] for t in all_targets],
        caveat='source_ring_start_and_unmatched_tail_affect_this_ordered_distance'))
    if preflight_only:
        base.dump(output/'PREFLIGHT.json', dict(target_images=144, requested=2740,
            real_annotations=sum(t['real_manual_n'] for t in all_targets),
            target_buildings=len({t['building_id'] for t in all_targets}),
            donor_buildings=len({r['building_id'] for r in sources['usable']}),
            donor_records=len(sources['usable']), model_coverage=144, panorama_coverage=144,
            thresholds=thresholds, difficulty_counts=dict(collections.Counter(t['difficulty'] for t in all_targets))))
        base.dump(output/'source_integrity.json', {p: base.digest(Path(p)) == h for p,h in hashes.items()})
        return
    targets = pick_targets(all_targets, pilot_only)
    base.dump(output/'target_manifest.json', [slim_target(t) for t in targets])
    calibration = {t['image_id']: image_calibration(t,sources['models'][t['image_id']]) for t in targets}
    base.dump(output/'image_calibration.json', calibration)
    base.write_csv(output/'donor_exclusions.csv', [dict(annotation_id=r['annotation_id'], image_id=r['image_id'],
        worker_id=r['worker_id'], building_id=r['building_id'], reason=r['geometry_status'])
        for r in sources['records'] if r['geometry_status'] != VALID])
    indices = {t['image_id']: j for j,t in enumerate(all_targets)}
    rows, failures = [], []
    for building in sorted({t['building_id'] for t in targets}):
        fitted = fit_fold(sources, building)
        if building in fitted['training_buildings']:
            raise ValueError('fold_building_leak')
        base.dump(output/f'fold_{building}.json', dict(held_out_building=building,
            training_buildings=fitted['training_buildings'], training_annotation_ids=fitted['training_annotation_ids'],
            profiles=fitted['profiles'], family_affinities=fitted['learned']['profiles'], pooled=fitted['learned']['pooled']))
        base.dump(output/f'donor_manifest_{building}.json', [dict(annotation_id=d['annotation_id'],
            worker_id=d['worker_id'], building_id=d['building_id'], image_id=d['image_id'], family=d['family'])
            for d in fitted['donors']])
        for target in [t for t in targets if t['building_id'] == building]:
            iid = target['image_id']; seen = set()
            real_points = {json.dumps(r['points'],separators=(',',':')) for r in target['workers']}
            for slot in range(target['need']):
                try:
                    for nonce in range(128):
                        row = make_row(target,sources['models'][iid],fitted,calibration[iid],seed,slot,indices[iid],nonce)
                        signature = json.dumps(row['points'],separators=(',',':'))
                        if signature not in seen and signature not in real_points:
                            seen.add(signature); break
                    else:
                        raise ValueError('unique_geometry_exhausted')
                    if row['export_worker_id'] in sources['first_ids']:
                        raise ValueError('round1_worker_id_collision')
                    if building in (row['residual_donor_building_id'],row['lead_time_donor_building_id']):
                        raise ValueError('target_building_donor_leak')
                    rows.append(row)
                except ValueError as exc:
                    failures.append(dict(image_id=iid,slot=slot,reason=str(exc)))
            print(target['image'], sum(r['image_id']==iid for r in rows), '/', target['need'], flush=True)
    rows.sort(key=lambda r:(r['image_id'],r['export_worker_id']))
    base.write_jsonl(output/'simulations.jsonl',rows)
    images = {t['image_id']: dict(image_url=t['image_url']) for t in targets}
    exported, export_summary = export_samples(rows, images, output)
    audits = []
    for t in targets:
        rs = [r for r in rows if r['image_id']==t['image_id']]
        errors = collections.Counter(k for r in rs for k in r['wild_error_types'])
        sd = disagreement([r['points'] for r in rs]) if len(rs)>1 else None
        audits.append(dict(image_id=t['image_id'],image=t['image'],difficulty=t['difficulty'],difficulty_basis=BASIS,
            disagreement_px=t['disagreement_px'],difficulty_thresholds=json.dumps(thresholds),
            real_n=t['real_manual_n'],need=t['need'],synthetic_n=len(rs),exported_n=sum(r['simulation_id'] in exported for r in rs),
            total_n=t['real_manual_n']+len(rs),wild_budget_k=t['wild_budget_k'],wild_n=sum(r['wild'] for r in rs),
            **{k: errors[k] for k in ERROR_TYPES},scope_votes=json.dumps(t['scope_votes'],sort_keys=True),
            scope_majority=calibration[t['image_id']]['scope_majority'],gt_none=True,
            synthetic_disagreement_px=sd,synthetic_to_real_ratio=sd/t['disagreement_px'] if sd is not None else None))
    base.write_csv(output/'difficulty_audit.csv',audits)
    base.write_csv(output/'generation_failures.csv',failures)
    integrity = {p:base.digest(Path(p))==h for p,h in hashes.items()}
    base.dump(output/'source_integrity.json',integrity)
    checks = dict(all_images_filled=all(a['total_n']==35 and a['exported_n']==a['need'] for a in audits),
        all_budgets_met=all(a['wild_n']==a['wild_budget_k'] for a in audits),
        geometry_issues=sum(base.geometry_status(r['points'])!=VALID for r in rows),
        within_image_duplicate_geometry_rows=sum(len(rs)-len({json.dumps(r['points']) for r in rs})
            for t in targets if (rs:=[r for r in rows if r['image_id']==t['image_id']])),
        unique_ids=len({r['export_worker_id'] for r in rows})==len(rows),
        round1_ids_disjoint=not ({r['export_worker_id'] for r in rows}&sources['first_ids']),
        donor_leaks=sum(r['held_out_building'] in (r['residual_donor_building_id'],r['lead_time_donor_building_id']) for r in rows),
        no_gt_evaluation=all(r['evaluation'] is None and r['evaluation_reason']=='no_gt_reference' for r in rows),
        all_sources_unchanged=all(integrity.values()), failures=len(failures), export=export_summary,
        protected_files=len(integrity), disagreement_audit=dict(status='diagnostic_only_no_match_claim',
            synthetic_mean_px=float(np.mean([a['synthetic_disagreement_px'] for a in audits if a['synthetic_disagreement_px'] is not None])),
            real_mean_px=float(np.mean([a['disagreement_px'] for a in audits])),
            ratio_quantiles=np.quantile([a['synthetic_to_real_ratio'] for a in audits if a['synthetic_to_real_ratio'] is not None],[0,.25,.5,.75,1]).tolist()),
        reproducibility='pending_independent_replay')
    passed = all(checks[k] for k in ('all_images_filled','all_budgets_met','unique_ids','round1_ids_disjoint','no_gt_evaluation','all_sources_unchanged'))
    passed &= not any(checks[k] for k in ('geometry_issues','within_image_duplicate_geometry_rows','donor_leaks','failures'))
    checks['functional_passed'] = bool(passed and export_summary['rejected']==0)
    base.dump(output/'VALIDATION.json',checks)
    summary = dict(mode='fill-144-gallery',generator_version=GENERATOR,seed=seed,synthetic=True,local_only=True,
        target_images=len(targets),requested=sum(t['need'] for t in targets),generated=len(rows),
        real_annotations=sum(t['real_manual_n'] for t in targets),wild=sum(r['wild'] for r in rows),normal=sum(not r['wild'] for r in rows),
        difficulty_basis=BASIS,difficulty_thresholds=thresholds,difficulty_counts=dict(collections.Counter(t['difficulty'] for t in targets)),
        gt_reference=None,evaluation_status='no_gt_reference',functional_passed=checks['functional_passed'],**export_summary)
    base.dump(output/'summary.json',summary)
    if not checks['functional_passed']:
        raise ValueError('round2_failed_see_VALIDATION')
    return summary


def verify_replay(first, second):
    first, second = Path(first), Path(second)
    names = sorted(p.name for p in first.iterdir() if p.is_file() and p.suffix in ('.json','.jsonl','.csv')
                   and p.name not in ('REPRODUCIBILITY.json','TEST_RESULTS.json','INDEPENDENT_AUDIT.json'))
    if set(names) != {p.name for p in second.iterdir() if p.is_file() and p.suffix in ('.json','.jsonl','.csv')
                      and p.name not in ('REPRODUCIBILITY.json','TEST_RESULTS.json','INDEPENDENT_AUDIT.json')}:
        raise ValueError('replay_file_set_mismatch')
    same = {n:base.digest(first/n)==base.digest(second/n) for n in names}
    if not all(same.values()):
        raise ValueError('replay_bytes_differ:' + ','.join(k for k,v in same.items() if not v))
    for directory in (first,second):
        path=directory/'VALIDATION.json';v=json.loads(path.read_text());v['reproducibility']='passed_independent_full_replay_byte_identical';base.dump(path,v)
    report=dict(passed=True,compared_files=len(names),same_bytes=same,
                sha256={n:base.digest(first/n) for n in names})
    for directory in (first,second):base.dump(directory/'REPRODUCIBILITY.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);p.add_argument('--seed',type=int,default=20261017)
    p.add_argument('--pilot-only',action='store_true');p.add_argument('--preflight-only',action='store_true')
    p.add_argument('--verify-replay',type=Path)
    a=p.parse_args()
    if a.verify_replay:verify_replay(a.output,a.verify_replay)
    else:run(a.output,a.seed,a.pilot_only,a.preflight_only)


if __name__=='__main__':main()
