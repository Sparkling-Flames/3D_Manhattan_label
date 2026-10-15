'use strict';
const fs=require('fs'),assert=require('assert'),crypto=require('crypto'),S=require('./dist/review-state.js'),G=require('./dist/geometry.js'),{integrate,FILES}=require('./integrate-confirmed-receipt.cjs');
const read=p=>JSON.parse(fs.readFileSync(p)),base=read('fixtures/published-v3.2-data.json'),data=read('dist/data.json'),rawBytes=fs.readFileSync(FILES.raw),raw=JSON.parse(rawBytes),overlay=read(FILES.overlay),report=read(FILES.report);
let checks=0;const check=(v,m)=>{assert(v,m);checks++},eq=(a,b,m)=>{assert.deepStrictEqual(a,b,m);checks++};
const by=Object.fromEntries(data.images.map(c=>[c.image_code,c])),baseBy=Object.fromEntries(base.images.map(c=>[c.image_code,c])),rawBy=Object.fromEntries(raw.records.map(r=>[r.image_code,r])),ids=new Set(overlay.records.map(r=>r.image_code));
eq(integrate(base,overlay,rawBytes,report),data,'Portable fixture rebuilds current data exactly');
eq(integrate(data,overlay,rawBytes,report),data,'Re-running integration is idempotent');
eq(fs.readFileSync('dist/catalogue/scope_receipt_20261010_raw.json'),rawBytes,'Raw receipt is byte-preserved');
eq(read('dist/catalogue/scope_receipt_20261010_accepted.json'),overlay);
eq(data.source_commit,base.source_commit);eq(data.counts.confirmed_received,16);eq(data.counts.confirmed_current_queue,11);
const init=S.initialize(data,null),stored={source_commit:data.source_commit,drafts:{},confirmations:{}};
for(const r of raw.records){stored.drafts[r.image_code]=S.clone(r);if(r.confirmed_version)stored.confirmations[r.image_code]=S.clone(r.confirmed_version);}
const resumed=S.initialize(data,stored);
for(const r of overlay.records){
 const c=by[r.image_code],old=baseBy[r.image_code],submitted=rawBy[r.image_code],detail=read('dist/'+c.detail_file);
 eq(c.confirmed_review,r.confirmed_review);eq(c.confirmed_review.polygon,submitted.polygon,'Submitted coordinates unchanged');eq(c.confirmed_review.operations,submitted.operations,'Never resnap or add gt_follow');
 check(init.drafts[r.image_code].completed);check(resumed.drafts[r.image_code].completed,'Matching received draft auto-confirms');check(resumed.confirmations[r.image_code].floor_region_confirmed);eq(resumed.drafts[r.image_code].polygon,submitted.polygon);
 check(c.confirmed_review.top_boundary_pending);eq(c.scope_receipt_evidence.reference_ready,false);eq(c.scope_receipt_evidence.formal_eligibility_changed,false);
 for(const k of Object.keys(old).filter(k=>!['confirmed_review','question'].includes(k)))eq(c[k],old[k],'Original data retained: '+r.image_code+'.'+k);
 for(const k of ['confirmed_review','confirmed_review_history','scope_receipt_evidence'])eq(detail[k],c[k],'Detail/index parity');
 if(old.confirmed_review){eq(c.confirmed_review.source,'user_chat');eq(c.confirmed_review.confirmed_at,'2026-10-10T11:53:17Z');eq(c.confirmed_review_history,[old.confirmed_review]);check(!submitted.completed&&!submitted.floor_region_confirmed,'Raw missing-button flags are not rewritten');}
 else{eq(c.confirmed_review.source,'workbench_button');eq(c.confirmed_review.confirmed_at,submitted.confirmed_version.confirmed_at);eq(c.confirmed_review_history,[]);}
 // A newer edited note is a different review and must survive publication.
 const newer=S.clone(stored);newer.drafts[r.image_code].note+=' newer local edit';newer.drafts[r.image_code].updated_at='2026-10-10T12:30:00Z';
 const retained=S.initialize(data,newer);eq(retained.drafts[r.image_code].note,newer.drafts[r.image_code].note);eq(retained.drafts[r.image_code].updated_at,newer.drafts[r.image_code].updated_at);check(!retained.drafts[r.image_code].completed);eq(retained.confirmations[r.image_code],init.confirmations[r.image_code]);
 // A newer explicit confirmation also takes precedence over this published seed.
 const clicked=S.confirm(c,retained.drafts[r.image_code],'2026-10-10T12:31:00Z');newer.drafts[r.image_code]=clicked.draft;newer.confirmations[r.image_code]=clicked.confirmation;
 const latest=S.initialize(data,newer);eq(latest.confirmations[r.image_code],clicked.confirmation);check(latest.drafts[r.image_code].completed);
}
for(const c of data.images)if(!ids.has(c.image_code))eq(c,baseBy[c.image_code],'Every non-receipt catalogue row unchanged');
eq(raw.records.filter(r=>!ids.has(r.image_code)).length,243);eq(data.images.filter(c=>!ids.has(c.image_code)&&!c.editable).length,21);
eq(overlay.records.filter(r=>r.operations.some(o=>o.type==='rectangle')).length,13);eq(overlay.records.flatMap(r=>r.operations).filter(o=>o.type==='gt_follow').length,0);
eq(overlay.records.filter(r=>r.decision==='full_gt').map(r=>r.image_code),['S9hNv5qa7GM-04','pa4otMbVnkk-14','wc2JMjhGNzB-26']);
const bad=S.clone(overlay);bad.records[0].polygon[0][0]+=.001;assert.throws(()=>integrate(base,bad,rawBytes,report));checks++;
assert.throws(()=>integrate(base,overlay,Buffer.from('{}'),report));checks++;
const qa={receipt_checks_passed:checks,accepted_regions:16,chat_reconfirmed_previous:5,button_confirmed_current_queue:11,raw_receipt_sha256:crypto.createHash('sha256').update(rawBytes).digest('hex'),source_compatibility_key_unchanged:true,all_other_243_exportable_and_21_readonly_rows_unchanged:true,old_confirmation_history_preserved:true,newer_local_edits_and_confirmations_preserved:true,submitted_polygons_and_operations_unchanged:true,browser_QA:'State and simulated UI checks only; no real browser visual/interaction pass claimed.',tested_on:'2026-10-10'};
fs.writeFileSync('QA-confirmed-receipt.json',JSON.stringify(qa,null,2)+'\n');console.log(qa);
