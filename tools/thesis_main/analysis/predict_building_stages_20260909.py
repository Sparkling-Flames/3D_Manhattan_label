"""冻结图像特征和同楼历史的配对留图预测；不根据测试表现选参数。"""
import gzip
import json
import math
import random
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.validate_building_stages_20260909 import OLD, OUT, MODES, weighted_curve, save_json, stage_onset as onset
from tools.thesis_main.analysis.transfer_multibuilding_stability_20260909 import interval_error
from tools.thesis_main.analysis.check_unb_prediction_20260909 import balanced_source, paired_gain_bounds


def neighbor_weights(target, sources, distances):
    if target in sources or not sources or len(set(sources)) != len(sources):
        raise ValueError('target leakage or invalid source identity')
    selected=sorted(sources,key=lambda s:(distances[target,s],s))[:3]
    ds=np.array([distances[target,s] for s in selected])
    if not np.isfinite(ds).all() or (ds<0).any():
        raise ValueError('invalid image distances')
    w=1/np.maximum(ds,1e-6)
    return selected,w/w.sum()


def image_distances(feature):
    x=np.asarray(feature,float)
    if x.ndim!=2 or not np.isfinite(x).all():
        raise ValueError('invalid features')
    norm=np.linalg.norm(x,axis=1,keepdims=True)
    if (norm==0).any():
        raise ValueError('zero feature vector')
    x=x/norm
    return np.sqrt(np.maximum(0,2-2*x@x.T))


def conditional_count(vectors, sources, weights):
    values=[(onset(vectors[s][:,0],vectors[s][:,1])[2],float(w)) for s,w in zip(sources,weights)]
    known=sorted((v,w) for v,w in values if v is not None)
    if not known:
        return np.nan,0
    value,w=map(np.array,zip(*known))
    return float(value[np.searchsorted(np.cumsum(w),w.sum()/2)]),len(known)


def same_linear_prediction(left,right):
    return left.keys()==right.keys() and all(abs(left[k]-right[k])<=1e-12 for k in left)


def make_designs(inventory,risk):
    rows=[]
    for building,g in inventory.groupby('building_id'):
        images=sorted(g.index.tolist()); n=len(images)
        if n<2:
            continue
        bins=pd.qcut(pd.Series({i:risk[i] for i in images}).rank(method='first'),min(3,n),labels=False).to_dict()
        counts=g.common_n.to_dict()
        for fraction in (.5,.6):
            s=max(1,min(n-1,int(n*fraction+.5)))
            if n>=4:
                s=min(s,n-2)
            all_groups=list(combinations(images,s))
            balanced=[src for src in all_groups if balanced_source(src,images,bins,counts)]
            for kind,groups in [('all',all_groups),('balanced',balanced)]:
                rng=random.Random(f'20260909|{building}|{fraction}|{kind}')
                selected=sorted(rng.sample(groups,200)) if len(groups)>200 else groups
                if not selected:
                    raise ValueError('no pre-feature balanced split')
                for fold,src in enumerate(selected):
                    target=sorted(set(images)-set(src))
                    rows.append(dict(building_id=building,fraction=fraction,design=kind,fold=fold,
                        source_n=len(src),target_n=len(target),possible_splits=len(groups),retained_splits=len(selected),
                        source_images_json=json.dumps(src),target_images_json=json.dumps(target)))
    return pd.DataFrame(rows)


def main():
    dest=OUT/'prediction'; dest.mkdir(parents=True,exist_ok=True)
    inv=pd.read_csv(OLD/'comparison/image_support_comparison.csv').set_index('image_id')
    f=pd.read_csv(OUT/'features/image_feature_audit.csv').set_index('image_id')
    cache=np.load(OUT/'features/image_features.npz',allow_pickle=False)
    ids=cache['image_ids'].tolist(); positions={i:p for p,i in enumerate(ids)}
    if set(ids)!=set(inv.index) or set(ids)!=set(f.index):
        raise ValueError('feature and inventory coverage mismatch')
    feature_names=['encoder_2','encoder_4','compressed','refined','shared','legacy_mean_phase0']
    distances={name:image_distances(cache[name]) for name in feature_names}
    risk=f.reindex(ids).d_model_feat_recomputed.to_numpy()
    distances['risk']=abs(risk[:,None]-risk[None,:])
    risk=dict(zip(ids,risk))
    dense=inv[inv.common_n>=16]
    designs=make_designs(dense,risk)
    designs.to_csv(dest/'split_manifest.csv',index=False)
    save_json(dest/'PREDICTION_PLAN.json',dict(status='exploratory_predefined_comparisons',primary_horizon=20,
        secondary='building minimum H plus all55 leave-building-out H19',target='anchor_stage probability bounds',
        configs=['q_0.950','ospa30_t6','hac_q_0.950'],fractions=[.5,.6],split_limit=200,
        balance='marginal risk rank tercile and common person count; never target stability',
        within='source mean or at most3 inverse-distance weighted neighbors',outside='entire target building excluded',
        blend='fixed 0.5 same-building mean + 0.5 outside feature neighbors',
        features=feature_names+['risk'],feature_fit='per-image L2 normalization; no human-label feature selection',
        conditional_count='weighted median of identified source onsets only; report source support and target coverage; supplementary',
        evaluation='legal onset domain and curve scores k2..H-5; mean within target then building; overlapping splits not independent',
        low_n='all N3-7 receive H20 forecasts; no long-horizon ground truth is invented; N0-2 inventory only'))
    curves=pd.read_csv(OUT/'stages/stage_curves.csv.gz')
    curves=curves[curves.kind.eq('anchor_stage')]
    vectors={key:g.sort_values('k')[['lower','upper']].to_numpy() for key,g in curves.groupby(['mode','config','horizon','image_id'])}
    for (mode,config,h,image),v in vectors.items():
        if len(v)!=h-5 or np.any(np.diff(v,axis=0)<-1e-12):
            raise ValueError('incomplete or non-monotone sustained curve')
    onsets={key:onset(v[:,0],v[:,1]) for key,v in vectors.items()}
    rows=[]
    def selection(target,sources,name):
        ix,w=neighbor_weights(positions[target],[positions[s] for s in sources],distances[name])
        return [ids[i] for i in ix],w
    def predictions(target,sources,outside,local,extended=True):
        pred={}
        def add(name,sel,w):
            p=weighted_curve([local[s] for s in sel],w)
            cp,n=conditional_count(local,sel,w)
            norm=np.asarray(w,float)/np.sum(w)
            pred[name]=(p,cp,n,dict(zip(sel,norm)))
        if sources:
            add('building_mean',sources,np.ones(len(sources)))
        add('outside_mean',outside,np.ones(len(outside)))
        names=feature_names+['risk'] if extended else ['shared','risk']
        for name in names:
            os,ow=selection(target,outside,name)
            add('outside_'+name,os,ow)
            if sources:
                ss,sw=selection(target,sources,name)
                add('within_'+name,ss,sw)
                p=.5*pred['building_mean'][0]+.5*pred['outside_'+name][0]
                # Count forecast for a blend follows the actual blend CDF; no ad hoc mixing of medians.
                result=onset(p[:,0],p[:,1])
                coefficients={}
                for source_name in ('building_mean','outside_'+name):
                    for image,weight in pred[source_name][3].items():
                        coefficients[image]=coefficients.get(image,0)+.5*weight
                pred['blend_'+name]=(p,float(result[2]) if result[2] is not None else np.nan,0,coefficients)
        return pred
    def score(meta,target,preds,true,truth):
        baseline_name='building_mean' if 'building_mean' in preds else 'outside_mean'
        baseline=preds[baseline_name][0][1:]
        for model,(p,cp,n,coefficients) in preds.items():
            lo,hi=interval_error(p[1:,0],p[1:,1],true[1:,0],true[1:,1])
            gl,gu=paired_gain_bounds(p[1:],baseline,true[1:])
            identical=same_linear_prediction(coefficients,preds[baseline_name][3])
            if identical:
                gl,gu=np.zeros(len(gl)),np.zeros(len(gu))
            z=onset(p[:,0],p[:,1])
            rows.append(meta|dict(image_id=target,model=model,curve_error_lower=lo.mean(),curve_error_upper=hi.mean(),
                gain_over_base_lower=gl.mean(),gain_over_base_upper=gu.mean(),target_unknown_width=np.mean(true[1:,1]-true[1:,0]),
                target_onset=truth[2],target_status=truth[3],pred_possible=z[0],pred_conservative=z[1],pred_status=z[3],
                count_prediction=cp,identified_source_n=n,identical_linear_prediction_to_base=identical,
                count_error=abs(cp-truth[2]) if truth[2] is not None and np.isfinite(cp) else np.nan))
    for building,dg in designs.groupby('building_id'):
        image_group=dense[dense.building_id.eq(building)]
        horizons=sorted({20,int(image_group.common_n.min())})
        for mode in MODES:
            for config in ('q_0.950','ospa30_t6','hac_q_0.950'):
                for h in horizons:
                    local={i:v for (m,c,H,i),v in vectors.items() if m==mode and c==config and H==h}
                    outside=sorted(i for i in local if inv.loc[i,'building_id']!=building)
                    for d in dg.itertuples():
                        sources=json.loads(d.source_images_json)
                        targets=json.loads(d.target_images_json)
                        meta=dict(experiment='high_split',building_id=building,mode=mode,config=config,horizon=h,
                                  fraction=d.fraction,design=d.design,fold=d.fold,source_n=len(sources))
                        for target in targets:
                            pred=predictions(target,sources,outside,local,extended=(h==20 and config=='q_0.950'))
                            score(meta,target,pred,local[target],onsets[mode,config,h,target])
        print(f'{building}: held-out targets scored; {len(rows)} rows',flush=True)
    # Single-high-image buildings are retained by a separate fully external prediction.
    for mode in MODES:
        for config in ('q_0.950','ospa30_t6','hac_q_0.950'):
            local={i:v for (m,c,h,i),v in vectors.items() if m==mode and c==config and h==19}
            for target in sorted(local):
                building=inv.loc[target,'building_id']; outside=sorted(i for i in local if inv.loc[i,'building_id']!=building)
                score(dict(experiment='all55_lobo',building_id=building,mode=mode,config=config,horizon=19,
                           fraction=0,design='all',fold=0,source_n=len(outside)),target,
                      predictions(target,[],outside,local),local[target],onsets[mode,config,19,target])
    result=pd.DataFrame(rows)
    result.to_csv(dest/'target_predictions.csv.gz',index=False)
    keys=['experiment','mode','config','horizon','fraction','design','model']
    metrics=['curve_error_lower','curve_error_upper','gain_over_base_lower','gain_over_base_upper','target_unknown_width','count_error']
    perimage=result.groupby(keys+['building_id','image_id'],dropna=False).agg(
        **{v:(v,'mean') for v in metrics}, appearances=('image_id','size'), count_appearances=('count_error','count'),
        target_status=('target_status','first'),target_onset=('target_onset','first')).reset_index()
    perimage.to_csv(dest/'per_image_scores.csv',index=False)
    perbuilding=perimage.groupby(keys+['building_id'],dropna=False).agg(
        **{v:(v,'mean') for v in metrics},images=('image_id','nunique'),
        count_targets=('count_error','count'),identified_targets=('target_onset','count'),
        count_appearances=('count_appearances','sum'),target_appearances=('appearances','sum')).reset_index()
    perbuilding.to_csv(dest/'per_building_scores.csv',index=False)
    summaries=[]
    for key,g in perbuilding.groupby(keys,dropna=False):
        summaries.append(dict(zip(keys,key))|{v:g[v].mean() for v in metrics}|dict(buildings=len(g),images=int(g.images.sum()),
            count_targets=int(g.count_targets.sum()),identified_targets=int(g.identified_targets.sum()),
            count_buildings=int(g.count_targets.gt(0).sum()),count_appearances=int(g.count_appearances.sum()),
            target_appearances=int(g.target_appearances.sum()),
            buildings_gain_definitely_positive=int(g.gain_over_base_lower.gt(0).sum()),buildings_gain_definitely_negative=int(g.gain_over_base_upper.lt(0).sum())))
    pd.DataFrame(summaries).to_csv(dest/'prediction_summary.csv',index=False)
    lowrows=[]
    for mode in MODES:
        for config in ('q_0.950','ospa30_t6','hac_q_0.950'):
            local={i:v for (m,c,h,i),v in vectors.items() if m==mode and c==config and h==20}
            for target,row in inv[inv.common_n.between(3,7)].iterrows():
                source=sorted(i for i in local if inv.loc[i,'building_id']==row.building_id)
                outside=sorted(i for i in local if inv.loc[i,'building_id']!=row.building_id)
                for model,(p,cp,n,_weights) in predictions(target,source,outside,local,extended=False).items():
                    z=onset(p[:,0],p[:,1])
                    lowrows.append(dict(image_id=target,building_id=row.building_id,observed_n=row.common_n,
                        mode=mode,config=config,model=model,horizon=20,source_high_n=len(source),
                        pred_possible=z[0],pred_conservative=z[1],pred_status=z[3],conditional_count=cp,
                        identified_source_n=n,evaluation_status='pending_long_horizon_annotations',
                        curve_bounds_json=json.dumps(p.tolist()),source_images_json=json.dumps(source)))
    pd.DataFrame(lowrows).to_csv(dest/'low_n_prospective_predictions.csv.gz',index=False)
    inv.assign(long_horizon_status=np.where(inv.common_n.ge(16),'historical_evaluation',
        np.where(inv.common_n.between(3,7),'prospective_prediction','inventory_only_N0to2'))).to_csv(dest/'all_image_inventory.csv')
    save_json(dest/'PREDICTION_QA.json',dict(status='passed',high_images=55,within_buildings=designs.building_id.nunique(),
        high_split_targets=result.loc[result.experiment.eq('high_split'),'image_id'].nunique(),split_rows=len(designs),
        target_prediction_rows=len(result),low_n_targets=len(inv[inv.common_n.between(3,7)]),
        low_n_buildings=inv[inv.common_n.between(3,7)].building_id.nunique(),inventory_N0to2=int(inv.common_n.le(2).sum()),
        feature_images=len(ids),new_human_validation=False,target_labels_used_in_selection=False,
        supervised_feature_training=False,unknown_as_failure=False,overlapping_folds_independent=False))
    print('prediction complete',flush=True)


if __name__=='__main__':
    main()
