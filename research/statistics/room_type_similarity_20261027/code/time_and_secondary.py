#!/usr/bin/env python3
"""Actual time-source-specific descriptive and LOBO analyses; no clock mixing."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd

SEED=2026102703
def mean_image(x,col):return x.groupby('image_key')[col].mean().mean()

def fit_predict(tr,te,alpha):
    # One image per observed worker, with independent source kind fitted separately.
    g=tr.groupby('worker_id').relative_log_time.agg(['sum','count'])
    general=(g['sum']/(g['count']+2)).to_dict()
    baseline=tr.worker_id.map(general).fillna(0)
    z=tr.assign(residual=tr.relative_log_time-baseline).groupby(['worker_id','room_type_model']).residual.agg(['sum','count'])
    extra=(z['sum']/(z['count']+alpha)).to_dict() if np.isfinite(alpha) else {}
    b=te.worker_id.map(general).fillna(0).to_numpy()
    p=b+np.array([extra.get((w,t),0) if t not in ['__MISSING__','无法判断','开放复合空间'] else 0 for w,t in zip(te.worker_id,te.room_type_model)])
    # Person predictions are on the same peer-relative scale, using known target roster only.
    q=te[['image_key','worker_id']].copy();q['p']=p;q['b']=b
    for col in ['p','b']:
        size=q.groupby('image_key')[col].transform('size');sm=q.groupby('image_key')[col].transform('sum')
        q[col]=(q[col]*size-sm)/(size-1)
    return q.b.to_numpy(),q.p.to_numpy()

def bootstrap_buildings(d,col,R=2000):
    x=d.groupby(['building','image_key'])[col].mean().reset_index()
    b=x.groupby('building')[col].agg(['sum','count'])
    rng=np.random.default_rng(SEED);ids=rng.integers(0,len(b),(R,len(b)))
    v=b['sum'].to_numpy()[ids].sum(1)/b['count'].to_numpy()[ids].sum(1)
    return np.quantile(v,[.025,.975]).tolist()

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();b=a.base;o=b/'results/time_secondary';o.mkdir(exist_ok=True,parents=True)
    d=pd.read_csv(b/'inputs/annotations.csv.gz',low_memory=False);im=pd.read_csv(b/'inputs/images.csv')
    use=d[(d.condition=='manual')&(d.layer=='ordinary')&d.formal_quality&d.time_positive].copy()
    allowed={'inherited_v1_audited_source':'usable','user_processed_reported_not_raw_log_replayed':'reported_processed'}
    use=use[[allowed.get(s)==v for s,v in zip(use.time_source,use.time_source_status)]].copy()
    coverage=[];des=[];preds=[];folds=[]
    for source,g in use.groupby('time_source'):
        coverage.append({'time_source':source,'records':len(g),'images':g.image.nunique(),'buildings':g.building.nunique(),'people':g.worker_id.nunique()})
        for (purpose,difficulty),q in g.groupby(['room_type_model','difficulty']):
            pi=q.groupby(['image_key','building']).agg(n=('object_id','size'),mean_log_time=('log_time','mean'),median_seconds=('source_time_seconds','median'),mean_Q=('Q','mean')).reset_index()
            des.append({'time_source':source,'room_type':purpose,'difficulty':difficulty,'records':len(q),'images':len(pi),'buildings':q.building.nunique(),'people':q.worker_id.nunique(),'image_equal_geomean_seconds':np.exp(pi.mean_log_time.mean()),'mean_image_median_seconds':pi.median_seconds.mean(),'Q_on_same_support':pi.mean_Q.mean()})
        n=g.groupby('image_key').log_time.transform('count');s=g.groupby('image_key').log_time.transform('sum')
        g['relative_log_time']=g.log_time-(s-g.log_time)/(n-1)
        g=g[(n>=3)&g.relative_log_time.notna()].copy()
        # Finite inner-building calibration, including the no-purpose option.
        for held in sorted(g.building.unique()):
            tr=g[g.building!=held];te=g[g.building==held].copy();scores={}
            for alpha in [1.,3.,10.,30.,100.,np.inf]:
                errors=[]
                for inner in sorted(tr.building.unique()):
                    it=tr[tr.building==inner];ir=tr[tr.building!=inner]
                    _,v=fit_predict(ir,it,alpha)
                    zz=it[['image_key']].copy();zz['ae']=abs(it.relative_log_time.to_numpy()-v);errors.extend(zz.groupby('image_key').ae.mean().tolist())
                scores[alpha]=float(np.mean(errors))
            best=min(scores,key=scores.get);bv,pv=fit_predict(tr,te,best)
            te['pred_general']=bv;te['pred_general_plus_purpose']=pv;te['pred_zero']=0.;te['alpha']=best;te['heldout_building']=held
            for model in ['general','general_plus_purpose','zero']:
                te['ae_'+model]=abs(te.relative_log_time-te['pred_'+model]);te['se_'+model]=(te.relative_log_time-te['pred_'+model])**2
            te['gain_purpose_ae']=te.ae_general-te.ae_general_plus_purpose
            preds.append(te[['object_id','worker_id','image_key','building','room_type_model','difficulty','time_source','source_time_seconds','log_time','relative_log_time','pred_zero','pred_general','pred_general_plus_purpose','alpha','heldout_building','ae_general','ae_general_plus_purpose','ae_zero','se_general','se_general_plus_purpose','se_zero','gain_purpose_ae']])
            folds.append({'time_source':source,'heldout_building':held,'train_records':len(tr),'test_records':len(te),'chosen_alpha':best,'inner_scores_json':json.dumps({str(k):v for k,v in scores.items()})})
    pd.DataFrame(coverage).to_csv(o/'TIME_SOURCE_COVERAGE.csv',index=False);pd.DataFrame(des).to_csv(o/'TIME_PURPOSE_DIFFICULTY.csv',index=False)
    pp=pd.concat(preds,ignore_index=True);pp.to_csv(o/'TIME_LOBO_PREDICTIONS.csv.gz',index=False,compression={'method':'gzip','mtime':0});pd.DataFrame(folds).to_csv(o/'TIME_LOBO_FOLDS.csv',index=False)
    sums=[]
    for source,q in pp.groupby('time_source'):
        pi=q.groupby(['building','image_key']).gain_purpose_ae.mean()
        for model in ['zero','general','general_plus_purpose']:
            sums.append({'time_source':source,'model':model,'records':len(q),'images':q.image_key.nunique(),'buildings':q.building.nunique(),'people':q.worker_id.nunique(),'MAE_image_equal':mean_image(q,'ae_'+model),'RMSE_image_equal':np.sqrt(mean_image(q,'se_'+model)),'MAE_building_equal':q.groupby(['building','image_key'])['ae_'+model].mean().groupby(level=0).mean().mean(),'purpose_MAE_gain':mean_image(q,'gain_purpose_ae'),'purpose_gain_building_bootstrap_95':json.dumps(bootstrap_buildings(q,'gain_purpose_ae')),'purpose_improved_images':int((pi>1e-12).sum()),'purpose_worse_images':int((pi< -1e-12).sum()),'purpose_tied_images':int((pi.abs()<=1e-12).sum())})
    pd.DataFrame(sums).to_csv(o/'TIME_LOBO_SUMMARY.csv',index=False)
    pp.groupby(['time_source','room_type_model','worker_id']).agg(records=('object_id','size'),images=('image_key','nunique'),buildings=('building','nunique'),mean_relative_log_time=('relative_log_time','mean'),gain_purpose_ae=('gain_purpose_ae','mean')).reset_index().to_csv(o/'TIME_PERSON_PURPOSE.csv',index=False)
    # Actual secondary boundaries, preserving all labels including unknown and mixed.
    rows=[]
    for (condition,layer,purpose),q in d.groupby(['condition','layer','room_type_model']):
        z=q[q.formal_quality&q.Q.notna()]
        rows.append({'condition':condition,'layer':layer,'room_type':purpose,'inventory_records':len(q),'inventory_images':q.image.nunique(),'formal_records':len(z),'formal_images':z.image.nunique(),'formal_buildings':z.building.nunique(),'formal_people':z.worker_id.nunique(),'mean_Q_image_equal':z.groupby('image_key').Q.mean().mean(),'mean_D10_image_equal':z.groupby('image_key').D10.mean().mean(),'excluded_by_review_records':int((q.cleaning_disposition=='excluded_by_review').sum()),'formal_quality_unavailable_records':int((~q.formal_quality).sum()),'scope_answered':int(q.scope_response_recorded.eq(True).sum()),'scope_judgement_opportunities':int(q.scope_judgement_opportunity.eq(True).sum())})
    pd.DataFrame(rows).to_csv(o/'SECONDARY_LAYER_PURPOSE_SUPPORT.csv',index=False)
    support=[]
    q=d[(d.condition=='manual')&(d.layer=='ordinary')&d.formal_quality]
    for purpose,z in q.groupby('room_type_model'):
        counts=z.groupby('worker_id').agg(images=('image','nunique'),buildings=('building','nunique'))
        support.append({'room_type':purpose,'people':len(counts),'people_two_buildings':int((counts.buildings>=2).sum()),'people_three_buildings':int((counts.buildings>=3).sum()),'people_two_images':int((counts.images>=2).sum()),'min_buildings':int(counts.buildings.min()),'median_buildings':float(counts.buildings.median()),'max_buildings':int(counts.buildings.max())})
    pd.DataFrame(support).to_csv(o/'PERSON_PURPOSE_REPEAT_SUPPORT.csv',index=False)
    r={'source_commit':'b9bcec809fbaec8ab055931a1abb7baa5db44dac','data_release':'v2','new_fusion_endpoints':0,'source_kinds':coverage,'outcome':'ln(source time) minus leave-self-out mean ln time of SAME source-kind peers on same image, n>=3','outer_split':'leave building out, no same-room cross-building inference needed','training':'ordinary Manual formal Q with positive valid source clock, sources fitted independently','parameters':'baseline shrink count+2; purpose residual shrink selected by full inner LOBO from 1,3,10,30,100,infinity; no-purpose included','equal_weight':'first observations within image; then image, separate building equal summary','missing_times':'remain absent; not target matched time, queue time or monetary cost','bootstrap':'2000 building cluster draws of OOF image losses; no refit; describes image-building heterogeneity, not new independent datasets','seed':SEED}
    (o/'METHOD_RECEIPT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(sums).to_string(index=False))

if __name__=='__main__':main()
