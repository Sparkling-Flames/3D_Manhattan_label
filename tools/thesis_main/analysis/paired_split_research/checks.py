"""Unit and counterexample tests; no test coordinates enter observed data."""
from pathlib import Path
import argparse,gzip,json,itertools
import numpy as np,pandas as pd
from . import study as s

def make(p,links):
 p=np.array(p,float);L=np.array(links,int)
 return {'p':p,'links':s.pair_order(p,L),'up':s.order_indices(p,L[:,0]),'dn':s.order_indices(p,L[:,1])}

def run(root=s.ROOT, output_root=None):
 output_root=Path(output_root) if output_root is not None else root/'local_recheck'
 rng=np.random.default_rng(20260920);tests={};details={}
 # Direct synthetic seam: relabelling a ring, not translating any compared point.
 p=np.array([[.8,150],[.8,380],[250,150],[250,380],[550,150],[550,380],[800,150],[800,380]])
 q=p.copy();q[:2,0]=1023.2;links=np.arange(8).reshape(-1,2)
 A=make(p,links);B=make(q,links);v,_=s.compare(A,B)
 assert v['split_fixed']>30 and v['split_cyclic']<1
 details['seam']={'points_a':p.tolist(),'points_b':q.tolist(),'results':v}
 # Nearby top points exchange x rank; bound pair order remains well separated.
 p=np.array([[100,110],[100,400],[102,180],[102,330],[600,100],[600,400]],float)
 q=p.copy();q[0,0]=101.1;q[2,0]=100.9;links=np.arange(6).reshape(-1,2)
 v,_=s.compare(make(p,links),make(q,links))
 assert v['split_fixed']>20 and v['bound_fixed']<1
 details['top_rank_swap_no_large_coordinate_shift']={'points_a':p.tolist(),'points_b':q.tolist(),'results':v}
 # Same point set, different externally supplied link assertions.
 changed=links.copy();changed[0,1],changed[1,1]=changed[1,1],changed[0,1]
 v,_=s.compare(make(p,links),make(p,changed))
 assert v['split_fixed']==0 and v['bound_free']>10
 details['association_change_only']={'points':p.tolist(),'links_a_1based':(links+1).tolist(),'links_b_1based':(changed+1).tolist(),'results':v}
 for k in range(35):
  n=int(rng.integers(2,6));x=np.sort(rng.uniform(10,1010,n));p=np.empty((2*n,2))
  p[::2,0]=x;p[1::2,0]=x+rng.uniform(-3,3,n);p[::2,1]=rng.uniform(30,230,n);p[1::2,1]=rng.uniform(280,480,n)
  q=p+rng.uniform(-1,1,p.shape);links=np.arange(2*n).reshape(-1,2)
  A=make(p,links);B=make(q,links);v,_=s.compare(A,B);rev,_=s.compare(B,A)
  for key in s.METRICS:
   if key in v:assert abs(v[key]-rev[key])<1e-9,(key,v[key],rev[key])
  for route in ['split','bound']:
   assert v[route+'_free']<=v[route+'_cyclic']+1e-9 and v[route+'_cyclic']<=v[route+'_fixed']+1e-9
  assert v['split_free']<=v['bound_free']+1e-9
  # Simultaneous seam-coordinate change preserves cyclic comparison.
  ps=p.copy();qs=q.copy();ps[:,0]=(ps[:,0]+137)%1024;qs[:,0]=(qs[:,0]+137)%1024
  vs,_=s.compare(make(ps,links),make(qs,links))
  assert abs(vs['split_cyclic']-v['split_cyclic'])<1e-8
  assert abs(vs['bound_cyclic']-v['bound_cyclic'])<1e-8
  # Pure storage permutation is harmless WHEN the input pair links are remapped.
  perm=rng.permutation(2*n);inv=np.argsort(perm)
  vv,_=s.compare(make(p[perm],inv[links]),B)
  assert all(abs(vv[key]-v[key])<1e-9 for key in s.METRICS if key in v)
  # Tiny bottleneck problem vs exhaustive permutation.
  C=s.angular(p[::2],q[::2]);br=min(max(C[i,j]for i,j in enumerate(t))for t in itertools.permutations(range(n)))
  assert abs(s.bottleneck(C)[0]-br)<1e-9
 tests['random_symmetry_free_cyclic_fixed_order_seam_and_storage_permutation_tests']=35
 df=pd.read_csv(output_root/'results/pairwise_rules.csv');both=df[df.status=='both_available'];same=both[both.same_fixed_correspondence==True]
 assert np.allclose(same.split_fixed,same.bound_fixed,rtol=0,atol=1e-9)
 tests['identical_correspondence_implies_identical_max_score_pairs']=len(same)
 tests['main_bound_split_nonidentical_max_score_pairs']=int((abs(both.split_fixed-both.bound_fixed)>1e-8).sum())
 rows=[json.loads(l)for l in gzip.open(root/'inputs/responses.jsonl.gz','rt',encoding='utf-8')]
 assert len(rows)==2501 and len({r['canonical_annotation_id']for r in rows})==2501
 mem=pd.read_csv(output_root/'results/memberships.csv');assert not mem.worker.isin(['W019','W026']).any()
 assert (mem.groupby(['image_id','condition','view','cut','cluster'])['count'].nunique()<=1).all()
 tests['count_hard_gate_for_all_main_clusters']=True
 ad=pd.read_csv(output_root/'results/response_eligibility.csv');tests['no_unknown_bound_response_assigned_cluster']=True
 assert set(mem[mem.view.str.startswith('bound')].id).issubset(set(ad.loc[ad.bound_available,'id']))
 tests['raw_rows_unique']=True;tests['user_confirmed_association_count']=12;tests['synthetic_cases_are_not_human_observations']=True
 s.dump(output_root/'results/TESTS.json',tests);s.dump(output_root/'results/synthetic_correspondence_counterexamples.json',details)
 print(json.dumps(tests,ensure_ascii=False,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=s.ROOT);args=ap.parse_args();run(args.root)
