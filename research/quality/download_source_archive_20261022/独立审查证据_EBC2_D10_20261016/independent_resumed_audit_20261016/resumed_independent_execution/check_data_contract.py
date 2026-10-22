from pathlib import Path
import json,hashlib,sys,numpy as np,pandas as pd,importlib.metadata as md
R=Path(__import__('os').environ['PRO_PACKAGE']).resolve();OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'src'))
from score_manifest import geometry_hash
import recompute_baseline as base
from b8_models import configs,score
base.initialize()
pairs=json.loads((R/'inputs/fixed_pairs.json').read_text()); pair={x['object_id']:x for x in pairs}
meta=pd.read_csv(R/'inputs/cohort_metadata.csv').set_index('object_id');ledger=pd.read_csv(R/'inputs/eligibility_ledger3152.csv').set_index('object_id');refs=pd.read_csv(R/'inputs/reference_catalog.csv').set_index('target_id')
details=json.loads((R/'inputs/current_difficulty.json').read_text()); diff={d['image_id']:d for d in details['records']};reg=json.loads((R/'MODEL_REGISTRY.json').read_text())
issues=[];checks={}
def ck(name,b):
 checks[name]=bool(b)
 if not b:issues.append(name)
ck('unique_pair_object_ids',len(pair)==len(pairs));ck('pair_ids_exact_metadata',set(pair)==set(meta.index));ck('pair_ids_exact_eligible_ledger',set(pair)==set(ledger.index[ledger.prior_full_score_eligible]));ck('ledger_3152_unique',len(ledger)==3152 and ledger.index.is_unique)
counts={};row_issues=[]
for p in pairs:
 oid=p['object_id'];m=meta.loc[oid];l=ledger.loc[oid];d=diff[p['image_id']];rr=refs.loc[p['reference_id']]
 for k,ok in {
 'answer_hash':geometry_hash(p['answer'])==p['answer_sha256']==m.new_answer_sha256,
 'reference_hash':geometry_hash(p['reference'])==p['reference_sha256']==m.new_reference_sha256,
 'answer_points_hash':geometry_hash(p['answer_points'])==p['answer_points_sha256'],
 'reference_points_hash':geometry_hash(p['reference_points'])==p['reference_points_sha256'],
 'answer_from_erp':geometry_hash(base.engine.geometry(p['answer_points']))==p['answer_sha256'],
 'reference_from_erp':geometry_hash(base.engine.geometry(p['reference_points']))==p['reference_sha256'],
 'ref_catalog_points':p['reference_points']==json.loads(rr.points_1024x512),
 'difficulty':p['difficulty']==d['current_class']==m.difficulty_v6==l.v6_difficulty,
 'difficulty_version':p['difficulty_version']==details['version']==m.difficulty_version_v6,
 'target_binding':p['reference_id']==p['current_target_id']==d['target_version']==m.current_target_id==l.current_target_id,
 'identity':p['image_id']==m.image_id==l.image_id==rr.image_id and p['worker_id']==m.worker_id==l.worker_id and p['condition']==m.condition==l.condition,
 'eligibility':p['original_quality_eligible'] is True and p['reference_complete'] is True and bool(rr.full_reference_available) and bool(d['difficulty_analysis_eligible']) and not bool(d['gt_error_excluded']) and not bool(l.gt_error_excluded) and bool(l.independent_vote_eligible) and not bool(l.target_changed_from_archived_score_audit) and p['worker_id'] not in ['W019','W026'] and p['source_pool_workers']==l.source_pool_workers and p['source_pool_workers']>=3,
 }.items():
  counts[k]=counts.get(k,0)+int(ok)
  if not ok:row_issues.append({'object_id':oid,'check':k})
ck('all_row_contract_checks',not row_issues)
files=json.loads((R/'FILE_HASHES.json').read_text());bad=[]
for f,e in files.items():
 p=R/f
 if p.stat().st_size!=e['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:bad.append(f)
ck('package_FILE_HASHES_correct',not bad)
ck('registry_fixed_pairs_hash',hashlib.sha256((R/'inputs/fixed_pairs.json').read_bytes()).hexdigest()==reg['fixed_pairs_sha256'])
B=pd.read_csv(R/'results/baseline_and_all_B_parameters.csv').set_index('object_id');S=pd.read_csv(R/'results/SCORES_891.csv').set_index('object_id');N=pd.read_csv(R/'results/normalized_scores891.csv').set_index('object_id')
direct=score(B.iou_2d,B.S_bottom_deg,B.dir,B.Hmean,B.Hcenter,configs()[1]);ck('D10_formula_matches',np.max(np.abs(direct-B.B8L2_s32_d10))<1e-12)
calc={}; delta=B.B8L2_s32_d10-B.B8L2_original;T=meta[['image_id','condition','building_id','difficulty_v6','worker_id']].join(B[['B8L2_original','B8L2_s32_d10']]);T['delta']=delta;T['EBC2_L2']=N.score_l2
calc['d10_delta']={'mean':delta.mean(),'median':delta.median(),'min':delta.min(),'max':delta.max(),'gt5':int((delta>5).sum()),'negative':int((delta<0).sum()),'image_equal':T.groupby(['image_id','condition']).delta.mean().mean()}
leave=[T[T.building_id!=b].groupby(['image_id','condition']).delta.mean().mean() for b in T.building_id.unique()];calc['d10_delta']['leave_building_min']=min(leave);calc['d10_delta']['leave_building_max']=max(leave)
calc['difficulty_strata']=[]
for (cond,level),g in T.groupby(['condition','difficulty_v6']):
 calc['difficulty_strata'].append({'condition':cond,'difficulty':level,'annotations':len(g),'images':g.image_id.nunique(),**g.groupby('image_id')[['B8L2_original','B8L2_s32_d10','EBC2_L2']].mean().mean().to_dict()})
old=pd.read_csv(R/'inputs/archived_v4_mainline_quality.csv').set_index('object_id');changed=meta[meta.difficulty_v6!=old.loc[meta.index].difficulty_class]
calc['changed_labels']={'rows':len(changed),'images':changed.image_id.nunique(),'old_new':changed.groupby(['difficulty_class','difficulty_v6']).size().to_dict().__str__()}
ck('scores_primary_equal_B',np.max(np.abs(S.B8L2_original-B.B8L2_original))<1e-12);ck('scores_primary_equal_D10',np.max(np.abs(S.B8L2_s32_d10-B.B8L2_s32_d10))<1e-12);ck('scores_primary_equal_EBC2L2',np.max(np.abs(S.EBC2_L2-N.score_l2))<1e-12)
controls=pd.read_csv(R/'results/controls_all_scores.csv');invalid=controls[controls.EBC2_status!='complete'];ck('invalid_controls_all_NA',len(invalid)==2 and invalid[['B8L2_original','B8L2_s32_d10','EBC2_score_l2']].isna().all().all())
door=json.loads((R/'inputs/doorway_conditional_pairs.json').read_text());ck('doorway_disjoint_main',not (set(p['object_id'] for p in door)&set(pair)));ck('doorway_held',all(p['original_quality_eligible'] is False for p in door))
rev=json.loads((R/'inputs/review24/quality_three_routes_review_20261016_v1.json').read_text())['decisions'];cf=pd.read_csv(R/'results/comment24_all_versions.csv').set_index('case_id');rank={'poor':0,'average_poor':1,'average':2,'good_average':3,'good':4}
ck('comments_verbatim',all(cf.loc[k,'comment']==v['comment'] for k,v in rev.items()))
calc['ordinal']={}
for col in ['B8L2_original','B8L2_s32_d10','EBC2_L2','IoU3D100']:
 inv=ties=total=0
 for i in range(len(cf)):
  for j in range(i):
   a,b=cf.iloc[i],cf.iloc[j]
   if a.grade not in rank or b.grade not in rank or a.grade==b.grade:continue
   z=(rank[a.grade]-rank[b.grade])*(a[col]-b[col]);inv+=int(z<0);ties+=int(abs(z)<1e-10);total+=1
 calc['ordinal'][col]={'total':total,'inversions':inv,'ties':ties}
calc['scope']={'rows':len(pairs),'images':len(set(p['image_id'] for p in pairs)),'workers':len(set(p['worker_id'] for p in pairs)),'conditions':meta.condition.value_counts().to_dict(),'b_pure_parameters':sum(c.family=='parameter_only' for c in configs()),'b_structural_variants':sum(c.family=='structural_loss_variant' for c in configs()),'controls':len(controls),'valid_controls':len(controls)-len(invalid),'doorway_conditional':len(door),'doorway_images':len(set(p['image_id'] for p in door)),'doorway_ring_confirmed':sum(p['ring_confirmed'] for p in door),'source_pool_under3':int((ledger.source_pool_workers<3).sum()),'new_scope_changed_rows':int(ledger.target_changed_from_archived_score_audit.sum()),'camera_outside':int((~N.answer_camera_inside).sum())}
out={'checks':checks,'failed_checks':issues,'per_row_pass_counts':counts,'row_issues':row_issues,'package_hash_errors':bad,'FILE_HASHES_entries':len(files),'statistics':calc,'environment':{'python':sys.version,'packages':{k:md.version(k) for k in ['numpy','pandas','scipy','shapely','pytest']}}}
(OUT/'independent_data_contract.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
