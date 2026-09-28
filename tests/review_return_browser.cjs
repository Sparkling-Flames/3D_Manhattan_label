const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=path.resolve('analysis_results/review_return_20260927'),browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({offline:true,viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);await page.waitForFunction(()=>window.RECONCILIATION_APP?.snapshot().imageReady);
  const initial=await page.evaluate(()=>RECONCILIATION_APP.exportData());assert.equal(initial.schema,'review_return_decisions_v2');assert.equal(Object.keys(initial.image_decisions).length,197);assert.equal(Object.keys(initial.annotation_decisions).length,625);
  assert.deepEqual(initial.traits,{});assert.deepEqual(initial.issue_decisions,{});
  assert.ok(await page.evaluate(()=>document.querySelector('.recon-points-panel').nextElementSibling.id==='return-panel'));
  assert.equal(await page.locator('.recon-final').evaluate(e=>e.open),true);
  const original=JSON.parse(fs.readFileSync(path.join(root,'evidence/review_return_original.json'),'utf8'));assert.deepEqual(initial.annotation_decisions,original.annotation_decisions);
  assert.equal(await page.locator('#recon-image option').count(),JSON.parse(fs.readFileSync(path.join(root,'page_manifest.json'),'utf8')).followup_images);
  assert.ok(await page.evaluate(()=>['jtcxE69GiFV-12','jtcxE69GiFV-30','UwV83HsGsw3-17'].every(code=>dataset.cases.find(c=>c.code===code).return_review.issues.some(i=>i.kind==='repair'&&i.annotation_ids.length))));
  assert.ok(await page.evaluate(()=>dataset.cases.every(c=>c.return_review.issues.every(i=>['undecided','repair','contradiction','semantic'].includes(i.kind)))));
  await page.locator('#recon-filter').selectOption('all');
  const ids=await page.evaluate(()=>Object.fromEntries(dataset.cases.map(c=>[c.code,c.image_id])));
  async function open(code){await page.locator('#recon-image').selectOption(ids[code]);await page.waitForFunction(id=>RECONCILIATION_APP.snapshot().imageId===id&&RECONCILIATION_APP.snapshot().imageReady,ids[code]);}
  await open('wc2JMjhGNzB-60');assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).imageProblemReviewed,false,'旧排除未核对不能因图级确认隐藏');
  assert.ok(await page.locator('#return-issues details').count()>0);
  assert.ok(await page.locator('.recon-member[data-review-state="pending"]').count()>0);
  await page.locator('.recon-member[data-review-state=pending]').first().evaluate(e=>e.scrollIntoView({block:'center',behavior:'instant'}));await page.screenshot({path:path.join(root,'qa-status-temporary.png')});
  await page.locator('#recon-unresolved').check();assert.ok(await page.locator(`#recon-image option[value="${ids['wc2JMjhGNzB-60']}"]`).count());await page.locator('#recon-unresolved').uncheck();
  const issue=page.locator('#return-issues details').first();await issue.locator('summary').first().click();await issue.locator('textarea').fill('隔离浏览器测试，保持待定。');
  const saved=await page.evaluate(()=>RECONCILIATION_APP.exportData());assert.equal(Object.keys(saved.issue_decisions).length,1);assert.equal(Object.values(saved.issue_decisions)[0].status,'pending');
  await page.reload();await page.waitForFunction(()=>window.RECONCILIATION_APP?.snapshot().imageReady);assert.deepEqual((await page.evaluate(()=>RECONCILIATION_APP.exportData())).issue_decisions,saved.issue_decisions);
  await page.locator('#recon-filter').selectOption('all');await open('q9vSo1VnCiC-09');assert.match(await page.locator('#return-usage').textContent(),/不进入人员主质量/);
  const classification=page.locator('#return-classification');assert.equal(await classification.evaluate(e=>e.open),true);await classification.locator('fieldset').first().locator('input[value="nonorthogonal"]').check();
  assert.equal((await page.evaluate(()=>RECONCILIATION_APP.exportData())).traits['image:'+ids['q9vSo1VnCiC-09']].difficulty,'unrecorded');
  await classification.locator('fieldset').first().locator('input[value="reference_omission"]').check();
  assert.ok((await page.evaluate(()=>RECONCILIATION_APP.exportData())).traits['image:'+ids['q9vSo1VnCiC-09']].tags.includes('reference_omission'));
  await classification.locator('fieldset').first().getByRole('button',{name:'确认补充分类'}).click();assert.equal((await page.evaluate(()=>RECONCILIATION_APP.exportData())).traits['image:'+ids['q9vSo1VnCiC-09']].status,'resolved');
  const originals=page.locator('#return-panel > details').filter({has:page.locator('summary',{hasText:'此次二审原文与整理释义（只读）'})}).first();await originals.locator('summary').first().click();
  const backgrounds=originals.locator('details').filter({has:page.locator('summary',{hasText:'背景核验与同房差异'})}).first();await backgrounds.locator('summary').first().click();
  const roomIssue=backgrounds.locator('details').filter({has:page.locator('summary',{hasText:'同房'})}).first();await roomIssue.locator('summary').first().click();assert.ok(await roomIssue.locator('img').count()>=2);await page.waitForFunction(()=>[...document.querySelectorAll('#return-panel img')].every(i=>i.complete&&i.naturalWidth>0));
  await page.locator('#recon-filter').selectOption('model');assert.ok(await page.locator('#recon-image option').count()>0);
  await page.locator('#recon-filter').selectOption('all');
  await open('B6ByNegPMKs-10');
  const source=page.locator('#return-panel details').filter({has:page.locator('summary', {hasText:'此次二审原文与整理释义（只读）'})}).first();if(!await source.evaluate(e=>e.open))await source.locator('summary').first().click();
  const model=page.locator('#return-panel details').filter({has:page.locator('summary',{hasText:'初始化核验 · W021'})}).last();await model.locator('summary').first().click();await model.getByRole('button',{name:'对照实际初始化与最终点'}).click();
  assert.match(await page.locator('#recon-legend').textContent(),/实际初始化/);
  if(!await classification.evaluate(e=>e.open))await classification.locator('summary').first().click();
  await classification.locator('select[aria-label="是否预设 Trap"]').last().selectOption('trap_uncertain');
  assert.ok(Object.values((await page.evaluate(()=>RECONCILIATION_APP.exportData())).traits).some(t=>t.tags.includes('trap_uncertain')));
  await page.locator('#recon-method').selectOption('complete');assert.match(await page.locator('#return-panel').textContent(),/affinity/);
  const downloadEvent=page.waitForEvent('download');await page.locator('#recon-export').click();const file=await downloadEvent;const exported=JSON.parse(fs.readFileSync(await file.path(),'utf8'));
  const upload=async v=>page.locator('#recon-import').setInputFiles({name:'review.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(v))});
  await upload({...exported,traits:{'image:unknown':{status:'resolved',tags:[],difficulty:'hard',comment:'',updated_at:new Date().toISOString()}}});await page.waitForFunction(()=>document.getElementById('recon-status').textContent.includes('导入失败'));assert.deepEqual((await page.evaluate(()=>RECONCILIATION_APP.exportData())).issue_decisions,exported.issue_decisions);
  await upload(original);await page.waitForFunction(()=>document.getElementById('recon-status').textContent.includes('导入成功'));assert.equal(Object.keys((await page.evaluate(()=>RECONCILIATION_APP.exportData())).annotation_decisions).length,625);
  await upload(exported);await page.waitForFunction(()=>document.getElementById('recon-status').textContent.includes('导入成功'));
  await page.locator('#recon-filter').selectOption('all');await open('2t7WUuJeko7-09');
  await page.locator('#recon-gallery').evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));
  await page.screenshot({path:path.join(root,'qa-temporary.png')});
  await classification.evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));await page.screenshot({path:path.join(root,'qa-panel-temporary.png')});
  await open('7y3sRwLe3Va-13');await page.locator('#recon-focus').selectOption('b11846422ee8df2c');
  assert.match(await page.locator('#return-trap-info').textContent(),/PreScreen阶段 · 人工构造Trap；最终点集与实际初始化一致/);
  await page.locator('#return-classification select[aria-label="是否预设 Trap"]').last().selectOption('trap_synthetic');
  assert.ok((await page.evaluate(()=>RECONCILIATION_APP.exportData())).traits['annotation:b11846422ee8df2c'].tags.includes('trap_synthetic'));
  await page.locator('#return-panel').evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));await page.screenshot({path:path.join(root,'qa-form-temporary.png')});
  await classification.evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));await page.screenshot({path:path.join(root,'qa-options-temporary.png')});
  assert.deepEqual(errors,[]);console.log('PASS: baseline完整、个体问题不隐藏、OOS保留用途、初始化叠加、固定簇、独立保存重载及v1/v2导入');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});




