'use strict';
// Reuse review36 rendering; this adapter only binds fixed cases and nonnumeric questions.
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg',storage='quality_pro_review_20261014_v1';
let im,A,B,G,texture,panoImg,views=[],syncing=false,displayMode='both',pan=[0,0,1024,512],current,visible=[],receipts={},loadToken=0;
function save(){if(!current?.questions.length)return;const answers={};for(const q of current.questions){const value=document.querySelector(`input[name="${q.id}"]:checked`)?.value||null;answers[q.id]={question:q.title,purpose:q.purpose,value,label:q.options.find(o=>o[0]===value)?.[1]||null}}
 if(!Object.values(answers).some(a=>a.value!==null)&&!$('comment').value)return;
 receipts[current.id]={case_id:current.id,source_pair:current.pair_id,image_id:current.image_id,bindings:current.bindings,answers,comment:$('comment').value,reviewed_at:new Date().toISOString()};
 try{localStorage.setItem(storage,JSON.stringify(receipts));$('saved').textContent='已在本地保存；完成后请导出'}catch(e){$('saved').textContent='本地保存失败，请立即导出回执'}}
function cameraMarker(v){const scale=Math.min(.18,Math.max(.06,bounds().radius*.025)),group=new THREE.Group();group.name='cameraMarker';
 const body=new THREE.Mesh(new THREE.BoxGeometry(scale*1.5,scale,scale),new THREE.MeshBasicMaterial({color:0xbd871d,depthTest:false}));body.renderOrder=20;group.add(body);
 const lens=new THREE.Mesh(new THREE.ConeGeometry(scale*.8,scale,12),new THREE.MeshBasicMaterial({color:0xf0c557,depthTest:false}));lens.rotation.x=-Math.PI/2;lens.position.z=-scale;lens.renderOrder=20;group.add(lens);
 const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0),new THREE.Vector3(0,-1,0)]),new THREE.LineDashedMaterial({color:0xa77513,dashSize:.07,gapSize:.045,depthTest:false}));line.computeLineDistances();group.add(line);
 const canvas=document.createElement('canvas');canvas.width=256;canvas.height=72;const ctx=canvas.getContext('2d');ctx.fillStyle='#fff4cd';ctx.fillRect(0,0,256,72);ctx.fillStyle='#6b4810';ctx.font='bold 36px sans-serif';ctx.textAlign='center';ctx.fillText('相机位置',128,49);
 const label=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),depthTest:false}));label.scale.set(scale*6,scale*1.7,1);label.position.set(0,scale*1.8,0);label.renderOrder=21;group.add(label);group.visible=!v.inside;v.group.add(group)}
function rebuild(reset=false){if(!views.length)return;renderModels(reset);views.forEach(cameraMarker);renderBEV();renderPano()}
async function loadCase(){const token=++loadToken;current=visible[$('case').selectedIndex];if(!current)return;
 $('count').textContent=($('case').selectedIndex+1)+' / '+visible.length;$('caseTitle').textContent=current.id+' · '+current.image_code;$('purpose').textContent=current.purpose;
 A=current.A;B=current.B;G=current.G;im={imageFile:current.photo,annotations:[A,B],groundtruths:[G]};pan=[0,0,1024,512];$('original').href=current.photo;
 $('static2d').src='review_assets/'+current.pair_id+'.jpg';$('static3d').src='review_assets/'+current.pair_id+'_3d.png';
 $('questions').replaceChildren();const prior=receipts[current.id];for(const q of current.questions){const f=document.createElement('fieldset'),l=document.createElement('legend'),p=document.createElement('p');l.textContent=q.title;p.textContent='用途：'+q.purpose;p.className='purpose';f.append(l,p);for(const [value,text]of q.options){const label=document.createElement('label'),input=document.createElement('input');label.className='answer';input.type='radio';input.name=q.id;input.value=value;input.checked=prior?.answers?.[q.id]?.value===value;label.append(input,document.createTextNode(text));f.append(label)}$('questions').append(f)}
 $('comment').value=prior?.comment||'';$('saved').textContent=prior?'已恢复本例回执':'';$('reviewHint').textContent=current.questions.length?'每题选一项；不确定可以直接选，不用勉强排序。':'本组只供备查，复用已有意见，不需要重复作答。';
 rebuild(true);const img=new Image();img.onload=()=>{if(token!==loadToken)return;panoImg=img;texture?.dispose();texture=new THREE.Texture(img);texture.needsUpdate=true;texture.wrapS=THREE.RepeatWrapping;texture.minFilter=THREE.LinearFilter;rebuild()};img.onerror=()=>{if(token===loadToken){$('fatal').hidden=false;$('fatal').textContent='原图未载入，请使用静态备份；不能仅凭模型判断照片语义。'}};img.src=current.photo_data;
}
function chooseMode(){save();visible=REVIEW_DATA.filter(c=>$('mode').value==='all'||c.questions.length);$('case').replaceChildren(...visible.map(c=>new Option(c.id+' · '+c.image_code,c.id)));loadCase()}
function startReview(){try{receipts=JSON.parse(localStorage.getItem(storage)||'{}')}catch(e){$('saved').textContent='历史回执读取失败，未覆盖旧值'}
 try{views=[createView('viewA'),createView('viewB')]}catch(e){$('fatal').hidden=false;$('fatal').textContent='三维WebGL暂不可用，可用下方静态二维/三维备份继续审核：'+e.message}
 $('mode').onchange=chooseMode;$('case').onchange=()=>{save();loadCase()};for(const [id,step]of [['prev',-1],['next',1]])$(id).onclick=()=>{const i=$('case').selectedIndex+step;if(i>=0&&i<visible.length){save();$('case').selectedIndex=i;loadCase()}};
 $('save').onclick=save;$('export').onclick=()=>{save();const blob=new Blob([JSON.stringify({schema:storage,decisions:Object.values(receipts)},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=storage+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 for(const id of ['showA','showB','showGT','pointLabels'])$(id).onchange=()=>rebuild();$('material').onchange=()=>rebuild();$('panoReset').onclick=()=>{pan=[0,0,1024,512];renderPano()};
 document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{preset(b.dataset.view);views.forEach(v=>{const m=v.group.getObjectByName('cameraMarker');if(m)m.visible=!v.inside})});
 document.querySelectorAll('[data-expand]').forEach(b=>b.onclick=()=>{$(b.dataset.expand).parentElement.classList.toggle('fullscreen')});
 function animate(){requestAnimationFrame(animate);views.forEach(v=>{if(v.control.enabled)v.control.update();v.renderer.render(v.scene,v.camera)})}animate();chooseMode();
}
