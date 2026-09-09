"""Manual参考执行画像作粗依据，Semi修改行为是否提供额外可复现信息。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.worker_reference_feasibility_20260909 import (
    ROOT, BASE, OUT as PREVIOUS, profiles, ordinal_groups, pool_responses,
    reference_metrics, jsonlines, predict_peers, POINTS,
)
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import unit_points,point_distances

OUT=ROOT/'analysis_results/semi_subtype_exploration_20260909_v1'


def semi_features(initial,final,reference):
    edit=point_distances(unit_points(initial),unit_points(final))
    row={f'edit_{m}':edit[m] for m in ['ospa30','ospa60']}
    for m in ['ospa30','ospa60']:
        row[f'gain_{m}']=None;row[f'final_{m}']=None;row[f'initial_{m}']=None
    if reference is not None:
        before=reference_metrics(initial,reference);after=reference_metrics(final,reference)
        for m in ['ospa30','ospa60']:
            row.update({f'gain_{m}':before[m]-after[m],f'final_{m}':after[m],f'initial_{m}':before[m]})
    row['net_point_change']=len(final)-len(initial)
    return row


def make_hierarchy(manual,semi,forced_fine=None):
    if manual.component.nunique()!=1 or semi.component.nunique()!=1:
        raise ValueError('disconnected_worker_effects')
    coarse=ordinal_groups(manual,2,'quantile')
    p=coarse[['worker_id','effect','label']].rename(columns={'effect':'manual_effect','label':'coarse_label'}).merge(
        semi[['worker_id','effect']].rename(columns={'effect':'semi_effect'}),on='worker_id',validate='one_to_one')
    x=np.column_stack([np.ones(len(p)),p.manual_effect])
    beta=np.linalg.lstsq(x,p.semi_effect,rcond=None)[0]
    p['manual_prediction']=x@beta;p['semi_residual']=p.semi_effect-p.manual_prediction
    quadratic=np.column_stack([x,p.manual_effect**2])
    p['manual_quadratic_prediction']=quadratic@np.linalg.lstsq(quadratic,p.semi_effect,rcond=None)[0]
    p['manual_plus_coarse']=p.manual_prediction+p.groupby('coarse_label').semi_residual.transform('mean')
    p['fine_label']=p.coarse_label.map(lambda v:f'{v}.0');p['split_status']='insufficient_members'
    for coarse_id,g in p.groupby('coarse_label'):
        if len(g)<4:continue
        candidate=ordinal_groups(g.assign(effect=g.semi_residual,component='0'),2,'ward')
        allowed=candidate.label.nunique()==2 and candidate.groupby('label').size().min()>=2
        p.loc[g.index,'split_status']='split' if allowed else 'singleton_or_no_separation_not_split'
        if allowed:p.loc[g.index,'fine_label']=[f'{coarse_id}.{v}' for v in candidate.label]
    if forced_fine is not None:
        p['fine_label']=p.worker_id.map(forced_fine)
        assert p.fine_label.notna().all()
        assert (p.fine_label.str.split('.').str[0].astype(int)==p.coarse_label).all()
        p['split_status']='edit_training_labels_reused_for_quality'
    p['layer_value']=p.manual_prediction+p.groupby('fine_label').semi_residual.transform('mean')
    p['coarse_value']=p.groupby('coarse_label').semi_effect.transform('mean')
    p['fine_value']=p.groupby('fine_label').semi_effect.transform('mean')
    p['effect']=p.semi_effect;p['label']=p.fine_label;p['component']='0';p['fit_status']='usable'
    p['manual_calibration_intercept']=beta[0];p['manual_calibration_slope']=beta[1]
    return p


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    measurements=pd.read_csv(PREVIOUS/'response_measurements.csv.gz',dtype=str,keep_default_na=False)
    manual=pool_responses(measurements[(measurements.raw_condition=='manual')&(measurements.measurement_status=='computable')])
    index=measurements.set_index('canonical_annotation_id',drop=False)
    proposals=pd.read_csv(BASE/'facts/proposal_response.csv.gz',dtype=str,keep_default_na=False)
    facts=pd.read_csv(BASE/'facts/proposal_fact.csv.gz',dtype=str,keep_default_na=False)
    assert proposals.canonical_annotation_id.is_unique
    assert set(proposals.canonical_annotation_id)==set(measurements.loc[measurements.raw_condition=='semi','canonical_annotation_id'])
    proposals=proposals.merge(facts[['proposal_id','initialization_source_kind']],on='proposal_id',validate='many_to_one')
    refs={r['image_id']:r for r in jsonlines(PREVIOUS/'reference_ledger.jsonl')}
    trace=pd.read_csv(ROOT/'analysis_results/annotation_research_prework_20260905_v2/evidence/initialization_trace.csv',dtype=str,keep_default_na=False).set_index('canonical_annotation_id')
    assert trace.index.is_unique and set(trace.index)==set(proposals.canonical_annotation_id)
    point_rows=jsonlines(POINTS)
    raw={r['canonical_annotation_id']:r['raw_points_1024x512'] for r in point_rows}
    rows=[]
    for r in proposals.to_dict('records'):
        a=index.loc[r['canonical_annotation_id']]
        for key in ['image_id','worker_id','building_id','stage','raw_condition']:
            assert r[key]==a[key]
        initial=json.loads(r['initial_points_json']);final=json.loads(r['final_points_json'])
        t=trace.loc[r['canonical_annotation_id']]
        assert t.initial_import_match_status=='all_matching' and t.initial_runtime_preview_match.lower()=='true'
        assert np.shape(final)==np.shape(raw[r['canonical_annotation_id']]) and np.allclose(final,raw[r['canonical_annotation_id']],atol=1e-7,rtol=0)
        ref=refs[r['image_id']]
        row={k:a[k] for k in ['canonical_annotation_id','image_id','building_id','worker_id','current20_member','stage']}
        row.update(context_key=r['proposal_id'],legacy_initialization_kind=r['initialization_source_kind'],
            source_group='recovered_c1_import' if r['initialization_source_kind']=='missing_required_initialization' else r['initialization_source_kind'],
            reference_basis=ref['basis'],reference_hold=ref['hold_reason'],
            initialization_evidence_status='import_and_runtime_preview_matched',
            **semi_features(initial,final,ref['points_1024x512'] if ref['score_allowed'] else None))
        rows.append(row)
    semi=pd.DataFrame(rows)
    assert not semi.duplicated(['context_key','worker_id']).any()
    semi.to_csv(OUT/'semi_response_features.csv',index=False)
    results=[];prediction_rows=[];members=[];full_members=[]
    for cohort,people in [('all26',set(manual.worker_id)),('current20',set(manual.loc[manual.current20_member.str.lower()=='true','worker_id']))]:
        man=manual[manual.worker_id.isin(people)];s=semi[semi.worker_id.isin(people)]
        for pool,data in [('all_initializations',s),('without_synthetic',s[s.source_group!='trap_synthetic_disjoint_source'])]:
            for metric in ['ospa30','ospa60']:
                for outcome in ['edit','final','final_via_edit_labels']:
                    field='edit' if outcome=='edit' else 'final'
                    d=data[data[f'{field}_{metric}'].notna()].assign(value=lambda x:x[f'{field}_{metric}'])
                    meta=dict(cohort=cohort,pool=pool,metric=metric,outcome=outcome)
                    manual_full=profiles(man.assign(value=man[metric]))
                    forced=None
                    if outcome=='final_via_edit_labels':
                        edit_fit=make_hierarchy(manual_full,profiles(data.assign(value=data[f'edit_{metric}'])))
                        forced=dict(zip(edit_fit.worker_id,edit_fit.fine_label))
                    full=make_hierarchy(manual_full,profiles(d),forced)
                    full_members.append(full.assign(**meta))
                    for building,test in d.groupby('building_id'):
                        m=man[man.building_id!=building].assign(value=lambda x:x[metric])
                        train=d[d.building_id!=building]
                        manual_fit=profiles(m);forced=None
                        if outcome=='final_via_edit_labels':
                            ed=data[data.building_id!=building].assign(value=lambda x:x[f'edit_{metric}'])
                            edit_fit=make_hierarchy(manual_fit,profiles(ed))
                            forced=dict(zip(edit_fit.worker_id,edit_fit.fine_label))
                        p=make_hierarchy(manual_fit,profiles(train),forced)
                        members.append(p.assign(**meta,heldout_building=building,
                            manual_training_buildings=json.dumps(sorted(m.building_id.unique())),
                            semi_training_buildings=json.dumps(sorted(train.building_id.unique()))))
                        names=['manual_prediction','manual_quadratic_prediction','manual_plus_coarse','coarse_value','fine_value']
                        pred=predict_peers(test,p).merge(p[['worker_id',*names]],on='worker_id',validate='many_to_one')
                        for name in names:
                            pred[name+'_centered']=pred[name]-pred.groupby('context_key')[name].transform('mean')
                            pred[name+'_sqerr']=(pred.target-pred[name+'_centered'])**2
                        prediction_rows.append(pred.assign(**meta))
    predictions=pd.concat(prediction_rows,ignore_index=True)
    for key,d in predictions.groupby(['cohort','pool','metric','outcome']):
        meta=dict(zip(['cohort','pool','metric','outcome'],key))
        cols=['baseline_sqerr','continuous_sqerr','layer_sqerr','manual_prediction_sqerr','manual_quadratic_prediction_sqerr',
              'manual_plus_coarse_sqerr','coarse_value_sqerr','fine_value_sqerr']
        b=d.groupby('building_id')[cols].mean()
        row=meta|dict(rows=len(d),images=d.image_id.nunique(),buildings=len(b),workers=d.worker_id.nunique())
        for name in cols[1:]:
            row[name+'_building_gain']=1-b[name].mean()/b.baseline_sqerr.mean()
        row['manual_plus_fine_vs_manual_building_gain']=1-b.layer_sqerr.mean()/b.manual_prediction_sqerr.mean()
        row['manual_plus_fine_vs_quadratic_building_gain']=1-b.layer_sqerr.mean()/b.manual_quadratic_prediction_sqerr.mean()
        row['manual_plus_fine_vs_manual_coarse_building_gain']=1-b.layer_sqerr.mean()/b.manual_plus_coarse_sqerr.mean()
        row['fine_vs_coarse_building_gain']=1-b.fine_value_sqerr.mean()/b.coarse_value_sqerr.mean()
        results.append(row)
    pd.DataFrame(results).to_csv(OUT/'validation_summary.csv',index=False)
    predictions.to_csv(OUT/'heldout_predictions.csv.gz',index=False)
    folds=pd.concat(members,ignore_index=True);folds.to_csv(OUT/'fold_members.csv',index=False)
    full=pd.concat(full_members,ignore_index=True);full.to_csv(OUT/'full_members.csv',index=False)
    keys=['cohort','pool','metric','outcome','worker_id']
    comparisons=folds.merge(full[keys+['coarse_label','fine_label']].rename(columns={
        'coarse_label':'full_coarse','fine_label':'full_fine'}),on=keys,validate='many_to_one')
    comparisons['same_coarse']=comparisons.coarse_label==comparisons.full_coarse
    comparisons['same_fine']=comparisons.fine_label==comparisons.full_fine
    comparisons.groupby(keys).agg(coarse_agreement=('same_coarse','mean'),fine_agreement=('same_fine','mean'),
        folds=('heldout_building','size'),fine_label_variants=('fine_label','nunique')).reset_index().to_csv(OUT/'membership_stability.csv',index=False)
    point_index=pd.DataFrame(point_rows)
    point_index=point_index[point_index.calculation_included][['image_id','worker_id']].drop_duplicates()
    support=[]
    for key,g in full[full.outcome=='edit'].groupby(['cohort','pool','metric','fine_label']):
        n=point_index[point_index.worker_id.isin(g.worker_id)].groupby('image_id').worker_id.nunique()
        support.append(dict(zip(['cohort','pool','metric','fine_label'],key))|dict(workers=len(g),
            theoretical_history_with_two_validation=max(0,len(g)-2),images_any=len(n),
            images_four_people=int((n>=4).sum()),images_five_people=int((n>=5).sum()),
            images_six_people=int((n>=6).sum())))
    pd.DataFrame(support).to_csv(OUT/'fine_group_convergence_support.csv',index=False)
    qa=dict(manual_responses=len(manual),semi_responses=len(semi),semi_images=semi.image_id.nunique(),
        reference_available=int(semi.final_ospa30.notna().sum()),source_counts=semi.source_group.value_counts().to_dict(),
        candidates_are_not_final_types=True,reference_gain_is_not_independent_axis=True,
        coarse_split='manual_effect_quantile2_exploratory_not_natural_clusters',
        fine_split='semi_residual_after_linear_manual_effect_within_coarse_Ward2_min2_members',
        initial_order='substrate_may_sort_x; independent_import_audit_for_this_batch_matched_original_sequences',
        outcome_separation='edit/final independently trained; final_via_edit_labels reuses training edit groups to predict final quality')
    (OUT/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False));print(pd.DataFrame(results).to_string(index=False))


if __name__=='__main__':run()
