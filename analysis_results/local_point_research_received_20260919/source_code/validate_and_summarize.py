"""Executable invariance tests, counterfactual stress tests and prespecified strata.
Synthetic changes are tests only: they are NEVER added to the corpus or counted as people.
"""
import json,itertools,math,hashlib,collections,platform
import numpy as np,pandas as pd,scipy
import local_points as lp
from precision_audit import stable_angles
R=lp.ROOT

def sf(a,b):return lp.features(stable_angles(a,b))

def run():
 rows,audit=lp.load();valid=[r for r in rows if lp.point_ok(r)];rng=np.random.default_rng(20260919)
 tests={};errors=[];synthetic=[]
 for r in valid:
  p=np.array(r['effective_points_1024x512']);n=len(p);selfc=stable_angles(p,p)
  assert (np.diag(selfc)==0).all();errors.append(np.diag(selfc).max())
  # Delete the best isolated point and duplicate a different existing point: count is unchanged.
  C=selfc.copy();np.fill_diagonal(C,np.inf);iso=C.min(1);j=int(iso.argmax());other=(j+1)%n
  if n>1:
   q=p.copy();q[j]=p[other];f=sf(p,q)
   assert f['ospa1']<=30/n+1e-8
   assert f['hausdorff']>=iso[j]-1e-7
   synthetic.append(dict(id=r['canonical_annotation_id'],code=audit.loc[r['canonical_annotation_id'],'code'],condition=r['raw_condition'],n=n,operation='replace_isolated_point_with_duplicate',removed_index=j,duplicated_index=other,known_isolation_deg=iso[j],ospa1=f['ospa1'],local_max=f['hausdorff'],pointcount_unchanged=True))
  # Exact duplicate changes record multiplicity, but the geometric set stays identical.
  dup=np.concatenate([p,p[:min(2,n)]],axis=0);f=sf(p,dup)
  assert f['hausdorff']<1e-10
  assert abs(f['ospa1']-30*min(2,n)/(n+min(2,n)))<1e-7
  synthetic.append(dict(id=r['canonical_annotation_id'],code=audit.loc[r['canonical_annotation_id'],'code'],condition=r['raw_condition'],n=n,operation='append_two_exact_duplicates',ospa1=f['ospa1'],local_max=f['hausdorff'],pointcount_unchanged=False))
 # Permutation and seam invariance, symmetric distances.
 for r,s in zip(valid[:100],valid[100:200]):
  p=np.array(r['effective_points_1024x512']);q=np.array(s['effective_points_1024x512']);f=sf(p,q)
  fp=sf(p[rng.permutation(len(p))],q[rng.permutation(len(q))]);rev=sf(q,p)
  pp=p.copy();qq=q.copy();pp[:,0]=(pp[:,0]+137)%1024;qq[:,0]=(qq[:,0]+137)%1024;rot=sf(pp,qq)
  for key in ['ospa1','ospa2','hausdorff']:
   assert abs(f[key]-fp[key])<1e-6 and abs(f[key]-rev[key])<1e-6 and abs(f[key]-rot[key])<1e-6
 tests['permutation_symmetry_common_yaw_instances']=100
 # Exact maximum cardinality radius matching and bottleneck against all small permutations.
 for n in range(1,6):
  for k in range(8):
   C=rng.uniform(0,20,(n,n));f=lp.features(C)
   best=min(max(C[i,perm[i]]for i in range(n))for perm in itertools.permutations(range(n)))
   assert abs(f['bottleneck']-best)<1e-10
   for rad in [3.,6.,9.,12.]:
    exact=max(sum(C[i,perm[i]]<=rad for i in range(n))for perm in itertools.permutations(range(n)))
    assert f['matched_'+str(int(rad))]==exact
 tests['matching_vs_permutations_instances']=40
 # Finite-pool joint novelty formula against enumerated subsets, on a real 5-person image.
 cache=json.loads((R/'results/cache.json').read_text());g=next(g for g in cache.values()if len(g['ids'])==5)
 O=np.array(g['Ds']['ospa1']);H=np.array(g['Ds']['hausdorff']);N=5;k=2;vals=[]
 for target in range(N):
  rem=[i for i in range(N)if i!=target]
  for subset in itertools.combinations(rem,k):vals.append(bool(np.min(O[target,list(subset)])<=6 and np.min(H[target,list(subset)])>9))
 AO=O<=6;AH=H<=9;np.fill_diagonal(AO,False);np.fill_diagonal(AH,False)
 def none(x):return np.mean([math.comb(N-1-int(v),k)/math.comb(N-1,k)if N-1-int(v)>=k else 0 for v in x.sum(1)])
 assert abs(np.mean(vals)-(none(AH)-none(AH|AO)))<1e-12
 tests['joint_finite_pool_formula_enumerated']=True
 # Archived OSPA partitions (same input order/algorithm): identity means exact pair relations.
 old=pd.read_csv(R/'inputs/old_ospa_memberships.csv');parities=[]
 for key,g in cache.items():
  iid,cond=key.split('|');D=np.array(g['Ds']['ospa1']);cnt=np.array(g['counts']);ids=g['ids']
  for cut in [3,6,9]:
   prev=old[(old.image_id==iid)&(old.condition==cond)&(old.method==f'OSPA30_c{cut}_gate0')].set_index('id').loc[ids].cluster.to_numpy()
   now=np.array(g['labels'][f'OSPA1_{cut}'])
   parities.append(np.array_equal(prev[:,None]==prev[None,:],now[:,None]==now[None,:]))
 assert all(parities)
 tests['archived_ospa_nongated_partitions_identical']=len(parities)
 tests['stable_self_distance_records']=len(valid)
 tests['versions']={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pandas':pd.__version__}
 pd.DataFrame(synthetic).to_csv(R/'results/synthetic_stress.csv',index=False)
 p=pd.read_csv(R/'results/pairwise.csv');strata=[]
 for rad in [6,9,12]:
  for condition in ['all','manual','semi','oos']:
   d=p if condition=='all'else p[p.condition==condition]
   selections={'samecount_ospa6close_localfar':d.same_count&(d.ospa1<=6)&(d.hausdorff>rad),'differentcount_ospa6far_localclose':~d.same_count&(d.ospa1>6)&(d.hausdorff<=rad),'samecount_localclose_matching_not_complete':d.same_count&(d.hausdorff<=rad)&(d['matched_'+str(rad)]<d.n_a)}
   for name,mask in selections.items():
    z=d[mask];strata.append(dict(radius=rad,condition=condition,stratum=name,pairs=len(z),images=z.image_id.nunique(),units=len(z[['image_id','condition']].drop_duplicates())))
 pd.DataFrame(strata).to_csv(R/'results/local_strata.csv',index=False)
 syn=pd.DataFrame(synthetic);v=syn[syn.operation=='replace_isolated_point_with_duplicate']
 tests['synthetic_samecount_local_loss_over9_but_ospa_atmost6']=int(((v.local_max>9)&(v.ospa1<=6)).sum())
 tests['synthetic_exact_duplicate_local_distance_zero']=int((syn.operation=='append_two_exact_duplicates').sum())
 (R/'results/TESTS.json').write_text(json.dumps(tests,ensure_ascii=False,indent=2))
 print(json.dumps(tests,indent=2));print(pd.DataFrame(strata).query('condition=="all"').to_string(index=False))
if __name__=='__main__':run()
