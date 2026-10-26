"""沿用既有房间用途标签，盘点同类场景研究支持；不拟合或重评分。"""
import gzip
import itertools
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/statistics/room_type_similarity_scoping_20261027'


def make_frame(records, image_metadata):
    images = {i['image_id']: i for i in image_metadata}
    rows = []
    for r in records:
        im = images[r['image_id']]
        room = im.get('room_spatial_classification') or {}
        evidence_room = r['image_evidence'].get('room_spatial_classification') or {}
        assert room == evidence_room, ('room_label_drift', r['image_id'])
        label = room.get('coarse_type')
        layer = 'oos' if r['is_oos'] else 'doorway' if r['is_doorway'] else 'ordinary'
        rows.append({k: r[k] for k in ['object_id', 'image_id', 'image_code', 'worker_id',
                                      'building_id', 'condition', 'quality_usable',
                                      'quality_use', 'B8L2', 'D10', 'current_class']} | {
            'layer': layer, 'room_type': label,
            'room_type_display': label if label else '未记录',
            'room_type_recorded': bool(label),
            'room_type_source': (im.get('room_classification_sources') or {}).get('coarse_type'),
        })
    result = pd.DataFrame(rows)
    assert not result.object_id.duplicated().any()
    return result


def ordinary_quality(frame):
    return frame[frame.quality_usable & frame.quality_use.eq('ordinary_primary')
                 & frame.layer.eq('ordinary') & frame.B8L2.notna()].copy()


def image_quality(frame):
    keys = ['condition', 'image_id', 'image_code', 'building_id',
            'room_type_display', 'current_class']
    return frame.groupby(keys, dropna=False).agg(
        records=('object_id', 'size'), workers=('worker_id', 'nunique'),
        Q_mean=('B8L2', 'mean'), Q_sd=('B8L2', 'std'),
        D10_mean=('D10', 'mean')).reset_index()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz',
                   'rt', encoding='utf-8') as stream:
        records = json.load(stream)['records']
    with gzip.open(ROOT / 'research/data/releases/v2/analysis_input/data.json.gz',
                   'rt', encoding='utf-8') as stream:
        images = json.load(stream)['images']
    frame = make_frame(records, images)

    def save(name, table):
        table.to_csv(OUT / name, index=False, encoding='utf-8-sig')

    save('IMAGE_TYPE_INDEX.csv', frame[['image_id', 'image_code', 'building_id',
         'room_type', 'room_type_display', 'room_type_recorded', 'room_type_source']]
         .drop_duplicates('image_id'))
    coverage = frame.groupby(['condition', 'layer', 'room_type_display'], dropna=False).agg(
        records=('object_id', 'size'), images=('image_id', 'nunique'),
        workers=('worker_id', 'nunique'), buildings=('building_id', 'nunique'),
        formally_quality_usable=('quality_usable', 'sum')).reset_index()
    save('INVENTORY_TYPE_COVERAGE.csv', coverage)
    q = ordinary_quality(frame)
    assert not q.duplicated(['condition', 'image_id', 'worker_id']).any()
    iq = image_quality(q)
    save('ORDINARY_IMAGE_QUALITY.csv', iq)
    summary = iq.groupby(['condition', 'room_type_display']).agg(
        images=('image_id', 'size'), buildings=('building_id', 'nunique'),
        records=('records', 'sum'), Q_image_equal=('Q_mean', 'mean'),
        Q_between_image_sd=('Q_mean', 'std'), Q_within_image_sd_mean=('Q_sd', 'mean'),
        D10_image_equal=('D10_mean', 'mean')).reset_index()
    save('ORDINARY_TYPE_DESCRIPTIVE.csv', summary)
    by_difficulty = iq.groupby(['condition', 'room_type_display', 'current_class']).agg(
        images=('image_id', 'size'), buildings=('building_id', 'nunique'),
        Q_image_equal=('Q_mean', 'mean')).reset_index()
    save('TYPE_DIFFICULTY_DESCRIPTIVE.csv', by_difficulty)
    support = q.groupby(['condition', 'worker_id', 'room_type_display']).agg(
        records=('object_id', 'size'), images=('image_id', 'nunique'),
        buildings=('building_id', 'nunique')).reset_index()
    save('WORKER_TYPE_SUPPORT.csv', support)
    worker_support = support.groupby(['condition', 'room_type_display']).agg(
        workers=('worker_id', 'size'),
        workers_at_least_3_images=('images', lambda x: int((x >= 3).sum())),
        workers_at_least_2_buildings=('buildings', lambda x: int((x >= 2).sum()))).reset_index()
    save('WORKER_TYPE_SUPPORT_SUMMARY.csv', worker_support)
    pair_rows = []
    for (condition, room_type), group in q.groupby(['condition', 'room_type_display']):
        cells = {iid: g for iid, g in group.groupby('image_id')}
        pairs = []
        for a, b in itertools.combinations(cells, 2):
            ga, gb = cells[a], cells[b]
            if ga.building_id.iloc[0] == gb.building_id.iloc[0]:
                continue
            common = len(set(ga.worker_id) & set(gb.worker_id))
            pairs.append((common, ga.current_class.iloc[0] == gb.current_class.iloc[0]))
        pair_rows.append(dict(condition=condition, room_type_display=room_type,
            cross_building_image_pairs=len(pairs),
            pairs_common_workers_ge4=sum(n >= 4 for n, _ in pairs),
            pairs_common_workers_ge4_same_difficulty=sum(n >= 4 and same for n, same in pairs)))
    save('CROSS_BUILDING_PAIR_SUPPORT.csv', pd.DataFrame(pair_rows))
    receipt = dict(version='room_type_similarity_scoping_20261027',
        inventory_records=len(frame), inventory_images=frame.image_id.nunique(),
        ordinary_quality_records=len(q), ordinary_quality_images=q.image_id.nunique(),
        ordinary_by_condition=q.groupby('condition').agg(
            records=('object_id', 'size'), images=('image_id', 'nunique'),
            workers=('worker_id', 'nunique'), buildings=('building_id', 'nunique')).reset_index().to_dict('records'),
        image_label_source='research/data/releases/v2/analysis_input/data.json.gz#images',
        score_source='research/statistics/v2_evidence_audit_20261019/records.json.gz',
        label_checks='Every observed image room classification agrees with frozen v2 evidence.',
        analysis='Coverage and descriptive image-equal means only; no correlation, prediction, p-value, fusion or relabeling.',
        missing_label_policy='Unrecorded stays unrecorded; literal 无法判断 retained separately.',
        cross_building_pair_policy='Capacity count only; overlapping pairs are not independent samples.')
    (OUT / 'SCOPE_CHECK.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=True))


if __name__ == '__main__':
    main()
