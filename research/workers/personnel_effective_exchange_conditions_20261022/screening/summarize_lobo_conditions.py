"""Exact-condition internal held-out support, including no-opportunity cells."""
from __future__ import annotations
from common_screening import *
from screen_conditions import VIEWS,KEY,PURPOSE_METRIC
from internal_lobo_check import SMALL,ci_values
import time

def main():
    receipts=[];totals=[]
    for view in VIEWS:
        folder=HERE/'lobo'/view
        if not(folder/'COMPLETION.json').exists():continue
        output=folder/'CONDITION_HELDOUT_SUMMARY.csv.gz'
        if output.exists():continue
        path=folder/'ALL_TRAINING_FOLD_CANDIDATES.csv.gz'
        if not path.exists():continue
        cols=['candidate_id','view']+KEY+['heldout_building','purpose','metric','train_selected',
          'heldout_has_registered_condition','train_valid_buildings','train_nonselection_reason']+['test_'+f for f in SMALL]
        d=pd.read_csv(path,usecols=cols,low_memory=False)
        out=[]
        for (cid,purpose),g in d.groupby(['candidate_id','purpose']):
            meta=g.iloc[0];observed=g[g.heldout_has_registered_condition]
            selected=observed[observed.train_selected]
            metric=PURPOSE_METRIC[purpose];sign=-1 if purpose=='time_saving' else 1
            v=selected['test_'+metric].dropna().to_numpy(float);av=observed['test_'+metric].dropna().to_numpy(float)
            lo,hi=ci_values(v)
            r={k:meta[k] for k in ['candidate_id','view']+KEY+['purpose','metric']}
            r.update(training_folds=len(g),observed_heldout_buildings=len(observed),
              selected_training_folds=int(g.train_selected.sum()),selected_without_target_opportunity=int((g.train_selected&~g.heldout_has_registered_condition).sum()),
              selected_with_target_opportunity=len(selected),valid_selected_heldout_buildings=len(v),
              test_mean=float(v.mean()) if len(v) else np.nan,test_median=float(np.median(v)) if len(v) else np.nan,
              positive_selected_heldout_buildings=int((v*sign>1e-10).sum()),
              negative_selected_heldout_buildings=int((v*sign< -1e-10).sum()),
              zero_selected_heldout_buildings=int((np.abs(v)<=1e-10).sum()),
              selected_same_direction_fraction=float((v*sign>1e-10).mean()) if len(v) else np.nan,
              bootstrap_lo95=lo,bootstrap_hi95=hi,
              all_observed_building_mean=float(av.mean()) if len(av) else np.nan,
              all_observed_building_median=float(np.median(av)) if len(av) else np.nan,
              all_observed_positive_buildings=int((av*sign>1e-10).sum()),
              all_observed_negative_buildings=int((av*sign< -1e-10).sum()))
            r['internal_status']='majority_direction_repeats' if len(v)>=4 and (v*sign>1e-10).mean()>=.6 and np.mean(v*sign)>0 else 'limited_heldout_support' if len(v)<4 else 'direction_does_not_repeat_in_majority'
            r['nonselection_reasons_observed']='|'.join(sorted(set(observed.train_nonselection_reason)))
            for f in ['cross_B8L2','cross_D10','C_failure','cross_loss_gt10','cross_failure_or_loss_gt10','cross_recorded_time_pct']:
                r['selected_test_'+f]=selected['test_'+f].mean()
            out.append(r)
        table=pd.DataFrame(out);receipt=save_csv('lobo/'+view+'/CONDITION_HELDOUT_SUMMARY.csv.gz',table);receipts.append(receipt)
        mini=table[table.valid_selected_heldout_buildings.ge(4)&table.m.ge(4)].copy()
        receipts.append(save_csv('lobo/'+view+'/CONDITION_HELDOUT_AT_LEAST_FOUR.csv',mini))
        totals.append(dict(view=view,condition_purposes=len(table),four_test_buildings=len(mini),
           majority_repeats=int(table.internal_status.eq('majority_direction_repeats').sum())))
        save_json('CONDITION_LOBO_SUMMARY_PROGRESS.json',dict(views=totals,files=receipts,native_calls=0))
    print(json.dumps(dict(status='available_views_summarized',views=totals)),flush=True)

if __name__=='__main__':main()
