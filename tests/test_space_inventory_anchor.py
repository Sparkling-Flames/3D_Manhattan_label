import json
import numpy as np
import pytest
from tools.thesis_main.analysis import space_inventory_anchor as inv


def ring(xs=(50,300,550,800),top=140):
    return [[x,y] for x in xs for y in (top,380)]


def test_periodic_nearest():
    assert inv.nearest([[1023,10]],[[1,10]]).tolist()==[2]


def test_complete_link_separates_doorway_spaces():
    rows=[]
    for i in range(8):
        p,g=inv.canonical(ring((100,150,200) if i==7 else (500,550,600)))
        rows.append(dict(annotation_id=str(i),geometry=g,points=p.tolist()))
    groups,audit=inv.partition(rows)
    assert sorted(map(len,groups))==[1,7]


def test_continuous_match_requires_ordered_subring():
    parent=ring();child=parent[2:8]
    assert inv.continuous_match(child,parent)==[1,2,3]
    assert inv.continuous_match(child[::-1],parent) is None


@pytest.fixture(scope='module')
def inventory():
    return inv.build_inventory()[0]


def test_259_oos_gt_policy_and_sources(inventory):
    assert len(inventory)==259
    for item in inventory:
        assert abs(sum(s['human_frequency'] for s in item['spaces'])-1)<1e-12
        if item['oos']:
            assert not item['gt_used_as_anchor']
            assert all(s['space_kind']=='alternative' for s in item['spaces'])
        for s in item['spaces']:
            assert s['anchor_source'] in ('gt_original','gt_manual_revision','cluster_medoid')
            assert s['anchor_junction_count']>=3
            assert s['human_n']==len(s['members'])


def test_real_doorway_frequency_and_oos_example(inventory):
    by={i['image_id']:i for i in inventory}
    door=by['2t7WUuJeko7_53937db036374126830e0f1203b04ead']
    assert sum(s['human_n'] for s in door['spaces'])==8
    assert len([s for s in door['spaces'] if s['human_n']])>=2
    oos=by['b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15']
    assert oos['oos'] and all(s['anchor_source']=='cluster_medoid' for s in oos['spaces'])


def test_hemisphere_projection_bounded():
    p=np.array(ring(top=271.5));assert inv.anchor_eligible(p)
    p[0,1]=290;assert not inv.anchor_eligible(p)
