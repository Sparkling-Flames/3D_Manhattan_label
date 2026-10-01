from pathlib import Path
from itertools import product,combinations
import json,csv
import numpy as np
import shapely
from shapely.geometry import Polygon,Point,LineString
from geometry_core import *
from matching import *
from real_inputs import get
from snapshot_synthetic import generate
BASE=Path(__file__).resolve().parents[1]
def dump(name,obj):
 (BASE/'results'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))
def table(name,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with (BASE/'results'/name).open('w',newline='') as f:
  d=csv.DictWriter(f,fields);d.writeheader();d.writerows([{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows])
def main():
 real=[dict(image=r[0]['image'],a=r[0],b=r[1]) for r in get()];alignment=[];windows=[];collinear=[]
 for rr in real:
  for s,g in product((1,2,4,8,16),(0.5,2,8)):
   results={side:cyclic_align(rr['a'],rr['b'],s,g,side) for side in ('bound','top','bottom')}
   mt=dict(results['top']['matched']);mb=dict(results['bottom']['matched'])
   conflict=[i for i in mt.keys()&mb.keys() if mt[i]!=mb[i]]
   it={j:i for i,j in mt.items()};ib={j:i for i,j in mb.items()}
   inverse_conflict=[j for j in it.keys()&ib.keys() if it[j]!=ib[j]]
   alignment.append(dict(image=rr['image'],sigma_px=s,gap=g,conflict_count=len(conflict)+len(inverse_conflict),conflict_a_indices=conflict,conflict_b_indices=inverse_conflict,**results))
  for label in ('a','b'):
   a=rr[label];geo=reconstruct(a);p=geo['floor'];t=np.c_[p[:,0],geo['heights']-1,p[:,1]]
   for i,turn in enumerate(turns(p)):
    if abs(turn)>8:continue
    j,k=(i-1)%len(p),(i+1)%len(p)
    def dist(x,a,b):
     e=b-a;v=np.clip(np.dot(x-a,e)/np.dot(e,e),0,1);return float(np.linalg.norm(x-a-v*e))
    floor_deviation=dist(p[i],p[j],p[k]);top_deviation=dist(t[i],t[j],t[k])
    q=np.delete(p,i,axis=0)
    collinear.append(dict(image=rr['image'],record=a['id'],pair_index_zero_based=i,turn_deg=float(turn),
      floor_to_chord_h=floor_deviation,top_to_chord_h=top_deviation,
      declared_bev_iou_after_omission=polygon_metrics(p,q)['bev_iou'],
      interpretation='hypothetical diagnostic only; no input or semantic stop label changed'))
 for rr,lo,hi in [(real[0],970,1035),(real[2],483,515)]:
  wa=angular_window_paths(reconstruct(rr['a'])['floor'],lo,hi);wb=angular_window_paths(reconstruct(rr['b'])['floor'],lo,hi)
  row=dict(image=rr['image'],a_id=rr['a']['id'],b_id=rr['b']['id'],b_ring_confirmed=rr['b']['ring_confirmed'],
   window_px=[lo,hi],span_degrees=(hi-lo)/1024*360,a_paths=wa,b_paths=wb,
   selection='hand-selected geometric diagnostic; not representative or visually validated')
  if len(wa)==len(wb)==1:
   row['shape']=path_metrics(wa[0]['points'],wb[0]['points'],.005)
   row['turns_a']=turns(wa[0]['points'],False).tolist();row['turns_b']=turns(wb[0]['points'],False).tolist()
  windows.append(row)
 dump('cyclic_alignment_sensitivity.json',alignment);dump('real_local_windows.json',windows);table('near_collinear_diagnostics.csv',collinear)
 # Same path, different original sampling: point/gap cost must not be read as spatial error.
 pa=np.array([[-.1,2],[.1,2]]);pb=np.array([[-.1,2],[0,2],[.1,2]])
 local=[dict(name='two_nodes_three_collinear_nodes',a=pa.tolist(),b=pb.tolist(),metrics=path_metrics(pa,pb,.001))]
 # Exact orthogonal paths with same anchors/tangents: 2 vs 4 genuine turns, not 2 vs 3.
 pa=np.array([[-1,2],[-.2,2],[-.2,2.2],[1,2.2]])
 pb=np.array([[-1,2],[-.4,2],[-.4,2.1],[.3,2.1],[.3,2.2],[1,2.2]])
 local.append(dict(name='two_turns_four_turns_manhattan',a=pa.tolist(),b=pb.tolist(),turns_a=turns(pa,False).tolist(),turns_b=turns(pb,False).tolist(),metrics=path_metrics(pa,pb,.002)))
 # Dense spike: retain true vertex rather than depend on phase of whole-perimeter samples.
 spike=next(c for c in generate() if c['case']=='near_three_pairs' and c['amplitude']==.002)
 pa,pb=[reconstruct(spike[k])['floor'] for k in ('a','b')]
 closed_a,closed_b=np.r_[pa,pa[:1]],np.r_[pb,pb[:1]]
 local.append(dict(name='snapshot_spike_vertex_preserving',metrics=path_metrics(closed_a,closed_b,.01),
   baseline_512=polygon_metrics(pa,pb,512),baseline_8192=polygon_metrics(pa,pb,8192)))
 parity=[]
 for n in range(7):
  possible=sorted({sum(v)%4 for v in product((-1,1),repeat=n)})
  parity.append(dict(nonzero_quarter_turns=n,possible_exit_directions_mod4=possible))
 dump('local_path_cases.json',local);dump('quarter_turn_parity.json',parity)
 # Deletion candidates, no coordinate fit, no donor support in objective.
 bump=np.array([[-2,-2],[2,-2],[2,2],[.2,2],[.2,2.4],[-.2,2.4],[-.2,2],[-2,2]])
 src=Polygon(bump);dense=sample_path(np.r_[bump,bump[:1]],.01);cand=[];raw_subsets=0;valid_simple_positive=0
 for k in range(3,len(bump)+1):
  for ids in combinations(range(len(bump)),k):
   q=bump[list(ids)];poly=Polygon(q);raw_subsets+=1
   valid_simple_positive+=int(poly.is_valid and poly.area>=1e-8)
   if not poly.is_valid or not poly.contains(Point(0,0)) or poly.area<1e-8:continue
   a=float(shapely.distance(shapely.points(dense),poly.boundary).max())
   sq=sample_path(np.r_[q,q[:1]],.01)
   b=float(shapely.distance(shapely.points(sq),src.boundary).max())
   # Original vertices explicitly included. Fidelity is geometry, not number of votes/nodes.
   cand.append(dict(ids=list(ids),vertices=k,axis_residual=axis_residual(q)['weighted'],
     fidelity_lower=max(a,b),fidelity_upper=(0. if poly.equals(src) else max(a,b)+.005),bev_iou=polygon_metrics(bump,q)['bev_iou'],
     unsupported_new_boundary_length=float(poly.boundary.difference(src.boundary.buffer(1e-8)).length),area=float(poly.area)))
 orth=[v for v in cand if v['axis_residual']<1e-8]
 simple=min(orth,key=lambda r:(r['vertices'],r['fidelity_lower']))
 budget=[]
 for eps in (.005,.01,.05,.1,.2,.4,.5):
  feasible=[v for v in orth if v['fidelity_upper']<=eps+1e-10]
  best=min(feasible,key=lambda r:(r['vertices'],r['fidelity_lower']))
  budget.append(dict(fidelity_budget=eps,selected=best))
 unique_orth=[]
 for v in orth:
  poly=Polygon(bump[v['ids']])
  if not any(poly.equals(o) for o in unique_orth):unique_orth.append(poly)
 out=dict(source=bump.tolist(),raw_subsets=raw_subsets,valid_simple_positive=valid_simple_positive,enumerated_valid=len(cand),orthogonal_candidates=len(orth),orthogonal_geometries=len(unique_orth),
    residual_then_complexity=simple,budget_sweep=budget,all_candidates=cand,
    addition_deletion_same_exhaustive_set=True)
 dump('subtraction_exhaustive.json',out)
 # Local-majority versus empirical whole-layout support, exact bit enumeration.
 observed=np.array([[1,1,0],[1,0,1],[0,1,1]],int);mv=(observed.mean(0)>=.5).astype(int)
 full=[]
 for bits in product((0,1),repeat=3):
  full.append(dict(pattern=list(bits),whole_count=int(np.all(observed==bits,axis=1).sum()),local_counts=(observed==bits).sum(axis=0).tolist()))
 dump('consensus_joint_counterexample.json',dict(observed=observed.tolist(),mv=mv.tolist(),mv_whole_count=int(np.all(observed==mv,axis=1).sum()),patterns=full,
   all_common_omission='when every observed bit is zero, unweighted MV remains zero for every k'))
 # A selected-one-worker-per-image panel cannot identify worker fixed effects.
 workers=np.array([0,1,2,0,1,3,0,2,4,4,1,0]);I=np.eye(12);W=np.eye(5)[workers];X=np.c_[I,W]
 delta=np.array([.2,-.1,.4,.05,-.3]);null=np.r_[-delta[workers],delta]
 dump('identifiability_counterexample.json',dict(images=12,illustrative_workers=5,design_columns=17,rank=int(np.linalg.matrix_rank(X)),
    effect_reallocation_prediction_max=float(abs(X@null).max()),
    scope='worker identities illustrative, NOT the actual full historical incidence graph; proof applies to every one-worker-per-image selection'))
 print(json.dumps({'real_windows':[(r['image'],len(r['a_paths']),len(r['b_paths']),[len(p['interior_vertex_indices']) for p in r['a_paths']],[len(p['interior_vertex_indices']) for p in r['b_paths']]) for r in windows],
     'collinear':collinear,'alignments':len(alignment),'split_conflicts':sum(r['conflict_count']>0 for r in alignment),
     'deletion_valid':len(cand),'orthogonal':len(orth),'simplest':simple,'local_cases':local,'parity':parity},indent=2))
if __name__=='__main__':main()
