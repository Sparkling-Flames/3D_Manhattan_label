const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8769/');
  await page.waitForFunction(()=>POINT_REVIEW_STATE().imageReady&&POINT_REVIEW_STATE().current==='R00669');
  assert.equal(await page.locator('#scope-filter').inputValue(),'selected');assert.equal(await page.locator('#case-select option').count(),14);
  assert.equal(await page.locator('#case-count').innerText(),'1 / 14');assert.match(await page.locator('#queue-context').innerText(),/待审：坐标异常/);
  assert.match(await page.locator('#version-warning').innerText(),/冻结研究输入中的有效点 \/ 配对 \/ 确认环缺失/);
  assert.equal(await page.locator('#case-select option').evaluateAll(options=>options.some(o=>['R01210','R02183','R03177','R01812','R02016','R00089','R01732','R02219','R02393','R00773','R01283'].some(id=>o.textContent.includes(id)))),false);
  const listed=await page.locator('#case-select option').evaluateAll(options=>options.map(o=>Number(o.value)));
  assert.deepEqual(listed,await page.evaluate(()=>POINT_REVIEW_DATA.review_queue.items.map(r=>POINT_REVIEW_DATA.cases.findIndex(c=>c.record_id===r.record_id))));
  await page.locator('#next').click();await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R02155');assert.equal(await page.locator('#case-count').innerText(),'2 / 14');
  await page.locator('#scope-filter').selectOption('all');assert.equal(await page.locator('#case-select option').count(),109);
  const excludedReview=await page.evaluate(()=>POINT_REVIEW_DATA.cases.findIndex(c=>c.record_id==='R01210'));await page.locator('#case-select').selectOption(String(excludedReview));
  await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R01210'&&POINT_REVIEW_STATE().imageReady);assert.match(await page.locator('#queue-context').innerText(),/既有单条人工裁决为 invalid/);
  const oosReview=await page.evaluate(()=>POINT_REVIEW_DATA.cases.findIndex(c=>c.record_id==='R00089'));await page.locator('#case-select').selectOption(String(oosReview));
  await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R00089'&&POINT_REVIEW_STATE().imageReady);assert.match(await page.locator('#queue-context').innerText(),/OOS标注已保留，既有明确无法计算记录/);
  const emptyOos=await page.evaluate(()=>POINT_REVIEW_DATA.cases.findIndex(c=>c.record_id==='R01283'));await page.locator('#case-select').selectOption(String(emptyOos));
  await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R01283'&&POINT_REVIEW_STATE().imageReady);assert.match(await page.locator('#queue-context').innerText(),/当前无有效点/);
  const excluded=await page.evaluate(()=>POINT_REVIEW_DATA.cases.findIndex(c=>c.record_id==='R02173'));await page.locator('#case-select').selectOption(String(excluded));
  await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R02173'&&POINT_REVIEW_STATE().imageReady);
  await page.locator('#tool-order').click();if(await page.locator('#baseline-choice').isVisible())await page.locator('#baseline-options button').first().click();
  await page.locator('#pair-drag-list .pair-token').first().waitFor();const draft=await page.evaluate(()=>POINT_REVIEW_STATE().records.R02173);
  await page.locator('#scope-filter').selectOption('selected');await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R00669'&&POINT_REVIEW_STATE().imageReady);
  assert.equal(await page.locator('#case-select option').count(),14);assert.deepEqual(await page.evaluate(()=>POINT_REVIEW_STATE().records.R02173),draft);
  await page.reload();await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R00669'&&POINT_REVIEW_STATE().imageReady);
  assert.deepEqual(await page.evaluate(()=>POINT_REVIEW_STATE().records.R02173),draft);assert.equal(await page.locator('#scope-filter').inputValue(),'selected');
  assert.deepEqual(errors,[]);await context.close();console.log('PASS 清单14份/8图默认导航、已排除及OOS无法计算移出、原109份查看、旧草稿保留与刷新');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
