"""Recompute fixed v2.1 answers against every recorded collinear reference stage."""
import json
from pathlib import Path
from dataclasses import replace
import numpy as np
import pandas as pd
from .quality_validation_followup_20261107 import ROOT, ENGINE
from .scope_quality_scoring_20261016 import scoring_engine

OUT=ROOT/'research/quality/collinear_score_audit_20261107'
BASE=ROOT/'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028/extension_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 OUT.mkdir(exist_ok=True)
 views=read(ROOT/'research/data/scope_redundant_vertices_20261016/scope_views.json')
 affected={v['target_id']:v for v in views if v['precision_removed'] or v['exact_removed']}
 stages={r['target_id']:r for r in read(BASE/'orthogonal_v2_user_axes/REFERENCES.json')}
 assert set(affected)=={r['target_id'] for r in stages.values() if r['raw_nodes']!=r['kept_nodes']},'uncovered compaction target'
 adopted={r['target_id']:r for r in read(BASE/'adopted_references_20261028/ceiling_adopted_20261028/REFERENCE_CATALOG.json')}
 pools=read(ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json')['images']+read(ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/pools/INPUT_SNAPSHOT.json')['images']
 ledger=[];rows=[]
 with scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (engine,models):
  def measure(points,ref):
   v=engine.measure(engine.geometry(points),engine.geometry(ref))
   if v['status']!='complete':return {'status':v['status']}
   m=v['metrics'];z={**m,'status':'complete'}
   for name,par in [('B8L2',models.MODELS['B8L2']),('D10',replace(models.MODELS['B8L2'],direction_scale_deg=10.))]:z[name]=float(models.score(*[m[k] for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']],par))
   return z
  for tid,v in affected.items():
   r=stages[tid];old=r['original_points'];keep=np.array(r['kept_1based'])-1;compact=np.asarray(old).reshape(-1,2,2)[keep].reshape(-1,2).tolist()
   current=adopted[tid]['points_1024x512']
   selected=[p for p in pools if p['reference']['target_id']==tid or p['meta']['reference_id']==tid]
   ledger.append(dict(target_id=tid,image=v['image_code'],raw_nodes=len(old)//2,compact_nodes=len(compact)//2,current_nodes=len(current)//2,exact_removed=len(v['exact_removed']),precision_removed=len(v['precision_removed']),baseline_identity=r['baseline_identity'],pools=len(selected),records=sum(len(p['records']) for p in selected),actual_pool_reference_matches=all(np.shape(p['reference']['points_1024x512'])==np.shape(current) and np.allclose(p['reference']['points_1024x512'],current,rtol=0,atol=1e-10) for p in selected)))
   for p in selected:
    assert ledger[-1]['actual_pool_reference_matches'],p['pool_id']
    for a in p['records']:
     identity=dict(target_id=tid,image=v['image_code'],pool_id=p['pool_id'],object_id=a['id'],condition=p['meta']['condition'],scope=p['meta'].get('analysis_scope','primary'))
     results={name:measure(a['points'],ref) for name,ref in [('before_compaction',old),('compaction_only',compact),('orthogonal',r['points_1024x512']),('current',current)]}
     for name,result in results.items():rows.append({**identity,'stage':name,**result,'stored_B8L2':a.get('B8L2'),'stored_D10':a.get('D10')})
   print(v['image_code'],ledger[-1]['records'],flush=True)
 df=pd.DataFrame(rows);df.to_csv(OUT/'SCORES.csv.gz',index=False);pd.DataFrame(ledger).to_csv(OUT/'REFERENCE_ADOPTION.csv',index=False,encoding='utf-8-sig')
 comparisons=[]
 for keys,g in df.groupby(['target_id','image','pool_id','object_id','condition','scope'],dropna=False):
  g=g.set_index('stage')
  for first,last in [('before_compaction','compaction_only'),('compaction_only','orthogonal'),('orthogonal','current'),('before_compaction','current')]:
   row=dict(zip(['target_id','image','pool_id','object_id','condition','scope'],keys));row['contrast']=first+'->'+last
   for col in ['B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']:row[col+'_delta']=g.loc[last,col]-g.loc[first,col]
   comparisons.append(row)
 diff=pd.DataFrame(comparisons);diff.to_csv(OUT/'PAIRED_DELTAS.csv',index=False,encoding='utf-8-sig')
 summary=diff.groupby(['image','target_id','contrast'],dropna=False).agg(records=('object_id','size'),paired=('B8L2_delta','count'),mean_Q_delta=('B8L2_delta','mean'),max_abs_Q_delta=('B8L2_delta',lambda x:x.abs().max()),over_01=('B8L2_delta',lambda x:(x.abs()>.1).sum())).reset_index();summary.to_csv(OUT/'SUMMARY.csv',index=False,encoding='utf-8-sig')
 current=df[df.stage.eq('current')];err=(current.B8L2-current.stored_B8L2).abs();derr=(current.D10-current.stored_D10).abs()
 checks=dict(targets=len(affected),images=len({v['image_code'] for v in affected.values()}),pools=sum(x['pools'] for x in ledger),records=len(current),all_current_reference_matches=all(x['actual_pool_reference_matches'] for x in ledger),max_stored_Q_error=float(err.max()),max_stored_D10_error=float(derr.max()),missing_stored_Q=int(current.stored_B8L2.isna().sum()),unscoreable_current=int(current.B8L2.isna().sum()),without_pool=[x['target_id'] for x in ledger if not x['pools']])
 assert checks['max_stored_Q_error']<1e-6 and checks['max_stored_D10_error']<1e-6
 (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');print(checks)
 for contrast,g in diff.groupby('contrast'):print(contrast,len(g),g.B8L2_delta.mean(),g.B8L2_delta.abs().max(),int((g.B8L2_delta.abs()>.1).sum()))
if __name__=='__main__':main()
