"""Read-only display packing, exact context bindings, and distinct support denominators."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from tools.thesis_main.analysis import build_research_workbench_v2_20261019 as builder


def row(oid, image='image', worker='W1', condition='manual', ref='ref'):
    return dict(object_id=oid,image_id=image,image_code=image,building_id='building',
                worker_id=worker,condition=condition,reference_id=ref,reference_version='frozen',
                quality_usable=True,independent_vote_eligible=True,cleaning_disposition='retained',
                is_doorway=False,is_oos=False,quality_use='ordinary_primary',quality_exclusion_reasons=[])


def test_support_keeps_conditions_references_and_independent_denominators_separate():
    rows = [row('a'),row('b',worker='W2'),row('c',condition='semi'),row('d',ref='alternative')]
    result = builder.build_support_payload(rows)
    assert result['totals'] == dict(records=4,images=1,workers=2,buildings=1,
        reference_bindings=2,quality_records=4,independent_vote_records=4)
    assert len(result['matrix']) == 3
    assert {(r['condition'],r['reference_id'],r['records']) for r in result['matrix']} == {
        ('manual','ref',2),('manual','alternative',1),('semi','ref',1)}
    manual = next(r for r in result['constant_support_cohorts']
                  if r['condition']=='manual' and r['minimum_people']==2)
    semi = next(r for r in result['constant_support_cohorts']
                if r['condition']=='semi' and r['minimum_people']==2)
    assert manual['images']==1 and semi['images']==0


def saved_state():
    return dict(n=1,minimum_support=1,assignments=[dict(id='a',worker='W1')],
                identity_groups=[dict(feature_id='node_000',support=1,selected=True)],
                candidate=dict(points=[[1,2],[1,3]],footprint=[[4,5]],feature_ids=['node_000'],
                    ring_confirmed=False,order_status='source_suggestion',geometry_status='ok',
                    status='geometry_review',reason='unconfirmed'),
                node_consensus={'status':'ready'},ring_diagnostics={'edges':[]})


def test_saved_state_preserves_geometry_missing_scores_and_unconfirmed_ring():
    source = saved_state()
    untouched = deepcopy(source)
    result = builder.pack_saved_state(source,'image','ref',{'a':row('a')},dict(B8L2=12.5))
    assert result['points'] == source['candidate']['points']
    assert result['footprint'] == source['candidate']['footprint']
    assert result['identity_groups'] == source['identity_groups']
    assert result['ring_diagnostics'] == source['ring_diagnostics']
    assert result['D10'] is None and result['ring_confirmed'] is False
    assert result['connected'] is True  # Saved algorithm connection is not human confirmation.
    assert source == untouched


@pytest.mark.parametrize('field,value', [('image_id','other'),('condition','semi'),
                                        ('reference_id','other'),('worker_id','W2')])
def test_saved_state_rejects_cross_context_votes(field,value):
    record = row('a');record[field]=value
    with pytest.raises(ValueError,match='binding mismatch'):
        builder.pack_saved_state(saved_state(),'image','ref',{'a':record})


def test_read_only_packer_does_not_import_or_run_research_engines():
    source = Path(builder.__file__).read_text(encoding='utf-8')
    assert 'view-data.js\'\n    single = json.loads' not in source
    assert "single_source = ROOT/'research/workers/personnel_type_validation_next_20261019/CASE_SCORE_AUDIT.json'" in source
    for forbidden in ('import fusion_engine','scoring_engine(', 'compute_score(', 'score_task(', 'fe.fuse('):
        assert forbidden not in source


def test_materialized_evidence_has_real_selected_states_and_offline_twin():
    path = builder.PAGE/'v2-resources/research_evidence.json'
    if not path.exists():
        pytest.skip('Run the v2 workbench builder for integration payload checks.')
    data = builder.read(path)
    assert data['snapshot_id']==builder.SNAPSHOT
    assert [r['id'] for r in data['quality']['cases']]==['S1','S2','S3','YQ24']
    for case in data['quality']['cases']:
        assert case['image_id'] and case['reference_id']==case['reference']['target_id']
        assert case['condition']=='manual'
        assert all(answer['points'] and 'components' in answer for answer in case['answers'])
    q9 = data['fusion']['cases'][0]
    assert [r['k'] for r in q9['nodes']] == list(range(5,21))
    assert q9['before']['k']==16 and q9['after']['k']==17
    assert q9['after']['ring_diagnostics']['edges']
    assert any(not r['selected'] for r in q9['after']['identity_groups'])
    assert len(data['fusion']['cases'])==8
    assert all(r['observation_status']=='unknown' for r in data['doorway']['cases'])
    assert len(data['doorway']['cases'])==19
    assert data['doorway']['non_oos_images']==17
    assert data['support']['totals']['records']==10439
    assert data['support']['retained']['workers']==60
    assert data['support']['totals']['quality_records']==7302
    script = path.with_suffix('.js').read_text(encoding='utf-8')
    assert script.startswith('window.researchLocalData[document.currentScript.src')
    assert json.loads(script.split(']= ',1)[1].strip().rstrip(';'))==data
    assert all((builder.ROOT/s['path']).is_file() for s in data['sources'])


def test_saved_state_rejects_mismatched_source_point_pair():
    state = saved_state()
    state['identity_groups'][0]['members'] = [dict(id='a',worker='W1',pair_index=0,points=[[9,9],[9,10]])]
    record = dict(row('a'),points_1024x512=[[1,2],[1,3]])
    with pytest.raises(ValueError,match='source geometry mismatch'):
        builder.pack_saved_state(state,'image','ref',{'a':record})


def test_selected_saved_geometry_and_scores_equal_frozen_sources():
    path = builder.PAGE/'v2-resources/research_evidence.json'
    if not path.exists():
        pytest.skip('Run the v2 workbench builder for integration payload checks.')
    data = builder.read(path)
    teams_path = builder.ROOT/'research/workers/personnel_composition_followup_20261019/TEAMS.json.gz'
    states_path = builder.ROOT/'research/fusion/fusion_change_mechanisms_20261020/STATES.json.gz'
    if not teams_path.exists() or not states_path.exists():
        pytest.skip('Frozen source inputs have not been materialized in this checkout.')
    teams = builder.read(teams_path)
    for case in data['quality']['cases'][:3]:
        for answer in case['answers']:
            source = teams[answer['team_key']]
            assert answer['points']==source['geometry']['points']
            assert answer['footprint']==source['geometry']['footprint']
            assert answer['B8L2']==source['B8L2'] and answer['D10']==source['D10']
            assert answer['workers']==source['member_workers']
            assert answer['components']=={k:source[k] for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')}
    states = builder.read(states_path)
    for node in data['fusion']['cases'][0]['nodes']:
        source = states[node['team_key']]
        assert node['points']==source['candidate']['points']
        assert node['identity_groups']==source['identity_groups']
        assert node['assignments']==source['assignments']
        assert node['ring_diagnostics']==source['ring_diagnostics']
