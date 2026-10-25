"""One concise exact-population example of a failure missed by the old 24.

All N-1 margins are scanned once after the registered experiment is complete.
No new endpoint request, outcome-dependent seed or team is generated.
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
    pools=pd.read_csv(base/'design/ACTUAL_POOLS.csv');pools=pools[pools.layer.isin(['ordinary_manual','doorway_manual'])]
    exact=pd.read_csv(root/'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz',low_memory=False)
    exact=exact[exact.pool_id.isin(pools.pool_id) & exact.k.eq(exact.pool_n-1)].copy()
    assert not exact.team_key.duplicated().any()
    old=pd.read_csv(base/'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz',low_memory=False)
    old=old[old.policy.eq('natural_random') & old.pool_id.isin(pools.pool_id) & old.k.eq(old.pool_n-1)].copy();old['batch']='old24'
    new=pd.read_csv(root/'new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz',low_memory=False,dtype={'seed':str,'master_seed':str})
    new=new[new.policy.eq('natural_random') & new.pool_id.isin(pools.pool_id) & new.k.eq(new.pool_n-1)].copy()
    new['batch']=new.batch.replace({'balanced_new24':'new24','focus_new48':'focus48'})
    relevant=['pool_id','path_id','k','team_key','batch','score_failure_nonpolicy']
    sampled=pd.concat([old[relevant],new[relevant]],ignore_index=True)
    rows=[]
    for pid,g in exact.groupby('pool_id'):
        meta=pools[pools.pool_id.eq(pid)].iloc[0]
        assert len(g)==meta.pool_n
        o=sampled[sampled.pool_id.eq(pid)&sampled.batch.eq('old24')]
        n=sampled[sampled.pool_id.eq(pid)&~sampled.batch.eq('old24')]
        failures=int(g.score_failure_nonpolicy.sum())
        rows.append(dict(pool_id=pid,image=meta.image,building=meta.building,layer=meta.layer,difficulty=meta.difficulty,pool_n=int(meta.pool_n),k=int(meta.pool_n)-1,
            exact_teams=len(g),exact_failures=failures,exact_failure_probability=failures/len(g),old24_attempts=len(o),old24_failures=int(o.score_failure_nonpolicy.sum()),new_attempts=len(n),new_failures=int(n.score_failure_nonpolicy.sum()),
            is_missed_then_observed=failures>0 and int(o.score_failure_nonpolicy.sum())==0 and int(n.score_failure_nonpolicy.sum())>0))
    allrows=pd.DataFrame(rows);eligible=allrows[allrows.is_missed_then_observed].copy()
    allrows.to_csv(out/'MISSED_FAILURE_CANDIDATE_SCAN.csv',index=False)
    if eligible.empty:
        (out/'MISSED_FAILURE_SELECTION.json').write_text(json.dumps(dict(eligible_examples=0,selected=None,reason='No exact failure absent from all old24 but observed in new registered paths'),indent=2));return
    priority={'uNb9QFRL6hY-47':0,'wc2JMjhGNzB-46':1}
    eligible['candidate_priority']=eligible.image.map(priority).fillna(2)
    eligible['ordinary_priority']=np.where(eligible.layer.eq('ordinary_manual'),0,1)
    chosen=eligible.sort_values(['candidate_priority','ordinary_priority','exact_failure_probability','image']).iloc[0]
    pid=chosen.pool_id;g=exact[exact.pool_id.eq(pid)];bad=g[g.score_failure_nonpolicy].copy();meta=pools[pools.pool_id.eq(pid)].iloc[0]
    workers=set(str(meta.workers).split('|'))
    has_focus=bool(((sampled.pool_id==pid)&sampled.batch.eq('focus48')).any())
    team_rows=[]
    for r in bad.to_dict('records'):
        member=str(r['member_workers']).split('|');absent='|'.join(sorted(workers-set(member)))
        counts={b:int(((sampled.pool_id==pid)&sampled.batch.eq(b)&sampled.team_key.eq(r['team_key'])).sum()) for b in ['old24','new24','focus48']}
        item={c:r.get(c) for c in ['team_key','pool_id','image','image_id','building','k','reference_id','reference_version','member_workers','member_object_ids','score_status','geometry_status','order_status','nodes','minimum_support','score_failure_nonpolicy','B8L2','geometry_state_pointer']}
        item.update(absent_worker=absent,finite_probability=1/int(meta.pool_n),old24_observations=counts['old24'],new24_observations=counts['new24'],extra48_observations=counts['focus48'] if has_focus else np.nan,combined48_observations=counts['old24']+counts['new24'],combined96_observations=sum(counts.values()) if has_focus else np.nan)
        team_rows.append(item)
    pd.DataFrame(team_rows).to_csv(out/'MISSED_FAILURE_SELECTED_TEAMS.csv',index=False)
    own=sampled[sampled.pool_id.eq(pid)].copy();own.to_csv(out/'MISSED_FAILURE_SELECTED_PATHS.csv',index=False)
    summaries=[]
    for name,batches in {'old24':['old24'],'new24':['new24'],'combined48':['old24','new24'],'focus48':['focus48'],'combined96':['old24','new24','focus48']}.items():
        if name in ['focus48','combined96'] and not has_focus:continue
        x=own[own.batch.isin(batches)]
        if not len(x):continue
        summaries.append(dict(sample=name,attempted_paths=len(x),unique_teams=x.team_key.nunique(),observed_failure_paths=int(x.score_failure_nonpolicy.sum()),observed_failure_rate=x.score_failure_nonpolicy.mean(),true_finite_failure_probability=chosen.exact_failure_probability,probability_of_no_failures_if_repeated=(1-chosen.exact_failure_probability)**len(x)))
    pd.DataFrame(summaries).to_csv(out/'MISSED_FAILURE_SELECTED_SUMMARY.csv',index=False)
    receipt=dict(eligible_examples=len(eligible),selected_image=chosen.image,selected_pool_id=pid,exact_failures=int(chosen.exact_failures),exact_teams=int(chosen.exact_teams),selection_rule='Prefer the two previously suggested images if eligible; otherwise ordinary Manual, smaller positive exact risk, then image name. One case only.',new_fusions=0)
    (out/'MISSED_FAILURE_SELECTION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
