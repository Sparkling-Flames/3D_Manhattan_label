"""Exploratory full-curve shape summary; no new endpoints or altered fusion.

Registered during execution, before inspecting the new full-curve results.
Odd k >=5 is contrasted with the mean of its even neighbours. This removes a
locally linear trend, but is an association with the frozen ceil(k/2) threshold,
not a causal vote-component ablation. Resample complete paths via saved weights.
"""
from pathlib import Path
import argparse,json,sys,os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import pandas as pd

COHORTS=['old48','stage1_104','stage2_104','new208','pooled256']
METRICS=['Q_mean','D10_mean','Q_p10','Q_sd_ddof1','nodes_mean','floor_turn5_mean',
         'actual_consensus_failure_rate','output_unscoreable_rate']
REGIONS={'low_5_9':[5,7,9],'middle_11_19':[11,13,15,17,19],
         'late_21_29':[21,23,25,27,29],'nearfull_31_33':[31,33]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);args=ap.parse_args();base=args.base.resolve()
    sys.path.insert(0,str(base/'analysis_precision26'))
    from precision_core import save_csv,save_json,seed_for
    from summarize_natural import estimate
    out=base/'analysis_shape26/results';out.mkdir(parents=True,exist_ok=True)
    source=base/'analysis_precision26/results_stage2';curves=pd.read_csv(source/'NATURAL_CURVES.csv.gz')
    meta=curves[['pool_id','image','building','layer','difficulty','pool_n']].drop_duplicates('pool_id').sort_values('pool_id')
    meta=meta[meta.pool_n.ge(30) & meta.layer.isin(['ordinary_manual','doorway_manual'])].reset_index(drop=True)
    assert len(meta[meta.layer.eq('ordinary_manual')])==157
    # Key -> (point, bootstrap vector), keeping a fixed per-image list of k.
    values={};image_rows=[];adjacent_rows=[]
    for i,row in meta.iterrows():
        with np.load(source/'bootstrap_cache'/(row.pool_id+'.npz')) as z:
            names=list(z['metric_names']);n=int(row.pool_n)
            observed={c:z['observed_'+c] for c in COHORTS}
            sampled={c:z['curve_'+c] for c in COHORTS};B=next(iter(sampled.values())).shape[0]
            for metric in METRICS:
                if metric not in names:continue
                mi=names.index(metric)
                valid=np.logical_and.reduce([np.isfinite(observed[c][:,mi]) for c in COHORTS])
                for region,odd_ks in REGIONS.items():
                    candidates=[k for k in odd_ks if k+1<=n]
                    ks=[k for k in candidates if valid[k-2:k+1].all()]
                    for c in COHORTS:
                        if ks:
                            idx=np.asarray(ks)-1
                            x=observed[c][:,mi]
                            point=float(np.mean(x[idx]-.5*(x[idx-1]+x[idx+1])))
                            bx=sampled[c][:,:,mi]
                            boot=np.mean(bx[:,idx]-.5*(bx[:,idx-1]+bx[:,idx+1]),axis=1)
                        else:point=np.nan;boot=np.full(B,np.nan)
                        values[(row.pool_id,c,region,metric)]=(point,boot)
                        image_rows.append(dict(**row.to_dict(),cohort=c,region=region,metric=metric,
                            contrast='odd minus mean of adjacent even k',candidate_odd_k='|'.join(map(str,candidates)),
                            common_odd_k='|'.join(map(str,ks)),common_odd_count=len(ks),estimate=point,
                            complete_path_bootstrap_replicates=int(np.isfinite(boot).sum())))
                for k in range(3,n):
                    if not valid[k-1:k+1].all():continue
                    for c in COHORTS:
                        d=observed[c][k,mi]-observed[c][k-1,mi]
                        adjacent_rows.append(dict(**row.to_dict(),cohort=c,metric=metric,k_from=k,k_to=k+1,
                            minimum_support_from=(k+1)//2,minimum_support_to=(k+2)//2,
                            threshold_step='rises' if k%2==0 else 'unchanged',estimate=float(d)))
    save_csv(pd.DataFrame(image_rows),out/'PARITY_LOCAL_CONTRAST_PER_IMAGE.csv.gz')
    save_csv(pd.DataFrame(adjacent_rows),out/'ADJACENT_STEP_PER_IMAGE.csv.gz')
    summary=[]
    for layer,g in meta.groupby('layer'):
        groups=[('全部' if layer=='ordinary_manual' else '单列',g)]
        if layer=='ordinary_manual':groups += list(g.groupby('difficulty'))
        for difficulty,h in groups:
            for region in REGIONS:
                for metric in METRICS:
                    for c in COHORTS:
                        ids=[p for p in h.pool_id if (p,c,region,metric) in values and np.isfinite(values[p,c,region,metric][0])]
                        if not ids:continue
                        x=np.asarray([values[p,c,region,metric][0] for p in ids]);boots=np.stack([values[p,c,region,metric][1] for p in ids])
                        buildings=h.set_index('pool_id').loc[ids].building.to_numpy()
                        for weighting in ['image_equal','building_equal']:
                            r=estimate(x,boots,buildings,weighting,B,seed_for(2026102631,layer,difficulty,region,metric,'buildings'))
                            summary.append(dict(layer=layer,difficulty=difficulty,cohort=c,region=region,metric=metric,
                                                weighting=weighting,contrast='odd minus neighbouring even average',**r))
    save_csv(pd.DataFrame(summary),out/'PARITY_LOCAL_CONTRAST_SUMMARY.csv')
    save_json(dict(source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',
       analysis_identity='exploratory curve-shape aggregation within the already frozen sampling design',
       new_fusion_endpoints=0,cohorts=COHORTS,regions=REGIONS,ordinary_fixed_N_ge_30=157,
       same_image_k_support='odd and two neighbouring even points finite in all five cohorts; exact list saved',
       inference='association with frozen odd/even threshold changes, not an isolated algorithm component effect'),out/'RECEIPT.json')
    print('parity summaries',len(summary),flush=True)

if __name__=='__main__':main()
