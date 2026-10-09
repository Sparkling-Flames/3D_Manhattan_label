"""接入最终审核计算视图；不重判清洗、场景或方法资格。"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from tools.thesis_main.analysis.finalize_review_20260928 import ROOT, read, dump
from tools.thesis_main.analysis.receive_order_review_20260928 import validate_return
from tools.thesis_main.analysis.build_order_gt_screened_20260928 import ordered_layout

FINAL = ROOT / 'analysis_results/final_review_summary_20260929'
SOURCE = ROOT / 'analysis_results/pairing_applied_20260929/preprocessed_source.json'
OUT = ROOT / 'analysis_results/research_input_20260929'
CONTRACT = ROOT / 'docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json'
SCHEMA = 'final_review_research_input_v1'


def rows(path):
    csv.field_size_limit(32 * 1024 * 1024)
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def indexed(items, key):
    result = {r[key]: r for r in items}
    if len(result) != len(items):
        raise ValueError('duplicate_key:' + key)
    return result


def typed(row, json_fields=(), bool_fields=()):
    result = dict(row)
    for k in json_fields:
        result[k] = json.loads(row[k])
    for k in bool_fields:
        if row[k] not in {'true', 'false'}:
            raise ValueError('invalid_boolean:' + k)
        result[k] = row[k] == 'true'
    return result


def build():
    source = read(SOURCE)
    objects = indexed(source['objects'], 'object_id')
    orders = read(FINAL / 'received_orders.json')
    validate_return(orders, objects)
    ledger = indexed(rows(FINAL / '全量3152份最终台账.csv'), 'object_id')
    evidence = indexed(rows(ROOT / 'analysis_results/review_final_20260928/全量复核.csv'), 'canonical_annotation_id')
    package = read(FINAL / '同房汇集_Matterport.json')
    layouts = indexed([o for room in package['rooms'] for o in room['objects']], 'object_id')
    registry = read(FINAL / '同房分类_原始完整记录.json')
    registry_images = indexed(registry['images'], 'image_id')
    if set(objects) != set(layouts) or set(ledger) != set(evidence):
        raise ValueError('source_population_mismatch')
    if set(ledger) != {oid for oid, o in objects.items() if o['object_kind'] == 'annotation'}:
        raise ValueError('annotation_population_mismatch')
    images = []
    for row in rows(FINAL / '逐图分类及覆盖.csv'):
        r = typed(row, ('room_spatial_classification', 'room_classification_sources', 'cleaning_counts', 'order_counts', 'comments'),
                  ('scope_explicit_tag', 'detail_explicit_tag', 'scope_existing_ledger', 'detail_existing_ledger', 'scope_comment_candidate', 'detail_comment_candidate'))
        r['building_id'] = registry_images[r['image_id']]['building']
        r['annotations'] = int(r['annotations'])
        r['population'] = 'research_annotation_image'
        r['references'] = {}
        images.append(r)
    image_map = indexed(images, 'image_id')
    for o in objects.values():
        if o['image_id'] not in image_map:
            if o['object_kind'] != 'gt_manual_revision':
                raise ValueError('unexpected_reference_only_image:' + o['image_id'])
            ri = registry_images[o['image_id']]
            image_map[o['image_id']] = dict(image_id=o['image_id'], image_code=o['image_code'],
                building_id=ri['building'], room_id='', annotations=0, references={},
                population='manual_gt_reference_only', room_spatial_classification=ri['spatial_classification'],
                room_classification_sources=ri['spatial_field_sources'])
    groups = defaultdict(list)
    for oid, r in ledger.items():
        groups[(r['worker_id'], r['image_id'], r['condition'])].append(oid)
    duplicates = []
    for key, ids in groups.items():
        current = [i for i in ids if ledger[i]['cleaning_disposition'] != 'historical_not_accepted']
        if len(current) > 1:
            raise ValueError('ambiguous_current_version:' + str(key))
        if len(ids) > 1:
            duplicates.append(dict(unit=list(key), object_ids=ids, current_object_id=current[0] if current else None))
    output = []
    for oid, o in objects.items():
        layout = layouts[oid]
        rec = orders['records'].get(oid)
        order = rec['order'] if rec else list(range(len(o['links_zero_based'] or [])))
        if rec and rec['status'] != 'confirmed':
            raise ValueError('unconfirmed_final_record:' + oid)
        if o['preprocessing_status'] == 'ready':
            expected = ordered_layout(o, order)
            for k in ('points_1024x512', 'links_zero_based', 'ordered_source_point_indices', 'ordered_source_pair_indices'):
                if layout[k] != expected[k]:
                    raise ValueError('final_layout_mismatch:' + oid + ':' + k)
        elif layout['points_1024x512'] is not None:
            raise ValueError('unpaired_layout:' + oid)
        # source-order arrays retain fixed point/pair identities; the Matterport array is a separate view.
        r = dict(o, points_1024x512=layout['points_1024x512'],
                 matterport_links_zero_based=layout['links_zero_based'],
                 ordered_source_point_indices=layout.get('ordered_source_point_indices'),
                 ordered_source_pair_indices=layout.get('ordered_source_pair_indices'),
                 ordered_source_point_labels=layout.get('ordered_source_point_labels'),
                 ring_confirmed=bool(rec), order_status=layout['order_status'], order_record=rec,
                 order_origins=orders['origins'].get(oid, []), geometry=layout['geometry'],
                 method_evaluability='not_assessed_per_method',
                 building_id=image_map[o['image_id']]['building_id'], room_id=image_map[o['image_id']]['room_id'])
        if o['object_kind'] != 'annotation':
            version = o['object_kind']
            refs = image_map[o['image_id']]['references']
            if version in refs:
                raise ValueError('duplicate_gt_version:' + o['image_id'])
            refs[version] = oid
            r['gt_version'] = version
            output.append(r)
            continue
        row = typed(ledger[oid], ('geometry_issues', 'unusable_pair_ids', 'repair_evidence', 'deleted_previous_point_indices'),
                    ('individually_reviewed', 'scope_difference_image', 'detail_difference_image', 'scope_difference_annotation', 'detail_difference_annotation'))
        old = evidence[oid]
        for k in ('cleaning_disposition', 'worker_quality_gate', 'condition'):
            if row[k] != old[k] or row[k] != o[k]:
                raise ValueError('decision_drift:' + oid + ':' + k)
        r['final_review'] = row
        r['review_evidence'] = {k: old[k] for k in ('verdict', 'historical_exclusion_reason', 'current_comment', 'current_decision_comment', 'image_comment', 'scope_policy', 'gt_version_note')}
        for k in ('analysis_gate_reasons', 'annotation_traits', 'image_traits', 'review_history', 'image_review_history', 'coverage_review', 'semantic_annotation_evidence', 'semantic_image_evidence', 'trap_model_evidence'):
            r['review_evidence'][k] = json.loads(old[k])
        for k in ('gt_substantive_error', 'gt_detail_omission', 'points_without_imputation'):
            r['review_evidence'][k] = typed(old, bool_fields=(k,))[k]
        repairs = o['repair_evidence']
        if isinstance(repairs, dict):
            repairs = [repairs]
        borrowed = [e for e in repairs if e['status'] == 'applied' and e.get('provenance', {}).get('borrowed_other_response') is True]
        for e in borrowed:
            if e['provenance']['donor_id'] not in ledger:
                raise ValueError('unknown_donor:' + oid)
        reasons = ([] if row['cleaning_disposition'] == 'retained' else [row['cleaning_disposition']])
        if borrowed:
            reasons.append('borrowed_points_not_independent_complete_response')
        r.update(condition=row['condition'], consensus_group=old['consensus_group'],
                 canonical_unit=[o['worker_id'], o['image_id'], o['condition']],
                 person_image_unit=[o['worker_id'], o['image_id']],
                 borrowed_point_provenance=borrowed,
                 independent_vote_eligible=not reasons, independent_vote_reasons=reasons,
                 main_quality_gate=dict(status=row['worker_quality_gate'], reasons=r['review_evidence']['analysis_gate_reasons']),
                 main_consensus_gate=dict(status=old['consensus_group'], reasons=[old['consensus_group']], scope_policy=old['scope_policy']))
        output.append(r)
    counts = Counter(o['object_kind'] for o in output)
    if counts != {'annotation': 3152, 'gt_original': 259, 'gt_manual_revision': 30} or len(images) != 259 or len(orders['records']) != 1295:
        raise ValueError('final_count_drift')
    annotations = [o for o in output if o['object_kind'] == 'annotation']
    summary = dict(objects=dict(counts), images=len(images), reference_only_images=len(image_map) - len(images), confirmed_orders=len(orders['records']),
                   cleaning=dict(Counter(o['cleaning_disposition'] for o in annotations)),
                   worker_quality_gate=dict(Counter(o['worker_quality_gate'] for o in annotations)),
                   consensus_group=dict(Counter(o['consensus_group'] for o in annotations)),
                   borrowed_annotations=sum(bool(o['borrowed_point_provenance']) for o in annotations),
                   independent_vote_candidates=sum(o['independent_vote_eligible'] for o in annotations), duplicate_groups=len(duplicates))
    result = dict(schema=SCHEMA, contract_version=read(CONTRACT)['contract_version'],
                  coordinate_frame=source['coordinate_frame'], preprocessing=source['method'],
                  sources=dict(preprocessing=str(SOURCE.relative_to(ROOT)).replace('\\', '/'),
                               final_review=str(FINAL.relative_to(ROOT)).replace('\\', '/'),
                               cleaning='analysis_results/review_final_20260928/全量复核.csv'),
                  summary=summary, objects=output, images=list(image_map.values()), room_registry=registry, duplicate_versions=duplicates,
                  model_unchanged_audit=rows(FINAL / '预标注未改动与影响评语汇总.csv'),
                  explicit_model_influence_comments=rows(FINAL / '用户comment明确记录_模型误导影响.csv'))
    OUT.mkdir(exist_ok=True)
    dump(OUT / 'preprocessed_source.json', result)
    dump(OUT / 'summary.json', summary)
    dump(OUT / 'field_contract.json', dict(schema=SCHEMA, documentation='docs/thesis_main/最终审核数据接入_20260929.md',
        source_identity_fields=['preprocessed_points', 'links_zero_based', 'point_labels'],
        final_ring_fields=['points_1024x512', 'matterport_links_zero_based', 'ordered_source_point_indices', 'ordered_source_pair_indices'],
        eligibility='独立票候选、主质量gate、主共识gate分别检查；candidate不等于方法可评价。',
        population='259研究图加2张仅人工GT参考图；3152人员记录全部保留。',
        unavailable='不可配对points_1024x512=null；默认未审环不冒充人工确认。'))
    return result


def load_current_input(*, apply_updates=True):
    """唯一当前读取入口；历史脚本仍读取其冻结版本。"""
    contract = read(CONTRACT)
    result = read(ROOT / contract['data']['preprocessed_source'])
    if result['schema'] != SCHEMA or result['contract_version'] != contract['contract_version']:
        raise ValueError('current_input_schema_or_contract_mismatch')
    if apply_updates and contract['data'].get('quality_update'):
        from .apply_quality_review_20261010 import apply_data
        result=apply_data(result,read(ROOT/contract['data']['quality_update']))
    return result


if __name__ == '__main__':
    print(json.dumps(build()['summary'], ensure_ascii=False, indent=2))
