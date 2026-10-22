from pathlib import Path
import sys,json,copy,traceback
R=Path(__import__('os').environ['PRO_PACKAGE']).resolve();O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'src'))
from score_manifest import score_record,geometry_hash
from compare_versions import compare
p=json.loads((R/'inputs/fixed_pairs.json').read_text())[0]
changes={
 'eligibility_literal_false_string':{'original_quality_eligible':'false'},
 'reference_complete_literal_false_string':{'reference_complete':'false'},
 'wrong_image_binding':{'image_id':'deliberately_wrong_image_id'},
 'missing_worker_identity':{'worker_id':None},
 'missing_object_identity':{'object_id':None},
 'NaN_source_pool_workers':{'source_pool_workers':float('nan')},
 'stale_difficulty_version':{'difficulty_version':'archived_wrong_version'},
 'missing_answer_geometry':{'answer':None},
 'nonmapping_answer_geometry':{'answer':[]},
 'nonnumeric_answer_geometry':{'answer':{'bottom3d':[['bad',-1,0]]*3,'top3d':[[0,1,0]]*3}},
 'no_top_geometry':{'answer':{'bottom3d':p['answer']['bottom3d']}},
}
rows=[]
for name,ch in changes.items():
 q=copy.deepcopy(p);q.update(ch)
 if 'answer' in ch:q['answer_sha256']=geometry_hash(q['answer'])
 try:
  r=score_record(q);rows.append({'case':name,'status':r['status'],'reason':r.get('reason'),'B8L2':r.get('B8L2'),'EBC2_L2':r.get('EBC2_L2')})
 except Exception as e:rows.append({'case':name,'exception':type(e).__name__+': '+str(e)})
# A test where numerical input comparison is unchanged but the target identity changes.
a={'object_id':'a','image_id':'image','current_target_id':'target','reference_id':'target','answer_sha256':'a_hash','reference_sha256':'r_hash','Q':1.0,'status':'complete','reference_version':'v1','difficulty_version':'v6'};b=copy.deepcopy(a);b.update(status='not_admitted',reference_version='unapproved',difficulty_version='v-old')
c=compare([a],[b],'Q').to_dict(orient='records')
out={'manifest_cases':rows,'comparator_changed_admission_metadata':c}
(O/'manifest_robustness.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False));print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
