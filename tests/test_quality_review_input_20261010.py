import copy
import csv
import json
from collections import Counter
import pytest
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input
from tools.thesis_main.data_prep.apply_quality_review_20261010 import ROOT, read_update, apply_data

@pytest.fixture(scope='module')
def pair():
    raw=json.loads((ROOT/'analysis_results/research_input_20260929/preprocessed_source.json').read_text(encoding='utf-8'))
    return raw,load_current_bundle()

def test_formal_integration_and_nonmutation(pair):
    raw,b=pair;old={o['object_id']:o for o in raw['objects']};new={o['object_id']:o for o in b['data']['objects']}
    assert set(old)==set(new) and b['validation']['confirmed_orders']==1312
    patched=[o for o in new.values() if o.get('quality_review_provenance')]
    assert len(patched)==14 and all(o['ring_confirmed'] for o in patched)
    effects={o['quality_review_provenance']['record_id']:o['quality_review_provenance']['order_effect'] for o in patched}
    assert {rid for rid,effect in effects.items() if effect=='review_x_adjacency_changed'}=={'R00669','R02155','R02963'}
    assert Counter(effects.values())=={'review_x_adjacency_changed':3,'review_x_candidate_retained':11}
    changes={r['dimensions']['change']:r['n'] for r in b['research']['cross_tables']['order_changes_by_kind'] if r['dimensions']['object_kind']=='annotation'}
    assert changes['review_x_adjacency_changed']==3 and changes['review_x_candidate_retained']==11
    assert 'new_pairing_and_reviewed_order' not in changes
    assert b['final_summary']['geometry']['surface_valid']==3014
    assert b['final_summary']['geometry']['pairing_unavailable']==129
    assert sum(bool(o['geometry']['issues']) for o in patched)==3
    for k,o in new.items():
        assert o['original_export_points']==old[k]['original_export_points']
        for field in ('cleaning_disposition','independent_vote_eligible','main_consensus_gate'):
            if field in o: assert o[field]==old[k][field]
        if o['object_kind']!='annotation':
            for field in ('preprocessed_points','points_1024x512','links_zero_based','order_record'):
                assert o[field]==old[k][field]
    assert all(o['worker_id'] not in ('W019','W026') for o in patched)
    assert {o['quality_review_provenance']['record_id'] for o in patched}.isdisjoint({'R00003','R00013','R00089','R01210'})


def test_109_queue_partition_and_source_identity(pair):
    raw,_=pair
    path=ROOT/'analysis_results/point_edit_review_20261009/109份审核范围与返回核对_20261010.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==len({r['record_id'] for r in rows})==109
    assert Counter(r['final_scope'] for r in rows)=={'excluded_worker':84,'resolved_outside_queue':11,'current_review_14':14}
    source={(str(o['source']['project']),str(o['source']['task']),str(o['source']['annotation']),o['image_id']):o
            for o in raw['objects'] if isinstance(o['source'],dict)}
    for r in rows:
        o=source[(r['source_project'],r['source_task'],r['source_annotation'],r['image_id'])]
        assert (r['worker_formal'],int(r['original_point_count']))==(o['worker_id'],len(o['original_export_points']))
        assert (r['final_scope']=='excluded_worker')==(o['worker_id'] in {'W019','W026'})
    excluded=[r for r in rows if r['final_scope']=='excluded_worker']
    assert Counter(r['worker_formal'] for r in excluded)=={'W019':57,'W026':27}
    assert sum(r['image_oos_confirmed']=='true' and int(r['original_point_count'])<8 for r in excluded)==11
    assert {r['record_id'] for r in rows if r['final_scope']=='current_review_14'}==set(read_update()['accepted_records'])
    resolutions=json.loads((ROOT/'research/point_review_109_received_20261009/queue_resolution_20261010.json').read_text(encoding='utf-8'))['records']
    assert set(resolutions)=={r['record_id'] for r in rows if r['final_scope']=='resolved_outside_queue'}
    assert Counter(x['outcome'] for x in resolutions.values())=={'existing_invalid':5,'retained_oos_uncalculable':5,'oos_no_effective_points':1}

def test_image_policy_and_score_not_changed(pair):
    _,b=pair;im={i['image_code']:i for i in b['data']['images']}
    assert im['x8F5xyUWy9e-01']['quality_review_20261010']['quality_reference_hold']
    assert not im['x8F5xyUWy9e-09']['quality_review_20261010']['quality_reference_hold']
    assert im['wc2JMjhGNzB-14']['quality_review_20261010']['quality_reference_hold']
    assert b['quality_update']['confirmed_policy']['scoring_implementation_changed'] is False
    for o in b['data']['objects']:
        if o['object_kind']=='annotation' and o['image_code'] in ('x8F5xyUWy9e-01','wc2JMjhGNzB-14'):
            assert o['main_quality_gate']['status'] in ('excluded','hold_reference_quality')

def test_loaders_identical_and_idempotent(pair):
    _,b=pair;direct=load_current_input()
    assert direct==b['data']
    assert apply_data(copy.deepcopy(direct),read_update())==direct

@pytest.mark.parametrize('mutation',['raw','source','return'])
def test_corruption_rejected(pair,mutation):
    raw,_=pair;data=copy.deepcopy(raw);u=read_update();first=next(iter(u['accepted_records'].values()));oid=first['identity']['canonical_object_id'];o=next(o for o in data['objects'] if o['object_id']==oid)
    if mutation=='raw':o['original_export_points'][0][0]+=1
    elif mutation=='source':o['source']['annotation']=-1
    else:first['points'][0]['x']+=1
    with pytest.raises(ValueError):apply_data(data,u)

def test_public_projection_exposes_policy(pair):
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    _,b=pair;panel,_=project_bundle(b)
    assert panel['source_manifest']['quality_update_revision']=='quality_review_20261010_v1'
    im=next(i for i in panel['images'] if i['code']=='x8F5xyUWy9e-01')
    assert all(not r['quality_candidate'] for r in im['annotations'])
