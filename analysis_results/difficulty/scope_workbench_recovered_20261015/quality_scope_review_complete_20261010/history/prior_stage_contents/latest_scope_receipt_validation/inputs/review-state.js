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
    }else if(o.type==='edge_move'){
      if(!Number.isInteger(o.index)||!Number.isFinite(o.offset)||Math.abs(o.offset)>10000)throw Error('拉伸记录无效');
    }else throw Error('未知修改类型');
  }
  let p=G.floor(c.reference_points_1024x512||[]);
  for(const op of ops){p=G.replay(p,[op]);if(!p||!cameraInside(p))throw Error('区域自交、断开或未包含相机');}
  if(!samePoly(p,r.cropped_floor_xz_h||r.polygon))throw Error('区域与修改历史不一致');
  if(!['','allow','full_gt','uncertain'].includes(r.decision))throw Error('结论无效');
  if(r.decision==='full_gt'&&ops.length)throw Error('完整GT结论与修改不一致');
  return {polygon:p,operations:clone(ops),cuts:ops.filter(o=>o.type==='cut').map(o=>({a:clone(o.a),b:clone(o.b),side:o.side})),decision:r.decision,note:String(r.note||'').slice(0,10000),top_boundary_pending:r.top_boundary_pending!==false,axis_angle:Number.isFinite(r.axis_angle)?r.axis_angle:0,completed:!!r.completed&&!!r.decision&&(r.decision!=='allow'||ops.length>0),updated_at:r.updated_at};
}
function sameReview(d,c){return !!d&&!!c&&samePoly(d.polygon,c.polygon)&&d.decision===c.decision&&d.note===c.note&&d.top_boundary_pending===c.top_boundary_pending}
function verifyConfirmation(c,r){
  const v=verifyOps(c,r);
  if(!v.completed||!r.confirmed_at||!Number.isFinite(Date.parse(r.confirmed_at)))throw Error('确认记录无效');
  return {...v,confirmed_at:r.confirmed_at,source:r.source==='user_chat'?'user_chat':'workbench_button',confirmation_message_id:r.confirmation_message_id||null,source_sha256:r.source_sha256||null,floor_region_confirmed:v.decision!=='uncertain',top_boundary_validation:'not established by this floor-region confirmation'};
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
const api={clone,cameraInside,samePoly,fresh,verifyOps,sameReview,verifyConfirmation,initialize,confirm};
if(typeof module!=='undefined')module.exports=api;else root.ReviewState=api;
})(typeof window==='undefined'?globalThis:window);
