import pathlib,json,hashlib,zipfile
import numpy as np,pandas as pd
P=pathlib.Path('/workspace/shared/personnel_partA_audit_20261019');R=P/'extracted/work_personnel_typing_A_20261019';O=P/'independent'
r={}
# exact archive and frozen payload
r['zips']=[]
for f in (P/'originals').glob('*.zip'):
 with zipfile.ZipFile(f) as z: bad=z.testzip();n=len(z.infolist())
 r['zips'].append(dict(name=f.name,bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),entries=n,crc_bad=bad))
for name,base in [('SOURCE_FILES.json',R/'recovered/repo_main_20261019'),('PORTABLE_MANIFEST.json',R/'recovered')]:
 m=json.loads((R/'reproducibility/pro_archive_manifests'/name).read_text());errs=[]
 for x in m:
  f=base/x['path'];h=hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
  if h!=x['sha256']:errs.append(x['path'])
 r[name]={'checked':len(m),'errors':errs}
print('hashes done',flush=True)
e=pd.read_csv(R/'assessment/COMMON_EVENT_ANALYSIS_INPUT.csv.gz');w=pd.read_csv(R/'assessment/EVENT_PREDICTIONS_WIDE.csv.gz');assert e.event_id.is_unique and w.event_id.is_unique and e.event_id.equals(w.event_id)
# Verify analysis label really derived from raw geometrical component flags.
y=e.both_complete & e.abs_B8L2_change.le(2)&e.floor_jaccard_difference.le(.05)&e.node_count_difference.eq(0)&e.structure_bound_cyclic_deg.le(3)
r['event_integrity']={'rows':len(e),'stable_rederived_mismatch':int((y!=e.stable_main).sum()),'panels':e.panel_id.value_counts().to_dict(),'incomplete_event_rows':int((~e.both_complete).sum())}
def summ(g,col):
 if not len(g):return dict(n=0,images=0,buildings=0,event_mean=None,image_mean=None,building_mean=None,ci=[None,None])
 im=g.groupby(['building','image_id'])[col].mean();a=im.groupby(level=0).mean().to_numpy();boot=np.random.default_rng(20261019).choice(a,(2000,len(a))).mean(1)
 return dict(n=len(g),images=g.image_id.nunique(),buildings=len(a),event_mean=float(g[col].mean()),image_mean=float(im.mean()),building_mean=float(a.mean()),ci=np.quantile(boot,[.025,.975]).tolist())
r['brier']=[];r['matched_stability']=[]
for method in ['forward_selected','reverse_selected','reverse_selected_swap']:
 for ref in ['old_QT','Q3','baseline_k_difficulty']:
  common=w['rel__'+method].ne('unknown')
  if ref!='baseline_k_difficulty':common &= w['rel__'+ref].ne('unknown')
  f=e.copy();f['difference']=(w['p__'+ref]-y)**2-(w['p__'+method]-y)**2
  for st,mask in [('all',np.ones(len(e),bool)),('common',common),('Q_near',common&e.q_near)]:
   g=f[mask&e.panel_id.eq('A_nested_even_v1')&e.k.eq(16)]
   r['brier'].append(dict(method=method,reference=ref,stratum=st,**summ(g,'difference')))
 f=e.copy();f['relation']=w['rel__'+method]
 f=f[f.panel_id.eq('A_nested_even_v1')&f.k.eq(16)&f.relation.ne('unknown')]
 a=f.groupby(['building','image_id','background_id','relation']).stable_main.mean().unstack().dropna(subset=['within','between']).reset_index();a['difference']=a.between-a.within
 r['matched_stability'].append(dict(method=method,**summ(a,'difference')))
print('stats done',flush=True)
# Independently re-estimate leave-building calibrators, no importing Pro functions.
lab=pd.read_csv(R/'assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz').fillna({'heldout_building':'FULL'})
r['calibrator_replay']=[]
for method in ['old_QT','forward_selected','reverse_selected','reverse_selected_swap']:
 maxerr=0.;unknown=0
 for b in sorted(e.building.unique()):
  l=lab[(lab.heldout_building==b)&(lab.method_id==method)]
  glob=l[l.difficulty=='global'].set_index('worker_id').class_id.to_dict();cond={(d,a):c for d,a,c in l[['difficulty','worker_id','class_id']].itertuples(index=False,name=None) if d!='global'}
  aa=[cond.get((d,a),glob.get(a,'unknown')) for d,a in zip(e.difficulty,e.worker_a)];bb=[cond.get((d,a),glob.get(a,'unknown')) for d,a in zip(e.difficulty,e.worker_b)]
  rel=np.where((np.array(aa)=='unknown')|(np.array(bb)=='unknown'),'unknown',np.where(np.array(aa)==np.array(bb),'within','between'))
  tr=e[(e.building!=b)&e.panel_id.eq('Pro_exact_fixed_background_v1')][['building','image_id','difficulty','k','stable_main']].copy();tr['relation']=rel[tr.index]
  def rates(keys,frame):return frame.groupby(keys+['building','image_id']).stable_main.mean().groupby(keys+['building']).mean()
  base=rates(['k','difficulty'],tr).groupby(['k','difficulty']).mean();bk=rates(['k'],tr).groupby('k').mean();bg=rates([],tr).mean()
  rr=rates(['k','difficulty','relation'],tr[tr.relation!='unknown']).groupby(['k','difficulty','relation']).agg(['sum','count'])
  rr['p']=[(v['sum']+2*base.get((k,d),bk.get(k,bg)))/(v['count']+2) for (k,d,z),v in rr.iterrows()]
  te=e[e.building==b];pred=np.array([rr.p.get((k,d,z),base.get((k,d),bk.get(k,bg))) for k,d,z in zip(te.k,te.difficulty,rel[te.index])]);maxerr=max(maxerr,float(np.max(abs(pred-w.loc[te.index,'p__'+method]))));unknown+=int((rel[te.index]=='unknown').sum())
 r['calibrator_replay'].append(dict(method=method,max_abs_probability_difference=maxerr,unknown_events=unknown))
 print('calibrator',method,maxerr,flush=True)
(O/'independent_metrics.json').write_text(json.dumps(r,indent=2));print(json.dumps(r['brier'][:6],indent=2))
