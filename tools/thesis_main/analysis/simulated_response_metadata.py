"""Empirical synthetic time, Semi edits and scope responses with donor provenance.

All training channels exclude the target building. Scope labels describe sampled
worker responses, not an adjudication of the generated geometry or floor extent.
"""
from __future__ import annotations

import csv
import json
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from tools.thesis_main.analysis import simulate_annotators as s1
from tools.thesis_main.analysis.simulate_annotators_opt import normalize_worker_id

EVIDENCE = s1.ROOT / 'analysis_results/annotation_research_prework_20260905_v2/evidence'
SCOPE = s1.ROOT / 'analysis_results/worker_four_block_exploration_20260910_v1/scope_responses.csv'


def read_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def load_evidence():
    return dict(time=read_csv(EVIDENCE / 'record_evidence.csv'),
                semi=read_csv(EVIDENCE / 'semi_initial_final_changes.csv'),
                scope=read_csv(SCOPE))


def eligible_time(row):
    try:
        seconds = float(row.get('active_time_seconds', ''))
    except (ValueError, TypeError):
        return False
    return (math.isfinite(seconds) and seconds > 0
            and row.get('time_active_time_formal_available', '').lower() == 'true'
            and row.get('active_time_owner_valid_status') == 'owner_valid_complete')


def select_pool(rows, worker, condition, point_count=None, minimum=3):
    condition_rows = [r for r in rows if r.get('condition', r.get('raw_condition')) == condition]
    personal = [r for r in condition_rows if normalize_worker_id(r['worker_id']) == worker]
    pools = []
    if point_count is not None:
        pools.append(('worker_condition_count', [r for r in personal if int(r.get('raw_final_point_count') or 0) == point_count]))
    pools.append(('worker_condition', personal))
    if point_count is not None:
        pools.append(('pooled_condition_count', [r for r in condition_rows if int(r.get('raw_final_point_count') or 0) == point_count]))
    pools.append(('pooled_condition', condition_rows))
    for label, pool in pools:
        if len(pool) >= minimum:
            return pool, label
    return condition_rows, 'sparse_condition' if condition_rows else 'no_training_evidence'


def transfer_semi(base, donor, cap=24.):
    """Transfer observed copy, displacement or pair deletion to a model proposal."""
    initial = np.asarray(json.loads(donor['initial_points_json']), dtype=float)
    final = np.asarray(json.loads(donor['final_points_json']), dtype=float)
    base = np.asarray(base, dtype=float)
    if not s1.parsed(initial) or not s1.parsed(final):
        return base.copy(), 'invalid_donor'
    if len(initial) != len(base):
        return base.copy(), 'initial_count_mismatch'
    if np.array_equal(initial, final):
        return base.copy(), 'empirical_copy'
    if len(final) > len(initial):
        return base.copy(), 'unsupported_addition'
    ip = initial.reshape(-1, 2, 2)
    fp = final.reshape(-1, 2, 2)
    # Refuse ambiguous source pairing, preserving its explicit failure reason.
    try:
        aligned_initial = s1.align_pairs(base, initial)
        s1.align_pairs(final, final)
    except ValueError:
        return base.copy(), 'ambiguous_donor_pairing'
    ip = aligned_initial.reshape(-1, 2, 2)
    fp = np.array([p[np.argsort(p[:, 1])] for p in fp])
    ir = s1.rays(ip.reshape(-1, 2)).reshape(-1, 2, 3)
    fr = s1.rays(fp.reshape(-1, 2)).reshape(-1, 2, 3)
    cost = np.arccos(np.clip(np.einsum('ikd,jkd->ijk', ir, fr), -1, 1)).mean(axis=-1)
    ii, fi = linear_sum_assignment(cost)
    delta = fp[fi] - ip[ii]
    delta[:, :, 0] = (delta[:, :, 0] + 512) % 1024 - 512
    candidate = base.reshape(-1, 2, 2)[ii] + np.clip(delta, -cap, cap)
    candidate[:, :, 0] %= 1024
    candidate[:, :, 1] = np.clip(candidate[:, :, 1], 0, 511.999)
    candidate = candidate.reshape(-1, 2)
    if s1.geometry_status(candidate) != 'basic_checks_passed_not_certified':
        return base.copy(), 'geometry_rejected'
    return candidate, 'empirical_edit'


def augment(sample, bank, evidence, building, condition, seed):
    row = dict(sample, condition=condition, synthetic=True, review_required=True)
    worker = normalize_worker_id(row['source_worker_profile_id'])
    train = {channel: [r for r in rows if r['building_id'] != building
                       and normalize_worker_id(r['worker_id']) not in {'19', '26'}]
             for channel, rows in evidence.items()}
    rng = np.random.default_rng(s1.seed_for(seed, 'semi'))
    row['semi_status'] = 'not_applicable'
    if condition == 'semi':
        base = bank[row['model_family']]['points']
        candidates = [r for r in train['semi']
                      if r.get('initial_structurally_valid') == 'true'
                      and r.get('final_structurally_valid') == 'true'
                      and int(r['initial_point_count']) == len(base)]
        pool, level = select_pool(candidates, worker, 'semi')
        row.update(initial_points=base, initialization_trace=dict(
            model_layout_id=row['model_layout_id'], model_family=row['model_family']),
            manual_residual_trace={k: row.get(k) for k in ('residual_source', 'residual_donor_annotation_id', 'residual_donor_building_id')},
            residual_source='semi_empirical_channel', residual_donor_annotation_id=None,
            residual_donor_image_id=None, residual_donor_building_id=None)
        if pool:
            donor = pool[int(rng.integers(len(pool)))]
            points, status = transfer_semi(base, donor)
            row.update(points=points.tolist(), semi_status=status, semi_pool=level,
                       semi_donor_annotation_id=donor['canonical_annotation_id'],
                       semi_donor_building_id=donor['building_id'])
        else:
            row.update(points=base, semi_status='no_training_evidence', semi_pool=level)
        row.update(geometry_status=s1.geometry_status(row['points']),
                   model_copy=bool(np.array_equal(row['points'], base)),
                   residual_applied=row['semi_status'] == 'empirical_edit',
                   residual_fallback_reason=None if row['semi_status'] in {'empirical_edit', 'empirical_copy'} else row['semi_status'])
    times = [r for r in train['time'] if eligible_time(r)]
    pool, level = select_pool(times, worker, condition, len(row['points']))
    rng = np.random.default_rng(s1.seed_for(seed, 'time'))
    row.update(active_time_seconds=None, lead_time_seconds=None, timing_status='not_simulated', time_pool=level)
    if pool:
        donor = pool[int(rng.integers(len(pool)))]
        try:
            lead = float(donor.get('lead_time_seconds') or '')
            if not math.isfinite(lead) or lead <= 0:
                lead = None
        except ValueError:
            lead = None
        row.update(active_time_seconds=float(donor['active_time_seconds']), lead_time_seconds=lead,
                   timing_status='simulated_empirical', time_donor_annotation_id=donor['canonical_annotation_id'],
                   time_donor_building_id=donor['building_id'])
    scope = [r for r in train['scope'] if r.get('worker_scope') in {'in_scope', 'oos'}]
    # This table can contain multiple axes per response; sample each response once.
    scope = list({r['canonical_annotation_id']: r for r in scope}.values())
    pool, level = select_pool(scope, worker, condition)
    row.update(scope_status='not_simulated', worker_scope_response=None, scope_pool=level,
               scope_geometry_relation='sampled_response_not_geometry_adjudication')
    if pool:
        rng = np.random.default_rng(s1.seed_for(seed, 'scope'))
        donor = pool[int(rng.integers(len(pool)))]
        row.update(scope_status='simulated', worker_scope_response=donor['worker_scope'],
                   scope_donor_annotation_id=donor['canonical_annotation_id'], scope_donor_building_id=donor['building_id'])
    return row
