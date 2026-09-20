"""Build a run-bound RC1 review using the existing Panorama Studio foundation."""
import argparse
import copy
import csv
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FOUNDATION = REPO / 'analysis_results/panorama_studio_20260907_v3'
SCHEMA = 'clustering_release_visual_review_v1'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def table(p):
    with p.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def verify_run(run_root, *, numerical_only=False):
    manifest = read(run_root/'RUN_MANIFEST.json')
    run_id = manifest['run_id']
    result_manifest = read(run_root/'results/RESULT_MANIFEST.json')
    publication = read(run_root/'results/PUBLICATION_CHECK.json')
    if result_manifest['run_id'] != run_id or publication['run_id'] != run_id or publication['numerical_gate'] != 'passed':
        raise ValueError('输入与结果运行版本不一致或数值检查未通过')
    required = {'cache.json', 'memberships.csv', 'point_ordinals.csv', 'minimal_local_check.csv', 'PUBLICATION_CHECK.json'}
    if not required <= set(result_manifest['files']) or 'inputs/responses.jsonl.gz' not in manifest['input_files']:
        raise ValueError('运行清单缺少审核必需文件')
    for base, entries in [(run_root, manifest['input_files']), (run_root/'results', result_manifest['files'])]:
        for name, expected in entries.items():
            path = (base/name).resolve()
            if not path.is_relative_to(base.resolve()):
                raise ValueError('运行清单文件缺失或越界: '+name)
            display_prefix = 'input/source/analysis_results/paired_split_research_received_20260920/'
            if (numerical_only and base == run_root and name.endswith('.jpg')
                    and any(name.startswith(display_prefix+sub+'/') for sub in ('history_visual_review', 'visual_checked'))):
                continue  # Display-only dependencies; numerical consumers never load these photos.
            if not path.is_file():
                raise ValueError('运行清单文件缺失或越界: '+name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('运行清单内容不一致: '+name)
    for p in (run_root/'inputs/user_reviews').glob('*.json'):
        if p.relative_to(run_root).as_posix() not in manifest['input_files']:
            raise ValueError('用户原文未登记进运行清单: '+p.name)
    return manifest


def check_ordinals(coords, records):
    """Reject results computed on another point revision before building a page."""
    if coords is None or sorted(int(o['point_index_1based']) for o in records) != list(range(1, len(coords)+1)):
        raise ValueError('结果端点编号未完整对应当前计算点')
    for o in records:
        x, y = coords[int(o['point_index_1based'])-1]
        if abs(float(o['x'])-x) > 1e-7 or abs(float(o['y'])-y) > 1e-7:
            raise ValueError('结果坐标与当前计算点版本不一致')


def validate_review(value, binding, keys):
    """Same checks as the browser importer; never reinterpret legacy answers."""
    if value.get('schema') != SCHEMA or value.get('binding') != binding:
        raise ValueError('审核版本或点集不匹配')
    decisions = value.get('decisions')
    if not isinstance(decisions, dict):
        raise ValueError('缺少裁决对象')
    for key, decision in decisions.items():
        if key not in keys or not isinstance(decision, dict):
            raise ValueError('未知图片或答案')
        if (decision.get('relation') not in ['', '可视为相近', '应分开保留差异', '暂不能判断']
                or not isinstance(decision.get('comment'), str)
                or not isinstance(decision.get('defer'), bool)):
            raise ValueError('裁决字段无效')
    return decisions


def user_records(value, iid):
    """Preserve complete matching objects, including notes with blank dropdowns."""
    if isinstance(value, list):
        return [item for child in value for item in user_records(child, iid)]
    if isinstance(value, dict):
        if value.get('image_id') == iid or str(value.get('key', '')).startswith(iid+'|'):
            return [value]
        found = []
        for key, child in value.items():
            if key == iid or key.startswith(iid+'|'):
                found.append({'key': key, 'original': child})
            else:
                found.extend(user_records(child, iid))
        return found
    return []


def build(run_root, visual_root, out):
    run_root, visual_root, out = map(Path, (run_root, visual_root, out))
    manifest = verify_run(run_root)
    result = run_root/'results'
    cache = read(result/'cache.json')
    with gzip.open(run_root/'inputs/responses.jsonl.gz', 'rt', encoding='utf-8') as f:
        responses = [json.loads(line) for line in f]
    by = {r['canonical_annotation_id']: r for r in responses}
    if len(by) != len(responses):
        raise ValueError('重复 canonical 身份')
    members, ordinals = table(result/'memberships.csv'), table(result/'point_ordinals.csv')
    choices = table(result/'minimal_local_check.csv')
    chosen = {r['image_id'] for r in choices}
    choices += [r for r in read(visual_root/'selected_b.json') if r['image_id'] not in chosen]
    if len(choices) != 16 or len({r['image_id'] for r in choices}) != 16:
        raise ValueError('首批必须恰好 16 张不重复图片')
    choices.sort(key=lambda r: (int(r.get('priority', 2)), r['code']))
    findings = []
    for name in ['agent_a.json', 'agent_b.json']:
        value = read(visual_root/name)
        findings.extend(value if isinstance(value, list) else value['cases'])
    reviews = [(p.name, read(p)) for p in sorted((run_root/'inputs/user_reviews').glob('*.json'))]
    hs = (FOUNDATION/'history_data.js').read_text(encoding='utf-8')
    lookup = {r['image_id']: r for r in json.JSONDecoder().raw_decode(hs.split('push(...', 1)[1])[0]}
    cases, images, points = [], [], {}
    for index, selection in enumerate(choices):
        iid, condition = selection['image_id'], selection['condition']
        key = iid+'|'+condition
        g = cache[key]
        raw = (FOUNDATION/lookup[iid]['history_script']).read_text(encoding='utf-8')
        original = json.JSONDecoder().raw_decode(raw.split('],', 1)[1])[0]
        source_variants = {v['source']['canonical_annotation_id']: v for v in original['variants']}
        ids = g['ids'] + sorted(r['canonical_annotation_id'] for r in responses
                               if r['image_id'] == iid and r['raw_condition'] == condition
                               and r['canonical_annotation_id'] not in g['ids'])
        vv = []
        for cid in ids:
            row = by[cid]
            coords = row['effective_points_1024x512']
            point_ordinals = [o for o in ordinals if o['id'] == cid]
            if cid in g['ids']:
                check_ordinals(coords, point_ordinals)
                if row['worker_id'] != g['workers'][g['ids'].index(cid)]:
                    raise ValueError('结果人员与当前身份不一致')
            display_points = coords if coords is not None else (row.get('raw_points_1024x512') or [])
            points[cid] = digest({'image_id': iid, 'condition': condition, 'worker': row['worker_id'],
                                  'points': coords, 'raw_points': row.get('raw_points_1024x512')})
            v = copy.deepcopy(source_variants.get(cid, {'name': cid, 'geometry': None, 'source': {}}))
            if coords is None or v['source'].get('effective_points') != coords:
                v.update(geometry=None, error='点集已更新／无对应历史3D；以当前二维点集为准')
            v['source'].update(canonical_annotation_id=cid, effective_points=coords,
                               display_points=display_points,
                               points_display_kind='计算点' if coords is not None else '无计算点；只展示原始点',
                               worker_id=str(row['worker_id']).removeprefix('W'), mode=condition.title(),
                               current_row=row, point_set_digest=points[cid], primary_eligible=cid in g['ids'])
            v['name'] = f"{row['worker_id']} · {condition.title()} · {len(display_points)}点 · {v['source']['points_display_kind']}"
            v['source']['ordinals'] = point_ordinals
            vv.append(v)
        labels = {}
        for metric, cut in [('split_cyclic', 9), ('split_cyclic', 6), ('split_cyclic', 12), ('ospa_gate', 6)]:
            mapping = {m['id']: m['cluster'] for m in members if m['image_id'] == iid
                       and m['condition'] == condition and m['metric'] == metric and float(m['cut']) == cut}
            if set(mapping) != set(g['ids']):
                raise ValueError('成员表与距离缓存不一致: '+key)
            labels[f'{metric}_{cut}'] = [mapping.get(cid, 'unavailable') for cid in ids]
        pair = [selection['id_a'], selection['id_b']]
        ia, ib = [g['ids'].index(cid) for cid in pair]
        dm = g['matrices']['split_cyclic']
        lab = labels['split_cyclic_9']
        cross = [(dm[a][b], a, b) for a in range(len(g['ids'])) for b in range(len(g['ids']))
                 if lab[a] == lab[ia] and lab[b] == lab[ib] and a != b]
        maxdist, a, b = max(cross) if cross else (dm[ia][ib], ia, ib)
        detail = [dict(ids=pair, workers=[by[c]['worker_id'] for c in pair], distance=dm[ia][ib], kind='指定作答对'),
                  dict(ids=[g['ids'][a], g['ids'][b]], workers=[g['workers'][a], g['workers'][b]], distance=maxdist,
                       kind='两簇最大跨簇距离' if lab[ia] != lab[ib] else '该簇最大距离')]
        record = dict(selection, key=key, ids=ids, labels=labels, pairs_detail=detail,
                      ai=[n for n in findings if n.get('image_id') == iid or n.get('code') == selection['code']],
                      user_original=[{'file': name, 'records': found} for name, value in reviews
                                     if (found := user_records(value, iid))], user_decision=None,
                      point_numbering='p 是本运行计算点数组的一基序号；有删补时不等于旧导出编号。无计算点记录显示原始数组序号。',
                      coverage='AI覆盖范围以逐条意见为准；界面可查看整图所有作答，不能据此称已全部目视')
        cases.append(dict(image_id=iid, title=selection['code']+' · '+condition, category='RC1 分簇视觉验收',
                          variants=vv, followup=record))
        photo = re.search(r'\{const image="(data:image/[^"\r\n]+)"', raw).group(1)
        images.append(f'{{const image={json.dumps(photo)};window.STUDIO_IMAGES[{index}]={{original:image,texture:image}};}}')
    binding = {'manifest': digest(manifest), 'point_sets': points,
               'review_content': digest([c['followup'] for c in cases]),
               'review_panel': hashlib.sha256(Path(__file__).with_name('release_review_panel.js').read_bytes()).hexdigest(),
               'results': {name: hashlib.sha256((result/name).read_bytes()).hexdigest()
                           for name in ['cache.json', 'memberships.csv', 'point_ordinals.csv']}}
    binding['id'] = digest(binding)
    out.mkdir(parents=True, exist_ok=True)
    for name in ['studio.js', 'studio.css', 'history.css', 'three.min.js', 'OrbitControls.js']:
        shutil.copyfile(FOUNDATION/name, out/name)
    shutil.copyfile(Path(__file__).with_name('release_review_panel.js'), out/'followup.js')
    html = (FOUNDATION/'index.html').read_text(encoding='utf-8')
    html = re.sub(r'<script[^>]*src="(?:image_\d+|history_data|history)\.js"[^>]*></script>', '', html)
    html = html.replace('</body>', '<script defer src="followup.js"></script></body>')
    html = html.replace('<title>空间标本 · 全景布局审查</title>', '<title>16图 · RC1分簇视觉验收</title>')
    (out/'index.html').write_text(html, encoding='utf-8')
    payload = dict(cases=cases, counts={'cases': len(cases), 'variants': sum(len(c['variants']) for c in cases)},
                   binding=binding, schema=SCHEMA)
    (out/'data.js').write_text('window.STUDIO_DATA='+json.dumps(payload, ensure_ascii=False, allow_nan=False)+
                              ';\nwindow.STUDIO_IMAGES={};\n'+'\n'.join(images), encoding='utf-8')
    (out/'REVIEW_MANIFEST.json').write_text(json.dumps(dict(binding=binding, cases=[c['followup'] for c in cases]),
                                           ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-root', required=True, type=Path)
    ap.add_argument('--visual-root', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    result = build(args.run_root, args.visual_root, args.out)
    print(json.dumps(result['counts']))
