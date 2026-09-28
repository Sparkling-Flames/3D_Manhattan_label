'use strict';
(() => {
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const states={ready:'已接入',pending:'待接入结果',not_computed:'未计算',insufficient:'人数不足',not_met:'未达标',unresolved:'判断未决',not_applicable:'不适用'};
const modules={
 overview:{name:'数据全景',en:'DATA LANDSCAPE',subtitle:'从图片、空间与作答，理解当前数据的覆盖范围。',metrics:['图片覆盖','房间 / 场景','实际参与人数','可分析作答'],chart:'数据覆盖与可分析范围',intro:'图片、房间、场景、人员及作答覆盖将在这里呈现。',defs:[['实际人数与作答','实际人数按当前结果切片的独立人员身份计数；同一人的多次作答不等于多个人。'],['覆盖与可分析范围','已接入、已作答与可分析范围分开呈现。分析方提供定义、单位、分母及纳入范围。'],['统计与精选案例','统计保留全部接入图片；精选清单仅控制离线图像、点集和 3D 资源的携带范围。']]},
 annotation:{name:'标注与分簇',en:'ANNOTATIONS & CLUSTERS',subtitle:'在全景图中连接人员点集、簇成员与局部差异。',metrics:['标注点集','支持簇','单人表达','精选案例'],chart:'点集与候选方法对照',intro:'接入人员点集、簇成员及局部差异后，可从图片索引进入全景与 3D 案例。',defs:[['点号与连接关系','点号属于明确的点集版本；保留原始身份、top y、bottom y、各端点 x 与连接关系。'],['方法对照','分簇方法按明确选择切换；不同方法的簇编号不默认具有对应关系。'],['3D 观察边界','原始重建、拟合展示与数值扰动分别标记。3D 只显示上游几何结果，不据此自动得出机制结论。']]},
 stability:{name:'人数与稳定性',en:'SAMPLE SIZE & STABILITY',subtitle:'观察人数增加时的分布变化、支持情况与持续阶段。',metrics:['已计算前缀','支持簇','单人表达','未决状态'],chart:'人数增加后的分布与阶段',intro:'人数曲线、持续阶段及未决状态将在此接入；缺失值保留为空。',defs:[['人数与顺序','横轴人数、人员子集和进入顺序由分析结果指定；不同重放序列分别标记。'],['支持与持续','支持簇、单人表达与持续阶段沿用所选方法的定义，展示页不选择阈值。'],['状态区分','人数不足、未计算、未达标与判断未决独立显示；这些状态不画成零，也不连接缺失段。']]},
 people:{name:'人员与组成',en:'PEOPLE & COMPOSITION',subtitle:'查看分类依据、覆盖与具体成员，探索不同进入顺序。',metrics:['分类覆盖','类别配比','可用成员','重放序列'],chart:'人员组成与进入顺序重放',intro:'分类依据、类别配比、成员名单和逐步重放结果将在此接入。',defs:[['分类方案','分类名称、依据和覆盖范围来自当前方案说明；不预设类别数量或 AABC 组成。'],['成员与配比','每项结果保留具体成员及分母；类别配比与人数、作答数分开解释。'],['进入顺序重放','播放分析方预先计算的行序列，只显示已提供的步骤；页面不训练分类或重算分簇。']]},
 rooms:{name:'同房与同场景',en:'ROOMS & SCENES',subtitle:'连接人工空间分组、逐图变化与历史／预测拆分。',metrics:['人工同房组','相似场景组','历史图片','预测图片'],chart:'逐图曲线与预测结果',intro:'接入人工分组、历史／预测身份及逐图结果后，可在同一空间范围内查看。',defs:[['人工同房分组','房间身份采用分析方提供的人工分组；相同建筑并不自动代表同一房间。'],['历史／预测拆分','拆分身份和来源由上游表格明确记录，逐图曲线保留图片关联，不静默合并。'],['预测的展示','预测数值、单位、参照对象与不确定性随结果接入；此页不训练或重新预测。']]},
 features:{name:'图片特征与难度',en:'FEATURES & UNCERTAINTY',subtitle:'为图片特征、模型输出与不确定性的关系保留研究视图。',metrics:['图片特征','模型输出','不确定性指标','已核验关系'],chart:'特征与不确定性的关系',intro:'待研究。尚未接入可展示的特征关系与核验结果。',defs:[['特征来源','图片特征和模型输出需保留版本、提取方法与来源关联；未完成部分显示待研究。'],['关系与不确定性','接入分析方给出的关系、估计与不确定性说明，不由展示页拟合或选取阈值。'],['核验边界','观察到的相关现象不自动构成难度或机制结论；核验状态必须随结果提供。']]}
};
const dims=['version','condition','method','classification','building','room','image'];
const labels=['数据版本','条件','分簇方法','分类方案','建筑','房间','图片'];
const catalog={version:'versions',method:'methods',classification:'classifications'};
let data, active='overview', scope={}, comparison='', imageQuery='', lastDetail=null, detailToken=0, returnFocus=null;
const palette=['#55755a','#ac8558','#7b91a0','#9a7792','#8a9360','#627b80'];
const escapePlot = x => String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const shown=x=>x===null||x===undefined?'—':Array.isArray(x)?x.join('、'):typeof x==='object'?JSON.stringify(x):String(x);
const label=(key,value)=>catalog[key]?data[catalog[key]].find(x=>x.id===value)?.label||value:value||'全部（已提供汇总）';
const context=v=>dims.map((k,i)=>`${labels[i]}：${label(k,v[k])}`).join(' · ');
const current=()=>data.views.find(v=>dims.every(k=>v[k]===scope[k]));
const compatible=(c,v)=>v&&dims.slice(0,4).every(k=>c[k]===v[k])&&v.image_ids.includes(c.image_id);
const casesFor=(id,v)=>data.cases.filter(c=>c.image_id===id&&compatible(c,v));
function button(text,fn){const b=el('button',text);b.onclick=fn;return b;}
function option(value,text){const o=el('option',text);o.value=value;return o;}
function fatal(error){$('fatal').hidden=false;$('fatal').textContent='数据包无法展示：'+error.message+'。请重新打包同一版本的完整资源。';}
function filters(){
 let candidates=data.views;
 dims.forEach((key,i)=>{
  const select=$('filter-'+key),values=[...new Set(candidates.map(v=>v[key]))];
  if(!values.includes(scope[key]))scope[key]=values[0];
  select.replaceChildren(...values.map(v=>option(v,label(key,v))));
  if(!values.length)select.append(option('','待接入'));
  select.disabled=values.length<2;select.value=scope[key]??'';
  candidates=candidates.filter(v=>v[key]===scope[key]);
 });
 $('compare').disabled=data.views.length<2;
 const others=data.views.filter(v=>v.id!==current()?.id);
 if(!others.some(v=>v.id===comparison)){comparison='';$('compare').checked=false;}
 $('compare-view').replaceChildren(option('','请选择一组结果'),...others.map(v=>option(v.id,context(v))));
 $('compare-view').value=comparison;$('compare-view').hidden=!$('compare').checked;
}
function empty(parent,title,description,slot){const box=el('div',undefined,'empty');box.append(el('span','◇','empty-symbol'),el('h3',title),el('p',description));if(slot)box.append(el('p',slot,'slot'));parent.append(box);}
function table(parent,columns,rows,view,unpaged=false){
 const replay=!unpaged&&['J','m','tail_fraction','h','observation_status'].every(key=>columns.some(c=>c.key===key));
 if(replay){
  const controls=el('div',undefined,'table-controls'),result=el('div',undefined,'replay-table');
  const rule=el('select'),h=el('select'),search=el('input'),full=el('input');
  const key=r=>JSON.stringify([r.J,r.m,r.tail_fraction]);
  const rules=[...new Map(rows.map(r=>[key(r),r])).values()];
  rules.forEach(r=>rule.append(option(key(r),`最多 ${r.J} 簇 · 每簇至少 ${r.m} 人 · 未支持份额 ≤ ${r.tail_fraction}`)));
  [...new Set(rows.map(r=>r.h))].forEach(v=>h.append(option(String(v),`后续观察 ${v} 人`)));
  rule.value=rules.length?key(rules[0]):'';h.value=rows.length?String(rows[0].h):'';
  rule.setAttribute('aria-label','查看判据');h.setAttribute('aria-label','后续观察人数');
  search.type='search';search.placeholder='搜索图片或成员';search.setAttribute('aria-label','搜索此表');full.type='checkbox';
  const label=el('label');label.append(full,el('span','显示完整字段'));
  const count=el('span');controls.append(rule,h,search,label,count);parent.append(controls,result);
  function update(){
   const q=search.value.trim().toLowerCase();
   const selected=rows.filter(r=>key(r)===rule.value&&String(r.h)===h.value&&(!q||columns.some(c=>shown(r[c.key]).toLowerCase().includes(q))));
   const compact=['code','N','success_orders','orders','success_fraction','observed_onset_median_success_only','observation_status'];
   const visible=full.checked?columns:columns.filter(c=>compact.includes(c.key));
   result.replaceChildren();table(result,visible,selected,view,true);
   count.textContent=`${selected.length} 行 · 当前判据（原表 ${rows.length} 行）`;
  }
  rule.onchange=h.onchange=full.onchange=search.oninput=update;search.value='';update();return;
 }
 const wrap=el('div',undefined,'table-wrap'),t=el('table'),head=el('thead'),tr=el('tr');
 columns.forEach(c=>tr.append(el('th',c.label+(c.unit?' / '+c.unit:''))));head.append(tr);t.append(head);const body=el('tbody');
 let filtered=rows,page=0;const pageSize=unpaged?Math.max(1,rows.length):100;
 const controls=rows.length>pageSize?el('div',undefined,'table-controls'):null;
 const search=controls?el('input'):null;
 const previous=controls?button('上一页',()=>{page--;paint();}):null,next=controls?button('下一页',()=>{page++;paint();}):null,count=el('span');
 function paint(){body.replaceChildren();filtered.slice(page*pageSize,(page+1)*pageSize).forEach(row=>{const r=el('tr');columns.forEach(c=>{const cell=el('td');if(c.key==='image_id'&&row[c.key])cell.append(button(row[c.key],()=>openCase(row[c.key],view)));else cell.textContent=c.key==='status'?states[row[c.key]]||shown(row[c.key]):shown(row[c.key]);if(typeof row[c.key]==='number')cell.classList.add('numeric');r.append(cell);});body.append(r);});if(controls){previous.disabled=page===0;next.disabled=(page+1)*pageSize>=filtered.length;count.textContent=`${filtered.length? page*pageSize+1:0}–${Math.min((page+1)*pageSize,filtered.length)} / ${filtered.length} 行（原表 ${rows.length} 行）`;}}
 if(controls){search.type='search';search.placeholder='搜索图片、成员或表格内容';search.setAttribute('aria-label','搜索此表');search.oninput=()=>{const q=search.value.trim().toLowerCase();filtered=q?rows.filter(r=>columns.some(c=>shown(r[c.key]).toLowerCase().includes(q))):rows;page=0;paint();};controls.append(search,previous,count,next);parent.append(controls);}
 paint();
 t.append(body);wrap.append(t);parent.append(wrap);
}
function sourceText(ids){return ids.map(id=>{const s=data.sources.find(x=>x.id===id);return `${s.label} [${id}]：${s.description}`;}).join('；');}
function metricCards(parent,mod){
 if(data.views.length&&(!mod||!mod.metrics.length))return;
 const grid=el('div',undefined,'metrics');
 const items=mod?.metrics.length?mod.metrics:modules[active].metrics.map(label=>({label,value:null,status:'pending',unit:'',definition:'待接入结果'}));
 items.forEach(m=>{const card=el('article',undefined,'metric');card.append(el('p',m.label,'metric-label'));const value=el('div',m.value===null?'—':shown(m.value),'metric-value');if(m.value!==null)value.append(el('small',m.unit));card.append(value,el('p',states[m.status],'muted'));const det=el('details');det.append(el('summary','口径与来源'),el('p',m.definition));if(m.source_ids)det.append(el('p',`分母：${shown(m.denominator)}；成员：${shown(m.member_ids)}；来源：${sourceText(m.source_ids)}`));card.append(det);grid.append(card);});parent.append(grid);
}
function drawChart(parent,chart,view){
 const card=el('article',undefined,'chart-card'),head=el('div',undefined,'card-head');head.append(el('h3',chart.title));card.append(head);
 const plot=el('div',undefined,'chart');card.append(plot);parent.append(card);
 const coverage=['coverage','endpoint'].includes(chart.id)&&chart.kind==='bar';
 const imageOrder=[...new Set(chart.rows.map(r=>r.x))],pageSize=24;
 let page=0,paging;
 if(coverage&&imageOrder.length>pageSize){paging=el('div',undefined,'zoom-range');head.append(paging);}
 function paint(){
 const visible=coverage?imageOrder.slice(page*pageSize,(page+1)*pageSize):imageOrder,visibleSet=new Set(visible);
 const chartRows=coverage?chart.rows.filter(r=>visibleSet.has(r.x)):chart.rows;
 if(paging){const previous=button('上一页',()=>{page--;paint();}),next=button('下一页',()=>{page++;paint();});previous.disabled=page===0;next.disabled=(page+1)*pageSize>=imageOrder.length;paging.replaceChildren(previous,el('span',`${page*pageSize+1}–${Math.min((page+1)*pageSize,imageOrder.length)} / ${imageOrder.length} 张图片`),next);}
 const groups=new Map();chartRows.forEach(row=>{const key=JSON.stringify([row.series,chart.group_by_image===false?'':row.image_id]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);});
 const categories=[...new Set(chartRows.map(r=>r.x))].filter(x=>typeof x==='string'),step=coverage?1:Math.max(1,Math.ceil(categories.length/12));
 const ticks=categories.filter((_,i)=>i%step===0),tickOptions=categories.length?{tickmode:'array',tickvals:ticks.map(escapePlot),ticktext:ticks.map(x=>escapePlot(x).replace(' · ','<br>')),tickangle:categories.length>12?-35:0}:{};
 const traces=[...groups.values()].map((rows,i)=>({
  name:escapePlot(rows[0].series+(rows[0].image_id&&chart.group_by_image!==false?' · '+rows[0].image_id:'')),type:chart.kind==='bar'?'bar':'scatter',
  mode:chart.kind==='line'?'lines+markers':'markers',connectgaps:false,textposition:'none',
  x:rows.map(r=>typeof r.x==='string'?escapePlot(r.x):r.x),y:rows.map(r=>r.value),
  customdata:rows.map(r=>[r.image_id,r.status,r.numerator,r.denominator,r.member_ids.join('、')]),
  text:rows.map(r=>escapePlot(`图片：${r.image_id||'汇总'}；${states[r.status]}；分子/分母：${shown(r.numerator)}/${shown(r.denominator)}；成员：${shown(r.member_ids)}`)),
  line:{color:palette[i%palette.length],width:2.5},marker:{color:coverage?({manual:'#55755a',oos:'#ac8558',semi:'#7b91a0'}[rows[0].series.toLowerCase()]||palette[i%palette.length]):palette[i%palette.length],size:8},
  hovertemplate:`${escapePlot(chart.x_label)}：%{x} ${escapePlot(chart.x_unit)}<br>${escapePlot(chart.y_label)}：%{y} ${escapePlot(chart.unit)}<br>%{text}<extra>%{fullData.name}</extra>`
 }));
 if(!chart.rows.some(r=>r.value!==null)){plot.remove();empty(card,'暂无可绘制数值','状态与缺失值保留在底层表格中。');}
 else Plotly.react(plot,traces,{barmode:'group',bargap:coverage?.2:.1,font:{family:'Segoe UI, Microsoft YaHei, sans-serif',size:15,color:'#425542'},paper_bgcolor:'#fff',plot_bgcolor:'#fff',colorway:palette,margin:{l:75,r:30,t:35,b:90},xaxis:{...tickOptions,...(coverage?{type:'category',categoryorder:'array',categoryarray:visible.map(escapePlot)}:{}),title:{text:escapePlot(chart.x_label+' / '+chart.x_unit)},gridcolor:'#edf1e9',automargin:true},yaxis:{...(coverage?{rangemode:'tozero',range:[0,Math.max(1,...chart.rows.map(r=>r.value??0))*1.1],dtick:Math.max(1,Math.ceil(Math.max(1,...chart.rows.map(r=>r.value??0))/6)),tickformat:',d'}:{}),title:{text:escapePlot(chart.y_label+' / '+chart.unit)},gridcolor:'#e6ece1',automargin:true},showlegend:true,legend:{orientation:'h',y:-.24},hovermode:'closest'},{responsive:true,displaylogo:false,scrollZoom:true,modeBarButtonsToRemove:['sendDataToCloud','toImage']}).then(()=>{if(plot.isConnected){plot.removeAllListeners('plotly_click');plot.on('plotly_click',ev=>{const id=ev.points[0]?.customdata?.[0];if(id)openCase(id,view);});}}).catch(fatal);
 }
 paint();
 card.append(el('p',chart.definition,'chart-note'));
 const missing=chart.rows.filter(r=>r.value===null);if(missing.length)card.append(el('p',`未绘制 ${missing.length} 个缺失值：${[...new Set(missing.map(r=>states[r.status]))].join('、')}。`,'chart-note missing'));
 const details=el('details',undefined,'table-details');details.append(el('summary','查看底层表格 · 数值 / 分母 / 成员 / 来源'));
 const cols=[['series','系列',''],['image_id','图片',''],['x',chart.x_label,chart.x_unit],['value',chart.y_label,chart.unit],['status','状态',''],['numerator','分子',''],['denominator','分母',''],['member_ids','成员（输入顺序）',''],['source_ids','来源 ID','']].map(([key,label,unit])=>({key,label,unit}));
 table(details,cols,chart.rows,view);card.append(details);
}
function renderView(parent,view,role){
 if(view){const choices=data.views.filter(v=>v.version==='shared_x_reanalysis_20260922_v1'&&!v.building&&!v.room&&!v.image);if(choices.length){const links=el('div',undefined,'context-note'),targets=view.version===choices[0].version?choices:[choices[0]];for(const v of targets)links.append(button(targets.length===1?'共享x重分析 · 打开四条件对照':label('condition',v.condition)+' · '+label('method',v.method),()=>{scope=Object.fromEntries(dims.map(k=>[k,v[k]]));comparison='';render();}));const example=data.views.find(v=>v.version===view.version&&v.version===choices[0].version&&v.condition===view.condition&&v.method===view.method&&v.image==='q9vSo1VnCiC_c421f07780004647a7198c4ac5371e8a');if(example)links.append(button('主簇与零散尾部 · 查看示例图',()=>{scope=Object.fromEntries(dims.map(k=>[k,example[k]]));comparison='';active='stability';render();}));parent.append(links);}}
 if(active==='people'&&view){
  const target=data.views.find(v=>v.classification==='old-classification-overview'&&v.method==='old-complete');
  const switchTo=v=>{scope=Object.fromEntries(dims.map(k=>[k,v[k]]));comparison='';render();};
  if(target&&view.classification!=='old-classification-overview'){const entry=el('div',undefined,'context-note');entry.append(button('人员分类对照 · 历史09-21（新分区尚未复验）',()=>switchTo(target)));parent.append(entry);}
  if(target&&view.classification==='old-classification-overview'){
   const nav=el('div',undefined,'context-note'),select=el('select');select.setAttribute('aria-label','分类详情与历史版本');
   const routes=[['Q_2 · 09-21完整上限与逐楼名单','old-Q_2'],['Q＋T二分类 · 09-21','old-QT_2'],['Q＋T三分类 · 09-21','old-QT_3'],['T快慢 · 09-10后续20人','ward-T-2'],['S范围判断 · 09-10后续20人','ward-S-2'],['B半自动行为 · 09-10后续20人','ward-B-2'],['Q＋B · 09-10后续20人','ward-QB-2'],['QTSB三分类 · 09-21','old-QTSB_3'],['三轴三分类 · 09-21','old-TRI_3']];
   for(const [name,id] of routes){const old=id.startsWith('ward-');const v=data.views.find(v=>v.classification===id&&v.version===(old?'history-20260910':view.version)&&v.method===(old?'old-q95':view.method)&&(!old||v.condition==='后续20人'));if(v){const option=el('option',name);option.value=v.id;select.append(option);}}
   nav.append(el('span','查看分类详情（含成员、覆盖与历史口径）'),select,button('打开所选分类',()=>{const v=data.views.find(v=>v.id===select.value);if(v)switchTo(v);}));parent.append(nav);
  }
 }
 if(view){const links=el('div',undefined,'context-note');for(const version of data.versions){if(version.id===view.version)continue;const choices=data.views.filter(v=>v.version===version.id&&!v.building&&v.modules[active].status==='ready');const target=choices.find(v=>v.classification==='median-same39')||choices.find(v=>v.classification==='old-Q_2'&&v.method==='old-complete')||choices[0];if(target)links.append(button('切换：'+version.label,()=>{scope=Object.fromEntries(dims.map(k=>[k,target[k]]));comparison='';render();}));}if(links.children.length){const history=el('details');history.append(el('summary','其他数据版本 · 展开选择'),links);parent.append(history);}}
 if(view&&!view.modules[active].charts.length&&!view.modules[active].tables.length){const available=data.views.filter(v=>v.version===view.version&&!v.building&&!v.room&&!v.image&&v.modules[active].status==='ready');if(available.length){const links=el('div',undefined,'context-note');available.forEach(v=>links.append(button('查看 '+label('condition',v.condition)+' · '+label('method',v.method),()=>{scope=Object.fromEntries(dims.map(k=>[k,v[k]]));comparison='';render();})));parent.append(links);}}
 if(role)parent.append(el('p',role+' · '+context(view),'result-label'));
 const mod=view?.modules[active];metricCards(parent,mod);
 if(!mod||!mod.charts.length&&!mod.tables.length){const card=el('article',undefined,'chart-card'),head=el('div',undefined,'card-head');const text=el('div');text.append(el('h3',modules[active].chart),el('p','研究结果展示区'));head.append(text,el('span',states[mod?.status||'pending'],'badge'));card.append(head);empty(card,mod?.status==='ready'?'当前筛选无结果':states[mod?.status||'pending'],mod?.note||modules[active].intro,'结果接入位置');const legend=el('div',undefined,'state-legend');['insufficient','not_computed','not_met','unresolved'].forEach(s=>legend.append(el('span','○ '+states[s])));card.append(legend);parent.append(card);}
 else{if(mod.note)parent.append(el('p',mod.note,'chart-note'));mod.charts.forEach(c=>drawChart(parent,c,view));mod.tables.forEach(t=>{const card=el('article',undefined,'chart-card');const head=el('div',undefined,'card-head');head.append(el('h3',t.title));card.append(head);table(card,t.columns,t.rows,view);if(active==='people'&&t.replay===true&&t.rows.length){const slider=el('input');slider.type='range';slider.min=1;slider.max=t.rows.length;slider.value=t.rows.length;slider.setAttribute('aria-label','进入顺序重放步骤');const output=el('output',`已显示 ${t.rows.length} / ${t.rows.length} 步`);slider.oninput=()=>{card.querySelectorAll('tbody tr').forEach((r,i)=>r.hidden=i>=Number(slider.value));output.textContent=`已显示 ${slider.value} / ${t.rows.length} 步（分析方提供的顺序）`;};const ctl=el('div',undefined,'zoom-range');ctl.append(slider,output);card.append(ctl);}parent.append(card);});}
}
function imageList(){
 const view=current(),items=data.images.filter(i=>view?.image_ids.includes(i.id)).sort((a,b)=>Number(!!casesFor(b.id,view).length)-Number(!!casesFor(a.id,view).length)),filtered=items.filter(i=>[i.id,i.building,i.room,i.scene].join(' ').toLowerCase().includes(imageQuery.toLowerCase()));
 $('image-count').textContent=items.length?`${items.length} 张统计图片 · ${items.filter(i=>casesFor(i.id,view).length).length} 张携带资源`:view?'本切片未提供逐图索引':'待接入结果';
 $('image-list').replaceChildren(...filtered.map(i=>{const b=button(i.id,()=>openCase(i.id,view));b.className='image-card';b.append(el('small',`${i.building} / ${i.room} · ${i.scene}`),el('small',casesFor(i.id,view).length?'精选案例 · 图像与点集':'统计可查 · 未包含图像资源'));return b;}));
 if(!filtered.length)$('image-list').append(el('p',imageQuery?'没有匹配的图片。':view?'本切片仅提供汇总结果，未提供可关联的逐图索引。':'待接入图片索引；接入后可查全部统计图片。','muted'));
}
function close(){detailToken++;$('drawer').hidden=true;$('drawer-content').replaceChildren();lastDetail=null;returnFocus?.focus();}
function render(){
 close();filters();const m=modules[active],index=Object.keys(modules).indexOf(active)+1;
 $('title').textContent=m.name;$('breadcrumb').textContent=m.name;$('eyebrow').textContent=String(index).padStart(2,'0')+' / '+m.en;$('subtitle').textContent=m.subtitle;
 document.querySelectorAll('nav button').forEach(b=>{b.classList.toggle('active',b.dataset.module===active);b.setAttribute('aria-current',b.dataset.module===active?'page':'false');});
 const view=current();$('scope').textContent=view?context(view):'筛选选项将在结果接入后启用。';$('release-state').textContent=states[view?.modules[active].status||'pending'];
 document.querySelectorAll('.chart.js-plotly-plot').forEach(p=>Plotly.purge(p));$('results').replaceChildren();renderView($('results'),view,comparison?'当前结果':'');
 const other=data.views.find(v=>v.id===comparison);if(other)renderView($('results'),other,'明确选择的对照结果（独立坐标与口径）');
 document.querySelector('.definitions').hidden=!!data.views.length;
 $('definition-cards').replaceChildren(...m.defs.map(([title,text])=>{const a=el('article');a.append(el('h3',title),el('p',text));return a;}));imageList();
}
function drawer(title){returnFocus=document.activeElement;$('drawer-title').textContent=title;$('drawer').hidden=false;$('drawer-content').replaceChildren();$('close-drawer').focus();return $('drawer-content');}
function definitions(){lastDetail={type:'definitions'};const body=drawer('版本与来源');body.append(el('p',`发布版本：${data.release}`,'context-note'));if(!data.views.length)modules[active].defs.forEach(([h,p])=>body.append(el('h3',h),el('p',p)));for(const [key,name] of [['versions','数据版本'],['methods','分簇方法'],['classifications','分类方案'],['sources','来源说明']]){body.append(el('h3',name));if(!data[key].length)body.append(el('p','待接入结果','muted'));data[key].forEach(x=>body.append(el('p',`${x.label} [${x.id}]：${x.description}`,'source-item')));}}
function svgNode(tag,attrs){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));return n;}
async function caseResources(body,c,view,token){
 const ctl=el('div',undefined,'case-controls'),label1=el('label','人员点集 / 展示类型'),select=el('select'),label2=el('label','明确叠加对照'),other=el('select');select.setAttribute('aria-label','人员点集');other.setAttribute('aria-label','对照点集');
 const kind={original:'原始重建',fit:'拟合展示',perturbation:'数值扰动'};
 select.append(...c.variants.map(v=>option(v.id,v.name+' · '+kind[v.kind])));other.append(option('','不叠加'),...c.variants.map(v=>option(v.id,v.name+' · '+kind[v.kind])));label1.append(select);label2.append(other);ctl.append(label1,label2);body.append(ctl);
 const roster=el('details');roster.append(el('summary',`全部簇成员与完整点集 · ${c.variants.length} 份`));const members=el('div',undefined,'case-roster');c.variants.forEach(v=>members.append(button(`${v.member_ids.join('、')} · 簇 ${v.cluster_ids.join('、')} · ${v.pairs.length*2}端点`,()=>{select.value=v.id;select.dispatchEvent(new Event('change'));})));roster.append(members);body.append(roster);
 body.append(el('p',`坐标基准 ${c.width}×${c.height} px；p 编号为源端点，组号不代表跨人的语义对应。`,'detail-note'));
 const stage=el('div'),info=el('div');body.append(stage,info);
 let image;
 try{image=await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=c.image_script;s.onload=()=>{resolve(window.DASHBOARD_IMAGE);s.remove();};s.onerror=()=>{s.remove();reject(new Error('精选图像资源缺失'));};document.head.append(s);});}catch(e){if(token===detailToken)stage.append(el('p',e.message,'missing'));return;}
 if(token!==detailToken)return;
 function draw(){
  stage.replaceChildren();info.replaceChildren();const v=c.variants.find(v=>v.id===select.value),v2=c.variants.find(v=>v.id===other.value);
  const wrap=el('div',undefined,'panorama-scroll'),svg=svgNode('svg',{viewBox:`0 0 ${c.width} ${c.height}`,role:'img','aria-label':'全景图及当前版本标注点集'});svg.append(svgNode('image',{href:image.original,width:c.width,height:c.height}));wrap.append(svg);stage.append(wrap);
  const zoom=el('input');zoom.type='range';zoom.min=100;zoom.max=400;zoom.value=100;zoom.setAttribute('aria-label','全景局部放大');zoom.oninput=()=>svg.style.width=zoom.value+'%';const z=el('label','局部放大','zoom-range');z.append(zoom);stage.append(z);
  if(!v){info.append(el('p','此精选图片未提供点集或 3D。','muted'));return;}
  const picked=el('p','点击端点查看点号与坐标。','context-note');stage.append(picked);
  [v,v2].filter(Boolean).forEach((variant,vi)=>{const color=vi?'#e8b07a':'#a1d3aa',lookup=new Map(variant.pairs.map(p=>[p.source_pair_id,p]));
   const segment=(a,b)=>svg.append(svgNode('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:color,'stroke-width':2}));
   const line=(p,q)=>{if(Math.abs(p[0]-q[0])<=c.width/2){segment(p,q);return;}const left=p[0]<q[0]?p:q,right=p[0]<q[0]?q:p;segment(left,[right[0]-c.width,right[1]]);segment([left[0]+c.width,left[1]],right);};
   variant.connections.forEach(([a,b])=>['top','bottom'].forEach(ep=>line(lookup.get(a)[ep],lookup.get(b)[ep])));
   variant.pairs.forEach(p=>{line(p.top,p.bottom);['top','bottom'].forEach(ep=>{const [x,y]=p[ep],dot=svgNode('circle',{cx:x,cy:y,r:5,fill:color,tabindex:0,'aria-label':`${variant.name} ${p.display_index} ${ep}`});const pick=()=>picked.textContent=`${variant.name} · 点集 ${c.pointset_version} · 点号 ${p.display_index} · ${p.source_pair_id} · ${ep} x=${x}, y=${y} px`;dot.onclick=pick;dot.onkeydown=e=>{if(e.key==='Enter')pick();};svg.append(dot);const text=svgNode('text',{x:x+7,y:y-7});text.textContent=`${vi?'B':'A'}${p.display_index}`;svg.append(text);});});
  });
  info.append(el('p',`A：${v.name} · ${kind[v.kind]}${v2?'；B：'+v2.name+' · '+kind[v2.kind]:''}`),el('p',`点集版本：${c.pointset_version}；成员：${shown(v.member_ids)}；簇：${shown(v.cluster_ids)}`),el('p',sourceText(v.source_ids),'detail-note'));
  const rows=v.pairs.map(p=>({number:p.display_index,id:p.source_pair_id,top_x:p.top[0],top_y:p.top[1],bottom_x:p.bottom[0],bottom_y:p.bottom[1],connection:v.connections.filter(e=>e[0]===p.source_pair_id).map(e=>e[1]).join('、')}));
  table(info,[['number','点号'],['id','原始 ID'],['top_x','top x'],['top_y','top y'],['bottom_x','bottom x'],['bottom_y','bottom y'],['connection','连接到']].map(([key,label])=>({key,label,unit:key.includes('_')?'px':''})),rows,view);
  info.append(el('h3','3D 预览'),el('p','仅展示已提供的原始重建与拟合几何。数值扰动是独立输入，不代表已核验的机制结论。','detail-note'));
  if(v.preview){const launch=button('展开此点集的 3D 预览',()=>{launch.disabled=true;const f=el('iframe',undefined,'preview-frame');f.title=v.name+' · 3D';f.src=v.preview;info.append(f);});info.append(launch);}else info.append(el('p','3D 不可用：此点集未提供已计算的几何资源。','missing'));
 }
 select.onchange=draw;other.onchange=draw;draw();
}
function openCase(id,view){
 const token=++detailToken;lastDetail={type:'case',id,view};const body=drawer('图片详情 · '+id),im=data.images.find(i=>i.id===id);
 body.append(el('p','继承筛选：'+context(view),'context-note'),el('p',`${im.building} / ${im.room} · ${im.scene}`));
 const exact=data.views.find(v=>v.image===id&&dims.slice(0,4).every(k=>v[k]===view[k]));
 if(exact)body.append(button('查看此图片的统计切片',()=>{scope=Object.fromEntries(dims.map(k=>[k,exact[k]]));comparison='';render();}));
 else body.append(el('p','未提供单图汇总切片；下表保留当前模块中关联此图片的逐行统计。','muted'));
 const stats=el('details');stats.append(el('summary','该图统计与簇成员'));body.append(stats);
 const mod=view.modules[active];for(const chart of mod.charts){const rows=chart.rows.filter(r=>r.image_id===id);if(rows.length){stats.append(el('h3',chart.title));table(stats,[{key:'x',label:chart.x_label,unit:chart.x_unit},{key:'value',label:chart.y_label,unit:chart.unit},{key:'status',label:'状态'},{key:'denominator',label:'分母'},{key:'member_ids',label:'成员'},{key:'source_ids',label:'来源 ID'}],rows,view);}}
 for(const t of mod.tables){const rows=t.rows.filter(r=>r.image_id===id);if(rows.length){stats.append(el('h3',t.title));table(stats,t.columns,rows,view);}}
 const matches=casesFor(id,view);if(!matches.length){body.append(el('h3','未包含图像资源'),el('p','此图片的统计仍保留在结果中；当前离线发布清单未携带其全景、点集与 3D。','muted'));return;}
 const select=el('select');select.setAttribute('aria-label','精选案例版本');select.append(...matches.map(c=>option(c.id,c.id+' · 点集 '+c.pointset_version)));body.append(select);const resources=el('div');body.append(resources);const show=()=>{resources.replaceChildren();caseResources(resources,matches.find(c=>c.id===select.value),view,++detailToken).catch(fatal);};select.onchange=show;show();
}
try{
 data=window.RESEARCH_DATA;
 if(data?.schema_version!=='research_dashboard_v1'||!Array.isArray(data.views))throw new Error('缺少数据或 schema 版本不支持');
 for(const v of data.views)for(const [key,cat] of Object.entries(catalog))if(!data[cat].some(x=>x.id===v[key]))throw new Error('版本 / 方法 / 分类不一致');
 Object.entries(modules).forEach(([key,m],i)=>{const b=button('',()=>{active=key;render();});b.dataset.module=key;b.append(el('span',String(i+1).padStart(2,'0')),document.createTextNode(m.name));$('navigation').append(b);});
 dims.forEach((key,i)=>{const l=el('label',labels[i]),s=el('select');s.id='filter-'+key;s.onchange=()=>{scope[key]=s.value;dims.slice(i+1).forEach(k=>delete scope[k]);comparison='';render();};l.append(s);$('filters').append(l);});
 $('reset').onclick=()=>{scope={};comparison='';imageQuery='';$('image-search').value='';$('compare').checked=false;render();};
 $('compare').onchange=()=>{if(!$('compare').checked){comparison='';render();}else $('compare-view').hidden=false;};
 $('compare-view').onchange=()=>{comparison=$('compare-view').value;render();};
 $('image-search').oninput=e=>{imageQuery=e.target.value;imageList();};$('definitions').onclick=definitions;$('close-drawer').onclick=close;
 $('detail-reset').onclick=()=>{const d=lastDetail;if(d?.type==='case')openCase(d.id,d.view);else definitions();};
 document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
 $('side-release').textContent=data.release;$('footer-release').textContent='发布版本 '+data.release+' · 本地只读';
 render();
}catch(e){fatal(e);}
})();
