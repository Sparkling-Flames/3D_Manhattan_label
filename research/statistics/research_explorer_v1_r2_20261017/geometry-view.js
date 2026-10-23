/* Read-only ERP / BEV / 3D. Projection conventions follow the existing gallery. */
window.WorkbenchGeometry=(()=>{
const C=window.WorkbenchCore,esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors={reference:'#7c3aed',answer:'#087f8c',fusion:'#b45309',raw:'#dc2626',received:'#e87914',initial:'#4f46e5'};
function mount(host,image,answer,reference,extra=null,options={}){
 if(!host)return;
 let mode='erp',yaw=-35,pitch=25,zoom=1,erpView=[0,0,1024,512];
 const layers=[{id:'reference',label:'查看参考',points:reference?.points,floor:reference?.floor,confirmed:true},
  {id:'answer',label:'个人作答',color:answer?.color,highlight:answer?.highlight,points:answer?.points,raw:answer?.raw_points,confirmed:!!answer?.points},
  {id:'fusion',label:'已保存融合',points:extra?.points,floor:extra?.footprint,confirmed:extra?.connected===true},
  {id:'raw',label:'原始导出散点',raw:answer?.raw_points,visible:false},
  {id:'received',label:'本轮预处理前散点',raw:answer?.before_preprocessing_points,visible:false},
  {id:'initial',label:'有绑定证据的Semi初始化',points:answer?.evidence?.semi_evidence?.initialization_points,confirmed:true,visible:false}]
 .concat(options.layers||[]).filter(l=>l.points||l.floor||l.raw).map(l=>({...l,color:l.color||colors[l.id]||'#64748b',visible:l.visible??true}));
 host.className='geometry';
 host.innerHTML=`<div class="geom-controls"><label>视图 <select data-view aria-label="几何视图"><option value="erp">原图叠线</option><option value="bev">BEV俯视</option><option value="3d">3D线框</option></select></label><button data-full>放大／全屏</button><button data-reset>重置视角</button><button data-zoom-in>局部放大＋</button><button data-zoom-out>缩小－</button><label><input type="checkbox" data-labels>点号（0基）</label><label><input type="checkbox" data-top checked>顶界</label><label>叠线 <input data-opacity type="range" min=".2" max="1" step=".1" value="${options.layers?.length ? 0.4 : 1}" aria-label="叠线不透明度"></label></div><div class="legend">${layers.map(l=>`<label><input type="checkbox" data-layer="${l.id}" ${l.visible?'checked':''}><i style="border-color:${l.color};border-top-style:${l.id==='reference'?'dashed':l.id==='fusion'?'dotted':'solid'}"></i>${l.label}</label>`).join('')}</div><div class="geom-photo"><svg viewBox="0 0 1024 512" role="img" aria-label="原图标注与空间参考叠线"></svg></div><canvas class="geom-canvas" hidden tabindex="0" aria-label="几何线框；方向键旋转，加减键缩放"></canvas><div class="geostatus">相机高度单位h，非实测米。${answer?.order_status?'作答环序状态：'+esc(answer.order_status)+'；连线沿用冻结输入，不表示本轮人工重审。 ' :''}${!reference?.points&&reference?.floor?'参考仅底面；不生成未知顶界。 ':''}${answer&&!answer.points?'作答仅原始散点或坐标不可用；不连接为确认环。 ':''}${extra&&!extra.connected?'融合环序未获确认，仅显示保存点和可用底面；不连接为完整布局。 ':''}${answer?.geometry_binding_reasons?.length?'坐标隔离原因：'+esc(answer.geometry_binding_reasons.join('、'))+'。 ':''}点号来自各自数组，不等于跨作答墙角身份。切换参考仅供查看，不改变评分绑定。</div>`;
 const photo=host.querySelector('.geom-photo'),svg=host.querySelector('svg'),canvas=host.querySelector('canvas');
 photo.style.aspectRatio='2 / 1';photo.style.minHeight='0';photo.style.overflow='hidden';
 const projectERP=([x,y,z])=>[((Math.atan2(x,-z)/(2*Math.PI)+.5)*1024+1024)%1024,(.5-Math.atan2(y,Math.hypot(x,z))/Math.PI)*512];
 function segments(l){
  if(l.points&&l.confirmed){const g=C.geometry(l.points);if(!g)return [];
   const lines=[];for(const ring of [g.bottom,...(host.querySelector('[data-top]').checked?[g.top]:[])]){
    ring.forEach((a,i)=>{const b=ring[(i+1)%ring.length];let old=projectERP(a);
     for(let n=1;n<=40;n++){const p=projectERP(a.map((x,k)=>x+(b[k]-x)*n/40));lines.push(...C.wrapSegment(old,p));old=p;}
    });
   }
   if(host.querySelector('[data-top]').checked)g.bottom.forEach((p,i)=>lines.push(...C.wrapSegment(projectERP(p),projectERP(g.top[i]))));
   return lines;
  }
  return l.floor?C.projectFloor(l.floor):[];
 }
 function draw(){
  const opacity=host.querySelector('[data-opacity]').value,labels=host.querySelector('[data-labels]').checked;
  photo.hidden=mode!=='erp';canvas.hidden=mode==='erp';
  if(mode==='erp'){
   svg.setAttribute('viewBox',erpView.join(' '));
   svg.innerHTML=(image?.photo?`<image href="${esc(image.photo)}" width="1024" height="512"/>`:'<text x="20" y="35">原图未接入；几何仍可查</text>')+layers.filter(l=>l.visible).map(l=>{
    const path=segments(l).map(([a,b])=>`M${a[0]} ${a[1]}L${b[0]} ${b[1]}`).join('');
    const pts=l.points||l.raw||[],dash=l.id==='reference'?'8 5':l.id==='fusion'?'3 4':'';
    return `<g opacity="${opacity}"><path d="${path}" fill="none" stroke="#fff" stroke-width="5"/><path d="${path}" fill="none" stroke="${l.color}" stroke-width="${l.highlight?4:2.2}" stroke-dasharray="${dash}"/>${pts.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="2.5" fill="${l.color}" stroke="white"/><title>${esc(l.label)} · 点${i}</title>${labels?`<text class="pointline" x="${p[0]+5}" y="${p[1]-5}">${i}</text>`:''}`).join('')}</g>`;
   }).join('');return;
  }
  const w=canvas.getBoundingClientRect().width||600,h=canvas.getBoundingClientRect().height||350,dpr=devicePixelRatio||1;
  canvas.width=w*dpr;canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
  const gs=layers.filter(l=>l.visible).map(l=>({l,g:l.points&&l.confirmed?C.geometry(l.points):l.floor?{bottom:l.floor.map(([x,z])=>[x,-1,z]),top:[]}:null})).filter(x=>x.g);
  const all=gs.flatMap(x=>[...x.g.bottom,...x.g.top]).concat([[0,-1,0]]);
  if(all.length===1){ctx.fillStyle='#526171';ctx.fillText('没有已确认可连接的几何；请查看原图散点。',20,40);return;}
  const lo=[0,1,2].map(i=>Math.min(...all.map(p=>p[i]))),hi=[0,1,2].map(i=>Math.max(...all.map(p=>p[i]))),center=lo.map((x,i)=>(x+hi[i])/2);
  const radius=Math.max(...all.map(p=>Math.hypot(...p.map((x,i)=>x-center[i]))),.01),scale=Math.min(w,h)*.4/radius*zoom;
  const project=p=>{const [x,y,z]=p.map((x,i)=>x-center[i]);if(mode==='bev')return [w/2+x*scale,h/2+z*scale];
   const a=yaw*Math.PI/180,b=pitch*Math.PI/180,u=x*Math.cos(a)-z*Math.sin(a),d=x*Math.sin(a)+z*Math.cos(a);return [w/2+u*scale,h/2-(y*Math.cos(b)-d*Math.sin(b))*scale];};
  for(const {l,g} of gs){ctx.strokeStyle=l.color;ctx.fillStyle=l.color;ctx.lineWidth=l.highlight?4:2;ctx.globalAlpha=Number(opacity);ctx.setLineDash(l.id==='reference'?[6,4]:l.id==='fusion'?[2,4]:[]);
   const line=(a,b)=>{const u=project(a),v=project(b);ctx.beginPath();ctx.moveTo(...u);ctx.lineTo(...v);ctx.stroke();};
   for(const ring of [g.bottom,...(mode==='3d'&&host.querySelector('[data-top]').checked?[g.top]:[])])ring.forEach((p,i)=>{line(p,ring[(i+1)%ring.length]);if(labels)ctx.fillText(String(i),...project(p));});
   if(mode==='3d'&&host.querySelector('[data-top]').checked)g.top.forEach((p,i)=>line(p,g.bottom[i]));
  }
  ctx.globalAlpha=1;ctx.setLineDash([]);ctx.fillStyle='#243247';const origin=project([0,-1,0]);ctx.fillRect(origin[0]-3,origin[1]-3,6,6);ctx.fillText('相机 / h',origin[0]+7,origin[1]);
 }
 host.querySelector('[data-view]').onchange=e=>{mode=e.target.value;draw();};
 host.querySelector('[data-full]').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen();else host.requestFullscreen().catch(()=>{});};
 host.querySelector('[data-reset]').onclick=()=>{yaw=-35;pitch=25;zoom=1;erpView=[0,0,1024,512];draw();};
 host.querySelectorAll('input').forEach(input=>input.oninput=()=>{const layer=layers.find(l=>l.id===input.dataset.layer);if(layer)layer.visible=input.checked;draw();});
 host.querySelector('img')?.addEventListener('error',e=>{e.target.replaceWith(Object.assign(document.createElement('p'),{textContent:'原图文件缺失；数值与几何仍可查。'}));});
 let drag=null;canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};
 canvas.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.5;pitch=Math.max(-89,Math.min(89,pitch+(e.clientY-drag[1])*.5));drag=[e.clientX,e.clientY];draw();};
 canvas.onpointerup=canvas.onpointercancel=()=>{drag=null;};
 canvas.onwheel=e=>{e.preventDefault();zoom=Math.max(.2,Math.min(8,zoom*Math.exp(-e.deltaY*.001)));draw();};
 canvas.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-'].includes(e.key))return;e.preventDefault();if(e.key==='ArrowLeft')yaw-=5;if(e.key==='ArrowRight')yaw+=5;if(e.key==='ArrowUp')pitch+=5;if(e.key==='ArrowDown')pitch-=5;if(e.key==='+')zoom*=1.1;if(e.key==='-')zoom/=1.1;draw();};
 function focus(rect){const [x0,x1,y0,y1]=rect,w=Math.min(1024,Math.max(64,x1-x0,(y1-y0)*2)),h=w/2;erpView=[Math.max(0,Math.min(1024-w,(x0+x1-w)/2)),Math.max(0,Math.min(512-h,(y0+y1-h)/2)),w,h];draw();}
 function erpZoom(factor,cx=erpView[0]+erpView[2]/2,cy=erpView[1]+erpView[3]/2){const w=Math.max(64,Math.min(1024,erpView[2]*factor));focus([cx-w/2,cx+w/2,cy-w/4,cy+w/4]);}
 host.querySelector('[data-zoom-in]').onclick=()=>mode==='erp'?erpZoom(.5):(zoom*=1.5,draw());
 host.querySelector('[data-zoom-out]').onclick=()=>mode==='erp'?erpZoom(2):(zoom/=1.5,draw());
 photo.style.touchAction='none';let pan=null;
 photo.onwheel=e=>{if(mode!=='erp')return;e.preventDefault();const b=photo.getBoundingClientRect();erpZoom(Math.exp(e.deltaY*.001),erpView[0]+(e.clientX-b.left)/b.width*erpView[2],erpView[1]+(e.clientY-b.top)/b.height*erpView[3]);};
 photo.onpointerdown=e=>{pan=[e.clientX,e.clientY,...erpView];photo.setPointerCapture(e.pointerId);};
 photo.onpointermove=e=>{if(!pan)return;const b=photo.getBoundingClientRect();erpView=[Math.max(0,Math.min(1024-pan[4],pan[2]-(e.clientX-pan[0])/b.width*pan[4])),Math.max(0,Math.min(512-pan[5],pan[3]-(e.clientY-pan[1])/b.height*pan[5])),pan[4],pan[5]];draw();};
 photo.onpointerup=photo.onpointercancel=()=>{pan=null;};
 if(options.focus)focus(options.focus);
 const observer=new ResizeObserver(()=>{if(!host.isConnected)observer.disconnect();else draw();});observer.observe(host);draw();return {focus};
}
return {mount};
})();
