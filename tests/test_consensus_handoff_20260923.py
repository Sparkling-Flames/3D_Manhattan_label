"""先行数值表不得通过缺失GT或表示失败缩小分母。"""
import csv
import json

from tools.thesis_main.analysis import build_consensus_handoff_20260923 as build


def test_numeric_keeps_collection_denominators_and_missing_gt(tmp_path):
    pairs = [[[x, 160], [x, 350]] for x in [100, 350, 600, 850]]
    rows = []
    for image, cid, worker, geometry, borrowed in [
        ('mixed', 'a', 'W1', pairs, False),
        ('mixed', 'b', 'W2', None, False),
        ('mixed', 'c', 'W3', pairs, True),
        ('invalid', 'd', 'W1', None, False),
        ('duplicate', 'e', 'W1', pairs, False),
        ('duplicate', 'f', 'W1', pairs, False),
    ]:
        rows.append(dict(image_id=image, canonical_annotation_id=cid, worker_id=worker,
                         building_id='B', raw_condition='manual', accepted_before_new_review=True,
                         pairs_shared_x=geometry, imputed_point=borrowed, known_wrong=False))
    references = {
        image: dict(code=image, manual_gt_changed=False, references=[
            dict(name='gt_original', pairs_shared_x=pairs, pairing_status='ok'),
            dict(name='gt_revised', pairs_shared_x=None, pairing_status='missing')])
        for image in ['mixed', 'invalid', 'duplicate']
    }
    build.write_json(tmp_path/'inputs/annotations.jsonl.gz', rows, lines=True)
    build.write_json(tmp_path/'inputs/references.json.gz', references)
    report = build.numeric(tmp_path, methods=['mv50'])
    assert report['quality_rows'] == len(rows)*2*2
    assert report['endpoint_rows'] == len(references)*2

    def read(name):
        with (tmp_path/name).open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))

    quality = read('individual_quality.csv')
    assert all(r['status'] == 'not_evaluable' and not r['iou']
               for r in quality if r['gt_version'] == 'gt_revised')
    assert all(r['status'] == 'not_evaluable' for r in quality
               if r['canonical_annotation_id'] in ['b','d'])
    endpoint = read('endpoint_pilot.csv')
    mixed = next(r for r in endpoint if r['image_id']=='mixed' and r['gt_version']=='gt_original')
    assert mixed['k']=='3' and mixed['used_k']=='1' and mixed['status']=='ok'
    assert json.loads(mixed['member_ids']) == ['a','b','c']
    assert json.loads(mixed['used_member_ids']) == ['a']
    assert float(mixed['iou']) == 1
    for row in endpoint:
        if row['image_id']=='invalid':
            assert row['status']=='not_evaluable' and 'no_eligible_members' in row['reason']
        if row['image_id']=='duplicate':
            assert row['k']=='1' and row['used_k']=='0'
            assert 'repeated_worker_requires_resolution' in row['reason']
