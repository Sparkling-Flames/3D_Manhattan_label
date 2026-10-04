"""Apply frozen externally supplied classes to one explicitly selected current roster.
Works with compact {'records':...} input or current {'images':...} input.
Class labels must already be trained outside the target building. Does not derive
Q/T/S/B from unknown review tags or missing logs, and never restores excluded votes.
"""
from pathlib import Path
import argparse,json,itertools
import pandas as pd
from finite_pool import make_basis

def run(input_path,class_path,out):
 if out.exists():raise ValueError('new_output_directory_required')
 data=json.loads(input_path.read_text(encoding='utf-8-sig'));c=json.loads(class_path.read_text(encoding='utf-8-sig'))
 image=c['image'];condition=c['condition'];members=c['members'];building=c['target_building']
 if c.get('training_target_isolation_verified') is not True:raise ValueError('training_isolation_not_attested')
 if not c.get('calibration_buildings') or building in c['calibration_buildings']:raise ValueError('calibration_building_leakage_or_missing')
 if not c.get('feature_source_bindings'):raise ValueError('feature_source_bindings_required')
 if 'images' in data:
  candidates=[x for x in data['images'] if x.get('code',x.get('image'))==image]
  if len(candidates)!=1:raise ValueError('missing_or_ambiguous_image')
  source=candidates[0];allrecords=source['annotations'];references=source.get('references',[])
 else:
  source=data
  if source.get('image')!=image:raise ValueError('wrong_image')
  allrecords=source['records'];references=[source['reference']] if source.get('reference') else []
 if source.get('building')!=building:raise ValueError('building_binding_mismatch')
 by={r['id']:r for r in allrecords};records=[];labels=[]
 for entry in members:
  r=by[entry['id']]
  if r['worker']!=entry['worker'] or r['condition']!=condition:raise ValueError('record_identity_or_condition_mismatch')
  if not r.get('independent') or not r.get('consensus_eligible'):raise ValueError('noneligible_person_must_not_be_restored')
  records.append(r);labels.append(entry['class'])
 if len(set(labels))>4:raise ValueError('prototype_budget_at_most_four_classes')
 if sorted(set(labels))!=list(range(len(set(labels)))):raise ValueError('noncontiguous_class_labels')
 ref=None
 if c.get('reference_evaluation_allowed'):
  rid=c['reference_id'];opts=[x for x in references if x['id']==rid]
  if len(opts)!=1:raise ValueError('reference_identity_unavailable')
  if not c.get('reference_eligibility_source'):raise ValueError('reference_eligibility_evidence_required')
  ref=opts[0]
 out.mkdir(parents=True)
 reference_failure=None
 try:b=make_basis(records,ref)
 except (ValueError,TypeError) as e:
  if str(e)=='reference_unavailable_no_repair':
   reference_failure=str(e);ref=None;b=make_basis(records,None)
  else:
   (out/'status.json').write_text(json.dumps(dict(status='whole_selected_roster_unavailable',reason=str(e),members=members),ensure_ascii=False,indent=2)+'\n');return
 N,_=b.group_data(labels);budget=1
 for n in N:budget*=n+1
 if budget>10000:raise ValueError('composition_budget_exceeded_explicitly')
 rows=[];trans=[]
 for K in itertools.product(*(range(n+1) for n in N)):
  if not sum(K):continue
  for rule in ['mv50','mv_strict']:
   meta=dict(image=image,condition=condition,composition='|'.join(map(str,K)),k=sum(K),rule=rule)
   row=dict(**meta,**b.area_summary(b.q(labels,K,rule)))
   if all(2*k<=n for k,n in zip(K,N)):row['same_k_disjoint_symdiff_union']=b.transition(labels,K,rule,'disjoint',())['expected_shape_change_union']
   rows.append(row)
   for g,n in enumerate(N):
    for count in [1,2]:
     if K[g]+count<=n:
      A=tuple(count if j==g else 0 for j in range(len(N)))
      trans.append(dict(**meta,operation='add',change='|'.join(map(str,A)),**b.transition(labels,K,rule,'add',A)))
 pd.DataFrame(rows).to_csv(out/'area.csv',index=False);pd.DataFrame(trans).to_csv(out/'transitions.csv',index=False)
 (out/'classes_used.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
 (out/'status.json').write_text(json.dumps(dict(status='computed',roster_n=len(records),class_sizes=N,reference_used=None if ref is None else ref['id'],reference_status='unavailable' if reference_failure else ('evaluated' if ref is not None else 'not_requested_or_not_applicable'),reference_failure_reason=reference_failure,checks=b.checks,scope='BEV_region_only_not_complete_top_bottom_layout'),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.input,a.classes,a.out)
