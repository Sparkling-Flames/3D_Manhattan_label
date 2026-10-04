#!/usr/bin/env python3
"""Independent cloud audit of the frozen personnel bundle.
No original files are modified. Reads bundle + archived full B input. Writes only --out.
Usage: PYTHONPATH=<compatible_dependencies> python audit_personnel.py --bundle PATH --archive PATH --replay PATH --out NEW_DIR
"""
from pathlib import Path
import argparse, json, hashlib, itertools, math, sys, csv, subprocess, tempfile, os
from collections import defaultdict, Counter
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from shapely.ops import unary_union, polygonize
from scipy.cluster.hierarchy import linkage, cut_tree

p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--replay',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
result={}; failures=[]
def put(name,value):
 result[name]=value
 (a.out/'audit_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')
 print(name, json.dumps(value,ensure_ascii=False,default=str)[:1000],flush=True)
def fail(section,message): failures.append(dict(section=section,message=message))
def close(x,y,tol=2e-12):return bool(np.allclose(x,y,atol=tol,rtol=tol,equal_nan=True))

# 1. Integrity. No claim that a supplied source commit can be authenticated offline.
man=json.loads((a.bundle/'MANIFEST.sha256.json').read_text());bad=[]
for name,m in man.items():
 raw=(a.bundle/name).read_bytes()
 if len(raw)!=m['bytes'] or hashlib.sha256(raw).hexdigest()!=m['sha256']:bad.append(name)
put('manifest',dict(entries=len(man),mismatches=bad,source_commit_authentication='not performed; packaged declarations and archived source only'))

# 2. Artifact replays: CSV + JSON bytes and NPZ every member, not zip timestamps.
rows=[]
for src in sorted((a.bundle/'results').iterdir()):
 dst=a.replay/'results'/src.name
 if not dst.exists():rows.append(dict(file=src.name,status='missing'));continue
 if src.suffix=='.npz':
  s=np.load(src);d=np.load(dst);ok=set(s.files)==set(d.files) and all(np.array_equal(s[k],d[k],equal_nan=True) if s[k].dtype.kind not in 'USO' else np.array_equal(s[k],d[k]) for k in s.files)
  rows.append(dict(file=src.name,status='exact_arrays' if ok else 'arrays_differ'))
 else:rows.append(dict(file=src.name,status='exact_bytes' if src.read_bytes()==dst.read_bytes() else 'bytes_differ'))
pd.DataFrame(rows).to_csv(a.out/'replay_comparison.csv',index=False)
put('replay_comparison',dict(files=len(rows),counts=dict(Counter(r['status'] for r in rows))))

old=json.loads((a.archive/'analysis_results/worker_profiles_20261003/input.json').read_text(encoding='utf-8-sig'))
old_by={x['code']:x for x in old['images']}; field_rows=[];rosters=[]; omissions=[]
def check_tree(x,y,path):
 if isinstance(x,dict):
  for k,v in x.items():
   if k not in y:field_rows.append(dict(path=path+'.'+k,status='absent_in_archive'))
   else:check_tree(v,y[k],path+'.'+k)
 else:field_rows.append(dict(path=path,status='exact' if x==y else 'different'))
for name in ['one_image_geometry.json','rpc_geometry.json']:
 d=json.loads((a.bundle/'inputs'/name).read_text());oldim=old_by[d['image']];o={r['id']:r for r in oldim['annotations']}
 for r in d['records']:
  check_tree(r,o[r['id']],d['image']+'.'+r['id'])
  omissions.append(dict(image=d['image'],id=r['id'],omitted_source_fields='|'.join(sorted(set(o[r['id']])-set(r)))))
 check_tree(d['reference'],next(r for r in oldim['references'] if r['id']==d['reference']['id']),d['image']+'.reference')
 candidates=[r for r in oldim['annotations'] if r['condition']=='manual' and r['independent'] and r['consensus_eligible'] and r['main_consensus_gate']['status']=='main_candidate']
 rosters.append(dict(image=d['image'],excerpt_n=len(d['records']),archive_total_n=len(o),candidate_ids_equal=set(r['id'] for r in candidates)==set(r['id'] for r in d['records']),worker_pairs_equal=set((r['id'],r['worker']) for r in candidates)==set((r['id'],r['worker']) for r in d['records']),excluded_ids=sorted(set(o)-set(r['id'] for r in d['records'])),borrowed_points_all_false_in_source=all(o[r['id']]['borrowed_points'] is False for r in d['records']),building_equal=d['building']==oldim['building'],difficulty_equal=d['difficulty']==oldim['difficulty']))
pd.DataFrame(field_rows).to_csv(a.out/'input_field_checks.csv',index=False);pd.DataFrame(omissions).to_csv(a.out/'excerpt_omitted_fields.csv',index=False)
put('geometry_field_check',dict(fields=len(field_rows),status_counts=dict(Counter(x['status'] for x in field_rows)),rosters=rosters,scope='Every field present in the 48 excerpt records and two references compared recursively; omitted fields are not implied present.'))

# 3. All 480 matrix values from original full B geometries and declared reference policy.
refpol=pd.read_csv(a.archive/'analysis_results/worker_profiles_20261003/reference_policy.csv').set_index(['policy','image'])
matrows=[];matrix_summary=[]
for policy in ['original','revised_where_available']:
 file='matrix_'+policy+'_iou.csv';n=pd.read_csv(a.bundle/'inputs'/file);o=pd.read_csv(a.archive/'analysis_results/worker_profiles_20261003'/file)
 for _,row in n.iterrows():
  oldim=old_by[row.image];version=refpol.loc[(policy,row.image),'version'];g=Polygon(next(r['footprint'] for r in oldim['references'] if r['version']==version));by={r['worker']:r for r in oldim['annotations']}
  for w in n.columns[2:]:
   rr=by[w];poly=Polygon(rr['footprint']);v=poly.intersection(g).area/poly.union(g).area
   matrows.append(dict(policy=policy,image=row.image,worker=w,record_id=rr['id'],reference_version=version,stored=float(row[w]),independent_iou=v,abs_error=abs(v-float(row[w]))))
 matrix_summary.append(dict(policy=policy,images=len(n),workers=len(n.columns)-2,buildings=n.building.nunique(),archive_frame_exact=n.equals(o),all_finite=bool(np.isfinite(n.iloc[:,2:].to_numpy()).all())))
pd.DataFrame(matrows).to_csv(a.out/'matrix_geometry_independent.csv',index=False)
put('matrices',dict(frames=matrix_summary,cells=len(matrows),max_abs_geometry_error=max(x['abs_error'] for x in matrows)))

# 4. Entire 73-row excerpt independently derived from archived inventory records.
inv=json.loads((a.archive/'analysis_results/research_panel_inventory_20261003/input.json').read_text());ims={x['image']:x for x in inv['images']};gg=defaultdict(list)
for r in inv['records']:gg[(r['image'],r['condition'],r['consensus_gate'])].append(r)
derived={}
for (im,c,g),members in gg.items():
 cand=[r for r in members if r['consensus_candidate']]
 if len(cand)<20:continue
 derived[(im,c,g)]=dict(candidate_n=len(cand),candidate_bev_failed_n=sum(not r['bev_ok'] for r in cand),reference_quality_compatible=g=='main_candidate' and bool(cand) and all(r['quality_candidate'] for r in cand),difficulty=ims[im]['difficulty'],building=ims[im]['building'],curve_ready=bool(cand) and all(r['bev_ok'] for r in cand))
checks=[];excerpt=pd.read_csv(a.bundle/'inputs/high_support_inventory_excerpt.csv');ek=set()
for _,r in excerpt.iterrows():
 key=(r.image,r.condition,r.consensus_gate);ek.add(key)
 for field,v in derived[key].items():checks.append(dict(image=r.image,condition=r.condition,field=field,stored=r[field],derived=v,equal=r[field]==v))
pd.DataFrame(checks).to_csv(a.out/'inventory_field_checks.csv',index=False)
# independent fixed-denominator coverage
coverage=[];manual=excerpt[excerpt.condition=='manual'];author_cov=pd.read_csv(a.bundle/'results/fixed47_coverage_by_k.csv')
for k in range(1,21):
 probs=[math.comb(int(r.candidate_n-r.candidate_bev_failed_n),k)/math.comb(int(r.candidate_n),k) if k<=r.candidate_n-r.candidate_bev_failed_n else 0. for _,r in manual.iterrows()]
 coverage.append(dict(k=k,denominator=len(manual),expected_computable_fraction=sum(probs)/len(manual),source_error=abs(sum(probs)/len(manual)-float(author_cov.loc[author_cov.k==k,'expected_computable_fraction'].iloc[0]))))
pd.DataFrame(coverage).to_csv(a.out/'coverage_independent.csv',index=False)
put('inventory',dict(excerpt_rows=len(excerpt),derived_high_support_rows=len(derived),key_sets_equal=set(derived)==ek,fields=len(checks),mismatches=[x for x in checks if not x['equal']],conditions=excerpt.condition.value_counts().to_dict(),coverage_max_abs_error=max(x['source_error'] for x in coverage)))

# 5. Re-run real nested script with target-building outcomes changed, while verifying
# selected method, training score, outer prediction are invariant. Each perturbation
# uses its own scratch directory, and keeps all images of the target together.
isolation=[]
orig_cells=pd.read_csv(a.bundle/'results/nested_prediction_cells.csv');orig_choices=pd.read_csv(a.bundle/'results/nested_method_choices.csv');folds=pd.read_csv(a.bundle/'results/nested_inner_folds.csv')
for policy in ['original','revised_where_available']:
 df=pd.read_csv(a.bundle/'inputs'/('matrix_'+policy+'_iou.csv'))
 for target in sorted(df.building.unique()):
  with tempfile.TemporaryDirectory(prefix='personnel-isolation-',dir=a.out) as td:
   root=Path(td);(root/'inputs').mkdir();(root/'results').mkdir()
   for pp in ['original','revised_where_available']:
    dd=pd.read_csv(a.bundle/'inputs'/('matrix_'+pp+'_iou.csv'))
    if pp==policy:
     mask=dd.building==target
     dd.loc[mask,dd.columns[2:]]=np.linspace(0,1,24)[None,:]+np.arange(mask.sum())[:,None]*.01
    dd.to_csv(root/'inputs'/('matrix_'+pp+'_iou.csv'),index=False)
   env=dict(os.environ,WORKER_RESEARCH_ROOT=str(root.resolve()))
   subprocess.run([sys.executable,str((a.bundle/'src/nested_profiles.py').resolve())],env=env,check=True,stdout=subprocess.DEVNULL)
   ch=pd.read_csv(root/'results/nested_method_choices.csv');cc=pd.read_csv(root/'results/nested_prediction_cells.csv');ff=pd.read_csv(root/'results/nested_inner_folds.csv')
   x=orig_choices[(orig_choices.policy==policy)&(orig_choices.target==target)].iloc[0];y=ch[(ch.policy==policy)&(ch.target==target)].iloc[0]
   p1=orig_cells[(orig_cells.policy==policy)&orig_cells.image.isin(df.loc[df.building==target,'image'])].prediction.to_numpy();p2=cc[(cc.policy==policy)&cc.image.isin(df.loc[df.building==target,'image'])].prediction.to_numpy()
   f1=folds[(folds.policy==policy)&(folds.outer==target)].inner_mse.to_numpy();f2=ff[(ff.policy==policy)&(ff.outer==target)].inner_mse.to_numpy()
   isolation.append(dict(policy=policy,target=target,method_invariant=x.selected_method==y.selected_method,prediction_max_abs_change=float(np.max(abs(p1-p2))),inner_score_max_abs_change=float(np.max(abs(f1-f2))),target_test_mse_changed=not np.isclose(x.test_mse,y.test_mse)))
pd.DataFrame(isolation).to_csv(a.out/'target_perturbation_isolation.csv',index=False)
put('target_isolation',dict(perturbations=len(isolation),all_methods_invariant=all(x['method_invariant'] for x in isolation),prediction_max_abs_change=max(x['prediction_max_abs_change'] for x in isolation),inner_score_max_abs_change=max(x['inner_score_max_abs_change'] for x in isolation),all_heldout_losses_changed=all(x['target_test_mse_changed'] for x in isolation),interpretation='Targets used only for image-centred evaluation. Known-worker relative scores, not deployable absolute quality forecasts.'))

# 6. Exhaustive finite-pool brute force over all bit patterns, all 2+3 compositions.
# Fresh implementation: enumerated actual identity sets and replacement operations.
sys.path.insert(0,str((a.bundle/'src').resolve()))
import finite_pool as author
G=[set(range(2)),set(range(2,5))];N=(2,3);nchecks=Counter();maxerr=defaultdict(float)
def selections(groups,K):
 return [frozenset().union(*parts) for parts in itertools.product(*[list(map(frozenset,itertools.combinations(sorted(g),k))) for g,k in zip(groups,K)])]
def bit(S,bits,rule):return sum(bits[x] for x in S)>=(len(S)//2+1 if rule=='mv_strict' else (len(S)+1)//2)
def record(kind,v,w):
 nchecks[kind]+=1;maxerr[kind]=max(maxerr[kind],float(np.max(np.abs(np.asarray(v)-w))))
for bits in itertools.product([0,1],repeat=5):
 C=tuple(sum(bits[i] for i in g) for g in G)
 for K in itertools.product(range(3),range(4)):
  if not sum(K):continue
  SS=selections(G,K)
  for rule in ['mv50','mv_strict']:
   old=[bit(S,bits,rule) for S in SS];q=sum(old)/len(SS)
   record('marginal',q,author.marginal(N,C,K,rule));record('same_k_independent',sum(x!=y for x in old for y in old)/len(SS)**2,2*q*(1-q))
   ops=[]
   for A in [(1,0),(0,1),(2,0),(0,2),(1,1)]:
    if all(k+aa<=n for k,aa,n in zip(K,A,N)):ops.append(('add',A))
   if all(2*k<=n for k,n in zip(K,N)):ops.append(('disjoint',()))
   for aa in range(2):
    for bb in range(2):
     if K[aa] and K[bb]<N[bb]:ops.append(('swap',(aa,bb)))
   for op,change in ops:
    values=[]
    for S in SS:
     if op=='add': TT=[S|T for T in selections([g-S for g in G],change)]
     elif op=='disjoint':TT=selections([g-S for g in G],K)
     else:
      aa,bb=change;TT=[S-{u}|{v} for u in S&G[aa] for v in G[bb]-S]
     oo=bit(S,bits,rule);values.append(np.mean([[oo!=bit(T,bits,rule),not oo and bit(T,bits,rule),oo and not bit(T,bits,rule)] for T in TT],axis=0))
    kind=op+('_'+str(sum(change)) if op=='add' else '')
    record(kind,np.mean(values,axis=0),author.coupled(N,C,K,rule,op,change))
   for g in range(2):
    if K[g]<N[g]:
     raw=np.mean([np.mean([bit(S,bits,rule)!=bool(bits[i]) for i in G[g]-S]) for S in SS])
     record('next_raw_person',raw,author.next_member_loss(N,C,K,rule,g))
put('finite_pool_independent_bruteforce',dict(check_counts=dict(nchecks),max_abs_error=dict(maxerr),total_checks=sum(nchecks.values()),all_pass=max(maxerr.values())<2e-12,scope='All 32 fixed binary annotation populations with 2+3 people; two rules; all nonempty feasible compositions; add one/two including mixed-class add-two; same/cross-class swap; disjoint and independent draws.'))

# 7. Independently construct planar regions, enumerate all six-person identity sets.
# Direct polygon-intersection consensus (without full-pool tiles) on spread samples.
six=[];denoms=[]
for name in ['one_image_geometry.json','rpc_geometry.json']:
 d=json.loads((a.bundle/'inputs'/name).read_text());rec=sorted(d['records'],key=lambda r:r['worker']);polys=[Polygon(r['footprint']) for r in rec];g=Polygon(d['reference']['footprint']);u=unary_union(polys)
 faces=list(polygonize(unary_union([p.boundary for p in polys])));faces=[f for f in faces if u.covers(f.representative_point())]
 area=np.array([f.area for f in faces]);inside=np.array([f.intersection(g).area for f in faces]);votes=np.array([[p.covers(f.representative_point()) for f in faces] for p in polys],np.uint8)
 S=np.array(list(itertools.combinations(range(24),6)),dtype=np.uint8);z=np.load(a.bundle/'results'/f'{d["image"]}_six_person_all_sets.npz')
 err={};vals={}
 for rule,t in [('mv50',3),('mv_strict',4)]:
  yy=np.empty(len(S));aa=np.empty(len(S))
  for start in range(0,len(S),1024):
   masks=votes[S[start:start+1024]].sum(axis=1)>=t;inter=masks@inside;ar=masks@area;yy[start:start+len(masks)]=inter/(g.area+ar-inter);aa[start:start+len(masks)]=ar
  vals[rule]=yy;err[rule]=dict(iou_max_abs_error=float(np.max(abs(yy-z['iou_'+rule]))),area_max_abs_error=float(np.max(abs(aa-z['area_'+rule]))))
  max_direct=0.
  for i in np.linspace(0,len(S)-1,19,dtype=int):
   pieces=[]
   for ids in itertools.combinations(S[i].tolist(),t):
    inter=polys[ids[0]]
    for j in ids[1:]:inter=inter.intersection(polys[j])
    pieces.append(inter)
   fused=unary_union(pieces);direct=fused.intersection(g).area/fused.union(g).area;max_direct=max(max_direct,abs(direct-yy[i]))
  err[rule]['direct_intersection_consensus_samples']=19;err[rule]['direct_iou_max_abs_error']=max_direct
 six.append(dict(image=d['image'],subsets=len(S),unique_sets=len({tuple(s) for s in S}),subsets_exact=np.array_equal(S,z['subsets']),workers_exact=list(z['worker'])==[r['worker'] for r in rec],record_ids_exact=list(z['record_id'])==[r['id'] for r in rec],error=err))
 denoms.append(dict(image=d['image'],union_area=float(u.area),reference_area=float(g.area),reference_outside_pool_union=float(g.difference(u).area),tile_union_area_error=float(abs(area.sum()-u.area)),max_individual_area_error=float(max(abs(votes@area-np.array([p.area for p in polys])))),tile_n=len(faces),geometry_duplicate_groups=[v for v in ({str(p.wkb):[rec[j]['worker'] for j,q in enumerate(polys) if p.equals(q)] for p in polys}).values() if len(v)>1]))
put('six_person_independent',six);put('denominators',denoms)

# 8. Machine-status conclusion, tolerances explicit.
if bad:fail('manifest',str(bad))
if any(r['status'] not in ['exact_arrays','exact_bytes'] for r in rows):fail('replay','results differ or missing')
if any(x['status']!='exact' for x in field_rows):fail('fields','excerpt mismatch')
if any(not x['equal'] for x in checks) or set(derived)!=ek:fail('inventory','archived ledger mismatch')
if max(x['abs_error'] for x in matrows)>2e-12:fail('matrices','IoU mismatch')
if any(not x['method_invariant'] or x['prediction_max_abs_change']>2e-12 or x['inner_score_max_abs_change']>2e-12 for x in isolation):fail('isolation','target influence')
if max(maxerr.values())>2e-12:fail('formula','brute force mismatch')
if any(not x['subsets_exact'] or max(vv for ee in x['error'].values() for kk,vv in ee.items() if kk.endswith('error'))>2e-12 for x in six):fail('six','enumeration mismatch')
put('conclusion',dict(status='PASS' if not failures else 'FAIL',failures=failures,absolute_relative_tolerance=2e-12,limits=['Offline comparison authenticates consistency with supplied frozen package and old full B input, not a live git commit or unseen source images.','Reproduction is BEV-only; T/S/B currently unbound, never imputed zero.','24 known people and 10 images from 8 buildings; two geometric examples do not validate new workers or all 44 high-support images.','Reference gate compatibility is upstream ledger screening, not new visual validation.']))
