'use strict';
// Projection paths and 3D wall construction retained from the prior review viewer.
function svgEl(tag,attrs){const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));return n}
function renderPano(){if(!im)return;const s=$('pano');s.replaceChildren();s.setAttribute('viewBox',pan.join(' '));s.append(svgEl('image',{href:im.imageFile,width:1024,height:512}));for(const [r,color,on]of [[A,'#12c4dc',displayMode!=='B'&&$('showA').checked],[B,'#ffb746',displayMode!=='A'&&$('showB').checked],[G,'#db8aff',$('showGT').checked]]){if(!r||!on)continue;for(const path of r.erpPaths||[]){for(const seg of path.segments){const d=seg.map((p,i)=>(i?'L':'M')+p[0]+','+p[1]).join(' ');s.append(svgEl('path',{d,fill:'none',stroke:'#09202d','stroke-width':2.7,'vector-effect':'non-scaling-stroke',opacity:.7}));s.append(svgEl('path',{d,fill:'none',stroke:color,'stroke-width':r===G?1.7:1.3,'stroke-dasharray':r===G?'5 3':'none','vector-effect':'non-scaling-stroke'}))}}if(r===G&&!$('pointLabels').checked)continue;r.points.forEach((p,i)=>{const c=svgEl('circle',{cx:p[0],cy:p[1],r:2.5,fill:color,stroke:'#142c3d','stroke-width':.6});c.style.cursor='pointer';c.onclick=e=>{e.stopPropagation();showCrop(r,p,i)};s.append(c);if($('pointLabels').checked&&i%2===0){const t=svgEl('text',{x:p[0]+4,y:p[1]-5,fill:'white','font-size':9,stroke:'#142c3d','stroke-width':2,'paint-order':'stroke'});t.textContent=(r===G?'G':'')+(1+Math.floor(i/2));s.append(t)}})}}
function showCrop(r,p,i){if(!panoImg?.complete)return;const c=$('crop'),ctx=c.getContext('2d');ctx.fillStyle='#122734';ctx.fillRect(0,0,c.width,c.height);const w=240,h=133,sx=p[0]-w/2,sy=p[1]-h/2;for(let k=-1;k<=1;k++)ctx.drawImage(panoImg,(k*1024-sx)*c.width/w,-sy*c.height/h,1024*c.width/w,512*c.height/h);ctx.strokeStyle='#09d9ef';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(c.width/2-12,c.height/2);ctx.lineTo(c.width/2+12,c.height/2);ctx.moveTo(c.width/2,c.height/2-12);ctx.lineTo(c.width/2,c.height/2+12);ctx.stroke();$('detailTitle').textContent=`${r.reviewId||'GT'} · 点对${1+Math.floor(i/2)} · ${i%2?'下端点':'上端点'}`;$('detail').showModal()}
function createView(host){const scene=new THREE.Scene();scene.background=new THREE.Color('#eaf0f4');const camera=new THREE.PerspectiveCamera(48,1,.001,1000);const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));$(host).append(renderer.domElement);const control=new THREE.OrbitControls(camera,renderer.domElement);control.enableDamping=true;scene.add(new THREE.HemisphereLight(0xffffff,0x72899a,1.1));const light=new THREE.DirectionalLight(0xffffff,.8);light.position.set(2,7,4);scene.add(light);const group=new THREE.Group();scene.add(group);const v={scene,camera,renderer,control,group,host,inside:false,yaw:0,pitch:0};let idrag=null;renderer.domElement.addEventListener('pointerdown',e=>{if(v.inside){idrag=[e.clientX,e.clientY,v.yaw,v.pitch];renderer.domElement.setPointerCapture(e.pointerId)}});renderer.domElement.addEventListener('pointermove',e=>{if(!idrag)return;v.yaw=idrag[2]-(e.clientX-idrag[0])*.006;v.pitch=Math.max(-1.45,Math.min(1.45,idrag[3]+(e.clientY-idrag[1])*.006));const targets=$('sync').checked?views:[v];targets.forEach(w=>{w.yaw=v.yaw;w.pitch=v.pitch;w.camera.position.set(0,0,0);w.camera.lookAt(Math.sin(v.yaw)*Math.cos(v.pitch),Math.sin(v.pitch),-Math.cos(v.yaw)*Math.cos(v.pitch))})});renderer.domElement.addEventListener('pointerup',()=>idrag=null);renderer.domElement.addEventListener('pointercancel',()=>idrag=null);control.addEventListener('change',()=>{if(syncing||!$('sync').checked)return;syncing=true;views.forEach(w=>{if(w===v)return;w.camera.position.copy(camera.position);w.camera.quaternion.copy(camera.quaternion);w.control.target.copy(control.target);w.camera.fov=camera.fov;w.camera.updateProjectionMatrix()});syncing=false});const ro=new ResizeObserver(()=>{const el=$(host),w=el.clientWidth,h=el.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix()});ro.observe($(host));return v}
function clearGroup(g){while(g.children.length){const o=g.children[0];g.remove(o);o.geometry?.dispose();if(Array.isArray(o.material))o.material.forEach(m=>m.dispose());else o.material?.dispose()}}
function mat(color){if($('material').value==='texture'&&texture)return new THREE.ShaderMaterial({uniforms:{pano:{value:texture}},side:THREE.DoubleSide,vertexShader:'varying vec3 p;void main(){p=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',fragmentShader:'uniform sampler2D pano;varying vec3 p;void main(){float u=.5+atan(p.x,-p.z)/6.28318530718;float v=.5+atan(p.y,length(p.xz))/3.14159265359;gl_FragColor=vec4(texture2D(pano,vec2(u,v)).rgb,1.0);}'});return new THREE.MeshStandardMaterial({color,side:THREE.DoubleSide,roughness:1,transparent:true,opacity:.62})}
function model(v,r,color){clearGroup(v.group);const t=r.top3d,b=r.bottom3d;if(!t||!b){return}const n=b.length;for(let i=0;i<n;i++){let j=(i+1)%n;const pts=[b[i],b[j],t[j],t[i]];if($('material').value!=='wire'){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute([0,1,2,0,2,3].flatMap(k=>pts[k]),3));g.computeVertexNormals();v.group.add(new THREE.Mesh(g,mat(color)))}const line=new THREE.BufferGeometry().setFromPoints([...pts,pts[0]].map(p=>new THREE.Vector3(...p)));v.group.add(new THREE.Line(line,new THREE.LineBasicMaterial({color})))}const axis=new THREE.AxesHelper(.25);v.group.add(axis)}
function preset(kind){if(!A)return;const {center,radius}=bounds();views.forEach(v=>{v.inside=kind==='inside';v.control.enabled=!v.inside;v.control.enablePan=kind!=='inside';v.control.enableZoom=kind!=='inside';v.camera.fov=kind==='inside'?80:48;if(kind==='inside'){v.yaw=0;v.pitch=0;v.camera.position.set(0,0,0);v.camera.lookAt(0,0,-1);v.control.target.set(0,0,-1);v.control.minDistance=1;v.control.maxDistance=1;}else{v.control.minDistance=.02;v.control.maxDistance=radius*30;v.control.target.copy(center);v.camera.position.copy(center).add(kind==='top'?new THREE.Vector3(.001,radius*2.8,.001):new THREE.Vector3(radius*1.6,radius*1.2,radius*1.9))}v.camera.near=.001;v.camera.far=radius*100+100;v.camera.updateProjectionMatrix();if(v.control.enabled)v.control.update()})}
function addGT(v){if(!$('showGT').checked)return;const r=G,t=r.top3d,b=r.bottom3d;if(!t||!b)return;const paths=[t.concat([t[0]]),b.concat([b[0]]),...t.map((p,i)=>[p,b[i]])];for(const ps of paths){const g=new THREE.BufferGeometry().setFromPoints(ps.map(p=>new THREE.Vector3(...p)));const line=new THREE.Line(g,new THREE.LineDashedMaterial({color:0xba69d4,dashSize:.06,gapSize:.035,transparent:true,opacity:.9,depthTest:false}));line.computeLineDistances();v.group.add(line)}}
function setDisplay(mode){displayMode=mode;document.querySelector('.stage').dataset.display=mode;document.querySelectorAll('[data-display]').forEach(b=>{b.classList.toggle('active',b.dataset.display===mode);b.setAttribute('aria-pressed',String(b.dataset.display===mode))});$('showA').checked=mode!=='B';$('showB').checked=mode!=='A';$('showA').disabled=mode==='B';$('showB').disabled=mode==='A';renderPano();renderList();renderMetrics();renderBEV()}
function renderModels(reset){if(!A||!B||!views.length)return;model(views[0],A,0x008ca5);model(views[1],B,0xc8881a);views.forEach(addGT);if(reset)preset('iso')}
function bounds() {
  const ps = im.annotations.concat(im.groundtruths).flatMap(r => [...(r.top3d || []), ...(r.bottom3d || [])]);
  const box = new THREE.Box3().setFromPoints(ps.map(p => new THREE.Vector3(...p)));
  return { center: box.getCenter(new THREE.Vector3()), radius: Math.max(box.getSize(new THREE.Vector3()).length() / 2, .5) };
}
function renderBEV() {
  const all = im.annotations.concat(im.groundtruths).flatMap(r => r.bottom3d || []);
  const xs = all.map(p => p[0]), zs = all.map(p => p[2]);
  const minX = Math.min(...xs, 0), maxX = Math.max(...xs, 0), minZ = Math.min(...zs, 0), maxZ = Math.max(...zs, 0);
  const scale = Math.min(530 / Math.max(maxX - minX, .1), 290 / Math.max(maxZ - minZ, .1));
  const center = [(minX + maxX) / 2, (minZ + maxZ) / 2];
  const xy = p => [320 + (p[0] - center[0]) * scale, 190 - (p[2] - center[1]) * scale];
  for (const [id, r] of [['bevA', A], ['bevB', B]]) {
    const svg = $(id); svg.replaceChildren();
    for (let j = 0; j <= 4; j++) {
      const xv = minX + (maxX - minX) * j / 4, zv = minZ + (maxZ - minZ) * j / 4;
      const x = xy([xv,0,0])[0], y = xy([0,0,zv])[1];
      svg.append(svgEl('line',{x1:x,y1:30,x2:x,y2:345,stroke:'#dce5eb'}));
      svg.append(svgEl('line',{x1:40,y1:y,x2:610,y2:y,stroke:'#dce5eb'}));
      const tx=svgEl('text',{x,y:367,'text-anchor':'middle','font-size':14,fill:'#546c7b'});tx.textContent=xv.toFixed(1);svg.append(tx);
      const tz=svgEl('text',{x:35,y:y+5,'text-anchor':'end','font-size':14,fill:'#546c7b'});tz.textContent=zv.toFixed(1);svg.append(tz);
    }
    function path(obj,color,isGT) {
      if (!obj?.bottom3d?.length) return;
      const pts = obj.bottom3d.concat([obj.bottom3d[0]]).map(xy);
      svg.append(svgEl('path',{d:pts.map((p,i)=>(i?'L':'M')+p.join(',')).join(' '),fill:isGT?'none':'#18799d0b',stroke:color,'stroke-width':isGT?2:2.7,'stroke-dasharray':isGT?'7 4':'none'}));
      if (!isGT) pts.slice(0,-1).forEach((p,i)=>{
        const c=svgEl('circle',{cx:p[0],cy:p[1],r:3.4,fill:color});svg.append(c);
        if ($('pointLabels').checked) { const t=svgEl('text',{x:p[0]+5,y:p[1]-5,'font-size':13,fill:color});t.textContent=i+1;svg.append(t); }
      });
    }
    if ($('showGT').checked) path(G,'#ad6dc5',true);
    path(r, id==='bevA'?'#157a9b':'#b8791b',false);
    const c=xy([0,0,0]);svg.append(svgEl('path',{d:`M${c[0]-5},${c[1]-5}l10,10m-10,0l10,-10`,stroke:'#152f42','stroke-width':2}));
    const cam=svgEl('text',{x:c[0]+7,y:c[1]+16,'font-size':13,fill:'#152f42'});cam.textContent='相机';svg.append(cam);
  }
  $('bevTitleA').textContent='A · '+A.reviewId+' · 原底部连接';
  $('bevTitleB').textContent='B · '+B.reviewId+' · 原底部连接';
}
