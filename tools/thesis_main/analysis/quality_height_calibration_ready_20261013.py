"""高度响应准备与预先限定的五候选比较；不改公式、参考或正式资格。"""
from collections import Counter, defaultdict
from copy import deepcopy
import json

import numpy as np

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import ROOT, ARCHIVE, engine, read

OUT = ROOT/'research/quality_height_calibration_ready_20261013'
ADMISSION = ROOT/'research/quality_data_admission_audit_20261013'
SCOPE = ROOT/'research/quality_scope_resolution_20261013'


def dump(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def configurations(e, design):
    base = e['configs'][design['base_candidate']]
    return {c['name']: dict(base, global_scale=c['global_scale'], local_scale=c['local_scale'])
            for c in design['candidates']}


def rectangle(hx, hz):
    bottom = np.array([[-hx, -1., -hz], [hx, -1., -hz], [hx, -1., hz], [-hx, -1., hz]])
    top = bottom.copy(); top[:, 1] = 1.6
    return dict(bottom3d=bottom.tolist(), top3d=top.tolist())


def control(reference, relative_offsets, e):
    annotation = deepcopy(reference)
    top = np.asarray(annotation['top3d']); top[:, 1] += 2.6*np.asarray(relative_offsets)
    annotation['top3d'] = top.tolist()
    for record, role in [(annotation, 'annotation'), (reference, 'reference')]:
        assert e['valid'].validate_record(record, role=role)['available']
    bottom = np.asarray(reference['bottom3d'])
    lengths = np.linalg.norm(np.roll(bottom, -1, axis=0)-bottom, axis=1)
    weights = lengths/lengths.sum()
    v = np.asarray(relative_offsets); n = np.roll(v, -1)
    mean = float(weights@((v+n)/2))
    second = float(weights@((v*v+v*n+n*n)/3))
    am = e['hm'].height_moments(annotation); gm = e['hm'].height_moments(reference)
    hc = e['center'].centered_height_components(annotation, reference, samples=4096, height_module=e['hm'])['Hcenter']
    metrics = dict(iou_2d=1., S_bottom_deg=0., dir=0.,
                   Hmean=abs(am['height_mean_h']/gm['height_mean_h']-1), Hcenter=hc)
    exact_hc = float(np.sqrt(max(0., second-mean*mean)))
    assert abs(metrics['Hmean']-abs(mean)) < 1e-10
    assert abs(hc-exact_hc) < 5e-6
    return dict(annotation_geometry=annotation, reference_geometry=reference, metrics=metrics,
                exact_Hm=abs(mean), exact_Hc=exact_hc, signed_mean_relative=mean,
                top_boundary_relative_rms=float(np.sqrt(second)),
                peak_corner_relative=float(np.max(np.abs(v))), relative_corner_offsets=v.tolist())


def controls(e, design, configs):
    old = read(ARCHIVE/'calibration/results/physical_controls.json')['rows']
    rows = [dict(case_id=r['case_id'], kind=r['kind'], origin='reused_frozen_control',
                 reference_case=r['reference_case'], metrics=r['metrics'],
                 top_boundary_relative_rms=2**.5*r['actual_budget'])
            for r in old if r['kind'] in ('local_height', 'global_height_high', 'global_height_low')]
    assert len(rows) == 48
    for shape, hx, hz in [('square', 2., 2.), ('narrow', 1., 4.)]:
        g = rectangle(hx, hz)
        patterns = dict(tilt_x=[-1, 1, 1, -1], tilt_z=[-1, -1, 1, 1], isolated_corner=[1, 0, 0, 0])
        new = [('perfect', 0., 0, [0.]*4)]
        for kind, pattern in patterns.items():
            for amplitude in design['controls']['peak_relative_amplitudes']:
                for sign in (-1, 1):
                    new.append((kind, amplitude, sign, sign*amplitude*np.array(pattern)))
        for amplitude in design['controls']['severe_uniform_amplitudes']:
            for sign in (-1, 1):
                new.append(('severe_uniform', amplitude, sign, np.full(4, sign*amplitude)))
        for sign in (-1, 1):
            new.append(('lower_and_tilt', .2, sign, -.25+sign*.2*np.array(patterns['tilt_x'])))
        for kind, amplitude, sign, offsets in new:
            rows.append(dict(case_id=f'{shape}:{kind}:{sign}:{amplitude}', reference_case=shape,
                             kind=kind, amplitude=amplitude, sign=sign, origin='new_geometry_control',
                             **control(g, offsets, e)))
    for r in rows:
        r['candidate_components'] = {n: e['score'].score_metrics(r['metrics'], c) for n, c in configs.items()}
        assert all(v['status'] == 'complete' for v in r['candidate_components'].values())
    groups = defaultdict(list)
    for r in rows:
        if r['origin'] == 'new_geometry_control' and r['kind'] not in ('perfect', 'lower_and_tilt'):
            groups[r['reference_case'], r['kind'], r['sign']].append(r)
    for group in groups.values():
        group.sort(key=lambda r: r['amplitude'])
        for name in configs:
            assert np.all(np.diff([r['candidate_components'][name]['score'] for r in group]) <= 1e-9)
    return rows


def evidence(data, scores):
    by = {r['id']: i for i, r in enumerate(data['rows'])}
    building = {r['id']: r['building_id'] for r in data['rows']}
    def weak(excluded=None):
        grades = [g for g in data['grades'] if building[g['id']] != excluded]
        pairs = [(a['id'], b['id']) for a in grades for b in grades if a['grade'] < b['grade']]
        inversions = sum(float(scores[by[a]] < scores[by[b]]-1e-10) +
                         .5*float(abs(scores[by[a]]-scores[by[b]]) <= 1e-10) for a, b in pairs)
        return dict(weak_grade_pairs=len(pairs), weak_grade_inversions=inversions)
    overall = []; close = []
    for c in data['constraints']:
        if c['dimension'] != 'processed_overall_quality':
            continue
        if c['evidence_type'] == 'explicit_direction':
            margin = float(scores[by[c['preferred_record_id']]]-scores[by[c['other_record_id']]])
            overall.append(dict(group=c['source_question_group'], margin=margin, satisfied=margin > 0))
        elif c['evidence_type'] == 'uncertain_and_qualitatively_close':
            a, b = c['record_ids']
            close.append(dict(group=c['source_question_group'], signed_gap=float(scores[by[a]]-scores[by[b]]),
                              target_gap=None, exact_tie=False))
    return dict(**weak(), explicit_overall=overall, qualitative_close=close,
                leave_one_evidence_building_out=[dict(excluded_building=b, **weak(b))
                    for b in sorted({building[g['id']] for g in data['grades']})])


def main():
    design = read(OUT/'DESIGN.json'); e = engine(); configs = configurations(e, design)
    data = read(ADMISSION/'MANUAL_PRIMARY_SEARCH_INPUTS.json')
    admission = {r['record_id']: r for r in read(ADMISSION/'FULL_ADMISSION.json')['records']}
    stages = {r['record_id']: r for r in read(SCOPE/'STAGE_LEDGER.json')['records']}
    review = read(SCOPE/'REVIEW_INTERPRETATION.json')
    closeout = read(ROOT/'research/quality_data_closeout_20261013/SUMMARY.json')
    ids = {r['id'] for r in data['rows']}
    assert len(ids) == len(data['rows']) == design['data']['expected_records']
    assert len(data['grades']) == 11 and len(data['constraints']) == 5
    assert {g['id'] for g in data['grades']} <= ids
    assert all(set(c['record_ids']) <= ids for c in data['constraints'])
    assert 'R00977' not in ids
    ledger = []
    for r in data['rows']:
        a = admission[r['id']]; s = stages[r['id']]
        assert a['condition'] == 'manual' and a['role'] == 'manual_development_candidate'
        assert not (a['original_holdout'] or a['personnel_barriers'] or a['context_barriers'] or a['numeric_barriers'])
        assert a['full_q_calibration_ready'] and not a['severe_exception']
        assert s['stage'] == 'ordinary_first_stage_candidate' and s['current_fit_view']
        assert a['object_id'] == r['object_id'] and a['reference_object_id'] == r['reference_object_id']
        ledger.append(dict(record_id=r['id'], object_id=r['object_id'], reference_object_id=r['reference_object_id'],
                           reference_version=r['reference_version'], image_id=r['image_id'], building_id=r['building_id'],
                           original_holdout=False, exposure=a['exposure'],
                           ordinary_status_is_explicit=s['ordinary_status_is_explicit'],
                           existing_conditional_development_allowed=a['existing_conditional_development_allowed']))
    control_rows = controls(e, design, configs)
    dump('CONTROLS.json', dict(schema='quality_height_response_controls_v1', records=control_rows,
                               equal_perceived_severity_claimed=False, new_controls_passed=True))
    prep = dict(schema='quality_height_preparation_v1', ready=True, records=len(ids),
                images=len({r['image_id'] for r in ledger}), buildings=len({r['building_id'] for r in ledger}),
                explicitly_ordinary=sum(r['ordinary_status_is_explicit'] for r in ledger),
                existing_conditional_authority=sum(r['existing_conditional_development_allowed'] for r in ledger),
                original_holdout=closeout['original_holdout'],
                original_holdout_members_in_new_frozen_fusion_diagnostics=closeout['original_holdout_members_in_new_frozen_fusion_diagnostics'],
                all_human_evidence_is_development=True, independent_validation_claimed=False,
                new_control_count=sum(r['origin']=='new_geometry_control' for r in control_rows), reused_control_count=48,
                grade_counts=dict(Counter(g['grade'] for g in data['grades'])),
                constraint_groups=sorted({c['source_question_group'] for c in data['constraints']}),
                questionnaire_counts=review['summary'], records_ledger=ledger,
                weak_grades=data['grades'], constraints=data['constraints'])
    dump('PREPARATION.json', prep)
    # Candidate scores are evaluated only after admission and geometry gates pass.
    normalized = [e['score'].normalized_metrics(r['metrics']) for r in data['rows']]
    arrays = {k: np.array([r[k] for r in normalized], dtype=float) for k in ('I', 'Sb', 'D', 'Hm', 'Hc')}
    assert all(np.isfinite(v).all() for v in arrays.values())
    outputs = {n: e['score'].evaluate_arrays(arrays, c) for n, c in configs.items()}
    summary = {}; scores = []
    for name, values in outputs.items():
        assert np.allclose(values['floor_score'], outputs['main']['floor_score'], atol=1e-12, rtol=0)
        delta = values['score']-outputs['main']['score']
        grouped = {}
        for field in ('image_id', 'building_id'):
            bins = defaultdict(list)
            for r, v in zip(data['rows'], delta): bins[r[field]].append(float(v))
            means = {k: float(np.mean(v)) for k, v in bins.items()}
            grouped[field] = dict(equal_group_mean_delta=float(np.mean(list(means.values()))), per_group_mean_delta=means)
        summary[name] = dict(evidence=evidence(data, values['score']), delta_min=float(delta.min()),
                             delta_median=float(np.median(delta)), delta_max=float(delta.max()),
                             absolute_delta_ge1=int(np.sum(abs(delta)>=1)), absolute_delta_ge5=int(np.sum(abs(delta)>=5)),
                             grouped_impacts=grouped)
        summary[name]['passes_explicit_overall_gate'] = all(x['satisfied'] for x in summary[name]['evidence']['explicit_overall'])
    for i, r in enumerate(data['rows']):
        scores.append(dict(record_id=r['id'], reference_object_id=r['reference_object_id'], metrics=r['metrics'],
                           candidate_components={n: {k: float(v[i]) for k, v in out.items()} for n, out in outputs.items()}))
    recent = []
    height = {r['record_id']: r for r in read(ROOT/'research/quality_height_correspondence_20261013/RESULTS.json')['records']}
    for r in review['records']:
        if r['record_id'] == 'R00977':
            recent.append(dict(record_id=r['record_id'], status='held_staircase_no_candidate_evaluation'))
            continue
        metrics = height[r['record_id']]['original_metrics']
        recent.append(dict(record_id=r['record_id'], status='shape_diagnostic_not_new_label',
                           in_primary=r['record_id'] in ids, interpretation=r['interpretation'], metrics=metrics,
                           candidate_components={n: e['score'].score_metrics(metrics, c) for n, c in configs.items()}))
    archived = {r['id']: r for r in read(ARCHIVE/'calibration/inputs/search_inputs.json')['rows']}
    severe_ids = {r['record_id'] for r in admission.values() if r['severe_exception'] and r['severe_historical_full_q_ready']}
    assert len(severe_ids) == 9 and severe_ids <= set(archived)
    diagnostic_ids = severe_ids | {'R00397', 'R00418', 'R01609', 'R02297'}
    assert not (diagnostic_ids & ids)
    historical = []
    for rid in sorted(diagnostic_ids):
        r = archived[rid]; a = admission[rid]
        historical.append(dict(record_id=rid, reference_object_id=r['reference_object_id'],
                               source='archived_search_inputs_existing_binding', role=a['role'], condition=a['condition'],
                               personnel_barriers=a['personnel_barriers'], context_barriers=a['context_barriers'],
                               severe_exception=a['severe_exception'], used_to_fit_or_select=False,
                               candidate_components={n: e['score'].score_metrics(r['metrics'], c) for n,c in configs.items()}))
    result = dict(schema='quality_height_bounded_comparison_v1', configs=configs, summary=summary,
                  records=scores, recent_shape_diagnostics=recent, historical_diagnostics=historical,
                  selection=dict(retained='main', promoted=False,
                                 reason='现有明确总质量方向只有P01；近期高度回执没有严重度/跨案例总质量次序，不能由弱等级或普遍涨分唯一识别尺度。'))
    dump('COMPARISON.json', result)
    print(json.dumps(dict(preparation={k:v for k,v in prep.items() if k not in ('records_ledger','weak_grades','constraints')},
                          comparisons={n: {k:v for k,v in r.items() if k!='grouped_impacts'} for n,r in summary.items()}), ensure_ascii=False))


if __name__ == '__main__':
    main()
