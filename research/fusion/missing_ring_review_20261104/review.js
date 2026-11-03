'use strict';
document.title='融合节点人工排序';
document.querySelector('h1').textContent='融合节点人工排序';
document.querySelector('.order-editor p').textContent='保留所有节点、坐标和票数，只调整连接顺序。编号不代表环序；默认不显示闭合布局。';
document.querySelector('.pano-caption').textContent='原图与当前点对；预览连接不等于自动融合输出';
document.querySelector('#raw-title').textContent='排列预览';
$('confirm-order').textContent='采用这个顺序';
$('pairing-problem').textContent='节点或位置有问题';
$('pairing-note').placeholder='填写节点编号和具体问题';
$('order-restore').textContent='恢复节点编号顺序（未确认）';
$('next-order').textContent='下一队 →';
$('example-question').hidden=true;
$('next-order').onclick=()=>{if(currentCase+1<dataset.cases.length)chooseCase(currentCase+1);else $('save-state').textContent='本页已到最后一队，请导出记录';};
const home=document.createElement('a');home.href='../index.html';home.textContent='返回全部图片';document.querySelector('.study-heading').prepend(home);
const originalSave=saveReview;
saveReview=function(status='draft'){
  if(activeSource()?.object_kind!=='fusion')return false;
  return originalSave(status);
};
const previousDescribe=describeSource;
const previewToggle=document.createElement('label');
previewToggle.innerHTML='<input type="checkbox" id="enable-ring-preview">显示当前排列的三维连线（仅预览）';
document.querySelector('.order-controls').append(previewToggle);
function updateRingPreview(){
  const fusion=activeSource()?.object_kind==='fusion';
  $('compare-grid').style.display=fusion&&!$('enable-ring-preview').checked?'none':'grid';
  if(fusion&&!$('enable-ring-preview').checked)$('show-edges').checked=false;
  drawPanorama();
}
$('enable-ring-preview').onchange=updateRingPreview;
describeSource=function(){
  previousDescribe();const s=activeSource();if(!s)return;
  const fusion=s.object_kind==='fusion';
  for(const id of ['confirm-order','pairing-problem','pending-order','order-apply','order-restore'])$(id).disabled=!fusion;
  $('pair-drag-list').style.pointerEvents=fusion?'auto':'none';
  if(fusion){
    identity.textContent=s.raw_condition+'；入选节点：'+s.node_supports.map((n,i)=>`对${i+1} ${n}票`).join('，');
    $('sample-evidence').textContent='团队：'+s.canonical_annotation_id+'；当前操作只保存人工排列。';
  }else identity.textContent=s.worker_id+' · 完整原答，沿用冻结顺序，仅供核对。请选择“融合节点”进行排序。';
  updateRingPreview();
};
const reviewChoose=chooseVariant;
chooseVariant=function(index,reset=false){$('enable-ring-preview').checked=false;reviewChoose(index,reset);describeSource();};
const importReview=$('import-orders').onchange;
$('import-orders').onchange=async e=>{
 try{
  const doc=JSON.parse(await e.target.files[0].text());
  if(Object.keys(doc.records||{}).some(id=>!id.startsWith('missing_ring:')))throw Error('只能导入融合节点排序记录，不能把原答设为已审核');
  await importReview(e);
 }catch(err){$('save-state').textContent='导入未应用：'+err.message;}
};
updateProgress=function(){
  const count=Object.values(saved).filter(r=>r.status==='confirmed').length;
  $('object-progress').textContent=`第 ${currentCase+1} / ${dataset.cases.length} 队 · 已采用 ${count} 队`;
};
$('download-orders').onclick=()=>{
 const metadata=Object.fromEntries(dataset.cases.map(c=>{const s=c.variants[0].source;return [s.object_id,{...s.review_metadata,feature_ids:s.feature_ids,node_supports:s.node_supports}];}));
 const doc={schema:reviewSchema,examples_only:false,records:saved,objects:metadata,formal_results_modified:false};
 const url=URL.createObjectURL(new Blob([JSON.stringify(doc,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='融合节点排序_'+location.pathname.split('/').pop().replace('.html','.json');a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
document.querySelector('.review-actions').append($('download-orders'));
describeSource();updateProgress();
$('show-sequence').checked=false;
document.body.classList.add('review-ready');
drawPanorama();
