"""Audit implementation invariance, cyclic-map consistency, and analytical replay formulas."""
from pathlib import Path
import itertools,json,sys,tempfile,gzip,copy
import numpy as np,pandas as pd
from release import prepare,cluster,frame,writejson,CONFIG
from history_analysis import next_uncovered,fixed_mode_stats

def run(root,out):
 st,rows,rec,elig,_=prepare(root);cache=json.loads((out/'cache.json').read_text());pairs=pd.read_csv(out/'pairwise.csv');mem=pd.read_csv(out/'memberships.csv');tests={}
 # Endpoint distance independent dot-product cross-check using only nonzero distances.
 p=pd.read_csv(out/'endpoint_correspondences.csv.gz');latA=(p.y_a+.5)/512*np.pi-np.pi/2;latB=(p.y_b+.5)/512*np.pi-np.pi/2;du=(p.x_a-p.x_b)/1024*2*np.pi
 dot=np.sin(latA)*np.sin(latB)+np.cos(latA)*np.cos(latB)*np.cos(du);deg=np.degrees(np.arccos(np.clip(dot,-1,1)));mask=p.error_deg>1e-4
 err=float(np.max(abs(deg[mask]-p.error_deg[mask])));assert err<1e-6;tests['endpoint_independent_formula_rows']=len(p);tests['endpoint_max_error_nonzero_deg']=err
 # Pure simultaneous coordinate yaw must not change cyclic distances (fixed order may change).
 rng=np.random.default_rng(20260920);checked=0
 for q in pairs[pairs.split_cyclic.notna()].sample(40,random_state=20260920).to_dict('records'):
  a,b=rec[q['id_a']],rec[q['id_b']]
  def change(z):
   zz=copy.deepcopy(z);perm=rng.permutation(len(z['p']));inv=np.argsort(perm);zz['p']=z['p'][perm].copy();zz['p'][:,0]=(zz['p'][:,0]+137)%1024
   zz['up']=st.order_indices(zz['p'],inv[z['up']]);zz['dn']=st.order_indices(zz['p'],inv[z['dn']]);zz['links']=None
   return zz
  score,_=st.compare(change(a),change(b));assert abs(score['split_cyclic']-q['split_cyclic'])<1e-7;checked+=1
 tests['simultaneous_yaw_and_storage_permutation_cases']=checked
 # Finite-pool probability and fixed-partition summaries agree with enumeration.
 for N in range(3,8):
  X=rng.uniform(0,20,(N,N));D=(X+X.T)/2;np.fill_diagonal(D,0);lab=cluster(D,9)
  for k in range(1,N):
   calc=0.;Ks=[];ones=[]
   for ix in itertools.combinations(range(N),k):
    remaining=set(range(N))-set(ix);calc+=np.mean([min(D[j,list(ix)])>9 for j in remaining])
    ls=lab[list(ix)];co=np.unique(ls,return_counts=True)[1];Ks.append(len(co));ones.append(sum(co==1)/k)
   exact=calc/len(Ks);assert abs(exact-next_uncovered(D,k))<1e-12
   t=fixed_mode_stats(lab,k);assert abs(np.mean(Ks)-t['retrospective_expected_modes'])<1e-12;assert abs(np.mean(ones)-t['retrospective_singleton_response_fraction'])<1e-12
 tests['finite_pool_enumeration_N3_to7']='passed'
 primary=mem[(mem.metric=='split_cyclic')&(mem.cut==9)];lookup={}
 for r in pairs.to_dict('records'):
  lookup[r['id_a'],r['id_b']]=r
 def shift(a,b,role):
  if a==b:return 0
  if (a,b) in lookup:return int(lookup[a,b][role+'_shift'])
  return -int(lookup[b,a][role+'_shift'])
 conflicts=[]
 for (iid,cond,cl),g in primary.groupby(['image_id','condition','cluster']):
  if len(g)<3:continue
  rootid=g.representative_id.iloc[0];ids=g.id.tolist()
  for a,b in itertools.combinations(ids,2):
   if rootid in [a,b]:continue
   for role,ix in [('top','up'),('bottom','dn')]:
    n=len(rec[a][ix]);res=(shift(rootid,a,role)+shift(a,b,role)-shift(rootid,b,role))%n
    if res:conflicts.append(dict(image_id=iid,condition=cond,cluster=cl,root_id=rootid,id_a=a,id_b=b,role=role,modulo_residual=res,n=n,meaning='selected_pairwise_mappings_not_global_physical_correspondence'))
 frame(out,'within_cluster_mapping_cycle_conflicts.csv',conflicts);tests['within_cluster_selected_mapping_cycle_conflicts']=len(conflicts)
 # Canonical frame-count guarantee and no pre-processing changes.
 assert not set(primary.worker)&{'W019','W026'};assert len(primary)==2379
 assert primary.groupby(['image_id','condition','cluster'])['count'].nunique().max()==1
 assert not pd.read_csv(out/'group_summary.csv').within_incompatible.any()
 tests['equal_count_groups_and_no_outside_diameter_pairs']=True
 tests['exact_source_unit_counts']={'records':len(rows),'units':len(cache)}
 writejson(out/'TESTS.json',tests)
if __name__=='__main__':
 r=Path(__file__).resolve().parents[1];run(r,r/'results/release')
