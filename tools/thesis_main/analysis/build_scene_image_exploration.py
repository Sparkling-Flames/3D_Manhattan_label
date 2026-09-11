"""原图库存 + AI目视初分的核对页；不读取布局标注、GT或收敛结果。"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/scene_image_exploration_20260910_v1'
TYPES = dict(B='卧室陈设', W='卫浴/卫生间', K='厨房', D='餐厅/用餐区',
             L='起居/会客区', X='复合或交界空间（不单选功能）', H='门厅/前室',
             C='走廊/通行段', S='楼梯/夹层平台', V='衣帽/洗衣/储物（待细分）',
             O='书房/办公区', M='会议区', U='空置或功能未定', E='半室外/露台',
             G='车库', R='影音休闲', F='运动健身', P='按摩/护理陈设', T='儿童活动区')
BOUNDARY = dict(candidate='较明确候选', possible='可能，待确认',
                not_observed='未见明确线索（未排除）')
COARSE = dict(bedroom='卧室', bathroom='卫浴', living='起居与休闲',
              kitchen_dining='厨房与用餐', circulation='通行与连接',
              work='工作与学习', utility='储藏与家务辅助',
              special='特殊用途（暂不合并分析）', mixed_unknown='复合／待定')
COARSE_MAP = {kind: coarse for coarse, kinds in dict(
    bedroom='B', bathroom='W', living='LRT', kitchen_dining='KD',
    circulation='HCS', work='OM', utility='V', special='EFPG',
    mixed_unknown='XU').items() for kind in kinds}
PRIOR = {
    'uNb9QFRL6hY_3b9e548b46af4410b97e1d12781ec3c9': 'r1',
    'uNb9QFRL6hY_5948424345f541b9a570b48f1cfcf622': 'r1',
    'uNb9QFRL6hY_978d7a8eb0794936bd8fd092306e1dc5': 'r1',
    'uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e': 'r2',
    'uNb9QFRL6hY_c1ebb8b34eb846ba9b5ce23b30b299a7': 'r2',
}


def inventory(root):
    rows = []
    for split in ('valid', 'test'):
        folder = root / f'data/mp3d_layout/{split}/img'
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        for path in sorted(folder.glob('*.png')):
            rows.append(dict(image_id=path.stem, building=path.stem.split('_')[0],
                             split=split, path=path.relative_to(root).as_posix()))
    rows.sort(key=lambda r: (r['building'], r['image_id']))
    counts = Counter()
    for row in rows:
        counts[row['building']] += 1
        row['number'] = counts[row['building']]
    if len({r['image_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate image identity across splits')
    return rows


def expand_judgments(raw, judgments):
    if set(judgments) != {r['building'] for r in raw}:
        raise ValueError('Building coverage mismatch')
    output = []
    for building, decision in judgments.items():
        records = {r['number']: r for r in raw if r['building'] == building}
        assigned = {}

        def assign(number, kind, group='', evidence=''):
            if number not in records or number in assigned or kind not in TYPES:
                raise ValueError(f'Invalid/duplicate visual assignment: {building}/{number}/{kind}')
            assigned[number] = dict(ai_type=kind, ai_group=group, group_evidence=evidence)

        for index, (kind, numbers, evidence) in enumerate(decision['groups'], 1):
            members = [int(n) for n in numbers.split()]
            if len(members) < 2:
                raise ValueError('A candidate group requires at least two images')
            for number in members:
                assign(number, kind, f'{building}:a{index:02d}', evidence)
        for number, kind in decision.get('singles', {}).items():
            assign(int(number), kind)
        for kind, numbers in decision.get('types', {}).items():
            for number in numbers.split():
                assign(int(number), kind)
        if set(assigned) != set(records):
            raise ValueError(f'Unreviewed inventory entries: {building}: {sorted(set(records)-set(assigned))}')
        strong = set(map(int, decision.get('threshold', '').split()))
        possible = set(map(int, decision.get('possible', '').split()))
        zoomed = set(map(int, decision.get('zoomed', '').split()))
        if strong & possible or not (strong | possible | zoomed) <= set(records):
            raise ValueError(f'Invalid boundary/zoom identities: {building}')
        for number, row in records.items():
            group = assigned[number]
            prior = PRIOR.get(row['image_id'], '')
            output.append(dict(row, **group, ai_boundary='candidate' if number in strong else
                               'possible' if number in possible else 'not_observed',
                               ai_coarse_type=COARSE_MAP[group['ai_type']],
                               ai_doorway='not_reviewed', user_doorway='', user_artifact='',
                               review_basis='contact_sheet_visual_first_pass',
                               original_image_rechecked=number in zoomed,
                               ai_status='provisional_not_user_confirmed',
                               building_note=decision['note'],
                               image_note=decision.get('image_notes', {}).get(str(number), ''),
                               prior_user_room=prior, user_room=prior, user_type='',
                               user_boundary='', user_status='未复核', user_note=''))
    return sorted(output, key=lambda r: (r['building'], r['number']))


def contact_sheets(rows, root, out):
    from PIL import Image, ImageDraw
    folder = out / 'contact_sheets'
    folder.mkdir(exist_ok=True)
    pages = []
    for building in sorted({r['building'] for r in rows}):
        group = [r for r in rows if r['building'] == building]
        for start in range(0, len(group), 24):
            part = group[start:start+24]
            canvas = Image.new('RGB', (1792, 42 + math.ceil(len(part)/4)*250), '#eeeeee')
            draw = ImageDraw.Draw(canvas)
            draw.text((10, 10), f'{building} / {part[0]["split"]} / {start+1}-{start+len(part)}', fill='black')
            for i, row in enumerate(part):
                with Image.open(root / row['path']) as im:
                    if im.width != 2 * im.height:
                        raise ValueError(f'Unexpected panorama ratio: {row["image_id"]}')
                    thumb = im.convert('RGB')
                    thumb.thumbnail((444, 222))
                x, y = (i % 4)*448, 42 + (i // 4)*250
                canvas.paste(thumb, (x, y))
                draw.text((x+4, y+224), f'{row["number"]:02d} {row["image_id"].split("_")[1][:8]}', fill='black')
            name = f'{building}_{start//24+1}.jpg'
            canvas.save(folder / name, quality=90)
            pages.append(name)
    (folder / 'index.json').write_text(json.dumps(pages, indent=2), encoding='utf8')


def apply_coarse_review(rows, decisions):
    """应用第二遍逐图判断，禁止用旧细标签补齐漏审图片。"""
    codes = dict(B='bedroom', W='bathroom', L='living', K='kitchen_dining',
                 C='circulation', O='work', V='utility', E='special', X='mixed_unknown')
    if set(decisions) != {r['building'] for r in rows}:
        raise ValueError('Coarse visual review building coverage mismatch')
    for building, decision in decisions.items():
        members = sorted((r for r in rows if r['building'] == building), key=lambda r: r['number'])
        labels = decision['codes'].split()
        if len(labels) != len(members) or any(c not in codes for c in labels):
            raise ValueError(f'Coarse visual review count/code mismatch: {building}')
        if not set(decision.get('notes', {})) <= {str(r['number']) for r in members}:
            raise ValueError(f'Coarse visual review note identity mismatch: {building}')
        for row, label in zip(members, labels):
            row['legacy_mapped_coarse_type'] = COARSE_MAP[row['ai_type']]
            row['ai_coarse_type'] = codes[label]
            row['coarse_review_basis'] = 'second_pass_image_visual_review'
            row['coarse_review_note'] = decision.get('notes', {}).get(str(row['number']), '')
            row['coarse_original_rechecked'] = row['number'] in decision.get('zoomed', [])


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>室内图片重新粗分类 · 等待你的确认</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#172b39;font:15px/1.55 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1500px;margin:auto;padding:20px}h1{margin:0;font-size:27px}p{margin:8px 0}.muted{color:#526777}.bar{background:white;position:sticky;top:0;z-index:2;border-bottom:1px solid #cbd5df;padding:10px 20px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}select,input,textarea,button{font:inherit;border:1px solid #aebcc7;border-radius:5px;padding:6px;background:white;color:#172b39}button{cursor:pointer;background:#e8f0f5}button:hover{background:#cfe1ee}label{display:inline-flex;gap:6px;align-items:center}#cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.card{background:white;border:1px solid #d5dfe5;border-radius:8px;overflow:hidden}.card img{display:block;width:100%;aspect-ratio:2;object-fit:contain;background:#e3e8ec}.body{padding:14px}.id{font-size:12px;overflow-wrap:anywhere;color:#526777}.badge{display:inline-block;background:#eaf0f4;padding:3px 8px;border-radius:4px;margin:4px 4px 4px 0}.candidate{background:#ffddba}.possible{background:#fff0c7}.fields{border-top:1px solid #ddd;margin-top:12px;padding-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:9px}.fields label{display:flex;align-items:stretch;flex-direction:column}.fields input,.fields select,.fields textarea{width:100%}.wide{grid-column:1/-1}.notice{background:#fff5db;padding:12px;border-left:4px solid #a4761e}.aihidden .ai{display:none}dialog{width:min(96vw,1800px);border:0;border-radius:8px}dialog img{width:100%}dialog::backdrop{background:#000b}#count{font-weight:600}summary{cursor:pointer}a{color:#175b8e}@media(max-width:900px){#cards{grid-template-columns:1fr}.bar{position:static}}
</style>
<header><h1>室内图片重新粗分类 · 等待你的确认</h1><p>valid 190张 + test 458张 · 25栋building · 已重新逐图目视粗分类，7个功能粗组＋特殊用途／复合待定；旧细标签仅作历史参考。</p>
<p class="notice">候选组可能是同房间、开放区域或交界处的同一局部场景，不代表确定房间总数。最终分类由你决定。新定义：相机位于门洞中间。旧交界候选仅供重新核对，不是新定义的确认结果。</p>
<details><summary>怎样填写，以及这次初分的边界</summary><p>先选building，再选候选组并对照原图。同一building内，你认为同房的图片填写相同房间编号；跨楼类型填写你自己的类别名。门洞中间拍摄与成像异常独立填写，可以暂不判断。粗类别来自第二遍逐图判断，保留旧细标签供对照。房间编号由building限定，跨楼同名不会被视为同房。</p><p>AI与用户填写分开保存。r1/r2只预填你此前确认的五张图的房间编号，其他字段仍空白。不同AI组可能需要合并，同一AI组也可能需要拆分。未配对不表示独立房间。</p><p>旧交界判断不自动填入新字段。新定义不包括仅靠近门口或看见邻室。成像异常记录明显错位、断裂或局部异常拉伸；正常全景投影形变不自动算异常。页面不展示标注点、质量、人数或稳定曲线。<a href="探索说明.md" target="_blank">阅读完整说明</a></p></details></header>
<div class="bar"><label>building <select id="building"></select></label><label>AI候选组 <select id="group"></select></label><label>AI粗功能组 <select id="coarse"></select></label><label>AI细标签 <select id="type"></select></label><label>旧AI交界候选 <select id="boundary"></select></label><label>我的门洞判断 <select id="doorway"></select></label><label>检索 <input id="search" placeholder="编号、文件名或观察"></label><label><input id="hideai" type="checkbox">隐藏AI建议</label><button id="export">导出我的分类 JSON</button><span id="save" role="status"></span></div>
<main><p id="count"></p><p id="buildingNote" class="muted"></p><div id="cards"></div></main>
<dialog id="zoom"><button id="closeZoom">关闭原图</button><p id="zoomTitle"></p><img id="zoomImage" alt="原始全景图"></dialog>
<script id="data" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.getElementById('data').textContent), rows=data.rows, $=id=>document.getElementById(id);
const key='hohonet-scene-user-review-20260910-v1';let edits={};
try{const saved=JSON.parse(localStorage.getItem(key)||'{}');if(!saved||Array.isArray(saved)||typeof saved!=='object')throw Error('格式错误');edits=saved;$('save').textContent='本地自动保存；请定期导出';}catch(e){$('save').textContent='本地记录读取失败，请导出当前填写另存';}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function options(el,items,first){el.innerHTML='<option value="">'+first+'</option>'+items.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('');}
const buildings=[...new Set(rows.map(r=>r.building))];
options($('building'),buildings.map(b=>[b,`${b} (${rows.filter(r=>r.building===b).length})`]),'全部building');
options($('coarse'),Object.entries(data.coarse_types).map(([k,v])=>[k,`${v} (${rows.filter(r=>r.ai_coarse_type===k).length})`]),'全部粗类别');options($('doorway'),['未填写','确认','疑似','否','无法判断'].map(v=>[v,v]),'全部新判断');options($('type'),Object.entries(data.types),'全部细标签');options($('boundary'),Object.entries(data.boundary),'全部状态');
$('building').value='';
function updateGroups(){const g=[...new Set(rows.filter(r=>!$('building').value||r.building===$('building').value).map(r=>r.ai_group).filter(Boolean))];options($('group'),g.map(x=>[x,`${x} (${rows.filter(r=>r.ai_group===x).length})`]),'全部候选组（含未配对）');$('group').add(new Option('仅未配对','ungrouped'));}
function field(r,k){return edits[r.image_id]?.[k]??r[k];}
function selectField(r,k,label,values){return `<label>${label}<select data-field="${k}">${values.map(v=>`<option ${field(r,k)===v?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;}
function render(){const b=$('building').value,g=$('group').value,t=$('type').value,a=$('boundary').value,c=$('coarse').value,d=$('doorway').value,q=$('search').value.trim().toLowerCase();
 const selected=rows.filter(r=>(!b||r.building===b)&&(!g||(g==='ungrouped'?!r.ai_group:r.ai_group===g))&&(!t||r.ai_type===t)&&(!a||r.ai_boundary===a)&&(!c||r.ai_coarse_type===c)&&(!d||(d==='未填写'?!field(r,'user_doorway'):field(r,'user_doorway')===d))&&(!q||[r.image_id,String(r.number),r.group_evidence,r.image_note,field(r,'user_note')].join(' ').toLowerCase().includes(q)));
 selected.sort((a,b)=>Object.keys(data.coarse_types).indexOf(a.ai_coarse_type)-Object.keys(data.coarse_types).indexOf(b.ai_coarse_type)||a.building.localeCompare(b.building)||Number(!a.ai_group)-Number(!b.ai_group)||a.ai_group.localeCompare(b.ai_group)||a.number-b.number);
 $('count').textContent=`当前显示 ${selected.length} / ${rows.length} 张；全库门洞判断已填 ${rows.filter(r=>field(r,'user_doorway')).length}，确认 ${rows.filter(r=>field(r,'user_doorway')==='确认').length}，疑似 ${rows.filter(r=>field(r,'user_doorway')==='疑似').length}（图数，非房间数）`;
 $('buildingNote').textContent=b?rows.find(r=>r.building===b).building_note:'';
 $('cards').innerHTML=selected.map(r=>`<article class="card" data-id="${esc(r.image_id)}"><a href="../../${r.path}" data-zoom="${esc(r.image_id)}"><img loading="lazy" src="../../${r.path}" alt="${esc(r.building)} 第${r.number}张全景图"></a><div class="body"><strong>${r.building} · 图${String(r.number).padStart(2,'0')} · ${r.split}</strong><div class="id">${r.image_id}</div><div class="ai"><span class="badge">粗组：${esc(data.coarse_types[r.ai_coarse_type])}</span><p class="muted">本轮观察：${esc(r.coarse_review_note||"依据图片中主要可见空间与功能设施重新粗分；最终由用户核对。")}</p><details><summary>旧细标签与候选同房线索</summary><span class="badge">旧细标签：${esc(data.types[r.ai_type])}</span><span class="badge ${r.ai_boundary}">旧交界候选：${data.boundary[r.ai_boundary]}</span><p>${r.ai_group?`候选组 ${esc(r.ai_group)} <button data-group="${r.ai_group}">只看同组</button>`:'房间/场景身份：未配对'}</p><p class="muted">${esc(r.group_evidence||'只有初步功能描述，缺少足够同房定位证据。')}</p><p class="muted">${esc(r.image_note)}</p></details></div>${r.prior_user_room?`<p>此前用户确认房间：<b>${r.prior_user_room}</b>（仅本图记录）</p>`:''}<div class="fields"><label>我的房间/场景编号<input data-field="user_room" value="${esc(field(r,'user_room'))}" placeholder="留空表示待定"></label><label>我的跨楼类型<input data-field="user_type" value="${esc(field(r,'user_type'))}" placeholder="可自定类别名"></label>${field(r,'user_boundary')?`<p class="wide">旧交界判断（保留，需复核）：${esc(field(r,'user_boundary'))}</p>`:''}${selectField(r,'user_doorway','相机是否位于门洞中间',['','确认','疑似','否','无法判断'])}${selectField(r,'user_artifact','可见拼接／异常形变',['','明显异常','疑似异常','未见明显异常','无法判断'])}${selectField(r,'user_status','本图复核状态',['未复核','已复核','需讨论'])}<label class="wide">我的备注<textarea rows="2" data-field="user_note">${esc(field(r,'user_note'))}</textarea></label></div></div></article>`).join('');}
$('cards').addEventListener('input',e=>{const f=e.target.dataset.field;if(!f)return;const id=e.target.closest('.card').dataset.id;edits[id]={...edits[id],[f]:e.target.value};try{localStorage.setItem(key,JSON.stringify(edits));$('save').textContent='已在当前浏览器保存；可导出JSON';}catch(err){$('save').textContent='本地保存失败，请立即导出JSON';}});
$('cards').addEventListener('change',e=>{if(['user_doorway','user_artifact'].includes(e.target.dataset.field))render();});
$('cards').addEventListener('click',e=>{const z=e.target.closest('[data-zoom]');if(z){e.preventDefault();const r=rows.find(r=>r.image_id===z.dataset.zoom);$('zoomImage').src='../../'+r.path;$('zoomTitle').textContent=r.image_id;$('zoom').showModal();}const g=e.target.closest('[data-group]');if(g){const r=rows.find(r=>r.ai_group===g.dataset.group);$('building').value=r.building;updateGroups();$('group').value=g.dataset.group;render();window.scrollTo(0,0);}});
$('closeZoom').onclick=()=>$('zoom').close();$('building').onchange=()=>{updateGroups();render();};['group','type','boundary','coarse','doorway'].forEach(id=>$(id).onchange=render);$('search').oninput=render;$('hideai').onchange=()=>document.body.classList.toggle('aihidden',$('hideai').checked);
$('export').onclick=()=>{const output={schema:'scene_user_review_v2',doorway_definition:data.doorway_definition,saved_at:new Date().toISOString(),interpretation:'用户填写；AI初分另存，空白不等于否定',rows:rows.map(r=>({image_id:r.image_id,building:r.building,split:r.split,...Object.fromEntries(['user_room','user_type','user_boundary','user_doorway','user_artifact','user_status','user_note'].map(k=>[k,field(r,k)]))}))};const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(output,null,2)],{type:'application/json'}));a.href=url;a.download='室内图片_我的分类.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
updateGroups();render();
</script></html>'''


def build(make_sheets=False):
    OUT.mkdir(parents=True, exist_ok=True)
    raw = inventory(ROOT)
    judgments = json.loads((OUT / 'ai_visual_judgments.json').read_text(encoding='utf8'))
    rows = expand_judgments(raw, judgments)
    coarse = {}
    for name in ('coarse_recheck_part1.json', 'coarse_recheck_part2.json'):
        part = json.loads((OUT / name).read_text(encoding='utf8'))
        if set(coarse) & set(part):
            raise ValueError('Duplicate coarse review building')
        coarse.update(part)
    apply_coarse_review(rows, coarse)
    (OUT / 'inventory.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf8')
    payload = dict(schema='scene_image_exploration_v3', types=TYPES, coarse_types=COARSE,
                   boundary=BOUNDARY, doorway_definition='相机位于门洞中间的空间交界处；旧交界候选不自动转换', rows=rows)
    (OUT / 'image_classification.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf8')
    page_data = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')
    (OUT / '图片初分核对.html').write_text(PAGE.replace('__DATA__', page_data), encoding='utf8')
    groups = Counter(r['ai_group'] for r in rows if r['ai_group'])
    summary = dict(images=len(rows), buildings=len(judgments), splits=dict(Counter(r['split'] for r in rows)),
                   candidate_groups=len(groups), grouped_images=sum(groups.values()),
                   unpaired_images=sum(not r['ai_group'] for r in rows),
                   boundary=dict(Counter(r['ai_boundary'] for r in rows)),
                   boundary_scope='legacy_broad_candidates_not_doorway_confirmations',
                   doorway_reviewed_images=0,
                   coarse_reviewed_images=len(rows),
                   coarse_changed_from_mapping=sum(r['ai_coarse_type'] != r['legacy_mapped_coarse_type'] for r in rows),
                   coarse_original_rechecked=sum(r['coarse_original_rechecked'] for r in rows),
                   coarse_types={COARSE[k]: v for k, v in Counter(r['ai_coarse_type'] for r in rows).items()},
                   types={TYPES[k]: v for k, v in Counter(r['ai_type'] for r in rows).items()},
                   original_rechecked=sum(r['original_image_rechecked'] for r in rows),
                   prior_user_confirmed_images=sum(bool(r['prior_user_room']) for r in rows),
                   candidate_group_size_distribution=dict(Counter(groups.values())))
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
    if make_sheets:
        contact_sheets(raw, ROOT, OUT)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contact-sheets', action='store_true')
    build(parser.parse_args().contact_sheets)
