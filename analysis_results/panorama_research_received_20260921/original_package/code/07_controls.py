"""Observation-count controls, Monte Carlo threshold sensitivity, and retained OOS lane."""
import common as c
import json,collections,itertools,math
import numpy as np,pandas as pd
from sklearn.linear_model import Ridge
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

def main():
    args=c.main_parser().parse_args();c.configure(args.source_root)
    rows,rec,views,_,_=c.load();im=pd.read_csv(c.ROOT/'results/image_metrics.csv').set_index('image_id')
    F=pd.read_csv(c.SOURCE/'analysis_results/clustering_release_local_20260920/current/input/supplement/model_image_features.csv').set_index('image_id')
    F['N']=im.N
    ro=pd.read_csv(c.SOURCE/'analysis_results/clustering_numeric_received_20260920/results/personnel/refitted_lobo_rosters.csv')
    # All roster summaries come from historical target-building-held-out types; unknown is explicit.
    for iid,v in views.items():
        if iid not in F.index:continue
        rr=ro[(ro.config=='Q_2')&(ro.heldout_building==v['building'])].set_index('worker')
        cl=[int(rr.loc[w,'subtype']) if w in rr.index else 0 for w in v['workers']]
        F.loc[iid,'Q2_type1_fraction']=np.mean(np.array(cl)==1);F.loc[iid,'Q2_unknown_fraction']=np.mean(np.array(cl)==0)
    counts=['bi_enclosed_corners','bi_extended_corners','hohonet_corners'];gaps=[z for z in F.columns if z.startswith('gap_')]
    configs={'N_only':['N'],'N_plus_roster':['N','Q2_type1_fraction','Q2_unknown_fraction'],
             'N_plus_model_counts':['N']+counts,'N_plus_model_counts_gaps':['N']+counts+gaps,
             'N_plus_model_and_roster':['N']+counts+gaps+['Q2_type1_fraction','Q2_unknown_fraction']}
    results=[]
    for outcome,minN in [('pair_disagreement',4),('U5',8),('U8',11)]:
        ids=[i for i in im.index if im.loc[i,'N']>=minN and i in F.index];b=np.array([views[i]['building'] for i in ids]);y=im.loc[ids,outcome].to_numpy()
        for hold in sorted(set(b)):
            tr=b!=hold;te=~tr
            for config,cols in configs.items():
                x=F.loc[ids,cols].to_numpy();imp=SimpleImputer(strategy='median');a=imp.fit_transform(x[tr]);d=imp.transform(x[te]);sc=StandardScaler();a=sc.fit_transform(a);d=sc.transform(d)
                w=np.array([1./sum(b[tr]==bb) for bb in b[tr]]);w*=len(w)/w.sum()
                model=Ridge(alpha=10.).fit(a,y[tr],sample_weight=w);pred=model.predict(d).clip(0,1)
                for iid,yi,pi in zip(np.array(ids)[te],y[te],pred):results.append(dict(image_id=iid,code=views[iid]['code'],building=hold,N=views[iid]['N'],outcome=outcome,config=config,value=yi,prediction=pi))
    pr=pd.DataFrame(results);pr['absolute_error']=abs(pr.value-pr.prediction)
    base=pr[pr.config=='N_only'][['image_id','outcome','absolute_error']].rename(columns={'absolute_error':'baseline_error'})
    pr=pr.merge(base,on=['image_id','outcome'],validate='many_to_one');pr['gain']=pr.baseline_error-pr.absolute_error
    c.save('model_N_roster_controls.csv',pr)
    summary=[]
    for (outcome,config),g in pr.groupby(['outcome','config']):summary.append(dict(outcome=outcome,config=config,MAE=g.groupby('building').absolute_error.mean().mean(),N_only_MAE=g.groupby('building').baseline_error.mean().mean(),gain=c.building_summary(g,'gain')))
    c.save('model_N_roster_controls_summary.json',summary)
    # Sampling precision of the *permutation probability*, not confidence about a new population.
    df=pd.read_csv(c.ROOT/'results/replay_onsets.csv');df=df[(df.epsilon==.1)&(df.profile=='uncapped')&(df.N>=8)&(df['tail']==3)].copy()
    B=len(json.loads((c.ROOT/'results/replay_orders.json').read_text())['orders']);z=1.95996398454;p=df.final_stable_probability.to_numpy()
    midpoint=(p+z*z/(2*B))/(1+z*z/B);half=z*np.sqrt(p*(1-p)/B+z*z/(4*B*B))/(1+z*z/B)
    df['permutation_probability_wilson_lower']=midpoint-half;df['permutation_probability_wilson_upper']=midpoint+half
    df['MC_crosses_080']=(midpoint-half<=.8)&(midpoint+half>=.8)
    c.save('permutation_MC_precision.csv',df)
    c.save('permutation_MC_precision_summary.json',[dict(method=k,images=len(g),B=B,threshold_CI_crossing=int(g.MC_crosses_080.sum()),
        nominal_identified=int((g.status=='identified').sum()),endpoint_Wilson_lower_ge080=int((g.permutation_probability_wilson_lower>=.8).sum()),
        interpretation='Pointwise numerical precision for uniform reordering probability; not an independent-annotator or simultaneous-curve confidence bound.') for k,g in df.groupby('method')])
    cp=pd.read_csv(c.ROOT/'results/same_room_identical_workers.csv');cp['gap_reduction']=cp.all_absolute_gap-cp.common_absolute_gap
    c.save('common_worker_control_summary.json',[dict(k=int(k),pairs=len(g),buildings=g.building.nunique(),families=g.family.nunique(),
        average_gap_full=g.groupby(['building','family']).all_absolute_gap.mean().groupby('building').mean().mean(),
        average_gap_common=g.groupby(['building','family']).common_absolute_gap.mean().groupby('building').mean().mean(),
        reduction=c.building_summary(g,'gap_reduction',room='family')) for k,g in cp.groupby('k')])
    lane=[]
    for iid,v in views.items():
        conditions=collections.Counter(r['raw_condition'] for r in v['rows'])
        lane.append(dict(image_id=iid,code=v['code'],N=v['N'],building=v['building'],historical_oos_lane=conditions.get('oos',0)>0,
            oos_responses=conditions.get('oos',0),pair_disagreement=im.loc[iid,'pair_disagreement'],U5=im.loc[iid,'U5'],U8=im.loc[iid,'U8']))
    ln=pd.DataFrame(lane);c.save('retained_oos_lane.csv',ln)
    counts=collections.Counter()
    for r in rows:
        if r['calculation_included'] and r['worker_id'] not in ['W019','W026']:
            for a in r.get('scope_original') or []:
                for ch in a.get('value',{}).get('choices',[]):counts[ch]+=1
    c.save('oos_retention_summary.json',dict(oos_lane_prediction_images=int(ln.historical_oos_lane.sum()),oos_lane_prediction_responses=int(ln.oos_responses.sum()),
        new_scope_response_choices=dict(counts),warning='historical planned_oos_lane is a sampling designation, NOT a newly adjudicated semantic OOS truth; response choices are not researcher truth.'))
    print(json.dumps(c.clean(summary),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
