#!/usr/bin/env node
'use strict';
// Apply only the validated floor-confirmation overlay; no GT or gate changes.
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto'),S=require('./dist/review-state.js');
const HERE=__dirname,clone=S.clone,sha=b=>crypto.createHash('sha256').update(b).digest('hex'),read=p=>JSON.parse(fs.readFileSync(p));
const FILES={raw:'fixtures/received-review-v3.2-20261010.json',overlay:'fixtures/accepted-review-v3.3-20261010.json',report:'fixtures/receipt-validation-v3.3-20261010.json'};
function integrate(input,overlay,rawBytes,report){
 const data=clone(input),raw=JSON.parse(rawBytes),by=Object.fromEntries(data.images.map(c=>[c.image_code,c]));
 assert(report.result.startsWith('PASS')&&report.errors.length===0,'Canonical validation must pass');
 assert.equal(sha(rawBytes),overlay.source.receipt_sha256,'Immutable raw receipt hash');
 assert.equal(overlay.source_commit,data.source_commit,'Keep source compatibility key');
 assert.equal(overlay.records.length,16);assert.equal(new Set(overlay.records.map(r=>r.image_code)).size,16);
 assert.equal(overlay.counts.prior_revised_confirmed_by_message,5);assert.equal(overlay.counts.new_button_confirmed,11);
 const untouched=Object.fromEntries(data.images.filter(c=>!overlay.records.some(r=>r.image_code===c.image_code)).map(c=>[c.image_code,clone(c)]));
 for(const r of overlay.records){
  const c=by[r.image_code],old=clone(c),rawRow=raw.records[r.provenance.receipt_record_index];
  assert(c&&c.editable);assert.equal(c.image_id,r.image_id);assert.equal(c.reference_object_id,r.reference_object_id);
  assert.deepStrictEqual(c.reference_points_1024x512,r.editing_reference_points_1024x512);
  assert.equal(rawRow.image_code,c.image_code);assert.deepStrictEqual(rawRow.polygon,r.polygon);assert.deepStrictEqual(rawRow.operations,r.operations);
  const confirmed=S.verifyConfirmation(c,r.confirmed_review);
  assert(S.samePoly(confirmed.polygon,rawRow.polygon));assert.deepStrictEqual(confirmed.operations,rawRow.operations);
  assert(confirmed.top_boundary_pending&&confirmed.floor_region_confirmed);assert.equal(r.reference_ready,false);assert.equal(r.formal_eligibility_changed,false);
  // Store submitted floats exactly. Verification tolerates only numerical replay noise.
  c.confirmed_review=clone(r.confirmed_review);
  const history=clone(c.confirmed_review_history||[]);
  for(const h of r.previous_confirmation_history||[])if(h.role==='site_prior_confirmed_review'&&!history.some(v=>JSON.stringify(v)===JSON.stringify(h.snapshot)))history.push(clone(h.snapshot));
  c.confirmed_review_history=history;
  c.scope_receipt_evidence={...clone(r.provenance),raw_receipt_file:'catalogue/scope_receipt_20261010_raw.json',accepted_overlay_file:'catalogue/scope_receipt_20261010_accepted.json',previous_confirmation_history:clone(r.previous_confirmation_history||[]),geometry_policy:'Use submitted operations and polygon as accepted. No resnapping, gt_follow conversion, or polygon correction.',reference_ready:false,formal_eligibility_changed:false,top_boundary_pending:true};
  if(c.scope_batch_id==='user_scope_batch11_20261010')c.question=`本轮 ${c.scope_batch_index}/11 · 已接回底面范围确认，可查看或继续修改；原范围意见及确认来源保留。顶界与正式资格仍需单独核实。`;
  const protectedKeys=Object.keys(old).filter(k=>!['confirmed_review','confirmed_review_history','scope_receipt_evidence','question'].includes(k));
  for(const k of protectedKeys)assert.deepStrictEqual(c[k],old[k],`Protected metadata: ${c.image_code}.${k}`);
 }
 for(const [id,row]of Object.entries(untouched))assert.deepStrictEqual(by[id],row,'Unchanged outside accepted 16: '+id);
 data.editor_data_revision='full_scope_catalogue_confirmed16_20261010';data.editor_version='3.3';
 data.counts.confirmed_received=data.images.filter(c=>c.confirmed_review?.floor_region_confirmed).length;
 data.counts.confirmed_current_queue=data.images.filter(c=>c.scope_batch_id==='user_scope_batch11_20261010'&&c.confirmed_review?.floor_region_confirmed).length;
 assert.equal(data.counts.confirmed_received,16);assert.equal(data.counts.confirmed_current_queue,11);
 data.confirmation_notice='已接回 16 张明确确认的底面范围（本轮 11 张及之前 5 张的更新）；有效本地修改继续保留。';
 data.candidate_notice='本轮11图底面范围已确认接回，之前5图采用最新回执及聊天确认；其余图片仍按既有证据继续复核。顶界、正式资格与评分未因此完成。';
 data.latest_scope_receipt={exported_at:raw.exported_at,sha256:sha(rawBytes),accepted_count:16,old_revised_count:5,new_button_count:11,source_user_confirmation:clone(overlay.source.user_confirmation),raw_file:'catalogue/scope_receipt_20261010_raw.json',accepted_file:'catalogue/scope_receipt_20261010_accepted.json'};
 data.new_scope_batch={...data.new_scope_batch,confirmed_received:11,scope:'Eleven floor regions explicitly confirmed in the received workbench export. This receipt does not validate top boundaries or change formal eligibility.'};
 return data;
}
function main(){
 const rawBytes=fs.readFileSync(path.join(HERE,FILES.raw)),overlay=read(path.join(HERE,FILES.overlay)),report=read(path.join(HERE,FILES.report)),dest=path.join(HERE,'dist');
 const data=integrate(read(path.join(dest,'data.json')),overlay,rawBytes,report);
 for(const r of overlay.records){const c=data.images.find(x=>x.image_code===r.image_code),p=path.join(dest,c.detail_file),detail=read(p);for(const k of ['confirmed_review','confirmed_review_history','scope_receipt_evidence'])detail[k]=clone(c[k]);fs.writeFileSync(p,JSON.stringify(detail));}
 fs.writeFileSync(path.join(dest,'data.json'),JSON.stringify(data));
 fs.writeFileSync(path.join(dest,'catalogue/scope_receipt_20261010_raw.json'),rawBytes);
 fs.copyFileSync(path.join(HERE,FILES.overlay),path.join(dest,'catalogue/scope_receipt_20261010_accepted.json'));
 console.log('Accepted 16 floor regions: 5 user-chat updates + 11 button confirmations; preserved raw receipt, old history, GT, gates, and source compatibility.');
}
module.exports={integrate,FILES};if(require.main===module)main();
