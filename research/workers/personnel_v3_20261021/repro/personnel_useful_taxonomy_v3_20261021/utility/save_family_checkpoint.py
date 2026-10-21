"""Immediately readable actual-effect table for one completed method family."""
import argparse,json
import pandas as pd
from prepare_training import HERE,atomic_csv,atomic_json,sha
from summarize_policy import macro_many

KEY=['delta_B8L2','delta_D10','time_percent_vs_uniform','time_seconds_delta',
    'failure_rate','failure_delta_pp','failure_or_loss_gt5_delta_pp','failure_or_loss_gt10_delta_pp']

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',required=True,choices=['manual','semi'])
    p.add_argument('--family',required=True);p.add_argument('--regime',default='cross_panel_LOBO');a=p.parse_args()
    folder=HERE/a.regime/a.condition/a.family
    path=folder/'PANEL_POLICY_RESULTS.csv.gz';d=pd.read_csv(path,low_memory=False)
    rows=[]
    for policy,g in d.groupby('policy'):
        subsets=[('all','all',g),('joint_time_support','all_compatible',g[g.all_candidates_time_compatible])]
        subsets += [('n_joint_time_support',str(n),z) for n,z in g[g.all_candidates_time_compatible].groupby('n')]
        for kind,value,z in subsets:
            stats,_=macro_many(z,KEY)
            for field,r in stats.items():rows.append(dict(condition=a.condition,family=a.family,regime=a.regime,
                policy=policy,slice_kind=kind,slice_value=value,outcome=field,**r))
    atomic_csv(pd.DataFrame(rows),folder/'POLICY_SUMMARY_CHECKPOINT.csv')
    ordinary=d[d.policy.eq('ordinary_uniform')]
    receipt=dict(status='complete',condition=a.condition,family=a.family,regime=a.regime,
        input_sha256=sha(path),panel_policy_rows=len(d),panels=ordinary.panel_id.nunique(),
        images=ordinary.image.nunique(),buildings=ordinary.building.nunique(),
        candidate_references=int(ordinary.common_candidates.sum()),
        compatible_time_panels=int(ordinary.all_candidates_time_compatible.sum()))
    atomic_json(receipt,folder/'POLICY_SUMMARY_CHECKPOINT_RECEIPT.json')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
