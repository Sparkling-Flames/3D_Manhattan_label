/* Companion editor for the existing green Panorama Studio renderer. */
(function(){
'use strict';
const D=window.POINT_REVIEW_DATA,M=window.PointReview,E=id=>document.getElementById(id),versions=['raw','historical','current','draft'];
const queueItems=D.review_queue.items,queueById=new Map(queueItems.map(r=>[r.record_id,r]));
const selectedIndices=queueItems.map(r=>D.cases.findIndex(c=>c.record_id===r.record_id)),allIndices=D.cases.map((_,i)=>i);
const scopeIndices=()=>E('scope-filter').value==='selected'?selectedIndices:allIndices;
E('scope-filter').options[0].textContent='本轮'+D.review_queue.selected_records+'份待核验';
E('panorama-panel').open=true;
const key=M.SCHEMA+':'+D.source_hash+':'+D.queue_hash,uiKey=key+':view';
E('panorama-panel').insertBefore(E('quick-editor'),E('panorama-panel').querySelector('.panorama-wrap'));
for(const id of ['cancel-selection','save-draft','confirm-patch','complete-next','defer-patch','export-patches'])E('quick-buttons').append(E(id));
E('cancel-selection').textContent='取消当前操作';E('save-draft').textContent='保存';E('export-patches').textContent='导出审核返回';
for(const id of ['edit-status','edit-selection'])E('quick-feedback').append(E(id));
let pendingAction=null;
const evidence=document.createElement('div');evidence.className='panorama-evidence';
const imageWrap=E('panorama-panel').querySelector('.panorama-wrap');imageWrap.before(evidence);evidence.append(imageWrap);
const reviewerCard=document.createElement('aside');reviewerCard.id='reviewer-card';
reviewerCard.innerHTML='<div id="queue-context"></div><h3>外部审核人的意见</h3><p id="reviewer-binding"></p><strong id="reviewer-conclusion"></strong><small>原始备注（只读）</small><blockquote id="reviewer-original-note"></blockquote><p id="reviewer-empty-note" hidden>原始备注为空</p><p id="reviewer-point-refs"></p><p class="reviewer-disclaimer">这是外部建议，未自动替你采用。</p><hr><strong id="my-review-status"></strong><p id="my-review-summary"></p><label for="review-note">我的备注（选填）</label>';
evidence.append(reviewerCard);reviewerCard.append(E('review-note'));
function renderOrder(){
 const ps=shownPairs(),position=ps.findIndex(p=>p.includes(selectedPoint)),paired=new Set(ps.flat()),rest=points().filter(p=>!p.deleted&&!paired.has(p.id)),closed=ps.length>=3&&rest.length===0;sorter.refresh();
 E('order-help').textContent=ps.length?'已配 '+ps.length+' 组'+(rest.length?' · 剩余 '+rest.length+' 点':' · 全部点已配对'):'尚无点对 · 可按x生成候选';
 E('sort-unpaired').replaceChildren(...rest.map(p=>{const b=document.createElement('button');b.textContent=p.label;b.title='未配对点 '+p.label+' · '+p.x+', '+p.y;b.onclick=()=>selectPoint(p.id);return b;}));
 E('sort-unpaired').hidden=rest.length===0;E('pair-by-x').disabled=!editable()||rest.length<2;
 E('pair-earlier').disabled=!editable()||position<=0;E('pair-later').disabled=!editable()||position<0||position>=ps.length-1;
 E('pair-order-map').textContent=ps.map((p,i)=>(i+1)+' '+label(p[0])+'/'+label(p[1])).join(' → ')+(closed?' → 首组':'');
 E('review-order').dataset.closed=String(closed);
}
function renderReviewer(){
 const r=row(),d=draft(),note=r.reviewer.reviewer_note,q=queueById.get(r.record_id),resolved=D.review_queue.resolved_items[r.record_id];
 E('queue-context').textContent=q?'本轮待核验 · '+q.category+'\n筛选原因：'+q.reason+'\n清单建议（待你判断）：'+q.advice:resolved?'已移出本轮待核验：'+resolved.reason:'已移出本轮待核验清单；仅供查看旧记录与草稿。';
 E('reviewer-binding').textContent=r.record_id+' · '+r.worker+' · '+r.image_id;
 E('reviewer-conclusion').textContent=r.reviewer.reviewer_conclusion;
 E('reviewer-original-note').textContent=note;E('reviewer-empty-note').hidden=note!=='';
 const refs=r.proposed_deletions.map(p=>p.derived_original_label);
 E('reviewer-point-refs').textContent=refs.length?'稳定原点映射：'+[...new Set(refs)].join('、'):'备注中的删点号：'+r.reviewer.proposed_delete_numbers+'；原始点共'+r.versions.raw.points.length+'个。';
 E('my-review-status').textContent='我的复核：'+(d?stateNames[d.status]:'未开始');
 E('my-review-summary').textContent=d?'独立草稿 '+M.active(d).length+'点 / '+d.pairs.length+'个上下点组；'+(M.hasChanges(d)?'有我的修改':'未改变基准点和配对')+'。未应用到正式数据。':'点击图片上方操作开始；外部结论与我的状态分别保存。';
}

const stateNames={completed:'我已完成本条',draft:'草稿',confirmed:'已确认补丁',deferred:'已暂缓',kept:'保持原裁决'};
let records={},blocked=false,selectedPoint=null,pairTop=null,drag=null,suppressClick=false,storageFailed=false,runtimeImageError=false;
const row=()=>D.cases[currentCase],draft=()=>records[row().record_id],view=()=>versions[currentVariant];
const points=()=>view()==='draft'?(draft()?.points||[]):(row().versions[view()]?.points||[]);
const shownPairs=()=>view()==='draft'?(draft()?.pairs||[]):(row().versions[view()]?.pairs||[]);
const point=id=>points().find(p=>p.id===id),textStatus=t=>E('edit-status').textContent=t;
const editable=()=>!blocked&&!storageFailed&&view()==='draft'&&!!draft();
const sorter=LegacyPairSort({container:E('pair-drag-list'),getPairs:shownPairs,label,isEditable:editable,redraw:draw,
 onOrder:(order,action)=>update(d=>M.reorder(d,order,action),'角点顺序与相邻连线已更新并自动保存；原点号、坐标及上下配对不变。'),
 onSelect:i=>selectPoint(shownPairs()[i]?.[0]),selectedPosition:()=>shownPairs().findIndex(p=>p.includes(selectedPoint))});
E('pair-earlier').onclick=()=>sorter.moveSelected(-1);E('pair-later').onclick=()=>sorter.moveSelected(1);E('show-ring-preview').onchange=draw;
E('pair-by-x').onclick=()=>update(d=>M.pairByX(d),'剩余点已按周期x配对；请核对候选，再拖动卡片调整顺序。');

function save(next,message='已自动保存，正式数据不变。'){
 try{M.exportFile(D,next);}catch(e){textStatus('未执行：'+e.message);return false;}
 records=next;
 try{localStorage.setItem(key,JSON.stringify(next));storageFailed=false;render();textStatus(message);return true;}
 catch(e){storageFailed=true;render();textStatus('本次改动尚未写入浏览器：'+e.message+'。请先导出审核返回；已保存的旧草稿仍保留。');return false;}
}
function update(fn,message){if(!editable()){textStatus(storageFailed?'先保存或导出尚未保存的改动。':'请点击补点、删点或移动点开始编辑。');return false;}
 try{return save({...records,[row().record_id]:fn(draft())},message);}catch(e){textStatus('未执行：'+e.message);return false;}}
try{records=JSON.parse(localStorage.getItem(key)||'{}');M.exportFile(D,records);}catch(e){blocked=true;records={};textStatus('本地草稿校验失败，编辑停止。可导出原缓存备份。'+e.message);}
function cancelAction(message='已取消当前操作；已保存的点修改保留。'){
 pendingAction=null;selectedPoint=null;pairTop=null;drag=null;suppressClick=false;E('edit-tool').value='select';E('baseline-choice').hidden=true;render();textStatus(message);
}
function resumeAction(action){
 if(view()!=='draft'){E('variant-select').value='3';chooseVariant(3);}
 pendingAction=null;E('baseline-choice').hidden=true;E('edit-tool').value=action.tool;pairTop=null;render();
 if(action.tool==='order'&&!draft().pairs.length&&!draft().operations.length){update(d=>M.pairByX(d),'已按周期x建立可撤销的点对候选；请核对上下配对，再拖动卡片调整顺序。');return;}
 textStatus('沿用独立草稿，基准：'+row().versions[draft().base_version].name+'；已有改动已保留。');
 if(action.run)action.run();
}
function prepareBase(version,action){
 if(draft())return resumeAction(action);
 try{if(save({...records,[row().record_id]:M.create(row(),version)},'已自动准备独立草稿。'))resumeAction(action);}catch(e){textStatus(e.message);}
}
function startAction(tool,run){
 if(tool==='select'&&!run)return cancelAction();
 if(blocked||storageFailed)return textStatus('编辑暂停：先保存或导出现有改动。');
 if(!originalImage)return textStatus('原图还未就绪，请等原图加载后再编辑。');
 const action={tool,run};if(draft())return resumeAction(action);
 const candidates=['current','historical','raw'].filter(v=>row().versions[v]?.available);
 const distinct=candidates.filter((v,i)=>!candidates.slice(0,i).some(w=>JSON.stringify(row().versions[v].points)===JSON.stringify(row().versions[w].points)&&JSON.stringify(row().versions[v].pairs)===JSON.stringify(row().versions[w].pairs)));
 if(distinct.length===1)return prepareBase(distinct[0],action);
 if(!distinct.length)return textStatus('没有可编辑的点版本，请暂缓并核对来源。');
 pendingAction=action;E('edit-tool').value='select';pairTop=null;
 E('baseline-explanation').textContent=row().history?'历史已确认删 '+row().history.removed_original_labels.join('、')+'。选择历史版本会保留这些删除；原始版本仍含已删点，只有你明确选择才使用。':'当前有效点与原始点有差异。请选择这次审核的点版本，已有正式数据不会改变。';
 E('baseline-options').replaceChildren(...distinct.map(v=>{const b=document.createElement('button');b.textContent=v==='historical'?'按历史生效版本开始（保留删除结果）':v==='current'?'按当前有效版本开始':'按原始版本开始'+(row().history?'（包含历史已删点）':'');b.className=v==='raw'?'':'primary';b.onclick=()=>prepareBase(v,pendingAction);return b;}));
 E('baseline-choice').hidden=false;render();textStatus('请选择本次编辑基准，然后直接在原图操作。');
}
function renderQuick(){
 const tool=E('edit-tool').value,d=draft(),selected=point(selectedPoint);
 const guides={order:'',select:'点击“补点”，再在原图目标位置单击一次；也可点击删点或移动点。',add:'补点模式：在原图目标位置单击一次。补完自动结束；继续补点请再点“补点”。',delete:selected&&!selected.deleted?'已选 '+selected.label+'：点击“删除所选点”。可用“撤销上一步”恢复本次删除。':'删点模式：先单击原图上的点，再点“删除所选点”。',move:'移动点模式：按住原图上的点并拖到目标位置；也可先选点，再单击目标位置。',pair:pairTop?'已选上点 '+label(pairTop)+'；再单击对应下点。':'上下配对：先单击上点，再单击对应下点。'};
 E('mode-guide').textContent=pendingAction?'先选择下面的点版本，选好后即可在原图操作。':guides[tool];
 E('panorama').dataset.tool=tool;E('review-order').hidden=tool!=='order';E('mode-guide').hidden=tool==='order';E('edit-selection').hidden=tool==='order'&&!selected;
 for(const b of document.querySelectorAll('[data-quick-tool]')){b.setAttribute('aria-pressed',String(b.dataset.quickTool===tool));b.disabled=blocked||storageFailed||!originalImage;}
 E('undo-step').disabled=!editable()||!M.canUndo(d);E('quick-delete').hidden=tool!=='delete';E('quick-delete').disabled=!editable()||!selected||selected.deleted;
 E('save-draft').disabled=blocked||!d;for(const id of ['confirm-patch','complete-next','defer-patch'])E(id).disabled=blocked||storageFailed||!originalImage;E('save-indicator').className=storageFailed?'unsaved':'';
 E('save-indicator').textContent=storageFailed?'尚未保存到浏览器，请先导出备份':d?'已自动保存 '+new Date(d.updated_at).toLocaleTimeString('zh-CN')+' · '+stateNames[d.status]:'尚未编辑 · 点击操作即可开始';
}
function label(id){return row().versions.raw.points.find(p=>p.id===id)?.label||draft()?.points.find(p=>p.id===id)?.label||id;}
function selectPoint(id){
 selectedPoint=id;const p=point(id)||row().versions.raw.points.find(p=>p.id===id);
 if(p){E('point-x').value=p.x;E('point-y').value=p.y;}render();
}
function pick(id){
 const p=point(id);if(!p||p.deleted)return selectPoint(id);
 if(E('edit-tool').value==='pair'&&editable()){
  if(pairTop===null){pairTop=id;selectPoint(id);textStatus('已选上点 '+label(id)+'；再选下点。');}
  else{const top=pairTop;pairTop=null;update(d=>M.pair(d,top,id));selectPoint(id);}
 }else selectPoint(id);
}
function coords(e){const r=E('panorama').getBoundingClientRect();return [(e.clientX-r.left)/r.width*1024,(e.clientY-r.top)/r.height*512];}
function hit(e){const r=E('panorama').getBoundingClientRect(),xy=coords(e);let id=null,best=14;
 for(const p of points()){if(p.deleted||p.x<0||p.x>=1024||p.y<0||p.y>512)continue;
 const dist=Math.hypot((p.x-xy[0])*r.width/1024,(p.y-xy[1])*r.height/512);if(dist<best){best=dist;id=p.id;}}return id;}
const meta=()=>({source:E('point-provenance').value.trim()||'用户在原图手动新增',imputed:E('point-imputed').checked,target_photo_sha256:row().photo_hash});
function addAt(x,y){
 if(!editable())return startAction('add',()=>addAt(x,y));
 if(update(d=>M.add(d,x,y,undefined,meta()),'已补1点并自动保存。补点模式已结束；继续补点请再点“补点”。')){selectedPoint=draft().points.at(-1).id;E('edit-tool').value='select';render();}
}
function moveAt(x,y){if(!selectedPoint)return textStatus('先选择要移动的稳定点号。');update(d=>M.move(d,selectedPoint,x,y),'移动已存草稿，相关配对已解除；请重新核对配对。');}
const oldFail=fail;fail=function(message){oldFail(message);if(!originalImage){runtimeImageError=true;E('texture-state').textContent='原图加载失败；确认修点已停止';textStatus('原图加载失败 / 缺失。仍可检查稳定原坐标，不能确认修点。');draw();}};
E('panorama').onclick=e=>{
 if(suppressClick){suppressClick=false;return;}
 const tool=E('edit-tool').value,id=hit(e);
 if(tool==='add'&&editable())addAt(...coords(e));
 else if(tool==='move'&&editable()&&selectedPoint&&!id)moveAt(...coords(e));
 else if(id)pick(id);
};
E('panorama').onpointerdown=e=>{if(E('edit-tool').value!=='move'||!editable())return;const id=hit(e);if(id){selectedPoint=id;drag={id,x:e.clientX,y:e.clientY};E('panorama').setPointerCapture(e.pointerId);selectPoint(id);}};
E('panorama').onpointerup=e=>{if(!drag)return;const start=drag;drag=null;if(Math.hypot(e.clientX-start.x,e.clientY-start.y)>3){selectedPoint=start.id;moveAt(...coords(e));suppressClick=true;}};
E('panorama').onpointercancel=()=>drag=null;
function draw(){
 const c=E('panorama'),ctx=c.getContext('2d');c.width=2048;c.height=1024;
 ctx.fillStyle='#e8ece6';ctx.fillRect(0,0,c.width,c.height);
 if(originalImage)ctx.drawImage(originalImage,0,0,c.width,c.height);
 else{ctx.fillStyle='#644d2c';ctx.font='32px Segoe UI';ctx.fillText(runtimeImageError?'原图加载失败 / 缺失；请核对路径':row().photo.available?'原图加载中…':'原图缺失；请核对版本与路径',40,70);}
 ctx.save();ctx.scale(2,2);
 const active=points(),ps=shownPairs(),byId=new Map(active.map(p=>[p.id,p]));
 // 预览沿有序完整上下点组连接；原始点数组保持原序。
 const closed=ps.length>=3&&active.filter(p=>!p.deleted).length===2*ps.length;
 if(E('show-ring-preview').checked&&ps.length>=2){
  for(let i=0;i<(closed?ps.length:ps.length-1);i++)for(const role of [0,1]){
   const a=byId.get(ps[i][role]),b=byId.get(ps[(i+1)%ps.length][role]);if(!a||!b||a.deleted||b.deleted||a.x<0||a.x>=1024||b.x<0||b.x>=1024)continue;
   let dx=b.x-a.x;if(dx>512)dx-=1024;if(dx<-512)dx+=1024;
   ctx.strokeStyle=role===0?'#bc741b':'#29845e';ctx.lineWidth=1.5;ctx.setLineDash([5,3]);ctx.beginPath();let last=null;
   for(let j=0;j<=64;j++){const x=((a.x+dx*j/64)%1024+1024)%1024,y=a.y+(b.y-a.y)*j/64;if(last===null||Math.abs(x-last)>512)ctx.moveTo(x,y);else ctx.lineTo(x,y);last=x;}ctx.stroke();ctx.setLineDash([]);
  }
 }
 // 原有上下对应线仍保留。

 for(const [a,b] of ps){const p=byId.get(a),q=byId.get(b);if(!p||!q||p.deleted||q.deleted)continue;
 ctx.strokeStyle='#428be0';ctx.lineWidth=1.6;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();}
 const raw=row().versions.raw.points,shown=new Set(active.filter(p=>!p.deleted).map(p=>p.id));
 const deleted=['historical','draft'].includes(view())?[...raw.filter(p=>!shown.has(p.id)),...active.filter(p=>p.deleted&&p.origin==='user_added')]:active.filter(p=>p.deleted);
 for(const p of deleted){if(p.x<0||p.x>=1024||p.y<0||p.y>512)continue;ctx.strokeStyle='#888';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(p.x-4,p.y-4);ctx.lineTo(p.x+4,p.y+4);ctx.moveTo(p.x+4,p.y-4);ctx.lineTo(p.x-4,p.y+4);ctx.stroke();if(E('edit-labels').checked){ctx.fillStyle='#666';ctx.font='11px Segoe UI';ctx.fillText(p.label+' 已删',p.x+6,p.y-6);}}
 for(const p of active){if(p.deleted||p.x<0||p.x>=1024||p.y<0||p.y>512)continue;const selected=p.id===selectedPoint;
 ctx.beginPath();ctx.arc(p.x,p.y,selected?5:3.2,0,2*Math.PI);ctx.fillStyle=selected?'#ffc562':p.origin==='original'?'#eaffee':'#ffb5f2';ctx.fill();ctx.strokeStyle='#315d43';ctx.lineWidth=1;ctx.stroke();
 if(E('edit-labels').checked){ctx.font='bold 11px Segoe UI';const t=p.label;ctx.fillStyle='#244d35';ctx.fillRect(p.x+5,p.y-17,ctx.measureText(t).width+7,15);ctx.fillStyle='white';ctx.fillText(t,p.x+8,p.y-6);}}
 ctx.restore();renderQuick();
}
drawPanorama=draw;
const oldChooseCase=chooseCase;
chooseCase=async function(i){if(storageFailed){textStatus('草稿未成功保存，暂不能切换。请先保存或导出。');E('case-select').value=currentCase;return;}
 sorter.cancel();pendingAction=null;selectedPoint=null;pairTop=null;drag=null;E('edit-tool').value='select';E('baseline-choice').hidden=true;runtimeImageError=false;E('version-ack').checked=false;
 await oldChooseCase(i);if(draft()){E('variant-select').value='3';chooseVariant(3);}render();
 try{localStorage.setItem(uiKey,JSON.stringify({record_id:row().record_id,scope:E('scope-filter').value}));}catch(e){}
};
const oldChooseVariant=chooseVariant;
chooseVariant=function(i,reset){pendingAction=null;selectedPoint=null;pairTop=null;E('edit-tool').value='select';E('baseline-choice').hidden=true;E('version-ack').checked=false;oldChooseVariant(i,reset);render();};
function eligible(i){const c=D.cases[i],f=E('review-filter').value,state=E('status-filter').value,s=records[c.record_id]?.status||'pending';
 return scopeIndices().includes(i)&&(!f||c.reviewer.reviewer_conclusion===f)&&(!state||state==='pending'&&!['completed','confirmed','deferred','kept'].includes(s)||state===s);}
function navigate(delta){const list=scopeIndices().filter(eligible);if(!list.length)return;const p=list.indexOf(currentCase);chooseCase(list[p<0?(delta>0?0:list.length-1):(p+delta+list.length)%list.length]);}
E('previous').onclick=()=>navigate(-1);E('next').onclick=()=>navigate(1);
function rebuildReviewFilter(){const f=E('review-filter'),old=f.value,counts={};scopeIndices().forEach(i=>{const category=D.cases[i].reviewer.reviewer_conclusion;counts[category]=(counts[category]||0)+1;});
 f.replaceChildren(new Option('全部意见',''),...Object.entries(counts).map(([category,n])=>new Option(category+' · '+n,category)));f.value=old in counts?old:'';}
for(const id of ['scope-filter','review-filter','status-filter'])E(id).onchange=()=>{if(id==='scope-filter'){rebuildReviewFilter();try{localStorage.setItem(uiKey,JSON.stringify({record_id:row().record_id,scope:E(id).value}));}catch(e){}}const i=scopeIndices().find(eligible);if(i!==undefined){if(!eligible(currentCase))chooseCase(i);else render();}else{render();textStatus('此筛选没有记录。');}};
rebuildReviewFilter();
function render(){
 const r=row(),d=draft(),v=view(),ps=points(),pairs=shownPairs();
 const scope=scopeIndices();E('case-select').replaceChildren(...scope.flatMap((i,j)=>eligible(i)||i===currentCase?[new Option((j+1)+' · '+D.cases[i].record_id+' · '+D.cases[i].image_code+' · '+D.cases[i].worker,i)]:[]));E('case-select').value=currentCase;
 E('case-count').textContent=(scope.indexOf(currentCase)+1)+' / '+scope.length;
 const counts={draft:0,completed:0,confirmed:0,deferred:0,kept:0};scope.forEach(i=>{const s=records[D.cases[i].record_id]?.status;if(s)counts[s]++;});
 E('review-progress').textContent=(E('scope-filter').value==='selected'?'本轮'+D.review_queue.selected_records+'份 / '+D.review_queue.selected_images+'图':'原109份 / 71图')+' · 待审 '+(scope.length-counts.completed-counts.confirmed-counts.deferred-counts.kept)+' · 草稿 '+counts.draft+' · 我已完成 '+(counts.completed+counts.confirmed)+' · 暂缓 '+counts.deferred+' · 保持 '+counts.kept;
 E('raw-title').textContent='配对 / 环 / 3D状态';
 E('version-summary').textContent='原始：'+r.versions.raw.points.length+'点  ｜  历史：'+(r.history?(r.versions.historical.points.length+'点，已删 '+r.history.removed_original_labels.join('/')):'未见直接点级确认')+'  ｜  当前有效：'+(r.current.preprocessed_points?.length??'缺失')+'  ｜  新草稿：'+(d?M.active(d).length+'点，'+d.status:'未建立');
 E('edit-proposals').replaceChildren(...(r.proposed_deletions||[]).map(p=>{const b=document.createElement('button');b.textContent=p.derived_original_label+'（待核删除提名）';b.title='原坐标 '+p.x_1024+', '+p.y_512+'；点击只选点，不删除';b.onclick=()=>selectPoint(p.stable_raw_point_key);return b;}));
 E('reviewer-text').textContent='新意见（待审）：'+r.reviewer.reviewer_conclusion+'；'+(r.reviewer.reviewer_note||'未给具体点位/坐标')+'\n历史：'+r.reviewer.combined_history_class;
 E('version-warning').textContent=r.warnings.join('\n');
 const selected=point(selectedPoint),raw=r.versions.raw.points.find(p=>p.id===selectedPoint);
 E('edit-selection').textContent=(selected||raw)?(selected||raw).label+' · 原坐标 '+(raw?raw.x+', '+raw.y:'新增非原点')+' · 查看 '+((selected?.x??'—')+', '+(selected?.y??'—'))+(selected?.deleted?' · 已删':''):'选择稳定点号；越界点可从下方点号或坐标表选择。';
 E('edit-point-buttons').replaceChildren(...ps.map(p=>{const b=document.createElement('button');b.textContent=p.label+(p.deleted?' ×':'');b.title=p.id+' · '+p.x+', '+p.y;b.className=p.id===selectedPoint?'selected-point':'';b.onclick=()=>pick(p.id);return b;}));
 E('edit-pairs').replaceChildren(...pairs.map(p=>{const li=document.createElement('li');li.append(label(p[0])+' 上 ↔ '+label(p[1])+' 下 ');const b=document.createElement('button');b.textContent='解除';b.disabled=!editable();b.onclick=()=>update(d=>M.unpair(d,p));li.append(b);return li;}));
 const valid=ps.filter(p=>!p.deleted).length,paired=new Set(pairs.flat()).size;
 E('pair-status').textContent='查看：'+(v==='draft'?'新草稿':r.versions[v].name)+' · 有效点 '+valid+' · 配对 '+pairs.length+' · 未配对 '+(valid-paired)+' · 冻结输入确认环：缺失 · 新补丁状态 '+(d?.status||'待审')+'。';
 E('point-geometry-empty').textContent='原始点 '+r.versions.raw.points.length+' · 冻结研究输入有效点 '+(r.current.preprocessed_points?.length??'缺失')+'\n查看版本 '+valid+' 点 / '+pairs.length+' 对。草稿点对与连接顺序不会自动生成正式3D房间。\n配对仅记录上下对应，不推断水平连接。';
 E('create-draft').disabled=blocked||!!d||v==='draft'||!r.versions[v]?.available;
 for(const id of ['add-point','move-point','delete-point','save-draft','reset-draft','confirm-patch','defer-patch','keep-decision','review-note'])E(id).disabled=!editable();
 E('move-point').disabled=!editable()||!selected||selected.deleted;E('delete-point').disabled=!editable()||!selected||selected.deleted;
 E('review-note').value=d?.note||'';
 E('review-source').textContent=JSON.stringify({record_id:r.record_id,canonical_object_id:r.canonical_object_id,image_id:r.image_id,source:r.source_identity,
 source_hash:r.source_hash,raw_hash:r.raw_hash,current_hash:r.current_hash,photo:r.photo,local_coordinate_parity:r.local_coordinate_parity,
 eligibility:{cleaning:r.current.cleaning_disposition,historical_exclusion_reason:r.current.review.historical_exclusion_reason,independent_vote_eligible:r.current.independent_vote_eligible,reasons:r.current.independent_vote_reasons,quality:r.current.main_quality_gate},
 historical:r.history,new_review:r.reviewer,current_initialization:r.current.initialization_notes,draft:d},null,2);
 const tbody=E('stable-point-table').querySelector('tbody');
 tbody.replaceChildren(...[...r.versions.raw.points,...ps.filter(p=>p.origin==='user_added')].map(p=>{const q=ps.find(x=>x.id===p.id),tr=document.createElement('tr');
 for(const s of [p.label+'\n'+p.id,p.origin==='original'?p.x+', '+p.y:'新增，非原作答',q?q.x+', '+q.y:'—',q?.deleted?'草稿删除':q?'保留':v==='historical'?'历史删除':v==='current'?'当前缺失':'不在基准']){
  const td=document.createElement('td');td.textContent=s;tr.append(td);}tr.onclick=()=>selectPoint(p.id);return tr;}));
 renderOrder();renderReviewer();draw();
}
E('create-draft').onclick=()=>{if(draft())return resumeAction({tool:'select'});try{const d=M.create(row(),view());if(save({...records,[row().record_id]:d},'草稿已建立，明确基准：'+view()+'；原正式数据不变。')){E('variant-select').value='3';chooseVariant(3);}}catch(e){textStatus(e.message);}};
E('reset-draft').onclick=()=>update(d=>M.reset(d),'已撤回至本次草稿基准；撤回前后与原操作均保留。');
E('cancel-selection').onclick=()=>cancelAction();
E('edit-tool').onchange=()=>startAction(E('edit-tool').value);
for(const b of document.querySelectorAll('[data-quick-tool]'))b.onclick=()=>startAction(b.dataset.quickTool);
E('undo-step').onclick=()=>{cancelAction();update(d=>M.undo(d),'已撤销最近一步点操作并自动保存，原操作与撤销记录均保留。');};
E('quick-delete').onclick=()=>{if(update(d=>M.remove(d,selectedPoint),'已删除所选点并自动保存；可撤销上一步。')){E('edit-tool').value='select';selectedPoint=null;render();}};
document.addEventListener('keydown',e=>{if(e.key==='Escape')cancelAction();});
window.addEventListener('beforeunload',e=>{if(storageFailed){e.preventDefault();e.returnValue='';}});
E('edit-labels').onchange=draw;
E('edit-zoom').oninput=()=>{E('panorama').style.width=100*Number(E('edit-zoom').value)+'%';};
function inputCoords(fn){try{if(!E('point-x').value.trim()||!E('point-y').value.trim())throw Error('请填写准确x、y坐标');fn(Number(E('point-x').value),Number(E('point-y').value));}catch(e){textStatus(e.message);}}
E('add-point').onclick=()=>inputCoords(addAt);
E('move-point').onclick=()=>inputCoords(moveAt);
E('delete-point').onclick=()=>update(d=>M.remove(d,selectedPoint));
E('review-note').oninput=()=>{if(editable()){const note=E('review-note').value;update(d=>M.status(d,'draft',note));}};
E('save-draft').onclick=()=>{if(draft())save(records,'已保存到此浏览器；刷新或切换记录可继续。请导出审核返回另存。');};
function finish(state,advance=false){
 if(state==='confirmed')state='completed';
 if(blocked||storageFailed)return textStatus('请先保存或导出尚未保存的改动。');
 if(!originalImage||row().photo.dimension_conflict)return textStatus('原图缺失或尺寸冲突，不能完成本条；请核对实际原图。');
 const mark=()=>{
  if(state==='kept'&&M.hasChanges(draft()))return textStatus('当前有我的点修改，请完成本条或稍后再看。');
  const ok=update(d=>({...M.status(d,state,E('review-note').value),completed_at:new Date().toISOString()}),'已记录我的复核状态；独立草稿已保存，正式数据不变。');
  if(ok&&advance)navigate(1);
 };
 if(!draft()||view()!=='draft')return startAction('select',mark);
 mark();
}
E('confirm-patch').onclick=()=>finish('completed');E('complete-next').onclick=()=>finish('completed',true);E('defer-patch').onclick=()=>finish('deferred');E('keep-decision').onclick=()=>finish('kept');
function download(value,name){const a=document.createElement('a'),u=URL.createObjectURL(new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type:'application/json'}));a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
E('export-patches').onclick=()=>{if(blocked)return download(localStorage.getItem(key)||'{}','109审核缓存_校验失败备份.json');try{download(M.exportFile(D,records),'109点编辑审核返回_20261009.json');textStatus('已导出独立审核返回JSON；未应用到正式数据。');}catch(e){textStatus('导出失败：'+e.message);}};
E('import-patches').onchange=async e=>{try{if(blocked)throw Error('本地损坏缓存须先备份处理');const file=JSON.parse(await e.target.files[0].text());const next=M.importFile(D,file,records);save(next,'导入完成。');}catch(e){textStatus('导入未应用：'+e.message);}e.target.value='';};
document.addEventListener('studio-case',()=>render());
window.POINT_REVIEW_STATE=()=>JSON.parse(JSON.stringify({current:row().record_id,version:view(),selected:selectedPoint,records,key,imageReady:!!originalImage,points:points(),pairs:shownPairs()}));
let lastView=null;try{lastView=JSON.parse(localStorage.getItem(uiKey)||'null');}catch(e){}
if(lastView?.scope==='all'){E('scope-filter').value='all';rebuildReviewFilter();}
const resumeIndex=D.cases.findIndex(c=>c.record_id===lastView?.record_id),first=scopeIndices()[0];
if(scopeIndices().includes(resumeIndex)&&resumeIndex!==currentCase)chooseCase(resumeIndex);else if(!scopeIndices().includes(currentCase))chooseCase(first);else{if(draft()){E('variant-select').value='3';chooseVariant(3);}render();}
})();
