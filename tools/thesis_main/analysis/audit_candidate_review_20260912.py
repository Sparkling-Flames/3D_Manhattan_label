"""核验外部候选快照；只写审计结果，不选择图片或派发任务。"""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import gzip
import json
import math

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/candidate_review_20260912_v2'
REGISTRY = ROOT / 'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'
VIEW = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
ACTIVE = {1, 2, 6, 8, 10, 12, 13, 15, 17, *range(28, 38)}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def coverage(rows, active=ACTIVE):
    manual = {int(r['worker_id']) for r in rows if r['unassisted_manual_included']}
    semi = {int(r['worker_id']) for r in rows if r['assistance_exposure'] == 'model_preannotation'}
    seen = {int(r['worker_id']) for r in rows}
    clean = active - seen
    return dict(manual_workers=sorted(manual), semi_workers=sorted(semi), clean_workers=sorted(clean),
                manual_included=len(manual), manual_active19=len(manual & active),
                manual_other=len(manual - active), semi=len(semi), semi_active19=len(semi & active),
                seen_active19=len(seen & active), clean_new_active19=len(clean),
                max_pooled_manual=len(manual) + len(clean),
                max_active19_manual=len(manual & active) + len(clean))


def main():
    registry = read(REGISTRY)
    data = read(OUT / 'candidate_payload.json')
    assert data['status'] == 'CANDIDATE_REVIEW_ONLY_NO_ASSIGNMENT'
    assert set(data['participants']) == ACTIVE
    images = {r['image_id']: r for r in registry['images']}
    groups = {r['review_code']: r for r in registry['groups']}
    with gzip.open(VIEW, 'rt', encoding='utf-8') as f:
        rows = [json.loads(line) for line in f]
    assert len(rows) == len({r['canonical_annotation_id'] for r in rows}) == 2501
    by_image = defaultdict(list)
    for r in rows:
        by_image[r['image_id']].append(r)
    sources = {}
    versions = 0
    raw_pairs = set()
    for path in sorted({r['raw_export_path'] for r in rows}):
        index = {}
        for task in read(ROOT / path):
            matches = [i for i in by_image if i in json.dumps(task['data'])]
            for ann in task.get('annotations', []):
                assert len(matches) == 1, (path, task['id'], matches)
                w = ann['completed_by']
                w = w['id'] if isinstance(w, dict) else w
                raw_pairs.add((int(w), matches[0]))
                key = (str(task['id']), str(ann['id']))
                assert key not in index
                index[key] = (task, ann)
                versions += 1
        sources[path] = index
    assert raw_pairs == {(int(r['worker_id']), r['image_id']) for r in rows}
    meta = []
    for r in rows:
        _, _, tid, wid, aid = r['raw_annotation_version_id'].split('|')
        task, ann = sources[r['raw_export_path']][tid, aid]
        worker = ann['completed_by']
        worker = worker['id'] if isinstance(worker, dict) else worker
        assert str(worker) == wid == str(r['worker_id'])
        assert r['image_id'] in json.dumps(task['data'])
        points = [[float(x['value']['x']) * 10.24, float(x['value']['y']) * 5.12]
                  for x in ann.get('result', []) if x.get('type') == 'keypointlabels']
        expected = r['raw_points_1024x512']
        assert len(points) == len(expected)
        assert all(math.isclose(x, y, abs_tol=1e-8, rel_tol=0) or (math.isnan(x) and math.isnan(y))
                   for a, b in zip(points, expected) for x, y in zip(a, b))
        choices = defaultdict(set)
        for item in ann.get('result', []):
            if item.get('type') == 'choices':
                choices[item['from_name']].update(item['value']['choices'])
        meta.append(dict(worker_id=int(wid), manual=r['unassisted_manual_included'],
                         semi=r['assistance_exposure'] == 'model_preannotation', choices=dict(choices)))
    assert len(data['images']) == len({r['image_id'] for r in data['images']}) == 112
    excluded_impact = []
    for r in data['images']:
        im = images[r['image_id']]
        assert r['review_decision'] == '待审' and r['difficulty_review'] == '未定'
        assert all(r[k] == im[k] for k in ['building', 'number', 'path', 'main_visual_space'])
        assert (ROOT / r['path']).is_file(), r['path']
        assert r['adopted_coarse_type'] == im['spatial_classification']['coarse_type']
        assert r['coarse_source'] == im['spatial_field_sources']['coarse_type']
        c = coverage(by_image[r['image_id']])
        assert all(r[k] == v for k, v in c.items()), r['image_id']
        assert c['manual_included'] == im['annotation_counts']['n_people']['manual_included']
        for n in [6, 8, 15, 19]:
            for basis, have in [('pooled', c['manual_included']), ('active19', c['manual_active19'])]:
                need = max(0, n - have)
                assert r[f'new_to_{n}_{basis}'] == need
                assert r[f'feasible_{n}_{basis}'] == (need <= c['clean_new_active19'])
        no_special = set(c['manual_workers']) - {19, 26}
        if len(no_special) != c['manual_included']:
            excluded_impact.append(dict(group=r['group'], number=r['number'],
                                        included=c['manual_included'], without_W19_W26=len(no_special)))
    for g in data['groups']:
        original = groups[g['group']]
        assert g['numbers'] == original['numbers']
        assert g['original_judgment'] == original['raw_current']
        assert g['review_state'] == original['review_state']
        assert g['coarse_types'] == original['spatial_summary']['coarse_type_counts']
        actual = {r['image_id'] for r in data['images'] if r['group'] == g['group']}
        assert actual == set(original['image_ids'])
        semi = {int(r['worker_id']) for i in actual for r in by_image[i]
                if r['assistance_exposure'] == 'model_preannotation'} & ACTIVE
        assert sorted(semi) == g['current19_same_room_semi_workers']
    populations = {'all_canonical': meta, 'usable_manual_all_workers': [r for r in meta if r['manual']],
                   'usable_manual_active19': [r for r in meta if r['manual'] and r['worker_id'] in ACTIVE],
                   'all_semi': [r for r in meta if r['semi']]}
    fields = sorted({key for r in meta for key in r['choices']})
    frequencies = {pop: {key: dict(Counter(v for r in rr for v in r['choices'].get(key, [])))
                         for key in fields} for pop, rr in populations.items()}
    with (OUT / 'results/meta_frequencies.csv').open(encoding='utf-8-sig', newline='') as f:
        saved = list(csv.DictReader(f))
    actual_keys = {(pop, field, value) for pop, fs in frequencies.items()
                   for field, counts in fs.items() for value in counts}
    assert actual_keys == {(r['population'], r['field'], r['value']) for r in saved}
    for r in saved:
        rr = populations[r['population']]
        assert int(r['n_records']) == len(rr)
        assert int(r['n_answered']) == sum(bool(x['choices'].get(r['field'])) for x in rr)
        assert int(r['n_positive']) == frequencies[r['population']][r['field']][r['value']]
    for name, key in [('candidate_images.csv', 'images'), ('candidate_groups.csv', 'groups')]:
        with (OUT / 'results' / name).open(encoding='utf-8-sig', newline='') as f:
            saved = list(csv.DictReader(f))
        assert len(saved) == len(data[key])
        for line, entry in zip(saved, data[key]):
            assert set(line) == set(entry)
            for k, value in entry.items():
                expected = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else '' if value is None else str(value)
                assert line[k] == expected, (name, k)
    old20 = {'G047': [6, 10, 17, 19], 'G057': [4, 10], 'G237': [5, 10], 'G207': [4, 45],
             'G178': [7, 14, 48, 78], 'G090': [7, 8, 11, 28], 'G027': [45], 'G202': [26]}
    selected = [r for r in data['images'] if r['number'] in old20.get(r['group'], [])]
    assert len(selected) == 20
    budgets = {f'{n}_{basis}': sum(r[f'new_to_{n}_{basis}'] for r in selected)
               for n in [15, 19] for basis in ['pooled', 'active19']}
    assert list(budgets.values()) == [s['new_annotations'] for s in data['budget_sensitivity']]
    pool_ids = {r['image_id'] for r in data['images']}
    scene_coverage = {}
    for name, subset in [('all648', list(images.values())),
                         ('candidate112', [r for r in images.values() if r['image_id'] in pool_ids])]:
        scene_coverage[name] = dict(
            images=len(subset),
            adopted_types=dict(Counter(r['spatial_classification']['coarse_type'] or '采用值为空' for r in subset)),
            doorway_working_labels=dict(Counter(r['doorway_reconciliation']['current_working_label'] for r in subset)))
    assert scene_coverage['candidate112']['doorway_working_labels']['确认'] == 1
    assert scene_coverage['candidate112']['doorway_working_labels']['疑似'] == 1
    result = dict(status='passed', registry_images=len(images), candidate_groups=len(data['groups']),
                  candidate_images=len(data['images']), buildings=len({g['building'] for g in data['groups']}),
                  raw_exports=len(sources), raw_versions=versions, canonical_checked=len(rows),
                  raw_unique_worker_images=len(raw_pairs), local_images_present=112,
                  current_participants=sorted(ACTIVE), old20_budget_scenarios=budgets,
                  field_coverage={p: {'n': len(rr), **{f: sum(bool(r['choices'].get(f)) for r in rr)
                                                      for f in fields}} for p, rr in populations.items()},
                  meta_frequencies=frequencies, W19_W26_source_count_sensitivity=excluded_impact,
                  scene_coverage=scene_coverage,
                  limitation='当前快照回查；无新目标结果、视觉裁定、功效证明或最终人员匹配。')
    (OUT / 'results/repository_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['status', 'candidate_groups', 'candidate_images', 'buildings', 'canonical_checked', 'old20_budget_scenarios']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
