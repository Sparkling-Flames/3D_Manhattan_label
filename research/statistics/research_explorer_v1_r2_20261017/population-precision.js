/* Saved precision results only; marginal estimates never become an invented entry path. */
window.PopulationPrecision=(()=>{
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const present=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const fmt=v=>present(v)?Number(v).toLocaleString('zh-CN',{maximumFractionDigits:3}):'缺失';
const id=k=>'population_precision__'+k;
const versions={hybrid48:'主展示：随机48＋精确边际',old24:'原24条',new24:'独立新24条',pooled48:'合并48条',focus96:'重点池96条'};
const layers={ordinary_manual:'普通 Manual',doorway_manual:'门洞 Manual（单列）'};
const metrics={Q_mean:'平均Q · 分',Q_p10:'P10 · 分',Q_sd_population_estimate:'Q总体SD估计 · 分',D10_mean:'D10 · 分',failure_rate:'失败率 · 比例',incomplete_rate:'不完整率 · 比例'};
const policies={joint_highq_first:'历史高Q类优先',structure_moreturn_first:'历史较多转折类优先',joint_fast_first:'历史快速类优先',structure_dominant_first:'历史人数最多结构类优先'};
const phases={early_3_to_half:'前段：3至floor(N/2)',low_3_to_6:'低人数：3至6',late_20_to_Nminus1:'后段：20至缺一人',full:'实际满员'};
const batches={old8:'原8条配对基础路径',new8:'独立新8条',combined16:'合并16条'};
const policyMetrics={paired_Q_delta:'配对Q差 · 分',paired_D10_delta:'配对D10差 · 分',failure_delta:'失败率差 · 百分点',labor_ratio_legal:'同域记录劳动比',QT_paired_Q_delta:'共同Q/T内Q差 · 分',Q_p10_delta_common:'配对支持P10差 · 分',Q_sd_delta_common_ddof1:'配对支持SD差 · 分'};
const select=(key,title,choices,value)=>`<label>${esc(title)}<select data-precision="${key}">${choices.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;
const opts=x=>Object.entries(x);
const table=(rows,columns)=>`<div class="tablewrap"><table><thead><tr>${columns.map(([,t])=>`<th>${esc(t)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(([key])=>`<td>${esc(typeof key==='function'?key(r):r[key]??'缺失')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const ncol=(k,t)=>[r=>fmt(r[k]),t];
function estimator(row){return row.estimator==='exact_finite_uniform_marginal'?'精确有限边际':row.estimator==='contract_deferred_k2'?'两人延期：未运行':'随机48前缀';}
function fixedRows(rows,s){
 const out=rows.filter(r=>r.panel===s.panel&&r.layer===s.layer&&r.difficulty===s.difficulty&&r.metric===s.metric&&r.weighting==='image_equal').sort((a,b)=>a.k-b.k);
 // A missing deferred stage is a gap, never a zero or a joined path segment.
 return out.length&&!out.some(r=>r.k===2)?[...out,{k:2,deferred:true}].sort((a,b)=>a.k-b.k):out;
}
function individualRows(data,s){
 const rows=(s.version==='hybrid48'?data.hybrid_images:data.batch_images).filter(r=>r.image===s.image&&(s.version==='hybrid48'||r.version===s.version));
 return rows.sort((a,b)=>a.k-b.k);
}
function pointPlot(rows){
 const usable=rows.filter(r=>present(r.estimate)),values=usable.map(r=>Number(r.estimate));
 if(!values.length)return '<p>所选范围没有保存的可用数值。</p>';
 const low=Math.min(...values),high=Math.max(...values),maxK=Math.max(...usable.map(r=>r.k));
 return `<figure class="chart"><svg viewBox="0 0 760 220" role="img" aria-label="固定图片范围的逐人数边际估计，散点不代表实际路径"><path d="M45 15V180H730" fill="none" stroke="#94a3b8"/>${usable.map(r=>{const x=45+r.k/maxK*675,y=180-(r.estimate-low)/(high-low||1)*145;return `<circle cx="${x}" cy="${y}" r="5" fill="${r.exact_images===r.observed_images?'#b45309':'#087f8c'}"><title>k=${r.k}，${fmt(r.estimate)}；精确${r.exact_images}图/随机48 ${r.random48_images}图；有效${r.observed_images}/${r.available_images}图</title></circle><text x="${x}" y="202" text-anchor="middle">${r.k}</text>`;}).join('')}<text x="45" y="12">${fmt(high)}</text><text x="45" y="176">${fmt(low)}</text></svg><figcaption>逐点边际估计：橙色为全部采用精确目录的点，绿色包含随机48；两人保留缺口。这里没有拼接实际进入路径，也没有置信带。</figcaption></figure>`;
}
const titles={hybrid_images:'逐图混合边际',hybrid_fixed:'固定图片人数曲线',batch_images:'四批次逐图结果',precision:'逐人数抽样精度',batch_differences:'新旧批次共同支持对照',paired_intervals:'同路径前后对照',exact:'完整有限边际',geometry_fixed:'固定157图几何V',vfua_votes:'VFua逐身份票账',policy_key:'前段Q修正结果',policy_summary:'策略固定支持与重抽',policy_images:'策略逐图阶段',wc2_weights:'wc2 低分频率',wc2_teams:'wc2全部缺一人团队'};
function jumpTables(keys){return `<details><summary>全部保存表与版本明细</summary><div class="actions">${keys.map(k=>`<button data-table-jump="${id(k)}">${esc(titles[k])}</button>`).join('')}</div></details>`;}
async function load(keys,ctx){const rows=await Promise.all(keys.map(k=>ctx.table(id(k))));return Object.fromEntries(keys.map((k,i)=>[k,rows[i]]));}
function natural(data,ctx){
 const s={layer:'ordinary_manual',panel:'fixed_N_ge_30',difficulty:'全部',metric:'Q_mean',version:'hybrid48',image:'',interval:'3_to_6',compareK:'6'};
 const draw=host=>{
  const availableDifficulties=[...new Set(data.hybrid_fixed.filter(r=>r.layer===s.layer).map(r=>r.difficulty))];if(!availableDifficulties.includes(s.difficulty))s.difficulty=availableDifficulties.includes('全部')?'全部':availableDifficulties[0];
  const images=data.hybrid_images.filter(r=>r.layer===s.layer&&r.pool_n>=Number(s.panel.split('_').at(-1))&&(s.difficulty==='全部'||r.difficulty===s.difficulty));
  const codes=[...new Set(images.map(r=>r.image))];if(!codes.includes(s.image))s.image=codes[0]||'';
  const summary=fixedRows(data.hybrid_fixed,s),individual=individualRows(data,s),selected=individual[0];
  const precision=data.precision.filter(r=>r.panel===s.panel&&r.layer===s.layer&&r.difficulty===s.difficulty&&(s.version==='hybrid48'?r.version==='pooled48':r.version===s.version));
  const paired=data.paired_intervals.filter(r=>r.image===s.image&&r.version===(s.version==='hybrid48'?'pooled48':s.version)&&r.interval===s.interval);
  const intervals=[...new Set(data.paired_intervals.map(r=>r.interval))];
  const allK=[...new Set(data.hybrid_images.filter(r=>r.image===s.image).map(r=>r.k))].sort((a,b)=>a-b);if(!allK.includes(Number(s.compareK)))s.compareK=String(allK[0]);
  const comparison=Object.keys(versions).flatMap(version=>individualRows(data,{...s,version}).filter(r=>r.k===Number(s.compareK)).map(r=>({...r,shownVersion:version})));
  const imageMeta=ctx.assets?.images.find(i=>i.image_code===s.image);
  host.innerHTML=`<p class="eyebrow">人数抽样精度补充 · 2026-10-25</p><h2>早段提高质量，困难图后段主要改善 P10 和成员选择的稳定性</h2><p>合48路径普通168图3→6：Q +5.346分，165升/3降；失败同时增加1.612个百分点。困难27图20→30：Q仅+0.016，P10 +4.153、SD −4.439，后二项各24/27图改善。困难20→30的Q路径重抽95%经验范围为[−0.623,+0.676]，P10为[+2.423,+6.098]、SD为[−5.000,−3.714]。平均Q差很小且方向不明确，不能说后段继续稳定升质，也不能据此证明精确为零。</p><p>固定157张N≥30普通图，合48四段几何V均22/22楼平均下降；独立新24在10→20为21/22。V描述成员选择的几何敏感性，不是对参考误差或Q的SD。门洞满员仍6/17失败。</p><div class="toolbar">${select('layer','采集层',opts(layers),s.layer)}${select('panel','固定最低人数',[6,10,20,30,35].map(n=>['fixed_N_ge_'+n,'N≥'+n]),s.panel)}${select('difficulty','人工难度',availableDifficulties.map(x=>[x,x]),s.difficulty)}${select('metric','指标',opts(metrics),s.metric)}</div>${pointPlot(summary)}${table(summary,[[r=>r.deferred?'2 · 延期':r.k,'人数k'],[r=>r.deferred?'未运行':fmt(r.estimate),'图等权保存值'],[r=>r.deferred?'不适用':`${r.observed_images}/${r.available_images}`,'有效/固定候选图'],[r=>r.deferred?'不适用':`${r.exact_images}/${r.random48_images}`,'精确/随机48图'],[r=>r.deferred?'不适用':fmt(r.MCSE_fixed_images_analytic),'固定图边际MCSE']])}<p class="scope-label">MCSE只描述固定图片下的边际抽样误差，不是建筑变化、人数差的误差或同时置信带。Q/P10/SD仅用可评结果，失败另用全部实际尝试；缺失不填0。</p>
  <h3>逐图：精确有限边际与四种路径版本分开看</h3><div class="toolbar">${select('image','图片',codes.map(x=>[x,x]),s.image)}${select('version','估计版本',opts(versions),s.version)}</div><p>主展示的单人、缺一人、满员及小池采用完整有限目录；普通点使用统一合48，不混入重点96。${s.version==='focus96'?'重点96只覆盖按旧规则选择的53个池，不外推到全库。':''}各版本SD保留原定义：随机表是样本SD(ddof1)，主展示是总体SD估计，精确目录为总体SD(ddof0)。</p>${individual.length?table(individual,[[r=>`${r.k}${r.k===r.pool_n?' · 满员':r.k===r.pool_n-1?' · 缺一人':''}`,'人数'],[r=>s.version==='hybrid48'?estimator(r):versions[s.version],'估计来源'],ncol('Q_mean','Q'),ncol('Q_p10','P10'),[r=>fmt(r.Q_sd_population_estimate??r.Q_sd_ddof1),'SD（按版本定义）'],ncol('failure_rate','失败率'),[r=>fmt(r.path_count??r.paths_attempted),'路径数'],ncol('unique_teams','不同团队'),[r=>fmt(r.Q_mean_MCSE??r.Q_mean_MCSE_analytic),'Q均值边际MCSE'],[r=>fmt(r.quality_valid_units??r.quality_valid_paths),'可评单位']]):'<p>该图没有此版本数据，保留缺失。</p>'}${imageMeta?`<a href="#release=v2&module=images&image=${esc(imageMeta.image_id)}">查看原图与完整个人标注</a>`:''}<p>满员各顺序回到同一支团队，精确MCSE和SD/V为0不代表Q正确。Semi没有本轮追加路径，下面保留原次要结果。</p>
  <h3>同图同人数：五种估计放在一起比较</h3><div class="toolbar">${select('compareK','比较人数',allK.map(k=>[String(k),String(k)]),s.compareK)}</div>${table(comparison,[[r=>versions[r.shownVersion],'版本'],[r=>r.shownVersion==='hybrid48'?estimator(r):'路径频数','权重/来源'],ncol('Q_mean','Q'),ncol('Q_p10','P10'),[r=>fmt(r.Q_sd_population_estimate??r.Q_sd_ddof1),'SD（定义随版本）'],[r=>fmt(r.Q_mean_MCSE??r.Q_mean_MCSE_analytic),'均值MCSE'],[r=>fmt(r.path_count??r.paths_attempted),'路径数'],ncol('unique_teams','不同团队')])}<p>无该批次数据则不造一行；四种随机版本各自保持原频数，精确目录每个不同团队等权。</p><details><summary>旧24／新24／合48／重点96的逐人数精度</summary>${table(precision,[[r=>versions[r.version],'版本'],ncol('k','k'),ncol('available_images','候选图'),ncol('quality_images','Q可用图'),ncol('mean_MCSE_median','单图均值MCSE中位数'),ncol('mean_MCSE_p90','MCSE P90'),ncol('P10_empirical_interval_estimable_images','P10区间可估图'),ncol('P10_empirical95_halfwidth_median','P10经验半宽中位数')])}<p>上面精度表随所选版本变化；主展示选择时显示合48精度。精确边际的抽样误差可为0，但参考误差并不因此消失。</p></details>
  <h3>实际增人比较：读取同路径配对表</h3><div class="toolbar">${select('interval','同一顺序前后比较',intervals.map(x=>[x,x.replaceAll('_to_','→')]),s.interval)}</div><p>这里使用${versions[s.version==='hybrid48'?'pooled48':s.version]}保存的配对路径，不用精确边际拼造进入过程。边际Q差和双方可评路径Q差不是同一估计对象。</p>${table(paired,[[r=>r.interval,'阶段'],ncol('marginal_Q_delta','边际Q差'),ncol('paired_Q_delta','同路径共同Q差'),ncol('both_quality_valid_paths','共同可评路径'),ncol('gained_score_paths','恢复可评'),ncol('lost_score_paths','新增不可评'),ncol('paths_attempted','全部路径')])}
  <details><summary>固定157图的几何V：批次、图和楼支持</summary>${table(data.geometry_fixed,[[r=>({combined48:'合并48',new24:'独立新24',old24:'原24'})[r.cohort]||r.cohort,'批次'],[r=>r.k_from+'→'+r.k_to,'人数'],ncol('delta_mean','平均V差'),[r=>r.images_decrease+'/'+r.images,'下降图/固定图'],[r=>r.buildings_decrease+'/'+r.buildings,'下降楼/固定楼']])}<p>几何V与Q标准差不是同一量，批次结果分别解释。</p></details>${wc2(data)}${jumpTables(['hybrid_images','hybrid_fixed','batch_images','precision','batch_differences','paired_intervals','exact','geometry_fixed','vfua_votes'])}`;
  host.querySelectorAll('[data-precision]').forEach(el=>el.onchange=()=>{s[el.dataset.precision]=el.value;draw(host);});
 };
 return {head:'<section class="panel" id="precisionNatural"></section>',activate:slot=>draw(slot.querySelector('#precisionNatural'))};
}
function wc2(data){
 const image=data.wc2_teams[0]?.image_id;
 return `<section class="panel"><h3>wc2-46：见过全部团队，仍可能没估准低分频率</h3><p>28支缺一人队中4支低分。96路径已覆盖全部28队，却只出现7次低分；随机线性P10为97.387，精确目录线性P10为52.406。抽样频次与有限目录均匀权重是两种分布；另保留逆CDF定义，不事后更换口径。</p>${table(data.wc2_weights,[[r=>({exact_uniform_28_teams:'完整28队等权',old24:'原24',new24:'独立新24',combined48:'合48',combined96:'重点96',focus48:'追加重点48',independent_new72:'独立新72'})[r.sample]||r.sample,'版本'],ncol('observations','记录/队数'),ncol('unique_teams','不同团队'),ncol('low_peak_observations','低分次数'),ncol('P10_linear','线性P10'),ncol('P10_inverseCDF','逆CDF P10')])}<details><summary>28支确定团队与实际缺席成员</summary>${table(data.wc2_teams,[['absent_worker','缺席成员'],ncol('B8L2','Q'),['score_peak','描述性分组'],ncol('combined48_path_count','合48频数'),ncol('combined96_path_count','合96频数'),ncol('finite_uniform_weight','有限目录权重')])}</details><a href="#release=v2&module=images&image=${esc(image)}">查看wc2-46原图与全部完整个人标注</a><p>VFua-04的35支缺一人团队有32支可评、3支失败；满员只有3节点。三份保存状态的逐身份票账保留在明细表中，只解释该例，不推广为所有图片的机制。</p><details><summary>VFua-04三个缺一人团队的身份票账</summary><p>三队均34人、门槛17票。缺W103时两组17/16票，缺W113时16/17票，缺W134时16/16票；原身份与是否入选分别保存，不重算或补连线。</p>${table(data.vfua_votes,[['absent_worker','缺席成员'],['feature_id','保存身份'],ncol('support','支持票'),[r=>r.selected?'入选':'未入选','结果']])}<figure><img class="briefing-visual" loading="lazy" src="../../../research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/analysis_geometry/case_VFua_04/VFUA_LEAVE_ONE_OUT_BEV.png" alt="VFua-04三个保存缺一人团队的底面与选中节点"><figcaption>保存案例几何；该例不能代表所有图的加人机制。</figcaption></figure></details><a href="#release=v2&module=patterns&case=F_SAVED_VFuaQ6m2Qom-04&condition=manual">查看VFua-04满员失败几何与原答</a></section>`;
}
function policy(data){
 const s={batch:'combined16',phase:'early_3_to_half',difficulty:'全部',metric:'paired_Q_delta',policy:'joint_highq_first'};
 const draw=host=>{
  const matching=(r,metric=s.metric)=>r.batch===s.batch&&r.phase===s.phase&&r.difficulty===s.difficulty&&r.metric===metric&&r.weighting==='image_equal';
  const rows=data.policy_summary.filter(r=>matching(r));
  const joint=data.policy_summary.filter(r=>matching(r,'labor_ratio_legal'));
  const details=data.policy_images.filter(r=>r.batch===s.batch&&r.phase===s.phase&&r.policy===s.policy&&(s.difficulty==='全部'||r.difficulty===s.difficulty));
  const value=(r,key)=>present(r[key])?fmt(r[key]*(s.metric==='failure_delta'?100:1)):'缺失';
  host.innerHTML=`<p class="eyebrow">策略固定支持修正 · 2026-10-25</p><h2>历史角色优先：前段质量方向重复，固定支持后再看精度</h2><p>合16前段固定157图：高Q优先 +7.672分（152/157图升），多转折 +6.127（135/157），快速 −1.742（53/157升），人数最多结构类 −1.944（31/157升）。独立新8重复四个平均方向。</p><p>沿用旧冻结V3_BEHAVIOR细类/V3_JOINT_QT粗类；这是进入顺序实验，不是DSTRUCT/RFUSE策略验证。前段为各图3至floor(N/2)，固定原8、新8、合16都可估的共同k；自然N≥30的157图与策略157图仅148图交集，不能混用名单。</p><div class="toolbar">${select('batch','配对批次',opts(batches),s.batch)}${select('phase','阶段',opts(phases),s.phase)}${select('difficulty','难度',['全部','简单','中等','困难'].map(x=>[x,x]),s.difficulty)}${select('metric','指标',opts(policyMetrics),s.metric)}</div>${table(rows,[[r=>policies[r.policy],'优先角色'],[r=>value(r,'estimate'),'图等权策略−自然 / 劳动比'],[r=>`${r.images}/${r.candidate_images}`,'可估/候选图'],[r=>`${r.positive_images}/${r.negative_images}/${r.nearzero_images}`,'正/负/零图'],[r=>`[${value(r,'path_lo')}, ${value(r,'path_hi')}]`,'路径重抽条件经验范围'],[r=>`${r.path_valid_replicates}/${r.bootstrap_replicates}；不可估${r.path_invalid_replicates}`,'可估重抽/总数'],[r=>`[${value(r,'building_lo')}, ${value(r,'building_hi')}]`,'建筑重抽经验范围']])}<p class="warning">路径范围仅条件于可估重抽；缺固定k或图片时保留不可估，不按剩余图片重分权。合16前段Q可估次数分别为997/939/818/731（总1000），原8快速类仅45次。这里不把这些范围画成完整曲线置信带，建筑重抽另列。</p><h3>记录劳动：使用各策略自己的共同Q/T支持</h3>${table(joint,[[r=>policies[r.policy],'策略'],ncol('images','合法共同Q/T图'),ncol('estimate','同域劳动比（策略/自然）'),[r=>fmt(data.policy_summary.find(q=>matching(q,'QT_paired_Q_delta')&&q.policy===r.policy)?.estimate),'同域Q差'],[r=>`${r.path_valid_replicates}/${r.bootstrap_replicates}`,'劳动比路径重抽可估/总数']])}<p>合16前段时间支持分别116/96/73/119图；不能把这些时间比与157图Q收益拼成同域双赢，也不是四策略共同时间图集。旧67图/18楼共同时间比较保留原8路径身份，见下方历史图表。失败始终按完整阶段全部尝试计算，不随Q共同k过滤。</p><details><summary>逐图固定人数支持与质量／时间</summary><div class="toolbar">${select('policy','查看策略',opts(policies),s.policy)}</div>${table(details,[['image','图片'],ncol('pool_n','N'),ncol('base_paths','基础路径'),ncol('fixed_Q_k','固定共同k数'),ncol('paired_Q_delta','同路径Q差'),ncol('attempted_prefixes','全部前缀尝试'),ncol('legal_QT_prefixes','合法Q/T前缀'),ncol('labor_ratio_legal','同域劳动比'),ncol('QT_paired_Q_delta','同域Q差'),ncol('failure_delta','失败率差')])}</details>${jumpTables(['policy_key','policy_summary','policy_images'])}`;
  host.querySelectorAll('[data-precision]').forEach(el=>el.onchange=()=>{s[el.dataset.precision]=el.value;draw(host);});
 };
 return {head:'<section class="panel" id="precisionPolicy"></section>',activate:slot=>draw(slot.querySelector('#precisionPolicy'))};
}
async function create(mode,ctx){
 const keys=mode==='policy'?['policy_key','policy_summary','policy_images']:['hybrid_images','hybrid_fixed','batch_images','precision','batch_differences','paired_intervals','exact','wc2_weights','wc2_teams','geometry_fixed','vfua_votes'];
 const data=await load(keys,ctx);if(!ctx.isCurrent())return {head:'',activate:()=>{}};
 return mode==='policy'?policy(data,ctx):natural(data,ctx);
}
return {create,fixedRows,individualRows,estimator,present};
})();
