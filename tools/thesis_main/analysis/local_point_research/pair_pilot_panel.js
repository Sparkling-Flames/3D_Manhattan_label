// Six-image pilot inside the existing Studio. Preview candidates never modify geometry.
window.addEventListener('DOMContentLoaded',()=>{
  const rows=window.POINT_PAIR_PILOT, schema='point_pair_pilot_20260919_v1';
  let decisions={}, current=0, generation=0;
  const panel=document.createElement('section');panel.className='adj';panel.id='point-pair-pilot';
  panel.innerHTML=`<h2>六图点对初验 · 待你确认</h2>
    <select id="ppCase"></select><button id="ppPrev">上一项</button><button id="ppNext">下一项</button>
    <p id="ppPurpose"></p><p id="ppObservation"></p><p id="ppOriginal"></p>
    <label><input id="ppEnabled" type="checkbox" checked>在原全景／局部窗口显示候选点对</label>
    <p>红色为人员A，蓝色为人员B。连线只表示候选上下对应，不是墙连接；下方3D保持原历史重建。点号沿用有效点数组。</p>
    <label>人员A配对预览 <select id="ppA"></select></label><label>人员B配对预览 <select id="ppB"></select></label>
    <label>显示 <select id="ppSide"><option value="both">两人叠加</option><option value="a">仅人员A</option><option value="b">仅人员B</option></select></label>
    <label>局部查看 <select id="ppFocus"></select></label><button id="ppGo">定位本项原图</button>
    <p id="ppBaseline"></p><p id="ppMetric"></p><div id="ppTable"></div>
    <details><summary>具体候选配对与匹配证据</summary><pre id="ppDetails" style="white-space:pre-wrap"></pre></details>
    <p>预览选择不等于接受候选。以下是你的判断，默认空白；可以只写文字。</p>
    <label>A配对 <select id="ppPairA"><option value="">未填写</option><option>接受当前候选</option><option>需要修改</option><option>不能判断</option></select></label>
    <label>B配对 <select id="ppPairB"><option value="">未填写</option><option>接受当前候选</option><option>需要修改</option><option>不能判断</option></select></label>
    <label>两份整图表达 <select id="ppRelation"><option value="">未填写</option><option>可视为相近</option><option>应分开保留差异</option><option>不能判断</option></select></label>
    <label><input id="ppDefer" type="checkbox">暂缓</label><p><textarea id="ppNote" rows="4" style="width:98%" placeholder="请注明位置、点号、配对修改或研究意见"></textarea></p>
    <button id="ppExport">导出六图点对审核</button><label>导入本批审核 <input id="ppImport" type="file" accept=".json"></label><p id="ppStatus" role="status"></p>`;
  const style=document.createElement('style');style.textContent='#point-pair-pilot table{border-collapse:collapse;margin:12px 0}#point-pair-pilot td,#point-pair-pilot th{padding:6px 14px;border:1px solid #ccd7d2;text-align:left}';panel.append(style);
  document.querySelector('main').prepend(panel);
  const el=id=>document.getElementById(id),row=()=>rows[current],fmt=x=>x===null?'点数不同：不计算严格距离':Number(x).toFixed(3)+'°';
  rows.forEach((r,i)=>el('ppCase').add(new Option(`${i+1}. ${r.code} · ${r.condition} · ${r.worker_a} / ${r.worker_b}`,i)));
  const fields=['PairA','PairB','Relation','Note'];
  function validate(value){
    if(value.schema!==schema||!value.decisions||Array.isArray(value.decisions)||typeof value.decisions!=='object')throw Error('不是六图点对审核文件');
    for(const [key,d] of Object.entries(value.decisions)){
      const r=rows.find(r=>r.key===key);
      if(!r||!d||fields.some(f=>typeof d[f]!=='string')||typeof d.defer!=='boolean')throw Error('身份或文字字段不匹配');
      for(const f of fields.slice(0,3))if(![...el('pp'+f).options].some(o=>o.value===d[f]))throw Error('判断选项不匹配');
      for(const side of ['a','b'])if(!Number.isInteger(d[side+'_candidate'])||!r['candidates_'+side][d[side+'_candidate']])throw Error('候选身份不匹配');
    }return value.decisions;
  }
  function persist(){try{localStorage.setItem(schema,JSON.stringify({schema,decisions}));el('ppStatus').textContent='已暂存；完成后请导出JSON。';}catch{el('ppStatus').textContent='暂存不可用，请导出JSON。';}}
  function save(){decisions[row().key]={...Object.fromEntries(fields.map(f=>[f,el('pp'+f).value])),defer:el('ppDefer').checked,a_candidate:Number(el('ppA').value),b_candidate:Number(el('ppB').value)};persist();}
  const enabled=()=>el('ppEnabled').checked&&dataset.cases[currentCase]?.image_id===row().image_id;
  function strokes(ctx){
    for(const side of ['a','b']){
      if(el('ppSide').value!=='both'&&el('ppSide').value!==side)continue;
      const r=row(),points=r['points_'+side],candidate=r['candidates_'+side][Number(el(side==='a'?'ppA':'ppB').value)];
      ctx.strokeStyle=side==='a'?'#ef4255':'#00b9e5';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=1.5;ctx.setLineDash(side==='a'?[]:[5,3]);
      for(const [i,j]of candidate.pairs){const a=points[i-1],b=points[j-1],dx=((b[0]-a[0]+1536)%1024)-512;
        for(const offset of [-1024,0,1024]){ctx.beginPath();ctx.moveTo(a[0]+offset,a[1]);ctx.lineTo(a[0]+dx+offset,b[1]);ctx.stroke();}}
      ctx.setLineDash([]);ctx.font='12px Segoe UI';ctx.textAlign='left';
      points.forEach((p,i)=>{ctx.beginPath();ctx.arc(p[0],p[1],3.2,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=.6;ctx.stroke();ctx.fillText(side.toUpperCase()+(i+1),p[0]+4,p[1]-4);});
    }
  }
  const originalPanorama=drawPanorama,originalCrop=drawCrop;
  drawPanorama=function(){
    if(!enabled()||!originalImage){originalPanorama();return;}
    const canvas=el('panorama');canvas.width=2048;canvas.height=1024;const ctx=canvas.getContext('2d');ctx.scale(2,2);ctx.drawImage(originalImage,0,0,1024,512);strokes(ctx);
  };
  drawCrop=function(){
    if(!enabled()||!originalImage){originalCrop();return;}
    document.querySelector('.selection-block').classList.add('has-selection');
    const canvas=el('crop'),ctx=canvas.getContext('2d'),r=row(),f=el('ppFocus').value;
    const p=f==='region'?r.focus:r['points_'+f[0]][Number(f.slice(1))];const zoom=canvas.width/160,left=p[0]-80,top=p[1]-canvas.height/zoom/2;
    ctx.clearRect(0,0,canvas.width,canvas.height);ctx.save();ctx.scale(zoom,zoom);ctx.translate(-left,-top);
    for(const offset of [-1024,0,1024]){ctx.drawImage(originalImage,offset,0,1024,512);ctx.save();ctx.translate(offset,0);strokes(ctx);ctx.restore();}ctx.restore();
  };
  function render(){
    const r=row(),ai=Number(el('ppA').value),bi=Number(el('ppB').value),c=r.comparisons.find(c=>c.a_candidate===ai&&c.b_candidate===bi),b=r.baseline;
    el('ppBaseline').textContent=`旧墙带1−IoU：${b.legacy_mask_distance?.toFixed(4)??'不可用'}；稳定OSPA：${fmt(b.stable_ospa1)}；逐点覆盖H：${fmt(b.hausdorff)}。冻结OSPA6：${b.frozen_membership.OSPA1_6?'同簇':'异簇'}；H9：${b.frozen_membership.Hausdorff_9?'同簇':'异簇'}。`;
    el('ppMetric').textContent=`上下分别一一匹配：${fmt(c.separate_bottleneck_deg)}；绑定点对一一匹配：${fmt(c.bound_bottleneck_deg)}。本批同点数例两者相同，尚无绑定额外优势证据。`;
    const table=document.createElement('table');table.innerHTML='<thead><tr><th>半径</th><th>上点匹配数</th><th>下点匹配数</th><th>绑定匹配对数</th><th>严格相容</th></tr></thead>';
    const body=document.createElement('tbody');for(const x of c.radii){const tr=document.createElement('tr');for(const v of [x.radius+'°',x.top_matched,x.bottom_matched,x.bound_matched_pairs,x.strict_compatible?'是':'否']){const td=document.createElement('td');td.textContent=v;tr.append(td);}body.append(tr);}table.append(body);el('ppTable').replaceChildren(table);
    el('ppDetails').textContent=JSON.stringify({A:r.candidates_a[ai],B:r.candidates_b[bi],matching:c.example_matching},null,2);
    drawPanorama();drawCrop();
  }
  async function locate(){
    const ticket=++generation,r=row(),i=dataset.cases.findIndex(c=>c.image_id===r.image_id);
    el('history-mode').value=r.condition==='semi'?'Semi':'Manual';await chooseCase(i);
    if(ticket!==generation)return;
    const v=dataset.cases[i].variants.findIndex(v=>v.source.canonical_annotation_id===r.id_a);
    if(v>=0){el('variant-select').value=v;chooseVariant(v,true);}
    document.querySelector('.workspace').classList.remove('hide-inspector');el('panorama-panel').open=true;render();
  }
  function show(){
    const r=row(),d=decisions[r.key]||{};el('ppCase').value=current;el('ppPurpose').textContent=r.purpose;el('ppObservation').textContent='视觉初判（待你确认）：'+r.observation;
    el('ppOriginal').textContent=r.user_original.length?'此前原文：'+r.user_original.map(x=>JSON.stringify(x.answer)).join('；'):'此人员组合没有已有用户裁决；不借用其他组合的意见。';
    for(const side of ['a','b']){const select=el(side==='a'?'ppA':'ppB');select.replaceChildren(...r['candidates_'+side].map((c,i)=>new Option(c.name,i)));select.value=d[side+'_candidate']??0;}
    el('ppFocus').replaceChildren(new Option('重点局部','region'),...['a','b'].flatMap(side=>r['points_'+side].map((p,i)=>new Option(side.toUpperCase()+(i+1),side+i))));
    fields.forEach(f=>el('pp'+f).value=d[f]||'');el('ppDefer').checked=!!d.defer;locate().catch(e=>el('ppStatus').textContent=e.message);
  }
  fields.forEach(f=>el('pp'+f).addEventListener('input',save));el('ppDefer').onchange=save;
  for(const id of ['ppA','ppB'])el(id).onchange=()=>{if(decisions[row().key]){el(id==='ppA'?'ppPairA':'ppPairB').value='';save();}render();};
  for(const id of ['ppEnabled','ppSide','ppFocus'])el(id).onchange=render;
  el('ppGo').onclick=()=>locate().then(()=>el('panorama-panel').scrollIntoView({behavior:'smooth',block:'center'})).catch(e=>el('ppStatus').textContent=e.message);
  el('ppCase').onchange=()=>{current=Number(el('ppCase').value);show();};
  for(const [id,delta]of [['ppPrev',-1],['ppNext',1]])el(id).onclick=()=>{current=Math.max(0,Math.min(rows.length-1,current+delta));show();};
  el('ppExport').onclick=()=>{const blob=new Blob([JSON.stringify({schema,exported_at:new Date().toISOString(),decisions,evidence:rows},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='六图点对_我的审核.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  el('ppImport').onchange=async()=>{const file=el('ppImport').files[0];if(!file)return;try{const incoming=validate(JSON.parse(await file.text()));if(Object.keys(decisions).length&&!confirm('将替换本批当前审核，请先导出未保存文字。继续？'))return;decisions=incoming;persist();show();}catch(e){el('ppStatus').textContent='未导入：'+e.message;}finally{el('ppImport').value='';}};
  try{const saved=localStorage.getItem(schema);if(saved)decisions=validate(JSON.parse(saved));}catch(e){el('ppStatus').textContent='暂存未读取：'+e.message;}
  document.addEventListener('studio-case',()=>{if(enabled()){const note=el('history-note');if(note)note.textContent+='；本批点对候选仅在主全景预览，历史分区/3D未更改。';}});
  show();
});
