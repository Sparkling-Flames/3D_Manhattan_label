"""Small completed-A-batch readout; no new inference or endpoint calls.

The final stage2 table retains the same old48/A104/152 values, so recipients
can reproduce this historical readout from S11 without a separate stage1 cache.
"""
from pathlib import Path
import argparse,json,sys
import pandas as pd


def main(base):
    base=base.resolve();sys.path.insert(0,str(base/'analysis_precision26'))
    from precision_core import save_csv,save_json
    selected=None
    for stage in (2,1):
        source=base/f'analysis_precision26/results_stage{stage}'
        receipt=source/'ANALYSIS_RECEIPT.json'
        if receipt.exists():
            r=json.loads(receipt.read_text())
            if r.get('complete_requested_pool_support') and r.get('pools')==194:
                selected=source;break
    if selected is None:raise RuntimeError('No completed all194 pool table')
    x=pd.read_csv(selected/'NATURAL_CURVES.csv.gz')
    x=x[x.layer.eq('ordinary_manual')&x.pool_n.ge(30)&x.k.isin([3,6,10,20,30])&
        x.cohort.isin(['old48','stage1_104','pooled152'])].copy()
    x['p10_hw']=(x.Q_p10_boot_high-x.Q_p10_boot_low)/2
    rows=[]
    for (cohort,k),g in x.groupby(['cohort','k']):
        assert len(g)==157 and g.Q_mean.notna().all()
        rows.append(dict(cohort=cohort,k=int(k),images=len(g),Q_mean=g.Q_mean.mean(),
            Q_P10=g.Q_p10.mean(),mean_MCSE_gt1=int(g.Q_mean_MCSE_analytic.gt(1).sum()),
            P10_halfwidth_gt2=int(g.p10_hw.gt(2).sum()),median_mean_MCSE=g.Q_mean_MCSE_analytic.median()))
    out=base/'analysis_reporting26/results'
    save_csv(pd.DataFrame(rows),out/'STAGE1_FIXED157_INTERMEDIATE_READOUT.csv')
    save_json(dict(source=str(selected.relative_to(base)),all194_pools_complete=True,
        final_current_result='Use full stage2 old48/new208/256; this table is the retained A-batch checkpoint',
        extra_fusion=0,extra_orders=0,extra_bootstrap=0),out/'STAGE1_READOUT_IDENTITY.json')
    print(pd.DataFrame(rows).to_string(index=False,float_format=lambda v:f'{v:.4f}'))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    main(ap.parse_args().base)
