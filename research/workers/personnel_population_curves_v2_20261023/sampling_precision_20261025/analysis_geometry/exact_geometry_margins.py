"""Exact geometry distances in enumerated finite k-person-team populations.

Each of the M distinct teams has probability 1/M in one draw. Two independent
draws therefore assign weight 1/M**2 to each ordered pair including identical
teams. Conditional valid-metric estimates use the corresponding valid mass.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
from safe_io import install_safe_csv_writer
install_safe_csv_writer()
from geometry_sampling_precision import META,distance_matrices,read_new_pool,ustat,prepare_compact_new


def one_pool(pid,d,cache,new_dirs):
    combined=Path(cache).parent/'combined_pool_geometry_cache'/(pid+'.pkl')
    if combined.exists():
        with combined.open('rb') as f:rows=pickle.load(f)
    else:
        with (Path(cache)/(pid+'.pkl')).open('rb') as f:rows=pickle.load(f)
        for dr in new_dirs:
            for key,r in read_new_pool(dr,pid).items():rows.setdefault(key,r)
    out=[];missing=[]
    for k,g in d.groupby('k'):
        if int(k)==2:continue
        absent=~g.team_key.isin(rows)
        if absent.any():
            missing.extend(g.loc[absent,['pool_id','k','team_key','exact_kind']].to_dict('records'));continue
        assert not g.team_key.duplicated().any()
        assert g.finite_team_space.nunique()==1 and len(g)==g.finite_team_space.iloc[0]
        assert np.max(np.abs(g.marginal_weight.to_numpy()-1/len(g)))<1e-12
        meta={c:g.iloc[0][c] for c in META}
        for metric,matrix in distance_matrices(g.team_key.tolist(),rows).items():
            result,_=ustat(matrix,exact_population=True)
            out.append(dict(meta,k=int(k),exact_kind=g.exact_kind.iloc[0],metric=metric,
                finite_team_space=len(g),valid_fraction=result['valid_paths']/len(g),
                exact_mean=result['mean'],exact_valid_teams=result['valid_paths'],
                exact_pair_denominator=result['valid_pairs'],mcse=0. if np.isfinite(result['mean']) else np.nan))
    return out,missing


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--design',required=True);ap.add_argument('--geometry-results',required=True);ap.add_argument('--new-endpoints-dir',action='append',default=[]);ap.add_argument('--jobs',type=int,default=3);a=ap.parse_args()
    p=Path(a.geometry_results);d=pd.read_csv(a.design)
    new_dirs=[prepare_compact_new(x,p) for x in a.new_endpoints_dir]
    rows=[];missing=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        todo=[ex.submit(one_pool,pid,g,p/'old_pool_geometry_cache',new_dirs) for pid,g in d.groupby('pool_id',sort=False)]
        for task in concurrent.futures.as_completed(todo):
            rr,mm=task.result();rows.extend(rr);missing.extend(mm)
    result=pd.DataFrame(rows);result.to_csv(p/'EXACT_GEOMETRY_MARGINALS.csv',index=False)
    pd.DataFrame(missing,columns=['pool_id','k','team_key','exact_kind']).to_csv(p/'EXACT_GEOMETRY_UNCOMPUTED_LINKS.csv.gz',index=False)
    path=p/'GEOMETRY_PATH_PRECISION.csv.gz'
    if path.exists():
        sampled=pd.read_csv(path)
        merged=sampled.merge(result[['pool_id','k','metric','exact_kind','finite_team_space','exact_mean','exact_valid_teams','valid_fraction']],on=['pool_id','k','metric'],how='inner',validate='many_to_one')
        merged['error_from_exact']=merged['mean']-merged.exact_mean
        merged['absolute_error_from_exact']=merged.error_from_exact.abs()
        merged['nominal95_covers_exact']=np.where(merged.mcse.notna() & merged.exact_mean.notna(),merged.absolute_error_from_exact<=1.96*merged.mcse+1e-12,np.nan)
        merged.to_csv(p/'GEOMETRY_SAMPLE_VS_EXACT.csv.gz',index=False)
        summary=[]
        for (cohort,kind,metric,layer),g in merged.groupby(['cohort','exact_kind','metric','layer']):
            for difficulty in ['ALL',*sorted(g.difficulty.dropna().unique())]:
                x=g if difficulty=='ALL' else g[g.difficulty.eq(difficulty)]
                good=x[x.error_from_exact.notna()]
                summary.append(dict(cohort=cohort,exact_kind=kind,metric=metric,layer=layer,difficulty=difficulty,
                    image_k_rows=len(good),images=good.image.nunique(),buildings=good.building.nunique(),
                    signed_error_mean=good.error_from_exact.mean(),absolute_error_median=good.absolute_error_from_exact.median(),
                    absolute_error_p90=good.absolute_error_from_exact.quantile(.9),absolute_error_max=good.absolute_error_from_exact.max(),
                    rmse=np.sqrt(np.mean(good.error_from_exact**2)),nominal95_coverage=good.nominal95_covers_exact.mean(),
                    coverage_denominator=int(good.nominal95_covers_exact.notna().sum())))
        pd.DataFrame(summary).to_csv(p/'GEOMETRY_SAMPLE_VS_EXACT_SUMMARY.csv',index=False)
    (p/'EXACT_GEOMETRY_RECEIPT.json').write_text(json.dumps(dict(exact_metric_rows=len(result),missing_registered_team_links=len(missing),finite_pair_weights='All ordered valid-team pairs including zero self-pairs, denominator valid_M**2',fusion_calls=0),indent=2))
    print('Exact geometry',len(result),'missing',len(missing),flush=True)


if __name__=='__main__':main()
