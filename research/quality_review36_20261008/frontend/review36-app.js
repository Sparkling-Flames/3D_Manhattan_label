'use strict';
const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
const Core = Review36Core;
let DATA, records, im, A, B, G, texture, panoImg, views = [], syncing = false;
let displayMode = 'A', pan = [0,0,1024,512], drag = null, ratings = {}, exposures = {};
let storageReady = true;
const fmt = (v,n=3) => v == null || !Number.isFinite(+v) ? 'NA' : (+v).toFixed(n);
const opt = (v,t) => new Option(t,v);
const recName = r => r.reviewId ? `${r.reviewId} · ${r.pairCount}对点` : 'GT';
const referenceName = version => version === 'manual_revision' ? '修订GT' : '原GT';
function allContext() { return { records, dataSnapshot: DATA.selection36.datasetFingerprintSha256 }; }
function viewingContext(){return {referenceVersion:G.version,referenceId:G.id,gtVisible:$('showGT').checked,displayMode,metricsVisible:$('metricDetails').open};}
function activeReference() { return im.groundtruths.find(r => r.version === $('referenceSelect').value); }
function exposure() {
  const e = exposures[A.reviewId] ||= { metricsSeen:false, referencesSeen:[], comparedRecordIds:[] };
  if ($('showGT').checked && !e.referencesSeen.includes(G.version)) e.referencesSeen.push(G.version);
  if (displayMode !== 'A' && B.id !== A.id && !e.comparedRecordIds.includes(B.id)) e.comparedRecordIds.push(B.id);
  if ($('metricDetails').open) e.metricsSeen = true;
  return e;
}
function persist() {
  try {
    const text = JSON.stringify(Core.makeExport(ratings, allContext()));
    if (storageReady) {
      const previous = localStorage.getItem(Core.STORAGE);
      if (previous) localStorage.setItem(Core.STORAGE+'-backup', previous);
      localStorage.setItem(Core.STORAGE, text);
      $('saveWarning').hidden = true;
      return true;
    }
  } catch (error) { storageReady = false; }
  $('saveWarning').hidden = false;
  $('saveWarning').textContent = '浏览器保存失败。当前意见仍在本页内存中，请立即导出JSON，关闭页面后可能丢失。';
  return false;
}
function saveExposure() {
  const e=exposure(), r=ratings[A.reviewId];
  if (!r) { saveRating(); return; }
  if (r) {
    r.metricsSeen ||= e.metricsSeen;
    r.referencesSeen = [...new Set([...(r.referencesSeen || []), ...e.referencesSeen])];
    r.comparedRecordIds = [...new Set([...(r.comparedRecordIds || []), ...e.comparedRecordIds])];
    r.lastViewingContext=viewingContext();
    r.updatedAt=new Date().toISOString();
    persist();
  }
}
function renderProgress() {
  const p=Core.progress(ratings,records);
  $('progressText').textContent=`${p.handled} / ${p.total} 已处理`;
  $('progressDetail').textContent=`已评分 ${p.rated} · 无法判断 ${p.unable}`;
  $('progressBar').value=p.handled;
}
function renderList() {
  $('recordList').replaceChildren();
  for (const r of im.annotations) {
    const saved=ratings[r.reviewId];
    const bt=document.createElement('button');
    bt.className='record'+(r.id===(displayMode==='B'?B?.id:A?.id)?' active':'');
    const title=document.createElement('span');title.textContent=r.reviewId;
    const pairs=document.createElement('small');pairs.textContent=r.pairCount+' 对点';title.append(pairs);
    const mark=document.createElement('span');mark.className='mark';
    mark.textContent=saved?.status==='rated'?'已评分':saved?.status==='unable'?'无法判断':saved?'草稿':'未评分';
    if(saved?.status==='rated'||saved?.status==='unable')mark.classList.add('done');
    bt.append(title,mark);
    bt.onclick=()=>{ $(displayMode==='B'?'bSelect':'aSelect').value=r.id;selectRecords(); };
    $('recordList').append(bt);
  }
  renderProgress();
}
function changeImage(targetId) {
  im=DATA.images.find(x=>x.code===$('imageSelect').value);
  $('aSelect').replaceChildren();$('bSelect').replaceChildren();$('referenceSelect').replaceChildren();
  for(const r of im.annotations){$('aSelect').add(opt(r.id,recName(r)));$('bSelect').add(opt(r.id,recName(r)));}
  for(const r of im.groundtruths)$('referenceSelect').add(opt(r.version,referenceName(r.version)));
  $('referenceSelect').value='original';G=activeReference();
  $('aSelect').value=targetId || im.annotations[0].id;
  $('bSelect').value=im.annotations.find(r=>r.id!==$('aSelect').value)?.id || $('aSelect').value;
  $('scope').textContent='本图选6份，按固定顺序审查。不同合理表达可得到较高分。';
  const code=im.code;panoImg=new Image();panoImg.onload=()=>{if(im.code===code)renderPano();};panoImg.src=im.imageFile;
  if(window.THREE) new THREE.TextureLoader().load(im.imageFile,t=>{
    if(im.code!==code){t.dispose();return;}
    if(texture)texture.dispose();texture=t;texture.colorSpace=THREE.SRGBColorSpace;renderModels(false);
  },undefined,()=>{ $('status').hidden=false;$('status').textContent='原图纹理读取失败，原图与线框仍可查看'; });
  pan=[0,0,1024,512];selectRecords(true);
}
function selectRecords(reset=false) {
  const previousId=A?.id;
  A=im.annotations.find(r=>r.id===$('aSelect').value);
  B=im.annotations.find(r=>r.id===$('bSelect').value);
  if(previousId!==A.id){
    $('metricDetails').open=false;
    const saved=ratings[A.reviewId];
    if(saved){$('referenceSelect').value=saved.referenceVersion;G=activeReference();$('showGT').checked=saved.gtVisible;}
  }
  exposure();renderList();renderPano();renderBEV();renderModels(reset);renderMetrics();loadRating();renderSourceInfo();
  $('titleA').textContent='A · '+recName(A);$('titleB').textContent='B · '+recName(B);
  const index=records.findIndex(r=>r.id===A.id);
  $('taskTitle').textContent=A.reviewId+' · '+im.label;
  $('taskSubtitle').textContent=`第 ${index+1} / 36 份 · 现存点只读`;
  $('previous').disabled=index===0;$('next').disabled=index===records.length-1;
  $('compareNotice').hidden=displayMode==='A';
  if($('detail').open)$('detail').close();
  try{localStorage.setItem(Core.STORAGE+'-position',A.reviewId);}catch{}
  if($('metricDetails').open || displayMode!=='A')saveExposure();
}
function renderSourceInfo() {
  const host=$('sourceInfo');host.replaceChildren();
  const facts=[`当前作答：${A.id} · ${A.pairCount}对点；本轮匿名编号 ${A.reviewId}`,
    `参考：${referenceName(G.version)} · ${G.id}。查看过的版本会写入导出文件。`,
    `来源几何状态：${A.geometryStatus || A.renderStatus}；经度边界：${A.metricsByReference?.[G.version]?.longitudeStatus || A.longitudeStatus || '未提供'}`,
    '原坐标、点对和连接保持不变；三维模型不自动修正墙角，也不改变纳入资格。'];
  for(const text of facts){const p=document.createElement('p');p.textContent=text;host.append(p);}
}
function renderMetrics() {
  const entries=[['iou','范围IoU（高为近）'],['C','归一质心距离'],['U','上界误差 / °'],['B','下界误差 / °'],['T','参考墙顶距离 / h'],['dir','自身墙向残差 / °'],['flat','自身平顶残差 / °'],['LCG','LC＋自身3D（试验分）']];
  const host=$('metrics');host.replaceChildren();
  for(const [key,label] of entries){
    const el=document.createElement('div');el.className='metric';const t=document.createElement('span');t.textContent=label;el.append(t);
    for(const [r,name] of [[A,'A'],[B,'B']]){
      if((name==='A'&&displayMode==='B')||(name==='B'&&displayMode==='A'))continue;
      const value=r.metricsByReference?.[G.version]?.metrics?.[key];
      const b=document.createElement(name==='A'?'b':'small');b.textContent=name+' '+fmt(value);el.append(b);
    }
    host.append(el);
  }
}
function loadRating() {
  const r=ratings[A.reviewId];
  document.querySelectorAll('input[name=overall]').forEach(x=>x.checked=r?.status==='unable'?x.value==='unable':r?.status==='rated'&&Number(x.value)===r.overallScore);
  $('scopeNote').value=r?.scopeNote||'';$('geometryNote').value=r?.geometryNote||'';
  document.querySelectorAll('.tags input').forEach(x=>x.checked=(r?.tags||[]).includes(x.value));
  $('ratingTitle').textContent='评价 A · '+A.reviewId;
  $('ratingReference').textContent=`当前显示 ${referenceName(G.version)}${$('showGT').checked?'':'（已隐藏）'}；评分按整体实际质量，非仅与GT重合。`;
  $('noteStatus').textContent=!storageReady&&r?'本页暂存，未成功写入浏览器；请导出JSON':r?.status==='rated'?`已保存：${r.overallScore}分`:r?.status==='unable'?'已保存：无法判断':r?'意见草稿已保存':'尚未评分';
  const e=exposures[A.reviewId] ||= {metricsSeen:false,referencesSeen:[],comparedRecordIds:[]};
  if(r){e.metricsSeen ||= r.metricsSeen;e.referencesSeen=[...new Set([...e.referencesSeen,...r.referencesSeen])];e.comparedRecordIds=[...new Set([...e.comparedRecordIds,...r.comparedRecordIds])];}
}
function saveRating() {
  const choice=document.querySelector('input[name=overall]:checked')?.value;
  const status=choice==='unable'?'unable':choice?'rated':'draft';
  const e=exposure();
  ratings[A.reviewId]={reviewId:A.reviewId,recordId:A.id,imageCode:im.code,status,
    overallScore:status==='rated'?Number(choice):null,
    scopeNote:$('scopeNote').value,geometryNote:$('geometryNote').value,
    tags:[...document.querySelectorAll('.tags input:checked')].map(x=>x.value),
    referenceVersion:G.version,referenceId:G.id,gtVisible:$('showGT').checked,
    metricsSeen:e.metricsSeen,referencesSeen:[...e.referencesSeen],comparedRecordIds:[...e.comparedRecordIds],
    lastViewingContext:viewingContext(),rubricVersion:'overall-five-level-pilot-v1',updatedAt:new Date().toISOString()};
  const saved=persist();
  $('noteStatus').textContent=saved?(status==='rated'?`已保存到此浏览器：${choice}分`:status==='unable'?'已保存到此浏览器：无法判断':'意见草稿已保存到此浏览器'):'尚未保存到浏览器，请导出备份';
  renderList();return status;
}
function gotoRecord(r) {
  if(r.imageCode!==im.code){$('imageSelect').value=r.imageCode;changeImage(r.id);}
  else{$('aSelect').value=r.id;selectRecords();}
  if(displayMode==='B'){setDisplay('A');$('compareNotice').hidden=true;}
  $('ratingPanel')?.scrollTo(0,0);
  try{localStorage.setItem(Core.STORAGE+'-position',r.reviewId);}catch{}
}
function navigate(delta) {const index=records.findIndex(r=>r.id===A.id);const r=records[index+delta];if(r)gotoRecord(r);}
function nextUnreviewed() {
  const index=records.findIndex(r=>r.id===A.id),ordered=records.slice(index+1).concat(records.slice(0,index+1));
  const r=ordered.find(x=>!['rated','unable'].includes(ratings[x.reviewId]?.status));
  if(r)gotoRecord(r);else $('noteStatus').textContent='36份均已处理，请导出JSON备份。无法判断的记录可稍后回看。';
}
function download(name,blob) {
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function exportJSON() {download('36份质量审查_'+new Date().toISOString().slice(0,10)+'.json',new Blob([JSON.stringify(Core.makeExport(ratings,allContext()),null,2)],{type:'application/json'}));}
function exportCSV() {download('36份质量审查_'+new Date().toISOString().slice(0,10)+'.csv',new Blob([Core.toCSV(ratings,records)],{type:'text/csv;charset=utf-8'}));}
async function importFile(file) {
  if(!file)return;
  try {
    const payload=JSON.parse(await file.text());
    const incoming=Core.validateImport(payload,records,DATA.selection36.datasetFingerprintSha256);
    const changed=incoming.filter(r=>!ratings[r.reviewId]||Date.parse(r.updatedAt)>Date.parse(ratings[r.reviewId].updatedAt)).length;
    if(!confirm(`读取到${incoming.length}条意见，将合入${changed}条较新的记录；本地较新的记录保留。继续吗？`))return;
    ratings=Core.mergeRatings(ratings,incoming);persist();loadRating();renderList();
    $('importStatus').textContent=`已合入${changed}条记录。历史两两意见不受影响。`;
  } catch(error) { $('importStatus').textContent='未导入：'+error.message; }
  finally { $('importFile').value=''; }
}
function bindPano() {
  const s=$('pano');s.addEventListener('wheel',e=>{
    e.preventDefault();const z=e.deltaY>0?1.12:1/1.12,w=Math.min(1024,Math.max(90,pan[2]*z)),h=w/2;
    const rect=s.getBoundingClientRect(),u=(e.clientX-rect.left)/rect.width,v=(e.clientY-rect.top)/rect.height;
    pan=[Math.min(1024-w,Math.max(0,pan[0]+u*(pan[2]-w))),Math.min(512-h,Math.max(0,pan[1]+v*(pan[3]-h))),w,h];renderPano();
  },{passive:false});
  s.onpointerdown=e=>{if(e.target.tagName==='circle')return;drag=[e.clientX,e.clientY,...pan];s.setPointerCapture(e.pointerId);};
  s.onpointermove=e=>{if(!drag)return;const r=s.getBoundingClientRect();pan[0]=Math.max(0,Math.min(1024-pan[2],drag[2]-(e.clientX-drag[0])*pan[2]/r.width));pan[1]=Math.max(0,Math.min(512-pan[3],drag[3]-(e.clientY-drag[1])*pan[3]/r.height));s.setAttribute('viewBox',pan.join(' '));};
  s.onpointerup=s.onpointercancel=()=>drag=null;
  s.ondblclick=()=>$('panoWrap').classList.remove('expanded');
}
async function init() {
  DATA=window.REVIEW36_DATA;
  if(!DATA || DATA.selection36.recordCount!==36)throw new Error('本轮数据未完整载入');
  records=DATA.images.flatMap(image=>image.annotations.map(r=>({...r,imageCode:image.code,referenceVersions:image.groundtruths.map(g=>g.version)})));
  for(const image of DATA.images)$('imageSelect').add(opt(image.code,image.label));
  try {
    const raw=localStorage.getItem(Core.STORAGE);
    if(raw){const loaded=Core.validateImport(JSON.parse(raw),records,DATA.selection36.datasetFingerprintSha256);ratings=Object.fromEntries(loaded.map(r=>[r.reviewId,r]));}
  } catch(error) {storageReady=false;$('saveWarning').hidden=false;$('saveWarning').textContent='已有本地数据无法读取，未覆盖原数据。请保留旧备份；本次评分请及时导出JSON。';}
  try { views=[createView('viewA'),createView('viewB')]; }
  catch(error){$('viewA').textContent=$('viewB').textContent='此浏览器未启用WebGL。原图与俯视仍可审查；无法判断3D时请注明。';}
  $('workspace').hidden=false;$('status').hidden=true;
  let resume;try{resume=records.find(r=>r.reviewId===localStorage.getItem(Core.STORAGE+'-position'));}catch{}
  if(resume)$('imageSelect').value=resume.imageCode;
  changeImage(resume?.id);setDisplay('A');
  $('imageSelect').onchange=()=>changeImage();$('aSelect').onchange=()=>selectRecords();$('bSelect').onchange=()=>{selectRecords();saveExposure();};
  $('referenceSelect').onchange=()=>{G=activeReference();renderPano();renderBEV();renderModels(false);renderMetrics();renderSourceInfo();loadRating();saveExposure();};
  $('showGT').onchange=()=>{renderPano();renderBEV();renderModels(false);loadRating();saveExposure();};
  for(const b of document.querySelectorAll('[data-display]'))b.onclick=()=>{setDisplay(b.dataset.display);$('compareNotice').hidden=displayMode==='A';saveExposure();};
  $('rateB').onclick=()=>{const b=B.id,old=A.id;$('aSelect').value=b;$('bSelect').value=old;setDisplay('A');selectRecords();};
  for(const key of ['showA','showB','pointLabels'])$(key).onchange=()=>{renderPano();renderBEV();};
  $('material').onchange=()=>renderModels(false);
  for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>preset(b.dataset.view);
  $('panoReset').onclick=()=>{pan=[0,0,1024,512];renderPano();};$('panoExpand').onclick=()=>$('panoWrap').classList.toggle('expanded');
  $('closeDetail').onclick=()=>$('detail').close();$('helpButton').onclick=()=>$('help').showModal();$('closeHelp').onclick=()=>$('help').close();
  $('metricDetails').ontoggle=()=>{if($('metricDetails').open)saveExposure();};
  document.querySelectorAll('input[name=overall],.tags input').forEach(x=>x.onchange=saveRating);
  $('scopeNote').oninput=saveRating;$('geometryNote').oninput=saveRating;
  $('previous').onclick=()=>navigate(-1);$('next').onclick=()=>navigate(1);$('nextUnreviewed').onclick=nextUnreviewed;
  $('saveNext').onclick=()=>{const status=saveRating();if(status==='draft'){$('noteStatus').textContent='请选择整体分或“无法判断”，也可用上方下一份暂时跳过。';return;}nextUnreviewed();};
  $('exportJSON').onclick=$('exportJSONBottom').onclick=exportJSON;$('exportCSV').onclick=exportCSV;
  $('importButton').onclick=()=>$('importFile').click();$('importFile').onchange=()=>importFile($('importFile').files[0]);
  document.addEventListener('keydown',e=>{if(e.key==='Escape')$('panoWrap').classList.remove('expanded');});
  bindPano();
  function loop(){requestAnimationFrame(loop);views.forEach(v=>{if(!$(v.host).clientWidth||!$(v.host).clientHeight)return;if(v.control.enabled)v.control.update();v.renderer.render(v.scene,v.camera);});}loop();
  window.review36={getState:()=>({image:im.code,A:A.reviewId,B:B.reviewId,reference:G.version,displayMode,ratings:structuredClone(ratings),progress:Core.progress(ratings,records)}),exportData:()=>Core.makeExport(ratings,allContext())};
}
init().catch(error=>{$('status').hidden=false;$('status').textContent='载入失败：'+error.message;console.error(error);});
