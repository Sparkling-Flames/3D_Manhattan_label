#!/usr/bin/env node
'use strict';
// Add source-backed navigation metadata only. Never alter GT, gates, drafts, or confirmations.
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const clone=x=>JSON.parse(JSON.stringify(x));
const FILES={queue:'dist/catalogue/missing-room-scope/extended_queue.json',validation:'dist/catalogue/missing-room-scope/validation.json'};
function integrate(input,queue){
 const data=clone(input);for(const original of JSON.parse(fs.readFileSync(path.join(__dirname,'dist/catalogue/recovered-room-views/candidate_entries.json')))){if(!data.images.some(c=>c.image_code===original.image_code)){const c=clone(original);c.evidence_source_commit=c.reference_provenance.source_commit;c.source_documents=[c.reference_provenance.snapshot,c.reference_provenance.independent_import_crosscheck,c.reference_provenance.original_manual_audit].map(v=>({path:v.path,url:v.url,pointer:v.pointer||null}));data.images.push(c)}}const by=Object.fromEntries(data.images.map(c=>[c.image_code,c]));
 assert.equal(queue.schema,'source_backed_room_scope_queue_v1');
 assert.equal(queue.source_commit,data.source_commit,'Queue and editor source identity must agree');
 assert.equal(data.images.length,282);assert.equal(data.images.filter(c=>c.in_current_corpus).length,259);
 const ids=new Set(queue.cases.map(c=>c.image_code));assert.equal(ids.size,queue.cases.length);
 const preserve=queue.preserve_confirmed_image_codes;
 assert.equal(preserve.length,16);assert(preserve.every(code=>by[code]?.confirmed_review?.floor_region_confirmed));
 for(const code of preserve)for(const k of ['polygon','operations','cuts','decision','note','completed','confirmed_at','floor_region_confirmed'])assert.deepStrictEqual(by[code].confirmed_review[k],queue.preserved_confirmations[code][k],'Exact accepted confirmation content '+code+'.'+k);
 const groups=queue.room_groups.map(g=>({...clone(g),source_download:'catalogue/missing-room-scope/'+g.room_source.path,visual_contact_sheet:g.visual_contact_sheet?'catalogue/missing-room-scope/'+g.visual_contact_sheet:null}));
 for(const g of groups){assert.equal(g.scope_votes_from_group,0);assert.equal(g.scope_approval_propagation_allowed,false)}
 for(const c of data.images){
  const memberships=groups.filter(g=>g.image_codes.includes(c.image_code)).map(g=>g.group_id);
  if(memberships.length)c.room_scope_group_ids=memberships;
 }
 queue.cases.forEach((q,order)=>{
  const c=by[q.image_code];assert(c&&c.editable&&(c.in_current_corpus||c.recovered_reference_view));assert(!c.confirmed_review);assert(!preserve.includes(q.image_code));
  for(const k of ['image_id','reference_object_id','reference_version','original_reference_object_id'])assert.deepStrictEqual(c[k],q[k],'Queue reference identity '+q.image_code+'.'+k);
  assert.equal(q.floor_region_confirmed,false);assert.equal(q.reference_ready,false);
  assert(['原评论明确范围差异','同房间待核对','范围线索待核对'].includes(q.queue_label));
  c.categories=[...new Set([...(c.categories||[]),'source_backed_scope_clues',...(q.priority<=2?['missing_room_scope_review']:[])])];
  c.missing_room_scope={order,priority:q.priority,label:q.queue_label,reason:q.queue_reason,scope_difference_status:q.scope_difference_status,reference_warning:q.historical_comment_GT_version_warning||c.evidence_summary||'',source_queue:FILES.queue.slice(5),direct_evidence_count:q.direct_evidence.length,source_summary:q.direct_evidence.slice(0,2).map(e=>({text:e.text,source_pointer:e.source_pointer,record_ids:e.record_ids||[],reference_version:e.reference_version||null,reference_id:e.reference_id||null,source:e.sources?.find(s=>s.role==='raw_review_export')||e.sources?.[0]||null})),independent_votes:null,evidence_count_is_not_vote_count:true};
 });
 data.default_category='missing_room_scope_review';data.initial_image=queue.initial_image;
 data.editor_version='3.4';data.editor_data_revision='source_backed_room_scope_review_20261010';
 data.room_scope_groups=groups;
 data.missing_room_scope_queue={schema:queue.schema,source_file:FILES.queue.slice(5),priority_image_codes:queue.cases.filter(q=>q.priority<=2).map(q=>q.image_code),all_clue_image_codes:queue.cases.map(q=>q.image_code),preserved_confirmed_image_codes:clone(preserve),external_related_views:clone(queue.external_related_views),label_definition:clone(queue.label_definition),stopping_condition:queue.stopping_condition};
 const priorityCodes=new Set(queue.cases.filter(q=>q.priority<=2).map(q=>q.image_code)),assignedGroups=groups.filter(g=>g.image_codes.some(code=>priorityCodes.has(code)));
 data.room_review_batch_policy={policy_id:'room_review_no_operations_20261010',user_message_id:'Sentinel_c96ad78b3cc8819189ffe4ca118d835e',user_instruction_at:'2026-10-10T12:05:33Z',user_instruction:'嗯嗯,你把这几张所在的同房间的图,都给我进行复核.我没有任何切割/操作的就是说明 继续使用原gt空间',no_operation_meaning:'use_displayed_editing_GT',scope:'available_editable_views_in_the_four_assigned_priority_room_groups_only',assigned_room_group_ids:assignedGroups.map(g=>g.group_id),assigned_image_codes:[...new Set(assignedGroups.flatMap(g=>g.image_codes))].filter(code=>by[code]?.editable),not_applied_before_export:true,preserve_existing_received_confirmations:true,explicit_uncertain_wins:true,alternative_regions_not_automatically_approved:true};
 data.counts.catalogue_images=data.images.length;data.counts.recovered_reference_views=data.images.filter(c=>c.recovered_reference_view).length;
 data.counts.missing_room_priority=queue.cases.filter(q=>q.priority<=2).length;
 data.counts.source_backed_scope_clues=queue.cases.length;data.counts.room_scope_groups=groups.length;data.counts.unavailable_related_views=queue.external_related_views.length;
 data.confirmation_notice=`优先核对 ${data.counts.missing_room_priority} 图；全部 ${queue.cases.length} 条图片线索可另行筛选。已接回 16 图底面确认，原坐标与操作保留。`;
 data.candidate_notice='文字线索与房间关联是核对入口，不要求每条线索重新画范围；各图独立判断，同房不等于同范围。顶界、GT、正式资格和旧分数保持原状。';
 // Every pre-existing image field except additive categories must remain exactly intact.
 input.images.forEach(old=>{const c=by[old.image_code];for(const key of Object.keys(old)){if(['categories','room_scope_group_ids','missing_room_scope'].includes(key))continue;assert.deepStrictEqual(c[key],old[key],'Protected image field '+old.image_code+'.'+key)}for(const category of old.categories||[])assert(c.categories.includes(category))});
 return data;
}
function main(){const root=__dirname,queue=JSON.parse(fs.readFileSync(path.join(root,FILES.queue))),dest=path.join(root,'dist/data.json');const data=integrate(JSON.parse(fs.readFileSync(dest)),queue);fs.writeFileSync(dest,JSON.stringify(data));console.log(`Source-backed clues: ${data.counts.source_backed_scope_clues}; priority default: ${data.counts.missing_room_priority}; room groups: ${data.counts.room_scope_groups}; all 16 confirmations unchanged.`)}
module.exports={integrate,FILES};if(require.main===module)main();
