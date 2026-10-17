"""Hierarchical empirical transfer using training-building personnel profiles."""
from __future__ import annotations

import collections
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from tools.thesis_main.analysis import simulate_annotators as base
from tools.thesis_main.analysis.simulator_personality_inputs import fit_profiles, QUALITY_VERSION


def fit_personality(records, models, heldout, *, profiles=None):
    training = [r for r in records if r['building_id'] != heldout]
    learned = base.fit(training, models)
    profiles = fit_profiles(records, heldout) if profiles is None else profiles
    donors = []
    for record in training:
        bank = models.get(record['image_id'], {})
        if not all(f in bank for f in base.FAMILIES):
            continue
        costs = np.array([base.distance(record['points'], bank[f]['points']) for f in base.FAMILIES])
        weights = np.exp(-(costs - costs.min()) / 5.)
        weights /= weights.sum()
        for family, weight in zip(base.FAMILIES, weights):
            proposal = np.asarray(bank[family]['points'], float).reshape(-1, 2, 2)
            answer = np.asarray(record['points'], float).reshape(-1, 2, 2)
            # Point identities within each source answer are already established by
            # the current loader. This assignment is only model-to-answer transfer.
            pr = base.rays(proposal.reshape(-1, 2)).reshape(-1, 2, 3)
            ar = base.rays(answer.reshape(-1, 2)).reshape(-1, 2, 3)
            cost = np.arccos(np.clip(np.einsum('ikd,jkd->ijk', pr, ar), -1, 1)).mean(axis=-1)
            ii, jj = linear_sum_assignment(cost)
            delta = answer[jj] - proposal[ii]
            delta[:, :, 0] = (delta[:, :, 0] + 512) % 1024 - 512
            donors.append(dict(worker_id=record['worker_id'], annotation_id=record['annotation_id'],
                record_id=record['record_id'], image_id=record['image_id'], building_id=record['building_id'],
                family=family, base_pairs=len(proposal), answer_pairs=len(answer),
                count_offset=len(answer) - len(proposal), kept_pairs=ii.tolist(),
                matched_answer_pairs=jj.tolist(), delta=delta.tolist(), weight=float(weight),
                active_time_seconds=record['active_time_seconds']))
    caps = {}
    for worker in {d['worker_id'] for d in donors}:
        values = np.concatenate([np.abs(np.asarray(d['delta']).reshape(-1, 2)) for d in donors if d['worker_id'] == worker])
        caps[worker] = np.quantile(values, .95, axis=0).tolist()
    buckets = collections.defaultdict(list)
    for donor in donors:
        buckets[(donor['family'], donor['base_pairs'])].append(donor)
    return dict(learned=learned, profiles=profiles, donors=donors, buckets=dict(buckets), caps=caps,
                records=training, heldout=heldout,
                training_buildings=sorted({r['building_id'] for r in training}),
                training_annotation_ids=sorted(r['annotation_id'] for r in training))


def mixture_pools(pool, worker, profiles, shrinkage=8.):
    personal = [d for d in pool if d['worker_id'] == worker]
    profile = profiles.get(worker, {})
    prototype = profile.get('prototype')
    peers = [d for d in pool if d['worker_id'] != worker
             and profile.get('quality') in ('higher', 'lower')
             and profiles.get(d['worker_id'], {}).get('prototype') == prototype]
    # Count unique responses, not duplicated model representations.
    n = len({d['annotation_id'] for d in personal})
    m = len({d['annotation_id'] for d in peers})
    wp = n / (n + shrinkage) if n else 0.
    wg = (1 - wp) * m / (m + shrinkage) if m else 0.
    weights = dict(personal=wp, prototype=wg, pooled=1 - wp - wg)
    if not pool:
        return dict(personal=[], prototype=[], pooled=[]), dict(personal=0., prototype=0., pooled=0.)
    return dict(personal=personal, prototype=peers, pooled=pool), weights


def axis_effect(profiles, worker, axis):
    value = profiles.get(worker, {}).get('axes', {}).get(axis, {}).get('effect')
    return value if value is not None and math.isfinite(value) else None


def choose_donor(pool, worker, fitted, seed):
    pools, weights = mixture_pools(pool, worker, fitted['profiles'])
    if not pool:
        return None, None, weights
    rng = np.random.default_rng(seed)
    levels = list(weights)
    level = levels[int(rng.choice(len(levels), p=list(weights.values())))]
    candidates = pools[level]
    scores = [axis_effect(fitted['profiles'], w, 'quality') for w in fitted['profiles']]
    scores = [v for v in scores if v is not None]
    spread = max(1., float(np.std(scores))) if scores else 1.
    target = axis_effect(fitted['profiles'], worker, 'quality')
    probabilities = []
    for donor in candidates:
        source = axis_effect(fitted['profiles'], donor['worker_id'], 'quality')
        similarity = 1 / (1 + ((source - target) / spread)**2) if source is not None and target is not None else 1.
        probabilities.append(donor.get('weight', 1.) * similarity)
    probabilities = np.array(probabilities); probabilities /= probabilities.sum()
    return candidates[int(rng.choice(len(candidates), p=probabilities))], level, weights


def transfer(base_points, donor, cap):
    base_points = np.asarray(base_points, float).reshape(-1, 2, 2)
    if donor['count_offset'] > 0:
        return base_points.reshape(-1, 2).copy(), 'unsupported_addition'
    keep = donor['kept_pairs']
    if len(keep) < 3:
        return base_points.reshape(-1, 2).copy(), 'too_few_pairs'
    candidate = base_points[keep] + np.clip(np.asarray(donor['delta']), -np.asarray(cap), np.asarray(cap))
    candidate[:, :, 0] %= 1024
    # Bounds and geometric deviations remain visible in diagnostics. Do not
    # replace problematic output with the original model to inflate validity.
    flat = candidate.reshape(-1, 2)
    return flat, 'transferred' if base.parsed(flat) else 'numeric_invalid_retained'


def sample_time(fitted, worker, donor, seed):
    pool = [dict(worker_id=r['worker_id'], annotation_id=r['annotation_id'],
                 building_id=r['building_id'], active_time_seconds=r['active_time_seconds'], weight=1.)
            for r in fitted['records'] if r['active_time_seconds'] is not None]
    if donor is not None and donor['active_time_seconds'] is not None:
        picked, level = donor, 'geometry_donor_joint_sample'
    else:
        picked, level, _ = choose_donor(pool, worker, fitted, seed)
    if picked is None:
        return dict(active_time_seconds=None, timing_status='not_simulated', time_fallback_reason='no_training_time')
    target = axis_effect(fitted['profiles'], worker, 'time')
    source = axis_effect(fitted['profiles'], picked['worker_id'], 'time')
    shift = target - source if target is not None and source is not None else 0.
    seconds = math.expm1(math.log1p(picked['active_time_seconds']) + shift)
    if not math.isfinite(seconds) or seconds <= 0:
        return dict(active_time_seconds=None, timing_status='not_simulated', time_fallback_reason='invalid_effect_shift')
    return dict(active_time_seconds=seconds, lead_time_seconds=None, timing_status='simulated_empirical_task_effect',
                time_donor_annotation_id=picked['annotation_id'], time_donor_worker_id=picked['worker_id'],
                time_donor_building_id=picked['building_id'], time_pool=level, time_log_effect_shift=shift)


def generate(bank, fitted, workers, seed, image_id, condition='manual', semi_mode='generative'):
    if semi_mode not in ('generative', 'strict'):
        raise ValueError('unknown_semi_mode')
    if condition not in ('manual', 'semi'):
        raise ValueError('unknown_simulation_condition')
    if condition == 'semi' and 'channels' not in fitted:
        raise ValueError('semi_requires_current_channel_evidence')
    rows = []
    for index, worker in enumerate(workers):
        learned = fitted['learned']
        rng = np.random.default_rng(base.seed_for(seed, worker, 'family'))
        family = base.FAMILIES[int(rng.choice(3, p=learned['profiles'].get(worker, learned['pooled'])))]
        points = bank[family]['points']
        pool = fitted['buckets'].get((family, len(points) // 2), [])
        donor, level, weights = choose_donor(pool, worker, fitted, base.seed_for(seed, worker, 'donor'))
        status = 'no_compatible_training_donor'
        candidate = np.asarray(points, float)
        if donor and condition == 'manual':
            candidate, status = transfer(points, donor, fitted['caps'][donor['worker_id']])
        semi_donor = None
        generative_info = None
        if condition == 'semi':
            from .personality_response_channels import semi_transfer
            pool = [d for d in fitted['channels']['semi'] if len(d['initial_points']) == len(points)]
            semi_donor, level, weights = choose_donor(pool, worker, fitted, base.seed_for(seed, worker, 'semi_donor'))
            status = 'no_compatible_semi_donor'
            if semi_donor:
                transferred, status = semi_transfer(points, semi_donor)
                candidate = np.asarray(transferred)
            if semi_mode == 'generative':
                from .semi_edit_distribution import generate_edit
                transferred, generative_info = generate_edit(points, fitted, worker, seed)
                candidate = np.asarray(transferred)
                status = generative_info['semi_status']
                anchor = generative_info['semi_global_source']
                semi_donor = dict(anchor, behavior=generative_info['semi_actual_behavior']) if anchor else None
                level = anchor['pool'] if anchor else None
                weights = generative_info.get('semi_move_mixture_weights', generative_info['semi_mixture_weights'])
            donor = None
        profile = fitted['profiles'].get(worker, dict(quality='uncertain', speed='uncertain', quality_reason='profile_missing', axes={}))
        quality_name = dict(higher='来源人员质量较高', lower='来源人员质量较低', uncertain='来源人员质量待定')[profile['quality']]
        speed_name = dict(faster='较快', slower='较慢', uncertain='速度待定')[profile['speed']]
        row = dict(simulation_id=f'{image_id}:hierarchical:{seed}:{index}', image_id=image_id,
            synthetic=True, review_required=True, method='worker', variant='hierarchical', condition='manual',
            simulated_worker_id='sim_' + worker, source_worker_profile_id=worker,
            name=f'{quality_name} / {speed_name} / W{int(worker):03d} / 分层采样',
            source_profile=profile, source_quality=profile['quality'], source_speed=profile['speed'],
            quality_version=QUALITY_VERSION, profile_found=worker in fitted['profiles'],
            profile_fallback_reason=profile.get('quality_reason'),
            model_family=family, model_layout_id=bank[family]['layout_id'], points=candidate.tolist(),
            geometry_status=base.geometry_status(candidate), generation_status=status,
            residual_source=level or 'no_compatible_training_donor', mixture_weights=weights,
            residual_applied=status in ('transferred', 'numeric_invalid_retained'),
            residual_fallback_reason=None if status == 'transferred' else status,
            residual_donor_annotation_id=donor['annotation_id'] if donor else None,
            residual_donor_worker_id=donor['worker_id'] if donor else None,
            residual_donor_building_id=donor['building_id'] if donor else None,
            residual_donor_image_id=donor['image_id'] if donor else None,
            source_count_offset=donor['count_offset'] if donor else None,
            source_deleted_pair_indices=sorted(set(range(donor['base_pairs'])) - set(donor['kept_pairs'])) if donor else [],
            source_delta_cap_px=fitted['caps'][donor['worker_id']] if donor else None,
            model_copy=bool(np.array_equal(candidate, points)),
            held_out_building=fitted['heldout'], ring_confirmed=False, order_status='model_ring_with_empirical_edits',
            scope_status='not_simulated', scope_fallback_reason='manual_personality_trial_only',
            semi_status='not_applicable')
        row.update(sample_time(fitted, worker, donor, base.seed_for(seed, worker, 'time')))
        if condition == 'semi':
            from .personality_response_channels import sample_semi_time
            row.update(condition='semi', simulation_id=row['simulation_id'] + ':semi',
                initial_points=points, final_points=candidate.tolist(), semi_status=status,
                semi_behavior=semi_donor['behavior'] if semi_donor else None,
                semi_purpose='normal_candidate', semi_pool=level,
                semi_donor_annotation_id=semi_donor['annotation_id'] if semi_donor else None,
                semi_donor_worker_id=semi_donor['worker_id'] if semi_donor else None,
                semi_donor_building_id=semi_donor['building_id'] if semi_donor else None,
                semi_donor_image_id=semi_donor['image_id'] if semi_donor else None,
                initialization_trace=dict(model_layout_id=row['model_layout_id'], model_family=family,
                    source='frozen_model_bank', manual_residual_applied=False),
                residual_applied=status in ('empirical_edit', 'generated_move', 'generated_addition', 'generated_move_fallback'), residual_source='semi_' + (level or 'missing'),
                residual_fallback_reason=None if status in ('empirical_copy', 'empirical_edit', 'generated_move', 'generated_addition') else status,
                name=row['name'] + ' / Semi')
            if generative_info:
                row.update(generative_info)
                row['residual_fallback_reason'] = row['semi_edit_fallback_reason']
            row.update(sample_semi_time(row, fitted, seed))
        if 'channels' in fitted:
            from .personality_response_channels import sample_scope, sample_lead_time
            row.update(sample_scope(row, fitted, seed))
            row.update(sample_lead_time(row, fitted, seed))
        rows.append(row)
    return rows
