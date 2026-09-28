const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.FOLLOWUP_URL||'http://127.0.0.1:8769/analysis_results/local_point_research_received_20260919/pro_followup_20260920/review/index.html');
  await page.waitForFunction(()=>window.STUDIO?.snapshot().imageReady && document.querySelector('#fu-focus canvas'));
  assert.equal(await page.locator('#case-select option').count(),6);
  for(let i=0;i<6;i++){
   await page.selectOption('#case-select',String(i));
   await page.waitForFunction(i=>window.STUDIO.snapshot().caseIndex===i && window.STUDIO.snapshot().imageReady,i);
   assert.equal(await page.inputValue('#fu-relation'),'');
   assert.equal(await page.locator('#fu-defer').isChecked(),false);
   await page.selectOption('#fu-method','Bottleneck_equal_9');
   assert.ok(await page.locator('#history-clusters input[type=checkbox]').count()>0);
   const card=page.locator('#history-clusters .history-card').first();
   await card.getByRole('button',{name:'一键取消',exact:true}).click();
   assert.equal(await card.locator('input:checked').count(),0);
   await card.getByRole('button',{name:'一键全选',exact:true}).click();
   assert.equal(await card.locator('input:checked').count(),await card.locator('input').count());
  }
  await page.selectOption('#case-select','0');
  await page.selectOption('#fu-relation','暂不能判断');await page.fill('#fu-comment','测试：原文与中文保留');await page.check('#fu-defer');
  const event=page.waitForEvent('download');await page.click('#fu-export');const download=await event;
  const content=await fs.readFile(await download.path());const saved=JSON.parse(content);
  assert.equal(saved.schema,'pro_followup_review_20260920_v1');assert.equal(saved.evidence.length,6);
  await page.evaluate(()=>localStorage.clear());await page.reload();await page.waitForSelector('#fu-import');
  await page.locator('#fu-import').setInputFiles({name:'review.json',mimeType:'application/json',buffer:content});
  await page.waitForFunction(()=>document.querySelector('#fu-status').textContent==='导入成功');
  assert.equal(await page.inputValue('#fu-comment'),'测试：原文与中文保留');
  assert.equal(await page.locator('#fu-defer').isChecked(),true);
  await page.locator('#fu-import').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from('{"schema":"bad"}')});
  await page.waitForFunction(()=>document.querySelector('#fu-status').textContent.includes('导入失败'));
  assert.equal(await page.inputValue('#fu-comment'),'测试：原文与中文保留');
  if(process.argv[2]){await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:process.argv[2],fullPage:false});}
  assert.deepEqual(errors,[]);
  console.log('PASS six cases; full clusters; blank decisions; all/none; Unicode roundtrip; malformed import preserves answers; no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
