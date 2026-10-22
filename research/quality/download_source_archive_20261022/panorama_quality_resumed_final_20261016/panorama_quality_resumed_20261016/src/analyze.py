"""Descriptive comparisons: frozen same-set scores, image equal weights,
common-worker sensitivity, and finite parameter reporting. No fitting to grades.
"""
from pathlib import Path
import json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
 meta=pd.read_csv(ROOT/'inputs/cohort_metadata.csv');b=pd.read_csv(ROOT/'results/baseline_and_all_B_parameters.csv');n=pd.read_csv(ROOT/'results/normalized_scores891.csv');n1=pd.read_csv(ROOT/'results/new_scores891.csv')
 newcols={'score':'EBC2_sum','score_l2':'EBC2_L2','score_no_normals':'EBC2_no_normals_sum','score_range_only':'EBC2_area_height'}
 n=n.rename(columns=newcols)
 nc=['object_id']+list(newcols.values())+['I','boundary_coverage','position_only_coverage','Hmean','Hcenter','answer_boundary_credit','reference_boundary_credit','answer_camera_inside','reference_camera_inside','height_tie_fraction_AG','height_tie_fraction_GA','Hcenter_tie_lower','reference_size_h','EBC2_side075','EBC2_side15','EBC2_angle20','EBC2_angle35','EBC2_half_boundary','EBC2_double_boundary']
 n=n[nc].rename(columns={x:'EBC2_'+x for x in ['I','Hmean','Hcenter']})
 # Keep source and independently recomputed measures explicitly separate.
 d=meta.merge(b,on='object_id',validate='one_to_one',suffixes=('_source','')).merge(n,on='object_id',validate='one_to_one').merge(n1[['object_id','score','score_l2','EBC1_strict','EBC1_soft']].rename(columns={'score':'EBC1_sum','score_l2':'EBC1_L2'}),on='object_id',validate='one_to_one')
 from b8_models import configs
 versions=[c.name for c in configs()]+['IoU3D100','EBC1_sum','EBC1_L2','EBC1_strict','EBC1_soft','EBC2_sum','EBC2_L2','EBC2_no_normals_sum','EBC2_area_height','EBC2_side075','EBC2_side15','EBC2_angle20','EBC2_angle35','EBC2_half_boundary','EBC2_double_boundary']
 d.to_csv(ROOT/'results/same_set_all_versions891.csv',index=False)
 rows=[]
 for (cond,level),g in d.groupby(['condition','difficulty_v6']):
  for version in versions:
   im=g.groupby('image_id')[version].mean()
   rows.append(dict(condition=cond,difficulty=level,version=version,annotations=len(g),images=len(im),workers=g.worker_id.nunique(),annotation_mean=g[version].mean(),image_equal_mean=im.mean(),image_median=im.median(),image_p10=im.quantile(.1),image_p90=im.quantile(.9),annotation_min=g[version].min(),annotation_max=g[version].max()))
 pd.DataFrame(rows).to_csv(ROOT/'results/difficulty_all_versions.csv',index=False)
 # Common workers are selected solely by support: >=2 distinct images in every tier.
 manual=d[d.condition=='manual'];counts=manual.groupby(['worker_id','difficulty_v6']).image_id.nunique().unstack(fill_value=0)
 lv=['简单','中等','困难'];common=counts.index[(counts[lv]>=2).all(axis=1)].tolist();wr=[]
 for v in versions:
  for level in lv:
   a=manual[(manual.worker_id.isin(common))&(manual.difficulty_v6==level)]
   wm=a.groupby('worker_id')[v].mean()
   wr.append(dict(version=v,difficulty=level,common_workers=len(common),images=a.image_id.nunique(),annotations=len(a),worker_equal_mean=wm.mean()))
 counts.to_csv(ROOT/'results/worker_difficulty_support.csv');pd.DataFrame(wr).to_csv(ROOT/'results/common_worker_sensitivity.csv',index=False)
 # Image-cluster bootstrap for descriptive precision only; it is not independent validation.
 rng=np.random.default_rng(20261016);boot=[]
 for cond in ['manual','semi']:
  for level,g in d[d.condition==cond].groupby('difficulty_v6'):
   im=g.groupby('image_id')[versions].mean();arr=im.to_numpy();idx=rng.integers(0,len(arr),size=(2000,len(arr)));means=arr[idx].mean(axis=1)
   for k,v in enumerate(versions):boot.append(dict(condition=cond,difficulty=level,version=v,image_count=len(arr),mean=arr[:,k].mean(),bootstrap_low=np.quantile(means[:,k],.025),bootstrap_high=np.quantile(means[:,k],.975),interpretation='exploratory image-cluster resampling, not independent validation'))
 pd.DataFrame(boot).to_csv(ROOT/'results/image_cluster_bootstrap.csv',index=False)
 # All candidate effect sizes relative to original: no cherry-picked best-only row.
 effects=[]
 for v in versions:
  delta=d[v]-d.B8L2_original;images=d.assign(delta=delta).groupby(['image_id','condition']).delta.mean()
  leave=[]
  for building in d.building_id.unique():
   a=d[d.building_id!=building];leave.append((a[v]-a.B8L2_original).groupby([a.image_id,a.condition]).mean().mean())
  effects.append(dict(version=v,annotations=len(d),mean_delta=delta.mean(),median_delta=delta.median(),image_equal_delta=images.mean(),p10_delta=delta.quantile(.1),p90_delta=delta.quantile(.9),min_delta=delta.min(),max_delta=delta.max(),increased_gt5=int((delta>5).sum()),decreased_gt5=int((delta< -5).sum()),building_delete_image_delta_min=min(leave),building_delete_image_delta_max=max(leave),not_quality_superiority=True))
 pd.DataFrame(effects).to_csv(ROOT/'results/all_candidate_effects.csv',index=False)
 # Raw comments, no grade fitting. Bind by stable ID, never K/N numbering guesses.
 rec=json.loads((ROOT/'inputs/review24/quality_three_routes_review_20261016_v1.json').read_text())['decisions'];case=[]
 indexed=d.set_index('object_id')
 for cid,x in rec.items():
  oid=x['bindings'][0]['object_id'];s=indexed.loc[oid]
  row=dict(case_id=cid,object_id=oid,record_id=x['bindings'][0]['record_id'],image_id=x['bindings'][0]['image_id'],comment=x['comment'],grade=x['grade'],grade_at_first_score_reveal=x.get('grade_at_first_score_reveal'),score_revealed_at=x.get('score_revealed_at'))
  row.update({v:float(s[v]) for v in versions});row.update({k:float(s[k]) for k in ['iou_2d','S_bottom_deg','dir','boundary_coverage','answer_boundary_credit','reference_boundary_credit','Hmean','Hcenter','EBC2_Hmean','EBC2_Hcenter']});case.append(row)
 cf=pd.DataFrame(case);cf.to_csv(ROOT/'results/comment24_all_versions.csv',index=False)
 # Auxiliary order descriptions, no optimizer or thresholds selected on these counts.
 rank={'poor':0,'average_poor':1,'average':2,'good_average':3,'good':4};rr=[]
 for v in versions:
  inv=ties=total=0
  for i in range(len(cf)):
   for j in range(i):
    if cf.grade[i] not in rank or cf.grade[j] not in rank or rank[cf.grade[i]]==rank[cf.grade[j]]:continue
    total+=1;z=(rank[cf.grade[i]]-rank[cf.grade[j]])*(cf[v][i]-cf[v][j]);inv+=z<0;ties+=abs(z)<1e-10
  rr.append(dict(version=v,unequal_grade_relations=total,inversions=int(inv),score_ties=int(ties),role='exposed development auxiliary, relations share observations'))
 pd.DataFrame(rr).to_csv(ROOT/'results/ordinal_auxiliary.csv',index=False)
 # Compare old labels saved with these same rows, not a changed sample.
 old4=pd.read_csv(ROOT/'inputs/archived_v4_mainline_quality.csv')
 old4=old4[['object_id','difficulty_class','current_target_id']].rename(columns={'difficulty_class':'archived_v4_difficulty','current_target_id':'archived_v4_target'})
 joined=d.merge(old4,on='object_id',validate='one_to_one')
 assert len(joined)==len(d)
 assert (joined.current_target_id==joined.archived_v4_target).all()
 changes=joined.loc[joined.archived_v4_difficulty!=joined.difficulty_v6,['image_id','image_code','building_id','archived_v4_difficulty','difficulty_v6','current_target_id']].drop_duplicates()
 changes.to_csv(ROOT/'results/label_changes_same_geometry.csv',index=False)
 # Component response algebra diagnostics. This reports co-response, not independent causes.
 cs=pd.read_csv(ROOT/'results/controls_all_scores.csv');factor=cs[cs.family=='factorial'].copy();factor.to_csv(ROOT/'results/factorial_response.csv',index=False)
 # Hard cases are retained: ranking changes both directions.
 delta=(d.EBC2_L2-d.B8L2_original);largest=d.assign(delta=delta).loc[delta.abs().sort_values(ascending=False).index[:40]]
 largest[['object_id','record_id','image_id','image_code','reference_id','B8L2_original','B8L2_s32_d10','B8L2_s50_d10','EBC2_sum','EBC2_L2','delta','iou_2d','dir','boundary_coverage','Hcenter','EBC2_Hcenter']].to_csv(ROOT/'results/largest_changes40.csv',index=False)
 summary=dict(real_rows=len(d),images=d.image_id.nunique(),common_worker_ids=common,conditions=d.condition.value_counts().to_dict(),difficulty={'manual':manual.groupby('difficulty_v6').agg(annotations=('object_id','size'),images=('image_id','nunique')).to_dict(orient='index')},label_changes_from_archived_source_images=len(changes),no_score_fit_to_grades=True,all_development_material=True)
 (ROOT/'results/comparison_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
