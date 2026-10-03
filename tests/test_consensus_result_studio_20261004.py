import copy
import json

import pytest

from tools.thesis_main.analysis.consensus_result_studio_20261004 import (
    attach_global_results, variant_for_cluster,
)
from tools.thesis_main.analysis.global_pair_consensus_20261004 import build_global_pair_consensuses


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


def test_global_display_uses_entire_roster_and_preserves_rule_specific_points(tmp_path):
    rows=[dict(id=f'R{i}',worker=f'P{i}',points=[[float(x),y] for x in xs for y in (120.,390.)])
          for i,xs in enumerate(([128,384,640,896],[128,256,384,640,896]))]
    results=build_global_pair_consensuses(rows)
    for r in results.values():r['reference_metrics']={}
    source=tmp_path/'primary.json'
    source.write_text(json.dumps(dict(images=[dict(image='test',n=2,methods=results)])))
    data=dict(counts={},cases=[dict(demo=dict(image='test',n=2,workers=rows),
        variants=[dict(source=dict(role='consensus_candidate'))])])
    def reset():
        (tmp_path/'data.js').write_text('window.STUDIO_IMAGES={};window.STUDIO_DATA='+json.dumps(data)+';\n')
        (tmp_path/'field_contract.json').write_text('{}')
    reset()
    result=attach_global_results(tmp_path,source)
    c=result['cases'][0]
    assert c['pattern_count']==1
    assert result['counts']['global_candidates']==2
    for method in ('mv50','mv_strict'):
        v=c['variants'][c['global_point_indices'][method]]
        assert v['source']['record_ids']==['R0','R1']
        assert v['source']['candidate_erp']['points']==results[method]['candidate']['points']
        assert [p for pair in v['geometry']['pairs'] for p in (pair['top'],pair['bottom'])]==results[method]['candidate']['points']
        assert v['geometry']['fit']['status']=='not_requested'
    assert len(c['variants'][c['global_point_indices']['mv50']]['source']['candidate']['points'])==10
    assert len(c['variants'][c['global_point_indices']['mv_strict']]['source']['candidate']['points'])==8
    # Equal N is not sufficient: a stale demo roster must fail instead of silently displaying it.
    data['cases'][0]['demo']['workers'][1]['id']='wrong_source'
    reset()
    with pytest.raises(ValueError,match='roster_identity_mismatch'):
        attach_global_results(tmp_path,source)
