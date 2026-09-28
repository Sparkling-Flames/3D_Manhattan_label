"""Target-building-held-out worker prediction and finite real-team composition decomposition."""
import common as c
import json,math,itertools,collections
import numpy as np,pandas as pd
from scipy.stats import spearmanr

CONFIGS=['Q_2','Q_3','QT_2','QT_3','QTSB_3','TRI_3']

def summaries(pred):
    res=[]
    for (outcome,model),z in pred.groupby(['outcome','model']):
        z=z.copy();z['mse']=(z.value-z.prediction)**2;z['base_mse']=z.value**2
        # First image, then building, preventing high-repetition images dominating.
        by=z.groupby(['building','image_id'])[['mse','base_mse']].mean().groupby('building').mean()
        gain=by.base_mse-by.mse
        rng=np.random.default_rng(c.SEED);bs=rng.choice(gain.to_numpy(),(5000,len(gain)),replace=True).mean(1)
        res.append(dict(outcome=outcome,model=model,responses=len(z),images=z.image_id.nunique(),buildings=len(by),
            MSE=by.mse.mean(),baseline_MSE=by.base_mse.mean(),relative_MSE_gain=1-by.mse.mean()/by.base_mse.mean(),
            absolute_gain_interval95=np.quantile(bs,[.025,.975]),unclassified_rows=int((~z.qualified).sum()),
            per_building_gain=gain.to_dict()))
    return res

def main():
    args=c.main_parser().parse_args();c.configure(args.source_root)
    _,_,views,_,_=c.load()
    wr=pd.read_csv(c.ROOT/'results/response_metrics.csv');wr=wr[wr.N>=4].copy()
    ro=pd.read_csv(c.SOURCE/'analysis_results/clustering_numeric_received_20260920/results/personnel/refitted_lobo_rosters.csv')
    for col in ['pair_disagreement','count_disagreement']:
        wr['centered_'+col]=wr[col]-wr.groupby('image_id')[col].transform('mean')
    predictions=[];profiles=[]
    for building in sorted(wr.building.unique()):
        tr=wr[wr.building!=building];te=wr[wr.building==building]
        assert not (set(tr.building)&{building})
        for outcome in ['pair_disagreement','count_disagreement']:
            col='centered_'+outcome
            # All available participants; image-centred means; buildings equally represented in each profile.
            train=tr.groupby(['worker','building'])[col].agg(['mean','size']).reset_index()
            eff=train.groupby('worker')['mean'].mean();ntrain=tr.groupby('worker').size();nb=train.groupby('worker').size()
            eff=eff*(ntrain/(ntrain+20.0));qualified=(ntrain>=4)&(nb>=2)
            eff=eff.where(qualified,0.)
            for w in sorted(wr.worker.unique()):profiles.append(dict(heldout_building=building,worker=w,outcome=outcome,
                effect=eff.get(w,0.),train_images=int(ntrain.get(w,0)),train_buildings=int(nb.get(w,0)),qualified=bool(qualified.get(w,False)),
                train_building_ids=';'.join(sorted(tr.loc[tr.worker==w,'building'].unique()))))
            def add(model,ps,qual):
                for (_,r),p,q in zip(te.iterrows(),ps,qual):predictions.append(dict(image_id=r.image_id,code=r.code,building=building,
                    worker=r.worker,N=r.N,new=bool(r['new']),outcome=outcome,model=model,value=r[col],prediction=p,qualified=bool(q)))
            # Continuous identity-linked tendency. No target responses used to obtain the effect.
            add('continuous_current_shrink20',te.worker.map(eff).fillna(0),te.worker.map(qualified).fillna(False))
            # Sign discretisation deliberately fixed at zero, not equal-sized bins or outcome optimization.
            sign={w:('positive' if eff[w]>.0 else 'negative') if qualified.get(w,False) else 'unclassified' for w in eff.index}
            zz=tr.assign(cls=tr.worker.map(sign).fillna('unclassified'))
            effect=zz.groupby('cls')[col].mean().to_dict();effect['unclassified']=0.
            add('current_sign_discrete',te.worker.map(sign).fillna('unclassified').map(effect).fillna(0),te.worker.map(qualified).fillna(False))
            for config in CONFIGS:
                rr=ro[(ro.heldout_building==building)&(ro.config==config)].drop_duplicates('worker').set_index('worker')
                cls=rr.subtype.astype(str).to_dict();z=tr.assign(cls=tr.worker.map(cls).fillna('unclassified'))
                # Class effect derived only from outside-building responses. Unclassified remains in the evaluation.
                estimates=z.groupby(['building','cls'])[col].mean().groupby('cls').mean().to_dict();estimates['unclassified']=0.
                labels=te.worker.map(cls).fillna('unclassified')
                add('historical_'+config,labels.map(estimates).fillna(0),labels!='unclassified')
                # Continuous historical features, same outer split, ridge regularization FIXED, missing flags.
                if config=='QTSB_3':
                    from sklearn.linear_model import Ridge
                    from sklearn.impute import SimpleImputer
                    from sklearn.preprocessing import StandardScaler
                    cols=['quality','time','scope_accept','scope_reject','benefit','edit']
                    X0=rr.reindex(tr.worker)[cols].to_numpy();X1=rr.reindex(te.worker)[cols].to_numpy()
                    # Fit every preprocessing transform ONLY on training rows.
                    imp=SimpleImputer(strategy='constant',fill_value=0.,add_indicator=True);X0=imp.fit_transform(X0);X1=imp.transform(X1)
                    sc=StandardScaler();X0=sc.fit_transform(X0);X1=sc.transform(X1)
                    model=Ridge(alpha=20).fit(X0,tr[col].to_numpy())
                    add('historical_continuous_QTSB',model.predict(X1),te.worker.isin(rr.index))
    pr=pd.DataFrame(predictions);pf=pd.DataFrame(profiles)
    c.save('worker_lobo_predictions.csv.gz',pr);c.save('worker_lobo_profiles.csv',pf);summary=summaries(pr);c.save('worker_prediction_summary.json',summary)
    # Per-worker image dependence: sample dispersion versus cross-building prediction, not test-retest noise.
    ws=wr.groupby('worker').agg(images=('image_id','nunique'),buildings=('building','nunique'),
        centered_disagreement_mean=('centered_pair_disagreement','mean'),between_image_SD=('centered_pair_disagreement','std'),
        positive_images=('centered_pair_disagreement',lambda x:(x>0).sum()),negative_images=('centered_pair_disagreement',lambda x:(x<0).sum())).reset_index()
    c.save('worker_image_dependence.csv',ws)
    # Same image, same count, composition variation vs changing actual members.
    rng=np.random.default_rng(c.SEED);team_summary=[];examples=[];panel_sizes=[]
    for iid,v in sorted(views.items()):
        N=v['N']
        if N<5:continue
        roster=ro[ro.heldout_building==v['building']]
        for n in [4,8,12,16,20]:
            if n>=N:continue
            total=math.comb(N,n)
            if total<=2000:teams=np.array(list(itertools.combinations(range(N),n)),int)
            else:
                ts=set()
                while len(ts)<2000:ts.add(tuple(sorted(rng.choice(N,n,replace=False))))
                teams=np.array(sorted(ts),int)
            aa,bb=np.triu_indices(n,1)
            Y=(v['d'][teams[:,aa],teams[:,bb]]>c.CUT).mean(1)
            var=float(Y.var());panel_sizes.append(dict(image_id=iid,building=v['building'],code=v['code'],N=N,n=n,feasible_teams=total,evaluated_unique_teams=len(teams),mean_disagreement=Y.mean(),SD=Y.std(),q10=np.quantile(Y,.1),q90=np.quantile(Y,.9)))
            for config in CONFIGS:
                rr=roster[roster.config==config].set_index('worker');labels=np.array([str(int(rr.loc[w,'subtype'])) if w in rr.index else 'U' for w in v['workers']]);types=sorted(set(labels))
                X=np.stack([(labels[teams]==typ).sum(1) for typ in types],1)
                tuples=[tuple(x) for x in X];buckets=collections.defaultdict(list)
                for j,t in enumerate(tuples):buckets[t].append(j)
                ss=0.;between=0.;within=0.;spreads=[]
                for key,ix in buckets.items():
                    yy=Y[ix];within+=len(ix)*yy.var()/len(Y);between+=len(ix)*(yy.mean()-Y.mean())**2/len(Y)
                    if len(ix)>=20:spreads.append(float(np.quantile(yy,.9)-np.quantile(yy,.1)))
                assert np.isclose(var,within+between)
                G=len(buckets);T=len(teams)
                eta=between/var if var>1e-14 else np.nan
                adj=1-(within*T/(T-G))/(var*T/(T-1)) if var>1e-14 and T>G else np.nan
                team_summary.append(dict(image_id=iid,code=v['code'],building=v['building'],N=N,n=n,config=config,teams=T,compositions=G,
                    unclassified_workers=int((labels=='U').sum()),total_variance=var,within_composition_variance=within,between_composition_variance=between,
                    composition_fraction=eta,adjusted_composition_fraction=adj,median_within_composition_q90_q10=np.median(spreads) if spreads else np.nan))
                if config=='Q_2' and n in [4,8]:
                    eligible=[(key,ix) for key,ix in buckets.items() if len(ix)>=20]
                    if eligible:
                        key,ix=max(eligible,key=lambda ki:Y[ki[1]].max()-Y[ki[1]].min())
                        j0=ix[int(Y[ix].argmin())];j1=ix[int(Y[ix].argmax())]
                        examples.append(dict(image_id=iid,code=v['code'],building=v['building'],N=N,n=n,config=config,
                            composition=';'.join(f'{t}:{x}' for t,x in zip(types,key)),teams_in_composition=len(ix),
                            minimum=float(Y[j0]),maximum=float(Y[j1]),lower_team=';'.join(v['workers'][j] for j in teams[j0]),
                            upper_team=';'.join(v['workers'][j] for j in teams[j1])))
    ts=pd.DataFrame(team_summary);pan=pd.DataFrame(panel_sizes)
    c.save('team_composition_variance.csv.gz',ts);c.save('team_panels.csv',pan);c.save('same_composition_member_examples.csv',pd.DataFrame(examples))
    sums=[]
    for (config,n),z in ts.groupby(['config','n']):
        valid=z[z.total_variance>1e-14]
        sums.append(dict(config=config,n=n,images=len(z),variable_images=len(valid),buildings=z.building.nunique(),
            mean_within_fraction=1-valid.composition_fraction.mean(),median_within_fraction=1-valid.composition_fraction.median(),
            building_equal_composition=c.building_summary(valid,'composition_fraction'),
            median_within_composition_spread=valid.median_within_composition_q90_q10.median()))
    c.save('composition_summary.json',sums)
    print(json.dumps(c.clean(summary),ensure_ascii=False,indent=2));print('team rows',len(ts),'unique panels',len(pan))

if __name__=='__main__':main()
