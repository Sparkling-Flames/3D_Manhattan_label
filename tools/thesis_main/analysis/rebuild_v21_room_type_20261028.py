"""Rebuild room-purpose inputs and refit saved LOBO methods for v2.1."""
import gzip, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.difficulty_mechanisms_v2_20261020 import reference_traits
from tools.thesis_main.analysis.same_room_structure_transfer_20261020 import geometry_features

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/statistics/room_type_similarity_20261027'
RELEASE=ROOT/'research/data/releases/v2.1'
OUT=RELEASE/'room_type_similarity'
FIELDS=['ref_geometry_status','ref_vertices','ref_turn3','ref_turn5','ref_turn10','ref_H','ref_short_edges','ref_short_min_horizontal_deg','ref_min_horizontal_deg','ref_radius_p90_h']
DIAG=['corner_delta','unmatched_ref_9','unmatched_ref_12','bottom_bias_9','omission','extension','log_area_ratio']
SCALARS=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','iou_3d_corner_mean','IoU3D100']

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def build_inputs():
    dest=OUT/'inputs';dest.mkdir(parents=True,exist_ok=True)
    old=pd.read_csv(BASE/'inputs/annotations.csv.gz',dtype={'object_id':str},low_memory=False)
    quality=pd.DataFrame(read(RELEASE/'quality_inventory.json')).set_index('object_id',verify_integrity=True)
    bindings=pd.DataFrame(read(RELEASE/'reference_bindings.json')).set_index('object_id',verify_integrity=True)
    refs={r['target_id']:r for r in read(RELEASE/'reference_catalog.json')}
    oldrefs={r['target_id']:r for r in read(ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
    diff={r['image_id']:r for r in read(RELEASE/'difficulty_records.json')['records']}
    assert old.object_id.is_unique and set(old.object_id)==set(quality.index)==set(bindings.index)
    old=old.set_index('object_id',drop=False); assert (old.image_id==quality.loc[old.index,'image_id']).all()
    geo={}
    with gzip.open(BASE/'inputs/annotation_geometry.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            x=json.loads(line);assert x['object_id'] not in geo;geo[x['object_id']]=x
    assert set(geo)==set(old.index)
    traits={};reused=changed=0
    for oid in old.index:
        q=quality.loc[oid]; b=bindings.loc[oid]; tid=q['reference_id']; eligible=bool(q.quality_usable)
        old.at[oid,'formal_quality']=eligible;old.at[oid,'quality_usable']=eligible;old.at[oid,'quality_use']=q.quality_use
        old.at[oid,'pool_analysis_eligible']=q.pool_analysis_eligible;old.at[oid,'independent_vote_eligible']=b.independent_vote_eligible
        old.at[oid,'layer']='oos' if q.is_oos else ('doorway' if q.quality_use=='doorway_quality' else ('ordinary' if q.quality_use=='ordinary_primary' else 'other_or_hold'))
        old.at[oid,'difficulty']=diff[q.image_id]['current_class']
        old.at[oid,'current_target']=diff[q.image_id].get('target_version')
        old.at[oid,'same_difficulty_target']=bool(tid and tid==diff[q.image_id].get('target_version'))
        old.at[oid,'binding_status']=b.binding_status
        old.at[oid,'reference_id']=tid;old.at[oid,'reference_version']=q.reference_version
        old.at[oid,'reference_full_available']=bool(refs[tid].get('full_reference_available')) if isinstance(tid,str) and tid in refs else False
        old.at[oid,'Q']=q.B8L2 if eligible else np.nan;old.at[oid,'B8L2']=q.B8L2 if eligible else np.nan;old.at[oid,'D10']=q.D10 if eligible else np.nan
        for c in SCALARS:old.at[oid,c]=q.get(c,np.nan) if eligible else np.nan
        if not isinstance(tid,str) or tid not in refs:
            for c in FIELDS+DIAG:old.at[oid,c]=np.nan
            continue
        ref=refs[tid]
        if tid not in traits:traits[tid]=reference_traits(ref['floor_xz_h'])
        for c in FIELDS:old.at[oid,c]=traits[tid].get(c,np.nan)
        t=traits[tid];h=t.get('ref_H');short=t.get('ref_short_edges')
        old.at[oid,'mechanism']='geometry_unknown' if h is None or pd.isna(h) else ('geometric_self_occlusion' if h>0 else ('short_edge_H0' if short>0 else 'plain_H0'))
        old.at[oid,'reference_sample']=bool(old.at[oid,'personal_sample'] and eligible and old.at[oid,'same_difficulty_target'] and pd.notna(t.get('ref_turn5')))
        same=(tid in oldrefs and oldrefs[tid]['points_1024x512']==ref['points_1024x512'] and geo[oid].get('reference_id')==tid)
        if same:reused+=1
        else:
            points=geo[oid].get('points_1024x512'); rp=ref.get('points_1024x512')
            if points and rp and len(points)>=6 and len(points)%2==0:
                z=geometry_features(points,rp)
            else:z={}
            for c in DIAG:old.at[oid,c]=z.get(c,np.nan)
            changed+=1
        old.at[oid,'turn_delta']=old.at[oid,'annotation_turn5']-old.at[oid,'ref_turn5']
        old.at[oid,'actual_simplification']=float(old.at[oid,'turn_delta']<0) if pd.notna(old.at[oid,'turn_delta']) else np.nan
    formal=old[old.formal_quality & old.Q.notna() & old.D10.notna()]
    assert not formal.duplicated(['image_key','worker_id']).any()
    assert (formal.reference_id==bindings.loc[formal.index,'chosen_target_id']).all()
    assert formal.groupby('image_key').reference_id.nunique().le(1).all()
    imgs=[]; refcols=FIELDS
    for key,g in old.groupby('image_key',sort=True):
        q=g[g.formal_quality & g.Q.notna()]; f=q.iloc[0] if len(q) else g.iloc[0]
        row={c:f[c] for c in ['image_key','image','image_code','image_id','building','building_id','condition','room_type','room_type_model','room_type_status','difficulty','is_oos','is_doorway','pool_id','historical_pool_layer','historical_pool_n']}
        row.update(layer='oos' if f.is_oos else ('doorway' if f.is_doorway else ('ordinary' if len(q) and (q.quality_use=='ordinary_primary').all() else 'other_or_hold')),n_records=len(g),n_formal=len(q),n_people=q.worker_id.nunique(),n_reference_ids=q.reference_id.nunique(),reference_id=q.reference_id.iloc[0] if q.reference_id.nunique()==1 else None,reference_version=q.reference_version.iloc[0] if q.reference_version.nunique()==1 else None,mean_Q=q.Q.mean(),median_Q=q.Q.median(),sd_Q=q.Q.std(ddof=1),p10_Q=q.Q.quantile(.1),mean_D10=q.D10.mean(),sd_D10=q.D10.std(ddof=1),low_Q50=(q.Q<50).mean() if len(q) else None,low_Q60=(q.Q<60).mean() if len(q) else None,workers_json=json.dumps(sorted(q.worker_id.unique())),object_ids_json=json.dumps(q.object_id.tolist()))
        for c in refcols:
            vals=q[c].dropna().unique();row[c]=vals[0] if len(vals)==1 else None
        for c in ['annotation_turn5','pair_n','near_straight_nodes_5deg','short_turn_edges','turn_delta','actual_simplification','omission','extension','bottom_bias_9','S_bottom_deg','dir','Hmean','height_mean_ratio','log_area_ratio','unmatched_ref_9','iou_2d']:
            row['mean_'+c]=q[c].mean();row['sd_'+c]=q[c].std(ddof=1);row['n_'+c]=int(q[c].notna().sum())
        imgs.append(row)
    images=pd.DataFrame(imgs);old.to_csv(dest/'annotations.csv.gz',index=False,compression={'method':'gzip','mtime':0});images.to_csv(dest/'images.csv',index=False)
    source=pd.read_csv(BASE/'inputs/annotations.csv.gz',low_memory=False);prev=set(source.loc[(source.condition=='manual')&(source.layer=='ordinary')&source.formal_quality&source.Q.notna()&source.D10.notna(),'image_key'])
    curr=images[(images.condition=='manual')&(images.layer=='ordinary')&(images.n_formal>0)];curr=curr.assign(support=np.where(curr.image_key.isin(prev),'original_support','new_support'));curr[['image_key','image','building','room_type_model','difficulty','n_formal','support']].to_csv(dest/'SUPPORT.csv',index=False)
    receipt=dict(records=len(old),formal_manual_records=len(formal[(formal.condition=='manual')&(formal.layer=='ordinary')]),manual_images=len(curr),manual_buildings=curr.building.nunique(),original_images=sum(curr.support=='original_support'),new_images=sum(curr.support=='new_support'),reference_traits_recomputed=len(traits),reference_diagnostics_reused=reused,reference_diagnostics_recomputed=changed,reference_unbound_or_missing=len(old)-reused-changed,original_geometry_reused=len(geo),no_fusion=True)
    (OUT/'INPUT_CHECKS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt,ensure_ascii=False),flush=True)



def fit_models(mode):
    sys.path.insert(0,str(BASE/'code'))
    inp=OUT/'inputs'
    if mode in ('image','image_prediction'):
        import image_similarity as image
        target=OUT/'results/image';target.mkdir(parents=True,exist_ok=True)
        a,d=image.load(inp)
        if mode=='image':
            image.describe(a,d,target);image.pairs_and_triplets(a,d,target)
        else:
            image.run_predictions(a,d,target);image.run_geometry_portfolio(a,d,target)
            for name in ['PREDICTION_CHECKS.json','ADDITIONAL_GEOMETRY_PORTFOLIO_RECEIPT.json']:
                path=target/name;receipt=read(path);receipt['frozen_script_source_commit']=receipt.pop('source_commit');receipt['data_release']='v2.1';path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    elif mode=='personal':
        import personal
        target=OUT/'results/personal';target.mkdir(parents=True,exist_ok=True)
        d=pd.read_csv(inp/'annotations.csv.gz',dtype={'object_id':str},low_memory=False)
        d=d[(d.condition=='manual')&(d.layer=='ordinary')&d.formal_quality&d.Q.notna()&d.D10.notna()].copy()
        assert not d[['image_key','worker_id']].duplicated().any()
        d['room_type_model']=d.room_type_model.fillna('__MISSING__');d['difficulty']=d.difficulty.fillna('__UNKNOWN__')
        nums=personal.numeric_columns(d);ps=[];hs=[];hyper=None
        for oc in ['Q','D10','annotation_turn5']:
            P,H,alpha=personal.fit_outcome(d[d[oc].notna()],oc,nums,target,hyper_from=hyper if oc=='D10' else None)
            if oc=='Q':hyper=alpha
            ps.append(P);hs.append(H)
        personal.summarize(pd.concat(ps),target);personal.repeatability(pd.concat(ps),pd.concat(hs),target)
        (target/'V21_CHECKS.json').write_text(json.dumps(dict(records=len(d),images=d.image_key.nunique(),buildings=d.building.nunique(),numeric_features=nums,OOF_rows=sum(len(p) for p in ps),D10_uses_Q_selected_alpha=True),indent=2)+'\n',encoding='utf8')
    elif mode=='protected':
        import personal, personal_protected_purpose as protected
        from sklearn.model_selection import GroupKFold
        target=OUT/'results/protected';target.mkdir(parents=True,exist_ok=True)
        d=pd.read_csv(inp/'annotations.csv.gz',dtype={'object_id':str},low_memory=False)
        d=d[(d.condition=='manual')&(d.layer=='ordinary')&d.formal_quality&d.Q.notna()&d.D10.notna()].copy().reset_index(drop=True)
        for oc in ['Q','D10']:d['r_'+oc]=personal.rel_target(d,oc)
        d.room_type_model=d.room_type_model.fillna('__MISSING__')
        folds=[];predictions=[];cvdata=[]
        for held in sorted(d.building.unique()):
            tr=d[d.building!=held];te=d[d.building==held];scores=[]
            for fi,(ii,vi) in enumerate(GroupKFold(n_splits=5).split(tr,groups=tr.building)):
                t=tr.iloc[ii];v=tr.iloc[vi]
                for lam in protected.LAMBDAS:
                    pred,_,_,_,_=protected.predict(t,v,'r_Q',lam)
                    scores.append(dict(held_out_building=held,inner_fold=fi,lambda_value='infinity' if np.isinf(lam) else str(int(lam)),mse=personal.image_mse(v.r_Q,pred,v),images=v.image_key.nunique()))
            cv=pd.DataFrame(scores);avg=cv.groupby('lambda_value').apply(lambda g:np.average(g.mse,weights=g.images),include_groups=False)
            order=['infinity' if np.isinf(x) else str(int(x)) for x in protected.LAMBDAS]
            best=min(order,key=lambda x:avg[x]);lam=np.inf if best=='infinity' else float(best)
            folds.append(dict(held_out_building=held,lambda_value=best,inner_image_mse=avg[best],train_images=tr.image_key.nunique(),target_images=te.image_key.nunique()));cvdata.append(cv)
            for oc in ['Q','D10']:
                pred,base,dev,n,shrink=protected.predict(tr,te,'r_'+oc,lam)
                z=te[['object_id','image_key','image','building','worker_id','room_type_model','room_type_status','difficulty']].copy()
                z['outcome']=oc;z['actual_relative']=te['r_'+oc].to_numpy();z['baseline_prediction']=base;z['purpose_prediction']=pred;z['selected_lambda']=best;z['same_purpose_history_buildings']=n;z['shrinkage_weight']=shrink
                z['baseline_ae']=abs(base-z.actual_relative);z['purpose_ae']=abs(pred-z.actual_relative);z['baseline_se']=(base-z.actual_relative)**2;z['purpose_se']=(pred-z.actual_relative)**2;predictions.append(z)
            print('protected',held,flush=True)
        P=pd.concat(predictions,ignore_index=True)
        checks=[]
        for oc in ['Q','D10']:
            old=pd.read_csv(OUT/f'results/personal/OOF_{oc}.csv.gz',dtype={'object_id':str});old=old[old.method=='person_history'][['object_id','predicted_relative']]
            z=P[P.outcome==oc].merge(old,on='object_id',validate='one_to_one');assert len(z)==len(old)==len(d)
            err=float(abs(z.baseline_prediction-z.predicted_relative).max());assert err<1e-10;checks.append(dict(outcome=oc,rows=len(z),baseline_max_abs_difference=err))
        P.to_csv(target/'PROTECTED_PURPOSE_OOF.csv.gz',index=False,compression={'method':'gzip','mtime':0});pd.DataFrame(folds).to_csv(target/'OUTER_FOLD_LAMBDA.csv',index=False);pd.concat(cvdata).to_csv(target/'INNER_CV.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        (target/'CHECKS.json').write_text(json.dumps(dict(baseline_checks=checks,seed=protected.SEED,lam_candidates=['infinity',64,16,4,1,0],D10_uses_Q_lambda=True),indent=2)+'\n',encoding='utf8')
    elif mode=='protected_summary':
        target=OUT/'results/protected';P=pd.read_csv(target/'PROTECTED_PURPOSE_OOF.csv.gz',dtype={'object_id':str})
        image=P.groupby(['outcome','image_key','image','building','room_type_model','room_type_status','difficulty'],as_index=False).agg(records=('object_id','size'),baseline_mae=('baseline_ae','mean'),purpose_mae=('purpose_ae','mean'),baseline_mse=('baseline_se','mean'),purpose_mse=('purpose_se','mean'),people=('worker_id','nunique'))
        image['mae_gain']=image.baseline_mae-image.purpose_mae;image.to_csv(target/'PER_IMAGE.csv',index=False)
        meta=image[image.outcome.eq('Q')];repeated=set()
        for r in meta.itertuples():
            if r.room_type_status=='recorded_purpose' and ((meta.room_type_model==r.room_type_model)&(meta.building!=r.building)).any():repeated.add(r.image_key)
        rng=np.random.default_rng(2026102704);summaries=[]
        for oc in ['Q','D10']:
            for label,sub in [('all',image[image.outcome==oc]),('recorded_multibuilding',image[(image.outcome==oc)&image.image_key.isin(repeated)])]:
                b=sub.groupby('building').agg(n=('image_key','size'),gain=('mae_gain','sum'),bm=('baseline_mse','sum'),pm=('purpose_mse','sum'));draw=rng.integers(0,len(b),(2000,len(b)));ns=b.n.to_numpy()[draw].sum(1);g=b.gain.to_numpy()[draw].sum(1)/ns
                rmse=np.sqrt(b.bm.to_numpy()[draw].sum(1)/ns)-np.sqrt(b.pm.to_numpy()[draw].sum(1)/ns)
                summaries.append(dict(outcome=oc,support=label,images=len(sub),buildings=sub.building.nunique(),baseline_mae=sub.baseline_mae.mean(),purpose_mae=sub.purpose_mae.mean(),mae_gain=sub.mae_gain.mean(),baseline_rmse=np.sqrt(sub.baseline_mse.mean()),purpose_rmse=np.sqrt(sub.purpose_mse.mean()),mae_gain_boot_lo=np.quantile(g,.025),mae_gain_boot_hi=np.quantile(g,.975),rmse_gain_boot_lo=np.quantile(rmse,.025),rmse_gain_boot_hi=np.quantile(rmse,.975)))
        pd.DataFrame(summaries).to_csv(target/'SUMMARY.csv',index=False)
    elif mode=='summary':
        support=pd.read_csv(inp/'SUPPORT.csv');oldkeys=set(support.loc[support.support=='original_support','image_key']);newkeys=set(support.loc[support.support=='new_support','image_key'])
        images=pd.read_csv(inp/'images.csv');images=images[(images.condition=='manual')&(images.layer=='ordinary')&(images.n_formal>0)]
        repeated=set()
        for row in images.itertuples():
            if row.room_type_status=='recorded_purpose' and ((images.room_type_model==row.room_type_model)&(images.building!=row.building)).any():repeated.add(row.image_key)
        oldsupport=pd.read_csv(BASE/'results/image/LOBO_TARGET_PURPOSE_SUPPORT.csv')
        oldrepeated=set(oldsupport.loc[oldsupport.repeated_recorded_purpose,'image_key'])
        panels=[('original',oldkeys),('original_repeated_v2',oldkeys&oldrepeated),('new',newkeys),('new_repeated_v21',newkeys&repeated),('all',oldkeys|newkeys),('repeated_v21',repeated)]
        out=[]
        for version,source in [('v2',BASE/'results/personal_protected_purpose/PROTECTED_PURPOSE_OOF.csv.gz'),('v2.1',OUT/'results/protected/PROTECTED_PURPOSE_OOF.csv.gz')]:
            p=pd.read_csv(source,dtype={'object_id':str},low_memory=False)
            for metric,g in p.groupby('outcome'):
                for panel,keys in panels:
                    sub=g[g.image_key.isin(keys)]
                    if sub.empty:continue
                    by=sub.groupby(['image_key','building'],as_index=False).agg(baseline=('baseline_ae','mean'),purpose=('purpose_ae','mean'),baseline_mse=('baseline_se','mean'),purpose_mse=('purpose_se','mean'),records=('object_id','size'))
                    out.append(dict(study='protected_person',version=version,metric=metric,panel=panel,images=len(by),buildings=by.building.nunique(),records=len(sub),baseline_mae=by.baseline.mean(),purpose_mae=by.purpose.mean(),gain_mae=(by.baseline-by.purpose).mean(),baseline_rmse=np.sqrt(by.baseline_mse.mean()),purpose_rmse=np.sqrt(by.purpose_mse.mean()),improved_images=int((by.baseline>by.purpose+1e-12).sum())))
        for version,source in [('v2',BASE/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz'),('v2.1',OUT/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz')]:
            p=pd.read_csv(source,low_memory=False)
            for metric in ['Q','D10']:
                for baseline,method in [('geometry_rich','geometry_purpose_rich'),('geometry_history','geometry_history_purpose')]:
                    z=p[p.metric.eq(metric) & p.method.isin([baseline,method])]
                    wide=z.pivot(index=['image_key','building'],columns='method',values='absolute_error').reset_index()
                    for panel,keys in panels:
                        sub=wide[wide.image_key.isin(keys)]
                        if sub.empty:continue
                        out.append(dict(study='image_prediction',comparison=baseline+'__'+method,version=version,metric=metric,panel=panel,images=len(sub),buildings=sub.building.nunique(),baseline_mae=sub[baseline].mean(),purpose_mae=sub[method].mean(),gain_mae=(sub[baseline]-sub[method]).mean(),improved_images=int((sub[baseline]>sub[method]+1e-12).sum())))
        pd.DataFrame(out).to_csv(OUT/'COMPARISON_OLD_NEW_SUPPORT.csv',index=False)
    else:raise ValueError(mode)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['inputs','image','image_prediction','personal','protected','protected_summary','summary'],default='inputs');args=ap.parse_args()
    if args.part=='inputs':build_inputs()
    else:fit_models(args.part)
