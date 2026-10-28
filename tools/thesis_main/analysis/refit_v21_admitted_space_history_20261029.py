"""仅在独立扩展目录接续质量历史与融合响应分类，保留原范围模型。"""
import argparse
import numpy as np
import pandas as pd
from .extend_v21_admitted_spaces_20261029 import OUT, TARGET, read, save


def joint():
    from . import refit_v21_joint_history_20261028 as native
    original=read(OUT/'quality_inventory.json'); additions={r['object_id']:r for r in read(TARGET/'ANALYSIS_RECORDS.json')}
    combined=[]
    for r in original:
        r=r.copy()
        if r['object_id'] in additions:
            a=additions[r['object_id']]
            for field in ['quality_usable','quality_use','B8L2','D10']:r[field]=a[field]
        combined.append(r)
    original_read=native.read
    native.read=lambda path: combined if path==OUT/'quality_inventory.json' else original_read(path)
    native.TARGET=TARGET/'joint_history_classification'
    native.main()
    save('joint_history_classification/EXTENSION_SCOPE.json',dict(quality_additions=231,existing_behavior_filter_additions=228,original_behavior_features_frozen=True,peer_key=['condition','layer','image_id','reference_id'],original_models_preserved=True,difficulty='no new difficulty labels; original frozen behavior/context inputs retained'))


def fusion():
    from . import refit_v21_fusion_roles_20261028 as native
    prep,_=native.modules()
    original=pd.read_csv(OUT/'fusion_role_classification/NATURAL_TRAINING_ENDPOINTS.csv.gz',low_memory=False)
    parts=[]
    for path in sorted((TARGET/'natural_inputs').glob('*.csv.gz')):
        d=pd.read_csv(path,low_memory=False)
        d=d[d.condition.eq('manual') & d.layer.eq('ordinary_manual') & d.path_index.lt(24) & d.k.isin(prep.NS)].copy()
        if d.empty:continue
        count=d.groupby('team_key').agg(path_occurrences=('path_id','size'),natural_path_n=('path_id','nunique'))
        d=d.drop_duplicates('team_key').merge(count,on='team_key',validate='one_to_one')
        d['iou2d100']=100*d.iou_2d
        d['log_floor_area']=np.log(d.floor_area_camera_h2.where(d.floor_area_camera_h2.gt(0)))
        d['log_height_mean']=np.log(d.height_mean_h.where(d.height_mean_h.gt(0)))
        d['support_origin']='other_admitted_target';parts.append(d)
    added=pd.concat(parts,ignore_index=True)
    full=pd.concat([original,added],ignore_index=True);assert full.team_key.is_unique
    full['group_id']=full.pool_id+'__n'+full.k.astype(str)
    full['group_unique_teams']=full.groupby('group_id').team_key.transform('size')
    full['complete_model_outputs']=full[prep.GEOM+prep.QUALITY].notna().all(axis=1)
    full['training_eligible']=full.complete_model_outputs & full.group_unique_teams.ge(4)
    full['fusion_failure']=~full.score_available.astype(bool);full['raw_mc_weight']=full.path_occurrences
    native.TARGET=TARGET/'fusion_role_classification';native.TARGET.mkdir(exist_ok=True)
    full.to_csv(native.TARGET/'NATURAL_TRAINING_ENDPOINTS.csv.gz',index=False)
    save('fusion_role_classification/INPUT_CHECKS.json',dict(original_rows=len(original),added_rows=len(added),added_pools=int(added.pool_id.nunique()),paths_per_pool=24,team_sizes=prep.NS,grouping='same target pool and team size',difficulty='ungraded, not used as transferred target difficulty',original_models_preserved=True))
    native.fit()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('family',choices=['joint','fusion']);args=ap.parse_args()
    joint() if args.family=='joint' else fusion()


if __name__=='__main__':main()
