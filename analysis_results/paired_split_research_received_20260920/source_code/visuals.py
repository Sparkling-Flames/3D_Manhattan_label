"""Precise 2D annotation overlays. Never infer a 3D wall connection from these lines."""
from pathlib import Path
import argparse,base64,gzip,json,html
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import study as s
from diagnostics import data

def imagepath(root,case):
 for f in [root/'visual'/(case['image_id']+'.jpg'),root/'visual'/(case['code']+'.png')]:
  if f.exists():return f
 return None

def font(n):
 for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf']:
  if Path(p).exists():return ImageFont.truetype(p,n)
 return ImageFont.load_default()

def drawcase(root,c,i):
 ip=imagepath(root,c)
 if ip is None:return None
 bg=Image.open(ip).convert('RGB').resize((1024,512));panels=[]
 for side,color in [('a',(230,65,40)),('b',(30,170,230))]:
  im=bg.copy();d=ImageDraw.Draw(im);pts=np.array(c['points_'+side]);pnums={}
  d.line((0,255.5,1024,255.5),fill=(190,190,190),width=1)
  for role in ['top','bottom']:
   inds=np.flatnonzero(pts[:,1]<255.5)if role=='top'else np.flatnonzero(pts[:,1]>255.5)
   inds=s.order_indices(pts,inds)
   for k,idx in enumerate(inds):pnums[idx]=('T'if role=='top'else'B')+str(k+1)
  # Only pair links are shown. They are not wall-to-wall edges.
  links=c['links_'+side]
  if links:
   for t,b in links:
    x,y=pts[t-1];xx,yy=pts[b-1];delta=(xx-x+512)%1024-512
    for off in [-1024,0,1024]:d.line((x+off,y,x+off+delta,yy),fill=color,width=1)
  for k,(x,y) in enumerate(pts):
   d.ellipse((x-3,y-3,x+3,y+3),fill=color,outline='black')
   label=f"{pnums.get(k,'?')}[p{k+1}]"
   d.text((x+5,y-14),label,fill=color,font=font(12),stroke_width=1,stroke_fill='black')
  panel=Image.new('RGB',(1024,560),'white');panel.paste(im,(0,48));dd=ImageDraw.Draw(panel)
  dd.text((10,5),f"{c['code']} {c['condition']} {c['worker_'+side]}  {len(pts)} points",fill='black',font=font(18))
  dd.text((10,27),'T/B index: separate x order. [p#]: unchanged source point. Lines: candidate pairs only.',fill='black',font=font(12));panels.append(panel)
 out=Image.new('RGB',(1024,1120),'white');out.paste(panels[0],(0,0));out.paste(panels[1],(0,560))
 path=root/'visual'/f"review_{i:02}_{c['code']}_{c['worker_a']}_{c['worker_b']}.jpg";out.save(path,quality=92)
 return path.name

def run(root=s.ROOT):
 cases=json.loads((root/'results/focused_cases.json').read_text());rows,recs,ad=data(root);cache=json.loads((root/'results/cache.json').read_text())
 for i,c in enumerate(cases,1):c['overlay']=drawcase(root,c,i)
 payload={'cases':cases,'groups':{},'records':{},'images':{}}
 for key,g in cache.items():
  payload['groups'][key]={'code':g['code'],'ids':g['ids'],'counts':g['counts'],'labels':g['labels']}
 for cid,a in recs.items():
  payload['records'][cid]={'worker':a['audit']['worker'],'p':a['p'].tolist(),'up':a['up'].tolist(),'dn':a['dn'].tolist(),
   'links':a['links'].tolist()if a['links']is not None else None,'source':a['audit']['pairing_source'],'role_source':a['audit']['role_source']}
 for c in cases:
  ip=imagepath(root,c)
  if ip and c['image_id']not in payload['images']:
   from io import BytesIO
   b=BytesIO();Image.open(ip).convert('RGB').resize((1536,768)).save(b,'JPEG',quality=87)
   payload['images'][c['image_id']]='data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()
 encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</',r'<\/')
 htmltext='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>上下绑定与分开按序｜2026-09-20</title>
<style>body{font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif;margin:24px auto;max-width:1440px;padding:0 20px;color:#17202a;background:#fafbfc}h1{font-size:27px}p{max-width:1100px}select,button{font:inherit;max-width:100%;padding:6px;margin:4px}canvas{width:100%;height:auto;background:#ddd;border:1px solid #aab}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:5px 10px;border-bottom:1px solid #ddd;text-align:left}.panel{background:white;border:1px solid #ddd;border-radius:6px;padding:14px;margin:12px 0}.warn{font-weight:600}.scroll{max-height:480px;overflow:auto}label{margin-right:8px}</style>
<h1>上下绑定与 top / bottom 分开按序比较</h1>
<p>固定 x 序为主实验；循环编号仅作接缝敏感性，不旋转任何一份作答的坐标。来源角色、原点编号与端点关联都保留。阈值是开发设置，不是语义真值。</p>
<div class="panel"><label>重点案例<select id="case"></select></label><br><label>全量图片 / 条件<select id="group"></select></label><br>
<label>A<select id="a"></select></label><label>B<select id="b"></select></label>
<label>比较规则<select id="method"><option value="split_fixed">top/bottom 分开，固定 x 顺序</option><option value="bound_fixed">上下绑定，点对固定 x 顺序</option><option value="split_cyclic">分开，循环序号对齐</option><option value="bound_cyclic">绑定，共用循环序号</option><option value="split_free">分开，自由瓶颈匹配对照</option><option value="bound_free">绑定，自由瓶颈匹配对照</option></select></label>
<label>半径<select id="cut"><option>3</option><option>6</option><option selected>9</option><option>12</option></select>度</label>
<label><input type="checkbox" id="showA" checked>A</label><label><input type="checkbox" id="showB" checked>B</label><label><input type="checkbox" id="links">显示作答内部候选上下连线</label><label>放大<input id="zoom" type="range" min="1" max="3" step=".5" value="1"></label></div>
<p id="note"></p><p id="status" class="warn"></p><div style="overflow:auto"><canvas id="canvas" width="2048" height="1024"></canvas></div>
<div class="panel"><h2>本图完整分区</h2><div id="members"></div></div><div class="panel"><h2>逐点对应：原始点号 p 从 1 起</h2><p>重点案例全部六种对应已计算；其他作答可直接查看固定序对应。不同点数不强制凑齐。</p><div class="scroll"><table id="points"></table></div></div>
<script>const D=PAYLOAD; const $=x=>document.getElementById(x); let chosen=null,img=null;
function opt(e,k,t){let o=document.createElement('option');o.value=k;o.textContent=t;e.appendChild(o)}
Object.keys(D.groups).sort((a,b)=>D.groups[a].code.localeCompare(D.groups[b].code)).forEach(k=>opt($('group'),k,D.groups[k].code+' / '+k.split('|')[1]));opt($('case'),'','全量自由选择');D.cases.forEach((c,i)=>opt($('case'),i,c.code+' '+c.worker_a+' / '+c.worker_b+' — '+c.source));
function fillPersons(){let g=D.groups[$('group').value];for(let id of ['a','b']){$(id).innerHTML='';g.ids.forEach(cid=>opt($(id),cid,D.records[cid].worker+' · '+D.records[cid].p.length+'点'))}$('b').selectedIndex=Math.min(1,g.ids.length-1);loadimg()}
function loadimg(){let iid=$('group').value.split('|')[0];img=null;if(D.images[iid]){let v=new Image();v.onload=()=>{if($('group').value.split('|')[0]===iid){img=v;render()}};v.src=D.images[iid]}render()}
function selectcase(){let c=D.cases[Number($('case').value)];if($('case').value==='')return;chosen=c;$('group').value=c.image_id+'|'+c.condition;fillPersons();$('a').value=c.id_a;$('b').value=c.id_b;render()}
function distance(a,b){let la=(a[1]+.5)/512*Math.PI-Math.PI/2,lb=(b[1]+.5)/512*Math.PI-Math.PI/2,du=(a[0]-b[0])*2*Math.PI/1024;let h=Math.sin((la-lb)/2)**2+Math.cos(la)*Math.cos(lb)*Math.sin(du/2)**2;h=Math.min(1,Math.max(0,h));return 360/Math.PI*Math.atan2(Math.sqrt(h),Math.sqrt(1-h))}
function mappings(A,B,method){let c=D.cases.find(c=>c.id_a===$('a').value&&c.id_b===$('b').value);let rev=false;if(!c){c=D.cases.find(c=>c.id_b===$('a').value&&c.id_a===$('b').value);rev=!!c}if(c&&c.comparisons[method].length)return c.comparisons[method].map(z=>rev?{...z,point_a:z.point_b,point_b:z.point_a,x_a:z.x_b,y_a:z.y_b,x_b:z.x_a,y_b:z.y_a}:z);
if(A.p.length!==B.p.length)return [];if(method.endsWith('free'))return [];let pairs=[];for(let role of ['top','bottom']){let j=role==='top'?0:1;let a=method.startsWith('bound')?(A.links||[]).map(v=>v[j]):A[j===0?'up':'dn'];let b=method.startsWith('bound')?(B.links||[]).map(v=>v[j]):B[j===0?'up':'dn'];if(!a.length||a.length!==b.length)return [];let shift=0;if(method==='split_cyclic'){let best=Infinity;for(let sh=0;sh<a.length;sh++){let v=Math.max(...a.map((x,i)=>distance(A.p[x],B.p[b[(i+sh)%b.length]])));if(v<best){best=v;shift=sh}}}if(method==='bound_cyclic'){let best=Infinity;for(let sh=0;sh<A.links.length;sh++){let v=Math.max(...A.links.flatMap((l,i)=>[0,1].map(j=>distance(A.p[l[j]],B.p[B.links[(i+sh)%B.links.length][j]]))));if(v<best){best=v;shift=sh}}}a.forEach((x,i)=>{let y=b[(i+shift)%b.length];pairs.push({role,ordinal:i+1,point_a:x+1,point_b:y+1,x_a:A.p[x][0],y_a:A.p[x][1],x_b:B.p[y][0],y_b:B.p[y][1],error_deg:distance(A.p[x],B.p[y])})})}return pairs}
function render(){let g=D.groups[$('group').value],A=D.records[$('a').value],B=D.records[$('b').value];if(!A||!B)return;let method=$('method').value,cut=Number($('cut').value),ctx=$('canvas').getContext('2d');ctx.clearRect(0,0,2048,1024);ctx.fillStyle='#e8e8e8';ctx.fillRect(0,0,2048,1024);if(img)ctx.drawImage(img,0,0,2048,1024);else{ctx.fillStyle='#444';ctx.font='28px sans-serif';ctx.fillText('此图未打包像素；仍显示冻结坐标，不虚构图像。',80,510)}let pairs=mappings(A,B,method);let labelmap={a:{},b:{}};pairs.forEach(p=>{labelmap.a[p.point_a]=(p.role==='top'?'T':'B')+p.ordinal;labelmap.b[p.point_b]=(p.role==='top'?'T':'B')+p.ordinal});
function draw(r,color,side){ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;if($('links').checked&&r.links)r.links.forEach(([u,v])=>{let [x,y]=r.p[u], [xx,yy]=r.p[v],dx=((xx-x+1536)%1024)-512;for(let off of [-1024,0,1024]){ctx.beginPath();ctx.moveTo(2*(x+off),2*y);ctx.lineTo(2*(x+off+dx),2*yy);ctx.stroke()}});r.p.forEach((p,i)=>{ctx.beginPath();ctx.arc(2*p[0],2*p[1],5,0,7);ctx.fill();ctx.font='20px sans-serif';ctx.lineWidth=3;ctx.strokeStyle='black';let txt=(labelmap[side][i+1]||'?')+'[p'+(i+1)+']';ctx.strokeText(txt,2*p[0]+7,2*p[1]-8);ctx.fillText(txt,2*p[0]+7,2*p[1]-8)})}
if($('showA').checked)draw(A,'#ff6544','a');if($('showB').checked)draw(B,'#25cbf1','b');$('canvas').style.width=(100*Number($('zoom').value))+'%';
let cc=D.cases.find(c=>c.id_a===$('a').value&&c.id_b===$('b').value);$('note').textContent=(cc?('证据来源：'+cc.source+'；用户裁决：'+(cc.relation||'本轮无新用户裁决')+'。'):'')+' A关联：'+A.source+'；B关联：'+B.source+'。';
$('status').textContent=A.p.length!==B.p.length?'点数不同：本轮严格表达分组直接分开；不记为局部算法成功。':(pairs.length?'当前对应的最大端点差：'+Math.max(...pairs.map(p=>p.error_deg)).toFixed(4)+'°':'该任意对的自由匹配明细未打包，或角色/关联不可用；不填零，完整分区仍可查。');
let labs=g.labels[method+'_'+cut];$('members').innerHTML='';if(labs){let ai=labs.ids.indexOf($('a').value),bi=labs.ids.indexOf($('b').value);$('status').textContent+='；完整分区：'+(ai<0||bi<0?'其中一份此视图不可计算':(labs.labels[ai]===labs.labels[bi]?'A/B同组':'A/B分开'))+'。';let blocks={};labs.ids.forEach((id,i)=>(blocks[labs.labels[i]]??=[]).push(D.records[id].worker));Object.entries(blocks).forEach(([k,v])=>{let p=document.createElement('p');p.textContent='组'+k+' ('+v.length+'人)：'+v.join(', ');$('members').appendChild(p)})}else $('members').textContent='该规则无可计算分区。';
$('points').innerHTML='<tr><th>角色</th><th>序号</th><th>A原点号</th><th>B原点号</th><th>A(x,y)</th><th>B(x,y)</th><th>角距</th></tr>'+pairs.map(p=>'<tr><td>'+p.role+'</td><td>'+p.ordinal+'</td><td>'+p.point_a+'</td><td>'+p.point_b+'</td><td>'+p.x_a.toFixed(2)+', '+p.y_a.toFixed(2)+'</td><td>'+p.x_b.toFixed(2)+', '+p.y_b.toFixed(2)+'</td><td>'+p.error_deg.toFixed(4)+'°</td></tr>').join('');}
$('case').onchange=selectcase;$('group').onchange=()=>{$('case').value='';chosen=null;fillPersons()};for(let x of ['a','b','method','cut','showA','showB','links','zoom'])$(x).onchange=render;fillPersons();$('case').value='6';selectcase();
</script></html>'''.replace('PAYLOAD',encoded)
 (root/'ATLAS.html').write_text(htmltext,encoding='utf-8');s.dump(root/'results/visual_case_index.json',cases)
 print('Rendered',sum(c['overlay']is not None for c in cases),'case pages; atlas',len(htmltext),'characters')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=s.ROOT);args=ap.parse_args();run(args.root)
