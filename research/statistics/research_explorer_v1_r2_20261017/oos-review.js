/* Browser review drafts are separate from frozen research evidence. */
(() => {
 'use strict';
 const data=window.OOS_REVIEW_DATA, images=data.images, key='hohonet-oos-review-v1', $=id=>document.getElementById(id);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const factors=['斜墙／平面非正交','斜顶','多标高天花板','多标高地面／楼梯挑空','曲面边界','原因未定'];
 const descriptions={
  '斜顶':['天花板是斜的','顶面本身有坡度，一边高、一边低；不是全景照片里线条看起来弯曲。'],
  '多标高天花板':['天花板有两层或多个高度','例如吊顶与主天花板不在同一高度；与整片天花板倾斜分开记录。'],
  '多标高地面／楼梯挑空':['地面有高低层，或连着楼梯','例如台阶、上层平台、楼梯井，使画面里出现不同高度的地面。'],
  '曲面边界':['弧形或连续转折的玻璃边界','包括连续转向的多片玻璃；不强行区分光滑弧面与多片折线。全景照片造成的弯曲不算。'],
  '原因未定':['暂时看不清／不能判断','可以先写下疑问，不用勉强选择。'],
  '斜墙／平面非正交':['旧草稿曾选“斜墙”（请核对）','目前已确认斜墙为x8-01、x8-09及b8-19。此项仅为保留你的旧草稿。']
 };
 const slantedWall=i=>(i.room==='G231'&&i.code.startsWith('x8'))||i.code==='b8cTxDM8gDG-19';
 let drafts={},current,storageIssue='';
 function validate(obj){
  if(!obj||obj.schema!=='oos_review_drafts_v1'||obj.release!=='v2'||!obj.records||typeof obj.records!=='object'||Array.isArray(obj.records))throw Error('文件不是此工作台的v2复核记录。');
  for(const [id,r] of Object.entries(obj.records)){
   if(!images.some(i=>i.id===id)||!r||!['未复核','需讨论','已复核'].includes(r.status)||typeof r.extent!=='string'||typeof r.note!=='string'||typeof r.updated_at!=='string')throw Error('图片身份或记录字段不匹配，未导入。');
   for(const field of ['visible','target'])if(!Array.isArray(r[field])||r[field].some(v=>!factors.includes(v)))throw Error('结构因素不匹配，未导入。');
  }
  return obj.records;
 }
 try{const saved=localStorage.getItem(key);if(saved)drafts=validate(JSON.parse(saved));}catch(e){storageIssue='本地记录未能读取：'+e.message+' 请保留导出备份。';}
 function envelope(){return {schema:'oos_review_drafts_v1',release:'v2',exported_at:new Date().toISOString(),records:drafts};}
 function status(s){$('status').textContent=s;}
 function progress(i){return drafts[i.id]?.status||'未复核';}
 function progressLabel(i){return {'未复核':'还没填写','需讨论':'暂时不能判断','已复核':'已填写'}[progress(i)];}
 function list(){
  const q=$('search').value.toLowerCase(),p=$('progress').value;
  const shown=images.filter(i=>(!q||[i.code,i.room,i.candidate].join(' ').toLowerCase().includes(q))&&(!p||progress(i)===p));
  $('count').textContent=`显示 ${shown.length} / 28 图 · 已填写 ${images.filter(i=>progress(i)==='已复核').length} 图`;
  $('image-list').innerHTML=shown.map(i=>`<button class="review-item" data-image="${esc(i.id)}" aria-current="${i.id===current?.id}"><img loading="lazy" src="${esc(i.photo)}" alt="${esc(i.code)}原图"><strong>${esc(i.code)}</strong><small>${esc(i.room)} · ${esc(progressLabel(i))}</small><small>${esc(i.candidate)}</small></button>`).join('')||'<p>没有符合筛选的图片。</p>';
 }
 function fields(name,selected){return factors.filter(v=>v!==factors[0]||selected.includes(v)&&!slantedWall(current)).map(v=>`<label class="factor-option"><input type="checkbox" name="${name}" value="${esc(v)}" ${selected.includes(v)?'checked':''}><span><b>${esc(descriptions[v][0])}</b><small>${esc(descriptions[v][1])}</small></span></label>`).join('');}
 function selection(id,answer){
  const a=current.answers.find(x=>x.id===answer);
  WorkbenchGeometry.mount($(id),{photo:current.photo},a?{points:a.points,raw_points:a.raw_points,order_status:a.order_status}:null,null);
 }
 function render(){
  const id=new URLSearchParams(location.hash.slice(1)).get('image');current=images.find(i=>i.id===id)||images[0];
  const r=drafts[current.id]||{status:'未复核',visible:[],target:[],extent:'',note:''};
  const opts='<option value="">只看原图</option>'+current.answers.map(a=>`<option value="${esc(a.id)}">${esc(a.worker)} · ${esc(a.condition)} · ${esc(a.disposition)} · ${esc(a.id)}</option>`).join('');
  const related=images.filter(i=>i.room===current.room&&i.id!==current.id&&i.room!=='未登记');
  const d=current.diagnostic;
  const diagnostic=d?`<p><b>新批Manual诊断：</b>${d.inventory_n}份记录，现有几何分析资格${d.pool_n}份；<span title="同图两份底面的对称差面积/两份自身并集面积，再对人员对平均。0重合，1不重合；不是与GT比较，也不测顶面。">原答底面分歧 ${d.R_pair_union_mean===null?'沿用暂停，未计算':d.R_pair_union_mean.toFixed(3)}</span>；记录时间中位数 ${d.source_seconds_median?.toFixed(0)??'缺失'}秒；选择不可标 ${d.scope_out_n}/${d.scope_normalized_n}。这些数值不评价谁正确。</p>`:'';
  $('review').innerHTML=`<section class="panel"><h2>${esc(current.code)} <small> · ${esc(current.room)}</small></h2><p><b>当前采用因素：</b>${esc(current.candidate)}</p><p>${esc(current.question)}</p>${slantedWall(current)?'<p><b>已确认：本图归为斜墙，无需再勾选，角度不确定。当前共3图：x8-01、x8-09（同房）及b8-19（玻璃斜段，范围仍需说明）。</b></p>':''}${diagnostic}<p class="hint">来源状态：${esc(current.basis)}。下方浏览器草稿独立保存；旧草稿不会覆盖上方采用记录。</p><div class="actions">${related.map(i=>`<a href="#image=${encodeURIComponent(i.id)}">同房 ${esc(i.code)}</a>`).join(' ')} <a href="index.html#release=v2&module=images&image=${encodeURIComponent(current.id)}&f_image=${encodeURIComponent(current.id)}" target="_blank" rel="noopener">完整作答、参考与来源 ↗</a><a href="${esc(current.photo)}" target="_blank" rel="noopener">打开原图 ↗</a></div></section>
  <section class="panel"><h2>原图与人员标注对照</h2><p class="hint">左右可选不同人的标注进行对照；可放大，也可切换俯视图和立体线框。没有确认点的连接顺序时只显示点。OOS超出标注标准；GT可能为满足曼哈顿约束而偏离真实边界，这里不以GT判定人员对错。</p><div class="review-pair"><section><label>左侧作答<select id="answer-a">${opts}</select></label><div id="view-a"></div></section><section><label>右侧作答<select id="answer-b">${opts}</select></label><div id="view-b"></div></section></div></section>
  <section class="panel"><h2>本图复核记录</h2><p class="hint">直接勾选这张图的情况，可多选。选完自动保存，不用再点“已复核”。其他问题写在下方即可。</p><form id="review-form"><fieldset><legend>这张图有什么情况？</legend>${fields('visible',r.visible)}</fieldset><details><summary>可选：说明要标哪一部分（有范围争议时再填）</summary><p class="hint">例如照片拍到了楼梯，但只要求标下面的房间。这里说明真正要标的部分包含哪些情况。</p><fieldset><legend>要标的部分包含什么？</legend>${fields('target',r.target)}</fieldset><label>要标哪里、不标哪里？<textarea id="extent" placeholder="例如：只标下面的房间，不包含楼梯">${esc(r.extent)}</textarea></label></details><label>补充说明（选填）<textarea id="note">${esc(r.note)}</textarea></label><p class="hint">自动保存修改；通过顶部按钮导出，后续再统一接回研究记录。</p></form></section>`;
  $('answer-a').onchange=e=>selection('view-a',e.target.value);$('answer-b').onchange=e=>selection('view-b',e.target.value);
  selection('view-a','');selection('view-b','');
  $('review-form').addEventListener('input',save);$('review-form').addEventListener('change',save);list();
 }
 function save(){
  const chosen=name=>{const values=Array.from(document.querySelectorAll(`input[name="${name}"]:checked`),el=>el.value);if(slantedWall(current)&&(name==='visible'||drafts[current.id]?.[name]?.includes(factors[0])))values.unshift(factors[0]);return values;};
  drafts[current.id]={status:chosen('visible').includes('原因未定')?'需讨论':'已复核',visible:chosen('visible'),target:chosen('target'),extent:$('extent').value,note:$('note').value,updated_at:new Date().toISOString()};
  try{localStorage.setItem(key,JSON.stringify(envelope()));status('已自动保存到当前浏览器；建议导出备份。');}catch(e){status('浏览器保存失败，记录仍在当前页面，请立即导出备份。');}list();
 }
 $('image-list').onclick=e=>{const b=e.target.closest('[data-image]');if(b)location.hash='image='+encodeURIComponent(b.dataset.image);};
 $('search').oninput=list;$('progress').onchange=list;window.addEventListener('hashchange',render);
 $('export').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(envelope(),null,2)],{type:'application/json'})),a=document.createElement('a');a.href=u;a.download='OOS复核记录_'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1500);status('已导出全部浏览器复核记录；原始研究数据未改变。');};
 $('import').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;const incoming=validate(JSON.parse(await f.text()));const conflicts=Object.keys(incoming).filter(id=>drafts[id]&&JSON.stringify(drafts[id])!==JSON.stringify(incoming[id]));if(conflicts.length&&!confirm(`有 ${conflicts.length} 张图片已有不同的本地记录，是否用导入记录覆盖？`))return;drafts={...drafts,...incoming};try{localStorage.setItem(key,JSON.stringify(envelope()));status('已导入记录并保存到浏览器。');}catch{status('已导入当前页面，但浏览器保存失败，请导出备份。');}render();}catch(err){status('导入失败：'+err.message);}finally{e.target.value='';}};
 render();if(storageIssue)status(storageIssue);
})();
