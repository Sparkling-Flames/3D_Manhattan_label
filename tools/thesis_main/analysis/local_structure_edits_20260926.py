"""局部连续链投票的有界增删探针；不读取参考，也不改写输入环。"""
from collections import Counter
import math

import numpy as np

from .structural_consensus_20260926 import fit_consensus, geometry_diagnostics, match_ring, score_candidate


def local_edit_probe(records, point_tol=.2, support_threshold=.5, max_steps=3, beam_width=4,
                     *, worker_weights=None, seed_worker_ids=None):
    """仅使用传入人员；相邻锚点间最多增删两个内部点，禁止重排。

    原始支持分母为全体独立输入人员；显式给权重时决策分母为总权重。
    权重不是人员数，也不是已校准的局部可见性/范围条件分母。
    ponytail: 有界束搜索只探索局部短链；需要更长链时扩大预先冻结的搜索预算。
    """
    if (not math.isfinite(point_tol) or point_tol <= 0 or not math.isfinite(support_threshold)
            or not 0 < support_threshold <= 1 or not isinstance(max_steps, int) or max_steps < 0
            or not isinstance(beam_width, int) or beam_width < 1):
        raise ValueError('invalid_parameters')
    rows, workers = [], set()
    for r in sorted(records, key=lambda x: str(x['id'])):
        worker, p = str(r['worker']), np.asarray(r['floor'], float)
        if worker in workers:
            raise ValueError('duplicate_worker')
        match_ring(p, p, point_tol)  # 共用核心输入坐标校验。
        workers.add(worker)
        rows.append(dict(id=str(r['id']), worker=worker, floor=p))
    cap, n = 128, len(rows)
    weights = {w: 1. for w in workers} if worker_weights is None else dict(worker_weights)
    if (set(weights) != workers or any(not math.isfinite(v) or v < 0 for v in weights.values())
            or (n and not sum(weights.values()))):
        raise ValueError('invalid_worker_weights')
    mass = float(sum(weights.values()))
    seed_workers = workers if seed_worker_ids is None else set(seed_worker_ids)
    if not seed_workers <= workers or (n and not seed_workers):
        raise ValueError('invalid_seed_workers')
    seed_rows = [r for r in rows if r['worker'] in seed_workers]
    weighted_count = lambda ids: float(sum(weights[w] for w in ids))
    result = dict(schema_version='local_structure_edits_20260926_v1',
                  parameters=dict(point_tol=point_tol, support_threshold=support_threshold,
                                  max_steps=max_steps, beam_width=beam_width, max_internal_chain_points=2,
                                  per_seed_step_proposal_cap=cap, vote_denominator=n, weight_denominator=mass),
                  worker_weights=weights, seed_worker_ids=sorted(seed_workers),
                  score_formula='.5*mean(vertex_weight/sum_weights)+.5*mean(edge_weight/sum_weights)-.02*direction_residual_deg/45',
                  vote_rule='one_worker_one_raw_vote; weighted_decisions_divide_by_total_weight; cyclic_contiguous_path_or_reverse',
                  search_count_rule='proposed=unique_threshold_eligible_unvisited_rings; evaluated=cap_selected; visited_includes_seeds',
                  limitations=['bounded_search_not_exhaustive', 'given_adjacency_unverified',
                               'no_height_or_ceiling_reconstruction', 'fixed_metric_tolerance',
                               'local_votes_do_not_certify_joint_or_semantic_validity',
                               'all_workers_denominator_is_not_scope_conditional'],
                  candidates=[], seeds=[], search=dict(proposed=0, evaluated=0, truncated=0, visited=0))
    if not rows:
        return dict(result, status='no_training_records')
    paths = {length: [] for length in (2, 3, 4)}
    for r in rows:
        for length in paths:
            if length <= len(r['floor']):
                chains = [r['floor'][(start+direction*np.arange(length)) % len(r['floor'])]
                          for start in range(len(r['floor'])) for direction in (1, -1)]
                paths[length].append((r['worker'], np.asarray(chains)))
    vote_cache = {}

    def votes(chain):
        key = tuple(np.asarray(chain).round(10).ravel())
        if key not in vote_cache:
            vote_cache[key] = [w for w, variants in paths[len(chain)]
                               if np.any(np.max(np.linalg.norm(variants-chain, axis=2), axis=1) <= point_tol+1e-12)]
        return vote_cache[key]

    def ring_key(p):
        # 仅去重使用舍入；候选坐标及所有距离仍使用原浮点值。
        return min(tuple(np.roll(p[::direction], shift, axis=0).round(10).ravel())
                   for direction in (1, -1) for shift in range(len(p)))

    def evaluate(p, actions):
        vertex_workers = [[r['worker'] for r in rows if np.min(np.linalg.norm(r['floor']-q, axis=1)) <= point_tol+1e-12] for q in p]
        vertex = list(map(len, vertex_workers))
        edge_workers = [votes(np.array([p[i], p[(i+1) % len(p)]])) for i in range(len(p))]
        edge = list(map(len, edge_workers))
        vertex_weight, edge_weight = list(map(weighted_count, vertex_workers)), list(map(weighted_count, edge_workers))
        geometry = geometry_diagnostics(p)
        support = score_candidate(p, rows, point_tol=point_tol)
        residual = geometry['weighted_direction_residual_deg']
        value = .5*np.mean(vertex_weight)/mass + .5*np.mean(edge_weight)/mass - .02*(residual if residual is not None else 45)/45
        state = 'observed_ring_candidate' if support['whole_ring_support'] else 'unsupported_joint_candidate'
        if geometry['polygon_status'] != 'valid' or geometry['zero_edges']:
            state = 'invalid_input_seed_kept_for_review' if not actions else 'invalid_edit_rejected'
        return dict(floor=p.tolist(), actions=actions, score=float(value), geometry=geometry,
                    whole_ring_support=support['whole_ring_support'], whole_ring_supporters=support['workers'],
                    whole_ring_weight=weighted_count(support['workers']),
                    status=state,
                    local_support=dict(vertex_counts=list(map(int, vertex)), edge_counts=edge,
                                       vertex_weights=vertex_weight, edge_weights=edge_weight,
                                       edge_workers=edge_workers, denominator=n, weight_denominator=mass))

    for kind, seed in [('minimum', min(seed_rows, key=lambda r: (len(r['floor']), r['id']))),
                       ('maximum', min(seed_rows, key=lambda r: (-len(r['floor']), r['id'])))]:
        initial = evaluate(seed['floor'], [])
        beam, visited = [initial], {ring_key(seed['floor'])}
        trace = dict(seed_kind=kind, seed_id=seed['id'], generated_candidates=[], rejected_examples=[],
                     rejection_counts=Counter(), steps=[], initial_geometry=initial['geometry'])
        for step in range(max_steps):
            proposals = {}
            for state in beam:
                p = np.asarray(state['floor'])

                def propose(q, action):
                    key = ring_key(q)
                    if key not in visited:
                        proposals.setdefault(key, (q, state['actions']+[action]))

                for i in range(len(p)):
                    for count in (1, 2):
                        if len(p)-count < 3:
                            continue
                        removed = [(i+j) % len(p) for j in range(count)]
                        anchors = np.array([p[i-1], p[(i+count) % len(p)]])
                        support = votes(anchors)
                        vector, offset = anchors[1]-anchors[0], p[i]-anchors[0]
                        exact = (count == 1 and np.linalg.norm(vector) > 1e-12
                                 and abs(np.cross(vector, offset)) <= 1e-10*np.linalg.norm(vector)
                                 and 0 < float(np.dot(offset, vector)) < float(np.dot(vector, vector)))
                        fraction = weighted_count(support)/mass
                        if exact or (fraction >= support_threshold and set(support)-{seed['worker']}):
                            propose(np.delete(p, removed, axis=0), dict(type='delete', indices=removed,
                                    points=p[removed].tolist(), anchors=anchors.tolist(), supporters=support,
                                    support_fraction=len(support)/n, weighted_support_fraction=fraction,
                                    evidence='exact_collinear_redundancy' if exact else 'supported_direct_edge'))
                    anchors = p[[i, (i+1) % len(p)]]
                    for length in (3, 4):
                        for donor, chains in paths[length]:
                            if donor == seed['worker']:
                                continue
                            near = np.max(np.linalg.norm(chains[:, [0, -1]]-anchors, axis=2), axis=1) <= point_tol+1e-12
                            for chain in chains[near]:
                                proposed_chain = np.vstack([anchors[0], chain[1:-1], anchors[1]])
                                support = votes(proposed_chain)
                                fraction = weighted_count(support)/mass
                                if fraction >= support_threshold:
                                    q = np.vstack([p[:i+1], chain[1:-1], p[i+1:]])
                                    propose(q, dict(type='insert', after_index=i, points=chain[1:-1].tolist(),
                                            anchors=anchors.tolist(), donor_worker=donor, supporters=support,
                                            support_fraction=len(support)/n, weighted_support_fraction=fraction,
                                            evidence='supported_contiguous_chain'))
            ordered = sorted(proposals.items(), key=lambda x: (-x[1][1][-1]['weighted_support_fraction'], x[0]))
            truncated = max(0, len(ordered)-cap)
            trace['steps'].append(dict(step=step+1, proposed=len(ordered), evaluated=min(cap, len(ordered)), truncated=truncated))
            for key, (p, actions) in ordered[:cap]:
                visited.add(key)
                candidate = evaluate(p, actions)
                if candidate['geometry']['polygon_status'] != 'valid' or candidate['geometry']['zero_edges']:
                    reason = candidate['geometry']['polygon_reason'] if not candidate['geometry']['zero_edges'] else 'zero_edge'
                    trace['rejection_counts'][reason] += 1
                    if len(trace['rejected_examples']) < 16:
                        trace['rejected_examples'].append(dict(floor=p.tolist(), actions=actions, reason=reason))
                else:
                    trace['generated_candidates'].append(candidate)
                    beam.append(candidate)
            beam.sort(key=lambda c: (-c['score'], -c['whole_ring_support'], len(c['floor']), ring_key(np.asarray(c['floor']))))
            beam = beam[:beam_width]
            if not ordered:
                break
        trace['rejection_counts'] = dict(trace['rejection_counts'])
        trace['visited'] = len(visited)
        trace['rejected_example_limit'] = 16
        result['seeds'].append(trace)
        result['candidates'].extend(dict(c, seed_kind=kind, seed_id=seed['id']) for c in beam)
        result['search']['visited'] += len(visited)
        for entry in trace['steps']:
            for key in ('proposed', 'evaluated', 'truncated'):
                result['search'][key] += entry[key]
    return dict(result, status='ok')


def cluster_pool_probe(records, point_tol=.2, support_threshold=.5, max_steps=2, beam_width=3,
                       *, outside_mode='soft'):
    """全来源点/链池，按当前训练簇条件加权；池本身不推断环序。

    簇外总权重上限是保护少数的设计先验，不能以保护结果反证少数合理。
    高度仅随源点留档，此路线仍只操作给定邻接的地面结构。
    """
    if outside_mode not in ('hard', 'soft'):
        raise ValueError('invalid_outside_mode')
    if (not math.isfinite(support_threshold) or not 0 < support_threshold <= 1
            or not isinstance(max_steps, int) or max_steps < 0
            or not isinstance(beam_width, int) or beam_width < 1):
        raise ValueError('invalid_parameters')
    fitted = fit_consensus(records, point_tol=point_tol, geometry_weight=0, height_weight=0)
    by_worker = {str(r['worker']): r for r in records}
    points = [dict(source_id=str(r['id']), worker=str(r['worker']), point_index=i, floor=list(p),
                   previous_index=(i-1) % len(r['floor']), next_index=(i+1) % len(r['floor']),
                   height=None if r.get('heights') is None else float(r['heights'][i]))
              for r in records for i, p in enumerate(r['floor'])]
    result = dict(schema_version='cluster_pool_probe_20260926_v1', status='ok',
                  input_workers=[str(r['worker']) for r in records], outside_mode=outside_mode,
                  pool=dict(points=points, adjacency='source_ring_only; no_global_pool_ring'),
                  mode_method='train_only_equal_count_complete_link; no_geometry_fit',
                  weight_formula='inside=1; outside_raw=.25*exp(-D/point_tol); outside_total<=.25*inside_total',
                  difference_formula='D=.5*mean(min_vertex_distance(A,B))+.5*mean(min_vertex_distance(B,A))+.25*point_tol*abs(countA-countB)',
                  minimum_searched_mode_support=3, modes=[], candidates=[],
                  limitations=['mode_discovery_depends_on_equal_count_and_point_tolerance',
                               'rare_modes_retained_without_search', 'outside_cap_is_prior_not_empirical_evidence',
                               'point_pool_has_no_independently_verified_adjacency', 'no_height_consensus',
                               'point_distance_for_weights_does_not_validate_topology'])
    for mode in fitted['modes']:
        members = set(mode['cluster_supporters'])
        reference = np.asarray(mode['representative_floor'])
        weights, differences = {}, {}
        for worker, r in by_worker.items():
            p = np.asarray(r['floor'])
            distances = np.linalg.norm(reference[:, None]-p[None], axis=2)
            difference = float(.5*distances.min(axis=0).mean()+.5*distances.min(axis=1).mean()
                               +.25*point_tol*abs(len(reference)-len(p)))
            differences[worker] = difference
            weights[worker] = 1. if worker in members else .25*math.exp(-difference/point_tol) if outside_mode == 'soft' else 0.
        outside_mass = sum(value for worker, value in weights.items() if worker not in members)
        scale = min(1., .25*len(members)/outside_mass) if outside_mass else 1.
        weights = {worker: value if worker in members else value*scale for worker, value in weights.items()}
        entry = dict(cluster_id=mode['mode_id'], members=sorted(members), train_support=len(members),
                     source_candidate_whole_ring_support=mode['candidate_whole_ring_support'],
                     worker_weights=weights, structural_differences=differences, outside_cap_scale=scale,
                     search_status='searched' if len(members) >= 3 else 'rare_input_mode_not_searched')
        if len(members) >= 3:
            probe = local_edit_probe(records, point_tol, support_threshold, max_steps, beam_width,
                                     worker_weights=weights, seed_worker_ids=members)
            entry['local_edit'] = probe
            candidates = probe['candidates']
        else:
            candidates = [dict(floor=r['floor'], actions=[], status='rare_input_candidate_not_searched',
                               whole_ring_support=score_candidate(r['floor'], records, point_tol=point_tol)['whole_ring_support'],
                               geometry=geometry_diagnostics(r['floor']), seed_kind='rare_original', seed_id=str(r['id']))
                          for r in records if str(r['worker']) in members]
        result['candidates'].extend(dict(c, cluster_id=mode['mode_id']) for c in candidates)
        result['modes'].append(entry)
    return result
