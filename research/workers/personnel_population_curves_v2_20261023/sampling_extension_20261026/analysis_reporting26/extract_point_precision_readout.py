"""Save the completed fixed-157 point precision readout; no new resampling."""
from pathlib import Path
import argparse
import hashlib
import json
import os
for name in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[name] = '1'
import pandas as pd


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--base', type=Path, required=True)
    base = ap.parse_args().base.resolve()
    folder = base / 'analysis_precision26/results_stage2'
    gate = json.loads((folder / 'ANALYSIS_RECEIPT.json').read_text())
    assert gate['complete_requested_pool_support'] and gate['pools'] == 194
    source = folder / 'NATURAL_CURVES.csv.gz'
    columns = ['pool_id','building','layer','difficulty','pool_n','cohort','k',
        'paths_attempted','quality_valid_paths','Q_mean','Q_p10','Q_sd_ddof1',
        'Q_mean_MCSE_analytic','P10_linear_boot_halfwidth','P10_order_halfwidth',
        'actual_consensus_failure_rate','output_unscoreable_rate']
    d = pd.read_csv(source, usecols=columns)
    d = d[d.layer.eq('ordinary_manual') & d.pool_n.ge(30) & d.k.isin([3,6,10,20,30])]
    rows = []
    for cohort in ['old48','stage1_104','stage2_104','new208','pooled256']:
        for k in [3,6,10,20,30]:
            g = d[d.cohort.eq(cohort) & d.k.eq(k)]
            assert len(g) == g.pool_id.nunique() == 157 and g.building.nunique() == 22
            assert g.Q_mean.notna().all() and g.paths_attempted.nunique() == 1
            rows.append(dict(cohort=cohort,k=k,images=157,buildings=22,
                paths_per_image=int(g.paths_attempted.iloc[0]),
                Q_valid_paths_min=int(g.quality_valid_paths.min()),
                Q_valid_paths_median=float(g.quality_valid_paths.median()),
                mean_Q_image_equal=float(g.Q_mean.mean()),
                mean_P10_linear_image_equal=float(g.Q_p10.mean()),
                mean_Q_SD_image_equal=float(g.Q_sd_ddof1.mean()),
                mean_MCSE_gt1_images=int(g.Q_mean_MCSE_analytic.gt(1).sum()),
                median_mean_MCSE=float(g.Q_mean_MCSE_analytic.median()),
                P10_empirical95_halfwidth_gt2_images=int(g.P10_linear_boot_halfwidth.gt(2).sum()),
                P10_inverseCDF_rank95_halfwidth_gt2_images=int(g.P10_order_halfwidth.gt(2).sum()),
                mean_actual_consensus_failure_probability=float(g.actual_consensus_failure_rate.mean()),
                mean_output_generated_unscoreable_probability=float(g.output_unscoreable_rate.mean()),
                support='fixed ordinary Manual N>=30; same 157 images at every displayed k',
                source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac'))
    out = base / 'analysis_reporting26/results'; out.mkdir(parents=True, exist_ok=True)
    target = out / 'FINAL_FIXED157_POINT_PRECISION_READOUT.csv'
    frame = pd.DataFrame(rows); raw = frame.to_csv(index=False,lineterminator='\n').encode('utf-8')
    temp = target.with_suffix('.writing');temp.write_bytes(raw);temp.replace(target)
    reread = pd.read_csv(target); assert len(reread)==25 and list(reread)==list(frame)
    receipt = dict(complete=True,all194_pool_analysis_complete=True,rows=25,fields=list(frame),
        source=str(source.relative_to(base)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        output=str(target.relative_to(base)),sha256=hashlib.sha256(raw).hexdigest(),
        CSV_read_to_EOF=True,new_orders=0,new_fusion=0,new_bootstrap=0,
        scope='pointwise estimates and precision; not a simultaneous curve confidence claim',
        old48_P10_note='Current common bootstrap seed gives 137/112/79/44 at k3/6/10/20; archived prior seed gives 137/110/80/44; no old endpoint changed')
    (out / 'FINAL_FIXED157_POINT_PRECISION_READOUT_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(dict(rows=len(frame),output=str(target),sha256=receipt['sha256'])),flush=True)


if __name__ == '__main__':main()
