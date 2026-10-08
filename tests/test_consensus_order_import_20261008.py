import copy
import json
import pytest
from tools.thesis_main.analysis.consensus_order_import_20261008 import prepare_orders,source_binding


def test_import_binds_coordinates_and_separates_identity_issues():
    s=dict(object_id='fusion:example',effective_points=[[1,2],[1,4],[3,2],[3,4]],
        points=[[1,2],[1,4],[3,2],[3,4]],effective_point_labels=['1','2','3','4'],
        links_zero_based=[[0,1],[2,3]],preprocessing='frozen_consensus_shared_x',feature_ids=['a','b'],default_preview_order=[0,1])
    live=dict(image='example',n=3,node_consensus={'nodes':[
        dict(feature_id='a',points=s['points'][:2]),dict(feature_id='b',points=s['points'][2:])]},
        candidate={'feature_ids':['a','b']})
    doc=dict(schema='fusion_order_review_20261008_v1',examples_only=False,records={s['object_id']:
        dict(binding=json.dumps(source_binding(s)),status='confirmed',order=[1,0],note='')})
    assert prepare_orders(doc,[s],[live])['accepted'][0]['manual_order']==['b','a']
    changed=copy.deepcopy(live);changed['node_consensus']['nodes'][0]['points'][0][0]=2
    assert prepare_orders(doc,[s],[changed])['pending'][0]['reason']=='needs_order_reconfirmation'
    doc['records'][s['object_id']]['status']='pairing'
    assert prepare_orders(doc,[s],[live])['pending'][0]['reason']=='needs_identity_review'
    doc['records'][s['object_id']]['order']=[0,0]
    with pytest.raises(ValueError,match='permutation'):prepare_orders(doc,[s],[live])


def test_resolved_incomplete_consensus_is_not_requeued_or_order_certified(tmp_path,monkeypatch):
    from tools.thesis_main.analysis import consensus_order_import_20261008 as module
    from tools.thesis_main.analysis.research_artifact_io import write_json
    workbench=tmp_path/'order_workbench';workbench.mkdir()
    for path,data in [(workbench/'user_order_review_20261008.json',{}),
                      (workbench/'sources.json',{'objects':[]}),(tmp_path/'outputs.json',[])]:
        write_json(path,data)
    item=dict(image='example',identity_review_resolution={'outcome':'retain_incomplete_consensus'},
              review_issue={'status':'incomplete_consensus_observed','note':'3 nodes retained'})
    write_json(tmp_path/'user_followup.json',{'records':[item]})
    monkeypatch.setattr(module,'OUT',tmp_path)
    monkeypatch.setattr(module,'prepare_orders',lambda *args:dict(accepted=[],unsubmitted=[],
        pending=[dict(image='example',reason='needs_identity_review',note='missing nodes')]))
    module.run()
    result=json.loads((tmp_path/'order_import.json').read_text(encoding='utf-8'))
    assert result['pending']==[] and result['accepted']==[]
    assert result['resolved_by_followup'][0]['resolution']==item['identity_review_resolution']
    assert json.loads((tmp_path/'user_followup.json').read_text(encoding='utf-8'))['records']==[item]
