const $=selector=>document.querySelector(selector);
const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const conditions={manual:'人工',semi:'半自动',oos:'OOS'};
const flagLabels={gt_problem:'GT / 参考问题',gt_uncertain:'GT 不确定',gt_detail_omission:'GT 细节遗漏',image_hold:'分析暂缓',current_pending:'问题待定',applicability_pending:'适用性待定',oos:'OOS · 仅诊断',no_retained:'无保留作答'};
const state={images:[],byId:new Map(),plans:new Map(),details:new Map(),detailId:null,detailToken:0,lastFocus:null};

export function parseAdditionalPeople(value){
 const text=String(value).trim();
 if(text==='')return null;
 if(!/^\d+$/.test(text)||!Number.isSafeInteger(Number(text)))throw new Error('请填写 0 或正整数；也可以留空。');
 return Number(text);
}

// ERP跨接缝的边在左右边界分开画，避免穿过整张原图。
export function wrapSegment(a,b){
 let [x1,y1]=a,[x2,y2]=b;
 if(Math.abs(x2-x1)<=512)return [[a,b]];
 x2+=x2>x1?-1024:1024;
 const edge=x2<0?0:1024;
 const y=y1+(y2-y1)*(edge-x1)/(x2-x1);
 return [[[x1,y1],[edge,y]],[[edge===0?1024:0,y],[b[0],b[1]]]];
}

export function floorToERP([x,z]){
 return [((Math.atan2(x,-z)/(2*Math.PI)+.5)*1024+1024)%1024,
  (.5+Math.atan2(1,Math.hypot(x,z))/Math.PI)*512];
}
export function projectFloorEdges(floor){
 const segments=[];
 floor.forEach((a,index)=>{
  const b=floor[(index+1)%floor.length];let previous=floorToERP(a);
  for(let step=1;step<=80;step++){
   const point=floorToERP([a[0]+(b[0]-a[0])*step/80,a[1]+(b[1]-a[1])*step/80]);
   segments.push(...wrapSegment(previous,point));previous=point;
  }
 });
 return segments;
}
function sceneHTML(image,detail=false){
 if(!image.scene)return '';
 const scene=image.scene;
 const recorded=scene.doorway_status&&!['none','not_recorded'].includes(scene.doorway_status);
 return (detail||recorded?`<span class="flag doorway ${!recorded?'unknown':''}">${escapeHTML(scene.doorway_label)}</span>`:'')+((detail||scene.conditional_difficulty!==image.difficulty.label)&&scene.conditional_difficulty?`<span class="flag conditional">固定目标条件难度 · ${escapeHTML(scene.conditional_difficulty)}</span>`:'');
}

async function request(url,options){
 const response=await fetch(url,{signal:AbortSignal.timeout(15000),...options});
 if(!response.ok){let message=`请求失败（${response.status}）`;try{const body=await response.json();message=body.error??body.detail??message;}catch{}throw new Error(message);}
 return response.json();
}
function planFor(id){return state.plans.get(id);}
function score(value){return Number.isFinite(value)?value.toFixed(1):'—';}
function flagHTML(image){
 const flags=Object.entries(image.flags).filter(([,on])=>on).map(([key])=>`<span class="flag ${key==='gt_problem'?'error':'warn'}">${escapeHTML(flagLabels[key]??key)}</span>`);
 if(image.multiple_spaces)flags.unshift(`<span class="flag space" title="${escapeHTML(image.space_notice)}">多空间 / 参考版本</span>`);
 if(image.new_batch)flags.unshift(`<span class="flag new-batch" title="${escapeHTML(image.new_batch.note)}">${image.new_batch.admitted?'新增已纳库存':'新增待纳入'} ${image.new_batch.records}份 / ${image.new_batch.people===null?'人数待核':image.new_batch.people+'人'}${image.new_batch.admitted?' · 质量可用 '+image.new_batch.quality_records+' / 受限 '+image.new_batch.limited_records:''}</span>`);
 return sceneHTML(image)+flags.join('');
}
function qualityHTML(image){
 const rows=image.quality_groups.filter(group=>group.condition!=='oos').map(group=>
  `<div class="quality-group"><div class="quality-label">${escapeHTML(conditions[group.condition]??group.condition)}${image.multiple_spaces?' · '+escapeHTML(group.space_label??group.target_id):''}</div><div class="quality-value"><span>B8L2 · 主</span><b>${score(group.B8L2)}</b><span class="quality-n">共同 n = ${group.n}</span></div><div class="quality-value"><span>D10 · 并列</span><b>${score(group.D10)}</b></div></div>`);
 if(!rows.length)rows.push('<div>当前暂无可用质量评分</div>');
 if(image.flags.oos)rows.push('<div class="diagnostic">OOS 分数仅诊断，不计质量均值</div>');
 return rows.join('');
}
function saveMessage(plan){
 if(plan.invalidCount)return ['error','人数格式有误，尚未保存'];
 if(plan.status==='error')return ['error','保存失败 · 正在重试'];
 if(plan.status==='saving')return ['saving','正在保存…'];
 if(plan.status==='pending')return ['pending','待保存…'];
 return ['saved',plan.updated_at?'已保存':'自动保存'];
}
function syncEditors(id){
 const plan=planFor(id);const [status,message]=saveMessage(plan);
 document.querySelectorAll('.plan-editor').forEach(editor=>{
  if(editor.dataset.imageId!==id)return;
  const count=editor.querySelector('.add-count'),note=editor.querySelector('.plan-note');
  if(count!==document.activeElement)count.value=plan.additional_people??'';
  if(note!==document.activeElement)note.value=plan.note;
  count.setAttribute('aria-invalid',String(Boolean(plan.invalidCount)));
  const label=editor.querySelector('.save-state');label.dataset.state=status;label.textContent=message;
  label.title=plan.error??'';
  label.setAttribute('role',status==='error'?'alert':'status');editor.classList.toggle('save-error',status==='error');
 });
}
function renderStats(){
 const all=[...state.plans.values()];
 $('#planned-total').textContent=all.reduce((sum,p)=>sum+(p.additional_people??0),0)+' 人';
 $('#planned-images').textContent=all.filter(p=>p.additional_people!==null||p.note.trim()).length+' 张图片有填写';
}
function scheduleSave(id){
 const plan=planFor(id);clearTimeout(plan.timer);
 if(plan.invalidCount){syncEditors(id);return;}
 plan.revision++;plan.status='pending';plan.error=null;syncEditors(id);
 plan.timer=setTimeout(()=>flushSave(id),600);
}
async function flushSave(id){
 const plan=planFor(id);if(plan.inflight||plan.invalidCount||plan.revision===plan.savedRevision)return;
 plan.inflight=true;plan.status='saving';syncEditors(id);
 const revision=plan.revision,payload={additional_people:plan.additional_people,note:plan.note};
 try{
  const result=await request('/api/plans/'+encodeURIComponent(id),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  plan.savedRevision=revision;plan.updated_at=result.saved_at??result.plan.updated_at;plan.error=null;
  plan.status=plan.revision===revision?'saved':'pending';
 }catch(error){plan.status='error';plan.error=error.message;plan.timer=setTimeout(()=>flushSave(id),5000);}
 finally{plan.inflight=false;syncEditors(id);if(plan.status==='pending')flushSave(id);}
}
function bindEditor(editor,id){
 editor.dataset.imageId=id;
 const count=editor.querySelector('.add-count'),note=editor.querySelector('.plan-note');
 count.setAttribute('aria-label',state.byId.get(id).image_code+' 补充人数');
 note.setAttribute('aria-label',state.byId.get(id).image_code+' 补充备注');
 count.addEventListener('input',()=>{
  const plan=planFor(id);
  try{if(count.validity.badInput)throw new Error('请填写整数');plan.additional_people=parseAdditionalPeople(count.value);plan.invalidCount=false;scheduleSave(id);}
  catch(error){plan.invalidCount=true;plan.error=error.message;clearTimeout(plan.timer);syncEditors(id);}
  renderStats();syncEditors(id);
 });
 note.addEventListener('input',()=>{planFor(id).note=note.value;scheduleSave(id);renderStats();syncEditors(id);});
 syncEditors(id);
}
function matches(image){
 const plan=planFor(image.image_id),query=$('#search').value.trim().toLowerCase();
 if(query&&![image.image_code,image.image_id,image.building_id,plan.note,...image.notes].join(' ').toLowerCase().includes(query))return false;
 if($('#building-filter').value&&image.building_id!==$('#building-filter').value)return false;
 if($('#difficulty-filter').value&&image.difficulty.label!==$('#difficulty-filter').value)return false;
 const situation=$('#scene-filter').value;
 if(situation==='doorway:any'&&(!image.scene?.doorway_status||['none','not_recorded'].includes(image.scene.doorway_status)))return false;
 if(situation.startsWith('doorway:')&&situation!=='doorway:any'&&image.scene?.doorway_status!==situation.slice(8))return false;
 if(situation==='oos'&&!image.flags.oos)return false;
 const status=$('#status-filter').value;if(status==='new_batch'&&!image.new_batch)return false;
 if(status==='removed'&&!image.counts.removed_records)return false;
 if(status&&!['new_batch','removed'].includes(status)&&!image.flags[status])return false;
 const space=$('#space-filter').value;if(space==='multiple'&&!image.multiple_spaces)return false;
 if(space==='user_candidates'&&!image.spaces.some(s=>s.user_candidate))return false;
 if(space==='single'&&image.spaces.length!==1)return false;
 if(space==='incomplete'&&!image.spaces.some(s=>!s.reference_full_available))return false;
 return !$('#filled-only').checked||plan.additional_people!==null||Boolean(plan.note.trim());
}
let thumbnailObserver;
function renderGallery(){
 thumbnailObserver?.disconnect();
 thumbnailObserver=new IntersectionObserver(entries=>{
  for(const entry of entries){
   if(!entry.isIntersecting)continue;
   const photo=entry.target;
   photo.src=photo.dataset.src;
   delete photo.dataset.src;
   thumbnailObserver.unobserve(photo);
  }
 },{rootMargin:'200px 0px'});
 const images=state.images.filter(matches),fragment=document.createDocumentFragment();
 for(const image of images){
  const card=$('#card-template').content.firstElementChild.cloneNode(true);card.dataset.imageId=image.image_id;
  const photo=card.querySelector('img');photo.dataset.src=image.thumbnail_url;photo.alt=image.image_code+' 全景缩略图';
  photo.addEventListener('error',()=>{photo.alt='缩略图暂不可用 · '+image.image_code;});
  card.querySelector('.image-name').textContent=image.image_code;
  const badge=card.querySelector('.difficulty-badge');badge.textContent=(image.difficulty.label||'未分类')+(image.difficulty.qualifier?' · '+image.difficulty.qualifier:'');badge.dataset.level=image.difficulty.label;
  card.querySelector('.card-location').textContent='楼栋 '+image.building_id;
  const count=image.counts;
  card.querySelector('.card-metrics').innerHTML=`<div class="metric"><strong>${count.retained_people}</strong>保留独立人员</div><div class="metric"><strong class="small-value">${count.removed_people} 人 / ${count.removed_records} 份</strong>移出涉及人员 / 作答<br>其中全部移出 ${count.fully_removed_people} 人</div>`;
  card.querySelector('.quality-lines').innerHTML=qualityHTML(image);
  card.querySelector('.card-flags').innerHTML=flagHTML(image);
  for(const button of card.querySelectorAll('.card-image,.image-name'))button.addEventListener('click',()=>{state.lastFocus=button;location.hash='image='+encodeURIComponent(image.image_id);});
  fragment.append(card);
 }
 $('#gallery').replaceChildren(fragment);
 $('#gallery').querySelectorAll('.card-image img').forEach(photo=>thumbnailObserver.observe(photo));
 $('#gallery').querySelectorAll('.plan-editor').forEach(editor=>bindEditor(editor,editor.closest('.image-card').dataset.imageId));
 $('#result-count').textContent=`显示 ${images.length} / ${state.images.length} 张图片`;
 $('#empty').hidden=images.length!==0;
}
function populateFilters(){
 const fill=(id,values)=>{for(const value of [...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN'))){const option=document.createElement('option');option.value=value;option.textContent=value;$(id).append(option);}};
 fill('#building-filter',state.images.map(i=>i.building_id));fill('#difficulty-filter',state.images.map(i=>i.difficulty.label));
 const situationOptions=[['doorway:any','门洞交界 · 全部已登记'],...new Map(state.images.filter(i=>i.scene).map(i=>[i.scene.doorway_status,['doorway:'+i.scene.doorway_status,i.scene.doorway_label]])).values(),['oos','OOS（可与门洞重叠）']];
 for(const [value,label] of situationOptions){const option=document.createElement('option');option.value=value;option.textContent=label;$('#scene-filter').append(option);}
 for(const [value,label] of [['removed','有移出标注'],...Object.entries(flagLabels)]){const option=document.createElement('option');option.value=value;option.textContent=label;$('#status-filter').append(option);}
 if(state.images.some(i=>i.new_batch)){const option=document.createElement('option');option.value='new_batch';option.textContent='新增批次来源';$('#status-filter').append(option);}
 for(const [value,label] of [['multiple','多空间 / 参考版本'],['single','单一空间 / 参考'],['incomplete','完整参考待补']]){const option=document.createElement('option');option.value=value;option.textContent=label;$('#space-filter').append(option);}
 const userScopes=state.images.filter(i=>i.spaces.some(s=>s.user_candidate)).length;
 const option=document.createElement('option');option.value='user_candidates';option.textContent=`你列的候选范围（${userScopes}图）`;$('#space-filter').append(option);
}
function editorHTML(){return `<div class="plan-editor"><div class="plan-input-line"><label>补充人数<input class="add-count" type="number" min="0" step="1" placeholder="未计划" inputmode="numeric"></label><span class="save-state" aria-live="polite"></span></div><label class="note-label"><span class="sr-only">补充备注</span><textarea class="plan-note" rows="3" placeholder="补充备注…"></textarea></label></div>`;}
function overlayMarkup(points,color){
 if(!points||points.length<4)return '';
 const valid=p=>Array.isArray(p)&&p.length>=2&&p.every(Number.isFinite);
 const top=points.filter((_,i)=>i%2===0),bottom=points.filter((_,i)=>i%2===1);let result='';
 const line=(a,b)=>{if(!valid(a)||!valid(b))return;for(const [p,q] of wrapSegment(a,b))result+=`<line x1="${p[0]}" y1="${p[1]}" x2="${q[0]}" y2="${q[1]}" stroke="${color}" vector-effect="non-scaling-stroke" stroke-width="1.7"/>`;};
 for(const ring of [top,bottom])ring.forEach((p,i)=>line(p,ring[(i+1)%ring.length]));
 top.forEach((p,i)=>{if(bottom[i])line(p,bottom[i]);});
 points.filter(valid).forEach(p=>{result+=`<circle cx="${p[0]}" cy="${p[1]}" r="2.2" fill="${color}" stroke="#25352f" stroke-width=".6"/>`;});
 return result;
}
function scatterMarkup(points,color){
 return (points??[]).filter(p=>Array.isArray(p)&&p.length>=2&&p.every(Number.isFinite)).map(p=>
  `<circle cx="${p[0]}" cy="${p[1]}" r="2.5" fill="${color}" stroke="#25352f" stroke-width=".7"/>`).join('');
}
function floorERPMarkup(floor,color){
 if(!floor||floor.length<3)return '';
 return projectFloorEdges(floor).map(([a,b])=>`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>`).join('');
}
function floorBEVMarkup(floor,allFloors){
 if(!floor||floor.length<3)return '<text x="160" y="120" text-anchor="middle" fill="#819087" font-size="13">暂无底面坐标</text>';
 const allPoints=allFloors.flat();
 const xs=[0,...allPoints.map(p=>p[0])],zs=[0,...allPoints.map(p=>p[1])];
 const minX=Math.min(...xs),maxX=Math.max(...xs),minZ=Math.min(...zs),maxZ=Math.max(...zs);
 const scale=Math.min(280/(maxX-minX||1),200/(maxZ-minZ||1));
 const point=([x,z])=>[20+(x-minX)*scale,220-(z-minZ)*scale];
 const origin=point([0,0]);
 return `<polygon points="${floor.map(p=>point(p).join(',')).join(' ')}" fill="#e0f3ef" stroke="#208e85" stroke-width="2"/><circle cx="${origin[0]}" cy="${origin[1]}" r="4" fill="#304e47"/><text x="${origin[0]+7}" y="${origin[1]-7}" fill="#536b5f" font-size="11">相机</text>`;
}
function annotationLabel(a){
 const quality=a.quality_usable?'B8L2 '+score(a.quality?.B8L2)+' / D10 '+score(a.quality?.D10):'未纳入质量';
 return `${a.worker_id} · ${conditions[a.condition]??a.condition} · ${a.retained?'保留':'移出'} · ${quality}`;
}
function candidateHTML(references){
 return `<section class="candidate-panel"><h3>候选空间范围 <span>${references.length} 个范围 / 参考版本</span></h3><p class="detail-note">人工候选单独标识；切换仅用于查看范围，作答与质量仍按原绑定显示。</p>
 <div class="candidate-tabs" aria-label="选择候选空间范围">${references.map((r,i)=>`<button type="button" class="candidate-choice" data-index="${i}" aria-pressed="false"><span class="candidate-type">${r.user_candidate?'你列的候选':'GT / 参考版本'}</span><strong>${escapeHTML(r.label)}</strong><small>${r.current?'当前 · ':''}${r.full_reference_available?'完整参考':'仅底面 / 参考待补'}</small></button>`).join('')}</div>
 <div class="candidate-preview"><div id="candidate-info"></div><div class="bev-wrap"><svg id="candidate-bev" viewBox="0 0 320 240" role="img" aria-label="候选空间俯视图"></svg><span>BEV 底面 · 保持原坐标比例</span></div></div></section>`;
}
function renderDetail(data){
 const image=data.image,id=image.image_id,count=image.counts;
 $('#detail-title').textContent=image.image_code;
 $('#detail-content').innerHTML=`<div class="detail-topline"><span>楼栋 ${escapeHTML(image.building_id)} · ${escapeHTML(image.difficulty.label)} · ${count.retained_people} 名独立人员</span><div class="detail-links"><a href="${escapeHTML(image.original_url)}" target="_blank" rel="noopener">新标签页原图 ↗</a><a href="${escapeHTML(image.original_url)}" download>下载原图</a></div></div>
  <div class="detail-scene">${sceneHTML(image,true)}</div>
  ${candidateHTML(data.references)}
  <div class="panorama-wrap"><img src="${escapeHTML(image.original_url)}" alt="${escapeHTML(image.image_code)} 原始全景"><svg id="annotation-overlay" viewBox="0 0 1024 512" preserveAspectRatio="none" aria-label="已有标注点与边叠加"></svg></div>
  <div class="annotation-controls"><label>已有作答 <select id="annotation-select"><option value="">仅看原图</option>${data.annotations.map((a,i)=>`<option value="${i}">${escapeHTML(annotationLabel(a))}</option>`).join('')}</select></label><label><input id="show-reference" type="checkbox"> 叠加对应参考 <span style="color:#bc8e27">●</span></label><label><input id="show-candidate" type="checkbox" checked> 候选范围 <span style="color:#208e85">●</span></label><span style="color:#cb5a8e">● 作答</span></div>
  <div id="annotation-description" class="annotation-description"></div>
  <div class="detail-metadata"><section class="detail-panel"><h3>人员与质量</h3><p>人工 ${count.manual_people} 人 · 半自动 ${count.semi_people} 人 · OOS ${count.oos_people} 人</p><p>保留 ${count.retained_records} 份 · 移出 ${count.removed_records} 份，涉及 ${count.removed_people} 人（其中整人移出 ${count.fully_removed_people} 人）</p><p>移出明细：用户排除 ${count.user_excluded_records} 份 · 待定 ${count.pending_records} 份 · 非独立等 ${count.nonindependent_records} 份</p><div class="quality-lines">${qualityHTML(image)}</div><div class="card-flags">${flagHTML(image)}</div>${image.new_batch?`<p class="new-batch-note">${image.new_batch.admitted?'新增作答已计入当前人数与份数；评分与限制见来源明细。':'新增批次单列，未加入现有独立人数或质量。'}${escapeHTML(image.new_batch.note)}</p>`:''}</section>
  <section class="detail-panel"><h3>空间与参考</h3>${image.space_notice?`<p>${escapeHTML(image.space_notice)}</p>`:''}${image.spaces.map(s=>`<p>${escapeHTML(s.label??s.target_id)}${s.current?' · 当前空间':''}<br>${s.reference_full_available?'完整参考可用':'完整参考待补'} · 已绑定保留作答 ${s.n_bound_retained} 份</p>`).join('')}</section></div>
  ${image.notes.length?`<section class="detail-panel"><h3>问题与原始备注</h3>${image.notes.map(n=>`<p>${escapeHTML(n)}</p>`).join('')}</section>`:''}
  ${editorHTML()}`;
 bindEditor($('#detail-content .plan-editor'),id);
 const select=$('#annotation-select');
 const first=data.annotations.findIndex(a=>a.retained&&(a.points||a.raw_points));if(first>=0)select.value=String(first);
 let candidateIndex=data.references.findIndex(r=>r.user_candidate&&r.current);
 if(candidateIndex<0)candidateIndex=data.references.findIndex(r=>r.user_candidate);
 if(candidateIndex<0)candidateIndex=data.references.findIndex(r=>r.current);
 if(candidateIndex<0&&data.references.length)candidateIndex=0;
 function draw(){
  const annotation=select.value===''?null:data.annotations[Number(select.value)];
  const reference=annotation?data.references.find(r=>r.target_id===annotation.target_id):data.references.find(r=>r.current);
  const candidate=data.references[candidateIndex];
  const candidateLayer=$('#show-candidate').checked&&candidate?(candidate.points?overlayMarkup(candidate.points,'#36c4b1'):floorERPMarkup(candidate.floor,'#36c4b1')):'';
  $('#annotation-overlay').innerHTML=(annotation?(annotation.points?overlayMarkup(annotation.points,'#ee76ad'):scatterMarkup(annotation.raw_points,'#ee76ad')):'')+($('#show-reference').checked&&reference?overlayMarkup(reference.points,'#f7cf65'):'')+candidateLayer;
  for(const button of document.querySelectorAll('.candidate-choice'))button.setAttribute('aria-pressed',String(Number(button.dataset.index)===candidateIndex));
  $('#candidate-bev').innerHTML=floorBEVMarkup(candidate?.floor,data.references.map(r=>r.floor).filter(Boolean));
  $('#candidate-info').innerHTML=candidate?`<p class="candidate-status">${candidate.user_candidate?'你列的人工候选':'GT / 参考版本'}${candidate.current?' · 当前空间':''}</p><h4>${escapeHTML(candidate.label)}</h4>${candidate.scope_label?`<p>范围：${escapeHTML(candidate.scope_label)}</p>`:''}${candidate.candidate_id?`<p>候选编号：${escapeHTML(candidate.candidate_id)}</p>`:''}<p>${candidate.full_reference_available?'已有完整参考':'完整参考待补'} · ${candidate.points?'原图叠加已有上下点对':'原图仅画底界，未补顶界'}</p>${candidate.note?`<p>${escapeHTML(({confirmed_polygon_extends_beyond_complete_source_domain:'此候选部分范围超出现有完整参考覆盖，目前只展示底面。',complete_top_geometry_not_bound:'此候选尚未绑定完整顶界，目前只展示底面。'})[candidate.note]??candidate.note)}</p>`:''}`:'<p>此图片暂无登记候选范围。</p>';
  const description=[];
  if(annotation){description.push(annotationLabel(annotation));if(annotation.quality_usable)description.push('B8L2 主 '+score(annotation.quality?.B8L2)+' · D10 并列 '+score(annotation.quality?.D10)+'；IoU3D100 '+score(annotation.quality?.IoU3D100)+'；历史对照 WQ '+score(annotation.quality?.WQ)+' / A10 '+score(annotation.quality?.A10)+'（A10与D10不同）');description.push('计算状态：'+annotation.calculation_status);if(annotation.routing)description.push('参考归属：几何路由（'+annotation.routing.route_reason+'）；不确定性：'+annotation.routing.uncertainty+'。不代表人工确认真实意图。');if(annotation.points_basis)description.push(annotation.points_basis);if(!annotation.points)description.push(annotation.raw_points?.length?'仅显示原始散点，配对与环序未确认，不连接边或闭环':'此作答没有可显示的点坐标');if(!annotation.quality_usable&&Number.isFinite(annotation.diagnostic_B8L2))description.push('诊断：B8L2 '+score(annotation.diagnostic_B8L2)+' / D10 '+score(annotation.diagnostic_D10)+'，不计质量均值');if(annotation.quality_exclusion_reasons?.length)description.push('质量限制：'+annotation.quality_exclusion_reasons.join('、'));if(annotation.exclusion_reasons?.length)description.push('原因：'+annotation.exclusion_reasons.join('、'));}
  if($('#show-reference').checked)description.push(reference?.points?'参考：'+reference.label:'对应参考暂无可显示的完整上下点');
  $('#annotation-description').textContent=description.join('；');
 }
 select.addEventListener('change',draw);$('#show-reference').addEventListener('change',draw);$('#show-candidate').addEventListener('change',draw);
 for(const button of document.querySelectorAll('.candidate-choice'))button.addEventListener('click',()=>{candidateIndex=Number(button.dataset.index);draw();});
 draw();
}
async function handleHash(){
 const id=new URLSearchParams(location.hash.slice(1)).get('image');state.detailId=id;const token=++state.detailToken;
 const open=Boolean(id);$('#detail-drawer').hidden=!open;$('#drawer-backdrop').hidden=!open;document.body.classList.toggle('drawer-open',open);
 if(!open){state.lastFocus?.focus();return;}
 $('#detail-title').textContent=state.byId.get(id)?.image_code??'图片详情';$('#detail-content').innerHTML='<div class="loading">正在加载原图与已有标注…</div>';$('#close-detail').focus();
 try{if(!state.byId.has(id))throw new Error('当前库存中未找到这张图片。');const data=state.details.get(id)??await request('/api/images/'+encodeURIComponent(id));state.details.set(id,data);if(token===state.detailToken)renderDetail(data);}
 catch(error){if(token===state.detailToken)$('#detail-content').innerHTML=`<div class="error-banner" role="alert">详情加载失败：${escapeHTML(error.message)}</div>`;}
}
function closeDetail(){history.replaceState(null,'',location.pathname+location.search);handleHash();}
async function start(){
 try{
  const [data,saved]=await Promise.all([request('/api/data'),request('/api/plans')]);state.images=data.images;state.byId=new Map(data.images.map(i=>[i.image_id,i]));
  for(const image of state.images){const p=saved.plans[image.image_id]??{additional_people:null,note:'',updated_at:null};state.plans.set(image.image_id,{...p,revision:0,savedRevision:0,status:'saved',inflight:false,invalidCount:false});}
  const admitted=data.summary.new_batch_admitted_records??0,pending=(data.summary.new_batch_records??0)-admitted;
  $('#overview-stats').innerHTML=`<span><strong>${data.summary.images}</strong> 当前标注库存图</span><span><strong>${data.summary.display_images??state.images.length}</strong> 张总览卡片</span><span><strong>${state.images.reduce((n,i)=>n+i.counts.retained_records,0)}</strong> 份现有保留作答</span>${admitted?`<span><strong>${admitted}</strong> 份新增已纳库存 · 质量可用 ${data.summary.new_batch_quality_records??0} / 受限 ${data.summary.new_batch_limited_records??0}</span>`:''}${pending?`<span><strong>${pending}</strong> 份新增待纳入</span>`:''}${data.summary.user_scope_images?`<span><strong>${data.summary.user_scope_images}</strong> 图人工候选 · ${data.summary.user_scope_candidates} 个范围</span>`:''}<span>人员按同图跨条件去重 · 已纳库存的新增批次不重复计数</span>`;
  populateFilters();renderGallery();renderStats();
  for(const selector of ['#search','#building-filter','#difficulty-filter','#scene-filter','#status-filter','#space-filter','#filled-only'])$(selector).addEventListener(selector==='#search'?'input':'change',renderGallery);
  $('#close-detail').addEventListener('click',closeDetail);$('#drawer-backdrop').addEventListener('click',closeDetail);window.addEventListener('hashchange',handleHash);
  document.addEventListener('keydown',event=>{
   if(!state.detailId)return;if(event.key==='Escape')closeDetail();
   if(event.key==='Tab'){const items=[...$('#detail-drawer').querySelectorAll('button,a,input,select,textarea')].filter(e=>!e.disabled);const first=items[0],last=items.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
  });
  await handleHash();
 }catch(error){$('#global-error').hidden=false;$('#global-error').textContent='加载失败：'+error.message+'。请刷新页面重试。';$('#result-count').textContent='尚未加载';}
}
if(typeof document!=='undefined')start();
