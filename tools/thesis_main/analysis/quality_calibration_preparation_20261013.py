"""整体质量调参准备：固定基线，汇总原证据和隔离约束，不执行参数搜索。"""
from collections import Counter
import json
import numpy as np

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import ROOT, ARCHIVE, engine, read, module, evaluate_geometry
from tools.thesis_main.analysis.quality_height_calibration_ready_20261013 import rectangle

OUT = ROOT/'research/quality_calibration_preparation_20261013'
ADMISSION = ROOT/'research/quality_data_admission_audit_20261013'
FROZEN_DIRECTIONS = module(ARCHIVE/'calibration/physical_controls.py', 'preparation_directions').directions


def dump(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def reference_points(hx, hz):
    bottom = np.asarray(rectangle(hx, hz)['bottom3d'])
    radius = np.linalg.norm(bottom[:, [0, 2]], axis=1)
    x = (np.arctan2(bottom[:, 0], -bottom[:, 2])/(2*np.pi)+.5)*1024
    points = np.empty((8, 2)); points[::2, 0] = points[1::2, 0] = x
    points[::2, 1] = (.5-np.arctan2(1.6, radius)/np.pi)*512
    points[1::2, 1] = (.5+np.arctan2(1., radius)/np.pi)*512
    return points


def perturb_bottom(points, mode, budget, sign):
    patterns = {'single_bottom': np.array([2., 0, 0, 0]),
                'distributed_bottom': np.array([1., -1., 1., -1.])}
    changed = points.copy()
    changed[1::2, 1] += sign*budget*patterns[mode]
    return changed


def paired_2d(points, reference):
    # Only synthetic controls have known vertex identity; never infer real matching from score.
    delta = np.asarray(points)-np.asarray(reference)
    delta[:, 0] = (delta[:, 0]+512)%1024-512
    return dict(bottom_y_rms_px=float(np.sqrt(np.mean(delta[1::2, 1]**2))),
                all_point_rms_px=float(np.sqrt(np.mean(np.sum(delta**2, axis=1)))),
                max_point_distance_px=float(np.max(np.linalg.norm(delta, axis=1))),
                changed_points=int(np.sum(np.any(abs(delta)>1e-10, axis=1))),
                known_synthetic_correspondence=True, included_in_quality=False)


def direction_profile(geometry):
    d = FROZEN_DIRECTIONS(np.asarray(geometry['bottom3d'])[:, [0, 2]])
    contribution = np.asarray(d['length_weight'])*np.asarray(d['abs_residual_deg'])**2
    d['two_largest_edges_squared_contribution_share'] = float(np.sort(contribution)[-2:].sum()/contribution.sum()) if contribution.sum()>1e-15 else 0.
    return d


def severe_ready(r):
    return bool(r['severe_exception'] and r['severe_historical_full_q_ready'] and r['condition']=='manual'
                and not r['context_barriers'] and not r['original_holdout']
                and r['existing_conditional_development_allowed']
                and r['severe_review']['effective_review_status']=='reviewed_severe')


def build_controls(e, protocol, config):
    results = []
    single_engine = dict(e, configs={'frozen_current': config})
    for hx, hz in protocol['new_control_design']['reference_floor_half_sizes']:
        reference = reference_points(hx, hz); g = e['geometry'](reference)
        cases = [('unchanged', 0, 0, reference.copy())]
        for mode in protocol['new_control_design']['modes']:
            for budget in protocol['new_control_design']['bottom_y_rms_pixels']:
                for sign in protocol['new_control_design']['signs']:
                    cases.append((mode, budget, sign, perturb_bottom(reference, mode, budget, sign)))
        for mode, budget, sign, points in cases:
            try:
                annotation = e['geometry'](points)
                value = evaluate_geometry(annotation, g, single_engine)
                profile = direction_profile(annotation)
                polygon = np.asarray(annotation['bottom3d'])[:, [0, 2]]
                edge = np.roll(polygon, -1, axis=0)-polygon
                theta = np.degrees(np.arctan2(edge[:, 1], edge[:, 0]))
                turn = (np.roll(theta, -1)-theta+180)%360-180
                weights = np.asarray(profile['length_weight'])
                profile['reference_axis_0_rms_deg'] = float(np.sqrt(weights@(((theta+45)%90-45)**2)))
                # These controls are four known rectangle corners, not arbitrary real rings with 180-degree stops.
                profile['known_rectangle_corner_turn_deviation_90_rms_deg'] = float(np.sqrt(np.mean((abs(turn)-90)**2)))
                if value['metrics'] is not None:
                    assert abs(value['metrics']['dir']-profile['D_rms_deg']) < 1e-8
            except ValueError as exc:
                value = dict(status='unavailable', metrics=None, candidate_components=None, reason_codes=[str(exc)])
                profile = None
            result = dict(case_id=f'{hx}x{hz}:{mode}:{sign}:{budget}', mode=mode, budget=budget, sign=sign,
                          reference_half_sizes=[hx, hz], reference_points=reference.tolist(), points=points.tolist(),
                          diagnostic_2d=paired_2d(points, reference), direction_profile=profile, **value)
            assert np.array_equal(points[::2], reference[::2])
            assert abs(result['diagnostic_2d']['bottom_y_rms_px']-budget)<1e-10
            results.append(result)
    return results


def main():
    protocol = read(OUT/'PROTOCOL.json'); e = engine()
    parameter_path = ARCHIVE/'calibration/recommended_parameters.json'
    parameter_before = parameter_path.read_bytes()
    config = e['configs'][protocol['current_candidate']]
    primary = read(ADMISSION/'MANUAL_PRIMARY_SEARCH_INPUTS.json')
    all_admission = read(ADMISSION/'FULL_ADMISSION.json')['records']
    admission = {r['record_id']: r for r in all_admission}
    archived = read(ARCHIVE/'calibration/inputs/search_inputs.json')
    rows = {r['id']: r for r in archived['rows']}
    primary_ids = {r['id'] for r in primary['rows']}
    severe_ids = {r['record_id'] for r in all_admission if severe_ready(r)}
    assert len(primary_ids)==574 and len(severe_ids)==9 and not primary_ids & severe_ids
    stages = {r['record_id']:r for r in read(ROOT/'research/quality_scope_resolution_20261013/STAGE_LEDGER.json')['records']}
    baseline = []
    for rid in sorted(primary_ids | severe_ids):
        a = admission[rid]; r = rows[rid]
        assert not a['context_barriers'] and not a['original_holdout']
        assert a['condition']=='manual' and a['reference_object_id']==r['reference_object_id']
        assert stages[rid]['stage']=='ordinary_first_stage_candidate'
        if rid in primary_ids:
            assert a['role']=='manual_development_candidate' and not a['personnel_barriers']
            source = next(x for x in primary['rows'] if x['id']==rid)
            assert source['metrics']==r['metrics']
        components = e['score'].score_metrics(r['metrics'], config)
        assert components['status']=='complete'
        baseline.append(dict(record_id=rid, object_id=r['object_id'], image_id=r['image_id'], building_id=r['building_id'],
                             worker_id=r['worker_id'], reference_object_id=r['reference_object_id'], reference_version=r['reference_version'],
                             metrics=r['metrics'], descriptor=r['descriptor'], components=components,
                             use='ordinary_development' if rid in primary_ids else 'separate_severe_constraint',
                             severe_review=a['severe_review'] if rid in severe_ids else None,
                             formal_personnel_gate=a['current_personnel_gate'], personnel_barriers=a['personnel_barriers'],
                             existing_conditional_development_allowed=a['existing_conditional_development_allowed'],
                             original_holdout=False, exposure=a['exposure'], formal_eligibility_newly_granted=False))
    old = read(ROOT/'research/quality_review_constraints_20261012/evidence.json')
    recent = read(ROOT/'research/quality_joint_calibration_feedback_20261013/USER_FEEDBACK.json')
    evidence = []
    def add(group, ids, source, content, use):
        evidence.append(dict(group=group, source=source, original_and_interpretation=content, use=use,
                             numeric_target=None, independent_validation=False,
                             bindings=[dict(record_id=rid, role=admission[rid]['role'], condition=admission[rid]['condition'],
                                            reference_object_id=admission[rid]['reference_object_id'],
                                            context_barriers=admission[rid]['context_barriers'],
                                            original_holdout=admission[rid]['original_holdout']) for rid in ids]))
    for group in ('P01','C01','C02','C03','C04','P04','P05'):
        mapping = [r['record_id'] for r in old['dataset_mapping']['mapping'] if r['group']==group]
        assert mapping
        add(group, mapping, 'research/quality_review_constraints_20261012/evidence.json',
            dict(raw=old['raw_receipt']['answers'][group], current=old['feedback']['interpretations'][group]),
            'conditional_question_group_evidence_respect_each_binding')
    for case in recent['case_feedback']:
        add(case['case_id'], case['record_ids'], 'research/quality_joint_calibration_feedback_20261013/USER_FEEDBACK.json', case,
            'withdrawn_old_preference_diagnostic_only' if case['case_id']=='J02' else 'current_qualitative_feedback_no_hard_grade')
    raw_chat = (ROOT/'research/quality_joint_calibration_feedback_20261013/raw/CHAT_FEEDBACK.txt').read_text(encoding='utf-8-sig')
    add('T20', ['R00397'], 'research/quality_joint_calibration_feedback_20261013/raw/CHAT_FEEDBACK.txt',
        dict(verbatim=raw_chat, interpretation=recent['chat_feedback'][0]), 'slightly_increase_height_penalty_direction_separate_historical_source')
    local = read(ROOT/'research/quality_top_height_response_20261012/local_impact_feedback.json')
    add('L01', [local['A'], local['B']], 'research/quality_top_height_response_20261012/local_impact_feedback.json', local,
        'separate_semi_qualitative_tradeoff_no_numeric_gap')
    scope = read(ROOT/'research/quality_scope_resolution_20261013/REVIEW_INTERPRETATION.json')
    evidence_out = dict(schema='quality_overall_preparation_evidence_v1', question_groups=evidence,
                        existing_weak_grades=primary['grades'], existing_primary_constraints=primary['constraints'],
                        latest_height_shape_receipts=scope, deduplicate_by_question_group_not_dimension=True,
                        user_height_penalty_direction_preserved=True, new_grade_thresholds=None)
    dump('EVIDENCE.json', evidence_out)
    dump('BASELINE.json', dict(schema='quality_overall_preparation_baseline_v1', current_config=config, rows=baseline,
                              configuration_count=1, new_parameter_comparison_performed=False))
    controls = build_controls(e, protocol, config)
    dump('BOTTOM_CONTROLS.json', dict(schema='quality_bottom_response_preparation_v1', rows=controls,
                                     configuration_count=1, equal_perceived_severity_claimed=False))
    response_findings = []
    for shape in protocol['new_control_design']['reference_floor_half_sizes']:
        for mode in protocol['new_control_design']['modes']:
            for sign in protocol['new_control_design']['signs']:
                sequence = sorted([r for r in controls if r['reference_half_sizes']==shape and r['mode']==mode and r['sign']==sign], key=lambda r:r['budget'])
                for previous, current in zip(sequence, sequence[1:]):
                    if previous['status']!='complete' or current['status']!='complete': continue
                    a = previous['candidate_components']['frozen_current']['score']
                    b = current['candidate_components']['frozen_current']['score']
                    if b>a+1e-8 and current['metrics']['iou_2d']<previous['metrics']['iou_2d']:
                        response_findings.append(dict(case_ids=[previous['case_id'], current['case_id']],
                            score_change=b-a, kind='input_error_increases_iou_decreases_score_increases',
                            human_order_not_assumed=True, source='BOTTOM_CONTROLS.json'))
    dump('RESPONSE_FINDINGS.json', dict(schema='quality_preparation_response_findings_v1', records=response_findings,
                                      use='predeclared_controls_reveal_tradeoff_not_new_human_labels'))
    height = read(ROOT/'research/quality_height_calibration_ready_20261013/CONTROLS.json')
    assert len(height['records'])==110
    assert parameter_before == parameter_path.read_bytes()
    summary = dict(schema='quality_overall_calibration_preparation_v1', preparation_complete=True,
                   parameter_search_performed=False, parameter_files_changed=False,
                   ordinary_records=574, ordinary_images=len({r['image_id'] for r in baseline if r['use']=='ordinary_development'}),
                   severe_records=9, severe_images=len({r['image_id'] for r in baseline if r['use']=='separate_severe_constraint'}),
                   question_groups=len(evidence), weak_grade_count=len(primary['grades']),
                   new_bottom_controls=len(controls), control_statuses=dict(Counter(r['status'] for r in controls)),
                   response_reversal_pairs=len(response_findings),
                   existing_height_controls_reused_by_reference=110,
                   existing_height_path='research/quality_height_calibration_ready_20261013/CONTROLS.json',
                   existing_structure_path='research/quality_pro_joint_archive_20261013/source/experiments/results/targeted_constructed_cases.json',
                   gate_boundaries='普通/严重单列；门洞第二阶段，OOS不调参；缺参考/配对保持不可算',
                   holdout_policy='原282保留，已知148曾进入融合诊断；不得宣称新增盲验证',
                   unresolved_research_questions=['方向集中与广泛畸变如何取舍','总分严重端标尺','高度适度加重的幅度'],
                   independent_validation_ready=False, human_review_required_now=False,
                   current_run_readiness='输入、来源、控制与规则已备齐；尚未搜索或选新参数')
    dump('SUMMARY.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
