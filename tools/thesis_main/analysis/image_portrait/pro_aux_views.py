"""Non-geometric supplementary D test using EXISTING predictions of other views.

This never calls geometrically inconsistent joint DA3 output an information fill.
Auxiliaries are exact other camera positions in the fixed same-room folds. They
need not have human labels. Uses only frozen per-image numerical model feedback.
"""
import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait.pro_statistics import building_bootstrap


def register():
    root=OUT/'features';reg=json.loads((root/'registry.json').read_text());cols=reg['B_feedback']['columns'];b=pd.read_csv(OUT/'B/model_feedback.csv').set_index('image_id');rows=[];target=[];aux=[];combined=[];ids=[]
    for f in load(BUNDLE/'evaluation/folds.jsonl.gz'):
        if f['design']!='same_room_leave_view':continue
        image=f['test'][0];others=sorted(f['train']);assert image not in others;assert all(x.split('_')[0]==image.split('_')[0]for x in others)
        if image not in b.index or not others or not all(x in b.index for x in others):raise ValueError('Missing declared auxiliary numeric evidence')
        x=b.loc[image,cols].to_numpy(float);a=b.loc[others,cols].to_numpy(float);ids.append(image);target.append(x);aux.append(a.mean(0));combined.append(np.concatenate([x,a.mean(0),a.std(0),[np.log1p(len(others))]]));rows.append(dict(image_id=image,room_id=f['room_id'],auxiliary_image_ids=';'.join(others),n_auxiliary_camera_positions=len(others),human_outcomes_not_used=True,spatial_registration_claim=False))
    for name,x in [('DX_target_feedback_matched',target),('DX_other_views_feedback_mean',aux),('DX_target_plus_aux_feedback',combined)]:
        x=np.asarray(x);np.savez_compressed(root/(name+'.npz'),image_ids=np.array(ids),X=x);reg[name]=dict(file=name+'.npz',dimensions=x.shape[1],family='D_non_geometric_late_exploration',model='',layer='',pool='',prespecified=False,columns=[],exact_duplicate_of=None,definition='Fixed accepted room relation; target vs other-camera feedback; no human auxiliary outcome and no reconstruction claim')
    write_json(root/'registry.json',reg);write_csv('D/non_geometric_auxiliary_inputs.csv',rows)


def compare():
    source=['DX_target_feedback_matched','DX_other_views_feedback_mean','DX_target_plus_aux_feedback'];a=pd.concat([pd.read_csv(OUT/'prediction'/f'{n}.csv.gz')for n in source],ignore_index=True);rows=[]
    for method in source[1:]:
        for key,g in a[a.feature==method].groupby(['algorithm','condition','target','design']):
            b=a[(a.feature==source[0])&(a.algorithm==key[0])&(a.condition==key[1])&(a.target==key[2])&(a.design==key[3])];z=g.merge(b[['image_id','fold_id','prediction','absolute_error']],on=['image_id','fold_id'],suffixes=('','_base')).dropna(subset=['prediction','prediction_base']);z['delta']=z.absolute_error-z.absolute_error_base;im=z.groupby(['image_id','building'],as_index=False)[['absolute_error','absolute_error_base','delta']].mean();ci=building_bootstrap(im,'delta');rows.append(dict(method=method,baseline=source[0],algorithm=key[0],condition=key[1],target=key[2],design=key[3],n_images=len(im),n_buildings=im.building.nunique(),method_MAE=im.absolute_error.mean(),target_only_MAE=im.absolute_error_base.mean(),delta_MAE=im.delta.mean(),CI_low=ci[0],CI_high=ci[1]))
    write_csv('D/non_geometric_auxiliary_increment.csv',rows)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['register','compare']);a=p.parse_args();register()if a.stage=='register'else compare()
