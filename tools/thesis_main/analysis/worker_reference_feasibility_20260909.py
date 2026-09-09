"""有复核优先、其余暂信GT：无序参考点偏差与跨building工人效应探索。"""
from pathlib import Path
from urllib.parse import urlparse
import gzip
import json
import re
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from tools.thesis_main.analysis.audit_building_convergence_20260908 import ordered_points
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import unit_points, point_distances
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import sufficient, solve, informative, predict_peers
from tools.thesis_main.analysis.materialize_annotation_research_prework_statistics_20260905 import worker_task_components

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
OUT = ROOT / 'analysis_results/worker_reference_feasibility_20260909_v1'
SEMANTICS = ROOT / 'analysis_results/uncertainty_decision_ready_20260908_v1/semantics/case_evidence.jsonl'
CORRECTIONS = ROOT / 'docs/thesis_main/TEST_MANUAL_GT_CORRECTIONS_20260823.md'
GT = ROOT / 'export_label/groudTruth.json'
POINTS = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/calculation_view.jsonl.gz'
METRICS = ['ospa30', 'ospa60', 'matched_angle', 'absolute_count_rate', 'missing_count_rate', 'extra_count_rate']
# 手工阅读评语后的分析处置，不是新增人工裁决。保留逐字原文以供检查。
# V07有已确认修订参考，原问卷“全有疑问”针对旧展示；采用修订坐标。
REVIEW_HOLD = {
    'V01': 'cross_view_reference_unresolved', 'V02': 'reviewer_oos',
    'V06': 'scope_unresolved', 'V09': 'gt_extended_scope_not_unique_rule_reference',
    'V10': 'remembered_gt_revision_not_identified', 'V11': 'scope_unresolved',
    'V12': 'boundary_choice_uncertain', 'V15': 'stitching_and_boundary_unresolved',
    'V19': 'gt_questioned_no_replacement', 'V20': 'gt_missing_protrusion_no_replacement',
    'V21': 'extended_scope_not_unique_rule_reference', 'V25': 'nonplanar_ceiling_uncertain',
    'V27': 'layered_ceiling_boundary_unresolved', 'V28': 'multiple_scope_choices',
    'V29': 'multiple_scope_choices', 'V31': 'multiple_scope_choices_even_with_corrected_gt',
    'V32': 'scope_comparison_unresolved', 'V33': 'cross_view_scope_unresolved',
    'V34': 'extended_scope_may_exceed_current_image', 'V35': 'gt_extended_scope_not_unique_rule_reference',
    'V38': 'gt_inaccurate', 'V40': 'boundary_and_gt_uncertain',
    'V44': 'review_prefers_enclosed_over_gt', 'V46': 'gt_missing_protrusion',
}
OLD_REVIEW_HOLD = {
    'VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d': 'local_gt_issue',
    'jh4fc5c5qoQ_77e6cfabf32d46fc9398ce824843adaa': 'gt_expands_across_door',
    'jh4fc5c5qoQ_b000c5baa76b454caa1c58c9aac585f6': 'gt_and_boundary_uncertain',
    'pRbA3pwrgk9_0350fc96e88c4a52886d4eb50b2d52c6': 'reviewer_oos',
    'pRbA3pwrgk9_8b07a4b08cf447abb246769d8dce8494': 'reviewer_oos',
    'pRbA3pwrgk9_bc9ae89832854c19a69741f97291efad': 'reviewer_oos',
}


def jsonlines(path):
    with (gzip.open(path, 'rt', encoding='utf-8') if path.suffix == '.gz' else path.open(encoding='utf-8')) as f:
        return [json.loads(line) for line in f if line.strip()]


def choose_reference(gt, corrected, hold):
    chosen = corrected or gt
    return dict(chosen or {}, basis='reviewed_reference' if corrected else 'gt_assumed_correct',
                score_allowed=chosen is not None and not hold,
                hold_reason=hold or ('' if chosen else 'missing_reference'))


def reference_metrics(points, reference):
    a, b = unit_points(points), unit_points(reference)
    result = point_distances(a, b)
    angle = np.degrees(np.arctan2(np.linalg.norm(np.cross(a[:, None], b[None, :]), axis=2), np.clip(a@b.T, -1, 1)))
    i, j = linear_sum_assignment(angle)
    result.update(matched_angle=float(angle[i, j].mean()),
                  absolute_count_rate=abs(len(a)-len(b))/len(b),
                  missing_count_rate=max(len(b)-len(a), 0)/len(b),
                  extra_count_rate=max(len(a)-len(b), 0)/len(b))
    return result


def profiles(data):
    data = informative(data)
    rows = []
    for number, component in enumerate(worker_task_components(data.assign(base_task_id=data.context_key).to_dict('records'))):
        d = data[data.worker_id.isin(component['workers'])]
        s = sufficient(d)
        effect, status, _ = solve(s, np.ones(len(s['buildings'])))
        for i, worker in enumerate(s['workers']):
            z = d[d.worker_id == worker]
            rows.append(dict(worker_id=worker, effect=effect[i] if effect is not None else np.nan,
                             fit_status=status, component=str(number), layer_value=0., label='not_classified',
                             training_rows=len(z), training_images=z.image_id.nunique() if 'image_id' in z else z.context_key.nunique(),
                             training_buildings=z.building_id.nunique()))
    return pd.DataFrame(rows, columns=['worker_id','effect','fit_status','component','layer_value','label',
                                       'training_rows','training_images','training_buildings'])


def cross_validate(data, training=None):
    train_source = data if training is None else training
    predictions, audit = [], []
    for building, test in data.groupby('building_id'):
        train = train_source[train_source.building_id != building]
        p = profiles(train)
        pred = predict_peers(test, p)
        predictions.append(pred)
        audit.append(dict(building_id=building, target_rows=len(test), predicted_rows=len(pred),
                          training_rows=len(train), training_buildings=train.building_id.nunique(),
                          training_building_ids=json.dumps(sorted(train.building_id.unique())),
                          unavailable_rows=len(test)-len(pred)))
    return pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame(), pd.DataFrame(audit)


def summarize(pred, meta):
    if pred.empty:
        return dict(**meta, rows=0, record_mse_gain=np.nan, building_mse_gain=np.nan), pd.DataFrame()
    bm = pred.groupby('building_id')[['baseline_sqerr','continuous_sqerr']].mean()
    gain = lambda a,b: float(1-a/b) if b > 1e-20 else np.nan
    row = dict(**meta, rows=len(pred), workers=pred.worker_id.nunique(), buildings=len(bm),
               contexts=pred.context_key.nunique(),
               record_mse_gain=gain(pred.continuous_sqerr.mean(), pred.baseline_sqerr.mean()),
               building_mse_gain=gain(bm.continuous_sqerr.mean(), bm.baseline_sqerr.mean()),
               buildings_improved=int((bm.continuous_sqerr < bm.baseline_sqerr).sum()))
    return row, bm.reset_index().assign(**meta)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    # 分析前固定口径；不看结果挑角点容差、工人门槛或合并阶段。
    (OUT/'PLAN.json').write_text(json.dumps(dict(metrics=METRICS, evaluation='leave_one_building_out_within_stage_condition',
        reference_policy='review_precedes_GT; unresolved_or_OOS_preserved_without_unique_reference_scoring',
        cohorts=['all_usable','fallback_only','reviewed_reference_only','current20_sensitivity'], worker_classes=None,
        geometry='unordered_spherical_endpoints; no_wall_or_Manhattan_validity_claim'), ensure_ascii=False, indent=2), encoding='utf-8')
    annotations = pd.read_csv(BASE/'annotations.csv.gz', dtype=str, keep_default_na=False)
    assert not annotations.canonical_annotation_id.duplicated().any()
    assert not annotations.duplicated(['context_key','worker_id']).any()
    references = jsonlines(BASE/'references.jsonl')
    public = {r['image_id']:r for r in references if r['source_role']=='public_dataset_import_reference'}
    historic = {r['image_id']:r for r in references if r['source_role']=='historical_adjudication_not_new_review'}
    assert len(public)==sum(r['source_role']=='public_dataset_import_reference' for r in references)
    confirmed_ids = set(re.findall(r'^\| `([^`]+)` \|', CORRECTIONS.read_text(encoding='utf-8'), re.M))
    assert len(confirmed_ids)==30
    corrected = {}
    for task in json.loads(GT.read_text(encoding='utf-8-sig')):
        image = Path(urlparse(task['data']['image']).path).stem
        if image not in confirmed_ids:
            continue
        live = [a for a in task['annotations'] if not a.get('was_cancelled')]
        if len(live)!=1 or image in corrected:
            raise ValueError('Ambiguous corrected GT identity: '+image)
        a = live[0]
        corrected[image] = dict(reference_id=f'current_manual_gt|{task["id"]}|{a["id"]}',
            points_1024x512=ordered_points(a['result']), source_path=str(GT.relative_to(ROOT)),
            confirmation_source=str(CORRECTIONS.relative_to(ROOT)))
    assert set(corrected)==confirmed_ids
    cases = {r['image_id']:r for r in jsonlines(SEMANTICS)}
    holds = dict(OLD_REVIEW_HOLD)
    for image, case in cases.items():
        if case['case_id'] in REVIEW_HOLD:
            holds[image] = REVIEW_HOLD[case['case_id']]
    candidate_reviews = json.loads((BASE/'archive/human30.json').read_text(encoding='utf-8'))['items']
    for r in candidate_reviews:
        if r['review']['scope']=='out_of_scope' or r['review_id'] in ['P30-007','P30-012','P30-016','P30-023']:
            holds[r['image_id']] = 'candidate_review_oos_or_reference_uncertain'
    ledger, chosen = [], {}
    for image in sorted(public):
        h = historic.get(image)
        c = corrected.get(image)
        if c is None and h and h['reference_quality_status']=='geometry_ready':
            c = h
        hold = holds.get(image)
        # 后来的坐标修订不自动撤销此前的OOS或参考不可用判断。
        if h and h['reference_quality_status']!='geometry_ready':
            hold = hold or 'historical_review_reference_not_geometry_ready'
        r = choose_reference(public.get(image), c, hold)
        r.update(image_id=image, case_id=cases.get(image,{}).get('case_id',''),
                 review_evidence=cases.get(image), historical_review=h,
                 candidate_review=next((x for x in candidate_reviews if x['image_id']==image),None))
        unit_points(r['points_1024x512'])
        chosen[image] = r
        ledger.append(r)
    with (OUT/'reference_ledger.jsonl').open('w', encoding='utf-8') as f:
        for r in ledger:
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
    view = {r['canonical_annotation_id']:r for r in jsonlines(POINTS)}
    assert set(view)==set(annotations.canonical_annotation_id)
    rows = []
    for a in annotations.to_dict('records'):
        v = view[a['canonical_annotation_id']]
        for k in ['image_id','worker_id','context_key','stage','block_index','raw_condition']:
            assert str(v[k])==a[k], (k,a['canonical_annotation_id'])
        r = chosen.get(a['image_id'])
        row = dict(a, reference_id=r['reference_id'] if r else '', reference_basis=r['basis'] if r else '',
                   reference_case=r['case_id'] if r else '',
                   reference_hold=r['hold_reason'] if r else 'missing_reference',
                   point_processing_status=v['processing_status'], point_failure=v['exclusion_reason'],
                   raw_point_count=v['raw_point_count'], effective_point_count=v['effective_point_count'])
        row['measurement_status'] = ('reference_unavailable' if not r or not r['score_allowed'] else
                                     'response_unavailable' if not v['calculation_included'] else 'computable')
        if row['measurement_status']=='computable':
            row.update(reference_metrics(v['effective_points_1024x512'], r['points_1024x512']))
        rows.append(row)
    measurements = pd.DataFrame(rows)
    measurements.to_csv(OUT/'response_measurements.csv.gz', index=False)
    measurements.groupby(['stage','raw_condition','reference_basis','measurement_status'],dropna=False).agg(
        responses=('canonical_annotation_id','size'), images=('image_id','nunique'), workers=('worker_id','nunique')).reset_index().to_csv(OUT/'coverage.csv',index=False)
    long = measurements[measurements.measurement_status=='computable'].melt(
        id_vars=list(annotations.columns)+['reference_basis'],value_vars=METRICS,var_name='metric',value_name='value')
    results, buildings, predictions, audits, fitted = [], [], [], [], []
    for (stage,condition,metric), d in long.groupby(['stage','raw_condition','metric']):
        for cohort, sub in [('all_usable',d),('fallback_only',d[d.reference_basis=='gt_assumed_correct']),
                            ('reviewed_reference_only',d[d.reference_basis=='reviewed_reference']),
                            ('current20_sensitivity',d[d.current20_member.str.lower()=='true'])]:
            if sub.empty:
                continue
            meta=dict(stage=stage,raw_condition=condition,metric=metric,cohort=cohort,evaluation='within_stage_LOBO')
            p,a = cross_validate(sub)
            summary,b = summarize(p,meta)
            results.append(summary); buildings.append(b); predictions.append(p.assign(**meta)); audits.append(a.assign(**meta))
            fitted.append(profiles(sub).assign(**meta))
        if stage in ['P1','C1'] and condition=='manual':
            other = 'C1' if stage=='P1' else 'P1'
            train = long[(long.stage==other)&(long.raw_condition=='manual')&(long.metric==metric)]
            meta=dict(stage=stage,raw_condition=condition,metric=metric,cohort='all_usable',evaluation=other+'_to_'+stage+'_LOBO')
            p,a = cross_validate(d,train)
            summary,b = summarize(p,meta)
            results.append(summary); buildings.append(b); predictions.append(p.assign(**meta)); audits.append(a.assign(**meta))
    for name, frames in [('validation_summary',[pd.DataFrame(results)]),('validation_by_building',buildings),
                         ('heldout_predictions',predictions),('fold_audit',audits),('worker_effects',fitted)]:
        pd.concat([f for f in frames if not f.empty],ignore_index=True).to_csv(OUT/(name+('.csv.gz' if name=='heldout_predictions' else '.csv')), index=False)
    qa=dict(canonical=len(measurements), images=measurements.image_id.nunique(), workers=measurements.worker_id.nunique(),
            contexts=measurements.context_key.nunique(), status=measurements.measurement_status.value_counts().to_dict(),
            corrected_gt_images=len(corrected), reference_records=len(ledger),
            reference_hold_counts=measurements.reference_hold.value_counts().to_dict(),
            point_status=measurements.point_processing_status.value_counts().to_dict(),
            originals_modified=False, corner_order_used=False, final_worker_classes_created=False)
    (OUT/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2), encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False), flush=True)
    print(pd.DataFrame(results).query("cohort=='all_usable' and raw_condition=='manual'").to_string(index=False), flush=True)


def pool_responses(data, metrics=METRICS):
    """只按图片与人组织；重复作答先各自计分，再取均值，不平均坐标。"""
    if data.canonical_annotation_id.duplicated().any():
        raise ValueError('duplicate_canonical_identity')
    if data.groupby('image_id').building_id.nunique().max()!=1:
        raise ValueError('image_building_conflict')
    if data.groupby('worker_id').current20_member.nunique().max()!=1:
        raise ValueError('worker_roster_conflict')
    d = data.copy()
    d[metrics] = d[metrics].astype(float)
    if not np.isfinite(d[metrics]).all().all():
        raise ValueError('nonfinite_metric')
    aggregation = {m:(m,'mean') for m in metrics}
    aggregation.update(response_count=('canonical_annotation_id','size'),
                       canonical_ids=('canonical_annotation_id',lambda x:json.dumps(sorted(x))),
                       current20_member=('current20_member','first'))
    result = d.groupby(['image_id','building_id','worker_id'],sort=True).agg(**aggregation).reset_index()
    result['context_key'] = result.image_id
    return result


def run_pooled():
    """复用已核验的逐响应参考测量；旧阶段、block、条件均不参与分组或拟合。"""
    dest = OUT/'pooled'
    dest.mkdir(exist_ok=True)
    original = pd.read_csv(OUT/'response_measurements.csv.gz',dtype=str,keep_default_na=False)
    base = pd.read_csv(BASE/'annotations.csv.gz',dtype=str,keep_default_na=False)
    assert len(original)==len(base) and set(original.canonical_annotation_id)==set(base.canonical_annotation_id)
    source = original[original.measurement_status=='computable']
    units = pool_responses(source)
    units.to_csv(dest/'image_worker_measurements.csv.gz',index=False)
    units[units.response_count>1].to_csv(dest/'repeated_responses.csv',index=False)
    results, predictions, folds, effects, by_building = [],[],[],[],[]
    for cohort,d in [('all26',units),('current20',units[units.current20_member.str.lower()=='true']),
                     ('no_repeat_sensitivity',units[units.response_count==1])]:
        for metric in METRICS:
            sample=d.assign(value=d[metric])
            meta=dict(cohort=cohort,metric=metric,evaluation='pooled_image_LOBO')
            p,a=cross_validate(sample)
            s,b=summarize(p,meta)
            results.append(s); by_building.append(b); predictions.append(p.assign(**meta))
            folds.append(a.assign(**meta)); effects.append(profiles(sample).assign(**meta))
    for name,frames in [('validation_summary',[pd.DataFrame(results)]),('validation_by_building',by_building),
                         ('heldout_predictions',predictions),('fold_audit',folds),('worker_effects',effects)]:
        pd.concat(frames,ignore_index=True).to_csv(dest/(name+('.csv.gz' if name=='heldout_predictions' else '.csv')),index=False)
    qa=dict(canonical_records=len(original),usable_responses=len(source),image_worker_units=len(units),
            images=units.image_id.nunique(),workers=units.worker_id.nunique(),buildings=units.building_id.nunique(),
            repeated_image_worker_units=int((units.response_count>1).sum()),
            source_status=original.measurement_status.value_counts().to_dict(),
            phase_condition_block_used=False,reference_policy_changed=False,raw_points_reordered=False,
            duplicate_handling='equal_response_mean_within_image_worker_then_equal_image_worker_weight',
            source='analysis_results/worker_reference_feasibility_20260909_v1/response_measurements.csv.gz',
            reproducibility='run default module first to rebuild source, then --pooled')
    (dest/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False),flush=True)
    print(pd.DataFrame(results).to_string(index=False),flush=True)


def ordinal_groups(p, k, method='quantile'):
    """训练效应分位数分档；同值不拆分，不声称存在天然类别。"""
    if k not in (2,3,4,5) or p.component.nunique()!=1:
        raise ValueError('unsupported_group_count_or_disconnected_training')
    p=p.copy()
    if method=='quantile':
        cuts=np.quantile(p.effect,np.arange(1,k)/k)
        p['label']=np.searchsorted(cuts,p.effect,side='left')+1
    elif method=='ward':
        from scipy.cluster.hierarchy import linkage,cut_tree
        observed=min(k,p.effect.nunique())
        labels=cut_tree(linkage(p[['effect']].to_numpy(),method='ward'),n_clusters=observed).ravel() if observed>1 else np.zeros(len(p),int)
        centers=p.assign(cluster=labels).groupby('cluster').effect.mean().sort_values()
        ranks={label:i+1 for i,label in enumerate(centers.index)}
        p['label']=[ranks[label] for label in labels]
    else:
        raise ValueError('unknown_group_method')
    p['layer_value']=p.groupby('label').effect.transform('mean')
    return p


def run_groups():
    dest=OUT/'pooled/groups'
    dest.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(OUT/'pooled/image_worker_measurements.csv.gz',dtype={'worker_id':str,'current20_member':str})
    summaries, memberships, heldout, full_members=[],[],[],[]
    for cohort,data in [('all26',d),('current20',d[d.current20_member.str.lower()=='true'])]:
        for metric in ['ospa30','ospa60']:
            data=data.assign(value=data[metric])
            full=profiles(data)
            for method in ['quantile','ward']:
                for k in (2,3,4,5):
                    full_members.append(ordinal_groups(full,k,method).assign(cohort=cohort,metric=metric,k=k,method=method))
            for building,test in data.groupby('building_id'):
                train=data[data.building_id!=building]
                p=profiles(train)
                for method in ['quantile','ward']:
                    for k in (2,3,4,5):
                        g=ordinal_groups(p,k,method)
                        memberships.append(g.assign(cohort=cohort,metric=metric,k=k,method=method,heldout_building=building))
                        pred=predict_peers(test,g)
                        heldout.append(pred.assign(cohort=cohort,metric=metric,k=k,method=method))
    predictions=pd.concat(heldout,ignore_index=True)
    members=pd.concat(memberships,ignore_index=True)
    full=pd.concat(full_members,ignore_index=True)
    stability=members.merge(full[['cohort','metric','k','method','worker_id','label']].rename(columns={'label':'full_label'}),
                            on=['cohort','metric','k','method','worker_id'],validate='many_to_one')
    stability['same_as_full']=stability.label==stability.full_label
    stability=stability.groupby(['cohort','metric','k','method','worker_id']).agg(
        same_as_full_fraction=('same_as_full','mean'),folds=('label','size'),
        distinct_labels=('label','nunique'),min_label=('label','min'),max_label=('label','max')).reset_index()
    for key,p in predictions.groupby(['cohort','metric','k','method']):
        cohort,metric,k,method=key
        bm=p.groupby('building_id')[['baseline_sqerr','continuous_sqerr','layer_sqerr']].mean()
        m=members[(members.cohort==cohort)&(members.metric==metric)&(members.k==k)&(members.method==method)]
        s=stability[(stability.cohort==cohort)&(stability.metric==metric)&(stability.k==k)&(stability.method==method)]
        f=full[(full.cohort==cohort)&(full.metric==metric)&(full.k==k)&(full.method==method)]
        summaries.append(dict(cohort=cohort,metric=metric,k=k,method=method,rows=len(p),buildings=len(bm),
            group_record_gain=1-p.layer_sqerr.mean()/p.baseline_sqerr.mean(),
            group_building_gain=1-bm.layer_sqerr.mean()/bm.baseline_sqerr.mean(),
            continuous_building_gain=1-bm.continuous_sqerr.mean()/bm.baseline_sqerr.mean(),
            improved_buildings=int((bm.layer_sqerr<bm.baseline_sqerr).sum()),
            full_group_sizes=json.dumps(f.groupby('label').size().to_dict()),
            smallest_training_group=int(m.groupby(['heldout_building','label']).size().min()),
            workers_same_all_folds=int((s.same_as_full_fraction==1).sum()),
            workers_same_at_least_90pct=int((s.same_as_full_fraction>=.9).sum()),
            minimum_observed_training_groups=int(m.groupby('heldout_building').label.nunique().min())))
    coverage=[]
    for key,g in full.groupby(['cohort','metric','k','method']):
        z=d.merge(g[['worker_id','label']],on='worker_id',validate='many_to_one')
        counts=pd.crosstab(z.image_id,z.label).reindex(columns=range(1,key[2]+1),fill_value=0)
        coverage.append(dict(zip(['cohort','metric','k','method'],key))|dict(images=len(counts),
            all_groups_at_least_one=int((counts.min(axis=1)>=1).sum()),
            all_groups_at_least_two=int((counts.min(axis=1)>=2).sum()),
            all_groups_at_least_three=int((counts.min(axis=1)>=3).sum())))
    for name,frame in [('validation_summary',pd.DataFrame(summaries)),('full_members',full),
                       ('combination_coverage',pd.DataFrame(coverage)),
                       ('fold_members',members),('worker_stability',stability),('heldout_predictions',predictions)]:
        frame.to_csv(dest/(name+('.csv.gz' if name=='heldout_predictions' else '.csv')),index=False)
    (dest/'METHOD.json').write_text(json.dumps(dict(k=[2,3,4,5],metrics=['ospa30','ospa60'],
        method='training_effect_quantiles_or_1D_Ward; group_mean_training_effect_prediction; ties_not_split',
        grouping_unit='worker',validation='leave_one_building_out; refit_and_recut_using_training_only',
        natural_cluster_count_established=False,personality_labels=False,independent_people_validation=False,
        stability='leave_one_building_deletion_against_full_fit_is_sensitivity_not_independent_replication',
        k_selection='parallel_exploratory_comparisons; no_confirmatory_best_k_selection'),indent=2),encoding='utf-8')
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pooled',action='store_true',help='合并全部阶段和条件，读取本入口既有逐响应测量')
    parser.add_argument('--groups',action='store_true',help='在合并资料上验证训练内2/3/4/5档')
    args=parser.parse_args()
    run_groups() if args.groups else run_pooled() if args.pooled else run()
