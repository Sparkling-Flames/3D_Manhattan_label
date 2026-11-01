"""Independent checks of delivered image-response tables; never modifies sources."""
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[3] / 'research/workers/image_response_v21_20261101'
SRC = BASE / 'HOHONET_v21_image_response_20261101'
OUT = BASE / 'independent_audit'


def close(actual, expected):
    assert np.allclose(actual, expected, rtol=1e-8, atol=1e-7, equal_nan=True), (actual, expected)


def onset(values, valid, n, tol, minimum):
    for k in range(3, n - max(5, math.ceil(.15*n)) + 1):
        tail = values[k-1:n]
        if len(tail) == n-k+1 and np.isfinite(tail).all() and min(valid[k-1:n]) >= minimum and np.ptp(tail) <= tol + 1e-9:
            return k
    return np.nan


def main():
    assert onset(np.ones(10), np.full(10,256),10,2,64)==3
    assert np.isnan(onset(np.arange(10),np.full(10,256),10,2,64))
    OUT.mkdir(exist_ok=True)
    counts = dict(pools=0, rows=0, k_cells=0, paired_metric_rows=0, onset_rows=0)
    primary=[]
    for domain in ['manual','doorway']:
        idx=pd.read_csv(SRC/f'stage03_response/{domain}/ANALYSIS_POOL_INDEX.csv')
        for entry in idx.itertuples():
            d=pd.read_csv(SRC/entry.source_file,low_memory=False)
            dest=SRC/entry.output_dir
            counts['pools']+=1
            counts['rows']+=len(d)
            if not len(d):
                assert entry.N==0
                continue
            assert not d.duplicated(['replicate_id','k']).any()
            assert d.pool_id.eq(entry.pool_id).all()
            assert d.N.eq(entry.N).all()
            # Exact original-answer sets must grow by one along each path.
            for _,g in d.groupby('replicate_id',sort=False):
                prev=set();last=0
                for row in g.sort_values('k').itertuples():
                    members=set(str(row.member_object_ids).split('|'))
                    assert len(members)==row.k and prev.issubset(members)
                    assert row.k==last+1
                    prev=members;last=row.k
                assert last==entry.N
            expected=pd.read_csv(dest/'POOL_K_STATISTICS.csv.gz').set_index('k')
            recalcs={}
            for k,g in d.groupby('k'):
                e=expected.loc[k]; assert len(g)==e.path_rows and g.team_key.nunique()==e.unique_teams
                for metric in ['B8L2','D10','IoU3D100']:
                    x=g[metric].to_numpy(float);x=x[np.isfinite(x)]
                    stats={'valid_n':len(x),'mean':np.mean(x) if len(x) else np.nan,
                           'p10':np.quantile(x,.1) if len(x) else np.nan,
                           'sd':np.std(x,ddof=1) if len(x)>1 else np.nan}
                    for key,value in stats.items():close(value,e[f'{metric}_{key}'])
                if k>=3: close(g.complete_evaluable.mean(),e.complete_evaluable_rate)
                recalcs[k]=[e.B8L2_mean,e.B8L2_p10,e.B8L2_sd,e.B8L2_valid_n,e.complete_evaluable_rate,e.complete_evaluable_valid_n]
                counts['k_cells']+=1
            status=pd.read_csv(dest/'STATUS_BY_K.csv.gz').set_index(['k','status_class'])
            observed=d.groupby(['k','status_class']).size()
            assert len(status)==len(observed)
            for key,v in observed.items(): assert v==status.loc[key,'path_n']
            s=pd.read_csv(dest/'PLATEAU_SENSITIVITY.csv.gz')
            arr=np.array([recalcs[k] for k in range(1,entry.N+1)])
            for r in s.itertuples():
                if r.metric not in ['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate']:continue
                c={'B8L2_mean':0,'B8L2_p10':1,'B8L2_sd':2,'complete_evaluable_rate':4}[r.metric]
                result=onset(arr[:,c],arr[:,5 if c==4 else 3],entry.N,r.tolerance,r.minimum_valid_paths)
                close(result,r.onset_k);counts['onset_rows']+=1
                if r.metric=='B8L2_mean' and r.primary_rule:
                    primary.append({'pool_id':entry.pool_id,'domain':entry.domain,'difficulty':entry.difficulty_en,'N':entry.N,'onset':result})
            try:
                ps=pd.read_csv(dest/'PATH_CHANGE_SUMMARY.csv.gz')
            except pd.errors.EmptyDataError:
                assert entry.N <= 3  # No pair of main-analysis counts exists.
                continue
            ps=ps[ps.metric.isin(['B8L2','D10','IoU3D100','complete_evaluable'])]
            pivots={m:d.pivot(index='replicate_id',columns='k',values=m) for m in ps.metric.unique()}
            for r in ps.itertuples():
                p=pivots[r.metric];x=p[r.k_from].to_numpy(float);y=p[r.k_to].to_numpy(float)
                ok=np.isfinite(x)&np.isfinite(y);v=y[ok]-x[ok]
                assert int(ok.sum())==r.both_valid_n
                close(v.mean() if len(v) else np.nan,r.mean_delta)
                close(np.abs(v).mean() if len(v) else np.nan,r.mean_abs_delta)
                assert (v>1e-9).sum()==r.positive_paths and (v< -1e-9).sum()==r.negative_paths
                counts['paired_metric_rows']+=1
            if counts['pools']%40==0: print(counts,flush=True)
    pd.DataFrame(primary).to_csv(OUT/'INDEPENDENT_ONSETS.csv',index=False)
    (OUT/'SCALAR_CHECKS.json').write_text(json.dumps(counts,indent=2),encoding='utf8')
    print(counts,flush=True)


def audit_live_sources():
    """Compare delivered analysis inputs with current saved path scores."""
    repo=Path(__file__).resolve().parents[3]
    counts={'manual_rows':0,'doorway_rows':0,'formula_rows':0,'formula_max_error':0.0}
    ix=pd.read_csv(SRC/'stage02_normalized/manual/POOL_INDEX.csv').set_index('pool_id')
    for r in pd.read_csv(SRC/'stage03_response/manual/ANALYSIS_POOL_INDEX.csv').itertuples():
        d=pd.read_csv(SRC/r.source_file,low_memory=False)
        raw=pd.read_csv(repo/ix.loc[r.pool_id,'source_table'],low_memory=False)
        raw['replicate_id']=raw.stratum.astype(str)+'::'+raw.path_id.astype(str)
        keys=['replicate_id','k'];raw=raw.set_index(keys).loc[pd.MultiIndex.from_frame(d[keys])].reset_index()
        assert len(raw)==len(d)
        for c in ['B8L2','D10','IoU3D100','nodes','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','complete_evaluable']:
            close(pd.to_numeric(d[c]),pd.to_numeric(raw[c]))
        for c in ['team_key','member_object_ids','reference_id','reference_version','score_status']:
            assert d[c].fillna('').astype(str).equals(raw[c].fillna('').astype(str)),(r.pool_id,c)
        est=100/(1+np.hypot(d.B8_floor_block,d.B8_direction_block)+d.B8_global_height_block+d.B8_local_height_block)
        ok=d.B8L2.notna() & est.notna()
        close(est[ok],d.loc[ok,'B8L2'])
        counts['formula_rows']+=int(ok.sum())
        if ok.any():counts['formula_max_error']=max(counts['formula_max_error'],float((est[ok]-d.loc[ok,'B8L2']).abs().max()))
        counts['manual_rows']+=len(d)
    raw=pd.read_csv(repo/'research/data/doorway_review_20261030/screen439_results_20261031/PAIRED_PATH_VALUES.csv.gz')
    for r in pd.read_csv(SRC/'stage03_response/doorway/ANALYSIS_POOL_INDEX.csv').itertuples():
        d=pd.read_csv(SRC/r.source_file,low_memory=False)
        if not len(d):continue
        s=raw[raw.pool_id.eq(r.pool_id)].rename(columns={'base_replicate':'replicate_id'})
        keys=['replicate_id','k'];s=s.set_index(keys).loc[pd.MultiIndex.from_frame(d[keys])].reset_index()
        assert len(s)==len(d)
        for c in ['B8L2','D10','IoU3D100','complete_evaluable']:close(d[c],s[c])
        assert d.member_object_ids.equals(s.member_object_ids)
        assert d.endpoint_source_key.equals(s.physical_team_key)
        counts['doorway_rows']+=len(d)
    (OUT/'LIVE_SCORES_CHECKS.json').write_text(json.dumps(counts,indent=2),encoding='utf8')
    print(counts,flush=True)


if __name__=='__main__':
    main()
    audit_live_sources()
