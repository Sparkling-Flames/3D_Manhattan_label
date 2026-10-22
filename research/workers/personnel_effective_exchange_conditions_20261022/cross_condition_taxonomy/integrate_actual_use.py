#!/usr/bin/env python3
"""Integrate completed endpoint evidence without changing frozen classes."""
import hashlib,io,json,os,zipfile
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent
NEW=HERE.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(p,b):
 p=Path(p);tmp=p.with_name(p.name+'.partial')
 with tmp.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def csv(name,d):atomic(HERE/name,d.to_csv(index=False).encode('utf-8-sig'))
def save(name,d):atomic(HERE/name,json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2).encode())

def main():
 before={f:sha(HERE/f) for f in ['CROSS_LABELS_ALL.csv','CROSS_LABELS_LOBO.csv.gz','LABEL_FREEZE.json']}
 sources=[];parts=[]
 for condition in ['manual','semi']:
  p=NEW/'joint_exchange'/('CROSS_'+condition.upper()+'_SAME_SUPPORT_SUMMARY.csv');d=pd.read_csv(p)
  d=d[d.source_domain.eq('new_only')].copy();assert len(d)==6;parts.append(d)
  sources.append(dict(path=str(p.relative_to(NEW)),sha256=sha(p),rows=len(pd.read_csv(p)),included_rows=len(d)))
 result=pd.concat(parts,ignore_index=True);csv('ACTUAL_TEAM_USE_SUMMARY.csv',result)
 raw=pd.read_csv(HERE/'ADOPTION_MATRIX_RAW_STAGE.csv');final=raw.copy();final['stage']='raw_and_actual_exchange_completed';final['actual_experiment']=''
 for i,r in final.iterrows():
  method=r['method'];condition=r['condition']
  if method=='XCOND_GEOM':
   final.loc[i,'team_use']='not included in the three-method common-anchor endpoint comparison; raw usefulness retained without claiming fusion replacement'
   final.loc[i,'actual_experiment']='not evaluated in this subexperiment'
   continue
  d=result[result.method_id.eq(method)&result.condition.eq(condition)&result.scope.eq('all_methods_scored_time_same_anchors')].iloc[0]
  allrow=result[result.method_id.eq(method)&result.condition.eq(condition)&result.scope.eq('all_registered_anchors')].iloc[0]
  final.loc[i,'actual_experiment']=f"new_only; same A,D,n,m4; class seats r2; {int(d.anchors)} common scored/time anchors/{int(d.images)} images/{int(d.buildings)} buildings"
  final.loc[i,'team_use']=f"C-B Q={d.net_B8L2:.6f}; C/B recorded time={d.net_recorded_time_geomean_pct:.6f}%; C-A Q={d.cross_B8L2:.6f}; full {int(allrow.anchors)} anchors C-B failure={100*allrow.net_failure_difference:.6f} percentage points"
  if method=='XCOND_GEOM_QT':
   final.loc[i,'adoption']='retain readable cross-condition descriptions; not a general replacement policy for own-condition joint classes'
   final.loc[i,'recommended_use']='readable two-condition Q/T/geometry combinations; preserve actual time and failure tradeoffs'
  elif condition=='manual':
   final.loc[i,'adoption']='conditional net replacement/efficiency taxonomy; not raw-shape equivalence or universal original-team improvement'
   final.loc[i,'recommended_use']='when replacing in supported candidate subspaces, smaller Q loss and less recorded time than same-composition alternative'
  else:
   final.loc[i,'adoption']='explicit quality-time tradeoff; not recommended as overall replacement or raw-shape class'
   final.loc[i,'recommended_use']='describe conditional recorded-time savings accompanied by lower Q than same-composition replacement'
 csv('ADOPTION_MATRIX_FINAL.csv',final)
 receipt=dict(sources=sources,method='read completed common-anchor summaries; no event re-evaluation, fitting, fusion, or score calls',
  unchanged_label_hashes=before,source_domain='new_only; all-formal domain remains separately reported in joint_exchange',
  exact_common_rule='same A, background D, n, actual m=4, changed class seats r=2; same history-center q-10t rule',
  failure_denominator='all_registered_anchors retained separately from all-methods score/time intersection')
 save('ACTUAL_TEAM_USE_SOURCE_RECEIPT.json',receipt)
 assert before=={f:sha(HERE/f) for f in before}
 # Compact reproducible package, without caches, repeated repository inputs,
 # original image sets, or intermediate checkpoints.
 paths=[]
 for p in sorted(HERE.rglob('*')):
  rel=p.relative_to(HERE)
  if not p.is_file() or any(x in ['__pycache__','checkpoints'] for x in rel.parts):continue
  if p.suffix in ['.zip','.log'] or p.name.endswith('.partial') or '_CHECKPOINT' in p.name or p.name in ['PACKAGE_MANIFEST.csv','DELIVERY_RECEIPT.json']:continue
  paths.append(p)
 csv('PACKAGE_MANIFEST.csv',pd.DataFrame([dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in paths]));paths.append(HERE/'PACKAGE_MANIFEST.csv')
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in paths:z.writestr('cross_condition_taxonomy/'+str(p.relative_to(HERE)),p.read_bytes())
 dest=HERE/'CROSS_TAXONOMY_PACKAGE_20261022.zip';atomic(dest,buf.getvalue())
 with zipfile.ZipFile(dest) as z:assert z.testzip() is None and len(z.namelist())==len(paths)
 receipt=dict(path=dest.name,bytes=dest.stat().st_size,sha256=sha(dest),files=len(paths),report_stage='raw_and_actual_exchange_final',
  labels_unchanged=True,old_method_registry_preserved=True,actual_use_summary_rows=len(result),original_photos_not_duplicated=True)
 save('DELIVERY_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
