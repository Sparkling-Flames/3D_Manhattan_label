import copy
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.clustering_release.pipeline import intake, corrected, rows_at, REPO


def fixture(tmp_path, worker='38', task=9001, aid=9002):
    export=[dict(id=task,data={'image':'https://example.invalid/new_image.png'},annotations=[dict(id=aid,completed_by=int(worker),result=[
        dict(type='keypointlabels',value={'x':20,'y':20}),dict(type='keypointlabels',value={'x':20,'y':80}),
        dict(type='choices',from_name='Scope',value={'choices':['in_scope']})])])]
    p=tmp_path/'export.json';p.write_text(json.dumps(export),encoding='utf8')
    m=dict(batch_id='software_fixture',stage='new_manual',project_id=101,export_path=p.name,worker_map={worker:'W'+worker.zfill(3)},
           tasks=[dict(runtime_task_id=task,image_id='new_image',building_id='new_building',raw_condition='manual',assistance_exposure='none')],
           record_type='independent_initial',annotation_form_version='manual_scope_only_v1')
    f=tmp_path/'manifest.json';f.write_text(json.dumps(m),encoding='utf8')
    return f,p,m,export


def test_append_is_idempotent_but_revision_and_identity_drift_fail(tmp_path):
    manifest,p,m,export=fixture(tmp_path)
    first,_=intake([], [manifest]);second,_=intake(first,[manifest])
    assert first==second and len(first)==1
    assert first[0]['active_time_seconds'] is None and first[0]['active_time_status']=='unfrozen'
    assert first[0]['difficulty_status']=='not_collected' and first[0]['model_issue_status']=='not_applicable'
    assert first[0]['scope_original'][0]['value']['choices']==['in_scope']
    export[0]['annotations'][0]['result'][0]['value']['x']=22;p.write_text(json.dumps(export),encoding='utf8')
    with pytest.raises(ValueError,match='revision'):intake(first,[manifest])
    export[0]['annotations'][0]['id']=9003;p.write_text(json.dumps(export),encoding='utf8')
    with pytest.raises(ValueError,match='Repeated person'):intake(first,[manifest])
    m['tasks'][0]['image_id']='wrong';manifest.write_text(json.dumps(m),encoding='utf8')
    with pytest.raises(ValueError,match='image'):intake([], [manifest])


def test_batch_order_and_combined_loading_produce_same_observations(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    pa,*_=fixture(a);pb,*_=fixture(b,worker='39',task=9011,aid=9012)
    together,_=intake([], [pa,pb]);reverse,_=intake([], [pb,pa])
    first,_=intake([], [pa]);split,_=intake(first,[pb])
    assert together==reverse==split and len(together)==2


def test_confirmed_correction_changes_two_effective_payloads_only():
    rows=rows_at(REPO/'analysis_results/paired_split_research_received_20260920/inputs/responses.jsonl.gz')
    by={r['canonical_annotation_id']:r for r in rows};index={}
    for cid,worker,aid in [('8ffe08f072e2b12e','2','4738'),('9b8f8bec4da82b48','18','4784')]:
        pts=copy.deepcopy(by[cid]['effective_points_1024x512'])
        if worker=='2':
            next(p for p in pts if p[1]>=512)[1]/=10
        else:pts=[p for p in pts if p[1]<512]
        index['3081',worker,aid]=(None,{'result':[dict(type='keypointlabels',value=dict(x=x/1024*100,y=y/512*100)) for x,y in pts]})
    updated,audit=corrected(rows,index,'software_fixture')
    assert len(updated)==2501 and len(audit)==2
    assert all(a['raw_points_1024x512']==b['raw_points_1024x512'] for a,b in zip(rows,updated))
    assert sum(a['effective_points_1024x512']!=b['effective_points_1024x512'] for a,b in zip(rows,updated))==2
    broken=copy.deepcopy(index);broken['3081','2','4738'][1]['result'][0]['value']['x']+=1
    with pytest.raises(ValueError,match='exactly one'):corrected(rows,broken,'bad')


def test_confirmed_odd_repairs_use_effective_points():
    from tools.thesis_main.analysis.clustering_release.release import prepare
    root=REPO/'analysis_results/clustering_release_local_20260920/current'
    _,rows,rec,elig,_=prepare(root)
    repaired=[r for r in rows if r['raw_point_count']%2 and r['effective_point_count'] is not None
              and r['effective_point_count']!=r['raw_point_count']]
    assert len(repaired)==11
    included=[]
    for r in repaired:
        e=elig.set_index('id').loc[r['canonical_annotation_id']]
        if e.excluded_worker:
            assert not e.split_available
            continue
        assert e.split_available
        assert rec[r['canonical_annotation_id']]['p'].tolist()==r['effective_points_1024x512']
        included.append(r)
    assert len(included)==7
    assert sum(r['imputed_point'] for r in included)==2
