#!/usr/bin/env python3
"""Rebuild a reader for the recovered full-corpus results; never recompute cluster labels.
39 original images are embedded as reduced JPEG previews. Other 175 images load only on request.
Run with --pixels-zip path/to/key39-original-pixels-20260918.zip; no fonts/weights are embedded.
"""
from pathlib import Path
import json,gzip,io,base64,zipfile,argparse
import numpy as np,pandas as pd
from PIL import Image
import legacy_reproduction as legacy

TEMPLATE=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>全量标注分簇与模型对照 · 恢复交付版</title>
<style>
:root{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;color:#202b38;background:#f4f6f8}body{margin:0;padding:24px;line-height:1.65}h1{margin:0 0 6px;font-size:28px}h2{font-size:19px}p{margin:8px 0}.card{background:white;border:1px solid #ccd3da;border-radius:8px;padding:16px;margin-top:16px}.muted{color:#536275;font-size:14px}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:10px 0}select,button,input{font:inherit;padding:5px 9px;max-width:100%}button{cursor:pointer}select{max-width:390px}#viewport{overflow:auto;max-height:1000px;border:1px solid #ccd3da;background:#eee}canvas{width:100%;display:block}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}th{background:#f4f6f8}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}a{color:#165d99}.status{padding:8px 0;font-size:14px}.legend{font-size:14px}#groupTable{max-height:440px;overflow:auto}details{margin-top:12px}code{overflow-wrap:anywhere}.warn{background:#fff7de;padding:10px;border-left:4px solid #c89c20}.chip{background:#eef2f5;padding:2px 7px;border-radius:4px}
</style>
<h1>全量标注分簇与模型对照</h1>
<p class="muted">2026-09-18 · 恢复交付版 · 固定研究提交 f8b7d60d · main d3477e7 / 历史输入 c61930e · W019/W026不进入分析，W011历史保留。</p>
<div class="card"><b>范围：214图、239个图片×条件；2388份保留记录，2364份配对几何，2381份可做无序点集比较。</b>
<p>本页从已恢复的逐份结果重建，不重新选择阈值，也不将不可计算记录作为单人簇。18种配对配置、6种点集配置、3种球面视图的适用分母分别保留。</p>
<p class="muted">全部数值和分组可离线查看。39张重点图嵌入的是原图缩略图；其余175张原图需点击联网加载，或选择本地对应图片。此图册不表示已逐点审完全部作答。切换原始点仅改变叠加，不改变按已确认有效点计算的分组。两项pending更正不进入主视图。</p></div>
<div class="card">
<div class="controls"><label>图片×条件 <select id="group"></select></label><button id="prev">上一项</button><button id="next">下一项</button><input id="search" placeholder="搜索图号，如 X7 或 B6-22"><button id="find">定位</button></div>
<div class="controls"><label>方案 <select id="method"></select></label><label>点版本 <select id="pointversion"><option value="effective">已确认有效点</option><option value="raw">原始点，仅叠加对照</option></select></label><label>人类边界 <select id="curve"><option value="none">不连接：只看原点</option><option value="linear">归一化线性边界</option><option value="spherical">归一化球面边界</option></select></label></div>
<div class="controls"><label>作答A <select id="personA"></select></label><label>作答B <select id="personB"></select></label><label>模型候选 <select id="model"><option value="none">不显示</option><option value="bi_enclosed">Bi enclosed</option><option value="bi_extended">Bi extended</option><option value="hohonet">HoHoNet</option><option value="ulayout_boundary">uLayout边界</option></select></label></div>
<div class="controls"><button id="loadremote">联网载入原尺寸图片</button><label>或载入本地图 <input id="localimage" type="file" accept="image/*"></label><label>放大 <input id="zoom" type="range" min="1" max="3" step="0.25" value="1"></label></div>
<div id="imageStatus" class="status"></div><p class="legend"><span style="color:#de3434">A：圆点</span>　<span style="color:#007dac">B：方点</span>　<span style="color:#167327">模型：空心点／曲线</span>。颜色不代表质量。点号保留导出顺序，不代表已确认墙面邻接。</p>
<div id="viewport"><canvas id="canvas" width="2048" height="1024"></canvas></div><div id="pairStatus" class="status"></div>
<details><summary>查看两份作答的身份、原始点与有效点</summary><pre id="points"></pre></details></div>
<div class="card"><h2 id="tableTitle"></h2><div id="groupTable"></div><p class="muted">各簇编号仅在当前图片、条件和配置下有效；不同方法相同编号不代表同一语义。密度方法未分配结果单独标注，不命名为确定模式。</p></div>
<div class="card"><h2>模型对照与已保存来源</h2><pre id="modelInfo"></pre><details><summary>重点图原评论与裁决（无新裁决时保持空白）</summary><pre id="comments"></pre></details><details><summary>本图全部原始记录状态</summary><pre id="recordStatus"></pre></details></div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
'use strict';const DATA=JSON.parse(document.getElementById('payload').textContent),$=x=>document.getElementById(x);
const keys=Object.keys(DATA.groups).sort((a,b)=>DATA.groups[a].code.localeCompare(DATA.groups[b].code)||a.localeCompare(b));let currentKey='',currentImage=null,request=0;
for(const k of keys){const g=DATA.groups[k];$('group').add(new Option(g.code+' · '+g.condition,k));}
for(const m of DATA.methods)$('method').add(new Option(m,m));
function esc(v){const e=document.createElement('span');e.textContent=String(v);return e.innerHTML;}
function group(){return DATA.groups[currentKey];}function label(id){return group().methods[$('method').value]?.[id]??null;}
function personOptions(select,keep){select.replaceChildren();select.add(new Option('不显示','none'));for(const r of group().records){const c=label(r.id);select.add(new Option(r.worker+' · '+(c===null?'未入该配置':'组'+c)+' · '+r.status,r.id));}if(keep&&[...select.options].some(o=>o.value===keep))select.value=keep;else select.selectedIndex=select.options.length>1?1:0;}
function selectGroup(){currentKey=$('group').value;currentImage=null;const g=group();personOptions($('personA'));personOptions($('personB'));if(g.records.length>1)$('personB').selectedIndex=2;renderTable();$('comments').textContent=g.comments?JSON.stringify(g.comments,null,2):'该图没有嵌入39图开发评论；不等于没有问题。';$('recordStatus').textContent=JSON.stringify(g.records.map(r=>({id:r.id,worker:r.worker,status:r.status,processing:r.processing,imputed:r.imputed,raw_n:r.raw?.length??null,effective_n:r.effective?.length??null})),null,2);$('modelInfo').textContent=JSON.stringify(g.modelSummary??{},null,2);let tok=++request;if(g.preview){loadImage(g.preview,tok,'已载入39重点图中的原图缩略图。');}else{$('imageStatus').textContent='当前未载入原图；请点击联网载入，或选择同图的本地文件。灰底上的点不能代替视觉审查。';draw();}}
function loadImage(src,tok,message){const im=new Image();im.onload=()=>{if(tok!==request)return;currentImage=im;$('imageStatus').textContent=message+' '+im.naturalWidth+'×'+im.naturalHeight;draw();};im.onerror=()=>{if(tok!==request)return;$('imageStatus').textContent='图片加载失败；数值与分组仍可查看。可选择本地同图文件。';draw();};im.src=src;}
function getr(id){return group().records.find(r=>r.id===id);}
function curve(events,type){if(!events||events.length<2)return null;const e=[...events].sort((a,b)=>a[0]-b[0]),out=[[],[]];for(let x=0;x<1024;x++){let i=e.length-1;for(let j=0;j<e.length;j++)if(e[j][0]<=x)i=j;const a=e[i],b=e[(i+1)%e.length],gap=(b[0]-a[0]+1024)%1024,dx=(x-a[0]+1024)%1024;if(gap<1e-7)return null;for(let k=1;k<=2;k++){let y;if(type==='spherical'){if(gap>=512||a[1]>=255.5||b[1]>=255.5||a[2]<=255.5||b[2]<=255.5)return null;const va=((a[k]+.5)/512-.5)*Math.PI,vb=((b[k]+.5)/512-.5)*Math.PI,t=dx*2*Math.PI/1024,G=gap*2*Math.PI/1024;y=(Math.atan((Math.tan(va)*Math.sin(G-t)+Math.tan(vb)*Math.sin(t))/Math.sin(G))/Math.PI+.5)*512-.5;}else y=a[k]+(b[k]-a[k])*dx/gap;out[k-1].push(y);}}return out;}
function drawCurve(ctx,arr,color){if(!arr)return;ctx.save();ctx.strokeStyle=color;ctx.lineWidth=1.4;for(const edge of arr){ctx.beginPath();for(let x=0;x<edge.length;x++){const y=edge[x];if(!Number.isFinite(y)){continue;}if(x===0)ctx.moveTo(x*1024/edge.length,y);else ctx.lineTo(x*1024/edge.length,y);}ctx.stroke();}ctx.restore();}
function markers(ctx,points,color,square=false,hollow=false){if(!points)return;ctx.save();ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=1.7;ctx.font='11px system-ui';points.forEach((p,i)=>{const [x,y]=p;if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||x>1024||y<0||y>512)return;ctx.beginPath();if(square)ctx.rect(x-3,y-3,6,6);else ctx.arc(x,y,3.7,0,Math.PI*2);if(hollow)ctx.stroke();else ctx.fill();ctx.strokeStyle='white';ctx.lineWidth=2.5;ctx.strokeText(String(i+1),x+5,y-4);ctx.fillStyle=color;ctx.fillText(String(i+1),x+5,y-4);ctx.strokeStyle=color;ctx.lineWidth=1.7;});ctx.restore();}
function draw(){const ctx=$('canvas').getContext('2d');ctx.setTransform(2,0,0,2,0,0);ctx.clearRect(0,0,1024,512);if(currentImage)ctx.drawImage(currentImage,0,0,1024,512);else{ctx.fillStyle='#e8ecf0';ctx.fillRect(0,0,1024,512);}ctx.strokeStyle='rgba(120,130,140,.25)';ctx.lineWidth=.5;for(let x=0;x<1024;x+=128){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,512);ctx.stroke();}const a=getr($('personA').value),b=getr($('personB').value),v=$('pointversion').value;for(const [r,color,sq]of [[a,'#de3434',false],[b,'#007dac',true]]){if(!r)continue;if($('curve').value!=='none'&&v==='effective')drawCurve(ctx,curve(r.events,$('curve').value),color);markers(ctx,r[v],color,sq);}const model=$('model').value,mp=DATA.models[group().image_id]?.[model];if(mp){if(model==='ulayout_boundary')drawCurve(ctx,mp,'#167327');else{markers(ctx,mp,'#167327',false,true);const events=[];for(let i=0;i+1<mp.length;i+=2)events.push([mp[i][0],Math.min(mp[i][1],mp[i+1][1]),Math.max(mp[i][1],mp[i+1][1])]);drawCurve(ctx,curve(events,'spherical'),'#167327');}}const msg=[];if(a)msg.push('A '+a.worker+'：'+a.status+'，该配置'+(label(a.id)===null?'不可计算':'组'+label(a.id)));if(b)msg.push('B '+b.worker+'：'+b.status+'，该配置'+(label(b.id)===null?'不可计算':'组'+label(b.id)));if(v==='raw')msg.push('注意：只显示原始点，成员关系仍来自已确认有效点主版本。');if(v==='raw'&&$('curve').value!=='none')msg.push('原始点模式不推造上下配对，因此不绘制人类连接。');$('pairStatus').textContent=msg.join('；');$('points').textContent=JSON.stringify({A:a??null,B:b??null},null,2);}
function renderTable(){const g=group(),m=$('method').value,groups={};let missing=[];for(const r of g.records){const l=label(r.id);if(l===null){missing.push(r.worker+' ['+r.status+']');continue;}(groups[l]??=[]).push(r);}const arr=Object.entries(groups).sort((a,b)=>b[1].length-a[1].length||Number(a[0])-Number(b[0]));$('tableTitle').textContent=g.code+' / '+g.condition+' · '+m+' · '+arr.length+'个显示组';let h='<table><thead><tr><th>显示组</th><th>人数</th><th>人员</th><th>备注</th></tr></thead><tbody>';for(const [l,rs]of arr){const notes=[];if(rs.some(r=>r.imputed))notes.push('包含已确认补点');if(rs.some(r=>g.noise?.[m]?.includes(r.id)))notes.push('密度未分配；非已识别模式');h+='<tr><td>'+esc(l)+'</td><td>'+rs.length+'</td><td>'+esc(rs.map(r=>r.worker).join(' · '))+'</td><td>'+esc(notes.join('；'))+'</td></tr>';}h+='</tbody></table>';if(missing.length)h+='<p class="warn">未进入当前配置：'+esc(missing.join('；'))+'</p>';$('groupTable').innerHTML=h;}
$('group').onchange=selectGroup;$('method').onchange=()=>{personOptions($('personA'),$('personA').value);personOptions($('personB'),$('personB').value);renderTable();draw();};for(const n of ['pointversion','personA','personB','model','curve'])$(n).onchange=draw;
$('prev').onclick=()=>{$('group').selectedIndex=Math.max(0,$('group').selectedIndex-1);selectGroup();};$('next').onclick=()=>{$('group').selectedIndex=Math.min(keys.length-1,$('group').selectedIndex+1);selectGroup();};$('find').onclick=()=>{const q=$('search').value.trim().toLowerCase();const k=keys.find(k=>groupCode(k).includes(q));if(k){$('group').value=k;selectGroup();}};function groupCode(k){return (DATA.groups[k].code+' '+DATA.groups[k].condition).toLowerCase();}
$('loadremote').onclick=()=>{$('imageStatus').textContent='正在从固定Git提交载入原图…';loadImage(group().url,++request,'已载入固定提交的原尺寸图片。');};$('localimage').onchange=()=>{const f=$('localimage').files[0];if(!f)return;loadImage(URL.createObjectURL(f),++request,'已载入本地图片（需自行确认与当前图号相符）。');};$('zoom').oninput=()=>{$('canvas').style.width=Number($('zoom').value)*100+'%';};
const first=keys.find(k=>DATA.groups[k].code==='X7HyMhZNoso-19'&&DATA.groups[k].condition==='manual');if(first)$('group').value=first;$('method').value='A3_cyclic_cut08';selectGroup();
window.recoveryAtlas={groupCount:keys.length,methodCount:DATA.methods.length,data:DATA};
</script></html>'''

def run(root:Path,pixels_zip:Path|None,output:Path):
    inp=root/'inputs/frozen';res=root/'results';data=json.loads((inp/'key39/data.json').read_text());ns=legacy.legacy_functions(data)
    meta={x['image_id']:x for x in (json.loads(l) for l in (root/'snapshot/history/analysis_results/image_portrait_20260914_v1/metadata/images.jsonl').read_text().splitlines())}
    human=[json.loads(l)for l in gzip.open(inp/'human/responses.jsonl.gz','rt')];audit=pd.read_csv(res/'all_response_audit.csv').set_index('id');cases={c['image_id']:c for c in data['cases']}
    memberships=[pd.read_csv(res/n) for n in ['memberships.csv','pointset_memberships.csv','spherical_memberships.csv']];methods=list(dict.fromkeys(m for f in memberships for m in f.method.unique()))
    payload={'groups':{},'methods':methods,'models':json.loads((res/'model_geometry_compact.json').read_text())};g=payload['groups']
    for r in human:
        if r['worker_id']in ['W019','W026']:continue
        cid=r['canonical_annotation_id'];iid=r['image_id'];k=iid+'|'+r['raw_condition'];a=audit.loc[cid]
        if k not in g:
            case=cases.get(iid);g[k]={'image_id':iid,'code':a['code'],'condition':r['raw_condition'],'records':[],'methods':{},'noise':{},'url':'https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/d3477e700082c0a8482f1ffabd9dcc5649c9754d/'+meta[iid]['path'],'comments':({'reviews':case.get('reviews'),'user_adjudications':case.get('user_adjudications'),'user_point_review':case.get('user_point_review')}if case else None)}
        norm=ns['normalize_geometry'](r['effective_points_1024x512']);events=legacy.pairs3(norm).tolist()if norm['valid']else None
        g[k]['records'].append({'id':cid,'worker':r['worker_id'],'status':a['analysis_status'],'processing':r['processing_status'],'imputed':r['imputed_point'],'raw':r['raw_points_1024x512'],'effective':r['effective_points_1024x512'],'events':events,'exclusion_reason':r['exclusion_reason'],'confirmation_source':r['confirmation_source'],'source_export':r['raw_export_path']})
    for f in memberships:
        for (iid,cond,m),s in f.groupby(['image_id','condition','method']):
            k=iid+'|'+cond;g[k]['methods'][m]={r['id']:int(r['cluster'])for r in s.to_dict('records')}
            if 'density_unassigned'in s:g[k]['noise'][m]=s.loc[s.density_unassigned,'id'].tolist()
    feats=pd.read_csv(res/'model_image_features.csv').set_index('image_id');targets=pd.read_csv(res/'model_linkage_targets.csv')
    for k,gr in g.items():
        gr['records'].sort(key=lambda r:r['worker']);row=feats.loc[gr['image_id']].to_dict();t=targets[(targets.image_id==gr['image_id'])&(targets.condition==gr['condition'])]
        gr['modelSummary']={'model_image_features':row,'human_comparison':t.to_dict('records')}
    embedded=0
    if pixels_zip:
        with zipfile.ZipFile(pixels_zip)as z:
            bycode={Path(n).stem:n for n in z.namelist()if n.lower().endswith(('.png','.jpg'))}
            for gr in g.values():
                if gr['code']not in bycode:continue
                im=Image.open(io.BytesIO(z.read(bycode[gr['code']]))).convert('RGB');im.thumbnail((1024,512));b=io.BytesIO();im.save(b,format='JPEG',quality=85)
                gr['preview']='data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode();embedded+=1
    payload=legacy.safe_json(payload)
    j=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</','<\\/')
    output.write_text(TEMPLATE.replace('__PAYLOAD__',j),encoding='utf-8')
    print(json.dumps({'groups':len(g),'records':sum(len(gr['records'])for gr in g.values()),'methods':len(methods),'embedded_unique_images':len({gr['image_id']for gr in g.values()if gr.get('preview')}),'bytes':output.stat().st_size},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--pixels-zip',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.root,a.pixels_zip,a.output)
