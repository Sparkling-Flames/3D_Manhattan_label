import pytest

from tools.thesis_main.analysis.layout_metric_response_20261001 import (
    synthetic_experiments, measure, select_real_panel,
)


def test_controlled_equivalence_identity_and_failure_boundaries():
    cases = synthetic_experiments()
    for case in cases:
        if case['family'] != 'equivalence':
            continue
        result = measure(case['a'], case['b'], synthetic=True)
        assert result['bev']['bev_range_iou'] == pytest.approx(1)
        assert result['bev']['centroid_distance_h'] < 1e-12
        assert result['boundary']['boundary_sampled_max'] < 1e-12
        assert result['column']['512x256']['iou'] == 1
        assert result['correspondence']['combined_rmse_h'] < 1e-12
        assert result['correspondence']['unmatched_a'] == (1 if case['case'].endswith('collinear_subdivision') else 0)
    near = next(c for c in cases if c['case'] == 'near_horizon_bottom_y' and c['amplitude'] == 4)
    unavailable = measure(near['a'], near['b'], synthetic=True)
    assert unavailable['bev']['status'] == 'unavailable'
    assert unavailable['bev']['reason']
    assert unavailable['column']['1024x512']['iou'] is None
    regular = next(c for c in cases if c['case'] == 'ordinary_bottom_y' and c['amplitude'] == .5)
    far = next(c for c in cases if c['case'] == 'near_horizon_bottom_y' and c['amplitude'] == .5)
    assert measure(far['a'], far['b'], synthetic=True)['correspondence']['floor_rmse_h'] > measure(regular['a'], regular['b'], synthetic=True)['correspondence']['floor_rmse_h']
    extension = next(c for c in cases if c['case'] == 'symmetric_extension' and c['amplitude'] == 1)
    result = measure(extension['a'], extension['b'], synthetic=True)
    assert result['bev']['bev_range_iou'] < 1
    assert result['bev']['centroid_distance_h'] < 1e-12
    assert result['manhattan'][0]['max_deg'] < 1e-12
    detail = next(c for c in cases if c['case'] == 'near_three_pairs' and c['amplitude'] == .002)
    coarse = measure(detail['a'], detail['b'], synthetic=True)
    dense = measure(detail['a'], detail['b'], synthetic=True, boundary_samples=8192)
    assert coarse['correspondence']['unmatched_a'] == 1
    assert coarse['manhattan'][0]['max_deg'] > 0
    assert dense['boundary']['boundary_sampled_max'] <= coarse['boundary']['boundary_sampled_max']+coarse['boundary']['sampled_max_upper_error_bound_h']+1e-12
    with pytest.raises(ValueError, match='invalid_boundary_samples'):
        measure(detail['a'], detail['b'], boundary_samples=0)


def test_panel_selection_uses_evidence_not_reference_distance():
    cases = synthetic_experiments()
    base = next(c for c in cases if c['case'] == 'cyclic_shift')['b']
    def image(code, **scene):
        return dict(code=code, scene=dict({'oos_status':'not_oos', 'doorway_status':'none'}, **scene), review={},
                    annotations=[dict(base, id='R'+code, cleaning='retained', review={},
                                      worker='P001', quality_candidate=False)], references=[])
    images = [image('a'), image('b'), image('c')]
    images[0]['annotations'][0]['review']['detail_annotation'] = True
    images[1]['annotations'][0]['review']['scope_annotation'] = True
    images[2]['annotations'][0]['ring_confirmed'] = False
    selected, coverage = select_real_panel(dict(images=images))
    assert {im['code'] for im, _ in selected} == {'a', 'b'}
    assert coverage['detail']['available_images'] == 1
    assert coverage['scope']['available_images'] == 1
    assert coverage['oos']['available_images'] == 0
    before = [(im['code'], r['id']) for im, r in selected]
    images[0]['references'] = [dict(base, id='irrelevant', version='original')]
    after, _ = select_real_panel(dict(images=images))
    assert before == [(im['code'], r['id']) for im, r in after]
    images[0]['annotations'][0]['review']['detail_annotation'] = False
    images[0]['review']['detail_comment_candidate'] = True
    _, coverage = select_real_panel(dict(images=images))
    assert coverage['detail']['available_images'] == 0  # 评论候选不升级为确认差异。


def test_output_contract_retains_missing_versions_and_real_noncorrespondence(tmp_path, monkeypatch):
    import csv
    import json
    from tools.thesis_main.analysis import layout_metric_response_20261001 as response
    monkeypatch.setattr(response, '_plots', lambda rows, out: None)
    base = synthetic_experiments()[0]['b']
    annotation = dict(base, id='R1', worker='P1', condition='manual', cleaning='retained',
        independent=True, consensus_eligible=True, quality_candidate=True, geometry_status='ok',
        review={}, main_quality_gate={'status':'candidate'}, main_consensus_gate={'status':'main_candidate'},
        source_point_indices=list(range(8)))
    reference = dict(base, id='G1', version='original', ring_confirmed=False, source_point_indices=list(range(8)))
    panel = dict(schema='layout_research_panel_v1', source_manifest={'source_entry':'unit_test'}, images=[
        dict(code='test_image', scene={'oos_status':'not_oos','doorway_status':'none'}, review={},
             annotations=[annotation], references=[reference])])
    result = response.run(panel,tmp_path)
    assert len(result['real']) == 2
    assert result['real'][0]['ring_confirmed_b'] is False
    assert result['real'][0]['metrics']['correspondence']['status'] == 'unavailable'
    missing = result['real'][1]['metrics']
    assert missing['bev']['bev_range_iou'] is None and missing['bev']['reason'] == 'reference_version_absent'
    assert missing['column']['1024x512']['iou'] is None
    contract = json.loads((tmp_path/'field_contract.json').read_text(encoding='utf-8'))
    for kind in ('synthetic','real'):
        with (tmp_path/(kind+'_metrics.csv')).open(encoding='utf-8-sig',newline='') as stream:
            assert next(csv.reader(stream)) == contract['csv_fields'][kind]
    saved = json.loads((tmp_path/'results.json').read_text(encoding='utf-8'))
    assert saved['real'][1]['metrics']['bev']['bev_range_iou'] is None
