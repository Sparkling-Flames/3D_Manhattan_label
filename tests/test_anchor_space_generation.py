import copy
import json
import numpy as np
import pytest
from tools.thesis_main.analysis import anchor_space_generation as gen
from tools.thesis_main.analysis import space_inventory_anchor as inv
from tools.thesis_main.analysis.export_synthetic_label_studio import export_samples


def entry():
    p=[[x,y] for x in (50,200,400,600,800) for y in (140,380)]
    s=dict(space_id='i:alt',space_kind='alternative',anchor_source='cluster_medoid',anchor_annotation_id='human',anchors=p,human_n=8,human_frequency=1.,pair_count_histogram={'5':8},scope_expected='oos',scope_counts={'oos':8},jitter_calibration={'quantiles':np.linspace(1,10,101).tolist(),'method':'fixture'})
    return dict(image_id='i',spaces=[s])


@pytest.mark.parametrize('wild,op',[(False,None),(True,'bounded_jitter'),(True,'continuous_subset'),(True,'alternative_space'),(True,'merge_collinear')])
def test_operations_are_bounded_valid_and_deterministic(wild,op):
    e=entry();frozen=copy.deepcopy(e)
    a,m,s=gen.generate_geometry(e,np.random.default_rng(7),wild,op)
    b,n,t=gen.generate_geometry(e,np.random.default_rng(7),wild,op)
    assert np.array_equal(a,b) and m==n and e==frozen
    assert inv.nearest(a,s['anchors']).max()<=20
    assert inv.base.geometry_status(a)==inv.VALID
    assert len(a)>=6
    if op=='continuous_subset':
        assert m['space_kind']=='subrange' and len(a)<10
        assert m['anchor_junction_count']==len(a)//2
        active=np.asarray(s['anchors']).reshape(-1,2,2)[m['anchor_pair_indices']].reshape(-1,2)
        assert np.allclose(inv.nearest(a,active),m['corner_anchor_dist_px'])


def test_scope_coherence_is_diagnostic():
    s=entry()['spaces'][0]
    assert gen.coherence(s,'oos')['consistent']
    assert not gen.coherence(s,'in_scope')['consistent']


def test_sample_identity_schema_and_export_roundtrip(monkeypatch,tmp_path):
    from tools.thesis_main.analysis import difficulty_wild_run as legacy
    old=dict(simulation_id='old',source_worker_profile_id='1',condition='manual',image_id='i',synthetic=True,wild=False,worker_scope_response='oos',lead_time_seconds=10.,generation_parameters={},source_hashes={},difficulty='简单',difficulty_version='v6',difficulty_source='fixture',wild_budget_k=0,need=1,real_manual_n=34,gt_error_excluded=False,pending_review=False,scope_reference_status='confirmed_full')
    monkeypatch.setattr(legacy,'sample_row',lambda *args:copy.deepcopy(old))
    row=gen.sample_row({},dict(image_id='i'),{},entry(),20261017,0,0)
    assert row['export_worker_id']=='S_MANUAL_300000'
    export_samples([row],{'i':dict(image_url='https://example.org/i.jpg')},tmp_path)
    ann=json.loads((tmp_path/'label_studio_synthetic.json').read_text())[0]['annotations'][0]
    for k in ('space_id','space_kind','corner_anchor_dist_px','space_scope_coherence','space_inventory_version'):
        assert ann[k]==row[k]


def test_quantile_calibration_typical_distribution():
    ds=[]
    for seed in range(100):
        p,m,s=gen.generate_geometry(entry(),np.random.default_rng(seed))
        ds.extend(m['corner_anchor_dist_px'])
    assert np.quantile(ds,.95)<=15 and max(ds)<=20


def test_output_exclusivity(tmp_path):
    from tools.thesis_main.analysis.anchor_space_run import run
    with pytest.raises(FileExistsError):run(tmp_path)


def test_collinear_merge_removes_only_wall_middle_vertex():
    xy=np.array([[1,1],[0,1],[-1,1],[-1,-1],[1,-1]],float)
    x=(np.arctan2(xy[:,0],-xy[:,1])/(2*np.pi)+.5)*1024
    b=256+np.arctan2(1.,np.linalg.norm(xy,axis=1))*512/np.pi
    p=np.array([[xx,yy] for xx,yyb in zip(x,b) for yy in (512-yyb,yyb)])
    assert gen.deletion_indices(p)==[1]
    e=entry();e['spaces'][0]['anchors']=p.tolist()
    q,m,s=gen.generate_geometry(e,np.random.default_rng(1),True,'merge_collinear')
    assert 'merge_collinear' in m['anchor_operations'] and len(q)==8
    assert inv.nearest(q,p).max()<=20


def test_stratified_space_sampling_respects_empirical_frequency(monkeypatch):
    from tools.thesis_main.analysis import difficulty_wild_run as legacy
    old=dict(wild=False,generation_parameters={},worker_scope_response='oos')
    monkeypatch.setattr(legacy,'sample_row',lambda *args:copy.deepcopy(old))
    e=entry();other=copy.deepcopy(e['spaces'][0]);e['spaces'][0]['human_frequency']=.875
    other.update(space_id='i:rare',human_frequency=.125);e['spaces'].append(other)
    rows=[gen.sample_row({},dict(image_id='i',need=16),{},e,20261017,i,0) for i in range(16)]
    assert sum(r['sampled_space_id']=='i:rare' for r in rows)==2
