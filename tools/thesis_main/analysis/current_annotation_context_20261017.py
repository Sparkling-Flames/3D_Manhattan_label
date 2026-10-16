"""将冻结旧评分与已登记新增库存连接；新增作答仅建空分数、待绑定上下文。"""
import copy
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _index(rows, key):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows): raise ValueError('duplicate_context_' + key)
    return result


def build_current_context(bundle, difficulty_records, reference_catalog, quality_records, binding_records):
    """保留旧ID全量；仅 batch_admission 中明确新增的ID可补待绑定行。"""
    objects = _index([o for o in bundle['data']['objects'] if o['object_kind']=='annotation'], 'object_id')
    quality = _index(quality_records, 'object_id'); bindings = _index(binding_records, 'object_id')
    if set(quality) != set(bindings) or not set(quality) <= set(objects):
        raise ValueError('frozen_quality_binding_population_mismatch')
    admission = bundle.get('batch_admission', {})
    records = admission.get('records', [])
    admitted = _index(records, 'object_id')
    if set(admitted) != set(objects) - set(quality):
        raise ValueError('unregistered_or_overlapping_annotation_increment')
    sources = [r['source_id'] for r in records]
    if len(sources) != len(set(sources)): raise ValueError('duplicate_admitted_source_id')
    for rows in (quality_records, binding_records, records):
        for row in rows:
            obj = objects[row['object_id']]
            if any(row[k] != obj[k] for k in ('image_id', 'worker_id', 'condition')):
                raise ValueError('context_annotation_identity_drift:' + row['object_id'])
    result = dict(quality_records=copy.deepcopy(quality_records), binding_records=copy.deepcopy(binding_records),
        difficulty_records=copy.deepcopy(difficulty_records), reference_catalog=copy.deepcopy(reference_catalog),
        admission_version=admission.get('version'), admitted_source_ids=sources)
    for row in records:
        ident = {k: row[k] for k in ('object_id', 'image_id', 'worker_id', 'condition')}
        result['quality_records'].append(dict(ident, quality_usable=False, calculation_status='pending_target',
            full_score_state='pending_target', score_status='unscored', quality_exclusion_reasons=['new_batch_target_binding_pending'],
            B8L2=None, WQ=None, A10=None, IoU3D100=None, diagnostic_B8L2=None,
            task_worker_active_seconds=row.get('task_worker_active_seconds'), batch_admission_version=admission['version']))
        result['binding_records'].append(dict(ident, target_binding_unique=False, chosen_target_id=None,
            binding_status='new_batch_target_binding_pending'))
    difficulty = _index(result['difficulty_records'], 'image_id')
    for row in admission.get('difficulty_records', []):
        if row['image_id'] in difficulty: raise ValueError('admitted_difficulty_overwrites_frozen_image')
        difficulty[row['image_id']] = row
        result['difficulty_records'].append(copy.deepcopy(row))
    refs = _index(result['reference_catalog'], 'target_id')
    for row in admission.get('reference_catalog', []):
        if row['target_id'] in refs: raise ValueError('admitted_reference_overwrites_frozen_target')
        refs[row['target_id']] = row
        result['reference_catalog'].append(copy.deepcopy(row))
    image_ids = {o['image_id'] for o in objects.values()}
    if set(difficulty) != image_ids:
        raise ValueError('current_difficulty_annotation_image_population_mismatch')
    current = [r['image_id'] for r in result['reference_catalog'] if r['current_target']]
    if set(current) != image_ids or len(current) != len(set(current)):
        raise ValueError('current_reference_image_population_mismatch')
    return result


def load_current_context(bundle):
    """只读固定旧用途版本；新参考/难度从同一bundle登记层叠加。"""
    def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
    usage = ROOT/'research/statistics/b8l2_usage_v6_20261016'
    def csv_rows(name):
        with (usage/name).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    quality = csv_rows('shared_records.csv')
    for row in quality: row['quality_usable'] = row['quality_usable']=='True'
    pointer_path = ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
    pointer = read(pointer_path)
    difficulty = read(pointer_path.parent/pointer['details'])
    if isinstance(difficulty, dict): difficulty = difficulty.get('records', difficulty.get('images'))
    catalog = read(ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs/reference_catalog.json')
    context = build_current_context(bundle, difficulty, catalog, quality, csv_rows('shared_bindings.csv'))
    context.update(difficulty_pointer=pointer)
    return context


def build_scored_context(bundle, difficulty_records, reference_catalog, quality_records, binding_records,
                         qualified_records, metadata):
    """读取完整共同评分；严格核对身份、用途掩码和两个指标的共同分母。"""
    if (metadata['version'], metadata['primary_metric'], metadata['parallel_metric']) != (
            'quality_b8l2_d10_20261017_v2', 'B8L2', 'D10'):
        raise ValueError('unsupported_shared_quality_context')
    quality_records=copy.deepcopy(quality_records); binding_records=copy.deepcopy(binding_records)
    objects=_index([o for o in bundle['data']['objects'] if o['object_kind']=='annotation'],'object_id')
    quality=_index(quality_records,'object_id'); bindings=_index(binding_records,'object_id')
    qualified=_index(qualified_records,'object_id')
    if set(objects)!=set(quality) or set(objects)!=set(bindings) or len(objects)!=metadata['counts']['inventory']:
        raise ValueError('shared_quality_binding_population_mismatch')
    def boolean(value):
        if type(value) is bool:return value
        if value in ('True','False'):return value=='True'
        raise ValueError('invalid_shared_context_boolean')
    def number(value):
        if value in ('',None):return None
        value=float(value)
        if not math.isfinite(value) or not 0<=value<=100:raise ValueError('invalid_shared_quality_score')
        return value
    usable=set()
    refs=_index(reference_catalog,'target_id')
    for oid,obj in objects.items():
        q,b=quality[oid],bindings[oid]
        for row in (q,b):
            if any(row[k]!=obj[k] for k in ('image_id','worker_id','condition')):
                raise ValueError('context_annotation_identity_drift:'+oid)
            for key,value in row.items():
                if value in ('True','False'):row[key]=boolean(value)
        for key in ('quality_usable','pool_analysis_eligible','is_oos','current_quality_eligible'):
            q[key]=boolean(q[key])
        b['target_binding_unique']=boolean(b['target_binding_unique'])
        q['B8L2'],q['D10']=number(q['B8L2']),number(q['D10'])
        if (q['B8L2'] is not None)!=q['quality_usable'] or (q['D10'] is not None)!=q['quality_usable']:
            raise ValueError('shared_quality_mask_mismatch:'+oid)
        if q['current_quality_eligible']!=q['quality_usable']:
            raise ValueError('shared_quality_eligibility_mismatch:'+oid)
        if q['quality_usable']:
            usable.add(oid)
            if q['is_oos'] or obj['condition']=='oos' or not q['pool_analysis_eligible'] or not b['target_binding_unique']:
                raise ValueError('shared_quality_gate_mismatch:'+oid)
            if not b['chosen_target_id'] or b['chosen_target_id']!=q['rescore_target_id'] or b['chosen_target_id'] not in refs:
                raise ValueError('shared_quality_reference_mismatch:'+oid)
            if refs[b['chosen_target_id']]['image_id']!=obj['image_id']:
                raise ValueError('shared_quality_reference_image_mismatch:'+oid)
    if usable!=set(qualified) or len(usable)!=metadata['counts']['quality_rows']:
        raise ValueError('shared_qualified_population_mismatch')
    for oid in usable:
        q=qualified[oid]
        if any(q[k]!=objects[oid][k] for k in ('image_id','worker_id','condition')) or any(
                number(q[m])!=quality[oid][m] for m in ('B8L2','D10')):
            raise ValueError('shared_qualified_value_mismatch:'+oid)
    image_ids={o['image_id'] for o in objects.values()}
    difficulty=_index(difficulty_records,'image_id')
    current=[r['image_id'] for r in reference_catalog if r['current_target']]
    if set(difficulty)!=image_ids or set(current)!=image_ids or len(current)!=len(image_ids):
        raise ValueError('shared_image_reference_population_mismatch')
    admission=bundle.get('batch_admission',{})
    return dict(quality_records=quality_records,binding_records=binding_records,
        difficulty_records=difficulty_records,reference_catalog=reference_catalog,
        admission_version=admission.get('version'),admitted_source_ids=[r['source_id'] for r in admission.get('records',[])],
        difficulty_pointer=dict(version='scope_preferred_difficulty_scope_resolved_20261016_v6_plus_new2',
            details='research/quality/quality_b8l2_d10_20261017/difficulty_records.json'),
        score_context_version=metadata['version'],primary_metric='B8L2',parallel_metric='D10')


def load_scored_context(bundle, source=None):
    """显式新版消费者入口；共同评分生成器继续使用load_current_context，避免自读循环。"""
    source=Path(source) if source else ROOT/'research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json'
    def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
    def rows(key):
        with (ROOT/metadata[key]).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
    metadata=read(source)
    return build_scored_context(bundle,read(ROOT/metadata['difficulty_records']),read(ROOT/metadata['reference_catalog']),
        rows('full_inventory_with_metric_eligibility'),rows('all_pre_score_bindings'),
        rows('recommended_qualified_scores'),metadata)
