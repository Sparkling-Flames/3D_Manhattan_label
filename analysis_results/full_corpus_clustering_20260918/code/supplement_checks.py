"""Supplementary paired error comparisons; no further fitting or semantic adjudication."""
from pathlib import Path
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1]
def run():
    r=R/'results';p=pd.read_csv(r/'model_dispersion_lobo_predictions.csv')
    a=p.pivot(index=['image_id','building'],columns='model',values='absolute_error');rng=np.random.default_rng(48981);rows=[]
    for m,b in [('model_counts_and_gaps','model_counts'),('counts_gaps_rotation','model_counts_and_gaps')]:
        d=(a[m]-a[b]).reset_index(name='diff');g=d.groupby('building')['diff'].agg(['sum','count']);ix=rng.integers(len(g),size=(4000,len(g)))
        z=g['sum'].values[ix].sum(1)/g['count'].values[ix].sum(1)
        rows.append(dict(model=m,baseline=b,delta_MAE=d['diff'].mean(),low=np.quantile(z,.025),high=np.quantile(z,.975)))
    pd.DataFrame(rows).to_csv(r/'model_dispersion_incremental_bootstrap.csv',index=False)
    a=pd.read_csv(r/'all_response_audit.csv');a=a[~a.worker.isin(['W019','W026'])]
    a[a.processing_status.str.startswith('confirmed')].to_csv(r/'active_approved_processing.csv',index=False)
    a[a.processing_status=='unconfirmed_odd_unchanged'].to_csv(r/'unconfirmed_odd_records.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':run()
