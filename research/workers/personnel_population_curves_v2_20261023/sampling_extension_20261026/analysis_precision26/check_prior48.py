#!/usr/bin/env python3
"""Recompute the supplied old48 precision counts; planning only, no fusion.

The square-root projections are explicitly local approximations, not claimed
coverage for quantiles, unseen modes or future observed estimates.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json,math,os
import numpy as np
import pandas as pd

def save(df,path):
    body=df.to_csv(index=False).encode('utf-8-sig')
    payload=gzip.compress(body,mtime=0) if path.suffix=='.gz' else body
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
    decoded=gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes()
    assert decoded==body
    lines=list(csv.reader(io.StringIO(decoded.decode('utf-8-sig'))))
    assert len(lines)-1==len(df) and all(len(x)==len(lines[0]) for x in lines)
    return dict(path=path.name,rows=len(df),fields=len(df.columns),sha256=hashlib.sha256(payload).hexdigest())

def main(prior,out):
    out.mkdir(parents=True,exist_ok=True)
    source=prior/'analysis_precision/new_results/NATURAL_POOL_K_BATCH_PRECISION.csv.gz'
    df=pd.read_csv(source,low_memory=False)
    old=df[df.version.eq('pooled48')].copy()
    old['P10_boot95_halfwidth']=(old.Q_p10_boot95_high-old.Q_p10_boot95_low)/2
    rows=[]
    for k,g in old[old.layer.eq('ordinary_manual')&old.pool_n.ge(30)&old.k.isin([3,6,10,20])].groupby('k'):
        rows.append(dict(k=int(k),images=g.pool_id.nunique(),buildings=g.building.nunique(),
            mean_MCSE_gt1=int(g.Q_mean_MCSE_analytic.gt(1).sum()),
            P10_empirical_halfwidth_gt2=int(g.P10_boot95_halfwidth.gt(2).sum()),
            mean_MCSE_missing=int(g.Q_mean_MCSE_analytic.isna().sum()),
            P10_empirical_halfwidth_missing=int(g.P10_boot95_halfwidth.isna().sum()),
            mean_MCSE_median=g.Q_mean_MCSE_analytic.median(),
            P10_empirical_halfwidth_median=g.P10_boot95_halfwidth.median()))
    counts=pd.DataFrame(rows)
    expected={3:(122,137),6:(72,110),10:(50,80),20:(31,44)}
    assert all((r.mean_MCSE_gt1,r.P10_empirical_halfwidth_gt2)==expected[r.k]
               and r.images==157 and r.buildings==22 for r in counts.itertuples())
    plans=[]
    # The capacity restriction keeps the complete low/medium/high panel on
    # the same images; per-image full-curve maxima also include actual N.
    for layer in ['ordinary_manual','doorway_manual']:
        base=old[old.layer.eq(layer)]
        for diff in ['全部']+(['简单','中等','困难'] if layer=='ordinary_manual' else []):
            d=base if diff=='全部' else base[base.difficulty.eq(diff)]
            for panel,minimum in [('all_eligible',0),('fixed_N_ge30',30),('fixed_N_ge35',35)]:
                h=d[d.pool_n.ge(minimum)]
                if h.empty:continue
                for target in [48,96,128,152,160,192,256,304,384,512]:
                    factor=math.sqrt(48/target)
                    for k in [3,6,10,20,30,35]:
                        g=h[h.k.eq(k)]
                        if g.empty:continue
                        mean=g.Q_mean_MCSE_analytic*factor;tail=g.P10_boot95_halfwidth*factor
                        plans.append(dict(layer=layer,difficulty=diff,panel=panel,k=k,target_R=target,
                            images=len(g),buildings=g.building.nunique(),sqrt_variance_factor=factor,
                            projected_mean_MCSE_median=mean.median(),projected_mean_MCSE_p90=mean.quantile(.9),
                            projected_mean_MCSE_le1=int(mean.le(1).sum()),
                            local_projected_P10_halfwidth_median=tail.median(),
                            local_projected_P10_halfwidth_le2=int(tail.le(2).sum()),
                            zero_fail_one_sided95_upper=1-.05**(1/target),
                            projection_is_not_finite_population_truth=True))
    full=[]
    h=old[old.k.ge(3)&old.k.lt(old.pool_n)]
    for pid,g in h.groupby('pool_id'):
        row=g.iloc[0]
        se=g.Q_mean_MCSE_analytic
        full.append(dict(pool_id=pid,image=row.image,building=row.building,layer=row.layer,
            difficulty=row.difficulty,pool_n=int(row.pool_n),evaluated_k=len(g),
            mean_MCSE_max=se.max(),mean_MCSE_max_k=int(g.loc[se.idxmax(),'k']) if se.notna().any() else np.nan,
            mean_MCSE_gt1_k=int(se.gt(1).sum()),mean_MCSE_missing_k=int(se.isna().sum()),
            P10_halfwidth_max=g.P10_boot95_halfwidth.max(),P10_halfwidth_gt2_k=int(g.P10_boot95_halfwidth.gt(2).sum())))
    receipts=[save(counts,out/'OLD48_SUPPLIED_PRECISION_COUNTS.csv'),
              save(pd.DataFrame(plans),out/'BUDGET_PRECISION_PROJECTIONS_NOT_OBSERVED.csv'),
              save(pd.DataFrame(full),out/'OLD48_PER_IMAGE_FULL_CURVE_DIAGNOSTIC.csv')]
    receipt=dict(source=str(source),source_sha256=hashlib.file_digest(source.open('rb'),'sha256').hexdigest(),
        source_rows=len(df),verified_supplied_eight_counts=True,new_fusion=0,new_random_paths=0,
        source_intervals='original saved 2000 whole-path bootstrap intervals, not recalculated with different seeds',outputs=receipts)
    (out/'PRIOR48_CHECK_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(counts.to_string(index=False))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--prior',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    q=a.parse_args();main(q.prior,q.out)
