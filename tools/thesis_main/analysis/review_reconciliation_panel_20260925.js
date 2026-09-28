/* 本轮审核独立保存；旧审核原话、原始点及历史裁决均只读。 */
'use strict';

function validateReviewReconciliation(value,binding,imageIds,annotationIds){
  const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
  const fields=(v,names)=>object(v)&&Object.keys(v).length===names.length&&names.every(k=>Object.hasOwn(v,k));
  const time=v=>typeof v==='string'&&Number.isFinite(Date.parse(v));
  const statuses=['pending','resolved'],modes=['raw','effective','shared_x'];
  const referenceNames=['gt_original','gt_revised','hohonet','bilayout_enclosed','bilayout_extended'].map(x=>'reference:'+x).concat([...annotationIds].map(x=>'reference:initial:'+x));
  if(!object(value)||value.schema!=='review_reconciliation_decisions_v1')throw Error('不是本轮最终复核文件；旧轮审核只能作为只读证据');
  if(JSON.stringify(value.binding)!==JSON.stringify(binding))throw Error('本轮数据版本不一致');
  if(Object.keys(value).some(k=>!['schema','binding','image_decisions','annotation_decisions','exported_at'].includes(k)))throw Error('存在未知顶层字段');
  if(!object(value.image_decisions)||!object(value.annotation_decisions))throw Error('缺少图级或作答级裁决');
  for(const [id,d] of Object.entries(value.image_decisions)){
    if(!imageIds.has(id)||!fields(d,['status','category','comment','updated_at'])||!statuses.includes(d.status)||
      !['doorway','doorway_difficult','doorway_annotatable','oos','reference_concern','ordinary','undetermined'].includes(d.category)||typeof d.comment!=='string'||!time(d.updated_at))throw Error('图片 ID 或裁决字段无效');
    if(d.status==='resolved'&&d.category==='undetermined')throw Error('未定图片不能标为已解决');
  }
  for(const [id,d] of Object.entries(value.annotation_decisions)){
    if(!annotationIds.has(id)||!fields(d,['status','verdict','comment','repair_confirmation','updated_at','view_context'])||
      !statuses.includes(d.status)||!['usable','invalid','repair_needed','undetermined'].includes(d.verdict)||
      typeof d.comment!=='string'||!time(d.updated_at)||!['unreviewed','confirm_existing','needs_followup','reject_proposal'].includes(d.repair_confirmation))throw Error('作答 ID 或裁决字段无效');
    if(d.status==='resolved'&&!['usable','invalid'].includes(d.verdict))throw Error('待定或待修复作答不能标为已解决');
    const c=d.view_context;
    if(!fields(c,['point_mode','reference_ids','cluster_method'])||!modes.includes(c.point_mode)||!['affinity','complete'].includes(c.cluster_method)||
      !Array.isArray(c.reference_ids)||new Set(c.reference_ids).size!==c.reference_ids.length||
      c.reference_ids.some(x=>typeof x!=='string'||(!annotationIds.has(x)&&!referenceNames.includes(x))))throw Error('查看上下文或参考 ID 无效');
  }
  return {image_decisions:value.image_decisions,annotation_decisions:value.annotation_decisions};
}
function sceneRuleAdvice(image,rawCount,effectiveCount,pairing,repairConfirmed=false){
  if(!image||image.status!=='resolved')return {action:'confirm_scene',text:'先确认图片是否OOS、难标门洞或可标门洞。历史线索与原选项不直接等于已确认分类。'};
  const category=image.category,held=['oos','doorway_difficult'].includes(category);
  const quality=held?'不进入人员主质量分析。':'';
  if(category==='doorway')return {action:'confirm_difficulty',text:'旧门洞分类尚未区分难标/可标，请补充；不套用OOS少于8点规则。'};
  if(category==='oos'&&(rawCount<8)!==(effectiveCount<8)&&!repairConfirmed)return {action:'check_repair',text:'原始与有效点数跨过8点门槛；先确认已有补点/删点，再采用有效点判定。'+quality};
  if(category==='oos'&&effectiveCount<8)return {action:'default_exclude',text:'已确认OOS且当前有效点少于8：默认建议排除，等待你确认保存。'+quality};
  if(held&&effectiveCount%2)return {action:'check_odd',text:'有效点为奇数：核查漏点、误点及补点记录，不直接推定整份无效。'+quality};
  if(held&&!['existing_accepted_pairing','ok'].includes(pairing.status))return {action:'check_pairing',text:(pairing.reason==='ambiguous_horizontal_assignment'?'存在等价配对候选，不等于完全无法配对。':'当前算法未获得配对，需人工确认是否真的完全无法配对。')+quality};
  if(held)return {action:'no_scene_exclusion',text:'有效点为偶数且有现有配对，不仅因难标/OOS或范围不同排除；其他明确执行错误仍逐份核查。'+quality};
  return {action:'ordinary_review',text:category==='doorway_annotatable'?'可标门洞单列；质量良好时不自动排除，人员评价资格仍需核对GT和范围。':'按普通作答规则判断，不套用OOS阈值。'};
}
if(typeof module!=='undefined')module.exports={validateReviewReconciliation,sceneRuleAdvice};

if(typeof document!=='undefined')(()=>{
  if(dataset.schema!=='review_reconciliation_v1')throw Error('二次复核数据版本不符');
  const imageIds=new Set(dataset.cases.map(c=>c.image_id));
  if(imageIds.size!==dataset.cases.length)throw Error('图片重复，停止载入');
  const annotationIds=new Set(dataset.cases.flatMap(c=>c.review.annotation_ids));
  const returnReview=window.REVIEW_RETURN;
  const decisionSchema=returnReview?'review_return_decisions_v2':'review_reconciliation_decisions_v1';
  const storageKey=decisionSchema+':'+dataset.binding.id;
  const panel=document.createElement('section');panel.id='reconciliation-panel';
  panel.innerHTML=`
    <header class="recon-heading"><div><h2>分簇与标注对照</h2><p>已完成的审核保留。这里只提示具体待核问题；随时可切到全部图片查阅，无需逐份重审。</p></div><span id="recon-count"></span></header>
    <details class="recon-semantics"><summary>两份审核的含义与本轮SOP</summary><p><b>你的审核：</b>以评论和共享图片背景为主。不同范围可能选保留/待定；GT问题或不同标法也可能选范围争议。门洞/OOS多选范围争议或待定；配对包括部分顺序问题。</p><p><b>一正的审核：</b>“GT与范围争议”表示标注本身没问题，只是范围不同，不表示GT错误。一正未必了解门洞/OOS；其独审图与全部排除作答均需复核。</p><a href="../../docs/thesis_main/两人审核归并与二次复核SOP_20260925.md" target="_blank">查看完整SOP与点数规则</a></details>
    <div class="recon-nav">
      <label>复核任务<select id="recon-filter"><option value="followup">本轮全部复核</option><option value="recheck_yizheng">一正复核（独审／补背景／排除）</option><option value="excluded">全部曾选排除的作答</option><option value="repair">补点与修复核对</option><option value="consistency">评论／相似标法／标准一致性</option><option value="all">完整资料库（含无需重审）</option></select></label>
      <label>图片线索<select id="recon-scene-filter"><option value="all">不限</option><option value="doorway">门洞相关</option><option value="oos">OOS相关</option><option value="representation">配对／顺序</option><option value="pending">含原选待定</option></select></label>
      <label>同房支持组<select id="recon-room"><option value="all">全部组</option><option value="unconfirmed">尚无支持归组</option></select></label>
      <label>查找<input id="recon-search" placeholder="图片编号或关键词"></label>
      <label class="recon-check"><input id="recon-unresolved" type="checkbox">隐藏已确认的待核对象</label>
      <div class="recon-image-nav"><button id="recon-previous" aria-label="上一张筛选图片">←</button><label>图片<select id="recon-image"></select></label><button id="recon-next" aria-label="下一张筛选图片">→</button></div>
    </div>
    <p id="recon-empty" hidden>当前筛选没有图片。请更换筛选条件；下方上次查看内容已隐藏。</p>
    <div id="recon-case">
      <h3 id="recon-title"></h3><p id="recon-summary"></p><p id="recon-room-note" class="recon-muted"></p>
      <details id="recon-shared-context"><summary>你的同图共享说明与“同图”引用</summary><div id="recon-shared-content"></div></details><div id="recon-questions"></div>
      <section class="recon-points-panel"><div class="recon-point-controls">
        <label>正在复核<select id="recon-focus"></select></label>
        <label>点位版本<select id="recon-points"><option value="effective">当前有效点</option><option value="raw">原始导出点</option><option value="shared_x">共享 x 点</option></select></label>
        <label class="recon-check"><input id="recon-numbers" type="checkbox" checked>点号</label>
        <button id="recon-3d">查看当前作答3D</button>
      </div><p id="recon-point-note"></p><p id="recon-rule-advice"></p><div id="recon-repair-summary"></div><p id="recon-point-warning" role="status" hidden></p><details id="recon-point-changes" hidden><summary>原始与有效点变更对照（按原点号）</summary><div></div></details><p id="recon-legend"></p><canvas id="recon-canvas" width="1024" height="512" aria-label="当前作答与所选参考的独立点图"></canvas>
      <canvas id="recon-zoom" width="800" height="400" aria-label="点击位置的局部放大" hidden></canvas><p id="recon-geometry-note" role="status"></p>
      <details class="recon-reference-box"><summary>选择对照：原始／修订 GT、模型及同图其他人员（可多选）</summary><div id="recon-references"></div></details></section>
      <section><h3>本份作答的两位审核原话</h3><div id="recon-events" class="recon-event-columns"></div>
        <details><summary>展开本图全部原话、同图引用及其他人员意见</summary><div id="recon-all-events" class="recon-event-columns"></div></details>
        <details><summary>原始导出、有效点、修复与配对来源</summary><pre id="recon-audit"></pre></details>
        <details><summary>既往图片／房间裁决原文</summary><div id="recon-history"></div></details>
      </section>
      <details class="recon-final"><summary>记录本次补充判断（按需填写，不要求重做旧审核）</summary><p>可在图级说明中一次记录本图问题的处理，无需逐份重填已明确的作答；需要改变某份有效性时，再填该份结论。确认图级复核不自动改写任何成员的有效性。修改填写会恢复为待定。</p>
        <div class="recon-decision-grid"><fieldset><legend>图片整体情况</legend>
          <label>归类<select id="recon-image-category"><option value="">未填写</option><option value="ordinary">普通图片</option><option value="doorway_difficult">门洞交界 · 难标</option><option value="doorway_annotatable">门洞交界 · 可以标注</option><option value="doorway">旧门洞记录 · 难度未分</option><option value="oos">确认OOS</option><option value="reference_concern">参考／范围存在争议</option><option value="undetermined">尚不能确定</option></select></label>
          <label>图片整体说明／本次问题处理<textarea id="recon-image-comment" rows="4"></textarea></label><p id="recon-image-state"></p><button id="recon-image-pending">保存待定</button><button id="recon-image-resolve">确认本图复核结论</button>
        </fieldset><fieldset><legend id="recon-ann-legend">当前作答</legend>
          <label>结论<select id="recon-ann-verdict"><option value="">未填写</option><option value="usable">可保留使用</option><option value="invalid">明确无效</option><option value="repair_needed">需修复后再审</option><option value="undetermined">尚不能确定</option></select></label>
          <label>历史修复核验<select id="recon-repair"><option value="unreviewed">尚未核验／不涉及</option><option value="confirm_existing">确认已有修复</option><option value="needs_followup">仍需追踪</option><option value="reject_proposal">不接受修复建议</option></select></label>
          <label>本份作答的依据<textarea id="recon-ann-comment" rows="4"></textarea></label><p id="recon-ann-state"></p><button id="recon-ann-pending">保存待定</button><button id="recon-ann-resolve">确认本份结论</button>
        </fieldset></div>
      </details>
      <section id="recon-gallery"><div class="recon-cluster-heading"><h3>各簇图像 · 成员点位叠加</h3><label>探索性共享 x 分区<select id="recon-method"><option value="affinity">直径约束全局亲近度</option><option value="complete">完整链接对照</option></select></label></div><p class="recon-muted">每张图卡叠加本簇所有成员，一人一色。点击图卡在大图比较，也可展开单人图。簇按采集条件分开；少数标法和未覆盖本身不代表错误。</p><div id="recon-clusters"></div></section>
    </div>
    <div class="recon-file-controls"><button id="recon-export">导出本轮最终复核</button><label>导入本轮最终复核<input id="recon-import" type="file" accept=".json"></label></div>
    <p id="recon-status" role="status" aria-live="polite"></p>`;
  document.querySelector('main').prepend(panel);
  document.body.classList.add('reconciliation-review');
  $('recon-questions').after($('recon-gallery'));
  $('recon-gallery').querySelector('.recon-cluster-heading').append($('recon-points').closest('label'));
  // Studio 会随材质/选点刷新按钮状态；原生 disabled fieldset 保证本轮始终不可操作。
  const orderEditor=document.querySelector('.order-editor'),orderGuard=document.createElement('fieldset');
  orderGuard.disabled=true;orderGuard.hidden=true;orderEditor.before(orderGuard);orderGuard.append(orderEditor);
  const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const option=(v,t)=>{const o=make('option',t);o.value=v;return o;};
  const caseById=new Map(dataset.cases.map((c,i)=>[c.image_id,i]));
  const verdictLabels={retain:'保留',invalid:'明确无效',gt_scope:'GT 与范围争议',representation:'配对／表示问题',pending:'待定'};
  const flags={doorway:'门洞相关线索',oos:'OOS线索',reference:'参考／范围',pending:'原选待定',followup:'定向复核',recheck_yizheng:'一正复核',excluded:'排除复核',consistency:'标准一致性',scene_rule:'场景点数规则',reviewer_context:'一正需补背景',comment_questions:'评论线索',representation:'配对／顺序',repair:'修复',yizheng:'一正',same_pattern:'相似标法',historical:'历史'};
  const modeNames={raw:'原始导出点',effective:'当前有效点',shared_x:'共享 x 点'};
  Object.assign(flags,{undecided:'尚未决定',contradiction:'判断可能矛盾',semantic:'评论含义不清',model:'Trap／预标注资料',statistics:'含已排除记录'});
  let decisions={image_decisions:{},annotation_decisions:{}},focusId=null,references=new Set(),photo=new Image(),imageReady=false,shownImage=null,zoomAt=null,navToken=0,returnPanel=null;
  const envelope=()=>({schema:decisionSchema,binding:dataset.binding,...decisions});
  const validate=value=>returnReview?returnReview.validate(value,dataset,imageIds,annotationIds,validateReviewReconciliation):validateReviewReconciliation(value,dataset.binding,imageIds,annotationIds);
  if(returnReview)decisions=validate(dataset.return_review.baseline);
  try{const saved=localStorage.getItem(storageKey);if(saved)decisions=validate(JSON.parse(saved));}catch(e){$('recon-status').textContent='浏览器记录未载入：'+e.message+'。请导入本轮备份。';}
  const current=()=>dataset.cases[currentCase];
  const annotations=()=>current().variants.filter(v=>v.source.role==='annotation');
  const variantId=v=>v.source.canonical_annotation_id||'reference:'+v.source.reference_name;
  const focus=()=>annotations().find(v=>v.source.canonical_annotation_id===focusId);
  const mode=()=>$('recon-points').value;
  const method=()=>$('recon-method').value;
  const pointList=v=>v.source[mode()==='raw'?'raw_points':mode()==='effective'?'effective_points':'shared_x_points']||[];
  const pointLabels=v=>v.source[mode()==='raw'?'raw_point_labels':mode()==='effective'?'effective_point_labels':'shared_x_point_labels']||[];
  const worker=v=>v.source.worker_id||v.name;
  const condition=v=>({manual:'Manual',oos:'OOS',semi:'Semi'}[v.source.condition]||v.source.condition||'未知条件');
  const imageResolved=c=>returnReview?returnReview.resolved(c,decisions):decisions.image_decisions[c.image_id]?.status==='resolved'&&!c.review.annotation_ids.some(id=>decisions.annotation_decisions[id]?.status==='pending');
  const confirmedSceneHold=()=>{const d=decisions.image_decisions[current().image_id];return d?.status==='resolved'&&['oos','doorway_difficult'].includes(d.category);};
  function filtered(){
    const q=$('recon-search').value.trim().toLowerCase(),f=$('recon-filter').value,r=$('recon-room').value,s=$('recon-scene-filter').value;
    return dataset.cases.filter(c=>(f==='all'||c.review.flags.includes(f))&&(s==='all'||c.review.flags.includes(s))&&(r==='all'||(r==='unconfirmed'?!c.review.room_id:c.review.room_id===r))&&
      (!$('recon-unresolved').checked||!c.review.flags.includes('followup')||!imageResolved(c))&&(!q||[c.code,c.image_id,c.review.summary,c.review.room_label,...c.review.annotation_ids].join(' ').toLowerCase().includes(q)));
  }
  for(const room of dataset.reconciliation.rooms.filter(r=>r.image_ids.some(id=>imageIds.has(id))))$('recon-room').append(option(room.id,room.label));
  function queue(){
    const rows=filtered();$('recon-image').replaceChildren(...rows.map(c=>option(c.image_id,`${c.code} · ${c.review.flags.includes('followup')?(imageResolved(c)?'本次问题已确认':c.review.followup_reasons.length+'项问题 · '+c.review.followup_ids.length+'份相关对照'):'资料查阅 · 无新增必审要求'}`)));
    if(rows.some(c=>c.image_id===current().image_id))$('recon-image').value=current().image_id;else $('recon-image').selectedIndex=-1;
    $('recon-count').textContent=`当前 ${rows.length} 张 · 资料库 ${dataset.cases.length} 张（非重审总量）`;
    $('recon-previous').disabled=$('recon-next').disabled=rows.length<2;
    const empty=rows.length===0;$('recon-empty').hidden=!empty;$('recon-case').hidden=empty;
    document.querySelector('.workspace').hidden=empty||confirmedSceneHold();document.querySelector('.study-heading').hidden=empty||confirmedSceneHold();
    return rows;
  }
  async function openCase(index){const token=++navToken;$('recon-case').inert=true;try{await chooseCase(index);}finally{if(token===navToken)$('recon-case').inert=false;}}
  async function refilter(){const rows=queue();if(rows.length&&!rows.some(c=>c.image_id===current().image_id))await openCase(caseById.get(rows[0].image_id));}
  for(const id of ['recon-filter','recon-scene-filter','recon-room','recon-unresolved'])$(id).onchange=refilter;
  $('recon-search').oninput=refilter;
  $('recon-image').onchange=()=>openCase(caseById.get($('recon-image').value));
  for(const [id,step] of [['recon-previous',-1],['recon-next',1]])$(id).onclick=()=>{const rows=filtered();if(rows.length){const i=rows.findIndex(c=>c.image_id===current().image_id);openCase(caseById.get(rows[(i+step+rows.length)%rows.length].image_id));}};
  function disableOrder(){document.querySelectorAll('.order-editor input,.order-editor button').forEach(e=>e.disabled=true);}
  function events(){const found=new Map();for(const v of annotations())for(const e of v.source.events||[])found.set(e.event_id,{...e,source_worker:worker(v),source_id:variantId(v)});return [...found.values()];}
  function eventCard(e){
    const a=make('article',undefined,'recon-event');a.dataset.eventId=e.event_id;
    const exposure={manual:'Manual',oos:'OOS',semi:'Semi'}[e.condition]||e.condition||'条件未记录';
    const optionText=e.verdict==='gt_scope'?(e.reviewer==='user'?'GT与范围争议（按你的评论解释）':'标注本身可接受，空间范围不同'):(verdictLabels[e.verdict]||e.verdict);
    a.append(make('strong',`${e.reviewer_label||e.reviewer} · ${e.source_worker||''} · ${exposure} · ${optionText}`),make('small',e.updated_at||'未记录时间'),make('p',e.comment||'（未写评论）','recon-original'));
    if(e.interpretation){a.append(make('p','整理释义（待确认）：'+(e.interpretation.summary||'未作释义'),'recon-interpretation'));
      const other=make('details'),summary=make('summary','对象、主题与“同图”引用线索');other.append(summary,make('pre',JSON.stringify(e.interpretation,null,2)));a.append(other);}
    a.append(make('small',e.event_id));return a;
  }
  function eventColumns(host,items){host.replaceChildren();for(const reviewer of ['user','yizheng']){const column=make('div');column.append(make('h4',reviewer==='user'?'你的原审核':'一正的原审核'));const rows=items.filter(e=>e.reviewer===reviewer);column.append(...(rows.length?rows.map(eventCard):[make('p','该对象没有这位审核者的记录。','recon-muted')]));host.append(column);}}
  function renderEvidence(){
    const all=events();eventColumns($('recon-events'),all.filter(e=>e.source_id===focusId));eventColumns($('recon-all-events'),all);
    $('recon-audit').textContent=JSON.stringify(focus()?.source.audit||{},null,2);
    $('recon-history').replaceChildren(...(current().review.history||[]).map(h=>make('pre',typeof h==='string'?h:JSON.stringify(h,null,2))));
    if(!$('recon-history').children.length)$('recon-history').append(make('p','本轮未找到匹配的历史裁决。'));
    const context=$('recon-shared-content'),byId=new Map(all.map(e=>[e.event_id,e]));context.replaceChildren();
    for(const id of current().review.shared_image_context_event_ids){if(byId.has(id))context.append(eventCard(byId.get(id)));}
    for(const link of current().review.same_image_links){const source=byId.get(link.event_id);context.append(make('p',`${source?.source_worker||link.event_id}：“${source?.comment||'同图'}” → ${link.context_event_ids.length?'可参考上面 '+link.context_event_ids.length+' 条图片/参考说明；不继承人员裁决':'两份JSON中未找到明确图片说明，保留缺失；历史资料仅辅助'}`));}
    if(!context.children.length)context.append(make('p','此图没有你的共享图片说明；不能凭一正的范围选项推定OOS或门洞。'));
    const repairs=focus()?.source.audit?.repairs||[];$('recon-repair-summary').replaceChildren(...repairs.map(r=>make('p',(r.status==='applied'?'已执行修复：':'仅提出，未应用：')+r.description)));
  }
  function questions(){
    const byId=new Map(events().map(e=>[e.event_id,e]));
    $('recon-questions').replaceChildren(...(current().review.questions||[]).map(q=>{const d=make('details',undefined,'recon-question');d.append(make('summary',q.title));
      if(q.workers?.length)d.append(make('p','相关人员：'+q.workers.join('、')));
      const reason=current().review.followup_reasons.find(r=>r.title===q.title);
      if(reason?.annotation_ids.length){const b=make('button','在大图叠加这些相关作答');b.onclick=()=>{references=new Set(reason.annotation_ids);setFocus(reason.annotation_ids[0]);$('recon-focus').scrollIntoView({behavior:'smooth',block:'center'});};d.append(b);}
      for(const id of q.evidence_event_ids||[]){const e=byId.get(id);d.append(e?eventCard(e):make('p','关联证据：'+id+'（不在当前图片事件中）'));}return d;}));
    const labels={pending:'明确待定',comment:'具体评论待统一',reviewer_context:'一正需补充图片背景',yizheng_only:'一正独审、你尚未审',exclusion_review:'曾选排除，必须再核',user_scene_retention:'你的门洞/OOS说明与保留记录',similar_exclusion:'相似标法排除差异',repair:'修复疑问',scene_rule:'场景属性与点数/配对核对'};
    const kinds=[...new Set(current().review.followup_reasons.map(r=>r.kind))];
    Object.assign(labels,{undecided:'尚未决定（含评论）',contradiction:'判断可能矛盾',semantic:'评论含义不清'});
    $('recon-questions').prepend(make('p',kinds.length?'本图复核来源：'+kinds.map(k=>labels[k]||k).join('、')+'。只核对有关问题，其他成员作为对照。':'本图供资料查阅，未生成新增复核要求。','recon-muted'));
  }
  function renderForms(){
    const image=decisions.image_decisions[current().image_id],ann=decisions.annotation_decisions[focusId];
    $('recon-image-category').value=image?.category||'';$('recon-image-comment').value=image?.comment||'';
    $('recon-ann-verdict').value=ann?.verdict||'';$('recon-ann-comment').value=ann?.comment||'';$('recon-repair').value=ann?.repair_confirmation||'unreviewed';
    $('recon-ann-legend').textContent='当前作答：'+(focus()?`${worker(focus())} · ${condition(focus())}`:'未选定');updateStates();
  }
  function updateRule(){
    const v=focus();if(!v)return;const s=v.source,ann=decisions.annotation_decisions[focusId];
    const advice=sceneRuleAdvice(decisions.image_decisions[current().image_id],s.raw_points.length,s.effective_points.length,s.audit.pairing,ann?.repair_confirmation==='confirm_existing');
    $('recon-rule-advice').textContent='本轮规则提示：'+advice.text;
    if(!ann)$('recon-ann-verdict').value=advice.action==='default_exclude'?'invalid':'';
    geometryNote();
  }
  function updateStates(){
    for(const [id,d] of [['recon-image-state',decisions.image_decisions[current().image_id]],['recon-ann-state',decisions.annotation_decisions[focusId]]])$(id).textContent=d?(d.status==='resolved'?'本轮已确认':'本轮仍待定')+' · '+d.updated_at:'本轮尚未填写，旧判断没有预填。';
    document.querySelectorAll('[data-decision-id]').forEach(e=>{const d=decisions.annotation_decisions[e.dataset.decisionId],needed=current().review.followup_ids.includes(e.dataset.decisionId);e.textContent=!d?(needed?'本次待核':'旧审核保留／供比较'):d.status==='resolved'?'已确认 · '+(d.verdict==='usable'?'保留':'无效'):'本次待定';e.dataset.state=d?.status||'blank';});
    updateRule();
    returnPanel?.render();
  }
  function persist(){
    validate(envelope());try{localStorage.setItem(storageKey,JSON.stringify(envelope()));$('recon-status').textContent='已保存到当前浏览器；请及时导出备份。';}catch(e){$('recon-status').textContent='浏览器保存失败，请立即导出当前答案：'+e.message;}updateStates();refilter();
  }
  function saveImage(status){try{
    const d={status,category:$('recon-image-category').value||'undetermined',comment:$('recon-image-comment').value,updated_at:new Date().toISOString()};
    const next={...decisions.image_decisions,[current().image_id]:d};validate({...envelope(),image_decisions:next});decisions.image_decisions=next;persist();
  }catch(e){$('recon-status').textContent='不能确认：'+e.message;}}
  function saveAnnotation(status){try{
    if(!focusId)throw Error('未选择作答');
    const d={status,verdict:$('recon-ann-verdict').value||'undetermined',comment:$('recon-ann-comment').value,repair_confirmation:$('recon-repair').value,updated_at:new Date().toISOString(),
      view_context:{point_mode:mode(),reference_ids:[...references].filter(id=>id!==focusId),cluster_method:method()}};
    const next={...decisions.annotation_decisions,[focusId]:d};validate({...envelope(),annotation_decisions:next});decisions.annotation_decisions=next;persist();
  }catch(e){$('recon-status').textContent='不能确认：'+e.message;}}
  for(const id of ['recon-image-category','recon-image-comment'])$(id).addEventListener(id.endsWith('comment')?'input':'change',()=>saveImage('pending'));
  for(const id of ['recon-ann-verdict','recon-ann-comment','recon-repair'])$(id).addEventListener(id.endsWith('comment')?'input':'change',()=>saveAnnotation('pending'));
  $('recon-image-pending').onclick=()=>saveImage('pending');$('recon-image-resolve').onclick=()=>saveImage('resolved');
  $('recon-ann-pending').onclick=()=>saveAnnotation('pending');$('recon-ann-resolve').onclick=()=>saveAnnotation('resolved');
  function viewerLabels(v){if(!v.geometry)return;$('raw-title').textContent='既有点对条件重建';$('raw-caption').textContent='既有点对与排列 · 保留重建假设';if(v.geometry.fit.status==='not_requested'){const row=$('metrics').firstElementChild;if(row){row.firstElementChild.textContent='约束拟合';row.lastElementChild.textContent='本轮未运行';}}}
  function geometryNote(){const v=focus();if(!v)return;const held=confirmedSceneHold();$('recon-geometry-note').textContent=held?'本轮已确认OOS或难标门洞，关闭3D展示，保留原图与点位。':v.geometry?'3D仅显示当前既有点对与排列的条件重建；点图版本切换不重算3D。本轮不调整顺序。':`本份不启动3D：${v.error||'当前没有可用几何'}。原始点和文字证据仍可审查。`;$('recon-3d').disabled=held||!v.geometry;viewerLabels(v);}
  function setFocus(id){
    const v=annotations().find(v=>variantId(v)===id);if(!v)return;focusId=id;$('recon-focus').value=id;
    $('variant-select').value=current().variants.indexOf(v);chooseVariant(current().variants.indexOf(v),true);disableOrder();
    renderReferences();syncChecks();renderEvidence();renderForms();geometryNote();pointChanges();draw();
    document.querySelectorAll('[data-focus-id]').forEach(e=>e.classList.toggle('active',e.dataset.focusId===focusId));
  }
  $('recon-focus').onchange=()=>setFocus($('recon-focus').value);
  $('recon-3d').onclick=()=>{const v=focus();if(v?.geometry){chooseVariant(current().variants.indexOf(v),true);viewerLabels(v);disableOrder();document.querySelector('.workspace').scrollIntoView({behavior:'smooth'});}};
  const originalVariantChange=$('variant-select').onchange;
  $('variant-select').onchange=e=>{const v=current().variants[Number(e.target.value)];if(v.source.role==='annotation')setFocus(variantId(v));else{originalVariantChange(e);viewerLabels(v);disableOrder();}};
  function renderReferences(){
    const host=$('recon-references');host.replaceChildren();
    for(const v of current().variants){const id=variantId(v),label=make('label'),check=document.createElement('input');check.type='checkbox';check.checked=references.has(id)&&id!==focusId;check.disabled=id===focusId;
      check.onchange=()=>{check.checked?references.add(id):references.delete(id);draw();syncChecks();};check.dataset.referenceId=id;
      label.append(check,document.createTextNode(v.source.role==='annotation'?`${worker(v)} · ${condition(v)}${id===focusId?'（当前）':''}`:v.name));host.append(label);}
  }
  function syncChecks(){document.querySelectorAll('[data-reference-id]').forEach(e=>{e.checked=references.has(e.dataset.referenceId)&&e.dataset.referenceId!==focusId;e.disabled=e.dataset.referenceId===focusId;});}
  const memberColor=v=>`hsl(${(annotations().indexOf(v)*137.508+205)%360} 75% 42%)`;
  function galleryCanvas(members){const canvas=make('canvas');canvas.width=1024;canvas.height=512;canvas.className='recon-cluster-canvas';canvas.dataset.members=JSON.stringify(members.map(variantId));return canvas;}
  function drawGallery(){
    document.querySelectorAll('.recon-cluster-canvas').forEach(canvas=>{const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,512);if(imageReady)ctx.drawImage(photo,0,0,1024,512);
      for(const id of JSON.parse(canvas.dataset.members)){const v=annotations().find(v=>variantId(v)===id);if(!v)continue;ctx.fillStyle=memberColor(v);ctx.strokeStyle='white';ctx.lineWidth=1.5;
        for(const [x,y] of pointList(v)){ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();ctx.stroke();}}
    });
  }
  function clusters(){
    const host=$('recon-clusters'),groups=new Map();
    for(const v of annotations()){const label=v.source.clusters?.[method()],covered=label!==null&&label!==undefined;
      const key=condition(v)+'|'+(covered?'cluster:'+label:'uncovered:'+variantId(v));if(!groups.has(key))groups.set(key,[]);groups.get(key).push(v);}
    host.replaceChildren(...[...groups.values()].map(members=>{const first=members[0],label=first.source.clusters?.[method()],covered=label!==null&&label!==undefined,card=make('article',undefined,'recon-cluster');
      const heading=make('h4',`${condition(first)} · ${covered?'簇 '+label+' · '+members.length+'份':'未覆盖 · '+worker(first)}`);card.append(heading);
      const preview=galleryCanvas(members);preview.tabIndex=0;preview.setAttribute('role','button');preview.setAttribute('aria-label','放大并叠加'+heading.textContent);
      const compare=()=>{references=new Set(members.map(variantId));setFocus(variantId(first));$('recon-focus').scrollIntoView({behavior:'smooth',block:'center'});};preview.onclick=compare;preview.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();compare();}};card.append(preview);
      if(covered){for(const [title,on] of [['叠加全簇',true],['取消本簇',false]]){const b=make('button',title);b.onclick=()=>{members.forEach(v=>on?references.add(variantId(v)):references.delete(variantId(v)));syncChecks();draw();};heading.append(b);}}
      for(const v of members){const id=variantId(v),row=make('div',undefined,'recon-member'),label=make('label'),check=document.createElement('input');check.type='checkbox';check.dataset.referenceId=id;check.checked=references.has(id)&&id!==focusId;
        check.onchange=()=>{check.checked?references.add(id):references.delete(id);syncChecks();draw();};label.append(check,document.createTextNode(`${worker(v)} · 原 ${v.source.raw_points?.length??0} / 有效 ${v.source.effective_points?.length??0} 点`));
        const state=make('span',undefined,'recon-member-state');state.dataset.decisionId=id;
        label.style.borderLeft='5px solid '+memberColor(v);label.style.paddingLeft='6px';
        const b=make('button','查看本份');b.dataset.focusId=id;b.onclick=()=>{setFocus(id);$('recon-focus').scrollIntoView({behavior:'smooth',block:'center'});};row.append(label,state,b);card.append(row);}
      const individuals=make('details'),thumbs=make('div',undefined,'recon-individuals');individuals.append(make('summary','展开本簇每人的单独标注图'));
      individuals.ontoggle=()=>{if(!individuals.open||thumbs.children.length)return;for(const v of members){const figure=make('figure'),canvas=galleryCanvas([v]);canvas.onclick=()=>{references=new Set();setFocus(variantId(v));$('recon-focus').scrollIntoView({behavior:'smooth',block:'center'});};figure.append(make('figcaption',worker(v)+' · '+condition(v)),canvas);thumbs.append(figure);}drawGallery();};individuals.append(thumbs);card.append(individuals);
      if(!covered)card.append(make('small',first.source.cluster_coverage||'未覆盖，不将其解释为一个簇'));return card;}));
    updateStates();syncChecks();drawGallery();
  }
  const outside=([x,y])=>x<0||x>1024||y<0||y>512;
  const pointText=p=>p?`(${p.map(n=>Number(n).toFixed(3)).join(', ')})${outside(p)?' · 图外':''}`:'该版本没有此点';
  function pointChanges(){
    const s=focus()?.source;if(!s)return;const raw=s.raw_points||[],effective=s.effective_points||[],rl=s.raw_point_labels||[],el=s.effective_point_labels||[];
    const off=raw.flatMap((p,i)=>outside(p)?[`${rl[i]||'原始第'+(i+1)+'点'} ${pointText(p)}`]:[]);
    const effectiveOff=effective.flatMap((p,i)=>outside(p)?[`${el[i]||'有效第'+(i+1)+'点'} ${pointText(p)}`]:[]);
    $('recon-point-warning').hidden=!off.length&&!effectiveOff.length;
    $('recon-point-warning').textContent=[off.length?'原始导出存在图外点：'+off.join('；')+'。':'',effectiveOff.length?'当前有效点仍有图外点：'+effectiveOff.join('；')+'。':'',off.length||effectiveOff.length?'图外点无法在画布内显示，但完整坐标保留在此。':'' ].join('');
    const rows=[];
    raw.forEach((p,i)=>{const label=rl[i],j=label===undefined?-1:el.indexOf(label),q=j<0?null:effective[j];if(!q||p.some((n,k)=>Math.abs(n-q[k])>1e-7))rows.push([label||'原始第'+(i+1)+'点',p,q]);});
    effective.forEach((p,i)=>{if(el[i]===undefined||!rl.includes(el[i]))rows.push([el[i]||'有效第'+(i+1)+'点',null,p]);});
    const box=$('recon-point-changes');box.hidden=!rows.length;box.querySelector('summary').textContent=`原始与有效点变更对照 · ${rows.length} 项（按原点号）`;
    const table=make('table'),head=make('tr');for(const t of ['原点号／记录标签','原始导出','当前有效'])head.append(make('th',t));table.append(head);
    for(const [label,p,q] of rows){const tr=make('tr');for(const t of [label,pointText(p),pointText(q)])tr.append(make('td',t));table.append(tr);}box.querySelector('div').replaceChildren(table);box.open=off.length>0||effectiveOff.length>0;
  }
  const colors=['#2074b4','#8c4cc1','#169879','#ce526d','#73621c','#4b62c2'];
  function draw(){
    const canvas=$('recon-canvas'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,512);if(imageReady)ctx.drawImage(photo,0,0,1024,512);
    const v=focus();if(!v)return;const refs=current().variants.filter(v=>references.has(variantId(v))&&variantId(v)!==focusId),layers=[...refs.map((v,i)=>({v,color:colors[i%colors.length]})),{v,color:'#ef7b28'}];
    const legend=[];for(const {v:variant,color} of layers){const points=pointList(variant),labels=pointLabels(variant);legend.push(`${variant===v?'当前：':''}${variant.source.role==='annotation'?worker(variant)+' · '+condition(variant):variant.name}（${points.length}点）`);
      ctx.fillStyle=color;ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.font='13px Segoe UI';points.forEach(([x,y],i)=>{ctx.beginPath();ctx.arc(x,y,variant===v?4.5:3.5,0,Math.PI*2);ctx.fill();ctx.stroke();if($('recon-numbers').checked){const p=labels[i];const text=typeof p==='string'?p:Number.isInteger(p)?'p'+p:'点'+(i+1)+'*';ctx.lineWidth=3;ctx.strokeText(text,x+6,y-5);ctx.fillText(text,x+6,y-5);ctx.lineWidth=1.5;}});}
    $('recon-legend').replaceChildren(...layers.map(({v:variant,color},i)=>{const s=make('span',legend[i]);s.style.borderLeft='6px solid '+color;return s;}));
    const missing=pointLabels(v).length!==pointList(v).length;
    $('recon-point-note').textContent=`${modeNames[mode()]}；原始 ${v.source.raw_points?.length??0} 点 / 有效 ${v.source.effective_points?.length??0} 点。橙色为当前作答；只显示点位，点击原图可局部放大。${!pointList(v).length?'此版本没有可用点，未自动代用其他版本。':''}${missing?' 带 * 的编号为展示序号，不是原始 p 号。':''}`;
    if(zoomAt)zoom();
    drawGallery();
  }
  function zoom(){const [x,y]=zoomAt,canvas=$('recon-canvas'),out=$('recon-zoom'),ctx=out.getContext('2d'),tile=document.createElement('canvas');tile.width=3072;tile.height=512;const t=tile.getContext('2d');for(let i=0;i<3;i++)t.drawImage(canvas,i*1024,0);ctx.clearRect(0,0,800,400);ctx.drawImage(tile,x+1024-160,Math.max(0,Math.min(352,y-80)),320,160,0,0,800,400);out.hidden=false;}
  $('recon-canvas').onclick=e=>{const r=e.currentTarget.getBoundingClientRect();zoomAt=[(e.clientX-r.left)/r.width*1024,(e.clientY-r.top)/r.height*512];zoom();};
  $('recon-points').onchange=draw;$('recon-numbers').onchange=draw;$('recon-method').onchange=clusters;
  function render(){
    const c=current();if(!c.history_loaded||!c.variants.length)return;
    const changed=shownImage!==c.image_id;shownImage=c.image_id;
    if(changed){focusId=c.review.followup_ids[0]||c.review.reviewed_ids[0]||c.review.annotation_ids[0];references=new Set(c.variants.some(v=>variantId(v)==='reference:gt_revised')?['reference:gt_revised']:[]);zoomAt=null;$('recon-zoom').hidden=true;imageReady=false;
      const iid=c.image_id,newPhoto=new Image();photo=newPhoto;newPhoto.onload=()=>{if(current().image_id!==iid||photo!==newPhoto)return;imageReady=true;draw();};newPhoto.onerror=()=>{if(photo===newPhoto)$('recon-status').textContent='当前原图载入失败，请核对本地图片路径。';};newPhoto.src=window.STUDIO_IMAGES[currentCase].original;}
    $('recon-title').textContent=c.code+' · '+c.review.flags.map(f=>flags[f]||f).join(' / ');$('recon-summary').textContent=c.review.summary||'';
    $('recon-room-note').textContent=(c.review.room_label||'同房关系尚无支持归组')+'；物理同房不等于标注范围相同。';
    $('recon-focus').replaceChildren(...annotations().map(v=>option(variantId(v),`${worker(v)} · ${condition(v)} · ${v.source.events?.length||0}条旧审核`)));
    questions();clusters();setFocus(focusId);queue();disableOrder();
  }
  if(returnReview)returnPanel=returnReview.install({dataset,current,focusId:()=>focusId,decisions:()=>decisions,make,option,save:next=>{validate({...envelope(),...next});decisions={...decisions,...next};persist();},compare:ids=>{references=new Set(ids);if(ids.length)setFocus(ids[0]);},openImage:id=>openCase(caseById.get(id)),refilter});
  document.addEventListener('studio-case',()=>{render();refilter();});disableOrder();queue();render();refilter();
  $('recon-export').onclick=()=>{const blob=new Blob([JSON.stringify({...envelope(),exported_at:new Date().toISOString()},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=returnReview?'全历史标注_定向补审_20260927.json':'全历史标注_二次复核_20260925.json';a.click();URL.revokeObjectURL(url);};
  $('recon-import').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;const imported=validate(JSON.parse(await f.text()));if((Object.keys(decisions.image_decisions).length||Object.keys(decisions.annotation_decisions).length)&&!confirm('用导入文件替换本轮最终判断？两位审核者的旧原文不会改变。'))return;
    localStorage.setItem(storageKey,JSON.stringify({schema:decisionSchema,binding:dataset.binding,...imported}));decisions=imported;renderForms();refilter();$('recon-status').textContent='导入成功；只载入本轮最终判断，旧审核原文保持只读。';
  }catch(err){$('recon-status').textContent='导入失败，现有答案保留：'+err.message;}finally{e.target.value='';}};
  window.RECONCILIATION_APP={exportData:envelope,snapshot:()=>({imageId:current().image_id,imageReady:imageReady&&shownImage===current().image_id,focusId,pointMode:mode(),clusterMethod:method(),focusedHasGeometry:!!focus()?.geometry,
    visibleImages:filtered().length,imageProblemReviewed:imageResolved(current()),imageDecisions:Object.keys(decisions.image_decisions).length,annotationDecisions:Object.keys(decisions.annotation_decisions).length,
    annotationResolved:Object.values(decisions.annotation_decisions).filter(d=>d.status==='resolved').length})};
})();
