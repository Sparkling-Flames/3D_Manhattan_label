"""Optional small image/model bridge. Predicts finite historical-pool coverage,
NOT future-annotator convergence. No DINO fitting or parameter search.
"""
import numpy as np,pandas as pd,json
from sklearn.linear_model import Ridge
from common import *

def main():
    groups=load_groups();rows,raw=rawdata();feat=pd.read_csv(STUDY/'input/supplement/model_image_features.csv').set_index('image_id')
    corners=['bi_enclosed_corners','bi_extended_corners','hohonet_corners'];allx=[c for c in feat if c!='building']
    targets=[]
    for key,g in groups.items():
        if g['condition']!='manual' or g['N']<19:continue
        ix=[i for i,cid in enumerate(g['ids']) if not raw[cid].get('imputed_point',False)]
        for m,d in g['matrices']['automatic'].items():
            dd=np.asarray(d)[np.ix_(ix,ix)]
            targets.append(dict(key=key,image_id=g['image_id'],code=g['code'],building=g['building'],metric=m,N=len(ix),k=5,target=next_uncovered(dd,5,nominal_cut(m,9)),features_available=g['image_id'] in feat.index))
    tar=save('model_bridge/finite_pool_targets.csv',targets);preds=[]
    for metric,ds in tar.groupby('metric'):
        for building in sorted(ds.building.unique()):
            train=ds[(ds.building!=building)&ds.features_available];test=ds[(ds.building==building)&ds.features_available]
            assert not set(train.building)&set(test.building)
            y=train.target.to_numpy();baseline=float(y.mean())
            for name,columns in [('history_mean',[]),('model_corners',corners),('model_corners_gaps_rotations',allx)]:
                if not columns:estimate=np.full(len(test),baseline)
                else:
                    a=feat.loc[train.image_id,columns].to_numpy(float);b=feat.loc[test.image_id,columns].to_numpy(float)
                    median=np.nanmedian(a,axis=0);median=np.where(np.isfinite(median),median,0);a=np.where(np.isfinite(a),a,median);b=np.where(np.isfinite(b),b,median)
                    mu=a.mean(0);sd=a.std(0);sd[sd<1e-12]=1
                    model=Ridge(alpha=1.).fit((a-mu)/sd,y);estimate=np.clip(model.predict((b-mu)/sd),0,1)
                for r,p in zip(test.itertuples(),estimate):preds.append(dict(metric=metric,model=name,heldout_building=building,image_id=r.image_id,code=r.code,N=r.N,target=r.target,prediction=float(p),absolute_error=abs(float(p)-r.target),squared_error=(float(p)-r.target)**2,train_images=len(train),train_buildings='|'.join(sorted(train.building.unique())),no_target_labels_in_fit=True))
    pr=save('model_bridge/lobo_predictions.csv',preds);summary=[]
    for (metric,model),g in pr.groupby(['metric','model']):
        bm=g.groupby('heldout_building')[['absolute_error','squared_error']].mean();summary.append(dict(metric=metric,model=model,images=len(g),buildings=len(bm),image_equal_MAE=g.absolute_error.mean(),building_equal_MAE=bm.absolute_error.mean(),building_equal_MSE=bm.squared_error.mean()))
    save('model_bridge/lobo_summary.csv',summary)
    registry=source_json('rc2_received/sources/current/study/input/supplement/scene_registry_current.json');manual={g['image_id']:g for g in groups.values() if g['condition']=='manual'};scene=[]
    for g in registry['groups']:
        ids=[x for x in g['image_ids'] if x in manual];high=[x for x in ids if manual[x]['N']>=19]
        scene.append(dict(group=g['review_code'],building=g['building'],source_review_state=g.get('review_state'),source_physical_same=g.get('raw_current',{}).get('physical_same'),registered_images=len(g['image_ids']),current_manual_images=len(ids),current_high_support_manual_images=len(high),image_ids='|'.join(ids),high_support_ids='|'.join(high),independent_room_identity_not_newly_adjudicated=True))
    save('model_bridge/scene_registry_coverage.csv',scene)
    dump('MODEL_BRIDGE_AUDIT.json',dict(optional_extension=True,target='next unrepresented response in the remaining finite historical pool after 5 random distinct people, with no borrowed imputation',prediction_not_future_convergence=True,models=['history_mean','model_corners','model_corners_gaps_rotations'],ridge_alpha=1.,hyperparameter_search=False,train_standardization_and_imputation_only=True,all_target_building_labels_excluded=True,human_difficulty_tags_used=False,new_image_features_trained=False,scene_group_membership_not_redefined=True))
    print(pd.DataFrame(summary).to_string(index=False),flush=True)
if __name__=='__main__':main()
