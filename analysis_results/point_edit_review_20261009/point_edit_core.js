/* 独立复核补丁；原点身份、原数组与人员资格只读。 */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.PointReview=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const SCHEMA='point_edit_review_20261009_v1',clone=v=>JSON.parse(JSON.stringify(v)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const identity=s=>({record_id:s.record_id,canonical_object_id:s.canonical_object_id,image_id:s.image_id,...(s.source_identity||{})});
const stamp=()=>new Date().toISOString(),uuid=()=>globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
const active=d=>d.points.filter(p=>!p.deleted),find=(d,id)=>{const p=d.points.find(p=>p.id===id&&!p.deleted);if(!p)throw Error('无效或已删除点：'+id);return p;};
function xPairs(d){
 const used=new Set(d.pairs.flat()),rest=active(d).filter(p=>!used.has(p.id));
 if(rest.length<2)throw Error('没有可新增的完整上下点对');
 if(rest.length%2)throw Error('剩余有效点为奇数；请先补点或删点，再按x配对');
 rest.forEach(p=>bounds(p.x,p.y));
 const originalIndex=new Map(rest.map((p,i)=>[p.id,i])),ids=rest.sort((a,b)=>a.x-b.x||originalIndex.get(a.id)-originalIndex.get(b.id)),options=[];
 for(const shift of [0,1]){
  const order=ids.slice(shift).concat(ids.slice(0,shift)),pairs=[];let cost=0;
  for(let i=0;i<order.length;i+=2){const [a,b]=[order[i],order[i+1]].sort((x,y)=>x.y-y.y);if(a.y===b.y){cost=Infinity;break;}
   cost+=Math.abs((a.x-b.x+512+1024)%1024-512);pairs.push([a.id,b.id]);}
  if(Number.isFinite(cost))options.push({cost,pairs});
 }
 if(!options.length)throw Error('候选上下点同y，无法按x自动配对；请手动配对');
 options.sort((a,b)=>a.cost-b.cost);
 const signature=pairs=>pairs.map(p=>p.slice().sort().join('|')).sort().join(';');
 if(options.length>1&&Math.abs(options[0].cost-options[1].cost)<1e-8&&signature(options[0].pairs)!==signature(options[1].pairs))throw Error('周期x配对存在等价歧义；请手动配对');
 return options[0].pairs.sort((a,b)=>{const mean=id=>{const p=find(d,id[0]),q=find(d,id[1]);return ((p.x+((q.x-p.x+512+1024)%1024-512)/2)%1024+1024)%1024;};return mean(a)-mean(b);});
}
function bounds(x,y){if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||x>=1024||y<0||y>512)throw Error('坐标越界：要求 0≤x<1024，0≤y≤512');}
function validPairs(d){const used=new Set();for(const p of d.pairs){if(!Array.isArray(p)||p.length!==2)throw Error('配对格式错误');const [a,b]=p.map(id=>find(d,id));for(const x of [a,b]){bounds(x.x,x.y);if(used.has(x.id))throw Error('点被重复配对');used.add(x.id);}if(a.y>=b.y)throw Error('请依次选择上点、下点');}}
function create(s,version){const v=s.versions[version];if(!v?.available)throw Error('该版本缺失或点身份不完整；请明确选择原始或历史版本');
 return {identity:identity(s),source_hash:s.source_hash,raw_hash:s.raw_hash||null,current_hash:s.current_hash||null,photo_hash:s.photo_hash||null,
 base_version:version,base_points:clone(v.points),base_pairs:clone(v.pairs||[]),points:clone(v.points),pairs:clone(v.pairs||[]),operations:[],
 status:'draft',note:'',updated_at:stamp(),scope:'review_patch_only',restore_eligibility:false,ring_confirmed:false};}
function undoTarget(d){const undone=new Set(d.operations.filter(o=>o.type==='undo').map(o=>o.undo_of));
 return [...d.operations].reverse().find(o=>o.type!=='undo'&&!undone.has(o.operation_id));}
const canUndo=d=>!!undoTarget(d),hasChanges=d=>!same(d.points,d.base_points)||!same(d.pairs,d.base_pairs);
function apply(d,type,fields,meta={}){
 const n=clone(d),op={operation_id:uuid(),timestamp:stamp(),type,...clone(fields)},beforePairs=clone(n.pairs);
 if(type==='add'){const {id,x,y}=fields;bounds(x,y);if(!id?.startsWith('new:')||n.points.some(p=>p.id===id))throw Error('新增点须使用独立new:身份');
  op.point_id=id;op.before=null;op.after={x,y};op.provenance=clone(meta);
  n.points.push({id,x,y,label:'新点 '+id.slice(4,12),origin:'user_added',source_index:null,provenance:clone(meta)});}
 else if(type==='move'){const p=find(n,fields.point_id);bounds(fields.x,fields.y);op.before={x:p.x,y:p.y};op.after={x:fields.x,y:fields.y};p.x=fields.x;p.y=fields.y;
  // 移动可能使上下方向失效，撤销相关配对并明确记录。
  n.pairs=n.pairs.filter(pair=>!pair.includes(p.id));}
 else if(type==='delete'){const p=find(n,fields.point_id);op.before={x:p.x,y:p.y};op.after=null;p.deleted=true;n.pairs=n.pairs.filter(p=>!p.includes(fields.point_id));}
 else if(type==='pair'){const [a,b]=fields.pair.map(id=>find(n,id));bounds(a.x,a.y);bounds(b.x,b.y);
  if(a.y>=b.y)throw Error('请依次选择上点、下点');if(a.id===b.id||n.pairs.flat().some(id=>fields.pair.includes(id)))throw Error('点被重复配对，请先解除相关点对');n.pairs.push(clone(fields.pair));}
 else if(type==='pair_x'){const pairs=xPairs(n);if(!same(fields.pairs,pairs))throw Error('x配对候选与当前点位不一致');n.pairs.push(...pairs);op.pairs=clone(pairs);}
 else if(type==='undo'){
  const target=undoTarget(n);if(!target)throw Error('没有可撤销的点操作');
  if(fields.undo_of&&fields.undo_of!==target.operation_id)throw Error('撤销目标与最近有效操作不匹配');
  op.undo_of=target.operation_id;op.before=clone(n.points);
  if(target.type==='add')n.points=n.points.filter(p=>p.id!==target.point_id);
  else if(target.type==='move'){const p=find(n,target.point_id);p.x=target.before.x;p.y=target.before.y;}
  else if(target.type==='delete'){const p=n.points.find(p=>p.id===target.point_id);delete p.deleted;}
  else if(target.type==='reset')n.points=clone(target.before);
  n.pairs=clone(target.pairs_before);op.after=clone(n.points);
 }
 else if(type==='order'){
  const order=fields.order,count=n.pairs.length;
  if(count<2||!Array.isArray(order)||order.length!==count||[...order].sort((a,b)=>a-b).some((v,i)=>v!==i))throw Error('排列必须完整且不重复，并至少有两个上下点对');
  op.group_unit='paired_top_bottom_endpoints';n.pairs=order.map(i=>clone(beforePairs[i]));
 }
 else if(type==='reset'){op.before=clone(n.points);n.points=clone(n.base_points);n.pairs=clone(n.base_pairs);op.after=clone(n.points);}
 else if(type==='unpair'){if(!n.pairs.some(p=>same(p,fields.pair)))throw Error('配对不存在');n.pairs=n.pairs.filter(p=>!same(p,fields.pair));}
 else throw Error('未知操作');
 op.pairs_before=beforePairs;op.pairs_after=clone(n.pairs);n.operations.push(op);n.status='draft';n.updated_at=op.timestamp;return n;
}
const add=(d,x,y,id='new:'+uuid(),meta={source:'用户按原图手动新增',imputed:false})=>apply(d,'add',{id,x,y},meta);
const move=(d,id,x,y)=>apply(d,'move',{point_id:id,x,y});
const remove=(d,id)=>apply(d,'delete',{point_id:id});
const pair=(d,a,b)=>apply(d,'pair',{pair:[a,b]});
const unpair=(d,p)=>apply(d,'unpair',{pair:p});
function status(d,state,note){if(!['draft','completed','confirmed','deferred','kept'].includes(state))throw Error('审核状态无效');
 if(state==='confirmed'){if(!active(d).length)throw Error('没有有效点；请暂缓并解释');active(d).forEach(p=>bounds(p.x,p.y));validPairs(d);}
 if(state==='confirmed'&&!String(note).trim())throw Error('请填写本次判断理由');
 return {...clone(d),status:state,note:String(note),updated_at:stamp()};}
function validate(s,d){
 if(!same(d.identity,identity(s)))throw Error('完整记录身份不匹配：'+s.record_id);
 if(d.source_hash!==s.source_hash||d.raw_hash!==(s.raw_hash||null)||d.current_hash!==(s.current_hash||null)||d.photo_hash!==(s.photo_hash||null))throw Error('来源hash不匹配：'+s.record_id);
 if(d.scope!=='review_patch_only'||d.restore_eligibility!==false||d.ring_confirmed!==false)throw Error('补丁不得改变资格或确认环序');
 let replay=create(s,d.base_version);if(!same(replay.base_points,d.base_points)||!same(replay.base_pairs,d.base_pairs))throw Error('基准点身份或配对漂移');
 if(!Array.isArray(d.operations)||typeof d.note!=='string'||typeof d.updated_at!=='string')throw Error('操作字段缺失');
 const seen=new Set();
 for(const op of d.operations){if(!op.operation_id||seen.has(op.operation_id)||typeof op.timestamp!=='string')throw Error('操作身份错误');seen.add(op.operation_id);
  const fields=op.type==='order'?{order:op.order,action:op.action}:op.type==='undo'?{undo_of:op.undo_of}:op.type==='reset'?{}:op.type==='add'?{id:op.id,x:op.x,y:op.y}:op.type==='move'?{point_id:op.point_id,x:op.x,y:op.y}:op.type==='delete'?{point_id:op.point_id}:op.type==='pair_x'?{pairs:op.pairs}:{pair:op.pair};
  replay=apply(replay,op.type,fields,op.provenance||{});const expected=replay.operations.at(-1);
  for(const k of ['before','after','pairs_before','pairs_after','point_id','undo_of'])if(!same(expected[k],op[k]))throw Error('操作前后追溯不匹配');
  expected.operation_id=op.operation_id;expected.timestamp=op.timestamp;
 }
 if(!same(replay.points,d.points)||!same(replay.pairs,d.pairs))throw Error('点或配对与操作记录不一致');
 status(d,d.status,d.note);return true;
}
function exportFile(data,records){for(const [id,d] of Object.entries(records)){const s=data.cases.find(c=>c.record_id===id);if(!s)throw Error('未知记录');validate(s,d);}
 return {schema:SCHEMA,source_hash:data.source_hash,queue_hash:data.queue_hash,exported_at:stamp(),scope:'review_patch_only',apply_to_formal:false,records:clone(records)};}
function importFile(data,file,records){if(file.schema!==SCHEMA||file.source_hash!==data.source_hash||file.queue_hash!==data.queue_hash||file.scope!=='review_patch_only'||file.apply_to_formal!==false)throw Error('来源或审核格式不匹配');
 if(!file.records||Array.isArray(file.records)||typeof file.records!=='object')throw Error('记录格式错误');const next=clone(records);
 for(const [id,d] of Object.entries(file.records)){const s=data.cases.find(c=>c.record_id===id);if(!s)throw Error('未知记录身份：'+id);validate(s,d);if(next[id]&&!same(next[id],d))throw Error('导入与本地草稿冲突：'+id);next[id]=clone(d);}return next;}
return {SCHEMA,create,add,move,remove,pair,unpair,pairByX:d=>apply(d,'pair_x',{pairs:xPairs(d)}),reorder:(d,order,action='drag_pair')=>apply(d,'order',{order,action}),undo:d=>apply(d,'undo',{}),canUndo,hasChanges,reset:d=>apply(d,'reset',{}),status,validate,exportFile,importFile,active,bounds};
});
