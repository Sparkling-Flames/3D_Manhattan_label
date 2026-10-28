'use strict';
(()=>{
 const cases=window.V21_EXCHANGE_CASES, select=document.getElementById('case'), team=document.getElementById('team'), answer=document.getElementById('answer');
 const showCandidates=document.getElementById('showCandidates'),candidate=document.getElementById('candidate'),supporter=document.getElementById('supporter');
 const focus=document.getElementById('reviewFocus'),showSupportPoints=document.getElementById('showSupportPoints');
 let c,preferred=null;
 const idsForFocus=(value,arm)=>value==='seam'?['node_003']:value==='near'?['node_004']:value==='split'?(arm==='C'?['node_005','node_011']:['node_005']):[];
 const esc=s=>String(s??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
 const fmt=x=>Number.isFinite(x)?x.toFixed(2):'不可评分';
 select.innerHTML=cases.map((x,i)=>`<option value="${i}">${esc(x.image.image_code)} · ${esc(x.image.difficulty.label)} · ${x.image_gap<0?'反例':'正向对照'}</option>`).join('');
 function selectCase(){
  c=cases[Number(select.value)||0];
  document.getElementById('blocks').innerHTML=['D','X','Y','Z'].map(k=>`<p><strong>${k}（${c[k].length}人${k==='X'||k==='Y'?' · 源类 '+esc(c.source_class):k==='Z'?' · 目标类 '+esc(c.target_class):''}）</strong>：${c[k].map(esc).join('、')}</p>`).join('');
  team.innerHTML=['A','B','C'].map(k=>`<option value="${k}">${k} = D + ${k==='A'?'X':k==='B'?'Y':'Z'} · Q ${fmt(c.teams[k].B8L2)}</option>`).join('');
  team.value='A';answer.value='';candidate.value='';supporter.value='';
  const [a,b,z]=['A','B','C'].map(k=>c.teams[k].B8L2);
  const valid=[a,b,z].every(Number.isFinite),within=valid?Math.abs(b-a):null,cross=valid?(Math.abs(z-a)+Math.abs(z-b))/2:null;
  document.getElementById('comparison').textContent=`图级平均：同类 ${fmt(c.image_within)}，跨类 ${fmt(c.image_cross)}，差值 ${fmt(c.image_gap)}。本事件：A→B ${valid?fmt(b-a):'不可评分'}，A→C ${valid?fmt(z-a):'不可评分'}，B→C ${valid?fmt(z-b):'不可评分'}；同类绝对变化 ${fmt(within)}，对称跨类绝对变化 ${fmt(cross)}，跨类－同类 ${valid?fmt(cross-within):'不可评分'}。跨类幅度更大不等于质量提高。`;
  draw();
 }
 function draw(){
  const t=c.teams[team.value], annotations=c.image.annotations;
  const records=t.member_object_ids.map(id=>annotations.find(a=>a.object_id===id)).filter(Boolean);
  const chosen=records.find(a=>a.object_id===answer.value)||records[0];
  answer.innerHTML=records.map(a=>`<option value="${esc(a.object_id)}">${esc(a.worker_id)} · ${c.D.includes(a.worker_id)?'共同背景':c.Z.includes(a.worker_id)?'目标类 Z':c.X.includes(a.worker_id)?'源类 X':'源类 Y'}</option>`).join('');
  if(chosen)answer.value=chosen.object_id;
  const layers=records.filter(a=>a!==chosen).map(a=>({id:'member_'+a.worker_id,label:a.worker_id+' · 完整原答',points:a.points,raw:a.raw_points,confirmed:!!a.points,visible:false}));
  const focusActive=focus.value&&c.event_id==='84320bad6f9ea2b352a805f2';
  const candidates=focusActive?t.review_groups.filter(x=>idsForFocus(focus.value,team.value).includes(x.feature_id)):(t.unselected_candidates||[]);
  const selected=candidates.find(x=>x.feature_id===(preferred||candidate.value));preferred=null;
  candidate.innerHTML='<option value="">选择候选</option>'+candidates.map(x=>`<option value="${esc(x.feature_id)}">${esc(x.feature_id)} · ${x.support}/${records.length}票 · ${x.selected?'已入选':'未入选'} · ${x.selected?'高于门槛':'距门槛'}${Math.abs(t.minimum_support-x.support)}票</option>`).join('');
  candidate.value=selected?.feature_id||'';
  supporter.innerHTML=selected?'<option value="">选择支持者</option>'+selected.members.map(m=>`<option value="${esc(m.object_id)}">${esc(m.worker_id)} · 原答点对 ${m.source_pair_index}</option>`).join(''):'<option value="">先选择候选</option>';
  supporter.value=selected&&selected.members.some(m=>m.object_id===chosen?.object_id)?chosen.object_id:'';
  document.getElementById('candidateStatus').textContent=candidates.length?`${focusActive?'本问题':'本队'}有 ${candidates.length} 个候选；${selected?`${selected.feature_id}：${selected.support}/${records.length}票，${selected.selected?'已入选':'未入选'}${selected.D_support==null?'':`，共同D ${selected.D_support}票 + 替换块 ${selected.replacement_support}票`}。`:''}选择候选可查看对应支持者。`:'本队没有待查看候选。';
  if(showCandidates.checked)for(const x of candidates)layers.push({id:'candidate_'+x.feature_id,label:`${x.selected?'已入选':'未入选'} ${x.feature_id} · ${x.support}/${records.length}票`,points:x.center,diagnostic:true,color:x===selected?'#d3276a':'#ad4d05',visible:true});
  if(showSupportPoints.checked&&selected)layers.push({id:'candidate_support_points',label:'该组支持者原答点对',points:selected.members.flatMap(m=>m.points),diagnostic:true,color:'#1963bd',visible:true});
  const g=t.geometry||{};
  window.WorkbenchGeometry.mount(document.getElementById('view'),c.image,chosen,c.reference,{points:g.points,footprint:g.footprint,connected:t.score_status==='complete_conditional'}, {layers});
  document.getElementById('status').textContent=`队伍 ${team.value} · ${records.length} 人 · B8L2 ${t.B8L2?.toFixed(3)??'缺失'} · ${t.score_status} · 投票门槛 ${t.minimum_support}；勾选其他成员叠加。`;
  document.getElementById('detail').textContent=`实际团队：${t.member_workers.join('、')}。入选节点支持数：${(t.node_supports||[]).join('、')}。保存几何：${g.status||'未记录'}；${g.reason||'无额外原因'}；环序${g.ring_confirmed?'已确认':'未确认'}。事件 ${c.event_id}。`;
 }
 function focusTeam(){const t=c.teams[team.value],ids=idsForFocus(focus.value,team.value),item=t.review_groups.find(x=>ids.includes(x.feature_id));preferred=item?.feature_id||null;answer.value=item?.members[0]?.object_id||'';draw();}
 focus.addEventListener('change',()=>{
  if(!focus.value){candidate.value='';draw();return;}
  const index=cases.findIndex(x=>x.event_id==='84320bad6f9ea2b352a805f2');select.value=String(index);selectCase();
  team.value=focus.value==='near'?'B':focus.value==='split'?'C':'A';showCandidates.checked=true;showSupportPoints.checked=true;
  document.getElementById('focusHelp').textContent=focus.value==='seam'?'这组公共D为5人；A/B 8票未入选，C 11票入选。切换A/B/C查看。':focus.value==='near'?'这组公共D为6人；A 10票入选、B 7票未入选、C 12票入选。切换A/B/C查看。':'A的一组D观察在C拆入两组（2人和5人），请选择C队两组逐一查看原答；是否为不同结构待你判断。';
  focusTeam();
 });
 select.addEventListener('change',()=>{focus.value='';document.getElementById('focusHelp').textContent='';selectCase();});team.addEventListener('change',()=>{answer.value='';candidate.value='';supporter.value='';if(focus.value)focusTeam();else draw();});answer.addEventListener('change',draw);
 showCandidates.addEventListener('change',draw);
 showSupportPoints.addEventListener('change',draw);
 candidate.addEventListener('change',()=>{const t=c.teams[team.value],groups=focus.value?t.review_groups:t.unselected_candidates,x=groups.find(y=>y.feature_id===candidate.value);if(x){showCandidates.checked=true;answer.value=x.members[0].object_id;}draw();});
 supporter.addEventListener('change',()=>{if(supporter.value)answer.value=supporter.value;draw();});selectCase();
})();
