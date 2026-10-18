import json,gzip,hashlib,itertools
from pathlib import Path
import pandas as pd,numpy as np
B=Path('/workspace/shared/personnel_v2_audit_20261018');C=B/'independent/curves';S=B/'extracted/work_v2_20261019';O=B/'independent/models';rd=lambda p:json.load(gzip.open(p,'rt')) if str(p).endswith('.gz') else json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();h=lambda x:hashlib.sha256(str(x).encode()).hexdigest()
reg=rd(C/'REGISTRATION.json');design=rd(C/'DESIGN.json');receipt=rd(C/'DESIGN_RECEIPT.json');pools=rd(S/'fusion/INPUT_SNAPSHOT.json.gz')['images'];by={p['pool_id']:p for p in pools};f=pd.read_csv(S/'profiles/fold_profiles.csv');pairs=pd.read_csv(S/'clusters/pair_distances.csv.gz');pairs=pairs[pairs.layer.eq('ordinary_manual')].copy();pairs['pair']=['|'.join(sorted(x)) for x in zip(pairs.worker_id_a,pairs.worker_id_b)];assert not pairs.duplicated(['pool_id','pair']).any()
checks={};checks['immutable_hashes']={p:sha(S/p)==v for p,v in reg['immutable_inputs'].items()};checks['registration_hash_matches']=sha(C/'REGISTRATION.json')==receipt['registration_sha'];checks['design_hash_matches']=sha(C/'DESIGN.json')==receipt['design_sha'];eligible=[p for p in pools if p['meta']['layer']=='ordinary_manual' and p['meta']['difficulty_aligned'] and len(p['records'])>=26];chosen={}
for p in sorted(eligible,key=lambda p:h(p['pool_id']+reg['seed'])):chosen.setdefault((p['meta']['building'],p['meta']['difficulty']),p['pool_id'])
checks['selected_pool_ids_exact']=set(chosen.values())==set(design['selected_pool_ids']);req={r['request_id']:r for r in design['requests']};assert len(req)==len(design['requests']);errors=[];cache={};max_qdiff=0;histgaps=[];abc_equal=0
for e in design['experiments']:
 p=by[e['pool_id']];building=e['building'];diff=e['difficulty'];fp=f[f.heldout_building.eq(building)].set_index('worker_id');rec={r['worker_id']:r for r in p['records']};a,b,c=[e[k] for k in 'abc'];rng=np.random.default_rng(int(h(e['pool_id']+str(e['context'])+reg['seed'])[:16],16));order=rng.permutation(sorted(rec)).tolist();bg=order[:23]
 assert e['background']==bg and set([a,b,c]).isdisjoint(bg) and len({a,b,c})==3
 assert all(fp.loc[w,'Q_supported'] for w in [a,b,c]);qd=abs(fp.loc[b,'Q_effect_B8L2']-fp.loc[c,'Q_effect_B8L2']);assert qd<=3;max_qdiff=max(max_qdiff,qd);assert len(rec[b]['points'])==len(rec[c]['points']);abc_equal+=len(rec[a]['points'])==len(rec[b]['points'])
 assert set(e['requests'])==set(map(str,reg['k']))
 for k,rs in e['requests'].items():
  assert set(rs)==set('abc')
  for arm,rid in rs.items():
   r=req[rid];assert r['worker_ids']==bg[:int(k)-1]+[e[arm]] and r['k']==int(k) and r['experiment_id']==e['experiment_id'];assert len(set(r['worker_ids']))==int(k)
 if building not in cache:
  t=pairs[pairs.building_id.ne(building)];prior=t.groupby(['pool_id','building_id','difficulty']).same_affinity_9.mean().reset_index().groupby(['building_id','difficulty']).same_affinity_9.mean().reset_index().groupby('difficulty').same_affinity_9.mean();st=t.groupby(['pair','difficulty']).agg(s=('same_affinity_9','sum'),n=('pool_id','nunique'),buildings=('building_id','nunique'));cache[building]=(prior,st)
 prior,st=cache[building]
 def hist(x,y):
  key=('|'.join(sorted((x,y))),diff)
  if key not in st.index:return None
  v=st.loc[key]
  if v.n<6 or v.buildings<3:return None
  return float((v.s+5*prior[diff])/(v.n+5))
 for x,key in [(b,'p_ab'),(c,'p_ac')]:
  actual=hist(a,x);assert actual==e[key] or (actual is not None and abs(actual-e[key])<1e-14)
 if e['method']=='history_same_difficulty':assert hist(a,b)-hist(a,c)>=.2;histgaps.append(hist(a,b)-hist(a,c))
 else:
  col='QT_B8L2' if e['method']=='QT' else 'fine_dtype_B8L2';labs=[fp.loc[w,col] for w in [a,b,c]];assert not any('unknown' in str(x) for x in labs);assert labs[0]==labs[1] and labs[0]!=labs[2]
 # Independently repeat all feasible-set sampling, without inspecting fusion outcomes.
 feasible=[]
 for aa,bb,cc in itertools.permutations(order[23:],3):
  if any(w not in fp.index or not fp.loc[w,'Q_supported'] or not np.isfinite(fp.loc[w,'Q_effect_B8L2']) for w in (aa,bb,cc)):continue
  if len(rec[bb]['points'])!=len(rec[cc]['points']) or abs(fp.loc[bb,'Q_effect_B8L2']-fp.loc[cc,'Q_effect_B8L2'])>3:continue
  if e['method']=='history_same_difficulty':
   pb,pc=hist(aa,bb),hist(aa,cc)
   if pb is None or pc is None or pb-pc<.2:continue
  else:
   labs=[str(fp.loc[w,col]) for w in (aa,bb,cc)]
   if any('unknown' in x.lower() or x=='nan' for x in labs) or not(labs[0]==labs[1] and labs[0]!=labs[2]):continue
  feasible.append((aa,bb,cc))
 rng=np.random.default_rng(int(h(e['pool_id']+str(e['context'])+e['method']+reg['seed'])[:16],16));assert feasible[int(rng.integers(len(feasible)))]==(a,b,c)
checks.update(experiments_checked=len(design['experiments']),requests_checked=len(req),all_registered_chain_members_match=True,all_selected_triples_deterministically_reproduced=True,max_bc_training_Q_difference=max_qdiff,history_min_probability_gap=min(histgaps),all_three_point_counts_equal_experiments=abc_equal,bc_equal_point_counts_all=True,history_pair_task_duplicates=0)
report={'checks':checks,'reviewed_code_sha':sha(C/'study.py'),'selection_uses_target_quality_or_affinity':False,'target_information_used':['known target difficulty','worker availability','b/c submitted point counts'],'training_isolation':'All fold Q/QT/QTD labels exclude entire target building; history pair statistics and difficulty prior also exclude target building. Historical pair labels only are used. Target difficulty is known stratification, not fitted from heldout outcomes.','aggregation_review':'Within triple near/far contrasts share outgoing a and exact same nested backgrounds; mean contexts within image, mean images within building, bootstrap paired building differences. Methods may have different identities/opportunities and are not directly paired method-v-method.','failure_review':'ComparisonPool makes joint stability false for incomplete/noncomparable outputs. Continuous metrics use both arms complete-score chains; request explicit four-k/two-arm assertions and actual filtered denominators.','registration_review':'Registration/DESIGN hashes match receipts and deterministic independent selection recreates triples without reading any fusion output. Self-written pre-run receipt alone cannot independently establish timing; parent live execution provenance is required.','interpretation_limits':['history same-difficulty is a pair relation, not a validated global class','selected b/c matches are conditional on submitted point count, not precollection assignment','neither a versus b/c Q nor all-three point counts are constrained; the two contrasted replacements share a, so b/c matching balances changes','bootstrap conditions on selected design and trained profiles; no causal intervention or independent new-data validation'],'issues_reported_to_author':['Assert exactly four k levels and both contrast arms before reducing chains','Continuous summary images/experiments should reflect filtered gm and separately report exclusions'],'status':'design_pass_with_reporting_safeguards_pending'}
(O/'CURVE_DESIGN_REVIEW.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
