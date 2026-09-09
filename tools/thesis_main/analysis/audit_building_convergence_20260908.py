"""审计同 building 准备资料的原始身份、点序、历史分母及有限人群曲线。

仅写入独立 audit 目录；复用历史几何引擎，不把计算复现当作视觉合法性证明。
"""
import argparse
import csv
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


CURRENT = {str(x) for x in [1, 2, 6, 8, 10, 11, 12, 13, 15, 17, *range(28, 38)]}


def read_csv(path):
    with (gzip.open(path, 'rt', encoding='utf-8-sig', newline='')
          if path.suffix == '.gz' else path.open(encoding='utf-8-sig', newline='')) as stream:
        return list(csv.DictReader(stream))


def truth(value):
    if str(value).lower() not in ('true', 'false'):
        raise ValueError(f'Unknown boolean: {value!r}')
    return str(value).lower() == 'true'


def ordered_points(results):
    points = []
    for item in results:
        if item.get('type') in ('keypointlabels', 'keypointregion'):
            value = item['value']
            if any(k not in value or value[k] is None for k in ('x', 'y')):
                raise ValueError('Incomplete raw keypoint')
            x, y = float(value['x']), float(value['y'])
            if not all(math.isfinite(v) for v in (x, y)):
                raise ValueError('Nonfinite raw keypoint')
            points.append([x * 1024 / 100, y * 512 / 100])
    return points


def require_same_points(left, right):
    if (len(left) != len(right)
            or any(len(p) != 2 or len(q) != 2 for p, q in zip(left, right))
            or any(not math.isfinite(b) or abs(a - b) > 1e-8
                   for p, q in zip(left, right) for a, b in zip(p, q))):
        raise ValueError('Raw coordinate/order mismatch')


def source_annotation_index(tasks):
    index = {}
    for task in tasks:
        for annotation in task.get('annotations', []):
            worker = annotation['completed_by']
            if isinstance(worker, dict):
                worker = worker.get('id', worker.get('pk'))
            key = (str(annotation.get('task', task['id'])), str(worker), str(annotation['id']))
            if key in index:
                raise ValueError(f'duplicate raw identity: {key}')
            if key[0] != str(task['id']):
                raise ValueError('Raw annotation task differs from parent task')
            index[key] = (task, annotation)
    return index


def unique(rows, key):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows) or '' in result:
        raise ValueError(f'Duplicate or empty {key}')
    return result


def require_partition_coverage(partitions, member_groups):
    if not set(member_groups) <= set(partitions):
        raise ValueError('Members reference an unknown partition')
    for pid in set(partitions) - set(member_groups):
        p = partitions[pid]
        if not (int(p['member_count']) == int(p['cluster_count']) == 0
                and p['partition_status'] == 'not_evaluable'):
            raise ValueError('Missing partition members: ' + pid)


def audit(root, out):
    import numpy as np
    from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
    from tools.thesis_main.analysis.audit_annotation_research_data_20260905 import _dense_boundaries
    from tools.thesis_main.analysis.preflight_data_20260906 import distance_matrix
    from tools.thesis_main.analysis.audit_preflight_claims_20260906 import finite_variance_projection

    out.mkdir(parents=True, exist_ok=True)
    def write(name, rows):
        if not rows:
            raise ValueError(f'No rows/field contract for {name}')
        with (out / name).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    base = root / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
    prepared = root / 'analysis_results/uncertainty_decision_ready_20260908_v1'
    preflight = root / 'analysis_results/preflight_20260906_v2'
    annotations = read_csv(base / 'annotations.csv.gz')
    by_id = unique(annotations, 'canonical_annotation_id')
    images = unique(read_csv(base / 'images.csv'), 'image_id')
    responses = unique(read_csv(prepared / 'response_index.csv.gz'), 'canonical_annotation_id')
    context_index = unique(read_csv(prepared / 'context_index.csv'), 'context_key')
    versions = [json.loads(line) for line in (base / 'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()]
    by_version = unique(versions, 'raw_annotation_version_id')
    assert set(responses) == set(by_id)
    selected = unique([r for r in versions if truth(r['selected_canonical_version'])], 'canonical_annotation_id')
    assert set(selected) == set(by_id)
    assert all(not truth(v['independent_analysis_unit']) for v in versions if not truth(v['selected_canonical_version']))
    variants = read_csv(base / 'facts/geometry_variants.csv.gz')
    raw_geometry = unique([v for v in variants if v['variant'] == 'raw'], 'canonical_annotation_id')
    strict_geometry = unique([v for v in variants if v['variant'] == 'strict_normalized'], 'canonical_annotation_id')
    assert set(raw_geometry) == set(strict_geometry) == set(by_id)

    print('逐条核对原始导出身份与点序...', flush=True)
    source_indices, source_checks, selected_points = {}, [], {}
    for v in versions:
        path = v['source_path']
        if path not in source_indices:
            source_indices[path] = source_annotation_index(json.loads((root / path).read_text(encoding='utf-8-sig')))
        key = (v['runtime_task_id'], v['worker_id'], v['raw_annotation_id'])
        task, annotation = source_indices[path][key]
        points = ordered_points(annotation['result'])
        require_same_points(points, v['points_1024x512'])
        assert [r for r in annotation['result'] if r.get('type') == 'keypointlabels'] == v['raw_keypoint_results']
        image_found = v['base_task_id'] in json.dumps(task.get('data', {}), ensure_ascii=False)
        if not image_found:
            raise ValueError(f'Raw task image binding missing: {v["raw_annotation_version_id"]}')
        if truth(v['selected_canonical_version']):
            a = by_id[v['canonical_annotation_id']]
            assert (a['runtime_task_id'], a['worker_id'], a['raw_annotation_id']) == key
            assert a['raw_export_path'] == path
            for field in ('stage', 'block_index', 'raw_condition', 'base_task_id'):
                assert a[field] == v[field]
            require_same_points(points, json.loads(raw_geometry[v['canonical_annotation_id']]['points_json']))
            selected_points[v['canonical_annotation_id']] = points
        source_checks.append(dict(raw_annotation_version_id=v['raw_annotation_version_id'],
                                  canonical_annotation_id=v['canonical_annotation_id'],
                                  selected_canonical_version=truth(v['selected_canonical_version']),
                                  source_path=path, image_binding_found=image_found,
                                  original_sequence_matches=True, point_count=len(points)))
    write('raw_version_audit.csv', source_checks)

    groups = defaultdict(list)
    for a in annotations:
        expected = '|'.join(a[k] for k in ('stage', 'block_index', 'base_task_id', 'raw_condition'))
        assert a['context_key'] == expected and a['image_id'] == a['base_task_id']
        assert a['building_id'] == images[a['image_id']]['building_id']
        assert truth(a['current20_member']) == (a['worker_id'] in CURRENT)
        for field in ('context_key', 'worker_id', 'stage', 'block_index', 'raw_condition', 'image_id', 'building_id'):
            assert a[field] == responses[a['canonical_annotation_id']][field]
        groups[expected].append(a)
    assert set(groups) == set(context_index)
    assert {a['image_id'] for a in annotations} == {k for k, v in images.items() if v['population_role'] == 'historical_annotated'}
    assert not any(v['room_instance_id'] for v in images.values())

    print('核对历史几何过滤与人数曲线；不改变原点序...', flush=True)
    old_records = unique(read_csv(preflight / 'record_inventory.csv'), 'canonical_annotation_id')
    assert set(old_records) == set(by_id)
    normalized, failures = {}, []
    for aid, points in selected_points.items():
        first = normalize_geometry(np.asarray(points).reshape(-1, 2))
        second = normalize_geometry(first['canonical_points']) if first['valid'] else first
        assert bool(second['valid']) == truth(old_records[aid]['valid']) == truth(strict_geometry[aid]['strict_valid'])
        if second['valid']:
            normalized[aid] = _dense_boundaries(second['pairs'])
        else:
            failures.append(dict(canonical_annotation_id=aid, context_key=by_id[aid]['context_key'],
                                 worker_id=by_id[aid]['worker_id'], reason=second['reason'],
                                 retained_in_identity_universe=True))
    write('strict_geometry_failures.csv', failures)
    old_tasks = unique(read_csv(preflight / 'task_inventory.csv'), 'context')
    matrices, task_checks = {}, []
    for context, rows in sorted(groups.items()):
        first = rows[0]
        workers = {r['worker_id'] for r in rows}
        assert len(workers) == len(rows)
        expected_n20 = len(workers & CURRENT)
        c = context_index[context]
        assert int(c['worker_count']) == int(c['response_count']) == len(workers)
        assert int(c['current20_worker_count']) == expected_n20
        old_context = '|'.join(first[k] for k in ('stage', 'block_index', 'raw_condition', 'base_task_id'))
        valid_rows = sorted([r for r in rows if r['canonical_annotation_id'] in normalized], key=lambda r: int(r['worker_id']))
        n = len(valid_rows)
        assert (old_context in old_tasks) == (n >= 2)
        if n >= 2:
            old = old_tasks[old_context]
            matrix = distance_matrix([normalized[r['canonical_annotation_id']] for r in valid_rows])
            matrices[old_context] = matrix
            assert int(old['n']) == n and int(old['n_raw']) == len(rows)
            assert int(old['n_current20']) == sum(r['worker_id'] in CURRENT for r in valid_rows)
            assert abs(float(old['D_mean']) - matrix.sum() / (n * (n - 1))) < 1e-10
        task_checks.append(dict(context_key=context, legacy_context=old_context,
                               image_id=first['image_id'], building_id=first['building_id'],
                               stage=first['stage'], block_index=first['block_index'], condition=first['raw_condition'],
                               raw_workers=len(rows), current20_workers=expected_n20, legacy_strict_workers=n,
                               legacy_task_inventory_present=old_context in old_tasks,
                               legacy_precision_coverage=n >= 20,
                               legacy_exclusion_reason='strict_support_lt2' if n < 2 else ('strict_support_lt20' if n < 20 else 'included')))
    write('context_denominator_audit.csv', task_checks)
    curves = read_csv(preflight / 'precision_curves_k_and_fraction.csv')
    curve_checks, seen = [], set()
    for r in curves:
        n, k = int(r['N']), int(r['k'])
        matrix = matrices[r['context']]
        assert len(matrix) == n and n >= 20 and 2 <= k <= n
        assert (r['context'], k) not in seen
        seen.add((r['context'], k))
        expected = math.sqrt(max(0.0, finite_variance_projection(matrix, k)))
        error = abs(expected - float(r['finite_sd']))
        assert error < 1e-8
        assert int(r['remaining']) == n-k
        if k == n:
            assert r['selected_medoid_to_remaining'] == '' and float(r['finite_sd']) == 0.0
        curve_checks.append(dict(legacy_context=r['context'], k=k, N=n, finite_sd=r['finite_sd'],
                                 independently_checked_sd=expected, absolute_error=error,
                                 full_roster_endpoint=k == n, role='finite_historical_roster_not_new_people'))
    assert seen == {(context, k) for context, matrix in matrices.items() if len(matrix) >= 20 for k in range(2, len(matrix)+1)}
    write('legacy_finite_curve_audit.csv', curve_checks)

    partitions = unique(read_csv(base / 'clusters/partitions.csv.gz'), 'partition_id')
    members = read_csv(base / 'clusters/memberships.csv.gz')
    member_groups = defaultdict(list)
    for member in members:
        member_groups[member['partition_id']].append(member)
    require_partition_coverage(partitions, member_groups)
    partition_checks = []
    for pid, p in partitions.items():
        roster, counts = [], Counter()
        for m in member_groups[pid]:
            if m['mapping_status'] == 'matched':
                response = by_id[m['canonical_annotation_id']]
                assert response['context_key'] == p['context_key']
                worker = response['worker_id']
                assert worker == m['worker_id']
            elif m['mapping_status'] == 'raw_version_only':
                v = by_version[m['raw_annotation_version_id']]
                assert not truth(v['selected_canonical_version']) and m['canonical_annotation_id'] == ''
                assert v['canonical_annotation_id'] == m['related_canonical_annotation_id']
                assert '|'.join(v[k] for k in ('stage', 'block_index', 'base_task_id', 'raw_condition')) == p['context_key']
                worker = v['worker_id']
            else:
                raise ValueError('Unresolved member: ' + repr(m))
            roster.append(worker)
            counts[m['cluster_id']] += 1
        assert len(roster) == len(set(roster)) == int(p['member_count'])
        assert len(counts) == int(p['cluster_count'])
        assert all(counts[m['cluster_id']] == int(m['cluster_support']) for m in member_groups[pid])
        partition_checks.append(dict(partition_id=pid, context_key=p['context_key'], version=p['version'],
                                     unique_workers=len(set(roster)), cluster_count=len(counts),
                                     reported_support=p['reported_support'], partition_status=p['partition_status'],
                                     has_saved_members=bool(roster),
                                     raw_version_only_members=sum(m['mapping_status']=='raw_version_only' for m in member_groups[pid]),
                                     top_support_tie=p['top_support_tie'], second_support_tie=p['second_support_tie']))
    write('partition_member_audit.csv', partition_checks)
    qa = dict(status='passed', raw_export_sources=len(source_indices), raw_versions=len(versions),
              canonical_responses=len(annotations), noncanonical_versions=len(versions)-len(selected),
              original_sequence_matches=len(source_checks), current_roster_in_historical_workers=len(CURRENT & {a['worker_id'] for a in annotations}),
              historical_images=len({a['image_id'] for a in annotations}), historical_buildings=len({a['building_id'] for a in annotations}),
              full_contexts=len(groups), legacy_task_contexts=len(old_tasks), legacy_strict_responses=len(normalized),
              strict_uncomputable_retained=len(failures), raw_support_ge20=sum(r['raw_workers']>=20 for r in task_checks),
              strict_support_ge20=sum(r['legacy_strict_workers']>=20 for r in task_checks),
              legacy_curve_rows_checked=len(curve_checks), max_finite_sd_error=max(r['absolute_error'] for r in curve_checks),
              mechanical_full_roster_endpoints=sum(r['full_roster_endpoint'] for r in curve_checks),
              legacy_partitions=len(partitions), legacy_member_records=len(members),
              partitions_without_members=sum(not r['has_saved_members'] for r in partition_checks),
              scope='重读既有底座所指原始来源；不重新选择canonical，不穷尽全部仓库外导出；几何引擎复用不等于视觉合法性确认；不计算新收敛阈值或新人模型。')
    (out / 'AUDIT_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return qa


def check_prepared(root, package):
    """不调用整理生成器，直接从事实表核验其派生数量、原评论和旧结果连接。"""
    base = root / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
    ready = root / 'analysis_results/uncertainty_decision_ready_20260908_v1'
    annotations = read_csv(base / 'annotations.csv.gz')
    images = unique(read_csv(base / 'images.csv'), 'image_id')
    groups = defaultdict(list)
    for row in annotations:
        groups[row['context_key']].append(row)
    coverage = unique(read_csv(package / 'building_image_context_coverage.csv'), 'context_key')
    assert set(coverage) == set(groups)
    for key, rows in groups.items():
        c = coverage[key]
        workers = {r['worker_id'] for r in rows}
        seen = {r['worker_id'] for r in annotations if r['image_id'] == c['image_id']}
        assert int(c['worker_count']) == int(c['response_count']) == len(rows) == len(workers)
        assert set(json.loads(c['worker_ids_json'])) == workers
        assert int(c['current20_worker_count']) == len(workers & CURRENT)
        assert set(json.loads(c['current20_worker_ids_json'])) == workers & CURRENT
        assert set(json.loads(c['canonical_annotation_ids_json'])) == {r['canonical_annotation_id'] for r in rows}
        assert int(c['max_equal_disjoint_k']) == len(workers)//2
        assert int(c['current20_no_record_same_image_count']) == len(CURRENT - seen)
        assert set(json.loads(c['current20_no_record_same_image_ids_json'])) == CURRENT - seen
        assert int(c['raw_geometry_computable_count']) == sum(truth(r['raw_geometry_computable']) for r in rows)
        for field in ('stage', 'block_index', 'image_id', 'building_id', 'raw_condition'):
            assert {r[field] for r in rows} == {c[field]}

    by_building = defaultdict(list)
    for row in annotations:
        by_building[row['building_id']].append(row)
    buildings = unique(read_csv(package / 'building_summary.csv'), 'building_id')
    assert set(buildings) == set(by_building)
    for key, rows in by_building.items():
        b = buildings[key]
        assert int(b['images']) == len({r['image_id'] for r in rows})
        assert int(b['contexts']) == len({r['context_key'] for r in rows})
        assert int(b['canonical_responses']) == len(rows)
        assert int(b['building_union_worker_count']) == len({r['worker_id'] for r in rows})
    panels = read_csv(package / 'building_stage_condition_support.csv')
    for panel in panels:
        subset = [r for r in coverage.values() if all(r[f] == panel[f] for f in ('building_id', 'stage', 'raw_condition'))]
        if panel['scope'] == 'raw_support_ge20_coverage_only':
            subset = [r for r in subset if int(r['worker_count']) >= 20]
        else:
            assert panel['scope'] == 'all_contexts'
        common = set.intersection(*[set(json.loads(r['worker_ids_json'])) for r in subset]) if subset else set()
        assert int(panel['contexts']) == len(subset)
        assert int(panel['images']) == len({r['image_id'] for r in subset})
        assert int(panel['all_context_common_worker_count']) == len(common)
        assert set(json.loads(panel['all_context_common_worker_ids_json'])) == common
        assert int(panel['all_context_common_max_equal_disjoint_k']) == len(common)//2
        assert int(panel['current20_all_context_common_count']) == len(common & CURRENT)
        assert int(panel['current20_all_context_common_max_equal_disjoint_k']) == len(common & CURRENT)//2
    candidates = unique(read_csv(package / 'candidate_images.csv'), 'image_id')
    assert set(candidates) == {k for k, r in images.items() if r['population_role'] == 'candidate_without_historical_annotation'}
    assert all(int(r['historical_response_count']) == int(r['historical_worker_count']) == 0 for r in candidates.values())
    assert all(truth(r['has_historical_building']) == (r['building_id'] in by_building) for r in candidates.values())
    arithmetic = read_csv(package / 'same_image_disjoint_group_arithmetic.csv')
    assert len(arithmetic) == len({(r['context_key'], r['k']) for r in arithmetic}) == 6 * len(groups)
    for row in arithmetic:
        n = len(groups[row['context_key']]); k = int(row['k'])
        assert 15 <= k <= 20 and int(row['historical_N']) == n
        assert truth(row['two_disjoint_equal_k_groups_supported']) == (n >= 2*k)
        assert int(row['additional_distinct_responses_needed_for_two_k']) == max(0, 2*k-n)

    cases = [json.loads(line) for line in (ready / 'semantics/case_evidence.jsonl').read_text(encoding='utf-8').splitlines()]
    comments = unique(read_csv(package / 'existing_human_comment_index.csv'), 'case_id')
    assert len(cases) == len(comments)
    for case in cases:
        c = comments[case['case_id']]
        answers = case['original_human_record']['answers']
        assert c['human_notes'] == answers.get('notes', '') and c['human_review_status'] == answers.get('status', '')
        assert json.loads(c['later_human_supplement_json']) == case.get('later_human_supplement')
        assert json.loads(c['final_user_decision_json']) == case.get('final_user_decision')
    portable = read_csv(package / 'existing_curves_context_links.csv.gz')
    cache = {}
    for row in portable:
        path = row['source_file']
        if path not in cache:
            cache[path] = read_csv(root / path)
        original = cache[path][int(row['source_row'])]
        copied = json.loads(row['original_row_json'])
        assert copied == {k: v for k, v in original.items() if k not in ('context_key', 'context_link_status')}
        if row['context_link_status'] == 'matched':
            c = coverage[row['context_key']]
            if original.get('context'):
                assert original['context'] == '|'.join(c[f] for f in ('stage', 'block_index', 'raw_condition', 'image_id'))
            if original.get('partition_id'):
                assert original['partition_id'] in json.loads(c['partition_ids_json'])
            for source, target in [('image', 'image_id'), ('image_id', 'image_id'), ('base_task_id', 'image_id'),
                                   ('stage', 'stage'), ('block_index', 'block_index'), ('condition', 'raw_condition'),
                                   ('raw_condition', 'raw_condition'), ('building', 'building_id'), ('building_id', 'building_id')]:
                if original.get(source):
                    assert original[source] == c[target]
        else:
            assert row['context_key'] == '' and row['context_link_status'] in ('ambiguous_context', 'unmatched_context')
    qa = dict(status='passed', context_rows=len(coverage), building_rows=len(buildings), panel_scope_rows=len(panels),
              candidate_rows=len(candidates), group_arithmetic_rows=len(arithmetic), human_comment_rows=len(comments),
              nonempty_original_comments=sum(bool(r['human_notes']) for r in comments.values()),
              portable_existing_rows=len(portable), portable_source_tables=len(cache),
              historical_two_disjoint_groups_at_k15_to20=sum(truth(r['two_disjoint_equal_k_groups_supported']) for r in arithmetic),
              validation='直接读取上游事实与原表核验；未调用整理生成器的数量或连接函数。')
    (package / 'audit/PREPARED_TABLE_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return qa


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check-prepared', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    out = args.out or root / 'analysis_results/building_convergence_preparation_20260908_v1/audit'
    if args.check_prepared:
        check_prepared(root, out.parent)
    else:
        audit(root, out)
