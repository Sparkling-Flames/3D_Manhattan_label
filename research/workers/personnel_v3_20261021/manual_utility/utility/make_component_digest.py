"""Readable actual component results for declared main policy comparators."""
import argparse
import pandas as pd
from prepare_training import HERE,atomic_csv
from policy_study import METRICS
from summarize_policy import macro_many

POLICIES=[('new_joint','history_Q'),('new_joint','history_T'),
    ('new_joint','QT_interaction__balanced'),
    ('old_structure','class_fine_interaction__balanced'),
    ('new_behavior','class_coarse_interaction__balanced'),
    ('new_behavior','class_fine_interaction__balanced'),
    ('new_joint','class_fine_interaction__balanced'),
    ('new_joint','exact_continuous_interaction__balanced'),
    ('new_joint','exact_continuous_interaction_class_fine__balanced'),
    ('old_multivariate','class_fine__quality'),('old_multivariate','QT_class_fine__balanced')]

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',required=True,choices=['manual','semi']);a=p.parse_args()
    rows=[]
    for family,policy in POLICIES:
        path=HERE/'cross_panel_LOBO'/a.condition/family/'PANEL_POLICY_RESULTS.csv.gz'
        d=pd.read_csv(path,low_memory=False);d=d[d.policy.eq(policy)]
        fields=['delta_'+f for f in METRICS]+['failure_rate','failure_delta_pp',
            'time_percent_vs_uniform','failure_or_loss_gt5_delta_pp','failure_or_loss_gt10_delta_pp']
        for kind,g in [('all',d),('joint_time_support',d[d.all_candidates_time_compatible])]:
            stats,_=macro_many(g,fields)
            for field,values in stats.items():rows.append(dict(condition=a.condition,regime='cross_panel_LOBO',
                family=family,policy=policy,slice_kind=kind,outcome=field,**values))
    atomic_csv(pd.DataFrame(rows),HERE/(a.condition.upper()+'_POLICY_COMPONENT_DIGEST.csv'))
    print(a.condition,'component digest',len(rows),flush=True)

if __name__=='__main__':main()
