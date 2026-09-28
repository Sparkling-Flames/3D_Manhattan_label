from copy import deepcopy

import pytest

from tools.thesis_main.analysis.receive_order_review_20260928 import validate_return, reconcile, expand_rooms


def test_return_binding_conflict_and_physical_room_scope():
    import json
    source = dict(preprocessed_points=[[10,100],[10,400]], point_labels=['p1','p2'],
                  links_zero_based=[[0,1]], preprocessing='shared_x_periodic_shortest_arc_v1')
    binding = dict(id='a', points=source['preprocessed_points'], labels=source['point_labels'],
                   links=source['links_zero_based'], preprocessing=source['preprocessing'])
    record = dict(binding=json.dumps(binding),status='confirmed',order=[0],note='',cause='',updated_at='2026-09-28T01:00:00Z')
    doc = dict(schema='order_review_20260928_v3',examples_only=False,records={'a':record})
    validate_return(doc, {'a':source})
    bad = deepcopy(doc);bad['records']['a']['order']=[True]
    with pytest.raises(ValueError,match='return_order'):
        validate_return(bad, {'a':source})
    bad = deepcopy(source);bad['preprocessed_points'][0][0]=11
    with pytest.raises(ValueError,match='return_binding'):
        validate_return(doc, {'a':bad})
    newer = deepcopy(doc);newer['records']['a']['updated_at']='2026-09-28T02:00:00Z'
    merged, history, conflicts = reconcile({'user':doc,'yizheng':newer})
    assert not conflicts and len(history['a'])==2 and merged['a']==newer['records']['a']
    newer['records']['a']['status']='pairing'
    merged, _, conflicts = reconcile({'user':doc,'yizheng':newer})
    assert merged=={} and conflicts==['a']
    expanded, room_map = expand_rooms({'a','z'}, [
        dict(candidate_id='yes',physical_same_supported=True,image_ids=['a','b']),
        dict(candidate_id='no',physical_same_supported=False,image_ids=['a','c'])])
    assert expanded=={'a','b','z'} and 'z' not in room_map and 'c' not in room_map
