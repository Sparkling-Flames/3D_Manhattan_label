/* Saved precision results only; marginal estimates never become an invented entry path. */
window.PopulationPrecision=(()=>{
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const present=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const fmt=v=>present(v)?Number(v).toLocaleString('zh-CN',{maximumFractionDigits:3}):'缺失';
const id=k=>'population_precision__'+k;
const versions={hybrid256:'主展示：256＋精确边际',pooled256:'合256纯路径',new208:'独立新208',stage1_104:'独立A104',stage2_104:'独立B104',old48:'旧48',prior96:'旧重点96（53池敏感性）',all_history304:'重点304（53池敏感性）',old24:'历史原24',new24:'历史新24'};
const layers={ordinary_manual:'普通 Manual',doorway_manual:'门洞 Manual（单列）'};
const metrics={Q_mean:'平均Q · 分',Q_p10:'P10 · 分',Q_sd_display:'Q分散程度SD · 分',V_floor:'底面几何波动V',D10_mean:'D10 · 分',actual_consensus_failure_rate:'实际共识失败率 · 比例',output_unscoreable_rate:'输出不可评分率 · 比例',reference_unavailable_rate:'参考不可用率 · 比例',not_executed_rate:'未执行率 · 比例'};
const policies={joint_highq_first:'历史高Q类优先',structure_moreturn_first:'历史较多转折类优先',joint_fast_first:'历史快速类优先',structure_dominant_first:'历史人数最多结构类优先'};
const phases={early_3_to_half:'前段：3至floor(N/2)',low_3_to_6:'低人数：3至6',late_20_to_Nminus1:'后段：20至缺一人',full:'实际满员'};
const batches={pooled32:'合32配对基础顺序',new16:'独立新16',old16:'旧16（按共同k）'};
const policyMetrics={paired_Q_delta:'配对Q差 · 分',paired_D10_delta:'配对D10差 · 分',actual_consensus_failure_delta:'实际共识失败率差 · 百分点',output_generated_unscorable_delta:'输出不可评分率差 · 百分点',failure_delta:'旧宽口径不可评率差 · 百分点',labor_ratio_legal:'同域记录劳动比',QT_paired_Q_delta:'共同Q/T内Q差 · 分',Q_p10_delta_common:'配对支持P10差 · 分',Q_sd_delta_common_ddof1:'配对支持SD差 · 分'};
const select=(key,title,choices,value)=>`<label>${esc(title)}<select data-precision="${key}">${choices.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;
const opts=x=>Object.entries(x);
const table=(rows,columns)=>`<div class="tablewrap"><table><thead><tr>${columns.map(([,t])=>`<th>${esc(t)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(([key])=>`<td>${esc(typeof key==='function'?key(r):r[key]??'缺失')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const ncol=(k,t)=>[r=>fmt(r[k]),t];
function estimator(row){return row.estimator==='exact_finite_uniform_marginal'?'精确有限边际':row.estimator==='contract_deferred_k2'?'两人延期：未运行':'随机256前缀';}
function fixedRows(rows,s){
 const out=rows.filter(r=>r.panel===s.panel&&r.layer===s.layer&&r.difficulty===s.difficulty&&r.metric===s.metric&&r.weighting==='image_equal').sort((a,b)=>a.k-b.k);
 // A missing deferred stage is a gap, never a zero or a joined path segment.
 return out.length&&!out.some(r=>r.k===2)?[...out,{k:2,deferred:true}].sort((a,b)=>a.k-b.k):out;
}
function individualRows(data,s){
 const rows=s.version==='hybrid256'?data.hybrid_images:s.version==='old24'||s.version==='new24'?data.legacy_batches:data.batch_images;
 return rows.filter(r=>r.image===s.image&&(s.version==='hybrid256'||(r.cohort??r.version)===s.version)).sort((a,b)=>a.k-b.k);
}
function hybridSummary(data,s){
 const n=Number(s.panel.split('_').at(-1));
 const rows=data.hybrid_images.filter(r=>r.layer===s.layer&&r.pool_n>=n&&(s.difficulty==='全部'||r.difficulty===s.difficulty)&&r.k<=n&&r.k!==2);
 const groups=Map.groupBy?Map.groupBy(rows,r=>r.image):rows.reduce((m,r)=>(m.has(r.image)||m.set(r.image,[]),m.get(r.image).push(r),m),new Map());
 const eligible=[...groups].filter(([,rr])=>rr.length===n-1&&rr.every(r=>present(r[s.metric]))).map(([im])=>im);
 const selected=rows.filter(r=>eligible.includes(r.image));
 const points=Array.from({length:n},(_,i)=>i+1).map(k=>{
  if(k===2)return {k,deferred:true};
  const rr=selected.filter(r=>r.k===k),exact=rr.filter(r=>r.estimator==='exact_finite_uniform_marginal').length;
  return {k,estimate:rr.length?rr.reduce((v,r)=>v+Number(r[s.metric]),0)/rr.length:null,images:rr.length,capacity_images:groups.size,buildings:new Set(rr.map(r=>r.building)).size,exact_images:exact,random_images:rr.length-exact};
 });
 return points;
}
function pointPlot(rows){
 const usable=rows.filter(r=>present(r.estimate));if(!usable.length)return '<p>所选范围没有保存的可用数值；不补零。</p>';
 const values=usable.map(r=>Number(r.estimate)),low=Math.min(...values),high=Math.max(...values),maxK=Math.max(...usable.map(r=>r.k));
 return `<figure class="chart"><svg viewBox="0 0 760 220" role="img" aria-label="固定图片范围的逐人数边际估计，散点不代表实际路径"><path d="M45 15V180H730" fill="none" stroke="#94a3b8"/>${usable.map(r=>{const x=45+r.k/maxK*675,y=180-(r.estimate-low)/(high-low||1)*145;return `<circle cx="${x}" cy="${y}" r="4" fill="${r.exact_images===r.images?'#b45309':'#087f8c'}"><title>k=${r.k}，${fmt(r.estimate)}；${r.images}/${r.capacity_images??r.candidate_images}图，${r.buildings??r.common_buildings}楼；精确${r.exact_images??'不适用'}</title></circle>${[1,3,6,10,20,30,35,maxK].includes(r.k)?`<text x="${x}" y="202" text-anchor="middle">${r.k}</text>`:''}`;}).join('')}<text x="45" y="12">${fmt(high)}</text><text x="45" y="176">${fmt(low)}</text></svg><figcaption>固定图片、图等权的边际散点；精确目录点为橙色，含随机估计为绿色。两人延期保留缺口；不拼造实际路径，不加置信带。</figcaption></figure>`;
}
const titles={hybrid_images:'256＋精确逐图边际',batch_images:'纯路径各批次',fixed_curves:'固定图片纯路径与范围',paired_intervals:'逐图同路径区间差',interval_summary:'人数区间汇总与支持',precision:'逐人数精度',geometry_fixed:'全程固定图片几何V',geometry_images:'逐图各批次几何V',policy_summary:'32策略汇总与重抽',policy_images:'32策略逐图阶段',policy_support:'策略固定共同k'};
function jumpTables(keys){return `<details><summary>全部保存表与CSV导出入口</summary><div class="actions">${keys.map(k=>`<button data-table-jump="population256__${k}">${esc(titles[k])}</button>`).join('')}</div></details>`;}
async function load(keys,ctx){
 const display={batch_images:'batch_display',geometry_images:'geometry_floor_images',geometry_fixed:'geometry_floor_fixed',policy_support:'policy_q_support'};
 const rows=await Promise.all(keys.map(k=>ctx.table('population256__'+(display[k]||k))));return Object.fromEntries(keys.map((k,i)=>[k,rows[i]]));
}
function savedFigures(mode){
 const root='../../../research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/';
 const specs=mode==='policy'?[
 ['report26/figures/P02_policy32_Q_labor_support','历史四策略32：157图Q与各自共同Q/T支持','_SOURCE.csv'],
 ]:[
 ['analysis_precision26/figures_stage2/F01_固定157全曲线_独立追加','固定N≥30的157候选图：各批纯路径曲线；图内全程支持按指标声明',null],
 ['analysis_precision26/figures_stage2/F03_35人与门洞曲线','N≥35与门洞单列：纯路径结果与不同指标支持',null],
 ['analysis_precision26/figures_stage2/N05_单图完整人数曲线','逐图低人数至实际满员；精确点与纯路径分开',null],
 ['analysis_geometry26/figures/F01_GEOMETRY_FULL_CURVE_AND_PRECISION','底面几何V：全程固定图片，纯路径估计',null],
 ['analysis_geometry26/low_k_cases/yqstnuAEVhm-31__manual__7b26e5d3cd__k5/CASE_CURVE_Q_RAW_FUSION_BEV','yqst-31：新208条保存的低人数分布、原答与融合几何',null],
 ];
 return `<details class="population-figures"><summary>新版${mode==='policy'?'32策略':'256自然与几何'}研究图版（固定图，不随上方筛选改变）</summary>${specs.map(([path,title,csv])=>`<figure><a href="${esc(root+path+'.png')}" target="_blank" rel="noopener"><img class="briefing-visual" loading="lazy" src="${esc(root+path+'.png')}" alt="${esc(title)}"></a><figcaption>${esc(title)} · <a href="${esc(root+path+'.pdf')}" target="_blank" rel="noopener">矢量PDF</a>${csv?` · <a href="${esc(root+path+csv)}" download>绘图CSV</a>`:''}</figcaption></figure>`).join('')}</details>`;
}
function natural(data,ctx){
 const s={layer:'ordinary_manual',panel:'fixed_N_ge_30',difficulty:'全部',metric:'Q_mean',version:'hybrid256',image:'',interval:'3_to_6',compareK:'6'};
 const draw=host=>{
  const diffs=[...new Set(data.hybrid_images.filter(r=>r.layer===s.layer).map(r=>r.difficulty))];if(!diffs.includes(s.difficulty)&&s.difficulty!=='全部')s.difficulty='全部';
  const codes=[...new Set(data.hybrid_images.filter(r=>r.layer===s.layer&&r.pool_n>=Number(s.panel.split('_').at(-1))&&(s.difficulty==='全部'||r.difficulty===s.difficulty)).map(r=>r.image))];if(!codes.includes(s.image))s.image=codes[0]||'';
  const summary=s.metric==='V_floor'?data.geometry_fixed.filter(r=>r.layer===s.layer&&r.panel===s.panel&&r.difficulty===s.difficulty&&r.metric==='V_floor'&&r.cohort==='pooled256'&&r.weighting==='image_equal').map(r=>({...r,images:r.common_images,buildings:r.common_buildings,capacity_images:r.candidate_images})):hybridSummary(data,s);
  const individual=individualRows(data,s),allK=[...new Set(data.hybrid_images.filter(r=>r.image===s.image).map(r=>r.k))].sort((a,b)=>a-b);if(!allK.includes(Number(s.compareK)))s.compareK=String(allK[0]||1);
  const comparison=Object.keys(versions).flatMap(version=>individualRows(data,{...s,version}).filter(r=>r.k===Number(s.compareK)).map(r=>({...r,shownVersion:version})));
  const cohort=s.version==='hybrid256'?'pooled256':s.version;
  const paired=data.paired_intervals.filter(r=>r.image===s.image&&r.cohort===cohort&&r.interval===s.interval);
  const intervals=[...new Set(data.paired_intervals.map(r=>r.interval))];
  const imageMeta=ctx.assets?.images.find(i=>i.image_code===s.image);
  const geometry=data.geometry_images.filter(r=>r.image===s.image&&r.cohort===cohort&&r.metric==='V_floor');
  const prec=data.precision.filter(r=>r.layer===s.layer&&r.panel===s.panel&&r.difficulty===s.difficulty&&r.cohort===cohort);
  const sourceLabel=r=>r.shownVersion==='hybrid256'?estimator(r)+' / '+(r.exact_kind||'纯路径'):versions[r.shownVersion];
  const displayCols=[[r=>`${r.k}${r.k===r.pool_n?' · 实际满员':r.k===r.pool_n-1?' · 缺一人':''}`,'人数k'],[sourceLabel,'版本 / 估计来源'],ncol('Q_mean','Q'),ncol('Q_p10','linear P10'),[r=>fmt(r.Q_sd_display??r.Q_sd_population_estimate??r.Q_sd_ddof1),'SD（按来源定义）'],ncol('actual_consensus_failure_rate','实际共识失败率'),ncol('output_unscoreable_rate','输出不可评分率'),ncol('reference_unavailable_rate','参考不可用率'),ncol('not_executed_rate','未执行率'),[r=>r.k===2?'规则延期：未运行':fmt(r.quality_valid_units??r.quality_valid_paths),'可评单位 / 延期'],ncol('paths_attempted','路径次数'),ncol('unique_teams','不同团队'),[r=>fmt(r.Q_mean_MCSE??r.Q_mean_MCSE_analytic),'均值MCSE']];
  host.innerHTML=`<p class="eyebrow">自然人数 · 256路径与精确有限边际 · 2026-10-27</p><h2>平均质量、低尾、成员选择波动与实际失败分别看</h2><p>困难27图3→6人：平均Q +6.107，26图升；实际失败率平均+4.326个百分点。20→30人：Q −0.175，P10 +4.246（24/27升）、SD −4.676（25/27降）、底面V −0.047685（26/27降）。后段平均Q变化较小，同时低尾与成员选择稳定性改善。保存的Q路径重抽范围为[−0.467,+0.110]，建筑范围为[−2.340,+2.381]，两者支持不同解释。</p><p>门洞6→10人：Q −1.006，12/17图降；实际失败率−13.534个百分点，17图全降。20→30人：Q在共同可评15图平均−1.729，但8升7降；实际失败率在16个有容量池平均+9.131个百分点。满员普通177图有1图实际失败，门洞17图有6图失败。均值方向、支持图数和失败事件不互换。</p><p class="scope-label">主展示为旧48＋独立新208＝256；A104/B104分别保留。53重点池的96/304仅作敏感性。Semi沿用原版。R是顺序条数，k是团队人数，N是池容量。</p><div class="toolbar">${select('layer','采集层',opts(layers),s.layer)}${select('panel','固定容量范围',[6,10,20,27,30,35].map(n=>['fixed_N_ge_'+n,'固定N≥'+n+'，展示至k'+n]),s.panel)}${select('difficulty','冻结难度',['全部',...diffs.filter(x=>x!=='全部')].map(x=>[x,x]),s.difficulty)}${select('metric','指标',opts(metrics),s.metric)}</div>${pointPlot(summary)}${table(summary,[[r=>r.deferred?'2 · 延期':r.k,'人数k'],[r=>r.deferred?'未运行':fmt(r.estimate),'图等权边际'],[r=>r.deferred?'不适用':`${r.images}/${r.capacity_images}`,'全程可用/容量候选图'],ncol('buildings','楼'),[r=>r.deferred||s.metric==='V_floor'?'不适用':`${r.exact_images}/${r.random_images}`,'精确/随机256图']])}<p>Q/P10/SD每项使用同一容量范围内、每个合法k均可评的固定图片；不同指标支持可能不同。实际失败用全部实际执行的非延期支持；输出不可评、参考缺口、未执行和延期独立保留。几何V读取保存的全程共同图片表，未用精确Q边际替代V。空白为不可估，不填0。</p>
  <h3>逐图：低人数、30、35与实际满员</h3><div class="toolbar">${select('image','图片',codes.map(x=>[x,x]),s.image)}${select('version','估计版本',opts(versions),s.version)}</div><p>单人、缺一人、满员及已穷尽小池优先使用已知精确均匀团队目录；其余主展示使用256路径。精确SD为总体ddof0，随机SD为样本ddof1；同一精确点仍保留纯路径的出现次数。linear P10与逆CDF P10各自保留。满员换组SD/V为0源于唯一团队，不能推出Q正确。</p>${table(individual.map(r=>({...r,shownVersion:s.version})),displayCols)}${imageMeta?`<a href="#release=v2&module=images&image=${esc(imageMeta.image_id)}">查看原图与全部完整个人标注</a>`:''}<div class="actions"><button data-module="case_story">查看已保存团队端点与融合几何</button></div>
  <details><summary>同图各人数的底面几何波动V（纯路径版本）</summary>${table(geometry,[ncol('k','人数k'),ncol('mean','V_floor'),ncol('mcse','V的MCSE'),ncol('valid_paths','有效路径'),ncol('valid_pairs','有效两两比较'),['metric_status','保存状态']])}</details>
  <h3>同图同人数：独立批次与历史敏感性</h3><div class="toolbar">${select('compareK','比较人数',allK.map(k=>[String(k),String(k)]),s.compareK)}</div>${table(comparison,displayCols)}<p>新208独立于旧48；A/B各104是新208的两半。重点96/304只有53池，没有该版本则不造行。原24/新24保留历史定义；当时未拆分的状态显示缺失，不能解释为零失败。</p>
  <details><summary>所选纯路径版本的逐人数精度</summary>${table(prec,[ncol('k','k'),ncol('images','图片'),ncol('mean_mcse_median','单图均值MCSE中位数'),ncol('mean_mcse_gt1_images','均值MCSE>1分图'),ncol('P10_boot_halfwidth_gt2_images','linear P10区间半宽>2分图'),ncol('P10_rank_halfwidth_median','逆CDF秩区间半宽中位数')])}<p>固定157图的k3，均值MCSE>1分由旧48的122图降至合256的20图；P10经验半宽>2分由137降至76。阈值是工作精度目标；精度改善不等于真实波动变小。</p></details>
  <h3>同路径人数差：使用纯路径配对，不拼接精确点</h3><div class="toolbar">${select('interval','区间',intervals.map(x=>[x,x.replaceAll('_to_','→')]),s.interval)}</div><p>当前${esc(versions[s.version])}。历史24条的配对结果仍见旧保存表；新版缺版本时保持空表。边际Q差与同路径两端共同可评Q差分别显示。</p>${table(paired,[['interval','区间'],ncol('marginal_Q_delta','边际Q差'),ncol('paired_Q_delta','共同可评路径Q差'),ncol('paired_Q_valid_paths','共同可评路径'),ncol('paths_attempted','全部路径'),ncol('actual_consensus_failure_delta','实际失败率差（比例）'),ncol('output_unscoreable_delta','输出不可评分率差')])}${wc2(data)}${jumpTables(['hybrid_images','batch_images','fixed_curves','paired_intervals','interval_summary','precision','geometry_fixed','geometry_images'])}`;
  host.querySelectorAll('[data-precision]').forEach(el=>el.onchange=()=>{s[el.dataset.precision]=el.value;draw(host);});
 };
 return {head:'<section class="panel" id="precisionNatural"></section>'+savedFigures('natural'),activate:slot=>draw(slot.querySelector('#precisionNatural'))};
}
function wc2(data){
 const image=data.wc2_teams[0]?.image_id;
 return `<section class="panel"><h3>wc2-46：见过全部团队，仍可能没估准低分频率</h3><p>28支缺一人队中4支低分。96路径已覆盖全部28队，却只出现7次低分；随机线性P10为97.387，精确目录线性P10为52.406。抽样频次与有限目录均匀权重是两种分布；另保留逆CDF定义，不事后更换口径。</p>${table(data.wc2_weights,[[r=>({exact_uniform_28_teams:'完整28队等权',old24:'原24',new24:'独立新24',combined48:'合48',combined96:'重点96',focus48:'追加重点48',independent_new72:'独立新72'})[r.sample]||r.sample,'版本'],ncol('observations','记录/队数'),ncol('unique_teams','不同团队'),ncol('low_peak_observations','低分次数'),ncol('P10_linear','线性P10'),ncol('P10_inverseCDF','逆CDF P10')])}<details><summary>28支确定团队与实际缺席成员</summary>${table(data.wc2_teams,[['absent_worker','缺席成员'],ncol('B8L2','Q'),['score_peak','描述性分组'],ncol('combined48_path_count','合48频数'),ncol('combined96_path_count','合96频数'),ncol('finite_uniform_weight','有限目录权重')])}</details><a href="#release=v2&module=images&image=${esc(image)}">查看wc2-46原图与全部完整个人标注</a><p>VFua-04的35支缺一人团队有32支可评、3支失败；满员只有3节点。三份保存状态的逐身份票账保留在明细表中，只解释该例，不推广为所有图片的机制。</p><details><summary>VFua-04三个缺一人团队的身份票账</summary><p>三队均34人、门槛17票。缺W103时两组17/16票，缺W113时16/17票，缺W134时16/16票；原身份与是否入选分别保存，不重算或补连线。</p>${table(data.vfua_votes,[['absent_worker','缺席成员'],['feature_id','保存身份'],ncol('support','支持票'),[r=>r.selected?'入选':'未入选','结果']])}<figure><img class="briefing-visual" loading="lazy" src="../../../research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/analysis_geometry/case_VFua_04/VFUA_LEAVE_ONE_OUT_BEV.png" alt="VFua-04三个保存缺一人团队的底面与选中节点"><figcaption>保存案例几何；该例不能代表所有图的加人机制。</figcaption></figure></details><a href="#release=v2&module=patterns&case=F_SAVED_VFuaQ6m2Qom-04&condition=manual">查看VFua-04满员失败几何与原答</a></section>`;
}
function policy(data){
 const s={batch:'pooled32',phase:'early_3_to_half',difficulty:'全部',metric:'paired_Q_delta',policy:'joint_highq_first'};
 const draw=host=>{
  const matching=(r,metric=s.metric)=>r.version===s.batch&&r.phase===s.phase&&r.difficulty===s.difficulty&&r.metric===metric&&r.weighting==='image_equal';
  const rows=data.policy_summary.filter(r=>matching(r)),joint=data.policy_summary.filter(r=>matching(r,'labor_ratio_legal'));
  const details=data.policy_images.filter(r=>r.version===s.batch&&r.phase===s.phase&&r.policy===s.policy&&(s.difficulty==='全部'||r.difficulty===s.difficulty));
  const pct=/failure|unscorable/.test(s.metric),value=(r,key)=>present(r[key])?fmt(r[key]*(pct?100:1)):'缺失';
  host.innerHTML=`<p class="eyebrow">历史进入策略 · 32条配对基础顺序 · 2026-10-27</p><h2>高Q、多转折、快速与人数最多结构类：分开看质量和劳动</h2><p>合32前段固定157图：高Q优先 +7.669分（151图升），多转折 +6.140（136图升），快速 −1.782（53图升），人数最多结构类 −1.940（31图升）。独立新16重复四个平均方向。沿用历史V3_BEHAVIOR／V3_JOINT_QT楼外角色，不是DSTRUCT/RFUSE策略验证。</p><p>前段为3至floor(N/2)，三版本固定共同k。策略157图与自然N≥30的157图仅148图交集。旧16按当前共同k收紧后，人数最多结构类为−1.947267，与历史−1.943602属于不同支持；没有改旧队伍分数。</p><div class="toolbar">${select('batch','配对批次',opts(batches),s.batch)}${select('phase','阶段',opts(phases),s.phase)}${select('difficulty','难度',['全部','简单','中等','困难'].map(x=>[x,x]),s.difficulty)}${select('metric','指标',opts(policyMetrics),s.metric)}</div>${table(rows,[[r=>policies[r.policy],'历史角色'],[r=>value(r,'estimate'),'图等权策略−自然 / 劳动比'],[r=>`${r.images}/${r.candidate_images}图 / ${r.buildings}楼`,'支持'],[r=>`${r.positive_images}/${r.negative_images}/${r.nearzero_images}`,'正/负/零（相对0）'],[r=>`[${value(r,'path_lo')}, ${value(r,'path_hi')}]`,'路径条件经验范围'],[r=>`${r.path_valid_replicates}/${r.bootstrap_replicates}；不可估${r.path_invalid_replicates}`,'可估重抽/总数'],[r=>`[${value(r,'building_lo')}, ${value(r,'building_hi')}]`,'建筑重抽范围']])}<p>合32前段Q的有效路径重抽依次为2000/1998/1976/1999（各请求2000）。不可估保留，不按剩余图重分权；失败百分比用全部实际尝试。劳动比的正/负计号是原表相对0，不能用来判断费时／节时，必须与1比较。</p>
  <h3>记录劳动：各策略自己的共同Q/T支持</h3>${table(joint,[[r=>policies[r.policy],'策略'],ncol('images','共同Q/T图'),ncol('buildings','楼'),ncol('estimate','合法配对劳动比（策略/自然）'),[r=>fmt(data.policy_summary.find(q=>matching(q,'QT_paired_Q_delta')&&q.policy===r.policy)?.estimate),'同支持Q差'],[r=>`${r.path_valid_replicates}/${r.bootstrap_replicates}`,'可估路径重抽']])}<p>合32前段共同Q/T支持为115/94/72/117图。快速类72图平均劳动比0.786092，同支持Q差−0.969；72图均节时，30图同时升质。其它策略的157图Q差不能与这些劳动比拼成同域收益。劳动比是逐合法配对路径的活动时间比的均值，不是总费用比或实际交付时间。旧67图/18楼共同时间结果继续保留原8路径身份。</p>
  <details><summary>逐图质量、劳动与固定共同k</summary><div class="toolbar">${select('policy','历史角色',opts(policies),s.policy)}</div>${table(details,[['image','图片'],ncol('pool_n','N'),ncol('base_paths','基础路径'),ncol('paired_Q_delta','共同Q差'),ncol('actual_consensus_failure_delta','实际失败率差（比例）'),ncol('output_generated_unscorable_delta','输出不可评率差'),ncol('labor_ratio_legal','劳动比'),ncol('QT_paired_Q_delta','共同Q/T的Q差')])}${table(data.policy_support.filter(r=>r.version===s.batch&&r.phase===s.phase&&r.policy===s.policy&&r.metric==='paired_Q_delta'),[['image','图片'],ncol('matched_k','共同k数'),['matched_k_list','实际k'],ncol('lost_k','收紧k数')])}</details>${jumpTables(['policy_summary','policy_images','policy_support'])}`;
  host.querySelectorAll('[data-precision]').forEach(el=>el.onchange=()=>{s[el.dataset.precision]=el.value;draw(host);});
 };
 return {head:'<section class="panel" id="precisionPolicy"></section>'+savedFigures('policy'),activate:slot=>draw(slot.querySelector('#precisionPolicy'))};
}
async function create(mode,ctx){
 const keys=mode==='policy'?['policy_summary','policy_images','policy_support']:['hybrid_images','batch_images','paired_intervals','precision','geometry_fixed','geometry_images'];
 const data=await load(keys,ctx);
 if(mode!=='policy'){
  const legacy=await Promise.all(['batch_images','wc2_weights','wc2_teams','vfua_votes'].map(k=>ctx.table(id(k))));
  Object.assign(data,{legacy_batches:legacy[0],wc2_weights:legacy[1],wc2_teams:legacy[2],vfua_votes:legacy[3]});
 }
 if(!ctx.isCurrent())return {head:'',activate:()=>{}};
 return mode==='policy'?policy(data):natural(data,ctx);
}
return {create,fixedRows,individualRows,hybridSummary,estimator,present};
})();
