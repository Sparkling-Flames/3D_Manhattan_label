"""Internal condition selection excluding each building's fusion outcomes.

Reuses the frozen personnel labels exactly. This is not a double-excluded
personnel-classification refit and not a new external blind test.
"""
from __future__ import annotations
from common_screening import *
from screen_conditions import VIEWS,KEY,ROOTKEY,PURPOSE_METRIC,THRESHOLDS,selection_reason
import time,argparse

PURPOSES=list(PURPOSE_METRIC)
SMALL=['cross_B8L2','cross_D10','common_quality_within_abs','common_quality_cross_abs',
 'abs_Q_change_advantage','stable_advantage','cross_ref_node_recall_5','cross_ref_edge_recall_5',
 'cross_omission','cross_extension','cross_fusion_turn_n','cross_fusion_short_turn_edges',
 'advantage_floor_jaccard_difference','advantage_mean_height_prism_pair_difference',
 'A_failure','B_failure','C_failure','cross_loss_gt10','cross_failure_or_loss_gt10',
 'cross_recorded_time_pct','cross_B8L2_time_qualified']

def ci_values(v,seed=2026102201):
    v=np.asarray(v,dtype=float);v=v[np.isfinite(v)]
    if len(v)<3:return (np.nan,np.nan)
    rng=np.random.default_rng(seed)
    sims=v[rng.integers(len(v),size=(2000,len(v)))].mean(axis=1)
    return tuple(np.quantile(sims,[.025,.975]))

def fold_stats(z,purpose,meta,images):
    metric=PURPOSE_METRIC[purpose];v=z[metric].dropna().to_numpy(float)
    row=dict(comparison=meta['comparison'],direction=meta['direction'],images=images)
    row.update({metric+'__building_'+k:value for k,value in dict(
      valid=len(v),mean=float(v.mean()) if len(v) else np.nan,
      median=float(np.median(v)) if len(v) else np.nan,
      positive=int((v>1e-10).sum()),negative=int((v< -1e-10).sum())).items()})
    row['cross_B8L2_time_qualified__building_mean']=z.cross_B8L2_time_qualified.mean()
    reason=selection_reason(row,purpose)
    sign=-1 if purpose=='time_saving' else 1
    same=int((v*sign>1e-10).sum())
    effect=float(v.mean())*sign if len(v) else np.nan
    return dict(train_valid_buildings=len(v),train_images=images,
      train_mean=float(v.mean()) if len(v) else np.nan,
      train_median=float(np.median(v)) if len(v) else np.nan,
      train_same_direction_buildings=same,train_same_direction_fraction=same/len(v) if len(v) else np.nan,
      train_selected=reason=='selected',train_nonselection_reason=reason,
      selection_score=effect*same/len(v) if len(v) else np.nan)

def run_view(view,all_buildings):
    path=HERE/'views'/view
    if not(path/'COMPLETION.json').exists():return None
    core=pd.read_csv(path/'CORE_ALL_CANDIDATES.csv.gz',usecols=['candidate_id','view']+KEY+['events','buildings','images'],low_memory=False)
    b=pd.read_csv(path/'BUILDING_CORE_MEANS.csv.gz')
    im=pd.read_csv(path/'IMAGE_CORE_MEANS.csv.gz',usecols=['candidate_id','building','image'])
    image_counts=im.groupby(['candidate_id','building']).size().to_dict()
    total_images=im.groupby('candidate_id').size().to_dict()
    by_candidate={cid:g for cid,g in b.groupby('candidate_id')}
    eligible=core[core.buildings.ge(4)].copy()
    rows=[]
    for meta in eligible.to_dict('records'):
        cid=meta['candidate_id'];z=by_candidate[cid]
        for heldout in all_buildings[meta['condition']]:
            train=z[z.building.ne(heldout)];test=z[z.building.eq(heldout)]
            nimages=total_images[cid]-image_counts.get((cid,heldout),0)
            for purpose in PURPOSES:
                stats=fold_stats(train,purpose,meta,nimages)
                r={field:meta[field] for field in ['candidate_id','view']+KEY}
                r.update(heldout_building=heldout,purpose=purpose,metric=PURPOSE_METRIC[purpose],
                    **stats,heldout_has_registered_condition=len(test)>0,
                    heldout_images=image_counts.get((cid,heldout),0),
                    personnel_labels_double_excluded_refit=False)
                for metric in SMALL:r['test_'+metric]=float(test[metric].iloc[0]) if len(test) else np.nan
                rows.append(r)
    folds=pd.DataFrame(rows)
    if not len(folds):
        save_json('lobo/'+view+'/COMPLETION.json',dict(status='complete',eligible_conditions=0,all_conditions=len(core)))
        return dict(view=view,eligible_conditions=0,selected_heldout_checks=0)
    receipts=[];folder='lobo/'+view+'/'
    receipts.append(save_csv(folder+'ALL_TRAINING_FOLD_CANDIDATES.csv.gz',folds))
    selected=folds[folds.train_selected & folds.heldout_has_registered_condition].copy()
    receipts.append(save_csv(folder+'SELECTED_CONDITION_HELDOUT_CHECKS.csv.gz',selected))
    # Choose among directions, n and m only on other-building evidence; a
    # chosen condition may have no held-out opportunity and remains so marked.
    choicekeys=['heldout_building','view','comparison','condition','method_id','tier','source_domain','parent_fixed','purpose']
    possible=folds[folds.train_selected].sort_values(['selection_score','train_valid_buildings','candidate_id'],ascending=[False,False,True])
    choices=possible.drop_duplicates(choicekeys).copy()
    receipts.append(save_csv(folder+'BEST_TRAIN_SELECTED_CONDITION.csv',choices))
    summaries=[]
    for scope,table in [('each_passing_condition',selected),('best_condition',choices)]:
        keys=['view','comparison','condition','method_id','tier','source_domain','parent_fixed','purpose']
        for k,g in table.groupby(keys,dropna=False):
            meta=dict(zip(keys,k));metric=PURPOSE_METRIC[meta['purpose']]
            signed=-1 if meta['purpose']=='time_saving' else 1
            vals=g['test_'+metric].dropna().to_numpy(float)
            r=dict(scope=scope,**meta,training_selections=len(g),
              distinct_selected_conditions=g.candidate_id.nunique(),
              heldout_buildings=g.heldout_building.nunique(),heldout_available=int(g.heldout_has_registered_condition.sum()),
              valid_heldout_checks=len(vals),test_mean=float(vals.mean()) if len(vals) else np.nan,
              test_median=float(np.median(vals)) if len(vals) else np.nan,
              positive_heldout_checks=int((vals*signed>1e-10).sum()),negative_heldout_checks=int((vals*signed< -1e-10).sum()),
              tie_heldout_checks=int((np.abs(vals)<=1e-10).sum()))
            # Multiple passing conditions in one held-out building are not
            # counted as independent buildings for this final check.
            bv=g.groupby('heldout_building')['test_'+metric].mean().dropna()
            r.update(test_building_equal_mean=bv.mean(),test_building_equal_median=bv.median(),
              valid_test_buildings=len(bv),positive_test_buildings=int((bv*signed>1e-10).sum()),
              negative_test_buildings=int((bv*signed< -1e-10).sum()))
            lo,hi=ci_values(bv.to_numpy());r['building_bootstrap_lo95']=lo;r['building_bootstrap_hi95']=hi
            for f in ['cross_B8L2','cross_D10','C_failure','cross_failure_or_loss_gt10','cross_recorded_time_pct']:
                r['test_building_mean_'+f]=g.groupby('heldout_building')['test_'+f].mean().mean()
            summaries.append(r)
    summary=pd.DataFrame(summaries)
    receipts.append(save_csv(folder+'HELDOUT_SUMMARY.csv',summary))
    excluded=core[~core.candidate_id.isin(eligible.candidate_id)][['candidate_id','view']+KEY+['events','buildings','images']].copy()
    excluded['reason']='Fewer than four observed buildings: cannot satisfy training support even before excluding a building.'
    receipts.append(save_csv(folder+'NOT_EXPANDED_INSUFFICIENT_SUPPORT.csv.gz',excluded))
    result=dict(status='complete',view=view,eligible_conditions=len(eligible),all_conditions=len(core),
      training_fold_rows=len(folds),selected_heldout_checks=len(selected),best_condition_choices=len(choices),
      best_conditions_without_heldout_opportunity=int((~choices.heldout_has_registered_condition).sum()),
      files=receipts,native_calls=0,personnel_labels_refitted=False,
      caveat='Repeatedly explored data; target fusion results excluded for condition choice. No full nested personnel refit, external blind test or unseen-building claim.')
    save_json(folder+'COMPLETION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['files','caveat']}),flush=True)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--view',choices=VIEWS);a=parser.parse_args()
    started=time.time()
    ev=pd.read_csv(HERE/'EVENTS_UNIFIED.csv.gz',usecols=['condition','building'])
    buildings={condition:sorted(z.building.unique()) for condition,z in ev.groupby('condition')}
    results=[]
    for view in [a.view] if a.view else VIEWS:
        done=HERE/'lobo'/view/'COMPLETION.json'
        if done.exists():results.append(json.loads(done.read_text()));continue
        r=run_view(view,buildings)
        if r is None:continue
        results.append(r);save_json('INTERNAL_LOBO_PROGRESS.json',dict(views=results,seconds=time.time()-started))
    if not a.view and len(results)==len(VIEWS):
        save_json('INTERNAL_LOBO_COMPLETION.json',dict(status='complete',views=results,seconds=time.time()-started,
          selection_rule='Freeze practical thresholds; rank passing conditions by oriented train building mean times train same-direction fraction, then support, then deterministic id.',
          data_version='v2',native_calls=0))

if __name__=='__main__':main()
