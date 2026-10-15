"""All applicable current-bound inputs, preserving held entries and source strata.
No new fit; no GT choice by quality. Rebuilds new pairs; rescores reliable stored
same-reference metrics and checks a deterministic geometrical sample.
"""
from quality import *
import csv,collections,time
S=ROOT/'source';R=ROOT/'results'
def main():
 start=time.perf_counter();d=read(S/'historical_current_formal_loader_data.json');obj={o['object_id']:o for o in d['objects']}
 gate=read(R/'recovered_admission_3152.json');rows=gate['records'];by={r['record_id']:r for r in rows}
 search={r['id']:r for r in read(S/'search_922.json')['rows']};old={r['id']:r for r in read(S/'calibration_922.json')['rows']}
 ready=read(ROOT/'source/ready/data/cohorts.json')
 readyrows={r['record_id']:r for layer in ['ordinary','severe','doorway','historical_only'] for r in ready[layer]}
 route={r['record_id']:r for r in read(S/'routing_429.json')['rows']}
 cand={c['candidate_id']:c for im in read(S/'routing_prepared.json')['candidate_images'] for c in im['candidates']}
 cache={};pairs={};canonical={};unbound=[]
 def geom(oid):
  if oid not in cache:cache[oid]=geometry(obj[oid]['points_1024x512'])
  return cache[oid]
 def add(r,ref,kind,layer,metrics=None,candidate=None):
  key=(r['record_id'],ref,kind)
  if key not in pairs:pairs[key]=dict(record_id=r['record_id'],object_id=r['object_id'],image_id=r['image_id'],image_code=r['image_code'],building_id=r['building_id'],worker_id=r['worker_id'],condition=r['condition'],stage=r['stage'],role=r['role'],reference_id=ref,score_kind=kind,use_layers=[],metrics=metrics,candidate_id=candidate,original_holdout=r['original_holdout'],personnel_barriers=r['personnel_barriers'],context_barriers=r['context_barriers'],formal_eligibility_newly_granted=False)
  if layer not in pairs[key]['use_layers']:pairs[key]['use_layers'].append(layer)
  return key
 def eligible_refs(r):return [x['object_id'] for x in r['available_reference_versions'].values() if not x['restrictions'] and obj[x['object_id']]['geometry']['status']=='surface_valid' and obj[x['object_id']]['links_zero_based']]
 for r in rows:
  rid=r['record_id'];rt=route.get(rid);f=search.get(rid)
  if r['role']=='manual_development_candidate':
   refs=eligible_refs(r)
   if rt:
    if rt['status']!='available':canonical[rid]=dict(status='route_unavailable');continue
    c=cand[rt['selected_candidate_id']];ref=c['reference_object_id'];full=rt['selected_full_status']=='available'
    m=None if full else dict(iou_2d=rt['I_selected'],S_bottom_deg=rt['Sb_selected_deg'],dir=rt['D_deg'],Hmean=None,Hcenter=None,iou_3d_corner_mean=None)
    k=add(r,ref,'full' if full else 'floor','ordinary_current',m,c['candidate_id']);canonical[rid]=dict(status='full' if full else 'floor',pair_key=k,binding='existing_route_preserved',uncertainty=rt.get('uncertainty'),manual_directive=rt.get('manual_directive_applied',False))
   elif f:
    k=add(r,f['reference_object_id'],'full','ordinary_current',f['metrics']);canonical[rid]=dict(status='full',pair_key=k,binding='frozen_fixed_reference')
   elif obj[r['object_id']]['geometry']['status']!='surface_valid' or not obj[r['object_id']]['links_zero_based']:
    canonical[rid]=dict(status='geometry_unavailable')
   elif len(refs)==1:
    k=add(r,refs[0],'full','ordinary_current');canonical[rid]=dict(status='full',pair_key=k,binding='single_existing_reference_conditional')
   elif len(refs)>1:
    canonical[rid]=dict(status='target_version_unresolved',reference_ids=refs)
    for ref in refs:add(r,ref,'full','ordinary_version_sensitivity_only')
   else:canonical[rid]=dict(status='reference_unavailable')
   # Preserve version sensitivities, without duplicating a response in main.
   if not f and len(refs)>1:
    for ref in refs:add(r,ref,'full','version_sensitivity_only')
  elif r['role']=='semi_secondary_candidate' and r['full_q_calibration_ready']:
   k=add(r,f['reference_object_id'],'full','semi_secondary',f['metrics']);canonical[rid]=dict(status='full',pair_key=k,binding='frozen_fixed_reference')
  elif r['role']=='severe_exception_candidate' and r['full_q_calibration_ready']:
   k=add(r,f['reference_object_id'],'full','severe_exception',f['metrics']);canonical[rid]=dict(status='full',pair_key=k,binding='severe_frozen_reference_no_personnel_restoration')
  elif rid in readyrows and r['stage']=='doorway':
   rr=readyrows[rid]
   if rr.get('status')=='complete':
    ref=rr.get('reference',{}).get('object_id') or rr.get('reference_object_id') or r['reference_object_id'];k=add(r,ref,'full','doorway_conditional',rr.get('metrics'))
    reason='Q01_small_reference_not_defined' if r['image_code']=='B6ByNegPMKs-43' else 'Q02_scope_mismatch_latest' if rid in ('R02200','R00990') else None
    canonical[rid]=dict(status='conditional_scope_diagnostic' if reason else 'conditional_full',pair_key=k,binding='ready_doorway_binding',same_target_quality_not_certified=True,reason=reason)
   else:canonical[rid]=dict(status='held',reasons=rr.get('reasons',rr.get('reason_codes',[])))
  elif rid in readyrows and rid in {r['record_id'] for r in ready['historical_only']}:
   rr=readyrows[rid];ref=rr.get('reference_object_id') or f['reference_object_id'];k=add(r,ref,'full','historical_only',rr.get('metrics') or f['metrics']);canonical[rid]=dict(status='historical_only',pair_key=k,binding='historical_bound_reference')
  else:canonical[rid]=dict(status='oos_not_applicable' if r['stage']=='oos' else 'held',reasons=r['personnel_barriers']+r['context_barriers']+r['numeric_barriers'])
 # IoU is in the archived legacy_metrics for some old rows, not copied into metrics.
 for key,p in pairs.items():
  rid,ref,kind=key
  if p['metrics'] is not None and kind=='full' and p['metrics'].get('iou_3d_corner_mean') is None and rid in old and old[rid]['reference_object_id']==ref:
   p['metrics']=dict(p['metrics'],iou_3d_corner_mean=old[rid].get('legacy_metrics',{}).get('iou_3d_corner_mean'))
 print('Queue',len(pairs),'canonical',collections.Counter(x['status'] for x in canonical.values()),flush=True)
 audits=[];fail=[];output=[];rebuild=0;rescore=0
 for j,(key,p) in enumerate(pairs.items()):
  try:
   stored=p.pop('metrics');need=stored is None or (p['score_kind']=='full' and stored.get('iou_3d_corner_mean') is None)
   if need or j%47==0:
    a=geom(p['object_id'])
    if p['candidate_id'] and cand[p['candidate_id']]['full_reference_available']:g=cand[p['candidate_id']]['full_geometry']
    elif p['score_kind']=='floor':g=None
    else:g=geom(p['reference_id'])
    if g is not None:
     result=measure(a,g);rebuild+=1
     if result['status']!='complete':raise ValueError(str(result))
     m=result['metrics']
     if stored is not None:
      errs={k:abs(stored[k]-m[k]) for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter','iou_3d_corner_mean') if stored.get(k) is not None};audits.append(dict(record_id=p['record_id'],reference_id=p['reference_id'],errors=errs));assert max(errs.values())<1e-8,(p['record_id'],errs)
     else:stored=m
   if stored is None:raise ValueError('metrics_unavailable')
   p['metrics']=stored;p['scores']=score(stored);p['calculation']='point_reconstruction' if need else 'stored_metrics_rescore';rescore+=not need
   t=stored.get('iou_3d_corner_mean');p['IoU3D100']=100*t if t is not None else None;p['status']=p['scores']['status']
  except (ValueError,KeyError,ArithmeticError) as e:
   p.update(status='unavailable',error=type(e).__name__+':'+str(e),metrics=None,scores=None,IoU3D100=None);fail.append(dict(key=key,error=p['error']))
  output.append(p)
  if j%100==0:print('done',j,'time',round(time.perf_counter()-start,1),flush=True)
 payload=dict(records=output,canonical=canonical,parity=audits,failures=fail,summary=dict(pair_records=len(output),unique_responses=len({p['record_id'] for p in output}),stored_rescored=rescore,point_measurements=rebuild,full_pairs=sum(p['status']=='complete' for p in output),floor_pairs=sum(p['status']=='floor_only' for p in output),failures=len(fail),seconds=time.perf_counter()-start,native_loader=False,parameters_changed=False))
 dump(R/'all_scores.json',payload);print(payload['summary'],flush=True)
if __name__=='__main__':main()
