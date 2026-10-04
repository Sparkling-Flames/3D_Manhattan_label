"""Independent bounded verification. Writes only beside this script."""
import sys
sys.dont_write_bytecode = True
import itertools, json, hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PKG=ROOT/'source/layout_foundations_20261004_v2'
sys.path.insert(0,str(PKG/'src'))
from quality import directed
from arc_consensus import Ring
from cases import rectangle

# Exhaust all positive paired vectors on a fixed finite grid, including ties.
checked=0
min_achieved={}
for n in range(1,5):
    tuples=np.array(list(itertools.product([1.,2.,3.],repeat=2*n)))
    U,D=tuples[:,:n],tuples[:,n:]
    R=U/D
    Us,Ds=np.sort(U,axis=1)[:,::-1],np.sort(D,axis=1)[:,::-1]
    for t in range(1,n+1):
        H=Us[:,t-1]/Ds[:,t-1]
        assert np.all(H>=R.min(axis=1)-1e-14)
        assert np.all(H<=R.max(axis=1)+1e-14)
        count=((U>=Us[:,t-1,None])&(D>=Ds[:,t-1,None])).sum(axis=1)
        assert count.min()>=max(0,2*t-n)
        min_achieved[f'{n},{t}']=int(count.min())
        checked+=len(U)

qp=HERE/'quality_control_inputs.json'
prehash=hashlib.sha256(qp.read_bytes()).hexdigest()
old=json.loads(qp.read_text())
ref=rectangle()
rows=[]
base=old['added_oscillation_control'][0]['prediction']
x=(np.arange(65536)+.5)*1024/65536
r=Ring(ref).evaluate(x*2*np.pi/1024)[0]
b=Ring(base).evaluate(x*2*np.pi/1024)[0]
for c in old['added_oscillation_control']:
    if c['additional_oscillation_nodes'] not in (0,1000):continue
    pred=c['prediction']
    ab,ba=directed(pred,ref,0,.025),directed(ref,pred,0,.025)
    p=Ring(pred).evaluate(x*2*np.pi/1024)[0]
    fixed=(x>=128)&(x<=512)
    outside_wiggle=(x<600)|(x>1000)
    pp=np.asarray(pred['points']).reshape(-1,2,2)[:,0]
    theta=pp[:,0]*2*np.pi/1024;phi=np.pi/2-pp[:,1]*np.pi/512
    rays=np.stack([-np.cos(phi)*np.sin(theta),np.sin(phi),np.cos(phi)*np.cos(theta)],axis=-1)
    nxt=np.roll(rays,-1,axis=0)
    length=np.degrees(np.arctan2(np.linalg.norm(np.cross(rays,nxt),axis=-1),(rays*nxt).sum(axis=-1))).sum()
    rows.append(dict(n=c['additional_oscillation_nodes'],candidate_length_deg=float(length),
        candidate_mean_deg=ab['mean_deg'],reference_mean_deg=ba['mean_deg'],
        equal_direction_mean_deg=(ab['mean_deg']+ba['mean_deg'])/2,
        equal_direction_quadrature_bound_deg=(ab['mean_absolute_numerical_bound_deg']+ba['mean_absolute_numerical_bound_deg'])/2,
        candidate_integral_deg_squared=float(length*ab['mean_deg']),
        fixed_error_region_change_px=float(abs(p[fixed]-b[fixed]).max()),
        outside_wiggle_region_change_px=float(abs(p[outside_wiggle]-b[outside_wiggle]).max()),
        uniform_longitude_mean_abs_error_px=float(abs(p-r).mean()),
        max_uniform_longitude_abs_error_px=float(abs(p-r).max()),
        error_reduction_at_any_longitude_px=float(np.maximum(abs(b-r)-abs(p-r),0).max())))
assert rows[1]['equal_direction_mean_deg']+rows[1]['equal_direction_quadrature_bound_deg']<rows[0]['equal_direction_mean_deg']-rows[0]['equal_direction_quadrature_bound_deg']
assert rows[1]['candidate_integral_deg_squared']>rows[0]['candidate_integral_deg_squared']
assert rows[1]['fixed_error_region_change_px']==0
assert rows[1]['outside_wiggle_region_change_px']==0
assert rows[1]['error_reduction_at_any_longitude_px']<1e-9
assert hashlib.sha256(qp.read_bytes()).hexdigest()==prehash
result=dict(finite_grid_rank_and_support_checks=checked,min_support_achieved=min_achieved,
    fine_quality_control=rows,input_quality_result_unchanged=True,
    method_note='Independent order-statistic enumeration; package metric rerun at 0.025-degree step versus original 0.05. Source geometry and local error rechecked on 65,536 longitude midpoints. Mathematical proof is separate.')
(HERE/'crosscheck_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
