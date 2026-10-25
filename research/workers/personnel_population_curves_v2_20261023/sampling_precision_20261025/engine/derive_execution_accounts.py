"""Rebuild computation-budget overlap and benchmark provenance from exact keys."""
from pathlib import Path
import argparse,json
import pandas as pd


def run(base,repo):
    src=repo/'research/workers/personnel_population_curves_v2_20261023'
    cols=['team_key','pool_id','image','building','layer','difficulty','pool_n','n',
          'endpoint_source','requested_natural','requested_policy','requested_exact']
    d=pd.read_csv(base/'design/ENDPOINT_DEPENDENCIES.csv.gz',usecols=cols)
    d['purpose_pattern']=d[['requested_natural','requested_policy','requested_exact']].apply(
        lambda r:'+'.join(x for x,f in zip(['natural','policy','exact_margin'],r) if f),axis=1)
    summary=d.groupby(['layer','difficulty','purpose_pattern','endpoint_source']).agg(
        endpoints=('team_key','size'),pools=('pool_id','nunique'),buildings=('building','nunique')).reset_index()
    summary.to_csv(base/'engine/BUDGET_BY_PURPOSE.csv',index=False)
    e=pd.read_csv(base/'design/EXACT_MARGINAL_TEAM_DESIGN.csv.gz',usecols=['team_key','exact_kind','k'])
    e=e.merge(d[['team_key','endpoint_source']],on='team_key',validate='one_to_one')
    e.groupby(['exact_kind','endpoint_source']).size().rename('endpoints').reset_index().to_csv(
        base/'engine/EXACT_ANCHOR_ENDPOINT_REUSE.csv',index=False)
    q=pd.read_csv(base/'engine/benchmark/REQUESTS.csv.gz',dtype={'seed':str})
    keys=set(q.team_key);old=set()
    for chunk in pd.read_csv(src/'results/ENDPOINT_SCALARS.csv.gz',usecols=['team_key'],chunksize=50000):
        old.update(set(chunk.team_key)&keys)
    r=q.assign(present_in_original_population_scalar=q.team_key.isin(old))
    main=set(d.loc[d.endpoint_source.eq('reused_new_benchmark_20261025'),'team_key'])
    r['used_as_new_endpoint_in_main']=r.team_key.isin(main)
    r['retained_as_timing_only_new_endpoint']=~r.present_in_original_population_scalar&~r.used_as_new_endpoint_in_main
    r.to_csv(base/'engine/benchmark/BENCHMARK_PROVENANCE.csv',index=False)
    x=dict(native_evaluations=len(r),explicit_saved_compatibility_checks=int(r.purpose.eq('saved_endpoint_compatibility').sum()),
        all_old_endpoint_recomputations_in_timing=int(r.present_in_original_population_scalar.sum()),
        genuinely_new_benchmark_endpoints=int((~r.present_in_original_population_scalar).sum()),
        reused_new_in_registered_main=int(r.used_as_new_endpoint_in_main.sum()),
        new_for_timing_only=int(r.retained_as_timing_only_new_endpoint.sum()))
    (base/'engine/benchmark/BENCHMARK_PROVENANCE.json').write_text(json.dumps(x,indent=2))
    print(json.dumps(x),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--repo',type=Path)
    a=p.parse_args();run(a.base,a.repo or a.base/'repo')
