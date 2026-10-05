"""读取固定小面板工件，生成探索路线的静态投影展示；不重新融合或评价。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .lee_consensus_demos_20261003 import compact_paths, project_display_record, region_projection
from .lee_tile_stage1_20261002 import ROOT


def project(record):
    if record.get('points') is None or record.get('footprint') is None:
        return dict(error=record.get('reason') or 'points_or_footprint_unavailable')
    try:
        return project_display_record(record)
    except ValueError as exc:
        return dict(error=str(exc))


def build(out: Path):
    out = Path(out)
    data = json.loads((out/'candidates.json').read_text(encoding='utf-8'))
    if data['schema'] != 'point_route_panel_v1':
        raise ValueError('unexpected_panel_schema')
    evaluations = json.loads((out/'evaluations.json').read_text(encoding='utf-8'))
    references = {r['image']: r['record'] for r in evaluations['references']}
    for image in data['images']:
        photos = [ROOT/'data/mp3d_layout'/split/'img'/(image['image_id']+'.png')
                  for split in ('train', 'valid', 'test')]
        photos = [p for p in photos if p.is_file()]
        if len(photos) > 1:
            raise ValueError('multiple_standard_split_photos:'+image['image_id'])
        image['photo'] = os.path.relpath(photos[0], out).replace('\\', '/') if photos else None
        image['record_views'] = [dict(id=r['id'], worker=r['worker'], view=project(r)) for r in image['records']]
        image['reference_view'] = project(references[image['image']])
        region = image['lee'].get('region')
        if region is None:
            image['lee_view'] = dict(error=image['lee']['status'])
        else:
            try:
                image['lee_view'] = dict(bottom_paths=[p for ring in region_projection(region)
                                                       for p in compact_paths(ring['paths'])])
            except ValueError as exc:
                image['lee_view'] = dict(error=str(exc))
        for state in image['states']:
            candidate = state['result']['candidate']
            state['view'] = (dict(error=candidate.get('reason') or 'candidate_unavailable')
                             if candidate['status'] == 'unavailable' else project(candidate))
    payload = json.dumps(dict(panel=data, evaluations=evaluations), ensure_ascii=False, allow_nan=False)
    path = out/'index.html'
    path.write_text(HTML.replace('__DATA__', payload.replace('</', '<\\/')), encoding='utf-8')
    return path


HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>四图点融合路线探索</title>
<style>
body{font:15px system-ui;margin:24px;color:#24313a;background:#f6f7f8}main{max-width:1250px;margin:auto}
select,button{padding:7px;margin:4px}label{display:inline-block;margin:4px}svg{width:100%;background:#222}
.notice{background:#fff0c9;padding:12px;border-left:5px solid #b96700}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:12px}
table{border-collapse:collapse;width:100%;background:white;font-size:12px}td,th{border:1px solid #ccd3d8;padding:6px;text-align:left}
.scroll{overflow:auto}circle{cursor:pointer}h1{font-size:24px}#errors{color:#923b16}small{color:#53616b}
</style><main><h1>四图点融合路线探索</h1>
<p class="notice">所有参数均为探索、未校准；5°仅为演示参数。候选连接尚未确认。点身份与来源支持不等于实体墙角认证。</p>
<label>图片 <select id="image"></select></label><label>探索阈值 <select id="threshold"></select></label>
<label>路线 <select id="route"></select></label><label>人员高亮 <select id="person"></select></label>
<label><input type="checkbox" id="gt">显示GT参考</label>
<p>灰：原人员；白：高亮人员；黄：候选上下投影与点；青：Lee仅底边；紫：GT参考。</p>
<svg id="canvas" viewBox="0 0 1024 512" role="img" aria-label="原全景上的声明几何投影曲线"></svg>
<p id="errors"></p><p id="status"></p><details><summary>当前完整状态与评价原数据</summary><pre id="status-data"></pre></details><h2>点击候选上下点查看身份来源</h2><pre id="source">尚未选择候选点。</pre>
<details><summary>当前路线绑定、anchor及支持定义（原数据）</summary><pre id="details"></pre></details>
<h2>全部参数与路线状态</h2><p>完整保留所有状态。同经度均差为边界纵向绝对差，不表示语义对应；域外项不补造数值。</p>
<div class="scroll"><table><thead><tr><th>图片 / 人数</th><th>θ</th><th>路线</th><th>候选状态</th><th>点对数</th><th>BEV IoU</th><th>上同经度均差 px</th><th>下同经度均差 px</th></tr></thead><tbody id="summary"></tbody></table></div>
<details><summary>全部评价原数据</summary><pre id="evaluation-data"></pre></details>
</main><script>
const DATA=__DATA__,images=DATA.panel.images,$=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
const labels={paired:'上下绑定点对',bottom_anchor:'下端锚定',top_anchor:'上端锚定',split_unique:'上下分开＋唯一原配对关联'};
const pretty=v=>JSON.stringify(v,null,2),thresholdLabel=t=>`${t}°（探索未校准${Number(t)===5?'；仅演示':''}）`;
const fixed=(v,n)=>typeof v==='number'?v.toFixed(n):'—';
const boundaryValue=(b,side)=>b?.status==='ok'?fixed(b[side+'_mean_abs_px'],3):b?.reason==='candidate_unavailable'?'无候选':'域外';
function options(select,rows){select.replaceChildren();for(const [value,label] of rows)select.add(new Option(label,value))}
function element(tag,attrs){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e}
function paths(view,color,width,opacity=1,bottomOnly=false){if(view.error)return;for(const key of bottomOnly?['bottom_paths']:['top_paths','bottom_paths','vertical_paths'])for(const d of view[key]||[])$('canvas').append(element('path',{d,stroke:color,'stroke-width':width,fill:'none',opacity}))}
function source(result,index){const candidate=result.candidate,id=candidate.feature_ids[index];
 const mapping=(candidate.source_pair_maps||[]).find(g=>g.feature_id===id)||(result.paired_identities||[]).find(g=>g.feature_id===id);
 const group=(result.identity_groups||[]).find(g=>g.feature_id===id);
 return {identity_id:id,route:result.route,point_support_count:candidate.point_support_counts?.[index]??null,
 support_interpretation:result.method_details?.support_interpretation??result.pairing_graph?.policy??result.method_details?.center,
 source_mapping:mapping,identity_group:group};}
function render(){const image=images[Number($('image').value)],t=Number($('threshold').value),route=$('route').value;
 const state=image.states.find(s=>Number(s.threshold_deg)===t&&s.route===route),result=state.result,candidate=result.candidate,errors=[];
 $('canvas').replaceChildren();if(image.photo)$('canvas').append(element('image',{href:image.photo,width:1024,height:512}));else errors.push('无原图：标准train/valid/test split均未找到');
 for(const record of image.record_views){if(record.view.error){errors.push(`人员 ${record.worker}/${record.id} 投影不可用：${record.view.error}`);continue}
 paths(record.view,record.id===$('person').value?'white':'#aaa',record.id===$('person').value?2:1,record.id===$('person').value?1:.4)}
 paths(image.lee_view,'#00e3e3',2,1,true);if(image.lee_view.error)errors.push('Lee底边不可用：'+image.lee_view.error);
 if($('gt').checked){paths(image.reference_view,'#cf95ff',2);if(image.reference_view.error)errors.push('GT投影不可用：'+image.reference_view.error)}
 if(state.view.error)errors.push('候选投影不可用：'+state.view.error);else{paths(state.view,'#ffd54a',2.5);
 (candidate.points||[]).forEach((p,i)=>{const dot=element('circle',{cx:p[0],cy:p[1],r:4,fill:i%2?'#ff9f32':'#fff176',stroke:'#222','stroke-width':1,tabindex:0,role:'button','aria-label':`候选${i%2?'下':'上'}端点 ${Math.floor(i/2)+1}`});
 const show=()=>$('source').textContent=pretty({endpoint:i%2?'bottom':'top',...source(result,Math.floor(i/2))});dot.onclick=show;dot.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}};$('canvas').append(dot)})}
 const evaluation=DATA.evaluations.rows.find(r=>r.image===image.image&&Number(r.threshold_deg)===t&&r.route===route);
 const leeEvaluation=DATA.evaluations.lee.find(r=>r.image===image.image);
 $('errors').textContent=errors.join('；');
 const ring=result.ring_diagnostics,boundary=evaluation?.boundary;
 $('status').textContent=`${image.image}，${image.n}人，${thresholdLabel(t)}，${labels[route]}。计算状态：${result.status}；ok仅表示计算检查通过，候选尚未确认。候选点对数：${(candidate.points||[]).length/2}；直接无支持边：${ring?.unsupported_edge_count??'不可用'}；未过半边：${ring?.below_majority_edge_count??'不可用'}。Lee仅底面IoU：${fixed(leeEvaluation?.bev?.iou,6)}。上／下同经度均差：${boundaryValue(boundary,'top')}／${boundaryValue(boundary,'bottom')} px。${boundary?.status!=='ok'?'上下度量不可用原因：'+pretty(boundary?.domain_failures??boundary?.reason)+ '。':''}`;
 $('status-data').textContent=pretty({image:image.image,n:image.n,threshold_deg:t,route,status:result.status,reason:candidate.reason,ring_confirmed:candidate.ring_confirmed,order_status:candidate.order_status,lee_status:image.lee.status,lee_warnings:image.lee.warnings,evaluation,lee_evaluation:leeEvaluation});
 $('details').textContent=pretty({method_details:result.method_details,center_method:candidate.center_method,minimum_support:result.minimum_support,vote_denominator:result.vote_denominator,pairing_graph:result.pairing_graph,ring_diagnostics:result.ring_diagnostics,correspondence_diagnostics:result.correspondence_diagnostics});
 $('source').textContent='尚未选择候选点。分开路线分别保存top_support、bottom_support、joint_support及对应来源。'}
function changeImage(){const image=images[Number($('image').value)];options($('person'),[['','全部原人员'],...image.records.map(r=>[r.id,`${r.worker} / ${r.id}`])]);render()}
options($('image'),images.map((r,i)=>[i,`${r.image} · ${r.n}人`]));
options($('threshold'),[...new Set(images.flatMap(r=>r.states.map(s=>s.threshold_deg)))].sort((a,b)=>a-b).map(t=>[t,thresholdLabel(t)]));$('threshold').value='1';
options($('route'),Object.entries(labels));
for(const image of images)for(const state of image.states){const result=state.result,e=DATA.evaluations.rows.find(r=>r.image===image.image&&Number(r.threshold_deg)===Number(state.threshold_deg)&&r.route===state.route),tr=document.createElement('tr');
 for(const text of [`${image.image} / ${image.n}`,thresholdLabel(state.threshold_deg),labels[state.route],result.status,(result.candidate.points||[]).length/2,fixed(e?.bev?.iou,6),boundaryValue(e?.boundary,'top'),boundaryValue(e?.boundary,'bottom')]){const td=document.createElement('td');td.textContent=text;tr.append(td)}$('summary').append(tr)}
$('evaluation-data').textContent=pretty(DATA.evaluations);
$('image').onchange=changeImage;for(const id of ['threshold','route','person','gt'])$(id).onchange=render;changeImage();
</script></html>'''
