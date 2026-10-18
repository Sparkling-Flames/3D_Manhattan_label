from copy import deepcopy

from tools.thesis_main.analysis.worker_annotation_similarity_20261018 import analyze_images


def image():
    points = [[128, 160], [128, 380], [384, 160], [384, 380],
              [640, 160], [640, 380], [896, 160], [896, 380]]
    return dict(image='sample', image_id='sample_id', building='sample', condition='manual',
                records=[dict(id=f'R{i}', object_id=f'object{i}', worker_id=f'W{i}',
                              points=deepcopy(points), source_pair_indices=list(range(4)),
                              ring_confirmed=True, order_status='confirmed', order_used='human_confirmed')
                         for i in range(3)])


def test_different_pair_counts_cannot_share_annotation_structure_cluster():
    source = image()
    extra = source['records'][2]
    extra['points'][2:2] = [[256, 160], [256, 380]]
    extra['source_pair_indices'] = list(range(5))
    pairs, memberships = analyze_images([source])
    unequal = [p for p in pairs if not p['same_pair_count']]
    assert len(unequal) == 2
    assert all(p['structure_bound_cyclic_deg'] is None and not p['structure_available']
               and p['structure_reason'] == 'different_pair_count' for p in unequal)
    for threshold in (6., 9., 12.):
        selected = {r['worker_id']: r for r in memberships
                    if r['method'] == 'annotation_structure_bound_cyclic_complete'
                    and r['threshold'] == threshold}
        assert selected['W0']['cluster_id'] == selected['W1']['cluster_id']
        assert selected['W0']['cluster_id'] != selected['W2']['cluster_id']


def test_original_annotation_analysis_does_not_consume_reference_quality_or_fusion(monkeypatch):
    source = image()
    expected = analyze_images([source])
    source['reference'] = object()
    source['fusion_output'] = object()
    for record in source['records']:
        record.update(B8L2=object(), quality_usable=object(), chosen_target_id=object(),
                      personnel_class=object(), fusion_output=object())

    def forbidden_read(*args, **kwargs):
        raise AssertionError('原作答分析不应另外读取参考或融合文件')

    monkeypatch.setattr('pathlib.Path.read_text', forbidden_read)
    assert analyze_images([source]) == expected
