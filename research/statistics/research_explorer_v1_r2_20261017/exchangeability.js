'use strict';
(()=>{
const D=window.EXCHANGEABILITY,$=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>x===null||x===undefined||x===''?null:Number.isFinite(Number(x))?Number(x):null;
const fmt=x=>num(x)===null?(x==null||x===''?'—':String(x)):num(x).toLocaleString('zh-CN',{maximumFractionDigits:4});
const yes=x=>x===true||x==='True'||x==='true';
const mean=xs=>xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:null;
const names={high:'高Q',middle:'中Q',low:'低Q',higher_faster:'高Q快',higher_slower:'高Q慢',lower_faster:'低Q快',lower_slower:'低Q慢',unclassified:'未知',same_class:'同类替换',cross_class:'跨类替换'};
const cols={k:'人数',swap_kind:'替换类型',comparison_id:'交换对',image_code:'图片',entrant_a:'原人员',entrant_b:'替换人员',anchor_class:'原人员类',replacement_class:'替换人员类',attempted_pairs:'尝试对',paired_valid_blocks:'同／跨均有效的块',valid_images:'有效图片',V_image_mean:'V图等权均值',V_zero_rate:'底面相同率',Q_abs_image_mean:'|质量差|图等权均值',Q_valid_images:'质量有效图',annotation_floor_jaccard_distance:'原答范围距离',floor_jaccard_difference:'融合范围变化V',B8L2_difference:'B8L2右减左',D10_difference:'D10右减左',node_count_difference:'节点数变化',both_complete:'两队完整几何',both_main:'两队用途允许'};
Object.assign(cols,{floor_jaccard_difference_discovery:'发现背景V',floor_jaccard_difference_check:'另一背景V',discover_exact_full:'发现时几何严格相同',full_geometry_equal_check:'另一背景仍严格相同',shared_background_members:'两背景共同人数'});
cols.V_zero_rate='V≤1e−12比例';
const table=(rows,keys)=>'<table><thead><tr>'+keys.map(k=>'<th>'+esc(cols[k]||k)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+keys.map(k=>'<td>'+esc(['swap_kind','anchor_class','replacement_class'].includes(k)?names[r[k]]||r[k]:fmt(r[k]))+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
const options=(id,rows,current)=>{$(id).innerHTML=rows.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('');if([...$(id).options].some(o=>o.value===String(current)))$(id).value=current;};
const cards=xs=>xs.map(([n,v,t])=>`<div class="metric"><span>${esc(n)}</span><strong>${esc(fmt(v))}</strong><small>${esc(t)}</small></div>`).join('');
if(!D){$('coverage').innerHTML='<div class="error">本地显示数据未构建，请按本轮交付说明生成。</div>';return;}
const teams=new Map(D.teams.map(r=>[r.request_id,r]));let selected=[];
const examples=[['16人同类替换：较大变化',r=>r.swap_kind==='same_class'],['16人跨类替换：较大变化',r=>r.swap_kind==='cross_class'],['16人高Q快类内替换',r=>r.scheme==='RelQT4'&&r.anchor_class==='higher_faster'&&r.swap_kind==='same_class']].map(([label,test])=>({label,row:D.pairs.filter(r=>Number(r.k)===16&&test(r)&&num(r.floor_jaccard_difference)!==null).sort((a,b)=>num(b.floor_jaccard_difference)-num(a.floor_jaccard_difference))[0]})).filter(x=>x.row);
$('examples').innerHTML=examples.map((e,i)=>`<button data-example="${i}">${esc(e.label)} · ${esc(e.row.image_code)}</button>`).join('');
$('examples').onclick=e=>{if(e.target.dataset.example===undefined)return;const r=examples[Number(e.target.dataset.example)].row;$('scene').value='';$('scheme').value=r.scheme;images();$('image').value=r.image_code;$('anchorClass').value=r.anchor_class;$('k').value='16';render();$('pair').value=r.comparison_id;compare();$('background').scrollIntoView({behavior:'smooth',block:'start'});};
$('coverage').innerHTML=cards([['图片／建筑',D.summary.independent_buildings,'同一8图面板；普通6、门洞2'],['团队请求',D.teams.length,'含同背景的A／B／C'],['单人替换对',D.pairs.length,'同类与跨类成对声明'],['人数','6 / 8 / 12 / 16','沿同一背景排列嵌套增加']]);
function rows(){return D.pairs.filter(r=>r.scheme===$('scheme').value&&(!$('anchorClass').value||r.anchor_class===$('anchorClass').value)&&(!$('scene').value||r.scene_bucket===$('scene').value)&&(!$('image').value||r.image_code===$('image').value)&&(!$('k').value||Number(r.k)===Number($('k').value)));}
function classes(){options('anchorClass',[['','全部类别'],...[...new Set(D.pairs.filter(r=>r.scheme===$('scheme').value).map(r=>r.anchor_class))].sort().map(x=>[x,names[x]||x])],$('anchorClass').value);render();}
function images(){const old=$('image').value;options('image',[['','全部图片'],...[...new Set(D.pairs.filter(r=>!$('scene').value||r.scene_bucket===$('scene').value).map(r=>r.image_code))].sort().map(x=>[x,x])],old);classes();}
function summaries(rs){
 const metric=$('metric').value+'_difference',out=[];
 const sizes=[...new Set(rs.map(r=>Number(r.k)))].sort((a,b)=>a-b),chains=new Map();
 for(const r of rs){if(!chains.has(r.chain_id))chains.set(r.chain_id,[]);chains.get(r.chain_id).push(r);}
 const fixedV=new Set([...chains].filter(([,vs])=>vs.length===sizes.length*2&&vs.every(r=>num(r.floor_jaccard_difference)!==null)).map(([id])=>id));
 const fixedQ=new Set([...chains].filter(([,vs])=>vs.length===sizes.length*2&&vs.every(r=>yes(r.both_main)&&num(r[metric])!==null)).map(([id])=>id));
 for(const k of [...new Set(rs.map(r=>Number(r.k)))].sort((a,b)=>a-b)){
  const group=rs.filter(r=>Number(r.k)===k),blocks=new Map();
  for(const r of group){if(!blocks.has(r.exchange_block_id))blocks.set(r.exchange_block_id,[]);blocks.get(r.exchange_block_id).push(r);}
  const valid=[...blocks.values()].filter(b=>b.length===2&&fixedV.has(b[0].chain_id));
  const quality=[...blocks.values()].filter(b=>b.length===2&&fixedQ.has(b[0].chain_id));
  for(const kind of ['same_class','cross_class']){
   const vs=valid.flat().filter(r=>r.swap_kind===kind),qs=quality.flat().filter(r=>r.swap_kind===kind);
   const equalImage=(data,value)=>mean([...new Set(data.map(r=>r.image_code))].map(image=>mean(data.filter(r=>r.image_code===image).map(value))));
   out.push({k,swap_kind:kind,attempted_pairs:group.filter(r=>r.swap_kind===kind).length,paired_valid_blocks:valid.length,valid_images:new Set(vs.map(r=>r.image_code)).size,V_image_mean:equalImage(vs,r=>num(r.floor_jaccard_difference)),V_zero_rate:equalImage(vs,r=>num(r.floor_jaccard_difference)<=1e-12?1:0),Q_abs_image_mean:equalImage(qs,r=>Math.abs(num(r[metric]))),Q_valid_images:new Set(qs.map(r=>r.image_code)).size});
  }
 }
 return out;
}
function sizeChart(summary){
 const x=k=>70+(k-6)*72,y=v=>255-v*210,colors={same_class:'#087f8c',cross_class:'#b45309'};
 $('sizeChart').innerHTML=`<svg viewBox="0 0 900 305" role="img" aria-label="按人数的同类与跨类替换V图等权均值">${[0,.25,.5,.75,1].map(q=>`<line x1="60" x2="830" y1="${y(q)}" y2="${y(q)}" stroke="#e2e8f0"/><text x="18" y="${y(q)+4}">${q}</text>`).join('')}${Object.keys(colors).map(kind=>{const rs=summary.filter(r=>r.swap_kind===kind);return rs.map((r,i)=>{if(r.V_image_mean===null)return '';const p=rs[i-1];return(p&&p.V_image_mean!==null?`<line x1="${x(p.k)}" y1="${y(p.V_image_mean)}" x2="${x(r.k)}" y2="${y(r.V_image_mean)}" stroke="${colors[kind]}"/>`:'')+`<circle cx="${x(r.k)}" cy="${y(r.V_image_mean)}" r="5" fill="${colors[kind]}"><title>${names[kind]}，k=${r.k}，V=${fmt(r.V_image_mean)}，${r.valid_images}图</title></circle>`;}).join('');}).join('')}${[6,8,12,16].map(k=>`<text x="${x(k)-10}" y="280">${k}人</text>`).join('')}</svg><div class="legend"><span style="color:#087f8c">● 同类替换</span><span style="color:#b45309">● 跨类替换</span></div>`;
}
function distanceChart(rs){
 const valid=rs.filter(r=>num(r.annotation_floor_jaccard_distance)!==null&&num(r.floor_jaccard_difference)!==null),x=v=>65+v*750,y=v=>255-v*220;
 $('distanceChart').innerHTML=`<svg viewBox="0 0 900 310" role="img" aria-label="原作答距离与单人替换的融合范围变化散点">${[0,.25,.5,.75,1].map(q=>`<line x1="60" x2="830" y1="${y(q)}" y2="${y(q)}" stroke="#e2e8f0"/><text x="18" y="${y(q)+4}">${q}</text><text x="${x(q)-8}" y="280">${q}</text>`).join('')}${valid.map(r=>`<circle data-pair="${esc(r.comparison_id)}" tabindex="0" role="button" aria-label="查看${esc(r.comparison_id)}" cx="${x(num(r.annotation_floor_jaccard_distance))}" cy="${y(num(r.floor_jaccard_difference))}" r="3.4" opacity=".55" fill="${r.swap_kind==='same_class'?'#087f8c':'#b45309'}"><title>${esc(r.image_code+'，'+r.k+'人，'+names[r.swap_kind]+'，'+r.entrant_a+'→'+r.entrant_b+'，原答距='+fmt(r.annotation_floor_jaccard_distance)+'，V='+fmt(r.floor_jaccard_difference))}</title></circle>`).join('')}<text x="325" y="302">原作答底面距离（1−IoU）</text></svg>`;
}
function render(){
 selected=rows();const old=$('pair').value,summary=summaries(selected),valid=selected.filter(r=>num(r.floor_jaccard_difference)!==null),metric=$('metric').value;
 $('counts').innerHTML=cards([['交换对',selected.length,'保留失败与用途受限对'],['底面变化可算',valid.length,'同类／跨类曲线另取共同有效块'],['质量差可算',selected.filter(r=>yes(r.both_main)&&num(r[metric+'_difference'])!==null).length,'主质量门及数值同时满足'],['图片',new Set(selected.map(r=>r.image_code)).size,'不是独立交换对数量']]);
 const support=D.support.filter(r=>r.scheme===$('scheme').value&&(!$('image').value||r.image_code===$('image').value)&&(!$('scene').value||r.scene_bucket===$('scene').value));
 const fast=support.filter(r=>r.class_label==='higher_faster');
 $('support').textContent=fast.length?`当前“高Q快”每池仅${Math.min(...fast.map(r=>Number(r.class_workers)))}–${Math.max(...fast.map(r=>Number(r.class_workers)))}人；这里检验他们在大队中的替换作用，不能组成6–16人的纯高快队。`:'绝对Q保留原分数尺度但受历史任务分配影响；相对Q调整任务条件。两轴分开，不重复加权为总分。';
 sizeChart(summary);$('bySize').innerHTML=table(summary,['k','swap_kind','attempted_pairs','paired_valid_blocks','valid_images','V_image_mean','V_zero_rate','Q_abs_image_mean','Q_valid_images']);distanceChart(selected);
 options('pair',selected.map(r=>[r.comparison_id,`${r.comparison_id} · ${r.image_code} · ${r.k}人 · ${names[r.swap_kind]} · ${r.entrant_a}→${r.entrant_b} · V=${fmt(r.floor_jaccard_difference)}`]),old);
 $('pairs').innerHTML=table(selected,['comparison_id','image_code','k','swap_kind','entrant_a','entrant_b','anchor_class','replacement_class','annotation_floor_jaccard_distance','floor_jaccard_difference',metric+'_difference','node_count_difference','both_complete','both_main']);
 const transfer=D.transfers.filter(r=>r.scheme===$('scheme').value&&(!$('anchorClass').value||r.anchor_class===$('anchorClass').value)&&(!$('scene').value||r.scene_bucket===$('scene').value)&&(!$('image').value||r.image_code===$('image').value)&&(!$('k').value||Number(r.k)===Number($('k').value)));
 const exact=transfer.filter(r=>yes(r.discover_exact_full)),small=transfer.filter(r=>yes(r.discover_small_floor_001));
 $('transferCounts').innerHTML=cards([['严格相同的发现机会',exact.length,'同人员重复k／方案，不能当独立人对'],['另一背景仍严格相同',exact.filter(r=>yes(r.full_geometry_equal_check)).length,'含未能计算的机会在发现分母中'],['V≤0.01的发现机会',small.length,'探索阈值；不是人群分类'],['另一背景V最大值',small.some(r=>num(r.floor_jaccard_difference_check)!==null)?Math.max(...small.map(r=>num(r.floor_jaccard_difference_check)).filter(x=>x!==null)):null,'仅对可计算的另一背景']]);
 $('transfers').innerHTML=table(transfer.filter(r=>yes(r.discover_exact_full)||yes(r.discover_small_floor_001)),['image_code','k','entrant_a','entrant_b','floor_jaccard_difference_discovery','floor_jaccard_difference_check','discover_exact_full','full_geometry_equal_check','shared_background_members']);compare();document.body.dataset.ready='true';
}
function compare(){
 const pair=selected.find(r=>r.comparison_id===$('pair').value);if(!pair)return;
 const a=teams.get(pair.request_a),b=teams.get(pair.request_b),pool=D.pools[a.image_id],metric=$('metric').value;
 const background=a.worker_ids.filter(w=>w!==pair.entrant_a);
 $('background').textContent=`固定${background.length}名背景人员：${background.join('、')}。仅将${pair.entrant_a}替换为${pair.entrant_b}，其余成员、参考及算法相同。`;
 for(const [side,row,entrant,cl] of [['A',a,pair.entrant_a,pair.anchor_class],['B',b,pair.entrant_b,pair.replacement_class]]){
  const saved=pool.states[row.state_key],candidate=saved?.candidate,person=pool.records.find(r=>r.worker_id===entrant),profile=D.profiles.find(r=>r.fold===row.building_id&&r.worker_id===entrant&&r.metric==='B8L2');
  $('members'+side).textContent=`${entrant}（${names[cl]||cl}）；楼外绝对Q=${fmt(profile?.absolute_Q)}，相对Q=${fmt(profile?.Q_effect)}，时间效应=${fmt(profile?.T_source_effect)}。整队${metric}=${fmt(row[metric])}；${yes(row.main_comparison_allowed)&&num(row[metric])!==null?'主质量可用':'无主质量结果（计算或用途受限）'}；${row.nodes}节点。`;
  WorkbenchGeometry.mount($('geometry'+side),pool,person,{points:pool.reference.points_1024x512,floor:pool.reference.floor_xz_h},candidate?{...candidate,connected:yes(row.connection_available)&&yes(row.floor_evaluable)}:null);
 }
 $('difference').textContent=`${names[pair.swap_kind]}：原答范围距离=${fmt(pair.annotation_floor_jaccard_distance)}；融合范围V=${fmt(pair.floor_jaccard_difference)}；节点数变化=${fmt(pair.node_count_difference)}；完整几何严格相同=${pair.full_geometry_equal===''?'未能判断':yes(pair.full_geometry_equal)?'是':'否'}；${yes(pair.both_main)&&num(pair[metric+'_difference'])!==null?metric+'右减左='+fmt(pair[metric+'_difference']):'没有可比较的主质量差'}。V很小仅说明范围近似，不能推出结构、位置及高度完全相同。`;
}
$('distanceChart').onclick=e=>{const id=e.target.dataset.pair;if(!id)return;$('pair').value=id;compare();$('background').scrollIntoView({behavior:'smooth',block:'start'});};
$('distanceChart').onkeydown=e=>{if(e.key==='Enter')e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));};
$('scene').onchange=images;$('scheme').onchange=classes;for(const id of ['anchorClass','image','k','metric'])$(id).onchange=render;$('pair').onchange=compare;
$('export').onclick=()=>{const keys=[...new Set(selected.flatMap(r=>Object.keys(r)))],quote=x=>'"'+String(x??'').replace(/"/g,'""')+'"',csv='\ufeff'+[keys.map(quote).join(','),...selected.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\r\n'),url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='v1_single_person_exchanges.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
images();
})();
