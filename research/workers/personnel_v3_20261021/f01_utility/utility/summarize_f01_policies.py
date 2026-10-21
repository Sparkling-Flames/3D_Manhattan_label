"""Independent completed F01 actual-choice checkpoint and paired contrasts."""
import json
import numpy as np
import pandas as pd
from prepare_training import HERE,atomic_csv,atomic_json,sha
from policy_study import METRICS
from summarize_policy import macro_many

def main():
    folder=HERE/'f01_finite_LOBO/manual/F01_fixed_history'
    path=folder/'PANEL_POLICY_RESULTS.csv.gz';d=pd.read_csv(path,low_memory=False)
    d['selected_fast_C01_n']=d.selected_coarse_mean_counts_json.map(lambda s:json.loads(s).get('C01',0))
    d['ordinary_fast_C01_n']=d.ordinary_coarse_mean_counts_json.map(lambda s:json.loads(s).get('C01',0))
    d['change_fast_C01_n']=d.selected_fast_C01_n-d.ordinary_fast_C01_n
    fields=['delta_'+f for f in METRICS]+['time_percent_vs_uniform','time_seconds_delta','failure_rate',
        'failure_delta_pp','failure_or_loss_gt5_delta_pp','failure_or_loss_gt10_delta_pp',
        'selected_fast_C01_n','ordinary_fast_C01_n','change_fast_C01_n']
    stats=[]
    for policy,g in d.groupby('policy'):
        for sk,sv,z in [('all','all',g)]+[('difficulty',v,z) for v,z in g.groupby('difficulty')]:
            results,_=macro_many(z,fields)
            for f,r in results.items():stats.append(dict(policy=policy,slice_kind=sk,slice_value=sv,outcome=f,**r))
    atomic_csv(pd.DataFrame(stats),HERE/'F01_POLICY_CHECKPOINT.csv')
    rows=[];paired=[]
    comparisons=[('class_coarse__balanced','QT__balanced'),
        ('class_coarse_interaction__balanced','QT_interaction__balanced'),
        ('QT_class_coarse__balanced','QT__balanced'),
        ('QT_class_coarse__quality','QT__quality'),
        ('transfer_main_QT_interaction__balanced','QT_interaction__balanced'),
        ('transfer_main_QT_interaction__balanced','class_coarse_interaction__balanced')]
    key=['panel_id','building','image','difficulty','n']
    keep=['B8L2','D10','failure_rate','failure_or_loss_gt5_vs_random_success_probability',
        'failure_or_loss_gt10_vs_random_success_probability','time_seconds','selected_fast_C01_n']
    for new,base in comparisons:
        z=d[d.policy.eq(new)][key+keep].merge(d[d.policy.eq(base)][key+keep],on=key,validate='one_to_one',suffixes=('_new','_base'))
        for f in keep:z['contrast_'+f]=z[f+'_new']-z[f+'_base']
        z['relative_time_percent_between_policies']=100*(z.time_seconds_new/z.time_seconds_base-1)
        z['new_policy']=new;z['baseline']=base;rows.append(z)
        for sk,sv,g in [('all','all',z)]+[('difficulty',v,g) for v,g in z.groupby('difficulty')]:
            results,_=macro_many(g,['contrast_'+f for f in keep]+['relative_time_percent_between_policies'])
            for f,r in results.items():paired.append(dict(new_policy=new,baseline=base,slice_kind=sk,slice_value=sv,outcome=f,**r))
    atomic_csv(pd.concat(rows,ignore_index=True),HERE/'F01_PAIRED_POLICY_EVENTS.csv')
    atomic_csv(pd.DataFrame(paired),HERE/'F01_PAIRED_POLICY_CHECKPOINT.csv')
    atomic_csv(d[['panel_id','building','image','difficulty','n','policy','common_candidates','selected_teams',
        'selected_fast_C01_n','ordinary_fast_C01_n','change_fast_C01_n','B8L2','D10',
        'failure_rate','time_seconds','time_percent_vs_uniform']],HERE/'F01_ACTUAL_POLICY_CHOICES.csv')
    curve=pd.read_csv(HERE/'F01_COMPLETE_CONFIGURATION_CURVE.csv')
    maximum=curve.groupby('panel_id').fast_C01_n.max()
    chosen=d[d.policy.eq('class_coarse_interaction__balanced')]
    assert np.allclose(chosen.selected_fast_C01_n,chosen.panel_id.map(maximum))
    atomic_json(dict(status='complete',input=str(path.relative_to(HERE)),input_sha256=sha(path),
        policies=d.policy.nunique(),selection_panels=d.panel_id.nunique(),
        buildings=d.building.nunique(),images=d.image.nunique(),
        common_member_sets=int(d[d.policy.eq('ordinary_uniform')].common_candidates.sum()),
        all_time_compatible=bool(d.all_candidates_time_compatible.all()),
        class_balanced_selects_maximum_feasible_fast_count_on_all_panels=True,
        class_balanced_selected_member_sets=int(chosen.selected_teams.sum()),fine_class_defined=False),HERE/'F01_POLICY_CHECKPOINT_RECEIPT.json')
    print('F01 policies',len(stats),'paired',len(paired),flush=True)

if __name__=='__main__':main()
