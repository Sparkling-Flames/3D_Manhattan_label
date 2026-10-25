'use strict';
window.MethodSupplements=(()=>{
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names={manual:'Manual 手动',semi:'Semi 半自动',left:'左更好',right:'右更好',close:'两者接近',uncertain:'各有问题或无法判断',reselected:'D10 重新形成',fixed_old_model:'固定旧模型',D10_reselected:'D10 重新形成',D10_fixed_old_model:'D10 固定旧模型',B8L2_original:'原 B8L2 分类',wall_auto:'墙线自动连接',medoid:'代表原答',lee_mv50:'Lee MV50 底面投票',ordinary_manual:'普通 Manual',doorway_manual:'门洞 Manual',special_manual:'特殊 Manual',ordinary_semi:'普通 Semi',special_semi:'特殊 Semi',new_batch_not_in_known_quality_case_tables:'新批候选（未认证从未曝光）',previously_exposed_quality_case:'已曝光机制题',floor_region:'仅底面',complete_layout:'完整布局',no_connection:'无法连接',below_four:'少于四点',complete_conditional:'有条件完整输出',weak:'弱',moderate:'中等',clear:'明确',clear_problem:'明显问题',not_resolved:'未能判断',scope_sensitive:'依赖范围',True:'是',False:'否'};
const fmt=v=>v===null||v===undefined||v===''?'—':Object.hasOwn(names,v)?names[v]:Number.isFinite(Number(v))?Number(v).toLocaleString('zh-CN',{maximumFractionDigits:3}):String(v);
const num=v=>v===''||v===null||v===undefined?null:Number(v);
const choose=(id,label,options,value)=>`<label>${esc(label)}<select id="${id}">${options.map(([key,name])=>`<option value="${esc(key)}" ${String(key)===String(value)?'selected':''}>${esc(name)}</option>`).join('')}</select></label>`;
const options=values=>[...new Set(values)].filter(v=>v!==undefined&&v!==null&&v!=='').sort((a,b)=>String(a).localeCompare(String(b),'zh')).map(v=>[v,names[v]||v]);
const grid=(rows,columns,max=24)=>`<div class="tablewrap"><table><thead><tr>${columns.map(([_,label])=>`<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${rows.slice(0,max).map(row=>`<tr>${columns.map(([key])=>`<td title="${esc(row[key]??'')}">${esc(fmt(row[key]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="scope-label">显示 ${Math.min(rows.length,max)} / ${rows.length} 行；完整来源见下方文件入口。</p>`;
const source=(path,label)=>`<a href="../../../${esc(path)}" target="_blank" rel="noopener">${esc(label)}</a>`;
const state={person:{condition:'manual',tier:'coarse',arm:'reselected',heldout:'ALL',panel:''},fusion:{condition:'manual',layer:'ordinary_manual',n:'4',team:'',member:''},quality:{case:'QV006'}};
let dataPromise;
function requireData(ctx){
 if(!ctx.assets.method_supplements)throw Error('请先运行 v2 研究台构建命令，生成方法补充资源。');
 if(!dataPromise)dataPromise=ctx.read(ctx.resourcesBase+ctx.assets.method_supplements).catch(error=>{dataPromise=null;throw error;});
 return dataPromise.then(data=>{if(data.schema!=='method_supplements_display_20261024_v1'||data.snapshot_id!==ctx.snapshot||data.data_release!=='v2')throw Error('方法补充资源版本或快照不一致');return data;});
}
function personnel(slot,data,ctx){
 const p=data.personnel,s=state.person;
 const conditions=options(p.PARTITION_COMPARISON.map(r=>r.condition));
 const heldouts=[['ALL','ALL · 全历史描述'],...options(p.PARTITION_COMPARISON.map(r=>r.heldout_building).filter(v=>v!=='ALL'))];
 if(!heldouts.some(([v])=>v===s.heldout))s.heldout='ALL';
 const partition=p.PARTITION_COMPARISON.filter(r=>r.condition===s.condition&&r.tier===s.tier&&r.formation_arm===s.arm&&r.heldout_building===s.heldout);
 const workers=p.WORKER_RANK_AND_LABELS.filter(r=>r.condition===s.condition&&r.formation_arm===s.arm&&r.heldout_building===s.heldout);
 const chosen=p.SELECTED_TEAM_CROSS_EVALUATION.filter(r=>r.condition_B8===s.condition&&r.tier===s.tier&&r.policy==='class_highq'&&r.compared_arm==='D10_'+s.arm);
 const changed=chosen.filter(r=>r.team_key_B8!==r.team_key_D10);
 const comparable=chosen.filter(r=>num(r.D10_delta)!==null);
 const delta=comparable.length?comparable.reduce((a,r)=>a+Number(r.D10_delta),0)/comparable.length:null;
 const summaries=p.COMPOSITION_COMMON_COMPARISON.filter(r=>r.condition===s.condition&&r.tier===s.tier);
 const panels=p.COMPOSITION_COMMON_PANEL_SUMMARY.filter(r=>r.condition===s.condition&&r.tier===s.tier);
 if(!panels.some(r=>r.panel_id===s.panel))s.panel=panels.find(r=>r.panel_id==='X7HyMhZNoso-05__semi__5212c0d241__v2__n16')?.panel_id||panels[0]?.panel_id||'';
 const panelRows=panels.filter(r=>r.panel_id===s.panel);
 const roles=p.STRUCTURE_HIGHQ_ROLE_SUMMARY.filter(r=>r.condition_B8===s.condition&&r.tier===s.tier);
 const abc=p.ABC_COMMON_PHYSICAL_SUMMARY.filter(r=>r.condition_B8===s.condition&&r.tier===s.tier);
 const legality=p.ABC_LEGALITY_SUMMARY.filter(r=>r.condition===s.condition&&r.tier===s.tier);
 slot.innerHTML=`<section class="panel"><h2>D10 人员形成敏感性</h2><p>原四套 B8L2 工作分类及名单保持原版本；这里单独比较同一批人用 D10 形成类别、重新选人后，同指标的团队表现。ALL 是全历史描述，楼外折排除目标建筑历史 ${ctx.hintButton('ARI')}。历史分区仅影响下方分区与逐人名单；选队和配比汇总各目标楼的楼外评价，ALL 不是选队模型。</p><p>已验收锚点：Manual 高Q团队改变 11/179；Semi 粗类 21/32、细类 19/32。D10 共同可评分平均差依次为 −0.006、−0.308、−1.153 分；Semi 后两项各有 28 个共同可评面板，新增失败 2/1。固定结构角色/队伍在 292 个可用面板中未改变。当前筛选下的逐队行见下方。</p><div class="toolbar">${choose('ms-person-condition','条件',conditions,s.condition)}${choose('ms-person-tier','粗/细类',[['coarse','粗类'],['fine','细类']],s.tier)}${choose('ms-person-arm','形成方案',[['reselected','D10 重选'],['fixed_old_model','固定旧模型']],s.arm)}${choose('ms-person-heldout','历史分区',heldouts,s.heldout)}</div><div class="actions"><a href="#module=personnel_main&tab=0">原四套分类名单</a>${source('research/workers/personnel_d10_formation_sensitivity_20261024/README.md','方法与完整结果')}</div></section>
 <section class="panel"><h2>分区与逐人归属 ${ctx.hintButton('ARI')}</h2>${grid(partition,[['formation_arm','形成方案'],['heldout_building','排除建筑'],['workers','人员'],['old_known','旧已知'],['d10_known','D10已知'],['ARI','ARI'],['matched_same','配对同组'],['old_family','旧方法族'],['d10_family','D10方法族']],20)}<details><summary>当前分区每位人员的旧/D10标签、Q/T与名次</summary><p>同组比较使用配对后的 D10 类号；原始 D10 类名可能只发生重命名。历史 Q 列为中心化值，可为负数，不是 0–100 原始质量分。</p>${grid(workers,[['worker_id','人员'],['coarse_label_B8','旧粗类'],['coarse_label_D10','D10原类'],['coarse_matched_D10','D10配对粗类'],['fine_label_B8','旧细类'],['fine_matched_D10','D10配对细类'],['q_history_B8','旧历史Q中心化'],['q_history_D10','D10历史Q中心化'],['rank_shift_D10_minus_B8','名次变化']],100)}</details></section>
 <section class="panel"><h2>同指标交叉评价</h2><p>当前形成方案 ${esc(fmt(s.arm))} 的 ${chosen.length} 个高Q分类选队面板，换队 ${changed.length}；D10 两队都可评分 ${comparable.length}，D10对照队减旧队均值 ${fmt(delta)}。两列 selected_workers 是 12 选 6 的所选六人块，其余背景人员固定；完整团队身份由 team_key 标识。失败单列，不把缺分记为零。</p>${grid([...changed,...chosen.filter(r=>r.team_key_B8===r.team_key_D10)],[['image_B8','图片'],['panel_id','固定面板'],['selected_workers_B8','旧所选6人块'],['selected_workers_D10','D10所选6人块'],['replacements','换人数'],['B8L2_B8','旧队B8L2'],['B8L2_D10','新队B8L2'],['D10_B8','旧队D10'],['D10_D10','新队D10'],['D10_delta','D10差'],['failure_delta','失败变化']],24)}</section>
 <section class="panel"><h2>配比解释与结构角色 ${ctx.hintButton('eta2')}</h2>${grid(summaries,[['compared_arm','比较'],['metric','指标'],['panels','面板'],['comparable_panels','共同可比'],['old_eta2_mean','旧η²均值'],['new_eta2_mean','新η²均值']],16)}${choose('ms-person-panel','逐面板',options(panels.map(r=>r.panel_id)),s.panel)}${panelRows.some(r=>r.B8L2_eta2===''||r.D10_eta2==='')?'<p class="warning">η² 不适用：没有质量波动。该 Semi 常数分面 924 队分数相同，不显示成 0 或 100%。Semi 共 42 个已知面板，41 个可比较。</p>':''}${grid(panelRows,[['formation_arm','形成方案'],['compared_arm','比较'],['matched_teams','匹配队'],['failed','失败'],['B8L2_valid','B8有效'],['B8L2_eta2','B8 η²'],['D10_valid','D10有效'],['D10_eta2','D10 η²']],12)}<details><summary>固定结构角色与高Q换队汇总</summary>${grid(roles,[['difficulty_B8','难度'],['panels','面板'],['available_both','两侧可用'],['role_changed','角色变化'],['changed_teams','换队'],['B8L2_delta','B8差'],['D10_delta','D10差']],20)}</details></section>
 <section class="panel"><h2>ABC 替换与资格敏感性</h2><p>同一组三支实际团队、同一角色下的作用差为零是设计恒等关系；角色重排与可用资格变化分开查看。m2/m3 对照不替代大块主结果。</p><details><summary>共同合法的三支实际团队</summary>${grid(abc,[['difficulty_B8','难度'],['m','m'],['compared_arm','比较'],['common_legal_events','共同合法'],['scored','可评分'],['same_orientation','同向'],['B8L2_extra_change','额外B8变化'],['D10_extra_change','额外D10变化']],40)}</details><details><summary>两侧合法性与未知</summary>${grid(legality,[['difficulty','难度'],['n','n'],['m','m'],['compared_arm','比较'],['attempts','尝试'],['both','双侧合法'],['old_only','仅旧'],['new_only','仅新'],['old_unknown','旧未知'],['new_unknown','新未知']],60)}</details></section>`;
 slot.querySelectorAll('select[id^="ms-person-"]').forEach(el=>el.onchange=()=>{s[el.id.slice(10)]=el.value;personnel(slot,data,ctx);});
}
function geoRings(footprint){if(!footprint||typeof footprint!=='object'||Array.isArray(footprint))return [];if(footprint.type==='Polygon')return footprint.coordinates;if(footprint.type==='MultiPolygon')return footprint.coordinates.flat();return [];}
async function fusion(slot,data,ctx){
 const f=data.fusion,s=state.fusion;
 const validLayers=options(f.TEAM_REGISTRATION.filter(r=>r.condition===s.condition).map(r=>r.layer)).map(([v])=>v);
 if(!validLayers.includes(s.layer))s.layer=validLayers.find(v=>v==='ordinary_'+s.condition)||validLayers[0]||'';
 const validN=options(f.TEAM_REGISTRATION.filter(r=>r.condition===s.condition&&r.layer===s.layer).map(r=>r.n)).map(([v])=>v);
 if(!validN.includes(s.n))s.n=validN[0]||'';
 const teams=f.TEAM_REGISTRATION.filter(r=>r.condition===s.condition&&r.layer===s.layer&&r.n===s.n);
 if(!teams.some(r=>r.request_id===s.team))s.team=teams[0]?.request_id||'';
 const team=teams.find(r=>r.request_id===s.team);
 const endpoints=team?f.METHOD_ENDPOINTS.filter(r=>r.request_id===team.request_id):[];
 const geometry=endpoints.map(e=>({endpoint:e,geometry:f.METHOD_GEOMETRY.find(g=>g.team_key===e.team_key&&g.method===e.method)}));
 const scene=f.COMMON_SCENE_SUMMARY.filter(r=>r.condition===s.condition&&r.layer===s.layer&&r.n===s.n&&r.comparison==='wall_auto_minus_medoid'&&r.metric==='B8L2'&&r.support_domain==='complete_layout');
 const attempts=f.ALL_ATTEMPT_STATUS.filter(r=>r.condition===s.condition&&r.layer===s.layer&&r.n===s.n);
 const floor=f.THREE_METHOD_FLOOR_SUMMARY.filter(r=>r.condition===s.condition&&r.layer===s.layer&&r.n===s.n);
 const displayedAttempts=attempts.map(r=>r.method==='lee_mv50'?{...r,full_outputs:'不适用',full_evaluable:'不适用'}:r);
 const displayedEndpoints=endpoints.map(r=>r.method==='lee_mv50'?{...r,full_output:'不适用',B8L2:'不适用',D10:'不适用'}:r);
 slot.innerHTML=`<section class="panel"><h2>同队三法：墙线自动连接、代表原答、Lee MV50</h2><p>固定 138 次团队尝试；完整布局共同可评 130 队，底面三法共同可评 131 队。普通 Manual 墙线减代表原答：n4 +7.108（16/22图），n8 −0.515（13/22），n16 −5.545（8/23）。均分和偏低的部分（P10）在共同可评域 ${ctx.hintButton('common_evaluable_domain')}，失败按全部尝试报告。Lee 只输出底面，顶界与完整Q为不适用，不记成失败 0。</p><div class="toolbar">${choose('ms-fusion-condition','条件',options(f.TEAM_REGISTRATION.map(r=>r.condition)),s.condition)}${choose('ms-fusion-layer','场景层',options(f.TEAM_REGISTRATION.filter(r=>r.condition===s.condition).map(r=>r.layer)),s.layer)}${choose('ms-fusion-n','人数',[['4','4'],['8','8'],['16','16']],s.n)}</div><p>${source('research/fusion/fusion_common_panel_20261024/README.md','方法、资格与全部保存结果')} · 代表原答 ${ctx.hintButton('medoid')}</p></section>
  <section class="panel"><h2>均值、多数、偏低的部分（P10）与失败</h2><p>下表逐难度分层，图片多数按独立图计，不把队数当人数。Lee 的完整布局与完整可评不属其声明能力，显示“不适用”；底面输出计数保留。</p>${grid(scene,[['difficulty','难度'],['images','图'],['teams','共同可评队'],['left_mean','墙线均值'],['right_mean','代表原答均值'],['mean_delta','差'],['positive_images','正向图'],['negative_images','负向图'],['left_p10','墙线P10'],['right_p10','代表P10']],30)}<details><summary>全部尝试状态，包括无连接和少于四点</summary>${grid(displayedAttempts,[['difficulty','难度'],['method','方法'],['attempts','尝试'],['full_outputs','完整输出'],['floor_outputs','底面输出'],['full_evaluable','完整可评'],['missing_connections','无连接'],['below_four','少于四点'],['self_intersections','自交']],40)}</details><details><summary>三法共同底面 IoU 与 P10</summary>${grid(floor,[['difficulty','难度'],['method','方法'],['teams','共同队'],['images','图'],['iou_mean','底面IoU均值'],['iou_p10','P10']],40)}</details></section>
  <section class="panel"><h2>固定团队原图、全部原答与三法几何</h2>${choose('ms-fusion-team','实际团队',teams.map(r=>[r.request_id,`${r.image} · ${fmt(r.condition)} · n${r.n} · ${r.request_id}`]),s.team)}${team?`<p>图片 ${esc(team.image)}；参考 ${esc(team.reference_id)}；成员 ${esc(team.member_workers)}。原对象 ${esc(team.member_object_ids)}。</p><div id="ms-fusion-member"></div>${grid(displayedEndpoints,[['method','方法'],['output_status','输出'],['full_output','完整布局'],['floor_output','底面'],['B8L2','B8L2'],['D10','D10'],['iou_2d','底面IoU'],['missing_connection','无连接'],['below_four','少点']],3)}<p>Lee GeoJSON 的 Polygon/MultiPolygon 每条环线都显示；环线只表示底面边界，不补造顶界或填充语义。无连接仅显示实际保存点，不闭合为布局。</p><div id="ms-fusion-geom"></div>`:'该筛选没有团队。'}</section>`;
 slot.querySelectorAll('select[id^="ms-fusion-"]').forEach(el=>el.onchange=()=>{s[el.id.slice(10)]=el.value;if(el.id!=='ms-fusion-team')s.team='';fusion(slot,data,ctx).catch(error=>slot.textContent=error.message);});
 if(!team)return;
 const image=await ctx.imageDetail(team.image);if(!ctx.isCurrent()||!slot.isConnected||state.fusion.team!==team.request_id)return;
 const memberIds=team.member_object_ids.split('|'),members=memberIds.map(id=>image.annotations.find(a=>a.object_id===id));
 if(members.some(a=>!a))throw Error('融合成员对象缺失：'+team.request_id);
 if(!memberIds.includes(s.member))s.member=memberIds[0];
 const memberHost=slot.querySelector('#ms-fusion-member'),reference=image.references.find(r=>r.target_id===team.reference_id);
 if(!reference)throw Error('融合参考身份不一致：'+team.request_id);
 memberHost.innerHTML=choose('ms-fusion-member-select','查看完整个人作答',members.map(a=>[a.object_id,`${a.worker_id} · ${a.object_id}`]),s.member);
 const draw=()=>{
  s.member=memberHost.querySelector('select').value;
  const selected=image.annotations.find(a=>a.object_id===s.member);
  const layers=members.filter(a=>a!==selected).map((a,i)=>({id:'member'+i,label:`成员 ${a.worker_id} · 完整原答`,points:a.points,confirmed:!!a.points,visible:false,color:'#64748b'}));
  for(const {endpoint:e,geometry:g} of geometry){if(!g)throw Error('缺少保存几何：'+e.team_key+' '+e.method);
   if(e.method==='lee_mv50')geoRings(g.footprint).forEach((ring,i)=>layers.push({id:'lee'+i,label:`Lee 底面环 ${i+1}`,floor:ring,confirmed:false,visible:true,color:'#15803d'}));
   else layers.push({id:e.method,label:e.method==='medoid'?'代表原答完整布局':'墙线方法保存几何',points:g.points,floor:g.footprint,confirmed:e.full_output==='True',visible:true,color:e.method==='medoid'?'#d97706':'#dc2626'});
  }
  window.WorkbenchGeometry.mount(slot.querySelector('#ms-fusion-geom'),image,selected,reference,null,{layers});
 };
 memberHost.querySelector('select').onchange=draw;draw();
}
async function quality(slot,data,ctx){
 const q=data.quality,s=state.quality,pair=q.pairs.find(r=>r.review_id===s.case)||q.pairs[0];s.case=pair.review_id;
 const observations={
 QV001:['偏好方向与分差大小是两回事','右侧被判断为相对更好，但两份都存在问题；19.41分的B8L2差距不能直接解释为同等幅度的人工感知差异。'],
 QV002:['人工偏好与指标方向不一致','该Semi案例的记录选择为右侧较好，B8L2、D10和均高IoU却偏向左侧。保留这个反向结果，不能把Manual中的方向支持推广到所有条件。'],
 QV006:['漏掉转折与保留转折的区别','左侧用四角简化了门洞附近的凹入墙段；右侧六角保留了这处转折，记录判断为右侧较好。右侧仍有局部定位误差，保留转折不代表整份标注正确。'],
 QV007:['简化结构与细节位置错误可以并存','左侧四角省略隔断，右侧八角保留隔断，但墙端位置和上下边界关系仍有问题。当前参考包含隔断；不能只凭转折更多判定整体更好。'],
 QV011:['点数相同，局部表达仍不同','两份均为12角，参考为16角；各有局部优势，但都没有完整表达凹入结构。应查看实际墙段，而不只比较点数。'],
 QV013:['不同指标可能给出相反排序','B8L2与D10偏向记录选择的右侧，均高IoU与布局深度RMSE偏向左侧。这说明不同指标衡量的信息及取舍并不相同。'],
 QV015:['相同六角不代表相同几何','两份与参考均为六角，但远端底点、长边方向和上下点对关系不同。结构数量相同，位置与局部高度仍需分别检查。'],
 QV016:['分数差与感知差','记录判断为两者接近，B8L2却相差约11.21分。方向对照不能替代总分差距的严重程度校准。'],
 QV018:['先区分标注对象，再比较精度','左侧八角沿壁炉凸出部分表达，右侧四角沿后方主墙表达，当前参考为四角。这里包含目标范围差异，不能仅用分数认定某一表达唯一正确。'],
 QV019:['分数接近，也可能两份都有明显缺陷','两份B8L2均约33.3分，均缺关键墙线并有斜向底边。近分不代表高质量。'],
 QV021:['近分也可以出现在较好标注中','本例两份B8L2约98.42与97.00，记录判断为接近。与QV019对照，分数接近和质量水平是两个问题。']
 };
 const observation=observations[pair.review_id];
 const controlTitles={HEIGHT_CONTROL_METRICS:'高度变化控制',BOTTOM_POINT_CONTROL_METRICS:'底点偏移控制',EXPOSED_STRUCTURE_AND_NEAR_SCORE_METRICS:'既有结构与近分案例对照'};
 const metrics=[['B8L2','B8L2'],['D10','D10'],['IoU3D100','均高棱柱IoU'],['legacy_iou3d_mean_height','旧均高IoU'],['layout_depth_rmse_m','布局深度RMSE（米）'],['layout_depth_delta1','布局深度δ1'],['iou_2d','底面IoU'],['S_bottom_deg','底边角距'],['Hmean','均高误差'],['Hcenter','局部高度误差']];
 const metricRows=metrics.map(([id,label])=>({label,left:pair['left_'+id],right:pair['right_'+id],preferred:pair['preferred_'+id],agrees:pair['agrees_human_'+id]}));
 const related=q.directions.filter(r=>r.condition===pair.condition&&r.exposure_group===pair.exposure_group);
 slot.innerHTML=`<section class="panel"><h2>质量指标能识别哪些差异？</h2><p>这部分检验评分能否反映实际的结构、位置与高度缺陷，并对照人工相对判断。它为质量方法提供证据，帮助解释后续人员研究中的分数变化。</p><div class="split equal"><div class="info"><strong>主要发现：不同指标保留的信息不同</strong><p>漏转折、局部高度和墙段定位需要分别查看；均高棱柱IoU不能独自概括所有局部差异。布局深度也能响应部分高度变化 ${ctx.hintButton('layout_depth')}。</p></div><div class="info"><strong>方向得到部分支持，分差仍需解释</strong><p>新批Manual的5项明确偏好中，B8L2与D10均有5项同向，均高IoU有3项；Semi的1项明确偏好与这些指标反向。人工判断接近的案例，也可能有较大总分差。</p></div></div><p class="scope-label">支持范围：25对、25图、15栋建筑，由一名复核者判断；其中20对新批候选、5对既有机制案例。按指标关系选取的诊断案例，不是随机样本准确率。所有案例与控制结果均保留在下方。</p></section>
 <section class="panel"><h2>具体差异：原图、完整标注与指标一起看</h2>${choose('ms-quality-case','全部25组对照',q.pairs.map(r=>[r.review_id,`${r.review_id} · ${observations[r.review_id]?.[0]||r.image} · ${fmt(r.condition)}`]),s.case)}<h3>${esc(observation?.[0]||'同图两份标注的质量对照')}</h3>${observation?`<p>${esc(observation[1])}</p>`:''}<p>图片 ${esc(pair.image)} · ${esc(fmt(pair.condition))} · 已记录的人工相对判断：<strong>${esc(fmt(pair.human_choice))}</strong>。这项选择用于方向对照，不代表两份标注的绝对质量。</p><div class="split equal"><div><h3>左：完整标注与参考</h3><div id="ms-quality-left"></div></div><div><h3>右：完整标注与参考</h3><div id="ms-quality-right"></div></div></div></section>
 <section class="panel"><h2>同一对几何的多指标对照</h2><p>综合分B8L2 ${ctx.hintButton('q_b8l2')}、对照分D10 ${ctx.hintButton('q_d10')}和IoU重合度越高，表示按该指标更接近参考；角距、高度误差及深度RMSE越小越好。深度δ1表示误差落在规定比例内的像素占比，越高越好。不同指标的单位和数值不能直接互相比较。</p>${window.MethodDiagrams?.comparison(pair)||''}${grid(metricRows,[['label','指标'],['left','左'],['right','右'],['preferred','指标偏向'],['agrees','与人工明确方向一致']],20)}<details><summary>同条件/暴露组的方向支持</summary>${grid(related,[['metric','指标'],['received_pairs','题'],['directional_pairs','明确方向'],['same_direction','同向'],['opposite_direction','反向'],['close_answers','接近'],['uncertain_answers','不确定']],30)}</details></section>
 <section class="panel"><h2>高度、底点与近分结构控制</h2><p>控制实验分别改变几何因素，查看各指标如何响应。全部保存结果可展开查看；缺失值保持缺失。</p>${Object.entries(q.controls).map(([name,rows])=>`<details><summary>${esc(controlTitles[name]||name)} · ${rows.length} 行</summary>${grid(rows,Object.keys(rows[0]||{}).map(k=>[k,k]),30)}${source(`research/quality/quality_independent_validation_20261024/${name}.csv`,'完整控制表')}</details>`).join('')}</section>
 <section class="panel"><details><summary>方法、来源与当前案例身份</summary><p>新批候选排除了已登记的既有案例，但未认证从未被看过。仅“左更好／右更好”纳入明确方向计数，“两者接近”和“各有问题或无法判断”分别保留。辅助视觉说明不计为第二名独立判断者；方向支持也不代表总分权重已得到全面校准。</p><p>当前案例：${esc(pair.review_id)}；${esc(fmt(pair.exposure_group))}。参考：${esc(pair.reference_id)}；左：${esc(pair.left_object_id)}；右：${esc(pair.right_object_id)}。</p><p>${source('research/quality/quality_independent_validation_20261024/human_review/REPORT_ZH.md','方法说明与原始复核档案')} · ${source('research/quality/quality_independent_validation_20261024/README.md','质量验证完整研究')}</p></details></section>`;
 slot.querySelector('#ms-quality-case').onchange=e=>{s.case=e.target.value;quality(slot,data,ctx).catch(error=>slot.textContent=error.message);};
 const image=await ctx.imageDetail(pair.image);if(!ctx.isCurrent()||!slot.isConnected||state.quality.case!==pair.review_id)return;
 const ref=image.references.find(r=>r.target_id===pair.reference_id),left=image.annotations.find(a=>a.object_id===pair.left_object_id),right=image.annotations.find(a=>a.object_id===pair.right_object_id);
 if(!ref||!left||!right)throw Error('人工题目原答/参考身份不一致：'+pair.review_id);
 window.WorkbenchGeometry.mount(slot.querySelector('#ms-quality-left'),image,left,ref);
 window.WorkbenchGeometry.mount(slot.querySelector('#ms-quality-right'),image,right,ref);
}
async function render(slot,ctx){
 if(ctx.release!=='v2'){slot.textContent='方法补充仅接入 v2；请切换数据版本。';return;}
 const data=await requireData(ctx);if(!ctx.isCurrent())return;
 if(ctx.tab===0)personnel(slot,data,ctx);
 else if(ctx.tab===1)await fusion(slot,data,ctx);
 else await quality(slot,data,ctx);
}
return {render,geoRings};
})();
