/* Saved research only: context-bound overlays and review exports; no scoring, fusion or label writes. */
window.ResearchComparison=(()=>{
'use strict';
const C=WorkbenchCore,esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors=['#087f8c','#b45309','#7c3aed','#2563eb','#be185d','#64748b'];
const labelFields={Rnew2:'Rnew2_geometry_quality_class',F01:'F01_efficiency_class'};
const defaults={case:'S07_reverse_new2',image:'',scheme:'Rnew2',cls:'all',worker:'',condition:'manual',layer:'all',team:'all',pair:'C',reference:'',blind:false};
const state={patterns:{...defaults},multiview:{group:'',worker:'',stage:'after',view:'all'}};
const feedback=[];
let savedCache;
const select=(id,title,items,value)=>`<label>${esc(title)}<select id="${id}">${items.map(([k,v])=>`<option value="${esc(k)}" ${String(k)===String(value)?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
const fmt=v=>v==null?'缺失':Number(v).toFixed(2);
function classOf(a,scheme,labels,caseLabels={}){
 if(scheme==='points')return a.points?`${a.points.length/2}对点`:'几何缺失';
 if(scheme==='origin')return a.worker_id&&Number(a.worker_id.slice(1))>=100?'新增人员':'旧人员';
 if(scheme==='case')return caseLabels[a.worker_id]||'类别未知';
 return labels[a.worker_id]?.[labelFields[scheme]]||'类别未知';
}
// Stable within a frozen snapshot, independent of sorting, class and score. This is review masking, not a security boundary.
function alias(kind,id,snapshot=''){
 let hash=2166136261;for(const ch of `${snapshot}|${kind}|${id}`){hash^=ch.charCodeAt(0);hash=Math.imul(hash,16777619);}
 return `${kind==='worker'?'成员':kind==='team'?'团队':'案例'} ${((hash>>>0).toString(16)).padStart(8,'0').toUpperCase()}`;
}
function layers(answers,scheme,labels,caseLabels,cls,worker,options={}){
 const groups=[...new Set(answers.map(a=>classOf(a,scheme,labels,caseLabels)))].sort();
 return answers.filter(a=>options.blind||cls==='all'||classOf(a,scheme,labels,caseLabels)===cls).filter(a=>a.points).map(a=>{
  const group=classOf(a,scheme,labels,caseLabels);
  return {id:options.blind?alias('worker',a.object_id,options.snapshot):a.object_id,
   label:options.blind?alias('worker',a.worker_id,options.snapshot):`${a.worker_id} · ${group}`,points:a.points,confirmed:true,
   color:a.worker_id===worker?'#dc2626':options.blind?colors[0]:colors[groups.indexOf(group)%colors.length],highlight:a.worker_id===worker};
 });
}
function resetSelection(s){s.team='all';s.cls='all';s.worker='';s.pair='C';s.reference='';s.reviewDraft={};}
function changeSelection(s,key,value,cases=[]){
 s[key]=value;
 if(['case','image','condition','layer'].includes(key)){
  resetSelection(s);
  if(key==='case'){const c=cases.find(c=>c.case_id===value);if(c){s.image=c.image_id;s.condition=c.condition;}}
  else s.case='';
 }else if(key==='reference'){s.team='all';s.cls='all';s.worker='';s.pair='C';}
 else if(key==='scheme'){s.cls='all';s.worker='';}
 else if(key==='team'){s.cls='all';s.worker='';}
 else if(key==='cls')s.worker='';
}
const linkKeys={case:'case',image:'image',condition:'condition',team:'team',worker:'worker',reference:'reference',snapshot:'requestedSnapshot',cmp_scheme:'scheme',cmp_class:'cls',cmp_layer:'layer',cmp_pair:'pair',cmp_blind:'blind'};
function readDeepLink(input){
 const get=input&&typeof input.get==='function'?k=>input.get(k):k=>input?.[k];
 const out={};for(const [url,key] of Object.entries(linkKeys)){const v=get(url);if(v!==undefined&&v!==null)out[key]=key==='blind'?v===true||v==='1'||v==='true':String(v);}
 return out;
}
function routeInput(options){
 if(options.deepLink)return readDeepLink(options.deepLink);
 if(typeof URLSearchParams!=='undefined'&&typeof window.location!=='undefined')return readDeepLink(new URLSearchParams(window.location.hash.slice(1)||window.location.search.slice(1)));
 return {};
}
function applyDeepLink(s,input,cases){
 const signature=JSON.stringify(input);if(signature===s.routeSignature)return;
 s.routeSignature=signature;
 if(!Object.keys(input).length)return;
 Object.assign(s,defaults,{case:'',requestedSnapshot:'',reviewDraft:{}},input);
 const c=cases.find(c=>c.case_id===s.case);
 if(c){if(!Object.hasOwn(input,'image'))s.image=c.image_id;if(!Object.hasOwn(input,'condition'))s.condition=c.condition;}
}
function sameGeometry(a,b){return ['points','floor'].every(k=>JSON.stringify(a?.[k]??null)===JSON.stringify(b?.[k]??null));}
function snapshotCompatible(snapshot,...objects){return !!snapshot&&objects.every(x=>!x?.snapshot_id||x.snapshot_id===snapshot);}
function resolveContext(image,cases,s,{snapshot,assetsSnapshot,requestedSnapshot,payload}={}){
 const notices=[];
 const c=cases.find(c=>c.case_id===s.case&&c.image_id===image.image_id&&c.condition===s.condition)||null;
 if(s.case&&!c)notices.push('所选案例与当前图片／条件不一致，已解除案例绑定。');
 const refs=image.references||[];
 const ref=s.reference?refs.find(r=>r.target_id===s.reference):refs.find(r=>r.target_id===c?.reference?.target_id)||refs.find(r=>r.current)||refs[0];
 if(s.reference&&!ref)notices.push('链接绑定的参考不在当前图片中；不替换成其它参考或融合。');
 const snapshotOK=snapshotCompatible(snapshot,{snapshot_id:assetsSnapshot},payload,image)&&(!requestedSnapshot||requestedSnapshot===snapshot);
 if(!snapshotOK)notices.push('快照缺失或与链接／资源不一致，已停用保存团队。');
 const caseReferenceMatches=!!c&&!!ref?.target_id&&c.reference?.target_id===ref.target_id&&sameGeometry(c.reference,ref);
 if(c&&!caseReferenceMatches)notices.push('当前查看参考与此案例冻结参考不同；隐藏原案例解释，不把历史结论应用于当前参考。');
 const compatible=x=>snapshotOK&&x.image_id===image.image_id&&x.condition===s.condition&&
  snapshotCompatible(snapshot,x)&&!!ref?.target_id&&x.reference?.target_id===ref.target_id&&sameGeometry(x.reference,ref)&&x.teams?.length;
 const fusionCase=(c&&compatible(c)?c:null)||cases.find(compatible)||null;
 if(!fusionCase)notices.push('当前图片、条件、参考与快照没有兼容的已保存融合；不生成新团队或分数。');
 return {case:c,caseReferenceMatches,reference:ref,fusionCase,teams:fusionCase?.teams||[],snapshot,snapshotOK,notices};
}
function reconcileSelection(s,answers,teams,labels,caseLabels){
 if(s.team!=='all'&&!teams.some(t=>t.label===s.team||t.team_key===s.team)){s.team='all';s.cls='all';s.worker='';}
 const chosen=teams.find(t=>t.label===s.team||t.team_key===s.team);if(chosen){s.team=chosen.label;answers=answers.filter(a=>chosen.workers.includes(a.worker_id));}
 const groups=[...new Set(answers.map(a=>classOf(a,s.scheme,labels,caseLabels)))].sort();
 if(s.cls!=='all'&&!groups.includes(s.cls)){s.cls='all';s.worker='';}
 const visible=answers.filter(a=>s.blind||s.cls==='all'||classOf(a,s.scheme,labels,caseLabels)===s.cls);
 const workers=[...new Set(visible.map(a=>a.worker_id))].sort();
 if(s.worker&&!workers.includes(s.worker))s.worker='';
 if(!teams.some(t=>t.label===s.pair))s.pair=teams[1]?.label||teams[0]?.label||'';
 return {answers,groups,workers,chosen};
}
function frozenState(s,context,options={}){
 return {schema:'research_comparison_state_v1',release:options.release||options.assets?.data_release||'v2',snapshot:context.snapshot,
  case:s.case||'',fusion_case:context.fusionCase?.case_id||'',image:s.image,condition:s.condition,reference:context.reference?.target_id||s.reference||'',team:s.team,worker:s.worker,
  cmp_scheme:s.scheme,cmp_class:s.cls,cmp_layer:s.layer,cmp_pair:s.pair,cmp_blind:s.blind?'1':'0',filters:{...options.filters}};
}
function makeDeepLink(frozen,base='index.html'){
 const params=new URLSearchParams();params.set('module',frozen.module||'patterns');
 for(const key of ['release','group','stage','view',...Object.keys(linkKeys)])if(frozen[key]!==undefined&&frozen[key]!==null)params.set(key,String(frozen[key]));
 for(const [key,value] of Object.entries(frozen.filters||{}))if(value)params.set('f_'+key,String(value));
 return String(base).split('#')[0]+'#'+params.toString();
}
function feedbackRecord(frozen,fields={},now=new Date().toISOString()){
 return {snapshot:frozen.snapshot,case_id:frozen.case||frozen.fusion_case||'',fusion_case_id:frozen.fusion_case||'',image_id:frozen.image,condition:frozen.condition,reference_id:frozen.reference,
  team_key:fields.team_key||'',team_label:fields.team_label||'',member_scope:frozen.team||'all',comparison_pair:frozen.cmp_pair||'',worker_id:frozen.worker||'',region:String(fields.region||''),
  status:fields.status||'unreviewed',notes:String(fields.notes||''),blind:frozen.cmp_blind==='1',created_at:now};
}
const feedbackColumns=['snapshot','case_id','fusion_case_id','image_id','condition','reference_id','team_key','team_label','member_scope','comparison_pair','worker_id','region','status','notes','blind','created_at'];
function exportFeedback(rows,kind){
 if(kind==='json')return JSON.stringify({schema:'research_comparison_feedback_v1',records:rows},null,2);
 // Prevent a review note from being interpreted as a spreadsheet formula when the CSV is opened.
 return C.csv(rows.map(r=>Object.fromEntries(feedbackColumns.map(k=>[k,typeof r[k]==='string'&&/^[=+\-@\t\r]/.test(r[k])?"'"+r[k]:r[k]]))),feedbackColumns);
}
function download(options,name,body,type){
 if(options.download)return options.download(name,body,type);
 const url=URL.createObjectURL(new Blob([body],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
async function render(host,options){
 const {mode,assets,loadImage,read}=options,filters=options.filters||{},s=state[mode];
 const generation=String(Number(host.dataset.compareGeneration||0)+1);host.dataset.compareGeneration=generation;
 const alive=()=>host.isConnected&&host.dataset.compareGeneration===generation&&(!options.isCurrent||options.isCurrent());
 const snapshot=options.snapshot||assets.snapshot_id;
 // comparisons.json is packaged alongside the resource index; its published v1 contract has no snapshot_id.
 // Bind that legacy payload to the exact index/read context, while validating explicit stamps when supplied.
 if(!savedCache||savedCache.read!==read||savedCache.assets!==assets||savedCache.snapshot!==snapshot){
  const entry={read,assets,snapshot,promise:read('v2-resources/comparisons.json')};savedCache=entry;
  entry.promise.catch(()=>{if(savedCache===entry)savedCache=null;});
 }
 const saved=await savedCache.promise;if(!alive())return;
 const labels=Object.fromEntries(saved.labels.map(r=>[r.worker_id,r]));
 if(mode==='multiview')return multiview(host,s,loadImage,labels,options,alive,saved);
 applyDeepLink(s,routeInput(options),saved.cases);
 const images=assets.images.filter(i=>!i.flags?.oos&&C.matchesImage(i,filters)&&
  (s.layer==='all'||String(C.imageFlags(i).doorway)===(s.layer==='doorway'?'true':'false')));
 const cases=saved.cases.filter(c=>images.some(i=>i.image_id===c.image_id));
 if(s.image&&!assets.images.some(i=>i.image_id===s.image)){host.innerHTML='<p class="placeholder">链接指定的图片没有接入当前快照；不替换成其它图片。</p>';return;}
 const selected=cases.find(c=>c.case_id===s.case);
 const im=images.find(i=>i.image_id===(s.image||selected?.image_id))||images[0];
 if(!im){host.innerHTML='<p class="placeholder">当前筛选没有非OOS图片。</p>';return;}
 if(s.image&&s.image!==im.image_id){resetSelection(s);s.case='';}
 s.image=im.image_id;
 const image=await loadImage(im.image_id);if(!alive())return;
 if(image.image_id!==im.image_id)throw Error('图片详情与索引不一致，停止混合显示。');
 const conditions=[...new Set(image.annotations.map(a=>a.condition))];
 if(!conditions.includes(s.condition)){
  if(routeInput(options).condition===s.condition){host.innerHTML='<p class="placeholder">链接指定的条件在当前图片中不可用；不借用其它条件的作答或融合。</p>';return;}
  s.condition=conditions[0]||'';resetSelection(s);s.case='';
 }
 const context=resolveContext(image,cases,s,{snapshot,assetsSnapshot:assets.snapshot_id,requestedSnapshot:s.requestedSnapshot,payload:saved});
 const c=context.case,ref=context.reference,teams=context.teams,fusionCase=context.fusionCase;
 if(s.case&&!c){s.case='';s.team='all';s.cls='all';s.worker='';}
 const {answers,groups,workers}=reconcileSelection(s,image.annotations.filter(a=>a.retained&&a.condition===s.condition),teams,labels,c?.worker_classes);
 if(!s.worker&&filters.worker&&workers.includes(filters.worker))s.worker=filters.worker;
 const frozen=frozenState(s,context,options),blind=s.blind;
 const reviewContext=JSON.stringify([snapshot,s.case,s.image,s.condition,ref?.target_id,s.team,s.worker,s.pair]);
 if(s.reviewContext!==reviewContext)s.reviewDraft={};s.reviewContext=reviewContext;
 const workerName=id=>blind?alias('worker',id,snapshot):id;
 const teamName=t=>blind?alias('team',t.team_key||t.label,snapshot):`团队${t.label}`;
 const caseName=x=>blind?alias('case',x.case_id,snapshot):`${x.case_id} · ${x.title}`;
 const link=makeDeepLink(frozen,options.linkBase||(typeof window.location!=='undefined'?window.location.href:'index.html'));
 host.innerHTML=`<section class="panel"><h2>${blind?'盲审：同图原答与已保存融合':'类别／标法 → 同图原答 → 已保存融合'}</h2>
 <p>${blind?'盲审隐藏人员编号、研究类别、案例解释与分数；匿名别名在同一快照内稳定。导出复核记录保留真实绑定ID用于追溯。':'全部非OOS图片为起点，门洞可单列，GT问题图仍保留标法研究。下方使用独立条件；全局图片条件限制图片，人员条件用于高亮。类别未知不补标签。Rnew2/F01来源于普通Manual研究；切到Semi或门洞仅作跨条件观察，不称类别已跨条件验证。'}</p>
 ${blind?'':'<p class="info">本页保留历史Rnew2／F01及案例冻结标签，不代表当前DSTRUCT／RFUSE分类验证。<a href="#release=v2&amp;module=personnel_main&amp;tab=0">查看当前7种分类与ALL／楼外名单</a>；新大块证据在人员研究第3步。筛选原答不重新生成团队。</p>'}
 <div class="toolbar">${select('rc-layer','场景',[['all','全部非OOS'],['ordinary','非门洞'],['doorway','门洞交界']],s.layer)}
 ${select('rc-case','已有发现',[['','自由浏览'],...cases.map(x=>[x.case_id,caseName(x)])],c?.case_id||'')}
 ${select('rc-image','图片',images.map(x=>[x.image_id,x.image_code]),s.image)}
 ${select('rc-condition','条件',conditions.map(x=>[x,x]),s.condition)}
 ${select('rc-reference','查看参考',[...(s.reference&&!ref?[[s.reference,s.reference+' · 不可用']]:[]),...(image.references||[]).map(x=>[x.target_id,x.label||x.target_id])],ref?.target_id||s.reference||'')}
 ${blind?'':select('rc-scheme','类别／标法',[['Rnew2','Rnew2：35名新人的研究类'],['F01','F01：高Q23人快慢'],['case','该案例冻结类别'],['points','本图点对数标法'],['origin','人员来源']],s.scheme)+select('rc-class','叠加类别',[['all','所有类别'],...groups.map(x=>[x,x])],s.cls)}
 ${select('rc-worker',blind?'红色高亮成员':'红色高亮人员',[['','不单独高亮'],...workers.map(x=>[x,workerName(x)])],s.worker)}
 ${select('rc-team','原答成员范围',[['all','全部保留作答'],...teams.map(t=>[t.label,teamName(t)+'成员'])],s.team)}
 <label><input id="rc-blind" type="checkbox" ${blind?'checked':''}>盲审模式</label></div>
 <p class="info" id="rc-context">图片 ${esc(im.image_code)} · 条件 ${esc(s.condition)} · 参考 ${esc(ref?.target_id||'不可用')} · 快照 ${esc(snapshot||'不可用')} · 案例 ${esc(c?(blind?alias('case',c.case_id,snapshot):c.case_id):'自由浏览')} · ${teams.length}支兼容保存团队</p>
 ${context.notices.map(n=>`<p class="warning">${esc(n)}</p>`).join('')}
 <p>${answers.length}份原答${blind?'':`；${groups.map(g=>`${esc(g)} ${answers.filter(a=>classOf(a,s.scheme,labels,c?.worker_classes)===g).length}人`).join(' / ')}`}。原答叠线不是融合。滚轮放大，拖拽平移，重置返回全景。</p>
 ${c&&context.caseReferenceMatches&&!blind?`<p class="info">${esc(c.explanation)}<br>来源：<a href="../../../${esc(c.source)}">冻结案例</a></p>`:''}
 ${image.flags?.gt_problem||image.flags?.image_hold?'<p class="warning">本图参考／用途存在限制；保留标法观察，不据此恢复正式质量资格。</p>':''}
 <details><summary>当前冻结状态链接</summary><p><a id="rc-state-link" href="${esc(link)}">打开此图片、条件、参考与选择</a></p>${blind?'':`<input id="rc-link-text" aria-label="当前冻结状态链接" readonly value="${esc(link)}">`}<button id="rc-export-state">导出状态JSON</button></details></section>
 <div class="geopair"><section class="panel"><h2>同图原标注叠加</h2><div id="rc-original"></div></section><section class="panel"><h2>对应已保存团队融合</h2><div id="rc-teams"></div></section></div>
 <section class="panel"><h2>复核记录</h2><p class="warning">本页会话保存，刷新或关闭前请导出；不会自动写回研究数据。</p><p>仅记录当前观察；不改研究标签、评分或源数据。区域可填ERP坐标范围、点号或文字描述。</p><div class="toolbar">
 ${select('rc-review-team','复核对象',[['','当前原答集合'],...teams.map(t=>[t.team_key,teamName(t)])],s.reviewDraft?.team_key||'')}
 <label>区域<input id="rc-review-region" value="${esc(s.reviewDraft?.region||'')}" placeholder="如 ERP x=420–600, y=100–380"></label>
 ${select('rc-review-status','复核状态',[['unreviewed','未定'],['needs_review','待复核'],['observed','已观察'],['no_issue_observed','未观察到问题']],s.reviewDraft?.status||'unreviewed')}
 <label>备注<textarea id="rc-review-notes">${esc(s.reviewDraft?.notes||'')}</textarea></label></div>
 <div class="actions"><button id="rc-review-add">记录本次观察</button><button id="rc-review-json" ${feedback.length?'':'disabled'}>导出复核JSON</button><button id="rc-review-csv" ${feedback.length?'':'disabled'}>导出复核CSV</button></div><p id="rc-review-count" role="status">本次页面会话已记录 ${feedback.length} 条；刷新前请导出。</p></section>`;
 WorkbenchGeometry.mount(host.querySelector('#rc-original'),image,null,{points:ref?.points,floor:ref?.floor},null,
  {layers:layers(answers,s.scheme,labels,c?.worker_classes,s.cls,s.worker,{blind,snapshot}),focus:c?.zoom});
 const teamHost=host.querySelector('#rc-teams');
 if(teams.length){
  const a=teams[0],b=teams.find(t=>t.label===s.pair)||teams[1]||teams[0];
  teamHost.innerHTML=`<p>保存结果来源：${esc(blind?alias('case',fusionCase.case_id,snapshot):fusionCase.case_id)}；已核对图片、条件、参考坐标与资源快照。筛选不改变已计算团队。</p>`+
   (teams.length>1?select('rc-pair','与'+teamName(a)+'比较',teams.slice(1).map(t=>[t.label,teamName(t)]),b.label):'')+
   (blind?`<p>${esc(teamName(a))} ${a.workers.length}人；${esc(teamName(b))} ${b.workers.length}人。</p>`:`<p>${esc(teamName(a))} ${a.workers.length}人：B8L2 ${fmt(a.B8L2)} / D10 ${fmt(a.D10)}；${esc(teamName(b))} ${b.workers.length}人：${fmt(b.B8L2)} / ${fmt(b.D10)}。节点 ${a.nodes} → ${b.nodes}。</p>`)+
   `<details><summary>${blind?'匿名成员':'实际成员与团队身份'}</summary><p>${esc(teamName(a))}：${esc(a.workers.map(workerName).join('、'))}<br>${esc(teamName(b))}：${esc(b.workers.map(workerName).join('、'))}</p>${blind?'':`<p>${esc(a.team_key)}<br>${esc(b.team_key)}</p>`}</details><div id="rc-fusion"></div>`;
  WorkbenchGeometry.mount(host.querySelector('#rc-fusion'),image,null,{points:ref?.points,floor:ref?.floor},null,{layers:[...new Set([a,b])].map((t,i)=>({id:blind?alias('team',t.team_key||t.label,snapshot):t.label,label:teamName(t),points:t.points,floor:t.footprint,confirmed:!!t.points,color:colors[i]})),focus:c?.zoom});
 }else teamHost.innerHTML='<p class="placeholder">当前上下文没有兼容的已保存融合；不借用其它条件、参考或快照的团队。</p>';
 const redraw=()=>render(host,options).catch(e=>{host.textContent=e.message;});
 for(const [id,key] of [['rc-case','case'],['rc-layer','layer'],['rc-image','image'],['rc-condition','condition'],['rc-reference','reference'],['rc-scheme','scheme'],['rc-class','cls'],['rc-worker','worker'],['rc-team','team'],['rc-pair','pair']]){
  const el=host.querySelector('#'+id);if(el)el.onchange=()=>{changeSelection(s,key,el.value,saved.cases);s.reviewDraft={};redraw();};
 }
 host.querySelector('#rc-blind').onchange=e=>{s.blind=e.target.checked;s.cls='all';redraw();};
 host.querySelector('#rc-export-state').onclick=()=>download(options,'comparison-state.json',JSON.stringify({...frozen,url:link},null,2),'application/json');
 const draft=()=>({team_key:host.querySelector('#rc-review-team').value,region:host.querySelector('#rc-review-region').value,status:host.querySelector('#rc-review-status').value,notes:host.querySelector('#rc-review-notes').value});
 for(const id of ['team','region','status','notes'])host.querySelector('#rc-review-'+id).oninput=()=>{s.reviewDraft=draft();};
 host.querySelector('#rc-review-add').onclick=()=>{
  const fields=draft(),team=teams.find(t=>t.team_key===fields.team_key);
  feedback.push(feedbackRecord(frozen,{...fields,team_label:team?.label||''}));s.reviewDraft={};
  host.querySelector('#rc-review-region').value='';host.querySelector('#rc-review-notes').value='';host.querySelector('#rc-review-status').value='unreviewed';host.querySelector('#rc-review-team').value='';
  host.querySelector('#rc-review-count').textContent=`本次页面会话已记录 ${feedback.length} 条；刷新前请导出。`;
  host.querySelector('#rc-review-json').disabled=false;host.querySelector('#rc-review-csv').disabled=false;
 };
 for(const kind of ['json','csv'])host.querySelector('#rc-review-'+kind).onclick=()=>{if(feedback.length)download(options,'comparison-feedback.'+kind,exportFeedback(feedback,kind),kind==='json'?'application/json':'text/csv;charset=utf-8');};
 if(options.onContext)options.onContext({...frozen,blind,fusion_case:fusionCase?.case_id||'',compatible_teams:teams.map(t=>t.team_key),notices:context.notices});
}
function readMultiviewLink(input){
 const get=input&&typeof input.get==='function'?k=>input.get(k):k=>input?.[k],out={};
 for(const key of ['group','worker','stage','view','snapshot','cmp_blind']){const v=get(key);if(v!==undefined&&v!==null)out[key]=String(v);}
 return out;
}
function groupFromRows(group,groups,rows){
 if(Object.hasOwn(groups,group))return group;
 const matches=[...new Set(rows.filter(r=>String(r.source_codes||'').split('|').some(code=>code===group||code.split(':').at(-1)===group)).map(r=>r.group_id).filter(id=>Object.hasOwn(groups,id)))];
 return matches.length===1?matches[0]:'';
}
async function resolveGroup(group,saved,options){
 if(Object.hasOwn(saved.groups,group))return group;
 if(options.groupAliases?.[group]&&Object.hasOwn(saved.groups,options.groupAliases[group]))return options.groupAliases[group];
 // A source relation ID (for example G046) is not a saved-state group ID (MV0001).
 // Resolve using the actual published coverage table, never by suffix/position heuristics.
 const index=await options.read('v2-data/index.json');
 if(index.snapshot_id!==(options.snapshot||options.assets.snapshot_id))return '';
 const meta=index.tables.find(t=>t.id==='same_room_multiview__group_coverage');if(!meta)return '';
 const rows=[];
 for(const part of meta.parts){const data=await options.read('v2-data/'+part.path);for(const row of data.rows)rows.push(Object.fromEntries(data.columns.map((k,i)=>[k,row[i]])));}
 return groupFromRows(group,saved.groups,rows);
}
async function multiview(host,s,loadImage,labels,options,alive,saved){
 const snapshot=options.snapshot||options.assets.snapshot_id;
 const input=options.deepLink||(typeof window.location!=='undefined'?new URLSearchParams(window.location.hash.slice(1)||window.location.search.slice(1)):{});
 const linkState=readMultiviewLink(input),signature=JSON.stringify(linkState);
 if(signature!==s.routeSignature){
  s.routeSignature=signature;
  if(Object.keys(linkState).length){s.group=linkState.group||'';s.worker=linkState.worker||'';s.stage=linkState.stage||'after';s.view=linkState.view||'all';s.requestedSnapshot=linkState.snapshot||'';s.blind=linkState.cmp_blind==='1'||linkState.cmp_blind==='true';}
 }
 const ids=Object.keys(saved.groups);
 if(!ids.length){host.innerHTML='<p class="placeholder">当前快照没有已保存的同成员跨视角组。</p>';return;}
 const sourceGroup=s.group;
 if(s.group&&!ids.includes(s.group)){
  try{s.group=await resolveGroup(s.group,saved,options);}catch{if(!alive())return;host.innerHTML='<p class="placeholder">来源关系组映射不可用；未替换成其它保存组。</p>';return;}
  if(!alive())return;
  if(!s.group){s.group=sourceGroup;host.innerHTML='<p class="placeholder">所选关系组尚无唯一对应的已保存多视角状态；未替换成其它组。</p>';return;}
 }
 if(!s.group)s.group=ids.includes('MV0005')?'MV0005':ids[0];
 if(!['before','after'].includes(s.stage)){host.innerHTML='<p class="placeholder">所选保存节点不可用。</p>';return;}
 if(!snapshotCompatible(snapshot,{snapshot_id:options.assets.snapshot_id},saved)||(s.requestedSnapshot&&s.requestedSnapshot!==snapshot)){host.innerHTML='<p class="placeholder">多视角链接与资源快照不一致，停止混合显示。</p>';return;}
 const views=saved.groups[s.group],workers=views[0][s.stage].workers;
 if(s.worker&&!workers.includes(s.worker))s.worker='';
 if(s.view!=='all'&&!views.some(v=>v.image_id===s.view||v.image_code===s.view)){host.innerHTML='<p class="placeholder">所选视角不在当前保存组内，未替换成其它视角。</p>';return;}
 const selected=s.view==='all'?views:views.filter(v=>v.image_id===s.view||v.image_code===s.view);
 if(s.view!=='all')s.view=selected[0].image_id;
 const blind=!!s.blind,workerName=w=>blind?alias('worker',w,snapshot):w;
 const frozen={schema:'research_comparison_state_v1',module:'multiview',release:options.release||'v2',snapshot,group:s.group,stage:s.stage,view:s.view,worker:s.worker,cmp_blind:blind?'1':'0'};
 const link=makeDeepLink(frozen,options.linkBase||(typeof window.location!=='undefined'?window.location.href:'index.html'));
 host.innerHTML=`<section class="panel"><h2>同房 · 同人员／同团队跨视角</h2><p>本专题使用下方独立条件，全局人员筛选不裁剪已保存团队。以下5个保存状态组来自既有结构迁移案例；各组同一步骤的实际成员与进入顺序在打包时逐项核对一致。它们不是全量124924个前缀的可视化覆盖。个人／团队切换不重新融合。</p><div class="toolbar">
 ${select('mv-group','关系／保存状态组',ids.map(id=>[id,`${id} · ${saved.groups[id].map(v=>v.image_code).join(' / ')}`]),s.group)}
 ${select('mv-stage','保存节点',[['before','增人前'],['after','增人后']],s.stage)}
 ${select('mv-worker','比较对象',[['','相同团队融合'],...workers.map(w=>[w,`${workerName(w)} · 同一人原答`])],s.worker)}
 ${select('mv-view','视角',[['all','全部视角并排'],...views.map(v=>[v.image_id,v.image_code])],s.view)}
 <label><input id="mv-blind" type="checkbox" ${blind?'checked':''}>盲审模式</label></div>
 <p class="info">保存组 ${esc(s.group)}${sourceGroup&&sourceGroup!==s.group?' · 来源关系 '+esc(sourceGroup):''} · 条件 manual · 保存节点 ${esc(s.stage)} · 快照 ${esc(snapshot)}</p>
 <p>当前共同团队${workers.length}人：${esc(workers.map(workerName).join('、'))}。${s.worker?'红色为同一人的作答'+(blind?'':'；其研究类别 '+esc(labels[s.worker]?.Rnew2_geometry_quality_class||'未知')):'青色为同一成员集合的已保存融合'}。可分别切换ERP／BEV／3D及局部放大。</p>
 <p><a id="mv-state-link" href="${esc(link)}">打开当前多视角冻结状态</a><button id="mv-export-state">导出状态JSON</button></p></section>
 <div class="geopair">${selected.map((v,i)=>`<section class="panel"><h2>${esc(v.image_code)}</h2><p>参考 ${esc(v.reference.target_id)}${blind?'':` · 团队 B8L2 ${fmt(v.before.B8L2)} → ${fmt(v.after.B8L2)}`} · 人数${v.before.workers.length} → ${v.after.workers.length}</p><div id="mv-${i}"></div><p id="mv-score-${i}"></p></section>`).join('')}</div>`;
 for(let i=0;i<selected.length;i++){
  const v=selected[i],image=await loadImage(v.image_id);if(!alive())return;
  const reference=image.references.find(r=>r.target_id===v.reference.target_id);
  const slot=host.querySelector('#mv-'+i);
  if(image.image_id!==v.image_id||!snapshotCompatible(snapshot,image,v)||!reference||!sameGeometry(reference,v.reference)){
   slot.textContent='当前图片、参考坐标或快照与保存状态不一致；未显示此融合。';continue;
  }
  const a=s.worker?image.annotations.find(r=>r.worker_id===s.worker&&r.condition==='manual'&&r.retained):null;
  if(s.worker&&!a){slot.textContent='当前视角没有该成员的保留Manual原答；不以团队融合代替个人作答。';continue;}
  const g=v[s.stage].geometry;
  WorkbenchGeometry.mount(slot,image,a?{...a,color:'#dc2626',highlight:true}:null,{points:v.reference.points,floor:v.reference.floor},s.worker?null:{...g,connected:!!g?.points});
  if(a)host.querySelector('#mv-score-'+i).textContent=blind?`${workerName(s.worker)} · 同一成员原答。`:`${s.worker} 个人B8L2 ${fmt(a.quality?.B8L2)}；环序 ${a.order_status}。`;
 }
 const redraw=()=>render(host,options).catch(e=>{host.textContent=e.message;});
 for(const [id,key] of [['mv-group','group'],['mv-stage','stage'],['mv-worker','worker'],['mv-view','view']])host.querySelector('#'+id).onchange=e=>{s[key]=e.target.value;if(key==='group'){s.view='all';s.worker='';}redraw();};
 host.querySelector('#mv-blind').onchange=e=>{s.blind=e.target.checked;redraw();};
 host.querySelector('#mv-export-state').onclick=()=>download(options,'multiview-state.json',JSON.stringify({...frozen,url:link},null,2),'application/json');
 if(options.onContext)options.onContext({...frozen,blind});
}
return {render,classOf,layers,alias,changeSelection,readDeepLink,applyDeepLink,resolveContext,reconcileSelection,frozenState,makeDeepLink,feedbackRecord,exportFeedback,readMultiviewLink,groupFromRows};
})();

