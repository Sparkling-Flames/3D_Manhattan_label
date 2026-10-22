import itertools,json
from pathlib import Path
import numpy as np,pytest
from structure_quality import *
from run_audit import geometry_from_points,prism_iou,xz,readj

ROOT=Path(__file__).resolve().parents[1]
R=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float)
B=np.array([[-2,-2],[2,-2],[2,2],[.25,2],[.25,2.3],[-.25,2.3],[-.25,2],[-2,2]],float)
C=working_config()

@pytest.mark.parametrize('p',[R,B,R@np.array([[1,.07],[0,1.]])])
def test_self_reference(p):
 assert structure(p,p,C)['C']==pytest.approx(1,abs=1e-12)
 assert candidate_score(1,0,0,0,structure(p,p,C)['C'],C)==pytest.approx(100)

@pytest.mark.parametrize('k',range(8))
@pytest.mark.parametrize('reverse',[False,True])
def test_ring_serialization(k,reverse):
 b=np.roll(B,k,axis=0)
 if reverse:b=b[::-1]
 assert structure(R,b,C)['C']==pytest.approx(structure(R,B,C)['C'],abs=1e-12)

@pytest.mark.parametrize('fraction',[.1,.25,.5,.9])
def test_exact_collinear_subdivision(fraction):
 p=np.insert(B,1,B[0]+fraction*(B[1]-B[0]),axis=0)
 assert structure(p,B,C)['C']==pytest.approx(1,abs=1e-12)
 assert floor_iou(p,B)==pytest.approx(1)
 assert length_dsc(p,B)['length_dsc']==pytest.approx(1)

@pytest.mark.parametrize('eps',[.001,.01,.03,.1])
def test_tiny_bevel_not_lost_corner(eps):
 p=np.array([[-2,-2],[2,-2],[2,2-eps],[2-eps,2],[-2,2]],float)
 assert structure(p,R,C)['C']==pytest.approx(1)
 assert structure(p,R,Config())['C']<.87

@pytest.mark.parametrize('a,b',[(R,B),(B,R),(R,R+[.2,0]),(R,R@np.array([[1,.05],[0,1]]))])
def test_symmetry(a,b):
 assert structure(a,b,C)['C']==pytest.approx(structure(b,a,C)['C'],abs=1e-12)

@pytest.mark.parametrize('angle',[17.,46.,91.,178.])
def test_common_yaw_invariance(angle):
 t=np.radians(angle);rot=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
 assert structure(R@rot,B@rot,C)['C']==pytest.approx(structure(R,B,C)['C'],abs=1e-10)

def test_protrusion_omission_and_false_positive():
 assert direction_rms(R)<1e-12 and direction_rms(B)<1e-12
 assert floor_iou(R,B)>.99
 s=structure(R,B,C);assert s['precision']==pytest.approx(1);assert s['recall']<.6
 assert structure(B,R,C)['recall']==pytest.approx(1)
 assert structure(B,R,C)['precision']<.6

def test_same_corner_count_wrong_location_not_accepted():
 p=B.copy();p[3:7,0]+=.8
 q=B.copy();q[3:7,0]-=.8
 assert len(p)==len(q)
 assert structure(p,q,C)['C']<.8

def test_input_not_mutated():
 a=B.copy();b=R.copy();av=a.copy();bv=b.copy();structure(a,b,C)
 assert np.array_equal(a,av) and np.array_equal(b,bv)

def test_self_non_manhattan_prior_conflict():
 p=R@np.array([[1,.1],[0,1.]])
 assert float(old_score(1,0,direction_rms(p),0,0))<100
 assert candidate_score(1,0,0,0,structure(p,p,C)['C'],C)==pytest.approx(100)

@pytest.mark.parametrize('bad',[np.array([[0,0],[1,1],[0,1],[1,0]]),np.array([[0,0],[0,0],[1,1]]),np.array([[0,0],[1,np.nan],[1,0]]),np.ones((3,3))])
def test_invalid_geometry_rejected(bad):
 with pytest.raises(ValueError):structure(bad,R,C)

@pytest.mark.parametrize('values',[(.8,np.nan,0,0,.5),(.8,0,0,np.nan,.5),(.8,0,0,0,np.nan),(.8,-1,0,0,.5)])
def test_missing_not_zero_imputed(values):
 with pytest.raises(ValueError):candidate_score(*values,C)

@pytest.mark.parametrize('I',[0,.2,.8,1])
def test_score_structure_monotone(I):
 scores=[candidate_score(I,1,.02,.02,c,C) for c in np.linspace(0,1,50)]
 assert np.diff(scores).min()>=-1e-12
 assert min(scores)>=0 and max(scores)<=100

@pytest.mark.parametrize('component',['I','Sb','Hm','Hc'])
def test_score_component_monotone(component):
 args=dict(I=.8,Sb=1.,Hm=.03,Hc=.02,C=.7);vals=np.linspace(.001,.9,30) if component=='I' else np.linspace(0,.5,30)
 ss=[]
 for val in vals:
  a=args|{component:val};ss.append(candidate_score(**a,cfg=C))
 if component=='I':assert np.diff(ss).min()>=-1e-12
 else:assert np.diff(ss).max()<=1e-12

def brute_linear(c):
 n,m=c.shape;best=0.
 for size in range(1,min(n,m)+1):
  for ia in itertools.combinations(range(n),size):
   for ib in itertools.combinations(range(m),size):best=max(best,sum(c[i,j] for i,j in zip(ia,ib)))
 return best

@pytest.mark.parametrize('seed',range(8))
def test_cyclic_dp_against_exhaustive(seed):
 rng=np.random.default_rng(seed);c=rng.random((4,5));expected=max(brute_linear(np.roll(c,k,axis=1)) for k in range(5))
 mass,pairs=cyclic_match(c)
 assert mass==pytest.approx(expected,abs=1e-12)
 assert len({a for a,b in pairs})==len(pairs) and len({b for a,b in pairs})==len(pairs)

def test_coordinate_convention_all30():
 g=readj(ROOT/'inputs/geometries30.json')
 for geo in g.values():
  g2=geometry_from_points(geo['points_1024x512'])
  assert np.max(abs(np.array(g2['bottom3d'])-np.array(geo['bottom3d'])))<1e-12
  assert np.max(abs(np.array(g2['top3d'])-np.array(geo['top3d'])))<1e-12

def test_positive_height_missing_rejected():
 g=dict(bottom3d=[[-2,-1,-2],[2,-1,-2],[2,-1,2],[-2,-1,2]],top3d=[[-2,-1,-2],[2,-1,-2],[2,-1,2],[-2,-1,2]])
 with pytest.raises(ValueError):mean_height(g)

def test_config_invalid():
 with pytest.raises(ValueError):Config(position_zero_deg=0)
 with pytest.raises(ValueError):Config(salience_full_h=0)
 with pytest.raises(ValueError):Config(structure_scale=-1)

def test_outside_camera_is_diagnostic_not_silent_repair():
 p=R+[4.1,0]
 assert not Polygon(p).contains(Point(0,0))
 assert np.isfinite(structure(p,R,C)['C'])
 assert np.array_equal(p,R+[4.1,0])
