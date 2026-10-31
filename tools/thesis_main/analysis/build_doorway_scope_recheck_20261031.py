"""Build quality-blind additional review; never mutate adopted pools."""
import gzip
import json
import os
import zipfile
from pathlib import Path
from tools.thesis_main.analysis.supplement_doorway_preparation_20261031 import floor

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/data/doorway_review_20261030'
OUT = BASE / 'scope_recheck_20261031'
SELECTION = {
    3: '走廊远端与近处门框混合：是否仍能形成空间1的合理主体？',
    5: '远端只有一对点，其余集中在近处门框：是否遗漏了主体墙角？',
    6: '远端只有一对点，底面呈狭长三角形：是否只是局部门框加远处点？',
    17: '四对点主要集中在右侧门柱附近，没有覆盖两侧房间主体；原空间2归属值得质疑。',
    20: '像是走廊的一个分支：可接受的单侧范围，还是不足以代表当前空间1？',
    22: '与同图W036近似；作为边界案例保留判断空间，不能仅因不覆盖完整参考而排除。',
    24: '远处走廊点与近处门框点形成狭长底面：漏了主墙角，还是合理走廊范围？',
    26: '门框附近多点聚集，主体呈狭长形：请判断是否保留。',
    37: '只覆盖影音室内部的一部分：合理可见范围，还是主体缺失？',
    41: '影音室局部点混入另一侧门框，未清楚形成任一完整主体。',
    44: '洗衣房一侧只覆盖局部分支：可否视为空间2的有效表达？',
    46: '卧室主体之外夹带洗衣房孤立点：仍保留为空间1，还是作为混杂作答排除？',
}
COMPARISONS = ['v2:new:100174', 'v2:new:100388', 'v2:new:102060', 'v2:new:102698']

def main(batch40=False):
    out = BASE / 'scope_recheck40_20261031' if batch40 else OUT
    read = lambda p: json.loads(p.read_text(encoding='utf8'))
    candidates = read(out / 'CANDIDATES.json')
    selection = {int(k): v for k, v in read(out / 'VISUAL_REASONS.json').items()} if batch40 else SELECTION
    ledger = {r['object_id']: r for r in read(BASE / 'pro_delivery_independent_audit_20261031/CORRECTED_RECORD_LEDGER.json')}
    cases = {c['image']: c for c in json.loads((BASE / 'data.js').read_text(encoding='utf8').split('=', 1)[1].rstrip().removesuffix(';'))['cases']}
    align = {r['image']: r for r in read(BASE / 'curve_preparation_v21/full_review_20261031/ALIGNMENT_DECISIONS.json')}
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
        frozen = json.loads(gzip.decompress(z.read('HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz')))
    items = []
    for r, reason, comparison in [(candidates[i], reason, False) for i, reason in selection.items()] + ([] if batch40 else [(ledger[i], '历史已排除实例，仅作标准对照，不在本轮重新裁决。', True) for i in COMPARISONS]):
        points = frozen[r['object_id']]['points']
        photo = (BASE / cases[r['image']]['photo']).resolve()
        assert photo.exists() and len(points) >= 6 and len(points) % 2 == 0
        if not comparison:
            assert r['base_candidate'] and not r['protected_adjudication']
            if not batch40:
                assert r['final_scope'] in ['空间1', '空间2']
        items.append(dict(object_id=r['object_id'], image=r['image'], worker=r['worker'], previous_scope=r['final_scope'], first_review=r['first_reviewer_quality'], reason=reason, comparison=comparison,
                          photo=os.path.relpath(photo, out).replace('\\', '/'), points=points, floor=floor(points), spaces=align[r['image']]['space_polygons']))
    assert len({r['object_id'] for r in items}) == (40 if batch40 else 16)
    if batch40:
        prior = read(OUT / 'USER_REVIEW_RECEIVED.json')['decisions']
        assert not {r['object_id'] for r in items}.intersection(prior)
        assert not {r['object_id'] for r in items}.intersection({'v2:new:100168', 'v2:new:100176', 'v2:new:100741'})
    config = 'const reviewConfig = ' + json.dumps({'key':'doorway-scope-eligibility-recheck40-20261031-v1','filename':'门洞追加40份复核_20261031.json','inferEligibility':True}, ensure_ascii=False) + ';\n' if batch40 else ''
    (out / 'review-data.js').write_text(config + 'const reviewItems = ' + json.dumps(items, ensure_ascii=False) + ';\n', encoding='utf8')
    print(f'{len(items)} records validated; points and final cuts bound; curves unchanged')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch40', action='store_true')
    main(parser.parse_args().batch40)
