"""Independent saved-data checks and bounded native reruns; never overwrites experiments."""
import os,sys,json,gzip,hashlib
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from shapely.geometry import Polygon,shape
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from tools.thesis_main.analysis.personnel_supplement_taxonomy_replay_20261024 import behavior,joint,SOURCE
from tools.thesis_main.analysis.research_round_20260929 import reconstruct
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus
D=ROOT/'research/workers/personnel_d10_formation_sensitivity_20261024'
F=ROOT/'research/fusion/fusion_common_panel_20261024'
C=ROOT/'research/workers/personnel_mixture_comparison_20261022/configurations'
metrics=['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter']
report={}
def csv(p):return pd.read_csv(p)
def gz(p):
 with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
def equal(a,b):np.testing.assert_allclose(np.asarray(a,float),np.asarray(b,float),rtol=1e-8,atol=1e-8,equal_nan=True)
def seed(s):return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8],'big')
def names(s):return set(s.split('|'))
def score(z,scale):
 I=z['iou_2d'];Sb=z['S_bottom_deg'];di=z['dir'];Hm=z['Hmean'];Hc=z['Hcenter']
 return 100*I/(I+np.hypot(1-I+I*Sb**2/32,I*1.5*di**2/(di**2+scale**2))+I*((Hm/.8)**2+(Hc/.25)**2))
raw=behavior.load();q=csv(D/'QUALIFIED_RECORD_SCORE_INPUTS.csv.gz');assert len(q)==7302
rawq=raw.set_index('object_id').loc[q.object_id];equal(q.B8L2,rawq.B8L2);equal(q.D10,rawq.D10)
assert raw.B8L2.notna().equals(raw.D10.notna())
report['d10_input']={'qualified':len(q),'mean_lift':float((q.D10-q.B8L2).mean()),'median_lift':float((q.D10-q.B8L2).median())}
old=pd.concat([csv(SOURCE/'JOINT_LABELS_ALL_DATA.csv'),csv(SOURCE/'JOINT_LABELS_LOBO.csv.gz')])
new=csv(D/'D10_LABELS_FIXED_AND_RESELECTED.csv.gz');cmp=csv(D/'PARTITION_COMPARISON.csv')
for r in cmp.itertuples():
 a=old[(old.condition==r.condition)&(old.heldout_building==r.heldout_building)].set_index('worker_id')
 b=new[(new.condition==r.condition)&(new.heldout_building==r.heldout_building)&(new.formation_arm==r.formation_arm)].set_index('worker_id')
 field=r.tier+'_label';z=a[[field]].join(b[[field]],lsuffix='_a',rsuffix='_b');z=z[(z[field+'_a']!='unknown')&(z[field+'_b']!='unknown')]
 assert len(z)==r.workers;equal(adjusted_rand_score(z[field+'_a'],z[field+'_b']),r.ARI)
raw['B8L2_peer_delta']=raw.D10_peer_delta;study=joint.Joint(raw)
choices=json.loads((D/'D10_RESELECTED_CHOICES.json').read_text(encoding='utf-8'))
olds={(x['condition'],x['heldout_building']):x for x in json.loads((SOURCE/'JOINT_SELECTED_MODELS.json').read_text(encoding='utf-8'))}
inner=csv(D/'D10_INNER_BUILDING_LOSSES.csv.gz');refits=0;recomputed_inner=0
for ch in choices:
 c,b=ch['condition'],ch['heldout_building'];exc=() if b=='ALL' else (b,)
 # Independent aggregation of worker Q/T features from explicitly excluded raw rows.
 train=study.fit_by[c];train=train[~train.building_id.isin(exc)]
 features=study.features(c,exc).set_index('worker_id')
 for column,dest in [('D10_peer_delta','q_history'),('log_time_peer_delta','t_history')]:
  expected=train.groupby(['worker_id','building_id'])[column].mean().groupby('worker_id').mean()
  equal(features[dest],expected.reindex(features.index))
 for arm,choice in [('fixed_old_model',olds[c,b]),('reselected',ch)]:
  a=study.labels(choice).set_index('worker_id').sort_index();z=new[(new.condition==c)&(new.heldout_building==b)&(new.formation_arm==arm)].set_index('worker_id').sort_index()
  for fld in ['coarse_label','fine_label','known']:assert a[fld].equals(z[fld]),(c,b,arm,fld)
  for fld in ['q_history','q_downside','t_history']:equal(a[fld],z[fld])
  refits+=1
 if b=='7y3sRwLe3Va':
  rows=pd.DataFrame(study.inner(c,b));saved=inner[(inner.condition==c)&(inner.heldout_building==b)]
  keys=['target_building','family','k'];aa=rows.set_index(keys).sort_index();bb=saved.set_index(keys).sort_index();assert aa.index.equals(bb.index)
  for fld in ['loss','workers','records','images','min_class']:equal(aa[fld],bb[fld])
  chosen,_=study.choose(c,b,rows.to_dict('records'));assert all(chosen[k]==ch[k] for k in ['family','fine_k','coarse_k'])
  recomputed_inner+=len(rows)
 study.fitted.cache_clear();study.features.cache_clear()
ledger=csv(D/'TRAINING_EXCLUSION_LEDGER.csv')
for r in ledger.itertuples():
 train=study.fit_by[r.condition];excluded=set() if pd.isna(r.excluded_buildings) else names(r.excluded_buildings)
 actual=train[~train.building_id.isin(excluded)];assert len(actual)==r.training_records
 assert not (set(actual.building_id)&excluded)
report['d10_fit']={'partition_rows':len(cmp),'label_refits':refits,'inner_losses_recomputed_two_outer_folds':recomputed_inner,'exclusion_rows':len(ledger)}
print('D10 formation passed',report['d10_fit'],flush=True)
endpoint=pd.concat([csv(C/f'ENDPOINT_OUTCOMES_{c}.csv.gz') for c in ['manual','semi']]).set_index('team_key',verify_integrity=True)
panels=csv(C/'PANELS_USED.csv').set_index('panel_id');teams=csv(C/'PANEL_TEAMS.csv.gz')
labels=pd.concat([old[old.heldout_building!='ALL'].assign(formation_arm='B8L2_original'),new[new.heldout_building!='ALL'].assign(formation_arm=lambda x:'D10_'+x.formation_arm)])
rosters={k:g.set_index('worker_id') for k,g in labels.groupby(['condition','heldout_building','formation_arm'])}
selected=csv(D/'SELECTED_TEAMS.csv.gz')
for r in selected.itertuples():
 p=panels.loc[r.panel_id];roster=rosters[p.condition,p.building,r.formation_arm];candidate=p.variable_workers.split('|')
 rank={w:i for i,w in enumerate(np.random.default_rng(seed(r.panel_id)).permutation(candidate))}
 lab=roster[r.tier+'_label'];high=roster[roster.known].groupby(r.tier+'_label').q_history.mean().idxmax()
 qh=roster.q_history;th=roster.t_history
 if r.policy=='class_highq':order=sorted(candidate,key=lambda w:(lab[w]!=high,rank[w]))
 elif r.policy=='continuous_q':order=sorted(candidate,key=lambda w:(-qh[w],rank[w]))
 else:
  v=(qh-qh.median())/(qh.quantile(.75)-qh.quantile(.25))-(th-th.median())/(th.quantile(.75)-th.quantile(.25))
  order=sorted(candidate,key=lambda w:(-v[w],rank[w]))
 assert set(order[:6])==names(r.selected_workers)
 for m in metrics:equal(getattr(r,m),endpoint.loc[r.team_key,m])
paired=csv(D/'SELECTED_TEAM_CROSS_EVALUATION.csv.gz')
for side in ['B8','D10']:
 actual=endpoint.loc[paired['team_key_'+side]]
 for m in metrics:equal(paired[m+'_'+side],actual[m])
for m in metrics:equal(paired[m+'_delta'],(paired[m+'_D10']-paired[m+'_B8']).where(paired.all_score_metrics_common))
report['d10_selection']={'selected_rows_rederived':len(selected),'paired_rows':len(paired),'highq':[]}
for (cond,tier),g in paired[(paired.policy=='class_highq')&(paired.compared_arm=='D10_reselected')].groupby(['condition_B8','tier']):
 report['d10_selection']['highq'].append(dict(condition=cond,tier=tier,panels=len(g),changed=int(g.replacements.gt(0).sum()),scored=int(g.D10_delta.notna().sum()),D10_delta=float(g.D10_delta.mean()),failure_net=int(g.failure_delta.sum())))
abc=csv(D/'ABC_EVENTS.csv.gz')
for side in 'ABC':
 z=endpoint.loc[abc['team_'+side]];assert np.array_equal(abc[side+'_failure'].to_numpy(),z.failure.to_numpy())
assert abc.A_class_counts.eq(abc.B_class_counts).all() and abc.A_class_counts.ne(abc.C_class_counts).all()
for m in metrics:
 a,b,c=[endpoint.loc[abc['team_'+s],m].to_numpy() for s in 'ABC'];within=np.abs(b-a);cross=(np.abs(c-a)+np.abs(c-b))/2
 for suffix,v in [('within_abs',within),('cross_abs',cross),('extra_abs',cross-within),('net_C_minus_B',c-b)]:equal(abc[m+'_'+suffix],np.where(abc.all_scored,v,np.nan))
for r in abc.itertuples():
 a,b,c=[names(getattr(r,s+'_selected_workers')) for s in 'ABC'];assert len(a)==len(b)==len(c)==6 and len(a&b)==len(a&c)==len(b&c)==6-r.m
common=csv(D/'ABC_COMMON_PHYSICAL_TRIPLES.csv.gz')
for r in common.itertuples():assert {getattr(r,'team_'+s+'_B8') for s in 'ABC'}=={getattr(r,'team_'+s+'_D10') for s in 'ABC'}
for m in ['B8L2','D10']:equal(common[m+'_extra_change'],common[m+'_extra_abs_D10']-common[m+'_extra_abs_B8']);equal(common.loc[common.same_orientation,m+'_extra_change'].dropna(),0)
report['d10_abc']={'events':len(abc),'common_triples':len(common),'same_orientation':int(common.same_orientation.sum())}
print('D10 selection and ABC passed',report['d10_selection'],report['d10_abc'],flush=True)
# Fusion: independently select medoid, rebuild Lee, remeasure every evaluable complete geometry.
pop=ROOT/'research/workers/personnel_population_curves_v2_20261023'
snapshot={p['pool_id']:p for p in gz(pop/'inputs/INPUT_SNAPSHOT.json.gz')['images']}
requests={r['request_id']:r for r in gz(pop/'inputs/REQUESTS_INITIAL.json.gz')['requests']}
reg=csv(F/'TEAM_REGISTRATION.csv');out=csv(F/'METHOD_ENDPOINTS.csv');geom={(x['team_key'],x['method']):x for x in json.loads((F/'METHOD_GEOMETRY.json').read_text(encoding='utf-8'))}
assert len(reg)==138 and len(out)==414
measured=0;lee_rebuilt=0;medoid_reselected=0
engroot=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
with scoring_engine(engroot/'measurement_engine.zip',engroot/'working_models.py') as (engine,models):
 for r in reg.itertuples():
  p=snapshot[r.pool_id];req=requests[r.request_id];assert req['draw_id']==0 and req['request_family']=='uniform_prefix' and set(req['worker_ids'])==names(r.member_workers)
  records=[x for x in p['records'] if x['worker_id'] in names(r.member_workers)];assert len(records)==r.n
  assert set(x['object_id'] for x in records)==names(r.member_object_ids) and p['meta']['reference_id']==r.reference_id
  shapes=[Polygon(reconstruct(x,coordinate_convention='continuous')['floor']) for x in records];assert all(s.is_valid and s.area>0 for s in shapes)
  dist=np.zeros((r.n,r.n))
  for i in range(r.n):
   for j in range(i):dist[i,j]=dist[j,i]=1-shapes[i].intersection(shapes[j]).area/shapes[i].union(shapes[j]).area
  idx=min(range(r.n),key=lambda i:(round(float(dist[i].sum()/(r.n-1)),12),records[i]['object_id']))
  g=out[(out.pool_id==r.pool_id)&(out.n==r.n)].set_index('method');assert len(g)==3
  assert g.loc['medoid','source_record_id']==records[idx]['object_id'];medoid_reselected+=1
  lee=tile_consensus([{'id':x['object_id'],'worker':x['worker_id'],'footprint':list(s.exterior.coords)[:-1]} for x,s in zip(records,shapes)])['regions']['mv50']
  savedlee=shape(geom[g.loc['lee_mv50','team_key'],'lee_mv50']['footprint']);assert lee.symmetric_difference(savedlee).area<1e-7;lee_rebuilt+=1
  ref=Polygon(p['reference']['floor_xz_h'])
  for method,z in g.iterrows():
   geometry=geom[z.team_key,method]
   poly=shape(geometry['footprint']) if method=='lee_mv50' else Polygon(geometry['footprint']) if geometry['footprint'] else None
   assert bool(poly is not None and poly.is_valid and poly.area>0)==bool(z.floor_output)
   if poly is not None:equal(poly.intersection(ref).area/poly.union(ref).area,z.iou_2d)
   if method!='lee_mv50' and z.full_evaluable:
    result=engine.measure(engine.geometry(geometry['points']),engine.geometry(p['reference']['points_1024x512']));assert result['status']=='complete'
    vals=result['metrics']
    for m in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']:equal(vals[m],z[m])
    equal(vals['iou_3d_corner_mean']*100,z.IoU3D100)
    equal(score(vals,8),z.B8L2);equal(score(vals,10),z.D10);measured+=1
  if medoid_reselected%30==0:print('fusion checked',medoid_reselected,flush=True)
pairs=csv(F/'COMMON_TEAM_METRICS.csv');idx=out.set_index(['team_key','method'])
for (comp,m),g in pairs.groupby(['comparison','metric']):
 left,right=comp.split('_minus_');a=idx.loc[[(k,left) for k in g.team_key],m];b=idx.loc[[(k,right) for k in g.team_key],m]
 equal(a,g.left_value);equal(b,g.right_value);equal(a.to_numpy()-b.to_numpy(),g.delta)
report['fusion']={'teams':len(reg),'medoids_reselected':medoid_reselected,'lee_native_rebuilt':lee_rebuilt,'complete_geometries_remeasured':measured,'paired_metric_rows':len(pairs),'status':out.groupby('method')[['full_evaluable','floor_output']].sum().astype(int).to_dict('index'),'ordinary_manual':[]}
for n,g in pairs[(pairs.comparison=='wall_auto_minus_medoid')&(pairs.metric=='B8L2')&(pairs.support_domain=='complete_layout')&(pairs.layer=='ordinary_manual')].groupby('n'):
 report['fusion']['ordinary_manual'].append(dict(n=int(n),images=len(g),mean_delta=float(g.delta.mean()),positive=int(g.delta.gt(1e-9).sum()),negative=int(g.delta.lt(-1e-9).sum())))
print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
Path(sys.argv[1]).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
