"""D: conditional source-history transfer, not pure target-image prediction.

Same-room uses fixed supported leave-view folds. Cross-building same-scene and
same-main-space sources are kept separate. Same-building is diagnostic only.
All exact neighbor IDs, missing cases and mixed-label room outcomes are retained.
"""
from __future__ import annotations
import collections,itertools
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_predict import load_tasks,Provider,prediction_row


def run():
    metadata=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False).set_index('image_id')
    viewfolds={f['test'][0]:f for f in read(B/'evaluation/folds.jsonl.gz') if f['design']=='same_room_leave_view'}
    reg=read(OUT/'kernels/registry.json');dino=[r['feature'] for r in reg if r['family']=='dinov3']
    # All pre-specified DINO layers/pools, no outer-outcome-selected best neighbor.
    methods=['source_frequency','source_frequency_smooth','source_random_expectation','feedback_counts_nearest',*dino]
    records=[];fail=[]
    for arm,target,q,Y,ordinal in load_tasks():
        q=q.reset_index(drop=True);ids=q.image_id.tolist();meta=metadata.loc[ids].reset_index();provider=Provider(ids)
        for name in dino:provider.load_deep(name)
        building=q.building.to_numpy();labels=Y.sum(1) if ordinal else Y[:,0]
        for j,i in enumerate(ids):
            candidates={}
            if i in viewfolds:candidates['same_room']=np.array([k for k,s in enumerate(ids) if s in set(viewfolds[i]['train'])],int)
            else:candidates['same_room']=np.array([],int)
            different=building!=building[j]
            candidates['same_scene_cross_building']=np.flatnonzero(different & (meta.scene_category.to_numpy()==meta.scene_category.iloc[j]))
            candidates['same_main_cross_building']=np.flatnonzero(different & (meta.main_function_primary.to_numpy()==meta.main_function_primary.iloc[j]))
            candidates['same_building_diagnostic']=np.flatnonzero((building==building[j])&(np.arange(len(ids))!=j))
            for design,tr0 in candidates.items():
                room_id=viewfolds.get(i,{}).get('room_id','') if design=='same_room' else ''
                room_mixed=bool(np.unique(labels[np.r_[tr0,j]]).size>1) if ordinal and len(tr0) else None
                for method in methods:
                    tr=tr0.copy();neighbor='';distance=np.nan
                    if method in dino:
                        good=provider.valid(method);tr=tr[good[tr]]
                        if not good[j]:tr=np.array([],int)
                    elif method=='feedback_counts_nearest':tr=tr[provider.valid('feedback_counts')[tr]]
                    if not len(tr):
                        fail.append(dict(image_id=i,condition=arm,target=target,design=design,method=method,room_id=room_id,status='no_available_source_history_or_target_features',source_candidates_before_feature_check=len(tr0)))
                        continue
                    if method.startswith('source_'):
                        pred=Y[tr].mean(0) if ordinal else np.median(Y[tr],axis=0)
                        if ordinal and method=='source_frequency_smooth':
                            counts=np.bincount(labels[tr].astype(int),minlength=3)+.5;prob=counts/counts.sum();pred=np.array([prob[1:].sum(),prob[2]])
                        if not ordinal and method=='source_random_expectation':pred=Y[tr].mean(0)
                        if method=='source_random_expectation':
                            losses=np.mean((Y[tr]-Y[j])**2,axis=1) if ordinal else np.mean(np.abs(Y[tr]-Y[j]),axis=1)
                            expected_loss=float(losses.mean())
                    else:
                        if method in dino:
                            K=provider.load_deep(method);similarity=K[j,tr];chosen=tr[np.argmax(similarity)];distance=float(1-K[j,chosen])
                        else:
                            if not provider.valid('feedback_counts')[j]:
                                fail.append(dict(image_id=i,condition=arm,target=target,design=design,method=method,status='target_feedback_missing'));continue
                            K=provider.kernel('feedback_counts',tr);ds=K[j,j]+np.diag(K)[tr]-2*K[j,tr];chosen=tr[np.argmin(ds)];distance=float(ds.min())
                        neighbor=ids[chosen];pred=Y[chosen].copy()
                    row=prediction_row(arm,target,method,'conditional_transfer',q,j,Y[j],pred,ordinal,n_train=len(tr),source_images=';'.join(ids[k] for k in tr),neighbor_image_id=neighbor,neighbor_distance=distance,source_history_condition=arm,room_id=room_id,mixed_label_room=room_mixed,information_condition='source image human histories observed; target human outcome held out',relation_limit='same building is not proof of same or different physical room' if design=='same_building_diagnostic' else '')
                    row['design']=design
                    if method=='source_random_expectation':
                        row['loss']=expected_loss
                        if ordinal:row['correct']=float(np.mean(labels[tr]==labels[j]))
                        row['probability_interpretation']='expected loss of random actual source, not loss of mean prediction'
                    records.append(row)
        print('TRANSFER',arm,target,'rows',len(records),flush=True)
    out=csv('D/conditional_predictions_with_neighbors.csv.gz',records);csv('D/conditional_missing_and_failures.csv.gz',fail)
    summaries=[]
    for key,g in out.groupby(['condition','target','design','feature']):
        for subset in ['all','mixed_rooms','uniform_rooms']:
            if subset!='all' and (key[2]!='same_room' or key[1]!='tier_primary'):continue
            d=g if subset=='all' else g[g.mixed_label_room.eq(subset=='mixed_rooms')]
            if not len(d):continue
            row=dict(zip(['condition','target','design','method'],key),subset=subset,images=d.image_id.nunique(),buildings=d.building.nunique(),rooms=d.room_id.nunique() if key[2]=='same_room' else 0,image_loss=d.loss.mean(),building_macro_loss=d.groupby('building').loss.mean().mean(),room_macro_loss=d.groupby('room_id').loss.mean().mean() if key[2]=='same_room' else np.nan,accuracy=d.correct.mean() if 'correct' in d and key[1]=='tier_primary' else np.nan)
            summaries.append(row)
    csv('D/conditional_transfer_summary.csv',summaries)
    contrasts=[]
    for key,g in out.groupby(['condition','target','design']):
        base=g[g.feature=='source_frequency'][['image_id','building','loss','mixed_label_room']]
        for method,z in g.groupby('feature'):
            if method=='source_frequency':continue
            p=z[['image_id','building','loss']].merge(base,on=['image_id','building'],suffixes=('_new','_base'));p['delta']=p.loss_new-p.loss_base
            contrasts.append(dict(condition=key[0],target=key[1],design=key[2],method=method,baseline='source_frequency',**paired_ci(p,'delta')))
    csv('D/conditional_paired_comparisons.csv',contrasts)
    same=out[(out.design=='same_room')&out.target.eq('tier_primary')]
    csv('D/mixed_room_actual_neighbors.csv',same[same.mixed_label_room.eq(True)])
    js('D/executed_summary.json',dict(prediction_rows=len(out),missing_rows=len(fail),same_room_tier_images=same.image_id.nunique(),same_room_tier_components=same.room_id.nunique(),dino_candidates=len(dino),all_neighbor_ids_recorded=True,source_history_not_pure_image=True,known_da3_bad_cameras_not_used=True,same_building_never_called_similar_scene=True))
    print(pd.DataFrame(summaries).query("method in ['source_frequency','dinov3__block3__panorama_global','dinov3__block12__panorama_global','dinov3__cls__panorama']").to_string(index=False),flush=True)

if __name__=='__main__':run()
