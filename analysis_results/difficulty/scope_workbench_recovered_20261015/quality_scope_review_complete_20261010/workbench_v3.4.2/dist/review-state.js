/* Confirmation snapshots are independent of editable drafts. Existing user edits always win; pristine old defaults can receive new confirmed seeds. */
(function(root){
'use strict';
const G=typeof module!=='undefined'?require('./geometry.js'):root.Geo;
const clone=o=>JSON.parse(JSON.stringify(o));
function cameraInside(p){return G.valid(p)&&G.inside([0,0],p)&&p.every((a,i)=>{const b=p[(i+1)%p.length],dx=b[0]-a[0],dy=b[1]-a[1],len2=dx*dx+dy*dy;if(!len2)return false;const t=Math.max(0,Math.min(1,-(a[0]*dx+a[1]*dy)/len2));return Math.hypot(a[0]+t*dx,a[1]+t*dy)>1e-7})}
function samePoly(a,b){return Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((p,i)=>Array.isArray(p)&&Array.isArray(b[i])&&p.length===2&&b[i].length===2&&p.every((v,j)=>Number.isFinite(v)&&Number.isFinite(b[i][j])&&Math.abs(v-b[i][j])<1e-8))}
function fresh(c){return {polygon:G.floor(c.reference_points_1024x512||[]),cuts:[],operations:[],decision:'',note:'',top_boundary_pending:true,completed:false,axis_angle:0}}
function verifyOps(c,r){
  const ops=r.operations||(r.cuts||[]).map(x=>({type:'cut',...x}));
  if(!Array.isArray(ops)||ops.length>100)throw Error('修改记录无效');
  for(const o of ops){
    if(!o||typeof o!=='object')throw Error('修改记录无效');
    if(o.type==='cut'||o.type==='rectangle'){
      if(![o.a,o.b].every(a=>Array.isArray(a)&&a.length===2&&a.every(v=>Number.isFinite(v)&&Math.abs(v)<10000)))throw Error('坐标无效');
      if(o.type==='cut'&&![1,-1].includes(o.side))throw Error('切割方向无效');
      if(o.type==='rectangle'&&(!Number.isFinite(o.angle)||Math.abs(o.angle)>180))throw Error('角度无效');
    }else if(o.type==='gt_follow'){
      if(!Array.isArray(o.lines)||o.lines.length!==4||o.lines.some(l=>!Array.isArray(l)||l.length!==2||l.some(p=>!Array.isArray(p)||p.length!==2||p.some(v=>!Number.isFinite(v)||Math.abs(v)>=10000)))||!G.boundaryQuad(o.lines))throw Error('GT贴合边线无效');
    }else if(o.type==='edge_follow'){
      if(!Number.isInteger(o.index)||!Array.isArray(o.line)||o.line.length!==2||o.line.some(p=>!Array.isArray(p)||p.length!==2||p.some(v=>!Number.isFinite(v)||Math.abs(v)>=10000)))throw Error('边线贴合记录无效');
    }else if(o.type==='edge_move'){
      if(!Number.isInteger(o.index)||!Number.isFinite(o.offset)||Math.abs(o.offset)>10000)throw Error('拉伸记录无效');
    }else throw Error('未知修改类型');
  }
  let p=G.floor(c.reference_points_1024x512||[]);
  for(const op of ops){p=G.replay(p,[op]);if(!p||!cameraInside(p))throw Error('区域自交、断开或未包含相机');}
  if(!samePoly(p,r.cropped_floor_xz_h||r.polygon)||(r.polygon&&!samePoly(p,r.polygon))||(r.cropped_floor_xz_h&&!samePoly(p,r.cropped_floor_xz_h)))throw Error('区域与修改历史不一致');
  if(!['','allow','full_gt','uncertain'].includes(r.decision))throw Error('结论无效');
  if(r.decision==='full_gt'&&ops.length)throw Error('完整GT结论与修改不一致');
  return {polygon:p,operations:clone(ops),cuts:ops.filter(o=>o.type==='cut').map(o=>({a:clone(o.a),b:clone(o.b),side:o.side})),decision:r.decision,note:String(r.note||'').slice(0,10000),top_boundary_pending:r.top_boundary_pending!==false,axis_angle:Number.isFinite(r.axis_angle)?r.axis_angle:0,completed:!!r.completed&&!!r.decision&&(r.decision!=='allow'||ops.length>0),updated_at:r.updated_at};
}
function sameReview(d,c){return !!d&&!!c&&samePoly(d.polygon,c.polygon)&&d.decision===c.decision&&d.note===c.note&&d.top_boundary_pending===c.top_boundary_pending}
function verifyConfirmation(c,r){
  const v=verifyOps(c,r);
  if(!v.completed||!r.confirmed_at||!Number.isFinite(Date.parse(r.confirmed_at)))throw Error('确认记录无效');
  return {...v,confirmed_at:r.confirmed_at,source:['user_chat','user_instruction_no_operations'].includes(r.source)?r.source:'workbench_button',...(r.source==='user_instruction_no_operations'?{no_operation_policy_id:r.no_operation_policy_id||null,confirmed_at_meaning:'exported_at_under_user_instruction'}:{}),confirmation_message_id:r.confirmation_message_id||null,source_sha256:r.source_sha256||null,floor_region_confirmed:v.decision!=='uncertain',top_boundary_validation:'not established by this floor-region confirmation'};
}
function initialize(data,saved){
  const drafts={},confirmations={},warnings=[],recovery=clone(saved?.unrecovered_drafts||{});
  const compatible=saved?.source_commit===data.source_commit;
  if(saved&&!compatible){warnings.push('旧存储的数据版本不匹配，未应用旧区域，原始存储已完整保留');recovery.previous_storage=clone(saved);}
  if(compatible){for(const [id,d] of Object.entries(saved.drafts||{})){if(!data.images.some(c=>c.image_code===id))recovery[id]=clone(d);}for(const [id,v] of Object.entries(saved.confirmations||{})){if(!data.images.some(c=>c.image_code===id))recovery[id+':confirmation']=clone(v);}}
  for(const c of data.images){
    const id=c.image_code,seed=c.confirmed_review?verifyConfirmation(c,c.confirmed_review):null;
    if(seed)confirmations[id]=seed;
    if(compatible&&saved.confirmations?.[id]){
      try{const local=verifyConfirmation(c,saved.confirmations[id]);if(!seed||Date.parse(local.confirmed_at)>Date.parse(seed.confirmed_at))confirmations[id]=local;}catch(e){warnings.push(id+' 的本地确认副本无法验证');recovery[id+':confirmation']=clone(saved.confirmations[id]);}
    }
    const local=compatible&&saved.drafts?.[id];
    if(local){try{const verified=verifyOps(c,local);const pristine=!local.updated_at&&!verified.operations.length&&!verified.decision&&!verified.note&&verified.top_boundary_pending&&samePoly(verified.polygon,fresh(c).polygon);drafts[id]=seed&&pristine?verifyOps(c,seed):verified;}catch(e){warnings.push(id+' 的旧草稿无法验证，原始副本已保留');recovery[id]=clone(local);}}
    if(!drafts[id])drafts[id]=confirmations[id]?verifyOps(c,confirmations[id]):fresh(c);
    if(confirmations[id])drafts[id].completed=sameReview(drafts[id],confirmations[id]);
  }
  return {drafts,confirmations,warnings,unrecovered_drafts:recovery};
}
function confirm(c,d,now=new Date().toISOString()){
  if(c.editable===false)throw Error(c.edit_block_reason||'此图暂不能编辑确认');
  const next=clone(d);
  if(!next.decision)next.decision=samePoly(next.polygon,G.floor(c.reference_points_1024x512||[]))?'full_gt':'allow';
  if(next.decision==='allow'&&!next.operations.length)next.decision='full_gt';
  next.completed=true;next.updated_at=now;
  const snapshot=verifyConfirmation(c,{...next,confirmed_at:now,source:'workbench_button'});
  return {draft:verifyOps(c,next),confirmation:snapshot};
}
// Named alternative target spaces share a reference, but never share approval.
const SPACE_SCHEMA='manual_scope_space_regions_v1';
function sourceBinding(c,sourceCommit){return {source_commit:sourceCommit,image_code:c.image_code,image_id:c.image_id,editing_reference_object_id:c.reference_object_id,editing_reference_version:c.reference_version,editing_reference_points_1024x512:clone(c.reference_points_1024x512)}}
function verifyBinding(c,b,sourceCommit){const expected=sourceBinding(c,sourceCommit);if(!b||Object.keys(expected).some(k=>JSON.stringify(b[k])!==JSON.stringify(expected[k])))throw Error('空间区域 GT／来源绑定不匹配')}
function regionStatus(r){return r.confirmed_version&&sameReview(r.draft,r.confirmed_version)?r.confirmed_version.floor_region_confirmed?'confirmed':'uncertain':r.confirmed_version?'modified':'pending'}
function exportRegions(c,regions,activeId,sourceCommit){return {schema:SPACE_SCHEMA,active_region_id:activeId,meaning:'alternative_annotation_target_floor_regions; not a disjoint partition or approved 3D reference',regions:regions.map(r=>({region_id:r.region_id,name:r.name,source_binding:sourceBinding(c,sourceCommit),...clone(r.draft),cropped_floor_xz_h:clone(r.draft.polygon),confirmed_version:r.confirmed_version?clone(r.confirmed_version):null,floor_region_confirmed:regionStatus(r)==='confirmed',reference_ready:false,formal_eligibility_changed:false}))}}
function verifyRegions(c,value,sourceCommit){
 if(!value||value.schema!==SPACE_SCHEMA||!Array.isArray(value.regions)||!value.regions.length||value.regions.length>50)throw Error('空间区域版本或数量无效');
 const seen=new Set(),regions=value.regions.map(r=>{
  if(!r||typeof r.region_id!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(r.region_id)||seen.has(r.region_id))throw Error('空间区域编号无效或重复');seen.add(r.region_id);
  if(typeof r.name!=='string'||!r.name.trim()||r.name.length>80)throw Error('空间区域名称无效');
  verifyBinding(c,r.source_binding,sourceCommit);
  if(r.reference_ready!==false||r.formal_eligibility_changed!==false)throw Error('空间候选不能自动成为正式参考');
  const draft=verifyOps(c,r),confirmed_version=r.confirmed_version?verifyConfirmation(c,r.confirmed_version):null;
  // Both polygon aliases must agree; neither may conceal a tampered polygon.
  if(r.polygon&&!samePoly(r.polygon,draft.polygon))throw Error('空间区域坐标字段不一致');
  draft.completed=!!confirmed_version&&sameReview(draft,confirmed_version);
  return {region_id:r.region_id,name:r.name.trim(),draft,confirmed_version};
 });
 if(!seen.has('primary')||!seen.has(value.active_region_id))throw Error('缺少原范围或当前空间区域');
 return {active_region_id:value.active_region_id,regions};
}
function initializeRegions(data,saved,state){
 const result={};if(!saved?.space_regions)return result;
 if(saved.source_commit!==data.source_commit){state.unrecovered_drafts.space_regions_previous_source=clone(saved.space_regions);return result}
 for(const [id,raw]of Object.entries(saved.space_regions)){
  const c=data.images.find(x=>x.image_code===id);
  try{if(!c||c.editable===false)throw Error('图片不可编辑');const verified=verifyRegions(c,raw,data.source_commit),p=verified.regions.find(r=>r.region_id==='primary');
   if(saved.drafts?.[id]&&(!sameReview(verifyOps(c,saved.drafts[id]),p.draft)||JSON.stringify(saved.drafts[id].operations||[])!==JSON.stringify(p.draft.operations)))throw Error('原范围草稿副本不一致');
   result[id]={active_region_id:verified.active_region_id,primary_name:p.name,alternatives:verified.regions.filter(r=>r.region_id!=='primary')};
  }catch(e){state.unrecovered_drafts[id+':space_regions']=clone(raw);state.warnings.push(id+' 的空间候选无法验证，完整副本已保留：'+e.message)}
 }
 return result;
}

const api={SPACE_SCHEMA,sourceBinding,verifyBinding,regionStatus,exportRegions,verifyRegions,initializeRegions,clone,cameraInside,samePoly,fresh,verifyOps,sameReview,verifyConfirmation,initialize,confirm};
if(typeof module!=='undefined')module.exports=api;else root.ReviewState=api;
})(typeof window==='undefined'?globalThis:window);
