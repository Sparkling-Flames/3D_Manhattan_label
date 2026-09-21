"""按结构增减应分簇的既有规则，复用Studio制作独立筛查页。"""
from collections import Counter
import base64
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.paired_split_research.release_review import FOUNDATION, SCHEMA, digest
from tools.label_studio.panorama_studio.geometry import analyze

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'analysis_results/panorama_research_received_20260921'
OUT = ROOT / 'analysis_results/cluster_screen_20260921'
RULE = '结构多画或少画属于不同表达，应分簇；奇数点另行复核。本轮主要核验同点数的对应、定位差与整簇一致性。'


def select_cases(pairs, excluded):
    q = pairs[pairs.same_count & (pairs.N >= 8) & ~pairs.image_id.isin(excluded)].copy()
    q = q.sort_values(['code', 'a_id', 'b_id'])
    q['gap'] = abs(q.fixed_max - 25.6)
    q['random'] = np.random.default_rng(20260921).random(len(q))
    rules = [
        ('对应核查', (q.fixed_max > 25.6) & (q.free_max <= 25.6), 2, 'fixed_max', False),
        ('近邻被拆', (q.fixed_max <= 25.6) & ~q.complete_same, 4, 'fixed_max', True),
        ('同簇远邻', (q.fixed_max > 25.6) & q.representative_same, 4, 'fixed_max', False),
        ('阈值外侧', (q.fixed_max > 25.6) & (q.fixed_max <= 34.134), 3, 'gap', True),
        ('阈值内侧', (q.fixed_max >= 17.066) & (q.fixed_max <= 25.6), 3, 'gap', True),
        ('普通对照', ((q.fixed_max <= 25.6) & q.complete_same & q.representative_same) |
                    ((q.fixed_max > 25.6) & ~q.complete_same & ~q.representative_same & (q.free_max > 25.6)),
         24, 'random', True),
    ]
    selected, seen, buildings = [], set(), Counter()
    for reason, mask, quota, order, ascending in rules:
        used = 0
        for _, row in q[mask].sort_values([order, 'code', 'a_id', 'b_id'], ascending=[ascending, True, True, True]).iterrows():
            if row.image_id in seen or buildings[row.building] >= 3:
                continue
            selected.append(dict(row.to_dict(), selection_reason=reason))
            seen.add(row.image_id); buildings[row.building] += 1; used += 1
            if used == quota or len(selected) == 24:
                break
        if len(selected) == 24:
            break
    return selected


def references(value):
    if isinstance(value, dict):
        result = {value[k] for k in ('image_id', 'code') if isinstance(value.get(k), str)}
        if isinstance(value.get('key'), str):
            result.add(value['key'].split('|')[0])
        for v in value.values():
            result |= references(v)
        return result
    if isinstance(value, list):
        return set().union(*(references(x) for x in value))
    return set()


def build():
    sys.path.insert(0, str(PACKAGE / 'original_package/code'))
    import common as c
    c.configure(PACKAGE / 'local_recompute/source_work')
    _, records, views, registry, _ = c.load()
    image_paths = {r['image_id']: ROOT / r['path'] for r in registry['images']}
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    source = c.SOURCE
    evidence = [source / 'analysis_results/clustering_release_local_20260920/current/inputs' / name
                for name in ('key39_source.json', 'pilot_evidence.json', 'new_six_evidence.json')]
    evidence += [ROOT / 'analysis_results/local_point_clustering_20260920/evidence/review_manifest_16.json',
                 ROOT / 'analysis_results/local_point_clustering_20260920/evidence/latest_decisions.json',
                 ROOT / 'analysis_results/cluster_review_extra_20260919/evidence.json']
    seen = set().union(*(references(read(p)) for p in evidence))
    # New intake's first eight point/version questions are already adjudicated.
    intake_manifest = ROOT / 'analysis_results/new_manual_analysis_20260921/审核/REVIEW_MANIFEST.json'
    for case in read(intake_manifest)['cases'][:8]:
        seen.add(case['key'].split('|')[0])
    excluded = {iid for iid, v in views.items() if iid in seen or v['code'] in seen}
    pair = pd.read_csv(PACKAGE / 'original_package/results/pair_diagnostics.csv.gz')
    members = pd.read_csv(PACKAGE / 'original_package/results/current_memberships.csv')
    for method in ('complete', 'representative'):
        labels = members[members.method == method].set_index('id').label
        pair[method + '_same'] = pair.a_id.map(labels) == pair.b_id.map(labels)
    selected = select_cases(pair, excluded)
    assert len(selected) == 24, '不足24张未审核候选，不自动复用已裁决图片'
    assert not {x['code'] for x in selected} & {'uNb9QFRL6hY-21', 'uNb9QFRL6hY-40'}
    summaries = json.JSONDecoder().raw_decode((FOUNDATION / 'history_data.js').read_text(encoding='utf8').split('push(...', 1)[1])[0]
    photo_lookup = {s['image_id']: s for s in summaries}
    OUT.mkdir(parents=True, exist_ok=True)
    cases, photos = [], []
    for index, item in enumerate(selected):
        v = views[item['image_id']]; variants = []; labels = {}; pairs = {}
        by_id = dict(zip(v['ids'], v['rows']))
        for cid in v['ids']:
            r = records[cid]; row = by_id[cid]; points = r['p'].tolist()
            assert len(points) % 2 == 0 and not row['imputed_point']
            ordered = [dict(source_pair_id=f'raw:{a+1}/{b+1}', top=dict(zip(('x', 'y'), points[a])),
                            bottom=dict(zip(('x', 'y'), points[b]))) for a, b in r['links']]
            geom, error = None, None
            try:
                geom = analyze(dict(width=1024, height=512, coordinate_mode='pixels', ordered_pairs=ordered))
            except ValueError as exc:
                error = '3D不可用；仍可看二维原点：' + str(exc)
            variants.append(dict(name=f"{row['worker_id']} · {len(points)}点", geometry=geom, error=error,
                source=dict(canonical_annotation_id=cid, worker_id=row['worker_id'][1:], mode=row['raw_condition'],
                            display_points=points, effective_points=points, points_display_kind='当前有效点', current_row=row)))
        ia, ib = [v['ids'].index(item[k]) for k in ('a_id', 'b_id')]
        assert np.isclose(v['d'][ia, ib], item['fixed_max'])
        for method in ('complete', 'representative'):
            lab, centres = c.part(v['d'], v['ids'], method)
            labels[method] = lab.tolist()
            assert bool(lab[ia] == lab[ib]) == item[method + '_same']
            ga, gb = np.flatnonzero(lab == lab[ia]), np.flatnonzero(lab == lab[ib])
            cross = v['d'][np.ix_(ga, gb)]; a, b = np.unravel_index(cross.argmax(), cross.shape)
            witness = [int(ga[a]), int(gb[b])]
            choices = [('指定作答对（下拉结论对象）', [ia, ib]), ('簇内最远成员' if lab[ia] == lab[ib] else '两簇最远阻挡成员', witness)]
            for idx in (ia, ib):
                center = v['ids'].index(centres[lab[idx] - 1])
                if center != idx:
                    choices.append(('指定作答与本簇真人代表', [idx, center]))
            pairs[method] = [dict(kind=title, ids=[v['ids'][i] for i in ix], workers=[v['workers'][i] for i in ix],
                                 distance=float(v['d'][ix[0], ix[1]]), unit='像素') for title, ix in choices]
        followup = dict(key=v['image_id'] + '|cluster_screen_20260921', code=v['code'], condition='Manual/OOS',
            reasons='请判断指定两份是否应同簇；若应分开，请写差异所在点号及原因。再切换阻挡成员或真人代表检查整簇。',
            ids=v['ids'], labels=labels, pairs_by_method=pairs,
            decision_options=['同一表达，可同簇', '不同表达，应分开', '对应需核查，暂缓', '暂不能判断'],
            coverage='本轮工作核验；不是盲审或独立验证集',
            point_numbering='p为当前有效点数组1-based编号，不自动表示跨人对应；3D连线仅辅助。',
            ai=[], user_original=[], user_decision=None,
            research_notes=dict(rule=RULE, selection=item, pairs_effective_1based={cid:(records[cid]['links']+1).tolist() for cid in v['ids']}))
        cases.append(dict(image_id=v['image_id'], title=f"{v['code']} · 第{index+1}题", category='分簇工作版 · 结构增减分开', variants=variants, followup=followup))
        if v['image_id'] in photo_lookup:
            raw = (FOUNDATION / photo_lookup[v['image_id']]['history_script']).read_text(encoding='utf8')
            match = re.search(r'\{const image="(data:image/[^;]+;base64,[^"]+)"', raw)
            if match is None:
                raise ValueError('缺少本地原图：' + v['image_id'])
            image_data = match.group(1)
        else:
            path = image_paths[v['image_id']]
            assert path.suffix == '.png'
            image_data = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
        # One embedded image per case; works offline without filesystem fetch permissions.
        photos.append(f'{{const image={json.dumps(image_data)};window.STUDIO_IMAGES[{index}]={{original:image,texture:image}};}}')
    cases = c.clean(cases)
    binding = dict(rule=RULE, input=digest([case['followup'] for case in cases]),
                   points=digest([[v['source']['display_points'] for v in case['variants']] for case in cases]))
    binding['id'] = digest(binding)
    payload = dict(schema=SCHEMA, binding=binding, cases=cases, counts=dict(cases=len(cases), variants=sum(len(x['variants']) for x in cases)),
        review_title='24图分簇筛查 · 沿用结构增减分开规则', export_filename='分簇筛查24图_我的审核.json',
        review_instructions=RULE + ' 先看指定两份，点图点击可放大；再看阻挡成员及整簇。数值是工作对照，不是正确答案。',
        decision_instructions='下拉只针对最初指定作答对。其他成员请在文字中写人员、点号和判断。若只是定位偏差，请说明是否大到需要分开；结构增减直接按应分开处理。质量疑点另写，不把少数自动判错。',
        method_options=[dict(value='complete', label='完整链接 · 25.6px'), dict(value='representative', label='真人代表半径 · 25.6px')])
    for name in ('studio.js', 'studio.css', 'history.css', 'three.min.js', 'OrbitControls.js'):
        shutil.copyfile(FOUNDATION / name, OUT / name)
    panel = (ROOT / 'tools/thesis_main/analysis/paired_split_research/release_review_panel.js').read_text(encoding='utf8')
    panel = panel.replace('原图／历史3D', '原图／条件3D')
    panel += "\n(()=>{const members=document.getElementById('history-clusters'),heading=members.previousElementSibling,box=document.createElement('details'),summary=document.createElement('summary');summary.textContent='展开整图成员，逐簇检查混入或过拆';heading.before(box);box.append(summary,heading,members);})();\n"
    (OUT / 'followup.js').write_text(panel, encoding='utf8')
    html = (FOUNDATION / 'index.html').read_text(encoding='utf8')
    html = re.sub(r'<script[^>]*src="(?:image_\d+|history_data|history)\.js"[^>]*></script>', '', html)
    html = html.replace('</body>', '<script defer src="followup.js"></script></body>').replace('<title>空间标本 · 全景布局审查</title>', '<title>24图分簇筛查</title>')
    (OUT / 'index.html').write_text(html, encoding='utf8')
    (OUT / 'data.js').write_text('window.STUDIO_DATA=' + json.dumps(payload, ensure_ascii=False, allow_nan=False) + ';\nwindow.STUDIO_IMAGES={};\n' + '\n'.join(photos), encoding='utf8')
    manifest = dict(binding=binding, cases=[x['followup'] for x in cases], selection_counts=Counter(x['selection_reason'] for x in selected),
                    buildings=len({x['building'] for x in selected}), excluded_reviewed_images=sorted(excluded),
                    prior_evidence=[str(p.relative_to(ROOT)) for p in evidence] + [str(intake_manifest.relative_to(ROOT))],
                    protocol_changed=False, odd_points_separate=True, decisions_prefilled=False)
    (OUT / 'REVIEW_MANIFEST.json').write_text(json.dumps(c.clean(manifest), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')
    print(json.dumps(dict(payload['counts'], selection=manifest['selection_counts'], buildings=manifest['buildings'], excluded_images=len(excluded)), ensure_ascii=False))


if __name__ == '__main__':
    build()
