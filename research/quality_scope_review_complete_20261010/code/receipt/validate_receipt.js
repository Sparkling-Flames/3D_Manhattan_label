'use strict';
// Offline receipt validation against immutable exported Site inputs. Node >=18.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=__dirname, inp=path.join(root,'inputs'),G=require('./inputs/geometry.js'),R=require('./inputs/review-state.js');
const load=n=>JSON.parse(fs.readFileSync(path.join(inp,n))),A=load('raw_scope_receipt.json'),D=load('data.json'),OLD=load('prior_normalized_confirmation_overlay.json'),OLDRAW=load('prior_raw_scope_receipt.json');
const clone=x=>JSON.parse(JSON.stringify(x)),eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const errors=[],warnings=[],rows=[],regionRows=[],steps=[],confirmationRows=[],snapRows=[],records=[],oldComparison=[];let checks=0;
const ck=(yes,where,check)=>{checks++;if(!yes)errors.push({where,check});};
const safe=(where,fn)=>{try{return fn()}catch(e){ck(false,where,e.message);return null}};
const counts=xs=>xs.reduce((a,x)=>(a[x]=(a[x]||0)+1,a),{});
const sourceSha=sha(fs.readFileSync(path.join(inp,'raw_scope_receipt.json')));
const user={message_id:'Sentinel_2646209598188191b7822706987eac95',message_at_precision:'2026-10-10 13:17 UTC (minute precision supplied)',verbatim:'完成了,统计好这些数据后,一并上传到github main',usage:'receipt handoff and publication request; not blanket confirmation of unedited unrelated rows'};
const by=new Map(D.images.map(c=>[c.image_code,c])),prior=new Map(OLD.records.map(c=>[c.image_code,c])),oldRaw=new Map(OLDRAW.records.map(c=>[c.image_code,c]));
const finite=(v,p)=>{if(typeof v==='number')ck(Number.isFinite(v),p,'finite numeric value');else if(Array.isArray(v))v.forEach((x,i)=>finite(x,p+'/'+i));else if(v&&typeof v==='object')Object.entries(v).forEach(([k,x])=>finite(x,p+'/'+k));};finite(A,'receipt');
const polyStats=p=>({vertices:p.length,area_h2:G.area(p),bounds:{min_x:Math.min(...p.map(q=>q[0])),max_x:Math.max(...p.map(q=>q[0])),min_z:Math.min(...p.map(q=>q[1])),max_z:Math.max(...p.map(q=>q[1]))}});
const ptSeg=(p,a,b)=>{let dx=b[0]-a[0],dy=b[1]-a[1],ll=dx*dx+dy*dy,t=ll?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/ll)):0;return Math.hypot(a[0]+t*dx-p[0],a[1]+t*dy-p[1])};
const camDist=p=>Math.min(...p.map((a,i)=>ptSeg([0,0],a,p[(i+1)%p.length])));
const delta=(p,q)=>({baseline:polyStats(p),current:polyStats(q),area_delta_h2:G.area(q)-G.area(p),area_relative_change:(G.area(q)-G.area(p))/G.area(p),ordered_coordinates_exactly_unchanged:eq(p,q),ordered_coordinates_equal_within_1e8:R.samePoly(p,q)});
const exportable=D.images.filter(c=>c.reference_points_1024x512?.length);
ck(A.schema==='manual_scope_crop_review_v2','root','schema');ck(A.editor_version==='3.4.2','root','editor version');
ck(A.exported_at==='2026-10-10T13:16:29.431Z','root','export time');ck(A.GT_modified===false,'root','GT unmodified');ck(eq(A.unrecovered_drafts,{}),'root','no unrecovered drafts');
ck(A.coordinate_frame==='camera_height_normalized_xz; original ERP 1024x512','root','coordinate frame');
for(const k of ['source_commit','latest_scope_review_source_commit'])ck(A[k]===D[k],'root',k+' matches Site');
ck(A.records.length===261&&exportable.length===261&&D.images.length===282,'root','261 exportable / 282 catalogue census');
ck(eq(A.records.map(r=>r.image_code),exportable.map(c=>c.image_code)),'root','exact census and order');
ck(new Set(A.records.map(r=>r.image_code)).size===261&&new Set(A.records.map(r=>r.image_id)).size===261,'root','unique image identity');
ck(D.images.filter(c=>!c.reference_points_1024x512?.length).every(c=>c.in_current_corpus===false&&!c.confirmed_review),'root','21 omitted historical catalogue rows are noneditable/unconfirmed');
const policy=A.room_review_batch_policy,basePolicy=D.room_review_batch_policy;
ck(eq(Object.fromEntries(Object.entries(policy).filter(([k])=>!['applied_at','applied_image_codes'].includes(k))),basePolicy),'policy','exact trusted Site policy');
ck(policy.applied_at===A.exported_at,'policy','policy evaluation at export');ck(policy.assigned_image_codes.length===23&&new Set(policy.assigned_image_codes).size===23,'policy','23 distinct assigned images');
const expectedRecordKeys='active_space_region_id axis_angle completed confirmed_version cropped_floor_xz_h cuts decision editing_reference_object_id editing_reference_points_1024x512 editing_reference_version evidence_source_commit floor_region_confirmed formal_eligibility_changed historical_original_GT_object_id historical_original_GT_points_1024x512 image_code image_id in_current_corpus latest_user_scope_review manual_region_may_extend_GT note operations original_GT_floor_xz_h original_GT_points_1024x512 polygon received_confirmed_history received_confirmed_version recovered_reference_view reference_object_id reference_provenance reference_ready reference_version review_scope scope_batch_id scope_receipt_evidence source_documents space_regions top_boundary_pending'.split(' ').sort();
function validateGeometry(c,r,label,recordSteps){
 const v=safe(label,()=>R.verifyOps(c,r));if(!v)return null;
 ck(R.samePoly(v.polygon,r.polygon)&&R.samePoly(v.polygon,r.cropped_floor_xz_h||r.polygon),label,'operation replay equals polygon aliases within 1e-8');
 ck(eq(v.operations,r.operations)&&eq(v.cuts,r.cuts),label,'exact effective operations and legacy cuts');
 ck(v.completed===r.completed,label,'completed field is internally valid');
 ck(G.valid(v.polygon)&&R.cameraInside(v.polygon),label,'valid simple polygon and camera strictly inside');
 let p=G.floor(c.reference_points_1024x512);for(let [i,op] of r.operations.entries()){
  const pre=p;p=safe(label+'/operations/'+i,()=>G.replay(pre,[op]));if(!p){ck(false,label,'operation produced null');break;}
  ck(G.valid(p)&&R.cameraInside(p),label+'/operations/'+i,'each operation keeps valid camera-containing geometry');
  if(['edge_move','edge_follow'].includes(op.type))ck(op.index>=0&&op.index<pre.length,label+'/operations/'+i,'edge index bound to pre-operation polygon');
  if(recordSteps)steps.push({image_code:c.image_code,region_id:r.region_id||'primary',operation_index:i,type:op.type,input_vertices:pre.length,output_vertices:p.length,valid:true,camera_inside:true,area_h2:G.area(p),polygon:clone(p)});
  if(recordSteps&&op.gt_snap){
   ck(op.gt_snap.version===1&&Array.isArray(op.gt_snap.matches),label,'valid snap metadata container');
   for(const m of op.gt_snap.matches){
    let seg=op.type==='edge_move'?G.moveEdgeDetailed(pre,op.index,op.offset)?.segment:op.type==='rectangle'?[p[m.edge],p[(m.edge+1)%p.length]]:null;
    ck(Number.isInteger(m.edge)&&m.edge>=0&&m.edge<(op.type==='rectangle'?4:pre.length),label,'snap edge index bound');
    ck(Number.isFinite(m.distance_px)&&m.distance_px>=0,label,'stored presnap distance finite');
    const gt=G.floor(c.reference_points_1024x512),kind=m.kind||'finite_edge';
    if(kind==='vertex')ck(Number.isInteger(m.gt_vertex)&&m.gt_vertex>=0&&m.gt_vertex<gt.length,label,'snap GT vertex binding');
    else ck(Number.isInteger(m.gt_edge)&&m.gt_edge>=0&&m.gt_edge<gt.length,label,'snap GT edge binding');
    let measure={};if(seg&&kind==='vertex')measure.final_target_vertex_to_edited_segment_h=ptSeg(gt[m.gt_vertex],...seg);
    else if(seg){let matches=G.edgeSnapCandidates(...seg,gt,10000,{maxAngleDegrees:5}),matched=matches.find(s=>s.gt_edge===m.gt_edge);let a=gt[m.gt_edge],b=gt[(m.gt_edge+1)%gt.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);measure={final_finite_overlap_h:matched?matched.overlap[1]-matched.overlap[0]:0,final_max_normal_residual_on_finite_overlap_h:matched?.distance??null,final_max_edited_endpoint_to_target_support_line_h:Math.max(...seg.map(p=>Math.abs(G.cross(a,b,p))/len))};}
    snapRows.push({image_code:c.image_code,region_id:r.region_id||'primary',operation_index:i,type:op.type,snap_kind:kind,...clone(m),...measure,distance_px_meaning:'presnap viewport distance; not final geometric residual'});
   }
  }
 }
 return v;
}
function validateConfirmation(c,r,label,role){
 const v=safe(label,()=>R.verifyConfirmation(c,r));if(!v)return null;
 validateGeometry(c,r,label,false);
 ck(['workbench_button','user_chat','user_instruction_no_operations'].includes(r.source),label,'explicit allowed provenance source (no fallback coercion)');
 ck(Number.isFinite(Date.parse(r.confirmed_at))&&Date.parse(r.confirmed_at)<=Date.parse(A.exported_at),label,'confirmation timestamp <= export');
 ck(r.floor_region_confirmed===v.floor_region_confirmed,label,'confirmation floor flag consistent with decision');
 if(r.source==='user_chat')ck(r.confirmation_message_id===OLD.source.user_confirmation.message_id||(c.confirmed_review_history||[]).some(h=>eq(h.snapshot||h,r)),label,'chat confirmation tied to known prior explicit approval or exact trusted historical snapshot');
 if(r.source==='user_instruction_no_operations')ck(policy.assigned_image_codes.includes(c.image_code)&&!r.operations.length&&r.decision==='full_gt'&&r.no_operation_policy_id===policy.policy_id&&r.confirmation_message_id===policy.user_message_id,label,'no-operation confirmation tightly scoped');
 confirmationRows.push({image_code:c.image_code,path:label,role,source:r.source,confirmed_at:r.confirmed_at,decision:r.decision,operation_count:r.operations.length,valid:true});return v;
}
for(let [index,r] of A.records.entries()){
 const id=r.image_code,c=by.get(id),label='/records/'+index;
 ck(eq(Object.keys(r).filter(k=>k!=='updated_at').sort(),expectedRecordKeys),label,'exact current record schema');if(!c){ck(false,label,'known image');continue;}
 let detail=null;if(c.recovered_reference_view){detail=load('records/'+id+'.json');ck(detail.image_code===id&&detail.image_id===c.image_id,label,'lazy detail identity');}
 const expectedHist=(detail?.original_reference_points_1024x512)||c.original_reference_points_1024x512||(c.reference_version==='original'?c.reference_points_1024x512:null);
 for(const [rk,value]of Object.entries({image_id:c.image_id,reference_object_id:c.reference_object_id,original_GT_points_1024x512:c.reference_points_1024x512,reference_version:c.reference_version,editing_reference_version:c.reference_version,editing_reference_object_id:c.reference_object_id,editing_reference_points_1024x512:c.reference_points_1024x512,historical_original_GT_object_id:c.original_reference_object_id||null,historical_original_GT_points_1024x512:expectedHist,received_confirmed_version:c.confirmed_review||null,received_confirmed_history:c.confirmed_review_history||[],scope_receipt_evidence:c.scope_receipt_evidence||null,evidence_source_commit:c.evidence_source_commit||D.evidence_source_commit,source_documents:c.source_documents||[],reference_provenance:c.reference_provenance||null,in_current_corpus:c.in_current_corpus,recovered_reference_view:!!c.recovered_reference_view,scope_batch_id:c.scope_batch_id||null,latest_user_scope_review:c.latest_user_scope_review||null}))ck(eq(r[rk],value),label,rk+' exact Site provenance match');
 const gt=G.floor(c.reference_points_1024x512);ck(R.samePoly(gt,r.original_GT_floor_xz_h),label,'baseline floor math');ck(G.valid(gt)&&R.cameraInside(gt),label,'baseline valid and camera inside');
 for(const k of ['top_boundary_pending','manual_region_may_extend_GT'])ck(r[k]===true,label,k+' remains true');
 for(const k of ['reference_ready','formal_eligibility_changed'])ck(r[k]===false,label,k+' remains false');
 ck(r.review_scope==='floor_region_only; top boundary must be separately validated',label,'floor-only scope');
 ck(eq(r.polygon,r.cropped_floor_xz_h),label,'root polygon aliases numerically exact');
 const verified=safe(label+'/space_regions',()=>R.verifyRegions(c,r.space_regions,A.source_commit));if(!verified)continue;
 ck(r.active_space_region_id===r.space_regions.active_region_id,label,'active region ID aliases exact');
 const active=r.space_regions.regions.find(x=>x.region_id===r.active_space_region_id);
 for(const k of ['polygon','operations','cuts','decision','note','top_boundary_pending','axis_angle','completed','updated_at','cropped_floor_xz_h','confirmed_version','floor_region_confirmed'])ck(eq(r[k],active[k]),label,'root equals active-region field '+k);
 validateGeometry(c,r,label,false);
 if(r.received_confirmed_version)validateConfirmation(c,r.received_confirmed_version,label+'/received_confirmed_version','received_primary');
 for(const [i,h]of r.received_confirmed_history.entries())validateConfirmation(c,h.snapshot||h,label+'/received_confirmed_history/'+i+(h.snapshot?'/snapshot':''),h.role||'historical');
 for(let [ri,reg]of r.space_regions.regions.entries()){
  const rp=label+'/space_regions/regions/'+ri,v=validateGeometry(c,reg,rp,true);if(!v)continue;
  ck(eq(reg.polygon,reg.cropped_floor_xz_h),rp,'region polygon aliases numerically exact');
  ck(reg.top_boundary_pending===true,rp,'candidate remains floor-only');
  let conf=reg.confirmed_version?validateConfirmation(c,reg.confirmed_version,rp+'/confirmed_version','current_region'):null;
  const matches=!!conf&&R.sameReview(v,conf),confirmed=matches&&conf.floor_region_confirmed;
  ck(reg.floor_region_confirmed===confirmed,rp,'exported confirmed flag equals verified current state');
  ck(reg.completed===matches,rp,'completion equals current matching snapshot');
  if(conf&&matches){ck(eq(reg.polygon,reg.confirmed_version.polygon)&&eq(reg.operations,reg.confirmed_version.operations)&&eq(reg.cuts,reg.confirmed_version.cuts),rp,'confirmed snapshot coordinates and effective operations numerically exact');ck(reg.updated_at===reg.confirmed_version.updated_at,rp,'confirmed edit timestamp exact');}
  if(reg.updated_at)ck(Number.isFinite(Date.parse(reg.updated_at))&&Date.parse(reg.updated_at)<=Date.parse(A.exported_at),rp,'edit timestamp <= export');
  const priorRecord=reg.region_id==='primary'?prior.get(id):null;
  const origin=confirmed?(priorRecord&&R.sameReview(reg,priorRecord.confirmed_review)?'inherited_prior_confirmation':conf.source==='user_instruction_no_operations'?'policy_no_operation_confirmation':'new_explicit_confirmation'):'unconfirmed';
  const state=confirmed?'confirmed':matches?'uncertain':conf?'modified_after_confirmation':reg.operations.length||reg.updated_at||reg.decision||reg.note?'unconfirmed_edited_draft':'untouched_unconfirmed_baseline';
  const rr={image_code:id,image_id:r.image_id,region_id:reg.region_id,region_name:reg.name,is_primary:reg.region_id==='primary',is_active:reg.region_id===r.active_space_region_id,source_pointer:rp,status:state,confirmation_origin:origin,confirmation_source:conf?.source||null,confirmed_at:conf?.confirmed_at||null,decision:reg.decision,operation_count:reg.operations.length,operation_types:reg.operations.map(o=>o.type),in_current_corpus:r.in_current_corpus,recovered_reference_view:r.recovered_reference_view,reference_version:r.reference_version,camera_inside:true,camera_boundary_min_distance_h:camDist(reg.polygon),geometry_delta:delta(gt,reg.polygon),included_in_overlay:confirmed};regionRows.push(rr);
  if(state==='untouched_unconfirmed_baseline')ck(!reg.confirmed_version&&!reg.operations.length&&!reg.cuts.length&&!reg.decision&&!reg.note&&!reg.updated_at&&R.samePoly(reg.polygon,gt),rp,'unconfirmed default remains pristine, never inferred as approved');
  if(confirmed){
   ck(c.editable===true,rp,'confirmed candidate is editable');
   const history=clone(r.received_confirmed_history);if(r.received_confirmed_version)history.push({role:'site_received_confirmation',snapshot:clone(r.received_confirmed_version)});
   records.push({image_code:id,image_id:r.image_id,region_id:reg.region_id,region_name:reg.name,is_primary:reg.region_id==='primary',is_active:reg.region_id===r.active_space_region_id,confirmation_origin:origin,reference_object_id:r.reference_object_id,editing_reference_version:r.editing_reference_version,editing_reference_object_id:r.editing_reference_object_id,editing_reference_points_1024x512:clone(r.editing_reference_points_1024x512),historical_original_GT_object_id:r.historical_original_GT_object_id,historical_original_GT_points_1024x512:clone(r.historical_original_GT_points_1024x512),...clone(reg.confirmed_version),polygon:clone(reg.polygon),cropped_floor_xz_h:clone(reg.polygon),confirmed_review:clone(reg.confirmed_version),in_current_corpus:r.in_current_corpus,recovered_reference_view:r.recovered_reference_view,reference_provenance:clone(r.reference_provenance),reference_ready:false,formal_eligibility_changed:false,review_scope:r.review_scope,manual_region_may_extend_GT:true,scope_batch_id:r.scope_batch_id,provenance:{receipt_filename:'空间范围人工审核_2026-10-10(3).json',receipt_sha256:sourceSha,receipt_exported_at:A.exported_at,receipt_record_index:index,receipt_json_pointer:rp,receipt_editor_version:A.editor_version,source_commit:A.source_commit,latest_scope_review_source_commit:A.latest_scope_review_source_commit,evidence_source_commit:r.evidence_source_commit,confirmation_basis:origin,confirmation_source:conf.source,source_binding:clone(reg.source_binding),user_handoff:user},protected_site_metadata:Object.fromEntries(['gates','hold_layers','reference_paused','historical_snapshot_hold','current_user_quality_reference_hold','formal_quality_hold_observed','identity_confirmed','annotation_count'].map(k=>[k,c[k]??null])),previous_confirmation_history:history});
  }
 }
 const current=regionRows.filter(x=>x.image_code===id),primaryRow=current.find(x=>x.is_primary);rows.push({...primaryRow,region_count:current.length,active_space_region_id:r.active_space_region_id,scope_batch_assigned:policy.assigned_image_codes.includes(id),priority_queue_member:D.missing_room_scope_queue.priority_image_codes.includes(id),previous_receipt_present:oldRaw.has(id)});
 if(prior.has(id)){const p=prior.get(id),pr=r.space_regions.regions.find(x=>x.region_id==='primary');oldComparison.push({image_code:id,polygon_exact:eq(pr.polygon,p.polygon),operations_exact:eq(pr.operations,p.operations),decision_exact:pr.decision===p.decision,confirmation_snapshot_exact:eq(pr.confirmed_version,p.confirmed_review),confirmed_at_exact:pr.confirmed_version?.confirmed_at===p.confirmed_at,geometry_delta:delta(p.polygon,pr.polygon)});}
}
const assigned=policy.assigned_image_codes.map(id=>rows.find(r=>r.image_code===id)),priority=D.missing_room_scope_queue.priority_image_codes.map(id=>rows.find(r=>r.image_code===id));
const newConfirmed=regionRows.filter(r=>r.confirmation_origin==='new_explicit_confirmation'),untouched=rows.filter(r=>r.status==='untouched_unconfirmed_baseline');
ck(prior.size===16&&oldComparison.length===16&&oldComparison.every(r=>r.polygon_exact&&r.operations_exact&&r.decision_exact&&r.confirmation_snapshot_exact&&r.confirmed_at_exact),'aggregate','all prior 16 confirmations preserved exactly');
ck(priority.length===19&&priority.every(r=>r?.status==='confirmed'&&r.confirmation_origin==='new_explicit_confirmation'),'aggregate','all priority 19 newly explicitly confirmed');
ck(assigned.length===23&&assigned.every(r=>r?.status==='confirmed'),'aggregate','all assigned 23 primary regions confirmed');
ck(eq(policy.applied_image_codes,records.filter(r=>r.source==='user_instruction_no_operations').map(r=>r.image_code)),'aggregate','policy applied list equals actual policy confirmations');
ck(records.length===35&&newConfirmed.length===19&&untouched.length===226,'aggregate','35 confirmed =16 inherited +19 new; 226 not approved');
ck(regionRows.length===261&&regionRows.every(r=>r.is_primary),'aggregate','261 primary regions; zero alternate candidates');
const fileNames=['raw_scope_receipt.json','data.json','geometry.js','review-state.js','app.js','prior_normalized_confirmation_overlay.json','prior_raw_scope_receipt.json','records/q9vSo1VnCiC-21.json','records/q9vSo1VnCiC-25.json'];
const inputs=Object.fromEntries(fileNames.map(n=>[n,{sha256:sha(fs.readFileSync(path.join(inp,n))),bytes:fs.statSync(path.join(inp,n)).size}]));
const summary={receipt_records:A.records.length,site_catalogue_images:D.images.length,omitted_historical_nonexportable_images:D.images.length-exportable.length,total_candidate_regions:regionRows.length,alternative_candidate_regions:regionRows.filter(r=>!r.is_primary).length,explicit_confirmed_images:new Set(records.map(r=>r.image_code)).size,confirmed_regions:records.length,confirmation_sources:counts(records.map(r=>r.source)),confirmation_origins:counts(records.map(r=>r.confirmation_origin)),decisions:counts(records.map(r=>r.decision)),new_confirmed_decisions:counts(newConfirmed.map(r=>r.decision)),geometrically_modified_confirmed_images:regionRows.filter(r=>r.included_in_overlay&&!r.geometry_delta.ordered_coordinates_equal_within_1e8).length,unconfirmed_pristine_images:untouched.length,modified_unconfirmed_regions:regionRows.filter(r=>r.status==='modified_after_confirmation'||r.status==='unconfirmed_edited_draft').length,uncertain_regions:regionRows.filter(r=>r.status==='uncertain').length,policy_auto_confirmation_count:policy.applied_image_codes.length,assigned_23_confirmed:assigned.filter(r=>r?.status==='confirmed').length,priority_19_confirmed:priority.filter(r=>r?.status==='confirmed').length,confirmed_current_corpus_images:records.filter(r=>r.in_current_corpus).length,confirmed_recovered_external_images:records.filter(r=>r.recovered_reference_view).length,operation_counts:counts(steps.map(s=>s.type)),operation_steps:steps.length,current_and_historical_confirmation_snapshots_checked:confirmationRows.length,snap_metadata_records:snapRows.length,snap_kinds:counts(snapRows.map(r=>r.snap_kind)),numerical_checks:checks,baseline_projection_max_abs_error:Math.max(...A.records.flatMap(r=>G.floor(by.get(r.image_code).reference_points_1024x512).flatMap((p,i)=>p.map((v,j)=>Math.abs(v-r.original_GT_floor_xz_h[i][j])))))};
const overlay={schema:'manual_floor_scope_confirmation_overlay_v1',extension_schema:'region_identity_and_confirmation_origin_v1',created_from_export_at:A.exported_at,coordinate_frame:A.coordinate_frame,source_commit:A.source_commit,evidence_source_commit:D.evidence_source_commit,latest_scope_review_source_commit:A.latest_scope_review_source_commit,source:{receipt_file:'inputs/raw_scope_receipt.json',receipt_sha256:sourceSha,receipt_exported_at:A.exported_at,user_handoff:user,immutable_input_hashes:inputs},scope:'Only explicitly confirmed individual floor regions. No alternative-region vote propagation or best-score selection. Baseline GT, top boundaries, formal eligibility and unrelated drafts remain unchanged.',GT_modified:false,formal_eligibility_changed:false,reference_ready:false,top_boundary_pending:true,record_count:records.length,counts:summary,records};
const report={schema:'scope_receipt_validation_report_v2',result:errors.length?'FAIL':'PASS',inputs,source:overlay.source,summary,errors,warnings,queue_coverage:{priority_19:priority,assigned_room_batch_23:assigned,policy:clone(policy)},prior_16_comparison:oldComparison,rows,region_rows:regionRows,operation_replay_steps:steps,confirmation_snapshots:confirmationRows,snap_metadata:snapRows,interpretation:['35 confirmations are not 261 confirmations. All 226 untouched unrelated baseline drafts remain unconfirmed.','No-operation policy was evaluated but applied to zero images: all assigned primaries already have matching explicit confirmations.','All 19 priority additions are button confirmations, including four full-GT decisions. The prior 16 snapshots are preserved exactly.','Both recovered q9 21/25 remain outside the current 259-image research corpus and contribute no newly invented research annotations. Historical-original coordinate fields are recovered original-equivalent snapshots, not proof of original TXT bytes.','Every export region is primary. No alternative candidate was created. edge_follow is supported by the frozen replay engine but this receipt has zero such operations.','Snap metadata is descriptive only; replay uses stored resolved operation coordinates. Vertex and extension matches are reported separately and are not misrepresented as finite-edge overlap.']};
const write=(n,v)=>fs.writeFileSync(path.join(root,n),JSON.stringify(v,null,2)+'\n');write('validation_report.json',report);if(!errors.length)write('normalized_confirmation_overlay.json',overlay);write('unconfirmed_226_image_codes.json',untouched.map(r=>r.image_code));
console.log(JSON.stringify({result:report.result,summary,errors,overlay_written:!errors.length,receipt_sha256:sourceSha},null,2));process.exitCode=errors.length?1:0;
