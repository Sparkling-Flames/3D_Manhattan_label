#!/usr/bin/env python3
"""Read-only handoff replay. Run with package root on PYTHONPATH. No GT used."""
import argparse, copy, hashlib, importlib, itertools, json, math, os, platform, sys, time
from collections import Counter, defaultdict
from pathlib import Path

parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path,required=True); parser.add_argument('--out',type=Path,required=True)
a=parser.parse_args(); src=a.source.resolve(); out=a.out.resolve(); out.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True; sys.path.insert(0,str(src)); os.environ.setdefault('MPLCONFIGDIR',str(out/'mplconfig')); os.environ.setdefault('NUMBA_CACHE_DIR',str(out/'numba_cache'))
def dump(name,value):
 (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def read(name): return json.loads((src/name).read_text(encoding='utf-8'))
def hashes(): return {str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(src.rglob('*')) if p.is_file()}
before_hash=hashes(); dump('source_sha256_before.json',before_hash)
import numpy as np
from tools.thesis_main.analysis.point_route_panel_20261005 import build_routes
from tools.thesis_main.analysis.point_context_probe_20261006 import compare_context, reviewed_relation, subdivision_control, threshold_sensitivity
versions={'python':sys.version,'platform':platform.platform()}
for name in ['numpy','scipy','shapely','pandas','matplotlib','PIL','numba']:
 
 try:
  mod=importlib.import_module(name); versions[name]={'version':mod.__version__,'file':mod.__file__}
 except ModuleNotFoundError:
  versions[name]={'version':None,'optional_audit_module_unavailable':True}
versions['declared_handoff']=read('manifest.json')['environment']; dump('environment.json',versions)
inputs=read('inputs.json'); expected=read('baselines.json')['states']; manifest=read('manifest.json'); before=copy.deepcopy(inputs)
rosters=[]; all_ids=[]; totalpairs=0
for im in inputs['images']:
 recs=im['records']; ids=[r['id'] for r in recs]; workers=[r['worker'] for r in recs]
 assert len(set(ids))==len(ids)==len(set(workers))
 assert len(recs)==next(x['n'] for x in manifest['images'] if x['image']==im['image'])
 for r in recs:
  p=np.asarray(r['points'],float); q=len(p)//2; totalpairs+=q
  assert len(p)>=8 and len(p)%2==0 and p.shape==(len(p),2) and np.isfinite(p).all()
  assert np.all(p>=0) and np.all(p[:,0]<=1024) and np.all(p[:,1]<=512)
  assert np.all(p[::2,0]==p[1::2,0]) and np.all(p[::2,1]<p[1::2,1])
  assert r['independent'] is True and r['consensus_eligible'] is True and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'
  assert r['borrowed_points'] is False and r['independence_reasons']==[]
  assert len(r['source_pair_indices'])==len(set(r['source_pair_indices']))==q
  assert len(r['source_point_indices'])==len(set(r['source_point_indices']))==len(p)
  assert len(r['source_point_labels'])==len(p)
  all_ids.append(r['id'])
 rosters.append({'image':im['image'],'n':len(recs),'ids':ids,'workers':workers,'endpoint_counts':sorted(Counter(len(r['points']) for r in recs).items()),'pair_count':sum(len(r['points'])//2 for r in recs),'confirmed_rings':sum(r['ring_confirmed'] is True for r in recs),'order_states':dict(Counter(r['order_status'] for r in recs)),'cleaning_states':dict(Counter(r['cleaning'] for r in recs))})
assert len(rosters)==9 and len(all_ids)==len(set(all_ids))==manifest['records']==150
from PIL import Image
image_inventory=[]
assert {p.stem for p in (src/'images').glob('*.png')}=={im['image'] for im in inputs['images']}
for p in sorted((src/'images').glob('*.png')):
 with Image.open(p) as photo:
  image_inventory.append({'image':p.stem,'pixel_dimensions':list(photo.size),'annotation_canvas':[1024,512]})
dump('image_inventory.json',image_inventory)

assert len(expected)==manifest['baseline_states']==108
assert [im['image'] for im in inputs['images']]==[im['image'] for im in manifest['images']]
dump('roster_checks.json',{'images':rosters,'image_count':9,'record_count':150,'pair_count':totalpairs,'eligibility_fields_passed':True,'provenance_index_shapes_passed':True,'scope':'Metadata and roster consistency within the extracted handoff; no unavailable upstream 137-image raw source was reconstructed.'})
actual=[]; failures=[]; opened=[]
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)): opened.append(str(args[0]))
sys.addaudithook(audit)
start=time.monotonic()
for im in inputs['images']:
 for t in [5,9,12]:
  try:
   for route,result in build_routes(im['records'],t).items(): actual.append(dict(image=im['image'],threshold_deg=t,route=route,result=result))
  except Exception as e:
   import traceback
   failures.append(dict(image=im['image'],threshold_deg=t,error=repr(e),traceback=traceback.format_exc()))
 print(im['image'],len(actual),'states',flush=True)
elapsed=time.monotonic()-start
construction_evaluation_reads=[p for p in opened if '/evaluation/' in p or p.endswith('references.json')]
assert not construction_evaluation_reads
assert inputs==before
# Exact comparison plus exhaustive numeric drift, with discrete differences distinguished.
differences=[]
def diff(x,y,p=''):
 if type(x)!=type(y):
  differences.append({'path':p,'kind':'type','expected_type':type(y).__name__,'actual_type':type(x).__name__,'expected':y,'actual':x}); return
 if isinstance(x,dict):
  if x.keys()!=y.keys(): differences.append({'path':p,'kind':'keys','expected':list(y),'actual':list(x)})
  for k in sorted(x.keys() & y.keys()): diff(x[k],y[k],p+'/'+str(k))
 elif isinstance(x,list):
  if len(x)!=len(y): differences.append({'path':p,'kind':'length','expected':len(y),'actual':len(x)})
  for i,(xx,yy) in enumerate(zip(x,y)): diff(xx,yy,p+'/'+str(i))
 elif x!=y:
  d={'path':p,'kind':'float' if isinstance(x,float) else 'discrete','expected':y,'actual':x}
  if isinstance(x,float): d.update(abs_error=abs(x-y),relative_error=abs(x-y)/max(abs(x),abs(y),1e-300),within_1e_9_abs_plus_1e_12_rel=abs(x-y)<=1e-9+1e-12*max(abs(x),abs(y)))
  differences.append(d)
diff(actual,expected)
floats=[d for d in differences if d['kind']=='float']; discrete=[d for d in differences if d['kind']!='float']
field_counts=Counter('/'.join(k for k in d['path'].split('/') if not k.isdigit()) for d in floats)
comparison={'expected_states':len(expected),'actual_states':len(actual),'runtime_seconds':elapsed,'failures':failures,'full_parsed_equality':actual==expected,'exact_equal_states':sum(x==y for x,y in zip(actual,expected)),'different_states':len({d['path'].split('/')[1] for d in differences}),'float_difference_count':len(floats),'non_float_difference_count':len(discrete),'max_absolute_float_error':max((d['abs_error'] for d in floats),default=0),'all_numeric_differences_within_abs1e_9_rel1e_12':all(d['within_1e_9_abs_plus_1e_12_rel'] for d in floats),'all_discrete_semantics_equal':not discrete,'numeric_fields':dict(field_counts),'largest_numeric_differences':sorted(floats,key=lambda d:d['abs_error'],reverse=True)[:20],'construction_evaluation_reads':construction_evaluation_reads,'input_unchanged_in_memory':inputs==before}
dump('actual_baselines.json',{'schema':'structure_constraint_baseline_v1','states':actual}); dump('comparison.json',comparison); dump('all_differences.json',differences)
print('COMPARISON',json.dumps({k:v for k,v in comparison.items() if k not in ['largest_numeric_differences','numeric_fields']},ensure_ascii=False),flush=True)
# Independent audits use vector atan2 distances, original metadata and explicit rings.
compact=[]; binding_count=0; group_count=0; max_angle_error=0.; max_match_error=0.; endpoint_pairs=0; checks=[]
def key(m): return m['id'],m['pair_index']
def ring_eq(a,b):
 return len(a)==len(b) and (not a or any(a==z[k:]+z[:k] for z in [b,b[::-1]] for k in range(len(b))))
for s in actual:
 im=next(im for im in inputs['images'] if im['image']==s['image']); records=im['records']; source={r['id']:r for r in records}; r=s['result']; c=r['candidate']; n=len(records); t=s['threshold_deg']; route=s['route']; minimum=(n+1)//2
 assert r['n']==r['vote_denominator']==n and r['minimum_support']==minimum and r['method']=='mv50'
 assert c['ring_confirmed'] is False and r['threshold_calibrated'] is False and not r['input_issues']
 sides=list(r['endpoint_groups'].items()) if route=='split_unique' else [({'paired':None,'top_anchor':'top','bottom_anchor':'bottom'}[route],r['identity_groups'])]
 for side,groups in sides:
  seen=[]
  for g in groups:
   members=g['members']; group_count+=1
   assert len(members)==g['support']==len(set(m['worker'] for m in members))
   assert g['support_workers']==[m['worker'] for m in members]
   if 'selected' in g: assert g['selected']==(g['support']>=minimum)
   for m in members:
    rec=source[m['id']]; i=m['pair_index']; binding_count+=1
    assert m['worker']==rec['worker'] and m['points']==rec['points'][2*i:2*i+2]
    assert m['source_pair_index']==rec['source_pair_indices'][i] and m['source_point_indices']==rec['source_point_indices'][2*i:2*i+2]
    seen.append(key(m))
   p=np.asarray([m['points'] for m in members]); u=p[:,:,0]*2*np.pi/1024; v=(.5-p[:,:,1]/512)*np.pi
   ray=np.stack((np.cos(v)*np.cos(u),np.cos(v)*np.sin(u),np.sin(v)),axis=-1)
   ang=np.degrees(np.arctan2(np.linalg.norm(np.cross(ray[:,None],ray[None,:]),axis=-1),np.einsum('isk,jsk->ijs',ray,ray)))
   max_angle_error=max(max_angle_error,abs(float(ang.max())-g['maximum_pair_angle_deg']))
   diam=ang.max() if side is None else ang[:,:,0 if side=='top' else 1].max()
   assert diam<=t+1e-9
   if side: max_match_error=max(max_match_error,abs(float(diam)-g['maximum_match_angle_deg']))
  assert len(seen)==len(set(seen))==sum(len(rec['points'])//2 for rec in records)
  assert set(seen)=={(rec['id'],i) for rec in records for i in range(len(rec['points'])//2)}
 for g in r.get('paired_identities',[]):
  top={key(m) for m in g['top_members']}; bottom={key(m) for m in g['bottom_members']}; joint={key(m) for m in g['joint_members']}
  assert joint==top&bottom and len(joint)==g['joint_support']; endpoint_pairs+=1
 # Source assignments preserve original ring indexing and confirmation.
 for ass in r['assignments']:
  rec=source[ass['id']]; assert ass['source_ring_confirmed']==rec['ring_confirmed'] and ass['source_order_status']==rec['order_status']
  assert len(ass['feature_ids'])==len(rec['points'])//2
 if route!='split_unique':
  membership={key(m):g['feature_id'] for g in r['identity_groups'] for m in g['members']}
  for ass in r['assignments']: assert ass['feature_ids']==[membership[(ass['id'],i)] for i in range(len(ass['feature_ids']))]
 ring=r['ring_diagnostics']
 if ring and ring.get('edges'):
  ids=c['feature_ids']; retained=set(ids); direct=defaultdict(set); projected=defaultdict(set); exact=proj=0
  for ass in r['assignments']:
   rr=ass['feature_ids']; kept=[v for v in rr if v in retained]
   for aa,bb in zip(rr,rr[1:]+rr[:1]): direct[tuple(sorted((aa,bb)))].add(ass['worker'])
   if len(kept)>=3:
    for aa,bb in zip(kept,kept[1:]+kept[:1]): projected[tuple(sorted((aa,bb)))].add(ass['worker'])
   proj+=ring_eq(kept,ids); exact+=ring_eq(rr,ids)
  for edge in ring['edges']:
   ek=tuple(sorted(edge['feature_ids'])); assert set(edge['support_workers'])==direct[ek] and edge['support']==len(direct[ek]); assert set(edge['projected_source_workers'])==projected[ek] and edge['projected_source_support']==len(projected[ek]); assert edge['meets_point_vote_threshold']==(edge['support']>=minimum)
  assert ring['exact_source_ring_support']==exact and ring['projected_source_ring_support']==proj
 selected=None if route=='split_unique' else sum(g['support']>=minimum for g in r['identity_groups'])
 generated=None if c['points'] is None else len(c['points'])//2
 if selected is not None and selected<3: assert c['points'] is None and c['reason']=='fewer_than_three_majority_pairs'
 if generated is not None and selected is not None: assert generated==selected
 compact.append({'image':s['image'],'n':n,'threshold_deg':t,'route':route,'selected_pair_count':selected,'generated_pair_count':generated,'below_four_selected_pairs':None if selected is None else selected<4,'status':c['status'],'reason':c['reason'],'geometry_status':c.get('geometry_status'),'minimum_support':minimum,'groups':{side or 'paired':len(groups) for side,groups in sides},'unsupported_edges':ring.get('unsupported_edge_count') if ring else None,'below_majority_edges':ring.get('below_majority_edge_count') if ring else None,'exact_source_ring_support':ring.get('exact_source_ring_support') if ring else None})
under4=[r for r in compact if r['below_four_selected_pairs']]
independent={'verified_states':len(actual),'source_member_bindings':binding_count,'identity_groups':group_count,'split_pairs_checked':endpoint_pairs,'maximum_vector_vs_source_angle_error_deg':max_angle_error,'maximum_vector_vs_source_match_error_deg':max_match_error,'all_membership_support_provenance_assignment_and_ring_checks_passed':True,'below_four_selected_states':under4,'three_pair_geometry_retained':sum(r['generated_pair_count']==3 and r['geometry_status']=='ok' for r in compact),'below_three_no_candidate':sum(r['selected_pair_count'] is not None and r['selected_pair_count']<3 and r['generated_pair_count'] is None for r in compact),'statuses_by_route':{route:dict(Counter(r['status'] for r in compact if r['route']==route)) for route in ['paired','bottom_anchor','top_anchor','split_unique']}}
dump('compact_states.json',compact); dump('independent_checks.json',independent)
print('INDEPENDENT CHECKS',json.dumps({k:v for k,v in independent.items() if k!='below_four_selected_states'}),flush=True)
# Recount all-image saved ledger; not a fresh 137-image geometry replay.
ledger=read('evidence/all_image_pair_count_audit.json'); inv=ledger['inventory']; rows=ledger['rows']; index={r['image']:r for r in inv}
assert len(inv)==len(index)==137 and sum(r['n'] for r in inv)==1520 and len(rows)==1644
assert {(r['image'],r['threshold_deg'],r['route']) for r in rows}==set(itertools.product(index,[5,9,12],['paired','bottom_anchor','top_anchor','split_unique']))
assert all(sum(count for endpoints,count in r['source_endpoint_counts'])==r['n'] and all(endpoints>=8 and endpoints%2==0 for endpoints,count in r['source_endpoint_counts']) for r in inv)
for r in rows:
 assert r['n']==index[r['image']]['n'] and r['minimum_support']==(r['n']+1)//2
 selected=r['selected_pair_count']; generated=r['generated_pair_count']
 if selected is not None: assert selected==sum(v>=r['minimum_support'] for v in r['group_supports']) and r['below_four_selected_pairs']==(selected<4)
 assert r['below_four_generated_pairs']==(None if generated is None else generated<4)
shortfalls={str(t):{'count':sum(r['below_four_selected_pairs'] for r in rows if r['route']=='paired' and r['threshold_deg']==t),'three':sum(r['selected_pair_count']==3 for r in rows if r['route']=='paired' and r['threshold_deg']==t),'zero_to_two':sum(r['selected_pair_count']<3 for r in rows if r['route']=='paired' and r['threshold_deg']==t)} for t in [5,9,12]}
assert [shortfalls[str(t)]['count'] for t in [5,9,12]]==[29,10,5]
issue_rows=[r for r in rows if r['input_issues']]; assert len(issue_rows)==12
assert all(r['image']=='rPc6DW4iMge-22' and r['n']==24 and r['minimum_support']==12 and r['input_issues']==[{'id':'R01424','worker':'P002','reason':'coordinates_outside_continuous_canvas'}] for r in issue_rows)
idx={(r['image'],r['threshold_deg'],r['route']):r for r in rows}; cross_fields=['n','minimum_support','selected_pair_count','generated_pair_count','below_four_selected_pairs','status','reason']
for c in compact:
 e=idx[c['image'],c['threshold_deg'],c['route']]
 for f in cross_fields: assert c[f]==e[f],(c['image'],c['threshold_deg'],c['route'],f,c[f],e[f])
summary={'scope':'Independent arithmetic and internal consistency checks of supplied 137-image/1644-state summary, plus crosscheck against 108 actually replayed panel states. Not a full 137-image geometry replay. Upstream raw geometry for remaining 128 images not provided here.','images':137,'qualified_records':1520,'records_are_not_unique_people':True,'all_inventory_records_at_least_eight_endpoints':True,'states':1644,'paired_shortfalls':shortfalls,'nine_degree_shortfalls_with_23_or_24_records':sum(r['n']>=23 and r['below_four_selected_pairs'] for r in rows if r['route']=='paired' and r['threshold_deg']==9),'preserved_failure':{'image':'rPc6DW4iMge-22','record':'R01424','worker':'P002','n':24,'minimum_support':12,'affected_state_rows':12,'reason':'coordinates_outside_continuous_canvas'},'replayed_panel_states_matched_ledger':len(compact),'other_routes':{route:{str(t):{'below_four_selected':None if route=='split_unique' else sum(r['below_four_selected_pairs'] is True for r in rows if r['route']==route and r['threshold_deg']==t),'below_four_generated':sum(r['below_four_generated_pairs'] is True for r in rows if r['route']==route and r['threshold_deg']==t),'no_generated':sum(r['generated_pair_count'] is None for r in rows if r['route']==route and r['threshold_deg']==t)} for t in [5,9,12]} for route in ['bottom_anchor','top_anchor','split_unique']}}
dump('global_count_ledger_checks.json',summary); print('GLOBAL',json.dumps(summary,ensure_ascii=False),flush=True)
# Reproduce numeric neighbor probe from delivered pools; leave visual study to separate review.
human=read('human_review.json'); pools={im['image']:im['records'] for im in inputs['images']}; neighbor=[]; nearest=[]
for review in human['reviews']:
 records=pools[review['image']]; source={r['id']:r for r in records}
 for rid,i in zip(review['record_ids'],review['processed_pair_indices'],strict=True):
  query=source[rid]; aa=np.asarray(query['points']).reshape(-1,2,2)
  for other in records:
   if other['worker']==query['worker']: continue
   bb=np.asarray(other['points']).reshape(-1,2,2)
   for metric in ['pair','top','bottom']:
    candidates=[]
    for j in range(len(bb)):
     v=dict(case_id=review['case_id'],image=review['image'],metric=metric,query=[rid,i],candidate=[other['id'],j],source_pair_indices=[query['source_pair_indices'][i],other['source_pair_indices'][j]],order_status=[query['order_status'],other['order_status']],relation=reviewed_relation(review,(rid,i),(other['id'],j),metric),**compare_context(aa,i,bb,j,metric))
     candidates.append(v)
    for v in candidates:
     for name in ['anchor','combined']: v[name+'_rank']=1+sum(x[name+'_deg']<v[name+'_deg']-1e-9 for x in candidates)
     neighbor.append(v)
    nearest.append(dict(case_id=review['case_id'],query=[rid,i],target_record=other['id'],metric=metric,candidate_count=len(candidates),anchor_nearest=[v['candidate'] for v in candidates if v['anchor_rank']==1],combined_nearest=[v['candidate'] for v in candidates if v['combined_rank']==1]))
reviewed=[v for v in neighbor if v['relation']!='unreviewed']; assert len(neighbor)==2565 and len(reviewed)==52
control=subdivision_control(); assert control['comparison']['anchor_deg']==0 and math.isclose(control['comparison']['combined_deg'],41.810314895778596,abs_tol=1e-9)
rpc=[v for v in reviewed if v['query']==['R02452',2] and v['candidate'][0]=='R01557' and v['metric']=='pair']
assert len(rpc)==2
correct=next(v for v in rpc if v['candidate'][1]==4); wrong=next(v for v in rpc if v['candidate'][1]==2)
assert correct['anchor_rank']==1 and correct['combined_rank']==2 and wrong['anchor_rank']==2 and wrong['combined_rank']==1
# Independent vector distance implementation validates all neighbor scalars.
def vector_angles(x,y):
 def rays(p):
  u=p[:,0]*2*np.pi/1024; v=(.5-p[:,1]/512)*np.pi
  return np.stack([np.cos(v)*np.cos(u),np.cos(v)*np.sin(u),np.sin(v)],axis=-1)
 x=rays(x); y=rays(y)
 return np.degrees(np.arctan2(np.linalg.norm(np.cross(x[:,None],y[None,:]),axis=-1),x@y.T))
neighbor_max_error=0.
for v in neighbor:
 source={r['id']:r for r in pools[v['image']]}; aa=np.asarray(source[v['query'][0]]['points']).reshape(-1,2,2); bb=np.asarray(source[v['candidate'][0]]['points']).reshape(-1,2,2); i=v['query'][1]; j=v['candidate'][1]
 aa=aa[[(i-1)%len(aa),i,(i+1)%len(aa)]]; bb=bb[[(j-1)%len(bb),j,(j+1)%len(bb)]]
 top=vector_angles(aa[:,0],bb[:,0]); bottom=vector_angles(aa[:,1],bb[:,1]); d={'top':top,'bottom':bottom,'pair':np.maximum(top,bottom)}[v['metric']]
 anch=float(d[1,1]); neigh=float(min(max(d[0,0],d[2,2]),max(d[0,2],d[2,0])))
 neighbor_max_error=max(neighbor_max_error,abs(anch-v['anchor_deg']),abs(neigh-v['neighbor_deg']),abs(max(anch,neigh)-v['combined_deg']))
assert neighbor_max_error<1e-9
# Ring representation controls: reversal, rotation and common seam shift preserve A/N/B.
rec=pools['rPc6DW4iMge-06']; aa=np.asarray(rec[0]['points']).reshape(-1,2,2); bb=np.asarray(rec[1]['points']).reshape(-1,2,2); i=j=0; score=compare_context(aa,i,bb,j,'pair'); invariant=[]
for label,x,ix,y,jx in [('reverse',aa[::-1],len(aa)-1-i,bb[::-1],len(bb)-1-j),('rotate',np.roll(aa,1,axis=0),(i+1)%len(aa),np.roll(bb,2,axis=0),(j+2)%len(bb))]:
 new=compare_context(x,ix,y,jx,'pair'); err=max(abs(new[k]-score[k]) for k in ['anchor_deg','neighbor_deg','combined_deg']); assert err<1e-9; invariant.append({'control':label,'max_error':err})
x=aa.copy(); y=bb.copy(); x[:,:,0]=(x[:,:,0]+171)%1024; y[:,:,0]=(y[:,:,0]+171)%1024; new=compare_context(x,i,y,j,'pair'); err=max(abs(new[k]-score[k]) for k in ['anchor_deg','neighbor_deg','combined_deg']); assert err<1e-9; invariant.append({'control':'common_seam_shift','max_error':err})
nb_summary={'scope':'Numeric reproduction only; no new visual adjudication or e9z study','full_comparisons':len(neighbor),'reviewed_directed_comparisons':len(reviewed),'unreviewed_comparisons':len(neighbor)-len(reviewed),'record_metric_queries':len(nearest),'rpc_correct_wrong':rpc,'subdivision_control':control,'vector_crosscheck_max_error_deg':neighbor_max_error,'ring_representation_invariance':invariant,'reviewed_relations_not_independent_samples':True}
dump('neighbor_summary.json',nb_summary); dump('neighbor_comparisons.json',neighbor); dump('neighbor_reviewed_comparisons.json',reviewed); dump('neighbor_threshold_sensitivity.json',threshold_sensitivity(reviewed)); dump('neighbor_nearest.json',nearest)
assert inputs==before
after_hash=hashes(); assert after_hash==before_hash; dump('source_sha256_after.json',after_hash)
dump('completion.json',{'completed':True,'source_files_unchanged':True,'source_file_count':len(before_hash),'python_files_on_disk':len(list((src/'tools').rglob('*.py')))+len(list((src/'lib').rglob('*.py'))),'declared_source_modules':manifest['source_modules'],'module_count_interpretation':'Manifest states 44 source_modules; extracted tree contains 45 .py files including package initializers. Counting definition is unspecified; replay is unaffected.','all_108_states_completed':len(actual)==108,'raw_four_pair_gate_not_applied':True,'no_full_137_geometry_replay_claimed':True,'no_reference_files_read_for_construction':True,'failures':failures})
print('DONE; source files unchanged',len(before_hash),flush=True)
