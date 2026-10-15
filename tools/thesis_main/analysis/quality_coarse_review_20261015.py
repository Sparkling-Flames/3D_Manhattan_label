"""WQ粗核验：32普通后12门洞；固定抽样与原几何，不调参、不改资格。"""
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import ARCHIVE, module
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality/quality_coarse_review_20261015'
TABLE = ROOT / 'research/quality/quality_joint_closeout_review_20261015/JOINT_COMPARISON_1145.csv'
SCHEMA = 'quality_coarse_review_20261015_v1'


def select_rows():
    frame = pd.read_csv(TABLE)
    previous = json.loads((ROOT / 'research/quality/quality_candidate_review_20261014/manifest.json').read_text(encoding='utf-8'))
    old_images = {b['image_id'] for c in previous['cards'] for b in c['bindings']}
    pool = frame[(frame.role == 'manual_development_candidate') & (frame.score_status == 'full') &
                 ~frame.same_target_quality_hold & ~frame.original_holdout & ~frame.image_id.isin(old_images)].copy()
    pool['sampling_quartile'] = pd.qcut(pool.WQ.rank(method='first'), 4, labels=False)
    rng = np.random.default_rng(20261015)
    chosen = []; used_images = set()
    for band in range(4):
        group = pool[pool.sampling_quartile == band].iloc[rng.permutation((pool.sampling_quartile == band).sum())]
        count = 0
        for _, row in group.iterrows():
            if row.image_id in used_images: continue
            chosen.append(dict(row, phase='ordinary', selection='score_coverage'))
            used_images.add(row.image_id); count += 1
            if count == 6: break
        assert count == 6
    # 另外四图各取一对：预先固定指标反序压力例，不混称随机代表样本。
    pairs = []
    for image, group in pool[~pool.image_id.isin(used_images)].groupby('image_id'):
        for ref, group_ref in group.groupby('reference_id'):
            records = list(group_ref.to_dict('records'))
            for i, a in enumerate(records):
                for b in records[i+1:]:
                    w, j = a['WQ']-b['WQ'], a['IoU3D100']-b['IoU3D100']
                    if w*j < 0 and min(abs(w), abs(j)) >= 5:
                        pairs.append((min(abs(w), abs(j)), a['record_id'], b['record_id'], a, b))
    pair_images = set()
    for _, _, _, a, b in sorted(pairs, key=lambda v: (-v[0], v[1], v[2])):
        if a['image_id'] in pair_images: continue
        for r in (a, b): chosen.append(dict(r, phase='ordinary', selection='metric_disagreement'))
        pair_images.add(a['image_id'])
        if len(pair_images) == 4: break
    assert len(chosen) == 32
    # 普通显示顺序不按分数或抽样类型排列，避免题序暗示预期档位。
    chosen = [chosen[i] for i in rng.permutation(len(chosen))]
    door = frame[(frame.score_status == 'conditional_full') & ~frame.same_target_quality_hold &
                 ~frame.original_holdout].sort_values(['image_id', 'WQ', 'record_id'])
    picked = []
    for image, group in door.groupby('image_id'):
        picked.append(group.iloc[int(rng.integers(len(group)))].to_dict())
    assert len(picked) == 10
    remaining = door[~door.record_id.isin([r['record_id'] for r in picked])]
    for rank in (0, len(remaining)-1):
        picked.append(remaining.sort_values(['WQ', 'record_id']).iloc[rank].to_dict())
    chosen += [dict(picked[i], phase='doorway', selection='doorway_image_coverage') for i in rng.permutation(len(picked))]
    result = pd.DataFrame(chosen)
    assert result.record_id.is_unique and len(result) == 44
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'photos').mkdir(exist_ok=True)
    rows = select_rows()
    bundle = load_current_bundle()
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    geometry = module(ARCHIVE / 'routing/prepare_inputs.py', 'coarse_review_geometry').geometry
    geometries = {}; cards = []; scores = {}; counters = {'ordinary': 0, 'doorway': 0}
    for _, r in rows.iterrows():
        counters[r.phase] += 1
        case = ('N' if r.phase == 'ordinary' else 'D') + f'{counters[r.phase]:02d}'
        for oid in (r.object_id, r.reference_id):
            obj = objects[oid]
            points = obj['points_1024x512']
            geometries[oid] = dict(geometry(points), points_1024x512=points)
            assert obj['image_id'] == r.image_id
        paths = [ROOT / 'data/mp3d_layout' / split / 'img' / (r.image_id+'.png') for split in ('train', 'valid', 'test')]
        photo = next((p for p in paths if p.is_file()), None)
        if photo is None: raise FileNotFoundError(r.image_id)
        shutil.copyfile(photo, OUT / 'photos' / photo.name)
        binding = dict(label='本份标注', record_id=r.record_id, object_id=r.object_id,
                       image_id=r.image_id, image_code=r.image_code, reference_object_id=r.reference_id,
                       reference_binding=r.reference_binding, score_status=r.score_status,
                       same_target_unconfirmed=bool(r.same_target_unconfirmed),
                       same_target_quality_hold=bool(r.same_target_quality_hold),
                       photo='photos/' + photo.name)
        cards.append(dict(id=case, phase=r.phase, bindings=[binding]))
        scores[case] = dict(WQ=float(r.WQ), IoU3D100=float(r.IoU3D100))
    manifest = dict(schema=SCHEMA, model='WQ-LS08-20261014', cards=cards,
                    counts=counters, score_hidden_initially=True,
                    exposure='development_coarse_review_not_independent_validation',
                    grade_scale='five_level_transition_v1',
                    grades=['good', 'good_average', 'average', 'average_poor', 'poor', 'scope', 'uncertain'])
    for name, data in [('manifest.json', manifest), ('geometries.json', geometries), ('scores.json', scores)]:
        (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    rows.drop(columns=['sampling_quartile']).to_csv(OUT / 'selection_provenance.csv', index=False, encoding='utf-8-sig')
    (OUT / 'data.js').write_text('const DATA='+json.dumps(manifest, ensure_ascii=False)+';\nconst GEOMETRIES='+json.dumps(geometries)+';\nconst SCORES='+json.dumps(scores)+';\n', encoding='utf-8')
    for original, name in [('quality_coarse_review_20261015.html', 'REVIEW.html'), ('quality_coarse_review_20261015.js', 'app.js')]:
        shutil.copyfile(Path(__file__).with_name(original), OUT / name)
    for name in ['geometry-core.js', 'viewer3d.js']:
        shutil.copyfile(ROOT / 'research/quality/quality_candidate_review_20261014' / name, OUT / name)
    print(f'准备完成：{len(cards)}份，普通32、门洞12；只复制所需原图、不缩图，几何及分数不变。')


if __name__ == '__main__':
    main()
