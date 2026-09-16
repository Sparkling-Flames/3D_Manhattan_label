"""Attach current research candidates to the existing Panorama Studio.

No classification, coordinate repair, model inference or human adjudication.
The portable evidence excludes image bytes; the generated Studio stays local.
"""
from __future__ import annotations
import base64
import collections
import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
B = ROOT / 'analysis_results/image_portrait_20260914_v1'
V1 = B / 'cloud/history_difficulty_20260915_v1/run_13859d59'
V2 = B / 'cloud/history_difficulty_review_20260915_v2/run_c0069628'
OUT = B / 'review_workflow_20260915'
LOCAL = B / 'local_review_studio'
OLD = ROOT / 'analysis_results/panorama_studio_20260907_v3'
STUDIO = ROOT / 'tools/label_studio/panorama_studio'
HERE = Path(__file__).resolve().parent


def read_rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f)) if '.csv' in path.name else [json.loads(x) for x in f if x.strip()]


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def validate_review(v):
    if v.get('status') not in ('未审核', '已审核', '暂缓') or not isinstance(v.get('reason'), str):
        raise ValueError('invalid review status/reason')
    if v.get('grade') not in ('', '简单', '中等', '困难候选', '三档不适用'):
        raise ValueError('invalid reviewed grade')
    if (v['status'] == '已审核') != bool(v['grade']):
        raise ValueError('reviewed grade must be explicitly adjudicated')


def validate_memberships(groups, raw):
    seen, people = set(), set()
    for group in groups:
        counts = set()
        for cid in group:
            if cid in seen or raw[cid]['worker_id'] in people:
                raise ValueError('duplicate annotation/person in partition')
            seen.add(cid); people.add(raw[cid]['worker_id'])
            counts.add(len(raw[cid]['effective_points_1024x512']))
        if len(counts) > 1:
            raise ValueError('different point count in one cluster')


def run(focus=False):
    local = LOCAL / 'key39' if focus else LOCAL
    out = OUT / 'key39' if focus else OUT
    images = {r['image_id']: r for r in read_rows(B / 'metadata/images.jsonl')}
    raw = {r['canonical_annotation_id']: r for r in read_rows(B / 'human/responses.jsonl.gz')}
    tags = {r['image_id']: r for r in read_rows(V1 / 'expert/independent_tags106.csv')}
    first = {(r['image_id'], r['condition']): r for r in read_rows(V1 / 'targets/primary_with_robustness.csv')}
    latest = {(r['image_id'], r['条件']): r for r in read_rows(V2 / 'USER_DECISION_TABLE.csv')}
    assert len(latest) == len(first) == 230 and latest.keys() == first.keys()
    assert all(not r[k] for r in latest.values() for k in ('用户最终粗类', '用户裁决原因', '簇语义裁决', '单人标法裁决')), 'Preserve returned human edits before regenerating'
    historical = {i for i, _ in latest}; ids = historical | tags.keys()
    assert len(historical) == 205 and len(tags) == 106 and len(ids) == 276
    metadata = {r['image_id']: r for r in read_rows(V1 / 'inputs/image_metadata_whitelist.csv')}
    memberships = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in read_rows(V2 / 'structure/real_mode_memberships.csv.gz'):
        if float(r['cut']) != .1:
            continue
        source = raw[r['canonical_annotation_id']]
        assert (source['image_id'], source['raw_condition'], source['worker_id']) == (r['image_id'], r['condition'], r['worker_id'])
        assert source['worker_id'] not in ('W019', 'W026')
        memberships[r['image_id'], r['condition']][r['cluster']].append(r['canonical_annotation_id'])
    for groups in memberships.values():
        validate_memberships(list(groups.values()), raw)
    queue = []
    if focus:
        study = B / 'cloud/image_links_after_review_20260915_v1/run_b02a97e2'
        queue = read_rows(study / 'local_image_review_queue.csv')
        ids = {r['image_id'] for r in queue}
        assert len(queue) == 44 and len(ids) == 39
        metadata.update({r['image_id']: r for r in read_rows(study / 'inputs/image_metadata_whitelist.csv')})
        for question in queue:
            for field in ('canonical_ids', 'representative_canonical_ids'):
                for cid in filter(None, question[field].split(';')):
                    assert raw[cid]['image_id'] == question['image_id'], (field, cid)
        for r in read_rows(study / 'oos/mode_memberships.csv'):
            source = raw[r['canonical_annotation_id']]
            assert (source['image_id'], source['worker_id'], source['raw_condition']) == (r['image_id'], r['worker_id'], 'oos')
            assert source['worker_id'] not in ('W019', 'W026')
            memberships[r['image_id'], 'oos_geometry'][r['cluster']].append(r['canonical_annotation_id'])
        for groups in memberships.values():
            validate_memberships(list(groups.values()), raw)

    # Reuse existing per-person 3D reconstructions only after checking exact raw points.
    old_text = (OLD / 'history_data.js').read_text(encoding='utf-8')
    old_cases, _ = json.JSONDecoder().raw_decode(old_text.split('cases.push(...', 1)[1])
    cached = {r['image_id']: r for r in old_cases}
    focused = {r['image_id'] for r in read_rows(V2 / 'expert/final_medium_hard_focus.csv')}
    ordered = sorted(ids, key=lambda i: (i not in focused, images[i]['building'], images[i]['number']))
    rows, cases, counts = [], [], collections.Counter()
    (local / 'history').mkdir(parents=True, exist_ok=True)
    for index, iid in enumerate(ordered):
        im = images[iid]; source_image = ROOT / im['path']
        assert source_image.is_file(), iid
        units = [dict(condition=c, previous=first[i, c], candidate=latest[i, c]) for i, c in latest if i == iid]
        row = dict(image_id=iid, building=im['building'], number=im['number'], image_path=im['path'],
                   scene=metadata[iid]['scene_category'], expert=tags.get(iid), units=units,
                   priority=iid in focused, original_image_checked=False,
                   questions=[dict(q, question_id=f'Q{j+1:02}') for j, q in enumerate(queue) if q['image_id'] == iid])
        rows.append(row)
        if iid in cached:
            text = (OLD / cached[iid]['history_script']).read_text(encoding='utf-8')
            payload, _ = json.JSONDecoder().raw_decode(text.split(',', 1)[1])
            photo, _ = json.JSONDecoder().raw_decode(text.split('const image=', 1)[1])
            variants = payload['variants']
            for v in variants:
                r = raw[v['source']['canonical_annotation_id']]
                assert r['image_id'] == iid and r['raw_points_1024x512'] == v['source']['raw_points']
                assert r['effective_points_1024x512'] == v['source']['effective_points']
                v['source']['main_worker_included'] = r['main_worker_included']
                if not r['main_worker_included']:
                    v['name'] += ' · 不纳入当前主分析'
                counts['reused_human_variants'] += 1
        else:
            assert iid not in historical, 'Historical geometry cache missing'
            photo = 'data:image/png;base64,' + base64.b64encode(source_image.read_bytes()).decode('ascii')
            variants = [dict(name='仅原图：没有本轮Manual/Semi历史', source={'role': 'image_only'}, error='没有真人布局；不生成候选难度或3D')]
        lookup = {v['source'].get('canonical_annotation_id'): j for j, v in enumerate(variants)}
        parts = {}
        for mode, condition in [('Manual', 'manual'), ('Semi', 'semi'), ('OOS', 'oos_geometry')]:
            groups = list(memberships.get((iid, condition), {}).values())
            parts[mode] = dict(status='第二轮候选分区；不是人工裁决',
                               candidates=[[[lookup[cid] for cid in g] for g in groups]] if groups else [])
            counts['clustered_responses'] += sum(map(len, groups))
        payload = dict(variants=variants, history=dict(partitions=parts), history_loaded=True)
        case = dict(image_id=iid, title=f"{im['building']} · {im['number']:02} · {row['scene']}",
                    category='图片难度审核 · 算法候选与人工结论分开', history_image=True,
                    history_script=f'history/{index}.js', variants=[])
        cases.append(case)
        script = f'Object.assign(window.STUDIO_DATA.cases[{index}],{encoded(payload)});\n'
        script += f'{{const image={encoded(photo)};window.STUDIO_IMAGES[{index}]={{original:image,texture:image}};}}'
        (local / case['history_script']).write_text(script, encoding='utf-8')
    if not focus:
        assert counts['clustered_responses'] == 2152
    portable = dict(schema='image_difficulty_review_evidence_v1', source_v1=str(V1.relative_to(ROOT)),
                    source_v2=str(V2.relative_to(ROOT)), early_k_candidates=list(range(2, 9)), rows=rows,
                    human_reviews=0, image_bytes_included=False, focus=focus,
                    image_root='../../../../' if focus else '../../../',
                    note='生成可看工具不等于实际看图；尚未审核不等于确认算法类别')
    write_json(out / 'review_evidence.json', portable)
    write_json(out / 'coverage.json', dict(images=len(rows), historical_images=len(ids & cached.keys()), image_conditions=sum(len(r['units']) for r in rows), questions=len(queue),
               original_tags=len(ids & tags.keys()), tag_overlap=len(ids & historical & tags.keys()), candidate_counts=dict(collections.Counter(
               r['条件'] + ':' + (r['建议粗类_非最终'] or '未分类') for (i, _), r in latest.items() if i in ids)),
               human_reviews=0, fresh_hd_image_reviews=0, **counts))
    groups = [{'code': 'REVIEW_ALL', 'building': '全部研究图片（不是同房）', 'images': [dict(id=r['image_id'], number=r['number'],
               manual=int(latest.get((r['image_id'], 'manual'), {}).get('原作答人数', 0)),
               semi=int(latest.get((r['image_id'], 'semi'), {}).get('原作答人数', 0))) for r in rows]}]
    dataset = dict(cases=cases, counts=dict(cases=len(cases), variants=counts['reused_human_variants']), annotation_writeback=False)
    (local / 'data.js').write_text('window.STUDIO_IMAGES={};window.STUDIO_DATA=' + encoded(dataset) + ';\nwindow.STUDIO_HISTORY=' + encoded(dict(groups=groups)) + ';\nwindow.DIFFICULTY_REVIEW=' + encoded(portable) + ';', encoding='utf-8')
    for name in ['studio.js', 'studio.css', 'history.css', 'index.html']:
        (local / name).write_bytes((STUDIO / name).read_bytes())
    for name in ['three.min.js', 'OrbitControls.js']:
        (local / name).write_bytes((STUDIO.parent / name).read_bytes())
    history = (STUDIO / 'history.js').read_text(encoding='utf-8')
    old_rule = 'q_boundary、q_wallwall均≥0.95，点数不同必分开；≥2人称簇，单人标法保留。使用人工复核后点；分簇不是收敛结论。'
    assert old_rule in history
    history = history.replace(old_rule, '本轮d_mask完整链接阈值0.10；点数不同分开，支持簇至少2位不同人员。点集叠加为已确认计算视图；3D复用原始顺序，二者可能不同。分簇不等于合理解释或收敛。')
    history = history.replace('同房组 · 历史标注', '当前研究图片 · 真实作答对照').replace('同房展示组', '图片集合')
    history = history.replace('<option>Semi</option>', '<option>Semi</option><option>OOS</option>')
    (local / 'history.js').write_text(history, encoding='utf-8')
    (local / 'review.js').write_bytes((HERE / 'review_handoff.js').read_bytes())
    page = (local / 'index.html').read_text(encoding='utf-8')
    page = page.replace('<script defer src="studio.js"></script>', '<script defer src="studio.js"></script><script defer src="history.js"></script><script defer src="review.js"></script><link rel="stylesheet" href="history.css">')
    (local / 'index.html').write_text(page, encoding='utf-8')
    print(json.dumps(dict(images=len(rows), units=sum(len(r['units']) for r in rows), questions=len(queue), **counts)), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--focus39', action='store_true')
    run(parser.parse_args().focus39)
