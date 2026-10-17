/* Read-only canvas viewer. Projection follows the repository's GeometryCore.project. */
(function(root){
'use strict';
const initial={yaw:-35,pitch:25,zoom:1};
const issueNames={ring_order_unconfirmed:'环序未确认',adjacent_pairing_unverified:'相邻上下点配对未确认',invalid_point_array:'坐标或点对数无效',wrong_hemisphere:'上下端点半球不符',near_horizon:'端点过于接近地平线',vertical_pair_mismatch:'上下端点水平位置不一致',invalid_footprint:'底环自交或面积无效',duplicate_or_zero_edge:'重复点或零长度边',camera_visibility_unresolved:'相机与房间可见关系待核查',pole_ray:'墙顶射线接近极点'};
function describe(g){
 if(!g)return '未提供 3D 数据';
 const status={available:'可显示',wireframe_warning:'原始线框',floor_only:'仅底面可还原',unavailable:'无法还原'}[g.status]||g.status;
 return status+(g.issues.length?'：'+g.issues.map(x=>issueNames[x]||x).join('；'):'');
}
function finitePoint(p){return Array.isArray(p)&&p.length===3&&p.every(Number.isFinite);}
function drawable(g){return g&&g.status!=='unavailable'&&g.floor.length>=3&&g.floor.every(finitePoint);}
function bounds(rows){
 const all=[[0,0,0],[0,-1,0]];
 for(const r of rows){const g=r.row.geometry3d;if(!drawable(g))continue;all.push(...g.floor);if(g.top.every(finitePoint))all.push(...g.top);}
 const lo=[0,1,2].map(i=>Math.min(...all.map(p=>p[i]))),hi=[0,1,2].map(i=>Math.max(...all.map(p=>p[i])));
 const center=lo.map((v,i)=>(v+hi[i])/2);
 return {lo,hi,center,radius:Math.max(.5,...all.map(p=>Math.hypot(...p.map((v,i)=>v-center[i]))))};
}
function project(p,b,cam,w,h){
 const [x,y,z]=p.map((v,i)=>v-b.center[i]),yaw=cam.yaw*Math.PI/180,pitch=cam.pitch*Math.PI/180;
 const u=x*Math.cos(yaw)-z*Math.sin(yaw),d=x*Math.sin(yaw)+z*Math.cos(yaw),v=y*Math.cos(pitch)-d*Math.sin(pitch);
 const scale=Math.min(w,h)*.40/b.radius*cam.zoom;
 return {x:w/2+u*scale,y:h/2-v*scale,depth:y*Math.sin(pitch)+d*Math.cos(pitch),scale};
}
function create(canvas,status){
 const ctx=canvas.getContext('2d');let cam={...initial},rows=[],box=bounds([]),alpha=.9,drag=null,draws=0;
 function draw(){
  if(canvas.hidden||canvas.parentElement?.hidden)return;
  const w=Math.max(240,canvas.getBoundingClientRect().width||640),h=420,dpr=root.devicePixelRatio||1;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#0b1420';ctx.fillRect(0,0,w,h);ctx.font='12px system-ui';ctx.lineJoin='round';
  const P=p=>project(p,box,cam,w,h);
  function line(a,b,color,width=1,dash=[]){const u=P(a),v=P(b);ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.moveTo(u.x,u.y);ctx.lineTo(v.x,v.y);ctx.stroke();}
  function label(p,t,color='#a6b6c9'){const q=P(p);ctx.fillStyle=color;ctx.fillText(t,q.x+6,q.y-6);}
  for(let i=0;i<=4;i++){const x=box.lo[0]+(box.hi[0]-box.lo[0])*i/4,z=box.lo[2]+(box.hi[2]-box.lo[2])*i/4;
   line([x,-1,box.lo[2]],[x,-1,box.hi[2]],'#243448');line([box.lo[0],-1,z],[box.hi[0],-1,z],'#243448');
   label([x,-1,box.hi[2]],x.toFixed(1));label([box.hi[0],-1,z],z.toFixed(1));}
  line([0,-1,0],[0,0,0],'#e5ebf2',1,[3,3]);label([0,-1,0],'地面 y/h = -1');label([0,0,0],'相机');
  const origin=P([0,0,0]);ctx.setLineDash([]);ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(origin.x,origin.y,4,0,Math.PI*2);ctx.fill();
  let drawn=0;
  ctx.globalAlpha=alpha;
  for(const item of rows){const g=item.row.geometry3d;if(!drawable(g))continue;drawn++;
   const rings=[g.floor];if(g.top.length===g.floor.length&&g.top.every(finitePoint))rings.push(g.top);
   rings.forEach((ring,j)=>ring.forEach((p,i)=>line(p,ring[(i+1)%ring.length],item.color,2,j===0?[6,4]:[])));
   if(rings.length===2)g.floor.forEach((p,i)=>line(p,g.top[i],item.color,1.4));
   rings.forEach(ring=>ring.forEach(p=>{const q=P(p);ctx.fillStyle=item.color;ctx.beginPath();ctx.arc(q.x,q.y,2.5,0,Math.PI*2);ctx.fill();}));
  }
  ctx.globalAlpha=1;ctx.setLineDash([]);
  label([box.hi[0],-1,box.hi[2]],'x/h');label([box.lo[0],-1,box.lo[2]],'z/h');
  if(!drawn){ctx.fillStyle='#b6c5d6';ctx.fillText(rows.length?'所选标注无法可靠还原，请查看状态说明。':'请勾选需要查看的标注。',20,30);}
  status.replaceChildren(...rows.map(item=>{const p=status.ownerDocument.createElement('p');p.textContent=item.title+'：'+(item.row.name||'未命名')+' · '+describe(item.row.geometry3d);return p;}));
  canvas.dataset.drawnCount=String(drawn);canvas.dataset.selectedCount=String(rows.length);draws++;
 }
 function preset(view){cam={...initial,...view};draw();}
 canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);canvas.focus();};
 canvas.onpointermove=e=>{if(!drag)return;cam.yaw+=(e.clientX-drag[0])*.5;cam.pitch=Math.max(-89,Math.min(90,cam.pitch+(e.clientY-drag[1])*.5));drag=[e.clientX,e.clientY];draw();};
 canvas.onpointerup=canvas.onpointercancel=canvas.onlostpointercapture=()=>{drag=null;};
 canvas.addEventListener('wheel',e=>{e.preventDefault();cam.zoom=Math.max(.2,Math.min(8,cam.zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});
 canvas.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-'].includes(e.key))return;e.preventDefault();
  if(e.key==='ArrowLeft')cam.yaw-=5;if(e.key==='ArrowRight')cam.yaw+=5;if(e.key==='ArrowUp')cam.pitch=Math.min(90,cam.pitch+5);if(e.key==='ArrowDown')cam.pitch=Math.max(-89,cam.pitch-5);
  if(e.key==='+'||e.key==='=')cam.zoom=Math.min(8,cam.zoom*1.1);if(e.key==='-')cam.zoom=Math.max(.2,cam.zoom/1.1);draw();};
 root.addEventListener('resize',draw);
 return {update(next,opacity){rows=next;alpha=opacity;box=bounds(rows);draw();},draw,
  reset:()=>preset(initial),top:()=>preset({yaw:0,pitch:90}),front:()=>preset({yaw:0,pitch:0}),
  snapshot:()=>({camera:{...cam},bounds:box,selected:rows.length,draws})};
}
const api={create,project,bounds,describe,drawable};root.SimulatedReview3D=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
