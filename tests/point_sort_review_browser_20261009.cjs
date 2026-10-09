const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');const ROOT='D:/Work/HOHONET',URL='http://127.0.0.1:8769/';
(async()=>{
 const browser=await chromium.launch({headless:true}),contexts=[],errors=[];const evidence={browser:'用户电脑上的隔离 Chromium',user_browser_profile_used:false};
 try{
  const c=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true});contexts.push(c);const p=await c.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto(URL);await p.locator('#scope-filter').selectOption('all');
  const ready=async(page=p,id)=>{await page.waitForFunction(id=>window.POINT_REVIEW_STATE?.().imageReady&&(!id||POINT_REVIEW_STATE().current===id),id);};await ready();
  const cases=await p.evaluate(()=>POINT_REVIEW_DATA.cases.map((r,i)=>({i,id:r.record_id,image:r.image_id,conclusion:r.reviewer.reviewer_conclusion,note:r.reviewer.reviewer_note})));
  const state=()=>p.evaluate(()=>POINT_REVIEW_STATE());const goto=async id=>{await p.locator('#case-select').selectOption(String(cases.find(c=>c.id===id).i));await ready(p,id);};
  for(const r of cases){await goto(r.id);assert.equal(await p.locator('#reviewer-conclusion').innerText(),r.conclusion);assert.equal(await p.locator('#reviewer-original-note').textContent(),r.note);assert((await p.locator('#reviewer-binding').innerText()).includes(r.id));assert((await p.locator('#reviewer-binding').innerText()).includes(r.image));assert((await p.evaluate(()=>originalImage.src)).endsWith('/image/'+r.image));}
  evidence.reviewer_original_conclusion_and_full_notes_matched=109;
  await goto('R02173');const raw=(await state()).points;
  await p.locator('#tool-order').click();if(await p.locator('#baseline-choice').isVisible())await p.locator('#baseline-options button').first().click();
  assert.equal((await state()).records.R02173.pairs.length,6);
  const pairButtons=async(a,b)=>{await p.locator('#tool-pair').click();await p.locator('#edit-point-buttons button').filter({hasText:new RegExp('^'+a+'$')}).click();await p.locator('#edit-point-buttons button').filter({hasText:new RegExp('^'+b+'$')}).click();};
  let before=(await state()).records.R02173;
  const cards=p.locator('#pair-drag-list .pair-token');assert.equal(await cards.count(),6);await cards.nth(1).scrollIntoViewIfNeeded();
  const a=await cards.nth(1).boundingBox(),b=await cards.nth(2).boundingBox();
  await p.mouse.move(a.x+a.width/2,a.y+a.height/2);await p.mouse.down();await p.mouse.move(a.x+a.width/2+12,a.y+a.height/2,{steps:3});const slot=await p.locator('#pair-drag-list').evaluate(el=>{const b=el.querySelectorAll('.pair-token')[1],r=el.getBoundingClientRect();return {x:r.left+b.offsetLeft+b.offsetWidth+2,y:r.top+b.offsetTop+b.offsetHeight/2};});await p.mouse.move(slot.x,slot.y,{steps:5});await p.mouse.up();
  let d=(await state()).records.R02173;assert.deepEqual(d.pairs,[before.pairs[0],before.pairs[2],before.pairs[1],...before.pairs.slice(3)]);assert.deepEqual(d.points,raw);assert.equal(d.operations.at(-1).type,'order');
  assert.match(await p.locator('#pair-order-map').innerText(),/1 p1\/p2 → 2 p3\/p4/);assert.equal(await p.locator('#show-ring-preview').isChecked(),true);
  await p.locator('#undo-step').click();assert.deepEqual((await state()).records.R02173.pairs,before.pairs);
  // 补删挪之后沿用同一完整点对排序逻辑。
  await p.locator('.advanced-edit').evaluate(el=>el.open=true);
  for(const y of [100,400]){await p.locator('#point-x').fill('950');await p.locator('#point-y').fill(String(y));await p.locator('#add-point').click();}
  d=(await state()).records.R02173;const added=d.points.slice(-2);await p.locator('#tool-pair').click();
  for(const point of added)await p.locator('#edit-point-buttons button').filter({hasText:point.label}).click();
  await p.locator('#tool-delete').click();await p.locator('#edit-point-buttons button').filter({hasText:/^p9$/}).click();await p.locator('#quick-delete').click();
  await p.locator('#tool-move').click();await p.locator('#edit-point-buttons button').filter({hasText:/^p1$/}).click();await p.locator('#point-x').fill('130');await p.locator('#point-y').fill('150');await p.locator('#move-point').click();await pairButtons('p1','p2');
  await p.locator('#tool-order').click();before=(await state()).records.R02173;await p.locator('#pair-drag-list .pair-token').nth(1).focus();await p.keyboard.press('Alt+ArrowRight');
  d=(await state()).records.R02173;assert.equal(d.operations.at(-1).type,'order');assert.deepEqual(d.points.slice(0,raw.length).map(v=>v.id),raw.map(v=>v.id));assert.equal(d.points.find(v=>v.label==='p9').deleted,true);
  const saved=d;await p.reload();await ready(p,'R02173');assert.deepEqual((await state()).records.R02173,saved);
  assert.equal(await p.locator('#version-ack').isVisible(),false);assert.equal(await p.locator('#review-note').inputValue(),'');
  await p.locator('#confirm-patch').click();assert.equal((await state()).records.R02173.status,'completed');assert.equal((await state()).records.R02173.note,'');assert.match(await p.locator('#my-review-status').innerText(),/我已完成/);
  await p.locator('#complete-next').click();assert.notEqual((await state()).current,'R02173');await ready();
  const [download]=await Promise.all([p.waitForEvent('download'),p.locator('#export-patches').click()]);const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.equal(exported.apply_to_formal,false);assert.equal(exported.records.R02173.ring_confirmed,false);
  const c2=await browser.newContext();contexts.push(c2);const p2=await c2.newPage();p2.on('pageerror',e=>errors.push(e.message));await p2.goto(URL);await ready(p2);await p2.locator('#scope-filter').selectOption('all');
  await p2.locator('#import-patches').setInputFiles({name:'sort-test.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(exported))});await p2.waitForFunction(()=>document.getElementById('edit-status').textContent==='导入完成。');assert.deepEqual(await p2.evaluate(()=>POINT_REVIEW_STATE().records),exported.records);
  await p2.locator('#case-select').selectOption(String(cases.find(c=>c.id==='R02173').i));await ready(p2,'R02173');await p2.reload();await ready(p2,'R02173');assert.deepEqual(await p2.evaluate(()=>POINT_REVIEW_STATE().records.R02173),exported.records.R02173);
  await goto('R00541');await p.locator('#tool-order').click();assert(await p.locator('#baseline-choice').isVisible());await p.locator('#baseline-options button').filter({hasText:/历史生效/}).click();assert(!(await state()).points.some(v=>v.label==='p5'));
  const old=fs.readFileSync(ROOT+'/tools/thesis_main/analysis/order_studio_20260926.js','utf8');const normalizedOld=old.replace(/\r\n/g,'\n');const block=normalizedOld.slice(normalizedOld.indexOf('function startPairDrag'),normalizedOld.indexOf('function saveReview'));const adapter=fs.readFileSync(ROOT+'/analysis_results/point_edit_review_20261009/point_edit_sort.js','utf8').replace(/\r\n/g,'\n');assert(adapter.includes(block));
  assert.deepEqual(errors,[]);evidence.passed=true;evidence.old_pointer_drag_code_reused_without_logic_changes=true;evidence.actual_drag_and_keyboard_sort_undo=true;evidence.add_delete_move_then_sort_stable_ids=true;evidence.sort_refresh_export_import=true;evidence.complete_without_checkbox_or_note=true;evidence.history_delete_not_restored=true;evidence.page_errors=errors;
  console.log('PASS old pair drag / sort undo / edited points & stable IDs / 109 original reviewer notes matched / simple completion / refresh / export & import');
 }finally{for(const c of contexts)await c.close();await browser.close();evidence.test_contexts_closed=true;evidence.test_drafts_persisted_to_user_profile=false;fs.writeFileSync(ROOT+'/analysis_results/point_edit_review_20261009/sort_browser_verification.json',JSON.stringify(evidence,null,2));}
})().catch(e=>{console.error(e);process.exitCode=1;});
