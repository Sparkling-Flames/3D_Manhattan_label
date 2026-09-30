import copy
import json
import numpy as np
import pytest
from tools.thesis_main.analysis.apply_pairing_preprocessing_20260929 import OUT, QUEUE, ROOT, read, raw_initial_points, validate_received, jsdata
from tools.thesis_main.analysis.shared_x_reanalysis_20260922 import shared_x
from tools.thesis_main.analysis.receive_order_review_20260928 import validate_return


def test_raw_initialization_and_received_bindings():
    o=dict(before_preprocessing_points=[[10,20],[10,40]],original_export_points=[[10,20],[14,40]],point_labels=['p1','p2'])
    points,ids,notes=raw_initial_points(o)
    assert points==[[10,20],[14,40]] and ids==[0,1] and notes
    assert shared_x(points,[[0,1]]).tolist()==[[12,20],[12,40]]
    assert shared_x([[1020,20],[4,40]],[[0,1]]).tolist()==[[0,20],[0,40]]
    cases={r['object_id']:r for r in jsdata(ROOT/'analysis_results/pairing_completion_review_20260929/data.js')['cases']}
    doc=read(OUT/'evidence/completed_pairing.json');validate_received(doc,cases)
    bad=copy.deepcopy(doc);next(iter(bad['records'].values()))['pairs'].pop()
    with pytest.raises(ValueError):validate_received(bad,cases)


def test_full_baseline_and_order_scope():
    objects={r['object_id']:r for r in read(OUT/'preprocessed_source.json')['objects']}
    assert len(objects)==3441 and sum(r['object_kind']=='annotation' for r in objects.values())==3152
    for o in objects.values():
        if o['preprocessing_status']!='ready':assert o['preprocessed_points'] is None;continue
        before=np.array(o['before_preprocessing_points']);after=np.array(o['preprocessed_points'])
        assert np.array_equal(before[:,1],after[:,1])
        assert np.array_equal(after,shared_x(before,o['links_zero_based']))
        if o['object_kind']=='annotation':
            for i,index in enumerate(o['original_export_indices']):
                if index is not None:assert before[i].tolist()==o['original_export_points'][index]
    kept=read(OUT/'preserved_orders.json');assert len(kept['records'])==1272
    validate_return(kept,objects)
    queue=read(QUEUE/'source_objects.json')['objects'];assert len(queue)==23
    assert len({r['image_id'] for r in queue})==18
    assert not set(r['object_id'] for r in queue)&set(kept['records'])
    assert all(len(o['links_zero_based'])>4 and o['preprocessing_status']=='ready' for o in queue)
    assert objects['f6bfdcf15004e457']['point_labels']==['p1','p2','p4','p5','p6','p7','p8','p9']
