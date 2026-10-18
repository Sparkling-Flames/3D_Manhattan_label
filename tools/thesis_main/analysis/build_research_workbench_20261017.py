"""打包研究工作台的只读离线几何，不重算研究、参考或融合。"""
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
OUT = PAGE / 'workbench-data'
REVISION = 'v1_integrated_analysis_20261017_r2'
FUSION = ROOT / 'research/fusion/wall_consensus_v1_process_20261017'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    path.write_text(payload, encoding='utf-8', newline='\n')
    path.with_suffix('.js').write_text(
        "window.researchLocalData[document.currentScript.src.replace(/\\.js$/, '.json')]= "
        + payload + ';\n', encoding='utf-8', newline='\n')


def read_table(data, index, name):
    meta = next(t for t in index['tables'] if t['id'] == name)
    rows = []
    for part in meta['parts']:
        value = read(data / part['path'])
        if value['columns'] != meta['columns']:
            raise ValueError('display columns drift: ' + name)
        for row in value['rows']:
            if len(row) != len(meta['columns']):
                raise ValueError('row width drift: ' + name)
            rows.append(dict(zip(meta['columns'], row)))
    if len(rows) != meta['row_count']:
        raise ValueError('display row count drift: ' + name)
    return rows


def is_true(value):
    return value is True or value in ('True', 'true')


def pack_image(image, scores, root):
    result = dict(image)
    if 'difficulty' in image:
        from .current_annotation_context_20261017 import apply_difficulty_overrides
        revised = apply_difficulty_overrides([dict(image_id=image['image_id'],
            current_class=image['difficulty']['label'])])[0]
        if revised['current_class'] != image['difficulty']['label']:
            result['difficulty'] = dict(image['difficulty'], label=revised['current_class'])
            result['scene'] = dict(image['scene'], conditional_difficulty=revised['current_class'])
            result['notes'] = [*image.get('notes', []),
                '2026-10-18用户确认难度为中等；历史r2统计尚未按此修订重分组。']
    result.pop('thumbnail_url', None)
    result.pop('original_url', None)
    available = [p for p in (image.get('original_path'), image.get('thumbnail_path')) if p and (root / p).is_file()]
    result['photo'] = '../../../' + available[0] if available else None
    result['photo_status'] = 'available' if available else 'missing'
    result['annotations'] = []
    for item in image['annotations']:
        annotation = dict(item)
        score = scores.get(item['object_id'])
        reasons = []
        if score is None or score['image_id'] != image['image_id']:
            reasons.append('object_or_image_not_in_consumer_snapshot')
        elif (score.get('rescore_target_id') or score.get('current_target_id')) != item.get('target_id'):
            reasons.append('target_binding_mismatch')
        elif is_true(score.get('quality_usable')) != is_true(item.get('quality_usable')):
            reasons.append('quality_use_mismatch')
        elif is_true(score.get('quality_usable')):
            for key in ('B8L2', 'D10'):
                a, b = score.get(key), item.get('quality', {}).get(key)
                if a is None or b is None or abs(float(a) - float(b)) > 1e-8:
                    reasons.append('score_mismatch:' + key)
        annotation.update(geometry_compatible=not reasons, geometry_binding_reasons=reasons)
        annotation['quality'] = {key: score.get(key) if score else None
                                 for key in ('B8L2', 'D10', 'IoU3D100')}
        annotation['quality_source'] = 'consumer_snapshot'
        annotation['source_quality_usable'] = item.get('quality_usable')
        annotation['quality_usable'] = is_true(score.get('quality_usable')) if score else False
        annotation['consumer_target_id'] = score.get('rescore_target_id') if score else None
        if score:
            annotation['calculation_status'] = score.get('calculation_status')
            for key in ('diagnostic_B8L2', 'diagnostic_D10', 'quality_exclusion_reasons'):
                annotation[key] = score.get(key)
        if reasons:
            annotation['points'] = annotation['raw_points'] = None
        result['annotations'].append(annotation)
    return result


def pack_pool(pool, states):
    if pool['pool_id'] != states['pool_id']:
        raise ValueError('pool identity mismatch')
    records = [{k: v for k, v in r.items() if k in (
        'id', 'object_id', 'worker', 'worker_id', 'points', 'points_1024x512',
        'ring_confirmed', 'order_status')} for r in pool['records']]
    packed = []
    for state in states['states']:
        automatic = state['automatic']
        packed.append(dict(subset=state['subset'], candidate=automatic.get('candidate'),
                           origin=state.get('origin'), ring_diagnostics=automatic.get('ring_diagnostics')))
    return dict(pool_id=pool['pool_id'], image=pool['image'], image_id=pool['image_id'],
                reference=pool['reference'], records=records, orders=states['orders'], states=packed)


def build():
    from .v1_statistics_revision_20261017 import publish_local_data
    history = PAGE.parent / 'research_explorer_20261017/explorer-data'
    history_files = publish_local_data(history) if (history / 'index.json').exists() else 0
    index = read(PAGE / 'explorer-data/index.json')
    if index['snapshot_id'] != REVISION:
        raise ValueError('consumer snapshot mismatch')
    scores = read_table(PAGE / 'explorer-data', index, 'quality__shared_records')
    required = {'object_id', 'image_id', 'rescore_target_id', 'quality_usable', 'B8L2', 'D10'}
    if scores and not required.issubset(scores[0]):
        raise ValueError('shared record contract missing: ' + ','.join(sorted(required - scores[0].keys())))
    by_object = {r['object_id']: r for r in scores}
    if len(by_object) != len(scores):
        raise ValueError('duplicate object IDs')
    gallery = read(ROOT / 'research/statistics/annotation_gallery_20261017/gallery.json')
    images = []
    incompatible = 0
    for number, image in enumerate(gallery['images']):
        packed = pack_image(image, by_object, ROOT)
        incompatible += sum(not a['geometry_compatible'] for a in packed['annotations'])
        path = f'images/{number}.json'
        write(OUT / path, packed)
        summary = {k: v for k, v in packed.items() if k not in ('annotations', 'references')}
        summary['detail'] = path
        images.append(summary)
    current = read(FUSION / 'CURRENT.json')
    inputs = read(FUSION / 'input_snapshot.json')
    captured = read(ROOT / 'research/statistics/v1_integrated_analysis_20261017_r2/DEPENDENCIES.json')
    dependencies = []
    fusion_matches = False
    for dependency in captured:
        path = ROOT / dependency['source_interface']
        actual = read(path) if path.is_file() else None
        matches = actual == dependency['source_metadata']
        dependencies.append(dict(module=dependency['module'], path=dependency['source_interface'],
                                 status='matches_at_build' if matches else 'differs_or_missing',
                                 captured=dependency['source_metadata'], current=actual))
        if dependency['module'] == 'fusion':
            fusion_matches = matches
    pools = []
    for number, pool in enumerate(inputs['images']):
        path = FUSION / 'pools' / pool['pool_id'] / 'states.json.gz'
        entry = dict(pool_id=pool['pool_id'], image=pool['image'], image_id=pool['image_id'],
                     condition=pool['condition'], reference_id=pool['reference']['target_id'])
        if path.is_file() and fusion_matches:
            state = json.loads(gzip.decompress(path.read_bytes()))
            output = f'pools/{number}.json'
            write(OUT / output, pack_pool(pool, state))
            entry.update(detail=output, status='saved_geometry')
        else:
            entry.update(detail=None, status='snapshot_mismatch' if not fusion_matches else 'not_saved')
        pools.append(entry)
    plan = ROOT / 'research/statistics/annotation_gallery_20261017/supplement_plan.json'
    manifest = dict(schema='research_workbench_display_v1', data_release='v1', snapshot_id=REVISION,
                    built_at=datetime.now(timezone.utc).isoformat(), images=images, pools=pools,
                    dependencies=dependencies, geometry_binding_mismatches=incompatible,
                    image_summary=gallery['summary'], gallery_score_context=gallery['score_context_version'],
                    fusion_revision=current['analysis_revision'],
                    supplement_plan=read(plan) if plan.exists() else None,
                    freshness='checked_at_build_only', historical_offline_files=history_files,
                    known_limits=['Semi初始化几何尚未适配，计量和来源已可查',
                                  '新研究、未保存测量、未接入图表保留占位，不推断结果'])
    write(OUT / 'index.json', manifest)
    print(json.dumps(dict(images=len(images), pools=len(pools), incompatible=incompatible), ensure_ascii=True))


if __name__ == '__main__':
    build()
