"""Balanced deterministic post-closeout audit queue; no GT/score-based ref changes.
No new labels are produced. Reasons and scores are kept OUT of the review HTML.
"""
from quality import *
import pandas as pd,ast,html,hashlib
from collections import Counter

def main():
 R=ROOT/'results';V=ROOT/'review';V.mkdir(exist_ok=True)
 f=pd.read_csv(R/'ORDINARY_962.csv');allf=pd.read_csv(R/'ALL_3152_LEDGER.csv');by=allf.set_index('record_id',drop=False);objs={o['object_id']:o for o in read(ROOT/'source/historical_current_formal_loader_data.json')['objects']}
 cands={c['reference_object_id']:c for im in read(ROOT/'source/routing_prepared.json')['candidate_images'] for c in im['candidates']}
 old={rid for c in read(ROOT/'source/latest_feedback_projection.json')['cases'] for rid in c['record_ids']};f=f[(~f.record_id.isin(old))&(~f.latest_step_reference_pending)]
 selections=[];used=set();images=Counter()
 def add(ids,reason,kind='quality',force=False):
  if any(rid in used for rid in ids):return False
  if not force and any(images[by.loc[rid].image_id]>=2 for rid in ids):return False
  for rid in ids:used.add(rid)
  for im in {by.loc[rid].image_id for rid in ids}:images[im]+=1
  selections.append(dict(case_id=f'C{len(selections)+1:02d}',record_ids=ids,selection_reason=reason,kind=kind));return True
 # Ten quantile strata: pick near stratum median; no photo-availability filter.
 fs=f.sort_values(['WQ','record_id']);bins=np.array_split(np.arange(len(fs)),10)
 for k,inds in enumerate(bins):
  sub=fs.iloc[inds].copy();mid=sub.WQ.median();sub['distance']=abs(sub.WQ-mid)
  for _,r in sub.sort_values(['distance','record_id']).iterrows():
   if add([r.record_id],f'ordinary_WQ_quantile_{k+1:02d}_typical_not_grade'):break
 # Four conflicting pairs from different images, two directions of IDs, not favored model.
 p=pd.read_csv(R/'ORDINARY_PAIRWISE_COMPARISONS.csv');p=p[p.WQ_IoU_reverse & (p.gap_WQ.abs()>=5)&(p.gap_IoU3D100.abs()>=5)].copy();p['salience']=np.minimum(p.gap_WQ.abs(),p.gap_IoU3D100.abs())
 chosenimages=set()
 for sign in (1,-1):
  n=0
  for _,r in p[p.gap_WQ*sign>0].sort_values(['salience','image_code'],ascending=[False,True]).iterrows():
   ids=[ast.literal_eval(r.A_ids)[0],ast.literal_eval(r.B_ids)[0]]
   if any(rid in old for rid in ids) or r.image_code in chosenimages:continue
   if add(ids,'same_reference_opposite_metric_order_not_winner'):
    chosenimages.add(r.image_code);n+=1
   if n==2:break
 # Representation, normal reference sensitivity, severe, doorway, floor-only, and step limits.
 sub=pd.read_csv(R/'HEIGHT_ESTIMATOR_AND_SUBDIVISION_962.csv');sub['abschange']=sub.subdivision_iou3d_change_pp.abs()
 for _,r in sub.sort_values('abschange',ascending=False).iterrows():
  if r.record_id not in old and add([r.record_id],'same_geometry_vertex_sampling_sensitivity'):break
 refs=read(R/'REFERENCE_VERSION_SENSITIVITY.json')['records']
 for r in sorted(refs,key=lambda r:-r['WQ_spread']):
  if add([r['record_id']],'two_GT_versions_not_two_accepted_targets','reference'):break
 sev=allf[(allf.role=='severe_exception_candidate')&allf.WQ.notna()].sort_values('WQ')
 for ix in (0,len(sev)//2,len(sev)-1):add([sev.iloc[ix].record_id],'severe_exception_separate_no_personnel_restoration',force=True)
 door=allf[(allf.stage=='doorway')&(allf.score_status=='conditional_full')&(~allf.record_id.isin(old))].sort_values('WQ')
 for ix in (0,len(door)//2,len(door)-1):add([door.iloc[ix].record_id],'doorway_conditional_low_middle_high_not_expected_low',force=True)
 fl=allf[allf.score_status=='floor'].sort_values('record_id');add([fl.iloc[0].record_id],'accepted_floor_only_no_borrowed_ceiling','floor',force=True)
 st=allf[(allf.image_id=="uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d")&allf.WQ.notna()].sort_values('record_id');add([st.iloc[0].record_id],'step_reference_pending_not_quality_grade','reference',force=True)
 # Q01 is an explicit documentation hold, not a request to repeat a completed preference.
 add(['R03332'],'Q01_small_space_accepted_precise_reference_still_missing','reference',force=True)
 rich=[];public=[]
 for c in selections:
  rows=[by.loc[rid].to_dict() for rid in c['record_ids']];im=rows[0]['image_id'];geoms=[];bindings=[];photo=ROOT/'source/ready/photos'/f'{im}.png'
  if not photo.exists():photo=ROOT/'source/additional_photos'/photo.name
  refs=[]
  for i,r in enumerate(rows):
   a=geometry(objs[r['object_id']]['points_1024x512']);geoms.append(dict(label=chr(65+i),geometry=a))
   ref=r.get('reference_id')
   if pd.notna(ref):refs.append(ref)
   elif r['score_status']=='target_version_unresolved':refs.extend([v['object_id'] for v in read(R/'recovered_admission_3152.json')['records'][0]['available_reference_versions'].values()] if False else [])
   bindings.append({k:r.get(k) for k in ('record_id','object_id','image_id','image_code','worker_id','reference_id','score_status','role','stage','original_holdout')})
  if c['kind']=='reference' and rows[0]['score_status']=='target_version_unresolved':
   gate=next(r for r in read(R/'recovered_admission_3152.json')['records'] if r['record_id']==rows[0]['record_id']);refs=[v['object_id'] for v in gate['available_reference_versions'].values() if not v['restrictions']]
  for j,ref in enumerate(dict.fromkeys(refs)):
   if rows[0]['record_id']=='R03332':label='既有大范围参考（不是小房间质量真值）'
   else:label='参考'+str(j+1)
   if ref in objs:g=geometry(objs[ref]['points_1024x512'])
   elif ref in cands:
    can=cands[ref];g=can['full_geometry'] if can['full_reference_available'] else {'bottom3d':[[p[0],-1,p[1]] for p in can['floor_xz_h']]}
   else:continue
   geoms.append(dict(label=label,geometry=g))
  rich.append(dict(**c,bindings=bindings,photo_available=photo.exists(),photo_path=str(photo.relative_to(ROOT)) if photo.exists() else None,prior_development_exposure=True,metrics=[{k:r.get(k) for k in ('WQ','current','IoU3D100','dir','Hmean','Hcenter','S_bottom_deg')} for r in rows]))
  public.append(dict(case_id=c['case_id'],kind=c['kind'],image_code=rows[0]['image_code'],record_ids=c['record_ids'],photo='../'+photo.relative_to(ROOT).as_posix() if photo.exists() else None,geometry=geoms,notice=('本例仅核查参考/空间；不按现有参考给作答定质量。' if c['kind']=='reference' else '仅底面参考，不判断完整高度质量。' if c['kind']=='floor' else '先看原图核对是否同一目标，再看底面与高度。'),scores_hidden=True))
 dump(V/'CANDIDATE_QUEUE.json',dict(cases=rich,summary=dict(cases=len(rich),responses=len(used),images=len(images),photos_available=sum(c['photo_available'] for c in rich),cases_without_photo=sum(not c['photo_available'] for c in rich)),selection_before_photo_filter=True,blind_test_claimed=False,not_a_new_review_prerequisite=True))
 flat=[dict(case_id=c['case_id'],selection_reason=c['selection_reason'],photo_available=c['photo_available'],**b,**m) for c in rich for b,m in zip(c['bindings'],c['metrics'])];pd.DataFrame(flat).to_csv(V/'CANDIDATE_BINDINGS.csv',index=False,encoding='utf-8-sig')
 dump(V/'DISPLAY_DATA.json',public)
 template=(ROOT/'src/review_template.html').read_text(encoding='utf-8');s=template.replace('__DATA__',json.dumps(public,ensure_ascii=False).replace('</','<\\/'));(V/'REVIEW.html').write_text(s,encoding='utf-8')
 print(read(V/'CANDIDATE_QUEUE.json')['summary'])
if __name__=='__main__':main()
