"""开发案例的人工审阅草稿与按需加载评价的方法对照；不回写研究源。"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from .layout_display_projection import compact_paths, region_projection
from .research_artifact_io import ROOT
from .point_route_panel_view_20261005 import project


def photo(image_id, out):
    matches = [ROOT/'data/mp3d_layout'/split/'img'/(image_id+'.png') for split in ('train', 'valid', 'test')]
    matches = [p for p in matches if p.is_file()]
    if len(matches) > 1:
        raise ValueError('multiple_standard_split_photos:'+image_id)
    return os.path.relpath(matches[0], out).replace('\\', '/') if matches else None


def write_page(path, body, script, payload):
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
    path.write_text(SHELL.replace('__BODY__', body).replace('__SCRIPT__', COMMON+script)
                    .replace('__DATA__', encoded), encoding='utf-8')


def build(out: Path):
    out = Path(out)
    panel = json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    if panel['schema'] != 'point_route_panel_v1':
        raise ValueError('unexpected_panel_schema')
    cases = json.loads((out/'review_cases.json').read_text(encoding='utf-8'))
    human_path = out/'human_review.json'
    human_reviews = json.loads(human_path.read_text(encoding='utf-8'))['reviews'] if human_path.exists() else []
    images = {image['image']: image for image in panel['images']}
    review = []
    for case in cases:
        image = images[case['image']]
        records = {str(r['id']): r for r in image['records']}
        # 人工页仅绑定案例指定的原记录；不嵌入方法、参数、候选或评价。
        review.append(dict(case=case, photo=photo(image['image_id'], out),
                           human_reviews=[r for r in human_reviews if r['case_id'] == case['id']],
                           records=[dict(id=records[str(rid)]['id'], worker=records[str(rid)]['worker'],
                                         points=records[str(rid)]['points'], view=project(records[str(rid)]))
                                    for rid in case['record_ids']]))
    display = copy.deepcopy(panel)
    for image in display['images']:
        image['photo'] = photo(image['image_id'], out)
        image['record_views'] = [dict(id=r['id'], worker=r['worker'], points=r['points'], view=project(r))
                                 for r in image['records']]
        if image['lee'].get('region') is not None:
            try:
                image['lee_view'] = dict(bottom_paths=[p for ring in region_projection(image['lee']['region'])
                                                       for p in compact_paths(ring['paths'])])
            except ValueError as exc:
                image['lee_view'] = dict(error=str(exc))
        else:
            image['lee_view'] = dict(error=image['lee']['status'])
        for state in image['states']:
            result = state['result']
            result['baseline_view'] = project(result['candidate'])
            connection = result['connection_review']
            variants = connection['observed_orders'] + ([connection['unanimous']] if connection['unanimous'] else [])
            for variant in variants:
                variant['view'] = project(variant['candidate'])
    write_page(out/'review.html', REVIEW_BODY, REVIEW_JS, review)
    write_page(out/'index.html', COMPARE_BODY, COMPARE_JS, display)
    evaluations = json.loads((out/'evaluations.json').read_text(encoding='utf-8'))
    reference_views = {item['image']: project(item['record']) for item in evaluations['references']}
    (out/'evaluation_projection.json').write_text(
        json.dumps(reference_views, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    return dict(review=out/'review.html', comparison=out/'index.html')


SHELL = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>点对应开发审阅</title><style>
body{font:15px system-ui;background:#f5f6f7;color:#263440;margin:24px}main{max-width:1200px;margin:auto}
button,select,textarea{font:inherit;padding:7px;margin:4px}label{display:inline-block;margin:5px}textarea{display:block;width:95%;height:80px}
svg{width:100%;height:65vh;background:#20252a}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:10px}.notice{background:#fff0cc;padding:12px}
circle{cursor:pointer}.error{color:#b14d20}a{color:#165d88}fieldset{margin:12px 0}h1{font-size:24px}
</style><main>__BODY__</main><script>const DATA=__DATA__;__SCRIPT__</script></html>'''

COMMON = r'''
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg',pretty=v=>JSON.stringify(v,null,2);
function el(tag,attrs={}){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e}
function options(id,rows){$(id).replaceChildren();for(const [value,label] of rows)$(id).add(new Option(label,value))}
function paths(svg,view,color,width=2,bottom=false){if(!view||view.error)return;for(const key of bottom?['bottom_paths']:['top_paths','bottom_paths','vertical_paths'])for(const d of view[key]||[])svg.append(el('path',{d,fill:'none',stroke:color,'stroke-width':width}))}
function background(svg,photo,show=true){if(photo&&show)svg.append(el('image',{href:photo,width:1024,height:512}));}
function dot(svg,point,color,label,show){const c=el('circle',{cx:point[0],cy:point[1],r:4,fill:color,stroke:'#222','stroke-width':1,tabindex:0,role:'button','aria-label':label});c.onclick=show;c.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}};svg.append(c);}
const DRAFT_KEY='hohonet_point_route_review_20261006_v1';
function drafts(){return JSON.parse(localStorage.getItem(DRAFT_KEY)||'{}')}
function saveDrafts(value){localStorage.setItem(DRAFT_KEY,JSON.stringify(value))}
'''

REVIEW_BODY = '''<h1>人工核验：开发案例</h1><p class="notice">这是已用于开发的案例，不称盲测。答案默认未回答；浏览与草稿不表示人工已确认。可直接在聊天给出案例答案。草稿只保存在本浏览器，不自动回写项目源。</p>
<label>案例 <select id="case"></select></label><label><input id="photo" type="checkbox" checked>原图</label><label><input id="rings" type="checkbox" checked>指定源环</label><label><input id="points" type="checkbox" checked>原点</label>
<button id="mode">切换全图</button><button id="comparison">打开方法对照</button><button id="export">导出审阅草稿JSON</button>
<h2 id="title"></h2><p id="question"></p><p id="recorded-review"></p><fieldset id="records"><legend>源记录显示</legend></fieldset>
<svg id="canvas" viewBox="0 0 1024 512" role="img" aria-label="指定原记录的真实投影与点"></svg><p id="error" class="error"></p>
<p>聊天判断另列；表单用于补充/修订，不自动替用户选择答案。</p><fieldset id="answers"><legend>问题答案（默认未回答）</legend></fieldset><label>备注<textarea id="note"></textarea></label><p id="saved"></p>
'''

REVIEW_JS = r'''
let selected=0,viewMode='local';const palette=['#ffd65e','#42e8d5','#eaa4ff','#a2d3ff'];
function current(){return DATA[selected]}
function persist(){const item=current(),all=drafts(),old=all[item.case.id]||{};all[item.case.id]={case_id:item.case.id,image:item.case.image,source_ids:item.case.record_ids,answer:$('answers').querySelector('input:checked')?.value??null,note:$('note').value,view_mode:viewMode,opened_comparison:old.opened_comparison===true};saveDrafts(all);$('saved').textContent='本地草稿已保存；未写回项目源。'}
function render(){const item=current(),c=item.case,svg=$('canvas'),errors=[];svg.replaceChildren();svg.setAttribute('viewBox',viewMode==='local'?c.view_box.join(' '):'0 0 1024 512');background(svg,item.photo,$('photo').checked);if(!item.photo)errors.push('无原图');
 item.records.forEach((r,i)=>{if(!$('records').querySelector(`input[data-index="${i}"]`).checked)return;const color=palette[i%palette.length];if($('rings').checked){paths(svg,r.view,color,1.5);if(r.view.error)errors.push(`${r.id}投影不可用：${r.view.error}`)}
 if($('points').checked)(r.points||[]).forEach((p,j)=>dot(svg,p,color,`${r.id}原点${j+1}`,()=>{}));
 for(const h of c.highlights.filter(h=>String(h.id)===String(r.id))){const offset=h.label_offset||[8,-8-i*5];for(const q of (r.points||[]).slice(2*h.pair_index,2*h.pair_index+2)){const x=q[0]+offset[0],y=q[1]+offset[1];svg.append(el('path',{d:`M${q[0]},${q[1]}L${x},${y}`,stroke:color,'stroke-width':.6,fill:'none'}));const text=el('text',{x,y,fill:color,'font-size':viewMode==='local'?5:12,stroke:'#222','stroke-width':.6,'paint-order':'stroke'});text.textContent=h.label;svg.append(text);svg.append(el('circle',{cx:q[0],cy:q[1],r:7,fill:'none',stroke:color,'stroke-width':2}))}}});
 $('mode').textContent=viewMode==='local'?'切换全图':'切换局部';$('error').textContent=errors.join('；');}
function changeCase(){selected=Number($('case').value);const item=current(),c=item.case,d=drafts()[c.id]||{};viewMode=d.view_mode||'local';$('title').textContent=c.title+' · '+c.id;$('question').textContent=c.question;$('recorded-review').textContent=(item.human_reviews||[]).map(r=>'已收到的聊天反馈：'+r.verbatim+(r.bottom_verbatim?'；下端原话：'+r.bottom_verbatim:'')+(r.correction_quote?'（已澄清指2t7）':'')).join('；');
 $('records').replaceChildren();item.records.forEach((r,i)=>{const l=document.createElement('label'),box=document.createElement('input');l.style.color=palette[i%palette.length];l.style.background='#20252a';l.style.padding='5px';box.type='checkbox';box.checked=true;box.dataset.index=i;box.onchange=render;l.append(box,document.createTextNode(`${String.fromCharCode(65+i)} · ${r.worker} / ${r.id}`));$('records').append(l)});
 $('answers').replaceChildren();const legend=document.createElement('legend');legend.textContent='问题答案（默认未回答）';$('answers').append(legend);for(const option of c.options){const l=document.createElement('label'),radio=document.createElement('input');radio.type='radio';radio.name='answer';radio.value=option;radio.checked=d.answer===option;radio.onchange=persist;l.append(radio,document.createTextNode(option));$('answers').append(l)}
 const clear=document.createElement('button');clear.textContent='清空答案';clear.onclick=()=>{$('answers').querySelectorAll('input').forEach(x=>x.checked=false);persist()};$('answers').append(clear);$('note').value=d.note||'';$('saved').textContent=d.opened_comparison?'草稿记录：已在本页打开过方法对照。':'';render();}
options('case',DATA.map((item,i)=>[i,item.case.id+' · '+item.case.title]));$('case').value=String(Math.max(0,DATA.findIndex(item=>item.case.id===location.hash.slice(1))));$('case').onchange=changeCase;
for(const id of ['photo','rings','points'])$(id).onchange=render;$('note').oninput=persist;$('mode').onclick=()=>{viewMode=viewMode==='local'?'full':'local';persist();render()};
$('comparison').onclick=()=>{persist();const all=drafts();all[current().case.id].opened_comparison=true;saveDrafts(all);window.open('index.html','_blank');$('saved').textContent='已记录本页点击打开方法对照。'};
$('export').onclick=()=>{persist();const all=drafts(),rows=DATA.map(item=>all[item.case.id]||{case_id:item.case.id,image:item.case.image,source_ids:item.case.record_ids,answer:null,note:'',view_mode:'local',opened_comparison:false});const url=URL.createObjectURL(new Blob([pretty({schema:DRAFT_KEY,status:'review_draft_not_confirmation',cases:rows})],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='point_route_review_draft_20261006.json';a.click();URL.revokeObjectURL(url)};changeCase();
'''

COMPARE_BODY = '''<h1>方法对照：开发案例</h1><p class="notice">所有阈值探索未校准；5°仅演示。默认全员一致原序（若有），否则只显示生成节点；不自动选择高支持备选。节点、配对支持和连接状态分别保留，不能称实体墙角已确认。</p>
<a href="review.html">返回人工开发核验</a><label>图片<select id="image"></select></label><label>阈值<select id="threshold"></select></label><label>路线<select id="route"></select></label><label>连接显示<select id="connection"></select></label>
<label><input id="originals" type="checkbox" checked>原记录投影</label><label><input id="lee" type="checkbox">Lee仅底边</label><button id="metrics">点击加载GT与评价</button><label><input id="gt" type="checkbox" disabled>显示GT</label><span id="viewed"></span>
<svg id="canvas" viewBox="0 0 1024 512" role="img" aria-label="路线节点及显式连接对照"></svg><p id="error" class="error"></p><p id="status"></p><pre id="source">点击节点查看来源。</pre>
<details><summary>当前完整连接与部分对应数据</summary><pre id="state-data"></pre></details><div id="evaluation" hidden><h2>原x排序基线的参考评价</h2><p id="evaluation-scope"></p><pre id="evaluation-data"></pre><h3>Lee自身底面参考评价</h3><pre id="lee-evaluation-data"></pre></div>
<button id="audit-load">显示人工对应诊断</button><section id="audit" hidden><h2>当前设置的人工对应诊断</h2><p>所列三点局部相容不等于多数支持或物理正确。合并现有整组的障碍不表示所有其他分区不可能。uNb案例下端同处是用户“应该”的判断，上端指向不同目标；下端同组本身不标为错误。</p><p id="audit-status"></p><div style="overflow:auto"><table><thead><tr><th>case / 匹配度量</th><th>三点局部门限相容</th><th>三点在原全员结果同组</th><th>现有组支持及达票</th><th>合并现有整组的障碍</th><th>不同上端目标同组记录</th></tr></thead><tbody id="audit-rows"></tbody></table></div><details><summary>当前诊断完整数据与冲突成员</summary><pre id="audit-data"></pre></details></section>
'''

COMPARE_JS = r'''
const images=DATA.images,labels={paired:'上下绑定点对',bottom_anchor:'下端锚定',top_anchor:'上端锚定',split_unique:'上下分开＋原配对关联'};let evaluations=null,gtViews=null,metricsVisible=false,viewed=false;
let audit=null;
function renderAudit(){if(!audit)return;const image=images[Number($('image').value)],s=state(),rows=audit.rows.filter(r=>r.image===image.image&&r.route===s.route&&Number(r.threshold_deg)===Number(s.threshold_deg));$('audit').hidden=false;$('audit-status').textContent=rows.length?`当前设置有${rows.length}条审核诊断。`:'当前图片／路线／阈值未审核；不能视为零错误。';$('audit-rows').replaceChildren();for(const r of rows){const p=r.probe,tr=document.createElement('tr');for(const value of [`${r.case_id} / ${r.metric} (${r.side})`,String(p.local_group_feasible),String(p.same_group),p.target_groups.map(g=>`${g.feature_id}: ${g.support}人，${g.selected?'达票':'未达票'}`).join('；'),`同人冲突${p.same_worker_merge_conflicts.length}个；整组直径${p.whole_group_merge_diameter_deg.toFixed(6)}°；${p.whole_group_merge_exceeds_threshold?'超过':'未超过'}当前门限`,r.different_upper_targets_in_same_group?.length?pretty(r.different_upper_targets_in_same_group):'无记录（不表示已确认无误）']){const td=document.createElement('td');td.textContent=value;td.style.border='1px solid #ccc';td.style.padding='6px';tr.append(td)}$('audit-rows').append(tr)}$('audit-data').textContent=pretty(rows)}
function state(){return images[Number($('image').value)].states.find(s=>Number(s.threshold_deg)===Number($('threshold').value)&&s.route===$('route').value)}
function chooseConnections(){const r=state().result,c=r.connection_review;const choices=[['nodes','生成点层（不成环）'],['baseline','显式x排序探索基线']];if(c.unanimous)choices.push(['unanimous','全员一致原序']);c.observed_orders.forEach((v,i)=>choices.push(['observed:'+i,`观测原序备选 ${i+1} · 支持${v.support} · 来源${v.source_ids.join('、')}`]));options('connection',choices);$('connection').value=c.unanimous?'unanimous':'nodes';render();}
function showPair(svg,pair,color){const center=pair.center;if(!center)return;svg.append(el('path',{d:`M${center[0][0]},${center[0][1]}L${center[1][0]},${center[1][1]}`,stroke:color,'stroke-dasharray':'4 4',fill:'none','stroke-width':1.5}));center.forEach((p,i)=>dot(svg,p,color,pair.feature_id+' '+(i?'bottom':'top'),()=>$('source').textContent=pretty({endpoint:i?'bottom':'top',...pair})));}
function render(){renderAudit();const image=images[Number($('image').value)],s=state(),r=s.result,c=r.candidate,svg=$('canvas'),errors=[];svg.replaceChildren();background(svg,image.photo);if(!image.photo)errors.push('无原图');if($('originals').checked)for(const record of image.record_views){paths(svg,record.view,'#999',1);if(record.view.error)errors.push(`${record.id}源投影不可用：${record.view.error}`)}
 if($('lee').checked){paths(svg,image.lee_view,'#23e3da',2,true);if(image.lee_view.error)errors.push('Lee投影不可用：'+image.lee_view.error)}
 const choice=$('connection').value,connection=r.connection_review,variant=choice==='unanimous'?connection.unanimous:choice.startsWith('observed:')?connection.observed_orders[Number(choice.split(':')[1])]:null;
 const candidate=variant?.candidate||c,view=variant?.view||r.baseline_view;
 if(choice!=='nodes'){if(view.error)errors.push('所选连接投影不可用：'+view.error);else paths(svg,view,'#ffd658',2.5)}
 const partial=r.partial_correspondences;
 if(partial&&!partial.full_pairing_complete){for(const pair of partial.pairs){if(pair.center)showPair(svg,pair,'#ffe262');else errors.push(`${pair.feature_id}部分对应无可绘中心：${pair.reason||'center_unavailable'}`)}for(const endpoint of partial.unresolved_endpoints){const p=endpoint.center?.[endpoint.side==='top'?0:1];if(p)dot(svg,p,endpoint.side==='top'?'#ef8aff':'#ff835f',endpoint.side+'未决端点',()=>$('source').textContent=pretty(endpoint));else errors.push(`${endpoint.side}/${endpoint.feature_id}未决端点无中心：${endpoint.reason||'center_unavailable'}`)}}
 else if(candidate.points)candidate.points.forEach((p,i)=>{const fid=candidate.feature_ids[Math.floor(i/2)],mapping=(candidate.source_pair_maps||[]).find(g=>g.feature_id===fid)||(r.paired_identities||[]).find(g=>g.feature_id===fid),group=(r.identity_groups||[]).find(g=>g.feature_id===fid);dot(svg,p,'#ffd658',fid+' '+(i%2?'bottom':'top'),()=>$('source').textContent=pretty({endpoint:i%2?'bottom':'top',identity_id:fid,source_mapping:mapping,identity_group:group,method_details:r.method_details,connection_source_ids:variant?.source_ids}))});
 else if(choice==='nodes')for(const group of (r.identity_groups||[]).filter(g=>g.selected)){if(group.center)showPair(svg,group,'#ffd658');else errors.push(`${group.feature_id}生成节点中心不可用：${group.center_status}`)}
 if(evaluations&&metricsVisible&&$('gt').checked){const view=gtViews?.[image.image];if(view){paths(svg,view,'#d89cff',2);if(view.error)errors.push('GT投影不可用：'+view.error)}else errors.push('GT投影未提供')}
 $('status').textContent=`${image.image} · ${image.n}人 · ${s.threshold_deg}°探索未校准${Number(s.threshold_deg)===5?'（仅演示）':''}。完整候选状态：${r.status}；${c.reason||'无计算告警'}。生成完整候选点对：${(c.points||[]).length/2}；保留部分对应：${partial?.pairs.length??0}对；未决端点：${partial?.unresolved_endpoints.length??0}；完整配对：${partial?String(partial.full_pairing_complete):'见完整候选'}。连接显示：${$('connection').selectedOptions[0].textContent}。${connection.reason||''}候选未确认，ok不是人工或物理确认。`;
 if((candidate.points||[]).length<8)$('status').textContent='不足4对：保留原始投票结果，需诊断完整性。 '+$('status').textContent;
 $('error').textContent=errors.join('；');$('state-data').textContent=pretty(r);$('source').textContent='点击生成节点、部分对应或未决端点查看原来源与支持字段。';
 $('evaluation').hidden=!metricsVisible;if(evaluations&&metricsVisible){$('evaluation-scope').textContent=choice==='baseline'?'以下现有数值仅评价原x排序基线；不评价节点层、部分对应或观测原序变体。':'当前显示不是原x排序基线。点方法分数已隐藏；切换“显式x排序探索基线”查看其参考评价。';$('evaluation-data').hidden=choice!=='baseline';$('evaluation-data').textContent=choice==='baseline'?pretty({evaluation_scope:'原x排序基线的参考评价',rows:evaluations.rows.filter(x=>x.image===image.image&&Number(x.threshold_deg)===Number(s.threshold_deg)&&x.route===s.route)}):'';$('lee-evaluation-data').textContent=pretty({evaluation_scope:'Lee自身底面参考评价',rows:evaluations.lee.filter(x=>x.image===image.image)});}}
options('image',images.map((im,i)=>[i,im.image+' · '+im.n+'人']));options('threshold',[...new Set(images.flatMap(im=>im.states.map(s=>s.threshold_deg)))].sort((a,b)=>a-b).map(t=>[t,t+'°（探索未校准'+(Number(t)===5?'；仅演示':'')+'）']));$('threshold').value=String(DATA.plan.display_threshold_deg??1);options('route',Object.entries(labels));
for(const id of ['image','threshold','route'])$(id).onchange=chooseConnections;for(const id of ['connection','originals','lee','gt'])$(id).onchange=render;
$('audit-load').onclick=async()=>{try{if(!audit){const response=await fetch('correspondence_audit.json');if(!response.ok)throw new Error('HTTP '+response.status);audit=await response.json()}renderAudit()}catch(e){$('audit').hidden=false;$('audit-status').textContent='诊断加载失败：'+e.message}};
$('metrics').onclick=async()=>{try{if(!evaluations){$('metrics').disabled=true;const response=await fetch('evaluations.json');if(!response.ok)throw new Error('evaluations HTTP '+response.status);evaluations=await response.json();viewed=true;$('viewed').textContent='已查看评价（隐藏不会清除该标记）';$('gt').disabled=false;const projectionResponse=await fetch('evaluation_projection.json');if(!projectionResponse.ok)throw new Error('GT projection HTTP '+projectionResponse.status);gtViews=await projectionResponse.json()}metricsVisible=!metricsVisible;$('metrics').textContent=metricsVisible?'隐藏GT与评价':'显示已加载GT与评价';render()}catch(e){$('error').textContent='评价加载失败：'+e.message}finally{$('metrics').disabled=false}};chooseConnections();
'''
