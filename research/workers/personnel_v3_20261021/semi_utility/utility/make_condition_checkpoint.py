"""Save a compact actual-effect checkpoint as soon as a condition is complete."""
import argparse,json
import pandas as pd
from prepare_training import HERE,atomic_csv,atomic_json
from summarize_policy import macro_many

KEY=['delta_B8L2','delta_D10','failure_delta_pp','time_percent_vs_uniform',
     'time_seconds_delta','failure_or_loss_gt5_delta_pp','failure_or_loss_gt10_delta_pp']

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=['manual','semi'],required=True);a=p.parse_args()
    paths=sorted(HERE.glob(f'*/{a.condition}/*/PANEL_POLICY_RESULTS.csv.gz'))
    data=pd.concat([pd.read_csv(p,low_memory=False) for p in paths],ignore_index=True)
    stats=[];coverage=[]
    for (regime,family,policy),d in data.groupby(['regime','family','policy']):
        slices=[('all','all',d),('joint_time_support','all_compatible',d[d.all_candidates_time_compatible])]
        slices += [('n',str(n),g) for n,g in d.groupby('n')]
        slices += [('n_joint_time_support',str(n),g) for n,g in d[d.all_candidates_time_compatible].groupby('n')]
        for kind,value,g in slices:
            if not len(g):continue
            r,_=macro_many(g,KEY)
            for outcome,detail in r.items():stats.append(dict(condition=a.condition,regime=regime,family=family,
                policy=policy,slice_kind=kind,slice_value=value,outcome=outcome,**detail))
    ordinary=data[data.policy.eq('ordinary_uniform')]
    coverage=ordinary.groupby(['condition','regime','family'],as_index=False).agg(
        panels=('panel_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),
        candidates=('common_candidates','sum'),complete_time_panels=('all_candidates_time_compatible','sum'),
        n_min=('n','min'),n_max=('n','max'))
    prefix=a.condition.upper()+'_UTILITY_CHECKPOINT'
    atomic_csv(pd.DataFrame(stats),HERE/(prefix+'.csv'))
    atomic_csv(coverage,HERE/(prefix+'_COVERAGE.csv'))
    atomic_json(dict(condition=a.condition,input_files=[str(p.relative_to(HERE)) for p in paths],
        completed_evaluations=len(paths),result_rows=len(data),final_for_present_registered_methods=True,
        main_summary_pending_other_condition=True),HERE/(prefix+'_RECEIPT.json'))
    print(coverage.to_string(index=False),flush=True)

if __name__=='__main__':main()
