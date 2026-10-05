from pathlib import Path
import json,html,importlib.util
r=Path(__file__).parent
D=json.loads((r/'inputs/domain.json').read_text());C=json.loads((r/'results/final/finite/all_candidates.json').read_text());P=json.loads((r/'results/final/finite/policy_outputs_before_truth.json').read_text());T=json.loads((r/'evaluation/synthetic_truth.json').read_text())
C=[{k:c[k] for k in ['id','choices','nodes_xz_top','points','geometry_valid','geometry_issues','compatibility','violated_constraints','unknown_constraints','admissible','pair_count','area_h2','carrier_loss_vector_h','exact_complete_source_workers','serialization_status','declared_paths_xz_top']} for c in C]
P=[{k:p[k] for k in ['policy','stream_id','status','candidate_ids','geometry_count','evidence_claims']} for p in P]
data=json.dumps({'domain':D,'candidates':C,'decisions':P,'truth':T},ensure_ascii=False,separators=(',',':')).replace('</',r'<\/')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>给定锚点的局部路径候选｜独立研究</title>
<style>body{font-family:system-ui,'Noto Sans CJK SC',sans-serif;color:#202a33;background:#f4f6f7;margin:0;padding:22px;line-height:1.6}main{max-width:1240px;margin:auto}h1{font-size:25px;margin:0 0 9px}h2{font-size:18px}p{margin:8px 0}.notice{background:#fff4da;border-left:4px solid #ac741b;padding:10px 14px}.controls,.card{background:white;border:1px solid #d7dfe3;padding:16px;margin-top:15px;border-radius:5px}select{max-width:100%;padding:7px;margin:4px;min-width:160px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}.card svg{width:100%;height:330px;background:#fbfcfc}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:7px;border-bottom:1px solid #dbe2e6;text-align:left}pre{background:#eef2f4;overflow:auto;max-height:300px;padding:12px;font-size:12px}small{color:#53616d}code{font-family:monospace}@media(max-width:800px){.grid{display:block}}</style>
<main><h1>局部路径：候选、证据与待定</h1><p>六个给定对应锚点 · 七名合成人员 · 324个完整赋值 · 保留全部失败</p>
<div class="notice">当前只浏览一个候选，不是自动选优。给定锚点和相容关系不代表真实对应已解决；多候选也不保证包含真值。所有图形均为合成数据的几何显示，不是原图视觉审核。</div>
<div class="controls"><label>政策/证据条件 <select id="policy"></select></label><br><label>完整候选 <select id="candidate"></select></label><label>局部放大段 <select id="seg"></select></label><br><label><input type="checkbox" id="gt">仅评价展示合成真值</label><select id="world"></select><p id="status"></p></div>
<div class="grid"><div class="card"><h2>完整底面与锚点</h2><svg id="bev" viewBox="0 0 500 340"></svg></div><div class="card"><h2>上下配对边的ERP投影</h2><svg id="erp" viewBox="0 0 600 340"></svg><small>直边投影采样仅用于显示；数值误差不由此图读取。</small></div></div>
<div class="grid"><div class="card"><h2>给定局部路径的对照</h2><svg id="zoom" viewBox="0 0 500 340"></svg><small>虚线为其他允许/待验路径；实线为当前选择。部分路径自身会导致非法候选。</small></div><div class="card"><h2>本次局部核验证据</h2><pre id="evidence"></pre><small>缺失不是否定；同一来源组的复制不增加一组独立证据。</small></div></div>
<div class="card"><h2>来源与新连接</h2><table><thead><tr><th>段</th><th>路径</th><th>原供者</th><th>构造</th><th>载体→候选误差h</th></tr></thead><tbody id="sources"></tbody></table><p id="whole"></p></div>
<div class="card"><h2>全部配对节点与失败信息</h2><pre id="raw"></pre></div>
<p><a href="REPORT_ZH.html">中文报告</a> · <a href="results/final/finite/candidate_ledger.csv">完整失败账本</a> · <a href="results/final/real/real_diagnostics.json">两处真实未裁决诊断</a></p></main>
<script>const DATA=__DATA__;
const $=x=>document.getElementById(x), all=DATA.candidates;
const label={budget_005:'0.05h路径预算',budget_020:'0.20h路径预算',carrier_pareto:'全观测路径Pareto保真',evidence_b0:'局部证据，0错误组',evidence_b1:'局部证据，至多1错误组'};
$('policy').innerHTML='<option value="-1">只看完整候选域（含失败）</option>'+DATA.decisions.map((p,i)=>`<option value="${i}">${label[p.policy.id]} | ${p.stream_id}</option>`).join('');
$('seg').innerHTML=DATA.domain.segments.map((s,i)=>`<option value="${i}">段${i}：A${i}→A${(i+1)%6}</option>`).join('');
$('world').innerHTML=DATA.truth.worlds.map(w=>`<option value="${w.id}">${w.id}</option>`).join('');
function refresh(){let v=+$('policy').value,p=v>=0?DATA.decisions[v]:null;let cs=p?all.filter(c=>p.candidate_ids.includes(c.id)):all;$('candidate').innerHTML=cs.map(c=>`<option value="${c.id}">${c.id} | ${c.geometry_valid?c.compatibility:'几何/锚点失败'} | ${c.pair_count===null?'不可序列化':c.pair_count+'对'}</option>`).join('');$('status').textContent=p?`${p.status}；${p.geometry_count}种几何；${p.candidate_ids.length}个表示状态。`: '324完整赋值；非法/不相容候选未删去。';$('evidence').textContent=p?JSON.stringify(p.evidence_claims,null,2):'未应用政策。';draw();}
function pth(nodes,x,y,closed=false){return nodes.map((p,i)=>(i?'L':'M')+x(p[0]).toFixed(3)+','+y(p[1]).toFixed(3)).join(' ')+(closed?' Z':'');}
function proj(p){let rr=Math.hypot(p[0],p[2]);return [((Math.atan2(p[0],-p[2])/(2*Math.PI)+.5+1)%1)*1024,(.5-Math.atan2(p[1],rr)/Math.PI)*512];}
function truthNodes(){let w=DATA.truth.worlds.find(w=>w.id===$('world').value);return w.choices.flatMap((q,i)=>DATA.domain.segments[i].paths[q].nodes_xz_top.slice(0,-1));}
function draw(){let c=all.find(c=>c.id===$('candidate').value);if(!c){['bev','erp','zoom'].forEach(k=>$(k).innerHTML='');$('raw').textContent='无可行候选；不填零误差，不自动回退到某份原答。';$('sources').innerHTML='';$('whole').textContent='';return;}
if(!c.nodes_xz_top){let xx=v=>250+v*47,yy=v=>185-v*47;$('bev').innerHTML=c.declared_paths_xz_top.map(ps=>`<path d="${pth(ps,xx,yy)}" fill="none" stroke="#a94b40" stroke-width="2"/>`).join('');$('erp').innerHTML='<text x="30" y="70" font-size="15">锚点不接合：不生成修复后的完整点环</text>';$('zoom').innerHTML='';$('sources').innerHTML='';$('whole').textContent='保留各段原声明，未生成新跨接来修补缺口。';$('raw').textContent=JSON.stringify(c,null,2);return;}
let x=v=>250+v*47,y=v=>185-v*47,n=c.nodes_xz_top;let s=`<path d="${pth(n,x,y,true)}" fill="#dcebf1" stroke="#1b6786" stroke-width="2"/>`;
if($('gt').checked)s+=`<path d="${pth(truthNodes(),x,y,true)}" fill="none" stroke="#b66320" stroke-width="2" stroke-dasharray="6 4"/>`;
s+=DATA.domain.anchors_xz_top.map((p,i)=>`<circle cx="${x(p[0])}" cy="${y(p[1])}" r="4" fill="#1f3039"/><text x="${x(p[0])+6}" y="${y(p[1])-6}" font-size="13">A${i}</text>`).join('');s+=`<text x="245" y="181" font-size="15">＋</text>`;$('bev').innerHTML=s;
let er='';for(let side of [0,1]){for(let i=0;i<n.length;i++){let a=n[i],b=n[(i+1)%n.length],last=null,pts=[];for(let k=0;k<=32;k++){let t=k/32,xyz=[a[0]+t*(b[0]-a[0]),side?-1:a[2]+t*(b[2]-a[2]),a[1]+t*(b[1]-a[1])],p=proj(xyz);if(last&&Math.abs(p[0]-last[0])>512){er+=`<path d="${pth(pts,v=>20+v*.54,v=>15+v*.6)}" fill="none" stroke="${side?'#ad6435':'#1b6786'}"/>`;pts=[];}pts.push(p);last=p;}er+=`<path d="${pth(pts,v=>20+v*.54,v=>15+v*.6)}" fill="none" stroke="${side?'#ad6435':'#1b6786'}"/>`;}}
for(let i=0;i<c.points.length;i+=2){let a=c.points[i],b=c.points[i+1];er+=`<line x1="${20+a[0]*.54}" x2="${20+b[0]*.54}" y1="${15+a[1]*.6}" y2="${15+b[1]*.6}" stroke="#c8d0d5" stroke-width=".6"/>`;}
$('erp').innerHTML=er;
let j=+$('seg').value,paths=DATA.domain.segments[j].paths,pts=paths.flatMap(p=>p.nodes_xz_top),xmin=Math.min(...pts.map(p=>p[0])),xmax=Math.max(...pts.map(p=>p[0])),ymin=Math.min(...pts.map(p=>p[1])),ymax=Math.max(...pts.map(p=>p[1])),sx=v=>30+440*(v-xmin)/(Math.max(.06,xmax-xmin)),sy=v=>290-240*(v-ymin)/Math.max(.08,ymax-ymin);$('zoom').innerHTML=paths.map((p,k)=>`<path d="${pth(p.nodes_xz_top,sx,sy)}" fill="none" stroke="${k==c.choices[j]?'#1b6786':'#a4adb4'}" stroke-width="${k==c.choices[j]?3:1.5}" ${k==c.choices[j]?'':'stroke-dasharray="4 4"'}/><text x="35" y="${22+k*17}" font-size="12">${p.id} | ${p.donors.map(d=>d.worker).join(',')||'无精确原路径供者'}</text>`).join('');
$('sources').innerHTML=c.choices.map((q,i)=>{let p=DATA.domain.segments[i].paths[q];return `<tr><td>${i}</td><td>${p.id}</td><td>${p.donors.map(d=>d.worker).join(', ')||'无；不可继承原路径票'}</td><td>${p.construction}</td><td>${c.carrier_loss_vector_h[i].toPrecision(5)}</td></tr>`}).join('');
$('whole').textContent='整环几何恰与以下原供者相同：'+(c.exact_complete_source_workers.join(', ')||'无')+'。这不是语义认可人数，也不要求输出必须由某人完整画过。';$('raw').textContent=JSON.stringify(c,null,2);
}
$('policy').onchange=refresh;['candidate','seg','world','gt'].forEach(k=>$(k).onchange=draw);$('policy').value='0';refresh();
</script></html>'''.replace('__DATA__',data)
(r/'EVIDENCE_VIEWER_ZH.html').write_text(page,encoding='utf-8')
text=(r/'REPORT_ZH.md').read_text()
# Keep numeric formulas as readable source if no browser math engine is available.
if importlib.util.find_spec('markdown2'):
 import markdown2;body=markdown2.markdown(text,extras=['tables','fenced-code-blocks'])
elif importlib.util.find_spec('mistune'):
 import mistune;body=mistune.create_markdown(plugins=['table'])(text)
else:body='<pre>'+html.escape(text)+'</pre>'
style='body{font-family:system-ui,"Noto Sans CJK SC",sans-serif;max-width:1050px;margin:35px auto;padding:0 24px;color:#202a33;line-height:1.85}h1{font-size:28px}h2{font-size:22px;border-bottom:1px solid #ced7df;padding-top:20px}h3{font-size:18px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #dbe3e8;padding:7px;text-align:left}th{background:#f1f5f7}pre{white-space:pre-wrap;overflow:auto;background:#f4f6f8;padding:12px}code{font-size:90%}a{color:#1b6786}'
(r/'REPORT_ZH.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>局部路径有限域研究</title><style>'+style+'</style><p><a href="EVIDENCE_VIEWER_ZH.html">查看完整候选与来源</a></p>'+body+'</html>',encoding='utf-8')
print('viewer',len(page),'report',len(body))
