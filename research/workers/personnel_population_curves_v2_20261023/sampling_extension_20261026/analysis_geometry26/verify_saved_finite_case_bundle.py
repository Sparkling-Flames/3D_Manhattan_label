"""Independently re-read the complete small case data and recompute its results.

Usage: python verify_saved_finite_case_bundle.py --case-dir finite_margin_cases
Needs no large repository input: all 89 teams, geometry, reference and all
registered paths used in this case are contained in the small case bundle.
"""
from __future__ import annotations
import argparse,gzip,json
from pathlib import Path
import numpy as np
import pandas as pd
from geometry_extension import COHORTS,distance_matrices,ustat,save_json
from finite_margin_cases import describe

def verify(folder):
    teams=pd.read_csv(folder/'EXACT_TEAMS_AND_NEW_PATH_FREQUENCIES.csv')
    paths=pd.read_csv(folder/'REGISTERED_PATH_ENDPOINT_BINDINGS.csv.gz')
    orders=pd.read_csv(folder/'EXACT_REGISTERED_ORDERS_AND_SEEDS.csv.gz',dtype={'seed':'string','master_seed':'string'})
    saved=pd.read_csv(folder/'FINITE_CATALOGUE_SAMPLING_COMPARISON.csv')
    saved_geo=pd.read_csv(folder/'FINITE_CATALOGUE_GEOMETRY_COMPARISON.csv')
    with gzip.open(folder/'FINITE_TEAM_GEOMETRY_AND_REFERENCES.json.gz','rt') as f:geometry=json.load(f)
    assert len(teams)==89
    assert not teams.team_key.duplicated().any()
    assert not paths.duplicated(['path_id','k']).any()
    assert set(paths.path_id)==set(orders.path_id)
    assert orders[orders.batch.isin(['extension_stage1_104','extension_stage2_104'])].path_id.nunique()==624
    o=orders.set_index('path_id').worker_order.to_dict()
    for r in paths.itertuples():assert set(o[r.path_id].split('|')[:r.k])==set(r.member_workers.split('|'))
    lookup=teams.set_index('team_key')
    for r in paths.itertuples():
        q=lookup.loc[r.team_key,'B8L2'];assert np.isclose(q,r.B8L2,equal_nan=True)
    largest=0.;largest_geo=0.;comparisons=0
    for case in geometry:
        pid=case['pool_id'];rows={r['team_key']:r for r in case['teams']}
        for cohort in ['exact_uniform_catalogue',*COHORTS]:
            exact=cohort=='exact_uniform_catalogue'
            if exact:x=teams[teams.pool_id.eq(pid)]
            else:
                x=paths[paths.pool_id.eq(pid)&paths.batch.isin(COHORTS[cohort])]
                if not COHORTS[cohort]<=set(paths[paths.pool_id.eq(pid)].batch):continue
            result=describe(x.B8L2,exact)
            s=saved[saved.pool_id.eq(pid)&saved.cohort.eq(cohort)].iloc[0]
            for field in ['mean_Q','P10_linear','P10_inverse_cdf','SD_Q','mean_Q_mcse']:
                assert pd.isna(result[field])==pd.isna(s[field])
                if np.isfinite(result[field]):largest=max(largest,abs(result[field]-s[field]))
            matrices,_=distance_matrices(x.team_key.tolist(),rows)
            for metric,matrix in matrices.items():
                value,_=ustat(matrix,exact)
                ss=saved_geo[saved_geo.pool_id.eq(pid)&saved_geo.cohort.eq(cohort)&saved_geo.metric.eq(metric)].iloc[0]
                for field in ['mean','mcse']:
                    assert pd.isna(value[field])==pd.isna(ss[field])
                    if np.isfinite(value[field]):largest_geo=max(largest_geo,abs(value[field]-ss[field]))
                comparisons+=1
    assert largest<1e-10 and largest_geo<1e-10
    from PIL import Image
    with Image.open(folder/'F_GEOMETRY_FINITE_FREQUENCY.png') as im:im.load();size=im.size
    receipt=dict(actual_team_rows=len(teams),actual_registered_path_rows=len(paths),actual_order_rows=len(orders),
        new_actual_registered_orders=624,all_csv_gzip_and_json_gzip_consumed_to_eof=True,
        q_max_absolute_recompute_error=largest,geometry_max_absolute_recompute_error=largest_geo,
        geometry_metric_comparisons=comparisons,full_png_decode_pixels=list(size),new_fusions=0)
    save_json(folder/'SMALL_BUNDLE_RECOMPUTE_RECEIPT.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case-dir',type=Path,required=True);a=p.parse_args();verify(a.case_dir.resolve())
