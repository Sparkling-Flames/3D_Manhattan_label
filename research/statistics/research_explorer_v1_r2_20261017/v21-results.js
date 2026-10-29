/* The snapshot is generated locally; no network request is needed. */
(() => {
  const data = window.V21_RESULTS;
  if (!data) { document.getElementById('counts').textContent = '结果快照不可用，请重新生成页面数据。'; return; }
  const releaseLabels={building:'本版仍在收尾。',computational_complete_pending_browser:'原主目标范围的计算和定向检查已完成；真实浏览器与下载验收待完成。'};
  const releaseStatus=releaseLabels[data.release?.status] || `版本状态：${data.release?.status || '未知'}。`;
  document.getElementById('releaseStatus').textContent = data.release?.full_mainline_including_other_targets_complete===false
    ? `${releaseStatus} 294池的可计算结构条件及TARGET新分类已完成；其它目标的正式人工难度和旧难度下游仍待接续。` : releaseStatus;
  document.getElementById('currentStatus').textContent = data.current ? `生成时全局 CURRENT 为 ${data.current.data_release}；快照时间 ${data.generated_utc}。` : '未取得全局版本收据。';
  const node = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
  const cellRow = (parent, cells) => { const tr = node('tr'); cells.forEach(x => tr.append(node('td', String(x)))); parent.append(tr); };
  const fmt = x => x == null ? '不可估' : Number(x).toFixed(2);
  const counts = document.getElementById('counts');
  const population=data.natural_receipt;
  document.getElementById('populationInventory').textContent=population ? `自然曲线共有 ${population.combined} 个 Manual 图片池：原有 ${population.original} 池使用 pooled256，新增 ${population.added} 池使用 new_space256。下面的 N≥30 图只显示满足该容量条件的子集。` : '自然曲线范围收据不可用。';
  [['库存作答', data.inventory.records], ['正式质量作答', data.inventory.quality], ['有正式质量作答的图片', data.inventory.images]].forEach(([label, value]) => {
    const c = node('div', undefined, 'card'); c.append(node('div', label), node('div', Number(value).toLocaleString('zh-CN'), 'number')); counts.append(c);
  });
  const ns = 'http://www.w3.org/2000/svg';
  const svgNode = (tag, attrs, text) => { const el = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, v)); if (text !== undefined) el.textContent = text; return el; };
  function renderCurve() {
    const scope = document.getElementById('curveScope').value;
    const points = data.natural.filter(x => x.scope === scope && x.k !== 2).concat(data.k2.filter(x => x.scope === scope)).sort((a,b) => a.k-b.k);
    const svg = document.getElementById('curve'), rows = document.getElementById('curveRows'); svg.replaceChildren(); rows.replaceChildren();
    const two = data.k2.find(x => x.scope === scope);
    document.getElementById('curveSupport').textContent = points.length ? `固定 N≥30；两人点 ${two ? two.images : 0} 张可评分图片。各人数支持见下方表格。` : '此范围暂无已保存的曲线结果。';
    document.getElementById('twoPersonDetail').textContent = two ? `两人：平均 Q ${fmt(two.q)}，共识未形成比例 ${fmt(two.failure * 100)}%；同路径 1→2 平均 ${fmt(two.pair12)} 分（${two.paired12.toLocaleString('zh-CN')} 条共同可评分路径），2→3 平均 ${fmt(two.pair23)} 分（${two.paired23.toLocaleString('zh-CN')} 条）。变化按图等权，两种路径支持可能不同；${data.k2_interval_receipt?'单点区间见下方。':'两人点抽样区间暂缺。'}` : '此范围暂无两人补算。';
    const intervalRows=document.getElementById('k2IntervalRows');intervalRows.replaceChildren();
    [['Q2','两人平均 Q'],['delta_1_2','同路径 1→2'],['delta_2_3','同路径 2→3']].forEach(([metric,label])=>{
      const d=(data.k2_intervals || []).filter(x=>x.scope===scope && x.metric===metric), p=d.find(x=>x.uncertainty==='paths_fixed_images'), b=d.find(x=>x.uncertainty==='buildings_fixed_path_estimates');
      const interval=x=>x && x.low!=null && x.high!=null?`[${fmt(x.low)}, ${fmt(x.high)}]`:'不可估';
      cellRow(intervalRows,[label, p?fmt(p.estimate):'不可估',interval(p),interval(b),p?`${p.images} / ${p.valid_paths.toLocaleString('zh-CN')}`:'无数据']);
    });
    if (!points.length) return;
    const vals = points.map(p => p.q), low = Math.floor(Math.min(...vals)/10)*10-5, high = Math.ceil(Math.max(...vals)/10)*10+5;
    const sx = k => 55+(k-1)*760/29, sy = q => 305-(q-low)*260/(high-low);
    svg.append(svgNode('line',{x1:55,y1:45,x2:55,y2:305,stroke:'#8ca0b4'}),svgNode('line',{x1:55,y1:305,x2:815,y2:305,stroke:'#8ca0b4'}));
    for (let v=Math.ceil(low/10)*10;v<=high;v+=10) { const y=sy(v); svg.append(svgNode('line',{x1:55,y1:y,x2:815,y2:y,stroke:'#e3eaf0'}),svgNode('text',{x:48,y:y+4,'text-anchor':'end',fill:'#53677c','font-size':12},String(v))); }
    [1,2,5,10,15,20,25,30].forEach(k => svg.append(svgNode('text',{x:sx(k),y:327,'text-anchor':'middle',fill:'#53677c','font-size':12},String(k))));
    svg.append(svgNode('text',{x:55,y:25,fill:'#53677c','font-size':13},'Q 均分'),svgNode('text',{x:815,y:345,'text-anchor':'end',fill:'#53677c','font-size':13},'进入人数'));
    let previous=null;
    points.forEach(p => {
      const x=sx(p.k),y=sy(p.q); if (previous && p.k===previous.k+1) svg.append(svgNode('line',{x1:sx(previous.k),y1:sy(previous.q),x2:x,y2:y,stroke:'#087e8b','stroke-width':2}));
      const circle=svgNode('circle',{cx:x,cy:y,r:p.k===2?5:3.3,fill:p.k===2?'#d87c29':'#087e8b'}); circle.append(svgNode('title',{},`${p.k} 人：Q ${fmt(p.q)}；${p.images} 图、${p.buildings} 建筑`)); svg.append(circle);
      cellRow(rows,[p.k,fmt(p.q),p.images,p.buildings,p.k===2?'独立两人补算':'自然曲线',p.failure==null?'不可估':`${fmt(p.failure*100)}%`,p.failure_images==null?'无有效记录':`${p.failure_images} / ${p.failure_eligible}`]);previous=p;
    });
  }
  document.getElementById('curveScope').addEventListener('change',renderCurve);renderCurve();
  data.variance.forEach(x => cellRow(document.getElementById('varianceRows'),[x.method==='DSTRUCT_K3'?'原标签，新评分':'v2.1 标签，新评分',`${fmt(x.share*100)}%`,x.panels,`${x.images} / ${x.buildings}`]));
  const labels={turn_deficit:'少转折数量 / MSE',reduced:'是否简化 / MSE',Q:'Q / MAE'};
  data.difficulty.forEach(x => cellRow(document.getElementById('difficultyRows'),[labels[x.outcome],fmt(x.old),fmt(x.new),`${fmt(x.improvement)}%`,`${x.better} / ${x.buildings}`]));
  const room=data.room_type && data.room_type.reported_support_comparison.find(x=>x.metric==='Q');
  document.getElementById('roomTypeResult').textContent=room?`${room.images} 图：几何模型 Q 平均绝对误差 ${fmt(room.baseline_MAE)}，加入用途后 ${fmt(room.purpose_MAE)}；数值越低越好。`:'当前没有可展示的独立核对结果。';
  const strict=document.getElementById('strictStatus');
  [['confirm','正向'],['reverse_confirm','反向']].forEach(([key,label])=>{const s=data.strict[key];strict.append(node('p',s ? `${label}：${s.complete?'事件测量完成':'进行中'}，已测量 ${s.measured.toLocaleString('zh-CN')} / 登记 ${s.registered.toLocaleString('zh-CN')} 个事件。` : `${label}：尚无完成收据。`));});
  const statuses=document.getElementById('moduleStatus');
  const phaseLabels={selection_heldout_building:'选择阶段楼外',within_building_extension:'楼内扩展'};
  (data.strict_comparison || []).forEach(r=>cellRow(document.getElementById('strictRows'),[phaseLabels[r.phase] || r.phase,`${r.n} / ${r.m} (${fmt(100*Number(r.m)/Number(r.n))}%)`,`${r.valid_images} / ${r.valid_buildings}`,fmt(r.within_building_equal),fmt(r.cross_building_equal),fmt(r.gap_building_equal),fmt(r.CA_building_equal),fmt(r.CB_building_equal)]));
  [['D10形成链',data.d10_formation?.complete?'形成、有限配比、选队与结构角色比较已完成':'待完成'],['当前同房统计',data.current_same_room_finite?.all_complete && data.current_same_room_large?.complete?'有限面板与大块事件统计已完成':'统计收尾中']].forEach(([label,status])=>statuses.append(node('p',`${label}：${status}`)));
  const policyDone=Object.values(data.current_policy_results || {}).filter(Boolean).length;
  const statusRows=[['原答评分',data.inventory?'已完成评分与资格统计':'未完成'],['描述与人员画像',data.descriptive && data.descriptive.tables?.personnel_profiles?'已完成描述统计与人员画像':'待完成'],['自然曲线',data.natural_receipt?'已接合原有与新增范围':'未完成'],['两人自然路径补算',data.k2_interval_receipt?'已完成独立补充及单点区间':data.k2_receipt?'已完成独立补充；区间待完成':'未完成'],['构成方差',data.variance_receipt?'固定面板与新旧标签比较已完成':'未完成'],['连续几何比较',data.difficulty_receipt?'已完成；三档保留建议':'未完成'],['同用途不同房间',data.room_type?'楼外结果的原答与误差独立核对已完成':'独立核对待完成'],['固定融合方法面板',data.fusion_common?.common_metric_support_unchanged?`已完成；${data.fusion_common.pools} 池、${data.fusion_common.teams} 队`:'待完成'],['历史冻结策略',data.frozen_policy && data.frozen_policy.old_metric_parity?'旧角色、旧路径重评分已完成':'待完成'],['当前标签策略',data.current_policy_design?`已登记设计；${policyDone} / 2 个范围有统计收据`:'待登记'],['历史同房设计',data.same_room?'已恢复历史设计输入；结果以专门收据为准':'待确认'],['当前标签同房',data.current_same_room?.complete?'团队端点已完成；比较结果以单独收据为准':'团队端点尚未完成']];
  const ul=node('ul');statusRows.forEach(([title,status])=>ul.append(node('li',`${title}：${status}`)));statuses.append(ul);
})();
