"""Audit the frozen Pro/dot return and export the two repaired budget ledgers.

Run after the original reproduce.py and dot evidence/independent_audit.py.
Assertions check the saved claims; this does not decide any real deletion.
"""
import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import scipy
import shapely

from tools.thesis_main.analysis import finite_local_paths_20261005 as fixed

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT/'research/local_path_research_20261005'
PRO = ARCHIVE/'pro_original'
OUT = ROOT/'analysis_results/local_path_review_20261005'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def cell(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def compare(a, b, location, numbers, diagnostics):
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), location
        for key in a:
            compare(a[key], b[key], location+'/'+key, numbers, diagnostics)
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), location
        for i, (v, w) in enumerate(zip(a, b)):
            compare(v, w, location+'/'+str(i), numbers, diagnostics)
    elif a != b:
        if type(a) in (int, float) and type(b) in (int, float):
            delta = abs(a-b)
            assert delta <= 1e-9, (location, a, b)
            numbers.append(delta)
        else:
            # GEOS may report a different crossing of the same invalid ring.
            assert '/geometry_issues/' in location, (location, a, b)
            assert a.startswith('Self-intersection[') and b.startswith('Self-intersection[')
            diagnostics.append({'location': location, 'original': a, 'local': b})


def main():
    bindings = {}
    for name in ('rPc6DW4iMge-06.json', 'uNb9QFRL6hY-67.json'):
        bindings[name] = (PRO/'inputs'/name).read_bytes() == (ROOT/'research/layout_reliability_20261005/pro_original/inputs'/name).read_bytes()
    for name in ('tools/thesis_main/analysis/local_shortcut_projection_20261005.py',
                 'tools/thesis_main/analysis/layout_reliability_20261005/arc_consensus.py',
                 'tests/test_local_shortcut_projection_20261005.py'):
        bindings[name] = (PRO/'upstream_minimal'/name).read_bytes() == (ROOT/name).read_bytes()
    assert all(bindings.values())
    records = [r for name in ('rPc6DW4iMge-06.json', 'uNb9QFRL6hY-67.json') for r in load(PRO/'inputs'/name)['records']]
    assert len(records) == 39 and len({r['worker'] for r in records}) == 24

    comparisons = []
    for path in sorted((PRO/'results/final').rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(PRO/'results/final')
        replay = OUT/'recomputed'/relative
        numbers, diagnostics = [], []
        if path.suffix == '.json':
            a, b = load(path), load(replay)
        else:
            with path.open(encoding='utf-8', newline='') as f, replay.open(encoding='utf-8', newline='') as g:
                a = [{k: cell(v) for k, v in row.items()} for row in csv.DictReader(f)]
                b = [{k: cell(v) for k, v in row.items()} for row in csv.DictReader(g)]
        compare(a, b, '', numbers, diagnostics)
        comparisons.append({'path': relative.as_posix(), 'byte_equal': path.read_bytes() == replay.read_bytes(),
                            'parsed_exact_equal': a == b, 'numeric_changed_leaves': len(numbers),
                            'max_numeric_abs_difference': max(numbers, default=0), 'geos_witness_changes': diagnostics})
    assert len(comparisons) == 19

    candidates = load(PRO/'results/final/finite/all_candidates.json')
    domain = load(PRO/'inputs/domain.json')
    probes = {p['id']: p for p in load(PRO/'inputs/probes.json')}
    old_policies = load(PRO/'results/final/finite/policy_outputs_before_truth.json')
    repaired, additions = [], []
    for old in old_policies:
        new = fixed.policy_select(candidates, domain, old['policy'], old['evidence_claims'], probes)
        assert all(new[k] == old[k] for k in ('candidate_ids', 'status', 'geometry_count', 'representation_count', 'local_decisions'))
        if old['policy']['kind'] == 'budget_compact':
            selected, excluded = set(new['candidate_ids']), set(new['excluded'])
            assert selected | excluded == {c['id'] for c in candidates if c['admissible']}
            assert not selected & excluded
            added = {k: v for k, v in new['excluded'].items() if k not in old['excluded']}
            additions.append({'policy': old['policy']['id'], 'added_reasons': added})
            new['stream_id'] = old['stream_id']
            repaired.append(new)
        else:
            assert new['excluded'] == old['excluded']
    assert [len(x['added_reasons']) for x in additions] == [9, 21]
    fixed.dump(OUT/'fixed_budget_policy_outputs.json', repaired)

    evidence = load(OUT/'dot_evidence_recomputed/summary.json')
    comparison = load(OUT/'dot_evidence_recomputed/delivered_comparison.json')
    assert comparison['candidate_rows_equal'] == 324 and comparison['evidence_outputs_equal'] == 64
    clean, single, double = [next(r for r in evidence['bounded_experiment'] if r['b'] == 1 and r['mode'] == mode)
                             for mode in ('clean', 'single_flip', 'double_distinct_flip')]
    assert clean['unique_geometries'] == 0 and clean['fixed_event_count'] == 100
    assert single['cases'] == single['truth_covered'] == 490 and single['wrong_fixed_event_count'] == 0
    assert double['cases'] == 1470 and double['empty'] == 30 and double['truth_covered'] == 0
    assert double['status_counts']['single_geometry_conditional'] == 73
    assert double['status_counts']['compatibility_unresolved'] == 19 and double['wrong_fixed_event_count'] == 554

    fixture = load(ARCHIVE/'dot_original/projection/interior_maximum_fixture.json')
    points = np.asarray(fixture['points_xyz_h'])
    sys.path.insert(0, str(PRO/'src'))
    spec = importlib.util.spec_from_file_location('pro_real_audit', PRO/'src/real_diagnostics.py')
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)
    continuous = real.continuous_curve_difference(points, points[[0, 2]])
    witness = fixture['interior_witness_x_px']
    theta = 2*np.pi*(witness/1024-.5)
    ray = np.array([np.sin(theta), -np.cos(theta)])
    cross = lambda a, b: a[0]*b[1]-a[1]*b[0]
    def ray_y(a, b):
        a, edge = a[[0, 2]], (b-a)[[0, 2]]
        rho = cross(a, edge)/cross(ray, edge)
        t = cross(a, ray)/cross(ray, edge)
        assert rho > 0 and 0 <= t <= 1
        return 512*(.5+np.arctan(1/rho)/np.pi)
    direct = abs(ray_y(points[0], points[2])-ray_y(points[1], points[2]))
    assert abs(direct-fixture['interior_max_abs_dy_px']) < 1e-9
    assert abs(continuous['max_abs_dy_px']-direct) < 1e-9
    assert direct-fixture['removed_point_abs_dy_px'] > .33
    fixed.dump(OUT/'interior_counterexample_check.json', {'fixture': fixture, 'pro_continuous': continuous,
                                                         'independent_finite_ray_at_witness_px': float(direct)})
    search = load(PRO/'results/final/finite/search_equivalence.json')
    state_counts = {k: {'all_visited_states': search[k]['visited_partial_states'],
                        'terminal_states': search[k]['complete_states'],
                        'nonterminal_states': search[k]['visited_partial_states']-search[k]['complete_states']}
                    for k in ('addition', 'elimination')}
    result = {'schema': 'local_path_return_review_v1', 'source_bindings': bindings,
              'real_records': len(records), 'distinct_workers': 24, 'reproduction_artifacts': comparisons,
              'original_tests_passed': {'pro_new': 27, 'upstream_minimal': 4},
              'local_regressions': {'before_fix_failed': 2, 'after_fix_passed': 2},
              'policies_checked_selection_unchanged': len(old_policies), 'exclusion_repairs': additions,
              'dot_independent_rebuilt_candidates': comparison['candidate_rows_equal'],
              'dot_independent_evidence_outputs': comparison['evidence_outputs_equal'],
              'dot_evidence_b1': {'clean': clean, 'single_error': single, 'two_distinct_errors': double},
              'enumeration_state_count_clarification': state_counts,
              'environment': {'numpy': np.__version__, 'scipy': scipy.__version__, 'shapely': shapely.__version__, 'geos': shapely.geos_version_string},
              'real_deletion_decisions': {'R01557_source6': 'undetermined', 'R02928_source3': 'undetermined'},
              'scope': 'finite-domain audit; no new original-image adjudication, GT review, whole-repository test, or automatic deletion'}
    fixed.dump(OUT/'checks.json', result)
    print(json.dumps({'artifacts': len(comparisons), 'byte_equal': sum(x['byte_equal'] for x in comparisons),
                      'max_numeric_abs_difference': max(x['max_numeric_abs_difference'] for x in comparisons),
                      'geos_witness_changes': sum(len(x['geos_witness_changes']) for x in comparisons),
                      'selection_unchanged': len(old_policies), 'repaired_exclusions': 30,
                      'double_error_cases': double['cases'], 'interior_max_px': float(direct)}))


if __name__ == '__main__':
    main()
