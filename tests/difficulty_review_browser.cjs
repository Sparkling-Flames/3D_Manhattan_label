// 仅使用隔离浏览器测试；测试答案不进入用户浏览器或研究数据。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve('analysis_results/difficulty_consensus_20261006/index.html')).href);
  assert.equal(await page.locator('.card').count(),8);
  await page.waitForFunction(()=>[...document.querySelectorAll('.pano')].every(i=>i.complete&&i.naturalWidth>0));
  assert.deepEqual(await page.locator('[data-key="difficulty"]').evaluateAll(es=>es.map(e=>e.value)),Array(8).fill(''));
  const difficulty=page.locator('[data-key="difficulty"]').first();
  await difficulty.selectOption('中等');
  await page.locator('[data-key="oos"]').first().selectOption('否');
  await page.locator('[data-key="doorway"]').first().selectOption('是');
  await page.locator('textarea').first().fill('自动测试，仅隔离浏览器');
  const pending=page.waitForEvent('download');await page.locator('#export').click();
  const downloaded=JSON.parse(fs.readFileSync(await (await pending).path(),'utf8'));
  assert.equal(downloaded.decisions.length,8);
  assert.equal(downloaded.decisions[0].oos,'否');assert.equal(downloaded.decisions[0].doorway,'是');
  await page.reload();assert.equal(await difficulty.inputValue(),'中等');
  await page.evaluate(()=>localStorage.clear());await page.reload();
  await page.locator('#import').setInputFiles({name:'review.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(downloaded))});
  await page.waitForFunction(()=>document.getElementById('saved').textContent.includes('已导入'));
  assert.equal(await difficulty.inputValue(),'中等');
  await page.locator('#filter').selectOption('pending');assert.equal(await page.locator('.card').count(),7);
  await page.locator('#filter').selectOption('all');
  await page.locator('.pano-button').first().click();assert.equal(await page.locator('#zoom').evaluate(e=>e.open),true);
  await page.locator('#close').click();
  await page.evaluate(()=>localStorage.clear());await page.reload();
  await page.screenshot({path:path.resolve('analysis_results/difficulty_consensus_20261006/browser_check.png')});
  assert.deepEqual(errors,[]);
  console.log('PASS: 8 images, blank defaults, independent scene fields, save/reload/export/import, filter and zoom');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
