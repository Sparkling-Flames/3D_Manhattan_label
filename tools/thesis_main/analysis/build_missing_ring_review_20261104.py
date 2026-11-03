"""盘点已保存的无完整来源环团队；为人工排序保留版本、成员及原生节点。"""
from pathlib import Path
import argparse
import collections
import gzip
import json
import subprocess
import re
import hashlib
import os
import html
import csv

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/fusion/missing_ring_review_20261104'
REASON = 'no_source_ring_covering_all_selected_nodes'


def inspect_row(row):
    state = row.get('full_state') or {}
    geom = row.get('geometry') or row.get('candidate') or {}
    state = state if isinstance(state, dict) else {}
    geom = geom if isinstance(geom, dict) else {}
    ring = state.get('ring_diagnostics') or row.get('ring_diagnostics') or {}
    candidate = state.get('candidate') or geom
    ring = ring if isinstance(ring, dict) else {}
    candidate = candidate if isinstance(candidate, dict) else {}
    return REASON in (row.get('geometry_reason'), geom.get('reason'),
                      ring.get('reason'), candidate.get('reason'))


def inventory():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = subprocess.check_output(['rg', '--files', '--no-ignore', 'research', 'analysis_results'], cwd=ROOT,
                                    text=True, encoding='utf8').splitlines()
    paths = sorted(p for p in paths if p.endswith(('.jsonl.gz', '.json.gz', '.json')) and 'missing_ring_review_20261104' not in p)
    previous = json.loads((OUT / 'SCAN.json').read_text(encoding='utf8')) if (OUT / 'SCAN.json').exists() else {'files': [], 'errors': []}
    counts = previous['files']; errors = previous['errors']
    done = {c['path'] for c in counts}
    paths = [p for p in paths if p not in done]
    with gzip.open(OUT / 'SOURCE_OCCURRENCES.jsonl.gz', 'at', encoding='utf8') as dest:
        for i, rel in enumerate(paths):
            hits = rows = 0
            try:
                opener = gzip.open if rel.endswith('.gz') else open
                with opener(ROOT / rel, 'rb') as stream:
                    lines = stream if rel.endswith('.jsonl.gz') else [stream.read()]
                    for line_no, line in enumerate(lines, 1):
                        rows += 1
                        if REASON.encode() not in line and b'no_connection' not in line:
                            continue
                        for row, pointer in nested_failures(json.loads(line)):
                            row = dict(row)
                            row['_review_source'] = rel.replace('\\', '/')
                            row['_review_line'] = line_no
                            row['_review_pointer'] = pointer
                            row['_exact_ring_reason'] = inspect_row(row)
                            dest.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                            hits += 1
            except (OSError, ValueError, EOFError) as error:
                errors.append({'path': rel, 'error': str(error)})
            counts.append({'path': rel, 'rows': rows, 'candidates': hits})
            if i % 500 == 0:
                (OUT / 'SCAN.json').write_text(json.dumps({'files': counts, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf8')
                print('scan', i, '/', len(paths), 'candidates', sum(c['candidates'] for c in counts), flush=True)
    (OUT / 'SCAN.json').write_text(json.dumps({'files': counts, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf8')
    print('inventory complete', len(paths), sum(c['candidates'] for c in counts), 'errors', len(errors), flush=True)


def nested_failures(value, pointer=''):
    if isinstance(value, dict):
        if inspect_row(value) or value.get('score_status') == 'no_connection':
            yield value, pointer
        else:
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    yield from nested_failures(child, pointer + '/' + str(key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from nested_failures(child, pointer + '/' + str(i))


def read(path):
    with (gzip.open(path, 'rt', encoding='utf8') if str(path).endswith('.gz') else open(path, encoding='utf8')) as f:
        return json.load(f)


def sequence(value):
    return value.split('|') if isinstance(value, str) else (value or [])


def load_inputs():
    names = [
        'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
        'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json',
        'research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz',
        'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz',
    ]
    pools = collections.defaultdict(list); objects = collections.defaultdict(list)
    for name in names:
        for pool in read(ROOT / name)['images']:
            pools[pool['pool_id']].append(pool)
            for r in pool['records']:
                objects[r.get('object_id', r['id'])].append((r, pool['meta']))
    name = 'research/fusion/doorway_population_v21_20261031/HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz'
    for oid, r in read(ROOT / name).items():
        objects[oid].append((r, {}))
    old = ROOT / 'analysis_results/direct_fusion_20261007/gap_sweep/population/inputs.json'
    if old.exists():
        for im in read(old)['images']:
            for r in im['records']:
                objects[r['id']].append((r, {'image': im['image'], 'image_id': im['image_id'], 'condition': '历史'}))
    return pools, objects


def selected_records(row, pools, objects):
    ids = sequence(row.get('member_object_ids'))
    workers = sequence(row.get('member_workers'))
    for pool in pools.get(row.get('pool_id'), []):
        own = {r['worker_id']: r for r in pool['records']}
        if workers and set(workers) <= own.keys():
            rr = [own[w] for w in sorted(workers)]
            if not ids or sorted(r['object_id'] for r in rr) == sorted(ids):
                return rr, pool['meta']
    rr = []; meta = {}
    for oid in ids:
        choices = objects.get(oid, [])
        distinct = {json.dumps(r['points'], sort_keys=True) for r, _ in choices}
        if len(distinct) != 1:
            raise ValueError('原答缺失或存在多个坐标版本: ' + oid)
        r, m = choices[0]; rr.append(r); meta.update(m)
    if not rr:
        raise ValueError('缺少可绑定的团队原答身份')
    return rr, meta


def state_records(state):
    points = collections.defaultdict(dict)
    for g in state['identity_groups']:
        for m in g['members']:
            points[m['id']][m['pair_index']] = m['points']
    rows = []
    for a in state['assignments']:
        own = points[a['id']]
        assert sorted(own) == list(range(len(a['feature_ids'])))
        rows.append({'id': a['id'], 'worker': a['worker'],
                     'points': [p for i in range(len(own)) for p in own[i]]})
    return rows


def prepare():
    from .consensus_delivery_20261008 import fuse, WORKING_GAP
    from .ring_correspondence_20261007 import build
    from .wall_consensus_v1_process_20261017 import cached_matching
    pools, objects = load_inputs()
    image_meta = {p['meta']['image']: p['meta'] for variants in pools.values() for p in variants}
    for rel in ['research/fusion/wall_consensus_v1_process_20261017/input_snapshot.json',
                'research/fusion/wall_consensus_quality_20261015/special/input_snapshot.json']:
        for im in read(ROOT/rel)['images']:
            image_meta.setdefault(im['image'], im)
    rows = {}; anonymous = 0
    with gzip.open(OUT / 'SOURCE_OCCURRENCES.jsonl.gz', 'rt', encoding='utf8') as f:
        for line in f:
            r = json.loads(line)
            state = r.get('full_state') or (r if r.get('node_consensus') else None)
            key = r.get('team_key') or r.get('physical_team_key')
            if not key:
                if state:
                    identity = [state['n'], state.get('assignments', state.get('identity_groups')), state['node_consensus']]
                    key = 'state:' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
                else:
                    anonymous += 1
                    continue  # Aggregate/status-only copies are not new identifiable teams.
            src = [r['_review_source'], r['_review_line'], r.get('_review_pointer', '')]
            if key not in rows:
                rows[key] = {'row': r, 'state': state, 'sources': []}
            own = rows[key]
            if state and not own['state']:
                own['state'] = state
            if r.get('member_object_ids') and not own['row'].get('member_object_ids'):
                own['row'] = r
            if src not in own['sources']:
                own['sources'].append(src)
    print('unique saved identities', len(rows), 'unbound copies', anonymous, flush=True)
    binding_file = OUT / 'SCALAR_BINDINGS.json'
    if binding_file.exists():
        for key, binding in read(binding_file).items():
            if key in rows:
                for field, value in binding.items():
                    if not rows[key]['row'].get(field): rows[key]['row'][field] = value
    (OUT / 'UNIQUE_INVENTORY.json.gz').write_bytes(gzip.compress(json.dumps(rows, ensure_ascii=False).encode()))
    ready = OUT / 'prepared'; ready.mkdir(exist_ok=True)
    errors = []; deferred = []; replayed = 0
    # All saved selected nodes are retained; replays only restore discarded intermediate geometry.
    with cached_matching() as match_cache:
        for i, (key, own) in enumerate(sorted(rows.items())):
            rid = hashlib.sha256(key.encode()).hexdigest()[:24]
            dest = ready / (rid + '.json.gz')
            if dest.exists():
                continue
            r = own['row']; state = own['state']; meta = {}
            try:
                if state:
                    records = state_records(state)
                else:
                    records, meta = selected_records(r, pools, objects)
                    state = (build(records, gap=WORKING_GAP) if len(records)==2 and (r.get('geometry') or {}).get('reason')==REASON
                             else fuse(records, gap=WORKING_GAP)['automatic']); replayed += 1
                    assert state['ring_diagnostics']['reason'] == REASON, '重放未复现无完整来源环'
                    assert r.get('nodes') is None or len(state['node_consensus']['nodes']) == r['nodes'], '节点数与保存值不同'
                    if r.get('node_supports'):
                        expected = [int(x) for x in sequence(r['node_supports'])]
                        assert [n['support'] for n in state['node_consensus']['nodes']] == expected, '节点票数与保存值不同'
                if state['candidate'].get('order_status') == 'two_person_sorting_deferred' or r.get('policy_deferred'):
                    deferred.append(key); continue
                nodes = state['node_consensus']['nodes']
                assert nodes and all(n['points'] is not None for n in nodes), '存在未定位节点，需要先处理对应/位置'
                image = r.get('image') or meta.get('image')
                if not image:
                    match = re.search(r'[A-Za-z0-9]{11}-\d{2}', key + ' ' + json.dumps(own['sources'][0]))
                    image = match.group() if match else None
                image_id = r.get('image_id') or meta.get('image_id')
                if not image_id and image in image_meta:
                    image_id = image_meta[image]['image_id']
                if not image_id:
                    for record in records:
                        options = objects.get(record.get('object_id', record['id']), [])
                        if options:
                            m = options[0][1]; image_id = m.get('image_id'); image = image or m.get('image')
                            if image_id: break
                assert image and image_id, '缺少图片绑定'
                result = dict(review_id=rid, team_key=key, image=image, image_id=image_id,
                              condition=r.get('condition', meta.get('condition', '待核对')),
                              k=state['n'], nodes=nodes, records=records,
                              ring_diagnostics=state['ring_diagnostics'], sources=own['sources'],
                              reference_id=r.get('reference_id'), reference_version=r.get('reference_version'),
                              data_release=r.get('data_release', r.get('underlying_data_version', '历史来源见记录')),
                              original_reason=REASON, recovered_from_raw=not bool(own['state']),
                              original_score_unchanged=True)
                dest.write_bytes(gzip.compress(json.dumps(result, ensure_ascii=False, allow_nan=False).encode()))
            except (AssertionError, ValueError, KeyError) as error:
                errors.append(dict(team_key=key, reason=str(error), sources=own['sources']))
            if i % 200 == 0:
                (OUT / 'PREPARE_PROGRESS.json').write_text(json.dumps(dict(processed=i,identities=len(rows),errors=errors,deferred=deferred),ensure_ascii=False,indent=2),encoding='utf8')
                print('prepare', i, '/', len(rows), 'errors', len(errors), flush=True)
                # Pairwise matches from unrelated images need not stay resident.
                if len(match_cache) > 50000: match_cache.clear()
    active_ids = [hashlib.sha256(key.encode()).hexdigest()[:24] for key in rows]
    (OUT / 'HISTORICAL_PREPARED_IDS.json').write_text(json.dumps(active_ids), encoding='utf8')
    (OUT / 'PREPARE.json').write_text(json.dumps(dict(identities=len(rows), unbound_status_copies=anonymous,
        replayed=replayed, deferred=deferred, errors=errors, prepared=sum((ready/(rid+'.json.gz')).exists() for rid in active_ids)), ensure_ascii=False, indent=2), encoding='utf8')
    print('prepare done', len(rows), 'errors', len(errors), flush=True)


def make_source(case):
    nodes = case['nodes']; points = [p for n in nodes for p in n['points']]
    return dict(object_id='missing_ring:' + case['review_id'], object_kind='fusion',
                canonical_annotation_id=case['team_key'], image_id=case['image_id'],
                worker_id='融合节点', raw_condition=f"{case['k']}人 · {case['condition']}",
                processing_status='没有完整来源环；等待人工排序', role='annotation',
                points=points, effective_points=points,
                effective_point_labels=[f"F{i//2+1}{'上' if i%2==0 else '下'}" for i in range(len(points))],
                original_point_ids_1based=[None]*len(points),
                links_zero_based=[[2*i,2*i+1] for i in range(len(nodes))],
                preprocessing='frozen_consensus_shared_x',
                default_preview_order=list(range(len(nodes))), ring_confirmed=False,
                feature_ids=[n['feature_id'] for n in nodes], node_supports=[n['support'] for n in nodes],
                review={}, review_metadata={k: case[k] for k in ('review_id','team_key','image','condition','k','sources','reference_id','reference_version','data_release')})


def build_pages():
    from .build_order_studio_20260926 import geometry_variant, encode
    active = set(read(OUT/'VALIDATED_REVIEW_IDS.json'))
    cases = [read(OUT/'prepared'/(rid+'.json.gz')) for rid in sorted(active)]
    with open(OUT/'TARGETED_MANUAL_CASES.csv',encoding='utf-8-sig',newline='') as f:
        group_ids={r['representative_review_id']:r['group_id'] for r in csv.DictReader(f)}
    by_image = collections.defaultdict(list)
    for c in cases: by_image[c['image']].append(c)
    pages = OUT / 'pages'; pages.mkdir(exist_ok=True)
    template = (ROOT / 'analysis_results/order_studio_20260926/index.html').read_text(encoding='utf8')
    for name in ['studio.js','studio.css','three.min.js','OrbitControls.js','order_studio.js','order_studio.css']:
        path = ROOT / ('tools/thesis_main/analysis/order_studio_20260926.' + name.split('.')[-1] if name.startswith('order_studio') else 'analysis_results/order_studio_20260926/' + name)
        template = template.replace('"'+name+'"', '"'+os.path.relpath(path,pages).replace(os.sep,'/')+'"')
    template = template.replace('</head>', '<style>#compare-grid{display:none}#panorama{visibility:hidden}.review-ready #panorama{visibility:visible}</style><script defer src="../review.js"></script></head>')
    photos = {p.stem:p for p in (ROOT/'data/mp3d_layout').glob('*/img/*.png')}
    entries=[]; missing=[]; raw_cache={}; geometries={}
    for image, group in sorted(by_image.items()):
        group.sort(key=lambda c:(-c['k'],c['team_key']))
        links=[]
        for start in range(0,len(group),40):
            batch=group[start:start+40]; name=f'current_verified__{image}__{start//40+1:04d}'
            dc=[]; images={}; raw={}
            for c in batch:
                if c['image_id'] not in photos:
                    missing.append(c['review_id']); continue
                s=make_source(c);s['review_metadata']['geometry_group_id']=group_ids[c['review_id']]
                sig=json.dumps(s['points'])
                if sig not in geometries:
                    geometries[sig]=geometry_variant('融合节点 · 待人工排序',s,s['points'],s['links_zero_based'])
                v=dict(geometries[sig],source=s)
                ids=[]
                for r in c['records']:
                    rid=hashlib.sha256(json.dumps([r['id'],r['points']],sort_keys=True).encode()).hexdigest()[:24]
                    if rid not in raw_cache:
                        p=r['points']; rs=dict(object_id='raw:'+rid,object_kind='raw_readonly',
                            canonical_annotation_id=r['id'],worker_id=r['worker'],raw_condition='完整原答 · 只读',
                            processing_status='冻结原答顺序',role='annotation',points=p,effective_points=p,
                            links_zero_based=[[i,i+1] for i in range(0,len(p),2)],
                            original_point_ids_1based=list(range(1,len(p)+1)),review={})
                        raw_cache[rid]=geometry_variant(r['worker']+' · 完整原答',rs,p,rs['links_zero_based'])
                    raw[rid]=raw_cache[rid]; ids.append(rid)
                dc.append(dict(title=f"{image} · {c['k']}人 · {c['review_id'][:6]}",image_id=c['image_id'],
                    category='自动连线未完成 · 人工排序复核',variants=[v],raw_ids=ids,room_id='',annotation_ids=[s['object_id']]))
                url=os.path.relpath(photos[c['image_id']],pages).replace(os.sep,'/')
                images[len(dc)-1]=dict(original=url,texture=url)
            if not dc: continue
            dataset=dict(cases=dc,counts=dict(cases=len(dc),variants=len(dc)),manifest=dict(
                export_schema='missing_ring_order_review_20261104_v1',examples_only=False,
                review_round='missing_source_ring_20261104',formal_data_connected=False))
            script='window.STUDIO_IMAGES='+encode(images)+';window.STUDIO_DATA='+encode(dataset)+';window.RAW_REVIEW_SOURCES='+encode(raw)+';'
            script+='window.STUDIO_DATA.cases.forEach(c=>c.variants.push(...c.raw_ids.map(id=>window.RAW_REVIEW_SOURCES[id])));'
            (pages/(name+'.js')).write_text(script,encoding='utf8')
            (pages/(name+'.html')).write_text(template.replace('"data.js"','"'+name+'.js"'),encoding='utf8')
            links.append(dict(path='pages/'+name+'.html',start=start+1,end=start+len(dc)))
        entries.append(dict(image=image,cases=len(group),links=links))
        print('pages',image,len(group),flush=True)
    (OUT/'PAGE_INDEX.json').write_text(json.dumps(dict(images=entries,missing_photos=missing),ensure_ascii=False,indent=2),encoding='utf8')
    rows=[]
    for e in entries:
        ll=' '.join(f'<a href="{x["path"]}">{x["start"]}–{x["end"]}</a>' for x in e['links'])
        rows.append(f'<tr><td>{html.escape(e["image"])}</td><td>{e["cases"]}</td><td>{ll}</td></tr>')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>融合节点人工排序复核</title>
<style>body{font:17px/1.7 system-ui;margin:32px auto;max-width:1150px;padding:0 20px;color:#193247}h1{font-size:28px}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #ccd8df;padding:10px;text-align:left}a{display:inline-block;margin:3px 8px 3px 0;color:#00647a}input{font:inherit;padding:8px;width:330px}.note{background:#edf4f8;padding:16px}</style>
<h1>融合节点人工排序复核</h1><p>这些团队已经选出节点，但没有一份原答的投影环覆盖全部入选节点。请查看原图和完整原答，判断能否只调整顺序得到合理布局。</p>
<div class="note">这里只分配当前半队、Q-only、变化联盟及普通主目标满员中的代表连接诊断；全部失败库存不作为人工任务。每页最多40项，完全相同节点坐标已合并。<br>默认不显示闭合布局，编号不代表环序。查看原图和完整原答后，拖动点对或填写排列，再选择“采用这个顺序”；如需删点或改位置，选择“节点或位置有问题”。三维连线必须主动开启，仅作预览。<br>记录自动保存在本页浏览器中；每页完成后导出 JSON。人工答案仅进入单独辅助分析，不覆盖自动失败、参考或分数。<a href="CURRENT_REAUDIT.md">完整核查与结论影响</a></div>
<p>COUNT</p><p><a href="unresolved.html">尚不能直接排序的结果</a> · <a href="README.md">操作与数据说明</a></p><label>查找图片 <input id="search" placeholder="例如 S9hNv5qa7GM-04"></label><table><thead><tr><th>图片</th><th>待复核结果</th><th>分批打开</th></tr></thead><tbody>ROWS</tbody></table>
<script>document.getElementById('search').oninput=e=>document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase()));</script><script src="export_all.js"></script></html>'''
    with open(OUT/'CURRENT_UNPREPARED.csv',encoding='utf-8-sig',newline='') as f:
        receipt={'errors':[r for r in csv.DictReader(f) if r['reason']=='存在未定位节点，需要先处理对应/位置']}
    unresolved_rows = ''.join('<tr><td>'+html.escape(e['team_key'])+'</td><td>'+html.escape(e['reason'])+'</td></tr>' for e in receipt['errors'])
    (OUT/'unresolved.html').write_text('<!doctype html><meta charset="utf-8"><title>尚不能直接排序的结果</title><style>body{font:16px/1.6 system-ui;margin:30px}td{padding:8px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}</style><a href="index.html">返回复核工作台</a><h1>尚不能直接排序的结果</h1><p>以下结果缺少确定节点坐标或身份绑定，未生成可采用的排序。保留原始状态，不能算作人工确认或已修复。</p><table><tr><th>保存身份</th><th>原因</th></tr>'+unresolved_rows+'</table>',encoding='utf8')
    count=f'{len(cases):,}个已恢复节点的结果，涉及{len(entries)}张图片。另有{len(receipt["errors"])}项待解决数据绑定/状态问题；见复核清单说明。'
    if (OUT/'user_order_return/IMPORT_RECEIPT.json').exists():
        returned=read(OUT/'user_order_return/IMPORT_RECEIPT.json')
        count+=f'<p>已回收{int(returned["records"])}组人工判断；<a href="user_order_return/README.md">回收索引与Pro接续任务</a>。辅助几何和评分是否完成，以接续回执为准。</p>'
    (OUT/'index.html').write_text(page.replace('COUNT',count).replace('ROWS','\n'.join(rows)),encoding='utf8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--phase', choices=['inventory', 'prepare', 'pages'], default='inventory')
    a = p.parse_args()
    {'inventory': inventory, 'prepare': prepare, 'pages': build_pages}[a.phase]()
