"""Build the agreed 50-image advisory review; never write human decisions."""
from __future__ import annotations

import argparse
import csv
import html
import json
import random
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.misc.panostretch import pano_connect_points
from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import _ordered_pairs, _read_txt
from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou_from_normalized_pairs
from tools.thesis_main.data_prep.build_annotation_uncertainty_batch1_review import _reference_pairs

SOURCE = ROOT / 'analysis_results/annotation_uncertainty_prescreen_20260903_v1'
DUAL = Path('D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions')
OUTPUT = ROOT / 'analysis_results/annotation_research_decision_audit_20260905_v1/review50'
QUOTAS = {'7y3sRwLe3Va': 2, 'B6ByNegPMKs': 5, 'UwV83HsGsw3': 5,
          'X7HyMhZNoso': 2, 'Z6MFQCViBuw': 2, 'b8cTxDM8gDG': 2,
          'e9zR4mvMWw7': 2, 'q9vSo1VnCiC': 6, 'rPc6DW4iMge': 4,
          'uNb9QFRL6hY': 6, 'wc2JMjhGNzB': 6, 'x8F5xyUWy9e': 2,
          'yqstnuAEVhm': 6}
LABELS = {'reference': '参考 GT（待核）', 'hohonet': 'HoHoNet',
          'bilayout_enclosed': 'Bi-Layout enclosed', 'bilayout_extended': 'Bi-Layout extended'}
COLORS = {'reference': '#00d77b', 'hohonet': '#ff4385',
          'bilayout_enclosed': '#00bdff', 'bilayout_extended': '#ffb000'}
FONT = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 17)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def select_images(rows, quotas, excluded, seed=20260905):
    if len(rows) != len({r['image_id'] for r in rows}):
        raise ValueError('duplicate image_id')
    result = []
    for building, count in sorted(quotas.items()):
        pool = sorted((r for r in rows if r['building_id'] == building and r['image_id'] not in excluded),
                      key=lambda r: r['image_id'])
        if len(pool) < count:
            raise ValueError(f'capacity {building}: {len(pool)} < {count}')
        # Independent deterministic stream per building; no dependence on input order.
        random.Random(f'{seed}:{building}').shuffle(pool)
        coverage = pool[:(count + 1) // 2]
        ranked = sorted(pool[(count + 1) // 2:], key=lambda r: (-r['max_mask_difference'], r['image_id']))
        picked = [(r, 'seeded_coverage') for r in coverage]
        picked += [(r, 'max_disagreement') for r in ranked[:count - len(coverage)]]
        for row, role in sorted(picked, key=lambda pair: pair[0]['image_id']):
            result.append({**row, 'selection_role': role, 'review_id': f'R50-{len(result)+1:03d}'})
    return result


def projected_segments(first, second, *, ceiling):
    xy = pano_connect_points(np.asarray(first), np.asarray(second), z=-50 if ceiling else 50)
    if not np.isfinite(xy).all():
        raise ValueError('non-finite projected edge')
    split = np.flatnonzero(np.abs(np.diff(xy[:, 0])) > 512) + 1
    return [piece for piece in np.split(xy, split) if len(piece) > 1]


def normalize_image(source):
    if source.width != 2 * source.height:
        raise ValueError(f'non-equirectangular image dimensions: {source.size}')
    return source.convert('RGB').resize((1024, 512), Image.Resampling.LANCZOS)


def panel(source, label, layouts=()):
    image = source.copy()
    draw = ImageDraw.Draw(image)
    for pairs, color in layouts:
        for i, first in enumerate(pairs):
            second = pairs[(i + 1) % len(pairs)]
            for field in ('y_ceiling', 'y_floor'):
                segments = projected_segments([first['x'], first[field]], [second['x'], second[field]], ceiling=field == 'y_ceiling')
                for segment in segments:
                    draw.line([tuple(p) for p in segment], fill=color, width=3)
            draw.line([(first['x'], first['y_ceiling']), (first['x'], first['y_floor'])], fill=color, width=3)
    # The title is outside the image; source pixels and coordinates stay intact.
    title = Image.new('RGB', (1024, 542), '#101b2b')
    title.paste(image, (0, 30))
    ImageDraw.Draw(title).text((8, 4), label, fill='white', font=FONT)
    return title


def build_candidates():
    manifest = read_json(SOURCE / 'machine_manifest.json')
    reviewed = read_json(SOURCE / 'human_review_export_20260905.json')['items']
    excluded = {r['image_id'] for r in reviewed}
    if len(excluded) != 30:
        raise ValueError('reviewed-30 identity drift')
    with (DUAL / 'test/manifest.csv').open(encoding='utf-8-sig') as stream:
        dual_rows = list(csv.DictReader(stream))
    dual = {r['pano_id']: r for r in dual_rows}
    if len(dual) != len(dual_rows):
        raise ValueError('duplicate dual pano_id')
    candidates, metrics = [], []
    for row in manifest['items']:
        if row['history_layer'] != 'no_existing_annotation_record' or row['image_id'] in excluded:
            continue
        image_id = row['image_id']
        match = dual[image_id]
        if match['status'] != 'ok':
            raise ValueError(f'dual geometry status: {image_id}: {match["status"]}')
        paths = {'reference': ROOT / row['assets']['reference']['path'],
                 'hohonet': ROOT / row['assets']['model_txt']['path']}
        paths.update({f'bilayout_{head}': DUAL / match[f'{head}_corners_px_path'] for head in ('enclosed', 'extended')})
        pairs = {}
        for name, path in paths.items():
            if name == 'reference':
                pairs[name] = _reference_pairs({'gt_source_type': row['assets']['reference']['source_type'], 'image_id': image_id}, path)
            else:
                raw = _read_txt(path)
                if not np.isfinite(raw).all() or np.any(raw[:, 0] < 0) or np.any(raw[:, 0] > 1024) or np.any(raw[:, 1] < 0) or np.any(raw[:, 1] >= 512):
                    raise ValueError(f'coordinate range {path}')
                pairs[name] = _ordered_pairs(raw, source=path)
                if name.startswith('bilayout_') and len(pairs[name]) != int(match[f'{name.split("_")[-1]}_corner_count']):
                    raise ValueError(f'dual corner count drift: {image_id}')
        distances = {}
        for left, right in combinations(pairs, 2):
            iou, meta = compute_layout_mask_iou_from_normalized_pairs(pairs[left], pairs[right])
            if iou is None:
                raise ValueError(f'non-evaluable selection metric: {image_id} {meta}')
            distances[f'{left}__{right}'] = 1.0 - iou
            metrics.append(dict(image_id=image_id, building_id=row['building_id'], left=left, right=right,
                                linear_mask_difference=1.0-iou, left_corner_pairs=len(pairs[left]), right_corner_pairs=len(pairs[right])))
        with Image.open(ROOT / row['assets']['image']['path']) as image:
            if image.width != 2 * image.height:
                raise ValueError(f'image dimensions: {image_id}: {image.size}')
            source_dimensions = list(image.size)
        candidates.append(dict(image_id=image_id, building_id=row['building_id'], image_path=(ROOT/row['assets']['image']['path']).as_posix(),
                               source_dimensions=source_dimensions, coordinate_dimensions=[1024,512],
                               reference_source_type=row['assets']['reference']['source_type'],
                               paths={k:v.as_posix() for k,v in paths.items()}, pairs=pairs,
                               max_mask_difference=max(distances.values()), differences=distances,
                               previous_machine_hint=row['machine'], history_layer=row['history_layer']))
    if len(candidates) != 136:
        raise ValueError(f'candidate pool drift: {len(candidates)}')
    return candidates, metrics, excluded


def validate_advisory(data, expected_ids):
    ids = [r['review_id'] for r in data.get('items', [])]
    if len(ids) != len(set(ids)) or not set(ids).issubset(expected_ids):
        raise ValueError('advisory identities')
    for row in data['items']:
        if row.get('advisory_only') is not True or 'human_review' in row or 'final_decision' in row:
            raise ValueError('machine advice cannot contain human decisions')


def write_page(rows, output, advisory):
    notes = {r['review_id']: r for r in advisory.get('items', [])}
    note_labels = {'scene':'原图可见证据','scope_hint':'范围初查提示','reference':'参考GT对照','hohonet':'HoHoNet对照','bi':'Bi-Layout两头对照','question':'留给研究者判断的问题','tags':'审查线索标签','priority':'人工关注优先级'}
    cards = []
    for row in rows:
        rid = row['review_id']
        note = notes.get(rid, {})
        observations = '<br>'.join(html.escape(f'{note_labels.get(k,k)}：{", ".join(v) if isinstance(v,list) else v}') for k,v in note.items() if k not in ('review_id','advisory_only','viewed_assets'))
        links = ' · '.join(f'<a href="previews/{rid}_{name}.jpg" target="_blank">{label}</a>' for name,label in LABELS.items())
        model_fields = ''.join(f'<label>{label}意见<select data-name="{name}_verdict"><option value="">未裁决</option><option value="no_obvious_issue">未见明显问题</option><option value="issue">有问题</option><option value="uncertain">不确定</option></select></label>' for name,label in LABELS.items() if name != 'reference')
        cards.append(f'''<section class="card" data-building="{row['building_id']}" data-id="{rid}" data-image="{row['image_id']}"><h2>{rid} · {row['building_id']}</h2>
<code>{row['image_id']}</code><p>选图：{'固定种子覆盖' if row['selection_role']=='seeded_coverage' else '差异优先'}；最大线性mask差异 {row['max_mask_difference']:.3f}（筛图诊断，不是错误率）</p>
<a href="previews/{rid}_original.jpg" target="_blank"><img loading="lazy" src="previews/{rid}_original.jpg" alt="{rid} 原图"></a>
<details><summary>查看四种布局对照</summary><p>{links} · <a href="previews/{rid}_overlay.jpg" target="_blank">叠图</a></p><img loading="lazy" src="previews/{rid}_comparison.jpg" alt="参考、HoHoNet、Bi-Layout两头对照"></details>
<details><summary>AI初查意见（仅建议，可独立于人工判断查看）</summary><p>{observations or '尚未完成视觉初查'}</p></details>
<div class="fields"><label>你的scope裁决<select data-name="scope"><option value="">未裁决</option><option value="in_scope">适用</option><option value="out_of_scope">不适用</option><option value="uncertain">待进一步判断</option></select></label>
<label>参考GT意见<select data-name="reference_verdict"><option value="">未裁决</option><option value="no_obvious_issue">未见明显问题</option><option value="issue">有问题</option><option value="uncertain">不确定</option></select></label>
{model_fields}<label>你的备注<textarea data-name="notes"></textarea></label></div></section>''')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>50张候选图 · 研究者决策资料</title>
<style>body{margin:0;background:#edf1f4;color:#152238;font:16px/1.6 system-ui,sans-serif}header,main{max-width:1100px;margin:auto;padding:20px}.card{background:white;border:1px solid #ccd6e1;border-radius:8px;margin:20px 0;padding:20px}img{max-width:100%;height:auto}code{overflow-wrap:anywhere}summary{cursor:pointer;font-weight:bold;padding:10px 0}.fields{display:flex;gap:20px;flex-wrap:wrap;margin-top:20px}label{display:flex;flex-direction:column}select,textarea,button{font:inherit;padding:8px}textarea{width:350px;min-height:65px}header{position:sticky;top:0;background:#edf1f4;z-index:2}.notice{background:#fff5d6;padding:15px}a{color:#116ba3}</style>
<header><b>50张新增候选图 · AI初查与人工裁决分开</b><br><label>按building浏览<select id="filter"><option value="">全部13个building</option>''' + ''.join(f'<option>{b}</option>' for b in sorted(QUOTAS)) + '''</select></label><button id="export">导出你的审核记录</button><span id="progress"></span></header>
<main><p class="notice">图片先看原图，再展开模型与AI意见。规则：闭合、单层Manhattan当前空间；在清晰门框、墙端等分界处闭合，不延伸进相邻空间。GT也待核；两种模型分歧不自动等于人类不确定性。曲线按原始角点环序的球面投影绘制，非旧预览的二维直线插值。本页不提交或修改任何原始数据。</p>''' + ''.join(cards) + '''</main>
<script>
const storageKey='annotation-research-review50-20260905-human-v1';let saved={},canSave=true;try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}');if(!saved||typeof saved!=='object'||Array.isArray(saved))throw Error('记录格式错误')}catch(e){saved={};canSave=false;alert('本地旧记录无法解析，已停用自动保存以保护旧记录。新填写内容请导出。')}
const cards=[...document.querySelectorAll('.card')];
function progress(){document.querySelector('#progress').textContent=' 人工scope已记录 '+cards.filter(c=>saved[c.dataset.id]?.scope).length+'/50'}
for(const card of cards){for(const field of card.querySelectorAll('[data-name]')){field.value=saved[card.dataset.id]?.[field.dataset.name]||'';field.addEventListener('change',()=>{saved[card.dataset.id]??={};saved[card.dataset.id][field.dataset.name]=field.value;try{if(canSave)localStorage.setItem(storageKey,JSON.stringify(saved))}catch(e){alert('浏览器未保存，请立即导出记录。')}progress()})}}
document.querySelector('#filter').onchange=e=>{for(const c of cards)c.hidden=!!e.target.value&&c.dataset.building!==e.target.value};
document.querySelector('#export').onclick=()=>{const payload={schema_version:'review50_human_v1',exported_at:new Date().toISOString(),items:cards.map(c=>({review_id:c.dataset.id,image_id:c.dataset.image,building_id:c.dataset.building,human_review:saved[c.dataset.id]||{}}))};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='review50_human_review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};progress();
</script></html>'''
    (output/'review.html').write_text(page,encoding='utf-8')


def build(output=OUTPUT, *, refresh=False):
    output.mkdir(parents=True, exist_ok=True)
    if refresh:
        selected = read_json(output/'selected50_manifest.json')['items']
    else:
        candidates, metrics, excluded = build_candidates()
        selected = select_images(candidates, QUOTAS, excluded)
        write_csv(output/'candidate136_pairwise_metrics.csv', metrics)
        selection = {r['image_id']:r for r in selected}
        write_csv(output/'candidate136_selection_audit.csv', [dict(image_id=r['image_id'],building_id=r['building_id'],max_mask_difference=r['max_mask_difference'],selected=r['image_id'] in selection,selection_role=selection.get(r['image_id'],{}).get('selection_role',''),review_id=selection.get(r['image_id'],{}).get('review_id','')) for r in sorted(candidates,key=lambda x:x['image_id'])])
        write_json(output/'selected50_manifest.json',dict(schema_version='annotation_research_review50_v1',advisory_only=True,seed=20260905,quotas=QUOTAS,metric='1-IoU periodic linear image-layout mask, not spherical area or error truth',rendering='pano_connect_points original ring order, seam split',excluded_reviewed_image_ids=sorted(excluded),items=selected))
        (output/'previews').mkdir(exist_ok=True)
        for row in selected:
            rid=row['review_id']
            with Image.open(row['image_path']) as raw: source=normalize_image(raw)
            panel(source,f'{rid} 原图 · {row["building_id"]}').save(output/f'previews/{rid}_original.jpg',quality=94)
            board=Image.new('RGB',(2048,1084),'white')
            for i,name in enumerate(LABELS):
                p=panel(source,f'{rid} {LABELS[name]}',[(row['pairs'][name],COLORS[name])])
                p.save(output/f'previews/{rid}_{name}.jpg',quality=94)
                board.paste(p,((i%2)*1024,(i//2)*542))
            board.save(output/f'previews/{rid}_comparison.jpg',quality=92)
            panel(source,f'{rid} GT绿 / HoHo粉 / Bi封闭蓝 / Bi延伸黄',[(row['pairs'][n],COLORS[n]) for n in LABELS]).save(output/f'previews/{rid}_overlay.jpg',quality=94)
        write_json(output/'QA.json',dict(selected_count=len(selected),pool_count=len(candidates),unique_count=len(selection),excluded_overlap=len(set(selection)&excluded),building_counts=dict(Counter(r['building_id'] for r in selected)),selection_roles=dict(Counter(r['selection_role'] for r in selected)),all_review_assets_exist=all((output/f'previews/{r["review_id"]}_{n}.jpg').is_file() for r in selected for n in ['original','comparison','overlay',*LABELS]),rendering='spherical projected edges; original ring order; no input edits',human_decisions_written=0))
    advice_path=output/'ai_visual_advisory.json'
    advisory=read_json(advice_path) if advice_path.exists() else {'items':[]}
    validate_advisory(advisory,{r['review_id'] for r in selected})
    write_page(selected, output, advisory)
    if advisory['items']:
        identity={r['review_id']:r for r in selected}
        write_csv(output/'ai_visual_advisory.csv', [dict(review_id=r['review_id'],image_id=identity[r['review_id']]['image_id'],building_id=identity[r['review_id']]['building_id'],selection_role=identity[r['review_id']]['selection_role'],advisory_only=True,**{k:(' | '.join(v) if isinstance(v,list) else v) for k,v in r.items() if k not in ('review_id','advisory_only')}) for r in advisory['items']])
        write_json(output/'ADVISORY_QA.json',dict(selected_count=len(selected),ai_reviewed_count=len(advisory['items']),complete=set(notes_id['review_id'] for notes_id in advisory['items'])==set(identity),all_viewed_assets_exist=all((output/p).is_file() for r in advisory['items'] for p in r['viewed_assets']),human_decisions_written=0,priority_counts=dict(Counter(r['priority'] for r in advisory['items']))))
    print(json.dumps({'selected':len(selected),'advisory_reviewed':len(advisory['items']),'output':str(output)},ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=OUTPUT)
    parser.add_argument('--refresh-review',action='store_true')
    args=parser.parse_args()
    build(args.output_dir,refresh=args.refresh_review)
