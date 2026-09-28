'use strict';
const ADOPTIONS=['','采用本组全部候选','部分采用，见逐图或备注','本轮暂不新增，保留研究记录','暂缓决定'];
const IMAGE_DECISIONS=['','采用','本轮暂不新增','暂缓'];
const PURPOSES=['同房多视角差异','同类型跨房间预测','局部细节表达差异','OOS或范围不明确情景','其他（见备注）'];
const blank=()=>({adoption:'',purposes:[],comment:'',defer:false,images:{}});
function validateReview(value,data){
  const stable=v=>JSON.stringify(v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,JSON.parse(stable(v[k]))])):Array.isArray(v)?v.map(x=>JSON.parse(stable(x))):v);
  if(value?.schema!==data.schema||stable(value.binding)!==stable(data.binding))throw Error('不是本轮版本，或候选成员／人数已变化；原记录未覆盖。');
  const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
  if(!object(value.decisions))throw Error('缺少审核记录');
  for(const [gid,d] of Object.entries(value.decisions)){
    const g=data.groups.find(g=>g.id===gid);
    if(!g||!object(d)||!ADOPTIONS.includes(d.adoption)||typeof d.comment!=='string'||typeof d.defer!=='boolean'||!Array.isArray(d.purposes)||d.purposes.some(p=>!PURPOSES.includes(p))||!object(d.images))throw Error('组判断字段不匹配');
    for(const [iid,a] of Object.entries(d.images))if(!g.images.some(i=>i.image_id===iid)||!object(a)||!IMAGE_DECISIONS.includes(a.decision)||typeof a.comment!=='string')throw Error('逐图判断不匹配');
  }
  return value.decisions;
}
if(typeof module!=='undefined')module.exports={validateReview,blank};
if(typeof document!=='undefined')(()=>{
  const D=window.COLLECTION_REVIEW,$=id=>document.getElementById(id),key='collection_adoption_review_20260921_v1';
  let state={},index=0,saveLocked=false;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const options=(choices,value)=>choices.map(c=>`<option value="${esc(c)}" ${c===value?'selected':''}>${esc(c||'未填写')}</option>`).join('');
  const hasContent=d=>d&&(d.adoption||d.comment.trim()||d.defer||d.purposes.length||Object.values(d.images).some(a=>a.decision||a.comment.trim()));
  const envelope=()=>({schema:D.schema,binding:D.binding,decisions:state,source_evidence:D.groups,exported_at:new Date().toISOString()});
  try{const saved=localStorage.getItem(key);if(saved)state=validateReview(JSON.parse(saved),D);}catch(e){saveLocked=true;$('notice').textContent='浏览器旧记录无法读取，未覆盖。可先在页面填写并导出；导入有效本轮备份后恢复自动保存。'+e.message;}
  function progress(){const n=Object.values(state).filter(hasContent).length;$('progress').textContent=`${index+1} / ${D.groups.length}`;$('group-status').textContent=`已有${n}组留下意见（含文字与暂缓，不代表全部采用）`;}
  function persist(){
    if(!saveLocked){try{localStorage.setItem(key,JSON.stringify(envelope()));$('save-status').textContent='已暂存于当前浏览器 · 请导出留档';}catch(e){$('notice').textContent='暂存失败，请立即导出审核：'+e.message;}}
    progress();
  }
  function save(){const g=D.groups[index],d=state[g.id]||blank();d.adoption=$('adoption').value;d.comment=$('comment').value;d.defer=$('defer').checked;d.purposes=[...$('purposes').querySelectorAll('input:checked')].map(e=>e.value);state[g.id]=d;persist();}
  function zoom(im){$('zoom-title').textContent=im.code;$('zoom-image').src=im.path;$('zoom-image').alt=im.code+' 原始全景';$('original-link').href=im.path;$('zoom').classList.remove('actual');$('zoom-scale').textContent='按原始尺寸查看';$('zoom').showModal();}
  function render(){
    const g=D.groups[index],d=state[g.id]||blank();$('group-select').value=g.id;$('previous').disabled=index===0;$('next').disabled=index===D.groups.length-1;
    $('group-title').textContent=`${g.priority}. ${g.id} · ${g.images.length}张候选`;$('question').textContent=g.question;$('group-count').textContent=`本轮拟新增 ${g.tasks} 份 · 下面是原图，没有新增AI视觉裁决。`;
    $('previous-note').textContent=g.previous.note||'此前没有非空评论；不代表没有问题，也不代表本轮已经同意采用。';
    $('previous-details').textContent=JSON.stringify({既有判断:g.previous,现有用途待定标签:g.holds,本组其他未安排视角:g.other_candidate_codes},null,2);
    $('cards').innerHTML=g.images.map(im=>{const a=d.images[im.image_id]||{decision:'',comment:''};return `<article class="model-card"><div class="model-header"><div><span class="eyebrow">ORIGINAL PANORAMA</span><h3>${esc(im.code)}</h3></div><button data-zoom="${esc(im.image_id)}" aria-label="放大${esc(im.code)}">⛶ 放大</button></div><button class="photo-button" data-zoom="${esc(im.image_id)}" aria-label="查看${esc(im.code)}原图"><img src="${esc(im.path)}" alt="${esc(im.code)} 原始全景"></button><div class="image-info"><p class="image-status">原图加载中…</p><p>${esc(im.scene)} · <span class="hint">${esc(im.oos)}</span></p><div class="counts"><span>冻结历史 <b>${im.history_n}</b></span><span>含当前提交 <b>${im.actual_n}</b></span><span>原必做补齐后 <b>${im.base_n}</b></span><span>本轮新增 <b>+${im.need}</b> → <b>${im.target}</b>人</span></div><details><summary>本图既有文字与人员安排</summary><pre>${esc(JSON.stringify({原采用记录:im.prior_image_record,既有文字:im.prior_notes,历史Manual人员:im.historical_workers,拟新增人员:im.proposed_workers},null,2))}</pre></details><label>本图例外／单独判断 <select data-image="${esc(im.image_id)}" data-field="decision">${options(IMAGE_DECISIONS,a.decision)}</select></label><label><span class="sr-only">${esc(im.code)}逐图备注</span><textarea data-image="${esc(im.image_id)}" data-field="comment" placeholder="选填：具体位置、例外或采用理由">${esc(a.comment)}</textarea></label></div></article>`;}).join('');
    $('cards').querySelectorAll('img').forEach(img=>{const status=img.closest('article').querySelector('.image-status');img.onload=()=>status.textContent=`原图 ${img.naturalWidth} × ${img.naturalHeight} · 点击放大`;img.onerror=()=>{status.textContent='原图加载失败，请勿据此裁决；可重新打开页面。';status.classList.add('error');};if(img.complete&&img.naturalWidth)img.onload();});
    $('adoption').value=d.adoption;$('comment').value=d.comment;$('defer').checked=d.defer;
    $('purposes').innerHTML=PURPOSES.map(p=>`<label><input type="checkbox" value="${esc(p)}" ${d.purposes.includes(p)?'checked':''}> ${esc(p)}</label>`).join('');progress();
  }
  function go(n){index=n;render();document.querySelector('.group-notes').scrollIntoView({behavior:'smooth',block:'start'});}
  $('group-select').innerHTML=D.groups.map(g=>`<option value="${g.id}">${g.priority}. ${g.id} · ${g.images.length}图 · +${g.tasks}份</option>`).join('');
  $('group-select').onchange=e=>go(D.groups.findIndex(g=>g.id===e.target.value));$('previous').onclick=()=>go(index-1);$('next').onclick=()=>go(index+1);
  $('save-next').onclick=()=>{save();if(index<D.groups.length-1)go(index+1);else $('save-status').textContent='已到最后一组，请导出审核文件。';};
  for(const id of ['adoption','defer','purposes'])$(id).addEventListener('change',save);$('comment').addEventListener('input',save);
  $('cards').addEventListener('click',e=>{const b=e.target.closest('[data-zoom]');if(b)zoom(D.groups[index].images.find(i=>i.image_id===b.dataset.zoom));});
  function imageEdit(e){const el=e.target;if(!el.dataset.image)return;const gid=D.groups[index].id,d=state[gid]||(state[gid]=blank());const a=d.images[el.dataset.image]||(d.images[el.dataset.image]={decision:'',comment:''});a[el.dataset.field]=el.value;persist();}
  $('cards').addEventListener('input',imageEdit);$('cards').addEventListener('change',imageEdit);
  $('layout').onclick=()=>{document.querySelector('main').classList.toggle('wide');$('layout').textContent=document.querySelector('main').classList.contains('wide')?'切换为双列对照':'切换为单列大图';};
  $('zoom-close').onclick=()=>$('zoom').close();$('zoom-scale').onclick=()=>{$('zoom').classList.toggle('actual');$('zoom-scale').textContent=$('zoom').classList.contains('actual')?'适应窗口':'按原始尺寸查看';};
  function exportFile(){const value=envelope();validateReview(value,D);const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='八组采集采用_我的审核.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('save-status').textContent='已发起JSON下载，请保留备份。';}
  $('export').onclick=exportFile;$('export-top').onclick=exportFile;
  $('import').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const value=JSON.parse(await f.text()),next=validateReview(value,D);if(Object.values(state).some(hasContent)&&!confirm('导入将替换当前本轮填写。请确认已导出需要保留的记录。继续导入？'))return;state=next;saveLocked=false;$('notice').textContent='';persist();render();$('save-status').textContent='导入成功，原文与本轮判断保持分开。';}catch(err){$('notice').textContent='导入失败，现有填写未改变：'+err.message;}finally{e.target.value='';}};
  $('legacy').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{$('legacy-text').textContent=JSON.stringify(JSON.parse(await f.text()),null,2);}catch(err){$('legacy-text').textContent='旧文件读取失败：'+err.message;}};
  render();
})();
