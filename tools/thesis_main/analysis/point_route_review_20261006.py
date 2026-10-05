"""Separate correspondence evidence, observed orders and exploratory x closure.

No new correspondence threshold, forced pairing, largest branch selection or GT use.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from .lee_tile_stage1_20261002 import ROOT, write_json
from .point_route_panel_20261005 import (build_routes, construct_panel, evaluate_panel, audit_outputs,
                                         paired_identity, member_key, INPUT)
from .paired_split_research.study import angular
from .research_round_20260929 import reconstruct
from .union_branch_consensus_20260926 import _ring_key

OUT = ROOT/'analysis_results/point_route_review_20261006'
HUMAN_REVIEW = ROOT/'research/point_route_review_20261006/human_review.json'
AUDIT_CONTRACT = dict(
    human_review='Published copy of the research human-review source; audit stage regenerates this copy. Verbatim statements and corrections are retained. No formal gold, source-label or eligibility changes.',
    human_review_source='research/point_route_review_20261006/human_review.json stores explicit chat judgments; analysis_results copy is published output. relation is same_corner_pair or different_upper_targets; different_upper_target_indices indexes the three listed observations. No formal gold or source annotation changes.',
    correspondence_audit='One row per reviewed case/threshold/route/group side. Local feasibility uses only the listed observations and the route metric, not physical validity or majority support. Merge conflicts concern existing whole groups; they do not reconstruct merge history or exclude a different partition. Upper-target mixing is not a judgment that bottom identity is wrong.',
    human_correspondence_checks='Reproducible 50-row subset for the two same-corner triples. matching_groups contains a group only if it contains every listed member; selected retains the unchanged full-pool vote threshold. Rejected rpc combination substitutes only the old purple observation.')


def probe_correspondence(groups, keys, metric, threshold, minimum):
    """Explain a saved partition without changing identities, votes, or its input geometry."""
    membership = {member_key(m): (g, m) for g in groups for m in g['members']}
    target = [membership[tuple(key)] for key in keys]
    selected_groups = list({g['feature_id']: g for g, _ in target}.values())

    def distances(members):
        p = np.asarray([m['points'] for m in members], float)
        top = angular(p[:, 0]-.5, p[:, 0]-.5)
        bottom = angular(p[:, 1]-.5, p[:, 1]-.5)
        return dict(top=top, bottom=bottom, pair=np.maximum(top, bottom))

    local = distances([m for _, m in target])
    members = [m for g in selected_groups for m in g['members']]
    union = distances(members)[metric]
    left, right = np.unravel_index(int(np.argmax(union)), union.shape)
    workers = defaultdict(list)
    for m in members:
        workers[str(m['worker'])].append(member_key(m))
    return dict(member_group_ids=[g['feature_id'] for g, _ in target],
        same_group=len(selected_groups) == 1,
        diameters_deg={side: float(d.max()) for side, d in local.items()},
        local_group_feasible=bool(local[metric].max() <= threshold and
                                  len({m['worker'] for _, m in target}) == len(target)),
        target_groups=[dict(feature_id=g['feature_id'], support=g['support'], selected=g['support'] >= minimum)
                       for g in selected_groups],
        same_worker_merge_conflicts=[dict(worker=w, members=ms) for w, ms in sorted(workers.items()) if len(ms) > 1],
        whole_group_merge_diameter_deg=float(union.max()),
        whole_group_merge_exceeds_threshold=bool(union.max() > threshold),
        whole_group_diameter_witness=[member_key(members[left]), member_key(members[right])])


def audit_correspondences(out):
    """Post-construction development audit; human judgments never enter clustering."""
    panel = json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    human = json.loads(HUMAN_REVIEW.read_text(encoding='utf-8'))
    images = {im['image']: im for im in panel['images']}
    bindings = fields = 0
    rows, legacy = [], []
    for review in human['reviews']:
        image = images[review['image']]
        records = json.loads((INPUT/'inputs'/f"{review['image']}.json").read_text(encoding='utf-8'))['records']
        source = {r['id']: r for r in records}
        saved = {r['id']: r for r in image['records']}
        assert set(source) == set(saved)
        for rid, record in source.items():
            for field, value in record.items():
                assert saved[rid][field] == value, (rid, field)
                fields += 1
        keys = list(zip(review['record_ids'], review['processed_pair_indices'], strict=True))
        rejected = (keys[:2]+[(keys[2][0], review['rejected_previous_purple_processed_pair_index'])]
                    if 'rejected_previous_purple_processed_pair_index' in review else None)
        expected = {(r['id'], i) for r in records for i in range(len(r['points'])//2)}
        for state in image['states']:
            r = state['result']
            assert r['vote_denominator'] == len(records)
            families = r.get('endpoint_groups') or {'pair': r['identity_groups']}
            for side, groups in families.items():
                observed = []
                for g in groups:
                    assert g['support'] == len(g['members']) == len({m['worker'] for m in g['members']})
                    for m in g['members']:
                        raw = source[m['id']]; index = m['pair_index']
                        assert m['worker'] == raw['worker']
                        assert m['points'] == raw['points'][2*index:2*index+2]
                        assert m['source_pair_index'] == raw['source_pair_indices'][index]
                        observed.append(member_key(m)); bindings += 1
                assert len(observed) == len(set(observed)) and set(observed) == expected
                metric = side if state['route'] == 'split_unique' else {
                    'paired': 'pair', 'top_anchor': 'top', 'bottom_anchor': 'bottom'}[state['route']]
                probe = probe_correspondence(groups, keys, metric, state['threshold_deg'], r['minimum_support'])
                wrong = (probe_correspondence(groups, rejected, metric, state['threshold_deg'], r['minimum_support'])
                         if rejected else None)
                rows.append(dict(case_id=review['case_id'], image=review['image'], relation=review['relation'],
                    bottom_relation=review.get('bottom_relation'),
                    route=state['route'], threshold_deg=state['threshold_deg'], side=side, metric=metric,
                    requested_members=keys, probe=probe, rejected_combination_probe=wrong,
                    different_upper_targets_in_same_group=[dict(members=[keys[a], keys[b]],
                        feature_id=probe['member_group_ids'][a])
                        for a, b in review.get('different_upper_target_indices', [])
                        if probe['member_group_ids'][a] == probe['member_group_ids'][b]]))
                if review['relation'] == 'same_corner_pair':
                    legacy.append(dict(case_id=review['case_id'], route=state['route'],
                        threshold_deg=state['threshold_deg'], side=side, confirmed_members=keys,
                        matching_groups=probe['target_groups'] if probe['same_group'] else [],
                        rejected_combination=rejected,
                        rejected_combination_matching_groups=wrong['target_groups'] if wrong and wrong['same_group'] else []))
    write_json(out/'human_review.json', human)
    write_json(out/'correspondence_audit.json', dict(schema='point_correspondence_audit_v1',
        human_review_source=str(HUMAN_REVIEW.relative_to(ROOT)).replace('\\', '/'),
        source_fields_checked=fields, source_member_bindings=bindings, rows=rows,
        policy='Post-hoc development diagnostics only; unchanged complete pools, source observations, thresholds, clustering, votes and GT. No merge-history or global optimum claim.'))
    write_json(out/'human_correspondence_checks.json', dict(schema='development_human_correspondence_probe_v1',
        scope='Two explicitly confirmed same-corner triples only; unb has different upper targets and is reported separately in correspondence_audit.json.', rows=legacy))
    contract = json.loads((out/'field_contract.json').read_text(encoding='utf-8'))
    contract.update(AUDIT_CONTRACT)
    write_json(out/'field_contract.json', contract)


def partial_correspondences(result):
    """Keep isolated two-node components; an unresolved component never becomes a ring."""
    minimum = result['minimum_support']
    selected = {side: {g['feature_id']: g for g in result['endpoint_groups'][side] if g['support'] >= minimum}
                for side in ('top', 'bottom')}
    edges = result['pairing_graph']['edges']
    degrees = {side: {fid: sum(e[side+'_id'] == fid for e in edges) for fid in selected[side]}
               for side in selected}
    pairs, covered = [], set()
    for edge in sorted(edges, key=lambda e: (e['top_id'], e['bottom_id'])):
        a, b = edge['top_id'], edge['bottom_id']
        if degrees['top'][a] != 1 or degrees['bottom'][b] != 1:
            continue
        group, reason = paired_identity(selected['top'][a], selected['bottom'][b], edge['members'], len(pairs)+1)
        if reason:
            continue
        pairs.append(group)
        covered.update([('top', a), ('bottom', b)])
    unresolved = [dict(side=side, feature_id=fid, degree=degrees[side][fid], center=g['center'],
                       members=g['members'], support=g['support'],
                       reason=('isolated_after_endpoint_vote' if degrees[side][fid] == 0
                               else 'outside_single_edge_component_or_unavailable_center'))
                  for side, groups in selected.items() for fid, g in groups.items() if (side, fid) not in covered]
    return dict(pairs=pairs, unresolved_endpoints=unresolved, full_pairing_complete=bool(pairs) and not unresolved,
                is_complete_layout=False, matching_uniqueness_assessed=False,
                policy='only isolated two-node one-edge components; no global matching search or forced choice; pairs are representation evidence, not certified corners')


def connection_review(result):
    """Only full source identity cycles are alternatives; do not delete unselected source nodes."""
    if result['route'] == 'split_unique':
        groups = result['paired_identities']
    else:
        groups = [g for g in result['identity_groups'] if g['selected']]
    by_id = {g['feature_id']: g for g in groups}
    review = dict(policy='preserve_full_roster_observed_order_when_unanimous; otherwise_nodes_only_with_explicit_order_controls',
                  unanimous=None, observed_orders=[], reason='no_full_roster_order_agreement')
    if len(groups) < 3 or any(g['center'] is None for g in groups):
        review['reason'] = 'insufficient_or_unavailable_pair_centers'
        return review
    signatures = {}
    for assignment in result['assignments']:
        ids = assignment['feature_ids']
        if (assignment.get('source_geometry_status') != 'ok' or len(ids) != len(groups)
                or len(set(ids)) != len(ids) or set(ids) != set(by_id)):
            continue
        signature = _ring_key(ids)
        entry = signatures.setdefault(signature, dict(feature_ids=list(ids), source_ids=[]))
        entry['source_ids'].append(assignment['id'])
    for number, (_, entry) in enumerate(sorted(signatures.items()), 1):
        ordered = [by_id[fid] for fid in entry['feature_ids']]
        candidate = dict(points=[p for g in ordered for p in g['center']], feature_ids=entry['feature_ids'],
            source_pair_maps=ordered, point_support_counts=None if result['route'] == 'split_unique' else [g['support'] for g in ordered],
            ring_confirmed=False, source_pair_indices=None, source_point_indices=None, source_point_labels=None,
            order_status='observed_identity_cycle_control_unconfirmed', status='unavailable', reason=None)
        geometry = reconstruct(candidate, coordinate_convention='continuous')
        candidate.update(footprint=geometry['floor'].tolist() if geometry['floor'] is not None else None,
                         geometry_status=geometry['status'], geometry_issues=geometry.get('issues', []))
        if geometry['status'] == 'ok':
            candidate.update(status='geometry_review', reason='observed_order_with_estimated_centers_not_scene_certification')
        else:
            candidate['reason'] = 'invalid_reconstructed_observed_order:'+str(geometry['reason'])
        variant = dict(entry, id=f'order_{number}', support=len(entry['source_ids']), candidate=candidate,
                       order_status=candidate['order_status'], support_basis='complete original identity cycle; not votes for generated coordinates')
        review['observed_orders'].append(variant)
    if len(review['observed_orders']) == 1 and review['observed_orders'][0]['support'] == result['n']:
        chosen = review['observed_orders'][0]
        if chosen['candidate']['status'] != 'unavailable':
            review.update(unanimous=chosen, reason=None)
        else:
            review['reason'] = 'unanimous_order_but_center_geometry_unavailable'
    return review


def run_controls(out):
    records = json.loads((INPUT/'inputs/rPc6DW4iMge-06.json').read_text(encoding='utf-8'))['records']
    source = next(r for r in records if r['id'] == 'R01518')
    rows = [dict(copy.deepcopy(source), id=f'synthetic_repeat_{i}', worker=f'synthetic_repeat_{i}') for i in range(3)]
    original = Polygon(reconstruct(source, coordinate_convention='continuous')['floor'])
    checks = []
    for threshold in (1., 5., 10.):
        result = build_routes(rows, threshold)['paired']
        review = connection_review(result)
        corrected = review['unanimous']['candidate']
        baseline = Polygon(result['candidate']['footprint']); preserved = Polygon(corrected['footprint'])
        checks.append(dict(threshold_deg=threshold, source_id=source['id'], pair_count=len(corrected['points'])//2,
            x_order_iou=original.intersection(baseline).area/original.union(baseline).area,
            observed_order_iou=original.intersection(preserved).area/original.union(preserved).area,
            exact_points_and_order=corrected['points'] == source['points'],
            x_candidate=result['candidate'], observed_candidate=corrected))
    write_json(out/'connection_controls.json', dict(kind='synthetic_repetition_of_one_observed_ring_not_three_new_people', checks=checks))


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    write_json(out/'PLAN.json', dict(revision='point_route_review_v2',
        base_plan='analysis_results/point_route_panel_20261005/PLAN.json',
        fixed_changes=['retain complete observed identity cycles without selecting largest support',
                       'retain isolated paired components and every unresolved selected endpoint',
                       'separate source-only human review from method and reference disclosure'],
        threshold_policy='1, 2.5, 5, 7.5, 10 degrees remain exploratory; 5 is a demonstration, not calibrated',
        evaluation_scope='evaluations.json evaluates the unchanged x-order baseline only; not observed-order alternatives or partial pairs',
        semantic_answers='Human feedback is held separately in research/point_route_review_20261006/human_review.json; construction does not consume it. No automatic corner certification.'))
    construct_panel(out)
    evaluate_panel(out)
    audit_outputs(out)
    data = json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    for image in data['images']:
        for state in image['states']:
            result = state['result']
            result['connection_review'] = connection_review(result)
            if state['route'] == 'split_unique':
                result['partial_correspondences'] = partial_correspondences(result)
    data['review_schema'] = 'point_route_review_v2'
    write_json(out/'candidates.json', data)
    states = [s for image in data['images'] for s in image['states']]
    partials = [dict(image=image['image'], threshold_deg=s['threshold_deg'],
                     pair_count=len(s['result']['partial_correspondences']['pairs']),
                     unresolved_count=len(s['result']['partial_correspondences']['unresolved_endpoints']),
                     baseline_status=s['result']['status'])
                for image in data['images'] for s in image['states'] if s['route'] == 'split_unique']
    write_json(out/'review_checks.json', dict(
        state_count=len(states),
        full_roster_observed_order_count=sum(s['result']['connection_review']['unanimous'] is not None for s in states),
        observed_order_variant_count=sum(len(s['result']['connection_review']['observed_orders']) for s in states),
        split_states=partials,
        evaluation_scope='unchanged x-order baseline only; alternatives and partial correspondences not evaluated'))
    run_controls(out)
    cases = [
        dict(id='2t7_corner', image='2t7WUuJeko7-06', title='入口附近的同一转角？',
             question='A、B、C标记的上下点对，是否指向同一个房间竖向转角？请区分位置偏差与不同结构，无法确认也可保留。',
             record_ids=['R00227', 'R00539', 'R01831'],
             highlights=[dict(id=r, pair_index=0, label=label) for r, label in zip(['R00227', 'R00539', 'R01831'], ['A', 'B', 'C'])],
             view_box=[100, 60, 220, 390], options=['同一转角，主要是定位差', '指向不同结构', '现有图像无法判定']),
        dict(id='unb_upper', image='uNb9QFRL6hY-67', title='淋浴区左侧的上端分歧',
             question='已收到你的解释：A上端标较矮玻璃顶部，B、C标玻璃延伸到天花板的位置；下端应该是同一处墙角。保留“应该”的判断程度，上端目标分开；本窗口无需重复确认。',
             record_ids=['R00144', 'R00526', 'R02210'],
             highlights=[dict(id=r, pair_index=0, label=label) for r, label in zip(['R00144', 'R00526', 'R02210'], ['A', 'B', 'C'])],
             view_box=[75, 65, 150, 390], options=['同一边界的定位差', '不同结构或高度边界', '上端待定，下端可视为同一处', '现有图像无法判定']),
        dict(id='rpc_lower', image='rPc6DW4iMge-06', title='已确认的紫色对应点与原误选对照',
             question='你已确认C确认（紫色源第4对）与A、B是同一墙角；C旧（紫色源第5对）是不同细节。两者并列保留以检查对应错误，源序号从1计数，无需重复确认。',
             record_ids=['R02452', 'R01986', 'R01557'],
             highlights=[dict(id='R02452', pair_index=2, label='A', label_offset=[18, 3]),
                         dict(id='R01986', pair_index=2, label='B', label_offset=[-30, -5]),
                         dict(id='R01557', pair_index=2, label='C旧·源5', label_offset=[15, -15]),
                         dict(id='R01557', pair_index=4, label='C确认·源4', label_offset=[-30, 15])],
             view_box=[160, 160, 125, 205], options=['维持聊天中已确认的对应', '需要修订此前判断'])
    ]
    write_json(out/'review_cases.json', cases)
    contract = json.loads((out/'field_contract.json').read_text(encoding='utf-8'))
    contract.update(review_schema='point_route_review_v2',
        connection_review='x baseline unchanged; all complete source identity-cycle alternatives retained. Full-roster unanimous valid cycle may be displayed by default. Otherwise nodes only; no largest branch choice. New rings remain unconfirmed.',
        partial_correspondences='Mutual degree-one edge components plus all unresolved selected endpoints; no forced matching, no closed polygon or area score for partial evidence, no global matching uniqueness claim.',
        review_cases='Three development windows, not blinded holdout cases. Explicit chat feedback is displayed separately from blank browser draft forms; unanswered issues must not be invented. Method/reference disclosure is separate from source-only review.',
        evaluation_scope='Existing evaluation rows refer only to the x-order baseline candidate. Do not transfer these scores to observed-order alternatives or partial pairs.',
        full_pairing_complete='All selected endpoint identities belong to retained single-edge components with available centers; this flag alone does not imply at least three pairs, a ring, geometric validity, or physical correspondence.',
        human_review='human_review.json is an independently saved user-review ledger, not generated by run(): schema/status, reviews with case_id/image/record_ids/processed_pair_indices/reviewer/source/verbatim/interpretation/not_decided, and pending_case_ids. It is scoped to the named observations, is not formal gold, and does not alter source labels or eligibility.',
        source_policy='Only display artifacts and independent analysis outputs change; no source annotations, qualification, weights, GT, SOP or protocol changes.')
    contract.update(AUDIT_CONTRACT)
    write_json(out/'field_contract.json', contract)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--stage', choices=['panel', 'audit'], default='panel')
    args = parser.parse_args()
    (run if args.stage == 'panel' else audit_correspondences)(args.out)
