"""Read-only evidence joins and isolated Semi, scope and elapsed-time channels."""
from __future__ import annotations

import collections
import copy
import json
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from . import simulate_annotators as base
from .simulator_personality_inputs import INVENTORY, JOINT, read_csv, truth, estimate_axis
from .simulate_annotators_opt import normalize_worker_id

EVIDENCE = base.ROOT / 'analysis_results/annotation_research_prework_20260905_v2/evidence'
SCOPE = base.ROOT / 'analysis_results/worker_four_block_exploration_20260910_v1/scope_responses.csv'
DISPUTES = base.ROOT / 'analysis_results/quality_scope_human_review_20261010/candidate_reconciliation_24.csv'
SCENES = base.ROOT / 'analysis_results/difficulty_scope_preferred_20261011/current_259.csv'
VERSION = 'personality_channels_v1'


def positive(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def normal_semi(gate):
    return (gate['role'] == 'semi_secondary_candidate' and gate['trap_status'] == 'confirmed_nontrap'
            and not gate['original_holdout'] and not gate['personnel_barriers'] and not gate['context_barriers'])


def validate_identity(row, inv):
    for key in ('image_id', 'building_id'):
        if row[key] != inv[key]:
            raise ValueError('channel_identity_mismatch:' + key)
    if normalize_worker_id(row['worker_id']) != normalize_worker_id(inv['worker_id']):
        raise ValueError('channel_identity_mismatch:worker')
    if row.get('condition', row.get('raw_condition')) != inv['condition']:
        raise ValueError('channel_identity_mismatch:condition')


def paired(points):
    """Only accept an existing adjacent column representation, never sort points."""
    if not base.parsed(points):
        return False
    a = np.asarray(points).reshape(-1, 2, 2)
    dx = (a[:, 0, 0] - a[:, 1, 0] + 512) % 1024 - 512
    return bool(np.all(np.abs(dx) < 1e-5) and np.all(a[:, 0, 1] < a[:, 1, 1]))


def semi_transfer(points, donor):
    initial, final = donor['initial_points'], donor['final_points']
    if not paired(initial) or not donor['final_pairing_verified']:
        return copy.deepcopy(points), 'ambiguous_donor_pairing'
    if len(initial) != len(points):
        return copy.deepcopy(points), 'initial_count_mismatch'
    if donor['behavior'] == 'copy':
        return copy.deepcopy(points), 'empirical_copy'
    if len(final) > len(initial):
        return copy.deepcopy(points), 'unsupported_addition'
    if len(final) < 6:
        return copy.deepcopy(points), 'too_few_pairs'
    ip = np.asarray(initial).reshape(-1, 2, 2)
    fp = np.asarray(final).reshape(-1, 2, 2)
    bp = np.asarray(points).reshape(-1, 2, 2)
    def assignment(a, b):
        ar = base.rays(a.reshape(-1, 2)).reshape(-1, 2, 3)
        br = base.rays(b.reshape(-1, 2)).reshape(-1, 2, 3)
        cost = np.arccos(np.clip(np.einsum('ikd,jkd->ijk', ar, br), -1, 1)).mean(-1)
        # A tied correspondence cannot support a reliable edit transfer.
        sorted_cost = np.sort(cost, axis=1)
        if cost.shape[1] > 1 and np.any(sorted_cost[:, 1] - sorted_cost[:, 0] < 1e-8):
            raise ValueError('ambiguous_transfer_correspondence')
        return linear_sum_assignment(cost)
    try:
        source, target = assignment(ip, bp)
        mapping = dict(zip(source.tolist(), target.tolist()))
        ii, jj = assignment(ip, fp)
    except ValueError as exc:
        return copy.deepcopy(points), str(exc)
    delta = fp[jj] - ip[ii]
    delta[:, :, 0] = (delta[:, :, 0] + 512) % 1024 - 512
    order = np.argsort([mapping[int(i)] for i in ii])
    candidate = bp[[mapping[int(i)] for i in ii]][order] + delta[order]
    candidate[:, :, 0] %= 1024
    flat = candidate.reshape(-1, 2).tolist()
    return flat, 'empirical_edit' if base.parsed(flat) else 'numeric_invalid_retained'


def load_channels(sources):
    inventory = read_csv(INVENTORY)
    inv_by = {r['historical_canonical_id']: r for r in inventory if r['historical_canonical_id']}
    if len(inv_by) != sum(bool(r['historical_canonical_id']) for r in inventory):
        raise ValueError('duplicate_channel_canonical_identity')
    gates = {r['record_id']: r for r in sources['gates']}
    objects = sources['objects']
    scenes = {r['image_id']: r['scene'] for r in read_csv(SCENES)}
    codes = {r['image_code']: r['image_id'] for r in inventory}
    disputes = {codes[r['image_code']]: dict(r) for r in read_csv(DISPUTES)}
    manual = {r['annotation_id']: r for r in sources['records']}
    quality_by_object = {r['object_id']: r for r in read_csv(JOINT)
        if r['condition'] == 'semi' and r['role'] == 'semi_secondary_candidate'
        and r['score_status'] == 'full' and not truth(r['same_target_unconfirmed'])
        and not truth(r['same_target_quality_hold']) and not truth(r['latest_step_reference_pending'])}
    semi, times, scope, ledger = [], [], [], []
    for raw in read_csv(EVIDENCE / 'semi_initial_final_changes.csv'):
        inv = inv_by.get(raw['canonical_annotation_id'])
        if inv is None:
            raise ValueError('unbound_semi_evidence')
        validate_identity(raw, inv)
        gate = gates[inv['record_id']]
        if inv['semi_initialization_evidence'] != 'import_and_runtime_preview_matched':
            raise ValueError('semi_initialization_not_verified')
        purpose = 'normal_candidate' if normal_semi(gate) else 'trap' if gate['trap_status'] == 'confirmed_trap' else 'unverified_or_held'
        initial = json.loads(raw['initial_points_json'])
        final = objects[inv['object_id']].get('points_1024x512')
        # Source pairing comes from the current loader; raw coordinates are not sorted here.
        verified = bool(objects[inv['object_id']].get('links_zero_based')) and final is not None
        count_delta = int(raw['final_point_count']) - int(raw['initial_point_count'])
        behavior = 'copy' if truth(raw['exact_geometry_equal']) else 'addition' if count_delta > 0 else 'deletion_and_move' if count_delta < 0 else 'move'
        donor = dict(annotation_id=inv['object_id'], record_id=inv['record_id'], worker_id=normalize_worker_id(inv['worker_id']),
            image_id=inv['image_id'], building_id=inv['building_id'], condition='semi', initial_points=initial,
            final_points=final, final_pairing_verified=verified, behavior=behavior, purpose=purpose, weight=1.,
            raw_source_sha256=raw['source_sha256'], model_edit_status=gate['model_edit_status'])
        score = quality_by_object.get(inv['object_id'])
        if score:
            donor.update(reference_id=score['reference_id'], WQ=float(score['WQ']),
                         IoU3D100=float(score['IoU3D100']), quality_version='WQ-LS08-20261014')
        ledger.append(dict(record_id=inv['record_id'], purpose=purpose, behavior=behavior,
            final_pairing_verified=verified, initial_pairing_verified=paired(initial),
            training_allowed=purpose == 'normal_candidate' and normalize_worker_id(inv['worker_id']) not in {'19', '26'}))
        if purpose == 'normal_candidate' and donor['worker_id'] not in {'19', '26'}:
            semi.append(donor)
    for raw in read_csv(EVIDENCE / 'record_evidence.csv'):
        inv = inv_by.get(raw['canonical_annotation_id'])
        if inv is None:
            continue
        validate_identity(raw, inv)
        for raw_key, inv_key in [('project_id', 'project_id'), ('runtime_task_id', 'runtime_task_id'), ('raw_annotation_id', 'raw_annotation_id')]:
            if str(raw[raw_key]) != str(inv[inv_key]):
                raise ValueError('time_raw_identity_mismatch:' + raw_key)
        gate = gates[inv['record_id']]
        if inv['object_id'] not in manual and not (inv['condition'] == 'semi' and normal_semi(gate)):
            continue
        worker = normalize_worker_id(inv['worker_id'])
        if worker in {'19', '26'}:
            continue
        lead = positive(raw['lead_time_seconds']) if raw['lead_time_status'] == 'available' else None
        active = positive(inv['time_seconds']) if truth(inv['time_training_eligible']) and truth(inv['time_usable']) else None
        times.append(dict(annotation_id=inv['object_id'], worker_id=worker, image_id=inv['image_id'],
            building_id=inv['building_id'], condition=inv['condition'], active_time_seconds=active,
            lead_time_seconds=lead, time_context=inv['time_context'] or inv['image_id'] + '|' + inv['condition'],
            weight=1., lead_time_is_active_time=truth(raw['time_lead_time_is_active_time'])))
    seen = {}
    for raw in read_csv(SCOPE):
        inv = inv_by.get(raw['canonical_annotation_id'])
        if inv is None:
            continue
        validate_identity(raw, inv)
        worker = normalize_worker_id(raw['worker_id'])
        if worker in {'19', '26'} or raw['worker_scope'] not in {'in_scope', 'oos'} or truth(raw['later_hold']):
            continue
        key = raw['canonical_annotation_id']
        if key in seen and seen[key] != raw['worker_scope']:
            raise ValueError('conflicting_scope_response')
        if key in seen:
            continue
        seen[key] = raw['worker_scope']
        scope.append(dict(annotation_id=inv['object_id'], worker_id=worker, image_id=raw['image_id'],
            building_id=raw['building_id'], condition=raw['condition'], response=raw['worker_scope'],
            scene=scenes.get(raw['image_id'], 'unknown'), weight=1.))
    return dict(semi=semi, times=times, scope=scope, scenes=scenes, disputes=disputes, semi_ledger=ledger,
        source_sha256={str(p): base.digest(p) for p in [EVIDENCE / 'semi_initial_final_changes.csv', EVIDENCE / 'record_evidence.csv', SCOPE, DISPUTES, SCENES, INVENTORY]})


def fit_channels(channels, fitted):
    heldout = fitted['heldout']
    result = {k: [r for r in channels[k] if r['building_id'] != heldout] for k in ('semi', 'times')}
    result.update(scope=channels['scope'], scenes=channels['scenes'], disputes=channels['disputes'], source_sha256=channels['source_sha256'])
    result['lead_effects'] = {condition: estimate_axis([r for r in result['times'] if r['condition'] == condition], 'lead_time_seconds', log=True)
        for condition in ('manual', 'semi')}
    result['active_effects'] = {condition: estimate_axis([r for r in result['times'] if r['condition'] == condition], 'active_time_seconds', log=True)
        for condition in ('manual', 'semi')}
    fitted['channels'] = result
    from .semi_edit_distribution import fit_distribution
    result['semi_distribution'] = fit_distribution(result['semi'], heldout)
    return fitted


def sample_scope(row, fitted, seed):
    from .personality_annotator_sampler import choose_donor, mixture_pools, axis_effect
    channels = fitted['channels']; iid = row['image_id']; condition = row['condition']
    scope = channels['scope']; worker = row['source_worker_profile_id']
    local = [r for r in scope if r['image_id'] == iid]
    training = [r for r in scope if r['building_id'] != fitted['heldout']]
    scene = channels['scenes'].get(iid, 'unknown')
    options = [('image_response_distribution', local),
        ('condition_scene_prior', [r for r in training if r['condition'] == condition and scene != 'unknown' and r['scene'] == scene]),
        ('condition_prior', [r for r in training if r['condition'] == condition]), ('cross_condition_prior', training)]
    level, pool = next(((name, pool) for name, pool in options if pool), ('no_evidence', []))
    rng = np.random.default_rng(base.seed_for(seed, worker, 'scope_response'))
    donor = None
    if pool:
        if local:
            donor = pool[int(rng.integers(len(pool)))]
        else:
            donor, _, _ = choose_donor(pool, worker, fitted, base.seed_for(seed, worker, 'scope_prior'))
    probabilities = collections.defaultdict(float)
    if local:
        for r in pool:
            probabilities[r['response']] += 1 / len(pool)
    elif pool:
        pools, weights = mixture_pools(pool, worker, fitted['profiles'])
        effects = [axis_effect(fitted['profiles'], w, 'quality') for w in fitted['profiles']]
        effects = [v for v in effects if v is not None]
        spread = max(1., float(np.std(effects))) if effects else 1.
        target_effect = axis_effect(fitted['profiles'], worker, 'quality')
        for name, candidates in pools.items():
            if not candidates or not weights[name]:
                continue
            scores = []
            for r in candidates:
                source_effect = axis_effect(fitted['profiles'], r['worker_id'], 'quality')
                similarity = 1 / (1 + ((source_effect - target_effect) / spread)**2) if source_effect is not None and target_effect is not None else 1.
                scores.append(r.get('weight', 1.) * similarity)
            for r, score in zip(candidates, scores):
                probabilities[r['response']] += weights[name] * score / sum(scores)
    dispute = channels['disputes'].get(iid)
    variant = ('small', 'large')[int(np.random.default_rng(base.seed_for(seed, worker, condition, 'scope_variant')).integers(2))] if dispute is not None else None
    return dict(worker_scope_response=donor['response'] if donor else None,
        scope_status='sampled_response' if donor else 'missing_evidence', scope_pool=level,
        scope_condition_fallback=bool(donor and donor['condition'] != condition),
        scope_sampling_probabilities=dict(probabilities),
        scope_donor_annotation_id=donor['annotation_id'] if donor else None,
        scope_donor_worker_id=donor['worker_id'] if donor else None,
        scope_donor_building_id=donor['building_id'] if donor else None,
        scope_geometry_relation='sampled_response_not_geometry_adjudication',
        scope_variant=variant, scope_variant_status='sampled_intent_only' if dispute is not None else 'not_applicable',
        scope_variant_source=str(DISPUTES) if dispute is not None else None, scope_geometry_bound=False)


def sample_lead_time(row, fitted, seed):
    from .personality_annotator_sampler import choose_donor, axis_effect
    condition = row['condition']; worker = row['source_worker_profile_id']
    pool = [r for r in fitted['channels']['times'] if r['condition'] == condition and r['lead_time_seconds'] is not None]
    joint = next((r for r in pool if r['annotation_id'] == row.get('time_donor_annotation_id')), None)
    donor, level = joint, 'active_time_joint_donor'
    if donor is None:
        donor, level, _ = choose_donor(pool, worker, fitted, base.seed_for(seed, worker, 'lead_time'))
    out = dict(lead_time_seconds=None, lead_time_status='missing_evidence', lead_time_pool=level,
        lead_time_donor_annotation_id=None, lead_time_donor_worker_id=None, lead_time_donor_building_id=None,
        lead_time_log_effect_shift=0., lead_time_is_active_time=False)
    if donor is None:
        return out
    effects = fitted['channels']['lead_effects'][condition]
    target, source = effects.get(worker, {}), effects.get(donor['worker_id'], {})
    supported = all(r.get('supported') for r in (target, source))
    shift = target['effect'] - source['effect'] if supported else 0.
    try:
        seconds = positive(math.expm1(math.log1p(donor['lead_time_seconds']) + shift))
    except OverflowError:
        seconds = None
    out.update(lead_time_seconds=seconds, lead_time_status=('simulated_task_effect' if supported else 'empirical_no_supported_effect') if seconds else 'invalid_effect_shift',
        lead_time_log_effect_shift=shift, lead_time_donor_annotation_id=donor['annotation_id'],
        lead_time_donor_worker_id=donor['worker_id'], lead_time_donor_building_id=donor['building_id'])
    return out


def sample_semi_time(row, fitted, seed):
    from .personality_annotator_sampler import choose_donor
    worker = row['source_worker_profile_id']
    pool = [r for r in fitted['channels']['times'] if r['condition'] == 'semi' and r['active_time_seconds'] is not None]
    donor = next((r for r in pool if r['annotation_id'] == row.get('semi_donor_annotation_id')), None)
    level = 'semi_geometry_joint_donor'
    if donor is None:
        donor, level, _ = choose_donor(pool, worker, fitted, base.seed_for(seed, worker, 'semi_time'))
    effects = fitted['channels']['active_effects']['semi']
    target = effects.get(worker, {})
    source = effects.get(donor['worker_id'], {}) if donor else {}
    supported = all(r.get('supported') for r in (target, source))
    shift = target['effect'] - source['effect'] if supported else 0.
    seconds = positive(math.expm1(math.log1p(donor['active_time_seconds']) + shift)) if donor else None
    return dict(active_time_seconds=seconds,
        timing_status=('simulated_semi_task_effect' if supported else 'simulated_semi_empirical_no_supported_effect') if donor else 'missing_semi_time_evidence',
        time_donor_annotation_id=donor['annotation_id'] if donor else None,
        time_donor_worker_id=donor['worker_id'] if donor else None,
        time_donor_building_id=donor['building_id'] if donor else None, time_pool=level, time_log_effect_shift=shift)
