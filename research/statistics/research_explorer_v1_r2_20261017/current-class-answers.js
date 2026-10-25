/* Current method/fold labels select saved answers, never a new score or team. */
window.CurrentClassAnswers=(()=>{
 'use strict';
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const option=(v,t)=>`<option value="${esc(v)}">${esc(t)}</option>`;
 function imageChoices(images,records,fold,worker){
  const supported=new Set(records.filter(r=>r.condition==='manual'&&(!worker||r.worker_id===worker)).map(r=>r.image_id));
  return images.filter(i=>!i.flags?.oos&&i.scene?.doorway_status==='none'&&(fold==='ALL'||i.building_id===fold)&&supported.has(i.image_id));
 }
 function answers(detail,row,worker){
  const members=new Set(row?.workers||[]);
  return detail.annotations.filter(a=>a.condition==='manual'&&members.has(a.worker_id)&&(!worker||a.worker_id===worker)).sort((a,b)=>a.worker_id.localeCompare(b.worker_id)||a.object_id.localeCompare(b.object_id));
 }
 async function mount(host,ctx,data){
  const records=await ctx.table('quality__shared_records');if(!ctx.isCurrent())return;
  host.innerHTML=`<h2>同一张原图：这些人实际怎样标？</h2><p>选择方法与历史范围后，用同一图的完整Manual原答核对类间表达。ALL仅作描述；选择楼外范围时只列该目标建筑。这里不重新生成团队，不将单例当作类的总体正确率。</p><p>ALL首次默认打开已核机制图jh-12的原图，RFUSE可切换B6-47；这里选取的左右个人原答只是可查看的表达，不代表机制实验里的整支团队。<a href="#release=v2&module=personnel_main&tab=5">查看两例精确团队、支持票与正反效果</a>。</p><div class="toolbar"><label>从名单选人<select id="classAnswerWorker"></select></label><label>真实图片<select id="classAnswerImage"></select></label><label>左侧类别<select id="classAnswerGroupA"></select></label><label>右侧类别<select id="classAnswerGroupB"></select></label></div><p id="classAnswerStatus" class="scope-label" role="status"></p><div class="split equal"><section><label>左侧完整原答<select id="classAnswerA"></select></label><div id="classAnswerViewA"></div></section><section><label>右侧完整原答<select id="classAnswerB"></select></label><div id="classAnswerViewB"></div></section></div><p class="scope-label">默认各取按匿名ID排列的第一份可见原答，不按分数挑选。连线采用保存点对与源环序；未确认环序由几何组件注明。图上点号属于各人的数组，不是跨人角点身份。未知人员可查看，不能补类；可查看原答不代表正式质量可用，既有参考问题或暂停不因此恢复。</p><div class="actions"><a href="#release=v2&module=personnel_main&tab=1">下一步：看实际混合配比与格内成员波动</a><a href="#release=v2&module=personnel_main&tab=2">再看同类换人／跨类替换的总体效果</a></div>`;
  const $=id=>host.querySelector('#'+id),worker=$('classAnswerWorker'),image=$('classAnswerImage'),ga=$('classAnswerGroupA'),gb=$('classAnswerGroupB'),sa=$('classAnswerA'),sb=$('classAnswerB');
  let rows=[],method='',fold='',detail=null,serial=0;
  function draw(){
   for(const [side,select] of [['A',sa],['B',sb]]){
    const a=detail?.annotations.find(a=>a.object_id===select.value),slot=$('classAnswerView'+side);
    if(a)window.WorkbenchGeometry.mount(slot,detail,a,null);
    else slot.innerHTML='<p class="placeholder">本图没有该类当前可选原答；保留缺失，不用他人代替。</p>';
   }
  }
  function refreshAnswers(){
   for(const [group,select,w] of [[ga,sa,worker.value],[gb,sb,'']]){
    const list=answers(detail,rows.find(r=>r.class_id===group.value),w);
    select.innerHTML=list.map(a=>option(a.object_id,`${a.worker_id} · ${Math.floor((a.points||a.raw_points||[]).length/2)}对点`)).join('');
   }
   const meta=ctx.assets.images.find(i=>i.image_id===image.value);
   $('classAnswerStatus').textContent=`${method} · ${fold==='ALL'?'ALL整体描述':'排除建筑 '+fold}；当前 ${meta?.image_code||'无图片'}。左侧${sa.options.length}份、右侧${sb.options.length}份可选原答。评分、配比和替换结果分别使用其保存实验标签。`;
   draw();
  }
  async function loadImage(){
   const token=++serial;detail=null;sa.innerHTML=sb.innerHTML='';draw();
   if(!image.value){$('classAnswerStatus').textContent='当前建筑／人员没有相应普通Manual原答；不补示例。';return;}
   $('classAnswerStatus').textContent='正在读取完整原答…';
   try{const saved=await ctx.imageDetail(image.value);if(token!==serial||!ctx.isCurrent())return;
    if(saved.image_id!==image.value)throw Error('图片身份不一致');detail=saved;refreshAnswers();
   }catch(e){if(token===serial&&ctx.isCurrent())$('classAnswerStatus').textContent='原答读取失败：'+e.message;}
  }
  function refreshImages(){
   const previous=image.value,list=imageChoices(ctx.assets.images,records,fold,worker.value);
   image.innerHTML=list.map(i=>option(i.image_id,`${i.image_code} · ${i.difficulty?.label||'难度未记录'}`)).join('');
   if(list.some(i=>i.image_id===previous))image.value=previous;else{const code=method.startsWith('RFUSE')?'B6ByNegPMKs-47':'jh4fc5c5qoQ-12',saved=list.find(i=>i.image_code===code);if(saved)image.value=saved.image_id;}
   return loadImage();
  }
  async function focus(person){
   if(!rows.some(r=>r.workers.includes(person)))return;
   worker.value=person;ga.value=rows.find(r=>r.workers.includes(person)).class_id;await refreshImages();
  }
  function update(selectedMethod,selectedFold){
   method=selectedMethod;fold=selectedFold;rows=data.rosters.filter(r=>r.method===method&&r.fold===fold);
   const people=rows.flatMap(r=>r.workers.map(w=>[w,`${w} · ${r.class_id}`]));
   worker.innerHTML=option('','全部可见人员')+people.sort((a,b)=>a[0].localeCompare(b[0])).map(x=>option(...x)).join('');
   const groups=rows.map(r=>option(r.class_id,data.role(r,rows)));
   ga.innerHTML=gb.innerHTML=groups.join('');gb.value=rows.filter(r=>r.known).at(-1)?.class_id||rows.at(-1)?.class_id||'';
   return refreshImages();
  }
  worker.onchange=()=>worker.value?focus(worker.value):refreshImages();image.onchange=loadImage;
  ga.onchange=()=>{worker.value='';refreshImages();};gb.onchange=()=>{if(detail)refreshAnswers();};sa.onchange=sb.onchange=draw;
  return {update,focus};
 }
 return {mount,imageChoices,answers};
})();
