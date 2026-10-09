const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const URL='http://127.0.0.1:8769/',out=path.resolve('analysis_results/point_edit_review_20261009/browser_verification.json');
(async()=>{
 const browser=await chromium.launch({headless:true});const contexts=[];const errors=[];const evidence={browser:'用户电脑上的隔离 Chromium（Playwright）',user_browser_profile_used:false,test_drafts_persisted_to_user_profile:false};
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true});contexts.push(context);
  const p=await context.newPage();p.on('pageerror',e=>errors.push(e.message));
  await p.goto(URL);
  const ready=async(page=p,id)=>{await page.waitForFunction(id=>window.POINT_REVIEW_STATE?.().imageReady&&(!id||POINT_REVIEW_STATE().current===id),id);await page.locator('.advanced-edit').evaluate(el=>el.open=true);};
  const state=()=>p.evaluate(()=>POINT_REVIEW_STATE());
  await ready();await p.locator('#scope-filter').selectOption('all');assert.equal(await p.locator('#case-select option').count(),109);assert(await p.locator('#panorama').isVisible());
  const cases=await p.evaluate(()=>POINT_REVIEW_DATA.cases.map((c,i)=>({i,id:c.record_id,image:c.image_id,count:c.versions.raw.points.length})));
  const goto=async id=>{await p.locator('#case-select').selectOption(String(cases.find(c=>c.id===id).i));await ready(p,id);};
  for(const c of cases){
   await goto(c.id);const s=await state();assert.equal(s.points.length,c.count);
   assert(s.points.every((v,i)=>v.label==='p'+(i+1)&&v.source_index===i&&v.id.endsWith('['+i+']')));
   const img=await p.evaluate(()=>({width:originalImage.naturalWidth,height:originalImage.naturalHeight,src:originalImage.src,canvasVisible:document.getElementById('panorama-panel').open}));
   assert(img.src.endsWith('/image/'+c.image));assert.equal(img.width,2048);assert.equal(img.height,1024);assert(img.canvasVisible);
  }
  evidence.records_loaded=109;evidence.original_images_decoded=71;evidence.every_record_original_point_identity_checked=true;
  console.log('PASS 109 records / 71 original images / stable raw IDs');
  assert.equal(await p.evaluate(()=>POINT_REVIEW_DATA.cases.reduce((n,c)=>n+c.proposed_deletions.length,0)),33);
  for(const [id,removed] of Object.entries({R02034:'p2',R00541:'p5',R02059:'p5',R01907:'p1'})){
   await goto(id);const raw=await state();await p.locator('#variant-select').selectOption('1');
   const historical=await state();assert.equal(historical.points.length,raw.points.length-1);assert(!historical.points.some(p=>p.label===removed));
   assert((await p.locator('#version-summary').innerText()).includes(removed));
   await p.locator('#variant-select').selectOption('2');assert.equal((await state()).points.length,0);
   assert.match(await p.locator('#pair-status').innerText(),/缺失/);assert(await p.locator('#create-draft').isDisabled());
  }
  evidence.historical_four_deletions_and_current_missing_checked=true;
  await goto('R00013');assert.match(await p.locator('#version-warning').innerText(),/19超过原始12/);
  for(const [id,label,x] of [['R00071','p10',44479.18070033388],['R00669','p5',5132.7049423815615],['R02155','p11',5132.7049423815615]]){
   await goto(id);assert.equal((await state()).points.find(p=>p.label===label).x,x);assert.match(await p.locator('#version-warning').innerText(),/越界/);
  }
  evidence.reported_point_number_and_coordinate_issues_checked=true;
  // 操作只在隔离浏览器上下文中，用户实际审核缓存不被使用。
  await goto('R00003');const original=(await state()).points;
  await p.locator('#create-draft').click();assert.equal((await state()).version,'draft');
  await p.locator('#add-point').click();assert.match(await p.locator('#edit-status').innerText(),/填写/);
  await p.locator('#edit-tool').selectOption('add');const box=await p.locator('#panorama').boundingBox();
  await p.locator('#panorama').click({position:{x:box.width*850/1024,y:box.height*130/512}});
  let s=await state(),d=s.records.R00003;assert.equal(d.points.length,original.length+1);assert(d.points.at(-1).id.startsWith('new:'));assert(Math.abs(d.points.at(-1).x-850)<2);
  assert.equal(d.points.at(-1).provenance.imputed,false);
  await p.locator('#edit-tool').selectOption('select');await p.locator('#edit-point-buttons button').filter({hasText:/^p1$/}).click();
  await p.locator('#point-x').fill('496.25');await p.locator('#point-y').fill('224.75');await p.locator('#move-point').click();
  assert.equal((await state()).records.R00003.points[0].x,496.25);
  await p.locator('#edit-point-buttons button').filter({hasText:/^p3$/}).click();await p.locator('#delete-point').click();
  d=(await state()).records.R00003;assert.equal(d.points[2].label,'p3');assert.equal(d.points[2].deleted,true);assert.equal(d.points[3].label,'p4');
  await p.locator('#edit-tool').selectOption('pair');
  await p.locator('#edit-point-buttons button').filter({hasText:/^p1$/}).click();await p.locator('#edit-point-buttons button').filter({hasText:/^p2$/}).click();
  d=(await state()).records.R00003;assert.deepEqual(d.pairs,[[original[0].id,original[1].id]]);
  await p.locator('#review-note').fill('隔离自动化测试：只验证补丁，不用于用户确认。');
  await p.locator('#save-draft').click();const saved=(await state()).records.R00003;
  await p.reload();await ready();assert.equal((await state()).version,'draft');assert.deepEqual((await state()).records.R00003,saved);
  assert.equal(await p.locator('#version-ack').isVisible(),false);await p.locator('#confirm-patch').click();
  assert.equal((await state()).records.R00003.status,'completed');assert.equal((await state()).current,'R00003');
  await p.locator('#edit-tool').selectOption('move');await p.locator('#edit-point-buttons button').filter({hasText:/^p4$/}).click();
  // 实际拖动一个稳定原点。
  s=await state();const p4=s.points.find(p=>p.label==='p4');await p.locator('#panorama').scrollIntoViewIfNeeded();const b=await p.locator('#panorama').boundingBox();
  const sx=b.x+b.width*p4.x/1024,sy=b.y+b.height*p4.y/512;
  await p.mouse.move(sx,sy);await p.mouse.down();await p.mouse.move(sx+16,sy+3,{steps:4});await p.mouse.up();
  d=(await state()).records.R00003;assert.equal(d.status,'draft');assert(d.points.find(p=>p.label==='p4').x>p4.x);assert.equal(d.operations.at(-1).type,'move');
  await p.locator('#review-note').fill('隔离自动化测试暂缓：环仍未确定。');await p.locator('#defer-patch').click();assert.equal((await state()).records.R00003.status,'deferred');
  const [download]=await Promise.all([p.waitForEvent('download'),p.locator('#export-patches').click()]);
  const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
  assert.equal(exported.apply_to_formal,false);assert.equal(exported.records.R00003.restore_eligibility,false);assert.equal(exported.records.R00003.ring_confirmed,false);
  assert.deepEqual(exported.records.R00003.operations.slice(0,4).map(o=>o.type),['add','move','delete','pair']);
  const context2=await browser.newContext({viewport:{width:1440,height:1050}});contexts.push(context2);const p2=await context2.newPage();
  await p2.goto(URL);await ready(p2);assert.equal(Object.keys(await p2.evaluate(()=>POINT_REVIEW_STATE().records)).length,0);
  await p2.locator('#import-patches').setInputFiles({name:'test-return.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(exported))});
  await p2.waitForFunction(()=>document.getElementById('edit-status').textContent==='导入完成。');
  assert.deepEqual(await p2.evaluate(()=>POINT_REVIEW_STATE().records),exported.records);
  await p2.reload();await ready(p2);assert.deepEqual(await p2.evaluate(()=>POINT_REVIEW_STATE().records),exported.records);
  const corrupt=structuredClone(exported);corrupt.records.R00003.identity.canonical_object_id='different-answer';
  await p2.locator('#import-patches').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(corrupt))});
  await p2.waitForFunction(()=>document.getElementById('edit-status').textContent.startsWith('导入未应用'));
  assert.deepEqual(await p2.evaluate(()=>POINT_REVIEW_STATE().records),exported.records);
  // 撤回有留痕，仍不重编号；只清空测试上下文中的本轮操作结果。
  await p.locator('#reset-draft').click();d=(await state()).records.R00003;assert.deepEqual(d.points,original);assert.equal(d.operations.at(-1).type,'reset');
  await p.locator('#save-draft').click();await p.reload();await ready();assert.equal((await state()).records.R00003.operations.at(-1).type,'reset');
  evidence.add_delete_move_canvas_drag_pair_passed=true;evidence.save_reload_export_import_passed=true;evidence.corrupt_import_rejected_without_overwrite=true;evidence.reset_keeps_trace=true;
  await p.locator('#review-filter').selectOption('需补点');assert.equal(await p.locator('#case-select option').count(),39);
  await p.locator('#review-filter').selectOption('');await goto('R00541');await p.locator('#variant-select').selectOption('1');
  // 缺图只在隔离上下文模拟；实际原图与服务器文件保持不变。
  const missingContext=await browser.newContext();contexts.push(missingContext);const missing=await missingContext.newPage();
  missing.on('pageerror',e=>errors.push(e.message));
  await missing.route('**/image/**',route=>route.fulfill({status:404,body:'test missing image'}));
  await missing.goto(URL);await missing.waitForFunction(()=>document.getElementById('texture-state').textContent.includes('原图加载失败'));
  assert.equal(await missing.evaluate(()=>POINT_REVIEW_STATE().imageReady),false);
  await missing.locator('.advanced-edit').evaluate(el=>el.open=true);await missing.locator('#create-draft').click();await missing.locator('#review-note').fill('自动测试缺图拦截，非用户确认');
  assert(await missing.locator('#confirm-patch').isDisabled());
  assert.equal(await missing.evaluate(()=>POINT_REVIEW_STATE().records[POINT_REVIEW_STATE().current].status),'draft');
  evidence.missing_image_message_and_confirmation_block_passed=true;
  assert.deepEqual(errors,[]);evidence.page_errors=errors;evidence.passed=true;
  console.log('PASS add/delete/move/drag/pair/save/reload/confirm/defer/export/import/reset');
 }finally{for(const c of contexts)await c.close();await browser.close();evidence.test_contexts_closed=true;fs.writeFileSync(out,JSON.stringify(evidence,null,2));}
})().catch(e=>{console.error(e);process.exitCode=1;});
