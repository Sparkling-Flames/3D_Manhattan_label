"""Independently compare clean replay output and audit the report's named claims.
No delivery source files are changed.
Usage: python verify_artifacts.py --source PACKAGE_ROOT --replay REPLAY_RESULTS
"""
from pathlib import Path
from collections import Counter
import argparse, csv, gzip, hashlib, json, math, itertools
P=argparse.ArgumentParser();P.add_argument('--source',type=Path,required=True,help='Extracted delivery package root');P.add_argument('--replay',type=Path,required=True,help='Newly reproduced results directory');a=P.parse_args()
S=a.source/'results';R=a.replay;OUT=R.parent

def load(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(1024*1024):h.update(c)
 return h.hexdigest()
def numeric_compare(a,b,stats,path='$'):
 if isinstance(a,dict) and isinstance(b,dict):
  if a.keys()!=b.keys():stats['structural_mismatches']+=1;return
  for k in a:numeric_compare(a[k],b[k],stats,path+'.'+str(k))
 elif isinstance(a,list) and isinstance(b,list):
  if len(a)!=len(b):stats['structural_mismatches']+=1;return
  for i,(x,y) in enumerate(zip(a,b)):numeric_compare(x,y,stats,path+f'[{i}]')
 elif type(a) in (int,float) and type(b) in (int,float):
  if a!=b:
   e=abs(a-b);stats['numeric_differences']+=1;stats['max_absolute_error']=max(e,stats['max_absolute_error'])
   if not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-10):stats['beyond_tolerance']+=1
   if len(stats['examples'])<5:stats['examples'].append(dict(path=path,source=a,replay=b))
 elif a!=b:
  stats['structural_mismatches']+=1
  if len(stats['examples'])<5:stats['examples'].append(dict(path=path,source=a,replay=b))

items=[];missing=[]
for s in sorted(S.rglob('*')):
 if not s.is_file():continue
 rel=s.relative_to(S);r=R/rel
 if not r.exists():missing.append(str(rel));continue
 hs,hr=sha(s),sha(r);row=dict(path=str(rel),source_bytes=s.stat().st_size,replay_bytes=r.stat().st_size,source_sha256=hs,replay_sha256=hr,byte_equal=hs==hr)
 if hs!=hr:
  stat=dict(numeric_differences=0,max_absolute_error=0,structural_mismatches=0,beyond_tolerance=0,examples=[])
  if s.suffix=='.gz':
   with gzip.open(s,'rt') as sf,gzip.open(r,'rt') as rf:
    for i,(x,y) in enumerate(itertools.zip_longest(sf,rf)):
     if x is None or y is None:stat['structural_mismatches']+=1;break
     if x!=y:numeric_compare(json.loads(x),json.loads(y),stat,f'$line[{i+1}]')
  elif s.suffix=='.json':numeric_compare(load(s),load(r),stat)
  else:
   with s.open(encoding='utf-8-sig') as sf,r.open(encoding='utf-8-sig') as rf:numeric_compare(list(csv.DictReader(sf)),list(csv.DictReader(rf)),stat)
  row['parsed_comparison']=stat
 items.append(row)
extras=sorted(str(p.relative_to(R)) for p in R.rglob('*') if p.is_file() and not (S/p.relative_to(R)).exists())
comparison=dict(source=str(S),replay=str(R),files=len(items),core_files=sum(not x['path'].startswith('summary/') for x in items),derived_summary_files=sum(x['path'].startswith('summary/') for x in items),byte_equal=sum(x['byte_equal'] for x in items),missing=missing,extra=extras,checks=items)
(OUT/'artifact_comparison.json').write_text(json.dumps(comparison,indent=2))

look=load(R/'domains/node_lookup.json');states=load(R/'domains/domains_summary.json');domains=[x for x in states if x.get('domain_id')];rpc=[x for x in domains if x['image']=='rPc6DW4iMge-06']
ns=look['rPc6DW4iMge-06'];nk=lambda i:f"{ns[i]['id']}:{ns[i]['pair_index']}"
target={i for i,n in enumerate(ns) if (n['id'],n['pair_index']) in [('R02452',2),('R01986',2),('R01557',4)]};wrong=next(i for i,n in enumerate(ns) if (n['id'],n['pair_index'])==('R01557',2))
checks=[]
def check(name,observed,expected):checks.append(dict(claim=name,observed=observed,expected=expected,passed=observed==expected))
check('local_domains',len(domains),41);check('total_feasible_partitions',sum(x['feasible'] for x in domains),1328993);check('full_records',load(R/'summary/summary.json')['full_records'],66);check('observations',sum(map(len,look.values())),400);check('distinct_workers',len({n['worker'] for nl in look.values() for n in nl}),24);check('baseline_states',len(load(R/'domains/baseline_partitions.json')),60);check('development_probes',len(load(R/'domains/development_probes.json')),45)
check('automatic_statuses',dict(Counter(x['automatic']['status'] for x in domains)),{'unchanged':28,'numerically_unique':13});check('rpc_domain_count',len(rpc),30);check('rpc_auto_repaired_domains',sum(any(x['automatic_triple_same']) for x in rpc),0);check('rpc_assisted_statuses',dict(Counter(x['assisted']['status'] for x in rpc)),{'constraints_outside_local_domain':21,'numerically_unique':9})
ledger_counts=[];main=[]
for state in domains:
 name=state['domain_id'];meta=load(R/'domains'/f'{name}.json');dom=meta['domain'];expected_union=set(dom['union']);forbidden=[tuple(p['nodes']) for p in dom['forbidden_pairs']]
 count=0;violations=0;old=[];minimum=float('inf');best=[];equal=[];human_count=0;mins=1000000;maxs=0;forced=None;size_hist=Counter()
 main5=name in {f'rPc6DW4iMge-06_{m}_5_d0' for m in ['pair','bottom','top']}
 with gzip.open(R/'domains'/meta['all_candidate_ledger'],'rt') as f:
  for line in f:
   row=json.loads(line);count+=1
   # Independent fixed-domain legality checks for every saved candidate.
   b0,b1=map(set,row['blocks'])
   legal=bool(b0 and b1 and not b0&b1 and b0|b1==expected_union and all((i in b0)!=(j in b0) for i,j in forbidden))
   violations+=not legal
   if main5:
    if row['cost']<minimum:minimum=row['cost']
    if row['edit_count']==0:old.append(row)
    group=b0 if next(iter(target)) in b0 else b1
    if target<=group and wrong not in group:
     human_count+=1;mins=min(mins,len(group));maxs=max(maxs,len(group));size_hist[len(group)]+=1;forced=set(group) if forced is None else forced&group
 ledger_counts.append(dict(domain_id=name,expected_count=state['feasible'],observed_count=count,invalid_candidates=violations,passed=count==state['feasible'] and violations==0))
 if main5:
  with gzip.open(R/'domains'/meta['all_candidate_ledger'],'rt') as f:
   for line in f:
    row=json.loads(line)
    if row['cost']<=minimum+1e-10:best.append(row['local_id'])
  policies={}
  for policy in ['automatic','human_assisted']:
   choice=meta[policy];selected=[r for r in meta['selected_details'] if r['local_id'] in choice['selected_ids']]
   policies[policy]=dict(choice=choice,selected=[dict(id=r['local_id'],cost=r['cost'],supports=r['supports'],moved=[[nk(i) for i in group] for group in r['moved_nodes_alternative_alignments']],lost=len(r['lost_coassignments']),added=len(r['added_coassignments']),identical_pairs_split=len(r['newly_split_identical_coordinates']),diameters=r['diameters_checked_deg'],correct_triple=r['human_development_probe']['same_group'],wrong_triple=r['human_development_probe']['wrong_triple_same_group']) for r in selected])
  main.append(dict(domain_id=name,feasible=count,baseline_id=old[0]['local_id'],baseline_cost=old[0]['cost'],minimum_cost=minimum,minimum_ids=best,human_feasible_count=human_count,target_group_size_range=[mins,maxs],forced_member_count=len(forced or []),size_histogram=dict(size_hist),policies=policies))
check('all_1328993_candidate_ledger_rows_legal',all(x['passed'] for x in ledger_counts),True)
by={x['domain_id'].split('_')[1]:x for x in main}
for m,n,h,ran,forced in [('pair',4096,1024,[6,16],6),('bottom',128,64,[10,16],10),('top',2048,512,[4,13],4)]:
 x=by[m];check(m+'_5deg_feasible',x['feasible'],n);check(m+'_5deg_human_feasible',x['human_feasible_count'],h);check(m+'_5deg_support_range',x['target_group_size_range'],ran);check(m+'_5deg_forced_member_count',x['forced_member_count'],forced)
check('pair_5deg_baseline_unique_W_minimum',by['pair']['minimum_ids'],[by['pair']['baseline_id']])
unb=next(x for x in load(R/'diagnostics/unb_target_layers.json') if x['threshold_deg']==5);check('unb_bottom_support',unb['bottom_support'],9);check('unb_upper_geometry_sizes',sorted(x['geometric_support'] for x in unb['geometric_top_subgroups']),[2,3,4]);check('unb_semantic_supports',{x['target']:x['top_support'] for x in unb['targets']},{'glass_to_ceiling':2,'low_glass_top':1,'unknown':6});check('unb_single_upper_target_selected',unb['single_upper_target_selected'],False)
rows=load(R/'controls/robustness_rows.json');check('transform_control_runs',len(rows),540);check('control_mode_counts',dict(Counter(x['mode'] for x in rows)),{'shuffle':144,'rename':144,'jitter':240,'seam':12});check('non_jitter_control_changes',sum(x['baseline_partition_changed'] or x['automatic_alternative_set_changed'] or x['assisted_alternative_set_changed'] for x in rows if x['mode']!='jitter'),0)
jitter=[x for x in load(R/'controls/robustness_summary.json') if x['mode']=='jitter'];expected_jitter={('rPc6DW4iMge-06','pair'):[6,13,6,96],('rPc6DW4iMge-06','bottom'):[12,12,12,50],('rPc6DW4iMge-06','top'):[3,8,3,24],('7y3sRwLe3Va-04','pair'):[2,2,0,23],('uNb9QFRL6hY-67','pair'):[5,5,0,5]}
for row in jitter:
 observed=[row[k] for k in ['baseline_changed','auto_set_changed','assisted_set_changed','max_changed_relations']];check('jitter_'+row['image']+'_'+row['metric'],observed,expected_jitter.get((row['image'],row['metric']),[0,0,0,0]))
check('all_five_upstream_scalar_checks',load(R/'summary/summary.json')['all_source_scalar_crosschecks_passed'],True)
check('all_selected_constraints_valid',load(R/'summary/summary.json')['all_selected_valid_constraints'],True)
check('all_selected_outside_memberships_fixed',load(R/'summary/summary.json')['all_selected_outside_memberships_fixed'],True)
result=dict(claims=checks,all_claims_pass=all(x['passed'] for x in checks),candidate_ledger_checks=ledger_counts,main_5deg=main,unb_5deg=unb,summary=load(R/'summary/summary.json'),control_jitter_summary=jitter)
(OUT/'claim_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(dict(files_compared=len(items),byte_equal=comparison['byte_equal'],core_files=comparison['core_files'],summary_files=comparison['derived_summary_files'],missing=missing,extra=extras,claims=len(checks),claims_passed=sum(x['passed'] for x in checks),ledger_rows=sum(x['observed_count'] for x in ledger_counts),illegal_rows=sum(x['invalid_candidates'] for x in ledger_counts)),indent=2))
