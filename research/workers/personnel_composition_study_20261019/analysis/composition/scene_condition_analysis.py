"""Post-freeze descriptive room-type stratification of already frozen contrasts.

No worker labels, hypotheses, image types or fusion rules are refit/merged here.
"""
import argparse,json,hashlib
from pathlib import Path
import pandas as pd
from fusion_runner import write

CANONICAL={'H1_Q_quantile':'confirm','H3_reverse_relation':'curves','H4_detail_role':'curves','H5_hard_structure':'curves','H7_conditional_complement':'curves','H8_role_mixture':'confirm','H9_semi_new':'conditions','H10_semi_old_tendency':'conditions','H11_doorway':'conditions'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,default=Path('analysis/composition/frozen_grid_results'));ap.add_argument('--conditions',type=Path,default=Path('analysis/independent/POOL_IMAGE_CONDITIONS.csv'));ap.add_argument('--out',type=Path,default=Path('analysis/composition/scene_analysis'));a=ap.parse_args()
    p=a.results/'frozen_contrasts_per_image.csv.gz';D=pd.read_csv(p);M=pd.read_csv(a.conditions,keep_default_na=False);assert not M.pool_id.duplicated().any()
    D=D[D.apply(lambda r: str(r.stage).startswith(CANONICAL.get(r.rule_id,'NEVER')) and bool(r.primary_contrast),axis=1)].copy()
    cols=['pool_id','room_coarse_type','main_visual_space','expected_annotation_extent']
    D=D.merge(M[[c for c in cols if c in M]],on='pool_id',how='left',validate='many_to_one');D['room_coarse_type']=D.room_coarse_type.fillna('').replace({'':'缺失（未归类）'})
    rows=[]
    for bydiff in [False,True]:
      grouping=['stage','phase','rule_id','contrast_id','method_id','domain','k','composition_a','composition_b','room_coarse_type']+(['difficulty'] if bydiff else [])
      for keys,g in D.groupby(grouping,dropna=False):
        r=dict(zip(grouping,keys));r['difficulty_stratum']=str(r.pop('difficulty')) if bydiff else 'all'
        r.update(paired_images=g.image.nunique(),paired_buildings=g.building.nunique(),scored_images=int(g.B8L2_mean_change.notna().sum()),positive_images=int((g.B8L2_mean_change>0).sum()),negative_images=int((g.B8L2_mean_change<0).sum()),unique_teams_a=int(g.unique_teams_a.sum()),unique_teams_b=int(g.unique_teams_b.sum()),scored_teams_a=int(g.scored_teams_a.sum()),scored_teams_b=int(g.scored_teams_b.sum()),image_ids='|'.join(sorted(g.image.unique())))
        for metric in ['B8L2_mean_change','B8L2_p10_change','D10_mean_change','complete_rate_change','nodes_mean_change','diag_wall_coverage_05_mean_change','diag_corner_recall_05_mean_change','IoU3D100_mean_change']:
          if metric not in g:continue
          b=g.groupby('building')[metric].mean();r[metric+'_building_equal']=b.mean();r[metric+'_image_equal']=g[metric].mean();r[metric+'_valid_images']=int(g[metric].notna().sum());r[metric+'_valid_buildings']=int(b.notna().sum())
        rows.append(r)
    a.out.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(a.out/'room_type_frozen_rule_strata.csv.gz',index=False)
    D[['stage','phase','rule_id','contrast_id','pool_id','image','building','difficulty','room_coarse_type','main_visual_space']].to_csv(a.out/'room_type_contrast_index.csv.gz',index=False)
    write(a.out/'SCENE_ANALYSIS_RECEIPT.json',dict(contrast_input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),condition_input_sha256=hashlib.sha256(a.conditions.read_bytes()).hexdigest(),input_contrasts=len(D),strata=len(rows),coarse_types=sorted(D.room_coarse_type.unique()),classification_refit=False,scene_types_merged=False,interpretation='Additional post-freeze descriptive stratification, not a separately frozen validation hypothesis. Existing review-based room type is not automatically a pre-collection predictor. Original scene flag is OOS/doorway qualification, not room function.'))

if __name__=='__main__':main()
