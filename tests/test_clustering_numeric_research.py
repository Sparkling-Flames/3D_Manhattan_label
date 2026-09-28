import sys,math,itertools,json,os,zipfile,hashlib
from pathlib import Path
import numpy as np,pandas as pd,pytest
REPO=Path(__file__).resolve().parents[1]
RECEIVED=REPO/'analysis_results/clustering_numeric_received_20260920'
os.environ.setdefault('CLUSTER_OUT',str(RECEIVED/'results'))
sys.path.insert(0,str(REPO/'tools/thesis_main/analysis/clustering_numeric_research'))
from common import *
from audit_numeric import independent_assignment,bottleneck_independent,cyclic_independent
from prefix_replay import PrefixEngine
from sensitivity_3d import geometry,perturb
from compare_runs import compare

def test_received_payload_is_unchanged():
    manifest=json.loads((RECEIVED/'DELIVERY_MANIFEST.json').read_text(encoding='utf8'))
    with zipfile.ZipFile(RECEIVED/'received_code.zip') as z:
        for row in manifest['files']:
            name=row['path']
            data=z.read(name) if name.startswith(('code/','tests/')) else (RECEIVED/name).read_bytes()
            assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],name

def test_cross_platform_float_json_and_bound_manifest(tmp_path):
    for side,value in [('a',9.0),('b',9.0+1e-14)]:
        folder=tmp_path/side/'source_replay';folder.mkdir(parents=True)
        payload=json.dumps({'ids':['worker-a','worker-b'],'labels':[1,2],'distance':value})
        (folder/'groups.json').write_text(payload,encoding='utf8')
        manifest={'inputs':'same','files':{'groups.json':hashlib.sha256(payload.encode()).hexdigest()}}
        (folder/'EXPERIMENT_MANIFEST.json').write_text(json.dumps(manifest),encoding='utf8')
    assert compare(tmp_path/'a',tmp_path/'b',tmp_path/'check')
    # A small float tolerance must never conceal changed discrete membership.
    path=tmp_path/'b/source_replay/groups.json'
    data=json.loads(path.read_text());data['labels']=[1,1];path.write_text(json.dumps(data))
    manifest_path=path.parent/'EXPERIMENT_MANIFEST.json'
    manifest=json.loads(manifest_path.read_text());manifest['files']['groups.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    assert not compare(tmp_path/'a',tmp_path/'b',tmp_path/'check_changed')
    # Equal copies of an invalid manifest must not bypass file verification.
    for side in ['a','b']:
        folder=tmp_path/side/'source_replay'
        (folder/'groups.json').write_text('{}')
        (folder/'EXPERIMENT_MANIFEST.json').write_text(json.dumps({'files':{'groups.json':'bad'}}))
    assert not compare(tmp_path/'a',tmp_path/'b',tmp_path/'check_bad_manifest')

@pytest.mark.parametrize('y',[10,100,250,300,450])
def test_same_vertical_pixel_shift_has_same_sphere_angle(y):
    assert angle_matrix([[500,y]],[[500,y+5]])[0,0]==pytest.approx(5*180/512,abs=1e-11)
    assert image_matrix([[500,y]],[[500,y+5]])[0,0]==5

def test_seam_and_latitude():
    assert image_matrix([[1023,200]],[[1,200]])[0,0]==2
    assert angle_matrix([[500,100]],[[505,100]])[0,0]<angle_matrix([[500,250]],[[505,250]])[0,0]
    assert angle_matrix([[0,300]],[[1024,300]])[0,0]<1e-10

def test_max_is_not_accumulated_difference():
    d=image_matrix([[1,100],[10,300]],[[3,100],[14,300]]);assert np.diag(d).max()==4;assert np.diag(d).sum()==6

@pytest.mark.parametrize('kind',['complete','representative'])
def test_identity_stable_partition(kind):
    ids=['c','a','b'];d=np.array([[0.,8,16],[8,0,8],[16,8,0]])
    l,reps=partition(d,ids,9,kind)
    for order in itertools.permutations(range(3)):
        order=list(order);ll,rr=partition(d[np.ix_(order,order)],[ids[i] for i in order],9,kind)
        assert dict(zip(ids,l))==dict(zip([ids[i] for i in order],ll));assert rr==reps
    assert len(set(l))==(2 if kind=='complete' else 1)

@pytest.mark.parametrize('seed',range(4))
def test_partition_guarantees(seed):
    rng=np.random.default_rng(seed);x=rng.normal(size=(9,2));d=np.linalg.norm(x[:,None]-x[None,:],axis=2);ids=[f'id{i}' for i in range(9)];t=1.
    for kind in ['complete','representative']:
        l,r=partition(d,ids,t,kind)
        for k in range(1,l.max()+1):
            ix=np.flatnonzero(l==k);j=ids.index(r[k-1]);assert np.round(d[ix,j],8).max()<=t
            if kind=='complete':assert np.round(d[np.ix_(ix,ix)],8).max()<=t

def test_hard_point_count_gate_is_not_real_distance():
    d=np.array([[0.,BLOCK],[BLOCK,0.]]);assert next_uncovered(d,1,9)==1
    for kind in ['complete','representative']:assert len(set(partition(d,['a','b'],9,kind)[0]))==2

def test_independent_dp_unique_ambiguous_and_unbalanced():
    p=np.array([[10,100],[20,100],[10,400],[20,400.]])
    l,n,c=independent_assignment(p,np.array([0,1]),np.array([2,3]));assert n==1 and c==0
    p[:,0]=10;l,n,c=independent_assignment(p,np.array([0,1]),np.array([2,3]));assert n==2
    assert independent_assignment(p,np.array([0]),np.array([2,3]))[1]==0

@pytest.mark.parametrize('seed',range(4))
def test_free_matching_bruteforce(seed):
    rng=np.random.default_rng(seed);d=rng.random((5,5));v,mp=bottleneck_independent(d)
    brute=min(max(d[i,j] for i,j in enumerate(perm)) for perm in itertools.permutations(range(5)))
    assert v==brute;cyc,_=cyclic_independent(d);assert v<=cyc<=np.diag(d).max()

@pytest.mark.parametrize('k',[1,2,3,4,5])
def test_exact_pair_uncovered_bruteforce(k):
    d=np.abs(np.arange(6)[:,None]-np.arange(6)[None,:]).astype(float);t=1.;values=[]
    for ix in itertools.combinations(range(6),k):
        remaining=[i for i in range(6) if i not in ix];values.append((d[np.ix_(remaining,ix)]>t).all(1).mean())
    assert next_uncovered(d,k,t)==pytest.approx(np.mean(values),abs=1e-14)
    assert np.isnan(next_uncovered(d,6,t))

@pytest.mark.parametrize('k',[1,2,3,4,5,6])
def test_fixed_label_expectations(k):
    labels=np.array([1,1,1,2,2,3]);a=[];b=[]
    for ix in itertools.combinations(range(6),k):
        c=np.bincount(labels[list(ix)])[1:];a.append((c>0).sum());b.append((c==1).sum())
    out=fixed_stats(labels,k);assert out['fixed_expected_clusters']==pytest.approx(np.mean(a));assert out['fixed_expected_singletons']==pytest.approx(np.mean(b))

def test_prefix_does_not_use_full_labels_for_reclustering():
    # B is a newly available representative connecting A and C, but A/C remain far.
    d=np.array([[0,16,8],[16,0,8],[8,8,0.]])
    eng=PrefixEngine({'sphere':d,'image':d},['a','b','c'],cuts=(9.,))
    before=eng.node(3);after=eng.node(7)
    assert before[0][1,0]==2 and after[0][1,0]==1
    assert before[0][1,4]==1  # Hindsight label view differs from available-prefix partition.
    assert before[0][0,8]==before[0][1,8]  # Pair coverage does not depend on kind.

def test_3d_conditional_sensitivities():
    a=np.array([100.,(90-30)*512/180-.5]);b=np.array([100.,(90+5)*512/180-.5]);_,_,rho,h,_=geometry(a,b)
    aa,bb=perturb(a,b,'top_y',5);assert geometry(aa,bb)[2]==rho
    aa,bb=perturb(a,b,'joint_x',5);assert geometry(aa,bb)[2:4]==(rho,h)
    aa,bb=perturb(a,b,'bottom_y',5);assert geometry(aa,bb)[2]/rho-1==pytest.approx(math.tan(math.radians(5))/math.tan(math.radians(5+5*180/512))-1,abs=1e-12)
    aa,bb=perturb(a,b,'bottom_y',-20);assert geometry(aa,bb)[4]!='conditional_valid'

def test_saved_numerical_audits():
    n=json.loads((OUT/'NUMERIC_AUDIT.json').read_text());assert n['original_points_changed']==0 and n['changed_coclustering_relations']==0
    assert n['raw_records']==2501 and n['bound_available']==2343 and n['partitions_verified']==5712
    p=json.loads((OUT/'PREFIX_AUDIT.json').read_text());assert p['coverage_partition_invariance']
    q=json.loads((OUT/'PERSONNEL_AUDIT.json').read_text());assert q['changed_old_roster_rows']==0 and not q['frozen_time_changed']

def test_no_target_building_leakage():
    for f in ['refitted_lobo_profiles.csv','geometry_lobo_profiles.csv']:
        d=pd.read_csv(OUT/'personnel'/f);assert all(x.heldout_building not in x.train_building_ids.split('|') for x in d.itertuples())
    d=pd.read_csv(OUT/'model_bridge/lobo_predictions.csv');assert all(x.heldout_building not in x.train_buildings.split('|') for x in d.itertuples())

def test_deferred_cases_not_adjudicated():
    d=json.loads((OUT/'review/comment_replies_16_plus_unb.json').read_text());assert len(d)==17
    assert sum(x['original_answer']['defer'] for x in d[:16])==8
    assert not any(x['new_visual_review'] for x in d)

def test_subtype_remaining_person_denominator():
    d=pd.read_csv(OUT/'personnel/subtype_prefix_checkpoints.csv');assert (d.images_with_remaining_person<=d.images).all()
    z=d[(d.config=='TRI_3')&(d.subtype==1)&(d.k==3)&(d.condition=='manual')]
    assert (z.images_with_remaining_person==0).all() and z.pair_uncovered.isna().all()
