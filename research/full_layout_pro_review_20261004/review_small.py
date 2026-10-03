"""小规模独立复核；不调用外部全实验入口，不写原下载或现有分析结果。"""
from collections import Counter
import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'external/src'))
sys.path.insert(0, str(REPO))
import consensus_lab as lab
from tools.thesis_main.analysis.global_pair_consensus_20261004 import build_global_pair_consensuses


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(name, obj):
    (ROOT / 'recompute' / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def vectors(points):
    """独立的单位向量/叉积球面角实现。"""
    p = np.asarray(points, float)
    u = 2 * np.pi * (p[:, 0] / 1024 - .5)
    v = np.pi * (p[:, 1] / 512 - .5)
    return np.c_[np.cos(v) * np.sin(u), np.sin(v), np.cos(v) * np.cos(u)]


def costs(a, b):
    matrices = []
    for role in (0, 1):
        va, vb = vectors(a[:, role]), vectors(b[:, role])
        dot = va @ vb.T
        cross = np.linalg.norm(np.cross(va[:, None, :], vb[None, :, :]), axis=-1)
        matrices.append(np.degrees(np.arctan2(cross, dot)))
    return np.maximum(*matrices)


def independent_joint(records, threshold):
    arrays = [lab.pairs(r) for r in sorted(records, key=lambda r: str(r['id']))]
    m = len(arrays[0])
    orders = sorted({tuple((start + sign * k) % m for k in range(m))
                     for start in range(m) for sign in (-1, 1)})
    matrices = {(i, j): costs(arrays[i], arrays[j]) for i, j in itertools.combinations(range(len(arrays)), 2)}
    states = []
    for tail in itertools.product(orders, repeat=len(arrays) - 1):
        maps = (tuple(range(m)),) + tail
        errors = [float(c[np.array(maps[i]), np.array(maps[j])].max()) for (i, j), c in matrices.items()]
        if max(errors) <= threshold + 1e-9:
            states.append(dict(maps=maps, score=sum(errors), pair_errors=errors))
    states.sort(key=lambda s: (s['score'], s['maps']))
    return dict(states_enumerated=len(orders) ** (len(arrays) - 1), feasible_count=len(states),
                optimal_count=sum(abs(s['score'] - states[0]['score']) <= 1e-9 for s in states),
                best_score=states[0]['score'] if states else None, feasible_assignments=states)


def main():
    tests = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'external/tests'), '-v'],
                           capture_output=True, text=True, encoding='utf-8', check=False)
    (ROOT / 'recompute/test_log.txt').write_text(tests.stdout + tests.stderr, encoding='utf-8')
    assert tests.returncode == 0, tests.stderr
    external_image = read(ROOT / 'external/inputs/current_excerpt.json')['images'][0]
    source = read(REPO / 'analysis_results/lee_expanded_20261003/source_input.json')
    local_image = next(v for v in source['images'] if v['code'] == external_image['code'])
    rows = external_image['annotations']
    local_rows = {r['id']: r for r in local_image['annotations']}
    binding = dict(image=external_image['code'], external_count=len(rows), local_count=len(local_rows),
                   same_annotation_id_set=set(local_rows) == {r['id'] for r in rows}, comparisons=[])
    for r in rows:
        local = local_rows[r['id']]
        mismatch = [key for key in r if r[key] != local.get(key)]
        binding['comparisons'].append(dict(id=r['id'], worker=r['worker'], compared_fields=list(r),
                                          mismatched_fields=mismatch, omitted_local_fields=sorted(set(local) - set(r))))
        assert not mismatch, (r['id'], mismatch)
    reference = read(ROOT / 'external/inputs/reference_excerpt.json')['references'][0]
    local_ref = next(r for r in local_image['references'] if r['id'] == reference['id'])
    ref_mismatch = [k for k in reference if reference[k] != (local_image['code'] if k == 'code' else local_ref.get(k))]
    binding['reference'] = dict(id=reference['id'], compared_fields=list(reference), mismatched_fields=ref_mismatch)
    assert not ref_mismatch, ref_mismatch
    write('source_binding.json', binding)

    cycle = read(ROOT / 'external/results/pairwise_unique_but_cycle_inconsistent.json')['records']
    audit = lab.cycle_audit(cycle, 5)
    assert audit['all_pairs_compatible_and_unique'] and len(audit['conflicts']) == 1
    joint = []
    for name, records in [('real_three', rows), ('synthetic_cycle', cycle)]:
        for threshold in (2.5, 5., 9.):
            independent = independent_joint(records, threshold)
            supplied = lab.joint_ring_alignment(records, threshold)
            assert independent['states_enumerated'] == 64
            assert independent['feasible_count'] == supplied.get('feasible_count', 0)
            assert independent['optimal_count'] == supplied.get('optimal_count', 0)
            if independent['feasible_count']:
                assert abs(independent['best_score'] - supplied['best_score']) < 1e-10
            joint.append(dict(case=name, threshold=threshold, independent=independent, prototype_status=supplied['status']))
    write('joint64_independent.json', joint)

    adj = read(ROOT / 'external/results/majority_adjacency_not_a_ring.json')
    xy = np.array(adj['points_xy']); rings = adj['cycles']
    polygons = [Polygon(xy[r]) for r in rings]
    edges = Counter(tuple(sorted((a, b))) for r in rings for a, b in zip(r, r[1:] + r[:1]))
    majority = {e for e, count in edges.items() if count >= 2}
    degrees = Counter(v for edge in majority for v in edge)
    solutions = []
    for tail in itertools.permutations(range(1, len(xy))):
        ring = (0,) + tail
        if ring[1] > ring[-1]:
            continue
        ring_edges = {tuple(sorted((a, b))) for a, b in zip(ring, ring[1:] + ring[:1])}
        poly = Polygon(xy[list(ring)])
        if ring_edges <= majority and poly.is_valid and poly.contains(Point(0, 0)):
            solutions.append(dict(ring=ring, discarded_majority_edges=sorted(majority - ring_edges),
                                  whole_ring_support=sum(ring_edges == {tuple(sorted((a, b))) for a, b in zip(r, r[1:] + r[:1])} for r in rings)))
    assert all(p.is_valid and p.contains(Point(0, 0)) for p in polygons)
    assert sorted(degrees.values()) == [2, 2, 2, 3, 3] and len(solutions) == 1
    write('adjacency_independent.json', dict(majority_edges=sorted(majority), degrees=dict(degrees),
          all_inputs_valid_and_contain_camera=True, admissible_cycles=solutions))

    witness = read(ROOT / 'external/results/local_majority_without_joint_witness.json')
    polys = [lab.polygon(r) for r in witness['records']]
    majority_region = unary_union([a.intersection(b) for a, b in itertools.combinations(polys, 2)])
    expected = lab.polygon(witness['majority_record'])
    assert majority_region.symmetric_difference(expected).area < 1e-10
    write('joint_witness_independent.json', dict(input_areas=[p.area for p in polys], majority_area=majority_region.area,
          symmetric_difference_to_111=majority_region.symmetric_difference(expected).area,
          full_111_observation_count=sum(p.symmetric_difference(expected).area < 1e-10 for p in polys),
          iou_to_inputs=[majority_region.intersection(p).area / majority_region.union(p).area for p in polys]))

    mismatch = read(ROOT / 'recompute/certification_objective_mismatch.json')
    records = mismatch['records']
    full = lab.full_alignment(lab.pairs(records[0]), lab.pairs(records[1]))
    part = lab.partial_alignment(lab.pairs(records[0]), lab.pairs(records[1]), 5)
    decision = lab.conditional_decision(records, tolerance=5)
    assert full['mapping'] != [b for a, b in part['mapping']]
    assert decision['status'] == 'single_candidate_conditional_on_method_tolerance'
    generated_maps = {v['id']: v['mapping'] for v in decision['single_candidate']['alignments']}
    c = lab.costs(lab.pairs(records[0]), lab.pairs(records[1]))
    write('certification_mismatch_verified.json', dict(
          both_inputs_valid=[lab.polygon(r).is_valid for r in records],
          both_inputs_contain_camera=[lab.polygon(r).contains(Point(0, 0)) for r in records],
          candidate_contains_camera=lab.polygon(decision['single_candidate']).contains(Point(0, 0)),
          certified_minimax=full, actual_minsum=part, generated_maps=generated_maps, status=decision['status'],
          minimax_sum=float(c[np.arange(3), full['mapping']].sum()),
          minsum_max=float(c[np.arange(3), [b for a, b in part['mapping']]].max()),
          consequence='certificate audits a different correspondence; not proof that this candidate is visually wrong'))
    nullable = copy.deepcopy(rows[:1]); nullable[0]['source_point_indices'] = None
    try:
        lab.derive_candidates(nullable)
    except TypeError as exc:
        nullable_result = dict(field='source_point_indices', value=None, error=str(exc))
    else:
        raise AssertionError('Expected nullable metadata bug not reproduced')
    write('nullable_metadata_error.json', nullable_result)

    global_results = []
    for name, records in [('real_three', rows), ('synthetic_cycle', cycle), ('majority_adjacency', adj['records']), ('no_whole_witness', witness['records'])]:
        out = build_global_pair_consensuses(records, 5)
        write('global_baseline_' + name + '.json', out)
        global_results.append(dict(case=name, rules={rule: dict(status=v['status'], reason=v['candidate']['reason'],
              selected_pairs=len(v['candidate']['feature_ids']), identity_count=len(v['identity_groups']),
              competing_matches=v['correspondence_diagnostics']['competing_worker_matches'],
              exact_source_ring_support=v['ring_diagnostics'].get('exact_source_ring_support'),
              projected_source_ring_support=v['ring_diagnostics'].get('projected_source_ring_support'),
              unsupported_edges=v['ring_diagnostics']['unsupported_edge_count'],
              below_majority_edges=v['ring_diagnostics']['below_majority_edge_count']) for rule, v in out.items()}))
    write('summary.json', dict(external_tests=25, tests_passed=True, source_binding='all copied computational fields exactly match; metadata excerpt incomplete',
          joint64=[dict(case=v['case'], threshold=v['threshold'], feasible=v['independent']['feasible_count'], optimal=v['independent']['optimal_count']) for v in joint],
          cycle_audit=audit, new_global_baseline=global_results,
          limits='one real image with three workers, controlled counterexamples; no full simulation or data reanalysis'))
    print(json.dumps(read(ROOT / 'recompute/summary.json'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
