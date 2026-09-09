import json
import gzip

from tools.thesis_main.analysis.analyze_q_thresholds_20260909 import gated_pairwise, q_partition, select_responses
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry


def test_default_run_preserves_existing_rich_inventory(tmp_path):
    from tools.thesis_main.analysis.analyze_q_thresholds_20260909 import INPUT, OUTPUT, run
    source = tmp_path / INPUT
    source.parent.mkdir(parents=True)
    points = [[x, y] for x in (100, 700) for y in (120, 390)]
    with gzip.open(source, 'wt', encoding='utf-8') as f:
        for worker in ('1', '2'):
            row = dict(canonical_annotation_id=worker, image_id='image', building_id='building',
                worker_id=worker, stage='P1', block_index=0, raw_condition='manual', assistance_exposure='none',
                calculation_included=True, unassisted_manual_included=True, effective_points_1024x512=points,
                raw_point_count=4, effective_point_count=4, processing_status='unchanged', distance_recompute_required=False)
            f.write(json.dumps(row) + '\n')
    inventory = (tmp_path / OUTPUT).parent / 'image_inventory.csv'
    inventory.parent.mkdir(parents=True)
    inventory.write_text('existing,rich,inventory\n', encoding='utf-8')
    qa = run(tmp_path, min_workers=1)
    assert qa['response_n'] == 2 and qa['pair_n'] == 1
    assert inventory.read_text(encoding='utf-8') == 'existing,rich,inventory\n'


def geometry(xs, shift=0):
    return normalize_geometry([[x, y + shift] for x in xs for y in (120, 390)])


def test_symmetric_worker_scenarios_and_no_imputation():
    source = [dict(canonical_annotation_id=str(w), image_id='image', worker_id=str(w),
                   calculation_included=True, assistance_exposure='none', unassisted_manual_included=True,
                   raw_points_1024x512=[[10, 20]], effective_points_1024x512=[[10, 20], [10, 400]],
                   effective_point_count=2, imputed_point=w == 30, processing_status='test')
              for w in (19, 26, 30)]
    assert len(select_responses(source)) == 3
    selected = select_responses(source, ('19', '26'), False)
    assert [r['worker_id'] for r in selected] == ['30']
    assert selected[0]['effective_point_count'] == 1
    assert source[-1]['effective_point_count'] == 2
    assert selected[0]['imputation_withheld']


def test_q_sensitivity_preserves_count_boundary_and_missing_metrics():
    a, b = geometry([100, 400, 750]), geometry([100, 400, 750], 32)
    pair = gated_pairwise(a, b)
    assert pair['q_boundary'] == 0.9375 and pair['q_wallwall'] == 1
    records = [{'canonical_annotation_id': str(i), 'worker_id': str(i), '_geometry': g}
               for i, g in enumerate((a, b))]
    assert q_partition(records, .95)['cluster_count'] == 2
    assert q_partition(records, .90)['cluster_count'] == 1
    different = geometry([100, 400, 750, 900])
    pair = gated_pairwise(a, different)
    assert pair['metric_compatible'] and pair['q_boundary'] is not None
    assert not pair['pointwise_correspondence_compatible'] and not pair['count_compatible']
    records[1]['_geometry'] = different
    assert q_partition(records, 0.)['cluster_count'] == 2
    invalid = normalize_geometry([[10, 20], [10, 400], [20, 60]])
    missing = gated_pairwise(a, invalid)
    assert missing['q_boundary'] is None and not missing['metric_compatible']
    records.append({'canonical_annotation_id': 'invalid', 'worker_id': 'invalid', '_geometry': invalid})
    result = q_partition(records, .8)
    assert result['valid_k'] == 2
    assert 'invalid' not in sum(json.loads(result['cluster_membership_json']), [])
