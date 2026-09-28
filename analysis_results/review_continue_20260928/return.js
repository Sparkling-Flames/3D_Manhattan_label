'use strict';
/* 原始二审保存在 baseline；新补充独立导出，不反写原件。 */
const RETURN_TAGS={nonorthogonal:'非正交，但可稳定标注',structure_oos:'结构／高度约束不适用',view_unobservable:'视角／遮挡导致边界难确定',doorway:'门洞交界',detail:'局部细节表达／简化',scope:'大块区域／停止范围取舍',reference_error:'参考实质错误，需核验版本',execution:'具体执行误差',model_unchanged:'初始化坐标未变',model_changed:'修改初始化后仍需核验'};
Object.assign(RETURN_TAGS,{trap_confirmed:'已核实预设 Trap',trap_not:'已核实非 Trap',trap_uncertain:'是否预设 Trap 待核实'});
Object.assign(RETURN_TAGS,{trap_synthetic:'预设Trap：人工构造',trap_natural:'预设Trap：选用模型自然错误'});
Object.assign(RETURN_TAGS,{reference_error:'GT 明显实质错误（需具体依据）',reference_omission:'GT 省略细小凹凸／细节（同一空间的表达简化）',reference_uncertain:'GT 情况尚不能确定',detail:'同一空间的细节表达不同',scope:'空间范围不同（含较小空间，不自动判低质量）'});
function validateReturn(value,data,imageIds,annotationIds,baseValidator){
  const obj=v=>v&&typeof v==='object'&&!Array.isArray(v), time=v=>typeof v==='string'&&Number.isFinite(Date.parse(v));
  const base={schema:'review_reconciliation_decisions_v1',binding:data.binding,image_decisions:value?.image_decisions,annotation_decisions:value?.annotation_decisions};
  if(value?.schema==='review_reconciliation_decisions_v1'){
    baseValidator(value,data.return_review.legacy_binding,imageIds,annotationIds);
    return {image_decisions:value.image_decisions,annotation_decisions:value.annotation_decisions,traits:{},issue_decisions:{}};
  }
  if(!obj(value)||value.schema!=='review_return_decisions_v2'||JSON.stringify(value.binding)!==JSON.stringify(data.binding))throw Error('补审版本或数据绑定不一致');
  if(Object.keys(value).some(k=>!['schema','binding','image_decisions','annotation_decisions','traits','issue_decisions','exported_at'].includes(k)))throw Error('补审存在未知字段');
  const old=baseValidator(base,data.binding,imageIds,annotationIds);
  if(!obj(value.traits)||!obj(value.issue_decisions))throw Error('缺少补充分类或问题状态');
  const issues=new Set(data.cases.flatMap(c=>(c.return_review?.issues||[]).map(i=>i.id)));
  for(const [id,t] of Object.entries(value.traits)){
    if(Array.isArray(t?.tags)&&t.tags.filter(k=>k.startsWith('trap_')).length>1)throw Error('Trap 状态不能同时选择多个');
    const known=id.startsWith('image:')?imageIds.has(id.slice(6)):id.startsWith('annotation:')&&annotationIds.has(id.slice(11));
    if(!known||!obj(t)||Object.keys(t).sort().join()!=='comment,difficulty,status,tags,updated_at'||!['pending','resolved'].includes(t.status)||!Array.isArray(t.tags)||new Set(t.tags).size!==t.tags.length||t.tags.some(k=>!Object.hasOwn(RETURN_TAGS,k))||!['unrecorded','easy','medium','hard'].includes(t.difficulty)||typeof t.comment!=='string'||!time(t.updated_at))throw Error('补充分类字段或对象无效');
  }
  for(const [id,v] of Object.entries(value.issue_decisions)){
    if(!issues.has(id)||!obj(v)||Object.keys(v).sort().join()!=='comment,status,updated_at'||!['pending','resolved'].includes(v.status)||typeof v.comment!=='string'||!time(v.updated_at)||(v.status==='resolved'&&!v.comment.trim()))throw Error('问题处理须有有效身份、状态和处理说明');
  }
  return {...old,traits:value.traits,issue_decisions:value.issue_decisions};
}
function annotationDisplayState(c,id,decisions){
  const d=decisions.annotation_decisions[id];
  const needed=d?.status==='pending'||(c.return_review?.issues||[]).some(i=>i.annotation_ids?.includes(id)&&decisions.issue_decisions[i.id]?.status!=='resolved');
  if(needed)return {state:'pending',text:d?.status==='resolved'&&d.verdict==='invalid'?'待你复核 · 原已排除':'待你复核'};
  if(d?.status==='resolved')return d.verdict==='invalid'?{state:'excluded',text:'已确认排除'}:{state:'retained',text:'已确认保留研究'};
  return {state:'context',text:'仅供对照'};
}
function trapSourceText(t){
  if(!t)return '历史Trap身份：尚未核验。';
  const stage=t.evidence?.formal_import?.includes('prescreen')?'PreScreen阶段':'历史任务设置';
  const origin={synthetic:'人工构造Trap',natural:'选用模型自然错误作为Trap'}[t.trap_origin]||'预设Trap（来源类型未明确）';
  const identity=t.trap_status==='confirmed_trap'?stage+' · '+origin:t.trap_status==='confirmed_nontrap'?stage+' · 明确对照任务（非Trap）':'历史记录未明确Trap身份';
  const edit={unchanged_coordinates:'最终点集与实际初始化一致',changed_coordinates:'最终点集相对实际初始化有改动'}[t.model_edit_status]||'初始化改动尚未核实';
  return identity+'；'+edit+'。这是来源核验结果，不是根据标注好坏猜测；点集未变不等于未检查。';
}
function returnResolved(c,d){return (c.return_review?.issues||[]).every(i=>d.issue_decisions[i.id]?.status==='resolved');}
function usageText(image,annotation,trait){
  if(annotation?.status==='resolved'&&annotation.verdict==='invalid')return '明确排除：不进入清洗后的分析；原始证据和排除统计保留。';
  if(annotation?.status==='pending')return '个人判断仍待定／待修复：保留原始研究记录，不自动排除，也不伪装成已确认可计算。';
  const tags=trait?.status==='resolved'?trait.tags:[];
  if(image?.status!=='resolved')return '图片分类尚待确认；个人保留不代表分析资格已确定。';
  if(['oos','doorway_difficult'].includes(image.category)||tags.some(t=>['nonorthogonal','structure_oos','view_unobservable'].includes(t)))return '保留场景差异研究；不进入人员主质量分析。非正交且可稳定标注的共识单列；其他场景按表示可用性研究，不强制3D。';
  if(tags.includes('reference_error'))return '作答仍保留；该参考版本的质量指标等待核验，不能把参考问题记为人员错误。';
  if(tags.includes('reference_uncertain'))return 'GT 情况尚不能确定：保留共识与参考的差异，不据此直接判定人员错误，等待具体依据。';
  if(tags.includes('reference_omission'))return 'GT 细节省略：作为同一空间的不同细节表达，仍纳入主分析并保留共识—GT差异；不修改GT，不自动判为人员错误。';
  return '保留进入主研究，包含质量误差、细节简化和范围取舍；具体指标须具备可用表示与可比较参考。未另填的比较成员沿用图片背景，不新增个人裁决。';
}
function installReturn(api){
  const {dataset,current,make,option}=api,$=id=>document.getElementById(id);
  $('recon-filter').replaceChildren(...[['followup','本页5图（含2图可选核查）'],['undecided','尚未决定（含评论待定）'],['repair','补点／删点'],['contradiction','前后判断可能矛盾'],['semantic','评论含义不清'],['model','Trap／预标注（单独收集）'],['all','本页全部5图']].map(x=>option(...x)));
  document.querySelector('.recon-heading h2').textContent='未决续审 · 3图判断＋2图历史核查';
  document.querySelector('.recon-heading p').textContent='最新复核已载入。先在大图下面橙框写本次处理说明；只有需要改分类或个人结论时再改其他表单。';
  $('recon-image-category').querySelector('[value="reference_concern"]').textContent='参考／标法差异（旧归类，不等于GT错误）';
  $('recon-scene-filter').querySelector('[value="pending"]').value='undecided';
  $('recon-scene-filter').querySelector('[value="undecided"]').textContent='当前未决（含评论）';
  $('recon-ann-verdict').querySelector('[value="usable"]').textContent='保留研究（允许误差；分析用途见说明）';
  const host=make('section');host.id='return-panel';document.querySelector('.recon-points-panel').after(host);
  const formTitle=make('h3');formTitle.id='return-form-title';host.append(formTitle);
  const overview=make('details');overview.append(make('summary','完整性核验、人员排除与图片分布报告'));
  const link=make('a','打开核验报告');link.href='README.md';link.target='_blank';overview.append(link);
  const stats=make('pre',JSON.stringify(dataset.return_review.summary,null,2));overview.append(stats);host.append(overview);
  const usage=make('p');usage.id='return-usage';host.append(usage);
  const statusLegend=make('p','橙色：待你复核　红色：已确认排除　绿色：已确认保留研究　灰色：仅供对照。仅图级问题不把全部人员标成待审。');statusLegend.className='recon-status-legend';$('recon-gallery').prepend(statusLegend);
  const trapInfo=make('p');trapInfo.id='return-trap-info';host.append(trapInfo);
  host.append(document.querySelector('.recon-final'));
  document.querySelector('.recon-final').open=true;
  document.querySelector('.recon-final > summary').textContent='补充图片／当前作答判断（已载入二审工作副本）';
  document.querySelector('.recon-final > p').textContent='填写上方当前大图的判断。切换标注者后，这里的作答对象同步切换。原始二审只读保留；合规难图仍属正常分析，结构复杂、细节多本身不是OOS或排除理由。';
  const original=make('details');original.append(make('summary','此次二审原文与整理释义（只读）'));const originalBody=make('div');original.append(originalBody);host.append(original);
  const questions=make('div');questions.id='return-issues';host.insertBefore(questions,document.querySelector('.recon-final'));
  const forms=make('details');forms.open=true;forms.id='return-classification';forms.append(make('summary','在这里填写：GT情况、标法差异、Trap补充（按需）'));
  forms.append(make('p','用途：解释共识与GT的差异，不把偏离GT直接算成人员错误。GT实质错误、细节省略、空间范围取舍分别记录；不同位置可同时存在多种情况。多标点不等于真实细节，须有墙体结构依据。请在依据中写明原始／修订GT及具体位置；不确定原因可以留待定。'));
  const formBody=make('div');formBody.className='return-trait-grid';forms.append(formBody);original.before(forms);
  let lastKey='';
  function save(next){try{api.save(next);}catch(e){$('recon-status').textContent='未保存：'+e.message;}}
  function traitForm(id,title){
    const field=make('fieldset'),t=api.decisions().traits[id];field.append(make('legend',title));
    const referenceKeys=['reference_error','reference_omission','reference_uncertain'],differenceKeys=['detail','scope'];
    const groups=[['参考GT的情况',referenceKeys],['标注之间的差异（不自动排除）',differenceKeys],['其他已知属性（可不填）',Object.keys(RETURN_TAGS).filter(k=>!referenceKeys.includes(k)&&!differenceKeys.includes(k))]];
    const checks=[];for(const [heading,keys] of groups){
      if(id.startsWith('annotation:')&&heading==='参考GT的情况'&&!referenceKeys.some(k=>t?.tags.includes(k)))continue;
      field.append(make('h4',id.startsWith('annotation:')&&heading==='参考GT的情况'?'此作答已有的GT标签（保留旧记录）':heading));for(const key of keys){const label=RETURN_TAGS[key];
      if(key.startsWith('trap_'))continue;
      if(id.startsWith('annotation:')&&['nonorthogonal','structure_oos','view_unobservable','doorway'].includes(key))continue;
      const wrap=make('label'),box=make('input');box.type='checkbox';box.value=key;box.checked=t?.tags.includes(key)||false;checks.push(box);wrap.append(box,document.createTextNode(label));field.append(wrap);
    }}
    const trap=make('select');trap.setAttribute('aria-label','是否预设 Trap');trap.append(...[['','不补充，沿用上方来源核验'],['trap_synthetic','预设Trap：人工构造'],['trap_natural','预设Trap：选用模型自然错误'],['trap_confirmed','预设Trap：来源类型尚未细分'],['trap_not','非预设Trap'],['trap_uncertain','Trap身份尚不能确定']].map(x=>option(...x)));trap.value=t?.tags.find(k=>k.startsWith('trap_'))||'';trap.hidden=!id.startsWith('annotation:');
    if(id.startsWith('annotation:')){field.append(make('h4','Trap身份补充／纠正'),make('p','历史身份见上方来源核验；仅有补充或异议时选择。模型自然出错不自动等于预设Trap。'));}field.append(trap);
    const difficulty=make('select');difficulty.append(...[['unrecorded','难度未记录'],['easy','简单'],['medium','中等'],['hard','困难（不代表OOS／不合规）']].map(x=>option(...x)));difficulty.value=t?.difficulty||'unrecorded';difficulty.hidden=id.startsWith('annotation:');field.append(difficulty);
    const comment=make('textarea');comment.rows=3;comment.value=t?.comment||'';comment.setAttribute('aria-label',title+'补充依据');field.append(comment);
    const state=make('p',t?(t.status==='resolved'?'补充已确认':'补充仍待定'):'尚无补充；不从空白猜难度或分类');field.append(state);
    const update=status=>{save({traits:{...api.decisions().traits,[id]:{status,tags:checks.filter(x=>x.checked).map(x=>x.value).concat(trap.value?[trap.value]:[]),difficulty:difficulty.value,comment:comment.value,updated_at:new Date().toISOString()}}});state.textContent=status==='resolved'?'补充已确认':'补充仍待定';};
    trap.onchange=()=>update('pending');
    for(const box of checks)box.onchange=()=>update('pending');difficulty.onchange=()=>update('pending');comment.oninput=()=>update('pending');
    for(const [label,status] of [['保存待定','pending'],['确认补充分类','resolved']]){const b=make('button',label);b.onclick=()=>update(status);field.append(b);}return field;
  }
  function render(){
    const c=current(),id=api.focusId(),ds=api.decisions();usage.textContent=usageText(ds.image_decisions[c.image_id],ds.annotation_decisions[id],ds.traits['image:'+c.image_id]);
    const focused=c.variants.find(v=>v.source.canonical_annotation_id===id);
    const who=focused?.source.worker_id||id;
    formTitle.textContent='填写二审 · '+c.code+' · '+who+' · '+(focused?.source.condition||'');
    document.querySelector('#recon-ann-verdict').closest('fieldset').querySelector('legend').textContent='当前作答 · '+who;
    for(const badge of document.querySelectorAll('[data-decision-id]')){
      const status=annotationDisplayState(c,badge.dataset.decisionId,ds);badge.textContent=status.text;badge.dataset.state=status.state;
      const row=badge.closest('.recon-member');if(row)row.dataset.reviewState=status.state;
    }
    for(const opt of $('recon-focus').options){const status=annotationDisplayState(c,opt.value,ds);opt.dataset.baseLabel??=opt.textContent;opt.textContent=status.text+' · '+opt.dataset.baseLabel;}
    // 保存文本时不重建正在编辑的控件，切换对象/导入后才刷新表单。
    const key=c.image_id+'|'+id;if(key===lastKey)return;lastKey=key;
    const trap=(c.return_review.trap_checks||[]).find(t=>t.annotation_id===id||t.canonical_annotation_id===id);
    trapInfo.textContent=trapSourceText(trap);
    const base=dataset.return_review.baseline;originalBody.replaceChildren();
    for(const [title,d] of [['图片整体原判断',base.image_decisions[c.image_id]],['当前作答原判断',base.annotation_decisions[id]]]){originalBody.append(make('h4',title),make('p',d?.comment||'无评论／未逐份填写'));const raw=make('details');raw.append(make('summary','原始选项与保存信息'),make('pre',JSON.stringify(d||{},null,2)));originalBody.append(raw);}
    const trapEvidence=make('details');trapEvidence.append(make('summary','当前作答 Trap 历史来源（只读）'),make('pre',JSON.stringify(trap||{},null,2)));originalBody.append(trapEvidence);
    for(const note of c.return_review.notes||[]){const d=make('details');d.append(make('summary',(note.worker||'图片整体')+' · '+(note.summary||note.raw_comment)),make('pre',JSON.stringify(note,null,2)));originalBody.append(d);}
    questions.replaceChildren();for(const issue of c.return_review.issues||[]){
      const box=make('details');box.className='recon-question';box.open=true;box.dataset.issueId=issue.id;
      const record=ds.issue_decisions[issue.id],title=make('summary',(record?.status==='resolved'?'已处理 · ':'待核 · ')+issue.title);box.append(title);
      const compare=make('button','叠加相关作答');compare.disabled=!issue.annotation_ids?.length;compare.onclick=()=>api.compare(issue.annotation_ids);box.append(compare);
      for(const e of issue.evidence||[]){box.append(make('p',e.title));const detail=make('details');detail.append(make('summary','展开原话与溯源依据'),make('pre',JSON.stringify(e.evidence,null,2)));box.append(detail);}
      if(issue.kind==='room_comparison'){
        const cards=make('div');cards.style.cssText='display:flex;flex-wrap:wrap;gap:12px';
        for(const row of issue.evidence.images||[]){const other=dataset.cases.find(x=>x.image_id===row.image_id);if(!other)continue;const card=make('figure');card.style.cssText='flex:1 1 360px;margin:0';const pic=make('img');pic.src=other.return_review.image_src;pic.alt=other.code+'同房原图';pic.style.width='100%';card.append(make('figcaption',other.code+' · '+(row.decision?.category||'未记录')),pic,make('p',row.decision?.comment||'无图片评论'));const button=make('button','查看此图全部标注');button.onclick=()=>api.openImage(other.image_id);card.append(button);cards.append(card);}box.append(cards);
      }
      const textarea=make('textarea');textarea.rows=3;textarea.value=record?.comment||'';textarea.setAttribute('aria-label',issue.title+'处理说明');box.append(textarea);
      const update=status=>{save({issue_decisions:{...api.decisions().issue_decisions,[issue.id]:{status,comment:textarea.value,updated_at:new Date().toISOString()}}});title.textContent=(api.decisions().issue_decisions[issue.id]?.status==='resolved'?'已处理 · ':'待核 · ')+issue.title;};textarea.oninput=()=>update('pending');
      for(const [label,status] of [['已记录但仍待定','pending'],['确认已处理此问题','resolved']]){const b=make('button',label);b.onclick=()=>update(status);box.append(b);}questions.append(box);
    }
    if(!questions.children.length)questions.append(make('p','本图没有新增必审问题；原判断与对照保留。'));
    const background=make('details');background.append(make('summary','背景核验与同房差异（不要求重复裁决）'));
    for(const item of c.return_review.background||[]){const b=make('details');b.append(make('summary',item.title),make('pre',JSON.stringify(item.evidence,null,2)));if(item.kind==='room_comparison'){const row=make('div');row.style.cssText='display:flex;gap:12px;flex-wrap:wrap';for(const x of item.evidence.images||[]){const other=dataset.cases.find(v=>v.image_id===x.image_id);if(!other)continue;const f=make('figure');f.style.cssText='flex:1 1 360px;margin:0';const img=make('img');img.src=other.return_review.image_src;img.alt=other.code;img.style.width='100%';f.append(make('figcaption',other.code+' · '+x.decision.category),img);row.append(f);}b.append(row);}background.append(b);}originalBody.append(background);
    formBody.replaceChildren(traitForm('image:'+c.image_id,'本图：GT情况与共有空间方案'),traitForm('annotation:'+id,'本份：'+who+' · 标法差异与Trap补充'));
    for(const m of c.return_review.model_checks||[]){const detail=make('details');detail.append(make('summary','初始化核验 · '+m.worker+' · '+m.status),make('pre',JSON.stringify(m,null,2)));const b=make('button','对照实际初始化与最终点');b.onclick=()=>api.compare([m.annotation_id,'reference:initial:'+m.annotation_id]);detail.append(b);originalBody.append(detail);}
    const frozen=make('details');frozen.append(make('summary','原评论簇号对应的固定成员（affinity）'),make('pre',JSON.stringify(c.return_review.cluster_references||[],null,2)));originalBody.append(frozen);
  }
  $('recon-import').addEventListener('change',()=>{lastKey='';});
  return {render};
}
if(typeof module!=='undefined')module.exports={validateReturn,returnResolved,usageText,annotationDisplayState,trapSourceText};
if(typeof window!=='undefined')window.REVIEW_RETURN={validate:validateReturn,resolved:returnResolved,install:installReturn};
