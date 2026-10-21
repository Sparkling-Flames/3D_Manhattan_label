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
    pair_rows=[];pair_stats=[]
    comparisons=[('class_fine','class_coarse'),('class_fine_interaction','class_coarse_interaction'),
        ('class_fine','source'),('class_fine_interaction','source'),
        ('class_fine_interaction','class_fine'),('class_fine_interaction','QT_interaction'),
        ('class_fine_interaction','exact_continuous_interaction'),
        ('exact_continuous_interaction_class_fine','exact_continuous_interaction'),
        ('QT_interaction','QT'),('QT_class_coarse','QT'),('QT_class_fine','QT'),
        ('QT_class_fine','QT_interaction')]
    for (regime,family),d in data.groupby(['regime','family']):
        for new,baseline in [(x+'__'+goal,y+'__'+goal) for x,y in comparisons for goal in ['quality','balanced']]:
            aa=d[d.policy.eq(new)];bb=d[d.policy.eq(baseline)]
            if not len(aa) or not len(bb):continue
            keys=['panel_id','building','image','n','all_candidates_time_compatible']
            fields=KEY+['time_seconds','selection_distribution_sha256']
            z=aa[keys+fields].merge(bb[keys+fields],on=keys,validate='one_to_one',suffixes=('_new','_baseline'))
            for field in KEY:z['contrast_'+field]=z[field+'_new']-z[field+'_baseline']
            z['relative_time_percent_between_policies']=100*(z.time_seconds_new/z.time_seconds_baseline-1)
            z['identical_selected_set_distribution']=z.selection_distribution_sha256_new.eq(z.selection_distribution_sha256_baseline).astype(float)
            meta=dict(condition=a.condition,regime=regime,family=family,new_policy=new,baseline=baseline)
            for k,v in meta.items():z[k]=v
            pair_rows.append(z)
            slices=[('all','all',z),('joint_time_support','all_compatible',z[z.all_candidates_time_compatible])]
            slices += [('n_joint_time_support',str(n),g) for n,g in z[z.all_candidates_time_compatible].groupby('n')]
            outcomes=['contrast_'+f for f in KEY]+['relative_time_percent_between_policies','identical_selected_set_distribution']
            for kind,value,g in slices:
                if not len(g):continue
                results,_=macro_many(g,outcomes)
                for outcome,detail in results.items():pair_stats.append(dict(meta,slice_kind=kind,slice_value=value,outcome=outcome,**detail))
    atomic_csv(pd.concat(pair_rows,ignore_index=True),HERE/(prefix+'_PAIRED_EVENTS.csv.gz'))
    atomic_csv(pd.DataFrame(pair_stats),HERE/(prefix+'_PAIRED.csv'))
    atomic_json(dict(condition=a.condition,input_files=[str(p.relative_to(HERE)) for p in paths],
        completed_evaluations=len(paths),result_rows=len(data),final_for_present_registered_methods=True,
        main_summary_pending_other_condition=True),HERE/(prefix+'_RECEIPT.json'))
    print(coverage.to_string(index=False),flush=True)

if __name__=='__main__':main()
