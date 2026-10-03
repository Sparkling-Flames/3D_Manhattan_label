import copy

import pytest

from tools.thesis_main.analysis.consensus_result_studio_20261004 import variant_for_cluster


def test_result_studio_keeps_full_candidate_points_and_disables_manhattan_fit():
    points=[[128.,120.],[128.,390.],[384.,118.],[384.,392.],
            [640.,125.],[640.,385.],[896.,122.],[896.,388.]]
    cluster=dict(id='pattern_01',members=['R2','R9'],workers=['P2','P9'],support=2,
        representative='R9',pair_count=4,candidate=dict(status='ok',reason=None,points=points,
        erp_key='R2|R9',source_pair_maps=[dict(id='R2',indices=[3,0,1,2])]))
    workers={'R2':dict(id='R2',worker='P2',erp={'points':points}),
             'R9':dict(id='R9',worker='P9',erp={'points':points})}
    before=copy.deepcopy(cluster)
    result=variant_for_cluster(cluster,workers,{'R2|R9':{'points':points}})
    assert cluster==before
    assert result['geometry']['fit']['status']=='not_requested'
    assert result['geometry']['coordinate_convention']=='continuous'
    assert result['geometry']['coordinate_convention_source']=='payload_and_argument'
    restored=[p for pair in result['geometry']['pairs'] for p in [pair['top'],pair['bottom']]]
    assert restored==points
    assert result['source']['representative']['id']=='R9'
    assert result['source']['cluster']['candidate']['source_pair_maps']==cluster['candidate']['source_pair_maps']
    assert [r['id'] for r in result['source']['members']]==['R2','R9']
    assert result['source']['candidate_erp']['points']==points
    broken=copy.deepcopy(cluster);broken['members'].append('missing')
    with pytest.raises(ValueError,match='member_identity'):
        variant_for_cluster(broken,workers,{'R2|R9':{}})


def test_unavailable_result_is_retained_without_inventing_points():
    cluster=dict(id='pattern_02',members=['R1'],workers=['P1'],support=1,representative='R1',
        pair_count=None,candidate=dict(status='unavailable',reason='invalid_points',points=None,erp_key='R1'))
    result=variant_for_cluster(cluster,{'R1':dict(id='R1',worker='P1',erp={})},{})
    assert result['error']=='invalid_points'
    assert 'geometry' not in result
    assert result['source']['cluster']['candidate']['points'] is None
