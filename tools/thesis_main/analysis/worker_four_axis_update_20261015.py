"""931-row scope sensitivity and explicit Q/T/S/B evidence; no source/eligibility edits."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from . import worker_wq_integration_20261015 as wq
from .worker_classification_progress_20261014 import half_stability
from .prescreen_scope_adjudication import _worker_scope

ROOT=wq.ROOT
OUT=ROOT/'research/workers/worker_four_axis_update_20261015'
PREV=ROOT/'research/workers/worker_wq_integration_20261015'
HISTORY=ROOT/'analysis_results/worker_four_block_exploration_20260910_v1'


def scope_target(scene):
    return 'in_scope' if scene=='clear' else None


def apply_scope_hold(panel,bindings):
    linked=panel.merge(bindings[['record_id','new_scope_binding_pending','use_panel']],on='record_id',validate='one_to_one')
    assert len(linked)==len(panel)
    return linked[~linked.new_scope_binding_pending].copy(),linked[linked.new_scope_binding_pending].copy()


def sensitivity(panel):
    previous=pd.read_csv(PREV/'profiles.csv');oldfold=pd.read_csv(PREV/'fold_profiles.csv')
    fits,performance=wq.profiles(panel,oldfold.fold[oldfold.fold!='full_descriptive'].unique())
    current=pd.read_csv(OUT/'profiles.csv')
    comparison=previous.merge(current,on=['axis','worker_id'],suffixes=('_959','_931'),validate='one_to_one')
    comparison['label_changed']=comparison.label_959.ne(comparison.label_931)
    comparison['effect_change']=comparison.effect_931-comparison.effect_959
    wq.table('profile_sensitivity.csv',comparison)
    edge=pd.read_csv(PREV/'replacement_pairs.csv')
    image_building=edge.set_index('image').building_id.to_dict()
    for axis in ['WQ','IoU3D100','height_vs_floor']:
        lookup=fits[fits.axis.eq(axis)].set_index(['fold','worker_id']).to_dict('index')
        categories=[];changes=[]
        for r in edge.itertuples():
            a=lookup.get((r.building_id,r.removed));b=lookup.get((r.building_id,r.added))
            valid=a and b and a['supported'] and b['supported'] and a['effect']!=0 and b['effect']!=0
            categories.append('same_class' if valid and np.sign(a['effect'])==np.sign(b['effect']) else 'cross_class' if valid else 'unclassified')
            changes.append(b['effect']-a['effect'] if valid else np.nan)
        edge[axis+'_swap']=categories;edge[axis+'_effect_change']=changes
    wq.table('replacement_pairs.csv',edge);wq.summarize_replacements(edge)
    entrants=pd.read_csv(PREV/'fixed_base_entrants.csv');associations=[]
    for axis in ['WQ','IoU3D100','height_vs_floor']:
        lookup=fits[fits.axis.eq(axis)].set_index(['fold','worker_id']).effect
        entrants[axis+'_effect']=[lookup.get((image_building[r.image],r.worker_id),np.nan) for r in entrants.itertuples()]
    for (image,base),g in entrants.groupby(['image','base']):
        for axis in ['WQ','IoU3D100','height_vs_floor','time']:
            for outcome in ['WQ','IoU3D100','raw_pair_distance']:
                associations.append(dict(image=image,base=base,axis=axis,outcome=outcome,
                    original_holdout=bool(g.original_holdout.any()),eligible_entrants=len(g),
                    **wq.summarize_entrants(g[axis+'_effect'],g[outcome])))
    wq.table('fixed_base_entrants.csv',entrants);wq.table('fixed_base_associations.csv',associations)
    oldedge=pd.read_csv(PREV/'replacement_pairs.csv')
    return fits,dict(performance=performance,full_label_changes=comparison[comparison.label_changed].groupby('axis').worker_id.apply(list).to_dict(),
        replacement_class_changes={axis:int((oldedge[axis+'_swap']!=edge[axis+'_swap']).sum()) for axis in ['WQ','IoU3D100','height_vs_floor']})


def evidence():
    bundle=load_current_bundle();objects={r['object_id']:r for r in bundle['data']['objects']}
    inventory=pd.read_csv(wq.OLD/'source_inventory.csv')
    for r in inventory.itertuples():
        obj=objects[r.object_id]
        assert (obj['worker_id'],obj['image_id'],obj['condition'])==(r.worker_id,r.image_id,r.condition)
    scenes=pd.DataFrame(wq.read(ROOT/'analysis_results/difficulty_scope_preferred_20261011/current_259.json')['records'])
    scope=pd.read_csv(HISTORY/'scope_responses.csv')
    scope['project_id']=scope.raw_export.str.extract(r'project-(\d+)-').astype(int)
    scope['historical_worker_id']=scope.worker_id.map(lambda x:f'W{int(x):03d}')
    raw_annotations={}
    for path in scope.raw_export.unique():
        annotations=[a for task in wq.read(ROOT/path) for a in task.get('annotations',[])]
        raw_annotations[path]={a['id']:a for a in annotations}
        assert len(raw_annotations[path])==len(annotations)
    geometry_present=[]
    for r in scope.itertuples():
        annotation=raw_annotations[r.raw_export][r.raw_annotation_id]
        raw,normalized,present=_worker_scope(annotation)
        assert raw==r.raw_scope and normalized==r.worker_scope
        assert int(annotation['completed_by'])==int(r.worker_id)
        geometry_present.append(present)
    scope['original_geometry_present']=geometry_present
    source=inventory[inventory.scope_historical_bound].merge(scope,on=['project_id','raw_annotation_id'],suffixes=('','_old'),validate='one_to_one')
    assert len(source)==1013 and source.worker_id.eq(source.historical_worker_id).all() and source.image_id.eq(source.image_id_old).all()
    source=source.merge(scenes[['image_id','scene','oos_subtype','doorway_status']],on='image_id',validate='many_to_one')
    assert not source.duplicated(['worker_id','image_id']).any()
    source['current_scope_target']=source.scene.map(scope_target)
    source['recorded_rejection']=source.worker_scope.map({'in_scope':0.,'oos':1.})
    source['current_clear_rejection']=source.recorded_rejection.where(source.current_scope_target.notna())
    source['historical_disagreement']=source.worker_scope.ne(source.final_scope).where(source.worker_scope.isin(['in_scope','oos'])&source.final_scope.isin(['in_scope','oos']))
    source['current_correctness_unknown']=source.current_scope_target.isna()
    wq.table('scope_records.csv',source)
    scope_summary=source.groupby(['scene','oos_subtype','doorway_status'],dropna=False).agg(records=('record_id','size'),images=('image_id','nunique'),
        buildings=('building_id','nunique'),workers=('worker_id','nunique'),reject_n=('recorded_rejection','sum'),
        reject_fraction=('recorded_rejection','mean'),historical_disagreements=('historical_disagreement','sum')).reset_index()
    wq.table('scope_scene_coverage.csv',scope_summary)
    wq.table('scope_worker_scene.csv',source.groupby(['worker_id','scene']).agg(records=('record_id','size'),
        images=('image_id','nunique'),reject_fraction=('recorded_rejection','mean')).reset_index())
    wq.table('scope_image_responses.csv',source.groupby(['image_code','scene','building_id']).agg(
        records=('record_id','size'),reject_n=('recorded_rejection','sum'),reject_fraction=('recorded_rejection','mean'),
        historical_final_values=('final_scope',lambda s:'|'.join(sorted(set(s))))).reset_index())
    semi=pd.read_csv(HISTORY/'semi.csv.gz');semi['historical_worker_id']=semi.worker_id.map(lambda x:f'W{int(x):03d}')
    b=inventory[inventory.condition.eq('semi')].merge(semi,left_on=['project_id','runtime_task_id','worker_id'],
        right_on=['project_id','runtime_task_id','historical_worker_id'],suffixes=('','_old'),validate='one_to_one')
    assert len(b)==574 and b.image_id.eq(b.image_id_old).all()
    b['behavior_context']=b.source_group+'|'+b.context_key
    b['trap_behavior_diagnostic']=b.source_cohort.eq('semi_trap_separate')&~b.original_holdout
    b['secondary_Q_use']=b.current_role.eq('semi_secondary_candidate')
    wq.table('semi_records.csv',b)
    wq.table('semi_coverage.csv',b.groupby(['source_cohort','current_role','original_holdout']).agg(records=('record_id','size'),
        workers=('worker_id','nunique'),images=('image_id','nunique'),buildings=('building_id','nunique'),
        median_edit=('edit_ospa30','median'),median_legacy_gain=('gain_ospa30','median')).reset_index())
    axes={}
    for name,column,selector in [('S_rejection','recorded_rejection',~source.original_holdout),
            ('S_clear_rejection','current_clear_rejection',~source.original_holdout&source.scene.eq('clear'))]:
        x=source[selector].copy();x['value']=x[column];x['context_key']='scope|'+x.image_id
        axes[name]=x[['record_id','worker_id','building_id','context_key','value']].dropna(subset=['value'])
    for name,column in [('B_edit','edit_ospa30'),('B_legacy_gain','gain_ospa30')]:
        x=b[b.trap_behavior_diagnostic].copy();x['value']=x[column];x['context_key']=x.behavior_context
        axes[name]=x[['record_id','worker_id','building_id','context_key','value']].dropna(subset=['value'])
    return axes,source,b,scenes


def auxiliary_profiles(axes,qualityfits,panel):
    profiles=[];predictions=[];half=[];folds=[];coverage=[]
    targets=sorted(set(panel.building_id)|{b for d in axes.values() for b in d.building_id})
    for axis,data in axes.items():
        coverage.append(dict(axis=axis,rows=len(data),workers=data.worker_id.nunique(),images_or_contexts=data.context_key.nunique(),buildings=data.building_id.nunique()))
        data=data.assign(**{axis:data.value})
        for target in [None]+targets:
            p=wq.fit_axis(data,axis,target);folds.append(p)
            if target is None:profiles.append(p);continue
            test=data[data.building_id.eq(target)].merge(p[p.supported][['worker_id','effect']],on='worker_id')
            test=test[test.groupby('context_key').worker_id.transform('size').ge(2)].copy()
            if test.empty:continue
            test['target']=test.value-test.groupby('context_key').value.transform('mean')
            test['prediction']=test.effect-test.groupby('context_key').effect.transform('mean')
            test['baseline_sqerr']=test.target**2;test['sqerr']=(test.target-test.prediction)**2;test['axis']=axis
            predictions.append(test[['record_id','worker_id','building_id','context_key','axis','target','prediction','baseline_sqerr','sqerr']])
        h=half_stability(data,sorted(data.worker_id.unique()));h['axis']=axis;half.append(h)
    p=pd.concat(profiles);f=pd.concat(folds);pred=pd.concat(predictions);h=pd.concat(half)
    wq.table('auxiliary_profiles.csv',p);wq.table('auxiliary_fold_profiles.csv',f);wq.table('auxiliary_predictions.csv',pred)
    wq.table('auxiliary_half_stability.csv',h);wq.table('auxiliary_coverage.csv',coverage)
    performance=[]
    for axis,g in pred.groupby('axis'):
        by=g.groupby('building_id')[['baseline_sqerr','sqerr']].mean()
        performance.append(dict(axis=axis,evaluated_rows=len(g),buildings=len(by),
            building_equal_reduction=1-by.sqerr.mean()/by.baseline_sqerr.mean(),pooled_reduction=1-g.sqerr.sum()/g.baseline_sqerr.sum(),
            improved_buildings=int((by.sqerr<by.baseline_sqerr).sum())))
    wq.table('auxiliary_performance.csv',performance)
    wide=p[p.supported].pivot(index='worker_id',columns='axis',values='effect')
    q=qualityfits[(qualityfits.axis=='WQ')&(qualityfits.fold=='full_descriptive')].set_index('worker_id').effect
    t=pd.read_csv(wq.OLD/'time_profiles.csv').set_index('worker_id');wide['Q']=q;wide['T']=t.effect.where(t.supported)
    corr=[]
    for axis in axes:
        for control in ['Q','T']:
            g=wide[[axis,control]].dropna();corr.append(dict(axis=axis,control=control,workers=len(g),spearman=g[axis].rank().corr(g[control].rank())))
    wq.table('four_axis_profiles.csv',wide.reset_index());wq.table('auxiliary_QT_associations.csv',corr)
    # Diagnose target-building Q residual association; this is not a new fitted prediction model.
    qpred=pd.read_csv(OUT/'predictions.csv');qpred=qpred[qpred.axis=='WQ'].copy()
    qpred['residual']=qpred.target-qpred.continuous_prediction
    time=pd.read_csv(wq.OLD/'time_assignments.csv')
    residuals=[]
    for (axis,building),g in f[f.fold!='full_descriptive'].groupby(['axis','fold']):
        test=qpred[qpred.building_id.eq(building)].merge(g[g.supported][['worker_id','effect']],on='worker_id')
        test=test.merge(time[(time.fold==building)&time.supported][['worker_id','effect']].rename(columns={'effect':'time_effect'}),on='worker_id')
        test=test[test.groupby('context_key').worker_id.transform('size').ge(2)].copy()
        if len(test)<6:continue
        for col in ['residual','effect','time_effect']:
            test[col]-=test.groupby('context_key')[col].transform('mean')
        design=np.column_stack([np.ones(len(test)),test.time_effect])
        a=test.residual-design@np.linalg.lstsq(design,test.residual,rcond=None)[0]
        b=test.effect-design@np.linalg.lstsq(design,test.effect,rcond=None)[0]
        residuals.append(dict(axis=axis,building_id=building,rows=len(test),workers=test.worker_id.nunique(),
            Q_residual_time_adjusted_correlation=np.corrcoef(a,b)[0,1] if np.std(a)>1e-12 and np.std(b)>1e-12 else None))
    wq.table('auxiliary_target_residual_associations.csv',residuals)
    return performance


def main():
    OUT.mkdir(parents=True,exist_ok=True);wq.OUT=OUT
    binding=pd.read_csv(ROOT/'research/difficulty/difficulty_target_integration_20261015/quality_bindings_1145.csv')
    panel,held=apply_scope_hold(pd.read_csv(PREV/'quality_panel.csv'),binding)
    assert len(panel)==931 and len(held)==28
    wq.table('quality_panel_931.csv',panel);wq.table('held_new_scope_28.csv',held)
    fits,sens=sensitivity(panel)
    axes,scope,semi,scenes=evidence();performance=auxiliary_profiles(axes,fits,panel)
    # Conditional annotation performance only for ordinary same-target records, not unmarkable/OOS scores.
    ordinary=panel[panel.use_panel.eq('ordinary_same_target_conditional')].merge(scenes[['image_id','current_class','scene']],on='image_id',validate='many_to_one')
    pred=pd.read_csv(OUT/'predictions.csv');pred=pred[pred.axis=='WQ']
    conditional=ordinary.merge(pred[['record_id','target','continuous_prediction']],on='record_id')
    conditional['loo_Q_residual']=conditional.target-conditional.continuous_prediction
    wq.table('conditional_quality_records.csv',conditional)
    wq.table('conditional_quality_profiles.csv',conditional.groupby(['worker_id','current_class']).agg(records=('record_id','size'),
        images=('image_id','nunique'),buildings=('building_id','nunique'),mean_loo_Q_residual=('loo_Q_residual','mean')).reset_index())
    wq.save('SUMMARY.json',dict(old_rows=959,current_rows=931,held_by_image=held.image_code.value_counts().to_dict(),
        quality_sensitivity=sens,scope_records=len(scope),scope_raw_responses_verified=len(scope),
        scope_geometry_present=int(scope.original_geometry_present.sum()),scope_current_unknown=int(scope.current_correctness_unknown.sum()),
        semi_records=len(semi),auxiliary_performance=performance,conditional_quality_rows=len(conditional),
        current_scope_target='clear ordinary acceptance only; other latest categories do not define binary correctness',
        B_interpretation='current-confirmed trap diagnostic on frozen historical OSPA30; not current WQ benefit',
        fusion_recomputed=False,old_results_preserved=True,formal_eligibility_changed=False))
    wq.save('FIELD_CONTRACT.json',dict(schema='worker_four_axis_update_20261015_v1',
        units={'Q':'WQ-LS08-20261014 points','T':'log1p seconds','S':'recorded response 0/1; not unrecorded skip','B':'historical OSPA30 edit or initial-minus-final reference error'},
        context='image/reference/condition for Q; image for S; source-group + initialization context for B',
        unknown='NA; unknown judgments are never filled as correct or incorrect',
        validation='all profiles and calibration exclude target building; halves use disjoint buildings; paired teams remain dependent',
        residual_association='descriptive Q leave-building residual correlation with auxiliary effect, within-target-task centered and time-effect residualized; not incremental prediction gain',
        tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob('*.csv')}))
    print((OUT/'SUMMARY.json').read_text(encoding='utf8'))


if __name__=='__main__':main()
