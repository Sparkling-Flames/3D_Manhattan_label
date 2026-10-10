"""Preserve exposed six; add two predeclared geometry-only comparisons."""
import os
from pathlib import Path
from collections import Counter
from common import read,save,csvwrite,digest
ROOT=Path(__file__).resolve().parents[1]
ASSETS=Path(os.environ.get('QUALITY_RESEARCH_ASSETS','/workspace/quality_recovered_20261010/quality_scope_review_complete_20261010/workbench_v3.4.2/dist/assets'))
def main():
 rows=read(ROOT/'results/current_components.json');lookup={r['record_id']:r for r in rows}
 geo=read(ROOT/'inputs/current_geometry_compact.json')['geometries']
 alignment={r['record_id']:r for r in read(ROOT/'results/target_alignment_ledger.json')}
 old=read(ROOT/'history/review_v1/answer_mapping_private.json');missing={r['building_id'] for r in rows if not r['room_id']}
 def room(r):return r['building_id']+(':whole_building_missing_room' if r['building_id'] in missing else ':room:'+r['room_id'])
 exposed={room(lookup[c['record_1']]) for c in old}
 groups=[]
 for r in rows:
  key=room(r);held=key not in exposed and int(digest(key)[:8],16)%5==0
  groups.append({'record_id':r['record_id'],'image_code':r['image_code'],'room_group':key,'grouping_rule':'whole_building_due_to_any_missing_room' if r['building_id'] in missing else 'verified_building_room','room_id_missing_this_record':not bool(r['room_id']),'prior_sample_exposed_group':key in exposed,'held_out_of_sample_and_future_calibration':held,'historically_unseen_claimed':False})
 held={x['record_id'] for x in groups if x['held_out_of_sample_and_future_calibration']}
 chosen=[]
 for c in old:
  c['room_group']=room(lookup[c['record_1']]);ids=[c[k] for k in ['record_1','record_2'] if k in c]
  c['target_alignment_flags']=[alignment[r] for r in ids]
  c['pure_regularity_calibration_allowed']=all(alignment[r]['target_unconfounded_conservative'] for r in ids) and c['case_id']!='X01'
  c['prior_sample_already_exposed']=True;chosen.append(c)
 candidates=read(ROOT/'results/regularity_sample_pair_candidates.json');audit=[]
 for kind,cid in [('direction','C06'),('flatness','C07')]:
  for p in candidates[kind]:
   a=lookup[p['irregular']];b=lookup[p['regular']];reason=None
   if a['record_id'] in held:reason='whole_group_held_out'
   elif p['image_code'] in {c['image_code'] for c in chosen}:reason='already_used_image'
   elif not (ASSETS/(a['image_code']+'.jpg')).exists():reason='missing_real_photo'
   else:
    ys=[x[1] for x in geo[a['reference_object_id']]['top3d']]
    if max(ys)-min(ys)>=.01:reason='reference_top_not_flat'
   # Actual pixels inspected before acceptance; visual evidence documents applicability, not quality judgment.
   inspected={'uNb9QFRL6hY-53':'真实像素：墙、窗与梁柱呈直线正交结构；壁炉突出且有遮挡，不能据此预填优劣。','wc2JMjhGNzB-40':'真实像素：主房间墙向正交、主顶界近水平；门洞/邻室单列，当前GT范围比较。'}
   if not reason and p['image_code'] not in inspected:reason='not_yet_pixel_inspected'
   audit.append({**p,'rejection_reason':reason,'visual_applicability_note':inspected.get(p['image_code'])})
   if reason:continue
   pair=[a,b]
   if int(digest(cid)[:8],16)%2:pair.reverse()
   chosen.append({'case_id':cid,'selection_stratum':kind+'_isolated_predeclared','image_code':a['image_code'],'room_group':room(a),'record_1':pair[0]['record_id'],'record_2':pair[1]['record_id'],'object_1':pair[0]['object_id'],'object_2':pair[1]['object_id'],'reference_object_id':a['reference_object_id'],'worker_1':pair[0]['worker_id'],'worker_2':pair[1]['worker_id'],'Q1':pair[0]['Q'],'Q2':pair[1]['Q'],'geometry_pair_evidence':p,'photo_path':str(ASSETS/(a['image_code']+'.jpg')),'target_alignment_flags':[alignment[x['record_id']] for x in pair],'pure_regularity_calibration_allowed':True,'historical_exposure':'历史归档材料，无历史未见声明','prior_sample_already_exposed':False,'visual_applicability_note':inspected[p['image_code']]})
   break
 chosen.sort(key=lambda c:c['case_id'])
 save(ROOT/'blind_sample/answer_mapping_private.json',chosen);csvwrite(ROOT/'results/room_holdout_manifest.csv',groups);save(ROOT/'results/regularity_sample_selection_audit.json',audit)
 responses=[]
 for c in chosen:
  if c['case_id']=='X01':responses.append({'case_id':c['case_id'],'case_type':'同一答案的空间匹配','空间判断（仅 A 可匹配/仅 B 可匹配/两者均可匹配/两者均不匹配/无法判断）':'','主要原因':'','信心':'','备注':''})
  else:responses.append({'case_id':c['case_id'],'case_type':'两份答案质量比较','优劣（答案1更好/答案2更好/相近/无法判断）':'','差距（小/中/大）':'','答案1（可接受/明显问题/严重不可接受/无法判断）':'','答案1主要原因':'','答案2（可接受/明显问题/严重不可接受/无法判断）':'','答案2主要原因':'','比较主要原因':'','信心':'','备注':''})
 csvwrite(ROOT/'blind_sample/user_response_blank.csv',responses)
 groupstate={}
 for g in groups:groupstate.setdefault(g['room_group'],set()).add(g['held_out_of_sample_and_future_calibration'])
 assert all(len(v)==1 for v in groupstate.values())
 assert all(c['record_1'] not in held and c.get('record_2') not in held for c in chosen)
 audit={'main_sample_cases':sum(c['case_id']!='X01' for c in chosen),'cross_space_cases':1,'whole_building_groups_due_to_missing_room':len(missing),'all_groups':len(groupstate),'held_out_groups':sum(next(iter(v)) for v in groupstate.values()),'held_out_records':len(held),'prior_exposed_groups_fixed_to_development':len(exposed),'group_leakage':False,'user_judgments_filled':False,'no_Q_used_for_new_geometry_pair_selection':True,'added_regularity_cases':[c['case_id'] for c in chosen if c['case_id'] in ['C06','C07']],'target_confounded_historical_general_examples':[c['case_id'] for c in chosen if not c['pure_regularity_calibration_allowed']]}
 save(ROOT/'blind_sample/selection_audit.json',audit);print(audit)
if __name__=='__main__':main()
