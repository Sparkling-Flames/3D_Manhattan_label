"""既有直接同房关系与共同人员的描述统计；不新增房间判断或融合实验。"""
import json
import math
from collections import defaultdict
from statistics import mean, median, stdev

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from .same_room_similarity_20261003 import relation_index

METRICS = ('WQ', 'A10', 'B8L2', 'iou_3d', 'active_time_seconds')
PROVENANCE = ('object_uid', 'reference_id', 'score_version', 'use_panel')


def _value(row, metric):
    value = row.get(metric)
    if value is None or value == '':
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _summary(values):
    """四分位数使用线性插值，与pandas默认口径一致；SD为样本SD。"""
    values = sorted(values)
    if not values:
        return dict(n=0, mean=None, median=None, sd=None, q25=None, q75=None, iqr=None)
    def quantile(p):
        position = (len(values) - 1) * p
        lower = int(position)
        return values[lower] + (values[min(lower+1, len(values)-1)] - values[lower]) * (position-lower)
    q25, q75 = quantile(.25), quantile(.75)
    return dict(n=len(values), mean=mean(values), median=median(values),
                sd=stdev(values) if len(values) > 1 else None,
                q25=q25, q75=q75, iqr=q75-q25)


def build_same_room_tables(records):
    """输入固定评分面板的作答列表；同人同图重复必须由调用方按条件/版本拆分。

    必需字段：object_uid、image_id、worker_id。METRICS中的None/NaN为空缺。
    iou_3d为0—1均高棱柱IoU，active_time_seconds为已核实的有效时间秒。
    reference_id/score_version/use_panel逐侧保留；用途不同不授予可比资格。
    返回关系台账、图对逐指标统计和共同人员逐指标明细三个list[dict]。
    """
    bundle = load_current_bundle()
    data = bundle['data']
    relations = relation_index(data['room_registry']['candidates'])
    images = {r['image_id']: r for r in data['images']}
    metadata = {}
    for row in data['room_registry'].get('images', []):
        building, number = row.get('building'), row.get('number')
        metadata[row['image_id']] = dict(
            building_id=building, image_code=f'{building}-{number:02d}'
            if building is not None and number is not None else None,
            source='room_registry.images')
    for source, rows in (('data.images', data['images']),
                         ('research.images', bundle.get('research', {}).get('images', []))):
        for row in rows:
            target = metadata.setdefault(row['image_id'], {'source': source})
            for field in ('building_id', 'image_code'):
                if row.get(field) is not None:
                    if target.get(field) is not None and target[field] != row[field]:
                        raise ValueError(f'image metadata mismatch: {row["image_id"]}, {field}')
                    target[field] = row[field]
    by_image = defaultdict(dict)
    seen_objects = set()
    for record in records:
        image, worker, uid = record['image_id'], record['worker_id'], record['object_uid']
        if image not in images:
            raise ValueError(f'unknown image_id: {image}')
        if uid in seen_objects or worker in by_image[image]:
            raise ValueError(f'duplicate object or image-worker: {uid}, {image}, {worker}')
        seen_objects.add(uid)
        by_image[image][worker] = record
    tables = {name: [] for name in ('same_room_relations', 'same_room_pair_metrics',
                                   'same_room_worker_pairs')}
    for (a, b), relation in sorted(relations.items()):
        left, right = by_image[a], by_image[b]
        common = sorted(left.keys() & right.keys())
        base = dict(image_a=a, image_b=b, relation=relation['tier'],
                    candidate_ids='|'.join(relation['candidates']))
        evidence = relation['evidence']
        ledger = dict(**base, building_a=metadata.get(a, {}).get('building_id') or 'unknown',
                      building_b=metadata.get(b, {}).get('building_id') or 'unknown',
                      image_code_a=metadata.get(a, {}).get('image_code') or 'unknown',
                      image_code_b=metadata.get(b, {}).get('image_code') or 'unknown',
                      image_metadata_source_a=metadata.get(a, {}).get('source', 'unknown'),
                      image_metadata_source_b=metadata.get(b, {}).get('source', 'unknown'),
                      n_records_a=len(left), n_records_b=len(right), n_common_workers=len(common),
                      n_only_a=len(left)-len(common), n_only_b=len(right)-len(common),
                      physical_same_supported=any(e['physical_same_supported'] for e in evidence),
                      physical_same_explicit_confirmed=any(e['physical_same_supported'] and
                          e['review_state'] == 'explicit_confirmed' for e in evidence),
                      evidence_json=json.dumps(evidence, ensure_ascii=False, sort_keys=True))
        for side, pool in (('a', left), ('b', right)):
            for field in ('reference_id', 'score_version', 'use_panel'):
                ledger[field+'s_'+side] = '|'.join(sorted({str(r[field]) for r in pool.values()
                                                         if r.get(field) is not None}))
        tables['same_room_relations'].append(ledger)
        base.update({k: v for k, v in ledger.items() if k.startswith(
            ('building_', 'image_code_', 'image_metadata_source_', 'reference_ids_',
             'score_versions_', 'use_panels_'))})
        for metric in METRICS:
            observed_a = [_value(r, metric) for r in left.values()]
            observed_b = [_value(r, metric) for r in right.values()]
            paired = []
            common_values_a, common_values_b = [], []
            for worker in common:
                x, y = _value(left[worker], metric), _value(right[worker], metric)
                if x is not None:
                    common_values_a.append(x)
                if y is not None:
                    common_values_b.append(y)
                row = dict(**base, metric=metric, worker_id=worker, value_a=x, value_b=y,
                           paired=x is not None and y is not None,
                           delta_b_minus_a=y-x if x is not None and y is not None else None)
                for field in PROVENANCE:
                    row[field+'_a'], row[field+'_b'] = left[worker].get(field), right[worker].get(field)
                tables['same_room_worker_pairs'].append(row)
                if row['paired']:
                    paired.append((x, y))
            result = dict(**base, metric=metric, n_records_a=len(left), n_records_b=len(right),
                          n_common_workers=len(common), n_pairs=len(paired),
                          n_missing_all_a=sum(v is None for v in observed_a),
                          n_missing_all_b=sum(v is None for v in observed_b),
                          n_missing_common_a=len(common)-len(common_values_a),
                          n_missing_common_b=len(common)-len(common_values_b),
                          n_unpaired_common=len(common)-len(paired))
            for label, values in (
                ('all_a', [v for v in observed_a if v is not None]),
                ('all_b', [v for v in observed_b if v is not None]),
                ('paired_a', [x for x, y in paired]), ('paired_b', [y for x, y in paired]),
                ('delta_b_minus_a', [y-x for x, y in paired]),
                ('absolute_paired_delta', [abs(y-x) for x, y in paired])):
                result.update({label+'_'+k: v for k, v in _summary(values).items()})
            tables['same_room_pair_metrics'].append(result)
    return tables
