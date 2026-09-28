const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=path.resolve('analysis_results/review_continue_20260928'),b=await chromium.launch({headless:true});
 try{
  const page=await b.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);
  await page.waitForFunction(()=>window.RECONCILIATION_APP?.snapshot().imageReady);
  assert.equal(await page.locator('#recon-image option').count(),5);
  const codes=await page.evaluate(()=>dataset.cases.map(c=>[c.code,c.image_id]));
  for(const [code,id] of codes){await page.locator('#recon-image').selectOption(id);await page.waitForFunction(id=>RECONCILIATION_APP.snapshot().imageId===id&&RECONCILIATION_APP.snapshot().imageReady,id);assert.equal(await page.locator('#return-issues > details').count(),1);}
  const box=page.locator('#return-issues > details');await box.locator('textarea').fill('隔离测试：继续待查');
  await box.getByRole('button',{name:'确认已处理此问题'}).click();
  const saved=await page.evaluate(()=>RECONCILIATION_APP.exportData());assert.equal(Object.values(saved.issue_decisions)[0].status,'resolved');
  await page.reload();await page.waitForFunction(()=>window.RECONCILIATION_APP?.snapshot().imageReady);
  assert.deepEqual((await page.evaluate(()=>RECONCILIATION_APP.exportData())).issue_decisions,saved.issue_decisions);
  const wait=page.waitForEvent('download');await page.locator('#recon-export').click();const dl=await wait;
  assert.equal(dl.suggestedFilename(),'全历史标注_未决续审_20260928.json');
  const output=JSON.parse(fs.readFileSync(await dl.path(),'utf8'));assert.equal(output.binding.id,'review_continue_20260928_v1');
  await page.locator('#recon-import').setInputFiles({name:'roundtrip.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(output))});
  await page.waitForFunction(()=>document.querySelector('#recon-status').textContent.includes('导入成功'));
  await page.locator('#return-issues').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'qa-temporary.png')});
  assert.deepEqual(errors,[]);console.log('PASS: 五图加载、独立baseline、问题保存重载及导出导入。');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
