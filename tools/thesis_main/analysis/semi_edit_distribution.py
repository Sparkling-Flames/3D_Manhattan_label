"""Building-excluded empirical generative Semi edits with explicit source traces."""
from __future__ import annotations

import collections
import copy

import numpy as np
from scipy.optimize import linear_sum_assignment

from . import simulate_annotators as base

VERSION = 'semi_edit_distribution_v2'
SUCCESS = frozenset(('empirical_copy', 'empirical_edit', 'generated_move', 'generated_addition', 'generated_move_fallback'))


def correspondence(initial, final):
    ir = base.rays(initial.reshape(-1, 2)).reshape(-1, 2, 3)
    fr = base.rays(final.reshape(-1, 2)).reshape(-1, 2, 3)
    cost = np.arccos(np.clip(np.einsum('ikd,jkd->ijk', ir, fr), -1, 1)).mean(-1)
    nearest = np.sort(cost, axis=1)
    if cost.shape[1] > 1 and np.any(nearest[:, 1] - nearest[:, 0] < 1e-8):
        raise ValueError('ambiguous_edit_correspondence')
    return linear_sum_assignment(cost)


def edge_features(left, right):
    gap = float((right[0, 0] - left[0, 0]) % 1024) / 1024
    return np.array([gap, (left[1, 1] - left[0, 1]) / 512,
                     (right[1, 1] - right[0, 1]) / 512])


def addition_events(initial, final, ii, jj):
    n = len(initial); m = len(final)
    mapping = dict(zip(ii.tolist(), jj.tolist()))
    if set(mapping) != set(range(n)):
        raise ValueError('addition_missing_anchor')
    # Accept only a cyclic insertion, with every original anchor retaining order.
    source_order = [i for _, i in sorted((j, i) for i, j in mapping.items())]
    if any((source_order[(i + 1) % n] - source_order[i]) % n != 1 for i in range(n)):
        raise ValueError('addition_anchor_order_unconfirmed')
    matched = set(mapping.values()); events = []
    for i in range(n):
        a, b = mapping[i], mapping[(i + 1) % n]
        inserted = []
        j = (a + 1) % m
        while j != b:
            if j in matched:
                raise ValueError('addition_anchor_order_unconfirmed')
            inserted.append(j); j = (j + 1) % m
        if not inserted:
            continue
        left, right = final[a], final[b]
        gap = float((right[0, 0] - left[0, 0]) % 1024)
        if gap < 1e-6:
            raise ValueError('addition_degenerate_edge')
        tokens = []
        for j in inserted:
            fraction = float((final[j, 0, 0] - left[0, 0]) % 1024) / gap
            interpolated = left[:, 1] * (1 - fraction) + right[:, 1] * fraction
            span = interpolated[1] - interpolated[0]
            if not 0 < fraction < 1 or span <= 1e-6:
                raise ValueError('addition_not_inside_supported_edge')
            tokens.append(dict(fraction=fraction, height_offsets=((final[j, :, 1] - interpolated) / span).tolist()))
        if [t['fraction'] for t in tokens] != sorted(t['fraction'] for t in tokens):
            raise ValueError('addition_fraction_order_unconfirmed')
        events.append(dict(features=edge_features(left, right).tolist(), tokens=tokens))
    if sum(len(e['tokens']) for e in events) != m - n:
        raise ValueError('addition_unaccounted_pairs')
    return events


def fit_distribution(donors, heldout):
    from .personality_response_channels import paired
    moves, additions, excluded = [], [], []
    for donor in donors:
        if donor['building_id'] == heldout or donor['worker_id'] in ('19', '26') or donor.get('purpose', 'normal_candidate') != 'normal_candidate':
            continue
        try:
            if not paired(donor['initial_points']) or not donor['final_pairing_verified'] or not paired(donor['final_points']):
                raise ValueError('unverified_pairing')
            initial = np.asarray(donor['initial_points'], float).reshape(-1, 2, 2)
            final = np.asarray(donor['final_points'], float).reshape(-1, 2, 2)
            if donor['behavior'] not in ('move', 'addition'):
                raise ValueError('behavior_not_supported_by_normal_model')
            ii, jj = correspondence(initial, final)
            common = dict(worker_id=donor['worker_id'], annotation_id=donor['annotation_id'],
                building_id=donor['building_id'], image_id=donor['image_id'], purpose='normal_candidate', weight=1.)
            if donor['behavior'] == 'move':
                if len(initial) != len(final):
                    raise ValueError('move_count_changed')
                delta = final[jj] - initial[ii]
                horizontal = (delta[:, 0, 0] + 512) % 1024 - 512
                vectors = np.column_stack((horizontal / 1024, delta[:, 0, 1] / 512, delta[:, 1, 1] / 512))
                center = np.median(vectors, axis=0)
                if not np.isfinite(vectors).all():
                    raise ValueError('nonfinite_training_delta')
                moves.append(dict(common, global_delta=center.tolist(), local_delta=(vectors - center).tolist(),
                                  observed_delta=vectors.tolist(), behavior='move'))
            else:
                events = addition_events(initial, final, ii, jj)
                additions.append(dict(common, events=events, behavior='addition', weak_support=True))
        except ValueError as exc:
            excluded.append(dict(annotation_id=donor['annotation_id'], reason=str(exc)))
    values = np.concatenate([np.abs(r['observed_delta']) for r in moves]) if moves else np.zeros((0, 3))
    cap = np.quantile(values, .95, axis=0).tolist() if len(values) else None
    return dict(version=VERSION, heldout=heldout, moves=moves, additions=additions, cap=cap,
        exclusions=excluded, training_annotation_ids=sorted(r['annotation_id'] for r in moves + additions),
        training_buildings=sorted({r['building_id'] for r in moves + additions}),
        counts=dict(move=len(moves), addition=len(additions)), shrinkage=8., scale=1.)


def generate_edit(points, fitted, worker, seed, requested_behavior=None):
    from .personality_annotator_sampler import choose_donor
    distribution = fitted['channels']['semi_distribution']
    rng = np.random.default_rng(base.seed_for(seed, worker, 'generative_semi'))
    moves, additions = distribution['moves'], distribution['additions']
    behavior_source, behavior_pool, weights = choose_donor(moves + additions, worker, fitted,
        base.seed_for(seed, worker, 'semi_behavior'))
    requested = requested_behavior or (behavior_source['behavior'] if behavior_source else 'move')
    out = dict(semi_generation_method=VERSION, semi_requested_behavior=requested, semi_actual_behavior=None,
        semi_behavior_pool=behavior_pool, semi_behavior_source_id=behavior_source['annotation_id'] if behavior_source else None,
        semi_distribution_counts=distribution['counts'], semi_delta_cap_normalized=distribution['cap'],
        semi_pool=behavior_pool, semi_mixture_weights=weights, semi_training_manifest='fold_' + fitted['heldout'] + '.json',
        semi_edit_fallback_reason=None, semi_global_source=None, semi_local_sources=[], semi_addition_source=None,
        semi_source_purpose='normal_candidate', semi_addition_weak_support=False)
    global_source, level, move_weights = choose_donor(moves, worker, fitted, base.seed_for(seed, worker, 'semi_global_move'))
    if global_source is None:
        return copy.deepcopy(points), dict(out, semi_status='no_learned_move_distribution',
            semi_edit_fallback_reason='no_building_excluded_normal_move_evidence')
    candidate = np.asarray(points, float).reshape(-1, 2, 2).copy()
    locals_ = []
    for i in range(len(candidate)):
        donor, local_pool, _ = choose_donor(moves, worker, fitted, base.seed_for(seed, worker, 'semi_local', i))
        vector = donor['local_delta'][int(rng.integers(len(donor['local_delta'])))]
        locals_.append(vector)
        out['semi_local_sources'].append(dict(annotation_id=donor['annotation_id'], worker_id=donor['worker_id'],
            building_id=donor['building_id'], pool=local_pool, purpose=donor['purpose']))
    delta = np.clip(np.asarray(locals_) + global_source['global_delta'], -np.asarray(distribution['cap']), distribution['cap'])
    candidate[:, :, 0] = (candidate[:, :, 0] + delta[:, 0, None] * 1024) % 1024
    candidate[:, 0, 1] += delta[:, 1] * 512
    candidate[:, 1, 1] += delta[:, 2] * 512
    out.update(semi_global_source=dict(annotation_id=global_source['annotation_id'], worker_id=global_source['worker_id'],
        building_id=global_source['building_id'], image_id=global_source['image_id'], pool=level, purpose='normal_candidate'),
        semi_move_mixture_weights=move_weights, semi_actual_behavior='move', semi_status='generated_move')
    fallback = None
    if requested == 'addition':
        addition, add_pool, _ = choose_donor(additions, worker, fitted, base.seed_for(seed, worker, 'semi_addition'))
        if addition is None:
            fallback = 'no_building_excluded_addition_evidence'
        else:
            try:
                inserts = {}; used = set()
                for event in addition['events']:
                    edges = [i for i in range(len(candidate)) if i not in used and
                        edge_features(candidate[i], candidate[(i + 1) % len(candidate)])[0] > 1e-6]
                    if not edges:
                        raise ValueError('no_supported_insertion_edge')
                    probabilities = np.array([np.exp(-np.abs(edge_features(candidate[i], candidate[(i + 1) % len(candidate)]) - event['features']).sum() / .25) for i in edges])
                    if not np.isfinite(probabilities).all() or probabilities.sum() <= 0:
                        raise ValueError('insertion_edge_weights_invalid')
                    i = edges[int(rng.choice(len(edges), p=probabilities / probabilities.sum()))]; used.add(i)
                    left, right = candidate[i], candidate[(i + 1) % len(candidate)]
                    gap = (right[0, 0] - left[0, 0]) % 1024
                    extra = []
                    for token in event['tokens']:
                        t = token['fraction']; interpolated = left[:, 1] * (1 - t) + right[:, 1] * t
                        heights = interpolated + np.asarray(token['height_offsets']) * (interpolated[1] - interpolated[0])
                        if not np.isfinite(heights).all() or heights[0] >= heights[1]:
                            raise ValueError('insertion_heights_invalid')
                        x = (left[0, 0] + gap * t) % 1024
                        extra.append([[x, heights[0]], [x, heights[1]]])
                    inserts[i] = extra
                candidate = np.asarray([pair for i, pair in enumerate(candidate) for pair in [pair, *inserts.get(i, [])]])
                out.update(semi_status='generated_addition', semi_actual_behavior='addition', semi_addition_weak_support=True,
                    semi_addition_source=dict(annotation_id=addition['annotation_id'], worker_id=addition['worker_id'],
                        building_id=addition['building_id'], image_id=addition['image_id'], pool=add_pool, purpose='normal_candidate'))
            except ValueError as exc:
                fallback = str(exc)
    elif requested != 'move':
        fallback = 'behavior_has_no_normal_training_support:' + requested
    if fallback:
        out.update(semi_status='generated_move_fallback', semi_edit_fallback_reason=fallback)
    flat = candidate.reshape(-1, 2).tolist()
    if not base.parsed(flat):
        out['semi_status'] = 'numeric_invalid_retained'
    return flat, out
