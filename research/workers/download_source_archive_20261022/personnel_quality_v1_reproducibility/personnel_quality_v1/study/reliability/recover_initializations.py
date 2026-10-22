"""Recover every actual task initialization from import + runtime preview evidence.

This verifies deployed task payloads, not that a person looked at every point.
The normalized current final geometry and raw worker export stay distinct.
"""
import hashlib,json
from pathlib import Path
from functools import lru_cache
from collections import Counter
from urllib.parse import parse_qs,urlparse
import numpy as np,pandas as pd
from paths import ROOT,REPO,OUT,STUDY

def points(result):return [[r['value']['x']*10.24,r['value']['y']*5.12] for r in result if r.get('type')=='keypointlabels']
def same(a,b):
 a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
 return a.shape==b.shape and bool(np.allclose(a,b,atol=1e-6,rtol=0))
def canonical(a):return sorted(tuple(round(float(x),6) for x in p) for p in a)
def sha(p):return hashlib.sha256(json.dumps(p,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
@lru_cache(None)
def tasks(path):return json.loads((REPO/path.replace('\\','/')).read_text(encoding='utf-8-sig'))
def preview(t):
 val=parse_qs(urlparse(t.get('data',{}).get('vis_3d','')).query).get('data')
 return [[p['x'],p[k]] for p in json.loads(val[0]) for k in ('y_ceiling','y_floor')] if val else None

def recover():
 objects=[o for o in json.loads((OUT/'validated_annotations.json').read_text()) if o['condition']=='semi']
 prop=pd.read_csv(REPO/'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/proposal_response.csv.gz').set_index('canonical_annotation_id').to_dict('index')
 trace=pd.read_csv(REPO/'analysis_results/annotation_research_prework_20260905_v2/evidence/initialization_trace.csv').set_index('canonical_annotation_id').to_dict('index')
 assert set(o['object_id'] for o in objects)==set(prop)==set(trace)
 rows=[];details=[]
 for o in objects:
  oid=o['object_id'];p=prop[oid];t=trace[oid];s=o['source']
  assert p['image_id']==o['image_id'] and f"W{int(p['worker_id']):03d}"==o['worker_id']
  assert t['base_task_id']==o['image_id'] and f"W{int(t['worker_id']):03d}"==o['worker_id']
  initial=json.loads(p['initial_points_json']);frozen_raw=json.loads(p['final_points_json'])
  runtime=[x for x in tasks(t['raw_export_path']) if x.get('id')==s['task']]
  assert len(runtime)==1,(oid,'runtime task count',len(runtime))
  runtime=runtime[0];answers=[a for a in runtime.get('annotations',[]) if a['id']==s['annotation']]
  assert len(answers)==1 and f"W{int(answers[0]['completed_by']):03d}"==o['worker_id']
  raw=points(answers[0]['result'])
  assert same(raw,o['original_export_points']),(oid,'current original mismatch')
  assert same(raw,frozen_raw),(oid,'historical final coordinate mismatch')
  imports=[]
  for path in json.loads(t['initial_import_paths_json']):
   matches=[v for v in tasks(path) if str(v.get('data',{}).get('base_task_id') or v.get('data',{}).get('image_id'))==o['image_id']]
   for im in matches:
    for pred in im.get('predictions',[]):
     if isinstance(pred,dict):
      ip=points(pred.get('result',[]))
      imports.append(dict(path=path,match=same(initial,ip),model_version=pred.get('model_version'),import_task_key=im.get('data',{}).get('task_id'),payload_hash=sha(ip)))
  assert imports and all(x['match'] for x in imports),(oid,'import conflict/missing')
  pv=preview(runtime); assert pv and same(initial,pv),(oid,'runtime preview conflict/missing')
  mc=o['review_evidence'].get('trap_model_evidence',{}).get('model_check')
  if mc:
   assert same(initial,mc['initial_points_1024x512']) and same(raw,mc['final_raw_points_1024x512'])
  status='unchanged_coordinates' if canonical(initial)==canonical(raw) else 'changed_coordinates'
  if o['model_edit_status']!='not_checked':assert status==o['model_edit_status']
  d=runtime.get('data',{})
  kind='synthetic_trap' if d.get('source_type')=='trap_synthetic' else 'natural_trap' if d.get('source_type')=='trap_natural' else 'control_natural' if d.get('semi_role')=='control' else 'unspecified_runtime_metadata'
  rec={k:o[k] for k in ['object_id','worker_id','image_id','image_code','building_id','condition','cleaning_disposition','trap_status','model_edit_status']}
  rec.update(initialization_source_verified=True,source_verification='all_import_payloads_and_runtime_preview_match',
   runtime_source=t['raw_export_path'],runtime_project=s['project'],runtime_task=s['task'],runtime_annotation=s['annotation'],
   runtime_initialization_kind=kind,runtime_semi_role=d.get('semi_role'),runtime_source_type=d.get('source_type'),runtime_trap_family=d.get('trap_family'),
   legacy_initialization_kind=t['legacy_initialization_source_kind'],stage=t['stage'],
   import_paths=[x['path'] for x in imports],n_import_payloads=len(imports),historical_checkpoint_bound=False,user_view_event_verified=False,
   recovered_edit_status=status,source_prior_not_checked=o['model_edit_status']=='not_checked',
   initial_point_count=len(initial),raw_final_point_count=len(raw),current_final_point_count=len(o['points_1024x512']) if o['points_1024x512'] else None,
   initialization_hash=sha([[round(float(x),8) for x in z] for z in initial]),initial_raw_hash=sha(initial),raw_final_hash=sha(raw),
   raw_final_equals_current=bool(o['points_1024x512'] is not None and same(raw,o['points_1024x512'])),
   current_point_repair_applied=bool(o.get('repair_evidence')),
   raw_net_point_change=len(raw)-len(initial),initial_and_final_same_array_order=same(initial,raw),
   initial_and_final_same_coordinate_multiset=canonical(initial)==canonical(raw))
  rows.append(rec);details.append(dict(object_id=oid,initial_points_1024x512=initial,raw_final_points_1024x512=raw,current_final_points_1024x512=o['points_1024x512'],import_payload_checks=imports))
 f=pd.DataFrame(rows)
 for col in ['import_paths']:f[col]=f[col].map(lambda x:json.dumps(x,ensure_ascii=False))
 f.to_csv(OUT/'initialization_evidence_574.csv',index=False,encoding='utf-8-sig')
 (OUT/'initialization_geometry_574.json').write_text(json.dumps(details,ensure_ascii=False),encoding='utf8')
 summary=dict(data_release='v1',semi_submissions=len(f),workers=f.worker_id.nunique(),images=f.image_id.nunique(),buildings=f.building_id.nunique(),
  initial_payloads_recovered=int(f.initialization_source_verified.sum()),runtime_sources=f.runtime_source.nunique(),
  current_edit_status=f.model_edit_status.value_counts().to_dict(),recovered_edit_status=f.recovered_edit_status.value_counts().to_dict(),
  runtime_initialization_kind=f.runtime_initialization_kind.value_counts().to_dict(),current_trap_status=f.trap_status.value_counts().to_dict(),
  newly_checked_by_old_status=f[f.source_prior_not_checked].recovered_edit_status.value_counts().to_dict(),
  limitations=['import + runtime preview is task-level initialization provenance, not a verified user-view event','old current trap_status remains unchanged; recovered runtime metadata is separate and does not readmit workers','raw worker output and current preprocessed/repaired geometry retained separately','historical model checkpoint remains unbound'])
 (OUT/'initialization_recovery_receipt.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':recover()
