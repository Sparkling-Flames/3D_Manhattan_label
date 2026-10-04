"""Offline numeric evidence viewer; no photographs, no remote dependencies."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from arc_consensus import Ring,TAU,W,H,footprint,paired_wall_proxy
sys.path.insert(0,str(ROOT))
from run_research import normalized_cases

def display_record(r):
    q=dict(r);u=(np.arange(2048)+.5)*TAU/2048;q['display_curves']=Ring(r).evaluate(u).tolist()
    q['display_x']=((np.arange(2048)+.5)*W/2048).tolist()
    if 'footprint' not in q:q['footprint']=footprint(r)[0].tolist()
    if 'top_xyz' not in q:
        a,b=paired_wall_proxy(r);q['top_xyz']=a.tolist();q['bottom_xyz']=b.tolist()
    return q
cases=[]
for label,image,rs,ref in normalized_cases(load_refs=True):
    p=ROOT/'results/final';e=json.loads((p/f'{label}_fusion.json').read_text());main=e['bev_mv50_complete_method']
    candidates={f'精确全员结果 / BEV≥50%兼容':display_record(e['methods'][main])}
    for eps in [.25,.5,1.,2.]:candidates[f'显示压缩 {eps:g}px（不作语义删点）']=display_record(json.loads((p/f'{label}_compressed_{eps:g}px.json').read_text()))
    other='mv50' if main=='mv_strict' else 'mv_strict'
    candidates['另一个平票规则 / ERP '+other]=display_record(e['methods'][other])
    candidates['5°点中心数值对照（非原模块完整诊断）']=display_record(json.loads((p/f'{label}_point_baseline.json').read_text())['mv50'])
    cases.append(dict(image=image,records=[display_record(r) for r in rs],reference=display_record(ref),
        exact=e['methods'][main],candidates=candidates,n=len(rs)))
data=json.dumps(cases,ensure_ascii=False,separators=(',',':')).replace('</',r'<\/')
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全员上下边界共识 · 数值证据</title>
<style>body{font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif;background:#f3f5f6;color:#18232c;margin:0}main{max-width:1260px;margin:auto;padding:26px}h1{font-size:28px;margin:0}h2{font-size:19px;margin:12px 0}.sub{color:#566673}.panel{background:white;border:1px solid #d6dfe3;padding:18px;margin:16px 0;border-radius:8px}.bar{display:flex;gap:15px;flex-wrap:wrap;align-items:center}select,button,input{font:inherit}select{padding:7px;max-width:100%}.notice{border-left:4px solid #c99838;padding:9px 14px;background:#fff8e7}canvas{max-width:100%;display:block;border:1px solid #dae0e3;margin:auto;background:#fff}#erp{width:1024px;aspect-ratio:2}#bev,#wall{width:480px;height:380px}.grid{display:flex;gap:20px;flex-wrap:wrap;justify-content:center}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:6px;border-bottom:1px solid #dde4e7;text-align:left;vertical-align:top}pre{white-space:pre-wrap;font-size:12px;max-height:330px;overflow:auto;background:#f5f7f8;padding:12px}code{overflow-wrap:anywhere}.legend{font-size:13px}.small{font-size:12px;color:#55656e}</style>
<main><h1>全员上下边界共识：完整点对与来源</h1><p class="sub">冻结 080949f5971000a32310d4e4ebf9028dab831a91 · 2026-10-04 · 无原图的数值研究</p>
<div class="notice">节点是精确投票轮廓的分段位置，不是已确认物理墙角。三维视图只有由上下点对派生的墙带，没有推测天花内表面。所有输入环和资格保持原状；本页面不运行筛人或GT选优。</div>
<div class="panel bar"><label>图片 <select id="case"></select></label><label>输出 <select id="method"></select></label><label><input type="checkbox" id="raw" checked> 全体输入</label><label><input type="checkbox" id="gt"> 固定原参考（仅对照）</label><label>强调人员 <select id="person"><option value="">无</option></select></label></div>
<div class="panel"><h2 id="title"></h2><p id="facts"></p><canvas id="erp" width="1024" height="512"></canvas><p class="legend">浅线：原始人员曲线；蓝线：输出上、下界；圆点：配对表示节点；虚线橙色：开启后的固定参考。点击画布靠近节点，查看其来源。背景为空是因为没有原始全景图。显示曲线采用2048列采样，定量验算使用解析分段事件。</p><p id="nodeinfo" class="small"></p></div>
<div class="panel grid"><div><h2>声明地面足迹</h2><canvas id="bev" width="480" height="380"></canvas></div><div><h2>上下点对墙带代理 · 非封闭实体</h2><canvas id="wall" width="480" height="380"></canvas><label>观察方向 <input id="yaw" type="range" min="0" max="360" value="35"></label></div></div>
<div class="panel"><h2>节点／原边来源</h2><p>压缩节点保留其精确节点索引；来源原边指向具体人员、作答和上下端点号。上下来源不同不等于错误，也不能把两个边界来源人数称为整面墙的共同支持。</p><pre id="provenance"></pre></div>
<div class="panel"><h2>全体当前人员（只读，不可在此改变分母）</h2><table><thead><tr><th>人员</th><th>作答</th><th>点对数</th><th>源环人工确认</th><th>原点对到精确全员曲线的最大上下差 / px</th></tr></thead><tbody id="roster"></tbody></table><p class="small">这些残差不是“错误”标签，不表示已进行语义角点对应；未被选中为分位边界的观测也未删除。</p></div>
<div class="panel"><h2>另一个明确保留的状态</h2><p>rPc6DW4iMge-06：选中的 R01518 / P017 与 R01784 / P001，前者的已确认环不是经度单向一周。两人组返回 <code>unsupported_entire_selected_roster</code>；仍保留两人、原环与有效BEV，不将它重新按x排序，不用单个成功者替代两人结果。</p></div>
</main><script>const DATA=__DATA__;
const $=id=>document.getElementById(id);let C,M;const blue='#164d74',orange='#b65d16';
DATA.forEach((d,i)=>$('case').add(new Option(d.image,i)));
function selectCase(){C=DATA[+$('case').value];$('method').innerHTML='';Object.keys(C.candidates).forEach(k=>$('method').add(new Option(k,k)));$('person').innerHTML='<option value="">无</option>';C.records.forEach(r=>$('person').add(new Option(r.worker+' / '+r.id,r.id)));draw();}
function line(ctx,p,fn,col,width=1,alpha=1,close=false,dash=[]){ctx.strokeStyle=col;ctx.lineWidth=width;ctx.globalAlpha=alpha;ctx.setLineDash(dash);ctx.beginPath();p.forEach((z,i)=>{const q=fn(z);i?ctx.lineTo(...q):ctx.moveTo(...q)});if(close)ctx.closePath();ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;}
function curves(ctx,r,col,width,alpha,dash=[]){for(let side=0;side<2;side++){line(ctx,r.display_x.map((x,i)=>[x,r.display_curves[side][i]]),v=>v,col,width,alpha,false,dash);}}
function draw(){M=C.candidates[$('method').value];const ctx=$('erp').getContext('2d');ctx.clearRect(0,0,1024,512);ctx.strokeStyle='#e6ebee';ctx.lineWidth=1;for(let x=0;x<=1024;x+=128){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,512);ctx.stroke()}for(let y=0;y<=512;y+=64){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(1024,y);ctx.stroke()}if($('raw').checked)C.records.forEach(r=>curves(ctx,r,'#6b7781',.65,.2));const hi=C.records.find(r=>r.id===$('person').value);if(hi)curves(ctx,hi,'#a51c62',1.7,1);if($('gt').checked)curves(ctx,C.reference,orange,1.3,1,[6,4]);curves(ctx,M,blue,2,1);M.points.forEach((p,i)=>{ctx.beginPath();ctx.arc(...p,2.5,0,Math.PI*2);ctx.fillStyle=blue;ctx.fill();if(i%2===0){ctx.strokeStyle='#7393aa';ctx.globalAlpha=.2;ctx.beginPath();ctx.moveTo(...p);ctx.lineTo(...M.points[i+1]);ctx.stroke();ctx.globalAlpha=1;}});
$('title').textContent=C.image+' / '+C.n+' 名独立人员 / '+M.points.length/2+' 个配对节点';$('facts').textContent='源环不重排；新环未人工确认。'+(M.maximum_vertical_curve_error_px!==undefined?'显示压缩最大上／下曲线偏差：'+M.maximum_vertical_curve_error_px.toFixed(6)+' px。':'精确结果或另列点中心对照；不据GT选择。');
const all=C.records.flatMap(r=>r.footprint).concat(M.footprint);const min=[Math.min(...all.map(v=>v[0])),Math.min(...all.map(v=>v[1]))],max=[Math.max(...all.map(v=>v[0])),Math.max(...all.map(v=>v[1]))];const s=Math.min(420/(max[0]-min[0]),320/(max[1]-min[1]));const xy=v=>[240+(v[0]-(min[0]+max[0])/2)*s,190-(v[1]-(min[1]+max[1])/2)*s];const b=$('bev').getContext('2d');b.clearRect(0,0,480,380);if($('raw').checked)C.records.forEach(r=>line(b,r.footprint,xy,'#78828a',.6,.3,true));if($('gt').checked)line(b,C.reference.footprint,xy,orange,1.2,1,true,[5,4]);line(b,M.footprint,xy,blue,2,1,true);let O=xy([0,0]);b.fillText('相机',O[0]+5,O[1]-5);b.beginPath();b.arc(...O,3,0,7);b.fill();
const w=$('wall').getContext('2d');w.clearRect(0,0,480,380);const yaw=+$('yaw').value*Math.PI/180,pts=M.top_xyz.concat(M.bottom_xyz);const flat=v=>{let x=Math.cos(yaw)*v[0]+Math.sin(yaw)*v[2],z=-Math.sin(yaw)*v[0]+Math.cos(yaw)*v[2];return[x,.45*z-.9*v[1]]};const zz=pts.map(flat),mx=Math.max(...zz.map(v=>Math.abs(v[0]))),my=Math.max(...zz.map(v=>Math.abs(v[1])));const k=Math.min(210/mx,160/my),view=v=>{let z=flat(v);return[240+k*z[0],190+k*z[1]]};line(w,M.top_xyz,view,blue,1.6,1,true);line(w,M.bottom_xyz,view,blue,1.6,1,true);M.top_xyz.forEach((v,i)=>line(w,[v,M.bottom_xyz[i]],view,'#5c7c94',.75,.6));
$('roster').innerHTML=C.records.map(r=>{let v=C.exact.source_pair_residuals.filter(x=>x.id===r.id),e=Math.max(...v.flatMap(x=>[Math.abs(x.source_minus_generated_top_px),Math.abs(x.source_minus_generated_bottom_px)]));return `<tr><td>${r.worker}</td><td>${r.id}</td><td>${r.points.length/2}</td><td>${r.ring_confirmed===true?'是':'否'}</td><td>${e.toFixed(5)}</td></tr>`}).join('');node(0);}
function node(i){let j=M.retained_exact_knot_indices?M.retained_exact_knot_indices[i]:i;let exact=M.knot_provenance?M:(M.retained_exact_knot_indices?C.exact:null);let prov=exact?.knot_provenance?.[j];$('nodeinfo').textContent='显示节点 '+i+'；精确节点 '+j+'；上点 '+JSON.stringify(M.points[2*i])+'；下点 '+JSON.stringify(M.points[2*i+1]);$('provenance').textContent=prov?JSON.stringify(prov,null,2):'该数值点中心对照的完整来源请见对应JSON及原仓库；不把精确弧结果的来源套给它。';}
$('erp').onclick=e=>{let x=(e.clientX-e.target.getBoundingClientRect().left)/e.target.getBoundingClientRect().width*1024;let best=0,d=1e9;for(let i=0;i<M.points.length/2;i++){let dx=Math.abs(M.points[2*i][0]-x);dx=Math.min(dx,1024-dx);if(dx<d){d=dx;best=i}}node(best)};
$('case').onchange=selectCase;['method','raw','gt','person','yaw'].forEach(id=>$(id).oninput=draw);selectCase();</script></html>'''.replace('__DATA__',data)
(ROOT/'EVIDENCE_VIEWER_ZH.html').write_text(html,encoding='utf-8')
print('viewer bytes',len(html.encode()))
