"""Recover a current-use projection from byte-pinned effective inputs.
This is NOT load_current_bundle(): comments/research-table validation is not claimed.
Uses the inspected main 134e7c7 admission/staging rules, with exact READY admission
rows as verification and the documented uNb-63 scene correction.
"""
from pathlib import Path
import json,csv,collections,hashlib
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'source'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
 data=read(S/'historical_current_formal_loader_data.json');objects={o['object_id']:o for o in data['objects']};ims={i['image_id']:i for i in data['images']}
 ids={o['object_id']:f'R{i:05d}' for i,o in enumerate(sorted(data['objects'],key=lambda x:x['object_id']),1)}
 frozen={r['object_id']:r for r in read(S/'search_922.json')['rows']};old={r['id']:r for r in read(S/'calibration_922.json')['rows']}
 ready=read(ROOT/'source/ready/data/cohorts.json');known={r['record_id']:r for r in ready['admissions']}
 scenes={r['image_id']:r['current_scene_review'] for r in known.values()};hist={r['object_id']:r for r in read(S/'severe_screen_115.json')};sev={r['object_id']:r for r in read(S/'severe_feedback.json')['records']}
 iholds={r['image_id'] for r in hist.values() if 'existing_image_wide_analysis_hold' in r['applicability_barriers']}
 holds={r['record_id']:r for r in csv.DictReader((S/'holdout_3152.csv').open(encoding='utf-8-sig'))}
 reg=read(S/'reference_exclusions.json');restr={}
 for kind in ('confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine'):
  for r in reg[kind]:
   for v in r['gt_versions']:restr.setdefault(v['gt_object_id'],[]).append(kind+':'+r['classification'])
 rows=[]
 for o in data['objects']:
  if o['object_kind']!='annotation':continue
  oid=o['object_id'];rid=ids[oid];im=ims[o['image_id']];prior=frozen.get(oid);h=holds[rid];assert h['image_code']==o['image_code']
  if o['condition']=='manual':cohort='manual_priority'
  elif o['condition']!='semi':cohort='other_condition_separate'
  elif o['trap_status']=='confirmed_trap':cohort='semi_trap_separate'
  elif o['model_edit_status']=='unchanged_coordinates':cohort='semi_unchanged_separate'
  elif 'model_unchanged' in o['review_evidence'].get('annotation_traits',{}).get('tags',[]):cohort='semi_model_issue_separate'
  elif o['trap_status']=='confirmed_nontrap' and o['model_edit_status']=='changed_coordinates':cohort='semi_nontrap_changed_candidate'
  else:cohort='semi_unverified_separate'
  if o['image_id'] in scenes:scene=scenes[o['image_id']]['scene']
  elif im['oos_status']=='confirmed':scene='oos_and_doorway' if im['doorway_status']=='difficult' else 'oos'
  elif im['oos_status']=='pending':scene='oos_pending'
  elif im['doorway_status'] in ('difficult','annotatable'):scene='doorway_'+im['doorway_status']
  else:scene='clear' if im['oos_status']=='not_oos' else 'unflagged'
  if o['image_code']=='uNb9QFRL6hY-63':scene='oos'
  label=sev.get(oid);histrow=hist.get(oid);reviewed=bool(label and label['effective_review_status']=='reviewed_severe');gate=old[rid]['gate'] if prior else None
  allowed=bool(prior and ((gate['new_descriptive_development_allowed'] and not gate['barriers'] and not gate['explicit_exposure_barriers']) if 'new_descriptive_development_allowed' in gate else (gate['old_review_gate_preserved'] and reviewed and histrow and histrow['full_Q_calibration_ready'] and gate['metadata']['evidence_layer']=='new_severe_conditional_development')))
  personnel=[]
  if o['worker_id'] in ['W019','W026']:personnel.append('excluded_worker:'+o['worker_id'])
  if o['cleaning_disposition']!='retained':personnel.append('cleaning:'+o['cleaning_disposition'])
  if o['worker_quality_gate']!='candidate_pending_geometry':personnel.append('formal_gate:'+o['worker_quality_gate'])
  if not o['independent_vote_eligible']:personnel.append('not_independent_vote')
  if o['borrowed_point_provenance']:personnel.append('borrowed_point_provenance')
  context=[]
  if scene in ('oos','oos_and_doorway','oos_pending','doorway_difficult','doorway_annotatable'):context.append('special_scene_separate_from_calibration:'+scene)
  if h['held_out_of_sample_and_future_calibration'].lower()=='true':context.append('original_holdout')
  if o['image_id'] in iholds:context.append('existing_image_wide_analysis_hold')
  if histrow:context.extend('severe_screen:'+v for v in histrow['applicability_barriers'])
  ref=prior['reference_object_id'] if prior else None
  if ref:context.extend('reference_excluded:'+v for v in restr.get(ref,[]))
  if not prior and im['references'] and all(restr.get(v) for v in im['references'].values()):context.append('all_existing_full_reference_versions_restricted')
  if prior and not allowed:context.append('no_existing_conditional_development_authority')
  numeric=[]
  if o['geometry']['status']!='surface_valid':numeric.append(o['geometry']['status'])
  if not o['links_zero_based']:numeric.append('pairing_unavailable')
  if not prior:numeric.extend(['outside_frozen_metrics','fixed_reference_binding_not_audited_in_922'])
  remaining=[v for v in personnel if not v.startswith(('excluded_worker:','cleaning:','formal_gate:excluded','not_independent_vote'))]
  exc=bool(reviewed and personnel and not remaining)
  if cohort not in ('manual_priority','semi_nontrap_changed_candidate') or context or(personnel and not exc):role='held_or_diagnostic'
  elif exc:role='severe_exception_candidate'
  else:role='manual_development_candidate' if cohort=='manual_priority' else 'semi_secondary_candidate'
  stage='oos' if o['condition']=='oos' or scene in ('oos','oos_and_doorway','oos_pending') else 'doorway' if scene.startswith('doorway') else 'ordinary'
  row=dict(record_id=rid,object_id=oid,image_id=o['image_id'],image_code=o['image_code'],building_id=o['building_id'],worker_id=o['worker_id'],condition=o['condition'],source_cohort=cohort,scene=scene,stage=stage,role=role,reference_object_id=ref,available_reference_versions={k:dict(object_id=v,restrictions=restr.get(v,[])) for k,v in im['references'].items()},original_holdout='original_holdout' in context,personnel_barriers=personnel,context_barriers=sorted(set(context)),numeric_barriers=sorted(set(numeric)),severe_exception=exc,full_q_calibration_ready=role!='held_or_diagnostic' and not numeric,existing_conditional_development_allowed=allowed,formal_eligibility_newly_granted=False,exposure='included_in_joint_development_package' if prior else 'not_certified_unexposed',source_geometry_status=o['geometry']['status'])
  rows.append(row)
 differences=[]
 for r in rows:
  if r['record_id'] not in known:continue
  k=known[r['record_id']]
  for key in ['object_id','image_id','worker_id','condition','source_cohort','role','reference_object_id','personnel_barriers','context_barriers','numeric_barriers','original_holdout','full_q_calibration_ready','severe_exception','existing_conditional_development_allowed']:
   if r[key]!=k[key]:differences.append(dict(record_id=r['record_id'],field=key,recovered=r[key],ready=k[key]))
 summary=dict(records=len(rows),objects=len(objects),conditions=dict(collections.Counter(r['condition'] for r in rows)),roles=dict(collections.Counter(r['role'] for r in rows)),stages=dict(collections.Counter(r['stage'] for r in rows)),cohorts=dict(collections.Counter(r['source_cohort'] for r in rows)),holdout=sum(r['original_holdout'] for r in rows),ready_overlap_checked=len(known),ready_field_differences=len(differences),native_full_loader_executed=False)
 dump(ROOT/'results/recovered_admission_3152.json',dict(summary=summary,records=rows,differences=differences,reference_restrictions=restr));print(json.dumps(summary,ensure_ascii=False,indent=2));print('differences',differences[:8])
if __name__=='__main__':main()
