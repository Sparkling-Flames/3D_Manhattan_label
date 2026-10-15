"""Frozen endpoints only: no new fusion, no synthetic k trajectory.
60 old endpoints rebuilt; 84 completed later use current-main metric projection.
Full reference rules independently reproduced. All formal eligibility stays false.
"""
from quality import *
from fusion_bindings import recover
from analyze_downstream import describe,corr
from collections import Counter,defaultdict
import pandas as pd

def main():
 old=read(ROOT/'source/fusion_220_old.json')['rows'];gap=recover();gm={(r['image_code'],r['version']):r for r in read(ROOT/'source/fusion_60_geometries.json')['rows']};data=read(ROOT/'source/historical_current_formal_loader_data.json');objects={o['object_id']:o for o in data['objects']};ad={r['record_id']:r for r in read(ROOT/'results/recovered_admission_3152.json')['records']};new={};proj=[]
 for line in (ROOT/'source/fusion_gap_metric_projection.tsv').read_text().splitlines():
  if not line or line.startswith('#'):continue
  v=line.split();i=int(v[0]);row=gap[i];m={k:None if not math.isfinite(float(x)) else float(x) for k,x in zip(['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','iou_3d_corner_mean'],v[1:])};assert len(v)==8
  if m['Hmean'] is not None:assert abs(abs(m['height_mean_ratio']-1)-m['Hmean'])<1e-12
  new[row['source_row_index']]=(row,m);proj.append(dict(source_record_index=i,**row,metrics=m,source_git_blob='98fd3813e71d70c36e39673bc4ea68ef4c285101',source_main='134e7c775b9ea25a076851c0605571ba0ea0ac31'))
 assert len(new)==85;assert sum(m['Hmean'] is not None for _,m in new.values())==84
 rows=[];parity=[];rebuilt=0;gc={}
 for idx,r in enumerate(old):
  members=[ad[m['record_id']] for m in r['members']]
  for m,a in zip(r['members'],members):assert m['object_id']==a['object_id'] and m['quality_worker_id']==a['worker_id'] and a['image_id']==r['image_id']
  x={k:r[k] for k in ['image_id','image_code','version','n','source','members','order_status','ring_confirmed','reference_id','unavailable_reason','use_barriers']}
  x.update(formal_comparison_eligible=False,stage=members[0]['stage'],member_restrictions=[a['record_id'] for a in members if a['personnel_barriers'] or a['context_barriers']],holdout_members=[a['record_id'] for a in members if a['original_holdout']],sequence_id=None,fusion_recomputed=False,metrics=None,scores=None,IoU3D100=None,full_score_scope_adjudicated=False)
  key=(r['image_code'],r['version']);m=None
  if key in gm:
   g=gm[key];a=geometry(g['source_points']);err=max(float(np.max(np.abs(np.asarray(a[k])-np.asarray(g['geometry'][k])))) for k in ['bottom3d','top3d']);assert err<1e-10
   ref=r['reference_id'];assert ref==g['reference_id'];gc.setdefault(ref,geometry(objects[ref]['points_1024x512']));out=measure(a,gc[ref]);assert out['status']=='complete';m=out['metrics'];rebuilt+=1
   errs={k:abs(m[k]-r['metrics'][k]) for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter'] if r['metrics'].get(k) is not None};parity.append(dict(image_code=r['image_code'],version=r['version'],geometry_error=err,metric_errors=errs));assert max(errs.values())<1e-8
   x.update(calculation='source_points_reconstruction',binding='previous_unique_frozen_reference',status='complete_conditional')
  elif idx in new:
   binding,m=new[idx];x['reference_id']=binding['reference_id'];x.update(calculation='stored_metrics_rescore_current_main_projection',binding=binding['classification'],status='complete_conditional' if m['Hmean'] is not None else 'floor_only',source_projection_record=next(v['source_record_index'] for v in proj if v['source_row_index']==idx))
  else:
   b=next((g for g in gap if g['source_row_index']==idx),None);x['status']=b['classification'] if b else 'geometry_or_order_held';x['binding']=x['status']
  if m is not None:x['metrics']=m;x['scores']=score(m);x['IoU3D100']=100*m['iou_3d_corner_mean'] if m.get('iou_3d_corner_mean') is not None else None
  rows.append(x)
 assert rebuilt==60 and sum(r['status']=='complete_conditional' for r in rows)==144
 # Auto/assisted actual endpoint pairs under the exact same reference.
 by=defaultdict(dict)
 for r in rows:
  if r['scores'] and r['scores']['WQ'] is not None:by[(r['image_id'],r['reference_id'])][r['version']]=r
 pairs=[]
 for (im,ref),v in by.items():
  if len(v)!=2:continue
  a,b=v['automatic'],v['assisted'];gaps={n:b['scores'][n]-a['scores'][n] for n in ['WQ','current']};gaps['IoU3D100']=b['IoU3D100']-a['IoU3D100']
  pairs.append(dict(image_id=im,image_code=a['image_code'],reference_id=ref,stage=a['stage'],automatic_n=a['n'],assisted_n=b['n'],gaps=gaps,reverse=gaps['WQ']*gaps['IoU3D100']<-1e-10,same_members={m['record_id'] for m in a['members']}=={m['record_id'] for m in b['members']},geometry_changed_any_metric=max(map(abs,gaps.values()))>1e-8,causal_effect_claimed=False))
 # Only numeric contrast to members using the same frozen reference. Never transfer
 # the reference selected by an individual to the fused endpoint.
 num={tuple((x['record_id'],x['reference_id'])):x for x in read(ROOT/'results/all_scores.json')['records'] if x['status']=='complete'};members=[]
 for r in rows:
  if not r['scores'] or r['scores']['WQ'] is None:continue
  mm=[num[(x['record_id'],r['reference_id'])] for x in r['members'] if (x['record_id'],r['reference_id']) in num]
  if len(mm)!=r['n']:continue
  gaps={n:r['scores'][n]-float(np.mean([x['scores'][n] for x in mm])) for n in ['WQ','current']};gaps['IoU3D100']=r['IoU3D100']-float(np.mean([x['IoU3D100'] for x in mm]))
  members.append(dict(image_id=r['image_id'],image_code=r['image_code'],version=r['version'],reference_id=r['reference_id'],n=r['n'],stage=r['stage'],member_restricted=bool(r['member_restrictions']),gaps=gaps,reverse=gaps['WQ']*gaps['IoU3D100']<-1e-10,all_member_comparators_same_reference=True))
 complete=[r for r in rows if r['status']=='complete_conditional'];summary=dict(endpoints=len(rows),full=144,floor_only=1,unavailable=75,point_rebuilt=60,stored_metrics_rescored=85,formal_qualified=0,full_stage_counts=dict(Counter(r['stage'] for r in complete)),full_with_member_restrictions=sum(bool(r['member_restrictions']) for r in complete),full_with_holdout_members=sum(bool(r['holdout_members']) for r in complete),WQ_IoU_correlation=corr([r['scores']['WQ'] for r in complete],[r['IoU3D100'] for r in complete]),WQ_change=describe([r['scores']['WQ']-r['scores']['current'] for r in complete]),auto_assisted_pairs=len(pairs),auto_assisted_nonidentical=sum(p['geometry_changed_any_metric'] for p in pairs),auto_assisted_direction_reversals=sum(p['reverse'] for p in pairs),complete_member_comparator_endpoints=len(members),fusion_minus_member_mean_direction_reversals=sum(p['reverse'] for p in members),fusion_algorithm_changed=False,per_k_trajectory_available=False)
 dump(ROOT/'source/fusion_gap_projection.json',dict(source_path='research/quality_downstream_audit_20261013/REFERENCE_GAP_AUDIT.json',original_file_bytes_retained=False,records=proj,projection='exact seven metric fields from connector response; reference bindings regenerated without scores; source indices retained'))
 dump(ROOT/'results/FUSION_220_RESULTS.json',dict(summary=summary,records=rows,point_parity=parity,auto_assisted_pairs=pairs,endpoint_vs_all_members=members))
 flat=[]
 for r in rows:
  x={k:r[k] for k in ['image_id','image_code','version','stage','n','reference_id','status','formal_comparison_eligible','member_restrictions','holdout_members','binding']};x.update(r['metrics'] or {});x.update(r['scores'] or {});x['IoU3D100']=r['IoU3D100'];flat.append(x)
 pd.DataFrame(flat).to_csv(ROOT/'results/FUSION_220_SCORES.csv',index=False,encoding='utf-8-sig');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
