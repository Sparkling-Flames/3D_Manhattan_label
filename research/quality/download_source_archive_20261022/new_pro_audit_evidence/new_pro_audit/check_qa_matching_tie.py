"""Fixed small GQS-v2 counterexample plus independent exhaustive correspondence check.
No algorithm changes. All z/x inputs and the row-vector common yaw matrix are explicit.
"""
from pathlib import Path
import argparse, json, sys, itertools, hashlib
import numpy as np
from shapely.geometry import Polygon, Point
ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'new_pro_return/panorama_quality_three_routes_20261016'
sys.path.insert(0,str(STUDY/'src'))
from geomscore import Config, score_pair, canonical, simplify

def geom(p,height=2.):
    p=np.asarray(p,float)
    return {'bottom3d':np.c_[p[:,0],-np.ones(len(p)),p[:,1]].tolist(),
            'top3d':np.c_[p[:,0],np.full(len(p),height-1),p[:,1]].tolist()}

def signed_turns(p):
    e=np.roll(p,-1,axis=0)-p;prev=np.roll(e,1,axis=0)
    return np.degrees(np.arctan2(prev[:,0]*e[:,1]-prev[:,1]*e[:,0],np.sum(prev*e,axis=1)))

def physical_pairs(p,r,level):
    a=simplify(p,level['eps_h'])[0];b=simplify(r,level['eps_h'])[0]
    ai=[int(np.argmin(np.linalg.norm(p-x,axis=1))) for x in a]
    ri=[int(np.argmin(np.linalg.norm(r-x,axis=1))) for x in b]
    return [[ai[i],ri[j]] for i,j in level['pairs']]

A=np.array([(3,0),(0,3),(-2,2),(-4,0),(-4,-2),(-1,-3)],float)
R=np.array([(-2,-4),(4,-2),(2,3),(-3,2),(-3,-1)],float)
ROT=np.array([[0.,-1.],[1.,0.]])
assert Polygon(A).is_valid and Polygon(R).is_valid
assert Polygon(A).contains(Point(0,0)) and Polygon(R).contains(Point(0,0))
# Convex pairs: all five reference corners can be matched. There are 6 choices
# of omitted A corner and five cyclic reference offsets, so 30 physical maps.
aa=signed_turns(A);ar=signed_turns(R);assert min(aa)>0 and min(ar)>0
alternatives=[]
for omit in range(6):
    ids=[i for i in range(6) if i!=omit]
    for shift in range(5):
        pairs=[(i,(j+shift)%5) for j,i in enumerate(ids)]
        cost=sum(float(np.linalg.norm(A[i]-R[j])) for i,j in pairs)
        angles=[abs(float(aa[i]-ar[j])) for i,j in pairs]
        penalty=float(np.mean([min((max(x-3,0)/20)**2,4) for x in angles]))
        alternatives.append(dict(omitted_A=omit,reference_offset=shift,pairs=pairs,position_cost=cost,angle_penalty=penalty))
alternatives.sort(key=lambda z:z['position_cost'])
minimum=alternatives[0]['position_cost']
minimizers=[z for z in alternatives if abs(z['position_cost']-minimum)<1e-13]
assert len(alternatives)==30 and len(minimizers)==2
assert np.linalg.norm(A[3]-R[4])==np.linalg.norm(A[4]-R[4])==np.sqrt(2.)
states=[]
for name,rot in [('original',np.eye(2)),('common_exact_90',ROT),('common_exact_180',ROT@ROT),('common_exact_270',ROT@ROT@ROT)]:
    p=A@rot;r=R@rot;s=score_pair(geom(p),geom(r),Config())
    pp=[physical_pairs(p,r,z) for z in s['angle_detail']['event_scales']]
    for lev in s['angle_detail']['event_scales']:
        assert (lev['nA'],lev['nR'],lev['matched'],lev['simplification_fallback'])==(6,5,5,False)
    states.append(dict(name=name,row_rotation=rot.tolist(),physical_pairs_by_scale=pp,score=s))
assert abs(states[0]['score']['I']-states[1]['score']['I'])<1e-14
assert states[0]['score']['surface_height']['local_penalty']==states[1]['score']['surface_height']['local_penalty']==0
assert states[0]['score']['surface_height']['mean_penalty']==states[1]['score']['surface_height']['mean_penalty']==0
assert abs(states[0]['score']['QA']-states[1]['score']['QA'])>4.5
result=dict(answer_xz=A.tolist(),reference_xz=R.tolist(),wall_height=2.,floor_y=-1.,
            discovered_with_seed=2026101602,discovery_trial=26,valid_pair_count_at_discovery=22,
            independent_max_cardinality=5,independent_all_maximum_cardinality_maps=alternatives,
            independent_minimum_position_cost=minimum,independent_position_minimizers=minimizers,states=states,
            exact_tie='R[4]=(-3,-1) is sqrt(2) from A[3]=(-4,0) and A[4]=(-4,-2); all other selected distances agree.',
            diagnosis='ordered_matching pair-index lex tie depends on canonical world-coordinate start. Same optimal physical correspondence set, different chosen angle penalty.',
            code_sha256=hashlib.sha256((STUDY/'src/geomscore.py').read_bytes()).hexdigest(),
            config_sha256=hashlib.sha256((STUDY/'config.json').read_bytes()).hexdigest())
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'new_pro_audit/qa_matching_tie_regression.json');args=ap.parse_args()
if args.out.exists():raise FileExistsError(args.out)
args.out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['independent_max_cardinality','independent_minimum_position_cost','independent_position_minimizers']},indent=2))
print(json.dumps([dict(state=s['name'],I=s['score']['I'],QA=s['score']['QA'],QB=s['score']['QB'],QC=s['score']['QC'],E_angle=s['score']['angle_detail']['angle_penalty'],pairs=s['physical_pairs_by_scale'][0]) for s in states],indent=2))
