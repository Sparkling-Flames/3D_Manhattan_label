"""沿既有参考选择拆解冻结候选分歧；不选择参数、参考或人工等级。"""
import csv
from collections import Counter, defaultdict
from itertools import combinations
from statistics import mean, median

from tools.thesis_main.analysis.quality_current_candidate_view_20261013 import (
    ROOT, SOURCE, read, load_inputs,
)
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

OUT = ROOT / 'research/quality_candidate_disagreement_20261013'
BASE = 'baseline_quad08'
MAIN = 'J_main_hill_tail12_g1_l025'
SIMPLE = 'J_simple_power8_g1_l025'
NAMES = (BASE, MAIN, SIMPLE)
LOSSES = ('boundary_loss', 'direction_loss', 'global_height_loss', 'local_height_loss')


def select_existing_reference(route, selected_ref, pairs, frozen_ref=None):
    if route is not None:
        if route['status'] != 'available':
            return 'route_unavailable', None
        if route['selected_full_status'] != 'available':
            return 'routed_floor_only', None
        if selected_ref not in pairs:
            raise ValueError('selected reference has no existing full metrics')
        return 'routed_full', selected_ref
    if frozen_ref is not None:
        if frozen_ref not in pairs:
            raise ValueError('frozen reference missing')
        return 'frozen_fixed_reference', frozen_ref
    if len(pairs) == 1:
        return 'single_existing_reference_conditional', next(iter(pairs))
    return ('unresolved_versions' if pairs else 'geometry_unavailable'), None


def loss_contributions(iou, old, new):
    """同分子加和分母的精确代数分解，不是因果归因或新评分。"""
    factor = -100 * iou / (old['denominator'] * new['denominator'])
    return {key: factor * (new[key] - old[key]) for key in LOSSES}


def describe(values):
    return dict(n=len(values), min=min(values), median=median(values), mean=mean(values),
                max=max(values)) if values else dict(n=0)


def main():
    scorer, configs, _, admission = load_inputs()
    objects = {o['object_id']:o for o in load_current_bundle()['data']['objects']}
    frozen = read(ROOT / 'research/quality_current_candidate_view_20261013/CANDIDATE_VIEW.json')['rows']
    expanded = read(ROOT / 'research/quality_manual_expansion_20261013/RESULTS.json')['records']
    routes = {r['record_id']: r['route'] for r in read(
        ROOT / 'research/quality_current_candidate_view_20261013/ROUTED_EXISTING_VIEW.json')['rows']}
    prepared = read(SOURCE / 'routing/inputs/prepared_input.json')
    references = {c['candidate_id']: c for im in prepared['candidate_images'] for c in im['candidates']}
    frozen_by_id = {r['record_id']: r for r in frozen}
    pairs = defaultdict(dict)
    for row in frozen + expanded:
        rid, ref = row['record_id'], row['reference_object_id']
        assert ref not in pairs[rid], (rid, ref)
        pairs[rid][ref] = row
    # 主式和简式的高度项必须相同，才能把二者差异解释为方向响应。
    assert all(configs[MAIN][k] == configs[SIMPLE][k] for k in
               ('global_scale', 'local_scale', 'global_power', 'local_power',
                'combine', 'iou_power', 'boundary_scale', 'boundary_power'))
    rows, unavailable = [], []
    for rid, gate in admission.items():
        if gate['role'] != 'manual_development_candidate':
            continue
        assert not gate['original_holdout'] and not gate['personnel_barriers'] and not gate['context_barriers']
        route = routes.get(rid)
        ref = references[route['selected_candidate_id']].get('reference_object_id') if route and route['selected_candidate_id'] else None
        old = frozen_by_id.get(rid)
        basis, ref = select_existing_reference(route, ref, pairs[rid], old['reference_object_id'] if old else None)
        obj = objects[gate['object_id']]
        context = {k:obj['final_review'][k] for k in ('scope_difference_image', 'detail_difference_image',
                    'scope_difference_annotation', 'detail_difference_annotation', 'scene_oos_status', 'order_state')}
        context['geometry_issues'] = obj['geometry']['issues']
        context['recorded_scope_or_detail_flag'] = any(context[k] for k in
                    ('scope_difference_image','detail_difference_image','scope_difference_annotation','detail_difference_annotation'))
        identity = dict(record_id=rid, object_id=gate['object_id'], image_code=gate['image_code'],
                        image_id=gate['image_id'], building_id=gate['image_code'].rsplit('-', 1)[0],
                        worker_id=gate['worker_id'], reference_basis=basis,
                        reference_object_id=ref, selected_candidate_id=route['selected_candidate_id'] if route else None,
                        route_uncertainty=route.get('uncertainty') if route else None,
                        manual_directive_applied=route.get('manual_directive_applied', False) if route else False,
                        manual_family_applied=route.get('manual_family_applied', False) if route else False,
                        exposure=gate['exposure'], original_holdout=False, existing_context=context)
        if basis in ('route_unavailable', 'geometry_unavailable', 'unresolved_versions'):
            unavailable.append(identity)
            continue
        if basis == 'routed_floor_only':
            metrics = dict(iou_2d=route['I_selected'], S_bottom_deg=route['Sb_selected_deg'],
                           dir=route['D_deg'], Hmean=None, Hcenter=None)
        else:
            metrics = pairs[rid][ref]['metrics']
        scores = {n: scorer.score_metrics(metrics, configs[n]) for n in NAMES}
        field = 'floor_score' if basis == 'routed_floor_only' else 'score'
        assert all(scores[n][field] is not None for n in NAMES), rid
        if route:
            expected = route['Q_floor_selected' if field == 'floor_score' else 'Q_full_selected']
            assert abs(scores[BASE][field] - expected) < 1e-8, rid
        row = dict(**identity, score_kind='floor_only' if field == 'floor_score' else 'full',
                   metrics=metrics, scores=scores,
                   candidate_deltas={n: scores[n][field] - scores[BASE][field] for n in NAMES[1:]})
        if field == 'score':
            row['main_vs_baseline_contributions'] = loss_contributions(metrics['iou_2d'], scores[BASE], scores[MAIN])
            assert abs(sum(row['main_vs_baseline_contributions'].values()) - row['candidate_deltas'][MAIN]) < 1e-9
            assert abs(scores[MAIN]['local_height_loss'] - scores[BASE]['local_height_loss']) < 1e-12
            # 关闭单个高度分量仅用于响应诊断，不能解释为真实错误修复。
            row['main_height_ablation_drop'] = {k: 100*metrics['iou_2d']/(scores[MAIN]['denominator']-scores[MAIN][k])-scores[MAIN]['score']
                                              for k in ('global_height_loss', 'local_height_loss')}
        rows.append(row)
    expected=sum(g['role']=='manual_development_candidate' for g in admission.values())
    assert len({r['record_id'] for r in rows + unavailable}) == len(rows) + len(unavailable) == expected
    summary = dict(ordinary_manual_records=expected, reference_basis_counts=dict(Counter(r['reference_basis'] for r in rows + unavailable)),
                   scored_records=len(rows), full=sum(r['score_kind']=='full' for r in rows),
                   floor_only=sum(r['score_kind']=='floor_only' for r in rows),
                   images=len({r['image_id'] for r in rows}), buildings=len({r['building_id'] for r in rows}))
    grouped = {}
    for level in ('image_code', 'building_id'):
        groups = defaultdict(list)
        for r in rows:
            groups[(r[level], r['score_kind'])].append(r)
        grouped[level] = [dict(group=k[0], score_kind=k[1], records=len(v),
            mean_delta={n:mean(r['candidate_deltas'][n] for r in v) for n in NAMES[1:]}) for k,v in sorted(groups.items())]
    summary['by_score_kind'] = {kind: {n:dict(**describe([r['candidate_deltas'][n] for r in rows if r['score_kind']==kind]),
        decrease_ge5=sum(r['candidate_deltas'][n]<=-5 for r in rows if r['score_kind']==kind),
        increase_ge5=sum(r['candidate_deltas'][n]>=5 for r in rows if r['score_kind']==kind)) for n in NAMES[1:]}
        for kind in ('full','floor_only')}
    full = [r for r in rows if r['score_kind']=='full']
    summary['main_full_contributions'] = {k:describe([r['main_vs_baseline_contributions'][k] for r in full]) for k in LOSSES}
    summary['full_context_strata'] = {label:dict(records=len(group), images=len({r['image_id'] for r in group}),
        mean_main_delta=mean(r['candidate_deltas'][MAIN] for r in group) if group else None)
        for label,group in [(label,[r for r in full if r['existing_context']['recorded_scope_or_detail_flag']==flag])
            for label,flag in [('recorded_scope_or_detail',True),('no_recorded_flag_not_confirmed_clean',False)]]}
    summary['height_coverage_descriptive_only'] = dict(
        global_ge_20percent_by_building=dict(Counter(r['building_id'] for r in full if r['metrics']['Hmean']>=.2)),
        local_ge_10percent_by_building=dict(Counter(r['building_id'] for r in full if r['metrics']['Hcenter']>=.1)),
        cutoffs_are_descriptive_not_quality_grades=True)
    summary['equal_image_mean_delta_full'] = {n:describe([r['mean_delta'][n] for r in grouped['image_code'] if r['score_kind']=='full']) for n in NAMES[1:]}
    dual = defaultdict(list)
    for r in expanded:
        dual[r['record_id']].append(r)
    version_sensitivity = [dict(record_id=rid, image_code=rr[0]['image_code'],
        current_role=admission[rid]['role'],context_barriers=admission[rid]['context_barriers'],
        reference_ids=[r['reference_object_id'] for r in rr],
        score_spread={n:abs(rr[0]['candidate_components'][n]['score']-rr[1]['candidate_components'][n]['score']) for n in NAMES})
        for rid,rr in dual.items() if len(rr)==2]
    summary['existing_version_sensitivity_not_main_selection'] = {n:describe([r['score_spread'][n] for r in version_sensitivity]) for n in NAMES}
    restored = {r['record_id']:r for r in read(OUT/'HISTORICAL_REFERENCE_BINDINGS.json')['records']}
    historical = []
    unresolved = [r for r in unavailable if r['reference_basis']=='unresolved_versions']
    assert {rid for rid in restored if admission[rid]['role']=='manual_development_candidate'} == {r['record_id'] for r in unresolved}
    for r in unresolved:
        binding = restored[r['record_id']]
        assert binding['object_id'] == r['object_id']
        ref = binding['historical_component']['reference_object_id']
        old = pairs[r['record_id']][ref]
        assert binding['historical_target_alignment']['target_unconfounded_conservative'] is False
        historical.append(dict(record_id=r['record_id'],image_code=r['image_code'],reference_object_id=ref,
            reference_basis='restored_historical_fixed_reference_not_current_target_assignment',
            source_binding=binding, metrics=old['metrics'], scores=old['candidate_components']))
        r['historical_fixed_reference_recoverable'] = True
        r['missing_kind'] = 'current_target_assignment_not_historical_reference_binding'
    summary['historical_fixed_reference_replay'] = dict(records=len(historical),images=len({r['image_code'] for r in historical}),
        all_target_confounded=True, included_in_single_reference_summary=False,
        main_deltas=describe([r['scores'][MAIN]['score']-r['scores'][BASE]['score'] for r in historical]))
    matrix = []
    with (SOURCE/'integration/results/reference_formula_four_way.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if admission[r['record_id']]['role']=='manual_development_candidate' and r['candidate']==MAIN:
                matrix.append(r)
    summary['routed_four_way'] = {kind:dict(rows=sum(r['score_kind']==kind for r in matrix),
        comparable=sum(r['score_kind']==kind and r['common_computable']=='True' and r['both_references_admitted']=='True' for r in matrix),
        changed_comparable=sum(r['score_kind']==kind and r['common_computable']=='True' and r['both_references_admitted']=='True' and r['reference_changed']=='True' for r in matrix))
        for kind in ('full','floor')}
    # 固定的机制极值清单，只定位问题，不作为代表样本或人工标签。
    case_ids = defaultdict(list)
    selectors = {'direction_formula_change':lambda r:-r['main_vs_baseline_contributions']['direction_loss'],
                 'global_height_response':lambda r:r['main_height_ablation_drop']['global_height_loss'],
                 'local_height_response':lambda r:r['main_height_ablation_drop']['local_height_loss']}
    for reason, key in selectors.items():
        images = set()
        for r in sorted(full, key=lambda r:(-key(r),r['record_id'])):
            if r['image_id'] in images:continue
            images.add(r['image_id']);case_ids[r['record_id']].append(reason)
            if len(images)==3:break
    cases = [dict(r, selection_reasons=case_ids[r['record_id']]) for r in full if r['record_id'] in case_ids]
    for r in cases:
        evidence = objects[r['object_id']]['review_evidence']
        r['existing_review_evidence'] = {k:evidence[k] for k in ('current_comment','current_decision_comment',
            'image_comment','gt_version_note','review_history','image_review_history')}
        r['review_source'] = 'analysis_results/research_input_20260929/manifest.json via load_current_bundle'
    # 仅同图、同参考比较次序；重复几何和相同人员不计入。
    cells = defaultdict(list)
    for r in full:cells[(r['image_id'],r['reference_object_id'])].append(r)
    reversals=[]
    for cell in cells.values():
        for a,b in combinations(cell,2):
            if a['worker_id']==b['worker_id'] or a['metrics']==b['metrics']:continue
            gaps={n:a['scores'][n]['score']-b['scores'][n]['score'] for n in NAMES}
            if gaps[MAIN]*gaps[SIMPLE]<-1e-10:
                reversals.append(dict(A=a['record_id'],B=b['record_id'],image_code=a['image_code'],
                    reference_object_id=a['reference_object_id'],gaps=gaps))
    summary['main_simple_order_reversals'] = dict(pairs=len(reversals),images=len({r['image_code'] for r in reversals}),
        both_gaps_ge2=sum(min(abs(r['gaps'][MAIN]),abs(r['gaps'][SIMPLE]))>=2 for r in reversals),
        threshold_role='descriptive_gap_only_not_human_significance')
    OUT.mkdir(parents=True,exist_ok=True)
    import json
    payload=dict(schema='quality_candidate_disagreement_20261013_v1',
        policy=dict(no_reference_selected_by_score=True, manual_only=True, formal_eligibility_newly_granted=False,
                    no_new_parameters=True, all_results_conditional_development=True, no_human_labels_created=True),
        summary=summary, groups=grouped, records=rows, unavailable=unavailable,
        existing_version_sensitivity=version_sensitivity, routed_four_way=matrix,
        historical_fixed_reference_replay=historical,
        mechanism_cases=cases, same_reference_order_reversals=reversals)
    (OUT/'RESULTS.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
