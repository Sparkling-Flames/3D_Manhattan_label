import copy

import numpy as np

from tools.label_studio.panorama_studio.geometry import project_pixel
from tools.thesis_main.analysis.erp_region_demo_20261003 import annotation_band, aggregate_records


def record(name='a', top=1.4, scale=1.):
    floor = np.array([[-2,-2],[2,-2],[2,2],[-2,2]]) * scale
    points = [p for x,z in floor for p in [project_pixel([x,top,z],1024,512),
                                          project_pixel([x,-1,z],1024,512)]]
    return dict(id=name, worker=name, points=points, footprint=floor.tolist())


def test_singleton_and_two_people_match_wall_region_union_intersection():
    records = [record(), record('b', top=2.2, scale=1.4)]
    frozen = copy.deepcopy(records)
    bands = [annotation_band(r, samples=64) for r in records]
    one = aggregate_records(records[:1], samples=64)
    assert one['status'] == 'ok'
    assert one['methods']['mv50']['top_points'] == one['methods']['mv_strict']['top_points']
    both = aggregate_records(records, samples=64)
    assert records == frozen and both['status'] == 'ok'
    y = np.linspace(0,512,257)[:,None]
    masks = [(y>=np.array(b['top'])) & (y<=np.array(b['bottom'])) for b in bands]
    for method, expected in [('mv50', masks[0]|masks[1]), ('mv_strict', masks[0]&masks[1])]:
        result = both['methods'][method]
        actual = (y>=np.array(result['top_points'])[:,1]) & (y<=np.array(result['bottom_points'])[:,1])
        assert np.array_equal(actual, expected)


def test_top_changes_region_when_bev_identical_and_duplicate_geometry_keeps_votes():
    a,b = record(), record('b', top=2.4)
    assert a['footprint'] == b['footprint']
    ba,bb = [annotation_band(r, samples=32) for r in (a,b)]
    assert np.allclose(ba['bottom'], bb['bottom'])
    assert not np.allclose(ba['top'], bb['top'])
    c = dict(a, id='c', worker='c')
    output = aggregate_records([a,b,c], samples=32)
    assert output['n'] == 3
    assert output['methods']['mv50']['threshold'] == 2
    assert np.allclose(np.array(output['methods']['mv50']['top_points'])[:,1], ba['top'])


def test_original_ring_cyclic_reverse_and_periodic_seam_are_preserved():
    a = record(); pairs = np.array(a['points']).reshape(-1,2,2)
    base = annotation_band(a, samples=64)
    for changed in [np.roll(pairs,1,axis=0), pairs[::-1]]:
        answer = annotation_band(dict(a,points=changed.reshape(-1,2).tolist()), samples=64)
        assert answer['status'] == 'ok'
        assert np.allclose(answer['top'], base['top'])
        assert np.allclose(answer['bottom'], base['bottom'])
    shifted = pairs.copy(); shifted[:,:,0] = (shifted[:,:,0]+80)%1024
    answer = annotation_band(dict(a,points=shifted.reshape(-1,2).tolist()), samples=64)
    assert np.allclose(answer['top'], np.roll(base['top'],5))
    assert np.allclose(answer['bottom'], np.roll(base['bottom'],5))


def test_unsupported_member_is_not_dropped_or_reordered():
    a=record(); b=record('b')
    points=np.array(b['points']).reshape(-1,2,2)[[0,2,1,3]].reshape(-1,2).tolist()
    b['points']=points
    answer=aggregate_records([a,b],samples=32)
    assert answer['status']=='unsupported' and answer['n']==2 and answer['methods']=={}
    assert answer['unsupported'][0]['id']=='b'
    assert b['points']==points
    bad=record('horizon');bad['points'][0][1]=256
    assert annotation_band(bad)['status']=='unsupported'
