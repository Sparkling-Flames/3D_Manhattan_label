"""汇总原图同房配对建议，生成独立复核页；不读取标注结果或改写人工交界。"""
import argparse
import json
from pathlib import Path
from collections import Counter

from tools.thesis_main.analysis.build_scene_image_exploration import ROOT, OUT, inventory

OPTIONS = {
    'physical_same': ['支持', '待定', '不支持'],
    'main_visual_alignment': ['一致', '不同', '待定'],
    'extent_alignment': ['预期相近', '存在明显差异', '待定'],
    'difficulty_similarity': ['预期相近', '可能出现小幅歧义', '存在明显差异', '待定'],
    'decision': ['优先候选', '基础候选', '对照候选', '待定', '不支持'],
    'status': ['', '已确认', '仍需讨论'],
}


def assemble(user, raw, parts):
    if user['schema'] != 'scene_open_layout_user_review_v3':
        raise ValueError('Unexpected source schema')
    idx = {r['image_id']: r for r in raw}
    users = {r['image_id']: r for r in user['rows']}
    if len(idx) != len(raw) or len(users) != len(user['rows']) or set(users) != set(idx):
        raise ValueError('Duplicate or missing source IDs')
    for i, r in users.items():
        if any(r[k] != idx[i][k] for k in ('building', 'number', 'split', 'path')):
            raise ValueError('Source identity mismatch')
    images, pairs, seen = {}, [], set()
    lookup = {(r['building'], r['number']): r['image_id'] for r in raw}
    for part in parts:
        if part['schema'] != 'same_room_research_pairs_v1' or set(part['buildings']) != {r['building'] for r in part['images']}:
            raise ValueError('Unexpected part schema or building coverage')
        for r in part['images']:
            i = r['image_id']
            if i not in idx or i in images or lookup.get((r['building'], r['number'])) != i:
                raise ValueError('Unknown or duplicate reviewed image')
            if r['view_basis'] not in ('individual_original', 'large_panel_recheck'):
                raise ValueError('Invalid visual review basis')
            for k in ('main_visual_space', 'expected_annotation_extent', 'ambiguity_and_information', 'note'):
                if not isinstance(r[k], str) or not r[k].strip():
                    raise ValueError('Missing image evidence: ' + k)
            nums = r['candidate_numbers']
            if not isinstance(nums, list) or len(nums) != len(set(nums)) or any(type(n) is not int or n == r['number'] or (r['building'], n) not in lookup for n in nums):
                raise ValueError('Invalid candidate numbers')
            images[i] = {**r, 'path': idx[i]['path'], 'split': idx[i]['split'], 'reviewer': part['reviewer']}
        for p in part['pairs']:
            key = (p['building'], p['a'], p['b'])
            if key in seen or type(p['a']) is not int or type(p['b']) is not int or p['a'] >= p['b'] or any((p['building'], n) not in lookup for n in (p['a'], p['b'])):
                raise ValueError('Invalid pair identity')
            if p['building'] not in part['buildings']:
                raise ValueError('Pair outside assigned buildings')
            seen.add(key)
            for k, vals in OPTIONS.items():
                if k != 'status' and p[k] not in vals:
                    raise ValueError('Invalid pair category: ' + k)
            if p['decision'] in ('优先候选', '基础候选') and (p['physical_same'] != '支持' or p['main_visual_alignment'] != '一致'):
                raise ValueError('Prediction pair lacks room/main-space support')
            if p['decision'] == '优先候选' and (p['extent_alignment'] != '预期相近' or p['difficulty_similarity'] == '存在明显差异'):
                raise ValueError('Priority pair lacks comparability')
            if any(not isinstance(p[k], str) or not p[k].strip() for k in ('evidence', 'differences')):
                raise ValueError('Missing direct pair evidence')
            pairs.append({**p, 'pair_id': f"{p['building']}:{p['a']:02d}-{p['b']:02d}",
                          'image_ids': [lookup[(p['building'], n)] for n in (p['a'], p['b'])], 'reviewer': part['reviewer']})
    if set(images) != set(idx):
        raise ValueError(f'Incomplete image review: {len(images)} / {len(idx)}')
    for p in pairs:
        if any(other not in images[i]['candidate_numbers'] for i, other in zip(p['image_ids'], (p['b'], p['a']))):
            raise ValueError('Pair absent from image comparison ledger: ' + p['pair_id'])
    pairs.sort(key=lambda p: (p['building'], p['a'], p['b']))
    paired = {i for p in pairs if p['decision'] in ('优先候选', '基础候选') for i in p['image_ids']}
    return dict(schema='same_room_pair_audit_v1', source_user=user, images=list(images.values()), pairs=pairs,
                summary=dict(images=len(images), buildings=len({r['building'] for r in raw}), pairs=len(pairs),
                             decisions=dict(Counter(p['decision'] for p in pairs)), candidate_images=len(paired),
                             views=dict(Counter(r['view_basis'] for r in images.values()))))


def render(audit, resume=None):
    return PAGE.replace('__DATA__', json.dumps(audit, ensure_ascii=False).replace('<', '\\u003c')).replace('__OPTIONS__', json.dumps(OPTIONS, ensure_ascii=False)).replace('__RESUME__', json.dumps(resume, ensure_ascii=False).replace('<', '\\u003c'))


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>同房研究：多图复核</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf2f5;color:#233b4b;font:16px/1.6 "Microsoft YaHei",sans-serif}main{max-width:1450px;margin:auto;padding:20px}header,article{background:white;padding:20px;margin-bottom:20px;border-radius:10px}h1{font-size:27px}h2{font-size:22px;color:#175d7e}p{margin:8px 0}nav{background:#deecf4;padding:12px;position:sticky;top:0;z-index:2}button,input,select,textarea{font:inherit;padding:6px;max-width:100%;border:1px solid #7f9db3;border-radius:4px}button{cursor:pointer;background:white}label{display:inline-block;margin:4px}figure{margin:15px 0}figcaption{padding:10px;background:#f0f6fa}img{width:100%;height:auto;aspect-ratio:2/1;display:block}small{color:#516878;overflow-wrap:anywhere}fieldset{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;border:2px solid #78a494}fieldset label{display:flex;flex-direction:column}fieldset .wide{grid-column:1/-1}pre{white-space:pre-wrap;font:inherit}a{color:#14658e}[data-changed="false"]{background:#e7f1ff;border-color:#6895c8}[data-changed="true"]{background:#fff0d6;border-color:#c78220}#save{display:block;font-size:14px}.evidence{padding:10px;background:#f1f7f5;border-left:4px solid #568f7c}@media(max-width:700px){main{padding:7px}fieldset{grid-template-columns:1fr}nav{position:static}}
</style><main><header><h1>同房研究：多图复核</h1><p id="summary"></p>
<p><b>研究配对：</b>同一实际房间、主视觉空间一致；预计标注范围与歧义／信息困难相近者优先。这里是原图判断，尚未证明收敛相似。</p>
<p><b>怎么填：</b>默认按关联候选组一起显示多张图，不限制每房2张。先看整组图片，再填写整组共用的一份判断；认可就保留，有异议再改或写评论。蓝色表示维持初始值，橙色表示修改；状态只由你手动改。交界沿用你的人工结果，只读展示。</p>
<p><b>优先候选</b>：预计可比；<b>基础候选</b>：同房同主空间，但范围／难度仍待核；<b>对照候选</b>：物理同房而视点条件不同；<b>待定</b>：身份或主空间证据不足；<b>不支持</b>：该对存在不合并依据。空缺配对不代表没有同房图。配对共用图片，不能把每对当独立样本。</p>
<p>“可能出现小幅歧义”表示你预计仍可能有少量范围解释或标法分歧，不自动改变研究建议，也不代表已测得分歧。个别图有差异或需要排除时，在本组评论写明图号。</p>
<p>默认每页一组，组内每张图只展示一次；整组只填一次。分组用于集中查看关联候选，<b>不是确认整组同房</b>，不会通过A–B、B–C自动确认A–C。筛选命中某一对时仍展示其所在整组，避免漏看其他视点。完成后请导出JSON。</p></header>
<nav><label>楼栋 <select id="building"><option value="">全部</option></select></label><label>建议 <select id="kind"><option value="优先候选">优先候选</option><option value="基础候选">基础候选</option><option value="对照候选">对照候选</option><option value="待定">待定</option><option value="不支持">不支持</option><option value="">全部</option></select></label><label>图号／关键词 <input id="search" size="14"></label>
<button id="prev">上一页</button> <span id="count"></span> <button id="next">下一页</button> <button id="export">导出完整配对复核</button><label>导入 <input id="import" type="file" accept=".json" style="width:155px"></label><span id="save" role="status"></span></nav><section id="cards"></section>
<details><summary>查看全部图片的检索记录（含暂无配对者）</summary><div id="inventory"></div></details></main>
<script id="audit" type="application/json">__DATA__</script><script>
const audit=JSON.parse(document.getElementById('audit').textContent),pairs=audit.pairs,options=__OPTIONS__;
const fields=[...Object.keys(options),'note'],byPair=new Map(pairs.map(p=>[p.pair_id,p])),byImage=new Map(audit.images.map(r=>[r.image_id,r])),source=new Map(audit.source_user.rows.map(r=>[r.image_id,r]));
const prefills=new Map(pairs.map(p=>[p.pair_id,Object.fromEntries(fields.map(f=>[f,p[f]||'']))]));
const resume=__RESUME__,key='same-room-groups-v3:'+audit.source_user.saved_at+':'+(resume?.saved_at||'blank'),save=document.getElementById('save');let edits={},page=0;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const current=id=>({...prefills.get(id),...edits[id]});
function validateEdits(v){if(!v||Array.isArray(v)||typeof v!=='object')throw Error('填写格式错误');for(const [id,e] of Object.entries(v)){if(!byPair.has(id)||!e||Array.isArray(e)||typeof e!=='object')throw Error('未知配对');for(const [f,s] of Object.entries(e))if(!fields.includes(f)||typeof s!=='string'||options[f]&&!options[f].includes(s))throw Error('未知字段或选项')}return v}
if(resume)edits=readImport(resume);

const building=document.getElementById('building'),kind=document.getElementById('kind'),search=document.getElementById('search');
for(const b of [...new Set(audit.images.map(r=>r.building))].sort())building.insertAdjacentHTML('beforeend',`<option>${esc(b)}</option>`);
document.getElementById('summary').textContent=`已重新目视检索 ${audit.summary.images} 图 / ${audit.summary.buildings} 楼，记录 ${pairs.length} 条直接比较关系；${Object.entries(audit.summary.decisions).map(([k,v])=>k+' '+v+' 对').join('，')}。原始统计为AI建议；你的已填写记录保留在对应表单中。`;
function picture(id){const r=byImage.get(id),u=source.get(id),c=u.current_classification,src='../../'+r.path;return `<figure><figcaption><b>${esc(r.building)} · ${String(r.number).padStart(2,'0')}</b><p>主空间：${esc(r.main_visual_space)}；预计范围：${esc(r.expected_annotation_extent)}</p><p>信息／歧义：${esc(r.ambiguity_and_information)}</p><p>人工交界：${esc(c.boundary||'沿用既有讨论，空值不等于否')}</p><p>原评论：${esc(u.source_user.user_note||'无')}；本轮评论：${esc(c.note||'无')}</p>${u.discussion?`<details><summary>既有讨论</summary><pre>${esc(JSON.stringify(u.discussion,null,2))}</pre></details>`:''}</figcaption><a href="${esc(src)}" target="_blank" rel="noopener"><img src="${esc(src)}" alt="${esc(r.building+' '+r.number)}" loading="lazy"></a><small>${esc(id)}</small></figure>`}
const titles={physical_same:'物理上是否同房',main_visual_alignment:'主视觉空间',extent_alignment:'预计标注范围',difficulty_similarity:'预计歧义／信息困难',decision:'研究配对建议',status:'我的复核状态',note:'我的评论'};
function control(f){return `<label class="${f==='note'?'wide':''}">${titles[f]}`+(f==='note'?'<textarea rows="3" data-field="note"></textarea>':`<select data-field="${f}">${options[f].map(v=>`<option value="${esc(v)}">${esc(v||'未单独标记')}</option>`).join('')}</select>`)+`<small></small></label>`}
function fill(){for(const box of document.querySelectorAll('fieldset[data-group]')){const id=box.dataset.group,c=groupCurrent(id);for(const f of box.querySelectorAll('[data-field]')){const name=f.dataset.field;f.value=c[name];const changed=c[name]!==groupPrefills.get(id)[name];f.dataset.changed=String(changed);f.nextElementSibling.textContent=changed?'已修改':'维持初始值';f.title='初始值：'+(groupPrefills.get(id)[name]||'（空）')}}}
function selected(){const q=search.value.trim().toLowerCase();return pairs.filter(p=>(!building.value||p.building===building.value)&&(!kind.value||p.decision===kind.value)&&(!q||/^\d+$/.test(q)&&[p.a,p.b].includes(Number(q))||!/^\d+$/.test(q)&&JSON.stringify(p).toLowerCase().includes(q)))}
function groupPairs(ps){
 const parent=new Map();for(const p of ps)for(const id of p.image_ids)parent.set(id,id);
 const find=id=>{while(parent.get(id)!==id)id=parent.get(id);return id};
 for(const p of ps)if(p.physical_same==='支持')parent.set(find(p.image_ids[1]),find(p.image_ids[0]));
 const groups=new Map();
 for(const p of ps){const [a,b]=p.image_ids,key=find(a)===find(b)?find(a):p.pair_id;
  if(!groups.has(key))groups.set(key,{pairs:[],image_ids:[]});const g=groups.get(key);g.pairs.push(p);
  for(const id of p.image_ids)if(!g.image_ids.includes(id))g.image_ids.push(id);
 }return [...groups.values()];
}
function pairEvidence(p){return '<h4>'+esc(p.pair_id)+'</h4><p>'+esc(p.evidence)+' '+esc(p.differences)+'</p>'+(Object.keys(edits[p.pair_id]||{}).length?'<p>你此前的逐对填写：'+esc(JSON.stringify(edits[p.pair_id]))+'</p>':'')}
function draw(){
 const matched=new Set(selected().map(p=>p.pair_id)),units=groups.filter(g=>g.pairs.some(p=>matched.has(p.pair_id)));
 const pages=Math.max(1,units.length);page=Math.max(0,Math.min(page,pages-1));
 document.getElementById('count').textContent=(page+1)+'/'+pages+' 页 · '+units.length+' 组';
 document.getElementById('prev').disabled=!page;document.getElementById('next').disabled=page>=pages-1;
 document.getElementById('cards').innerHTML=units.slice(page,page+1).map(g=>'<article><h2>'+esc(g.pairs[0].building)+' · '+g.image_ids.map(id=>String(byImage.get(id).number).padStart(2,'0')).join(' / ')+'</h2><p>'+g.image_ids.length+' 张候选图，共用下方一份判断。若个别图应排除或单独分组，请在本组评论写图号和原因。</p>'+g.image_ids.map(picture).join('')+'<fieldset data-group="'+esc(g.group_id)+'"><legend>本组判断（整组只填写一次）</legend>'+fields.map(control).join('')+'</fieldset><details><summary>查看原始逐对依据和以前的填写（只读）</summary>'+g.pairs.map(pairEvidence).join('')+'</details></article>').join('')||'<article>当前筛选无候选组。</article>';fill()
}
for(const el of [building,kind,search])el.addEventListener('input',()=>{page=0;draw()});

document.getElementById('prev').onclick=()=>{page--;draw();window.scrollTo(0,0)};document.getElementById('next').onclick=()=>{page++;draw();window.scrollTo(0,0)};
document.addEventListener('input',e=>{const f=e.target.dataset.field,box=e.target.closest('fieldset[data-group]');if(!f||!box)return;const id=box.dataset.group;groupEdits[id]={...groupEdits[id],[f]:e.target.value};fill();persist()});
function legacyExport(){return {...structuredClone(audit),schema:'same_room_pair_user_review_v1',saved_at:new Date().toISOString(),pairs:pairs.map(p=>({...structuredClone(p),prefill:{...prefills.get(p.pair_id)},current:current(p.pair_id),changed_fields:fields.filter(f=>current(p.pair_id)[f]!==prefills.get(p.pair_id)[f]),user_revision:{...edits[p.pair_id]}}))}}
function readImport(d){if(d.schema!=='same_room_pair_user_review_v1'||JSON.stringify(d.source_user)!==JSON.stringify(audit.source_user)||JSON.stringify(d.images)!==JSON.stringify(audit.images)||!Array.isArray(d.pairs)||d.pairs.length!==pairs.length)throw Error('不是本页完整导出文件或原始内容发生改变');const next={},seen=new Set();for(const r of d.pairs){const p=byPair.get(r.pair_id);if(!p||seen.has(r.pair_id))throw Error('未知或重复配对');seen.add(r.pair_id);for(const k of Object.keys(p))if(JSON.stringify(r[k])!==JSON.stringify(p[k]))throw Error('原配对建议被改写');validateEdits({[r.pair_id]:r.user_revision});const initial=prefills.get(r.pair_id),c={...initial,...r.user_revision};if(JSON.stringify(r.prefill)!==JSON.stringify(initial)||JSON.stringify(r.current)!==JSON.stringify(c)||JSON.stringify(r.changed_fields)!==JSON.stringify(fields.filter(f=>c[f]!==initial[f])))throw Error('填写与导出值不一致');next[r.pair_id]=r.user_revision}return next}
document.getElementById('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(makeExport(),null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='同房研究_我的整组复核.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
document.getElementById('import').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const d=JSON.parse(await f.text()),old=readImport(d),updated=readGroups(d,old);if(Object.keys(groupEdits).length&&!confirm('用导入文件替换当前填写？请先导出尚未备份的修改。'))return;edits=old;groupEdits=updated;fill();persist()}catch(err){save.textContent='导入失败，当前填写未改：'+err.message}finally{e.target.value=''}};
document.getElementById('inventory').innerHTML=audit.images.map(r=>`<p><a href="${esc('../../'+r.path)}" target="_blank" rel="noopener">${esc(r.building)} · ${String(r.number).padStart(2,'0')}</a>：${esc(r.main_visual_space)}；直接比较 ${esc(r.candidate_numbers.join('、')||'本轮未列出')}。</p>`).join('');
const groups=groupPairs(pairs).map(g=>({...g,group_id:g.image_ids.slice().sort().join('|')}));
const groupById=new Map(groups.map(g=>[g.group_id,g]));
const groupPrefills=new Map(groups.map(g=>[g.group_id,Object.fromEntries(fields.map(f=>{
 const vals=[...new Set(g.pairs.map(p=>prefills.get(p.pair_id)[f]))];
 return [f,f==='status'||f==='note'?'':vals.length===1?vals[0]:'待定'];
}))]));
const groupCurrent=id=>({...groupPrefills.get(id),...groupEdits[id]});
function seedNotes(old){const out={};for(const g of groups){const notes=new Map();for(const p of g.pairs){const note=old[p.pair_id]?.note;if(note){if(!notes.has(note))notes.set(note,[]);notes.get(note).push(p.a+'/'+p.b)}}if(notes.size)out[g.group_id]={note:[...notes].map(([n,ids])=>'此前 '+ids.join('、')+'：'+n).join('\n')}}return out}
function validateGroups(v){if(!v||Array.isArray(v)||typeof v!=='object')throw Error('组填写格式错误');for(const [id,e] of Object.entries(v)){if(!groupById.has(id)||!e||Array.isArray(e)||typeof e!=='object')throw Error('未知组');for(const [f,s] of Object.entries(e))if(!fields.includes(f)||typeof s!=='string'||options[f]&&!options[f].includes(s))throw Error('未知组字段或选项')}return v}
function readGroups(d,old){if(!d.group_reviews){if(d.form_version===3)throw Error('缺少组记录');return seedNotes(old)}if(!Array.isArray(d.group_reviews)||d.group_reviews.length!==groups.length)throw Error('组记录不完整');const out={};for(const r of d.group_reviews){const g=groupById.get(r.group_id);if(!g||Object.hasOwn(out,r.group_id)||JSON.stringify(r.image_ids)!==JSON.stringify(g.image_ids)||JSON.stringify(r.pair_ids)!==JSON.stringify(g.pairs.map(p=>p.pair_id)))throw Error('组成员或编号改变');validateGroups({[r.group_id]:r.user_revision});const initial=groupPrefills.get(r.group_id),c={...initial,...r.user_revision};if(JSON.stringify(r.prefill)!==JSON.stringify(initial)||JSON.stringify(r.current)!==JSON.stringify(c)||JSON.stringify(r.changed_fields)!==JSON.stringify(fields.filter(f=>c[f]!==initial[f])))throw Error('组填写与导出不一致');out[r.group_id]=r.user_revision}return out}
let groupEdits=resume?readGroups(resume,edits):{};
try{const stored=localStorage.getItem(key);if(stored!==null)groupEdits=validateGroups(JSON.parse(stored));save.textContent='已带入既有填写；现在每组只填一次。完成后请导出JSON。'}catch(e){save.textContent='自动读取失败，已带入的填写保留：'+e.message}
function persist(){try{localStorage.setItem(key,JSON.stringify(groupEdits));save.textContent='本组填写已自动保存；请导出JSON备份。'}catch(e){save.textContent='自动保存失败，请立即导出JSON。'}}
function makeExport(){return {...legacyExport(),form_version:3,group_reviews:groups.map(g=>({group_id:g.group_id,image_ids:g.image_ids.slice(),pair_ids:g.pairs.map(p=>p.pair_id),prefill:{...groupPrefills.get(g.group_id)},current:groupCurrent(g.group_id),changed_fields:fields.filter(f=>groupCurrent(g.group_id)[f]!==groupPrefills.get(g.group_id)[f]),user_revision:{...groupEdits[g.group_id]}}))}}

draw();
</script></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    def read(name):
        return json.loads((OUT / name).read_text(encoding='utf-8-sig'))
    audit = assemble(read('user_review_20260912_v3.json'), inventory(ROOT),
                     [read(f'same_room_pairs_{x}_20260912.json') for x in 'abcd'])
    (OUT / 'same_room_pair_audit_20260912.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    resume = json.loads(args.resume.read_text(encoding='utf-8-sig')) if args.resume else None
    if args.resume:
        (OUT / 'user_pair_review_resume_v1.json').write_bytes(args.resume.read_bytes())
    (OUT / '同房研究_整组复核_v3.html').write_text(render(audit, resume), encoding='utf-8')
    print(json.dumps(audit['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
