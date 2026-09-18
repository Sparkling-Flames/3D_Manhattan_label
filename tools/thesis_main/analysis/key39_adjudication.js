/* Independent user adjudication. Never changes annotations or historical clusters. */
const KEY39_SCHEMA = 'key39_user_adjudication_v1';
function key39Empty(evidence) {
  return {schema:KEY39_SCHEMA, evidence_schema:evidence.schema, source_v2:evidence.source_v2,
    decisions:evidence.cases.flatMap(c=>c.issues.map(q=>({image_id:c.image_id,issue_id:q.issue_id,condition:q.condition,answer:'',note:''}))),
    point_decisions:evidence.cases.flatMap(c=>c.odd_records.map(r=>({image_id:c.image_id,canonical_annotation_id:r.canonical_annotation_id,
      worker_id:r.worker_id,condition:r.condition,action:'',point_index:null,added_coordinate:null,reason:'',confirmed:false}))),
    legacy_review:null};
}
function key39Validate(value, evidence) {
  const fail=s=>{throw Error(s);}, empty=key39Empty(evidence);
  if(!value || value.schema!==KEY39_SCHEMA || value.evidence_schema!==evidence.schema || value.source_v2!==evidence.source_v2)fail('裁决文件版本不匹配');
  for(const [field,id] of [['decisions','issue_id'],['point_decisions','canonical_annotation_id']]) {
    if(!Array.isArray(value[field]) || value[field].length!==empty[field].length)fail('裁决记录不完整');
    const expected=new Map(empty[field].map(r=>[r[id],r])), seen=new Set();
    for(const r of value[field]) {
      const base=expected.get(r[id]);
      if(!base || seen.has(r[id]) || r.image_id!==base.image_id || r.condition!==base.condition)fail('重复或未知的图片／条件／问题');
      seen.add(r[id]);
      const c=evidence.cases.find(c=>c.image_id===r.image_id);
      if(field==='decisions') {
        const q=c.issues.find(q=>q.issue_id===r.issue_id);
        if(typeof r.note!=='string' || !['',...q.options,'其他判断','暂缓'].includes(r.answer))fail('裁决选项无效');
        if(r.answer==='其他判断' && !r.note.trim())fail('其他判断需要填写文字');
      } else {
        const source=c.odd_records.find(x=>x.canonical_annotation_id===r.canonical_annotation_id);
        if(r.worker_id!==source.worker_id || typeof r.reason!=='string' || typeof r.confirmed!=='boolean')fail('点复核人员或字段不匹配');
        if(!['','remove_confirmed_point','add_confirmed_point','leave_unchanged','exclude_response_temporarily','defer'].includes(r.action))fail('点复核动作无效');
        if(r.confirmed) {
          if(!r.action || !r.reason.trim())fail('确认点复核前请选择动作并写明依据');
          if(source.pending_update && ['remove_confirmed_point','add_confirmed_point'].includes(r.action))fail('此记录已有待应用新导出，不能再次提交删补点');
          if(r.action==='remove_confirmed_point' && (!Number.isInteger(r.point_index) || r.point_index<0 || r.point_index>=source.raw_points.length))fail('请选择明确的原始点');
          if(r.action==='add_confirmed_point' && (!Array.isArray(r.added_coordinate) || r.added_coordinate.length!==2 || !r.added_coordinate.every(Number.isFinite) || r.added_coordinate[0]<0 || r.added_coordinate[0]>1024 || r.added_coordinate[1]<0 || r.added_coordinate[1]>=512))fail('补点坐标需在1024×512图内');
        }
      }
    }
  }
  if(value.legacy_review!==null)key39ValidateLegacy(value.legacy_review,evidence);
  return JSON.parse(JSON.stringify(value));
}
function key39ValidateLegacy(v,evidence) {
  if(!v || v.schema!=='image_difficulty_user_review_v1' || v.source_v2!==evidence.source_v2 || !Array.isArray(v.reviews) || !Array.isArray(v.image_notes))throw Error('旧审核版本不匹配');
  const images=new Set(evidence.cases.map(c=>c.image_id)), units=new Set(evidence.cases.flatMap(c=>c.reviews.user_condition_records.map(r=>r.image_id+'|'+r.condition)));
  const notes=new Set(), records=new Set();
  for(const r of v.image_notes){if(!images.has(r.image_id)||notes.has(r.image_id)||typeof r.note!=='string')throw Error('旧图片笔记无效');notes.add(r.image_id);}
  for(const r of v.reviews){const k=r.image_id+'|'+r.condition,q=r.review;if(!units.has(k)||records.has(k)||!q||!['未审核','暂缓','已审核'].includes(q.status)||!['','简单','中等','困难候选','三档不适用'].includes(q.grade)||(q.status==='已审核')!==!!q.grade||!['reason','cluster_semantics','singleton_assessment'].every(k=>typeof q[k]==='string'))throw Error('旧条件审核无效');records.add(k);}
  if(notes.size!==images.size||records.size!==units.size)throw Error('旧审核不完整');
  return JSON.parse(JSON.stringify(v));
}
function key39Export(state,evidence){
  const v=key39Validate(state,evidence);v.saved_at=new Date().toISOString();v.evidence=evidence;
  v.point_decisions=v.point_decisions.map(r=>{const src=evidence.cases.find(c=>c.image_id===r.image_id).odd_records.find(x=>x.canonical_annotation_id===r.canonical_annotation_id);return {...r,selected_original_point:r.point_index===null?null:src.raw_points[r.point_index],imputed_not_original_worker_response:r.action==='add_confirmed_point',application_status:'pending_not_applied'};});
  v.confirmed_point_repair_instructions=v.point_decisions.filter(r=>r.confirmed&&r.action!=='defer').map(r=>{
    const src=evidence.cases.find(c=>c.image_id===r.image_id).odd_records.find(x=>x.canonical_annotation_id===r.canonical_annotation_id);
    const decision={action:r.action,user_words:r.reason,application_status:'pending_not_applied'};
    if(r.action==='add_confirmed_point')Object.assign(decision,{added_coordinate_1024x512:r.added_coordinate,preserve_all_original_points:true,append_to_calculation_copy_only:true,imputed_not_original_worker_response:true,reference_evidence:r.reason});
    return {canonical_annotation_id:r.canonical_annotation_id,annotation_identity:src.annotation_identity,image_id:r.image_id,worker_id:r.worker_id,raw_count:src.raw_point_count,candidate_index_zero_based:r.point_index,candidate_point:r.selected_original_point,user_decision:decision};
  });
  return v;
}
if(typeof module!=='undefined')module.exports={key39Empty,key39Validate,key39ValidateLegacy,key39Export};
if(typeof window!=='undefined')window.addEventListener('DOMContentLoaded',()=>{
  const evidence=window.KEY39_ADJUDICATION;if(!evidence)return;
  const storageKey='key39-final-adjudication-20260918-v1';
  let state=key39Empty(evidence),blocked=false;
  const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  const option=(value,text=value)=>{const n=el('option',text);n.value=value;return n;};
  const css=el('style');css.textContent='.adj{border:2px solid #297d72;padding:22px;margin:16px 0;background:#f8fbfa;color:#172f2b;border-radius:12px}.adj h2,.adj h3{margin:10px 0}.adj p{line-height:1.65;white-space:pre-wrap}.adj-toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.adj-columns{display:grid;grid-template-columns:1fr 1fr;gap:18px}.adj article{padding:14px;border:1px solid #bccdc7;border-radius:8px;margin:14px 0;background:white}.adj textarea{width:100%;box-sizing:border-box;min-height:70px}.adj select{max-width:100%}.adj button{cursor:pointer}.adj canvas,.adj img{max-width:100%;height:auto}.adj label{display:block;margin:8px 0}.adj small{display:block;color:#42645d}.adj-status{font-weight:bold}.adj details{margin:12px 0}@media(max-width:750px){.adj-columns{grid-template-columns:1fr}}';document.head.append(css);
  const panel=el('section');panel.className='adj';panel.id='key39-adjudication';
  panel.append(el('h2','39图 · 双方意见与最终裁决'),el('p','争议优先，全部39图可回查。原文与视觉意见供参考，最终裁决由你填写；新导出和删补点决定暂不应用到旧分簇。'));
  const toolbar=el('div');toolbar.className='adj-toolbar';
  const filter=el('select');filter.setAttribute('aria-label','裁决筛选');filter.append(option('priority','争议优先 · 全39图'),option('disagreement','只看双方明确冲突'),option('algorithm','只看算法分簇疑问'),option('odd','只看奇数点'),option('all','全部39图 · 原顺序'));
  const select=el('select');select.setAttribute('aria-label','裁决图片');const prev=el('button','上一张'),next=el('button','下一张'),exp=el('button','导出最终裁决JSON'),inp=el('input');inp.type='file';inp.accept='.json';inp.setAttribute('aria-label','导入裁决或旧审核JSON');
  const importLabel=el('label','导入裁决／旧审核 ');importLabel.append(inp);toolbar.append(filter,prev,select,next,exp,importLabel);
  const status=el('p'),message=el('p');status.className='adj-status';message.setAttribute('role','status');
  const content=el('div');panel.append(toolbar,status,message,content);document.querySelector('main').prepend(panel);
  const count=()=>{status.textContent=`39图；${state.decisions.filter(r=>r.answer&&r.answer!=='暂缓').length}/${state.decisions.length}项已裁决，${state.decisions.filter(r=>r.answer==='暂缓').length}项暂缓；${state.point_decisions.filter(r=>r.confirmed).length}份点复核已确认。`;};
  function save(){count();if(blocked){message.textContent='缓存异常，未覆盖旧缓存。请导入备份恢复。';return;}try{localStorage.setItem(storageKey,JSON.stringify(state));message.textContent='已在本浏览器保存，请定期导出。原始意见及标注未改变。';}catch(e){message.textContent='自动保存失败，请立即导出：'+e.message;}}
  try{const saved=localStorage.getItem(storageKey);if(saved)state=key39Validate(JSON.parse(saved),evidence);}catch(e){blocked=true;message.textContent='缓存异常，暂停覆盖：'+e.message;}
  const choices=()=>{const current=select.value;let rows=evidence.cases.filter(c=>filter.value==='disagreement'?c.visual.category.includes('disagreement'):filter.value==='algorithm'?c.visual.category.includes('algorithm'):filter.value==='odd'?c.odd_records.length:true);if(filter.value==='priority')rows=[...rows].sort((a,b)=>Number(b.visual.category.includes('disagreement'))-Number(a.visual.category.includes('disagreement')));select.replaceChildren(...rows.map(c=>option(c.image_id,`${c.visual.category.includes('disagreement')?'争议 · ':''}${c.code} · ${c.issues.length}项`)));if(rows.some(c=>c.image_id===current))select.value=current;};
  async function open(){const i=dataset.cases.findIndex(c=>c.image_id===select.value);if(i>=0)await chooseCase(i);else content.replaceChildren(el('p','当前筛选无图片。'));}
  filter.onchange=()=>{choices();open();};select.onchange=open;prev.onclick=()=>{if(select.options.length){select.selectedIndex=(select.selectedIndex-1+select.options.length)%select.options.length;open();}};next.onclick=()=>{if(select.options.length){select.selectedIndex=(select.selectedIndex+1)%select.options.length;open();}};
  function evidenceButton(c,worker,condition,cid){const button=el('button',worker+' · 点集／3D');button.onclick=async()=>{await chooseCase(dataset.cases.findIndex(x=>x.image_id===c.image_id));const variants=dataset.cases[currentCase].variants;const i=variants.findIndex(v=>cid?v.source.canonical_annotation_id===cid:Number(v.source.worker_id)===Number(worker.slice(1))&&(!condition||condition==='image'||v.source.mode===({manual:'Manual',semi:'Semi',oos_geometry:'OOS'}[condition])));if(i<0){message.textContent='未找到同条件作答，请在原人员列表中核对。';return;}document.getElementById('variant-select').value=i;chooseVariant(i,true);document.querySelector('.workspace').scrollIntoView({behavior:'smooth'});};return button;}
  function render(){const c=evidence.cases.find(c=>c.image_id===dataset.cases[currentCase].image_id);if(!c)return;if([...select.options].some(o=>o.value===c.image_id))select.value=c.image_id;content.replaceChildren(el('h3',c.code));
    for(const change of evidence.pending_export_update.changes.filter(x=>x.image_id===c.image_id)){content.append(el('p','待应用的新导出 · '+change.worker_id+' / annotation '+change.annotation_id+'：'+(change.kind==='coordinate_correction'?'纵坐标761.187969924812% → 76.1187969924812%，28点不变。':'删除越界点，21 → 20点。')+' 当前展示仍为旧快照，未重算。'));}
    const labels={disagreement:'双方明确冲突',complement:'相容补充',algorithm:'算法分簇疑问'};content.append(el('p',c.visual.category.map(x=>labels[x]).join(' · ')));
    const original=el('details');original.open=true;original.append(el('summary','原图 · 不叠加标注'));const img=el('img');img.alt=c.code+' 原图';img.src='../../../../'+c.image_path;original.append(img);content.append(original);
    const cols=el('div');cols.className='adj-columns';for(const [title,note] of [['你的原文',c.reviews.user_image_note],['一正原文',c.reviews.peer_image_note]]){const box=el('article');box.append(el('h3',title),el('p',note));cols.append(box);}content.append(cols);
    const old=el('details');old.append(el('summary','查看双方原始条件选项（不等于最终裁决）'));for(const [name,rows] of [['你',c.reviews.user_condition_records],['一正',c.reviews.peer_condition_records]])old.append(el('p',name+'：'+(rows.length?rows.map(r=>r.condition+' · '+JSON.stringify(r.review)).join('\n'):'无条件选项；图级文字保留')));content.append(old);
    if(state.legacy_review){const imported=el('details');imported.append(el('summary','另行导入的旧审核（不自动转成最终裁决）'),el('p',state.legacy_review.image_notes.find(r=>r.image_id===c.image_id).note));content.append(imported);}
    content.append(el('h3','实际视觉核查 · 初步意见'),el('p',c.visual.observations),el('small','覆盖：原图已看；'+(c.visual.overlay_coverage.length?c.visual.overlay_coverage.map(r=>r.condition+' '+(r.workers||[]).join('/')).join('；'):'未核对点叠加')),el('small','限制：'+c.visual.limits));
    for(const q of c.issues){const card=el('article'),r=state.decisions.find(x=>x.issue_id===q.issue_id),answer=el('select'),note=el('textarea');answer.setAttribute('aria-label',q.title+'裁决');answer.append(option('','尚未裁决'),...q.options.map(x=>option(x)),option('其他判断'),option('暂缓'));answer.value=r.answer;note.value=r.note;note.placeholder='你的依据、具体位置或其他判断';note.setAttribute('aria-label',q.title+'依据');card.append(el('h3',q.title),el('p',q.question),el('small',({image:'图片整体',manual:'Manual',semi:'Semi',oos_geometry:'OOS几何'}[q.condition])+' · '+q.location));const buttons=el('div');buttons.className='adj-toolbar';for(const w of q.workers)buttons.append(evidenceButton(c,w,q.condition));card.append(buttons,answer,note);const update=()=>{const nextState=JSON.parse(JSON.stringify(state)),nr=nextState.decisions.find(x=>x.issue_id===q.issue_id);nr.answer=answer.value;nr.note=note.value;try{key39Validate(nextState,evidence);r.answer=nr.answer;r.note=nr.note;save();}catch(e){message.textContent=e.message+'；此项更改尚未保存。';}};answer.onchange=update;note.oninput=update;content.append(card);}
    if(!c.issues.length)content.append(el('p','本图暂无单独提出的裁决问题；双方原文与视觉观察可回查。'));
    if(c.odd_records.length){content.append(el('h3','孤立奇数点 · 待你复核'),el('p','以下为旧有效点仍为奇数的作答。删点须明确原始点编号，补点须确认坐标；只保存决定，不立即修复或重算。'));
      for(const source of c.odd_records)pointCard(c,source,img);
    }
    count();
  }
  function pointCard(c,source,img){const r=state.point_decisions.find(x=>x.canonical_annotation_id===source.canonical_annotation_id),card=el('article');card.append(el('h3',source.worker_id+' · '+source.condition+' · 原始'+source.raw_point_count+'点／旧有效'+source.effective_points.length+'点'),el('small','身份：'+source.canonical_annotation_id+'；'+source.processing_status),evidenceButton(c,source.worker_id,source.condition,source.canonical_annotation_id));
    if(source.pending_update)card.append(el('p','此作答的新导出已删除越界点，21→20点，尚未应用。下面只展示旧快照，请勿重复删点。'));
    const canvas=el('canvas');canvas.width=1024;canvas.height=512;canvas.setAttribute('aria-label',source.worker_id+'原始点编号图');
    const action=el('select');action.setAttribute('aria-label',source.worker_id+'点复核动作');for(const [v,t] of [['','尚未选择'],['remove_confirmed_point','确认手滑多标：删除所选点'],['add_confirmed_point','确认漏标：补入指定坐标'],['leave_unchanged','保留不动'],['exclude_response_temporarily','此份暂不纳入分析'],['defer','暂不能确定']]){const o=option(v,t);if(source.pending_update&&['remove_confirmed_point','add_confirmed_point'].includes(v))o.disabled=true;action.append(o);}action.value=r.action;
    const index=el('select');index.setAttribute('aria-label',source.worker_id+'原始点编号');index.append(option('','选择要删除的原始点'),...source.raw_points.map((p,i)=>option(String(i),`点${i+1} · ${source.point_result_ids[i]} · (${p.map(x=>x.toFixed(2)).join(', ')})`)));index.value=r.point_index===null?'':String(r.point_index);
    const x=el('input'),y=el('input');for(const [n,label] of [[x,'补点x（0—1024）'],[y,'补点y（0—512）']]){n.type='number';n.step='any';n.placeholder=label;n.setAttribute('aria-label',source.worker_id+label);}if(r.added_coordinate){x.value=r.added_coordinate[0];y.value=r.added_coordinate[1];}
    const reason=el('textarea');reason.placeholder='确认依据；补点需注明参考来源，补点属于复原值而非原始作答';reason.setAttribute('aria-label',source.worker_id+'点复核依据');reason.value=r.reason;
    const confirm=el('button','确认并保存本份点复核'),info=el('p');info.textContent=r.confirmed?'已保存你的确认，等待后续应用。':'尚未确认';
    const draw=()=>{const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,512);if(img.complete&&img.naturalWidth)ctx.drawImage(img,0,0,1024,512);ctx.font='bold 15px sans-serif';source.raw_points.forEach((p,i)=>{if(p[0]<0||p[0]>1024||p[1]<0||p[1]>=512)return;ctx.beginPath();ctx.arc(p[0],p[1],6,0,Math.PI*2);ctx.fillStyle=String(i)===index.value?'#00ffee':'#ff4242';ctx.fill();ctx.strokeStyle='#111';ctx.lineWidth=3;ctx.strokeText(String(i+1),p[0]+7,p[1]-7);ctx.fillStyle='white';ctx.fillText(String(i+1),p[0]+7,p[1]-7);});if(action.value==='add_confirmed_point'&&x.value!==''&&y.value!==''){ctx.strokeStyle='#00ffee';ctx.lineWidth=3;ctx.strokeRect(Number(x.value)-6,Number(y.value)-6,12,12);}};
    img.addEventListener('load',draw);draw();
    const draft=()=>{r.action=action.value;r.point_index=index.value===''?null:Number(index.value);r.added_coordinate=x.value!==''&&y.value!==''?[Number(x.value),Number(y.value)]:null;r.reason=reason.value;r.confirmed=false;info.textContent='草稿已保存；请确认本份点复核。';save();draw();};for(const n of [action,index,x,y,reason])n.oninput=draft;
    canvas.onclick=e=>{const rect=canvas.getBoundingClientRect(),px=(e.clientX-rect.left)/rect.width*1024,py=(e.clientY-rect.top)/rect.height*512;if(action.value==='add_confirmed_point'){x.value=px.toFixed(4);y.value=py.toFixed(4);}else if(action.value==='remove_confirmed_point'){const distances=source.raw_points.map(p=>Math.hypot(p[0]-px,p[1]-py)),min=Math.min(...distances);if(min<=20)index.value=String(distances.indexOf(min));}draft();};
    confirm.onclick=()=>{draft();const nextState=JSON.parse(JSON.stringify(state)),nr=nextState.point_decisions.find(x=>x.canonical_annotation_id===r.canonical_annotation_id);nr.confirmed=true;try{key39Validate(nextState,evidence);r.confirmed=true;save();info.textContent='已保存你的确认，等待后续应用。';}catch(e){info.textContent=e.message;}};
    card.append(canvas,el('small','删点：先选择动作，再点图上编号或下拉选择；补点：先选择动作，再点图定位或填写坐标。图外点请在下拉列表核对。'),action,index,x,y,reason,confirm,info);content.append(card);
  }
  exp.onclick=()=>{try{const v=key39Export(state,evidence);const url=URL.createObjectURL(new Blob([JSON.stringify(v,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download='39图争议_最终裁决.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message.textContent='已导出；包含原文、视觉依据及待应用修正。';}catch(e){message.textContent='导出失败：'+e.message;}};
  inp.onchange=async()=>{try{const file=inp.files[0];if(!file)return;const v=JSON.parse(await file.text());if(v.schema==='image_difficulty_user_review_v1'){const legacy=key39ValidateLegacy(v,evidence);state={...state,legacy_review:legacy};}else state=key39Validate(v,evidence);blocked=false;save();render();message.textContent='导入成功；旧审核文字不会自动成为最终裁决。';}catch(e){message.textContent='导入失败，当前裁决保留：'+e.message;}finally{inp.value='';}};
  document.addEventListener('studio-case',render);choices();open();count();
  window.KEY39_ADJUDICATION_API={exportData:()=>key39Export(state,evidence),validateImport:v=>key39Validate(v,evidence)};
});
