"""Evaluate frozen new classes on separate cached discovery m=1 experiments.
No label fitting. Same fixed background, n and source for all comparisons.
"""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,time,hashlib
from pathlib import Path
import numpy as np,pandas as pd
BASE=Path(__file__).resolve().parent;ROOT=Path(os.environ.get('INTERCHANGEABILITY_WORK_ROOT',BASE.parent))
sys.path.insert(0,str(ROOT/'audit_learning'))
import learn_corner_types as learner
EXTRA=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pairscale','top_max_pairscale','bev_max_local_radius_fraction']
EXTRA += ['count_not_verified_equal','missing_geometry']
learner.METRICS += [x for x in EXTRA if x not in learner.METRICS]

OUT=BASE/'discovery_evaluation';OUT.mkdir(exist_ok=True)
def summarize(rows,keys):
 f=pd.DataFrame(rows);cols=[c for c in f if c.startswith(('within_','between_','distance','candidate_','baseline_','delta_')) and c not in keys]
 return f.groupby(keys,dropna=False)[cols].mean().reset_index() if len(f) else f

def run():
 t=time.perf_counter();labelpath=ROOT/'audit_learning/corner_fit_legacy/worker_labels.csv'
 labels=pd.read_csv(labelpath);assert labels.method_id.nunique()==6
 chunks=sorted((BASE/'discovery_endpoints').glob('*.csv.gz'))
 f=learner.prepare(pd.concat([pd.read_csv(p) for p in chunks],ignore_index=True))
 f['different_count']=f.status.eq('different_corner_count').astype(float)
 f['count_not_verified_equal']=(~f.same_count).astype(float)
 f['missing_geometry']=f.status.eq('missing_connected_geometry').astype(float)
 split=json.loads((ROOT/'unpacked/analysis/composition/SPLIT.json').read_text());assert set(f.building)==set(split['discovery_buildings']);assert f.event_id.is_unique
 manifest={};rows=[];pairs=[];profiles=[];ledger=[]
 feat=pd.read_csv(ROOT/'unpacked/interchangeability_20261020/forward/features_train.csv.gz').set_index('worker_id')
 r=pd.read_csv(ROOT/'unpacked/interchangeability_20261020/reverse/mixed_fit/worker_labels.csv.gz');r=r[r.method_id.eq('R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1')&r.known].set_index('worker_id').class_id
 for mid,g in labels.groupby('method_id'):
  g=g[g.known].sort_values('worker_id')
  if not len(g):
   ledger.append(dict(method_id=mid,baseline='all',common_anchors=0,reason='No known labels; failed or unsupported fit'));continue
  workers=g.worker_id.tolist();lab=pd.factorize(g.class_id,sort=True)[0];counts=np.bincount(lab);fast=learner.Anchors(f,workers)
  base={'method_id':mid,'workers':len(workers),'classes':len(counts),'class_sizes':counts.tolist(),'paired_events_in_support':len(f[f.worker_a.isin(workers)&f.worker_b.isin(workers)]),'possible_anchors':fast.nbg,'common_anchors':int(fast.common(lab).sum())}
  manifest[mid]=base
  rows.extend(dict(method_id=mid,kind='candidate',**v) for v in fast.evaluate(lab))
  controls={}
  ledger.append(dict(method_id=mid,baseline='source_only',common_anchors=0,reason='All entrants are new-source; a source-only label has no between-class arm'))
  for name,col in [('Q','q_beta'),('T','t_source_origin_effect')]:
   assert np.isfinite(feat.loc[workers,col]).all(), 'missing control feature '+col
   assert feat.loc[workers,'core_supported' if name=='Q' else 't_supported'].all(), 'unsupported control feature '+col
   rank=feat.loc[workers,[col]].reset_index().sort_values([col,'worker_id']).worker_id.tolist();c={w:i for i,ws in enumerate(np.split(np.asarray(rank),np.cumsum(counts)[:-1])) for w in ws};controls[name+'_same_capacity']=np.array([c[w] for w in workers])
  if all(w in r.index for w in workers):controls['Rnew2']=pd.factorize(r.loc[workers],sort=True)[0]
  rng=np.random.default_rng(2026102012)
  controls.update({f'random_{draw:02d}':rng.permutation(lab) for draw in range(40)})
  for name,cl in controls.items():
   common=int((fast.common(lab)&fast.common(cl)).sum());ledger.append(dict(method_id=mid,baseline=name,common_anchors=common))
   pairs.extend(dict(method_id=mid,baseline=name,**v) for v in fast.paired(lab,cl))
  lookup=dict(zip(workers,g.class_id));ff=f[f.worker_a.isin(workers)&f.worker_b.isin(workers)].copy();ff['class_a']=ff.worker_a.map(lookup);ff['class_b']=ff.worker_b.map(lookup)
  for cls,cf in ff[ff.class_a.eq(ff.class_b)].groupby('class_a'):
   valid=cf[cf.distance.notna()];pr=dict(method_id=mid,class_id=cls,members='|'.join(g[g.class_id.eq(cls)].worker_id),attempted_pairs=len(cf),valid_pairs=len(valid),images=cf.pool_id.nunique(),buildings=cf.building.nunique(),anchors=cf.groupby(['pool_id','k','background_id']).ngroups,unique_worker_pairs=cf.groupby(['worker_a','worker_b']).ngroups)
   for metric in ['distance','different_count','incomplete','distance_valid']+EXTRA:
    bb=cf.groupby(['building','pool_id','k','background_id'])[metric].mean().groupby(['building','pool_id','k']).mean().groupby(['building','pool_id']).mean().groupby('building').mean();pr[metric+'_building_equal_mean']=bb.mean();pr[metric+'_event_p90']=cf[metric].quantile(.9)
   profiles.append(pr)
  print(mid,fast.nbg,base['common_anchors'],flush=True)
 pd.DataFrame(rows).to_csv(OUT/'DISCOVERY_BUILDINGS.csv',index=False);summarize(rows,['method_id','kind']).to_csv(OUT/'DISCOVERY_SUMMARY.csv',index=False)
 pd.DataFrame(pairs).to_csv(OUT/'PAIRED_BASELINE_BUILDINGS.csv.gz',index=False);summarize(pairs,['method_id','baseline']).to_csv(OUT/'PAIRED_BASELINE_SUMMARY.csv',index=False)
 pd.DataFrame(profiles).to_csv(OUT/'CLASS_APPLICABILITY.csv',index=False);pd.DataFrame(ledger).to_csv(OUT/'BASELINE_SUPPORT.csv',index=False)
 learner.write(OUT/'METHOD_SUPPORT.json',manifest);learner.write(OUT/'RUN_RECEIPT.json',dict(events=len(f),images=f.pool_id.nunique(),buildings=sorted(f.building.unique()),extraction_chunks=len(chunks),labels_sha256=hashlib.sha256(labelpath.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),elapsed_seconds=time.perf_counter()-t,scope='new-source m1 exact background legacy endpoints; no fusion, no fitting, no assertion of block generalization'))
if __name__=='__main__':run()
