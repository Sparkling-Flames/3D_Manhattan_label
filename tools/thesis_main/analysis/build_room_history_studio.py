"""Attach all reviewed room groups to the existing offline Panorama Studio."""
import csv
import gzip
import json
import shutil
from collections import defaultdict
from pathlib import Path

from tools.label_studio.panorama_studio.build import annotation_layout, data_image, read_json
from tools.label_studio.panorama_studio.geometry import analyze
from tools.thesis_main.analysis.analyze_q_thresholds_20260909 import q_partition
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/panorama_studio_20260907_v3'
HERE = ROOT / 'tools/label_studio/panorama_studio'
REGISTRY = ROOT / 'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'
SOURCE = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'


def partition_view(rows, variants, saved=None):
    eligible = [r for r in rows if r['calculation_included']]
    by_id = {v['source']['canonical_annotation_id']: i for i, v in enumerate(variants)}
    if not eligible:
        return dict(status='没有纳入计算的历史记录', candidates=[])
    if len({str(r['worker_id']) for r in eligible}) != len(eligible):
        raise ValueError('同图同条件人员重复，不能当作独立支持数')
    if saved is None:
        records = [dict(canonical_annotation_id=r['canonical_annotation_id'], worker_id=r['worker_id'],
                        _geometry=normalize_geometry(r['effective_points_1024x512'])) for r in eligible]
        saved = q_partition(records, .95)
    candidates = json.loads(saved['candidate_partitions_json'])
    counts = {r['canonical_annotation_id']: r['effective_point_count'] for r in eligible}
    for candidate in candidates:
        flat = [i for group in candidate for i in group]
        assert len(flat) == len(set(flat)) and set(flat) <= set(counts)
        for group in candidate:
            assert len({counts[i] for i in group}) == 1, '点数不同不可同簇'
    return dict(status=('唯一分区' if saved['partition_status'] == 'unique' else '分区不唯一或不可确定') +
                       ('；枚举截断' if str(saved['enumeration_truncated']).lower() == 'true' else ''),
                candidates=[[[by_id[i] for i in group] for group in candidate] for candidate in candidates],
                source='既有q=.95分区' if 'image_id' in saved else '复用q_partition，探索展示q=.95')


def main():
    registry = read_json(str(REGISTRY))
    with gzip.open(SOURCE, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    grouped = defaultdict(list)
    for r in rows:
        grouped[r['image_id']].append(r)
    partition_path = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1/revised/with_workers/geometry/full_q_partitions.csv'
    with partition_path.open(encoding='utf-8-sig', newline='') as stream:
        saved = {r['image_id']: r for r in csv.DictReader(stream) if float(r['threshold']) == .95}
    inventory = {r['image_id']: r for r in registry['images']}
    existing = read_json(str(OUT / 'geometry_audit.json'))
    offset = len(existing['cases'])
    dest = OUT / 'history'; dest.mkdir(exist_ok=True)
    summaries, total = [], 0
    # Prioritize the requested group; every other annotated inventory image follows.
    requested = next(g['image_ids'] for g in registry['groups'] if g['review_code'] == 'G179')
    ids = sorted(set(grouped) & set(inventory), key=lambda i: (i not in requested, inventory[i]['building'], inventory[i]['number']))
    for index, iid in enumerate(ids, offset):
        image = inventory[iid]; variants = []
        rr = sorted(grouped[iid], key=lambda r: (r['assistance_exposure'], int(r['worker_id'])))
        for r in rr:
            _, _, task_id, worker, ann_id = r['raw_annotation_version_id'].split('|')
            assert str(r['worker_id']) == worker
            tasks = [t for t in read_json(str(ROOT / r['raw_export_path'])) if str(t['id']) == task_id]
            assert len(tasks) == 1 and iid in json.dumps(tasks[0]['data'])
            ann = next(a for a in tasks[0]['annotations'] if str(a['id']) == ann_id)
            author = ann['completed_by']; assert str(author['id'] if isinstance(author, dict) else author) == worker
            mode = 'Manual' if r['assistance_exposure'] == 'none' else 'Semi'
            v = dict(name=f"{mode} · W{worker} · 原始{r['raw_point_count']}点 · 复核后{r['effective_point_count']}点",
                     source=dict(role='historical_annotation', mode=mode, worker_id=worker,
                                 canonical_annotation_id=r['canonical_annotation_id'], path=r['raw_export_path'],
                                 task_id=task_id, annotation_id=ann_id, processing=r['processing_status'],
                                 calculation_included=r['calculation_included'], exclusion_reason=r['exclusion_reason'],
                                 raw_points=r['raw_points_1024x512'], effective_points=r['effective_points_1024x512'],
                                 geometry_basis='3D按原始导出上下点对顺序；分簇按复核后点，拟合不参与分簇'))
            try:
                v['geometry'] = analyze(annotation_layout(tasks[0], ann_id))
            except ValueError as exc:
                v['error'] = str(exc)  # Keep the worker and exact points visible even when 3D cannot parse.
            variants.append(v)
        partitions = {}
        for mode, exposure in [('Manual', 'none'), ('Semi', 'model_preannotation')]:
            subset = [r for r in rr if r['assistance_exposure'] == exposure]
            partitions[mode] = partition_view(subset, variants, saved.get(iid) if mode == 'Manual' else None)
        title = f"{image['building']} · {image['number']:02} · 历史{len(rr)}份"
        summary = dict(image_id=iid, title=title, category='同房研究历史 · Manual / Semi分开',
                       history_image=True, history_script=f'history/{index}.js', variants=[])
        payload = dict(variants=variants, history=dict(partitions=partitions), history_loaded=True)
        # Reuse Studio's 2048px JPEG preview; source PNG remains unchanged and is not copied.
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
        photo = json.dumps(data_image(ROOT / image['path'], texture=True))
        script = f'Object.assign(window.STUDIO_DATA.cases[{index}],{encoded});\n' + f'{{const image={photo};window.STUDIO_IMAGES[{index}]={{original:image,texture:image}};}}'
        (dest / f'{index}.js').write_text(script, encoding='utf-8')
        summaries.append(summary); total += len(rr)
        print(f'{index-offset+1}/{len(ids)} {image["building"]}:{image["number"]:02} {len(rr)} records', flush=True)
    groups = [dict(code=g['review_code'], building=g['building'], images=[dict(id=i, number=inventory[i]['number'],
                    manual=inventory[i]['annotation_counts']['n_people']['manual'], semi=inventory[i]['annotation_counts']['n_people']['semi']) for i in g['image_ids']]) for g in registry['groups']]
    script = 'window.STUDIO_DATA.cases.push(...' + json.dumps(summaries, ensure_ascii=False) + ');\nwindow.STUDIO_HISTORY=' + json.dumps(dict(groups=groups), ensure_ascii=False) + ';'
    script += f'window.STUDIO_DATA.counts.cases=window.STUDIO_DATA.cases.length;window.STUDIO_DATA.counts.variants+={total};'
    (OUT / 'history_data.js').write_text(script, encoding='utf-8')
    for name in ['studio.js', 'history.js', 'history.css']:
        shutil.copy2(HERE / name, OUT / name)
    page = (HERE / 'index.html').read_text(encoding='utf-8')
    page = page.replace('<script defer src="studio.js"></script>', '<script defer src="history_data.js"></script><script defer src="studio.js"></script><script defer src="history.js"></script><link rel="stylesheet" href="history.css">')
    (OUT / 'index.html').write_text(page, encoding='utf-8', newline='\n')
    audit = dict(schema='room_history_studio_v1', groups=len(groups), images=len(ids), records=total,
                 registry=str(REGISTRY), snapshot=str(SOURCE), q=.95, different_point_counts_separate=True,
                 minimum_cluster_support=2, source_annotations_modified=False,
                 geometry_basis='原始导出顺序3D；复核后点q分簇；两者不同则显示点数与处理状态',
                 original_engineering_cases_preserved=offset)
    (OUT / 'history_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    assert len(groups) == 260 and len(ids) == 214
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
