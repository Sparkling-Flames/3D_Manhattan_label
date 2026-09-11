"""把原图复核记录与用户原始填写并列展示；不修改用户标签。"""
import argparse
import json
from collections import Counter
from html import escape
from pathlib import Path

from tools.thesis_main.analysis.build_scene_image_exploration import ROOT, OUT, inventory


def assemble(user, raw, parts):
    if user['schema'] != 'scene_user_review_v2':
        raise ValueError('Unexpected user schema')
    idx = {r['image_id']: r for r in raw}
    users = {r['image_id']: r for r in user['rows']}
    if len(users) != len(user['rows']) or set(users) != set(idx):
        raise ValueError('Duplicate or missing user image IDs')
    for image_id, r in users.items():
        if (r['building'], r['split']) != (idx[image_id]['building'], idx[image_id]['split']):
            raise ValueError('Image metadata mismatch')
        for field in ('user_room', 'user_type', 'user_doorway', 'user_artifact', 'user_status', 'user_note'):
            if not isinstance(r[field], str):
                raise ValueError('Invalid user field')
    reviewed, issues, originals = [], [], set()
    for part in parts:
        reviewed.extend(part['reviewed'])
        issues.extend(r for r in part['issues'] if r['dimension'] != 'doorway')
        originals.update(part.get('additional_original_ids', []))
    if len({r['image_id'] for r in reviewed}) != len(reviewed):
        raise ValueError('Duplicate visual review')
    for r in reviewed:
        if r['image_id'] not in idx or r['original_viewed'] is not True:
            raise ValueError('Invalid original review')
        originals.add(r['image_id'])
        label = users[r['image_id']]['user_doorway']
        assessment = r['doorway_assessment']
        if assessment not in ('支持候选', '证据不足', '更像非门洞', '无法判断'):
            raise ValueError('Unknown doorway assessment')
        disputed = (assessment == '更像非门洞' and label != '否') or (label == '确认' and assessment != '支持候选') or (label == '否' and assessment == '支持候选')
        severity = '建议修正' if assessment == '更像非门洞' and label == '确认' else '需确认'
        suggestion = {'更像非门洞': '按当前严格定义，建议改为否；若只是墙端/开放分区影响，可另记备注。',
                      '证据不足': '保留疑似或无法判断；需要额外定位证据才能确认门洞中间。',
                      '无法判断': '保留无法判断，不计作确认，也不据此推定质量低。',
                      '支持候选': '保留门洞候选；单幅图不能量测是否精确居中。'}[assessment]
        issues.append(dict(image_id=r['image_id'], dimension='doorway' if disputed else 'reference',
                           severity=severity if disputed else '对照记录', reason=r['reason'],
                           suggestion=suggestion, related_ids=[], assessment=assessment))
    if not originals <= set(idx):
        raise ValueError('Unknown original ID')
    targets = {r['image_id'] for r in users.values() if r['user_doorway'] != '否'}
    if not targets <= {r['image_id'] for r in reviewed}:
        raise ValueError('Nonnegative doorway review incomplete')
    for r in issues:
        ids = [r['image_id'], *r.get('related_ids', [])]
        if not set(ids) <= set(idx):
            raise ValueError('Unknown issue ID')
        r['images'] = [{**idx[i], 'user': users[i]} for i in ids]
    order = {'room': 0, 'doorway': 1, 'type': 2, 'artifact': 3, 'reference': 4}
    issues.sort(key=lambda r: (order[r['dimension']], r['images'][0]['building'], r['images'][0]['number']))
    for n, r in enumerate(issues, 1):
        r['case_id'] = f'C{n:03d}'
    disputes = [r for r in issues if r['dimension'] != 'reference']
    return dict(schema='scene_user_visual_audit_v1', user_saved_at=user['saved_at'],
                interpretation='AI原图目视复核候选；用户原始填写逐字段保留；未作几何定位或标签覆盖。',
                summary=dict(input_images=len(raw), original_images_viewed=len(originals),
                             doorway_originals=len(reviewed), doorway_nonnegative=len(targets),
                             source_doorway_counts=dict(Counter(r['user_doorway'] for r in users.values())),
                             doorway_assessments=dict(Counter(r['doorway_assessment'] for r in reviewed)),
                             dispute_cases=len(disputes), dispute_by_dimension=dict(Counter(r['dimension'] for r in disputes)),
                             disputed_unique_images=len({r['image_id'] for r in disputes})),
                source_user=user, reviewed=reviewed, original_ids=sorted(originals), cases=issues)


def render(audit):
    names = dict(room='房间编号', doorway='门洞位置', type='粗分类', artifact='图像异常', reference='对照记录')
    cards = []
    for r in audit['cases']:
        pictures = []
        for im in r['images']:
            u = im['user']
            src = '../../' + im['path']
            label = f"{im['building']} · {im['number']:02d} · {im['image_id'].split('_')[1][:8]}"
            meta = ' ｜ '.join(f'{name}：{u[field] or "未填"}' for field, name in
                              [('user_room', '房间'), ('user_type', '类型'), ('user_doorway', '门洞'), ('user_artifact', '异常')])
            fields = []
            for field, title, options in [
                ('user_room', '我的房间编号', None), ('user_type', '我的粗分类', None),
                ('user_doorway', '相机是否在门洞中间', ['确认', '疑似', '否', '无法判断']),
                ('user_artifact', '图像异常', ['明显异常', '疑似异常', '未见明显异常', '无法判断']),
                ('user_note', '我的备注', None),
                ('user_audit_status', '我这次的复核状态', ['待我复核', '已确认', '仍需讨论'])]:
                if options:
                    control = f'<select data-field="{field}">' + ''.join(f'<option>{x}</option>' for x in options) + '</select>'
                else:
                    control = f'<input data-field="{field}">' if field != 'user_note' else f'<textarea rows="2" data-field="{field}"></textarea>'
                fields.append(f'<label>{title}{control}</label>')
            pictures.append(f'<figure><figcaption><b>{escape(label)}</b><br>{escape(meta)}<br>原备注：{escape(u["user_note"] or "无")}</figcaption><a href="{escape(src)}" target="_blank"><img loading="lazy" src="{escape(src)}" alt="{escape(label)}"></a><small>{escape(im["image_id"])}</small><fieldset data-image="{escape(im["image_id"])}"><legend>在这里填写（已带入原分类，可直接修改）</legend>{"".join(fields)}</fieldset></figure>')
        cards.append(f'<article id="{r["case_id"]}" data-kind="{r["dimension"]}"><h2>{r["case_id"]} · {names[r["dimension"]]} · {escape(r["severity"])}</h2><p><b>复核判断：</b>{escape(r.get("assessment", ""))} {escape(r["reason"])}</p><p><b>建议：</b>{escape(r["suggestion"])}</p>{"".join(pictures)}</article>')
    s = audit['summary']
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>分类与门洞位置：争议图片复核</title>
<style>body{margin:0;background:#f1f4f7;color:#233344;font:16px/1.65 "Microsoft YaHei",sans-serif}main{max-width:1400px;margin:auto;padding:24px}header,article{background:white;border-radius:12px;padding:22px;margin-bottom:22px}h1{margin:0 0 10px;font-size:27px}h2{font-size:21px;color:#17567e}figure{margin:14px 0 24px}figcaption{background:#f0f5f9;padding:10px}img{display:block;width:100%;height:auto}small{overflow-wrap:anywhere;color:#687682}nav{position:sticky;top:0;background:#e6eef5;padding:12px;z-index:2}select{font:inherit;padding:5px;max-width:70%}[hidden]{display:none}p{margin:7px 0}</style><main><header><h1>分类与门洞位置：争议图片复核</h1>''' + f'''
<p>检查 {s['input_images']} 条填写记录；本轮重点查看 {s['original_images_viewed']} 张原图，其中 {s['doorway_nonnegative']} 张“确认／疑似／无法判断”全部复核。列出 {s['dispute_cases']} 项争议（同图可涉及多个问题）。这不是全量标签正确率评估。</p>
<p><b>门洞标准：</b>相机位于同一门洞内、两个空间交界处。门洞候选不等于精确居中已经证实；看见门、靠近门、处于柱子或墙端旁都不足以确认。</p>
<p><b>阅读方法：</b>先看“房间编号”，再看“门洞位置”。每项保留原填写并给出复核依据，点击图片看原图。成对图片上下排列，便于对照相同家具、窗和入口。</p>
<p>“建议修正”表示有较具体的冲突线索；“需确认”表示仍有争议；“对照记录”含有依据的候选、保留疑似及维持否。</p>
<p><b>填写：</b>每张图下面修改分类，然后把“我这次的复核状态”选为“已确认”或“仍需讨论”；认可原分类也可直接选“已确认”。同图在多项出现时自动同步。完成后点“导出完整648图分类”，把JSON发回来。</p>
<p><b>范围说明：</b>标注者提交了全部648图的分类（638图已复核、10图需讨论），房间、类型、门洞、异常均已填写。113图是AI本轮重点原图复核量，不是标注者完成量。本页只展示复核涉及的图片；导出保留全部648条，其他图原样保留。</p></header>
<nav><label for="kind">筛选：</label><select id="kind"><option value="disputes">全部争议</option>''' + ''.join(f'<option value="{k}">{v}</option>' for k,v in names.items()) + '''<option value="all">全部（含对照）</option></select> <span id="count"></span></nav>''' + ''.join(cards) + '''</main><script>
const sel=document.querySelector('#kind'),cards=[...document.querySelectorAll('article')];
function filter(){let n=0;for(const c of cards){c.hidden=!(sel.value==='all'||sel.value===c.dataset.kind||(sel.value==='disputes'&&c.dataset.kind!=='reference'));if(!c.hidden)n++}document.querySelector('#count').textContent=n+' 项'}
sel.addEventListener('change',filter);if(location.hash&&document.querySelector(location.hash)?.dataset.kind==='reference')sel.value='reference';filter();
</script><style>img{aspect-ratio:2/1}</style>''' + '<script id="source" type="application/json">' + json.dumps(audit['source_user'], ensure_ascii=False).replace('<', '\\u003c') + '''</script>
<style>fieldset{border:2px solid #3b7d9b;background:#eef8f6;padding:16px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}legend{font-weight:bold}fieldset label{display:flex;flex-direction:column}input,textarea,fieldset select{font:inherit;padding:8px;max-width:100%;box-sizing:border-box}button{font:inherit;padding:7px;cursor:pointer}#save{font-size:14px;margin-left:10px}@media(max-width:650px){fieldset{grid-template-columns:1fr}}</style>
<script>
const source=JSON.parse(document.querySelector('#source').textContent),original=new Map(source.rows.map(r=>[r.image_id,r]));
const key='scene-dispute-review-v1:'+source.saved_at,boxes=[...document.querySelectorAll('fieldset[data-image]')];let edits={};
const nav=document.querySelector('nav');nav.insertAdjacentHTML('beforeend',' <button id="export">导出完整648图分类</button><span id="save" role="status"></span>');
const save=document.querySelector('#save');
try{const stored=JSON.parse(localStorage.getItem(key)||'{}');if(!stored||Array.isArray(stored)||typeof stored!=='object'||Object.entries(stored).some(([id,v])=>!original.has(id)||!v||typeof v!=='object'||Object.values(v).some(x=>typeof x!=='string')))throw Error('记录格式不匹配');edits=stored;save.textContent='当前浏览器自动保存；完成后请导出';}catch(e){save.textContent='本地记录读取失败：'+e.message;}
function fill(id){for(const box of boxes){if(id&&box.dataset.image!==id)continue;const data={...original.get(box.dataset.image),...edits[box.dataset.image]};for(const f of box.querySelectorAll('[data-field]'))f.value=data[f.dataset.field]??(f.dataset.field==='user_audit_status'?'待我复核':'');}}
fill();
document.addEventListener('input',e=>{const field=e.target.dataset.field,box=e.target.closest('fieldset[data-image]');if(!field||!box)return;const id=box.dataset.image;edits[id]={...edits[id],[field]:e.target.value};if(field!=='user_audit_status')edits[id].user_audit_status='待我复核';fill(id);try{localStorage.setItem(key,JSON.stringify(edits));save.textContent='已自动保存；'+Object.values(edits).filter(r=>r.user_audit_status==='已确认').length+' 图本轮已确认';}catch(err){save.textContent='本地保存失败，请立即导出JSON';}});
document.querySelector('#export').onclick=()=>{const output={...source,saved_at:new Date().toISOString(),audit_source_saved_at:source.saved_at,rows:source.rows.map(r=>{const row={...r,...edits[r.image_id]};if(row.user_audit_status==='已确认')row.user_status='已复核';else if(row.user_audit_status==='仍需讨论')row.user_status='需讨论';return row;})};const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(output,null,2)],{type:'application/json'}));a.href=url;a.download='室内图片_争议复核后完整分类.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
</script></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', type=Path, required=True)
    args = parser.parse_args()
    user = json.loads(args.user.read_text(encoding='utf-8'))
    parts = [json.loads((OUT / f'user_audit_part{n}.json').read_text(encoding='utf-8')) for n in (1, 2)]
    audit = assemble(user, inventory(ROOT), parts)
    audit['source_path'] = str(args.user)
    (OUT / 'user_visual_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / '争议图片复核.html').write_text(render(audit), encoding='utf-8')
    print(json.dumps(audit['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
