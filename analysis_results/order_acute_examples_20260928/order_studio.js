/* Independent single-annotation view; the shared Studio and all source arrays stay unchanged. */
'use strict';
let loosePoint = null;
let hoveredPair = null;
let requestedAnnotation = new URL(location.href).searchParams.get('annotation');
const controls = document.createElement('section');
controls.className = 'order-controls';
controls.innerHTML = '<label>查找图片 <input id="image-search" placeholder="如 B6ByNegPMKs-11"></label><label>查找人员 / 来源 <input id="worker-search" placeholder="如 W021"></label><label><input id="show-points" type="checkbox" checked>标注点</label><label><input id="show-point-ids" type="checkbox" checked>原点号</label><label><input id="show-edges" type="checkbox">连接线</label><span id="filter-note" role="status"></span>';
document.querySelector('.study-heading').after(controls);
const identity = document.createElement('p');identity.id = 'order-identity';controls.after(identity);
document.querySelector('h1').textContent = '独立角点顺序工作台';
document.querySelector('.inspector-title h3').textContent = '点位与顺序';
document.querySelector('#panorama-panel summary').innerHTML = '<span>原图与单份标注 <small>点击点位查看局部；左右接缝相连</small></span>';
document.querySelector('.canvas-hint').firstChild.textContent = '拖动旋转 · 滚轮缩放 · 俯视查看占据范围　';
document.querySelector('.order-editor p').textContent = '只移动完整上下点组。坐标、配对、原始数据不改；切换来源或刷新前请先导出。预览排列与几何显示有效不等于正确环序。';
document.querySelector('footer').firstChild.textContent = '独立排序与空间范围研究 ';
document.querySelector('footer span').textContent = '不包含质心、IoU 或排除裁决';
document.querySelector('.pano-caption').textContent = '全景预览 · 2048px JPEG 副本';
document.querySelector('.source-details p:last-child').textContent = '本页仅显示原始几何与顺序预览。模型采用相机高度为 1 的相对尺度；它不是独立测得的真实房间。';
$('compare-grid').classList.add('only-raw');$('panorama-panel').open = true;$('decor').checked = false;

function activeSource(){return dataset.cases[currentCase]?.variants[currentVariant]?.source;}
function pointLabel(index){const id=activeSource()?.original_point_ids_1based[index];return id==null?`E${index+1}*`:`P${id}`;}
function previewLink(index){return activeSource()?.links_zero_based?.[previewOrder[index]];}
function pairDisplay(index){
 const fixed=activeSource()?.links_zero_based?.findIndex(pair=>pair.includes(index));
 if(fixed==null||fixed<0)return '未配对';
 return `${previewOrder.indexOf(fixed)+1}·对${fixed+1}`;
}
function describeSource(){
  const source=activeSource();if(!source)return;
  identity.textContent=source.canonical_annotation_id
    ? `${source.worker_id} · ${source.raw_condition} · canonical ${source.canonical_annotation_id} · ${source.processing_status}`
    : `参考来源：${source.reference_name} · ${source.reference_source}`;
  identity.textContent+='｜P=原点号；E*=有效点，不能唯一追溯原点。上下配对沿用现状，环序待核验。';
  if(!geometry)$('order-map').textContent='上下配对或投影不可用；二维点仍可查看。此状态不等于标注无效。';
}

const baseChooseVariant=chooseVariant;
chooseVariant=function(index,resetView=false){loosePoint=null;baseChooseVariant(index,resetView);describeSource();};
const baseUpdateOrderEditor=updateOrderEditor;
updateOrderEditor=function(){
  baseUpdateOrderEditor();
  $('order-status').textContent=!geometry?'无可核对点组':previewOrder.some((v,i)=>v!==i)?'预览顺序 · 待核验':'当前顺序 · 待核验';
};

// Draw one source, never consensus fills, fitted geometry or other workers.
drawPanorama=function(){
  const canvas=$('panorama'),ctx=canvas.getContext('2d');canvas.width=2048;canvas.height=1024;
  if(!originalImage)return;
  ctx.scale(2,2);ctx.drawImage(originalImage,0,0,1024,512);
  const source=activeSource();if(!source)return;
  if(geometry&&$('show-edges').checked){
    for(let i=0;i<geometry.pairs.length;i++)for(const ep of ['top','bottom'])
      drawPath(ctx,boundaryPoints(geometry.raw,ep,i),$('edge-color')?.value||'#ff2d85',false,1.5);
  }
  const link=geometry&&selected?previewLink(selected.index):null;
  const picked=link?link[endpoint==='top'?0:1]:loosePoint;
  if(!$('show-points').checked)return;
  const labelBoxes=[];
  source.points.forEach((point,index)=>{
    const fixed=source.links_zero_based?.findIndex(pair=>pair.includes(index));
    const active=index===picked||fixed===hoveredPair;
    ctx.beginPath();ctx.arc(...point,active?4.5:2.5,0,Math.PI*2);ctx.fillStyle=active?'#ffb24c':'#eafff5';ctx.fill();
    ctx.strokeStyle='#245e50';ctx.lineWidth=1;ctx.stroke();
    if($('show-point-ids').checked||active){
      if(fixed==null||fixed<0)return;
      const position=previewOrder.indexOf(fixed)+1;
      const x=Math.max(12,Math.min(960,point[0]+15));let y=Math.max(12,Math.min(500,point[1]-14));
      for(const shift of [0,-28,28,-56,56,-84,84,-112,112]){
        const candidate=Math.max(12,Math.min(500,point[1]-14+shift));
        if(!labelBoxes.some(b=>Math.abs(b.y-candidate)<25&&x<b.x+66&&x+66>b.x)){y=candidate;break;}
      }
      labelBoxes.push({x,y});ctx.beginPath();ctx.moveTo(...point);ctx.lineTo(x,y);ctx.strokeStyle=active?'#17649b':'#ffffffaa';ctx.lineWidth=1;ctx.stroke();
      const sequenceVisible=$('show-sequence')?.checked!==false;
      if(sequenceVisible){ctx.beginPath();ctx.arc(x,y,11,0,Math.PI*2);ctx.fillStyle='#fff1dc';ctx.fill();
      ctx.lineWidth=2;ctx.strokeStyle='#b95a00';ctx.stroke();
      ctx.font='bold 14px Segoe UI';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#954400';ctx.fillText(String(position),x,y);}
      ctx.textBaseline='middle';
      ctx.font='12px Segoe UI';const label=`对${fixed+1}`,width=ctx.measureText(label).width+10;
      ctx.fillStyle=active?'#d4edff':'#f1f8ff';ctx.fillRect(x+15,y-10,width,20);
      ctx.strokeStyle='#17649b';ctx.lineWidth=1.5;ctx.strokeRect(x+15,y-10,width,20);
      ctx.textAlign='left';ctx.fillStyle='#125384';ctx.fillText(label,x+20,y);
    }
  });
};
const baseDrawCrop=drawCrop;
drawCrop=function(){
  if(geometry){
    baseDrawCrop();
    if(originalImage&&selected){const ctx=$('crop').getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(9,9,220,27);
      ctx.fillStyle='#5b6d59';ctx.fillText('当前端点 ●   周期展开',18,29);}
    return;
  }
  const source=activeSource();if(loosePoint===null||!source||!originalImage){baseDrawCrop();return;}
  const p=source.points[loosePoint],canvas=$('crop'),ctx=canvas.getContext('2d'),zoom=canvas.width/160;
  const left=p[0]-80,top=p[1]-canvas.height/zoom/2;
  ctx.clearRect(0,0,canvas.width,canvas.height);ctx.save();ctx.scale(zoom,zoom);ctx.translate(-left,-top);
  for(let shift=-1;shift<=1;shift++)ctx.drawImage(originalImage,shift*1024,0,1024,512);
  ctx.beginPath();ctx.arc(...p,2.3,0,Math.PI*2);ctx.fillStyle='#ffb24c';ctx.fill();ctx.strokeStyle='white';ctx.lineWidth=.6;ctx.stroke();ctx.restore();
};
const basePanoramaClick=$('panorama').onclick;
$('panorama').onclick=function(event){
  if(geometry){basePanoramaClick(event);return;}
  const source=activeSource();if(!source?.points.length||!originalImage)return;
  const rect=this.getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width*1024,y=(event.clientY-rect.top)/rect.height*512;
  let nearest=Infinity;loosePoint=null;
  source.points.forEach((p,i)=>{const dx=((p[0]-x+512)%1024+1024)%1024-512,d=Math.hypot(dx,p[1]-y);if(d<nearest){nearest=d;loosePoint=i;}});
  document.querySelector('.selection-block').classList.add('has-selection');
  $('selection-kind').textContent=pointLabel(loosePoint);
  $('selection-details').textContent=`${pointLabel(loosePoint)} · 有效数组第 ${loosePoint+1} 点 · 坐标 ${source.points[loosePoint].join(', ')}；上下配对未确认。`;
  drawPanorama();drawCrop();
};
const baseUpdateSelection=updateSelection;
updateSelection=function(){
  baseUpdateSelection();
  if(geometry&&selected){const ids=previewLink(selected.index);if(ids){
    const line=document.createElement('div');line.textContent=`当前组 ${selected.index+1}：上 ${pointLabel(ids[0])} / 下 ${pointLabel(ids[1])}`;
    $('selection-details').prepend(line);
  }}
};
const baseOrderRecord=orderRecord;
orderRecord=function(){
  const source=activeSource(),record=baseOrderRecord();
  return {...record,schema_version:'order_studio_preview_order_v1',contract_version:dataset.manifest.contract_version,
    source_identity:clone(source),preview_endpoint_effective_point_ids_1based:previewOrder.flatMap(i=>(source.links_zero_based?.[i]||[]).map(j=>j+1)),
    ring_confirmed:false,source_geometry_writeback:false};
};
STUDIO.orderRecord=orderRecord;
$('order-export').onclick=()=>{
  const record=orderRecord(),a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));
  a.href=url;a.download=`${dataset.cases[currentCase].title}_${activeSource().canonical_annotation_id||activeSource().reference_name}_preview_order.json`;
  a.click();URL.revokeObjectURL(url);
};
for(const id of ['show-points','show-point-ids','show-edges'])$(id).onchange=drawPanorama;
function filterWorkers(selectMatch=false){
  const text=$('worker-search').value.trim().toLowerCase(),options=[...$('variant-select').options];
  for(const option of options)option.hidden=!option.text.toLowerCase().includes(text);
  const visible=options.filter(o=>!o.hidden);
  $('filter-note').textContent=visible.length?`${visible.length} 个来源可选`:'本图没有匹配人员；当前显示来源未改变';
  if(selectMatch&&visible.length&&!visible.some(o=>Number(o.value)===currentVariant)){
    $('variant-select').value=visible[0].value;chooseVariant(Number(visible[0].value));
  }
}
$('worker-search').oninput=()=>filterWorkers(true);
$('image-search').oninput=()=>{
  const text=$('image-search').value.trim().toLowerCase(),options=[...$('case-select').options];
  for(const option of options)option.hidden=!`${dataset.cases[Number(option.value)].title} ${dataset.cases[Number(option.value)].image_id}`.toLowerCase().includes(text);
  const visible=options.filter(o=>!o.hidden);
  if(visible.length&&!visible.some(o=>Number(o.value)===currentCase))chooseCase(Number(visible[0].value));
  if(!visible.length)$('filter-note').textContent='没有匹配图片；当前图片未改变';
};
document.addEventListener('studio-case',()=>{
  if(requestedAnnotation){const index=dataset.cases[currentCase].variants.findIndex(v=>v.source.canonical_annotation_id===requestedAnnotation);
    if(index>=0){$('variant-select').value=index;chooseVariant(index);requestedAnnotation=null;}}
  filterWorkers(true);describeSource();
});
if(requestedAnnotation){const index=dataset.cases.findIndex(c=>c.annotation_ids.includes(requestedAnnotation));
  if(index>=0)chooseCase(index);else fail('找不到指定 canonical 身份：'+requestedAnnotation);}
describeSource();
requestAnimationFrame(()=>{views.forEach(resize);drawPanorama();});

// 只移动完整点对；草稿与用户确认分离，正式数据暂不接入。
const editor=document.querySelector('.order-editor');
$('panorama-panel').after(editor);
const dragArea=document.createElement('div');dragArea.id='pair-drag-list';dragArea.setAttribute('aria-label','拖动完整点对排序');editor.prepend(dragArea);
const actions=document.createElement('div');actions.className='review-actions';
actions.innerHTML='<button id="confirm-order">确认当前顺序</button><button id="pending-order">尚不能确定</button><button id="pairing-problem">配对有问题</button><button id="download-orders">导出全部记录</button><label>导入记录 <input id="import-orders" type="file" accept=".json"></label><p id="save-state" role="status"></p><label id="example-question">这例的锐角更像是：<select id="example-cause"><option value="">尚未判断</option><option value="order">顺序问题</option><option value="points">点位／标注问题</option><option value="structure">真实结构或遮挡</option><option value="representation">重建表示问题</option><option value="uncertain">无法判断</option></select></label>';
editor.append(actions);
const detail=document.createElement('p');detail.id='sample-evidence';editor.prepend(detail);
const storageKey='order_review_20260928_v2:'+location.pathname;
let saved={},demoOrder=[0,1,2,3,4,5],pointerDrag=null,restoring=false;
try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}');}catch(e){$('save-state').textContent='本地记录读取失败，请先导出备份，勿覆盖。';}
function inputBinding(){const s=activeSource();return s?.canonical_annotation_id?JSON.stringify({id:s.canonical_annotation_id,points:s.effective_points||s.points,labels:s.effective_point_labels,links:s.links_zero_based}):null;}
function drawDrag(){
 const s=activeSource(),empty=s?.role==='empty',order=empty?demoOrder:previewOrder;
 dragArea.replaceChildren();
 if(empty)$('order-restore').disabled=false;
 detail.textContent=empty?'空工作台：以下六组是假数据，仅供试拖动，不保存到研究记录。':`默认顺序的尖角：${Object.entries(s?.screening?.acute_angles_degrees||{}).map(([k,v])=>`组${k}（${v}°）`).join('、')}。连续锐角仅是候选线索，拖动后不代表仍是这些角。原审核：${s?.review?.current_decision_comment||'未填写'}。模型记录：${s?.review?.model_edit_status||'未记录'}；Trap：${s?.review?.trap_status||'未记录'}。`;
 $('example-question').hidden=!dataset.manifest.examples_only;
 for(let i=0;i<order.length;i++){
  const b=document.createElement('button');b.className='pair-token';b.dataset.position=i;b.dataset.pair=order[i];
  const ids=s?.links_zero_based?.[order[i]],labels=s?.effective_point_labels;
  b.textContent=`对${order[i]+1}`;
  b.title=ids?ids.map(j=>labels?.[j]||pointLabel(j)).join(' / '):'演示点对';
  b.onpointerdown=e=>startPairDrag(e,b,i);
  b.onmouseenter=b.onfocus=()=>{hoveredPair=order[i];drawPanorama();};
  b.onmouseleave=b.onblur=()=>{hoveredPair=null;drawPanorama();};
  b.onclick=e=>{if(e.detail===0&&geometry)select({kind:'point',index:i,endpoint:'top'});};
  b.onkeydown=e=>{if(e.altKey&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();movePair(i,e.key==='ArrowLeft'?Math.max(0,i-1):Math.min(order.length,i+2));}};
  dragArea.append(b);
 }
 for(const id of ['confirm-order','pending-order','pairing-problem'])$(id).disabled=empty;
}
function startPairDrag(e,button,index){
 if(e.button!==0||pointerDrag)return;
 e.preventDefault();button.focus();
 pointerDrag={id:e.pointerId,button,index,x:e.clientX,y:e.clientY,lifted:false};
 dragArea.setPointerCapture(e.pointerId);
}
dragArea.onpointermove=e=>{
 const d=pointerDrag;if(!d||e.pointerId!==d.id)return;
 if(!d.lifted&&Math.hypot(e.clientX-d.x,e.clientY-d.y)<5)return;
 if(!d.lifted){
  const rect=d.button.getBoundingClientRect();d.lifted=true;d.dx=d.x-rect.left;d.dy=d.y-rect.top;
  d.ghost=d.button.cloneNode(true);d.ghost.classList.add('pair-floating');d.ghost.style.width=rect.width+'px';document.body.append(d.ghost);
  d.button.remove();d.marker=document.createElement('span');d.marker.className='pair-insertion';d.marker.setAttribute('aria-hidden','true');
 }
 d.ghost.style.left=(e.clientX-d.dx)+'px';d.ghost.style.top=(e.clientY-d.dy)+'px';
 // Keep the gap marker out of layout so the remaining cards close up immediately.
 const cards=[...dragArea.querySelectorAll('.pair-token')],areaBox=dragArea.getBoundingClientRect();
 const rects=cards.map(b=>({left:areaBox.left+b.offsetLeft,top:areaBox.top+b.offsetTop,width:b.offsetWidth,height:b.offsetHeight,right:areaBox.left+b.offsetLeft+b.offsetWidth}));
 let nearest=0,best=Infinity;
 rects.forEach((r,i)=>{const dy=Math.abs(e.clientY-(r.top+r.height/2));if(dy<best){best=dy;nearest=i;}});
 const row=rects.map((r,i)=>({r,i})).filter(({r})=>Math.abs(r.top-rects[nearest]?.top)<5);
 const next=row.find(({r})=>e.clientX<r.left+r.width/2);
 d.target=next?next.i:row.length?row[row.length-1].i+1:0;
 const last=rects.at(-1),gap=12;
 const tail=last&&(last.right+gap+last.width<=areaBox.right-9
  ?{...last,left:last.right+gap}:{...last,left:rects[0].left,top:last.top+last.height+gap});
 const slots=[...rects,tail];
 cards.forEach((b,i)=>{const r=rects[i],slot=slots[i+(i>=d.target?1:0)];b.style.transform=`translate(${slot.left-r.left}px,${slot.top-r.top}px)`;});
 const anchor=slots[d.target];
 if(anchor){d.marker.style.left=(anchor.left-areaBox.left)+'px';d.marker.style.top=(anchor.top-areaBox.top)+'px';d.marker.style.width=anchor.width+'px';d.marker.style.height=anchor.height+'px';dragArea.append(d.marker);}
};
function finishPairDrag(cancel=false){
 const d=pointerDrag;if(!d)return;pointerDrag=null;
 if(dragArea.hasPointerCapture(d.id))dragArea.releasePointerCapture(d.id);
 if(d.lifted){
  d.ghost.remove();d.marker.remove();
  if(!cancel){const empty=activeSource()?.role==='empty',order=[...(empty?demoOrder:previewOrder)];const [pair]=order.splice(d.index,1);order.splice(d.target??d.index,0,pair);
   if(empty){demoOrder=order;drawDrag();}else setPreviewOrder(order,'drag_pair');
  }else drawDrag();
 }else if(!cancel&&geometry)select({kind:'point',index:d.index,endpoint:'top'});
 hoveredPair=null;drawPanorama();
}
dragArea.onpointerup=()=>finishPairDrag();
dragArea.onpointercancel=()=>finishPairDrag(true);
dragArea.onlostpointercapture=()=>finishPairDrag(true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&pointerDrag){e.preventDefault();finishPairDrag(true);}});
function movePair(from,to){
 const empty=activeSource()?.role==='empty',order=[...(empty?demoOrder:previewOrder)];
 if(!Number.isInteger(from)||from<0||from>=order.length||to<0||to>order.length)return;
 const [item]=order.splice(from,1);order.splice(to>from?to-1:to,0,item);
 if(empty){demoOrder=order;drawDrag();}else setPreviewOrder(order,'drag_pair');
}
function saveReview(status='draft'){
 const binding=inputBinding(),s=activeSource();if(!binding||restoring)return;
 saved[s.canonical_annotation_id]={binding,status,order:[...previewOrder],cause:$('example-cause').value,updated_at:new Date().toISOString()};
 try{localStorage.setItem(storageKey,JSON.stringify(saved));$('save-state').textContent=({draft:'草稿已保存',confirmed:'已确认顺序',pending:'已记录：尚不能确定',pairing:'已记录：配对有问题'})[status];}catch(e){$('save-state').textContent='本地保存失败，请立即导出记录。';}
}
const dragSetOrder=setPreviewOrder;
setPreviewOrder=function(order,action){dragSetOrder(order,action);drawDrag();saveReview();};
STUDIO.setPreviewOrder=setPreviewOrder;
const dragChooseVariant=chooseVariant;
chooseVariant=function(index,reset=false){
 finishPairDrag(true);hoveredPair=null;
 restoring=true;dragChooseVariant(index,reset);const s=activeSource(),record=saved[s?.canonical_annotation_id];
 $('example-cause').value='';$('save-state').textContent='未确认';
 if(record){if(record.binding!==inputBinding())$('save-state').textContent='输入点版本改变：旧记录未套用，请先导出。';
 else{if(geometry)setPreviewOrder(record.order,'restore_draft');$('example-cause').value=record.cause||'';$('save-state').textContent=record.status==='confirmed'?'已确认顺序':record.status==='draft'?'已恢复草稿':'已记录，仍待判断';}}
 restoring=false;drawDrag();
};
$('confirm-order').onclick=()=>{if(geometry)saveReview('confirmed');else $('save-state').textContent='无可用点对，不能确认顺序。';};
$('pending-order').onclick=()=>saveReview('pending');$('pairing-problem').onclick=()=>saveReview('pairing');
$('example-cause').onchange=()=>saveReview();
$('order-restore').onclick=()=>{if(activeSource()?.role==='empty'){demoOrder=[0,1,2,3,4,5];drawDrag();}else setPreviewOrder(previewOrder.map((_,i)=>i),'restore_default');};
$('download-orders').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema:'order_review_20260928_v2',examples_only:!!dataset.manifest.examples_only,records:saved},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='角点顺序审核.json';a.click();URL.revokeObjectURL(url);};
$('import-orders').onchange=async e=>{try{
 const doc=JSON.parse(await e.target.files[0].text());if(doc.schema!=='order_review_20260928_v2'||doc.examples_only!==!!dataset.manifest.examples_only||!doc.records)throw Error('文件版本或用途不匹配');
 const merged={...saved};
 for(const [id,r] of Object.entries(doc.records)){
  const binding=JSON.parse(r.binding),n=binding.links?.length||0;
  if(binding.id!==id||!['draft','confirmed','pending','pairing'].includes(r.status)||!Array.isArray(r.order)||r.order.length!==n||[...r.order].sort((a,b)=>a-b).some((v,i)=>v!==i))throw Error('顺序记录不完整');
  if(merged[id]&&JSON.stringify(merged[id])!==JSON.stringify(r))throw Error('存在本地记录冲突，未覆盖');merged[id]=r;
 }
 localStorage.setItem(storageKey,JSON.stringify(merged));saved=merged;chooseVariant(currentVariant);$('save-state').textContent='导入完成';
}catch(err){$('save-state').textContent='导入未应用：'+err.message;}};
document.addEventListener('studio-case',drawDrag);
if(activeSource())chooseVariant(currentVariant);else drawDrag();

// 单屏操作：主界面只留点对、确认和下一图；研究记录折叠保留。
const more=document.createElement('details');more.id='order-more';
const moreTitle=document.createElement('summary');moreTitle.textContent='记录与备份';more.append(moreTitle);
for(const element of [detail,$('pending-order'),$('pairing-problem'),$('download-orders'),$('import-orders').parentElement])more.append(element);
editor.append(more);
$('example-question').style.display='none';
const nextCase=document.createElement('button');nextCase.id='next-order';nextCase.textContent='下一张 →';nextCase.onclick=()=>chooseCase(currentCase+1);
$('confirm-order').after(nextCase);
$('confirm-order').textContent='确认';
const legend=document.createElement('p');legend.id='order-legend';legend.innerHTML='<span class="identity-key">对N</span> 固定点对　<span class="sequence-key">1</span> 当前连接次序　拖起卡片，移到目标附近后松手；首尾相连。';editor.prepend(legend);
document.querySelector('h1').textContent='点对排序';
$('show-edges').checked=true;
$('panorama-panel').querySelector('summary').textContent='原图 · 当前连接顺序';
const displayOptions=document.createElement('div');displayOptions.id='order-display-options';
displayOptions.innerHTML='<label>连线颜色 <select id="edge-color"><option value="#ff2d85">亮粉</option><option value="#00e5ff">亮青</option><option value="#ffe600">亮黄</option><option value="#ff4025">亮红</option></select></label><label><input id="show-sequence" type="checkbox" checked>显示顺序</label><button id="hide-order-overlays" type="button">隐藏顺序和连线</button>';
displayOptions.insertBefore($('show-edges').parentElement,$('hide-order-overlays'));legend.after(displayOptions);
function updateOverlayControls(){ $('hide-order-overlays').textContent=$('show-sequence').checked||$('show-edges').checked?'隐藏顺序和连线':'显示顺序和连线';drawPanorama(); }
$('edge-color').onchange=$('show-sequence').onchange=$('show-edges').onchange=updateOverlayControls;
$('hide-order-overlays').onclick=()=>{const show=!($('show-sequence').checked||$('show-edges').checked);$('show-sequence').checked=$('show-edges').checked=show;updateOverlayControls();};
drawPanorama();requestAnimationFrame(()=>views.forEach(resize));
