"""Prepare the audited key39 clustering evidence for non-visual Pro review.

No production clustering, raw annotations, assignment or user decisions are changed.
Run with an existing NumPy/SciPy environment; --check verifies the portable bundle.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import io
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).resolve().parents[3]
BASE = 'analysis_results/image_portrait_20260914_v1'
V2 = BASE + '/cloud/history_difficulty_review_20260915_v2/run_c0069628'
FOLLOW = BASE + '/cloud/image_links_after_review_20260915_v1/run_b02a97e2'
LOCAL = ROOT / BASE / 'local_review_studio/key39'
REVIEWS = ROOT / 'analysis_results/human_review_reconciliation_20260918'
OUT = ROOT / 'analysis_results/pro_cluster_review_20260918'
MODES = {'Manual': 'manual', 'Semi': 'semi', 'OOS': 'oos_geometry'}


def json_after(text, marker):
    assert text.count(marker) == 1, marker
    return json.JSONDecoder().raw_decode(text.split(marker, 1)[1])[0]


def partition(dm, pcs, cut):
    # Verification-only reproduction of history_difficulty_review_v2.cluster.
    dm, pcs = np.asarray(dm, float), np.asarray(pcs, int)
    labels = np.empty(len(pcs), int)
    offset = 0
    for pc in sorted(set(pcs)):
        ix = np.flatnonzero(pcs == pc)
        labs = np.ones(len(ix), int) if len(ix) < 2 else fcluster(
            linkage(squareform(dm[np.ix_(ix, ix)], checks=True), method='complete'),
            cut, criterion='distance')
        labels[ix] = labs + offset
        offset = int(labels[ix].max())
    return labels


def validate(bundle):
    assert bundle['schema'] == 'pro_cluster_review_key39_v1'
    cases = bundle['cases']
    assert len(cases) == len({c['image_id'] for c in cases}) == 39
    seen = set()
    total = valid_total = group_count = 0
    for case in cases:
        responses = {r['canonical_annotation_id']: r for r in case['responses']}
        assert len(responses) == len(case['responses'])
        assert not seen.intersection(responses)
        seen.update(responses)
        total += len(responses)
        assert case['reviews']['user_image_note'] and case['reviews']['peer_image_note']
        for response in responses.values():
            assert response['image_id'] == case['image_id']
            assert response['raw_export_check']['status'] == 'matched_identity_and_points'
            assert len(response['raw_points_1024x512']) == response['raw_point_count']
        for group in case['groups']:
            ids, workers, pcs = group['canonical_ids'], group['workers'], group['point_counts']
            n = len(ids)
            assert n == len(set(ids)) == len(set(workers)) == len(pcs)
            dm = np.asarray(group['distance_matrix'], float).reshape(n, n)
            assert np.isfinite(dm).all() and np.allclose(dm, dm.T, atol=0, rtol=0)
            assert np.all(np.diag(dm) == 0)
            assert np.all((dm >= 0) & (dm <= 2))
            for k, cid in enumerate(ids):
                r = responses[cid]
                assert r['worker_id'] == workers[k] and r['worker_id'] not in ('W019', 'W026')
                assert r['analysis_audit']['valid'] == 'True'
                assert len(r['effective_points_1024x512']) == pcs[k]
                assert r['analysis_audit']['condition'] == group['condition']
                for j in range(k):
                    assert (pcs[k] == pcs[j] and dm[k, j] <= 1) or (pcs[k] != pcs[j] and dm[k, j] == 2)
            reproduced = partition(dm, pcs, .1)
            expected = {frozenset(c['canonical_ids']) for c in group['display_clusters']}
            actual = {frozenset(ids[k] for k in range(n) if reproduced[k] == label) for label in set(reproduced)}
            assert actual == expected, (case['code'], group['condition'], 'display partition mismatch')
            assert [c['display_index'] for c in group['display_clusters']] == list(range(1, len(expected) + 1))
            valid_total += n
            group_count += 1
    assert (total, valid_total, group_count) == (843, 781, 45), (total, valid_total, group_count)
    assert sum(len(c['historical_evidence']['questions']) for c in cases) == 44
    assert len(bundle['selection_resolution']['high_history_images']) == 22
    assert all(r['current_recommendation'] == 'reuse_history_no_default_new_assignment'
               for r in bundle['selection_resolution']['high_history_images'])
    selection = bundle['selection_resolution']['candidate_review_77']
    assert len(selection) == len({r['image_id'] for r in selection}) == 77
    high = [r for r in selection if r['current_recommendation'] == 'reuse_high_history_no_default_new_assignment']
    required = [r for r in selection if r['current_recommendation'] == 'await_existing_required_results_no_round_number_topup']
    sparse = [r for r in selection if r['current_recommendation'] == 'review_sparse_view_need_and_common_people_before_assignment']
    assert (len(high), len(required), len(sparse)) == (22, 5, 50)
    assert all(r['new_approved_quantity'] is None for r in selection)
    assert all(r['history_manual'] + r['planned'] == 19 and r['gap'] == 1 for r in required)
    assert all(0 <= r['history_manual'] <= 7 and r['planned'] == 0 and r['adopted'] for r in sparse)
    return dict(images=39, displayed_responses=total, clustered_responses=valid_total,
                image_conditions=group_count, original_questions=44,
                primary_partition_parity='all_45_match_display', raw_export_checks='all_843_match')


def prepare(ref):
    resolved = subprocess.run(['git', 'rev-parse', ref], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    sources = []

    def blob(path):
        data = subprocess.run(['git', 'show', resolved + ':' + path], cwd=ROOT, check=True, capture_output=True).stdout
        sources.append({'path': path, 'bytes': len(data)})
        return data

    def table(path):
        data = blob(path)
        if path.endswith('.gz'):
            data = gzip.decompress(data)
        return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))

    user = json.loads((REVIEWS / '用户_39图文字审核_原始.json').read_text(encoding='utf-8-sig'))
    peer = json.loads((REVIEWS / '一正_39图审核_原始.json').read_text(encoding='utf-8-sig'))
    adoption = json.loads((REVIEWS / '用户_11图采集采用_原始.json').read_text(encoding='utf-8-sig'))
    notes = [{r['image_id']: r['note'] for r in x['image_notes']} for x in (user, peer)]
    evidence = json.loads((ROOT / BASE / 'review_workflow_20260915/key39/review_evidence.json').read_text(encoding='utf-8'))
    studio = json_after((LOCAL / 'data.js').read_text(encoding='utf-8'), 'window.STUDIO_DATA=')
    image_ids = {c['image_id'] for c in studio['cases']}
    assert image_ids == notes[0].keys() == notes[1].keys() == {c['image_id'] for c in evidence['rows']}
    raw = {r['canonical_annotation_id']: r for r in map(json.loads, gzip.decompress(blob(BASE + '/human/responses.jsonl.gz')).decode('utf-8').splitlines())}
    audits = {r['canonical_annotation_id']: r for r in table(FOLLOW + '/inputs/response_audit.csv.gz')}
    index = json.loads(blob(FOLLOW + '/inputs/group_index.json'))
    cache = np.load(io.BytesIO(blob(FOLLOW + '/inputs/pairwise_geometry.npz')), allow_pickle=False)
    effective = json.loads(blob(FOLLOW + '/inputs/effective_points.json'))
    membership = [r for r in table(V2 + '/structure/real_mode_memberships.csv.gz') if r['image_id'] in image_ids and float(r['cut']) == .1]
    membership += [r for r in table(FOLLOW + '/oos/mode_memberships.csv') if r['image_id'] in image_ids]
    static = [r for r in table(V2 + '/structure/per_image_all_cuts.csv') if r['image_id'] in image_ids]
    static += [r for r in table(FOLLOW + '/oos/static_all_cuts.csv') if r['image_id'] in image_ids]
    keys = {(r['image_id'], r['condition']): r for r in index}
    review_report = (REVIEWS / '审核对照与选图处理说明.md').read_text(encoding='utf-8')
    comparisons = dict(re.findall(r'^### \d{2}\. ([^\n]+).*?\*\*比较与处理建议：\*\*([^\n]+)', review_report, re.M | re.S))
    assert len(comparisons) == 39
    exports = {}
    cases = []
    keep = ('canonical_annotation_id', 'annotation_identity', 'image_id', 'worker_id', 'raw_condition',
            'assistance_exposure', 'stage', 'context_key', 'raw_export_path', 'coordinate_width', 'coordinate_height',
            'raw_points_1024x512', 'effective_points_1024x512', 'raw_point_count', 'effective_point_count',
            'processing_status', 'calculation_included', 'exclusion_reason', 'confirmation_source',
            'imputed_point', 'review_decision', 'main_worker_included')
    for case in studio['cases']:
        iid = case['image_id']
        ev = next(r for r in evidence['rows'] if r['image_id'] == iid)
        code = f"{ev['building']}-{ev['number']:02d}"
        text = (LOCAL / case['history_script']).read_text(encoding='utf-8')
        payload = json.JSONDecoder().raw_decode(text.split(',', 1)[1])[0]
        responses = []
        for v in payload['variants']:
            s = v['source']; cid = s['canonical_annotation_id']; r = raw[cid]
            assert r['image_id'] == iid and r['worker_id'] == f"W{int(s['worker_id']):03d}"
            assert s['raw_points'] == r['raw_points_1024x512'] and s['effective_points'] == r['effective_points_1024x512']
            path = ROOT / s['path']
            if str(path) not in exports:
                tasks = json.loads(path.read_text(encoding='utf-8-sig'))
                assert isinstance(tasks, list), path
                exports[str(path)] = {(str(t['id']), str(a['id'])): a for t in tasks for a in t.get('annotations', [])}
            ann = exports[str(path)][str(s['task_id']), str(s['annotation_id'])]
            owner = ann['completed_by']; owner = owner['id'] if isinstance(owner, dict) else owner
            assert int(owner) == int(s['worker_id']), cid
            point_results = [x for x in ann['result'] if x['type'] == 'keypointlabels']
            points = [[x['value']['x'] * 1024 / 100, x['value']['y'] * 512 / 100] for x in point_results]
            assert np.asarray(points).shape == np.asarray(s['raw_points']).shape and np.allclose(points, s['raw_points'], atol=1e-8, rtol=0), cid
            response = {k: r[k] for k in keep}
            response['analysis_audit'] = audits[cid]
            response['display_error'] = v.get('error')
            response['raw_export_check'] = {'status': 'matched_identity_and_points', 'path': s['path'],
                'task_id': s['task_id'], 'annotation_id': s['annotation_id'],
                'point_result_ids': [x['id'] for x in point_results],
                'out_of_range_point_indices_zero_based': [k for k, (x, y) in enumerate(points) if not (0 <= x <= 1024 and 0 <= y < 512)]}
            responses.append(response)
        groups = []
        for mode, condition in MODES.items():
            candidates = payload['history']['partitions'][mode]['candidates']
            if not candidates:
                assert (iid, condition) not in keys or keys[iid, condition]['n_valid'] == 0
                continue
            assert len(candidates) == 1
            meta = keys[iid, condition]; key = meta['key']
            ids = cache[key + '_ids'].tolist(); workers = cache[key + '_workers'].tolist()
            pcs = cache[key + '_pcs'].tolist(); dm = cache[key + '_dm'].tolist()
            clusters = []
            for j, indices in enumerate(candidates[0], 1):
                members = [payload['variants'][k]['source']['canonical_annotation_id'] for k in indices]
                old_labels = {r['cluster'] for r in membership if r['image_id'] == iid and r['condition'] == condition and r['canonical_annotation_id'] in members}
                assert len(old_labels) == 1
                expected = {r['canonical_annotation_id'] for r in membership if r['image_id'] == iid and r['condition'] == condition and r['cluster'] in old_labels}
                assert expected == set(members)
                clusters.append({'display_index': j, 'display_title': f'簇 {j} · {len(members)}人' if len(members) >= 2 else '单人标法 · 1人',
                                 'source_cluster_label': next(iter(old_labels)), 'canonical_ids': members,
                                 'workers': [raw[c]['worker_id'] for c in members]})
            for cid in ids:
                assert raw[cid]['effective_points_1024x512'] == effective[cid]
            groups.append({'condition': condition, 'cache_group_key': key, 'observed_count': meta['n_observed'],
                'excluded_count': meta['n_excluded'], 'canonical_ids': ids, 'workers': workers, 'point_counts': pcs,
                'distance_matrix': dm, 'display_clusters': clusters,
                'historical_static_sensitivity': [r for r in static if r['image_id'] == iid and r['condition'] == condition]})
        cases.append({'image_id': iid, 'code': code, 'image_path_reference_only': ev['image_path'],
            'scene': ev['scene'], 'historical_evidence': ev, 'responses': responses, 'groups': groups,
            'reviews': {'user_image_note': notes[0][iid], 'peer_image_note': notes[1][iid],
                'user_condition_records': [r for r in user['reviews'] if r['image_id'] == iid],
                'peer_condition_records': [r for r in peer['reviews'] if r['image_id'] == iid],
                'assistant_text_comparison_not_visual_adjudication': comparisons[code],
                'final_scope_adjudication': None, 'final_difficulty_adjudication': None}})
    source_paths = ['tools/thesis_main/analysis/image_portrait/' + x for x in (
        'history_difficulty_review_v2.py', 'history_difficulty_v1_people.py', 'image_links_followup_prepare.py', 'review_handoff.py')]
    source_paths += ['tools/thesis_main/analysis/geometry_consensus/representation.py',
                     'tools/thesis_main/analysis/geometry_consensus/pairwise.py',
                     'tools/thesis_main/analysis/quality_core/geometry_metrics.py',
                     'tools/thesis_main/analysis/analyze_q_thresholds_20260909.py',
                     'tools/thesis_main/analysis/geometry_cluster_v2.py']
    code_sources = {p: blob(p).decode('utf-8-sig') for p in source_paths}
    code_sources['local_key39/history.js'] = (LOCAL / 'history.js').read_text(encoding='utf-8')
    plan = json.loads((ROOT / 'analysis_results/full_history_coverage_20260916/全历史覆盖机器表.json').read_text(encoding='utf-8-sig'))
    selected = [{k: r[k] for k in ('image_id', 'code', 'history_manual', 'planned', 'gap', 'adopted', 'new_proposed')} |
                {'current_recommendation': 'reuse_history_no_default_new_assignment'} for r in plan['images'] if r['core']]
    selection_review = []
    for r in plan['images']:
        if not r['new_proposed']:
            continue
        if r['core']:
            action = 'reuse_high_history_no_default_new_assignment'
        elif r['planned']:
            action = 'await_existing_required_results_no_round_number_topup'
        else:
            action = 'review_sparse_view_need_and_common_people_before_assignment'
        selection_review.append({k: r[k] for k in ('image_id', 'code', 'room', 'history_manual',
            'planned', 'target', 'gap', 'new_proposed', 'adopted', 'oos')} |
            {'current_recommendation': action, 'new_approved_quantity': None})
    assert len(selection_review) == 77
    assert sum(r['gap'] for r in plan['images']) == 592
    bundle = {'schema': 'pro_cluster_review_key39_v1', 'created_date': '2026-09-18',
        'source': {'branch_reference': ref, 'resolved_revision': resolved, 'git_files': sources,
                   'local_ui': str(LOCAL.relative_to(ROOT)), 'raw_export_files_checked': len(exports)},
        'method': {'actual_ui_method': 'equal_point_count_then_complete_linkage_dmask', 'primary_distance_cut': .1,
                   'distance_definition': '1 - IoU of integer-sampled periodic ceiling-to-floor masks; 1024x512',
                   'different_point_count_distance_sentinel': 2, 'minimum_people_for_supported_cluster': 2,
                   'legacy_q_boundary_q_wallwall_095_is_not_this_ui_method': True,
                   'cluster_does_not_imply_semantic_validity_or_convergence': True},
        'review_provenance': {'user': {k: user[k] for k in ('schema','saved_at','source_v1','source_v2')},
                             'peer': {k: peer[k] for k in ('schema','saved_at','source_v1','source_v2')},
                             'image_level_notes_do_not_assign_mode_specific_grades': True},
        'cases': cases, 'source_code_snapshots': code_sources,
        'selection_resolution': {'old_total_922_is_not_current_assignment': True, 'new_assignment_total': None,
            'required_480_progress': 'unverified_user_confirmed_20260918',
            'current_user_instruction': '完成进度尚未核实，先整理候选',
            'high_history_images': selected, 'candidate_review_77': selection_review,
            'historical_11_review': adoption,
            'current_11_status': 'all_pending_new_collection_necessity_not_final_adoption'},
        'limitations': ['No image bytes or new visual judgments.', '39 images are selected review cases, not a representative validation sample.',
            'Human notes are post-hoc and include disagreements; not a ground-truth partition.',
            'Invalid/excluded responses remain in responses and are not assigned a cluster.',
            'OOS task lane, worker scope response, and researcher scope judgment are separate.',
            'Legacy difficulty choices in raw annotations are deliberately not exported as research labels.',
            'Source snapshots document the method; their research entrypoints must not be automatically executed.']}
    bundle['validation'] = validate(bundle)
    serial = json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert 'data:image/' not in json.dumps(cases, ensure_ascii=False)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'data.json').write_text(serial, encoding='utf-8', newline='\n')
    print(json.dumps(bundle['validation'], ensure_ascii=False))
    print('Raw export files:', len(exports), 'Bytes:', len(serial.encode('utf-8')))



def export_delta(old_tasks, new_tasks):
    """Compare source results only; never replace the historical computation view."""
    def index(tasks):
        result = {}
        for t in tasks:
            for a in t['annotations']:
                key = (t['id'], a['id'])
                if key in result:
                    raise ValueError('Duplicate annotation identity')
                result[key] = a
        return result
    old, new = index(old_tasks), index(new_tasks)
    if old.keys() != new.keys():
        raise ValueError('Annotation identities added or deleted')
    changes = []
    for key, a in old.items():
        b = new[key]
        owner = lambda x: x['completed_by']['id'] if isinstance(x['completed_by'], dict) else x['completed_by']
        if owner(a) != owner(b):
            raise ValueError('Annotation owner changed')
        if a['result'] == b['result']:
            continue
        ap = {r['id']: r for r in a['result'] if r['type'] == 'keypointlabels'}
        bp = {r['id']: r for r in b['result'] if r['type'] == 'keypointlabels'}
        added, removed = sorted(bp.keys() - ap.keys()), sorted(ap.keys() - bp.keys())
        changed = sorted(k for k in ap.keys() & bp.keys() if ap[k] != bp[k])
        nonpoints_same = [r for r in a['result'] if r['type'] != 'keypointlabels'] == [r for r in b['result'] if r['type'] != 'keypointlabels']
        only_coordinates = not added and not removed and bool(changed) and nonpoints_same
        for k in changed:
            ac, bc = json.loads(json.dumps(ap[k])), json.loads(json.dumps(bp[k]))
            for axis in ('x', 'y'):
                ac['value'].pop(axis); bc['value'].pop(axis)
            only_coordinates &= ac == bc
        kind = 'coordinate_correction' if only_coordinates else 'point_deletion' if removed and not added and not changed and nonpoints_same else 'other_result_change'
        points = lambda rs: [[r['value']['x'] * 10.24, r['value']['y'] * 5.12] for r in rs if r['type'] == 'keypointlabels']
        changes.append(dict(task_id=key[0], annotation_id=key[1], worker_id=f'W{int(owner(a)):03d}',
            kind=kind, old_point_count=len(ap), new_point_count=len(bp),
            added_point_result_ids=added, removed_point_result_ids=removed, changed_point_result_ids=changed,
            old_result=a['result'], new_result=b['result'], new_raw_points_1024x512=points(b['result']),
            updated_at=b.get('updated_at'), applied_to_geometry=False))
    return dict(schema='pending_export_update_v1', task_count=len(new_tasks), annotation_count=len(new),
                applied_to_geometry=False, status='pending_method_decision_no_recompute', changes=changes)


def enrich(bundle, visual, delta):
    # Additive annotation only: old results and matrices must remain byte-equivalent as JSON values.
    lookup = {v['image_id']: v for v in visual}
    if len(visual) != 39 or len(lookup) != 39 or lookup.keys() != {c['image_id'] for c in bundle['cases']}:
        raise ValueError('Visual coverage must match all 39 unique images')
    result = json.loads(json.dumps(bundle, ensure_ascii=False, allow_nan=False))
    for case in result['cases']:
        v = lookup[case['image_id']]
        if v['code'] != case['code'] or v['original_viewed'] is not True or not v['observations']:
            raise ValueError('Visual identity/coverage mismatch')
        case['visual_review'] = v
        case['adjudication_issues'] = []
        responses = {r['worker_id'] for r in case['responses']}
        for i, issue in enumerate(v['issues'], 1):
            if issue['condition'] not in ('image', 'manual', 'semi', 'oos_geometry'):
                raise ValueError('Unknown issue condition')
            allowed_workers = responses if issue['condition'] == 'image' else {r['worker_id'] for r in case['responses'] if r['analysis_audit']['condition'] == issue['condition']}
            if not set(issue['workers']).issubset(allowed_workers):
                raise ValueError('Unknown issue worker: ' + case['code'])
            if len(issue['options']) < 2 or len(set(issue['options'])) != len(issue['options']):
                raise ValueError('Invalid issue choices')
            case['adjudication_issues'].append(dict(issue, issue_id=case['image_id'] + ':' + str(i)))
    result['pending_export_update'] = delta
    result['review_extension_schema'] = 'key39_visual_adjudication_evidence_v1'
    if 'research_clarification' not in result:
        result['research_request'] = dict(
            point_count_policy='historical_partition_rule_not_a_final_research_constraint',
            method_freedom='Open exploration of representation, scale, distance, grouping and non-clustering alternatives.',
            freeze='Historical geometry and partitions remain unchanged.')
    result['limitations'] = [x for x in result['limitations'] if x != 'No image bytes or new visual judgments.']
    result['limitations'] = list(dict.fromkeys(result['limitations'] + ['No image bytes. Actual visual observations are preliminary; final adjudications remain with the user.']))
    return result


def supplement(new_export):
    import shutil
    original = json.loads((OUT / 'data.json').read_text(encoding='utf-8'))
    visual = []
    for name in ('visual_first20.json', 'visual_last19.json'):
        visual.extend(json.loads((REVIEWS / name).read_text(encoding='utf-8-sig')))
    old_path = ROOT / 'analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-28-at-2026-07-01-07-14-56a198ba.json'
    delta = export_delta(json.loads(old_path.read_text(encoding='utf-8-sig')),
                         json.loads(Path(new_export).read_text(encoding='utf-8-sig')))
    if {(c['task_id'], c['annotation_id'], c['kind'], c['old_point_count'], c['new_point_count']) for c in delta['changes']} != {
            (3081, 4738, 'coordinate_correction', 28, 28), (3081, 4784, 'point_deletion', 21, 20)}:
        raise ValueError('Unexpected export differences; inspect before proceeding')
    delta.update(old_export_reference=str(old_path.relative_to(ROOT)), new_export_reference=str(new_export))
    response_lookup = {(r['raw_export_check']['task_id'], r['raw_export_check']['annotation_id']): (c, r)
                       for c in original['cases'] for r in c['responses']}
    for change in delta['changes']:
        case, r = response_lookup[(str(change['task_id']), str(change['annotation_id']))]
        old_points = [[x['value']['x'] * 10.24, x['value']['y'] * 5.12] for x in change['old_result'] if x['type'] == 'keypointlabels']
        if not np.allclose(old_points, r['raw_points_1024x512'], atol=1e-8, rtol=0):
            raise ValueError('Pending delta does not match frozen raw points')
        if not all(0 <= x <= 1024 and 0 <= y < 512 for x, y in change['new_raw_points_1024x512']):
            raise ValueError('Corrected export still contains out-of-range points')
        change.update(image_id=case['image_id'], code=case['code'], stage=r['stage'],
                      canonical_annotation_id=r['canonical_annotation_id'])
    enriched = enrich(original, visual, delta)
    for before, after in zip(original['cases'], enriched['cases']):
        assert before['responses'] == after['responses'] and before['groups'] == after['groups'] and before['reviews'] == after['reviews']
    cases = []
    for c in enriched['cases']:
        odd = []
        for r in c['responses']:
            # Only unresolved odd records, including a pending correction explicitly distinguished from the old snapshot.
            pts = r['effective_points_1024x512']
            if pts is None or len(pts) % 2 == 0:
                continue
            pending = next((x for x in delta['changes'] if x['canonical_annotation_id'] == r['canonical_annotation_id']), None)
            odd.append(dict(canonical_annotation_id=r['canonical_annotation_id'], worker_id=r['worker_id'],
                annotation_identity=r['annotation_identity'], stage=r['stage'], raw_export_reference=r['raw_export_check'],
                condition=r['analysis_audit']['condition'], raw_point_count=r['raw_point_count'],
                raw_points=r['raw_points_1024x512'], effective_points=pts,
                processing_status=r['processing_status'], pending_update=pending,
                point_result_ids=r['raw_export_check']['point_result_ids']))
        cases.append(dict(image_id=c['image_id'], code=c['code'], image_path=c['image_path_reference_only'],
            reviews=c['reviews'], visual=c['visual_review'], issues=c['adjudication_issues'], odd_records=odd))
    ui = dict(schema='key39_visual_adjudication_evidence_v1', source_v2=enriched['review_provenance']['user']['source_v2'],
              cases=cases, pending_export_update=delta)
    serial = lambda value: json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (OUT / 'data.json').write_text(serial(enriched), encoding='utf-8', newline='\n')
    (REVIEWS / '39图裁决依据.json').write_text(serial(ui), encoding='utf-8', newline='\n')
    (LOCAL / 'adjudication-data.js').write_text('window.KEY39_ADJUDICATION=' + serial(ui).rstrip() + ';\n', encoding='utf-8', newline='\n')
    shutil.copyfile(Path(__file__).with_name('key39_adjudication.js'), LOCAL / 'adjudication.js')
    page = LOCAL / 'index.html'
    html = page.read_text(encoding='utf-8')
    if 'src="adjudication.js"' not in html:
        html = html.replace('</body>', '<script defer src="adjudication-data.js"></script>\n<script defer src="adjudication.js"></script>\n</body>')
        page.write_text(html, encoding='utf-8', newline='\n')
    report = ['# 39图视觉核查与用户裁决入口', '',
        '[打开原39图审核页](../image_portrait_20260914_v1/local_review_studio/key39/index.html)', '',
        '两个子智能体已实际查看全部39张原图；以下观察不是最终裁决。旧点集、分簇、距离和收敛结果未重算。', '',
        '页面默认争议优先，可切换全部39图。双方原文、原有选项、视觉意见和最终裁决分别保留。', '',
        '新导出两项差异仅作为待应用记录：P1/Project28/task3081，W002/4738坐标更正28→28；W018/4784删点21→20。', '']
    for c in cases:
        v=c['visual']
        report += ['## ' + c['code'], '', '**用户原文：**' + c['reviews']['user_image_note'], '',
            '**一正原文：**' + c['reviews']['peer_image_note'], '', '**视觉观察：**' + v['observations'], '',
            '**核查范围：**原图已看；叠加：' + json.dumps(v['overlay_coverage'], ensure_ascii=False), '',
            '**限制：**' + v['limits'], '']
        for issue in c['issues']:
            report += ['- 待裁决：' + issue['question'] + '（位置：' + issue['location'] + '）']
        report += ['']
    (REVIEWS / '39图视觉复核与裁决说明.md').write_text('\n'.join(line.rstrip() for line in report), encoding='utf-8', newline='\n')
    print(json.dumps(dict(images=len(cases), issues=sum(len(c['issues']) for c in cases),
         odd_records=sum(len(c['odd_records']) for c in cases), pending_changes=len(delta['changes']),
         historical_geometry_unchanged=True), ensure_ascii=False))



def incorporate_user_review(bundle, review, context):
    """Preserve source wording; interpretation cannot silently become an exclusion rule."""
    if review['schema'] != 'key39_user_adjudication_v1' or review['source_v2'] != bundle['review_provenance']['user']['source_v2']:
        raise ValueError('Review source mismatch')
    expected = {q['issue_id']: (c['image_id'], q['condition'], q['options'])
                for c in bundle['cases'] for q in c['adjudication_issues']}
    seen = set()
    for r in review['decisions']:
        key = r['issue_id']
        if key in seen or key not in expected or (r['image_id'], r['condition']) != expected[key][:2]:
            raise ValueError('Review identity mismatch or duplicate')
        if r['answer'] not in ['', '暂缓', '其他判断', *expected[key][2]] or not isinstance(r['note'], str):
            raise ValueError('Invalid review answer')
        seen.add(key)
    if seen != expected.keys():
        raise ValueError('Incomplete review identities')
    responses = {r['canonical_annotation_id']: (c['image_id'], r)
                 for c in bundle['cases'] for r in c['responses']}
    seen_points = set()
    for d in review['point_decisions']:
        cid = d['canonical_annotation_id']
        if cid in seen_points or cid not in responses:
            raise ValueError('Point review identity mismatch')
        iid, r = responses[cid]
        if (d['image_id'], d['worker_id'], d['condition']) != (iid, r['worker_id'], r['analysis_audit']['condition']):
            raise ValueError('Point review identity mismatch')
        seen_points.add(cid)
    result = json.loads(json.dumps(bundle, ensure_ascii=False, allow_nan=False))
    result['user_review_original'] = json.loads(json.dumps(review, ensure_ascii=False))
    result['research_clarification'] = context
    result['research_request'] = dict(
        objective=context['agreed_research_object'],
        point_count_policy=context['point_count_policy'],
        method_freedom=context['method_freedom'],
        research_value=context['research_value'],
        unmentioned_cases=context['unmentioned_cases'],
        directions_not_exhaustive=['大致覆盖范围与结构表达、局部定位的联系和区别',
            'B6-22拥挤角点与图片级/局部尺度适应；周期接缝及点对应',
            'W037等跨图重复行为、人员构成与图片条件的联系',
            'OOS、错误、少数与单人作答的分布；稳定不等于正确',
            '新标法出现、比例稳定、局部波动与质量收益的不同过程'],
        freeze=context['freeze'])
    for c in result['cases']:
        c['user_adjudications'] = [r for r in review['decisions'] if r['image_id'] == c['image_id']]
        c['user_point_review'] = [r for r in review['point_decisions'] if r['image_id'] == c['image_id']]
        c['adjudication_interpretation'] = '规范偏好与研究价值分开；不作为排除其他标法、OOS或人员的指令。未评论不表示通过审核。'
    result['review_ingestion'] = dict(schema='key39_research_review_ingestion_v1',
        answers=len(review['decisions']), deferred=sum(r['answer']=='暂缓' for r in review['decisions']),
        point_records=len(review['point_decisions']), confirmed_point_records=sum(r['confirmed'] for r in review['point_decisions']),
        confirmed_repairs_applied=0, geometry_recomputed=False,
        source_archive='../human_review_reconciliation_20260918/用户_39图最终裁决_原始.json')
    for old, new in zip(bundle['cases'], result['cases']):
        for key in ('responses', 'groups', 'reviews'):
            assert old[key] == new[key]
    assert result['pending_export_update'] == bundle['pending_export_update']
    return result


def import_adjudication(path):
    source = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    context = json.loads((OUT / '研究对象澄清_用户原话.json').read_text(encoding='utf-8'))
    bundle = json.loads((OUT / 'data.json').read_text(encoding='utf-8'))
    result = incorporate_user_review(bundle, source, context)
    (OUT / 'data.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    lines = ['# 用户最新裁决与重点研究案例', '',
        '用户原话优先；选项表示规范偏好，不是研究排除。原始39图文字、一正意见和视觉意见仍在data.json各案例中。', '',
        '26项回答，4项暂缓；8份点复核尚无已确认修复。未提及图片不是无问题对照。', '']
    for c in result['cases']:
        lines += ['## '+c['code'], '', '用户此前图级原话：'+c['reviews']['user_image_note'], '']
        for r in c['user_adjudications']:
            q=next(q for q in c['adjudication_issues'] if q['issue_id']==r['issue_id'])
            lines += ['- 问题：'+q['question'], '  条件／位置：'+r['condition']+' / '+q['location'],
                      '  选择：'+r['answer'], '  **用户补充原文：**'+(r['note'] or '（空白，不推断）'), '']
        for r in c['user_point_review']:
            if r['reason']:
                lines += ['点复核原话（confirmed='+str(r['confirmed'])+'）：'+r['reason'], '']
    lines += ['## 额外优先线索（助手整理，不替代原话）', '',
        '- B6-22：角点拥挤、上下点x未对齐、尺度适应。原话“1,2,30,34”的指代保留，不凭数字自动推定为簇号。',
        '- uNb-40：左右接缝与拥挤点；uNb-45、X7-19：凸起尖端与连接墙体处是否都表达。',
        '- e9-16：第三对bottom y及W032向下一层想象平面延伸的用户解释。',
        '- rPc-15/20、wc-67：用户对W037反复增加细节的观察；wc-60另保留其具体作答评论，不自动归为同一人。',
        '- uNb-36/52/63、Uw-06/23：OOS、信息缺失和人为截止所造成的范围问题。',
        '- B6-11左右截止、q9-32多范围、wc-59透玻璃、yq-34略微越过门口也保留。',
        '- wc-67“按照簇1的第4对点补充”是待精确匹配的文字意见，不据此自动生成坐标。', '',
        '本索引不是穷举问题列表，也不是新方法训练标签或独立验证集。']
    (OUT / '用户裁决与重点案例.md').write_text('\n'.join(line.rstrip() for line in lines)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result['review_ingestion'], ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-ref', default='codex/image-portrait-20260914')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--supplement-export', help='Append visual review and a pending export delta without recomputing geometry')
    parser.add_argument('--adjudication', help='Import original user review without changing historical results')
    args = parser.parse_args()
    if args.adjudication:
        import_adjudication(args.adjudication)
    elif args.supplement_export:
        supplement(args.supplement_export)
    elif args.check:
        print(json.dumps(validate(json.loads((OUT / 'data.json').read_text(encoding='utf-8'))), ensure_ascii=False))
    else:
        prepare(args.source_ref)


if __name__ == '__main__':
    main()
