"""Explain two existing N-1 cells with rare success missed by the original 24.

Uses only completed registered results. No fusion, case-image or seed search.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from population_paths import add_population_root_argument,resolve_population_root
from safe_io import install_safe_csv_writer
install_safe_csv_writer()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',required=True);ap.add_argument('--out',required=True);add_population_root_argument(ap);a=ap.parse_args()
    root=Path(a.study).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    base=resolve_population_root(root,a.population_root)
    pools=pd.read_csv(base/'design/ACTUAL_POOLS.csv')
    chosen=['B6ByNegPMKs-42','b8cTxDM8gDG-08']
    pools=pools[pools.image.isin(chosen)&pools.layer.eq('doorway_manual')]
    assert len(pools)==2
    exact=pd.read_csv(root/'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz',low_memory=False)
    exact=exact[exact.pool_id.isin(pools.pool_id)&exact.k.eq(exact.pool_n-1)].copy()
    assert len(exact)==69
    fields=['pool_id','path_id','k','team_key','batch','B8L2','D10','score_failure_nonpolicy','score_status','policy_deferred','replicate','seed']
    old=pd.read_csv(base/'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz',low_memory=False,dtype={'seed':str,'master_seed':str})
    old=old[old.pool_id.isin(pools.pool_id)&old.policy.eq('natural_random')&old.k.eq(old.pool_n-1)].copy();old['batch']='old24'
    new=pd.read_csv(root/'new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz',low_memory=False,dtype={'seed':str,'master_seed':str})
    new=new[new.pool_id.isin(pools.pool_id)&new.policy.eq('natural_random')&new.k.eq(new.pool_n-1)].copy()
    new['batch']=new.batch.replace({'balanced_new24':'new24','focus_new48':'focus48'})
    paths=pd.concat([old.reindex(columns=fields),new.reindex(columns=fields)],ignore_index=True)
    exact['absent_worker']=''
    for pid,g in exact.groupby('pool_id'):
        p=pools[pools.pool_id.eq(pid)].iloc[0];workers=set(str(p.workers).split('|'))
        exact.loc[g.index,'absent_worker']=['|'.join(sorted(workers-set(str(x).split('|')))) for x in g.member_workers]
    exact.to_csv(out/'RARE_SUCCESS_EXACT_TEAMS.csv.gz',index=False)
    paths.to_csv(out/'RARE_SUCCESS_REGISTERED_PATHS.csv',index=False)
    summaries=[]
    for pid,g in exact.groupby('pool_id'):
        p=pools[pools.pool_id.eq(pid)].iloc[0]
        success=g[g.B8L2.notna()]
        assert len(success)==1 and int(g.score_failure_nonpolicy.sum())==len(g)-1
        own=paths[paths.pool_id.eq(pid)]
        assert len(own)==96
        meta=dict(pool_id=pid,image=p.image,building=p.building,layer=p.layer,pool_n=int(p.pool_n),k=int(p.pool_n)-1,
                  finite_teams=len(g),finite_scorable_teams=len(success),finite_failed_teams=int(g.score_failure_nonpolicy.sum()),
                  true_success_probability=len(success)/len(g),exact_conditional_Q=float(success.B8L2.iloc[0]),
                  success_team_key=success.team_key.iloc[0],success_absent_worker=success.absent_worker.iloc[0])
        cohorts={'old24':['old24'],'new24':['new24'],'combined48':['old24','new24'],
                 'independent_new72':['new24','focus48'],'combined96':['old24','new24','focus48']}
        for label,batches in cohorts.items():
            x=own[own.batch.isin(batches)]
            summaries.append(dict(meta,sample=label,attempted_paths=len(x),unique_teams=x.team_key.nunique(),
                                  scorable_paths=int(x.B8L2.notna().sum()),failed_paths=int(x.score_failure_nonpolicy.sum()),
                                  conditional_Q=x.B8L2.mean(),probability_of_zero_scorable_in_R=(1-meta['true_success_probability'])**len(x)))
    pd.DataFrame(summaries).to_csv(out/'RARE_SUCCESS_SUPPORT_SUMMARY.csv',index=False)
    success=exact[exact.B8L2.notna()]
    success.to_csv(out/'RARE_SUCCESS_ONLY_EVALUABLE_TEAMS.csv',index=False)
    (out/'RARE_SUCCESS_RECEIPT.json').write_text(json.dumps(dict(source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',
        images=chosen,exact_team_rows=len(exact),registered_path_rows=len(paths),summary_rows=len(summaries),new_fusion_calls=0,
        selection='The two already identified doorway N-1 pools with original24 all failed but a single evaluable finite team; no new geometry or image case.'),ensure_ascii=False,indent=2))
    print(pd.DataFrame(summaries)[['image','sample','finite_teams','exact_conditional_Q','success_absent_worker','attempted_paths','scorable_paths','failed_paths']].to_string(index=False),flush=True)


if __name__=='__main__':main()
