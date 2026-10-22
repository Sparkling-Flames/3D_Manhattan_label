#!/usr/bin/env python3
"""Generate a read-only evidence browser: supplied geometry and raw review history.
No new photographs, reference choices, or adjudications are generated.
"""
from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parent

def build():
    r=ROOT/'results'
    f=pd.read_csv(r/'FEEDBACK_30_ALL_RECORDS_AND_RAW_COMMENTS.csv').fillna('')
    geo={x['case_id']:x for x in json.load(open(r/'REVIEW_GEOMETRY_30.json'))}
    cards=[]
    fields=['case_id','record_id','object_id','image_code','reference_id','phase','selection','prior_case','first_reveal_grade','final_grade','score_revealed_at','first_viewed_at','updated_at','comment','scope_comment_reason','WQ','A10','S8','B8L2','C8_anchor_matched','IoU3D100','loss_F','loss_d','loss_H','Q_gain_scale_only_from_WQ','Q_gain_pool_only_at_c8']
    for row in f.to_dict('records'):
        d={k:row[k] for k in fields};d['geometry']=geo[row['case_id']];cards.append(d)
    payload=json.dumps(cards,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
    html=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>质量组合机制 · 30份原始证据</title>
<style>body{font:17px/1.65 system-ui;margin:0 auto;max-width:1150px;padding:28px}h1{font-size:27px}button,select{font:inherit;margin:4px;padding:7px 12px}section{border:1px solid #ccc;padding:18px;margin:18px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 monospace}blockquote{margin:10px 0;padding:15px;border-left:4px solid #999;white-space:pre-wrap}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:6px 10px;border-bottom:1px solid #ddd;text-align:left}canvas{width:100%;height:480px;touch-action:none}.hint{font-size:14px}nav{position:sticky;top:0;background:white;padding:8px;border-bottom:1px solid #aaa}[hidden]{display:none}</style>
<h1>组合机制研究：30份原话与固定几何</h1><p>本页是已曝光资料的只读查阅，不是独立盲评。原始回执、首揭示档位和最终档位分别保留；没有补造首揭示时的评论、修改原因或新RGB判断。</p>
<nav><button id="prev">上一份</button><select id="pick"></select><button id="next">下一份</button><button id="reveal">展开／隐藏模型结果</button></nav>
<section><h2 id="title"></h2><pre id="binding"></pre><div id="history"></div><blockquote id="comment"></blockquote><p id="scope"></p></section>
<section><button id="bev">底面俯视</button><button id="view3d">三维线框</button><canvas id="canvas" width="1000" height="480"></canvas><p class="hint">实线：作答；虚线：固定参考。三维模式可拖动旋转。仅显示本包声明几何，不是原图，不构成新的视觉裁决；额外点数不自动正确或错误。</p></section>
<section id="scores" hidden><h2>同输入、同参考结果</h2><div id="table"></div><p class="hint">F与d是非负变换损失，不是独立随机误差。C匹配B的单项轴和等强对角线，分数接近的一部分由设计保证。</p></section>
<script>const DATA=__DATA__;
let idx=0,mode='bev',yaw=.7,pitch=.5,drag=null;const $=x=>document.getElementById(x),names={poor:'较差',average_poor:'一般与较差之间',average:'一般',good_average:'较好与一般之间',good:'较好'};
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
DATA.forEach((x,i)=>{let o=document.createElement('option');o.value=i;o.textContent=x.case_id+' | '+x.record_id;$('pick').append(o)});
function render(){const d=DATA[idx];$('pick').value=idx;$('title').textContent=d.case_id+' · '+d.image_code+' · '+d.record_id;
$('binding').textContent='object_id: '+d.object_id+'\nreference_id: '+d.reference_id+'\nphase: '+d.phase+'\nselection: '+d.selection+'\n旧题号（仅作出处）: '+(d.prior_case||'无');
$('history').innerHTML='<table><tr><th>首次揭示时档位</th><td>'+esc(names[d.first_reveal_grade]||'未记录档位')+'</td></tr><tr><th>最终档位</th><td>'+esc(names[d.final_grade])+'</td></tr><tr><th>首次看本卡</th><td>'+esc(d.first_viewed_at)+'</td></tr><tr><th>首次揭示分数</th><td>'+esc(d.score_revealed_at)+'</td></tr><tr><th>最后记录更新时间</th><td>'+esc(d.updated_at)+'</td></tr></table>';
$('comment').textContent=d.comment||'（原始备注为空）';$('scope').textContent=d.scope_comment_reason?'范围评论敏感性标记：'+d.scope_comment_reason+'。不改写原档位或既有资格。':'没有新增范围裁决。';
$('table').innerHTML='<table><tr><th>模型／分项</th><th>读数</th></tr>'+['WQ','A10','S8','B8L2','C8_anchor_matched','IoU3D100','loss_F','loss_d','loss_H','Q_gain_scale_only_from_WQ','Q_gain_pool_only_at_c8'].map(k=>'<tr><td>'+k+'</td><td>'+Number(d[k]).toFixed(4)+'</td></tr>').join('')+'</table>';draw();}
function draw(){const c=$('canvas'),ctx=c.getContext('2d'),d=DATA[idx].geometry;ctx.clearRect(0,0,c.width,c.height);let rings=[];
for(const [key,hkey,dash] of [['a','ah',[]],['g','gh',[7,5]]]){let p=d[key],h=d[hkey];if(mode==='bev'){rings.push({v:p.map(x=>[x[0],0,x[1]]),dash})}else{let b=p.map(x=>[x[0],-1,x[1]]),t=p.map((x,i)=>[x[0],h[i]-1,x[1]]);rings.push({v:b,dash},{v:t,dash});for(let i=0;i<p.length;i++)rings.push({v:[b[i],t[i]],dash,open:true});}}
function proj(v){if(mode==='bev')return [v[0],-v[2]];let x=v[0]*Math.cos(yaw)-v[2]*Math.sin(yaw),z=v[0]*Math.sin(yaw)+v[2]*Math.cos(yaw);return [x,-v[1]*Math.cos(pitch)+z*Math.sin(pitch)];}
let ps=rings.flatMap(x=>x.v.map(proj)),xs=ps.map(x=>x[0]),ys=ps.map(x=>x[1]),minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys);let s=Math.min((c.width-70)/(maxx-minx||1),(c.height-70)/(maxy-miny||1)),mx=(minx+maxx)/2,my=(miny+maxy)/2;function screen(v){let p=proj(v);return [c.width/2+(p[0]-mx)*s,c.height/2+(p[1]-my)*s]};
for(const ring of rings){ctx.setLineDash(ring.dash);ctx.lineWidth=ring.dash.length?1.6:2.3;ctx.beginPath();ring.v.forEach((v,i)=>{let [x,y]=screen(v);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});if(!ring.open)ctx.closePath();ctx.stroke();}ctx.setLineDash([]);ctx.fillText(mode==='bev'?'BEV / camera-height units':'Declared 3D wireframe',25,24);}
$('pick').onchange=e=>{idx=+e.target.value;render()};$('prev').onclick=()=>{idx=(idx+DATA.length-1)%DATA.length;render()};$('next').onclick=()=>{idx=(idx+1)%DATA.length;render()};$('reveal').onclick=()=>{$('scores').hidden=!$('scores').hidden};$('bev').onclick=()=>{mode='bev';draw()};$('view3d').onclick=()=>{mode='3d';draw()};$('canvas').onpointerdown=e=>{drag=[e.clientX,e.clientY];e.target.setPointerCapture(e.pointerId)};$('canvas').onpointermove=e=>{if(drag&&mode==='3d'){yaw+=(e.clientX-drag[0])*.006;pitch+=(e.clientY-drag[1])*.006;drag=[e.clientX,e.clientY];draw()}};$('canvas').onpointerup=()=>drag=null;render();</script></html>'''
    (ROOT/'EVIDENCE_30.html').write_text(html.replace('__DATA__',payload),encoding='utf-8')
    return len(cards)

if __name__=='__main__':print('Read-only cards:',build())
