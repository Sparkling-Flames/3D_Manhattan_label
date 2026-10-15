"""只审计难度与质量参考的绑定，不读取Q或调整分类。"""
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/difficulty_coarse_closeout_20261014'
SOURCE = ROOT / 'analysis_results/difficulty_scope_preferred_20261011/current_259.json'
QUALITY = ROOT / 'research/quality_pro_handoff_20261014/quality_pro_handoff_20261014_READY.zip'


def same_floor(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape:
        return False
    return any(np.allclose(a, np.roll(c, k, axis=0), atol=1e-8, rtol=0)
               for c in (b, b[::-1]) for k in range(len(b)))


def floor(points):
    p = np.asarray(points, dtype=float)[1::2]
    u, v = (p[:, 0] / 1024 - .5) * 2 * np.pi, (p[:, 1] / 512 - .5) * np.pi
    assert np.all(v > 0), 'reference bottom above horizon'
    return np.column_stack((np.sin(u) / np.tan(v), -np.cos(u) / np.tan(v)))


def relation(d, ref, objects):
    if d is None:
        return 'image_not_in_difficulty'
    if not ref:
        return 'reference_missing'
    if ref not in objects:
        return 'reference_not_in_package'
    obj = objects[ref]
    assert obj['image_id'] == d['image_id'], 'reference image binding mismatch'
    equal = same_floor(d['selected']['floor'], floor(obj['points_1024x512']))
    if ref == d['target_version']:
        return 'same_id_same_floor' if equal else 'same_id_geometry_drift'
    return 'different_id_same_floor_only' if equal else 'different_floor'


def save(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    # 只允许环起点和方向等价，不通过简化、拟合或最高Q选择参考。
    p = [[1, 0], [0, 1], [-1, 0], [0, -1]]
    assert same_floor(p, p[2:]+p[:2]) and same_floor(p, p[::-1])
    assert not same_floor(p, [[2, 0], [0, 1], [-1, 0], [0, -1]])
    obj = dict(image_id='test', points_1024x512=[[x,y] for x in (128,384,640,896) for y in (150,350)])
    d = dict(image_id='test',target_version='a',selected=dict(floor=floor(obj['points_1024x512'])))
    assert relation(d,'a',{'a':obj}) == 'same_id_same_floor'
    assert relation(d,'b',{'b':obj}) == 'different_id_same_floor_only'
    assert relation(d,None,{}) == 'reference_missing'
    assert relation(d,'c',{}) == 'reference_not_in_package'
    d['selected']['floor'] = d['selected']['floor'] * 2
    assert relation(d,'b',{'b':obj}) == 'different_floor'
    assert relation(d,'a',{'a':obj}) == 'same_id_geometry_drift'
    doc = json.loads(SOURCE.read_text(encoding='utf-8'))
    rows = doc['records']; by = {r['image_id']: r for r in rows}
    assert len(rows) == len(by) == 259
    assert Counter(r['current_class'] for r in rows) == {'简单':144,'中等':30,'困难':38,'待复核':5,'单列':42}
    with zipfile.ZipFile(QUALITY) as z:
        cohorts = json.loads(z.read('data/cohorts.json'))
        objects = {r['object_id']: r for r in json.loads(z.read('data/objects.json'))['objects']}
    bindings = []
    for cohort in ('ordinary', 'severe', 'doorway'):
        for r in cohorts[cohort]:
            d = by.get(r['image_id'])
            ref = r['reference_object_id'] if cohort != 'doorway' else (r['reference'] or {}).get('object_id')
            rel = relation(d, ref, objects)
            bindings.append(dict(cohort=cohort, record_id=r['record_id'], image_id=r['image_id'],
                image=d['image'] if d else r.get('image_code',''),
                difficulty_class=d['current_class'] if d else '', difficulty_version=doc['version'],
                difficulty_target_id=d['target_version'] if d else '', quality_reference_id=ref or '',
                target_relation=rel, quality_status=r.get('status','existing_cohort'),
                ordinary_three_class_candidate=bool(d and d['current_class'] in ('简单','中等','困难')
                    and cohort=='ordinary' and rel=='same_id_same_floor'),
                eligibility_granted=False))
    assert len(bindings) == len({r['record_id'] for r in bindings}) == 800
    fusion = []
    for p in sorted((ROOT/'analysis_results/consensus_delivery_20261008').glob('*.json')):
        r = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(r, dict) or not all(k in r for k in ('image_id','automatic','assisted')):
            continue
        d = by.get(r['image_id'])
        fusion.append(dict(image_id=r['image_id'],image=r['image'],difficulty_class=d['current_class'] if d else '',
            difficulty_target_id=d['target_version'] if d else '',difficulty_version=doc['version'],
            fusion_source=str(p.relative_to(ROOT)).replace('\\','/'),
            target_relation='evaluation_reference_not_declared' if d else 'image_not_in_difficulty',
            reference_alignment_confirmed=False))
    OUT.mkdir(exist_ok=True)
    save('quality_target_bindings.csv',bindings)
    save('quality_target_unmatched.csv',[r for r in bindings if r['target_relation']!='same_id_same_floor'])
    save('fusion_target_bindings.csv',fusion)
    quality_ids = {r['image_id'] for r in bindings}
    save('quality_image_coverage.csv',[dict(image=r['image'],image_id=r['image_id'],
        target_version=r['target_version'],current_class=r['current_class'],
        has_accepted_alternative=len(r['candidates'])>1,
        in_quality_ready_package=r['image_id'] in quality_ids,
        quality_record_count=sum(x['image_id']==r['image_id'] for x in bindings)) for r in rows])
    save('difficulty_targets.csv',[dict(image=r['image'], image_id=r['image_id'],difficulty_version=doc['version'],
        target_version=r['target_version'],current_class=r['current_class'],conditional_difficulty=r['conditional_difficulty'],
        N_turn=r['N_turn'],H=r['H'],inference_burden=r['inference_burden'],scene=r['scene'],
        evidence=r['evidence'],details='../../analysis_results/difficulty_scope_preferred_20261011/current_259.json',
        review='../../analysis_results/difficulty_scope_preferred_20261011/review.html') for r in rows])
    summary=dict(version=doc['version'],source=str(SOURCE.relative_to(ROOT)),quality_package=str(QUALITY.relative_to(ROOT)),
        classifications=dict(Counter(r['current_class'] for r in rows)),
        quality_records=len(bindings),quality_images=len({r['image_id'] for r in bindings}),
        quality_relations=dict(Counter(r['target_relation'] for r in bindings)),
        ordinary_three_class_candidate_records=sum(r['ordinary_three_class_candidate'] for r in bindings),
        ordinary_three_class_candidate_images=len({r['image_id'] for r in bindings if r['ordinary_three_class_candidate']}),
        difficulty_images_absent_from_quality=sum(r['image_id'] not in quality_ids for r in rows),
        accepted_alternative_images_in_quality=sum(len(r['candidates'])>1 and r['image_id'] in quality_ids for r in rows),
        fusion_records=len(fusion),fusion_relations=dict(Counter(r['target_relation'] for r in fusion)),
        classification_changed=False,eligibility_changed=False,quality_scores_read=False,
        test='cyclic/reversed floor equivalence and changed-coordinate rejection; unique bindings and frozen counts')
    (OUT/'CHECKS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == '__main__':
    main()
