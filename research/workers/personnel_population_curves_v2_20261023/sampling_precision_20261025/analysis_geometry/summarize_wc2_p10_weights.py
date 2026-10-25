"""One registered-result P10 diagnostic; no new team, seed, fusion or figure.

The two observed score peaks are separated at the midpoint of the largest
adjacent score gap in the complete 28-team catalogue. This is a description
of this case, not a personnel classification or a fitted prediction rule.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from population_paths import add_population_root_argument,resolve_population_root
from safe_io import atomic_bytes,install_safe_csv_writer
install_safe_csv_writer()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',required=True);ap.add_argument('--out',required=True);add_population_root_argument(ap);a=ap.parse_args()
    root=Path(a.study).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    base=resolve_population_root(root,a.population_root)
    pools=pd.read_csv(base/'design/ACTUAL_POOLS.csv')
    pool=pools[pools.image.eq('wc2JMjhGNzB-46')&pools.layer.eq('ordinary_manual')].iloc[0]
    pid=pool.pool_id;N=int(pool.pool_n);k=N-1
    all_exact=pd.read_csv(root/'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz',low_memory=False)
    exact=all_exact[all_exact.pool_id.eq(pid)&all_exact.k.eq(k)].copy().sort_values('B8L2')
    assert len(exact)==N==28 and exact.team_key.nunique()==28
    assert exact.B8L2.notna().all() and not exact.score_failure_nonpolicy.any()
    q=exact.B8L2.to_numpy();gap_index=int(np.argmax(np.diff(q)))
    lo=float(q[gap_index]);hi=float(q[gap_index+1]);threshold=(lo+hi)/2
    exact['score_peak']=np.where(exact.B8L2<threshold,'low','high')
    workers=set(str(pool.workers).split('|'))
    exact['absent_worker']=['|'.join(sorted(workers-set(str(x).split('|')))) for x in exact.member_workers]
    exact['finite_uniform_weight']=1/N
    cols=['pool_id','path_id','k','team_key','batch','policy','pool_n','replicate','seed','B8L2','D10','score_failure_nonpolicy']
    def load(path,batch=None):
        d=pd.read_csv(path,usecols=lambda c:c in cols,low_memory=False,dtype={'seed':str})
        d=d[d.pool_id.eq(pid)&d.k.eq(k)&d.policy.eq('natural_random')].copy()
        if batch is not None:d['batch']=batch
        return d
    old=load(base/'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz','old24')
    new=load(root/'new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz')
    new['batch']=new.batch.replace({'balanced_new24':'new24','focus_new48':'focus48'})
    paths=pd.concat([old,new],ignore_index=True)
    assert len(paths)==96 and not paths.path_id.duplicated().any()
    paths=paths.merge(exact[['team_key','absent_worker','score_peak','B8L2']].rename(columns={'B8L2':'catalog_Q'}),on='team_key',validate='many_to_one')
    assert (paths.B8L2-paths.catalog_Q).abs().max()<1e-9
    paths.to_csv(out/'WC2_46_REGISTERED_PATHS.csv',index=False)
    cohorts={'old24':['old24'],'new24':['new24'],'combined48':['old24','new24'],
             'focus48':['focus48'],'independent_new72':['new24','focus48'],'combined96':['old24','new24','focus48']}
    exact_linear=float(np.quantile(q,.1,method='linear'))
    exact_cdf=float(np.quantile(q,.1,method='inverted_cdf'))
    low_n=int((exact.score_peak=='low').sum());rows=[]
    def add(label,data,basis):
        values=data.B8L2.to_numpy();valid=values[np.isfinite(values)]
        value=float(np.quantile(valid,.1,method='linear'))
        rows.append(dict(pool_id=pid,image=pool.image,building=pool.building,pool_n=N,k=k,sample=label,count_basis=basis,
            observations=len(data),scorable_observations=len(valid),failures=int(data.score_failure_nonpolicy.sum()),
            unique_teams=data.team_key.nunique(),unique_low_peak_teams=data.loc[data.score_peak.eq('low'),'team_key'].nunique(),
            low_peak_observations=int(data.score_peak.eq('low').sum()),low_peak_frequency=float(data.score_peak.eq('low').mean()),
            Q_mean=float(valid.mean()),P10_linear=value,P10_inverseCDF=float(np.quantile(valid,.1,method='inverted_cdf')),
            exact_catalog_linear_P10=exact_linear,exact_uniform_population_inverseCDF_P10=exact_cdf,
            difference_from_catalog_linear=value-exact_linear,difference_from_uniform_population_inverseCDF=value-exact_cdf,
            exact_low_peak_probability=low_n/N,largest_gap_lower_Q=lo,largest_gap_upper_Q=hi,descriptive_peak_threshold=threshold))
    add('exact_uniform_28_teams',exact,'complete_catalogue_teams')
    for label,batches in cohorts.items():
        d=paths[paths.batch.isin(batches)];add(label,d,'registered_random_paths')
        counts=d.team_key.value_counts()
        exact[label+'_path_count']=exact.team_key.map(counts).fillna(0).astype(int)
    summaries=pd.DataFrame(rows)
    summaries.to_csv(out/'WC2_46_BATCH_P10_AND_WEIGHTS.csv',index=False)
    wanted=['team_key','pool_id','image','image_id','building','condition','layer','difficulty','pool_n','k',
            'reference_id','reference_version','member_workers','member_object_ids','score_status','geometry_status','order_status',
            'score_available','complete_evaluable','complete_floor_evaluable','score_failure_nonpolicy','B8L2','D10','nodes','floor_turn5_n',
            'minimum_support','geometry_state_pointer','geometry_source_file','endpoint_origin','absent_worker','score_peak','finite_uniform_weight']
    wanted=[c for c in wanted if c in exact]+[c+'_path_count' for c in cohorts]
    exact[wanted].to_csv(out/'WC2_46_EXACT_28_TEAMS_AND_FREQUENCIES.csv',index=False)
    receipt=dict(source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',image=pool.image,pool_id=pid,N=N,k=k,
        exact_team_count=28,registered_paths=96,new_fusion_calls=0,low_peak_teams=low_n,high_peak_teams=N-low_n,
        exact_low_peak_probability=low_n/N,largest_gap_lower_Q=lo,largest_gap_upper_Q=hi,peak_threshold=threshold,
        peak_definition='Midpoint of the largest adjacent score gap in the complete catalogue, determined without path frequencies; descriptive only.',
        main_P10_definition='numpy.quantile(values, 0.1, method=linear), retained for both original and new reported curves',
        finite_catalogue_linear_P10=exact_linear,uniform_finite_population_inverseCDF_P10=exact_cdf,
        definition_difference_catalogue_linear_minus_inverseCDF=exact_linear-exact_cdf,
        interpretation='As random draws grow, sample linear P10 approaches the inverse-CDF quantile of the finite uniform team distribution; a small complete-catalogue linear percentile is a different convention. Both are reported explicitly.')
    atomic_bytes(out/'WC2_46_RECEIPT.json',json.dumps(receipt,ensure_ascii=False,indent=2).encode('utf-8'))
    print(summaries[['sample','observations','unique_teams','low_peak_observations','low_peak_frequency','P10_linear','P10_inverseCDF']].to_string(index=False),flush=True)
    print(exact[exact.score_peak.eq('low')][['absent_worker','B8L2','nodes','floor_turn5_n',*[c+'_path_count' for c in cohorts]]].to_string(index=False),flush=True)


if __name__=='__main__':main()
