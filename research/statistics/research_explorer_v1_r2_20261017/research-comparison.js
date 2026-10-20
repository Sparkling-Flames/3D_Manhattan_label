/* Saved research only: class overlays and shared-member multiview, no scoring or fusion. */
window.ResearchComparison=(()=>{
const C=WorkbenchCore,esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors=['#087f8c','#b45309','#7c3aed','#2563eb','#be185d','#64748b'];
const labelFields={Rnew2:'Rnew2_geometry_quality_class',F01:'F01_efficiency_class'};
const state={patterns:{case:'S07_reverse_new2',scheme:'Rnew2',cls:'all',worker:'',condition:'manual',layer:'all',team:'all',pair:'C'},multiview:{group:'',worker:'',stage:'after',view:'all'}};
let saved;
const select=(id,title,items,value)=>`<label>${esc(title)}<select id="${id}">${items.map(([k,v])=>`<option value="${esc(k)}" ${String(k)===String(value)?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
const fmt=v=>v==null?'缺失':Number(v).toFixed(2);
function classOf(a,scheme,labels,caseLabels={}){
 if(scheme==='points')return a.points?`${a.points.length/2}对点`:'几何缺失';
 if(scheme==='origin')return a.worker_id&&Number(a.worker_id.slice(1))>=100?'新增人员':'旧人员';
 if(scheme==='case')return caseLabels[a.worker_id]||'类别未知';
 return labels[a.worker_id]?.[labelFields[scheme]]||'类别未知';
}
function layers(answers,scheme,labels,caseLabels,cls,worker){
 const groups=[...new Set(answers.map(a=>classOf(a,scheme,labels,caseLabels)))].sort();
 return answers.filter(a=>cls==='all'||classOf(a,scheme,labels,caseLabels)===cls).filter(a=>a.points).map(a=>{
  const group=classOf(a,scheme,labels,caseLabels);
  return {id:a.object_id,label:`${a.worker_id} · ${group}`,points:a.points,confirmed:true,
   color:a.worker_id===worker?'#dc2626':colors[groups.indexOf(group)%colors.length],highlight:a.worker_id===worker};
 });
}
function reference(image,c){return c?.reference||image.references.find(r=>r.current)||image.references[0];}
function normalReference(r){return {points:r?.points,floor:r?.floor};}
async function render(host,options){
 const {mode,assets,loadImage,read,filters}=options,s=state[mode];
 const generation=String(Number(host.dataset.compareGeneration||0)+1);host.dataset.compareGeneration=generation;
 const alive=()=>host.isConnected&&host.dataset.compareGeneration===generation;
 saved=saved||await read('v2-resources/comparisons.json');
 if(!alive())return;
 const labels=Object.fromEntries(saved.labels.map(r=>[r.worker_id,r]));
 if(mode==='multiview')return multiview(host,s,loadImage,labels,options,alive);
 const images=assets.images.filter(i=>!i.flags.oos&&C.matchesImage(i,filters)&&
  (s.layer==='all'||String(C.imageFlags(i).doorway)===(s.layer==='doorway'?'true':'false')));
 const cases=saved.cases.filter(c=>images.some(i=>i.image_id===c.image_id));
 const selected=cases.find(c=>c.case_id===s.case);
 const im=images.find(i=>i.image_id===(s.image||selected?.image_id))||images[0];
 if(!im){host.innerHTML='<p class="placeholder">当前筛选没有非OOS图片。</p>';return;}
 s.image=im.image_id;
 const image=await loadImage(im.image_id);if(!alive())return;
 const c=cases.find(c=>c.case_id===s.case&&c.image_id===im.image_id);
 const conditions=[...new Set(image.annotations.map(a=>a.condition))];
 if(!conditions.includes(s.condition))s.condition=conditions[0];
 let answers=image.annotations.filter(a=>a.retained&&a.condition===s.condition);
 const ref=reference(image,c);
 const fusionCase=c?.teams?.length?c:saved.cases.find(x=>x.image_id===im.image_id&&x.condition===s.condition&&x.teams.length&&x.reference?.target_id===ref?.target_id);
 const teams=fusionCase?.teams||[],chosen=teams.find(t=>t.label===s.team);
 if(chosen)answers=answers.filter(a=>chosen.workers.includes(a.worker_id));
 const groups=[...new Set(answers.map(a=>classOf(a,s.scheme,labels,c?.worker_classes)))].sort();
 if(s.cls!=='all'&&!groups.includes(s.cls))s.cls='all';
 const workers=[...new Set(answers.map(a=>a.worker_id))].sort();
 if(!s.worker&&filters.worker&&workers.includes(filters.worker))s.worker=filters.worker;
 host.innerHTML=`<section class="panel"><h2>类别／标法 → 同图原答 → 已保存融合</h2><p>全部非OOS图片为起点，门洞可单列，GT问题图仍保留标法研究。下方使用独立条件；全局图片条件限制图片，人员条件用于高亮。类别未知不补标签。Rnew2/F01来源于普通Manual研究；切到Semi或门洞仅作跨条件观察，不称类别已跨条件验证。</p><div class="toolbar">
 ${select('rc-layer','场景',[['all','全部非OOS'],['ordinary','非门洞'],['doorway','门洞交界']],s.layer)}
 ${select('rc-case','已有发现',[['','自由浏览'],...cases.map(x=>[x.case_id,`${x.case_id} · ${x.title}`])],c?.case_id||'')}
 ${select('rc-image','图片',images.map(x=>[x.image_id,x.image_code]),s.image)}
 ${select('rc-condition','条件',conditions.map(x=>[x,x]),s.condition)}
 ${select('rc-scheme','类别／标法',[['Rnew2','Rnew2：35名新人的研究类'],['F01','F01：高Q23人快慢'],['case','该案例冻结类别'],['points','本图点对数标法'],['origin','人员来源']],s.scheme)}
 ${select('rc-class','叠加类别',[['all','所有类别'],...groups.map(x=>[x,x])],s.cls)}
 ${select('rc-worker','红色高亮人员',[['','不单独高亮'],...workers.map(x=>[x,x])],s.worker)}
 ${select('rc-team','原答成员范围',[['all','全部保留作答'],...teams.map(t=>[t.label,`保存团队${t.label}成员`])],s.team)}</div>
 <p>${esc(im.image_code)} · ${answers.length}份原答；${groups.map(g=>`${esc(g)} ${answers.filter(a=>classOf(a,s.scheme,labels,c?.worker_classes)===g).length}人`).join(' / ')}。原答叠线不是融合。滚轮以指针位置放大，拖拽平移，重置返回全景。</p>
 ${c?`<p class="info">${esc(c.explanation)}<br>来源：<a href="../../../${esc(c.source)}">冻结案例</a></p>`:''}
 ${image.flags.gt_problem||image.flags.image_hold?'<p class="warning">本图参考／用途存在限制；保留标法观察，不据此恢复正式质量资格。</p>':''}</section>
 <div class="geopair"><section class="panel"><h2>同图原标注叠加</h2><div id="rc-original"></div></section><section class="panel"><h2>对应已保存团队融合</h2><div id="rc-teams"></div></section></div>`;
 WorkbenchGeometry.mount(host.querySelector('#rc-original'),image,null,normalReference(ref),null,
  {layers:layers(answers,s.scheme,labels,c?.worker_classes,s.cls,s.worker),focus:c?.zoom});
 const teamHost=host.querySelector('#rc-teams');
 if(teams.length){
  const a=teams[0],b=teams.find(t=>t.label===s.pair)||teams[1]||teams[0];
  teamHost.innerHTML=`<p>保存结果来源：${esc(fusionCase.case_id)}；与当前图、条件及绑定参考对应。类别筛选不改变这支已计算团队。</p>`+select('rc-pair','与团队A比较',teams.slice(1).map(t=>[t.label,`团队${t.label}`]),b.label)+`<p>A ${a.workers.length}人：B8L2 ${fmt(a.B8L2)} / D10 ${fmt(a.D10)}；${esc(b.label)} ${b.workers.length}人：${fmt(b.B8L2)} / ${fmt(b.D10)}。节点 ${a.nodes} → ${b.nodes}。</p><details><summary>实际成员与团队身份</summary><p>A：${esc(a.workers.join('、'))}<br>${esc(b.label)}：${esc(b.workers.join('、'))}</p><p>${esc(a.team_key)}<br>${esc(b.team_key)}</p></details><div id="rc-fusion"></div>`;
  WorkbenchGeometry.mount(host.querySelector('#rc-fusion'),image,null,normalReference(ref),null,{layers:[a,b].map((t,i)=>({id:t.label,label:'团队'+t.label,points:t.points,floor:t.footprint,confirmed:!!t.points,color:colors[i]})),focus:c?.zoom});
 }else teamHost.innerHTML='<p class="placeholder">该图／案例未接入对应已保存融合，不生成新团队或分数。可选择S01—S10查看实际团队对照；M类局部案例用于原答结构观察。</p>';
 const redraw=()=>render(host,options).catch(e=>{host.textContent=e.message;});
 for(const [id,key] of [['rc-layer','layer'],['rc-image','image'],['rc-condition','condition'],['rc-scheme','scheme'],['rc-class','cls'],['rc-worker','worker'],['rc-team','team'],['rc-pair','pair']]){
  const el=host.querySelector('#'+id);if(el)el.onchange=()=>{s[key]=el.value;if(key==='image'){s.case='';s.team='all';}if(['scheme','condition','layer'].includes(key))s.cls='all';redraw();};
 }
 host.querySelector('#rc-case').onchange=e=>{s.case=e.target.value;const n=saved.cases.find(x=>x.case_id===s.case);if(n){s.image=n.image_id;s.condition=n.condition;}s.team='all';redraw();};
}
async function multiview(host,s,loadImage,labels,options,alive){
 const ids=Object.keys(saved.groups);if(!ids.includes(s.group))s.group=ids.includes('MV0005')?'MV0005':ids[0];
 const views=saved.groups[s.group],workers=views[0][s.stage].workers;
 if(s.worker&&!workers.includes(s.worker))s.worker='';
 const selected=s.view==='all'?views:views.filter(v=>v.image_id===s.view);
 host.innerHTML=`<section class="panel"><h2>同房 · 同人员／同团队跨视角</h2><p>本专题使用下方独立条件，全局人员筛选不裁剪已保存团队。以下5个保存状态组来自既有结构迁移案例；各组同一步骤的实际成员与进入顺序在打包时逐项核对一致。它们不是全量124924个前缀的可视化覆盖。个人／团队切换不重新融合。</p><div class="toolbar">
 ${select('mv-group','关系／保存状态组',ids.map(id=>[id,`${id} · ${saved.groups[id].map(v=>v.image_code).join(' / ')}`]),s.group)}
 ${select('mv-stage','保存节点',[['before','增人前'],['after','增人后']],s.stage)}
 ${select('mv-worker','比较对象',[['','相同团队融合'],...workers.map(w=>[w,`${w} · 同一人原答`])],s.worker)}
 ${select('mv-view','视角',[['all','全部视角并排'],...views.map(v=>[v.image_id,v.image_code])],s.view)}</div>
 <p>当前共同团队${workers.length}人：${esc(workers.join('、'))}。${s.worker?'红色为同一人的作答；其研究类别 '+esc(labels[s.worker]?.Rnew2_geometry_quality_class||'未知'):'青色为同一成员集合的已保存融合'}。可分别切换ERP／BEV／3D及局部放大。</p></section><div class="geopair">${selected.map((v,i)=>`<section class="panel"><h2>${esc(v.image_code)}</h2><p>团队 B8L2 ${fmt(v.before.B8L2)} → ${fmt(v.after.B8L2)}，人数${v.before.workers.length} → ${v.after.workers.length}；个人分数在切换时单列。</p><div id="mv-${i}"></div><p id="mv-score-${i}"></p></section>`).join('')}</div>`;
 for(let i=0;i<selected.length;i++){
  const v=selected[i],image=await loadImage(v.image_id);if(!alive())return;
  const a=s.worker?image.annotations.find(r=>r.worker_id===s.worker&&r.condition==='manual'&&r.retained):null;
  const g=v[s.stage].geometry;
  WorkbenchGeometry.mount(host.querySelector('#mv-'+i),image,a?{...a,color:'#dc2626',highlight:true}:null,{points:v.reference.points,floor:v.reference.floor},s.worker?null:{...g,connected:!!g?.points});
  if(a)host.querySelector('#mv-score-'+i).textContent=`${s.worker} 个人B8L2 ${fmt(a.quality.B8L2)}；环序 ${a.order_status}。`;
 }
 for(const [id,key] of [['mv-group','group'],['mv-stage','stage'],['mv-worker','worker'],['mv-view','view']])host.querySelector('#'+id).onchange=e=>{s[key]=e.target.value;if(key==='group')s.view='all';render(host,options).catch(e=>{host.textContent=e.message;});};
}
return {render,classOf,layers};
})();
