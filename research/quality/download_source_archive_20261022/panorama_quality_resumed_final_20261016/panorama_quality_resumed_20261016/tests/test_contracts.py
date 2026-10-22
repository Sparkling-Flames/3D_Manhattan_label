from pathlib import Path
import sys,json,copy
import numpy as np,pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from controls import geom,transform,redundant
from envelope_quality import normalized_pair,NormalizedConfig,shell
from b8_models import score,configs
from score_manifest import score_record,geometry_hash
SQ=geom([[-2,-2],[2,-2],[2,2],[-2,2]])
@pytest.mark.parametrize('yaw',[0,1,37,90,173,270,359])
def test_common_yaw(yaw):
 a=geom([[-2,-2],[2.3,-2],[1.9,2],[-2,2]],[1.8,2.3,2.1,2]);r=SQ
 x=normalized_pair(a,r);y=normalized_pair(transform(a,angle=yaw),transform(r,angle=yaw))
 assert abs(x['score_l2']-y['score_l2'])<1e-9
@pytest.mark.parametrize('n',[0,1,2,3])
def test_ring(n):
 a=transform(SQ,scale=1.2);x=normalized_pair(a,SQ);y=normalized_pair(transform(a,roll=n,reverse=True),transform(SQ,roll=3-n))
 assert abs(x['score_l2']-y['score_l2'])<1e-9
@pytest.mark.parametrize('scale',[.1,1.,10.])
def test_reference_relative_normalization(scale):
 a=transform(SQ,angle=8);x=normalized_pair(a,SQ);y=normalized_pair(transform(a,scale=scale),transform(SQ,scale=scale))
 assert abs(x['score_l2']-y['score_l2'])<1e-9
@pytest.mark.parametrize('p',[SQ,geom([[-2,-2],[2,-2],[3,2],[-2,2]]),geom([[-2,-2],[2,-2],[2,2],[0,1],[-2,2]],[2,2.5,2,1.7,2])])
def test_legal_reference_self(p):assert abs(normalized_pair(p,p)['score_l2']-100)<1e-9

def test_full_redundancy():
 a=geom([[-2,-2],[2,-2],[2,2],[-2,2]],[1.5,2,2.5,2]);assert abs(normalized_pair(redundant(a),a)['score_l2']-100)<1e-9

def test_top_peak_not_discarded():
 a=geom([[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]],[2,3,2,2,2]);m=normalized_pair(a,SQ);assert m['I']==1 and m['Hcenter']>0 and m['score_l2']<100

def test_invalid_not_zero():
 r=normalized_pair(geom([[-2,-2],[2,2],[-2,2],[2,-2]]),SQ);assert r['status']=='not_evaluable' and r['score'] is None

def test_missing_not_zero():assert normalized_pair({'bottom3d':SQ['bottom3d']},SQ)['score'] is None

def test_camera_outside_not_silently_dropped():
 r=normalized_pair(transform(SQ,shift=(3,0)),SQ);assert r['status']=='complete' and r['answer_camera_inside']==False

def test_no_overlap_is_zero():assert normalized_pair(transform(SQ,shift=(10,0)),SQ)['score']==0
@pytest.mark.parametrize('c',configs())
def test_B_component_monotonicity(c):
 assert float(score(0,0,0,0,0,c))==0
 assert float(score(.8,1,3,.1,.1,c))>float(score(.6,1,3,.1,.1,c))
 assert float(score(.8,1,3,.1,.1,c))>float(score(.8,2,4,.2,.2,c))

def admitted():
 p=copy.deepcopy(json.loads((ROOT/'inputs/fixed_pairs.json').read_text())[0]);return p
@pytest.mark.parametrize('key,value,status',[('reference_complete',False,'reference_incomplete'),('original_quality_eligible',False,'not_admitted'),('source_pool_workers',2,'source_pool_below3'),('worker_id','W019','not_admitted'),('current_target_id','another_reference','binding_error'),('reference_sha256','wrong','hash_error')])
def test_manifest_holds(key,value,status):
 p=admitted();p[key]=value;r=score_record(p);assert r['status']==status and r['EBC2_L2'] is None

def test_manifest_pure_parameter_identity():
 p=admitted();r=score_record(p);assert r['status']=='complete';assert r['B8L2_D10']>=r['B8L2'];assert r['reference_id']==p['reference_id']
