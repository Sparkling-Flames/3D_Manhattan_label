from copy import deepcopy
import numpy as np

from tools.thesis_main.analysis.scope_local_routing_20261017 import route_missing_space
from tools.thesis_main.analysis.scope_quality_binding_20261016 import build_affected_records
from tests.test_scope_quality_binding_20261016 import fixture


def points(floor):
    q = np.asarray(floor)
    x = (np.arctan2(q[:, 0], -q[:, 1])/(2*np.pi)+.5)*1024
    y = (np.arctan(1/np.linalg.norm(q, axis=1))/np.pi+.5)*512
    return [[float(a), float(b)] for a, by in zip(x, y) for b in (120, by)]


def test_local_routing_precedes_quality_and_preserves_source_and_uncertainty():
    square = [[-1,-1],[1,-1],[1,1],[-1,1]]
    spaces = [dict(target_id='a',floor_xz_h=square), dict(target_id='b',floor_xz_h=(np.asarray(square)*2).tolist())]
    source = points(square); before = deepcopy(source)
    chosen, evidence = route_missing_space(source, spaces, {'a','b'}, {})
    assert chosen == 'a' and evidence['route_reason'] == 'local_differentiating_structure'
    assert not evidence['quality_or_height_used_for_route'] and not evidence['route_is_quality_acceptance']
    assert evidence['uncertainty'] and source == before


def test_exact_double_tie_is_not_resolved_by_candidate_name_and_bad_floor_is_pending():
    square = [[-1,-1],[1,-1],[1,1],[-1,1]]
    spaces = [dict(target_id=k,floor_xz_h=square) for k in ['a','b']]
    chosen, evidence = route_missing_space(points(square), spaces, {'a','b'}, {})
    assert chosen == '' and evidence['uncertainty'] == 'exact_iou_and_boundary_tie'
    chosen, evidence = route_missing_space([[0,100],[0,200]]*3, spaces, {'a','b'}, {})
    assert chosen == '' and evidence['status'] == 'floor_unavailable'


def test_family_excludes_even_a_perfect_outside_match_and_camera_outside_is_pending():
    square = np.asarray([[-1,-1],[1,-1],[1,1],[-1,1]])
    spaces = [dict(target_id=k,floor_xz_h=(square*scale).tolist()) for k,scale in [('a',1),('b',2),('c',3)]]
    chosen, evidence = route_missing_space(points(square*3), spaces, {'a','b'}, {})
    assert chosen in {'a','b'} and set(evidence['candidate_floor_metrics'])=={'a','b'}
    chosen, evidence = route_missing_space(points(square+[5,0]), spaces, {'a','b'}, {})
    assert chosen=='' and evidence['uncertainty']=='camera_not_inside_floor'


def test_manual_and_geometry_drift_protection_survive_new_router_and_old_default():
    bundle, difficulty, routing = fixture()
    square = difficulty[0]['selected']['floor']
    for obj in bundle['data']['objects']:obj['points_1024x512'] = points(square)
    routing['records'][0]['source_object'] = deepcopy(bundle['data']['objects'][0])
    old = build_affected_records(bundle,difficulty,routing_input=routing)
    assert not old['affected_records'][1]['chosen_target_id']
    auto = build_affected_records(bundle,difficulty,routing_input=routing,resolve_multiple_spaces=True)
    assert auto['affected_records'][1]['chosen_target_id'] == 'new'
    routing['manual_overrides']['R1'] = dict(object_id='0',selected_candidate_id='b-01:A')
    direct = build_affected_records(bundle,difficulty,routing_input=routing,resolve_multiple_spaces=True)
    assert direct['affected_records'][0]['chosen_target_id'] == 'old'
    routing['records'][0]['source_object']['points_1024x512'][0][0] += 1
    drift = build_affected_records(bundle,difficulty,routing_input=routing,resolve_multiple_spaces=True)
    assert drift['affected_records'][0]['binding_status'] == 'pending_manual_evidence_geometry_changed'
    assert not drift['affected_records'][0]['chosen_target_id']
