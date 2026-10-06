"""Small-panel correspondence controls. Every angle is an uncalibrated parameter.

Single-end anchoring is a limited hybrid, not an adaptive correspondence solver.
Split endpoints use only unambiguous original-pair incidence; no forced matching.
"""
from __future__ import annotations

import copy
import argparse
import json
import math
from pathlib import Path
from collections import Counter

import numpy as np
from shapely.errors import GEOSException
from shapely.geometry import Polygon, mapping, shape

from .global_pair_consensus_20261004 import _identities, _result, _ring_diagnostics
from .lee_tile_stage1_20261002 import ROOT, tile_consensus, write_json
from .layout_reliability_20261005.arc_consensus import Ring, Unsupported, area_scores
from .layout_reliability_20261005.continuous_metrics import fixed_longitude
from .research_round_20260929 import reconstruct

OUT = ROOT/'analysis_results/point_route_panel_20261005'
INPUT = ROOT/'research/layout_reliability_20261005/pro_original'


def member_key(member):
    return str(member['id']), member['pair_index']


def paired_identity(top_group, bottom_group, joint, number):
    """Construct one representation pair without asserting a closed layout."""
    if top_group['center'] is None or bottom_group['center'] is None:
        return None, 'ambiguous_periodic_endpoint_center'
    top, bottom = top_group['center'][0], bottom_group['center'][1]
    dx = (bottom[0]-top[0]+512) % 1024-512
    if abs(abs(dx)-512) < 1e-9:
        return None, 'half_turn_endpoint_center_alignment'
    x = (top[0]+dx/2) % 1024
    return dict(feature_id=f'paired_{number:03d}', center=[[x, top[1]], [x, bottom[1]]],
                top_feature_id=top_group['feature_id'], bottom_feature_id=bottom_group['feature_id'],
                top_support=top_group['support'], bottom_support=bottom_group['support'],
                joint_support=len(joint), top_members=top_group['members'], bottom_members=bottom_group['members'],
                joint_members=joint, endpoint_centers_before_x_alignment=[top, bottom],
                x_adjustment_px=[dx/2, -dx/2], x_alignment_tolerance_calibrated=False), None


def split_candidate(records, threshold, top_data, bottom_data):
    tops, assignments, issues, top_diagnostic = top_data
    bottoms, _, _, bottom_diagnostic = bottom_data
    n = len(records)
    minimum = math.ceil(n/2)
    top_selected = {g['feature_id']: g for g in tops if g['support'] >= minimum}
    bottom_selected = {g['feature_id']: g for g in bottoms if g['support'] >= minimum}
    bottom_membership = {member_key(m): g['feature_id'] for g in bottom_selected.values() for m in g['members']}
    links = {}
    for top_id, group in top_selected.items():
        for member in group['members']:
            bottom_id = bottom_membership.get(member_key(member))
            if bottom_id is not None:
                links.setdefault((top_id, bottom_id), []).append(member)
    top_degree = {k: sum(a == k for a, _ in links) for k in top_selected}
    bottom_degree = {k: sum(b == k for _, b in links) for k in bottom_selected}
    ambiguous = ([{'side': 'top', 'feature_id': k, 'degree': d} for k, d in top_degree.items() if d != 1]
                 + [{'side': 'bottom', 'feature_id': k, 'degree': d} for k, d in bottom_degree.items() if d != 1])
    graph = dict(edges=[dict(top_id=a, bottom_id=b, joint_support=len(m), members=m) for (a, b), m in links.items()],
                 ambiguous_top_or_bottom=ambiguous,
                 policy='selected endpoint identities must have exactly one observed opposite identity; no joint-majority gate')
    candidate = dict(status='unavailable', reason=None, points=None, footprint=None,
                     ring_confirmed=False, order_status='default_x_exploratory_unconfirmed',
                     source_pair_indices=None, source_point_indices=None, source_point_labels=None,
                     point_support_counts=None, feature_ids=[], source_pair_maps=[],
                     center_method='separate endpoint medians; periodic midpoint x after unique source-pair incidence')
    result = dict(schema_version='point_route_panel_v1', route='split_unique', threshold_deg=threshold,
                  threshold_calibrated=False, vote_denominator=n, n=n, minimum_support=minimum,
                  method='mv50', candidate=candidate, endpoint_groups={'top': tops, 'bottom': bottoms},
                  pairing_graph=graph, paired_identities=[], assignments=[], input_issues=issues,
                  correspondence_diagnostics={'top': top_diagnostic, 'bottom': bottom_diagnostic},
                  ring_diagnostics=None, status='unavailable')
    if ambiguous:
        candidate['reason'] = 'nonunique_or_missing_endpoint_pairing'
        return result
    if len(links) < 3:
        candidate['reason'] = 'fewer_than_three_paired_endpoint_identities'
        return result
    groups, identity_map = [], {}
    for number, ((a, b), joint) in enumerate(sorted(links.items()), 1):
        g, reason = paired_identity(top_selected[a], bottom_selected[b], joint, number)
        if reason:
            candidate['reason'] = reason
            return result
        groups.append(g)
        identity_map.update({member_key(m): g['feature_id'] for m in joint})
    source_assignments = copy.deepcopy(assignments)
    for assignment in source_assignments:
        assignment['feature_ids'] = [identity_map.get((str(assignment['id']), i), f"unpaired:{assignment['id']}:{i}")
                                     for i in range(len(assignment['feature_ids']))]
    ordered, ring = _ring_diagnostics(groups, source_assignments, n, minimum)
    result.update(paired_identities=ordered, assignments=source_assignments, ring_diagnostics=ring)
    if ring['ambiguous_x_pairs']:
        candidate['reason'] = 'ambiguous_shared_x_order'
        return result
    candidate.update(points=[p for g in ordered for p in g['center']], feature_ids=[g['feature_id'] for g in ordered],
                     source_pair_maps=ordered)
    geometry = reconstruct(candidate, coordinate_convention='continuous')
    candidate.update(footprint=geometry['floor'].tolist() if geometry['floor'] is not None else None,
                     geometry_status=geometry['status'], geometry_issues=geometry.get('issues', []),
                     geometry_polygon_valid=geometry['polygon_valid'])
    if geometry['status'] != 'ok':
        candidate['reason'] = 'invalid_candidate_ring:'+str(geometry['reason'])
    else:
        # Uniqueness of this incidence graph does not certify physical identity or x alignment.
        candidate.update(status='geometry_review', reason='independent_endpoints_and_new_ring_unconfirmed')
    result['status'] = candidate['status']
    return result


def build_routes(records, threshold):
    threshold = float(threshold)
    if not math.isfinite(threshold) or not 0 < threshold < 180:
        raise ValueError('invalid_exploratory_threshold')
    records = list(records)
    identities = {side: _identities(records, threshold, match_side=side) for side in (None, 'bottom', 'top')}
    routes = {}
    for route, side in [('paired', None), ('bottom_anchor', 'bottom'), ('top_anchor', 'top')]:
        groups, assignments, issues, diagnostics = identities[side]
        value = _result(groups, assignments, issues, diagnostics, len(records), threshold, 'mv50')
        value.update(schema_version='point_route_panel_v1', route=route)
        if side:
            value['method_details']['identity'] = f'{side} spherical endpoint angle; same-person-constrained complete linkage'
            value['method_details']['support_interpretation'] = 'anchor identity members; paired partners estimate the other endpoint, not a joint-location majority certificate'
            value['method_details']['scope'] = 'limited single-end anchored hybrid; no automatic choice of anchor side'
        routes[route] = value
    routes['split_unique'] = split_candidate(records, threshold, identities['top'], identities['bottom'])
    return routes


def synthetic_controls():
    def record(i, top, bottom):
        return dict(id=f'R{i}', worker=f'P{i}', points=[[x, y] for x in (128., 384., 640., 896.) for y in (top, bottom)],
                    source_pair_indices=list(range(4)), source_point_indices=list(range(8)),
                    ring_confirmed=True, order_status='synthetic_given_adjacency')
    return dict(top_dispersion=[record(i, y, 390.) for i, y in enumerate((80., 120., 160.))],
                bottom_dispersion=[record(i, 120., y) for i, y in enumerate((350., 390., 430.))],
                marginal_joint_vote_counterexample=[record(i, t, b) for i, (t, b) in enumerate(
                    [(120., 390.)]*2+[(120., 430.)]*4+[(160., 390.)]*4)])


def construct_panel(out, plan=None):
    if plan is None:
        plan = json.loads((OUT/'PLAN.json').read_text(encoding='utf-8'))
    source = json.loads((ROOT/'analysis_results/lee_expanded_20261003/source_input.json').read_text(encoding='utf-8'))
    source_images = {r['code']: r for r in source['images']}
    images, checks, all_workers = [], [], set()
    for code in plan['images']:
        image = source_images[code]
        current = {r['id']: r for r in image['annotations'] if r['independent'] and r['consensus_eligible']
                   and r['condition'] == 'manual' and r['main_consensus_gate']['status'] == 'main_candidate'}
        records = (list(current.values()) if plan.get('roster_source') == 'current_source_input' else
                   json.loads((INPUT/'inputs'/f'{code}.json').read_text(encoding='utf-8'))['records'])
        if set(current) != {r['id'] for r in records}:
            raise ValueError('full_roster_drift:'+code)
        fields_checked = 0
        for record in records:
            for field, value in record.items():
                if field not in ('image', 'evidence_kind'):
                    if current[record['id']][field] != value:
                        raise ValueError('source_field_drift:'+code+':'+record['id']+':'+field)
                    fields_checked += 1
        before = copy.deepcopy(records)
        states = [dict(threshold_deg=t, route=route, result=result)
                  for t in plan['thresholds_deg'] for route, result in build_routes(records, t).items()]
        if records != before:
            raise AssertionError('source_mutated')
        display_records, domain_failures = [], []
        for record in records:
            geometry = reconstruct(record, coordinate_convention='continuous')
            display_records.append(dict(record, footprint=geometry['floor'].tolist() if geometry['floor'] is not None else None))
            try:
                Ring(record)
            except Unsupported as exc:
                domain_failures.append(dict(id=record['id'], reason=str(exc)))
        try:
            lee = tile_consensus(display_records)
            lee_result = dict(status='ok', method='mv50', region=mapping(lee['regions']['mv50']), warnings=lee['warnings'])
        except (ValueError, GEOSException) as exc:
            lee_result = dict(status='unavailable', reason=str(exc), method='mv50', region=None)
        images.append(dict(image=code, n=len(records), image_id=image['image_id'], records=display_records,
                           lee=lee_result, states=states, source_single_value_failures=domain_failures))
        all_workers.update(r['worker'] for r in records)
        checks.append(dict(image=code, records=len(records), bound_fields=fields_checked, source_unchanged=True))
        print(f'{code}: {len(records)} records, {len(states)} route/threshold states', flush=True)
    if sum(i['n'] for i in images) != plan['expected_records']:
        raise ValueError('panel_record_count_drift')
    out.mkdir(parents=True, exist_ok=True)
    write_json(out/'candidates.json', dict(schema='point_route_panel_v1', plan=plan, images=images))
    controls = [dict(control=name, n=len(records), states=[dict(threshold_deg=t, route=route, result=result)
                for t in plan['thresholds_deg'] for route, result in build_routes(records, t).items()])
                for name, records in synthetic_controls().items()]
    write_json(out/'controls.json', controls)
    write_json(out/'construction_checks.json', dict(images=checks, record_count=sum(i['n'] for i in images),
        unique_worker_ids=len(all_workers), real_states=sum(len(i['states']) for i in images),
        control_states=sum(len(i['states']) for i in controls), gt_used_in_construction=False,
        source_references_accessed_by_construction=False,
        note='Source inventory also contains historical references; only annotations and image IDs are accessed. This is an already-seen development panel, not a blinded experiment.'))


def evaluate_panel(out, reference_file=None):
    # Candidates are serialized first and reloaded here; references cannot select route, threshold or ring.
    data = json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    if reference_file is None:
        reference_file = json.loads((INPUT/'evaluation/references.json').read_text(encoding='utf-8'))
    references = {}
    for item in reference_file['images']:
        refs = [r for r in item['references'] if r['version'] == 'original']
        if len(refs) != 1:
            raise ValueError('nonunique_original_reference:'+item['image'])
        ref = refs[0]
        geo = reconstruct(ref, coordinate_convention='continuous')
        if not geo['polygon_valid']:
            raise ValueError('invalid_fixed_reference:'+item['image'])
        references[item['image']] = dict(ref, footprint=geo['floor'].tolist())
    rows, lee_rows = [], []
    for image in data['images']:
        ref = references[image['image']]
        gt = Polygon(ref['footprint'])
        lee = image['lee']
        lee_rows.append(dict(image=image['image'], status=lee['status'],
            bev=area_scores(shape(lee['region']), gt) if lee['status'] == 'ok' else None,
            upper_boundary_status='not_defined_by_bev_tile_vote'))
        for state in image['states']:
            result = state['result']; candidate = result['candidate']; ring = result['ring_diagnostics'] or {}
            row = dict(image=image['image'], n=image['n'], threshold_deg=state['threshold_deg'], route=state['route'],
                status=candidate['status'], reason=candidate.get('reason'), pair_count=len(candidate['points'] or [])//2,
                ring_confirmed=False, unsupported_edges=ring.get('unsupported_edge_count'),
                below_majority_edges=ring.get('below_majority_edge_count'), exact_source_ring_support=ring.get('exact_source_ring_support'),
                bev=None, boundary=dict(status='unavailable', reason='candidate_unavailable'))
            if candidate['status'] != 'unavailable':
                row['bev'] = area_scores(Polygon(candidate['footprint']), gt)
                domain_failures = []
                for role, record in [('candidate', candidate), ('reference', ref)]:
                    try:
                        Ring(record)
                    except Unsupported as exc:
                        domain_failures.append(dict(role=role, reason=str(exc)))
                row['boundary'] = (dict(status='unavailable', reason='outside_single_value_metric_domain',
                                        domain_failures=domain_failures) if domain_failures
                                   else dict(status='ok', **fixed_longitude(candidate, ref)))
            rows.append(row)
    write_json(out/'evaluations.json', dict(schema='point_route_panel_evaluation_v1', rows=rows, lee=lee_rows,
        references=[dict(image=code, record=record) for code, record in references.items()],
        interpretation='Post-construction original-reference discrepancies, not physical correctness or threshold calibration. All attempted states remain.'))
    write_json(out/'field_contract.json', dict(schema='point_route_panel_v1',
        candidates='All fixed pools and route/threshold states declared in the saved plan; original metadata, full identity members, center and adjacency diagnostics retained.',
        controls='Three mechanism controls, each planned threshold times four routes; no synthetic reference scores.',
        anchor_support='Votes establish only the anchor identity. Other endpoint coordinates use original paired partners; their spread can exceed the identity threshold.',
        split_support='top_support and bottom_support are marginal identity supports; joint_support counts original pair incidence, not votes for the generated coordinate; point_support_counts is null.',
        status='ok denotes existing computational checks only. Every generated ring is unconfirmed, including ok. geometry_review also retains a computable candidate; unavailable is not interpreted as no possible consensus.',
        minimum_corners='2026-10-06 revised user direction: retain raw majority outputs without a four-pair gate. Report fewer-than-four pairs separately; structure-constrained candidates are a parallel research route, not changes to raw votes.',
        connection='New center-x ring only; source order unchanged. Direct and deletion-projected source adjacency are separate, neither establishes physical correctness.',
        geometry='BEV omission/extension h² and centroid h use camera-height units; no top score for Lee BEV. Uniform-longitude boundary px discrepancy applies only to single-valued rings; not nearest boundary distance or semantic matching.',
        reference='Only original version; no threshold, identity, ring or route selection by GT. Previously seen development panel, not holdout validation.'))


def audit_outputs(out):
    data = json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    controls = json.loads((out/'controls.json').read_text(encoding='utf-8'))
    rows = json.loads((out/'evaluations.json').read_text(encoding='utf-8'))['rows']
    cases = [(im['records'], im['states']) for im in data['images']]
    cases += [(synthetic_controls()[c['control']], c['states']) for c in controls]
    checked = bindings = 0; max_error = max_x_adjust = 0.
    for records, states in cases:
        source = {r['id']: r for r in records}
        for state in states:
            result = state['result']; route = state['route']; theta = state['threshold_deg']
            assert result['vote_denominator'] == len(records)
            sides = list(result['endpoint_groups'].items()) if route == 'split_unique' else [(None, result['identity_groups'])]
            for side, groups in sides:
                observed = []
                for g in groups:
                    members = g['members']
                    assert len(members) == g['support'] == len({m['worker'] for m in members})
                    for m in members:
                        assert m['points'] == source[m['id']]['points'][2*m['pair_index']:2*m['pair_index']+2]
                        observed.append(member_key(m)); bindings += 1
                    p = np.array([m['points'] for m in members]); u = p[:,:,0]/1024*2*np.pi; v = (.5-p[:,:,1]/512)*np.pi
                    rays = np.stack([np.cos(v)*np.cos(u), np.cos(v)*np.sin(u), np.sin(v)], axis=-1)
                    # Independent vector atan2 check of the core's haversine angular distances.
                    angle = np.rad2deg(np.arctan2(np.linalg.norm(np.cross(rays[:,None], rays[None,:]), axis=-1),
                                                 np.einsum('isk,jsk->ijs', rays, rays)))
                    max_error = max(max_error, abs(float(angle.max())-g['maximum_pair_angle_deg']))
                    match = side or {'paired': None, 'top_anchor': 'top', 'bottom_anchor': 'bottom'}[route]
                    diameter = angle.max() if match is None else angle[:,:,(0 if match == 'top' else 1)].max()
                    assert diameter <= theta+1e-9
                assert len(observed) == len(set(observed)) == sum(len(r['points'])//2 for r in records)
            for g in result.get('paired_identities', []):
                top = {member_key(m) for m in g['top_members']}; bottom = {member_key(m) for m in g['bottom_members']}
                assert g['joint_support'] == len(top & bottom)
                max_x_adjust = max(max_x_adjust, max(abs(v) for v in g['x_adjustment_px']))
            assert result['candidate']['ring_confirmed'] is False
            checked += 1
    write_json(out/'output_checks.json', dict(
        real_route_statuses={route: dict(Counter(r['status'] for r in rows if r['route'] == route)) for route in data['plan']['routes']},
        real_candidates_with_geometry=sum(r['bev'] is not None for r in rows),
        boundary_computable=sum(r['boundary']['status'] == 'ok' for r in rows),
        boundary_domain_failures=dict(Counter(f['role'] for r in rows for f in r['boundary'].get('domain_failures', []))),
        verified_states=checked, source_member_bindings=bindings,
        independent_vector_max_pair_diameter_error_deg=max_error, largest_split_x_adjustment_px=max_x_adjust,
        interpretation='Audit of saved states; not additional scientific samples or test-suite counts.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--stage', choices=['build', 'evaluate', 'check', 'all'], default='all')
    args = parser.parse_args()
    if args.stage in ('build', 'all'):
        construct_panel(args.out)
    if args.stage in ('evaluate', 'all'):
        evaluate_panel(args.out)
    if args.stage in ('check', 'all'):
        audit_outputs(args.out)
