"""Scientific boundary checks for fixed-node human ordering (no fusion replay)."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.apply_manual_ring_orders_20261104 import (
    REASON, geometry_details, reference_contexts, saved_state,
)


def case_without_complete_source_ring():
    points = [[[128+256*i,128.],[128+256*i,384.]] for i in range(4)]
    records=[]
    nodes=[]
    for j in range(4):
        included=[i for i in range(4) if i!=j]
        records.append(dict(id=f'r{j}',worker=f'w{j}',points=[p for i in included for p in points[i]]))
    for i in range(4):
        members=[]
        for j in range(4):
            included=[z for z in range(4) if z!=j]
            if i in included:
                members.append(dict(id=f'r{j}',worker=f'w{j}',pair_index=included.index(i)))
        nodes.append(dict(feature_id=f'node_{i}',points=points[i],support=3,members=members))
    return dict(k=4,nodes=nodes,records=records,ring_diagnostics=dict(
        reason=REASON,feature_ids=[],tied_best=False,alternatives=[],edges=[]),
        review_id='synthetic',reference_id='ref_a',reference_version='version_a')


def test_order_only_reconstruction_keeps_every_fixed_input(monkeypatch):
    from tools.thesis_main.analysis import ring_correspondence_20261007 as ring
    def forbidden(*args,**kwargs):
        raise AssertionError('Clustering/fusion was not authorized')
    monkeypatch.setattr(ring,'build',forbidden)
    c=case_without_complete_source_ring();original=deepcopy(c)
    automatic=saved_state(c)
    assisted=saved_state(c,['node_0','node_1','node_2','node_3'])
    assert c==original
    assert automatic['candidate']['points'] is None
    assert assisted['candidate']['geometry_status']=='ok'
    assert assisted['node_consensus']==automatic['node_consensus']
    assert assisted['node_consensus']['nodes']==c['nodes']
    assert assisted['candidate']['points']==[p for n in c['nodes'] for p in n['points']]


@pytest.mark.parametrize('order',[
    ['node_0','node_1','node_2'],
    ['node_0','node_1','node_2','node_2'],
    ['node_0','node_1','node_2','invented'],
])
def test_incomplete_duplicate_or_foreign_order_is_rejected(order):
    with pytest.raises(ValueError,match='exactly_once'):
        saved_state(case_without_complete_source_ring(),order)


def test_crossing_order_keeps_failure_and_witness():
    from tools.thesis_main.analysis.research_round_20260929 import reconstruct
    c=case_without_complete_source_ring()
    order=['node_0','node_2','node_1','node_3']
    r=saved_state(c,order)
    assert r['candidate']['geometry_status']=='unavailable'
    g=reconstruct(r['candidate'])
    d=geometry_details(g,order)
    assert 'Self-intersection' in d['polygon_validation']
    assert d['nonadjacent_intersections']
    assert r['candidate']['points']==[p for fid in order for n in c['nodes'] if n['feature_id']==fid for p in n['points']]


def test_distinct_reference_contexts_are_not_collapsed():
    c=case_without_complete_source_ring()
    links=pd.DataFrame([dict(reference_id='ref_b',reference_version='version_b'),
                        dict(reference_id=np.nan,reference_version=np.nan)])
    contexts,bindings=reference_contexts(c,links)
    assert contexts==[('ref_a','version_a'),('ref_b','version_b')]
    assert bindings[0]['resolved_reference_id']=='ref_b'
    assert bindings[1]['resolved_reference_id']=='ref_a'
