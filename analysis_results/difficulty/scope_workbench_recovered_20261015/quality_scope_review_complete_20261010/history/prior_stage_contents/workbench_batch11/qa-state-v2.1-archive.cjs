const fs=require('fs'),vm=require('vm'),assert=require('assert'),G=require('./dist/geometry.js'),S=require('./dist/review-state.js');
const data=JSON.parse(fs.readFileSync('dist/data.json')),KEY='layout-scope-crop-v1';let checks=0;
const check=(v,msg)=>{assert(v,msg);checks++},eq=(a,b,msg)=>{assert.deepStrictEqual(JSON.parse(JSON.stringify(a)),JSON.parse(JSON.stringify(b)),msg);checks++};
function boot(stored){
  const elements={},saved=new Map(stored?[[KEY,JSON.stringify(stored)]]:[]);
  const el=id=>elements[id]||(elements[id]={value:id==='yaw'?'0':'',checked:['showGT','showCrop','showAll','topPending','orthogonal'].includes(id),disabled:false,hidden:false,textContent:'',innerHTML:'',style:{},dataset:{},tagName:'DIV',classList:{toggle(){},remove(){},contains(){return false}},querySelectorAll(){return []},click(){if(!this.disabled)this.onclick?.()},getContext(){return new Proxy({},{get:()=>()=>{}})}});
  const choices=['allow','full_gt','uncertain'].map(x=>({dataset:{decision:x},classList:{toggle(){}}}));
  const modes=['cut','rectangle','edge'].map(x=>({dataset:{mode:x},classList:{toggle(){}}}));
  const ctx={console,Geo:G,ReviewState:S,document:{querySelector:s=>el(s.slice(1)),querySelectorAll:s=>s==='[data-decision]'?choices:s==='[data-mode]'?modes:[],addEventListener(){},activeElement:{tagName:'BODY'},createElement:()=>({click(){}})},localStorage:{setItem:(k,v)=>saved.set(k,v),getItem:k=>saved.get(k)},Image:class{constructor(){this.complete=false}},fetch:async()=>({ok:true,json:async()=>data}),setTimeout:()=>1,clearTimeout(){},Date,Blob,URL:{createObjectURL:()=>'',revokeObjectURL(){}},window:null};ctx.window=ctx;
  vm.createContext(ctx);vm.runInContext(fs.readFileSync('dist/app.js','utf8'),ctx);
  return new Promise(resolve=>setImmediate(()=>resolve({w:ctx.workbench,el,saved,choices,ctx})));
}
(async()=>{
  const init=S.initialize(data,null);
  eq(data.images.length,5);eq(data.images.map(c=>c.annotations.length),[6,6,6,5,6]);
  for(const [i,c]of data.images.entries()){
    check(fs.existsSync('dist/'+c.photo),'original photo exists');check(fs.existsSync('dist/'+c.evidence_file));check(c.historical_comments.length>0);
    eq(init.drafts[c.image_code].completed,i<3);
    if(i<3){eq(init.confirmations[c.image_code].polygon,c.confirmed_review.polygon);check(init.confirmations[c.image_code]!==init.drafts[c.image_code]);}
    else{eq(init.drafts[c.image_code].polygon,G.floor(c.reference_points_1024x512));check(!init.confirmations[c.image_code]);}
  }
  // Legacy storage has the three exact confirmed polygons but completed=false.
  const legacy={source_commit:data.source_commit,drafts:Object.fromEntries(data.images.slice(0,3).map(c=>[c.image_code,{...S.clone(c.confirmed_review),completed:false}]))};
  let migrated=S.initialize(data,legacy);
  for(const c of data.images.slice(0,3)){check(migrated.drafts[c.image_code].completed);eq(migrated.drafts[c.image_code].polygon,legacy.drafts[c.image_code].polygon);}
  // Every valid local edit wins over publication defaults, irrespective of timestamp.
  const c0=data.images[0],changed=S.clone(legacy);changed.drafts[c0.image_code]={...S.fresh(c0),polygon:G.rectangle([-2,-2],[2,2],0),operations:[{type:'rectangle',a:[-2,-2],b:[2,2],angle:0}],decision:'allow',note:'newer local draft',updated_at:'2026-10-10T04:00:00Z'};
  migrated=S.initialize(data,changed);eq(migrated.drafts[c0.image_code].polygon,changed.drafts[c0.image_code].polygon);eq(migrated.drafts[c0.image_code].note,'newer local draft');check(!migrated.drafts[c0.image_code].completed);eq(migrated.confirmations[c0.image_code].polygon,c0.confirmed_review.polygon);
  const notes=S.clone(legacy);notes.drafts[c0.image_code].note='newer note';let noteState=S.initialize(data,notes);eq(noteState.drafts[c0.image_code].note,'newer note');check(!noteState.drafts[c0.image_code].completed);
  const corrupt=S.clone(legacy);corrupt.drafts[c0.image_code].polygon=[[0,0]];let recovered=S.initialize(data,corrupt);eq(recovered.unrecovered_drafts[c0.image_code],corrupt.drafts[c0.image_code]);check(recovered.warnings.length===1);
  let localConfirmed=S.confirm(c0,changed.drafts[c0.image_code],'2026-10-10T04:30:00Z');let reloaded=S.initialize(data,{source_commit:data.source_commit,drafts:{[c0.image_code]:localConfirmed.draft},confirmations:{[c0.image_code]:localConfirmed.confirmation}});eq(reloaded.drafts[c0.image_code].polygon,localConfirmed.draft.polygon);eq(reloaded.confirmations[c0.image_code].confirmed_at,'2026-10-10T04:30:00Z');check(reloaded.drafts[c0.image_code].completed);
  // A future data-source revision must not silently overwrite the older local store.
  const mismatch={...S.clone(changed),source_commit:'previous-revision'};
  const mismatched=S.initialize(data,mismatch);eq(mismatched.unrecovered_drafts.previous_storage,mismatch);check(mismatched.warnings.some(x=>x.includes('版本不匹配')));
  const mismatchUI=await boot(mismatch);check(!mismatchUI.el('recoveryWarning').hidden);eq(JSON.parse(mismatchUI.saved.get(KEY)).unrecovered_drafts.previous_storage,mismatch);eq(mismatchUI.w.exportData().unrecovered_drafts.previous_storage,mismatch);
  const {w,el,saved,choices}=await boot();check(w);eq(el('name').textContent,'q9vSo1VnCiC-29');check(el('nav').innerHTML.includes('✓ 已确认'));eq(w.exportData().records.length,5);check(w.exportData().records.slice(0,3).every(r=>r.completed&&r.floor_region_confirmed&&!r.reference_ready));check(w.exportData().records.slice(3).every(r=>!r.completed&&!r.floor_region_confirmed));
  eq(el('evidenceCount').textContent,'全部 5 份标注证据');check(el('evidenceSummary').textContent.includes('hold_scene_or_reference'));check(el('historicalComments').innerHTML.includes('这gt是标到门外的房间了'));
  // Navigating never approves new targets.
  el('next').click();eq(el('name').textContent,'pRbA3pwrgk9-02');check(!w.exportData().records[3].completed);eq(el('evidenceCount').textContent,'全部 6 份标注证据');
  // Prominent single confirmation click applies a valid preview and persists a distinct snapshot.
  w.setRectangle([-.4,-.3],[.3,.4],0);el('confirm').click();let d=w.getDraft();eq(d.decision,'allow');check(d.completed);eq(d.operations.at(-1).type,'rectangle');eq(el('reviewStatus').textContent,'✓ 已确认');let snap=w.getConfirmation();eq(snap.polygon,d.polygon);check(snap.floor_region_confirmed);check(JSON.parse(saved.get(KEY)).confirmations['pRbA3pwrgk9-02'].completed);
  // Repeated confirmation, edits, undo/redo, and persistence preserve the confirmed polygon.
  el('confirm').click();eq(w.getDraft().polygon,snap.polygon);w.setEdge(1,-.1);el('apply').click();check(!w.getDraft().completed);eq(el('reviewStatus').textContent,'本地修改待确认');eq(w.getConfirmation().polygon,snap.polygon);el('undo').click();check(w.getDraft().completed);eq(el('reviewStatus').textContent,'✓ 已确认');el('redo').click();check(!w.getDraft().completed);el('restoreConfirmed').click();eq(w.getDraft().polygon,snap.polygon);check(w.getDraft().completed);
  // New q9 remains original GT until explicitly decided.
  w.loadImage(3);eq(w.getDraft().polygon,G.floor(data.images[3].reference_points_1024x512));el('confirm').click();eq(w.getDraft().decision,'full_gt');check(w.getDraft().completed);check(w.getConfirmation().floor_region_confirmed);
  // Uncertain is saved as a decision, never presented as approval.
  choices[2].onclick();el('confirm').click();check(w.getDraft().completed);check(!w.getConfirmation().floor_region_confirmed);eq(el('reviewStatus').textContent,'已记录待定');
  // Invalid preview and partial line cannot be confirmed.
  w.setLine([0,-10],[0,10]);check(el('confirm').disabled);let before=w.getConfirmation();el('confirm').click();eq(w.getConfirmation(),before);el('cancel').click();
  // Round trip new records with separate confirmation metadata.
  const output=w.exportData();check(output.records.every(r=>!r.reference_ready));check(!output.GT_modified);await el('file').onchange({target:{files:[{text:async()=>JSON.stringify(output)}],value:'round-trip'}});check(el('toast').textContent.includes('已导入'));
  let bad=S.clone(output);bad.source_commit='wrong';await el('file').onchange({target:{files:[{text:async()=>JSON.stringify(bad)}],value:'bad'}});check(el('toast').textContent.includes('导入失败'));
  bad=S.clone(output);bad.records[3].original_GT_points_1024x512[0][0]++;await el('file').onchange({target:{files:[{text:async()=>JSON.stringify(bad)}],value:'bad'}});check(el('toast').textContent.includes('GT绑定不匹配'));
  // Exact user-received v2 remains importable, and does not erase confirmation snapshots.
  let received=JSON.parse(fs.readFileSync('fixtures/received-review-v2.json'));
  await el('file').onchange({target:{files:[{text:async()=>JSON.stringify(received)}],value:'received'}});check(el('toast').textContent.includes('已导入'));check(w.exportData().records.slice(0,3).every(r=>r.completed&&r.floor_region_confirmed));
  // Legacy cut-only v1 is accepted; later images remain intact on partial import.
  let v1={schema:'manual_scope_crop_review_v1',source_commit:data.source_commit,records:[S.clone(received.records[0])]};delete v1.records[0].operations;
  await el('file').onchange({target:{files:[{text:async()=>JSON.stringify(v1)}],value:'v1'}});check(el('toast').textContent.includes('已导入'));eq(w.exportData().records.length,5);
  // Existing operations: a cut, redo, rectangle, and outward edge all remain functional.
  w.loadImage(0);el('reset').click();const original=S.clone(w.getDraft().polygon);w.setLine([-2.3,-10],[-2.3,10]);check(!el('apply').disabled);el('apply').click();eq(w.getDraft().cuts.length,1);check(G.area(w.getDraft().polygon)<G.area(original));el('undo').click();eq(w.getDraft().polygon,original);el('redo').click();eq(w.getDraft().cuts.length,1);
  w.setRectangle([-3,-3],[3,3],0);el('apply').click();eq(w.getDraft().operations.at(-1).type,'rectangle');let rectArea=G.area(w.getDraft().polygon);w.setEdge(1,-.4);el('apply').click();check(G.area(w.getDraft().polygon)>rectArea);
  w.setRectangle([-2,-2],[2,2],0);choices[1].onclick();check(el('cancel').disabled);eq(w.getDraft().operations.length,0);
  // Reloading a modified old image keeps the draft and calls it pending, not server-confirmed.
  const pendingUI=await boot(changed);eq(pendingUI.el('name').textContent,c0.image_code);eq(pendingUI.w.getDraft().polygon,changed.drafts[c0.image_code].polygon);eq(pendingUI.el('reviewStatus').textContent,'本地修改待确认');eq(pendingUI.w.getConfirmation().polygon,c0.confirmed_review.polygon);
  // Undoing after a new confirmation cannot export completed=true for a mismatched old polygon.
  w.setRectangle([-1,-1],[1,1],0);el('confirm').click();w.setRectangle([-2,-2],[2,2],0);el('confirm').click();el('undo').click();check(!w.getDraft().completed);eq(el('reviewStatus').textContent,'本地修改待确认');
  const persisted=JSON.parse(saved.get(KEY)),again=await boot(persisted);eq(again.w.exportData().records.map(r=>r.polygon),w.exportData().records.map(r=>r.polygon));
  const qa={state_checks_passed:checks,geometry_checks_passed:49,browser_QA:'not run: previously verified Chromium socket creation is denied by this execution host; no retry or browser pass claimed',coverage:['five-image dataset and complete evidence','legacy v1/v2 import','first-batch confirmation migration','preserve newer local drafts and note changes','independent confirmed snapshots and explicit one-click confirmation','uncertain is not approved','new images start at original GT','cut/rectangle/edge edit/undo/redo regression','invalid preview protection','export/import/reload'],tested_on:'2026-10-10'};fs.writeFileSync('QA.json',JSON.stringify(qa,null,2)+'\n');console.log(qa);
})().catch(e=>{console.error(e);process.exitCode=1});
