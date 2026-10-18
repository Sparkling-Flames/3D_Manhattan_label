"""数据v1阶段整合：只读现有评分/画像/真实团队，不改几何、资格或冻结负载。"""
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/statistics/v1_integrated_analysis_20261017'
COMMON=ROOT/'research/quality/quality_b8l2_d10_20261017'
STATS=ROOT/'research/statistics/b8l2_d10_statistics_20261017'
WORKERS=ROOT/'research/workers/worker_b8l2_d10_20261017'
VERSION='v1_integrated_analysis_20261017_r1'
METRICS=('B8L2','D10')
KEYS=['image_id','condition','rescore_target_id','reference_version']


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def csv(path,frame):
    d=frame.copy()
    for c in d:
        if d[c].map(lambda v:isinstance(v,(list,dict,tuple))).any():
            d[c]=d[c].map(lambda v:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else v)
    d.to_csv(path,index=False,encoding='utf-8-sig')


def summarize(frame):
    """一个采集条件的完整库存切片；已屏蔽的质量不恢复，低尾不是人工错误标签。"""
    assert frame.object_id.is_unique and frame.condition.nunique()<=1
    assert frame.B8L2.notna().equals(frame.D10.notna())
    assert frame.B8L2.notna().equals(frame.quality_usable)
    scored=frame[frame.quality_usable]
    r=dict(n_inventory=len(frame),n_images=frame.image_id.nunique(),n_workers=frame.worker_id.nunique(),
        n_vote_kept=int(frame.pool_vote_eligible.sum()),n_source=int(frame.pool_analysis_eligible.sum()),
        n_quality=len(scored),n_quality_images=scored.image_id.nunique(),n_quality_workers=scored.worker_id.nunique(),
        n_quality_missing_in_source=int((frame.pool_analysis_eligible & ~frame.quality_usable).sum()),
        n_targets=scored.rescore_target_id.nunique())
    for m in METRICS:
        s=scored[m]
        for name,value in dict(mean=s.mean(),median=s.median(),sd=s.std(ddof=1),q10=s.quantile(.1),
            q25=s.quantile(.25),q75=s.quantile(.75),minimum=s.min(),
            image_equal_mean=scored.groupby('image_id')[m].mean().mean()).items():
            r[m+'_'+name]=value
    for name,col in [('source_time','source_active_time_seconds'),('analysis_source_time','active_time_seconds'),
                     ('target_time','target_matched_time_seconds')]:
        s=frame[col].dropna()
        r.update({name+'_n':len(s),name+'_missing':len(frame)-len(s),name+'_median':s.median(),
                  name+'_mean':s.mean(),name+'_q10':s.quantile(.1)})
        r['quality_'+name+'_n']=int((frame.quality_usable & frame[col].notna()).sum())
    return r


def strata(frame,dimensions,axis):
    assert 'condition' in dimensions
    rows=[]
    for identity,cell in frame.groupby(dimensions,dropna=False,sort=True):
        identity=identity if isinstance(identity,tuple) else (identity,)
        rows.append(dict(axis=axis,**dict(zip(dimensions,identity)),**summarize(cell)))
    return pd.DataFrame(rows)


def peer_context(panel,metric):
    """同任务其他人的均分只作任务组成诊断；不是重新拟合的相对Q。"""
    assert not panel.duplicated(KEYS+['worker_id']).any()
    result=panel.copy()
    sums=result.groupby(KEYS,dropna=False)[metric].transform('sum')
    n=result.groupby(KEYS,dropna=False)[metric].transform('count')-1
    result['peer_n']=n
    result['peer_mean']=(sums-result[metric])/n.replace(0,np.nan)
    result['peer_residual']=result[metric]-result.peer_mean
    return result


def worker_mix(panel,profiles):
    rows=[];evidence=[]
    for metric in METRICS:
        fit=profiles[(profiles.panel=='current')&(profiles.axis==metric)&(profiles.fold=='full_descriptive')].set_index('worker_id')
        assert fit.index.is_unique and set(fit.index)==set(panel.worker_id)
        peers=peer_context(panel,metric)
        for worker,cell in peers.groupby('worker_id'):
            f=fit.loc[worker];s=cell[metric]
            rows.append(dict(worker_id=worker,metric=metric,n=len(cell),n_images=cell.image_id.nunique(),
                n_buildings=cell.building_id.nunique(),raw_mean=s.mean(),image_equal_mean=cell.groupby('image_id')[metric].mean().mean(),
                median=s.median(),q10=s.quantile(.1),sd=s.std(ddof=1),relative_Q_effect=f.effect,
                relative_Q_supported=f.supported,relative_Q_label=f.label,n_peer_tasks=int(cell.peer_mean.notna().sum()),
                peer_task_baseline=cell.peer_mean.mean(),mean_peer_residual=cell.peer_residual.mean(),
                simple_share=cell.difficulty_class.eq('简单').mean(),medium_share=cell.difficulty_class.eq('中等').mean(),
                difficult_share=cell.difficulty_class.eq('困难').mean(),label_use='full_sample_descriptive_not_selection'))
        evidence.append(peers[['object_id','worker_id',*KEYS,'peer_n','peer_mean','peer_residual']].assign(metric=metric))
    result=pd.DataFrame(rows)
    for metric,ix in result.groupby('metric').groups.items():
        d=result.loc[ix]
        result.loc[ix,'raw_order']=d.raw_mean.rank(ascending=False,method='average')
        result.loc[ix,'adjusted_order']=d.relative_Q_effect.rank(ascending=False,method='average')
    result['raw_minus_adjusted_order']=result.raw_order-result.adjusted_order
    return result,pd.concat(evidence,ignore_index=True)


def within_worker(frame):
    rows=[]
    for (worker,condition),cell in frame[frame.quality_usable].groupby(['worker_id','condition']):
        for axis in ['difficulty_class','scene_bucket','quality_use']:
            groups={str(k):v for k,v in cell.groupby(axis)}
            for a,b in combinations(sorted(groups),2):
                x,y=groups[a],groups[b]
                row=dict(worker_id=worker,condition=condition,axis=axis,level_a=a,level_b=b,n_a=len(x),n_b=len(y),
                    images_a=x.image_id.nunique(),images_b=y.image_id.nunique(),
                    shared_images=len(set(x.image_id)&set(y.image_id)),
                    interpretation='different_tasks_descriptive_not_causal')
                for metric in METRICS:
                    row.update({metric+'_mean_a':x[metric].mean(),metric+'_mean_b':y[metric].mean(),
                        metric+'_image_equal_a':x.groupby('image_id')[metric].mean().mean(),
                        metric+'_image_equal_b':y.groupby('image_id')[metric].mean().mean(),
                        metric+'_a_minus_b':x[metric].mean()-y[metric].mean(),
                        metric+'_q10_a':x[metric].quantile(.1),metric+'_q10_b':y[metric].quantile(.1)})
                rows.append(row)
    return pd.DataFrame(rows)


def paired_conditions(frame):
    keys=['worker_id','image_id','rescore_target_id','reference_version']
    d=frame[frame.quality_usable & frame.condition.isin(['manual','semi'])]
    assert not d.duplicated(keys+['condition']).any()
    pairs=d[d.condition.eq('manual')].merge(d[d.condition.eq('semi')],on=keys,suffixes=('_manual','_semi'),validate='one_to_one')
    for metric in METRICS:pairs[metric+'_final_semi_minus_manual']=pairs[metric+'_semi']-pairs[metric+'_manual']
    keep=keys+['object_id_manual','object_id_semi']+[m+s for m in METRICS for s in ['_manual','_semi','_final_semi_minus_manual']]
    return pairs[keep].assign(interpretation='matched_final_outputs_not_initialization_gain')


def compose_team(workers,building,axis,profiles):
    fit=profiles[(profiles.panel=='current')&(profiles.axis==axis)&(profiles.fold==building)].set_index('worker_id')
    assert fit.index.is_unique
    labels=[fit.loc[w,'label'] if w in fit.index and fit.loc[w,'supported'] else 'unclassified' for w in workers]
    return labels.count('above_pool'),labels.count('below_pool'),sum(k not in ['above_pool','below_pool'] for k in labels)


def qt_composition(workers,building,axis,profiles):
    q=profiles[(profiles.panel=='current')&(profiles.axis==axis)&(profiles.fold==building)].set_index('worker_id')
    t=profiles[(profiles.panel=='T_source')&(profiles.axis=='T_source')&(profiles.fold==building)].set_index('worker_id')
    counts={k:0 for k in ['higher_faster','higher_slower','lower_faster','lower_slower','unclassified']}
    for w in workers:
        if w not in q.index or w not in t.index or not q.loc[w,'supported'] or not t.loc[w,'supported']:
            counts['unclassified']+=1;continue
        a,b=q.loc[w,'label'],t.loc[w,'label']
        if a not in ['above_pool','below_pool'] or b not in ['above_pool','below_pool']:
            counts['unclassified']+=1;continue
        counts[('higher' if a=='above_pool' else 'lower')+'_'+('faster' if b=='below_pool' else 'slower')]+=1
    return counts


def team_tables(teams,folds,replacements):
    assert not teams.duplicated(['image','subset']).any()
    expanded=[]
    for r in teams.to_dict('records'):
        workers=r['workers'].split('|');assert len(set(workers))==len(workers)==r['k']
        for axis in METRICS:
            high,low,unknown=compose_team(workers,r['building_id'],axis,folds)
            qt=qt_composition(workers,r['building_id'],axis,folds)
            expanded.append(dict(r,label_basis=axis,n_relative_higher=high,n_relative_lower=low,n_unclassified=unknown,
                composition=f'{high}|{low}|{unknown}',classification_source='target_building_out_profiles',
                QT_composition='|'.join(str(qt[k]) for k in qt),**{'QT_'+k:v for k,v in qt.items()},
                D10_minus_B8L2=r['D10']-r['B8L2']))
    bridge=pd.DataFrame(expanded)
    primary=bridge[bridge.primary_attempt_eligible]
    rows=[]
    for keys,d in primary.groupby(['image','building_id','k','label_basis','composition']):
        complete=d[d.primary_comparison_eligible]
        r=dict(zip(['image','building_id','k','label_basis','composition'],keys),n_attempts=len(d),
            n_complete=len(complete),n_failed=len(d)-len(complete),complete_rate=len(complete)/len(d),
            n_distinct_member_sets=d.subset.nunique(),member_selection='stored_sets_only_no_reselection')
        for metric in METRICS:
            s=complete[metric]
            r.update({metric+'_mean':s.mean(),metric+'_median':s.median(),metric+'_sd':s.std(),
                metric+'_q10':s.quantile(.1),metric+'_range':s.max()-s.min()})
        rows.append(r)
    pair_rows=[]
    eligible=replacements[replacements.primary_comparison_eligible]
    for axis in METRICS:
        for keys,d in eligible.groupby(['image','building_id','k','current_'+axis+'_swap']):
            r=dict(zip(['image','building_id','k','replacement_kind'],keys),label_basis=axis,n_pairs=len(d),
                n_base_sets=d.base.nunique(),n_teams=len(set(d.team_a)|set(d.team_b)),
                overlapping_pairs=True,floor_change_mean=d.floor_change.mean(),floor_change_median=d.floor_change.median(),
                raw_pair_change_mean=d.raw_pair_change.mean())
            for metric in METRICS:
                r.update({metric+'_change_mean':d[metric+'_change'].mean(),
                    metric+'_abs_change_mean':d[metric+'_change'].abs().mean(),metric+'_change_q10':d[metric+'_change'].quantile(.1)})
            pair_rows.append(r)
    return dict(fixed_team_bridge=bridge,team_composition_summary=pd.DataFrame(rows),
                replacement_group_summary=pd.DataFrame(pair_rows))


def semi_tables(records):
    from ..data_prep.consolidate_research_input import load_current_bundle
    bundle=load_current_bundle(ROOT/'analysis_results/research_input_20261017/manifest.json')
    objects={o['object_id']:o for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    evidence=ROOT/'analysis_results/annotation_research_prework_20260905_v2/evidence'
    initial=pd.read_csv(evidence/'initialization_trace.csv').set_index('canonical_annotation_id')
    changes=pd.read_csv(evidence/'semi_initial_final_changes.csv').set_index('canonical_annotation_id')
    historical=pd.read_csv(ROOT/'research/workers/worker_four_axis_update_20261015/semi_records.csv').set_index('object_id')
    assert initial.index.is_unique and changes.index.is_unique and set(initial.index)==set(historical.index)==set(changes.index)
    current=records[records.condition.eq('semi')].set_index('object_id');assert set(current.index)==set(initial.index)
    targeted=pd.DataFrame(bundle['data']['model_unchanged_audit']);assert targeted.object_id.is_unique
    selected=set(targeted.object_id)
    rows=[]
    for oid,row in current.iterrows():
        obj=objects[oid];i=initial.loc[oid];c=changes.loc[oid]
        assert np.allclose(json.loads(c.final_points_json),obj['original_export_points'],rtol=0,atol=1e-8),oid
        assert i.initial_import_match_status=='all_matching' and i.initial_runtime_preview_match
        ev=obj['review_evidence'].get('trap_model_evidence',{});check=ev.get('model_check') or {}
        rows.append(dict(object_id=oid,worker_id=obj['worker_id'],image_id=obj['image_id'],image_code=obj['image_code'],
            cleaning_disposition=obj['cleaning_disposition'],trap_status=ev.get('trap_status','not_recorded'),
            current_coordinate_audit=ev.get('model_edit_status','not_checked'),
            model_check_present=bool(check),targeted_note=oid in selected,
            initial_import_match=i.initial_import_match_status,initial_runtime_preview_match=i.initial_runtime_preview_match,
            exact_checkpoint_bound=False,actual_view_event_proven=False,initial_import_sources=i.initial_import_paths_json,
            proposal_id=c.proposal_id,proposal_response_id=c.proposal_response_id,
            legacy_order_sensitive_exact_equal=c.exact_geometry_equal,
            legacy_edit_ospa30=historical.loc[oid,'edit_ospa30'],legacy_gain_ospa30=historical.loc[oid,'gain_ospa30'],
            final_quality_usable=row.quality_usable,final_B8L2=row.B8L2,final_D10=row.D10,
            calculation_status=row.calculation_status,current_target_id=row.rescore_target_id,
            source_active_time_seconds=row.source_active_time_seconds,target_matched_time_seconds=row.target_matched_time_seconds,
            current_B8L2_gain=np.nan,current_D10_gain=np.nan,
            provenance_status='planned_import_and_runtime_preview_not_view_event'))
    chains=pd.DataFrame(rows)
    worker=[]
    for wid,d in chains.groupby('worker_id'):
        worker.append(dict(worker_id=wid,n_semi=len(d),n_credible_import_preview=len(d),
            n_current_model_checks=int(d.model_check_present.sum()),n_targeted_notes=int(d.targeted_note.sum()),
            n_trap=int(d.trap_status.eq('confirmed_trap').sum()),n_nontrap=int(d.trap_status.eq('confirmed_nontrap').sum()),
            n_trap_unknown=int((~d.trap_status.isin(['confirmed_trap','confirmed_nontrap'])).sum()),
            n_coordinate_unchanged=int(d.current_coordinate_audit.eq('unchanged_coordinates').sum()),
            n_coordinate_changed=int(d.current_coordinate_audit.eq('changed_coordinates').sum()),
            n_coordinate_not_checked=int(d.current_coordinate_audit.eq('not_checked').sum()),
            n_final_quality=int(d.final_quality_usable.sum()),n_initial_final_B8L2_gain=0,
            note='targeted notes are not a population error denominator'))
    exclusions=records[records.cleaning_disposition.isin(['excluded_by_review','historical_not_accepted'])][[
        'object_id','worker_id','image_id','image_code','condition','cleaning_disposition','pool_vote_exclusion_reasons',
        'quality_exclusion_reasons']].copy()
    exclusions['overlap_with_targeted_note']=exclusions.object_id.isin(selected)
    exclusions['severity_status']='cleaning_source_only_see_reliability_event_links_for_cited_attribution'
    notes=targeted[[c for c in ['object_id','worker_id','image_id','image_code','condition','model_edit_status','trap_status',
        'comment_evidence','influence_comment','evidence_interpretation'] if c in targeted]].copy()
    return dict(semi_chain_crosswalk=chains,semi_worker_coverage=pd.DataFrame(worker),
        exclusion_event_crosswalk=exclusions,targeted_model_notes=notes)


def reliability_summary(evidence):
    rows=[]
    for (worker,condition),d in evidence.groupby(['worker_id','condition']):
        known=d.known_wrong_initialization_opportunity
        remains=d.explicit_error_remains & known
        repaired=d.explicit_correction_success & known
        assessed=d.severe_assessed_under_explicit_rule
        n=int(known.sum());errors=int(d.confirmed_person_error_exclusion.sum())
        q=d[d.quality_usable]
        row=dict(worker_id=worker,condition=condition,n_total=len(d),n_images=d.image_id.nunique(),
            n_quality=len(q),n_targeted_notes=int(d.targeted_audit_member.sum()),
            n_known_person_error=errors,n_severe_assessed=int(assessed.sum()),
            n_severe_attribution_unknown=len(d)-int(assessed.sum()),
            known_person_error_share_all_submissions=errors/len(d),
            known_person_error_share_assessed=errors/int(assessed.sum()) if assessed.any() else np.nan,
            n_known_error_opportunity=n,n_explicit_unfixed=int(remains.sum()),n_explicit_repaired=int(repaired.sum()),
            n_repair_status_unknown=int((known & ~remains & ~repaired).sum()),
            known_unfixed_lower_bound_share=int(remains.sum())/n if n else np.nan,
            overlap_unfixed_person_error=int((remains & d.confirmed_person_error_exclusion).sum()),
            rates_not_population_estimates=True)
        for m in METRICS:row.update({m+'_retained_quality_mean':q[m].mean(),m+'_retained_quality_q10':q[m].quantile(.1)})
        rows.append(row)
    return pd.DataFrame(rows)


def current_reliability(records):
    source=ROOT/'research/workers/worker_v1_composition_20261017'
    if not (source/'record_evidence.csv').is_file():return {}
    ev=pd.read_csv(source/'record_evidence.csv')
    assert ev.object_id.is_unique and set(ev.object_id)==set(records.object_id)
    a,b=ev.set_index('object_id').sort_index(),records.set_index('object_id').sort_index()
    for c in ['worker_id','image_id','condition','quality_usable','B8L2','D10']:
        pd.testing.assert_series_equal(a[c],b[c])
    assert not (ev.explicit_error_remains & ~ev.known_wrong_initialization_opportunity).any()
    assert not (ev.explicit_error_remains & ev.explicit_correction_success).any()
    columns=['object_id','worker_id','image_id','condition','targeted_audit_member',
        'known_wrong_initialization_opportunity','explicit_error_remains','explicit_correction_success',
        'confirmed_person_error_exclusion','severe_assessed_under_explicit_rule','source_pointer',
        'current_metric_net_gain_status']
    return dict(reliability_worker_summary=reliability_summary(ev),reliability_event_links=ev[columns])


def attach_stability(states,pairs):
    keys=['pool_id','k']
    fields=['path_id','R_union_normalized','B8L2','D10','main_comparison_allowed','complete_evaluable','subset']
    a=states[keys+fields].rename(columns={c:c+'_a' for c in fields})
    b=states[keys+fields].rename(columns={c:c+'_b' for c in fields})
    joined=pairs.merge(a,left_on=keys+['path_a'],right_on=keys+['path_id_a'],validate='many_to_one')
    joined=joined.merge(b,left_on=keys+['path_b'],right_on=keys+['path_id_b'],validate='many_to_one')
    assert len(joined)==len(pairs)
    joined['both_main_quality']=(joined.main_comparison_allowed_a & joined.main_comparison_allowed_b
        & joined.B8L2_a.notna() & joined.B8L2_b.notna())
    joined['R_pair_mean']=(joined.R_union_normalized_a+joined.R_union_normalized_b)/2
    for m in METRICS:joined[m+'_abs_difference']=(joined[m+'_a']-joined[m+'_b']).abs()
    return joined


def process_tables(records,folds):
    source=ROOT/'research/fusion/wall_consensus_v1_process_20261017'
    inputs=OUT/'inputs';inputs.mkdir(exist_ok=True)
    if (inputs/'fusion_states.csv').is_file():
        previous=read(OUT/'FUSION_INPUT_SNAPSHOT.json')
        status=previous['status_before'];status_after=previous['status_after']
        states=pd.read_csv(inputs/'fusion_states.csv',low_memory=False)
        stability=pd.read_csv(inputs/'fusion_stability.csv');transitions=pd.read_csv(inputs/'fusion_transitions.csv')
    else:
        status=read(source/'STATUS.json')
        states=pd.read_csv(source/'trajectory_scores.csv',low_memory=False)
        stability=pd.read_csv(source/'same_k_stability.csv');transitions=pd.read_csv(source/'transitions.csv')
        status_after=read(source/'STATUS.json')
    assert not states.duplicated(['pool_id','path_id','k']).any()
    pathcheck=states.groupby(['pool_id','path_id']).agg(n=('k','size'),max_k=('k','max'),
        min_k=('k','min'),pool_n=('original_pool_n','max'))
    assert (pathcheck.n.eq(pathcheck.pool_n)&pathcheck.max_k.eq(pathcheck.pool_n)&pathcheck.min_k.eq(1)).all()
    assert states.B8L2.notna().equals(states.D10.notna())
    assert states.loc[states.k.eq(1),'R_union_normalized'].isna().all()
    assert (states.R_valid_pairs<=states.R_possible_pairs).all()
    persons=pd.read_csv(ROOT/'research/workers/worker_v1_composition_20261017/fold_person_profiles.csv')
    for p in persons.to_dict('records'):
        assert p['fold'] not in json.loads(p['Q_training_buildings'])
        assert p['fold'] not in json.loads(p['T_source_training_buildings'])
    fit=persons.set_index(['fold','metric','worker_id']);assert fit.index.is_unique
    fit=fit[['Q_group','QT_group']].to_dict('index')
    poolmeta=states[['pool_id','image','condition','layer','difficulty','original_pool_n']].drop_duplicates()
    assert poolmeta.pool_id.is_unique
    image_building=records.drop_duplicates('image_code').set_index('image_code').building_id.to_dict()
    members=[]
    for row in states.to_dict('records'):
        workers=row['member_workers'].split('|');assert len(set(workers))==row['k']
        building=image_building[row['image']]
        for metric in METRICS:
            qs=[];qt=[]
            for w in workers:
                key=(building,metric,w)
                p=fit.get(key)
                qs.append(p['Q_group'] if p is not None else 'unclassified')
                qt.append(p['QT_group'] if p is not None else 'unclassified')
            high=qs.count('higher');low=qs.count('lower');unknown=len(qs)-high-low
            members.append(dict(pool_id=row['pool_id'],path_id=row['path_id'],k=row['k'],label_basis=metric,
                composition=f'{high}|{low}|{unknown}',n_higher=high,n_lower=low,n_unclassified=unknown,
                QT_composition='|'.join(str(qt.count(k)) for k in ['higher_faster','higher_slower','lower_faster','lower_slower']),
                QT_unclassified=sum(k not in ['higher_faster','higher_slower','lower_faster','lower_slower'] for k in qt)))
    bridge=pd.DataFrame(members)
    retained=['pool_id','path_id','k','image','condition','layer','difficulty','reference_id','reference_version',
        'path_kind','request_id','subset','same_target','quality_allowed','main_comparison_allowed',
        'original_pool_n','complete_evaluable','R_union_normalized','R_symdiff_h2','R_valid_pairs','R_possible_pairs',
        'B8L2','D10','source_time_available','source_active_seconds']
    bridge=bridge.merge(states[retained],on=['pool_id','path_id','k'],validate='many_to_one')
    random=states[states.path_kind.eq('random')]
    summary=[]
    for keys,d in random.groupby(['pool_id','k']):
        q=d[d.main_comparison_allowed & d.B8L2.notna()]
        row=dict(pool_id=keys[0],k=keys[1],path_attempts=len(d),path_complete=int(d.complete_evaluable.sum()),
            n_quality=int(d.B8L2.notna().sum()),n_main_quality=len(q),subset_n=d.subset.nunique(),
            R_mean=d.R_union_normalized.mean(),R_symdiff_h2_mean=d.R_symdiff_h2.mean(),
            R_valid_pairs_min=int(d.R_valid_pairs.min()),R_possible_pairs=int(d.R_possible_pairs.max()),
            source_time_complete_paths=int(d.source_time_available.sum()),
            source_active_seconds_mean=d.source_active_seconds.mean())
        for m in METRICS:row.update({m+'_main_mean':q[m].mean(),m+'_main_q10':q[m].quantile(.1)})
        summary.append(row)
    summary=pd.DataFrame(summary).merge(poolmeta,on='pool_id',validate='many_to_one')
    pairs=attach_stability(states,stability)
    v=[]
    for keys,d in pairs.groupby(['pool_id','k']):
        unique=d[~d.same_subset]
        q=d[d.both_main_quality]
        v.append(dict(pool_id=keys[0],k=keys[1],stability_attempts=len(d),same_subset_pairs=int(d.same_subset.sum()),
            valid_floor_pairs=int(d.floor_jaccard_difference.notna().sum()),
            distinct_subset_floor_pairs=int(unique.floor_jaccard_difference.notna().sum()),
            V_mean_all=d.floor_jaccard_difference.mean(),V_mean_distinct_subsets=unique.floor_jaccard_difference.mean(),
            both_main_quality_pairs=len(q),B8L2_abs_difference_mean=q.B8L2_abs_difference.mean(),
            D10_abs_difference_mean=q.D10_abs_difference.mean()))
    summary=summary.merge(pd.DataFrame(v),on=['pool_id','k'],validate='one_to_one')
    fields=['pool_id','path_id','k','B8L2','D10','R_union_normalized','complete_evaluable','main_comparison_allowed','subset','member_workers']
    a=states[fields].rename(columns={c:c+'_from' for c in fields if c not in ['pool_id','path_id']})
    b=states[fields].rename(columns={c:c+'_to' for c in fields if c not in ['pool_id','path_id']})
    steps=transitions.merge(a,on=['pool_id','path_id','k_from'],validate='many_to_one').merge(
        b,on=['pool_id','path_id','k_to'],validate='many_to_one')
    assert len(steps)==len(transitions) and steps.k_to.sub(steps.k_from).eq(1).all()
    for r in steps[['member_workers_from','member_workers_to']].itertuples(index=False):
        assert set(r[0].split('|'))<set(r[1].split('|'))
    steps['both_main_quality']=(steps.main_comparison_allowed_from & steps.main_comparison_allowed_to
        & steps.B8L2_from.notna() & steps.B8L2_to.notna())
    for m in METRICS:steps[m+'_delta']=(steps[m+'_to']-steps[m+'_from']).where(steps.both_main_quality)
    steps['R_delta']=steps.R_union_normalized_to-steps.R_union_normalized_from
    step_summary=[]
    for keys,d in steps.groupby(['pool_id','path_kind','k_from','k_to']):
        q=d[d.both_main_quality]
        row=dict(pool_id=keys[0],path_kind=keys[1],k_from=keys[2],k_to=keys[3],path_pairs=len(d),both_main_quality=len(q),
            to_incomplete=int((d.complete_evaluable_from & ~d.complete_evaluable_to).sum()),
            to_complete=int((~d.complete_evaluable_from & d.complete_evaluable_to).sum()),
            floor_change_mean=d.floor_jaccard_difference.mean(),R_delta_mean=d.R_delta.mean())
        for m in METRICS:row.update({m+'_mean_delta':q[m+'_delta'].mean(),
            m+'_positive_paths':int(q[m+'_delta'].gt(0).sum()),m+'_negative_paths':int(q[m+'_delta'].lt(0).sum())})
        step_summary.append(row)
    step_summary=pd.DataFrame(step_summary).merge(poolmeta,on='pool_id',validate='many_to_one')
    composition=[]
    for axis in ['composition','QT_composition']:
        for keys,d in bridge[bridge.path_kind.eq('random')].groupby(['pool_id','k','label_basis',axis]):
            q=d[d.main_comparison_allowed & d.B8L2.notna()]
            row=dict(pool_id=keys[0],k=keys[1],label_basis=keys[2],composition_axis=axis,composition=keys[3],
                n_attempts=len(d),n_complete=int(d.complete_evaluable.sum()),n_main_quality=len(q),
                distinct_member_sets=d.subset.nunique(),R_mean=d.R_union_normalized.mean())
            for m in METRICS:row[m+'_mean']=q[m].mean()
            composition.append(row)
    write(OUT/'FUSION_INPUT_SNAPSHOT.json',dict(status_before=status,status_after=status_after,
        published_status_count_matches=status_after['path_states']==len(states),
        source=source.relative_to(ROOT).as_posix(),
        state_rows=len(states),same_k_pairs=len(stability),transitions=len(transitions),
        path_kinds=states.path_kind.value_counts().to_dict(),complete_paths=len(pathcheck),
        selection_status='only actual complete published paths; missing requested outcomes remain missing'))
    # 保存本次实际读取的完成批次；上游后续接请求不改变本轮分母。
    if not (inputs/'fusion_states.csv').exists():
        for name,frame in [('fusion_states.csv',states),('fusion_stability.csv',stability),('fusion_transitions.csv',transitions)]:csv(inputs/name,frame)
    comp_stability=[]
    for metric in METRICS:
        c=bridge[bridge.label_basis.eq(metric)][['pool_id','path_id','k','composition','n_unclassified']]
        a=c.rename(columns={'path_id':'path_a','composition':'composition_a','n_unclassified':'unknown_a'})
        b=c.rename(columns={'path_id':'path_b','composition':'composition_b','n_unclassified':'unknown_b'})
        pair=pairs.merge(a,on=['pool_id','path_a','k'],validate='many_to_one').merge(
            b,on=['pool_id','path_b','k'],validate='many_to_one')
        pair['composition_relation']=np.where(pair.unknown_a.add(pair.unknown_b).gt(0),'classification_incomplete',
            np.where(pair.composition_a.eq(pair.composition_b),'same_Q_composition','different_Q_composition'))
        for keys,d in pair.groupby(['pool_id','k','composition_relation']):
            changed=d[~d.same_subset];q=changed[changed.both_main_quality]
            comp_stability.append(dict(pool_id=keys[0],k=keys[1],composition_relation=keys[2],label_basis=metric,
                n_pairs=len(d),n_same_members=int(d.same_subset.sum()),n_distinct_members=len(changed),
                n_valid_distinct_geometry=int(changed.floor_jaccard_difference.notna().sum()),
                V_mean_distinct=changed.floor_jaccard_difference.mean(),n_both_main_quality=len(q),
                B8L2_abs_difference=q.B8L2_abs_difference.mean(),D10_abs_difference=q.D10_abs_difference.mean()))
    requested=request_contrasts(states)
    return dict(process_member_composition=bridge,process_image_k=summary,process_stability_pairs=pairs,
        process_adjacent_steps=steps,process_step_summary=step_summary,
        process_composition_summary=pd.DataFrame(composition),
        process_composition_stability=pd.DataFrame(comp_stability),**requested)


def request_contrasts(states):
    worker=ROOT/'research/workers/worker_v1_composition_20261017'
    saved=OUT/'inputs';saved.mkdir(parents=True,exist_ok=True)
    planned_path=saved/'planned_metric_contrasts.csv'
    planned=pd.read_csv(planned_path if planned_path.exists() else worker/'metric_selection_contrasts.csv')
    if not planned_path.exists():csv(planned_path,planned)
    computed=states[states.request_id.notna()].copy()
    failure_path=saved/'worker_request_status.json'
    upstream_failure=ROOT/'research/fusion/wall_consensus_v1_process_20261017/worker_request_status.json'
    failure=read(failure_path if failure_path.exists() else upstream_failure) if (
        failure_path.exists() or upstream_failure.exists()) else dict(rejected_paths=[])
    if not failure_path.exists():write(failure_path,failure)
    failed_images={r['image'] for r in failure['rejected_paths']}
    for key,d in computed.groupby('request_id'):
        assert all(d[c].nunique(dropna=False)==1 for c in ['pool_id','subset','reference_id','reference_version','B8L2','D10','main_comparison_allowed']),key
    scores=computed.drop_duplicates('request_id')
    fields=['request_id','reference_id','reference_version','main_comparison_allowed','B8L2','D10']
    a=scores[fields].rename(columns={k:k+'_fixed' for k in fields})
    b=scores[fields].rename(columns={k:k+'_reselected' for k in fields})
    d=planned.merge(a,left_on='B8L2_selected_team',right_on='request_id_fixed',how='left',validate='many_to_one')
    d=d.merge(b,left_on='D10_reselected_team',right_on='request_id_reselected',how='left',validate='many_to_one')
    d['both_published']=d.request_id_fixed.notna()&d.request_id_reselected.notna()
    d['publication_status']=np.where(d.both_published,'published',np.where(
        d.image_code.isin(failed_images) if 'image_code' in d else False,'whole_pool_input_failed','not_published'))
    same=(d.reference_id_fixed.eq(d.reference_id_reselected)&d.reference_version_fixed.eq(d.reference_version_reselected))
    assert same[d.both_published].all()
    mask=(d.both_published & d.main_comparison_allowed_fixed.eq(True)&d.main_comparison_allowed_reselected.eq(True)
        & d.B8L2_fixed.notna()&d.B8L2_reselected.notna())
    d['both_main_quality']=mask
    d['fixed_member_D10_minus_B8L2']=(d.D10_fixed-d.B8L2_fixed).where(mask)
    d['reselection_at_fixed_B8L2']=(d.B8L2_reselected-d.B8L2_fixed).where(mask)
    d['reselection_at_fixed_D10']=(d.D10_reselected-d.D10_fixed).where(mask)
    assert np.allclose(d.loc[mask,'fixed_member_D10_minus_B8L2']+d.loc[mask,'reselection_at_fixed_D10'],
        d.loc[mask,'D10_reselected']-d.loc[mask,'B8L2_fixed'])
    request_path=saved/'planned_worker_paths.json'
    request=read(request_path if request_path.exists() else worker/'TEAM_REQUESTS.json');paths=[]
    if not request_path.exists():write(request_path,dict(data_release='v1',paths=request['paths']))
    indexed=scores.set_index('request_id')
    for p in request['paths']:
        if p['policy']=='random':continue
        for k,(target,control) in enumerate(zip(p['prefix_request_ids'],p['matched_random_prefix_request_ids']),1):
            x=indexed.loc[target] if target in indexed.index else None
            y=indexed.loc[control] if control in indexed.index else None
            valid=(x is not None and y is not None and x.main_comparison_allowed and y.main_comparison_allowed
                and pd.notna(x.B8L2) and pd.notna(y.B8L2))
            row=dict(image_id=p['image_id'],image=p['image_code'],path_id=p['path_id'],policy=p['policy'],
                selection_metric=p['selection_metric'],k=k,target_request=target,random_request=control,
                focus_supported=p['policy_has_focus_support'],both_published=x is not None and y is not None,
                focus_available_n=p['focus_group_available_n'],
                focus_covers_k=p['focus_group_available_n'] is not None and p['focus_group_available_n']>=k,
                both_main_quality=valid)
            row['publication_status']='published' if row['both_published'] else (
                'whole_pool_input_failed' if p['image_code'] in failed_images else 'not_published')
            for m in METRICS:
                row[m+'_strategy_minus_random']=x[m]-y[m] if valid else np.nan
                row[m+'_strategy']=x[m] if valid else np.nan
                row[m+'_random']=y[m] if valid else np.nan
            paths.append(row)
    strategies=pd.DataFrame(paths)
    return dict(metric_reselection_contrasts=d,strategy_vs_matched_random=strategies,
                strategy_common_pool_summary=strategy_comparisons(strategies) if len(strategies) else pd.DataFrame())


def strategy_comparisons(frame):
    comparisons=[('Q_higher_first','Q_lower_first'),('QT_higher_faster_first','QT_higher_slower_first'),
                 ('QT_lower_faster_first','QT_lower_slower_first')]
    rows=[]
    for metric in METRICS:
        at=frame[frame.k.eq(3)&frame.selection_metric.eq(metric)]
        valid=at[at.both_main_quality & at.focus_covers_k]
        for left,right in comparisons:
            a=valid[valid.policy.eq(left)];b=valid[valid.policy.eq(right)]
            d=a.merge(b,on='image_id',suffixes=('_left','_right'),validate='one_to_one')
            row=dict(selection_metric=metric,k=3,left_policy=left,right_policy=right,
                n_planned_images=at.image_id.nunique(),n_eligible_left=len(a),n_eligible_right=len(b),n_common_images=len(d),
                focus_covers_entire_k=True)
            for outcome in METRICS:
                delta=d[outcome+'_strategy_left']-d[outcome+'_strategy_right']
                row.update({outcome+'_left_minus_right_mean':delta.mean(),outcome+'_left_minus_right_median':delta.median(),
                    outcome+'_positive_images':int(delta.gt(0).sum()),outcome+'_negative_images':int(delta.lt(0).sum())})
            rows.append(row)
    return pd.DataFrame(rows)


def same_room_integration():
    p=ROOT/'research/same_room/same_room_v1_process_20261017'
    if not (p/'SUMMARY.json').is_file():return {}
    source=read(p/'SUMMARY.json');assert source['data_release']=='v1' and source['quality_records']==1911
    pairs=pd.read_csv(p/'endpoint_pairs.csv')
    pairs=pairs[pairs.condition.eq('manual')&pairs.confirmation.eq('user_classified_comparable')&pairs.metric.isin(METRICS)]
    keys=['image_a','image_b','condition']
    cols=['paired_workers','n_paired','absolute_mean_gap','mean_absolute_person_delta','worker_spearman','user_group_ids','building']
    a=pairs[pairs.metric.eq('B8L2')][keys+cols]
    b=pairs[pairs.metric.eq('D10')][keys+cols]
    d=a.merge(b,on=keys,validate='one_to_one',suffixes=('_B8L2','_D10'))
    assert d.paired_workers_B8L2.equals(d.paired_workers_D10) and d.n_paired_B8L2.equals(d.n_paired_D10)
    panel=pd.read_csv(p/'selected_process_panel.csv')
    raw=pd.read_csv(p/'original_response_disagreement_summary.csv')
    raw=panel[['request_id','image_a','image_b']].merge(raw,on='request_id',validate='one_to_one')
    d=d.merge(raw[['image_a','image_b','request_id','original_R_a','original_R_b','worker_pair_pattern_spearman']],
        on=['image_a','image_b'],how='left',validate='one_to_one')
    d['same_room_process_status']=source['process_comparison_status']
    d['has_common_quality']=d.n_paired_B8L2.gt(0)
    write(OUT/'SAME_ROOM_INPUT_SNAPSHOT.json',source)
    return dict(same_room_endpoint_integration=d,
        same_room_weighting_sensitivity=pd.read_csv(p/'balanced_endpoint_summary.csv'))


def room_low_tails(records,memberships):
    assert not memberships.duplicated(['group_id','image_id']).any()
    matched=memberships[['group_id','image_id']].merge(records,on='image_id',validate='many_to_many')
    assert not matched.duplicated(['group_id','object_id']).any()
    group=strata(matched,['group_id','condition','quality_use'],'user_original_room_group')
    worker=strata(matched,['group_id','worker_id','condition','quality_use'],'worker_original_room_group')
    d=worker[worker.n_quality.gt(0)]
    spread=[]
    for keys,cell in d.groupby(['worker_id','condition','quality_use']):
        row=dict(zip(['worker_id','condition','quality_use'],keys),n_groups=len(cell),
            groups_overlap=True,smallest_cell_n=int(cell.n_quality.min()),largest_cell_n=int(cell.n_quality.max()))
        for m in METRICS:row[m+'_group_mean_range']=cell[m+'_mean'].max()-cell[m+'_mean'].min()
        spread.append(row)
    return group,worker,pd.DataFrame(spread)


def md(frame):
    def value(v):
        if pd.isna(v):return '—'
        if isinstance(v,(float,np.floating)):return f'{v:.2f}'
        return str(v).replace('|',' / ')
    return '\n'.join(['|'+'|'.join(frame.columns)+'|','|'+'|'.join(['---']*len(frame.columns))+'|']+[
        '|'+'|'.join(value(v) for v in row)+'|' for row in frame.itertuples(index=False,name=None)])


def finish_package(tables,records,mix):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False})
    figure=OUT/'figures';figure.mkdir(exist_ok=True)
    main=mix[mix.metric.eq('B8L2')]
    fig,ax=plt.subplots(figsize=(9,5.5))
    scatter=ax.scatter(main.raw_mean,main.relative_Q_effect,s=main.n*2,c=main.peer_task_baseline,cmap='viridis',alpha=.8)
    fig.colorbar(scatter,ax=ax,label='同题其他人均分（排除本人）')
    selected=main.sort_values('raw_minus_adjusted_order',key=abs,ascending=False).head(6)
    offsets=[(5,5),(5,5),(5,-24),(5,5),(-46,-5),(5,14)]
    for r,offset in zip(selected.itertuples(),offsets):ax.annotate(r.worker_id,(r.raw_mean,r.relative_Q_effect),
        xytext=offset,textcoords='offset points',arrowprops=dict(arrowstyle='-',lw=.4,color='#999'))
    ax.axhline(0,color='#888',lw=.7);ax.set(xlabel='相同1048份Manual训练面板：每人原始Q均值',
        ylabel='已发布任务调整相对Q效应',title='绝对输出与相对表现并列：24人，未合成总分')
    fig.text(.08,.01,'点面积随作答数变化；颜色为同任务其他人均分。标出顺序变化最大的6人；仅描述，不用于选人。',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,1))
    for ext in ['png','svg']:fig.savefig(figure/('01_绝对与相对质量.'+ext),dpi=170)
    plt.close(fig)
    process=tables['process_image_k']
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    plot_rows=[]
    for ax,condition in zip(axes,['manual','semi']):
        d=process[process.k.eq(3)&process.condition.eq(condition)&process.layer.eq('ordinary')&
            process.original_pool_n.gt(3)&process.R_valid_pairs_min.eq(process.R_possible_pairs)&
            process.V_mean_distinct_subsets.notna()].copy()
        ax.scatter(d.R_mean,d.V_mean_distinct_subsets,s=23,alpha=.7,color='#267984')
        ax.set(xlabel='当前3人原答R（固定全池面积归一化）',ylabel='不同成员融合底面的V = 1−IoU',
            title=f'{condition}：{len(d)}个图×条件池，固定k=3')
        plot_rows.append(d.assign(figure_condition=condition))
    fig.text(.05,.01,'每池仅4条随机路径；相同成员对与全池k=N的零波动不入散点。未做显著性或因果解释。',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1))
    for ext in ['png','svg']:fig.savefig(figure/('02_原答分歧与融合稳定性.'+ext),dpi=170)
    plt.close(fig);csv(figure/'02_plot_data.csv',pd.concat(plot_rows,ignore_index=True))
    contrast=tables['metric_reselection_contrasts']
    cols=['fixed_member_D10_minus_B8L2','reselection_at_fixed_B8L2','reselection_at_fixed_D10']
    d=contrast[contrast.k.eq(3)&contrast.both_main_quality].groupby('image_id')[cols].mean().dropna()
    fig,ax=plt.subplots(figsize=(9,5))
    if len(d):ax.boxplot([d[c] for c in cols],labels=['固定成员：D10−B8L2','重选成员：固定B8L2评价','重选成员：固定D10评价'],showfliers=True)
    ax.axhline(0,color='#888',lw=.7);ax.set(ylabel='评分差（分）',title=f'指标尺度与重选人员分开：固定k=3，{len(d)}图等权')
    fig.text(.05,.01,'每图先平均本次已完整发布的策略；未发布/不合用途的请求保留缺失。分数变化不证明几何改善。',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1))
    for ext in ['png','svg']:fig.savefig(figure/('03_固定成员与重选成员.'+ext),dpi=170)
    plt.close(fig);csv(figure/'03_plot_data.csv',d.reset_index())
    dependencies=[]
    for module,path,meta,status in [
        ('workers','research/workers/worker_v1_composition_20261017','CHECKS.json','evidence_and_published_requests_adopted'),
        ('fusion','research/fusion/wall_consensus_v1_process_20261017','STATUS.json','captured_complete_published_paths_only'),
        ('same_room','research/same_room/same_room_v1_process_20261017','SUMMARY.json','endpoints_and_R_adopted_paired_process_pending'),
        ('difficulty','research/difficulty/difficulty_v1_analysis_20261017','CHECKS.json','current_v1_strata_and_paired_worker_descriptions_adopted')]:
        p=ROOT/path
        dependencies.append(dict(module=module,path=path,available=(p/meta).is_file(),status=status if (p/meta).is_file() else 'missing',
            handoff_present=(p/'HANDOFF.md').is_file(),source_metadata=read(p/meta) if (p/meta).is_file() else {}))
    csv(OUT/'DEPENDENCIES.csv',pd.DataFrame(dependencies));write(OUT/'DEPENDENCIES.json',dependencies)
    severe=tables['reliability_worker_summary'];events=tables['reliability_event_links']
    explicit=int(events.explicit_error_remains.sum());opportunity=int(events.known_wrong_initialization_opportunity.sum())
    errors=int(events.confirmed_person_error_exclusion.sum());assessed=int(events.severe_assessed_under_explicit_rule.sum())
    case=main[['worker_id','raw_mean','relative_Q_effect','raw_order','adjusted_order','peer_task_baseline','n','n_images']].merge(
        severe.groupby('worker_id',as_index=False).agg(known_person_errors=('n_known_person_error','sum'),
            known_unfixed=('n_explicit_unfixed','sum'),judged=('n_severe_assessed','sum')),on='worker_id',validate='one_to_one')
    csv(OUT/'quality_and_reliability_side_by_side.csv',case)
    case_shift=case.set_index('worker_id').loc[selected.worker_id].reset_index()
    raw_summary=tables['manual_semi_coverage'][['condition','quality_use','n_inventory','n_quality','n_quality_images','B8L2_mean','B8L2_image_equal_mean','D10_mean']].rename(
        columns=dict(condition='条件',quality_use='用途',n_inventory='库存数',n_quality='质量数',n_quality_images='质量图数',
        B8L2_mean='B8作答均分',B8L2_image_equal_mean='B8图等权均分',D10_mean='D10作答均分'))
    base=tables['process_step_summary']
    adjacent=base[(base.k_from>=3)&base.path_kind.eq('random')&base.condition.eq('manual')&
        base.layer.eq('ordinary')&base.both_main_quality.gt(0)]
    total_pairs=len(adjacent);negative=int(adjacent.B8L2_mean_delta.lt(0).sum())
    fusion=read(OUT/'FUSION_INPUT_SNAPSHOT.json')
    request=contrast.groupby('policy').agg(requested=('k','size'),both_published=('both_published','sum'),
        both_main_quality=('both_main_quality','sum'),members_changed=('members_changed','sum')).reset_index()
    csv(OUT/'reselection_coverage.csv',request)
    room=tables.get('same_room_weighting_sensitivity',pd.DataFrame())
    room_display=room[room.metric.eq('B8L2')] if len(room) else room
    room_display=room_display.rename(columns=dict(metric='指标',minimum_common='最低共同人数',pairs='图对数',
        buildings='建筑数',user_groups='人工组数',pair_equal_gap='图对等权差',group_equal_gap='组等权差',
        building_group_equal_gap='建筑与组等权差'))
    findings=dict(data_release='v1',analysis_revision=VERSION,quality_rows=1911,
        semi_known_error_opportunities=opportunity,semi_explicit_unfixed=explicit,
        semi_other_outcomes_not_established=opportunity-explicit,
        known_person_error_exclusions=errors,explicit_severe_assessment_opportunities=assessed,
        no_current_metric_initial_scores=True,manual_semi_matched_final_pairs=len(tables['manual_semi_matched']),
        ordinary_manual_pool_adjacent_cells=total_pairs,B8L2_negative_pool_adjacent_cells=negative,
        captured_process_states=fusion['state_rows'],captured_paths=fusion['complete_paths'],
        captured_process_images=process.image.nunique(),
        metric_reselection_requested=len(contrast),metric_reselection_both_published=int(contrast.both_published.sum()),
        metric_reselection_both_main_quality=int(contrast.both_main_quality.sum()),
        strategy_outcome_missing=int((~tables['strategy_vs_matched_random'].both_published).sum()),
        metric_reselection_whole_pool_failed=int(contrast.publication_status.eq('whole_pool_input_failed').sum()),
        metric_reselection_not_published=int(contrast.publication_status.eq('not_published').sum()),
        same_room_complete_paired_process_not_claimed=True)
    write(OUT/'FINDINGS.json',findings)
    source=read(OUT/'SOURCE_INPUTS.json');source.update(
        process_capture='FUSION_INPUT_SNAPSHOT.json; inputs/fusion_*.csv, replayed on subsequent runs',
        worker_reliability='research/workers/worker_v1_composition_20261017/record_evidence.csv',
        difficulty='research/difficulty/difficulty_v1_analysis_20261017',
        same_room='research/same_room/same_room_v1_process_20261017',
        requested_selection='inputs/planned_metric_contrasts.csv; inputs/planned_worker_paths.json')
    write(OUT/'SOURCE_INPUTS.json',source)
    report=f'''# 数据v1统计整合：质量、人员组成与共识过程

2026-10-17，分析修订 `{VERSION}`。数据仍为v1；共同评分包中的v2、难度中的v6都不是数据v2。本包只读评分、画像、证据和已存真实融合，不改空间归属、难度、GT排除、资格、参数或release，不更新补人记录。

## 1. 当前分母仍成立，但“库存／来源／质量／训练”不能替换

3222份、261图、27源身份；独立票保留2991，来源分析合格2880，质量可用1911（普通1699、门洞188、其它24）。2774完整计算、298仅底面、122输入不可计算、28待绑定相加覆盖全库存；完整计算包含诊断，不能当质量分母。原始清洗retained=2993仍含2份非独立等限制，不等于2991独立票。

{md(raw_summary)}

以上保留Manual/Semi及用途层的作答等权、图等权；不能把总体Manual−Semi均分差叫辅助收益。OOS仅诊断。来源active time有2019份，既有target-matched有440份；两种时间各自按真实非空交集使用，新增5205秒没有伪造成同目标耗时。详见 `inventory_flow.csv`、`coverage_axes.csv`，复用旧统计的完整record_lookup及原因/时间缺失表，未重复另造全167列台账。

## 2. 哪些原均分受任务组成影响

只在人员线程同一1048份普通Manual训练面板比较，24人、87图；原分与已发布任务调整相对Q并列。相对Q不是只减三个难度均值，也未在本包重拟合。下表按原始顺序与相对效应顺序变化幅度机械取6人，顺序仅为描述；不把绝对与相对Q再加成总分。

{md(case_shift[['worker_id','n','n_images','raw_mean','relative_Q_effect','raw_order','adjusted_order','peer_task_baseline']].rename(columns=dict(worker_id='人员',n='作答数',n_images='图数',raw_mean='原均分',relative_Q_effect='相对Q效应',raw_order='原均分顺序',adjusted_order='调整后顺序',peer_task_baseline='同题其他人均分')))}

例如W013原均分约61.01，原始顺序22而任务调整后17，仍为负相对效应；W018原始顺序5、调整后3，不能仅因均分不是最高便判断相对一般。同任务其他人均分是排除本人后的组成线索，仍会受其他人的组成影响，不是纯因果难度。此面板每人每图只有一条，所以个人的图等权和作答等权相同；总体图等权仍可不同。

`worker_mix_adjustment.csv`、`peer_task_evidence.csv`给出所有人而非仅上述例子。`worker_context_relative_effects.csv`复用各难度/门洞的现有相对效应与支持数；`within_worker_contrasts.csv`和原房间组低尾表保留同一人跨条件差异、独立图数、q10和缺失。不同层通常不是同任务，差值不当因果能力变化。q10只是经验低尾，少量记录的分位不稳；不是错误/可接受阈值。

## 3. 清洗后高Q与偶发错误可以并存

人员模块逐事件证据已接入。574份Semi初始链均为计划导入与运行预览匹配；不是精确模型检查点或实际观看事件证明。466份有当前坐标审查，100未改、366修改，其余108未检查；105条定向线索不是574份总体随机审核。旧order-sensitive相等与当前坐标多重集不等同，链表保留两轴，不静默合并。

已登记{opportunity}个已知错误初始化机会，确认错误仍在{explicit}份，其余{opportunity-explicit}份没有因此自动算作修复成功；不能用“1−未改率”造纠错率。已知残留占已知机会的下限为{explicit/opportunity:.1%}，审核选择偏向异常，不外推完整Semi总体。人员线程另有{errors}份明确文字支持的个人错误剔除，分布和审核分母见 `reliability_worker_summary.csv`；全部3222提交作分母是已知错误下限，按明确规则可判断的{assessed}份是另一分母。85份审核排除、133历史未接纳不能全改名个人严重错误；GT、OOS、借点、整人历史排除和来源不明各保留。

`quality_and_reliability_side_by_side.csv`把当前输出Q与已知失误/覆盖并列，没把剔除填0，也没做新的综合分。`reliability_event_links.csv`按object_id保持残留与剔除重叠，不能相加扣两次。当前B8L2/D10的初始化分仍未发布，因此净改善未计算；历史OSPA30收益只作历史列。本次同人员、同图、同目标且双条件都质量可用的Manual/Semi最终配对为{len(tables['manual_semi_matched'])}，不存在可用它替代初始化净收益的依据。

例如W036普通Manual训练原均分73.02、相对效应+5.53，同时有1份明确个人错误剔除、2份确认Semi错误残留。其Semi保留质量20份均分88.30，不会消除这两份纠错线索；反过来也不能拿少量定向事件把其全部输出归零。这正是质量均值与可靠性覆盖需要并列的原因。

## 4. 同k构成与具体成员：只用真实已存输出

旧642个真实团队继续作为单独面板，普通合格尝试399、完整374，25个无完整输出保留；4076替换对重叠，不能当4076个独立样本。`fixed_team_bridge.csv`附目标建筑外的Q二分和Q×T构成，固定成员同时评价B8L2/D10；`team_composition_summary.csv`区分同k构成与同构成不同成员的输出分布。旧团队的参考和用途掩码不因当前单人绑定而自动放宽。

更广过程本次固定读取{fusion['state_rows']}个已完整发布路径节点、{fusion['complete_paths']}条路径；原4随机路径基线覆盖233池/208图，保留1个整池输入失败，不删坏成员凑成功。额外人员策略只采用实际已发布完整路径。本包保存消费快照并默认重放，源STATUS与CSV发布时的计数若短暂错位在FUSION_INPUT_SNAPSHOT中原样记录，不以计划数冒充完成数。当前人员策略覆盖见 `reselection_coverage.csv`，未发布输出仍缺失。

## 5. 原答R、融合V、完整率与参考Q是不同结果

R来自融合线程保存的当前成员原答平均两两底面对称差，归一化分母是固定全池并集；k=1没有R，有效/可能人对数保留。V来自已有同k两个实际融合结果的1−IoU；相同成员与全员k=N的零波动单列，不当正确性证明。四随机路径的重复子集按原路径频次保留，另报唯一集合数。`process_image_k.csv`把R/V、完整路径数、质量数和Q接在同一池×k；`process_composition_stability.csv`进一步区分同Q构成、不同构成、分类不充分及实际成员是否相同。

仅4条随机路径基线、普通Manual且前后均有主用途质量的池×相邻k单元中，有{negative}/{total_pairs}个单元的路径均值B8L2下降。策略路径在底表另按path_kind分层，没有混进随机基线。它们重复使用图片，不是{total_pairs}个独立实验；下降也不自动证明融合无效。缺完整几何和缺参照Q的分母另报，不能只画成功均分讲“增人必然更接近GT”。独立难度模块固定104图的k=3/4/6面板已接入来源：困难组原答R与换组V均值较高，但完整性随k也可能下降；该观察不是难度标签独立验证，不能据此调整标签或推出所有困难图必然不一致。

## 6. 固定成员的指标敏感性与重选成员分开

`metric_reselection_contrasts.csv`保留全部{len(contrast)}个计划比较，其中两端已发布{int(contrast.both_published.sum())}个、双端主用途可比{int(contrast.both_main_quality.sum())}个。{findings['metric_reselection_whole_pool_failed']}个比较因rPc-22整池输入失败没有输出，另有{findings['metric_reselection_not_published']}个尚未发布，归因分列，失败不叫排队。固定成员D10−B8L2只改尺度；另用固定B8L2或固定D10评价重选成员后的差，恒等式逐行核验。不能把重选收益归因于公式，也不能把D10上涨说成几何更准确。`strategy_vs_matched_random.csv`另与原请求配对随机前缀比较，保留策略支持不足、缺输出和失败；不重算融合。

策略名称表示“该类先进入”，不保证人数k时全是该类；`focus_available_n/focus_covers_k`明确该类能否填满前缀，不能把人数不足后补其它人的前缀叫纯高Q或纯快者组合。

在同k=3、两策略类别都足够填满3人、两端均通过主用途资格的共同图片上，另做成对描述，避免直接比较覆盖不同的两列均值：

{md(tables['strategy_common_pool_summary'][['selection_metric','left_policy','right_policy','n_eligible_left','n_eligible_right','n_common_images','B8L2_left_minus_right_median','B8L2_positive_images','B8L2_negative_images']])}

这里“正/负”是共同图片上的真实策略差，不是独立重复试验；Q×T分组也不要求每个终点都优胜。同类人员仍可能产生不同几何，低尾、失败和具体成员效应见底表。

## 7. 房间按已有分类接入，关系不当独立样本

原260组/259工作组及777直接关系登记沿用；房间低尾和人员×房间表可重叠，不跨组相加、不以建筑代房间或传递关系。最新同房模块有83个范围可比Manual端点图对、8建筑、11人工组；不等于83个独立房间。仅换权重就会改变平均端点差：

{md(room_display)}

`same_room_endpoint_integration.csv`保留217个范围可比Manual候选图对，其中83对有共同质量人员，`has_common_quality`明确其余空支持；并列两指标差与已选9对中的原答R。平均差小也可能掩盖相反方向的个人差。新同房已提出9对、4次重放、536个两侧前缀，其中7对参考主资格，但完整成对几何过程仍等待融合结果。本包不从独立随机路径拼造“同一共同人员序列”的同房迁移结论。

## 复算、底表与未完成

运行 `python -m tools.thesis_main.analysis.v1_integrated_analysis_20261017`。SOURCE_INPUTS记录v1与分析修订；FIELD_CONTRACT说明每表、分母、低尾与时间口径；DEPENDENCIES记录已采用和仍待输出。输入快照默认重放，不静默跟随上游滚动扩大本次面板。已有逐人逐图/房间宽表及原因/时间缺失表复用原路径，本包只补低尾、组成与跨模块连接。

关键图：

![绝对与相对质量](figures/01_绝对与相对质量.png)

![原答与融合变化](figures/02_原答分歧与融合稳定性.png)

![尺度与重选](figures/03_固定成员与重选成员.png)

未完成：当前指标下的可信初始化净改善；同房请求的完整成对真实人数过程。rPc-22的整池输入失败及其对应144个重选比较保留，不靠删人“修好”；本次已接全部2580条获准人员策略路径，不能把已拒绝15条叫尚未运行。没有新拟合综合人员分、没有重新算融合几何，没有启动数据v2。各过程、视角及替换对共享人和图，当前是阶段描述而非大量独立实验或因果结论。检查与全局登记需求见HANDOFF。
'''
    (OUT/'README.md').write_text(report,encoding='utf-8')
    contract=read(OUT/'FIELD_CONTRACT.json')
    for name,frame in [('quality_and_reliability_side_by_side',case),('reselection_coverage',request)]:
        contract['files'][name]=dict(rows=len(frame),columns=list(frame.columns))
    contract.update(process_snapshot='inputs/fusion_*.csv are the consumed completed publication, not a new data release',
        reliability='source event decisions from worker_v1_composition; known error shares and judged opportunities separate; unknown not correct',
        low_n='empirical q10 retained even for small n; small cells are not stable tail estimates; not a severe-error cutoff',
        reselection='fixed selected members metric change and reselected members at fixed metric are separate; no unpublished geometry imputation')
    write(OUT/'FIELD_CONTRACT.json',contract)


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    release=read(ROOT/'research/data/releases/CURRENT.json');assert release['data_release']=='v1'
    release_manifest=read(ROOT/release['manifest']);cross=read(COMMON/'CROSS_MODULE_INPUTS.json')
    r=pd.read_csv(STATS/'record_lookup.csv');q=pd.read_csv(ROOT/cross['full_inventory_with_metric_eligibility'])
    assert r.object_id.is_unique and set(r.object_id)==set(q.object_id)
    frozen=pd.read_csv(ROOT/'research/data/releases/v1/records.csv')
    assert set(r.object_id)==set(frozen.object_id)
    assert len(r)==cross['counts']['inventory']==release_manifest['counts']['annotations']
    assert r.B8L2.notna().equals(r.D10.notna()) and r.B8L2.notna().equals(r.quality_usable)
    assert int(r.quality_usable.sum())==cross['counts']['quality_rows']==1911
    for c in ['image_id','worker_id','condition','rescore_target_id','reference_version','B8L2','D10','quality_usable']:
        pd.testing.assert_series_equal(r.set_index('object_id')[c].sort_index(),q.set_index('object_id')[c].sort_index())
    assert not (r.quality_usable & (r.is_oos | ~r.pool_analysis_eligible)).any()
    profiles=pd.read_csv(WORKERS/'profiles.csv');folds=pd.read_csv(WORKERS/'fold_profiles.csv')
    panel=pd.read_csv(WORKERS/'quality_panel.csv');assert set(panel.object_id)<=set(r.object_id)
    for m in METRICS:
        assert np.allclose(panel[m],r.set_index('object_id').loc[panel.object_id,m],rtol=0,atol=1e-8)
    mix,peer=worker_mix(panel,profiles)
    rooms,worker_rooms,room_spread=room_low_tails(r,pd.read_csv(STATS/'user_original_group_memberships.csv'))
    teams=pd.read_csv(WORKERS/'team_scores.csv');replacements=pd.read_csv(WORKERS/'replacement_pairs.csv')
    context_effects=profiles[profiles.panel.str.startswith('difficulty_') | profiles.panel.eq('doorway')].copy()
    tables=dict(worker_mix_adjustment=mix,peer_task_evidence=peer,worker_context_relative_effects=context_effects,
        low_tail_units=pd.concat([strata(r,['worker_id','condition','quality_use'],'worker'),
            strata(r,['image_id','image_code','condition','quality_use'],'image'),
            strata(r,['worker_id','condition','difficulty_class','quality_use'],'worker_difficulty'),
            strata(r,['worker_id','condition','scene_bucket','quality_use'],'worker_scene')],ignore_index=True),
        within_worker_contrasts=within_worker(r),manual_semi_matched=paired_conditions(r),
        room_low_tail=rooms,worker_room_low_tail=worker_rooms,worker_room_spread=room_spread,
        **team_tables(teams,folds,replacements),**semi_tables(r),**current_reliability(r),
        **process_tables(r,folds),**same_room_integration())
    stages={'raw_inventory':np.ones(len(r),dtype=bool),'cleaning_retained':r.cleaning_disposition.eq('retained'),
        'independent_vote_kept':r.pool_vote_eligible,'source_analysis_eligible':r.pool_analysis_eligible,
        'quality_usable':r.quality_usable,'ordinary_quality':r.quality_use.eq('ordinary_primary'),
        'doorway_quality':r.quality_use.eq('doorway_quality'),'other_quality':r.quality_use.eq('special_conditional_only')}
    tables['inventory_flow']=pd.DataFrame([dict(stage=k,n=int(v.sum()),images=r[v].image_id.nunique(),
        workers=r[v].worker_id.nunique(),denominator=len(r),exclusive=False) for k,v in stages.items()])
    axes=[]
    for c in ['condition','cleaning_disposition','calculation_status','quality_use','binding_status']:
        for value,n in r[c].value_counts(dropna=False).items():axes.append(dict(axis=c,value=str(value),n=int(n),denominator=len(r),exclusive_within_axis=True))
    tables['coverage_axes']=pd.DataFrame(axes)
    tables['manual_semi_coverage']=strata(r,['condition','quality_use'],'condition')
    for name,data in tables.items():csv(OUT/(name+'.csv'),data)
    write(OUT/'SOURCE_INPUTS.json',dict(data_release='v1',analysis_revision=VERSION,
        release_policy='research/data/releases/VERSION_POLICY.md',release_manifest=release['manifest'],
        current_score_manifest='research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json',
        score_version=cross['version'],statistics_source=STATS.relative_to(ROOT).as_posix(),
        worker_source=WORKERS.relative_to(ROOT).as_posix(),parameters=cross['parameters'],
        frozen_release_modified=False,common_scores_modified=False,source_tables_reused_without_copy=[
            'worker_inventory.csv','image_inventory.csv','worker_condition_stats.csv','image_condition_stats.csv',
            'worker_difficulty.csv','worker_special_axes.csv','user_original_group_summary.csv',
            'room_direct_pair_summary.csv','exclusion_reason_hits.csv','time_missing_records.csv']))
    checks=dict(data_release='v1',analysis_revision=VERSION,inventory=len(r),images=r.image_id.nunique(),
        quality_rows=int(r.quality_usable.sum()),quality_use=r.quality_use.value_counts().to_dict(),
        vote_retained=int(r.pool_vote_eligible.sum()),source_rows=int(r.pool_analysis_eligible.sum()),
        source_time_n=int(r.source_active_time_seconds.notna().sum()),target_time_n=int(r.target_matched_time_seconds.notna().sum()),
        relative_panel_rows=len(panel),relative_workers=panel.worker_id.nunique(),relative_images=panel.image_id.nunique(),
        teams=len(teams),primary_team_attempts=int(teams.primary_attempt_eligible.sum()),
        primary_team_complete=int(teams.primary_comparison_eligible.sum()),replacement_pairs=len(replacements),
        identical_metric_masks=True,frozen_release_unchanged=True,shared_scores_unchanged=True,
        tables={k:len(v) for k,v in tables.items()})
    write(OUT/'CHECKS.json',checks)
    write(OUT/'FIELD_CONTRACT.json',dict(analysis_revision=VERSION,data_release='v1',
        key='object_id for answers; image/subset for teams; group_id/object_id within overlapping room views',
        metrics='B8L2 primary; D10 only 8 to 10 degree sensitivity, same rows/reference/eligibility',
        low_tail='q10 empirical 10th percentile, not an unacceptable-error label; SD ddof=1; null when undefined',
        weighting='answer equal and image equal separate; source time and audited target time separate; no zero imputation',
        worker_mix='same 1048-row ordinary Manual training panel, existing full-descriptive relative Q; rank shifts descriptive only, never target selection',
        peer_baseline='same image/condition/exact target/reference_version, self excluded; singleton unknown; not a new relative model',
        team_composition='target-building-out profiles on existing stored member sets only; label_basis sensitivity changes grouping not member selection',
        replacement='overlapping same-k swaps; floor_change/raw_pair_change preserve source definitions, not independent trials',
        rooms='existing original user groups; overlaps and pairs not independent/additive; no building-to-room inference',
        manual_semi='matched final scores alone are not Q(final)-Q(initial), nor causal assistance benefit',
        files={k:dict(rows=len(v),columns=list(v.columns)) for k,v in tables.items()}))
    finish_package(tables,r,mix)
    assert read(COMMON/'CROSS_MODULE_INPUTS.json')==cross
    print(json.dumps(checks,ensure_ascii=False),flush=True)
    return tables,r,mix


if __name__=='__main__':run()
