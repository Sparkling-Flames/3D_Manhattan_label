'use strict';
// 本轮导航独立于旧114图页面；绑定和保存格式沿用共同工作台。
const queueControls=document.createElement('div');queueControls.id='queue-controls';
queueControls.innerHTML='<label>查看 <select id="queue-mode"><option value="pending">待审核</option><option value="confirmed">已确认（只读）</option><option value="reference">原始GT对照（只读）</option></select></label>';
queueControls.append($('image-search').parentElement,$('worker-search').parentElement);controls.after(queueControls);
const queueNotice=document.createElement('p');queueNotice.id='queue-notice';queueControls.after(queueNotice);
const queueEntries=dataset.cases.flatMap((c,ci)=>c.variants.map((v,vi)=>({ci,vi,source:v.source})));
const queueSources=new Map([...(window.ORDER_HISTORY_SOURCES||[]).map(s=>[sourceId(s),s]),...queueEntries.map(e=>[sourceId(e.source),e.source])]);
let queueValid=true;
function validQueueRecord(s,r){return s&&r&&r.binding===sourceBinding(s)&&['draft','pending','confirmed','pairing'].includes(r.status)&&Array.isArray(r.order)&&r.order.length===s.links_zero_based.length&&[...r.order].sort((a,b)=>a-b).every((v,i)=>Number.isInteger(v)&&v===i);}
try{if(reviewLoadError)throw reviewLoadError;for(const [id,r] of Object.entries(saved))if(!validQueueRecord(queueSources.get(id),r))throw Error(id);}catch(e){queueValid=false;queueNotice.textContent='本地记录校验失败，已停止编辑，请导出备份检查：'+e.message;}
function reviewState(s){return s.object_kind==='gt_original'?'reference':saved[sourceId(s)]?.status==='confirmed'?'confirmed':saved[sourceId(s)]?.status==='pairing'?'pairing':'pending';}
function readOnlyOrder(){return !queueValid||reviewState(activeSource())!=='pending';}
function visibleQueue(){const image=$('image-search').value.trim().toLowerCase(),worker=$('worker-search').value.trim().toLowerCase();return queueEntries.filter(e=>{const c=dataset.cases[e.ci],s=e.source;return reviewState(s)===$('queue-mode').value&&`${c.title} ${c.image_id} ${c.room_id}`.toLowerCase().includes(image)&&`${s.worker_id||''} ${s.raw_condition||''} ${s.reference_name||''}`.toLowerCase().includes(worker);});}
updateProgress=function(){const counts={pending:0,confirmed:0,pairing:0};queueEntries.forEach(e=>{const state=reviewState(e.source);if(state in counts)counts[state]++;});$('object-progress').textContent=`待审 ${counts.pending} · 已确认 ${counts.confirmed} · 本页新增配对问题 ${counts.pairing} · 生成时配对待处理 ${dataset.summary.pairing_deferred}`;};
function updateQueueUI(){
 const visible=visibleQueue(),match=visible.some(e=>e.ci===currentCase&&e.vi===currentVariant),readonly=readOnlyOrder()||!match;
 for(const option of $('case-select').options)option.hidden=!visible.some(e=>e.ci===Number(option.value));
 for(const option of $('variant-select').options)option.hidden=!visible.some(e=>e.ci===currentCase&&e.vi===Number(option.value));
 for(const id of ['confirm-order','pending-order','pairing-problem','pairing-note','order-restore','order-apply','order-permutation'])if($(id))$(id).disabled=readonly;
 dragArea.querySelectorAll('button').forEach(b=>b.setAttribute('aria-disabled',String(readonly)));
 for(const id of ['panorama-panel','compare-grid','pair-drag-list'])$(id).hidden=!match;
 $('case-select').disabled=$('variant-select').disabled=!visible.length;
 if(queueValid)queueNotice.textContent=visible.length?`${visible.length} 份符合当前筛选 · ${readonly?'只读查看，确认结果直接沿用':'待审；确认或报告配对错误后自动前进'} · 原图号 ${dataset.cases[currentCase].original_slot||'新增'}`:'当前筛选下没有对象。';
 $('order-status').textContent=readonly?'只读 · '+(reviewState(activeSource())==='reference'?'原始GT':'已确认'):'待审核';
 updateProgress();
}
const queueDrawDrag=drawDrag;drawDrag=function(){queueDrawDrag();updateQueueUI();};
const queueChooseVariant=chooseVariant;chooseVariant=function(index,reset=false){queueChooseVariant(index,reset);updateQueueUI();};
const queueSetOrder=setPreviewOrder;setPreviewOrder=function(order,action){if(!restoring&&readOnlyOrder())return;queueSetOrder(order,action);};STUDIO.setPreviewOrder=setPreviewOrder;
const queueStartDrag=startPairDrag;startPairDrag=function(...args){if(!readOnlyOrder())queueStartDrag(...args);};
const queueSaveReview=saveReview;saveReview=function(status='draft'){if(readOnlyOrder()||restoring)return false;return queueSaveReview(status);};
const queueChooseCase=chooseCase;chooseCase=async function(index){await queueChooseCase(index);const visible=visibleQueue().filter(e=>e.ci===currentCase);if(visible.length&&!visible.some(e=>e.vi===currentVariant)){const entry=visible[0];$('variant-select').value=entry.vi;chooseVariant(entry.vi);}updateQueueUI();};
async function showQueueEntry(e){if(!e){updateQueueUI();return;}if(currentCase!==e.ci)await chooseCase(e.ci);$('variant-select').value=e.vi;chooseVariant(e.vi);}
async function applyQueueFilter(){const list=visibleQueue();if(!list.some(e=>e.ci===currentCase&&e.vi===currentVariant))await showQueueEntry(list[0]);updateQueueUI();}
async function nextQueue(delta=1,imageOnly=false){const allIndex=queueEntries.findIndex(e=>e.ci===currentCase&&e.vi===currentVariant),list=visibleQueue().filter(e=>!imageOnly||e.ci!==currentCase);const ordered=delta>0?list:[...list].reverse();await showQueueEntry(ordered.find(e=>delta>0?queueEntries.indexOf(e)>allIndex:queueEntries.indexOf(e)<allIndex)||ordered[0]);}
for(const id of ['image-search','worker-search'])$(id).oninput=applyQueueFilter;
$('queue-mode').onchange=applyQueueFilter;
$('previous').onclick=()=>nextQueue(-1,true);$('next').onclick=()=>nextQueue(1,true);$('next-order').onclick=()=>nextQueue();
for(const [id,status] of [['confirm-order','confirmed'],['pairing-problem','pairing']])$(id).onclick=async()=>{if(geometry&&saveReview(status))await nextQueue();updateQueueUI();};
const queueImport=$('import-orders').onchange;$('import-orders').onchange=async e=>{await queueImport(e);await applyQueueFilter();};
if(!queueValid){$('import-orders').disabled=true;$('download-orders').onclick=()=>downloadQueueFile('角点顺序审核_损坏记录备份.txt',localStorage.getItem(storageKey)||'','text/plain');}
$('order-restore').textContent='恢复默认排列';
$('order-legend').append(' 已确认结果直接沿用；人工修订GT未确认时默认按共享x升序，固定点对编号不变。');
detail.textContent='本轮依据原始GT连接环筛选；原始GT仅作只读对照，配对问题另行处理。';
function connectionLayout(s,r){
 if(s.object_kind==='gt_original'||r?.status!=='confirmed'||!validQueueRecord(s,r))throw Error('必须是绑定有效的已确认对象');
 const indices=r.order.flatMap(i=>s.links_zero_based[i]);if([...indices].sort((a,b)=>a-b).some((v,i)=>v!==i)||indices.length!==s.points.length)throw Error('点对未完整覆盖点集');
 return {object_id:sourceId(s),object_kind:s.object_kind,image_id:s.image_id,source:s.provenance,preprocessing:s.preprocessing,coordinate_frame:'1024x512',closed:true,ordered_source_pair_indices:[...r.order],ordered_source_point_indices:indices,ordered_source_point_labels:indices.map(i=>s.effective_point_labels[i]),points_1024x512:indices.map(i=>[...s.points[i]]),links_zero_based:indices.filter((_,i)=>i%2===0).map((_,i)=>[2*i,2*i+1])};
}
function confirmedConnections(){return queueEntries.filter(e=>reviewState(e.source)==='confirmed').map(e=>connectionLayout(e.source,saved[sourceId(e.source)]));}
function downloadQueueFile(name,value,type='application/json'){const url=URL.createObjectURL(new Blob([value],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
const exportConnections=document.createElement('button');exportConnections.id='export-connections';exportConnections.textContent='导出已确认连接数组';more.append(exportConnections);
exportConnections.onclick=()=>downloadQueueFile('已确认连接顺序_Matterport.json',JSON.stringify({schema:'matterport_connection_order_v1',objects:confirmedConnections(),formal_analysis_connected:false},null,2));
const exportTxt=document.createElement('button');exportTxt.id='export-order-txt';exportTxt.textContent='导出当前已确认 label_cor';more.append(exportTxt);
exportTxt.onclick=()=>{try{const o=connectionLayout(activeSource(),saved[sourceId(activeSource())]);downloadQueueFile(o.object_id.replace(/[^a-zA-Z0-9_-]/g,'_')+'.txt',o.points_1024x512.map(p=>p.join(' ')).join('\n')+'\n','text/plain');}catch(e){$('save-state').textContent=e.message;}};
applyQueueFilter();
