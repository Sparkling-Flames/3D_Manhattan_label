"""New-batch admission, paired B8L2/D10 profiles and frozen-team sensitivity."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .worker_b8l2_20261016 import bind_admission, profile_panel, prediction_rows, performance, csv as write_csv
from .worker_wq_integration_20261015 import read, summarize_entrants
from .worker_classification_progress_20261014 import half_stability
from .wall_consensus_quality_20261015 import save
from .scope_quality_scoring_20261016 import scoring_engine
from .quality_b8l2_d10_20261017 import model_parameters

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'research/quality/quality_b8l2_d10_20261017'
OUT=ROOT/'research/workers/worker_b8l2_d10_20261017'
PREVIOUS=ROOT/'research/workers/worker_b8l2_20261016'
SHARED16=ROOT/'research/statistics/b8l2_shared_v6_20261016'
COMPONENTS=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']


def csv(name,frame):write_csv(name,frame,directory=OUT)


def review_new_record(row, history):
    same=history[history.image_id.eq(row['image_id'])]
    if not same.empty:
        flags=set(same.original_holdout)
        if flags=={True}:return True,'inherited_same_image_holdout'
        if flags=={False}:return False,'existing_nonheld_image_development'
        return None,'inconsistent_historical_image_holdout_pending'
    building=history[history.building_id.eq(row['building_id'])]
    if not building.empty and not building.original_holdout.any():
        return False,'new_image_in_nonheld_building_development'
    return None,'new_image_in_mixed_or_held_building_pending'


def source_time_value(row):
    if pd.notna(row['target_matched_time_seconds']):raise ValueError('new target time is not certified')
    if (row['time_source']!='active_log_v10_admitted' or row['time_rule_version']!='session_max_then_sum_v10_task_worker'
        or row['task_worker_active_seconds']!=row['source_active_time_seconds'] or row['task_worker_active_seconds']<=0):
        raise ValueError('new source time mismatch')
    return float(np.log1p(row['task_worker_active_seconds']))


def admit(data):
    gates=read(PREVIOUS/'admission_snapshot.json')
    historical=pd.DataFrame(gates).merge(pd.read_csv(SHARED16/'shared_records.csv')[['object_id','building_id']],on='object_id',validate='one_to_one')
    batch={r['object_id']:r for r in read(ROOT/'analysis_results/research_input_20261017/batch_admission.json')['records']}
    identity=pd.read_csv(ROOT/'research/statistics/new_annotation_intake_20261017/records.csv')
    identity=identity.set_index('source_id')
    reviews=[]
    for r in data[data.new_batch].to_dict('records'):
        b=batch[r['object_id']];raw=identity.loc[b['source_id']]
        assert all(r[k]==b[k] for k in ['image_id','worker_id','condition'])
        assert raw.worker_mapping_confirmed and raw.worker_id==r['worker_id'] and raw.analysis_included
        assert raw.task_worker_time_adopted and raw.task_worker_active_seconds==r['task_worker_active_seconds']
        assert raw.worker_id in set(historical.worker_id),'new identity requires a separate design'
        held,reason=review_new_record(r,historical)
        usable_source=(r['cleaning_disposition']=='retained' and r['independent_vote_eligible'] and r['pool_vote_eligible']
            and r['worker_quality_gate']=='candidate_pending_geometry' and json.loads(r['main_quality_gate'])['status']=='candidate_pending_geometry')
        development=held is False and usable_source
        g={k:r[k] for k in ['object_id','image_id','worker_id','condition']}
        g.update(original_holdout=held,role='manual_development_candidate' if development else 'held_or_diagnostic',
            personnel_barriers=[] if usable_source else ['source_gate_failed'],
            context_barriers=[] if development else ['original_holdout' if held else 'module_admission_pending'])
        gates.append(g)
        reviews.append(dict(**g,building_id=r['building_id'],image_code=r['image_code'],review_basis=reason,
            source_id=b['source_id'],source_time_log1p=source_time_value(r),task_worker_active_seconds=r['task_worker_active_seconds'],
            source_scope_response=b['worker_scope_response'],quality_usable=r['quality_usable'],
            module_development_candidate=development,formal_eligibility_newly_granted=False))
    assert {r['object_id'] for r in reviews}==set(batch)
    csv('new_admission_review.csv',reviews);save(OUT/'admission_snapshot.json',gates)
    bound=bind_admission(data,gates)
    return bound,pd.DataFrame(reviews)


def add_scores(frame,models):
    d=frame.copy()
    for name,params in zip(['B8L2','D10'],model_parameters(models)):
        values=models.score(*[d[k].to_numpy() for k in COMPONENTS],params=params)
        if name in d:
            assert np.allclose(values,d[name],rtol=0,atol=1e-7),'published score recomposition mismatch'
        d[name]=values
    return d


def context(frame):
    d=frame.copy()
    d['context_key']=d[['image_id','condition','reference_id','reference_version']].apply(lambda r:json.dumps(r.tolist()),axis=1)
    assert not d.duplicated(['context_key','worker_id']).any()
    return d


def fit_panels(bound,models):
    current=context(add_scores(bound[bound.profile_allowed & bound.quality_usable],models))
    previous=add_scores(pd.read_csv(PREVIOUS/'current_quality_panel.csv'),models)
    assert set(previous.object_id)<=set(current.object_id)
    retained=current[current.object_id.isin(previous.object_id)].set_index('object_id').loc[previous.object_id]
    for col in ['worker_id','image_id','condition','reference_id','reference_version']:
        assert retained[col].tolist()==previous[col].tolist(),'old panel identity/reference drift'
    assert np.allclose(retained.B8L2,previous.B8L2,rtol=0,atol=1e-8)
    csv('quality_panel.csv',current)
    door=context(add_scores(bound[bound.quality_use.eq('doorway_quality') & bound.quality_usable & ~bound.is_oos],models))
    door_train=door[door.admission_original_holdout.eq(False)].copy()
    csv('doorway_evidence.csv',door);csv('doorway_training_panel.csv',door_train)
    teams=pd.read_csv(PREVIOUS/'team_scores.csv')
    extra=set(teams.building_id)|set(door.building_id)
    batch_only=current[current.object_id.isin(previous.object_id)|current.new_batch].copy()
    no_fallback=current[~current.binding_status.eq('local_evidence_insufficient_floor_iou_fallback')].copy()
    panels={'previous949':previous,'previous_plus_new_batch':batch_only,'current':current,'no_floor_iou_fallback':no_fallback,'doorway':door_train}
    panels.update({'difficulty_'+str(k):v.copy() for k,v in current.groupby('difficulty_class')})
    fits=[];predictions=[];coverage=[]
    for name,d in panels.items():
        f,p=profile_panel(d,name,['B8L2','D10'],extra)
        fits.append(f);predictions.append(p)
        coverage.append(dict(panel=name,rows=len(d),workers=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=d.building_id.nunique()))
    time_allowed=(bound.condition.eq('manual')&bound.pool_analysis_eligible&bound.ordinary_difficulty_eligible
        &bound.admission_role.eq('manual_development_candidate')&bound.admission_original_holdout.eq(False)
        &bound.admission_personnel_barriers.map(len).eq(0)&bound.admission_context_barriers.map(len).eq(0))
    for name,col in [('T_source','source_active_time_seconds'),('T_target','target_matched_time_seconds')]:
        d=bound[time_allowed & bound[col].notna()].copy()
        assert d[col].gt(0).all() and d.time_source_file.notna().all() and not d.time_source.str.contains('lead_time',case=False).any()
        keys=['image_id','condition']+(['reference_id','reference_version'] if name=='T_target' else [])
        d['context_key']=d[keys].apply(lambda r:json.dumps(r.tolist()),axis=1);d[name]=np.log1p(d[col])
        csv(name+'_panel.csv',d)
        old_time=pd.read_csv(PREVIOUS/(name+'_panel.csv'))
        time_bridge=old_time[['object_id',col]].merge(d[['object_id',col,'new_batch']],on='object_id',how='outer',suffixes=('_previous','_current'),indicator=True)
        time_bridge['seconds_delta']=time_bridge[col+'_current']-time_bridge[col+'_previous']
        assert time_bridge.loc[time_bridge['_merge'].eq('both'),'seconds_delta'].abs().max()<1e-8
        csv(name+'_membership_bridge.csv',time_bridge)
        f,p=profile_panel(d,name,[name],extra|set(current.building_id))
        fits.append(f);predictions.append(p)
        coverage.append(dict(panel=name,rows=len(d),workers=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=d.building_id.nunique()))
    fits=pd.concat(fits,ignore_index=True)
    for axis in ['B8L2','D10']:
        for tname in ['T_source','T_target']:
            for building,test in current.groupby('building_id'):
                if tname=='T_target':test=test[test.target_matched_time_seconds.notna()]
                qf=fits[(fits.panel=='current')&(fits.axis==axis)&(fits.fold==building)]
                tf=fits[(fits.panel==tname)&(fits.fold==building)]
                p=prediction_rows(test,qf,axis,tf)
                p['panel'],p['axis'],p['comparison']='current',axis,'QT_'+tname
                predictions.append(p)
    preds=pd.concat(predictions,ignore_index=True)
    for (panel,comparison),g in preds[preds.axis.isin(['B8L2','D10'])].groupby(['panel','comparison']):
        assert set(g.loc[g.axis.eq('B8L2'),'object_id'])==set(g.loc[g.axis.eq('D10'),'object_id']),(panel,comparison,'unpaired metric evaluation')
    keys=['object_id','worker_id','building_id','context_key','panel','axis','comparison','target','label',
        'continuous_prediction','class_prediction','QT_prediction','baseline_sqerr','continuous_sqerr','class_sqerr','QT_sqerr']
    csv('predictions.csv',preds.reindex(columns=keys));csv('prediction_performance.csv',performance(preds))
    csv('fold_profiles.csv',fits);csv('profiles.csv',fits[fits.fold.eq('full_descriptive')]);csv('coverage.csv',coverage)
    stability=[]
    for axis in ['B8L2','D10']:
        h=half_stability(current.assign(value=current[axis]),sorted(current.worker_id.unique()))
        h['axis']=axis;stability.append(h)
    csv('disjoint_halves.csv',pd.concat(stability,ignore_index=True).replace({'faster':'below_pool','slower':'above_pool'}))
    sensitivity=[]
    full=fits[fits.fold.eq('full_descriptive')]
    for pa,aa,pb,ab,label in [('previous949','B8L2','previous949','D10','metric_only_previous949'),
        ('current','B8L2','current','D10','metric_only_current'),('previous949','B8L2','previous_plus_new_batch','B8L2','batch_only_B8L2'),
        ('previous_plus_new_batch','B8L2','current','B8L2','old_routing_coverage_B8L2'),
        ('current','B8L2','no_floor_iou_fallback','B8L2','fallback_binding_sensitivity'),
        ('doorway','B8L2','doorway','D10','metric_only_doorway')]:
        a=full[(full.panel==pa)&(full.axis==aa)].set_index('worker_id')
        b=full[(full.panel==pb)&(full.axis==ab)].set_index('worker_id')
        d=a[['effect','label','supported']].join(b[['effect','label','supported']],lsuffix='_a',rsuffix='_b',how='outer').reset_index()
        d['comparison']=label;d['label_changed']=d.label_a.ne(d.label_b)
        d['rank_a']=d.effect_a.where(d.supported_a).rank(ascending=False);d['rank_b']=d.effect_b.where(d.supported_b).rank(ascending=False)
        sensitivity.append(d)
    csv('profile_sensitivity.csv',pd.concat(sensitivity,ignore_index=True))
    old_time_profile=pd.read_csv(PREVIOUS/'profiles.csv')
    time_sensitivity=[]
    for name in ['T_source','T_target']:
        a=old_time_profile[old_time_profile.panel.eq(name)][['worker_id','effect','label','supported']]
        b=full[full.panel.eq(name)][['worker_id','effect','label','supported']]
        d=a.merge(b,on='worker_id',suffixes=('_previous','_current'),validate='one_to_one')
        d['axis']=name;d['label_changed']=d.label_previous.ne(d.label_current);time_sensitivity.append(d)
    csv('time_profile_sensitivity.csv',pd.concat(time_sensitivity,ignore_index=True))
    conditional=[]
    for (panel,axis,building),p in preds[(preds.panel.str.startswith('difficulty_')|preds.panel.eq('doorway'))].groupby(['panel','axis','building_id']):
        d=panels[panel];test=d[d.object_id.isin(p.object_id)]
        fit=fits[(fits.panel=='current')&(fits.axis==axis)&(fits.fold==building)]
        g=prediction_rows(test,fit,axis)
        matched=p[['object_id','target','baseline_sqerr','continuous_sqerr']].merge(g[['object_id','target','continuous_sqerr']],
            on='object_id',suffixes=('_condition','_general'),validate='one_to_one')
        assert len(matched)==len(p) and np.allclose(matched.target_condition,matched.target_general)
        matched['panel'],matched['axis'],matched['building_id']=panel,axis,building
        conditional.append(matched)
    paired=pd.concat(conditional,ignore_index=True);csv('condition_general_matched_predictions.csv',paired)
    comparisons=[]
    for (panel,axis),d in paired.groupby(['panel','axis']):
        b=d.groupby('building_id')[['baseline_sqerr','continuous_sqerr_condition','continuous_sqerr_general']].mean()
        comparisons.append(dict(panel=panel,axis=axis,rows=len(d),buildings=len(b),
            condition_reduction=1-b.continuous_sqerr_condition.mean()/b.baseline_sqerr.mean(),
            general_reduction=1-b.continuous_sqerr_general.mean()/b.baseline_sqerr.mean(),
            condition_better_buildings=int((b.continuous_sqerr_condition<b.continuous_sqerr_general).sum())))
    csv('condition_general_comparison.csv',comparisons)
    return current,fits


def fixed_teams(current,fits,models,new):
    teams=pd.read_csv(PREVIOUS/'team_scores.csv')
    assert set(teams.image).isdisjoint(set(new.image_code)),'new annotations overlap frozen team images'
    eligible=teams.B8L2.notna()
    recomposed=add_scores(teams[eligible],models)
    teams['D10']=np.nan;teams.loc[eligible,'D10']=recomposed.D10
    csv('team_scores.csv',teams)
    pairs=pd.read_csv(PREVIOUS/'replacement_pairs.csv')
    scored=teams.set_index(['image','subset'])
    pairs['D10_change']=[scored.loc[(r.image,r.team_b),'D10']-scored.loc[(r.image,r.team_a),'D10'] for r in pairs.itertuples()]
    comparisons=[('previous949','B8L2'),('previous949','D10'),('previous_plus_new_batch','B8L2'),('current','B8L2'),('current','D10'),('T_source','T_source')]
    for panel,axis in comparisons:
        f=fits[(fits.panel==panel)&(fits.axis==axis)].set_index(['fold','worker_id'])
        labels=[]
        for r in pairs.itertuples():
            keys=[(r.building_id,r.removed),(r.building_id,r.added)]
            assert set(scored.loc[(r.image,r.team_a),'workers'].split('|'))-set(scored.loc[(r.image,r.team_b),'workers'].split('|'))=={r.removed}
            if all(k in f.index and f.loc[k].supported and f.loc[k].label!='unclassified' for k in keys):
                labels.append('same_class' if f.loc[keys[0]].label==f.loc[keys[1]].label else 'cross_class')
            else:labels.append('unclassified')
        pairs[panel+'_'+axis+'_swap']=labels
    for axis in ['B8L2','D10']:
        q=pairs['current_'+axis+'_swap'];t=pairs.T_source_T_source_swap
        pairs['QT_'+axis+'_swap']=np.where(q.eq('unclassified')|t.eq('unclassified'),'unclassified',
            np.where(q.eq('same_class')&t.eq('same_class'),'same_class','cross_class'))
    csv('replacement_pairs.csv',pairs)
    changes=[]
    for a,b,label in [('previous949_B8L2_swap','previous949_D10_swap','metric_only_previous949'),
        ('current_B8L2_swap','current_D10_swap','metric_only_current'),('previous949_B8L2_swap','previous_plus_new_batch_B8L2_swap','batch_only_B8L2'),
        ('previous_plus_new_batch_B8L2_swap','current_B8L2_swap','old_routing_coverage_B8L2')]:
        changes.append(dict(comparison=label,pairs=len(pairs),changed=int(pairs[a].ne(pairs[b]).sum()),
            primary_pairs=int(pairs.primary_attempt_eligible.sum()),changed_primary=int((pairs[a].ne(pairs[b])&pairs.primary_attempt_eligible).sum())))
    csv('replacement_label_sensitivity.csv',changes)
    entrants=pd.read_csv(PREVIOUS/'fixed_base_entrants.csv').drop(columns=['effect','B8L2','WQ','IoU3D100'])
    entrants=entrants.merge(teams[['image','subset','building_id','B8L2','D10']],on=['image','subset'],validate='many_to_one')
    summaries=[];base_comparisons=[]
    for axis in ['B8L2','D10']:
        f=fits[(fits.panel=='current')&(fits.axis==axis)].set_index(['fold','worker_id'])
        entrants[axis+'_effect']=[f.loc[(r.building_id,r.worker_id)].effect if (r.building_id,r.worker_id) in f.index and f.loc[(r.building_id,r.worker_id)].supported else np.nan for r in entrants.itertuples()]
        for (image,base),d in entrants.groupby(['image','base']):
            for outcome in ['B8L2','D10']:
                summaries.append(dict(axis=axis,outcome=outcome,image=image,base=base,primary=bool(d.primary.all()),attempts=len(d),
                    **summarize_entrants(d[axis+'_effect'],d[outcome])))
        for candidate,label in [(axis,'current_'+axis+'_swap'),('QT_'+axis,'QT_'+axis+'_swap')]:
            for (image,k,base),d in pairs.groupby(['image','k','base']):
                same=d[d[label]=='same_class'];cross=d[d[label]=='cross_class']
                if same.empty or cross.empty:continue
                base_comparisons.append(dict(axis=candidate,image=image,k=k,base=base,primary=bool(d.primary_attempt_eligible.all()),
                    same_pairs=len(same),cross_pairs=len(cross),floor_cross_minus_same=cross.floor_change.mean()-same.floor_change.mean(),
                    quality_cross_minus_same=cross[axis+'_change'].abs().mean()-same[axis+'_change'].abs().mean()))
    csv('fixed_base_entrants.csv',entrants);csv('fixed_base_associations.csv',summaries);csv('matched_base_comparisons.csv',base_comparisons)


def ledgers(bound,reviews,current):
    reasons=pd.read_csv(SOURCE/'record_reason_audit.csv')[['object_id','primary_reason']]
    bound=bound.merge(reasons,on='object_id',validate='one_to_one')
    cols=['object_id','worker_id','image_id','image_code','condition','building_id','new_batch','quality_use','quality_usable','is_doorway','is_oos',
        'scene_bucket','calculation_status','full_score_state','input_geometry_status','input_geometry_reasons','measurement_reasons',
        'primary_reason','quality_exclusion_reasons','admission_original_holdout','admission_role','profile_allowed',
        'source_active_time_seconds','target_matched_time_seconds','task_worker_active_seconds','source_scope_response','binding_status',
        'reference_id','reference_version','input_version','snapshot_version','B8L2_version','D10_version','B8L2','D10']
    ledger=bound[cols].copy();ledger['in_Q_training']=ledger.object_id.isin(current.object_id)
    csv('personnel_ledger.csv',ledger)
    old_ids=set(pd.read_csv(PREVIOUS/'current_quality_panel.csv').object_id)
    ledger['profile_membership_change']=np.where(ledger.object_id.isin(old_ids),'retained_previous949',
        np.where(ledger.in_Q_training,np.where(ledger.new_batch,'added_new_batch','added_old_routing_coverage'),'outside_Q_training'))
    csv('profile_membership_bridge.csv',ledger[['object_id','worker_id','image_code','condition','new_batch','quality_use',
        'quality_usable','admission_original_holdout','profile_membership_change','binding_status']])
    for name in ['worker_usage_summary.csv','worker_primary_reasons.csv','worker_reason_hits.csv','worker_scene_usage.csv','scene_usage.csv','member_changes.csv']:
        d=pd.read_csv(SOURCE/name)
        if name=='worker_usage_summary.csv':
            d=d.merge(ledger.groupby('worker_id').in_Q_training.sum().rename('Q_training_records').reset_index(),on='worker_id',validate='one_to_one')
            assert len(d)==27 and d.n_submissions.sum()==len(bound)
        csv(name,d)
    scope=pd.read_csv(ROOT/'research/workers/worker_four_axis_update_20261015/scope_records.csv')
    old=scope[['object_id','worker_id','image_id','building_id','worker_scope']].copy();old['source']='historical_scope_1013'
    new=reviews[['object_id','worker_id','image_id','building_id','source_scope_response']].copy()
    new['worker_scope']=new.source_scope_response.map(lambda x:x[0] if len(x)==1 else None)
    new['source']='adopted_batch98_scope';new=new.drop(columns=['source_scope_response'])
    responses=pd.concat([old,new],ignore_index=True)
    assert responses.object_id.is_unique
    responses['new_correctness_not_inferred']=True
    csv('scope_response_evidence.csv',responses)
    auxiliary=pd.read_csv(PREVIOUS/'four_axis_evidence.csv')
    csv('historical_auxiliary_evidence.csv',auxiliary)
    full=pd.read_csv(OUT/'profiles.csv');wide=full[full.panel.eq('current')&full.supported].pivot(index='worker_id',columns='axis',values='effect')
    for axis in ['T_source','T_target']:
        wide[axis]=full[full.panel.eq(axis)&full.supported].set_index('worker_id').effect
    auxnames=['S_rejection','S_clear_rejection','B_edit','B_legacy_gain']
    joined=wide.join(auxiliary.set_index('worker_id')[auxnames]);csv('four_axis_evidence.csv',joined.reset_index())
    correlations=[]
    for aux in auxnames:
        for axis in ['B8L2','D10','T_source','T_target']:
            d=joined[[aux,axis]].dropna()
            correlations.append(dict(auxiliary=aux,axis=axis,workers=len(d),spearman=d[aux].rank().corr(d[axis].rank())))
    csv('auxiliary_correlations.csv',correlations)
    save(OUT/'AUXILIARY_STATUS.json',dict(S='historical 1013 plus 70 raw choices retained; in/out is not target routing or correctness',
        B='no new semi annotations; historical modification and OSPA30 gain retained, not renamed B8L2/D10 gain'))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=read(SOURCE/'CROSS_MODULE_INPUTS.json');data=pd.read_csv(ROOT/manifest['full_inventory_with_metric_eligibility'])
    assert len(data)==manifest['counts']['inventory'] and data.quality_usable.sum()==manifest['counts']['quality_rows']
    assert data.object_id.is_unique and not data.loc[data.is_oos,'quality_usable'].any()
    assert data.loc[data.is_oos,['B8L2','D10']].isna().all().all()
    save(OUT/'INPUTS.json',dict(shared_manifest=manifest,shared_root=str(SOURCE.relative_to(ROOT)),
        frozen_previous='research/workers/worker_b8l2_20261016',
        admission='same-image historical holdouts inherited; new images in an entirely nonheld building enter exploratory development; no quality-selected admission',
        time='source task-worker duration only; new target time remains missing',parameters=read(SOURCE/'MODEL_PARAMETERS.json'),
        team_reference_and_use='worker_b8l2_20261016 frozen references and use; no automatic router-based team recertification',
        reference_snapshot='reference_catalog_snapshot.json'))
    save(OUT/'reference_catalog_snapshot.json',read(SOURCE/'reference_catalog.json'))
    csv('shared_input_snapshot.csv',data)
    bound,reviews=admit(data)
    with scoring_engine(SHARED16/'inputs/measurement_engine.zip',SHARED16/'inputs/working_models.py') as (_,models):
        current,fits=fit_panels(bound,models)
        fixed_teams(current,fits,models,data[data.new_batch])
    ledgers(bound,reviews,current)
    assert read(SOURCE/'CROSS_MODULE_INPUTS.json')==manifest,'shared manifest changed during run; refreeze before delivery'
    save(OUT/'CHECKS.json',dict(inventory=len(data),quality_usable=int(data.quality_usable.sum()),new_records=len(reviews),
        existing_worker_ids=sorted(reviews.worker_id.unique()),new_training_records=int((current.new_batch).sum()),
        new_quality_holdout_records=int((bound.new_batch&bound.quality_usable&bound.admission_original_holdout.eq(True)).sum()),
        Q_rows=len(current),Q_workers=current.worker_id.nunique(),Q_images=current.image_id.nunique(),
        new_source_seconds=float(reviews.task_worker_active_seconds.sum()),new_target_time_rows=int(data.loc[data.new_batch,'target_matched_time_seconds'].notna().sum()),
        old_snapshots_changed=False,shared_binding_changed=False,formula_tuned=False,fusion_rerun=False,
        primary_metric='B8L2',sensitivity_metric='D10_not_A10',new_pending_target_records=int((data.new_batch&data.calculation_status.eq('pending_target')).sum())))
    save(OUT/'FIELD_CONTRACT.json',dict(version='worker_b8l2_d10_20261017_v1',
        tables={p.name:dict(rows=len(pd.read_csv(p)),columns=pd.read_csv(p,nrows=0).columns.tolist()) for p in OUT.glob('*.csv')},
        paired_comparison='B8L2/D10 identical records references folds; D10 changes direction scale 8 to 10 only',
        inference='buildings/images, not overlapping teams as independent repeats; class signs descriptive',
        missing='missing never zero; OOS diagnostic not quality; source duration not selected-target duration'))


if __name__=='__main__':main()
