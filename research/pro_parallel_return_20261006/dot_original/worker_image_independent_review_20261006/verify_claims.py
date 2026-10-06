#!/usr/bin/env python3
"""Compare recomputed values with the reported precision; no inferential tests."""
import argparse,json
from pathlib import Path
import pandas as pd


def verify(out):
    s=pd.read_csv(out/'sensitivity.csv',float_precision='round_trip');w=pd.read_csv(out/'worker_summary.csv',float_precision='round_trip')
    f=s[(s.variant=='full')&(s.scale=='GT_normalized')]
    expected={'original':{'O':[87.8,2.6,9.6],'E':[27.8,17.9,54.3],'D':[86.7,4.3,9.0]},'revised_where_available':{'O':[75.5,4.8,19.6],'E':[24.2,11.3,64.5],'D':[69.1,6.5,24.4]}}
    checks=[]
    def check(name,actual,expected):
        ok=actual==expected; checks.append({'claim':name,'actual':actual,'reported':expected,'passed':bool(ok)});assert ok,name
    for policy,metrics in expected.items():
        for metric,exp in metrics.items():
            row=f[(f.policy==policy)&(f.metric==metric)].iloc[0]
            for col,e in zip(['image_pct','worker_pct','residual_pct'],exp):check(f'{policy}/{metric}/{col}: one decimal',round(float(row[col]),1),e)
    for policy,rho,neg,pos,cross,worst in [('original',.198,6,39,22,1.),('revised_where_available',.160,7,38,23,5.)]:
        row=f[(f.policy==policy)&(f.metric=='D')].iloc[0]
        check(f'{policy}/D/rho: three decimals',round(float(row.rank_correlation_median),3),rho)
        for col,exp in [('rank_correlation_negative',neg),('rank_correlation_positive',pos),('n_image_pairs',45),('workers_above_and_below_image_mean',cross)]:check(f'{policy}/D/{col}',int(row[col]),exp)
        ws=w[(w.policy==policy)&(w.metric=='D')&(w.scale=='GT_normalized')].set_index('worker')
        for worker,col,exp in [('P017','overall_mean_error_rank',1.),('P017','best_image_rank',1.),('P017','worst_image_rank',worst),('P002','overall_mean_error_rank',2.),('P002','worst_image_rank',21.5)]:check(f'{policy}/D/{worker}/{col}',float(ws.loc[worker,col]),exp)
    return {'all_checks_passed':True,'n_checks':len(checks),'checks':checks}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('results_dir');a=p.parse_args();out=Path(a.results_dir)
    r=verify(out);(out/'claim_checks.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(f"{r['n_checks']} reported-statistic checks passed")
