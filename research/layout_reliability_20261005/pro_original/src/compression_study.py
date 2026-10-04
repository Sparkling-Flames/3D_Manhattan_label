"""Exact-knot shortcut study: archived policy and a bottom-lock constraint.
No evaluation reference is consumed. All ring indices in outputs refer to the
saved exact all-roster consensus. Floating certificates are numerical checks.
"""
from __future__ import annotations
import argparse,copy,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from arc_consensus import Ring,W,H,TAU,equal_coeff,footprint
from simplify import compress,extrema_error
from continuous_metrics import fixed_longitude,depth_height_change,height_envelope,height_envelope_audit,witness_and_provenance
ROOT=Path(__file__).resolve().parents[1]
def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.tolist() if hasattr(a,'tolist') else float(a)),encoding='utf-8')
def circular_costs(exact):
    q=np.array(exact['points']).reshape(-1,2,2);m=len(q);u=q[:,0,0]/W*TAU
    us=np.r_[u,u+TAU,u[0]+2*TAU];r=Ring(exact)
    C=np.array([r.active(((a+b)/2)%TAU).coeff for a,b in zip(us[:m],us[1:m+1])]);C=np.concatenate([C,C])
    cost=np.full((m,m+1),np.inf)
    for i in range(m):
        cost[i,1]=0.
        for s in range(2,m+1):
            j=i+s
            if us[j]-us[i]>=np.pi-1e-10:break
            M=np.array([[np.sin(us[i]),np.cos(us[i])],[np.sin(us[j]),np.cos(us[j])]])
            z=np.tan(np.pi*(.5-q[[i%m,j%m],:,1]/H));new=np.linalg.solve(M,z).T
            cost[i,s]=max(extrema_error(C[k,side],new[side],us[k],us[k+1]) for k in range(i,j) for side in (0,1))
    return cost

def bottom_turns(exact):
    q=np.array(exact['points']).reshape(-1,2,2);u=q[:,0,0]/W*TAU;us=np.r_[u,u[0]+TAU];r=Ring(exact)
    C=[r.active(((a+b)/2)%TAU).coeff for a,b in zip(us[:-1],us[1:])]
    return [i for i in range(len(q)) if not equal_coeff(C[i-1][1],C[i][1])]

def path_costs(circ,start=0,mandatory=()):
    m=len(circ);c=np.full((m+1,m+1),np.inf)
    for i in range(m):
        for j in range(i+1,m+1):
            if not any(i<k<j for k in mandatory):c[i,j]=circ[(start+i)%m,j-i]
    return c

def make_candidate(exact,eps,circ,start=0,locked=False):
    q=np.array(exact['points']).reshape(-1,2,2);m=len(q)
    # The original routine consumes only points/provenance when supplied costs.
    rotated=copy.deepcopy(exact);rotated['points']=np.roll(q,-start,axis=0).reshape(-1,2).tolist()
    mandatory=[(i-start)%m for i in bottom_turns(exact)] if locked else []
    out=compress(rotated,eps,path_costs(circ,start,mandatory))
    out['retained_exact_knot_indices']=[(k+start)%m for k in out['retained_exact_knot_indices']]
    out['removed_exact_knot_indices']=sorted(set(range(m))-set(out['retained_exact_knot_indices']))
    for edge in out['connections']:
        i,j=edge.pop('exact_edge_range');edge['exact_edge_indices']=[(k+start)%m for k in range(i,j)]
        edge['exact_endpoint_indices']=[(i+start)%m,(j+start)%m]
    out.update(anchor_exact_index=start,compression_policy='bottom_locked' if locked else 'pixel_only',
        exact_source_guarantee_inherited=False,required_bottom_knot_indices=bottom_turns(exact) if locked else [],
        approximation='finite shortcut minimum knot count at stated retained anchor; bottom breaks mandatory' if locked else 'archived finite shortcut minimum knot count at stated retained anchor')
    if locked:
        _,a=footprint(exact);_,b=footprint(out)
        out['bottom_lock_numerical_symmetric_difference_h2']=a.symmetric_difference(b).area
        if out['bottom_lock_numerical_symmetric_difference_h2']>1e-8*max(1,a.area):raise AssertionError('bottom_lock_failed')
    return out

def run(image):
    input=json.loads((ROOT/'inputs'/f'{image}.json').read_text());records=input['records']
    fusion=json.loads((ROOT/'results/construction'/f'{image}_exact.json').read_text())
    if fusion['status']!='ok_conditional_representation':return
    exact=fusion['methods'][fusion['bev_mv50_complete_method']];threshold=exact.get('vote_threshold',exact.get('threshold'))
    print('keys',exact.keys(),flush=True)
    # Both boundaries use the ERP integer vote threshold, not BEV threshold.
    threshold=len(records)//2+1
    out=ROOT/'results/compression';out.mkdir(exist_ok=True)
    cache=out/f'{image}_circular_costs.npy'
    t=time.time()
    if cache.exists():circ=np.load(cache)
    else:circ=circular_costs(exact);np.save(cache,circ)
    print(image,'costs',time.time()-t,flush=True)
    env=height_envelope(records);print(image,'envelope pieces',len(env),flush=True)
    _,poly=footprint(exact);base=witness_and_provenance(exact,records,threshold)
    dump(out/f'{image}_exact_witnesses.json',base)
    rows=[];phase=[]
    for eps in [.25,.5,1.,2.]:
        for locked in [False,True]:
            name=('bottom_locked' if locked else 'pixel_only')+f'_{eps:g}px'
            c=make_candidate(exact,eps,circ,0,locked);dump(out/f'{image}_{name}.json',c)
            row=dict(image=image,policy=c['compression_policy'],epsilon_px=eps,pair_count=c['pair_count'],exact_pair_count=len(circ),bottom_turn_count=len(bottom_turns(exact)),certificate_px=c['maximum_vertical_curve_error_px'])
            row.update(fixed_longitude(c,exact));row.update(depth_height_change(c,exact));row.update(height_envelope_audit(c,env))
            witness=witness_and_provenance(c,records,threshold);dump(out/f'{image}_{name}_witnesses.json',witness)
            row.update({k:v for k,v in witness.items() if not isinstance(v,(list,dict))})
            _,p=footprint(c);row.update(bev_symmetric_difference_h2=poly.symmetric_difference(p).area,bev_area_change_h2=p.area-poly.area,bev_iou_to_exact=poly.intersection(p).area/poly.union(p).area)
            rows.append(row)
            print(image,name,'nodes',c['pair_count'],'h',row['height_max_change_h'],'witness loss',row['longitude_share_below_exact_lower_bound'],flush=True)
        for s in range(len(circ)):
            c=make_candidate(exact,eps,circ,s,False);_,p=footprint(c)
            phase.append(dict(image=image,epsilon_px=eps,anchor_exact_index=s,anchor_x=float(np.array(exact['points'])[2*s,0]),pair_count=c['pair_count'],bev_area_h2=p.area,bev_symmetric_difference_h2=poly.symmetric_difference(p).area,retained_indices='|'.join(map(str,c['retained_exact_knot_indices']))))
    pd.DataFrame(rows).to_csv(out/f'{image}_losses.csv',index=False)
    pd.DataFrame(phase).to_csv(out/f'{image}_anchor_sensitivity.csv',index=False)
    print('DONE',image,time.time()-t,flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--image',required=True);a=ap.parse_args();run(a.image)
