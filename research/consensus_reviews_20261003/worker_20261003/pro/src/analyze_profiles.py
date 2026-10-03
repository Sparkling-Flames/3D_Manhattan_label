"""Independent audit of published complete worker-by-image matrices.

All scores are descriptive reference agreement. No tiers, source eligibility,
geometry, or GT are modified. Bootstrap and permutation diagnostics condition
on the selected buildings; they do not establish population generalization.
"""
from __future__ import annotations
from itertools import combinations
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'
SEED=20261003

def load(name):
    f=pd.read_csv(ROOT/'inputs'/name, float_precision='round_trip')
    return f, f.iloc[:,2:].to_numpy(float)

def corr(a,b):
    if np.std(a)==0 or np.std(b)==0:return None
    return float(spearmanr(a,b).statistic)

def higher_mask(x):
    n=len(x)
    if n%2: raise ValueError('equal halves require an even roster')
    s=np.sort(x)
    if abs(s[n//2]-s[n//2-1])<1e-12:return None
    return x>(s[n//2]+s[n//2-1])/2

def admissible_halves(x):
    """All top-half memberships at a 1e-12 cutoff tie; no ID tie breaking."""
    n=len(x); cut=np.sort(x)[n//2]; tied=np.flatnonzero(np.abs(x-cut)<1e-12)
    mandatory=x>cut+1e-12; need=n//2-int(mandatory.sum())
    out=[]
    for choice in combinations(tied,need):
        v=mandatory.copy();v[list(choice)]=True;out.append(v)
    return np.array(out)

def fit_lobo(Y, buildings):
    r=Y-Y.mean(axis=1,keepdims=True)
    pred=np.zeros_like(r); folds=[]; highs=[]
    for b in sorted(set(buildings)):
        tr=buildings!=b;te=~tr
        mean=Y[tr].mean(0); hi=higher_mask(mean) if Y.shape[1]%2==0 else None
        pred[te]=r[tr].mean(0)
        folds.append(dict(building=b,spearman=corr(mean,Y[te].mean(0)),
            higher_minus_lower=None if hi is None else float(Y[te][:,hi].mean()-Y[te][:,~hi].mean())))
        highs.append(hi)
    mse=float(np.mean((r-pred)**2));zero=float(np.mean(r*r))
    return dict(skill=1-mse/zero,mse=mse,zero_mse=zero,folds=folds,highs=highs,
                mean_rank_correlation=float(np.mean([f['spearman'] for f in folds])))

def main():
    OUT.mkdir(exist_ok=True)
    f,Y=load('matrix_original_iou.csv'); _,R=load('matrix_revised_where_available_iou.csv')
    _,C=load('matrix_original_centroid_normalized.csv');_,CR=load('matrix_revised_where_available_centroid_normalized.csv')
    buildings=f.building.to_numpy();workers=np.array(f.columns[2:]);B=sorted(set(buildings))
    checks=[]
    for ch in json.loads((ROOT/'inputs/transfer_checks.json').read_text()):
        raw=(ROOT/'inputs'/ch['file']).read_bytes()
        dig=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        assert dig==ch['expected_git_blob_sha'];checks.append(dict(file=ch['file'],git_blob_sha=dig,verified=True))
    allfolds=[];sps=[];split_members=[];influence=[];variance=[];profile=[];bootstrap=[];identities=[]
    headline={}
    for policy,Z,cc in [('original',Y,C),('revised_where_available',R,CR)]:
        fit=fit_lobo(Z,buildings);H=np.array(fit['highs'])
        headline[policy]=dict(relative_prediction_skill=fit['skill'],mean_lobo_rank_corr=fit['mean_rank_correlation'],
            lobo_high_always=int(H.all(0).sum()),lobo_low_always=int((~H).all(0).sum()),
            lobo_switch=int((H.any(0)&~H.all(0)).sum()),iou_centroid_profile_spearman=corr(1-Z.mean(0),cc.mean(0)))
        for b,fold,hi in zip(B,fit['folds'],fit['highs']):
            allfolds.append(dict(policy=policy,**fold))
        for j,w in enumerate(workers):
            profile.append(dict(policy=policy,worker=w,mean_iou=float(Z[:,j].mean()),
              rank=float(rankdata(-Z.mean(0))[j]),lobo_upper_fraction=float(H[:,j].mean())))
        # Exact ANOVA identity for this rectangular matrix, not population variance components.
        mu=Z.mean();im=Z.mean(1)-mu;wo=Z.mean(0)-mu;res=Z-mu-im[:,None]-wo[None,:]
        ss=[Z.shape[1]*sum(im*im),Z.shape[0]*sum(wo*wo),np.sum(res*res)]
        for name,v in zip(['image_SS','worker_SS','interaction_plus_error_SS'],ss):
            variance.append(dict(policy=policy,component=name,ss=float(v),fraction=float(v/sum(ss))))
        # Every possible disjoint 4-building / 4-building split. Unordered splits: 35.
        memberships=[]
        for split in combinations(B,4):
            if B[0] not in split:continue
            a=np.isin(buildings,split);p=Z[a].mean(0);q=Z[~a].mean(0)
            AP,AQ=admissible_halves(p),admissible_halves(q)
            agreements=np.array([(hp==hq).mean() for hp in AP for hq in AQ])
            memberships.extend([AP.mean(0),AQ.mean(0)])
            sps.append(dict(policy=policy,buildings_a='|'.join(split),buildings_b='|'.join(b for b in B if b not in split),
              image_n_a=int(a.sum()),image_n_b=int((~a).sum()),spearman=corr(p,q),admissible_halves_a=len(AP),admissible_halves_b=len(AQ),same_half_fraction_min=float(agreements.min()),
              same_half_fraction_max=float(agreements.max()),same_half_fraction=float(agreements.mean())))
        M=np.array(memberships)
        for j,w in enumerate(workers):
            split_members.append(dict(policy=policy,worker=w,upper_frequency_all_70_four_building_sets=float(M[:,j].mean())))
        part=[s for s in sps if s['policy']==policy]
        headline[policy].update(disjoint_split_median_rho=float(np.median([s['spearman'] for s in part])),
          disjoint_split_median_same_half=float(np.median([s['same_half_fraction'] for s in part])),
          disjoint_splits_with_cutoff_tie=sum(s['admissible_halves_a']>1 or s['admissible_halves_b']>1 for s in part),
          all_four_building_upper=int((M==1).all(0).sum()),all_four_building_lower=int((M==0).all(0).sum()))
        # Every leave-one-worker influence audit; omissions are NOT eligibility decisions.
        for j,w in enumerate(workers):
            keep=np.arange(len(workers))!=j;zfit=fit_lobo(Z[:,keep],buildings)
            influence.append(dict(policy=policy,omitted=w,roster_n=int(keep.sum()),relative_prediction_skill=zfit['skill'],
                mean_lobo_rank_corr=zfit['mean_rank_correlation']))
        for omitted in [[],['P017'],['P017','P002']]:
            keep=~np.isin(workers,omitted);zfit=fit_lobo(Z[:,keep],buildings)
            headline[policy]['influence_'+('-'.join(omitted) or 'none')]=dict(n=int(keep.sum()),skill=zfit['skill'],
                  mean_lobo_rho=zfit['mean_rank_correlation'])
        # Label exchangeability diagnostic: same permutation for all images within a building.
        # T = squared norm of building-equally-averaged within-image residual profile.
        block=np.stack([(Z[buildings==b]-Z[buildings==b].mean(1,keepdims=True)).mean(0) for b in B])
        obs=float(np.sum(block.mean(0)**2));rng=np.random.default_rng(SEED)
        null=np.empty(20000)
        for t in range(len(null)):
            sh=np.array([rng.permutation(x) for x in block]);null[t]=np.sum(sh.mean(0)**2)
        headline[policy]['building_label_permutation']=dict(observed=obs,null_mean=float(null.mean()),
           draws=len(null),p_upper=float((1+(null>=obs).sum())/(len(null)+1)),
           caveat='Conditional label-exchangeability diagnostic, selected eight buildings; not causal or prospective confirmation.')
        np.savez_compressed(OUT/f'permutation_{policy}.npz',null=null,observed=obs)
        # Resample calibration buildings, then re-estimate halves on each bootstrap sample.
        # Target building stays absent; bootstrap preserves image weighting within each occurrence.
        for target in B:
            trainB=[b for b in B if b!=target]
            sums=np.stack([Z[buildings==b].sum(0) for b in trainB]);ns=np.array([(buildings==b).sum() for b in trainB])
            rng=np.random.default_rng(SEED+B.index(target));draw=rng.integers(len(trainB),size=(10000,len(trainB)))
            means=sums[draw].sum(1)/ns[draw].sum(1)[:,None]
            cutoff=np.median(means,axis=1); ties=np.abs(np.sort(means,axis=1)[:,12]-np.sort(means,axis=1)[:,11])<1e-12
            valid=means;cut=np.sort(means,axis=1)[:,12];tie_mask=np.abs(means-cut[:,None])<1e-12
            mandatory=means>cut[:,None]+1e-12
            high=mandatory.astype(float)+tie_mask*((12-mandatory.sum(1))/tie_mask.sum(1))[:,None]
            ranks=rankdata(-valid,axis=1)
            for j,w in enumerate(workers):
                bootstrap.append(dict(policy=policy,target_building=target,worker=w,valid_bootstrap=len(valid),
                  cutoff_ties=int(ties.sum()),upper_fraction=float(high[:,j].mean()),rank_p10=float(np.quantile(ranks[:,j],.1)),
                  rank_p90=float(np.quantile(ranks[:,j],.9))))
        for j,k in combinations(range(len(workers)),2):
            same=np.isclose(Z[:,j],Z[:,k],atol=1e-14,rtol=0)&np.isclose(cc[:,j],cc[:,k],atol=1e-14,rtol=0)
            if same.any():identities.append(dict(policy=policy,worker_a=workers[j],worker_b=workers[k],same_both_metrics=int(same.sum()),images='|'.join(f.image[same])))
    geom_metric=[]
    for policy,Z,cc in [('original',Y,C),('revised_where_available',R,CR)]:
        within=(Z-Z.mean(1,keepdims=True))**2
        for j,row in f.iterrows():
            geom_metric.append(dict(policy=policy,image=row.image,building=row.building,
                within_image_loss_centroid_rho=corr(1-Z[j],cc[j]),
                centroid_mean=float(cc[j].mean()),centroid_total_contribution=float(cc[j].sum()/cc.sum()),
                worker_discrimination_ss_contribution=float(within[j].sum()/within.sum()),iou_mean=float(Z[j].mean())))
    # Reproduce documented maxima for original policy without choosing a weight.
    weight_rows=[]
    for b in B:
        mask=buildings!=b;bas=rankdata(-Y[mask].mean(0))
        for lam in [0,.25,.5,1,2]:
            rank=rankdata(((1-Y[mask])+lam*C[mask]).mean(0))
            weight_rows.append(dict(target_building=b,weight=lam,max_abs_rank_change=float(np.max(np.abs(rank-bas)))))
    for fn,rows in [('lobo_recomputed.csv',allfolds),('disjoint_building_splits.csv',sps),('four_building_membership.csv',split_members),
        ('leave_one_worker_influence.csv',influence),('matrix_ss_decomposition.csv',variance),('profiles_recomputed.csv',profile),
        ('calibration_building_bootstrap.csv',bootstrap),('equal_metric_cells.csv',identities),('metric_image_diagnostics.csv',geom_metric),
        ('weight_grid_recomputed.csv',weight_rows)]:
        pd.DataFrame(rows).to_csv(OUT/fn,index=False)
    # Exact reproduction of documented structural summaries, tolerances stated.
    assert headline['original']['lobo_switch']==9
    assert abs(headline['original']['iou_centroid_profile_spearman']-.3226086956521739)<1e-12
    maximums=pd.DataFrame(weight_rows).groupby('weight').max_abs_rank_change.max().tolist();assert maximums==[0,5,6,10,14]
    H1=np.array(fit_lobo(Y,buildings)['highs']);H2=np.array(fit_lobo(R,buildings)['highs'])
    assert int(np.count_nonzero(H1!=H2))==22
    headline['reference_policy_changed_cells']=int(np.count_nonzero(H1!=H2))
    headline['reference_policy_profile_rank_rho']=corr(Y.mean(0),R.mean(0))
    headline['transfer_checks']=checks
    (OUT/'profile_analysis_summary.json').write_text(json.dumps(headline,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in headline.items() if k!='transfer_checks'},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
