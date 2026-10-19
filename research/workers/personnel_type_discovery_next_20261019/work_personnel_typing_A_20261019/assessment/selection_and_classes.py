#!/usr/bin/env python3
"""Selection utility and category coverage; no changes to discovered categories."""
from pathlib import Path
from itertools import combinations
import json,sys
import numpy as np
import pandas as pd
from sklearn.metrics import normalized_mutual_info_score,adjusted_rand_score
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE))
from evaluate_common import attach,unit_summary,savej,boolcol,PRIMARY

def class_descriptions(l):
    p=ROOT/'recovered/work_v2_20261019/profiles'
    hist=pd.concat([pd.read_csv(p/'full_profiles.csv'),pd.read_csv(p/'fold_profiles.csv')],ignore_index=True)
    hist=hist[['heldout_building','worker_id','origin','Q_effect_B8L2','absolute_B8L2_mean','absolute_B8L2_p10','absolute_B8L2_sd','T_source_median','theta_easy_B8L2','theta_medium_B8L2','theta_hard_B8L2']]
    x=l.merge(hist,on=['heldout_building','worker_id'],how='left',validate='many_to_one')
    rows=[];mix=[]
    for (fold,m,d),g in x.groupby(['heldout_building','method_id','difficulty']):
        known=g[g.class_id.ne('unknown')]
        if len(known):
            sizes=known.class_id.value_counts();mix.append(dict(heldout_building=fold,method_id=m,difficulty=d,known_workers=len(known),unknown_workers=len(g)-len(known),classes=len(sizes),singleton_classes=int(sizes.eq(1).sum()),dyad_classes=int(sizes.eq(2).sum()),within_class_pairs=int(sum(n*(n-1)//2 for n in sizes)),origin_nmi=float(normalized_mutual_info_score(known.origin.fillna('unknown'),known.class_id)),largest_class_workers=int(sizes.max())))
        for c,a in g.groupby('class_id'):
            r=dict(heldout_building=fold,method_id=m,difficulty=d,class_id=c,workers=len(a),members='|'.join(sorted(a.worker_id)),old_workers=int(a.origin.eq('v1').sum()),new_workers=int(a.origin.eq('new').sum()))
            for col in hist.columns[3:]:r[col+'_mean']=a[col].mean();r[col+'_median']=a[col].median()
            rows.append(r)
    pd.DataFrame(rows).to_csv(HERE/'CLASS_MEMBERS_AND_PROFILES.csv.gz',index=False)
    pd.DataFrame(mix).to_csv(HERE/'CLASS_SIZE_ORIGIN_COVERAGE.csv',index=False)
    pairs=[];summary=[]
    for (m,d),g in l.groupby(['method_id','difficulty']):
        workers=sorted(g.worker_id.unique());outer=g[g.heldout_building.ne('FULL')]
        if not len(outer):continue
        mat=outer.pivot(index='worker_id',columns='heldout_building',values='class_id').reindex(workers)
        full=g[g.heldout_building.eq('FULL')].set_index('worker_id').class_id.to_dict()
        agreement=[];fold_ari=[]
        for a,b in combinations(workers,2):
            x,y=mat.loc[a],mat.loc[b];known=x.notna()&y.notna()&x.ne('unknown')&y.ne('unknown')
            n=int(known.sum());freq=float(x[known].eq(y[known]).mean()) if n else np.nan
            fullknown=full.get(a,'unknown')!='unknown' and full.get(b,'unknown')!='unknown';same=full.get(a)==full.get(b) if fullknown else None
            if n and fullknown:agreement.append(freq if same else 1-freq)
            pairs.append(dict(method_id=m,difficulty=d,worker_a=a,worker_b=b,known_outer_folds=n,coassignment_frequency=freq,full_fit_same_class=same,full_fit_membership_is_descriptive=True))
        for a,b in combinations(mat.columns,2):
            z=mat[[a,b]].dropna();z=z[z[a].ne('unknown')&z[b].ne('unknown')]
            if len(z)>1:fold_ari.append(adjusted_rand_score(z[a],z[b]))
        summary.append(dict(method_id=m,difficulty=d,mean_pair_agreement_to_full=np.mean(agreement) if agreement else np.nan,median_fold_pair_ARI=np.median(fold_ari) if fold_ari else np.nan,p10_fold_pair_ARI=np.quantile(fold_ari,.1) if fold_ari else np.nan,fold_comparisons=len(fold_ari)))
    pd.DataFrame(pairs).to_csv(HERE/'COASSIGNMENT_STABILITY_PAIRS.csv.gz',index=False)
    pd.DataFrame(summary).to_csv(HERE/'COASSIGNMENT_STABILITY_SUMMARY.csv',index=False)

def choose_larger(a,b,known):return np.where(known,np.where(a>b,1.,np.where(a<b,0.,.5)),np.nan)

def last_seat(e,l):
    p=ROOT/'recovered/work_v2_20261019/profiles/fold_profiles.csv'
    hist=pd.read_csv(p)[['heldout_building','worker_id','Q_effect_B8L2']]
    out=e[['event_id','panel_id','building','image_id','k','difficulty','pair_origin']].copy()
    qknown=e.q_support_a&e.q_support_b
    choices={'random':np.full(len(e),.5),'Q':choose_larger(e.beta_a,e.beta_b,qknown),'QD':choose_larger(e.theta_a,e.theta_b,e.theta_support_a&e.theta_support_b)}
    faster=choose_larger(-e.time_a,-e.time_b,e.time_support_a&e.time_support_b)
    for name,values,known in [('QT',(e.beta_a,e.beta_b),qknown),('QTD',(e.theta_a,e.theta_b),e.theta_support_a&e.theta_support_b)]:
        a,b=values;v=choose_larger(a,b,known);band=(a-b).abs().le(3)&known;v[band]=faster[band];choices[name]=v
    for m in [x for x in l.method_id.unique() if x in ['Q3','old_QT','old_QTD_archive','forward_selected','forward_full','reverse_selected','reverse_selected_global','reverse_selected_difficulty','reverse_selected_geometry','reverse_selected_swap']]:
        v=np.full(len(e),np.nan)
        for b in sorted(e.building.unique()):
            lab=l[l.heldout_building.eq(b)&l.method_id.eq(m)]
            f=lab.merge(hist[hist.heldout_building.eq(b)],on=['heldout_building','worker_id'],validate='many_to_one')
            means=f[f.class_id.ne('unknown')].groupby(['difficulty','class_id']).Q_effect_B8L2.mean().to_dict()
            idx=e.index[e.building.eq(b)];te=e.loc[idx];ca,cb,rel=attach(te,lab)
            qa=[];qb=[]
            for d,a,c in zip(te.difficulty,ca,cb):
                qa.append(means.get((d,a),means.get(('global',a),np.nan)));qb.append(means.get((d,c),means.get(('global',c),np.nan)))
            qa=np.array(qa);qb=np.array(qb);v[idx]=choose_larger(qa,qb,np.isfinite(qa)&np.isfinite(qb))
        choices['class_mean_Q__'+m]=v
    rows=[];den=[]
    for name,v in choices.items():
        out['choose_a_probability__'+name]=v
        f=e.copy();f['choice_supported']=np.isfinite(v)
        ca=f.complete_a.astype(float);cb=f.complete_b.astype(float)
        f['completion_advantage']=v*ca+(1-v)*cb-(ca+cb)/2
        f['conditional_Q_advantage']=v*f.B8L2_a+(1-v)*f.B8L2_b-(f.B8L2_a+f.B8L2_b)/2
        f['conditional_D10_advantage']=v*f.D10_a+(1-v)*f.D10_b-(f.D10_a+f.D10_b)/2
        qa=f.B8L2_a.fillna(0);qb=f.B8L2_b.fillna(0)
        f['team_failure_zero_utility_advantage']=v*qa+(1-v)*qb-(qa+qb)/2
        ta=f.source_entrant_time_a;tb=f.source_entrant_time_b
        f['source_incremental_seconds_advantage']=v*ta+(1-v)*tb-(ta+tb)/2
        ta=f.target_entrant_time_a;tb=f.target_entrant_time_b
        f['target_incremental_seconds_advantage']=v*ta+(1-v)*tb-(ta+tb)/2
        for panel,gp in f.groupby('panel_id'):
            for k,gk in gp.groupby('k'):
                for stratum,mask in [('all',gk.choice_supported),('Q_near_3',gk.choice_supported&gk.q_near)]+[(o,gk.choice_supported&gk.pair_origin.eq(o))for o in ['old-old','new-new','old-new']]:
                    g=gk[mask];den.append(dict(policy=name,panel_id=panel,k=k,stratum=stratum,registered_events=len(gk),supported_events=len(g),images=g.image_id.nunique(),buildings=g.building.nunique(),both_complete=int(g.both_complete.sum()),both_source_entrants_known=int((g.source_entrant_time_a.notna()&g.source_entrant_time_b.notna()).sum())))
                    for metric in ['completion_advantage','conditional_Q_advantage','conditional_D10_advantage','team_failure_zero_utility_advantage','source_incremental_seconds_advantage','target_incremental_seconds_advantage']:
                        rows.append(dict(policy=name,panel_id=panel,k=k,stratum=stratum,metric=metric,**unit_summary(g,metric)))
    out.to_csv(HERE/'LAST_SEAT_CHOICES.csv.gz',index=False)
    pd.DataFrame(rows).to_csv(HERE/'LAST_SEAT_POLICY_SUMMARY.csv',index=False)
    pd.DataFrame(den).to_csv(HERE/'LAST_SEAT_POLICY_COVERAGE.csv',index=False)

def worker_tails(e,w):
    rows=[];pair=[]
    for m in ['Q3','old_QT','old_QTD_archive','forward_selected','reverse_selected','reverse_selected_global','reverse_selected_difficulty']:
        col='rel__'+m
        if col not in w:continue
        f=e.copy();f['relation']=w[col].to_numpy()
        for (panel,r,a,b),g in f[f.relation.ne('unknown')].groupby(['panel_id','relation','worker_a','worker_b']):
            z=unit_summary(g,'stable_main');pair.append(dict(method_id=m,panel_id=panel,relation=r,worker_a=a,worker_b=b,**z,abs_Q_p90=g.abs_delta_Q.quantile(.9),floor_p90=g.floor_change.quantile(.9),failures=int(g.either_failure.sum())))
        f=f[f.relation.eq('within')]
        for worker in sorted(set(f.worker_a)|set(f.worker_b)):
            for panel,g in f[f.worker_a.eq(worker)|f.worker_b.eq(worker)].groupby('panel_id'):
                peers=set(g.worker_a)|set(g.worker_b);peers.discard(worker)
                rows.append(dict(method_id=m,panel_id=panel,worker_id=worker,within_class_peers=len(peers),peer_ids='|'.join(sorted(peers)),**unit_summary(g,'stable_main'),abs_Q_p90=g.abs_delta_Q.quantile(.9),floor_p90=g.floor_change.quantile(.9),either_failure=int(g.either_failure.sum())))
    pd.DataFrame(rows).to_csv(HERE/'WORKER_WITHIN_CLASS_TAILS.csv.gz',index=False)
    pd.DataFrame(pair).to_csv(HERE/'ACTUAL_PAIR_TAILS.csv.gz',index=False)

def main():
    e=pd.read_csv(HERE/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz',low_memory=False)
    l=pd.read_csv(HERE/'ALL_SELECTED_AND_BASELINE_LABELS.csv.gz',low_memory=False)
    w=pd.read_csv(HERE/'EVENT_PREDICTIONS_WIDE.csv.gz',low_memory=False)
    for c in ['q_support_a','q_support_b','theta_support_a','theta_support_b','time_support_a','time_support_b','q_near','stable_main','complete_a','complete_b','both_complete','either_failure']:e[c]=boolcol(e[c])
    class_descriptions(l);print('class descriptions and pair stability complete',flush=True)
    last_seat(e,l);print('last-seat selection complete',flush=True)
    worker_tails(e,w);print('whole within-class tail diagnostics complete',flush=True)
if __name__=='__main__':main()
