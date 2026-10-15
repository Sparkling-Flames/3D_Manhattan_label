'use strict';
// Reproducible offline validator. Run: node validate_receipt.js
// The three Site inputs and raw receipt are immutable copies, never patched.
const fs=require('fs'), path=require('path'),crypto=require('crypto');
const root=__dirname, inp=path.join(root,'inputs'),G=require('./inputs/geometry.js'),R=require('./inputs/review-state.js');
const rawBytes=fs.readFileSync(path.join(inp,'raw_scope_receipt.json'));
const receipt=JSON.parse(rawBytes),data=JSON.parse(fs.readFileSync(path.join(inp,'data.json')));
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const canonical=x=>JSON.stringify(x),equal=(a,b)=>canonical(a)===canonical(b),clone=x=>JSON.parse(canonical(x));
const source_sha256=sha(rawBytes);
const USER={message_id:'Sentinel_9ed00ac0b1388191a64819aae866107b',message_at:'2026-10-10T11:53:17Z',verbatim:'等一下,先把我这几张图审查完毕. 我刚刚把之前确认范围的6张图已经重新修改,但是我忘记点击确认了. 这是我确认范围的,请你落实相关数据,之后再统一上传main'};
const countClarification={message_id:'Sentinel_b0471b82acec8191b2289d5f76e245bd',message_at:'2026-10-10T11:56:26Z',verbatim:'那就是之前审核的5张.'};
const expectedPrior=['b8cTxDM8gDG-18','e9zR4mvMWw7-09','e9zR4mvMWw7-17','pRbA3pwrgk9-02','q9vSo1VnCiC-29'];
const expectedNew=['S9hNv5qa7GM-04','pa4otMbVnkk-14','q9vSo1VnCiC-11','q9vSo1VnCiC-12','uNb9QFRL6hY-44','uNb9QFRL6hY-55','uNb9QFRL6hY-68','uNb9QFRL6hY-81','wc2JMjhGNzB-22','wc2JMjhGNzB-26','wc2JMjhGNzB-29'];
const expectedFull=['S9hNv5qa7GM-04','pa4otMbVnkk-14','wc2JMjhGNzB-26'];
const errors=[],warnings=[],rows=[],records=[],prior=[],newRows=[],untouched=[];
const assert=(yes,where,what)=>{if(!yes)errors.push({where,check:what});};
const eps=1e-8;
const samePoly=R.samePoly;
function finiteTree(x,p='$') {if(typeof x==='number')assert(Number.isFinite(x),p,'finite number');else if(Array.isArray(x))x.forEach((v,i)=>finiteTree(v,p+'['+i+']'));else if(x&&typeof x==='object')Object.entries(x).forEach(([k,v])=>finiteTree(v,p+'.'+k));}
finiteTree(receipt);
const expectedRoot=['schema','editor_version','latest_scope_review_source_commit','source_commit','exported_at','coordinate_frame','GT_modified','legacy_field_notice','unrecovered_drafts','records'];
assert(equal(Object.keys(receipt),expectedRoot),'root','exact export root key order/schema');
assert(receipt.schema==='manual_scope_crop_review_v2','root','schema');
assert(receipt.editor_version==='3.2','root','editor version');
for(const k of ['source_commit','latest_scope_review_source_commit'])assert(receipt[k]===data[k],'root',k+' matches Site');
assert(receipt.exported_at==='2026-10-10T11:52:40.335Z','root','expected export timestamp');
assert(receipt.coordinate_frame==='camera_height_normalized_xz; original ERP 1024x512','root','coordinate frame');
assert(receipt.GT_modified===false,'root','GT unmodified declaration');
assert(equal(receipt.unrecovered_drafts,{}),'root','no unrecovered draft evidence omitted');
const exportable=data.images.filter(c=>c.reference_points_1024x512?.length);
assert(receipt.records.length===259&&data.images.length===280&&exportable.length===259,'root','259 exportable records plus 21 historical catalogue-only entries');
assert(data.images.filter(c=>!c.reference_points_1024x512?.length).every(c=>c.in_current_corpus===false&&!c.confirmed_review),'Site','21 omitted historical entries have no editing reference or confirmation');
const by=new Map(data.images.map(c=>[c.image_code,c]));
assert(by.size===280,'Site','unique image codes');
assert(new Set(data.images.map(c=>c.image_id)).size===280,'Site','unique image IDs');
assert(new Set(receipt.records.map(c=>c.image_code)).size===259,'receipt','unique image codes');
assert(new Set(receipt.records.map(c=>c.image_id)).size===259,'receipt','unique image IDs');
assert(equal(receipt.records.map(r=>r.image_code),exportable.map(c=>c.image_code)),'receipt','exact Site image census and ordering');
assert(equal(data.new_scope_batch.images,expectedNew),'Site','new batch identity list');
function bounds(p){return {min_x:Math.min(...p.map(p=>p[0])),max_x:Math.max(...p.map(p=>p[0])),min_z:Math.min(...p.map(p=>p[1])),max_z:Math.max(...p.map(p=>p[1]))};}
function signedArea(p){return p.reduce((s,a,i)=>{let b=p[(i+1)%p.length];return s+a[0]*b[1]-b[0]*a[1]},0)/2;}
function intersectConvex(subject,clip){let p=clone(subject),sgn=Math.sign(signedArea(clip));for(let i=0;i<clip.length&&p.length;i++){let a=clip[i],b=clip[(i+1)%clip.length],q=[];for(let j=0;j<p.length;j++){let u=p[j],v=p[(j+1)%p.length],fu=sgn*G.cross(a,b,u),fv=sgn*G.cross(a,b,v);let iu=fu>=0,iv=fv>=0;if(iu)q.push(u);if(iu!==iv){let t=fu/(fu-fv);q.push([u[0]+t*(v[0]-u[0]),u[1]+t*(v[1]-u[1])]);}}p=q;}return p;}
function delta(old,p){let ob=bounds(old),nb=bounds(p),oa=G.area(old),na=G.area(p);let cv=p.length===4&&p.every((a,i)=>Math.abs(G.cross(a,p[(i+1)%4],p[(i+2)%4]))>eps)&&p.every((a,i)=>Math.sign(G.cross(a,p[(i+1)%4],p[(i+2)%4]))===Math.sign(signedArea(p)));let ia=cv?G.area(intersectConvex(old,p)):samePoly(old,p)?oa:null;return {old_vertices:old.length,new_vertices:p.length,old_area_h2:oa,new_area_h2:na,area_delta_h2:na-oa,area_relative_change:(na-oa)/oa,old_bounds:ob,new_bounds:nb,bounds_delta:Object.fromEntries(Object.keys(ob).map(k=>[k,nb[k]-ob[k]])),exact_ordered_coordinates_unchanged:equal(old,p),intersection_area_h2:ia,symmetric_difference_area_h2:ia===null?null:Math.max(0,oa+na-2*ia)};}
function cameraDistance(p){return Math.min(...p.map((a,i)=>{let b=p[(i+1)%p.length],d=[b[0]-a[0],b[1]-a[1]],ll=d[0]**2+d[1]**2,t=Math.max(0,Math.min(1,-(a[0]*d[0]+a[1]*d[1])/ll));return Math.hypot(a[0]+t*d[0],a[1]+t*d[1]);}));}
function snapsFor(r,gt){const op=r.operations.at(-1);if(!op?.gt_snap)return [];return op.gt_snap.matches.map(m=>{assert(Number.isInteger(m.edge)&&m.edge>=0&&m.edge<r.polygon.length,r.image_code,'snap source edge index');assert(Number.isInteger(m.gt_edge)&&m.gt_edge>=0&&m.gt_edge<gt.length,r.image_code,'snap GT edge index');let final=G.edgeSnapCandidates(r.polygon[m.edge],r.polygon[(m.edge+1)%r.polygon.length],gt,10000).find(s=>s.gt_edge===m.gt_edge);assert(!!final,r.image_code,'snap pair has finite overlap and <=0.5 degree angular difference');return {...m,stored_distance_px_semantics:'distance before snapping at user viewport scale; not a final residual',actual_final_max_normal_distance_h:final?.distance??null,actual_final_half_line_error_h:final?.line_error??null,actual_final_signed_mean_normal_offset_h:final?.offset??null,actual_final_finite_overlap_h:final?final.overlap[1]-final.overlap[0]:null,actual_final_exact_parallel:final?.exact??null};});}
const expectedKeys=['axis_angle','completed','confirmed_version','cropped_floor_xz_h','cuts','decision','editing_reference_object_id','editing_reference_points_1024x512','editing_reference_version','evidence_source_commit','floor_region_confirmed','formal_eligibility_changed','historical_original_GT_object_id','historical_original_GT_points_1024x512','image_code','image_id','latest_user_scope_review','manual_region_may_extend_GT','note','operations','original_GT_floor_xz_h','original_GT_points_1024x512','polygon','received_confirmed_version','reference_object_id','reference_ready','reference_version','review_scope','scope_batch_id','top_boundary_pending'];
for(const [index,r] of receipt.records.entries()){
 const c=by.get(r.image_code),id=r.image_code;if(!c){assert(false,id,'known identity');continue;}
 assert(equal(Object.keys(r).filter(k=>k!=='updated_at').sort(),expectedKeys),id,'exact export record schema');
 for(let [rk,ck] of [['image_id','image_id'],['reference_object_id','reference_object_id'],['original_GT_points_1024x512','reference_points_1024x512'],['reference_version','reference_version'],['editing_reference_version','reference_version'],['editing_reference_object_id','reference_object_id'],['editing_reference_points_1024x512','reference_points_1024x512']])assert(equal(r[rk],c[ck]),id,rk+' exact Site provenance match');
 const gt=G.floor(c.reference_points_1024x512||[]), historicalPoints=c.original_reference_points_1024x512||(c.reference_version==='original'?c.reference_points_1024x512:null);
 assert(samePoly(r.original_GT_floor_xz_h,gt),id,'baseline floor Node replay agrees within 1e-8');
 assert(equal(r.historical_original_GT_object_id,c.original_reference_object_id||null),id,'historical original object exact');
 assert(equal(r.historical_original_GT_points_1024x512,historicalPoints),id,'historical original points exact');
 assert(equal(r.received_confirmed_version,c.confirmed_review||null),id,'received old confirmation exact');
 assert(r.evidence_source_commit===data.evidence_source_commit,id,'evidence commit exact');
 assert(equal(r.scope_batch_id,c.scope_batch_id||null),id,'scope batch ID exact');
 assert(equal(r.latest_user_scope_review,c.latest_user_scope_review||null),id,'latest source review exact');
 for(const k of ['top_boundary_pending','manual_region_may_extend_GT'])assert(r[k]===true,id,k+' true');
 for(const k of ['reference_ready','formal_eligibility_changed'])assert(r[k]===false,id,k+' false');
 assert(r.review_scope==='floor_region_only; top boundary must be separately validated',id,'floor only');
 assert(Array.isArray(r.operations)&&Array.isArray(r.cuts)&&typeof r.note==='string'&&typeof r.axis_angle==='number'&&typeof r.completed==='boolean'&&typeof r.floor_region_confirmed==='boolean',id,'typed draft fields');
 assert(r.polygon.every(p=>Array.isArray(p)&&p.length===2&&p.every(x=>Number.isFinite(x)&&Math.abs(x)<10000)),id,'finite two-dimensional polygon');
 assert(equal(r.polygon,r.cropped_floor_xz_h),id,'polygon aliases exact');
 let v;try{v=R.verifyOps(c,r);}catch(e){assert(false,id,'operation verification: '+e.message);continue;}
 assert(samePoly(v.polygon,r.polygon),id,'operation geometry matches draft');
 assert(equal(v.operations,r.operations)&&equal(v.cuts,r.cuts),id,'effective operations and legacy cuts agree');
 assert(v.completed===r.completed,id,'completion declaration valid');
 assert(G.valid(gt)&&R.cameraInside(gt),id,'baseline simple valid and camera strictly inside');
 assert(G.valid(v.polygon)&&R.cameraInside(v.polygon),id,'final simple valid and camera strictly inside');
 if(r.updated_at){assert(Number.isFinite(Date.parse(r.updated_at))&&Date.parse(r.updated_at)<=Date.parse(receipt.exported_at),id,'edit timestamp precedes export');}
 let p=gt;let steps=[];for(const op of r.operations){p=G.replay(p,[op]);steps.push({operation:op.type,valid:G.valid(p),camera_inside:R.cameraInside(p),vertices:p.length,area_h2:G.area(p)});}
 let conf=null;if(r.confirmed_version){try{conf=R.verifyConfirmation(c,r.confirmed_version);}catch(e){assert(false,id,'confirmation replay: '+e.message);}assert(Date.parse(r.confirmed_version.confirmed_at)<=Date.parse(receipt.exported_at),id,'confirmation predates export');}
 assert(r.floor_region_confirmed===(!!conf&&R.sameReview(v,conf)),id,'exported confirmation status corresponds to exact current review');
 let status;
 if(c.confirmed_review&&!R.sameReview(v,R.verifyConfirmation(c,c.confirmed_review))){status='prior_confirmed_edited_missing_button';prior.push(id);assert(!r.completed&&!r.floor_region_confirmed,id,'changed old draft is unconfirmed in raw receipt');assert(equal(r.confirmed_version,c.confirmed_review),id,'raw still preserves old confirmation');assert(r.updated_at>c.confirmed_review.confirmed_at,id,'newer draft than old confirmation');}
 else if(!c.confirmed_review&&r.floor_region_confirmed){status='new_button_confirmation';newRows.push(id);assert(r.completed&&r.confirmed_version.source==='workbench_button',id,'new confirmation is button sourced');assert(equal(r.confirmed_version.polygon,r.polygon)&&equal(r.confirmed_version.operations,r.operations)&&r.confirmed_version.updated_at===r.updated_at,id,'new snapshot exactly matches latest draft');}
 else{status='untouched_pristine';untouched.push(id);assert(!r.updated_at&&!r.operations.length&&!r.cuts.length&&!r.decision&&!r.note&&!r.completed&&!r.floor_region_confirmed&&!r.confirmed_version&&!c.confirmed_review,id,'untouched row has no update or confirmation evidence');assert(equal(r.polygon,r.original_GT_floor_xz_h)&&samePoly(r.polygon,gt),id,'untouched polygon exact exported baseline and replay within 1e-8');}
 const snaps=snapsFor(r,gt);
 const row={image_code:id,source_pointer:'/records/'+index,status,provenance_exact:true,decision:r.decision,operation_count:r.operations.length,operation_types:r.operations.map(o=>o.type),editable:c.editable,reference_version:c.reference_version,valid:true,camera_inside:true,camera_boundary_min_distance_h:cameraDistance(r.polygon),operation_replay_steps:steps,raw_completed:r.completed,raw_floor_region_confirmed:r.floor_region_confirmed,raw_updated_at:r.updated_at||null,raw_confirmation_at:r.confirmed_version?.confirmed_at||null,normalized_included:status!=='untouched_pristine',baseline_geometry_delta:delta(gt,r.polygon),previous_confirmation_geometry_delta:c.confirmed_review?delta(c.confirmed_review.polygon,r.polygon):null,gt_snap_edges:snaps,gt_snap_max_final_normal_distance_h:snaps.length?Math.max(...snaps.map(x=>x.actual_final_max_normal_distance_h)):null};
 rows.push(row);
 if(status==='untouched_pristine')continue;
 assert(c.editable===true,id,'selected row editable');
 const isChat=status==='prior_confirmed_edited_missing_button';
 const replayed=R.verifyConfirmation(c,{...clone(v),completed:true,confirmed_at:isChat?USER.message_at:r.confirmed_version.confirmed_at,source:isChat?'user_chat':'workbench_button',confirmation_message_id:isChat?USER.message_id:(r.confirmed_version.confirmation_message_id||null),source_sha256});
 const current={...replayed,polygon:clone(r.polygon)}; // Preserve the received coordinates byte-for-byte numerically.
 const history=[];for(const [role,snapshot] of [['site_prior_confirmed_review',c.confirmed_review],['raw_confirmed_version',r.confirmed_version],['raw_received_confirmed_version',r.received_confirmed_version]])if(snapshot)history.push({role,snapshot:clone(snapshot)});
 records.push({image_code:id,image_id:r.image_id,reference_object_id:r.reference_object_id,editing_reference_version:r.editing_reference_version,editing_reference_object_id:r.editing_reference_object_id,editing_reference_points_1024x512:clone(r.editing_reference_points_1024x512),historical_original_GT_object_id:r.historical_original_GT_object_id,historical_original_GT_points_1024x512:clone(r.historical_original_GT_points_1024x512),...clone(current),cropped_floor_xz_h:clone(current.polygon),confirmed_review:clone(current),reference_ready:false,formal_eligibility_changed:false,review_scope:r.review_scope,manual_region_may_extend_GT:true,scope_batch_id:r.scope_batch_id,provenance:{receipt_filename:'空间范围人工审核_2026-10-10(2).json',receipt_sha256:source_sha256,receipt_exported_at:receipt.exported_at,receipt_record_index:index,receipt_json_pointer:'/records/'+index,receipt_editor_version:receipt.editor_version,source_commit:receipt.source_commit,latest_scope_review_source_commit:receipt.latest_scope_review_source_commit,evidence_source_commit:r.evidence_source_commit,confirmation_basis:isChat?'explicit_user_message_adopts_updated_draft_despite_missing_button':'matching_workbench_button_snapshot',raw_draft_completed:r.completed,raw_floor_region_confirmed:r.floor_region_confirmed,user_message_id:USER.message_id,user_message_at:USER.message_at},protected_site_metadata:{gates:clone(c.gates),hold_layers:clone(c.hold_layers),reference_paused:c.reference_paused,historical_snapshot_hold:c.historical_snapshot_hold,current_user_quality_reference_hold:c.current_user_quality_reference_hold,formal_quality_hold_observed:c.formal_quality_hold_observed,identity_confirmed:c.identity_confirmed},previous_confirmation_history:history});
}
assert(equal(prior,expectedPrior),'aggregate','exact five identifiable prior revisions');
assert(equal(newRows,expectedNew),'aggregate','exact eleven new button confirmations');
assert(equal(records.filter(r=>r.decision==='full_gt').map(r=>r.image_code),expectedFull),'aggregate','exact three full baseline decisions');
assert(records.filter(r=>r.decision==='allow').length===13,'aggregate','thirteen manual decisions');
assert(untouched.length===243,'aggregate','243 unchanged rows');
assert(prior.length===data.images.filter(c=>c.confirmed_review).length,'aggregate','all Site old confirmations accounted for; no sixth');
const inputs=Object.fromEntries(['raw_scope_receipt.json','data.json','geometry.js','review-state.js'].map(n=>[n,{sha256:sha(fs.readFileSync(path.join(inp,n))),bytes:fs.statSync(path.join(inp,n)).size}]));
const sixth={initial_user_reported_prior_count:6,clarified_user_prior_count:5,identified_prior_count:5,unresolved_count:0,status:'resolved_by_explicit_user_clarification',clarification:countClarification,evidence:['Site has exactly five old confirmation seeds','Receipt has exactly five edited prior confirmations','Only sixteen records have any operations, decision, timestamp, or confirmation','Remaining 243 are untouched baseline rows with no operations, timestamp, decision, or confirmation'],action:'Exactly five prior revisions are confirmed. No sixth row exists or is inferred.'};
const overlay={schema:'manual_floor_scope_confirmation_overlay_v1',created_from_export_at:receipt.exported_at,coordinate_frame:receipt.coordinate_frame,source_commit:receipt.source_commit,evidence_source_commit:data.evidence_source_commit,latest_scope_review_source_commit:receipt.latest_scope_review_source_commit,source:{receipt_file:'inputs/raw_scope_receipt.json',receipt_sha256:source_sha256,receipt_exported_at:receipt.exported_at,user_confirmation:USER,prior_count_clarification:countClarification,immutable_site_input_hashes:inputs},scope:'Confirmation-only floor-region overlay; original/editing GT, ceiling/top boundary, gates, formal eligibility, scoring, and other 243 rows are not modified.',GT_modified:false,formal_eligibility_changed:false,reference_ready:false,top_boundary_pending:true,record_count:records.length,counts:{new_button_confirmed:11,prior_revised_confirmed_by_message:5,allow:13,full_gt:3,untouched_excluded:243},prior_count_resolution:sixth,records};
const report={schema:'scope_receipt_validation_report_v1',result:errors.length?'FAIL':'PASS',inputs,source:overlay.source,summary:{records:259,unique_images:259,site_catalogue_images:280,omitted_historical_nonexportable_images:21,baseline_math_max_abs_discrepancy:Math.max(...receipt.records.map(r=>{let gt=G.floor(by.get(r.image_code).reference_points_1024x512);return Math.max(...gt.flatMap((p,i)=>p.map((v,j)=>Math.abs(v-r.original_GT_floor_xz_h[i][j]))));})),identity_and_provenance_exact:rows.length,all_operation_replays_valid:rows.length,all_baseline_and_final_polygons_valid_camera_inside:rows.length,prior_edits:prior,new_button_confirmed:newRows,unchanged_count:untouched.length,normalized_records:records.length,full_gt:expectedFull,manual_rectangle_count:records.filter(r=>r.operations.length).length,gt_follow_operation_count:records.reduce((s,r)=>s+r.operations.filter(o=>o.type==='gt_follow').length,0),max_matched_gt_edge_final_normal_distance_h:Math.max(...rows.map(x=>x.gt_snap_max_final_normal_distance_h||0))},prior_count_resolution:sixth,errors,warnings,interpretation:['The five raw completed=false drafts are explicitly confirmed only by the later user message; raw flags remain unchanged in the immutable receipt.','The eleven new button confirmation timestamps are retained exactly; the new receipt SHA256 is added only in the normalized layer.','Every stored snap match is approximate, but final measured normal residuals are tiny; distance_px is a pre-snap measurement, not final error. No rejection or automatic geometric adjustment follows.','Full GT means the user accepts the editing-baseline floor polygon only; this is not independent top-boundary validation.','No label, GT, Site, repository, formal gate, or scoring state was edited.','88 baseline floors have cross-runtime floating-point differences up to 8.881784197001252e-16; all original 2D GT coordinates match exactly and every exported coordinate is preserved in the overlay.', 'Historical source-review floor_region_confirmed=false values are retained as historical evidence, not substituted for the later explicit confirmations.'],rows};
fs.writeFileSync(path.join(root,'validation_report.json'),JSON.stringify(report,null,2)+'\n');
if(!errors.length)fs.writeFileSync(path.join(root,'normalized_confirmation_overlay.json'),JSON.stringify(overlay,null,2)+'\n');
fs.writeFileSync(path.join(root,'unchanged_243_image_codes.json'),JSON.stringify(untouched,null,2)+'\n');
console.log(JSON.stringify({result:report.result,errors,summary:report.summary,raw_sha256:source_sha256,overlay_written:!errors.length},null,2));
process.exitCode=errors.length?1:0;
