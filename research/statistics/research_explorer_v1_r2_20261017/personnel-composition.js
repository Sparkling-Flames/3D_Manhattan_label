'use strict';
(()=>{
const D=window.PERSONNEL_COMPOSITION,$=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=x=>x===null||x===undefined||x===''?null:Number.isFinite(Number(x))?Number(x):null;
const yes=x=>x===true||x==='True'||x==='true';
const fmt=x=>number(x)===null?(x===''||x==null?'—':String(x)):number(x).toLocaleString('zh-CN',{maximumFractionDigits:3});
const names={higher:'Q较高',lower:'Q较低',high:'Q高',middle:'Q中',low:'Q低',higher_faster:'高Q快',higher_slower:'高Q慢',lower_faster:'低Q快',lower_slower:'低Q慢',unknown:'未知',unclassified:'未知'};
const comp=x=>String(x||'').split('|').map(s=>{const [key,n]=s.split(':');return (names[key]||key)+(n?'×'+n:'');}).join(' ＋ ');
const columns={request_id:'请求',composition:'类别构成',member_sets:'不同成员集合',quality_member_sets:'主质量集合',nodes:'保留节点',R_union_normalized:'原答分歧R',complete_evaluable:'完整几何',main_comparison_allowed:'主质量用途',worker_id:'人员',Q_effect:'相对Q',T_source_effect:'来源T',Q_contexts:'Q任务数',Q_buildings:'Q建筑数',Q2:'Q二分',QT4:'Q×速度',Q3:'Q三档',Q3_25_75:'三档边界敏感性',source_time_complete:'完整来源时间',source_time_seconds:'来源活动秒'};
Object.assign(columns,{V_floor_jaccard_mean:'换人范围V均值',V_floor_jaccard_max:'换人范围V最大值',V_valid_pairs:'V有效配对',B8L2_mean:'B8L2均值',B8L2_range:'B8L2极差',D10_mean:'D10均值',D10_range:'D10极差',source_time_known_sum:'已知来源秒合计',source_time_missing_n:'来源时间缺失人数',target_time_known_sum:'已知目标秒合计',target_time_missing_n:'目标时间缺失人数',record_id:'作答',image_code:'图片',raw_point_count:'原始点数',effective_point_count:'有效点数',removed_original_labels:'已删除点',added_labels:'新增点',coordinate_edits:'坐标修正',order_id:'加入路径'});
const table=(rows,keys)=>'<table><thead><tr>'+keys.map(k=>'<th>'+esc(columns[k]||k)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+keys.map(k=>'<td>'+esc(k==='composition'?comp(r[k]):['B8L2_range','D10_range'].includes(k)&&Number(r.quality_member_sets)<2?'不足2组':['Q2','Q3','QT4','Q3_25_75'].includes(k)?(names[r[k]]||r[k]):fmt(r[k]))+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
const cards=items=>items.map(([label,value,note])=>`<div class="metric"><span>${esc(label)}</span><strong>${esc(fmt(value))}</strong><small>${esc(note)}</small></div>`).join('');
const options=(id,values,current,all=false)=>{$(id).innerHTML=(all?'<option value="">全部构成</option>':'')+values.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('');if([...$(id).options].some(o=>o.value===String(current)))$(id).value=current;};
let filtered=[];
if(!D){$('coverage').innerHTML='<div class="error">显示数据未构建；请查看README中的构建命令。</div>';return;}
const images=[...new Set(D.teams.map(r=>r.image_code))].sort();
options('image',images.map(i=>[i,i]),images[0]);
$('coverage').innerHTML=cards([['本轮图片',images.length,'普通与门洞分层'],['独立建筑',new Set(D.teams.map(r=>r.building_id)).size,'推断单位不使用重叠团队数'],['声明请求',D.teams.length,'含不同前缀与重复终点'],['当前数据','v1','冻结画像；修订后的有效几何']]);
$('pointEdits').innerHTML=table(D.point_edits,['record_id','image_code','worker_id','raw_point_count','effective_point_count','removed_original_labels','added_labels','coordinate_edits']);
const preferenceLabel=value=>({left:'左侧较好',right:'右侧较好',tie:'两者接近',close:'两者接近',uncertain:'未明确排序'}[value]||'未明确排序');
Object.assign(columns,{case_number:'例子',preference_label:'已记录相对判断'});
$('humanFeedback').innerHTML=table((D.human_feedback||[]).map(r=>({...r,preference_label:preferenceLabel(r.preference)})),['case_number','image_code','request_a','request_b','preference_label']);
$('reviewCases').innerHTML=D.review_cases.map((r,i)=>`<button data-case="${i}">${i+1} · ${esc(r.scheme)} · ${esc(r.image_code)}</button>`).join('');
$('reviewCases').onclick=e=>{const i=e.target.dataset.case;if(i===undefined)return;const c=D.review_cases[Number(i)];$('scheme').value=c.scheme;$('image').value=c.image_code;$('experiment').value='fixed_k_composition_and_members';controls();$('k').value='4';$('composition').value='';render();$('teamA').value=c.request_a;$('teamB').value=c.request_b;compare();$('geometryA').scrollIntoView({behavior:'smooth',block:'center'});};
function baseRows(){return D.teams.filter(r=>r.scheme===$('scheme').value&&r.image_code===$('image').value&&r.experiment===$('experiment').value);}
function controls(change){
 const rows=baseRows();const oldK=$('k').value;
 options('k',[...new Set(rows.map(r=>Number(r.k)))].sort((a,b)=>a-b).map(k=>[String(k),String(k)]),oldK||'4');
 const compositions=[...new Set(rows.filter(r=>Number(r.k)===Number($('k').value)).map(r=>r.composition))].sort();
 options('composition',compositions.map(c=>[c,comp(c)]),change==='composition'?$('composition').value:'',true);render();
}
function drawChart(rows){
 const metric=$('metric').value,valid=rows.filter(r=>yes(r.main_comparison_allowed)&&number(r[metric])!==null&&number(r.nodes)!==null);
 if(!valid.length){$('chart').innerHTML='<div class="placeholder">当前条件没有主质量可比较分数；下方保留请求状态和已保存几何。</div>';return;}
 const groups=[...new Set(valid.map(r=>r.composition))],colors=['#087f8c','#b45309','#7c3aed','#1d4ed8','#b91c1c','#6b7280','#166534'];
 const max=Math.max(...valid.map(r=>number(r.nodes)))+1,min=Math.max(0,Math.min(...valid.map(r=>number(r.nodes)))-1);
 const x=n=>60+(n-min)/(max-min||1)*790,y=q=>260-q*2.2;
 $('chart').innerHTML=`<svg viewBox="0 0 900 310" role="img" aria-label="每个真实团队的保留节点数与主质量分数">${[0,25,50,75,100].map(q=>`<line x1="60" x2="850" y1="${y(q)}" y2="${y(q)}" stroke="#e2e8f0"/><text x="18" y="${y(q)+4}">${q}</text>`).join('')}<text x="20" y="17">${metric}</text>${valid.map(r=>`<circle cx="${x(number(r.nodes))}" cy="${y(number(r[metric]))}" r="5" opacity=".75" fill="${colors[groups.indexOf(r.composition)%colors.length]}"><title>${esc(r.request_id+'；'+comp(r.composition)+'；节点'+r.nodes+'；'+metric+'='+fmt(r[metric]))}</title></circle>`).join('')}<text x="60" y="280">${min}</text><text x="835" y="280">${max}</text><text x="350" y="300">融合保留节点数（不等于正确结构数）</text></svg><div class="legend">${groups.map((g,i)=>`<span><i style="border-color:${colors[i%colors.length]}"></i>${esc(comp(g))}</span>`).join('')}</div>`;
}
function render(){
 const composition=$('composition').value,metric=$('metric').value;
 filtered=baseRows().filter(r=>Number(r.k)===Number($('k').value)&&(!composition||r.composition===composition));
 const first=filtered[0],main=filtered.filter(r=>yes(r.main_comparison_allowed)&&number(r[metric])!==null);
 $('counts').innerHTML=cards([['请求',filtered.length,'每行对应已声明团队或前缀'],['不同成员集合',new Set(filtered.map(r=>r.state_key)).size,'重复终点不增加样本'],['完整几何',filtered.filter(r=>yes(r.complete_evaluable)).length,'失败不填0分'],['主质量可评价',main.length,'其余质量值只供诊断']]);
 $('scopeNote').textContent=first?`当前图片：${first.image_code}；${String(first.scene_bucket).includes('doorway')?'门洞层':'普通层'}；分类基于${first.selection_metric}的目标建筑外画像。终点评价切换不改变成员。`:'当前方案没有此实验请求；未生成虚构曲线。';
 drawChart(filtered);
 drawOrders();
 const cells=$('experiment').value==='fixed_k_composition_and_members'?D.cells.filter(r=>r.scheme===$('scheme').value&&r.image_code===$('image').value&&Number(r.k)===Number($('k').value)&&(!composition||r.composition===composition)):[];
 const available=cells[0]?Object.keys(cells[0]):[];
 const keys=['composition','member_sets','quality_member_sets',metric+'_mean',metric+'_range','V_valid_pairs','V_floor_jaccard_mean','V_floor_jaccard_max'].filter(k=>available.includes(k));
 $('cells').innerHTML=cells.length?table(cells,keys):'<div class="placeholder">此条件没有固定构成的替换汇总；顺序前缀不自动当作独立换人实验。</div>';
 for(const side of ['A','B'])options('team'+side,filtered.map(r=>[r.request_id,r.request_id+' · '+comp(r.composition)+' · '+r.worker_ids.join('/')]),filtered[side==='A'?0:Math.min(1,filtered.length-1)]?.request_id);
 $('teams').innerHTML=filtered.length?table(filtered,['request_id','composition','nodes',metric,'R_union_normalized','complete_evaluable','main_comparison_allowed','source_time_known_sum','source_time_missing_n','target_time_known_sum','target_time_missing_n']):'<div class="placeholder">没有该条件请求。</div>';
 const profiles=first?D.profiles.filter(r=>r.fold===first.building_id&&r.metric===first.selection_metric):[];
 $('profiles').innerHTML=table(profiles,['worker_id','Q_effect','T_source_effect','Q2','QT4','Q3','Q3_25_75','Q_contexts','Q_buildings']);
 compare();document.body.dataset.ready='true';
}
function drawOrders(){
 const active=$('experiment').value==='same_endpoint_order';$('orderPanel').hidden=!active;if(!active)return;
 const rows=baseRows(),metric=$('metric').value,paths=[...new Set(rows.map(r=>r.order_id))],colors=['#087f8c','#b45309','#7c3aed'];
 const x=k=>70+(k-1)*240,y=q=>260-q*2.2,valid=r=>yes(r.main_comparison_allowed)&&number(r[metric])!==null;
 $('orderChart').innerHTML=`<svg viewBox="0 0 900 305" role="img" aria-label="相同最终成员的加入路径质量；缺失处断开">${[0,25,50,75,100].map(q=>`<line x1="60" x2="830" y1="${y(q)}" y2="${y(q)}" stroke="#e2e8f0"/><text x="18" y="${y(q)+4}">${q}</text>`).join('')}${paths.map((p,i)=>{const rs=rows.filter(r=>r.order_id===p).sort((a,b)=>a.k-b.k);return rs.map((r,j)=>{if(!valid(r))return '';const previous=rs[j-1];return (previous&&valid(previous)&&Number(r.k)===Number(previous.k)+1?`<line x1="${x(Number(previous.k))}" y1="${y(number(previous[metric]))}" x2="${x(Number(r.k))}" y2="${y(number(r[metric]))}" stroke="${colors[i]}"/>`:'')+`<circle cx="${x(Number(r.k))}" cy="${y(number(r[metric]))}" r="${6-i}" fill="${colors[i]}"><title>${esc(p+'；k='+r.k+'；'+metric+'='+fmt(r[metric]))}</title></circle>`;}).join('');}).join('')}${[1,2,3,4].map(k=>`<text x="${x(k)-12}" y="290">k=${k}</text>`).join('')}</svg>`;
 $('orderTable').innerHTML=table(rows,['order_id','k','composition','nodes',metric,'complete_evaluable','source_time_known_sum','source_time_missing_n']);
}
function compare(){
 const selected=[];
 for(const side of ['A','B']){
  const row=filtered.find(r=>r.request_id===$('team'+side).value);selected.push(row);
  if(!row){$('geometry'+side).innerHTML='<div class="placeholder">无可选团队。</div>';$('members'+side).textContent='';continue;}
  const pool=D.pools[row.image_id],saved=pool.states[row.state_key],candidate=saved?.candidate;
  const profiles=D.profiles.filter(p=>p.fold===row.building_id&&p.metric===row.selection_metric);
  $('members'+side).textContent=row.worker_ids.map(w=>{const p=profiles.find(p=>p.worker_id===w);return w+'（'+(names[p?.[row.scheme]]||p?.[row.scheme]||'未知')+'）';}).join('、')+`；${$('metric').value}=${fmt(row[$('metric').value])}；${yes(row.main_comparison_allowed)&&number(row[$('metric').value])!==null?'主质量可用':'无主质量结果（计算或用途受限）'}；自动环${candidate?.ring_confirmed?'有确认记录':'未人工确认'}。`;
  if(!saved){$('geometry'+side).innerHTML='<div class="placeholder">该请求未保存可展示几何，参见失败状态。</div>';continue;}
  WorkbenchGeometry.mount($('geometry'+side),pool,null,{points:pool.reference.points_1024x512,floor:pool.reference.floor_xz_h},candidate?{...candidate,connected:yes(row.connection_available)&&yes(row.floor_evaluable)}:null);
 }
 const [a,b]=selected,metric=$('metric').value;
 const feedback=(D.human_feedback||[]).find(r=>r.request_a===a?.request_id&&r.request_b===b?.request_id);
 $('selectedFeedback').hidden=!feedback;$('selectedFeedback').textContent=feedback?'已记录相对判断：'+preferenceLabel(feedback.preference)+'。对应当前左右两队，不代表分差大小已获人工校准。':'';
 $('comparison').textContent=a&&b?`${a.composition===b.composition?'同构成替换具体成员':'不同类别构成'}；同人数k=${a.k}。${yes(a.main_comparison_allowed)&&yes(b.main_comparison_allowed)&&number(a[metric])!==null&&number(b[metric])!==null?'右减左主质量差：'+fmt(number(b[metric])-number(a[metric])):'至少一侧不满足主质量比较资格，不能把诊断差作为主质量收益。'}`:'';
}
for(const id of ['scheme','image','experiment'])$(id).onchange=()=>controls(id);
$('k').onchange=()=>{options('composition',[...new Set(baseRows().filter(r=>Number(r.k)===Number($('k').value)).map(r=>r.composition))].sort().map(c=>[c,comp(c)]),'',true);render();};
$('composition').onchange=$('metric').onchange=render;
$('teamA').onchange=$('teamB').onchange=compare;
$('export').onclick=()=>{const keys=[...new Set(filtered.flatMap(r=>Object.keys(r)))],quote=v=>'"'+String(Array.isArray(v)?v.join('|'):v??'').replace(/"/g,'""')+'"',csv='\ufeff'+[keys.map(quote).join(','),...filtered.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='v1_personnel_composition_filtered.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
controls();
})();
