"""Predict actual fixed-background replacement impact on unseen buildings."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from cluster_transfer import DIFF

HERE=Path(__file__).resolve().parent;FUSION=HERE.parent/'fusion';PROFILES=HERE.parent/'profiles';SEED=2026101941

def profile_lookup(outer,fold,nested,buildings):
    out={}
    for b in buildings:
        p=fold[fold.heldout_building.eq(outer)] if b==outer else nested[nested.outer_heldout_building.eq(outer)&nested.inner_heldout_building.eq(b)]
        assert len(p)==60
        out[b]=p.set_index('worker_id').to_dict('index')
    return out

def worker_traits(p,d):
    q=p['Q_effect_B8L2'] if p['Q_supported'] else np.nan
    t=p['T_source_effect'] if p['T_source_supported'] else np.nan
    delta=p['theta_'+d+'_B8L2']-q if p.get('difficulty_supported_'+d,False) else np.nan
    return np.asarray([q,t,delta],float)

def task_weights(d):
    nb=d.building_id.nunique();ni=d.pool_id.nunique()
    images_b=d[['building_id','pool_id']].drop_duplicates().groupby('building_id').size()
    k_i=d[['pool_id','k']].drop_duplicates().groupby('pool_id').size()
    bg_ik=d[['pool_id','k','background_id']].drop_duplicates().groupby(['pool_id','k']).size()
    pairs_bg=d.groupby('background_id').size()
    return np.asarray([ni/(nb*images_b[b]*k_i[p]*bg_ik[p,k]*pairs_bg[bg]) for b,p,k,bg in zip(d.building_id,d.pool_id,d.k,d.background_id)])

def build_features(d,lookup,label_map,pair_geometry):
    # At most 22*60*3 trait vectors per outer split; vectorized row lookup follows.
    workers=sorted(set(d.entrant_a)|set(d.entrant_b));blds=sorted(d.building_id.unique());diffs=['easy','medium','hard']
    table=[]
    for b in blds:
        for w in workers:
            for difficulty in diffs:
                vals=worker_traits(lookup[b][w],difficulty)
                table.append(dict(building_id=b,worker=w,diff=difficulty,q=vals[0],t=vals[1],delta=vals[2]))
    t=pd.DataFrame(table)
    base=d[['building_id','entrant_a','entrant_b','difficulty']].copy();base['diff']=base.difficulty.map(DIFF)
    aa=base.merge(t,left_on=['building_id','entrant_a','diff'],right_on=['building_id','worker','diff'],how='left',validate='many_to_one')
    bb=base.merge(t,left_on=['building_id','entrant_b','diff'],right_on=['building_id','worker','diff'],how='left',validate='many_to_one')
    x=pd.DataFrame(index=d.index)
    for k in [12,16,24]:x['k_'+str(k)]=d.k.eq(k).astype(float)
    x['difficulty_medium']=base['diff'].eq('medium').to_numpy(float);x['difficulty_hard']=base['diff'].eq('hard').to_numpy(float)
    for v in ['q','t','delta']:
        x[v+'_mean']=(aa[v].to_numpy()+bb[v].to_numpy())/2;x[v+'_absdiff']=abs(aa[v].to_numpy()-bb[v].to_numpy())
    bg={}
    for row in d[['background_id','background_workers','building_id','difficulty']].drop_duplicates('background_id').itertuples():
        people=row.background_workers.split('|');a=np.asarray([worker_traits(lookup[row.building_id][w],DIFF[row.difficulty]) for w in people])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            mean=np.nanmean(a,axis=0);sd=np.nanstd(a,axis=0)
        bg[row.background_id]=np.r_[mean,sd,np.isfinite(a).mean(axis=0)]
    a=np.asarray([bg[x] for x in d.background_id])
    for i,v in enumerate(['q','t','delta']):x['background_'+v+'_mean']=a[:,i];x['background_'+v+'_sd']=a[:,i+3];x['background_'+v+'_coverage']=a[:,i+6]
    for cut in [9,12]:
        flags=[];mins=[];maxs=[]
        bgcounts={}
        for row in d[['pool_id','background_id','background_workers']].drop_duplicates('background_id').itertuples():
            people=row.background_workers.split('|');bgcounts[row.background_id]=collections.Counter(label_map[row.pool_id,cut,w] for w in people)
        for pid,wa,wb,bid,k in zip(d.pool_id,d.entrant_a,d.entrant_b,d.background_id,d.k):
            ca,cb=label_map[pid,cut,wa],label_map[pid,cut,wb];cc=bgcounts[bid]
            pa,pb=cc[ca]/(k-1),cc[cb]/(k-1);flags.append(ca==cb);mins.append(min(pa,pb));maxs.append(max(pa,pb))
        x[f'cluster{cut}_same']=np.asarray(flags,float);x[f'cluster{cut}_background_min_share']=mins;x[f'cluster{cut}_background_max_share']=maxs
    geom=np.asarray([pair_geometry[pid,wa,wb] for pid,wa,wb in zip(d.pool_id,d.entrant_a,d.entrant_b)],float)
    x['raw_endpoint_log1p_deg']=np.log1p(geom[:,0]);x['raw_floor_disagreement']=geom[:,1];x['different_point_count']=geom[:,2]
    return x

def cols(model):
    base=['k_12','k_16','k_24','difficulty_medium','difficulty_hard'];features=[]
    if model=='known_task':return base
    if model in ['Q','QT','QTD','QTD_actual_cluster_9']:
        traits=['q']+(['t'] if model in ['QT','QTD','QTD_actual_cluster_9'] else [])+(['delta'] if model in ['QTD','QTD_actual_cluster_9'] else [])
        for v in traits:features.extend([v+'_mean',v+'_absdiff','background_'+v+'_mean','background_'+v+'_sd','background_'+v+'_coverage'])
    if model in ['actual_cluster_9','actual_cluster_12','QTD_actual_cluster_9']:
        cut=12 if model=='actual_cluster_12' else 9;features.extend([f'cluster{cut}_same',f'cluster{cut}_background_min_share',f'cluster{cut}_background_max_share'])
    if model=='raw_pair_geometry':features.extend(['raw_endpoint_log1p_deg','raw_floor_disagreement','different_point_count'])
    return base+features

def fit_predict(xtr,xte,y,w,bounds):
    a,b=xtr.to_numpy(float),xte.to_numpy(float);ma=~np.isfinite(a);mb=~np.isfinite(b)
    with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);med=np.nanmedian(a,axis=0)
    keep=np.isfinite(med)
    # Entirely unsupported numerical columns are removed rather than assigned a value.
    a=np.column_stack([np.where(ma[:,keep],med[keep],a[:,keep]),ma.astype(float)])
    b=np.column_stack([np.where(mb[:,keep],med[keep],b[:,keep]),mb.astype(float)])
    scaler=StandardScaler();a=scaler.fit_transform(a,sample_weight=w);b=scaler.transform(b)
    model=Ridge(alpha=1.);model.fit(a,y,sample_weight=w)
    return np.clip(model.predict(b),*bounds)

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--pilot',action='store_true');ap.add_argument('--input',type=Path,default=FUSION/'INITIAL_replacements.csv.gz');ap.add_argument('--repair-folds',default='');args=ap.parse_args()
    out=HERE/('swap_transfer_pilot' if args.pilot else 'swap_transfer');out.mkdir(exist_ok=True)
    keep=['pool_id','image_id','image','building','difficulty','layer','k','background_id','background_draw_id','background_workers',
          'entrant_a','entrant_b','team_id_a','team_id_b','abs_B8L2_change','floor_jaccard_difference','joint_geometric_stable','both_complete']
    d=pd.read_csv(args.input,usecols=keep);d=d[d.layer.eq('ordinary_manual')].copy()
    if args.pilot:
        pilot=set(json.loads((FUSION/'DESIGN.json').read_text())['pilot_pool_ids']);d=d[d.pool_id.isin(pilot)]
    d['event_key']=[pid+'|'+a+'|'+b if a<=b else pid+'|'+b+'|'+a for pid,a,b in zip(d.pool_id,d.team_id_a,d.team_id_b)]
    d=d.drop_duplicates('event_key').reset_index(drop=True);d['building_id']=d.building;d['image_code']=d.image
    fold=pd.read_csv(PROFILES/'fold_profiles.csv');nested=pd.read_csv(PROFILES/'nested_fold_features.csv')
    labels=pd.read_csv(HERE/'assignments.csv');labels=labels[labels.method.eq('affinity') & labels.layer.eq('ordinary_manual')]
    label_map={(r.pool_id,int(r.threshold_deg),r.worker_id):r.local_cluster_id for r in labels.itertuples()}
    pair=pd.read_csv(HERE/'pair_distances.csv.gz');pair=pair[pair.layer.eq('ordinary_manual')]
    pair_geometry={}
    for r in pair.itertuples():
        v=[r.distance_deg,1-r.floor_iou,int(not r.available)]
        pair_geometry[r.pool_id,r.worker_id_a,r.worker_id_b]=v;pair_geometry[r.pool_id,r.worker_id_b,r.worker_id_a]=v
    models=['known_task','Q','QT','QTD','actual_cluster_9','actual_cluster_12','QTD_actual_cluster_9','raw_pair_geometry']
    outcomes={'abs_B8L2_change':(0,100),'floor_jaccard_difference':(0,1),'joint_geometric_stable':(0,1)}
    scores=[];foldcoverage=[];prediction_paths=[]
    with threadpool_limits(limits=1):
        for outer in sorted(d.building_id.unique()):
            if args.repair_folds and outer not in set(args.repair_folds.split(',')):continue
            lookup=profile_lookup(outer,fold,nested,d.building_id.unique());x=build_features(d,lookup,label_map,pair_geometry)
            train=d.building_id.ne(outer);test=~train;foldpred=[]
            for outcome,bounds in outcomes.items():
                observed=d[outcome].notna();tr=train & observed;te=test & observed
                y=d.loc[tr,outcome].to_numpy(float);w=task_weights(d.loc[tr]);actual=d.loc[te,outcome].to_numpy(float)
                z=d.loc[te,['event_key','pool_id','image_id','image_code','building_id','difficulty','k','background_id','entrant_a','entrant_b']].copy();z['outcome']=outcome;z['actual']=actual
                foldcoverage.append(dict(heldout_building=outer,outcome=outcome,train_examples=int(tr.sum()),test_attempts=int(test.sum()),test_observed=int(te.sum()),test_unavailable=int((test & ~observed).sum()),
                    train_images=d.loc[tr,'pool_id'].nunique(),test_images=d.loc[test,'pool_id'].nunique(),nested_features=True))
                for model in models:
                    prediction=fit_predict(x.loc[tr,cols(model)],x.loc[te,cols(model)],y,w,bounds)
                    zz=z.copy();zz['model']=model;zz['prediction']=prediction;zz['squared_error']=(prediction-actual)**2;zz['absolute_error']=abs(prediction-actual)
                    zz['information']='prospective_historical_features' if model in ['known_task','Q','QT','QTD'] else 'target_annotation_oracle'
                    foldpred.append(zz)
                    bg=zz.groupby(['pool_id','image_id','image_code','building_id','difficulty','k','background_id'])[['squared_error','absolute_error']].mean().reset_index()
                    image=bg.groupby(['pool_id','image_id','image_code','building_id','difficulty','k'])[['squared_error','absolute_error']].mean().reset_index();image['model']=model;image['outcome']=outcome;image['n']=zz.groupby(['pool_id','k']).size().reindex(pd.MultiIndex.from_frame(image[['pool_id','k']])).to_numpy()
                    scores.append(image)
            path=out/(outer+'_predictions.csv.gz');temporary=path.with_suffix('.gz.tmp')
            with gzip.open(temporary,'wt',encoding='utf-8',newline='') as f:pd.concat(foldpred,ignore_index=True).to_csv(f,index=False)
            with gzip.open(temporary,'rb') as f:
                while f.read(1024*1024):pass
            temporary.replace(path);prediction_paths.append(path.name)
            print(json.dumps(dict(heldout_building=outer,test_replacement_pairs=int(test.sum()),models=len(models),outcomes=len(outcomes))),flush=True)
    if args.repair_folds:
        fresh=pd.concat(scores,ignore_index=True);saved=pd.read_csv(out/'image_k_scores.csv');keys=['pool_id','k','model','outcome']
        paired=fresh.merge(saved,on=keys,suffixes=('_replayed','_original'),validate='one_to_one')
        assert len(paired)==len(fresh)
        differences={m:float((paired[m+'_replayed']-paired[m+'_original']).abs().max()) for m in ['squared_error','absolute_error','n']}
        assert all(v<1e-10 for v in differences.values()),differences
        recovery=dict(repaired_folds=args.repair_folds.split(','),prediction_files=prediction_paths,
            all_predictions_recomputed_same_registered_models=True,summary_image_k_rows_checked=len(paired),
            max_absolute_difference_from_initial_in_memory_scores=differences,atomic_gzip_readback=True)
        (out/'PREDICTION_REPAIR_RECEIPT.json').write_text(json.dumps(recovery,indent=2)+'\n');print(json.dumps(recovery,indent=2));return
    image=pd.concat(scores,ignore_index=True);image.to_csv(out/'image_k_scores.csv',index=False)
    sums=[];comps=[];rng=np.random.default_rng(SEED)
    for outcome,g in image.groupby('outcome'):
        for k in ['all',8,12,16,24]:
            h=g if k=='all' else g[g.k.eq(k)]
            by_image=h.groupby(['building_id','pool_id','model'])[['squared_error','absolute_error']].mean().reset_index()
            building=by_image.groupby(['building_id','model'])[['squared_error','absolute_error']].mean().reset_index()
            for model,b in building.groupby('model'):
                arr=b.squared_error.to_numpy();sim=rng.choice(arr,(3000,len(arr)),replace=True).mean(1)
                sums.append(dict(outcome=outcome,k=k,model=model,images=h[h.model.eq(model)].pool_id.nunique(),buildings=len(b),
                    MSE=arr.mean(),RMSE=np.sqrt(arr.mean()),MAE=b.absolute_error.mean(),low=np.quantile(sim,.025),high=np.quantile(sim,.975)))
            wide=building.pivot(index='building_id',columns='model',values='squared_error')
            for model,base in [(m,'known_task') for m in models if m!='known_task']+[('QTD','QT'),('QTD_actual_cluster_9','QTD'),('QTD_actual_cluster_9','actual_cluster_9')]:
                delta=(wide[model]-wide[base]).dropna();sim=rng.choice(delta.to_numpy(),(3000,len(delta)),replace=True).mean(1)
                comps.append(dict(outcome=outcome,k=k,model=model,baseline=base,buildings=len(delta),delta_MSE=delta.mean(),low=np.quantile(sim,.025),high=np.quantile(sim,.975),
                    improved_buildings=int((delta<0).sum()),worse_buildings=int((delta>0).sum())))
    pd.DataFrame(sums).to_csv(out/'summary.csv',index=False);pd.DataFrame(comps).to_csv(out/'paired_comparisons.csv',index=False)
    pd.DataFrame(foldcoverage).to_csv(out/'fold_coverage.csv',index=False)
    receipt=dict(stage='pilot_interface_check' if args.pilot else 'full_available_registered_replacements',images=d.pool_id.nunique(),buildings=d.building_id.nunique(),
        distinct_actual_replacement_pairs=len(d),all_attempts_joint_stability=True,quality_and_floor_missing_not_imputed=True,
        double_excluded_worker_features=True,targets_use_actual_fusion_not_worker_Q=True,prospective_oracle_separated=True,
        registration_sha256=hashlib.sha256((HERE/'SWAP_TRANSFER_REGISTRATION.json').read_bytes()).hexdigest(),
        input_file=str(args.input),input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),predictions=prediction_paths)
    (out/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
