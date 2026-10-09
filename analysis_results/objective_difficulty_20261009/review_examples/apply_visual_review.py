"""将固定的看图裁决应用于粗分类使用表；保留自动结构字段和特殊组状态。"""
import csv
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent


def main():
    source = OUT / 'score_recheck.csv'
    original = source.read_bytes()
    rows = list(csv.DictReader(original.decode('utf-8-sig').splitlines()))
    receipt = json.loads((OUT / 'six_pair_visual_review_20261010.json').read_text(encoding='utf-8'))
    reviews = {r['image_id']: r for r in receipt['records']}
    assert len(reviews) == len(receipt['records']) == 39
    changes = []
    for row in rows:
        ordinary = row['difficulty_status'] == 'provisional_structure_proxy'
        row['working_difficulty_class'] = row['existing_coarse_class'] if ordinary else ''
        row['classification_basis'] = 'legacy_structure_proxy' if ordinary else 'separate_or_pending'
        row['visual_review_reason'] = ''
        r = reviews.get(row['image_id'])
        if r:
            assert row['gt_object_id'] == r['gt_object_id']
            assert int(row['N']) == r['N'] == 6 and int(row['H']) == r['H']
            assert row['existing_coarse_class'] == r['previous_class']
            row['visual_review_reason'] = r['reason']
            if r['decision'] == 'simple':
                assert ordinary and r['H'] == 0
                assert r['visual_occlusion'] in ('none', 'limited_local')
                row['working_difficulty_class'] = '简单'
                row['classification_basis'] = 'codex_photo_review_20261010'
                changes.append(row['image'])
    assert len(rows) == len({r['image_id'] for r in rows}) == 259
    assert len(changes) == 6 and source.read_bytes() == original
    assert all(not r['working_difficulty_class'] for r in rows if r['difficulty_status'] != 'provisional_structure_proxy')
    with (OUT / 'working_classification_20261010.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    result = dict(changed=changes, classes=dict(Counter(r['working_difficulty_class'] or '单列或待定' for r in rows)))
    (OUT / 'working_classification_20261010_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
