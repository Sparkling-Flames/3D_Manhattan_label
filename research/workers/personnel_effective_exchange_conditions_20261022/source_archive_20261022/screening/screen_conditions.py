"""Uniform exact-condition screen of prior completed exchanges.

Never refits personnel labels and never calls fusion. Statistical summaries
balance common backgrounds, images and buildings. All candidate conditions and
nonselection reasons are saved before internal leave-building-out rechecks.
"""
from __future__ import annotations
from common_screening import *
from build_unified_screening import QUALITY,LOCATION,EXPRESSION,PAIR,HISTORY
import argparse,time,warnings
warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)

ROOTKEY=['comparison','condition','method_id','tier','source_domain','n','m','parent_fixed']
KEY=ROOTKEY+['direction','target_difficulty']
METRICS_CORE=['cross_B8L2','cross_D10','same_B8L2','common_quality_within_abs',
 'common_quality_cross_abs','abs_Q_change_advantage','stable_advantage',
 'cross_IoU3D100','cross_iou_2d','cross_ref_node_recall_5','cross_ref_edge_recall_5',
 'cross_omission','cross_extension','cross_fusion_turn_n','cross_fusion_short_turn_edges',
 'cross_fusion_redundancy_n','advantage_floor_jaccard_difference',
 'advantage_mean_height_prism_pair_difference','A_failure','B_failure','C_failure',
 'same_loss_gt10','cross_loss_gt10','same_failure_or_loss_gt10','cross_failure_or_loss_gt10',
 'cross_failure_difference','same_recorded_time_pct','cross_recorded_time_pct',
 'cross_B8L2_time_qualified','time_variation_advantage','cross_turn_history_change',
 'cross_area_history_change','cross_height_history_change','cross_history_block_Q_change']
ALL_METRICS=list(dict.fromkeys(METRICS_CORE+
 [a+'_'+m for a in ['same','cross'] for m in QUALITY+LOCATION+EXPRESSION]+
 [a+'_'+m for a in ['within','cross','advantage'] for m in PAIR]+
 [a+'_'+m for a in ['same','cross'] for m in ['loss_gt5','loss_gt10','gain_gt5','gain_gt10',
 'failure_difference','complete_to_failure','failure_to_complete','failure_or_loss_gt10']]+
 ['cross_'+a+'_change' for a in HISTORY]))
VIEWS=['class_block','class_net','class_block_difficulty','class_any_direction',
       'history_turn','history_short','history_redundancy','history_area','history_height']
PURPOSE_METRIC={'quality':'cross_B8L2','interchangeability':'abs_Q_change_advantage',
 'floor_separation':'advantage_floor_jaccard_difference',
 'prism_separation':'advantage_mean_height_prism_pair_difference',
 'node_recall':'cross_ref_node_recall_5','edge_recall':'cross_ref_edge_recall_5',
 'time_saving':'cross_recorded_time_pct'}
THRESHOLDS={'quality':1.,'interchangeability':.5,'floor_separation':.003,
 'prism_separation':.003,'node_recall':.02,'edge_recall':.02,'time_saving':10.}

def read_events():
    names=set(ALL_METRICS+ROOTKEY+['analysis_event_id','event_id','actual_exchange_id','directed_pair_id',
     'common_background_id','common_background','building','image','pool_id','panel_id','prior_stage',
     'prior_stages','design_scopes','registered_rows','role_block_direction','role_net_direction',
     'raw_block_direction','exact_fold_direction','role_alignment','difficulty',
     'team_A','team_B','team_C','outgoing_block_X','same_count_block_Y','changed_count_block_Z',
     'fold_selected_family','fold_coarse_k','fold_fine_k','composition_turnover_AC','whole_class_transfer',
     'same_source_counts','source_and_historyQ5_matched']+
     ['direction_'+s+'_history' for s in ['turn','short','redundancy','area','height']])
    d=pd.read_csv(HERE/'EVENTS_UNIFIED.csv.gz',usecols=lambda x:x in names,low_memory=False)
    for metric in ALL_METRICS:
        if metric not in d:d[metric]=np.nan
        d[metric]=pd.to_numeric(d[metric],errors='coerce').astype(float)
    return d

def label_view(d,view):
    d=d.copy()
    if view.startswith('class_block'):d['direction']=d.role_block_direction
    elif view=='class_net':d['direction']=d.role_net_direction
    elif view=='class_any_direction':d['direction']='all_archived_class_directions'
    else:
        axis=view.removeprefix('history_')
        d['direction']=axis+'_history:'+d['direction_'+axis+'_history']
    d['target_difficulty']=d.difficulty if view.endswith('_difficulty') else 'ALL'
    idx=d[KEY].drop_duplicates().sort_values(KEY).copy()
    idx['view']=view
    idx['candidate_id']=[digest([view,*row])[:24] for row in idx[KEY].itertuples(index=False,name=None)]
    d=d.merge(idx[KEY+['candidate_id']],on=KEY,validate='many_to_one')
    return d,idx

def balanced(d,metrics):
    bg=d.groupby(['candidate_id','building','image','common_background_id'],dropna=False)[metrics].mean()
    images=bg.groupby(level=['candidate_id','building','image']).mean()
    buildings=images.groupby(level=['candidate_id','building']).mean()
    return bg,images,buildings

def agg_stats(d,metrics,prefix):
    g=d.groupby(level='candidate_id') if isinstance(d.index,pd.MultiIndex) else d.groupby('candidate_id')
    mean=g[metrics].mean();median=g[metrics].median();count=g[metrics].count()
    out={}
    for metric in metrics:
        for stat,table in [('mean',mean),('median',median),('valid',count)]:out[metric+'__'+prefix+'_'+stat]=table[metric]
    if prefix in ['image','building']:
        for sign in ['positive','negative','zero']:
            v=d[metrics].gt(1e-10) if sign=='positive' else d[metrics].lt(-1e-10) if sign=='negative' else d[metrics].abs().le(1e-10)
            n=v.groupby(level='candidate_id').sum()
            for metric in metrics:out[metric+'__'+prefix+'_'+sign]=n[metric]
    return pd.DataFrame(out)

def condition_support(d):
    g=d.groupby('candidate_id',sort=False)
    support=g.agg(events=('analysis_event_id','size'),registered_rows=('registered_rows','sum'),
      actual_exchanges=('actual_exchange_id','nunique'),directed_pairs=('directed_pair_id','nunique'),
      backgrounds=('common_background_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),
      stages=('prior_stages',lambda s:'|'.join(sorted(set('|'.join(s).split('|'))))),
      families=('fold_selected_family',lambda s:'|'.join(sorted(set(s.astype(str))))),
      coarse_k_min=('fold_coarse_k','min'),coarse_k_max=('fold_coarse_k','max'),
      fine_k_min=('fold_fine_k','min'),fine_k_max=('fold_fine_k','max'),
      whole_class_transfer_events=('whole_class_transfer','sum'),
      class_seat_min=('composition_turnover_AC','min'),class_seat_max=('composition_turnover_AC','max'),
      source_matched_events=('same_source_counts','sum'),Q5_source_matched_events=('source_and_historyQ5_matched','sum'),
      A_failed_events=('A_failure','sum'),B_failed_events=('B_failure','sum'),C_failed_events=('C_failure','sum'))
    # Unique actual endpoints and blocks make repeated use of the same teams
    # visible instead of equating an event count with an independent sample.
    teams=[]
    for cid,z in g:
        ts=set(z.team_A)|set(z.team_C)|set(z.team_B.dropna())
        teams.append(dict(candidate_id=cid,unique_teams=len(ts),
          unique_X_blocks=z.outgoing_block_X.nunique(),unique_Y_blocks=z.same_count_block_Y.nunique(),
          unique_Z_blocks=z.changed_count_block_Z.nunique()))
    return support.join(pd.DataFrame(teams).set_index('candidate_id'))

def selection_reason(row,purpose,prefix='building',min_support=4):
    metric=PURPOSE_METRIC[purpose];sgn=-1 if purpose=='time_saving' else 1
    count=row.get(metric+'__'+prefix+'_valid',0)
    images=row.get('images',0)
    mean=row.get(metric+'__'+prefix+'_mean',np.nan)*sgn
    median=row.get(metric+'__'+prefix+'_median',np.nan)*sgn
    pos=row.get(metric+'__'+prefix+('_negative' if sgn<0 else '_positive'),0)
    reasons=[]
    if purpose=='interchangeability' or purpose.endswith('separation'):
        if row.get('comparison')!='ABC_matched':reasons.append('no_matched_same-composition_arm')
    if not np.isfinite(mean):reasons.append('metric_unavailable')
    if count<min_support:reasons.append('fewer_than_4_valid_buildings')
    if images<min_support:reasons.append('fewer_than_4_images')
    if not (np.isfinite(mean) and mean>=THRESHOLDS[purpose]):reasons.append('mean_below_practical_effect')
    if not(np.isfinite(median) and median>1e-10):reasons.append('median_not_in_selected_direction')
    if count and pos/count<.60:reasons.append('fewer_than_60pct_buildings_same_direction')
    if purpose in ['node_recall','edge_recall'] and pos<3:reasons.append('fewer_than_3_positive_buildings')
    if purpose=='time_saving':
        q=row.get('cross_B8L2_time_qualified__'+prefix+'_mean',np.nan)
        if not(np.isfinite(q) and q>=-2):reasons.append('same-time-support_Q_loss_over_2_or_unknown')
    if str(row.get('direction','')).endswith(':unknown'):reasons.append('historical_direction_unknown')
    return '|'.join(reasons) if reasons else 'selected'

def select_rows(core):
    out=[]
    for row in core.to_dict('records'):
        for purpose in PURPOSE_METRIC:
            reason=selection_reason(row,purpose)
            metric=PURPOSE_METRIC[purpose]
            item={f:row[f] for f in ['candidate_id','view']+KEY+['events','images','buildings','backgrounds','unique_teams']}
            item.update(purpose=purpose,metric=metric,selected=reason=='selected',reason=reason,
              mean=row.get(metric+'__building_mean'),median=row.get(metric+'__building_median'),
              valid_buildings=row.get(metric+'__building_valid'),
              positive_buildings=row.get(metric+'__building_positive'),negative_buildings=row.get(metric+'__building_negative'),
              same_Q_abs=row.get('common_quality_within_abs__building_mean'),
              cross_Q_abs=row.get('common_quality_cross_abs__building_mean'),
              A_fail=row.get('A_failure__building_mean'),C_fail=row.get('C_failure__building_mean'),
              cross_loss_gt10_success_Q=row.get('cross_loss_gt10__building_mean'),
              cross_failure_or_loss_gt10=row.get('cross_failure_or_loss_gt10__building_mean'),
              prior_repeated_exploration=True)
            out.append(item)
    return pd.DataFrame(out)

def detailed_components(d,index,core):
    # Single-building candidates are already fully represented by their event
    # rows and CORE_ALL. Complete component summaries focus on repeated support.
    selected_ids=set(core.loc[core.buildings.ge(2),'candidate_id'])
    z=d[d.candidate_id.isin(selected_ids)]
    bg,im,b=balanced(z,ALL_METRICS)
    stats=agg_stats(z,ALL_METRICS,'event').join(agg_stats(im,ALL_METRICS,'image')).join(agg_stats(b,ALL_METRICS,'building'))
    stats.columns=pd.MultiIndex.from_tuples([c.split('__',1) for c in stats.columns],names=['metric','stat'])
    long=stats.stack(level='metric',future_stack=True).reset_index()
    long=long[long.event_valid.gt(0)]
    return long.merge(index[['candidate_id','view']+KEY],on='candidate_id',validate='many_to_one')

def run_view(d,view):
    start=time.time();x,index=label_view(d,view)
    bg,im,b=balanced(x,METRICS_CORE)
    core=index.set_index('candidate_id').join(condition_support(x)).join(
      agg_stats(x,METRICS_CORE,'event')).join(agg_stats(im,METRICS_CORE,'image')).join(
      agg_stats(b,METRICS_CORE,'building')).reset_index()
    selection=select_rows(core)
    path='views/'+view+'/'
    receipts=[]
    receipts.append(save_csv(path+'CORE_ALL_CANDIDATES.csv.gz',core))
    receipts.append(save_csv(path+'SELECTION_ALL_PURPOSES.csv.gz',selection))
    chosen=selection[selection.selected]
    receipts.append(save_csv(path+'SELECTED_CONDITIONS.csv',chosen))
    receipts.append(save_csv(path+'BUILDING_CORE_MEANS.csv.gz',b.reset_index()))
    receipts.append(save_csv(path+'IMAGE_CORE_MEANS.csv.gz',im.reset_index()))
    mapping=x[['candidate_id','analysis_event_id']].drop_duplicates()
    receipts.append(save_csv(path+'EVENT_MEMBERSHIP.csv.gz',mapping))
    # Complete component table is produced for role-specific, aggregate and
    # historical turn/scale conditions. Other axis screens retain all metrics
    # in the exact event file, so their values remain reproducible.
    if view in ['class_block','class_net','class_any_direction','history_turn','history_area','history_height']:
        components=detailed_components(x,index,core)
        receipts.append(save_csv(path+'ALL_COMPONENTS_REPEATED_SUPPORT.csv.gz',components))
    result=dict(status='complete',view=view,events=len(x),candidate_conditions=len(index),
      repeated_building_conditions=int(core.buildings.ge(2).sum()),selected_purpose_conditions=len(chosen),
      selected_unique_conditions=chosen.candidate_id.nunique(),files=receipts,seconds=time.time()-start,
      native_fusion_calls=0,all_nonselection_reasons_saved=True)
    save_json(path+'COMPLETION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)
    return result

def priority_report(d):
    cases=[('A2_n17m9',(d.method_id.eq('A2_relation')&d.condition.eq('manual')&d.n.eq(17)&d.m.eq(9))),
      ('M_M01_to_M00_n10m5',(d.method_id.eq('M_structure')&d.tier.eq('fine')&d.n.eq(10)&d.m.eq(5)&d.raw_block_direction.eq('M01:5 -> M00:5'))),
      ('M_M01_to_M00_n10m6',(d.method_id.eq('M_structure')&d.tier.eq('fine')&d.n.eq(10)&d.m.eq(6)&d.raw_block_direction.eq('M01:6 -> M00:6'))),
      ('V3_BEHAVIOR_n10m7',(d.method_id.eq('V3_BEHAVIOR')&d.condition.eq('manual')&d.n.eq(10)&d.m.eq(7)))]
    pieces=[]
    for name,mask in cases:
        z=d[mask].copy();z['focus_id']=name
        for mode in ['combined','role_direction','history_turn_direction']:
            x=z.copy();x['view']=mode
            x['direction']='all_actual_directions' if mode=='combined' else x.role_block_direction if mode=='role_direction' else x.direction_turn_history
            pieces.append(x)
    x=pd.concat(pieces,ignore_index=True)
    keys=['focus_id','view','comparison','condition','method_id','tier','source_domain','direction','n','m','parent_fixed']
    ix=x[keys].drop_duplicates()
    ix['candidate_id']=[digest(['priority',*row])[:24] for row in ix[keys].itertuples(index=False,name=None)]
    x=x.merge(ix,on=keys,validate='many_to_one')
    bg,im,b=balanced(x,METRICS_CORE)
    out=ix.set_index('candidate_id').join(condition_support(x)).join(agg_stats(x,METRICS_CORE,'event')).join(
        agg_stats(im,METRICS_CORE,'image')).join(agg_stats(b,METRICS_CORE,'building')).reset_index()
    receipts=[save_csv('PRIORITY_CONDITION_CORE.csv',out),save_csv('PRIORITY_CONDITION_BUILDING_MEANS.csv',b.reset_index().merge(ix,on='candidate_id'))]
    save_json('PRIORITY_SCREEN_COMPLETION.json',dict(status='complete',files=receipts,selection='inherited candidate descriptions; not newly selected',native_calls=0))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--view',choices=VIEWS);parser.add_argument('--priority-only',action='store_true')
    a=parser.parse_args();started=time.time()
    if not(HERE/'UNIFIED_COMPLETION.json').exists():raise RuntimeError('Wait for complete immutable unified table')
    d=read_events();priority_report(d)
    if a.priority_only:return
    completed=[]
    for view in [a.view] if a.view else VIEWS:
        done=HERE/'views'/view/'COMPLETION.json'
        if done.exists():completed.append(json.loads(done.read_text()));continue
        completed.append(run_view(d,view))
        save_json('SCREEN_PROGRESS.json',dict(status='running',views=completed,seconds=time.time()-started))
    if not a.view:save_json('SCREEN_COMPLETION.json',dict(status='complete',views=completed,seconds=time.time()-started,
        source_sha256=sha(HERE/'EVENTS_UNIFIED.csv.gz'),data_version='v2',native_calls=0))

if __name__=='__main__':main()
