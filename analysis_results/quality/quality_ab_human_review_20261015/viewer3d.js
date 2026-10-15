'use strict';
const Review3D=(()=>{
  const initial={yaw:-35,pitch:25,zoom:1};
  let cam={...initial},bounds,panels=[];
  function draw(){
    for(const {canvas,reference,answer} of panels){
      const w=canvas.getBoundingClientRect().width,h=420,dpr=window.devicePixelRatio||1;
      canvas.width=Math.round(w*dpr);canvas.height=h*dpr;
      const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
      ctx.fillStyle='#fcfdfb';ctx.fillRect(0,0,w,h);ctx.font='12px system-ui';
      const project=p=>GeometryCore.project(p,bounds,cam,w,h);
      function line(a,b,color,width=1,dash=[]){const u=project(a),v=project(b);ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.moveTo(u.x,u.y);ctx.lineTo(v.x,v.y);ctx.stroke();}
      function label(p,t,color='#65776c'){const q=project(p);ctx.fillStyle=color;ctx.fillText(t,q.x+5,q.y-5);}
      const {lo,hi}=bounds;
      for(let i=0;i<=4;i++){
        const x=lo[0]+(hi[0]-lo[0])*i/4,z=lo[2]+(hi[2]-lo[2])*i/4,y=lo[1]+(hi[1]-lo[1])*i/4;
        line([x,-1,lo[2]],[x,-1,hi[2]],'#dde3df');
        line([lo[0],-1,z],[hi[0],-1,z],'#dde3df');
        line([lo[0],y,lo[2]],[hi[0],y,lo[2]],'#e6ebe7');
        label([x,-1,hi[2]],x.toFixed(1));label([hi[0],-1,z],z.toFixed(1));label([lo[0],y,lo[2]],(y+1).toFixed(1));
      }
      line([lo[0],lo[1],lo[2]],[lo[0],hi[1],lo[2]],'#97a69b');
      label([hi[0],-1,hi[2]],'x / h');label([hi[0],-1,lo[2]],'z / h');label([lo[0],hi[1],lo[2]],'离地高度 / h');
      for(const [g,color]of [[reference,'#218944'],[answer,'#d66c00']]){
        for(const key of ['bottom3d','top3d']){const ring=g[key];ring.forEach((p,i)=>line(p,ring[(i+1)%ring.length],color,2,key==='bottom3d'?[5,4]:[]));}
        g.bottom3d.forEach((p,i)=>line(p,g.top3d[i],color,1));
      }
      const origin=project([0,0,0]);ctx.setLineDash([]);ctx.strokeStyle='#111';ctx.lineWidth=2;
      ctx.beginPath();ctx.moveTo(origin.x-6,origin.y);ctx.lineTo(origin.x+6,origin.y);ctx.moveTo(origin.x,origin.y-6);ctx.lineTo(origin.x,origin.y+6);ctx.stroke();label([0,0,0],'相机','#111');
    }
  }
  function bind(canvas){
    let drag=null;
    canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};
    canvas.onpointermove=e=>{if(!drag)return;cam.yaw+=(e.clientX-drag[0])*.5;cam.pitch=Math.max(-89,Math.min(90,cam.pitch+(e.clientY-drag[1])*.5));drag=[e.clientX,e.clientY];draw();};
    canvas.onpointerup=canvas.onpointercancel=canvas.onlostpointercapture=()=>{drag=null;};
    canvas.addEventListener('wheel',e=>{e.preventDefault();cam.zoom=Math.max(.4,Math.min(4,cam.zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});
    canvas.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-'].includes(e.key))return;e.preventDefault();if(e.key==='ArrowLeft')cam.yaw-=5;if(e.key==='ArrowRight')cam.yaw+=5;if(e.key==='ArrowUp')cam.pitch=Math.min(90,cam.pitch+5);if(e.key==='ArrowDown')cam.pitch=Math.max(-89,cam.pitch-5);if(e.key==='+')cam.zoom=Math.min(4,cam.zoom*1.1);if(e.key==='-')cam.zoom=Math.max(.4,cam.zoom/1.1);draw();};
  }
  function open(card){
    const container=document.getElementById('geometry');container.replaceChildren();cam={...initial};
    panels=card.bindings.map(b=>{
      const section=document.createElement('div'),title=document.createElement('strong'),canvas=document.createElement('canvas');
      title.textContent=b.label+' · 绿＝参考，橙＝作答';canvas.tabIndex=0;canvas.setAttribute('aria-label',b.label+'三维布局，拖动或方向键旋转，滚轮或加减键缩放');
      section.append(title,canvas);container.append(section);bind(canvas);
      return {canvas,reference:GEOMETRIES[b.reference_object_id],answer:GEOMETRIES[b.object_id]};
    });
    const all=panels.flatMap(p=>[p.reference,p.answer]).flatMap(g=>[...g.bottom3d,...g.top3d]).concat([[0,0,0],[0,-1,0]]);
    const lo=[0,1,2].map(i=>Math.min(...all.map(p=>p[i]))),hi=[0,1,2].map(i=>Math.max(...all.map(p=>p[i])));
    const center=lo.map((v,i)=>(v+hi[i])/2),radius=Math.max(...all.map(p=>Math.hypot(...p.map((v,i)=>v-center[i]))));
    bounds={lo,hi,center,radius};draw();
  }
  for(const [id,view]of [['viewReset',initial],['viewTop',{yaw:0,pitch:90,zoom:1}],['viewFront',{yaw:0,pitch:0,zoom:1}]])document.getElementById(id).onclick=()=>{cam={...view};draw();};
  window.addEventListener('resize',()=>{if(panels.length)draw();});
  return {open};
})();
