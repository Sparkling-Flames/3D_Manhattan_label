"""Read-only review evidence. Imported handoff code remains an immutable exhibit.

No clustering, fitting, coordinate editing, or automatic visual conclusions.
Optional point permutations are separate preview proposals pending human judgment.
"""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import importlib.util
import io
import html
import json
import sys
import urllib.request

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / 'analysis_results/uncertainty_handoff_received_20260907_v1/original_package'
OUT = ROOT / 'analysis_results/uncertainty_visual_review_20260907_v1'


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True  # Keep the received archive free of generated caches.
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


def helpers():
    audit = module('audit', ARCHIVE / 'review_code/audit.py')
    audit.ROOT = ROOT
    audit.P = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
    audit.O = OUT / 'reproduced_numerical'
    renderer = module('handoff_renderer', ROOT / 'tools/thesis_main/analysis/uncertainty_review_renderer.py')
    return audit, renderer


def studio_data(text):
    """Decode exactly STUDIO_DATA, rather than the preceding STUDIO_IMAGES assignment."""
    marker = 'window.STUDIO_DATA='
    if text.count(marker) != 1:
        raise ValueError('Expected one STUDIO_DATA assignment')
    data, end = json.JSONDecoder().raw_decode(text.split(marker, 1)[1].lstrip())
    tail = text.split(marker, 1)[1].lstrip()[end:].strip()
    if tail not in ('', ';') or not isinstance(data.get('cases'), list):
        raise ValueError('Unexpected studio data suffix or schema')
    return data


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def preview_order(points, audit):
    """Propose a preview-only permutation after an observed serialization failure.

    1 px is a conservative pairing lookup tolerance, never a quality criterion.
    Azimuth order assumes a visible star-shaped ring; the proposal requires vision
    review and cannot establish the original author's intended adjacency.
    """
    try:
        audit.footprint(points)
    except ValueError as error:
        if str(error) not in ('invalid_original_order_polygon', 'adjacent_pair_same_hemisphere'):
            raise ValueError('unsupported_failure: ' + str(error)) from error
    else:
        raise ValueError('already_computable_no_reorder')
    p = np.asarray(points, float)
    try:
        _, mapping = audit.roles(points)
        pairs = np.array(mapping).reshape(-1, 2).tolist()
        method = 'existing_pairs_azimuth_order'
    except ValueError:
        tops = np.flatnonzero(p[:, 1] < 256)
        bottoms = np.flatnonzero(p[:, 1] > 256)
        if len(tops) != len(bottoms) or len(tops) * 2 != len(p):
            raise ValueError('unequal_endpoint_roles')
        pairs = []
        for t in tops:
            candidates = bottoms[abs((p[bottoms, 0] - p[t, 0] + 512) % 1024 - 512) <= 1.0]
            if len(candidates) != 1:
                raise ValueError('nonunique_vertical_pairing')
            pairs.append([int(t), int(candidates[0])])
        if len({b for t, b in pairs}) != len(bottoms):
            raise ValueError('nonunique_vertical_pairing')
        method = 'unique_vertical_pairing_then_azimuth_order'
    pairs.sort(key=lambda pair: p[pair[1], 0] % 1024)
    mapping = [int(i) for pair in pairs for i in pair]
    proposed = [points[i] for i in mapping]
    audit.footprint(proposed)
    return proposed, mapping, method


def adjustments():
    audit, renderer = helpers()
    # Written observations are independent evidence; rendering never fills them.
    viewed = set()
    for name in ('comparison_notes.json', 'comparison_notes_expansion.json'):
        viewed.update(json.loads((OUT / name).read_text(encoding='utf-8')))
    rows = []
    for file in sorted((OUT / 'cases').glob('*/render_log.json')):
        assert file.parent.name in viewed
        for original in json.loads(file.read_text(encoding='utf-8')):
            if original['status'] != 'failed':
                continue
            record = dict(case_id=original['case_id'], variant=original['variant'], source_id=original['source_id'], original_error=original['error'], human_final_judgment=None, original_coordinates_changed=False, status='unresolved', visually_reviewed=False)
            source = json.loads((file.parent / (original['variant'] + '_source.json')).read_text(encoding='utf-8'))
            if not (source['name'].startswith('human_') or source['name'].startswith('reference_')):
                record['reason'] = 'model_degeneracy_not_repaired'
                rows.append(record)
                continue
            try:
                proposed, mapping, method = preview_order(source['points'], audit)
                record.update(status='proposed_unreviewed', method=method, old_point_id_for_new_index=mapping, original_points=source['points'], preview_points=proposed, pairing_changed=method.startswith('unique_'), adjacency_changed=True)
                texture = np.asarray(Image.open(OUT / 'images' / (original['image_id'] + '.jpg')).convert('RGB'))
                floor, top, _ = audit.lift(proposed)
                after = Image.new('RGB', (1024, 320), 'white')
                ImageDraw.Draw(after).text((5, 5), 'PREVIEW PROPOSAL; original point IDs; no coordinate edit', fill='black', font=renderer.FONT)
                overlay, _ = renderer.overlay(texture, proposed, True, point_ids=mapping)
                after.paste(overlay.resize((512,256)), (0,35))
                for i, topview in enumerate((True,False)):
                    after.paste(renderer.render(texture,floor,top,top=topview,size=256),(512+i*256,35))
                panel = Image.new('RGB',(1024,640),'white')
                panel.paste(Image.open(file.parent / (original['variant'] + '_panel.jpg')), (0,0))
                panel.paste(after,(0,320))
                dest = OUT / 'adjustments' / (original['case_id'] + '_' + original['variant'] + '.jpg')
                dest.parent.mkdir(parents=True, exist_ok=True)
                panel.save(dest, quality=95)
                record['panel'] = dest.relative_to(OUT).as_posix()
            except ValueError as error:
                record.update(status='unresolved', reason=str(error))
            rows.append(record)
    write_json(OUT / 'preview_adjustment_proposals.json', rows)
    print('proposals', sum(r['status']=='proposed_unreviewed' for r in rows), 'unresolved', sum(r['status']=='unresolved' for r in rows))


def questionnaire(records, proposals):
    """Publish an independent human questionnaire; never seed answers from AI notes."""
    data = []
    recheck_path = OUT / 'visual_order_recheck_notes.json'
    rechecks = json.loads(recheck_path.read_text(encoding='utf-8')) if recheck_path.exists() else {}
    if rechecks:
        assert set(rechecks) == {r['case_id'] for r in records}
    def adjustment_info(a):
        result = {k:a[k] for k in ('variant','panel','decision','observation')}
        mapping = a['old_point_id_for_new_index']
        order = ' → '.join('('+','.join(str(n) for n in mapping[i:i+2])+')' for i in range(0,len(mapping),2))
        result['explanation'] = ('触发原因：'+a['original_error']+'。以0为起点的原点编号，新预览顺序为 '+order+'。'
            + ('保留原上下点对，改变组间邻接。' if not a['pairing_changed'] else '重新推测上下点配对，并改变组间邻接。')
            + '按方位角排序只是预览假设；未核实导出排列是否代表作者的墙边连接，能成网格不能证明作者意图或标注正确。')
        return result
    for row in records:
        variants = []
        for source in row['shown_layouts']:
            name = source['name']
            label = name.replace('Bi-Layout_', 'Bi ').replace('HoHoNet_single', 'HoHoNet')
            label = label.replace('reference_', '参考布局 ').replace('human_rank', '真人簇显示代表 ').replace('human_individual_', '真人个体 ')
            variants.append(dict(variant=source['variant'], label=label, source_id=source['source_id'], original_status=source['original_status']))
            # Show only source point positions, without asserting any wall adjacency.
            folder = OUT/'cases'/row['case_id']
            points = json.loads((folder/(source['variant']+'_source.json')).read_text(encoding='utf-8'))['points']
            labels = ''.join(f'<circle cx="{x}" cy="{y}" r="2" fill="white"/><text x="{x+3}" y="{y-3}">{i}</text>' for i,(x,y) in enumerate(points))
            (folder/'hd'/(source['variant']+'_points.svg')).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="1024" viewBox="0 0 1024 512"><image href="panorama.png" width="1024" height="512"/><g font-size="8" font-family="sans-serif" fill="white" stroke="black" stroke-width="0.5" paint-order="stroke">'+labels+'</g></svg>',encoding='utf-8')
        has_proposal = any(a['case_id']==row['case_id'] and 'panel' in a for a in proposals)
        warning = '点序复查勘误：本图有未确认的重排假设；以下历史观察中依赖重排解释范围或正确性的判断暂停采用。请结合原始点和疑点记录核查。\n\n' if has_proposal else ''
        data.append(dict(case_id=row['case_id'], image_id=row['image_id'], building_id=row['building_id'],
                         has_humans=row['population_role']=='historical_annotated', variants=variants,
                         ai_observation=('本次高清与点序复看（AI初步意见，可不同意）：\n'+rechecks[row['case_id']]+'\n\n【此前观察，保留供追溯】\n' if rechecks else '')+warning+row['blind_observation']+'\n'+row['comparison'], ai_question=row['question'],
                         adjustments=[adjustment_info(a) for a in proposals if a['case_id']==row['case_id'] and 'panel' in a]))
    assert len({r['case_id'] for r in data}) == len(data)
    template = Path(__file__).with_name('review_questionnaire')
    (OUT / 'case_index.html').write_bytes((OUT / 'index.html').read_bytes())
    for name in ('index.html', 'questionnaire.js'):
        (OUT / name).write_bytes((template / name).read_bytes())
    (OUT / 'questionnaire_data.js').write_text('window.REVIEW_CASES='+json.dumps(data,ensure_ascii=False,allow_nan=False).replace('</','<\\/')+';\n',encoding='utf-8')


def finalize():
    """Assemble previously written visual observations, never infer them from files."""
    blind, comparison = {}, {}
    for suffix in ('', '_expansion'):
        blind.update(json.loads((OUT / f'blind_notes{suffix}.json').read_text(encoding='utf-8')))
        comparison.update(json.loads((OUT / f'comparison_notes{suffix}.json').read_text(encoding='utf-8')))
    selection = pd.read_csv(OUT / 'selection.csv', keep_default_na=False)
    expected = set(selection.case_id)
    assert set(blind) == set(comparison) == expected and len(expected) == 50
    proposals = json.loads((OUT / 'preview_adjustment_proposals.json').read_text(encoding='utf-8'))
    notes = json.loads((OUT / 'preview_adjustment_review_notes.json').read_text(encoding='utf-8'))
    for row in proposals:
        key = row['case_id'] + '|' + row['variant']
        if 'panel' in row:
            assert key in notes
            row.update(notes[key], visually_reviewed=True, status='reviewed_preview_proposal')
            assert row['preview_points'] == [row['original_points'][i] for i in row['old_point_id_for_new_index']]
            assert sorted(row['old_point_id_for_new_index']) == list(range(len(row['original_points'])))
        else:
            row.update(decision='unresolved_no_proposal', observation='原始失败叠图已阅读；无法仅用保守点序调整解决，未生成替代网格。')
    write_json(OUT / 'preview_adjustments_reviewed.json', proposals)
    records, layouts, pages = [], [], []
    cluster_table = pd.read_csv(ARCHIVE / 'review_results/analysis/clusters_to_bi.csv', keep_default_na=False).set_index('cluster_id')
    for row in selection.to_dict('records'):
        case = row['case_id']
        folder = OUT / 'cases' / case
        logs = json.loads((folder / 'render_log.json').read_text(encoding='utf-8'))
        evidence = [f'cases/{case}/{n}' for n in ('02_blind_perspectives.jpg','03_comparison.jpg')]
        assert all((OUT / p).is_file() for p in evidence)
        with Image.open(OUT / 'images' / (row['image_id'] + '.jpg')) as im:
            im.verify()
        for log in logs:
            log.update(overlay_visually_reviewed=True, mesh_visually_reviewed=log['status']=='rendered_unreviewed', human_final_judgment=None)
            log['generation_status'] = log['status']
            log['review_status'] = 'mesh_and_overlay_reviewed' if log['mesh_visually_reviewed'] else 'overlay_reviewed_mesh_unavailable'
            layouts.append(log)
        shown = []
        for log in logs:
            source = json.loads((folder / (log['variant'] + '_source.json')).read_text(encoding='utf-8'))
            source.pop('points')
            source.update(variant=log['variant'], original_status=log['status'])
            if 'cluster_id' in source:
                cluster = cluster_table.loc[source['cluster_id']]
                source.update(cluster_floor_support=int(cluster.floor_support), representative_basis='medoid_of_floor_computable_members_only')
            shown.append(source)
        # Explicit numerical identity, distinct from visual similarity or old zero distance.
        e = json.loads((folder / '00_Bi-Layout_enclosed_source.json').read_text(encoding='utf-8'))['points']
        x = json.loads((folder / '01_Bi-Layout_extended_source.json').read_text(encoding='utf-8'))['points']
        row.update(blind_observation=blind[case], **comparison[case], bi_raw_coordinates_equal=e==x,
                   auxiliary_visual_review_completed=True, review_date='2026-09-07', reviewer='AI辅助视觉审查',
                   evidence_files=evidence, human_final_judgment=None, intrinsic_ambiguity_label=None,
                   shown_layouts=shown,
                   original_mesh_available=sum(l['status']=='rendered_unreviewed' for l in logs),
                   original_mesh_failed=sum(l['status']=='failed' for l in logs))
        records.append(row)
        esc = html.escape
        adjustments_html = ''
        for adj in proposals:
            if adj['case_id'] == case:
                adjustments_html += '<p>' + esc(adj['variant'] + '：' + adj['decision'] + '；' + adj['observation']) + '</p>'
                if 'panel' in adj:
                    adjustments_html += f'<img loading="lazy" src="../../{adj["panel"]}" alt="点序调整前后对照">'
        sources = '<ul>' + ''.join(f'<li><a href="{esc(l["variant"])}_source.json">{esc(l["variant"])}：{esc(l["source_id"])}</a>；{esc(l["status"])}</li>' for l in logs) + '</ul>'
        body = f'<h1>{case} · {esc(row["building_id"])}</h1><p>{esc(row["image_id"])}</p><p>AI建议；人工最终判断为空。先看原图，再展开布局。图中3D采用单位相机高度、单全景回投影；不是扫描真值。</p><img src="02_blind_perspectives.jpg" alt="原图及四个局部透视"><p>{esc(blind[case])}</p><details><summary>展开布局、3D及辅助观察</summary><img src="03_comparison.jpg" alt="模型、参考和所示真人响应"><p>{esc(row["comparison"])}</p><p>待人工判断：{esc(row["question"])}</p>{sources}{adjustments_html}</details>'
        assets_path = folder / 'hd/assets.json'
        if assets_path.exists():
            assets = json.loads(assets_path.read_text(encoding='utf-8'))
            full = '<p>原始PNG · 2048×1024；点击图片查看原尺寸。下面的旧拼图仅作概览。</p><a href="hd/panorama.png" target="_blank"><img src="hd/panorama.png" alt="2048×1024原始全景"></a>'
            body = body.replace('<img src="02_blind_perspectives.jpg"', full+'<details><summary>展开旧版局部透视概览</summary><img src="02_blind_perspectives.jpg"').replace('alt="原图及四个局部透视">','alt="原图及四个局部透视"></details>')
            gallery = '<p><a href="hd/studio/index.html" target="_blank">打开新版交互3D：旋转、缩放、室内视角、点位联动</a></p><p>左窗原始几何，右窗为工具的约束拟合诊断；拟合结果不等于正确标注。无法读取的点组保留失败。高清显示升级未重新裁定旧观察。</p>'
            for item in assets['overlays']:
                gallery += '<details><summary>'+esc(item['name'])+' · 高清标注叠图</summary><p><a target="_blank" href="hd/'+item['overlay']+'">打开矢量叠图，可用浏览器缩放</a></p><object type="image/svg+xml" data="hd/'+item['overlay']+'" style="width:100%;aspect-ratio:2/1"></object></details>'
            body = body.replace('<img src="03_comparison.jpg"',gallery+'<details><summary>旧版低分辨率对照概览</summary><img src="03_comparison.jpg"').replace('alt="模型、参考和所示真人响应">','alt="模型、参考和所示真人响应"></details>')
        css = '<style>body{font:17px/1.7 system-ui;max-width:1400px;margin:30px auto;padding:0 20px;color:#183044}img{display:block;max-width:100%;height:auto;margin:20px 0}summary{cursor:pointer;font-weight:bold}a{color:#086a98}td,th{padding:8px;text-align:left;border-bottom:1px solid #ddd}</style>'
        body = f'<p><a href="../../index.html#{case}">← 打开这张图的三步审查问卷（填写／保存）</a></p>' + body
        body = '<p>点序复查：旧失败图红线为脚本直连诊断，不是作者墙边证据。导出列表不等于已核实的邻接；重排仅是假设。<a href="../../ORDER_REVIEW_ZH.md">50图核查与勘误</a></p>' + body
        (folder / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+case+'辅助视觉检查</title>'+css+body, encoding='utf-8')
        pages.append(f'<tr><td><a href="cases/{case}/index.html">{case}</a></td><td>{esc(row["building_id"])}</td><td>{"历史" if row["population_role"]=="historical_annotated" else "候选"}</td><td>{esc(row["question"])}</td></tr>')
    (OUT / 'visual_reviews.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in records),encoding='utf-8')
    flat = [{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in records]
    pd.DataFrame(flat).to_csv(OUT / 'visual_reviews.csv',index=False,encoding='utf-8-sig')
    write_json(OUT / 'layout_review_status.json', layouts)
    counts = dict(actual_auxiliary_visual_reviews=len(records), historical_images=30, candidate_images=20,
                  unique_buildings=selection.building_id.nunique(), historical_buildings=selection[selection.population_role=='historical_annotated'].building_id.nunique(),
                  candidate_buildings=selection[selection.population_role!='historical_annotated'].building_id.nunique(),
                  original_layouts=len(layouts), original_mesh_available=sum(r['mesh_visually_reviewed'] for r in layouts), original_mesh_failed=sum(not r['mesh_visually_reviewed'] for r in layouts),
                  preview_permutations_viewed=len(notes), preview_rejected=sum(n['decision']=='reject_as_interpretive_preview' for n in notes.values()),
                  human_final_judgments=0, overlap_human30=0, overlap_old_ai50=0, published_this_turn=False)
    write_json(OUT / 'REVIEW_STATUS.json', counts)
    (OUT / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>50张辅助视觉检查</title>'+css+'<h1>50张辅助视觉检查</h1><p>30张历史图＋20张候选；排除原人工30及AI50。逐图观察是探索性建议，不是正式歧义标签或人工裁决。每页先显示原图，手动展开布局。<a href="README_ZH.md">交付说明</a></p><table><thead><tr><th>案例</th><th>building</th><th>来源</th><th>待判断的问题</th></tr></thead><tbody>'+''.join(pages)+'</tbody></table>',encoding='utf-8')
    questionnaire(records, proposals)
    print(json.dumps(counts,ensure_ascii=False))


def verify():
    """Offline verification of review records, source coordinates, and receipt."""
    audit, _ = helpers()
    annotations, images, partitions, members, versions, models, refs, raw, norm = audit.load()
    manifest = json.loads((ARCHIVE / 'review_results/DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        path = (ARCHIVE / entry['path']).resolve()
        assert path.is_relative_to(ARCHIVE.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], entry['path']
    sources = {k:v['points_1024x512'] for k,v in raw.items()}
    sources.update({r['layout_id']:r['points_1024x512'] for r in models+refs})
    records = [json.loads(line) for line in (OUT / 'visual_reviews.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(records) == len({r['image_id'] for r in records}) == 50
    source_count = 0
    for row in records:
        assert row['auxiliary_visual_review_completed'] and row['blind_observation'] and row['comparison']
        assert row['human_final_judgment'] is None and row['intrinsic_ambiguity_label'] is None
        assert row['room_instance_id'] == '' and row['human30_id'] == row['ai50_id'] == ''
        for source in (OUT / 'cases' / row['case_id']).glob('*_source.json'):
            data = json.loads(source.read_text(encoding='utf-8'))
            assert data['points'] == sources[data['source_id']], str(source)
            source_count += 1
        for evidence in row['evidence_files']:
            with Image.open(OUT / evidence) as im:
                im.verify()
    assert len(annotations)==2501 and len(versions)==2513 and len(images)==380
    results = dict(offline=True, canonical_rows=len(annotations), raw_versions=len(versions), images_in_pool=len(images),
                   archive_manifest_members_unchanged=len(manifest['files']), reviewed_images=len(records),
                   source_coordinate_copies_exact=source_count, all_human_judgments_blank=True)
    write_json(OUT / 'VALIDATION.json', results)
    print(json.dumps(results))


def select(census):
    """Building-balanced exploratory selection; previous human30 and AI50 excluded."""
    selected = []
    for population, count in [('historical_annotated', 30), ('candidate_without_historical_annotation', 20)]:
        pool = census[(census.population_role == population) & (census.human30_id == '') & (census.ai50_id == '')].copy()
        building_counts = {}
        for i in range(count):
            score = 'human_floor_mean' if population == 'historical_annotated' and i % 4 < 2 else 'bi_floor'
            ascending = i % 2 == 0
            pool['_building_count'] = pool.building_id.map(building_counts).fillna(0)
            pool['_score'] = pd.to_numeric(pool[score], errors='coerce')
            row = pool.sort_values(['_building_count', '_score', 'image_id'], ascending=[True, ascending, True]).iloc[0]
            record = {k: v for k, v in row.to_dict().items() if not k.startswith('_')}
            record['selection_reason'] = f'building coverage first; {score} {"ascending" if ascending else "descending"}; exploratory, not prevalence sample'
            selected.append(record)
            building_counts[row.building_id] = building_counts.get(row.building_id, 0) + 1
            pool = pool[pool.image_id != row.image_id]
    # Four historical cases plus one candidate calibrate the same workflow first.
    selected = selected[:4] + [selected[30]] + selected[4:30] + selected[31:]
    for i, row in enumerate(selected, 1):
        row.update(case_id=f'V{i:02}', phase='calibration' if i <= 5 else 'expansion')
    assert len({r['image_id'] for r in selected}) == 50
    return pd.DataFrame(selected)


def download(row):
    p = OUT / 'images' / (row['image_id'] + '.jpg')
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        if p.exists():
            data = p.read_bytes()
            status = 'cached_verified_download'
        else:
            if not row['image_url'].startswith('https://'):
                raise ValueError('Expected HTTPS source URL')
            with urllib.request.urlopen(row['image_url'], timeout=30) as response:
                data = response.read()
            status = 'downloaded_and_decoded'
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
        if width != height * 2:
            raise ValueError('Expected equirectangular 2:1 image')
        if not p.exists():
            p.write_bytes(data)
        return dict(image_id=row['image_id'], status=status, path=str(p.relative_to(OUT)), url=row['image_url'], bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), width=width, height=height, error='')
    except Exception as e:
        return dict(image_id=row['image_id'], status='failed', error=f'{type(e).__name__}: {e}')


def variants(mid, audit, loaded, clusters):
    annotations, images, partitions, members, versions, models, refs, raw, norm = loaded
    result = []
    def add(name, source_id, points, role, **extra):
        result.append(dict(name=name, source_id=source_id, points=points, geometry_role=role, **extra))
    for r in models:
        if r['image_id'] == mid and r['source_role'] in ('offline_dual_prediction', 'offline_ep300_replay'):
            add(r['model_family'] + '_' + r['head'], r['layout_id'], r['points_1024x512'], r['source_role'])
    references = [r for r in refs if r['image_id'] == mid]
    for i, r in enumerate(references):
        add('reference_' + str(i), r['layout_id'], r['points_1024x512'], r.get('source_role', ''), reference_status=r.get('reference_status', ''), scope_status=r.get('scope_status', ''))
    choices = clusters[(clusters.image_id == mid) & (clusters.representative_id != '')].copy()
    # Select one context, then two supported clusters; never combine ranks from different contexts.
    if len(choices):
        context = choices.groupby('context_key').original_support.sum().sort_values(ascending=False).index[0]
        choices = choices[choices.context_key == context].sort_values(['rank', 'cluster_id']).head(2)
        for r in choices.to_dict('records'):
            k = r['representative_id']
            add(f'human_rank{r["rank"]}', k, raw[k]['points_1024x512'], 'raw_canonical_member_selected_by_upstream_normalized_medoid', context_key=r['context_key'], cluster_id=r['cluster_id'], cluster_support=int(r['original_support']))
    else:
        # Images lacking an extended73 partition retain individual humans, without fabricated clusters.
        rows = annotations[annotations.image_id == mid].sort_values(['context_key', 'worker_id'])
        if len(rows):
            rows = rows[rows.context_key == rows.iloc[0].context_key].head(2)
            for r in rows.itertuples():
                add('human_individual_W' + str(r.worker_id), r.canonical_annotation_id, raw[r.canonical_annotation_id]['points_1024x512'], 'raw_individual_not_cluster_representative', context_key=r.context_key)
    return result


def render_case(row, audit, renderer, loaded, clusters):
    dest = OUT / 'cases' / row['case_id']
    dest.mkdir(parents=True, exist_ok=True)
    tex = np.asarray(Image.open(OUT / 'images' / (row['image_id'] + '.jpg')).convert('RGB'))
    original = Image.fromarray(tex).resize((1024, 512))
    original.save(dest / '01_original_blind.jpg', quality=95)
    blind = Image.new('RGB', (1024, 1216), 'white')
    blind.paste(original, (0, 0))
    for i, yaw in enumerate([0, 90, 180, 270]):
        view = renderer.title(renderer.perspective(tex, yaw, width=512, height=320), f'yaw {yaw}; FOV 80 deg')
        blind.paste(view, ((i % 2) * 512, 512 + (i // 2) * 352))
    blind.save(dest / '02_blind_perspectives.jpg', quality=93)
    vv = variants(row['image_id'], audit, loaded, clusters)
    panels = []
    logs = []
    for i, variant in enumerate(vv):
        label = f'{i:02}_{variant["name"]}'
        write_json(dest / (label + '_source.json'), variant)
        log = dict(case_id=row['case_id'], image_id=row['image_id'], variant=label, source_id=variant['source_id'], geometry_role=variant['geometry_role'], coordinates_changed=False, adjacency_changed=False, visually_reviewed=False)
        panel = Image.new('RGB', (1024, 320), 'white')
        title = variant['name'] + ' | ' + variant['source_id'][:35]
        ImageDraw.Draw(panel).text((5, 5), title, fill='black', font=renderer.FONT)
        try:
            points = variant['points']
            arr, mapping = audit.roles(points)
            floor, top, _ = audit.lift(points)
            q = audit.project(np.stack([top, floor], axis=1).reshape(-1, 3))
            error = q - arr
            error[:, 0] = (error[:, 0] + 512) % 1024 - 512
            log.update(endpoint_role_map=mapping, roundtrip_error_px=float(abs(error).max()), max_pair_dx_px=float(abs((arr[::2, 0] - arr[1::2, 0] + 512) % 1024 - 512).max()))
            overlay, _ = renderer.overlay(tex, points, True)
            overlay.save(dest / (label + '_overlay.jpg'), quality=95)
            panel.paste(overlay.resize((512, 256)), (0, 35))
            audit.footprint(points)
            for j, topview in enumerate((True, False)):
                view = renderer.render(tex, floor, top, top=topview, size=256)
                panel.paste(view, (512 + j * 256, 35))
                view.save(dest / (label + ('_top.jpg' if topview else '_oblique.jpg')), quality=93)
            log['status'] = 'rendered_unreviewed'
        except (ValueError, IndexError, TypeError) as e:
            log.update(status='failed', error=f'{type(e).__name__}: {e}')
            points = np.asarray(variant['points'], float)
            if points.ndim == 2 and points.shape[1] == 2 and np.isfinite(points).all():
                overlay, _ = renderer.overlay(tex, points, False)
                panel.paste(overlay.resize((512, 256)), (0, 35))
            ImageDraw.Draw(panel).text((520, 70), 'NO MESH: ' + str(e)[:52], fill='red', font=renderer.FONT)
        panel.save(dest / (label + '_panel.jpg'), quality=93)
        panels.append(panel)
        logs.append(log)
    contact = Image.new('RGB', (1024, 320 * len(panels)), 'white')
    for i, panel in enumerate(panels):
        contact.paste(panel, (0, 320 * i))
    contact.save(dest / '03_comparison.jpg', quality=94)
    write_json(dest / 'render_log.json', logs)
    return logs


def prepare(start, end):
    audit, renderer = helpers()
    OUT.mkdir(parents=True, exist_ok=True)
    census = pd.read_csv(ARCHIVE / 'review_results/census/images_380.csv', keep_default_na=False)
    chosen = select(census)
    chosen.to_csv(OUT / 'selection.csv', index=False)
    rows = chosen.iloc[start - 1:end].to_dict('records')
    if start > 5:
        calibration = json.loads((OUT / 'CALIBRATION_REVIEW.json').read_text(encoding='utf-8'))
        assert calibration['display_calibration_passed'] and calibration['actual_cases_viewed'] >= 3
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        downloads = list(pool.map(download, rows))
    write_json(OUT / f'downloads_{start:02}_{end:02}.json', downloads)
    failed = [d for d in downloads if d['status'] == 'failed']
    if failed:
        raise RuntimeError('Failed image downloads; see download log')
    loaded = audit.load()
    clusters = pd.read_csv(ARCHIVE / 'review_results/analysis/clusters_to_bi.csv', keep_default_na=False)
    all_logs = []
    for row in rows:
        all_logs.extend(render_case(row, audit, renderer, loaded, clusters))
        print(row['case_id'], row['image_id'], 'generated, not yet reviewed', flush=True)
    write_json(OUT / f'GENERATION_{start:02}_{end:02}.json', dict(images=len(rows), layouts=len(all_logs), failed_layouts=sum(x['status'] == 'failed' for x in all_logs), completed_visual_reviews=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'reproduce', 'adjustments', 'finalize', 'verify'])
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=5)
    args = parser.parse_args()
    if args.command == 'reproduce':
        helpers()[0].run()
    elif args.command == 'adjustments':
        adjustments()
    elif args.command == 'finalize':
        finalize()
    elif args.command == 'verify':
        verify()
    else:
        assert 1 <= args.start <= args.end <= 50
        prepare(args.start, args.end)
