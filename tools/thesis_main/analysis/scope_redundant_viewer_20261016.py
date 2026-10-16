"""展示全部已整理空间与每个原编号；不修改审核或评分数据。"""
import json
import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/data/scope_redundant_vertices_20261016'


def build():
    rows = json.loads((OUT/'scope_views.json').read_text(encoding='utf-8'))
    checks = json.loads((OUT/'CHECKS.json').read_text(encoding='utf-8'))
    difficulty = json.loads((ROOT/checks['input_sources'][0]).read_text(encoding='utf-8'))
    images = {r['image_id']:r for r in difficulty['records']}
    for r in rows:
        photo = Path(images[r['image_id']]['photo'])
        assert photo.is_file(), photo
        r['photo_url'] = quote(Path(os.path.relpath(photo,OUT)).as_posix(),safe='/')
    rows.sort(key=lambda r:(r['image_code'],not r['current_target'],r['target_id']))
    assert len(rows)==checks['scope_views'] and len({r['target_id'] for r in rows})==len(rows)
    html = TEMPLATE.replace('__DATA__',json.dumps(rows,ensure_ascii=False).replace('</','<\\/'))
    (OUT/'REVIEW.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(spaces=len(rows),images=len({r['image_id'] for r in rows}),output=str(OUT/'REVIEW.html')),ensure_ascii=False))


TEMPLATE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>全部空间 · 点位处理对照</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#182b3a;font:15px/1.55 system-ui,"Microsoft YaHei",sans-serif}
header{background:#16384a;color:white;padding:17px 24px}h1{font-size:23px;margin:0}header p{margin:4px 0 0;color:#c7dce7}
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);gap:18px;padding:18px}aside{position:sticky;top:12px;height:calc(100vh - 125px);display:flex;flex-direction:column;background:white;border-radius:10px;padding:12px}
input[type=search]{width:100%;padding:10px;border:1px solid #bbc9d2;border-radius:6px}#list{overflow:auto;margin-top:10px}button{cursor:pointer;font:inherit;background:white;border:1px solid #c1ced7;border-radius:6px;padding:7px 12px;color:inherit}button:hover{background:#e8f3f8}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #1598c3}
.item{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid #eef1f3;border-radius:0;padding:9px 6px}.item.active{background:#dceff6;border-left:4px solid #087ea4}.small{font-size:12px;color:#5d7280}.item b{font-size:14px}.dot{color:#c65e00;font-weight:bold}
main{min-width:0}.panel{background:white;padding:16px;border-radius:10px;margin-bottom:16px}.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}h2{font-size:21px;margin:0 0 7px}.tag{background:#edf2f6;padding:3px 8px;border-radius:5px;font-size:13px}.notice{background:#fff5df;padding:9px 12px;border-radius:6px;margin:10px 0}.legend{display:flex;gap:15px;flex-wrap:wrap;font-size:13px;margin:8px 0}.legend b{font-size:18px}select{font:inherit;padding:6px;border:1px solid #becbd4;border-radius:6px}
#photoScroll{overflow:auto;border-radius:7px;background:#152531}#photoWrap{position:relative;width:100%;min-width:100%}#photo{display:block;width:100%;aspect-ratio:2/1}#overlay{position:absolute;inset:0;width:100%;height:100%}svg text{font-family:Arial,"Microsoft YaHei",sans-serif;paint-order:stroke;stroke-linejoin:round}.bottom{display:grid;grid-template-columns:minmax(300px,.9fr) minmax(350px,1.1fr);gap:16px}#bev{width:100%;background:#f7fafb;border-radius:7px;display:block}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:7px 9px;border-bottom:1px solid #e5ebef;text-align:left}th{background:#edf3f6}tr[data-point]{cursor:pointer}tr.selected{background:#fff0b5}summary{cursor:pointer;font-weight:600;margin:8px 0}.mono{font-size:11px;overflow-wrap:anywhere;color:#627380}#pointInfo{min-height:25px;font-weight:600;color:#875100}#position{min-width:70px}a{color:#007b9f}@media(max-width:950px){.layout{grid-template-columns:1fr}aside{position:static;height:230px}.bottom{grid-template-columns:1fr}}
</style>
<header><h1>全部空间 · 点位处理对照</h1><p>41张图片 · 43个新／备选空间，全量展示，不只显示发现冗余的空间。</p></header>
<div class="layout"><aside><input id="search" type="search" placeholder="搜索图片编号，如 uNb、wc2" aria-label="搜索空间"><div id="count" class="small"></div><nav id="list" aria-label="全部空间"></nav></aside>
<main><section class="panel"><div class="bar"><button id="prev">← 上一个</button><span id="position"></span><button id="next">下一个 →</button><span class="small">可用键盘左右键</span></div><h2 id="title"></h2><div id="badges" class="bar"></div><p id="summary"></p><div class="notice">这里展示的是处理对照与派生视图。原GT、作答和正式评分未被改写；橙色点只是精度内近似简化，不是已经认定的真实冗余墙角。</div>
<div class="bar"><label>查看范围 <select id="mode"><option value="raw">当前空间原始点</option><option value="exact">严格等价精简</option><option value="precision">精度内简化预览</option></select></label><label><input id="old" type="checkbox" checked> 叠加旧范围</label><label><input id="oldLabels" type="checkbox"> 显示旧点编号</label><label>原图放大 <input id="zoom" type="range" min="100" max="220" step="20" value="100"></label></div>
<div class="legend"><span><b style="color:#00d7e9">●</b> 当前空间保留点</span><span><b style="color:#ff4270">●</b> 严格共线中间点</span><span><b style="color:#ffb526">●</b> 精度内近共线点</span><span><b style="color:#b6a2e3">●</b> 旧范围／旧点</span></div><div id="pointInfo">点击点或下方点位表，可同时定位原图和俯视图。</div>
<div id="photoScroll"><div id="photoWrap"><img id="photo" alt="当前图片的原始全景"><svg id="overlay" viewBox="0 0 1024 512" aria-label="原图底边点位叠线"></svg></div></div><p class="small">原图叠线沿三维底边投影绘制；只显示底边，不补造未知顶界。所有编号保持精简前编号，旧点以“旧”区分。俯视图中的○为相机位置。</p></section>
<div class="bottom"><section class="panel"><h2>旧范围与新范围</h2><svg id="bev" viewBox="0 0 560 450" aria-label="新旧范围俯视图"></svg><p class="small">虚线为旧范围；实线为所选视图。精简后的点仍以原位置保留标记，方便检查去掉了哪里。</p><details><summary>空间身份与处理边界</summary><p id="target" class="mono"></p><p id="refstate"></p><p id="measure"></p></details></section>
<section class="panel"><h2>当前空间 · 每个点的处理</h2><table><thead><tr><th>原编号</th><th>底面结构处理</th><th>完整上下点对</th></tr></thead><tbody id="points"></tbody></table><details><summary id="oldSummary">旧点在新空间中的位置</summary><p class="small">以下是坐标位置关系，不等于自动判定墙角对应或作答错误。旧空间仍独立保留。</p><table><thead><tr><th>旧编号</th><th>与新空间的关系</th></tr></thead><tbody id="oldPoints"></tbody></table></details><p><a href="README.md">处理说明</a> · <a href="scope_summary.csv">全部空间清单</a></p></section></div></main></div>
<script>
const data=__DATA__, $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';let index=0,chosen=null;
const colors={keep:'#00d7e9',exact:'#ff4270',precision:'#ffb526',old:'#b6a2e3'};
const relation={same_coordinate_vertex:'仍是新环中的同坐标点',on_new_edge_not_vertex:'落在新边上，不再是顶点',inside_new_scope_not_vertex:'位于新范围内部，不再是边界顶点',outside_new_scope:'位于新范围外'};
function label(r){return r.current_target?'当前空间':('备选空间 '+(r.target_id.includes(':space_c:')?'C':r.target_id.includes(':space_d:')?'D':''))}
function node(parent,name,attrs,text){let n=document.createElementNS(NS,name);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;parent.append(n);return n}
function erp(p){return [((Math.atan2(p[0],-p[1])/(2*Math.PI)+.5)*1024+1024)%1024,(.5+Math.atan2(1,Math.hypot(...p))/Math.PI)*512]}
function paths(points){let out=[],part=[];for(let e=0;e<points.length;e++){let a=points[e],b=points[(e+1)%points.length];for(let s=0;s<=80;s++){let t=s/80,q=erp([a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t]);if(part.length&&Math.abs(q[0]-part.at(-1)[0])>512){out.push(part);part=[]}part.push(q)}}if(part.length)out.push(part);return out}
function line(svg,pts,color,dash=false,width=2){node(svg,'polyline',{points:pts.map(p=>p.join(',')).join(' '),fill:'none',stroke:color,'stroke-width':width,'stroke-dasharray':dash?'7 5':'','stroke-linejoin':'round'})}
function marker(svg,p,text,color,id,old=false){let g=node(svg,'g',{});if(!old&&chosen===id)node(g,'circle',{cx:p[0],cy:p[1],r:14,fill:'none',stroke:'#fff','stroke-width':4});node(g,'circle',{cx:p[0],cy:p[1],r:old?3:5,fill:color,stroke:'#152531','stroke-width':1});let tx=p[0]>980&&svg.id==='overlay'?p[0]-10:p[0]+8;node(g,'text',{x:tx,y:p[1]-8,fill:color,stroke:svg.id==='overlay'?'#101b23':'white','stroke-width':3,'font-size':svg.id==='overlay'?15:13,'font-weight':700},text);if(!old){g.style.cursor='pointer';g.onclick=()=>{chosen=id;draw()};node(g,'title',{},'当前原编号 '+id)}}
function status(r,n){return r.exact_removed.includes(n)?'exact':r.precision_removed.includes(n)?'precision':'keep'}
function geometry(r){return $('mode').value==='exact'?r.exact_floor_view.floor:$('mode').value==='precision'?r.precision_floor_view.floor:r.original_floor}
function draw(){let r=data[index],mode=$('mode').value,p=geometry(r),svg=$('overlay');svg.replaceChildren();let bev=$('bev');bev.replaceChildren();
 if($('old').checked)for(const path of paths(r.old_floor))line(svg,path,colors.old,true,1.8);for(const path of paths(p))line(svg,path,colors.keep,false,2.2);
 if($('oldLabels').checked)r.old_floor.forEach((q,i)=>marker(svg,erp(q),'旧'+(i+1),colors.old,i+1,true));
 r.original_floor.forEach((q,i)=>marker(svg,erp(q),String(i+1),colors[status(r,i+1)],i+1));
 let all=[...r.old_floor,...r.original_floor,[0,0]],xs=all.map(q=>q[0]),ys=all.map(q=>q[1]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys),scale=Math.min(470/Math.max(maxX-minX,.01),350/Math.max(maxY-minY,.01)),cx=(minX+maxX)/2,cy=(minY+maxY)/2;
 let map=q=>[280+(q[0]-cx)*scale,225-(q[1]-cy)*scale];
 if($('old').checked)line(bev,[...r.old_floor,r.old_floor[0]].map(map),colors.old,true);line(bev,[...p,p[0]].map(map),'#00899c',false,2.5);
 if($('oldLabels').checked)r.old_floor.forEach((q,i)=>marker(bev,map(q),'旧'+(i+1),'#8767b1',i+1,true));r.original_floor.forEach((q,i)=>marker(bev,map(q),String(i+1),status(r,i+1)==='keep'?'#00899c':colors[status(r,i+1)],i+1));let c=map([0,0]);node(bev,'circle',{cx:c[0],cy:c[1],r:5,fill:'white',stroke:'#344959','stroke-width':2});node(bev,'text',{x:c[0]+9,y:c[1]+16,fill:'#344959','font-size':12},'相机');
 $('points').replaceChildren();r.original_floor.forEach((q,i)=>{let n=i+1,st=status(r,n),tr=document.createElement('tr');tr.dataset.point=n;tr.className=chosen===n?'selected':'';let desc=st==='exact'?'严格共线：精简视图不计转折':st==='precision'?'近共线：仅精度内预览简化':'保留为当前结构点';let pair=r.paired_view?(r.paired_view.mapping.pair_removed_1based.includes(n)?'上下等价，可精简':'保留'):'顶界未完整核验，不删除点对';for(const x of [n,desc,pair]){let td=document.createElement('td');td.textContent=x;tr.append(td)}tr.onclick=()=>{chosen=n;draw()};$('points').append(tr)});
 $('pointInfo').textContent=chosen?'已定位当前原编号 '+chosen+'；'+({keep:'保留点',exact:'严格共线中间点',precision:'精度内近共线候选'})[status(r,chosen)]:'点击点或下方点位表，可同时定位原图和俯视图。';
 let pd=r.precision_floor_view;$('measure').textContent='精度内预览的底面面积变化：'+pd.symmetric_difference_area_h2.toPrecision(3)+' h²；最大边界位移：'+pd.hausdorff_distance_h.toPrecision(3)+' h。h为归一化相机高度。';
}
function list(){let q=$('search').value.trim().toLowerCase(),shown=0;$('list').replaceChildren();data.forEach((r,i)=>{if(!(r.image_code+' '+label(r)).toLowerCase().includes(q))return;shown++;let b=document.createElement('button');b.className='item'+(i===index?' active':'');let title=document.createElement('b');title.textContent=(i+1)+'. '+r.image_code;b.append(title);let sub=document.createElement('div');sub.className='small';sub.textContent=label(r)+' · '+r.raw_vertices+'点'+(r.precision_removed.length?' · 检出'+r.precision_removed.length+'个中间点':' · 无残留中间点');b.append(sub);b.onclick=()=>show(i);$('list').append(b)});$('count').textContent='显示 '+shown+' / '+data.length+' 个空间（全部均可查看）'}
function show(i){index=(i+data.length)%data.length;chosen=null;let r=data[index];$('title').textContent=r.image_code+' · '+label(r);$('position').textContent=(index+1)+' / '+data.length;$('photo').src=r.photo_url;$('photo').alt=r.image_code+' 原始全景';$('badges').replaceChildren();for(const t of ['旧范围 '+r.old_floor.length+' 点','新范围保存 '+r.raw_vertices+' 点','严格转折 '+r.exact_turns,'精度内转折 '+r.precision_turns]){let s=document.createElement('span');s.className='tag';s.textContent=t;$('badges').append(s)}$('summary').textContent=r.precision_removed.length?'当前原编号 '+r.precision_removed.join('、')+' 为严格或精度内中间点。其他点也逐一列在下表。':'本空间未发现残留的严格或精度内共线中间点；仍展示全部新旧点，便于核对范围改变。';$('target').textContent=r.target_id;$('refstate').textContent=r.full_reference_available?'该目标已有完整参考；这里仅展示底面。':'该目标尚无合格完整顶界；本页只展示已确认底面，不能据此给完整质量分。';$('oldSummary').textContent='旧范围全部 '+r.old_vertex_roles.length+' 个点的位置关系';$('oldPoints').replaceChildren();for(const v of r.old_vertex_roles){let tr=document.createElement('tr');for(const text of ['旧'+v.old_vertex_1based,relation[v.relation]+(v.matched_new_vertices_1based.length?'（新'+v.matched_new_vertices_1based.join('、')+'）':'')]){let td=document.createElement('td');td.textContent=text;tr.append(td)}$('oldPoints').append(tr)}list();draw();history.replaceState(null,'','#'+(index+1))}
$('prev').onclick=()=>show(index-1);$('next').onclick=()=>show(index+1);$('search').oninput=list;for(const x of ['mode','old','oldLabels'])$(x).onchange=draw;$('zoom').oninput=()=>$('photoWrap').style.width=$('zoom').value+'%';document.addEventListener('keydown',e=>{if(['INPUT','SELECT'].includes(document.activeElement.tagName))return;if(e.key==='ArrowRight')show(index+1);if(e.key==='ArrowLeft')show(index-1)});show(Math.max(0,Math.min(data.length-1,(parseInt(location.hash.slice(1))||1)-1)));
</script></html>'''


if __name__ == '__main__':
    build()
