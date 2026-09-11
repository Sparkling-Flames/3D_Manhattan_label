"""Merge the visual review ledger; render a separate, editable review page."""
import json
from collections import Counter
from pathlib import Path

from tools.thesis_main.analysis.build_scene_image_exploration import OUT

TYPES = ['卧室', '卫浴', '起居与休闲', '厨房与用餐', '通行与连接', '工作与学习',
         '储藏与家务辅助', '特殊用途', '开放复合空间', '无法判断']
BOUNDARIES = ['交界候选', '近交界暂不归入', '暂不归入', '无法判断']


def assemble(manifest, parts, crosses, discussions):
    if manifest['schema'] != 'scene_open_layout_manifest_v3':
        raise ValueError('Unexpected manifest schema')
    source = manifest['source_user']
    original = {r['image_id']: r for r in source['rows']}
    idx = {r['image_id']: r for r in manifest['rows']}
    if len(original) != len(source['rows']) or len(idx) != len(manifest['rows']) or set(original) != set(idx):
        raise ValueError('Duplicate or missing source IDs')
    if any(r['source_user'] != original[i] or (r['building'], r['split']) !=
           (original[i]['building'], original[i]['split']) for i, r in idx.items()):
        raise ValueError('Source metadata changed')
    carry = {i for i, r in idx.items() if r['review_mode'] == 'carry_discussion'}
    if set(discussions) != carry:
        raise ValueError('Discussion coverage mismatch')
    reviews, reviewers = {}, {}
    for part in parts:
        if part['schema'] != 'scene_open_layout_part_v3':
            raise ValueError('Unexpected review schema')
        for r in part['rows']:
            i = r['image_id']
            if i not in idx or i in reviews or i in carry:
                raise ValueError('Unknown, duplicate or carried review')
            m = idx[i]
            if any(r[k] != m[k] for k in ('building', 'number', 'review_mode')):
                raise ValueError('Review metadata mismatch')
            if r['view_basis'] not in ('individual_original', 'large_panel_recheck') or (
                    m['review_mode'] == 'new_original' and r['view_basis'] != 'individual_original'):
                raise ValueError('Invalid visual coverage claim')
            if r['coarse_type'] not in TYPES or r['boundary'] not in BOUNDARIES or r['room_action'] not in (
                    '保留原组', '新增候选', '建议拆分', '待定') or type(r['needs_discussion']) is not bool:
                raise ValueError('Invalid category')
            for key in ('focus', 'boundary_reason', 'room_note', 'ambiguity_note', 'comment_interpretation', 'reason'):
                if not isinstance(r[key], str) or not r[key].strip():
                    raise ValueError('Missing per-image evidence: ' + key)
            if not isinstance(r['functions'], list) or not all(isinstance(v, str) for v in r['functions']):
                raise ValueError('Invalid functions')
            numbers = {x['number'] for x in idx.values() if x['building'] == m['building']}
            related = r['related_numbers']
            if not isinstance(related, list) or any(type(n) is not int or n == m['number'] or n not in numbers for n in related) or len(set(related)) != len(related):
                raise ValueError('Invalid related image numbers')
            reviews[i], reviewers[i] = r, part['reviewer']
    if set(reviews) != set(idx) - carry:
        raise ValueError('Incomplete non-carried review coverage')
    cross_by_id = {}
    for cross in crosses:
        if cross['schema'] != 'scene_open_layout_cross_v3':
            raise ValueError('Unexpected cross-review schema')
        for r in cross['rows']:
            i = r['image_id']
            if i not in reviews or r['verdict'] not in ('支持', '部分支持', '证据不足'):
                raise ValueError('Invalid cross review')
            viewed = r['viewed_image_ids']
            if i not in viewed or not set(viewed) <= set(idx) - carry or r['reviewer'] == reviewers[i]:
                raise ValueError('Invalid independent visual evidence')
            if not isinstance(r['reason'], str) or not r['reason'] or not isinstance(r['suggested_changes'], dict):
                raise ValueError('Missing cross-review evidence')
            related = r['suggested_changes'].get('related_numbers', [])
            numbers = {x['number'] for x in idx.values() if x['building'] == idx[i]['building']}
            if not isinstance(related, list) or any(type(n) is not int or n == idx[i]['number'] or n not in numbers for n in related):
                raise ValueError('Invalid cross-review related numbers')
            if any(x['reviewer'] == r['reviewer'] for x in cross_by_id.get(i, [])):
                raise ValueError('Duplicate cross review')
            cross_by_id.setdefault(i, []).append(r)
    if any(r['needs_discussion'] and i not in cross_by_id for i, r in reviews.items()):
        raise ValueError('Unfinished independent cross checks')
    rows = [{**r, 'review': reviews.get(i), 'reviewer': reviewers.get(i),
             'needs_attention': bool(reviews.get(i, {}).get('needs_discussion') or
                                     any(x['verdict'] != '支持' for x in cross_by_id.get(i, []))),
             'cross_reviews': cross_by_id.get(i, []), 'discussion': discussions.get(i)} for i, r in idx.items()]
    return dict(schema='scene_open_layout_audit_v3', source_user=source, rows=rows,
                summary=dict(total=len(rows), reviewed=len(reviews), carried=len(carry),
                             modes=dict(Counter(r['review_mode'] for r in rows)),
                             views=dict(Counter(r['view_basis'] for r in reviews.values())),
                             issues=sum(r['needs_attention'] for r in rows),
                             cross_checked=len(cross_by_id),
                             cross_disagreements=sum(any(x['verdict'] != '支持' for x in rr) for rr in cross_by_id.values())))


def render(audit):
    data = json.dumps(audit, ensure_ascii=False).replace('<', '\\u003c')
    return PAGE.replace('__AUDIT_DATA__', data).replace('__TYPES__', json.dumps(TYPES, ensure_ascii=False)).replace('__BOUNDARIES__', json.dumps(BOUNDARIES, ensure_ascii=False))


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>室内空间复核：整体布局、同房与交界</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef2f5;color:#223543;font:16px/1.65 "Microsoft YaHei",sans-serif}main{max-width:1420px;padding:20px;margin:auto}header,article{background:white;border-radius:10px;padding:20px;margin-bottom:20px}h1{font-size:26px;margin:0}h2{font-size:21px;color:#19577c}h3{margin:10px 0}p{margin:8px 0}nav{position:sticky;top:0;background:#e0edf4;padding:12px;z-index:3;border-bottom:1px solid #abc}button,input,select,textarea{font:inherit;padding:6px;border:1px solid #8fa8b8;border-radius:4px;max-width:100%}button{cursor:pointer;background:white}button:hover{background:#d7f0ec}label{display:inline-block;margin:3px}img{width:100%;height:auto;aspect-ratio:2/1;display:block}figure{margin:14px 0 24px;border-top:2px solid #cedde6}figcaption{padding:10px;background:#f1f7fa}.evidence{padding:10px;border-left:4px solid #527f99;background:#f4f8fa}.cross{border-left-color:#b98324;background:#fff8e9}fieldset{border:2px solid #4b8a83;background:#eff9f6;padding:12px;margin-top:10px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}fieldset label{display:flex;flex-direction:column}legend{font-weight:bold}.wide{grid-column:1/-1}small{overflow-wrap:anywhere;color:#526877}.tag{display:inline-block;padding:2px 7px;background:#e7f0f7;border-radius:5px;margin:2px}.warn{color:#8b4907}.keep{color:#496d60}dialog{width:min(1450px,98vw);max-height:94vh;overflow:auto;border:1px solid #abc;border-radius:8px}dialog::backdrop{background:#001c3ba8}.dialogbar{position:sticky;top:-1px;background:white;padding:10px;z-index:2}[hidden]{display:none!important}#save{display:block;font-size:14px}details{margin:9px 0}pre{white-space:pre-wrap;font:inherit}a{color:#146f9c}@media(max-width:700px){fieldset{grid-template-columns:1fr}main{padding:8px}nav{position:static}header,article{padding:12px}}
[data-field][data-changed="false"],.initial-key{background:#e7f1ff;border-color:#6895c8;color:#183b60}[data-field][data-changed="true"],.changed-key{background:#fff0d6;border-color:#c78220;color:#633e0b}[data-field-state]{font-size:12px}fieldset input,fieldset select,fieldset textarea{width:100%}
</style><main><header><h1>室内空间复核：整体布局、同房与交界</h1>
<p id="summary"></p><p><b>本页为AI初步建议，最终由你分类。</b>厨房、餐厅、起居可属于一个连续开放空间；同房身份、整体粗类、主要呈现区域、交界条件分别记录。看见另一房间或觉得难标，不自动算交界。精确相机中心未用坐标验证。</p>
<p><b>怎么填：</b>主审判断已预填，检查无误就保持原样，只修改有异议的地方。<span class="tag initial-key">蓝色：维持初始值</span><span class="tag changed-key">橙色：已修改</span>改回初始值会恢复蓝色。你之前保存或导入的填写优先保留。交叉意见仍在上方并列，未自动代替主审。</p>
<p><b>本轮状态可选：</b>仅由你手动修改，改分类、评论等不会重设状态。未单独标记不妨碍导出当前分类；颜色只表示是否改值，不声称未改项已经逐张审核。已讨论图仅预填讨论摘要，不从旧选项推翻近期决定。</p>
<p>每页15组，按原房号组织只是方便对照，<b>不代表原组已确认</b>。同楼关联图可点开上下对比。已讨论的38图单独沿用记录，不要求重复作答。修改自动保存在当前浏览器，结束前请导出完整JSON；可以导入本页先前导出的JSON继续。</p></header>
<nav><label>楼栋 <select id="building"><option value="">全部</option></select></label>
<label>范围 <select id="scope"><option value="issues">本轮需确认</option><option value="cross">复核意见不一致</option><option value="open">开放复合空间建议</option><option value="boundary">交界候选建议</option><option value="all">全部648图</option><option value="carry">已讨论沿用</option></select></label>
<label>定位 <input id="search" placeholder="楼名 / 图号 / 关键词" size="20"></label>
<button id="prev">上一页</button> <span id="count"></span> <button id="next">下一页</button>
<button id="export">导出完整648图复核</button> <label>导入已导出JSON <input type="file" id="import" accept=".json" style="width:150px"></label><span id="save" role="status"></span></nav>
<section id="cards"></section></main><dialog id="compare"><div class="dialogbar"><button id="close">关闭对比</button></div><div id="comparison"></div></dialog>
<script id="audit" type="application/json">__AUDIT_DATA__</script>
<script>
const audit=JSON.parse(document.getElementById('audit').textContent),rows=audit.rows,byId=new Map(rows.map(r=>[r.image_id,r]));
const types=__TYPES__,boundaries=__BOUNDARIES__,fields=['coarse_type','functions','focus','boundary','room','note','status'];
const key='scene-open-layout-v3:'+audit.source_user.saved_at,save=document.getElementById('save');let edits={},page=0;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label=r=>r.building+' · '+String(r.number).padStart(2,'0');
const prefills=new Map(rows.map(r=>{const v=r.review;return [r.image_id,{coarse_type:v?.coarse_type||'',functions:v?.functions.join('、')||'',focus:v?.focus||'',boundary:v?.boundary||'',room:v?v.room_action+'；'+v.room_note:r.discussion?.summary||'',note:'',status:''}]}));
const currentValues=id=>({...prefills.get(id),...edits[id]});
const changedFields=id=>fields.filter(f=>currentValues(id)[f]!==prefills.get(id)[f]);
function validateEdits(value){if(!value||Array.isArray(value)||typeof value!=='object')throw Error('填写记录必须是对象');for(const [id,e] of Object.entries(value)){if(!byId.has(id)||!e||Array.isArray(e)||typeof e!=='object')throw Error('未知图号或格式错误');for(const [k,v] of Object.entries(e))if(!fields.includes(k)||typeof v!=='string')throw Error('未知字段或非文本值');if(e.status&&!['待我确认','已确认','仍需讨论'].includes(e.status))throw Error('未知复核状态')}return value}
try{edits=validateEdits(JSON.parse(localStorage.getItem(key)||'{}'));save.textContent='已读取当前浏览器记录；完成后请导出JSON。'}catch(e){save.textContent='未能读取自动保存：'+e.message+'。可导入JSON恢复。'}
function persist(){try{localStorage.setItem(key,JSON.stringify(edits));save.textContent='已自动保存；本轮已确认 '+Object.values(edits).filter(x=>x.status==='已确认').length+' 图。请导出JSON备份。'}catch(e){save.textContent='自动保存失败，修改仍在本页内存中，请立即导出JSON。'}}
const building=document.getElementById('building'),scope=document.getElementById('scope'),search=document.getElementById('search');
for(const b of [...new Set(rows.map(r=>r.building))])building.insertAdjacentHTML('beforeend',`<option>${esc(b)}</option>`);
const s=audit.summary;document.getElementById('summary').textContent=`共 ${s.total} 图：本轮重新查看 ${s.reviewed} 图，沿用近期讨论 ${s.carried} 图。${s.issues} 图含需确认事项；${s.cross_checked} 图有独立交叉复核，其中 ${s.cross_disagreements} 图未完全一致。主审建议与交叉意见并列保留。`;
function control(name,title,options){return `<label>${title}`+(options?`<select data-field="${name}"><option value="">${name==='status'?'未单独标记（可保持）':'未填写'}</option>${options.map(x=>`<option>${esc(x)}</option>`).join('')}</select>`:name==='note'?'<textarea data-field="note" rows="3" placeholder="你的判断或保留疑问；评论会逐条读取"></textarea>':`<input data-field="${name}">`)+'<small data-field-state></small></label>'}
function figure(r){const v=r.review,u=r.source_user;const src='../../'+r.path;
 let evidence=v?`<div class="evidence"><p><b>主审建议：</b>${esc(v.coarse_type)} ｜ 功能：${esc(v.functions.join('、'))} ｜ ${esc(v.focus)}</p><p><b>交界：</b>${esc(v.boundary)}。${esc(v.boundary_reason)}</p><p><b>同房：</b>${esc(v.room_action)}。${esc(v.room_note)}</p><p><b>依据：</b>${esc(v.reason)}</p><p><b>歧义线索：</b>${esc(v.ambiguity_note)}</p><p><b>评论解读：</b>${esc(v.comment_interpretation)}</p><small>${esc(v.review_mode==='new_original'?'新增原图逐张目视':'既往已看图按新标准复看')} · ${esc(v.view_basis==='individual_original'?'本轮单独查看原图':'本轮大图板重新目视')}</small></div>`:`<div class="evidence keep"><b>沿用已讨论决定，不重新裁决：</b><p>${esc(r.discussion.summary)}</p><details><summary>查看讨论原记录</summary><pre>${esc(JSON.stringify(r.discussion,null,2))}</pre></details></div>`;
 const titles={coarse_type:'整体粗类',functions:'功能组合',focus:'主要呈现区域',boundary:'交界条件',boundary_reason:'交界依据',room_action:'同房处理',room_note:'同房依据',related_numbers:'楼内关联号'};
 for(const c of r.cross_reviews)evidence+=`<div class="evidence cross"><b>独立交叉复核：${esc(c.verdict)}</b><p>${esc(c.reason)}</p>${Object.entries(c.suggested_changes).map(([k,val])=>`<p>${esc(titles[k]||k)}：${esc(Array.isArray(val)?val.join('、'):val)}</p>`).join('')}</div>`;
 let nums=[...new Set([...(v?.related_numbers||[]),...r.cross_reviews.flatMap(c=>c.suggested_changes.related_numbers||[])])];
 let related=nums.map(n=>rows.find(x=>x.building===r.building&&x.number===n)).filter(Boolean);
 const comparisons=(related.length?'<p>关联对照（关系见上文，不自动合并）：'+related.map(o=>`<button data-pair="${esc(o.image_id)}" data-from="${esc(r.image_id)}">与 ${String(o.number).padStart(2,'0')} 对比</button>`).join(' ')+'</p>':'')+`<label>也可另选同楼图片对比 <select data-compare-from="${esc(r.image_id)}"><option value="">选择楼内图号</option>${rows.filter(o=>o.building===r.building&&o.image_id!==r.image_id).map(o=>`<option value="${esc(o.image_id)}">${String(o.number).padStart(2,'0')} · 原${esc(o.source_user.user_room||'未分组')} · ${esc(o.review?.focus||'沿用讨论')}</option>`).join('')}</select></label>`;
 return `<figure id="im-${esc(r.image_id)}"><figcaption><h3>${esc(label(r))} ${r.needs_attention?'<span class="tag warn">需确认</span>':''}${!v?'<span class="tag keep">沿用讨论</span>':''}</h3><p>原填写：房间 ${esc(u.user_room||'未填')} ｜ ${esc(u.user_type)} ｜ 门洞 ${esc(u.user_doorway||'未填')}</p><p><b>原评论：</b>${esc(u.user_note||'无')}</p></figcaption><a href="${esc(src)}" target="_blank" rel="noopener"><img loading="lazy" src="${esc(src)}" alt="${esc(label(r))}"></a><small>${esc(r.image_id)}</small>${evidence}${comparisons}<fieldset data-image="${esc(r.image_id)}"><legend>你的本轮判断${!v?'（已有讨论，无需重复填写）':''}</legend>${control('coarse_type','整体粗分类',types)}${control('functions','功能组合（可多个，如厨房、餐饮）')}${control('focus','主要呈现区域（如起居为主，厨房次要）')}${control('boundary','是否处于两个区域交接位置',boundaries)}${control('room','同房判断（如与05同房／原r2拆分／待定）')}${control('status','本轮状态',['待我确认','已确认','仍需讨论'])}<div class="wide">${control('note','我的评论')}</div>${v?`<button type="button" data-adopt="${esc(r.image_id)}">恢复主审预填（保留状态和评论）</button>`:''}</fieldset></figure>`}
function fill(id,skip){for(const box of document.querySelectorAll('fieldset[data-image]')){const rowId=box.dataset.image;if(id&&rowId!==id)continue;const e=currentValues(rowId),initial=prefills.get(rowId);for(const f of box.querySelectorAll('[data-field]')){const name=f.dataset.field,changed=e[name]!==initial[name];if(f!==skip)f.value=e[name];f.dataset.changed=String(changed);f.nextElementSibling.textContent=changed?'已修改':'维持初始值';f.title='初始值：'+(initial[name]||'（空）')}}}
function selected(){const q=search.value.trim().toLowerCase();return rows.filter(r=>(!building.value||r.building===building.value)&&(scope.value==='all'||scope.value==='carry'&&!r.review||scope.value==='issues'&&r.needs_attention||scope.value==='cross'&&r.cross_reviews.some(c=>c.verdict!=='支持')||scope.value==='open'&&r.review?.coarse_type==='开放复合空间'||scope.value==='boundary'&&(r.review?.boundary==='交界候选'||r.cross_reviews.some(c=>c.suggested_changes.boundary==='交界候选')))&&(!q||/^\d+$/.test(q)&&r.number===Number(q)||!/^\d+$/.test(q)&&JSON.stringify(r).toLowerCase().includes(q)))}
function draw(){const groups=new Map();for(const r of selected()){const k=r.building+' / 原 '+(r.source_user.user_room||'未分组 '+r.number);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r)}const entries=[...groups];const pages=Math.max(1,Math.ceil(entries.length/15));page=Math.min(page,pages-1);document.getElementById('count').textContent=`${page+1}/${pages} 页 · ${entries.length} 组 / ${selected().length} 图`;document.getElementById('prev').disabled=!page;document.getElementById('next').disabled=page>=pages-1;document.getElementById('cards').innerHTML=entries.slice(page*15,page*15+15).map(([k,rr])=>`<article><h2>${esc(k)}</h2>${rr.map(figure).join('')}</article>`).join('')||'<article>当前筛选无图片。</article>';fill()}
for(const el of [building,scope,search])el.addEventListener('input',()=>{page=0;draw()});
document.getElementById('prev').onclick=()=>{page--;draw();window.scrollTo(0,0)};document.getElementById('next').onclick=()=>{page++;draw();window.scrollTo(0,0)};
document.addEventListener('input',e=>{const f=e.target.dataset.field,box=e.target.closest('fieldset[data-image]');if(!f||!box)return;const id=box.dataset.image;edits[id]={...edits[id],[f]:e.target.value};fill(id,e.target);persist()});
function compare(from,to){document.getElementById('comparison').innerHTML=[byId.get(from),byId.get(to)].map(figure).join('');fill();const d=document.getElementById('compare');if(!d.open)d.showModal();d.scrollTop=0}
document.addEventListener('change',e=>{if(e.target.dataset.compareFrom&&e.target.value)compare(e.target.dataset.compareFrom,e.target.value)});
document.addEventListener('click',e=>{const pair=e.target.closest('[data-pair]'),adopt=e.target.closest('[data-adopt]');if(pair)compare(pair.dataset.from,pair.dataset.pair);if(adopt){const id=adopt.dataset.adopt;edits[id]={...edits[id]};for(const f of ['coarse_type','functions','focus','boundary','room'])edits[id][f]=prefills.get(id)[f];fill(id);persist()}});
document.getElementById('close').onclick=()=>document.getElementById('compare').close();
function makeExport(){return {schema:'scene_open_layout_user_review_v3',form_version:2,saved_at:new Date().toISOString(),source_saved_at:audit.source_user.saved_at,source_user:audit.source_user,rows:rows.map(r=>({...r,prefill:prefills.get(r.image_id),current_classification:currentValues(r.image_id),changed_fields:changedFields(r.image_id),user_revision:edits[r.image_id]||{}}))}}
document.getElementById('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(makeExport(),null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='室内空间_本轮完整复核_v3.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
function readImport(d){if(d.schema!=='scene_open_layout_user_review_v3'||d.source_saved_at!==audit.source_user.saved_at||JSON.stringify(d.source_user)!==JSON.stringify(audit.source_user)||!Array.isArray(d.rows)||d.rows.length!==rows.length)throw Error('不是本轮完整导出文件');const next={},ids=new Set();for(const r of d.rows){if(!byId.has(r.image_id)||ids.has(r.image_id))throw Error('重复或未知图片');ids.add(r.image_id);next[r.image_id]=r.user_revision}return validateEdits(next)}
document.getElementById('import').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const next=readImport(JSON.parse(await f.text()));if(Object.keys(edits).length&&!confirm('用导入文件替换当前浏览器的本轮填写？未导出的修改会被替换。'))return;edits=next;fill();persist()}catch(err){save.textContent='导入失败，当前填写未改变：'+err.message}finally{e.target.value=''}};
draw();
</script></html>'''


def main():
    def read(name):
        return json.loads((OUT / name).read_text(encoding='utf-8'))
    manifest = read('review_round_manifest_v3.json')
    source = json.loads(Path(manifest['source_user_path']).read_text(encoding='utf-8'))
    if source != manifest['source_user']:
        raise ValueError('Original user source changed since this review manifest')
    audit = assemble(manifest,
                     [read(f'open_layout_review_{owner}_v3.json') for owner in ('a', 'b', 'root')],
                     [read(p.name) for p in sorted(OUT.glob('open_layout_cross_*_v3.json'))],
                     read('open_layout_carried_discussions_v3.json'))
    (OUT / 'open_layout_audit_v3.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / '室内空间_新标准复核_v3.html').write_text(render(audit), encoding='utf-8')
    print(json.dumps(audit['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
