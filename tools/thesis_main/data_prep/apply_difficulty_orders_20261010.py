"""接收三份固定点对排序回执；原坐标、配对和资格不变。"""
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REVIEW = ROOT / 'analysis_results/image_difficulty_full_review_20261010/user_review_20261010'
REVISION = 'difficulty_orders_20261010_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def apply_data(data, receipt=None):
    from tools.thesis_main.analysis.final_review_summary_20260929 import geometry_status
    from tools.thesis_main.analysis.receive_order_review_20260928 import validate_return
    receipt = read(REVIEW / 'confirmed_orders.json') if receipt is None else receipt
    sources = {s['object_id']: s for s in read(REVIEW / 'order_workbench/sources.json')['objects']}
    audit = {s['object_id']: s for s in read(REVIEW / 'order_audit.json')['records']}
    if receipt['schema'] != 'difficulty_individual_order_20261010_v1' or receipt['examples_only'] is not False or set(receipt['records']) != set(sources):
        raise ValueError('order_receipt_population_or_schema')
    objects = {o['object_id']: o for o in data['objects']}
    converted = {}
    for oid, r in receipt['records'].items():
        s, o = sources[oid], objects[oid]
        expected = dict(id=oid, points=s['points'], labels=s['effective_point_labels'], links=s['links_zero_based'], preprocessing=s['preprocessing'])
        if json.loads(r['binding']) != expected or r['status'] != 'confirmed':
            raise ValueError('frozen_order_binding_or_status:' + oid)
        order = r['order']
        if any(type(i) is not int for i in order) or sorted(order) != list(range(len(s['links_zero_based']))):
            raise ValueError('order_permutation:' + oid)
        indices = audit[oid]['ordered_source_point_indices']
        if o['object_kind'] != 'annotation' or o['image_id'] != s['image_id'] or o['worker_id'] != s['worker_id'] or o['source'] != s['provenance']:
            raise ValueError('order_source_identity:' + oid)
        if [o['preprocessed_points'][i] for i in indices] != s['points']:
            raise ValueError('order_coordinate_drift:' + oid)
        frozen_pairs = [indices[i:i+2] for i in range(0, len(indices), 2)]
        canonical_order = [o['links_zero_based'].index(frozen_pairs[i]) for i in order]
        binding = dict(id=oid, points=o['preprocessed_points'], labels=o['point_labels'], links=o['links_zero_based'], preprocessing=o['preprocessing'])
        converted[oid] = dict(r, binding=json.dumps(binding, ensure_ascii=False), order=canonical_order)
    validate_return(dict(schema='order_review_20260928_v3', examples_only=False, records=converted), objects)
    for oid, record in converted.items():
        o = objects[oid]
        indices = [i for pair in record['order'] for i in o['links_zero_based'][pair]]
        o.update(ordered_source_pair_indices=record['order'], ordered_source_point_indices=indices,
                 ordered_source_point_labels=[o['point_labels'][i] for i in indices],
                 points_1024x512=[o['preprocessed_points'][i] for i in indices],
                 order_record=record, ring_confirmed=True, order_status='human_confirmed')
        o['order_origins'] = [REVISION]
        o['order_review_provenance'] = dict(source=(REVIEW/'confirmed_orders.json').relative_to(ROOT).as_posix(), revision=REVISION)
        o['geometry'] = geometry_status(o, record['order'])
        o['final_review'].update(order_state='human_confirmed', order_change='user_confirmed_adjacency_changed',
                                 geometry_status=o['geometry']['status'], geometry_issues=o['geometry']['issues'])
    data['summary']['confirmed_orders'] = sum(o['ring_confirmed'] for o in data['objects'])
    data['order_update_revision'] = REVISION
    for im in data['images']:
        group = [o for o in data['objects'] if o['image_id'] == im['image_id'] and o['object_kind'] == 'annotation']
        if any(o['object_id'] in converted for o in group):
            im['order_counts'] = dict(Counter(o['order_status'] for o in group))
            im['geometry_counts'] = dict(Counter(o['geometry']['status'] for o in group))
    return data


def apply_bundle(loaded):
    data = apply_data(loaded['data'])
    objects = {o['object_id']: o for o in data['objects']}
    changed = {oid for oid, o in objects.items() if o.get('order_review_provenance', {}).get('revision') == REVISION}
    research = loaded['research']
    for r in research['annotations']:
        if r['object_id'] in changed:
            o = objects[r['object_id']]
            r.update(order_status=o['order_status'], geometry_status=o['geometry']['status'],
                     geometry_issues=o['geometry']['issues'], order_change='user_confirmed_adjacency_changed',
                     order_change_evidence=copy.deepcopy(o['order_review_provenance']))
    for im in research['images']:
        group = [r for r in research['annotations'] if r['image_id'] == im['image_id']]
        if any(r['object_id'] in changed for r in group):
            im['order_counts'] = dict(Counter(r['order_status'] for r in group))
            im['geometry_counts'] = dict(Counter(r['geometry_status'] for r in group))
    table = research['cross_tables']['order_changes_by_kind']
    for r in table:
        r['ids'] = [oid for oid in r['ids'] if oid not in changed]
        r['n'] = len(r['ids'])
    research['cross_tables']['order_changes_by_kind'] = [r for r in table if r['n']] + [dict(dimensions=dict(object_kind='annotation', change='user_confirmed_adjacency_changed'), n=len(changed), ids=sorted(changed))]
    table = research['cross_tables']['order_representation']
    fields = list(table[0]['dimensions'])
    included = {oid for row in table for oid in row['ids']}
    groups = defaultdict(list)
    for r in research['annotations']:
        if r['object_id'] in included:
            groups[tuple(r[k] for k in fields)].append(r['object_id'])
    research['cross_tables']['order_representation'] = [dict(dimensions=dict(zip(fields, k)), n=len(v), ids=v) for k, v in sorted(groups.items())]
    research['summary']['confirmed_order_objects'] = data['summary']['confirmed_orders']
    research['order_update_revision'] = REVISION
    anns = [o for o in data['objects'] if o['object_kind'] == 'annotation']
    loaded['final_summary'].update(confirmed_orders=data['summary']['confirmed_orders'],
        geometry=dict(Counter(o['geometry']['status'] for o in anns)),
        current_order_status_counts=dict(Counter(o['order_status'] for o in anns)), order_update_revision=REVISION)
    for oid in changed:
        loaded['final_orders']['records'][oid] = objects[oid]['order_record']
        loaded['final_orders'].setdefault('origins', {})[oid] = objects[oid]['order_origins']
    return loaded
