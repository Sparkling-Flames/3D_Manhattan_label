"""Read-only scientific case exhibits for four already selected Q/QT teams.

No fusion, scoring, classification, or selection is run. Frozen stage05 is read
only; outputs go exclusively to stage06_synthesis/selection_case_exhibits.
"""
from pathlib import Path
import argparse,base64,csv,gzip,hashlib,io,json,math,shutil,sys,zipfile,zlib
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parent
OUT=ROOT/'stage06_synthesis/selection_case_exhibits'
CASES=ROOT/'stage05_selection_stop/selection/cases'
ORDER=['large_quality_loss_1','large_quality_loss_2','large_quality_gain','different_members_small_quality_change']
COMMIT='13a7861334749805a86dc19e9ea79fcaa71020c0'
sys.path.insert(0,str(ROOT/'scripts/vendor'))
from fetch_originals_range import RemoteZip,BASE,SIZES

def hashfile(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
    with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig')) as f:return json.load(f)
def dump(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csvsave(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def initial_sources():
    OUT.mkdir(parents=True,exist_ok=True)
    cases=[]
    for name in ORDER:
        src=CASES/(name+'.json');d=load(src);assert d['row']['version']=='v21_history_reselected_fixed_candidates'
        dest=OUT/'source_cases'/src.name;dest.parent.mkdir(exist_ok=True)
        if dest.exists():assert hashfile(dest)==hashfile(src)
        else:shutil.copyfile(src,dest)
        cases.append(d)
    wanted={d['target_meta']['image'] for d in cases}
    idx=OUT/'FROZEN_IMAGE_INDEX.csv';zi=OUT/'FROZEN_ZIP_MEMBER_INDEX.csv'
    if not idx.exists():
        src=ROOT/'stage01_half_team/originals/FROZEN_RELEASE_IMAGE_INDEX.csv'
        rows=[r for r in csv.DictReader(src.open(encoding='utf-8-sig')) if r['image_code'] in wanted]
        assert len(rows)==4;csvsave(idx,rows)
    rows=list(csv.DictReader(idx.open(encoding='utf-8-sig')));assert {r['image_code'] for r in rows}==wanted
    if not zi.exists():
        src=WORK/'HOHONET_v21_reaudit_20261029/stage04_cases/six_cases/source/ZIP_MEMBER_INDEX.csv'
        if not src.exists():raise FileNotFoundError('Frozen ZIP-member index needed for local CRC verification: '+str(src))
        keys={(r['archive'],r['archive_path']) for r in rows}
        zs=[r for r in csv.DictReader(src.open(encoding='utf-8-sig')) if (r['archive'],r['archive_path']) in keys]
        assert len(zs)==4;csvsave(zi,zs)
    return cases,rows,{(r['archive'],r['archive_path']):r for r in csv.DictReader(zi.open(encoding='utf-8-sig'))}

def images(rows,zindex,fetch=False):
    dest=OUT/'originals';dest.mkdir(exist_ok=True);receipts=[];missing=[];transfers=[]
    # Known local original folders only. No compressed cache or rendered plot is accepted.
    bases=[ROOT/'stage01_half_team/originals',ROOT/'stage02_same_room/abc/cases/images',WORK/'HOHONET_v21_AC_population_20261029/stage06_cases',WORK/'HOHONET_v21_reaudit_20261029/stage04_cases',WORK/'audit_cases']
    old=load(dest/'ORIGINALS_RECEIPT.json') if (dest/'ORIGINALS_RECEIPT.json').exists() else None
    previous={r['image_code']:r for r in old['images']} if old else {}
    for r in rows:
        z=zindex[(r['archive'],r['archive_path'])];code=r['image_code'];target=dest/(code+'.png')
        candidates=[target]
        for b in bases:
            if b.exists():candidates.extend(b.rglob(code+'.png'));candidates.extend(b.rglob(r['image_id']+'.png'))
        found=None
        for p in candidates:
            if not p.is_file() or p.stat().st_size!=int(r['bytes']):continue
            data=p.read_bytes()
            if f'{zlib.crc32(data)&0xffffffff:08x}'!=z['zip_crc32']:continue
            found=p;break
        if found is None:missing.append(r);continue
        if found!=target:shutil.copyfile(found,target)
        receipt=previous.get(code,{**r,'source_url':BASE+r['archive'],'zip_crc32':z['zip_crc32'],'acquisition':'existing_exact_original','source_local':str(found),'sha256':hashfile(target)})
        assert receipt['sha256']==hashfile(target)
        receipts.append(receipt)
    if missing and not fetch:raise RuntimeError('Missing frozen originals; rerun with --fetch-images for bounded ZIP ranges: '+','.join(r['image_code'] for r in missing))
    for archive in sorted({r['archive'] for r in missing}):
        remote=RemoteZip(BASE+archive,SIZES[archive])
        with zipfile.ZipFile(remote) as z:
            for r in missing:
                if r['archive']!=archive:continue
                member=z.getinfo(r['archive_path']);info=zindex[(archive,r['archive_path'])]
                assert f'{member.CRC:08x}'==info['zip_crc32']
                data=z.read(member)
                assert len(data)==int(r['bytes']) and (zlib.crc32(data)&0xffffffff)==member.CRC
                target=dest/(r['image_code']+'.png');target.write_bytes(data)
                receipts.append({**r,'source_url':BASE+archive,'zip_crc32':info['zip_crc32'],'acquisition':'frozen_release_selected_member_byte_ranges','source_local':None,'sha256':hashfile(target)})
                print('original acquired',r['image_code'],len(data),flush=True)
        transfers.append({'archive':archive,'full_archive_bytes':SIZES[archive],'transferred_bytes':remote.transferred,'ranges':remote.ranges})
    assert len(receipts)==4
    for r in receipts:
        p=dest/(r['image_code']+'.png')
        with Image.open(p) as im:im.verify()
        with Image.open(p) as im:assert im.size==(2048,1024)
    receipt={'commit':COMMIT,'frozen_release':'quality-original-images-20261015','images':receipts,'zip_ranges':(old.get('zip_ranges',[]) if old else [])+transfers,'full_archive_downloaded':False,'only_four_preselected_cases':True,'image_index_sha256':hashfile(OUT/'FROZEN_IMAGE_INDEX.csv'),'zip_member_index_sha256':hashfile(OUT/'FROZEN_ZIP_MEMBER_INDEX.csv')}
    dump(dest/'ORIGINALS_RECEIPT.json',receipt)
    return {r['image_code']:r for r in receipts}

NOTES={
 'large_quality_loss_1':{
  'title':'uNb-01：省记录劳动，但质量明显下降', 'focus':[905,298,4],
  'look':'先切到重点墙段：检查 x≈905、y≈290–301 的底部角点与两侧墙段，再比较底面图的缩入及顶部高度。这里给出的是原图与已保存几何的可见差异；对象遮挡或目标边界的人工判断仍需要看图。',
  'numbers':'两队均为 4 个有效转折。QT 的边界、方向、高度损失均较 Q 增大，底面 IoU 降低；不是以节点数改变解释这次降质。',
 },
 'large_quality_loss_2':{
  'title':'uNb-43：短墙段附近差异与降质尾部', 'focus':[76,285,4],
  'look':'先切到重点墙段：比较 x≈73–84 的相邻角点及短墙段，特别是 y≈306–309 的底部位置。可切换单人原答，检查换出与换入成员各自怎样表达这一区域。不要把这段自动命名为真实结构或错误结构；请对照原图确认。',
  'numbers':'两队均为 6 个有效转折，底面 IoU 均较高；已保存 direction_loss 从约 0.00349 增至 0.59775。dir 是内部正交方向偏离指标，不应读成“相对于参考墙方向的误差”；微小角点位移、短边方向与分数的关系需要几何与原图共同判断。',
 },
 'large_quality_gain':{
  'title':'uNb-12：升质，同时记录劳动增加', 'focus':[182,286,4],
  'look':'检查 x≈182、y≈286–288 的底部角点及相邻墙段；再观察其他角点是否一起变化。这里换入 W133、换出 W101，保留其余 4 人。',
  'numbers':'QT 的边界和方向损失下降，但高度损失增加；总 Q 的提高不等于每个质量分项都提高。记录劳动也增加，不能把 QT 规则理解为每张图都省劳动。',
 },
 'different_members_small_quality_change':{
  'title':'S9h-10：成员改变，融合几乎不变', 'focus':[103,420,3],
  'look':'全图和重点墙段都可比较：两端点几乎重合。重点位置是 x≈103、y≈421 的底部角点。原答选择器允许查看 W110 与 W113，确认个人记录有何不同。',
  'numbers':'两队 B8L2 均约 98.525，差值仅约 0.00000471；这是高分且端点几乎一致的案例。没有完整候选票账，不能据此认定“背景锁定”或某一投票机制。',
 }
}

HTML=r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOHONET v2.1 · Q / QT 选队人工查看</title><style>
:root{--ink:#192b3b;--muted:#526576;--bg:#edf1f5;--q:#00afff;--qt:#fa4c6f;--ref:#ffe066;--raw:#ce72ff}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:15px/1.55 system-ui,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}main{max-width:1520px;padding:24px;margin:auto}h1{font-size:27px;margin:4px 0 6px}h2{font-size:20px;margin:0 0 10px}h3{font-size:17px;margin:0 0 8px}p{margin:7px 0}.eyebrow{font-size:12px;letter-spacing:1px;color:#42596d}.muted,small{color:var(--muted)}.box{background:white;border:1px solid #dce3eb;border-radius:12px;padding:17px;margin:14px 0}.toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:10px}.toolbar label{display:flex;align-items:center;gap:6px}button,select,input{font:inherit;border:1px solid #b7c5d2;border-radius:6px;padding:7px;background:white;color:var(--ink)}button{cursor:pointer}button:hover{background:#e7f3ff}select{max-width:100%}input[type=number]{width:86px}input[type=checkbox]{accent-color:#167bb5}button.primary{background:#174a6c;color:white;border-color:#174a6c}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.summary .num{font-size:25px;font-weight:700;line-height:1.3;margin-top:3px}.metric{background:#f3f6f9;border-radius:8px;padding:12px}.bad{color:#b12b47}.good{color:#106a57}.legend{display:flex;gap:18px;flex-wrap:wrap;margin:10px 0}.swatch:before{content:'';display:inline-block;width:27px;height:4px;background:var(--c);vertical-align:middle;margin-right:6px;border:1px solid #233746}.frame{background:#141b22;border-radius:6px;overflow:hidden}canvas{width:100%;height:auto;display:block;touch-action:none}.caph{background:#e9eef3;padding:8px 10px;font-size:14px;min-height:41px}.pill{display:inline-block;border-radius:5px;padding:2px 6px;background:#eef3f8;margin:2px;font-size:13px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:7px 9px;border-bottom:1px solid #e0e6ed;text-align:right;vertical-align:top}th:first-child,td:first-child{text-align:left}thead{background:#f0f4f8}.scroll{overflow:auto;max-height:580px}.mono{font-family:ui-monospace,Consolas,monospace;overflow-wrap:anywhere;font-size:12px}details{margin:10px 0}summary{cursor:pointer;font-weight:600}.note{border-left:4px solid #d8aa32;background:#fff9e8;padding:11px 14px;margin:12px 0}.foot{font-size:12px}.raw-meta{min-height:70px;padding:9px;background:#f4f1fb}.two-col{columns:2;column-gap:28px}.download{display:flex;gap:8px;flex-wrap:wrap}@media(max-width:850px){main{padding:12px}.grid{grid-template-columns:1fr}.summary{grid-template-columns:repeat(2,1fr)}h1{font-size:23px}.two-col{columns:1}}
</style></head><body><main>
<div class="eyebrow">HOHONET · v2.1 · 已有选队案例的人工查看补充</div><h1>Q / QT 两队，完整原图与几何对照</h1>
__CASE_LINKS__
<p class="muted">4 个在完整策略分析之后选定的案例。只展示冻结结果；没有新增选队、融合、评分或机制实验。普通 Manual，同图同目标，均为 5 人团队。</p>
<div class="box"><div class="toolbar"><label>案例 <select id="case"></select></label><button id="downloadCase">下载原始案例 JSON</button><button id="downloadPool">下载该图完整原答池</button><button id="downloadPng">下载真实原图</button></div><h2 id="title" style="margin-top:14px"></h2><p id="identity" class="muted"></p><div id="summary" class="summary"></div><div id="members"></div></div>
<div class="box"><h2>1. 同一视口下比较原图、参考与两队共识</h2><div class="toolbar"><button id="full" class="primary">全图</button><button id="focus">重点墙段</button><label>放大 <select id="zoom"><option value="1">1×</option><option value="2">2×</option><option value="3">3×</option><option value="4">4×</option><option value="6">6×</option></select></label><label>中心 x <input id="cx" type="number" min="0" max="1024" step="1" value="512"></label><label>中心 y <input id="cy" type="number" min="0" max="512" step="1" value="256"></label><label><input id="reference" type="checkbox" checked>当前参考</label><label><input id="other" type="checkbox">叠加另一队</label><label><input id="labels" type="checkbox" checked>节点序号</label></div>
<div class="legend"><span class="swatch" style="--c:var(--ref)">当前正式参考</span><span class="swatch" style="--c:var(--q)">Q 队</span><span class="swatch" style="--c:var(--qt)">QT 队</span><span class="swatch" style="--c:var(--raw)">单人原答</span></div>
<div class="grid"><section><h3 id="qHead"></h3><div class="frame"><canvas id="qCanvas" width="1536" height="768"></canvas></div><div id="qCap" class="caph"></div></section><section><h3 id="qtHead"></h3><div class="frame"><canvas id="qtCanvas" width="1536" height="768"></canvas></div><div id="qtCap" class="caph"></div></section></div>
<p class="foot muted">点击任一全景画布可将该位置设为共同视口中心；各画布同步。坐标采用原标注的 1024×512，原图为 2048×1024。墙段按三维直线投影到 ERP，跨全景接缝时分段绘制。不会在二维图上用直线错误连接两端。</p><div class="note"><p id="look"></p><p id="numbers"></p></div>
</div>
<div class="box"><h2>2. 逐人完整原答，以及底面位置和尺度</h2><div class="toolbar"><label>原答 <select id="raw"></select></label><label><input id="rawTeams" type="checkbox">原答图叠加两队共识</label></div><p class="muted">选择器先列两队成员，再列同一合法图池的其他人员。查看原答不改变团队；未入两队的记录只供上下文检查。</p><div class="grid"><section><div class="frame"><canvas id="rawCanvas" width="1536" height="768"></canvas></div><div id="rawMeta" class="raw-meta"></div></section><section><canvas id="bevCanvas" width="900" height="720" style="background:#f8fafc;border:1px solid #dce4ed;border-radius:6px"></canvas><p class="foot muted">底面采用冻结端点 footprint，与当前参考同坐标；相机在原点，长度以相机高度 h 归一化，不是全局米制定位。仅比较同一图片、同一目标。</p></section></div>
<details><summary>当前原答的完整点坐标与原始记录</summary><pre id="rawJson" class="mono" style="white-space:pre-wrap;max-height:420px;overflow:auto"></pre></details><details><summary>两队全部角点坐标（保持保存顺序，不重排序、不自动匹配）</summary><div id="points" class="scroll"></div></details>
</div>
<div class="box"><h2>3. 质量分项、结构、几何与合法同源记录劳动</h2><p class="muted">Δ = QT − Q。B8L2 / D10 越高越好；损失项越低越好。几何与数量变化本身不带好坏方向。缺值显示“—”，不填零。劳动是合法同源的记录秒数合计，不是墙钟耗时。</p><div id="metrics" class="scroll"></div></div>
<div class="box"><h2>4. 证据边界与精确来源</h2><p>本页只对 <code>score_status = complete_conditional</code> 的融合端点显示闭合共识。保留冻结输出顺序与 <code>ring_confirmed=false</code> 等原始状态，不将“可条件评分”改写成人工确认闭环。参考显示其完整正式边界；原答按冻结记录声明顺序呈现完整原答，不追加排序或人工确认。</p><p>这 4 例未生成专用完整候选轨迹。源 JSON 虽保存入选节点支持摘要，但它不能证明未入选结构、节点身份或连接的成因；本页不据总分、入选票数或成员替换方向推断投票机制。</p><p>Q 与 QT 是沿用原策略在当前历史质量及同一候选资格下的重选结果，不是人员类型的最终分类选择。原图只帮助人工核对已保存的结果，不参与选队或调参。</p><div id="provenance" class="mono"></div><p class="foot muted">需要人工判断的具体问题：上述重点墙段究竟对应什么真实边界、参考是否贴合可见空间、遮挡处怎样连接。已有数据可显示位置、形状与质量分项差异；缺少的过程证据不能用分数补造。</p></div>
</main><script id="dataset" type="application/json">__DATA__</script><script>
'use strict';const DATA=JSON.parse(document.getElementById('dataset').textContent),COL={Q:'#00afff',QT:'#fa4c6f',R:'#ffe066',raw:'#ce72ff'};let active=0,img=null,ready=false;const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));const fmt=(v,d=4)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(d):v===true?'是':v===false?'否':v==null?'—':String(v);const signed=(v,d=4)=>typeof v==='number'&&Number.isFinite(v)?(v>0?'+':'')+v.toFixed(d):'—';const current=()=>DATA.cases[active],qp=()=>current().source.endpoints[current().source.row.base_team_key],tp=()=>current().source.endpoints[current().source.row.team_key];
function world(p,bottom=null){const az=p[0]/1024*2*Math.PI,el=(.5-p[1]/512)*Math.PI,r=-1/Math.tan((.5-(bottom||p)[1]/512)*Math.PI);return[-Math.sin(az)*r,bottom?r*Math.tan(el):-1,Math.cos(az)*r]}
function project(v){let x=Math.atan2(-v[0],v[2])/(2*Math.PI);if(x<0)x+=1;return[x*1024,(.5-Math.atan2(v[1],Math.hypot(v[0],v[2]))/Math.PI)*512]}
function view(){return{z:+$('zoom').value,x:+$('cx').value,y:+$('cy').value}}
function map(p,c){const v=view(),s=c.width/(1024/v.z);return[(p[0]-v.x)*s+c.width/2,(p[1]-v.y)*s+c.height/2]}
function line(ctx,c,pts,color,width=2,dash=[]){ctx.lineCap='round';ctx.lineJoin='round';for(const shift of [-1024,0,1024]){for(const under of [true,false]){ctx.beginPath();let prev=null;for(const p of pts){if(!p||!p.every(Number.isFinite)){prev=null;continue}const v=map([p[0]+shift,p[1]],c);if(!prev||Math.abs(p[0]-prev[0])>512)ctx.moveTo(...v);else ctx.lineTo(...v);prev=p}ctx.strokeStyle=under?'rgba(0,0,0,.8)':color;ctx.lineWidth=under?width+2:width;ctx.setLineDash(under?[]:dash);ctx.stroke()}ctx.setLineDash([])}}
function marker(ctx,c,p,color,text){for(const dx of [-1024,0,1024]){const[x,y]=map([p[0]+dx,p[1]],c);if(x<-20||x>c.width+20||y<-20||y>c.height+20)continue;ctx.beginPath();ctx.arc(x,y,4,0,2*Math.PI);ctx.fillStyle=color;ctx.strokeStyle='#111';ctx.lineWidth=2;ctx.fill();ctx.stroke();if($('labels').checked&&text){ctx.font='bold 16px sans-serif';ctx.strokeStyle='rgba(0,0,0,.95)';ctx.lineWidth=4;ctx.strokeText(text,x+8,y-7);ctx.fillStyle=color;ctx.fillText(text,x+8,y-7)}}}
function curve(a,b){const out=[];for(let i=0;i<=96;i++){const t=i/96;out.push(project(a.map((v,k)=>v*(1-t)+b[k]*t)))}return out}
function layout(ctx,c,points,color,label,close,width=2){if(!points||points.length<2)return;const n=Math.floor(points.length/2);for(let i=0;i<n;i++){const t=points[2*i],b=points[2*i+1];line(ctx,c,curve(world(t,b),world(b)),color,width);marker(ctx,c,b,color,label+(i+1));if(close&&n>=3){const j=(i+1)%n,nt=points[2*j],nb=points[2*j+1];line(ctx,c,curve(world(b),world(nb)),color,width);line(ctx,c,curve(world(t,b),world(nt,nb)),color,width)}}}
function panorama(id,mode){const c=$(id),ctx=c.getContext('2d'),v=view(),s=c.width/(1024/v.z);ctx.fillStyle='#121a23';ctx.fillRect(0,0,c.width,c.height);if(img&&img.complete&&img.naturalWidth){for(const dx of [-1024,0,1024]){const[x,y]=map([dx,0],c);ctx.drawImage(img,x,y,1024*s,512*s)}}if($('reference').checked)layout(ctx,c,current().source.reference.points_1024x512,COL.R,'R',true,2);if(mode==='Q'||mode==='QT'){const e=mode==='Q'?qp():tp();layout(ctx,c,e.geometry.points,COL[mode],mode,e.score_status==='complete_conditional',3);if($('other').checked){const o=mode==='Q'?tp():qp(),k=mode==='Q'?'QT':'Q';layout(ctx,c,o.geometry.points,COL[k],k,o.score_status==='complete_conditional',2)}}else{if($('rawTeams').checked){for(const[k,e]of[['Q',qp()],['QT',tp()]])layout(ctx,c,e.geometry.points,COL[k],k,e.score_status==='complete_conditional',2)}const r=current().pool.records[+$('raw').value];if(r)layout(ctx,c,r.points,COL.raw,r.worker_id+'·',true,3)}ctx.fillStyle='rgba(12,20,30,.8)';ctx.fillRect(8,8,270,31);ctx.fillStyle='white';ctx.font='17px sans-serif';ctx.fillText(`${mode==='RAW'?'单人完整原答':mode+' 融合'} · ${v.z}× · 中心 (${fmt(v.x,0)},${fmt(v.y,0)})`,17,30)}
function bev(){const c=$('bevCanvas'),ctx=c.getContext('2d'),r=current().source.reference.floor_xz_h,geos=[['R',r,true],['Q',qp().geometry.footprint,qp().score_status==='complete_conditional'],['QT',tp().geometry.footprint,tp().score_status==='complete_conditional']];ctx.clearRect(0,0,c.width,c.height);const all=[...r,...qp().geometry.footprint,...tp().geometry.footprint,[0,0]],xs=all.map(p=>p[0]),zs=all.map(p=>p[1]),loX=Math.min(...xs),hiX=Math.max(...xs),loZ=Math.min(...zs),hiZ=Math.max(...zs),scale=Math.min((c.width-140)/(hiX-loX),(c.height-150)/(hiZ-loZ)),mx=(loX+hiX)/2,mz=(loZ+hiZ)/2,mp=p=>[c.width/2+(p[0]-mx)*scale,c.height/2-(p[1]-mz)*scale];ctx.font='18px sans-serif';ctx.fillStyle='#30445a';ctx.fillText('同一相机坐标中的完整底面',24,31);const ox=mp([0,0]);ctx.strokeStyle='#cbd5df';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(ox[0],50);ctx.lineTo(ox[0],c.height-40);ctx.moveTo(40,ox[1]);ctx.lineTo(c.width-40,ox[1]);ctx.stroke();ctx.fillStyle='#33485d';ctx.fillText('x / h →',c.width-100,ox[1]-10);ctx.fillText('z / h ↑',ox[0]+10,65);for(const[k,pts,close]of geos){if(k==='R'&&!$('reference').checked)continue;ctx.beginPath();pts.forEach((p,i)=>{const v=mp(p);i?ctx.lineTo(...v):ctx.moveTo(...v)});if(close)ctx.closePath();ctx.lineWidth=6;ctx.strokeStyle='#35404a';ctx.stroke();ctx.lineWidth=3;ctx.strokeStyle=COL[k];ctx.stroke();pts.forEach((p,i)=>{const[x,y]=mp(p);ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fillStyle=COL[k];ctx.fill();if($('labels').checked){ctx.font='16px sans-serif';ctx.strokeStyle='#35404a';ctx.lineWidth=3;ctx.strokeText(k+(i+1),x+7,y-6);ctx.fillText(k+(i+1),x+7,y-6)}})}ctx.beginPath();ctx.arc(...ox,5,0,Math.PI*2);ctx.fillStyle='#2b4358';ctx.fill();ctx.fillText('相机',ox[0]+10,ox[1]+22);const bar=1*scale;ctx.strokeStyle='#283e52';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(35,c.height-30);ctx.lineTo(35+bar,c.height-30);ctx.stroke();ctx.fillText('1 h',35,c.height-40)}
function render(){if(!img||!img.complete)return;panorama('qCanvas','Q');panorama('qtCanvas','QT');panorama('rawCanvas','RAW');bev();window.__exhibitReady=true;ready=true}
function metricRows(){const fields=[['B8L2','B8L2 ↑',6],['D10','D10 ↑',6],['iou_2d','底面 IoU ↑',6],['IoU3D100','IoU3D × 100 ↑',6],['boundary_loss','boundary_loss ↓',8],['direction_loss','direction_loss ↓',8],['height_loss','height_loss ↓',8],['global_height_loss','global_height_loss ↓',8],['local_height_loss','local_height_loss ↓',8],['S_bottom_deg','底面位置 S_bottom (°) ↓',6],['dir','内部正交方向 dir (°) ↓',6],['Hmean','Hmean ↓',6],['Hcenter','Hcenter ↓',6],['omission','遗漏比例 ↓',6],['extension','外扩比例 ↓',6],['nodes','输出节点数',0],['fusion_turn_n','有效转折数',0],['fusion_short_turn_edges','短转折边数',0],['fusion_redundancy_n','冗余数',0],['ref_node_recall_5','参考节点保留 (5)',6],['ref_node_recall_9','参考节点保留 (9)',6],['ref_edge_recall_5','参考结构边保留 (5)',6],['ref_edge_recall_9','参考结构边保留 (9)',6],['geometry_area_h2','底面面积 / h²',6],['centroid_x_h','底面质心 x / h',6],['centroid_z_h','底面质心 z / h',6],['height_mean_h','平均高度 / h',6],['recorded_time_total_seconds','合法同源记录劳动 (秒)',3],['source_time_known_n','同源劳动有记录人数',0],['recorded_time_eligible','记录劳动可比',0],['score_status','评分状态',0],['geometry_status','几何状态',0],['connection_available','连接可用',0]];return '<table><thead><tr><th>指标</th><th>Q</th><th>QT</th><th>Δ QT − Q</th></tr></thead><tbody>'+fields.map(([k,l,d])=>{let a=qp()[k],b=tp()[k];return `<tr><td>${l}<br><small>${k}</small></td><td>${esc(fmt(a,d))}</td><td>${esc(fmt(b,d))}</td><td>${typeof a==='number'&&typeof b==='number'?esc(signed(b-a,d)):'—'}</td></tr>`}).join('')+'</tbody></table>'}
function rawInfo(){const c=current(),r=c.pool.records[+$('raw').value],q=qp().member_workers.includes(r.worker_id),t=tp().member_workers.includes(r.worker_id),role=q&&t?'两队共同成员':q?'仅 Q 队':t?'仅 QT 队':'未入此两队';$('rawMeta').innerHTML=`<b>${esc(r.worker_id)} · ${role}</b>　B8L2 ${fmt(r.B8L2,4)} · D10 ${fmt(r.D10,4)}<br>原答 ${esc(r.object_id)} · ${r.points.length/2} 对顶/底点 · 同源记录秒数 ${fmt(r.source_time_seconds,3)}<br><small>${esc(r.time_source_kind)}；顺序 ${esc(r.order_used)}；ring_confirmed=${esc(r.ring_confirmed)}</small>`;$('rawJson').textContent=JSON.stringify(r,null,2);render()}
function tablePoints(){return[['Q',qp()],['QT',tp()]].map(([name,e])=>'<h3>'+name+'</h3><table><thead><tr><th>冻结序号</th><th>top x</th><th>top y</th><th>bottom x</th><th>bottom y</th><th>floor x / h</th><th>floor z / h</th></tr></thead><tbody>'+e.geometry.footprint.map((p,i)=>'<tr><td>'+(i+1)+'</td>'+[...e.geometry.points[2*i],...e.geometry.points[2*i+1],...p].map(v=>'<td>'+fmt(v,6)+'</td>').join('')+'</tr>').join('')+'</tbody></table>').join('')}
function setCase(i){active=i;window.__exhibitReady=false;ready=false;const c=current(),d=c.source,q=qp(),t=tp(),delta=t.B8L2-q.B8L2,dt=t.recorded_time_total_seconds-q.recorded_time_total_seconds;document.title=c.title+' · HOHONET v2.1';$('title').textContent=c.title;$('identity').textContent=`${d.target_meta.image} · ${d.target_meta.building} · ${d.target_meta.room_id} · ${d.target_meta.difficulty} · ${d.target_meta.layer} · 历史来源图 ${d.source_meta.image} · 当前图池 ${c.pool.records.length} 人`;$('summary').innerHTML=[['Q → QT · B8L2',fmt(q.B8L2,3)+' → '+fmt(t.B8L2,3)],['Δ B8L2',signed(delta,6)],['Q → QT · 记录秒数',fmt(q.recorded_time_total_seconds,3)+' → '+fmt(t.recorded_time_total_seconds,3)],['记录劳动变化',signed(dt,3)+' 秒 ('+signed(dt/q.recorded_time_total_seconds*100,2)+'%)']].map(([k,v])=>'<div class="metric"><small>'+k+'</small><div class="num">'+v+'</div></div>').join('');const common=q.member_workers.filter(w=>t.member_workers.includes(w)),out=q.member_workers.filter(w=>!t.member_workers.includes(w)),inc=t.member_workers.filter(w=>!q.member_workers.includes(w));$('members').innerHTML=`<p><b>Q 队：</b>${q.member_workers.join(' · ')}　<b>QT 队：</b>${t.member_workers.join(' · ')}</p><p><b>共同：</b>${common.join(' · ')}　<b>Q 换出：</b>${out.join(' · ')}　<b>QT 换入：</b>${inc.join(' · ')}</p><p class="foot muted">两队均从相同 ${d.row.available_workers} 人历史资格候选中选取：${esc(d.row.available_worker_ids)}。Q/QT 是本研究的历史策略简称，精确策略标识 ${esc(d.row.policy)}。</p>`;$('look').textContent=c.look;$('numbers').textContent=c.numbers;$('qHead').textContent='Q · B8L2 '+fmt(q.B8L2,6)+' / D10 '+fmt(q.D10,6);$('qtHead').textContent='QT · B8L2 '+fmt(t.B8L2,6)+' / D10 '+fmt(t.D10,6);$('qCap').textContent='Q 状态：'+q.score_status+'；geometry='+q.geometry_status+'；完整端点 '+q.nodes+' 节点';$('qtCap').textContent='QT 状态：'+t.score_status+'；geometry='+t.geometry_status+'；完整端点 '+t.nodes+' 节点';const indices=c.pool.records.map((r,i)=>({r,i,role:q.member_workers.includes(r.worker_id)&&t.member_workers.includes(r.worker_id)?0:q.member_workers.includes(r.worker_id)?1:t.member_workers.includes(r.worker_id)?2:3})).sort((a,b)=>a.role-b.role||a.r.worker_id.localeCompare(b.r.worker_id));$('raw').innerHTML=indices.map(({r,i,role})=>`<option value="${i}">${esc(r.worker_id)} · ${['两队共同','仅 Q','仅 QT','未入两队'][role]} · B8L2 ${fmt(r.B8L2,2)} · ${r.points.length/2} 角点</option>`).join('');$('metrics').innerHTML=metricRows();$('points').innerHTML=tablePoints();$('provenance').innerHTML=`冻结提交：${DATA.commit}<br>目标：${esc(d.reference.target_id)}<br>参考版本：${esc(d.reference.reference_version)}<br>Q team_key：${esc(q.team_key)}<br>QT team_key：${esc(t.team_key)}<br>案例源 SHA256：${c.source_sha256}<br>当前 INPUT SHA256：${DATA.input_sha256}<br>原图发布：${esc(c.image_receipt.source_url)}<br>ZIP member：${esc(c.image_receipt.archive_path)}<br>原图 CRC32：${c.image_receipt.zip_crc32}<br>原图 SHA256：${c.image_receipt.sha256}<br>当前完整原答池：${c.pool.records.length} 条；两队并集 ${d.target_raw_records.length} 条；源 JSON 同时保留历史图原答。`;$('zoom').value='1';$('cx').value='512';$('cy').value='256';$('other').checked=false;$('rawTeams').checked=false;img=new Image();img.onload=render;img.src=c.image_data;rawInfo()}
function download(name,text,type='application/json'){const u=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
$('case').innerHTML=DATA.cases.map((c,i)=>`<option value="${i}">${esc(c.title)}</option>`).join('');$('case').addEventListener('change',()=>setCase(+$('case').value));for(const id of ['zoom','cx','cy','reference','other','labels','rawTeams'])$(id).addEventListener('change',render);$('raw').addEventListener('change',rawInfo);$('full').onclick=()=>{$('zoom').value='1';$('cx').value='512';$('cy').value='256';render()};$('focus').onclick=()=>{const[x,y,z]=current().focus;$('zoom').value=String(z);$('cx').value=x;$('cy').value=y;render()};for(const id of ['qCanvas','qtCanvas','rawCanvas'])$(id).onclick=e=>{const c=$(id),r=c.getBoundingClientRect(),v=view(),dx=(e.clientX-r.left)/r.width-.5,dy=(e.clientY-r.top)/r.height-.5;$('cx').value=((v.x+dx*1024/v.z)%1024+1024)%1024;$('cy').value=Math.max(0,Math.min(512,v.y+dy*512/v.z));render()};$('downloadCase').onclick=()=>download(current().source_name,current().source_text);$('downloadPool').onclick=()=>download(current().pool.meta.image+'_full_target_pool.json',JSON.stringify(current().pool,null,2));$('downloadPng').onclick=()=>{const a=document.createElement('a');a.href=current().image_data;a.download=current().source.target_meta.image+'.png';a.click()};window.__exhibitCases=DATA.cases.length;window.__exhibitClosurePolicy='fusion_closed_only_complete_conditional';setCase(0);
</script></body></html>'''

def build(cases,receipts):
    input_path=ROOT/'source/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json'
    expected='18e7a9159ea3f13ff7ca4d649d09de4be0a93075c325fcb8ba5f8ad41fa3aa37'
    assert hashfile(input_path)==expected
    pools={p['pool_id']:p for p in load(input_path)['images']}
    data=[];index=[];checks=[];metrics=[]
    for name,d in zip(ORDER,cases):
        p=pools[d['target_meta']['pool_id']];by_id={r['object_id']:r for r in p['records']}
        assert p['meta']==d['target_meta'] and p['reference']==d['reference']
        for r in d['target_raw_records']:assert r==by_id[r['object_id']]
        q=d['endpoints'][d['row']['base_team_key']];t=d['endpoints'][d['row']['team_key']]
        assert len(q['member_workers'])==len(t['member_workers'])==5
        assert q['score_status']==t['score_status']=='complete_conditional'
        for e in [q,t]:
            assert e['reference_id']==d['target_meta']['reference_id']
            assert set(e['member_object_ids']) <= set(by_id)
            assert {by_id[x]['worker_id'] for x in e['member_object_ids']}==set(e['member_workers'])
            assert e['recorded_time_eligible'] and e['source_time_known_n']==5
            assert abs(sum(by_id[x]['source_time_seconds'] for x in e['member_object_ids'])-e['recorded_time_total_seconds'])<1e-8
            assert len(e['geometry']['points'])==2*len(e['geometry']['footprint'])==2*e['nodes']
        image=d['target_meta']['image'];file='case_'+image+'.html'
        poolpath=OUT/'full_target_pools'/(image+'.json');dump(poolpath,p)
        entry={**NOTES[name],'source':d,'source_name':name+'.json','source_text':(CASES/(name+'.json')).read_text(encoding='utf-8'),'source_sha256':hashfile(CASES/(name+'.json')),'pool':p,'image_receipt':receipts[image],'image_data':'data:image/png;base64,'+base64.b64encode((OUT/'originals'/(image+'.png')).read_bytes()).decode()}
        data.append(entry)
        index.append({'case':name,'image':image,'html':file,'source_case':'source_cases/'+name+'.json','full_target_pool':str(poolpath.relative_to(OUT)),'original':'originals/'+image+'.png','pool_records':len(p['records']),'team_union_records':len(d['target_raw_records']),'Q_team_key':q['team_key'],'QT_team_key':t['team_key'],'Q_B8L2':q['B8L2'],'QT_B8L2':t['B8L2'],'delta_B8L2':t['B8L2']-q['B8L2'],'Q_D10':q['D10'],'QT_D10':t['D10'],'Q_labor_seconds':q['recorded_time_total_seconds'],'QT_labor_seconds':t['recorded_time_total_seconds'],'Q_score_status':q['score_status'],'QT_score_status':t['score_status'],'source_case_sha256':entry['source_sha256'],'original_sha256':receipts[image]['sha256']})
        checks.append({'image':image,'case_exact_copy':hashfile(OUT/'source_cases'/(name+'.json'))==entry['source_sha256'],'full_pool_reference_meta_exact':True,'all_selected_raw_records_exact':True,'member_identity_validated':True,'same_source_labor_sum_validated':True,'full_geometry_point_count_validated':True,'Q_conditional_complete':True,'QT_conditional_complete':True,'pool_records':len(p['records'])})
        for k in ['B8L2','D10','iou_2d','IoU3D100','boundary_loss','direction_loss','height_loss','global_height_loss','local_height_loss','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9','geometry_area_h2','centroid_x_h','centroid_z_h','height_mean_h','recorded_time_total_seconds','score_status']:
            a,b=q.get(k),t.get(k);metrics.append({'case':name,'image':image,'metric':k,'Q':a,'QT':b,'delta_QT_minus_Q':b-a if isinstance(a,(int,float)) and isinstance(b,(int,float)) else None})
    common={'commit':COMMIT,'input_sha256':expected,'no_scientific_recalculation':True}
    def page(filename,entries):
        payload=json.dumps({**common,'cases':entries},ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
        links='<div class="download">'+''.join('<a href="'+r['html']+'">'+r['image']+' 独立页</a>' for r in index)+'</div>' if len(entries)>1 else ''
        dest=OUT/filename;dest.write_text(HTML.replace('__DATA__',payload).replace('__CASE_LINKS__',links),encoding='utf-8')
        txt=dest.read_text(encoding='utf-8');saved=json.loads(txt.split('<script id="dataset" type="application/json">',1)[1].split('</script>',1)[0]);assert len(saved['cases'])==len(entries)
        for e in saved['cases']:
            assert hashlib.sha256(base64.b64decode(e['image_data'].split(',',1)[1])).hexdigest()==e['image_receipt']['sha256']
            assert json.loads(e['source_text'])==e['source']
        return {'file':filename,'case_n':len(entries),'bytes':dest.stat().st_size,'sha256':hashfile(dest),'embedded_images_and_json_readback':True}
    html_checks=[page('index.html',data)]
    html_checks.extend(page(r['html'],[d]) for r,d in zip(index,data))
    csvsave(OUT/'EXHIBIT_INDEX.csv',index);csvsave(OUT/'Q_QT_FROZEN_METRICS.csv',metrics)
    for fn,n in [('EXHIBIT_INDEX.csv',4),('Q_QT_FROZEN_METRICS.csv',len(metrics))]:assert len(list(csv.DictReader((OUT/fn).open(encoding='utf-8-sig'))))==n
    receipt={'commit':COMMIT,'scientific_recomputation':False,'classification_changed':False,'stage05_modified':False,'four_existing_selected_cases_only':True,'case_n':4,'unique_endpoint_n':8,'full_target_record_n':sum(len(d['pool']['records']) for d in data),'selected_target_record_n':sum(len(d['source']['target_raw_records']) for d in data),'input_sha256':expected,'fused_closure_rule':'Only score_status=complete_conditional is drawn as a closed fused consensus; raw declaration and formal reference preserve their original complete record order.','original_source_receipt':'originals/ORIGINALS_RECEIPT.json','checks':checks,'html_checks':html_checks,'metric_row_n':len(metrics),'browser_validation':'BROWSER_VALIDATION.json (separate actual Chromium execution)'}
    dump(OUT/'BUILD_VALIDATION.json',receipt)
    readme='''# Q / QT 选队四案例：直接人工查看补充

本目录仅补充已有案例的原图及完整几何查看，不运行新选队、评分、融合或机制实验；不修改已冻结的 stage05。

## 入口

- [四案例总入口](index.html)：独立离线 HTML，原图、冻结案例 JSON、当前完整目标原答池均内嵌。
- [uNb-01 降质尾部](case_uNb9QFRL6hY-01.html)：重点检查 x≈905 的底部角点和相邻墙段。
- [uNb-43 降质尾部](case_uNb9QFRL6hY-43.html)：重点检查 x≈73–84 的短墙段附近；保存的方向损失变大，不以此代替人工判断。
- [uNb-12 升质但劳动增加](case_uNb9QFRL6hY-12.html)。
- [S9h-10 成员改变、融合几乎不变](case_S9hNv5qa7GM-10.html)。

浏览器打开即可；不依赖服务器或外部资源。点击“重点墙段”放大已有几何差异；两个团队与原答视口同步，可选择全部当前合法图池中的单人原答。原图 2048×1024，所有标注坐标为 1024×512；三维直墙段经 ERP 投影显示，接缝分段。底面使用冻结 footprint，保留点顺序。

## 证据及边界

`source_cases/` 为 4 份已选案例的逐字节副本；其中保留全部团队成员目标原答及历史来源原答、参考、完整两端点。`full_target_pools/` 增补从当前固定 INPUT 精确提取的 4 个合法目标池，共 138 份完整目标原答；只是供查看的上下文，不加入团队。`EXHIBIT_INDEX.csv` 可回连团队键、原图、案例 SHA 与数值；`Q_QT_FROZEN_METRICS.csv` 为已有端点分项的摘录，没有重评分。

本页仅对 `complete_conditional` 融合端点闭合显示；这 8 个端点均符合该条件。`ring_confirmed=false` 与顺序待人工确认状态原样保留。参考和原答保持其声明的完整记录顺序，不追加排序或人工确认。未取得专用完整候选轨迹，不能以总分或入选票数推断未入选节点、身份合并或连接机制。

原图来源为冻结发布 `quality-original-images-20261015`。1 张复用已验证本地原图，3 张只下载其 ZIP member 所需 byte ranges；CRC32、SHA256、归档 URL、成员路径及传输范围见 `originals/ORIGINALS_RECEIPT.json`。当前冻结提交为 `13a7861334749805a86dc19e9ea79fcaa71020c0`。

## 验证与复现

- `BUILD_VALIDATION.json`：成员、原答、参考、劳动合计、几何点数及 HTML 内嵌数据读回。
- `BROWSER_VALIDATION.json`：真实 Chromium 浏览器的离线打开、4 案切换、放大及原答选择检查。
- `browser_checks/`：验收截图。
- 脚本：研究根 `scripts/build_selection_case_exhibits.py`；运行 `python scripts/build_selection_case_exhibits.py` 只用已保存原图重新构建。仅当原图缺失时 `--fetch-images` 才会做冻结发布的有界获取。

这些是完整策略结果之后的解释案例，不是总体效果的分母或重新选型依据。总体均值、多数图与坏尾仍以冻结 `stage05_selection_stop/README.md`、报告及逐图表为准。
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    print(json.dumps({'html_files':[h['file'] for h in html_checks],'full_target_record_n':receipt['full_target_record_n'],'metric_rows':len(metrics),'output_bytes':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())},ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fetch-images',action='store_true');ap.add_argument('--images-only',action='store_true');args=ap.parse_args()
    cases,rows,zindex=initial_sources();r=images(rows,zindex,args.fetch_images)
    if not args.images_only:build(cases,r)

if __name__=='__main__':main()
