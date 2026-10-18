from pathlib import Path
import sys,json,gzip,hashlib,itertools,datetime,argparse
import numpy as np,pandas as pd
BASE=Path('/workspace/shared/personnel_v2_audit_20261018')
SRC=BASE/'extracted/work_v2_20261019'; OUT=Path(__file__).parent
sys.path.insert(0,str(SRC/'fusion'))
import pool_io

def h(x):return hashlib.sha256(str(x).encode()).hexdigest()
def save(p,x):pool_io.save(OUT/p,x)
def read(p):return pool_io.read(OUT/p)
def register():
 reg=dict(name='prospective_nested_pair_swap_exploration_v1',created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_commit=pool_io.COMMIT,
 retrospective_exploratory=True,no_new_blind_test=True,k=[8,12,16,24],pool_selection='ordinary_manual, aligned frozen difficulty, n>=26; first sha256(pool_id+seed) per building*difficulty',seed='20261018-curves-v1',backgrounds_per_pool=2,background='uniform seeded permutation, first23 background; rest are candidates; nested first k-1',
 matching='same outgoing a; b/c equal point counts; all three training Q supported; abs(Qb-Qc)<=3; unknown QT/QTD excluded',
 methods=['history_same_difficulty','QT','QTD'],history='training buildings only; canonical unordered pair; shrinkage5 toward building-equal difficulty prior; >=6 shared tasks and>=3 buildings; p(a,b)-p(a,c)>=0.2',
 QT='QT_B8L2',QTD='fine_dtype_B8L2',selection='one uniformly sampled feasible ordered (a,b,c) per method/context; no target cluster/Q/output used',
 outcomes='same a/b/c for all k; complete four-k chain; primary all joint_stable_main; failures false; continuous max abs Q conditional all score-comparable; also strict/wide original tolerances',
 inference='image average then building equal; paired within triple; bootstrap buildings 10000 draws fixed seed; descriptive conditional design',
 stopping='all preregistered teams run once; all exceptions retained; no outcome-based design revision',
 immutable_inputs={str(p.relative_to(SRC)):pool_io.sha(p) for p in [SRC/'fusion/INPUT_SNAPSHOT.json.gz',SRC/'profiles/fold_profiles.csv',SRC/'clusters/pair_distances.csv.gz']})
 save('REGISTRATION.json',reg)
 pairs=pd.read_csv(SRC/'clusters/pair_distances.csv.gz');pairs=pairs[pairs.layer.eq('ordinary_manual')].copy();pairs['pair']=['|'.join(sorted((a,b))) for a,b in zip(pairs.worker_id_a,pairs.worker_id_b)]
 fold=pd.read_csv(SRC/'profiles/fold_profiles.csv')
 pools=pool_io.load_pools();eligible=[p for p in pools if p['meta']['layer']=='ordinary_manual' and p['meta']['difficulty_aligned'] and len(p['records'])>=26]
 chosen={}
 for p in sorted(eligible,key=lambda p:h(p['pool_id']+reg['seed'])):chosen.setdefault((p['meta']['building'],p['meta']['difficulty']),p)
 requests=[];experiments=[];coverage=[];trcache={}
 for (building,diff),pool in sorted(chosen.items()):
  if building not in trcache:
   train=pairs[pairs.building_id.ne(building)]
   assert not train.building_id.eq(building).any()
   prior=train.groupby(['pool_id','building_id','difficulty']).same_affinity_9.mean().reset_index().groupby(['building_id','difficulty']).same_affinity_9.mean().reset_index().groupby('difficulty').same_affinity_9.mean().to_dict()
   stats=train.groupby(['pair','difficulty']).agg(s=('same_affinity_9','sum'),n=('pool_id','nunique'),buildings=('building_id','nunique'))
   trcache[building]=(prior,stats)
  prior,stats=trcache[building]; fp=fold[fold.heldout_building.eq(building)].set_index('worker_id').to_dict('index'); records={r['worker_id']:r for r in pool['records']}
  def hist(a,b):
   key=('|'.join(sorted((a,b))),diff)
   if key not in stats.index:return None
   st=stats.loc[key]
   if st.n<6 or st.buildings<3:return None
   return float((st.s+5*prior[diff])/(st.n+5))
  for context in range(2):
   rng=np.random.default_rng(int(h(pool['pool_id']+str(context)+reg['seed'])[:16],16)); order=rng.permutation(sorted(records)).tolist();background=order[:23];candidates=order[23:]
   good=[]
   for a,b,c in itertools.permutations(candidates,3):
    if any(w not in fp or not fp[w]['Q_supported'] or not np.isfinite(fp[w]['Q_effect_B8L2']) for w in (a,b,c)):continue
    if len(records[b]['points'])!=len(records[c]['points']):continue
    if abs(fp[b]['Q_effect_B8L2']-fp[c]['Q_effect_B8L2'])>3:continue
    good.append((a,b,c))
   for method in reg['methods']:
    feasible=[]
    for a,b,c in good:
     if method=='history_same_difficulty':
      pb,pc=hist(a,b),hist(a,c)
      if pb is None or pc is None or pb-pc<.2:continue
     else:
      key='QT_B8L2' if method=='QT' else 'fine_dtype_B8L2';labs=[str(fp[w][key]) for w in (a,b,c)]
      if any('unknown' in x.lower() or x=='nan' for x in labs) or not(labs[0]==labs[1] and labs[0]!=labs[2]):continue
     feasible.append((a,b,c))
    coverage.append(dict(pool_id=pool['pool_id'],building=building,difficulty=diff,context=context,method=method,pool_n=len(records),candidate_n=len(candidates),matched_triples=len(good),feasible_triples=len(feasible)))
    if not feasible:continue
    rr=np.random.default_rng(int(h(pool['pool_id']+str(context)+method+reg['seed'])[:16],16));a,b,c=feasible[int(rr.integers(len(feasible)))];eid=h([pool['pool_id'],context,method,a,b,c])[:16]
    exp=dict(experiment_id=eid,pool_id=pool['pool_id'],building=building,difficulty=diff,context=context,method=method,a=a,b=b,c=c,background=background,p_ab=hist(a,b),p_ac=hist(a,c),q_a=fp[a]['Q_effect_B8L2'],q_b=fp[b]['Q_effect_B8L2'],q_c=fp[c]['Q_effect_B8L2'],requests={})
    for k in reg['k']:
     exp['requests'][str(k)]={}
     for arm,w in [('a',a),('b',b),('c',c)]:
      rid='curve_'+eid+'_'+str(k)+'_'+arm;ws=background[:k-1]+[w]
      requests.append(dict(request_id=rid,pool_id=pool['pool_id'],k=k,worker_ids=ws,experiment_id=eid,arm=arm,method=method,context=context));exp['requests'][str(k)][arm]=rid
    experiments.append(exp)
 payload=dict(requests=requests,experiments=experiments,selected_pool_ids=[p['pool_id'] for p in chosen.values()])
 save('DESIGN.json',payload);pd.DataFrame(coverage).to_csv(OUT/'coverage_design.csv',index=False)
 save('DESIGN_RECEIPT.json',dict(registration_sha=pool_io.sha(OUT/'REGISTRATION.json'),design_sha=pool_io.sha(OUT/'DESIGN.json'),eligible_pools=len(eligible),selected_pools=len(chosen),experiments=len(experiments),requests=len(requests),methods=pd.Series([e['method'] for e in experiments]).value_counts().to_dict(),all_output_computation_not_started=True))
 print(read('DESIGN_RECEIPT.json'))

def run():
 import fusion_engine as fe
 design=read('DESIGN.json');pools={p['pool_id']:p for p in pool_io.read(SRC/'fusion/INPUT_SNAPSHOT.json.gz')['images']}
 fe.OUT=OUT;pool_io.OUT=OUT
 receipts=[]
 for pid,g in itertools.groupby(sorted(design['requests'],key=lambda r:r['pool_id']),key=lambda r:r['pool_id']):
  rec=fe.run_pool(pools[pid],list(g));receipts.append(rec);save('RUN_RECEIPTS.json',receipts);print(pid,rec['new_fusions'],rec['total_seconds'],flush=True)
 summarize()

def summarize():
 import compare_fusions as cf
 design=read('DESIGN.json');pools={p['pool_id']:p for p in pool_io.read(SRC/'fusion/INPUT_SNAPSHOT.json.gz')['images']};cf.OUT=OUT
 rows=[]
 for pid,exps in itertools.groupby(sorted(design['experiments'],key=lambda x:x['pool_id']),key=lambda x:x['pool_id']):
  cp=cf.ComparisonPool(pools[pid])
  for exp in exps:
   for k,rs in exp['requests'].items():
    for arm in ('b','c'):
     z=cp.pair(rs['a'],rs[arm]);z.update(experiment_id=exp['experiment_id'],method=exp['method'],arm='same_or_near' if arm=='b' else 'cross_or_far',context=exp['context']);rows.append(z)
 pd.DataFrame(rows).to_csv(OUT/'comparisons.csv.gz',index=False)
 curves=[]
 for (eid,arm),g in pd.DataFrame(rows).groupby(['experiment_id','arm']):
  assert len(g)==4 and set(g.k)=={8,12,16,24}, 'incomplete_four_k_chain'
  x=g.iloc[0];allq=g.quality_comparable.all();curves.append(dict(experiment_id=eid,arm=arm,method=x.method,building=x.building,pool_id=x.pool_id,difficulty=x.difficulty,all_complete=g.both_complete.all(),all_q=allq,curve_stable=g.joint_stable_main.all(),curve_strict=g.joint_stable_strict.all(),curve_wide=g.joint_stable_wide.all(),max_abs_Q=g.B8L2_change.abs().max() if allq else np.nan,mean_abs_Q=g.B8L2_change.abs().mean() if allq else np.nan,mean_signed_Q=g.B8L2_change.mean() if allq else np.nan))
 cv=pd.DataFrame(curves);assert len(rows)==len(design['experiments'])*8 and len(cv)==len(design['experiments'])*2;assert cv.groupby('experiment_id').arm.nunique().eq(2).all();cv.to_csv(OUT/'curves.csv',index=False);summary=[]
 for method,g in cv.groupby('method'):
  for metric in ['curve_stable','curve_strict','curve_wide','all_complete','max_abs_Q','mean_abs_Q']:
   gm=g
   if metric in ['max_abs_Q','mean_abs_Q']:
    jointly=g.groupby('experiment_id').all_q.all();gm=g[g.experiment_id.isin(jointly[jointly].index)]
   im=gm.groupby(['building','pool_id','arm'])[metric].mean().unstack('arm');b=im.groupby('building').mean();delta=(b['cross_or_far']-b['same_or_near']).dropna();rng=np.random.default_rng(20261018);boots=rng.choice(delta.to_numpy(),size=(10000,len(delta)),replace=True).mean(axis=1) if len(delta) else np.array([np.nan]);summary.append(dict(method=method,metric=metric,buildings=len(delta),images=gm.pool_id.nunique(),experiments=gm.experiment_id.nunique(),attempted_experiments=g.experiment_id.nunique(),excluded_experiments=g.experiment_id.nunique()-gm.experiment_id.nunique(),same_or_near=b['same_or_near'].mean(),cross_or_far=b['cross_or_far'].mean(),cross_minus_same=delta.mean(),low=np.nanquantile(boots,.025),high=np.nanquantile(boots,.975)))
 pd.DataFrame(summary).to_csv(OUT/'SUMMARY.csv',index=False);print(pd.DataFrame(summary).to_string(index=False))
if __name__=='__main__':
 arg=argparse.ArgumentParser();arg.add_argument('stage',choices=['register','run','summarize']);a=arg.parse_args();globals()[a.stage]()
