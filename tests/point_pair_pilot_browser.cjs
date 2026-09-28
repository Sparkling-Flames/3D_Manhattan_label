const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1440,height:1050},acceptDownloads:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(process.env.PILOT_URL||'http://127.0.0.1:8768/analysis_results/image_portrait_20260914_v1/local_review_studio/key39/index.html');
  await page.waitForFunction(()=>window.POINT_PAIR_PILOT&&originalImage&&dataset.cases[currentCase].image_id===POINT_PAIR_PILOT[0].image_id);
  assert.equal(await page.locator('#ppCase option').count(),6);
  assert.equal(await page.locator('#ppRelation').inputValue(),'');
  for(let i=0;i<6;i++){
   await page.selectOption('#ppCase',String(i));
   await page.waitForFunction(i=>originalImage&&dataset.cases[currentCase].image_id===POINT_PAIR_PILOT[i].image_id&&dataset.cases[currentCase].variants[currentVariant]?.source.canonical_annotation_id===POINT_PAIR_PILOT[i].id_a,i);
   assert.equal(await page.locator('#ppTable tbody tr').count(),4);
   assert.ok(await page.evaluate(()=>document.getElementById('panorama').width===2048));
  }
  await page.selectOption('#ppCase','4');
  await page.waitForFunction(()=>originalImage&&dataset.cases[currentCase].image_id===POINT_PAIR_PILOT[4].image_id);
  assert.equal(await page.locator('#ppB option').count(),2);
  await page.selectOption('#ppB','1');await page.selectOption('#ppPairB','接受当前候选');
  await page.fill('#ppNote','视觉审核测试：11–10／12–9；仍待判断。');
  await page.selectOption('#ppRelation','不能判断');await page.check('#ppDefer');
  const expected=await page.evaluate(()=>JSON.parse(localStorage.getItem('point_pair_pilot_20260919_v1')).decisions);
  const downloadPromise=page.waitForEvent('download');await page.click('#ppExport');const download=await downloadPromise;
  const bytes=await fs.readFile(await download.path()),payload=JSON.parse(bytes.toString('utf8'));
  assert.deepEqual(payload.decisions,expected);
  await page.fill('#ppNote','临时改变');page.on('dialog',d=>d.accept());
  await page.locator('#ppImport').setInputFiles({name:'审核.json',mimeType:'application/json',buffer:bytes});
  await page.waitForFunction(()=>document.getElementById('ppNote').value==='视觉审核测试：11–10／12–9；仍待判断。');
  assert.equal(await page.locator('#ppB').inputValue(),'1');assert.equal(await page.locator('#ppPairB').inputValue(),'接受当前候选');
  const original=await page.evaluate(()=>localStorage.getItem('point_pair_pilot_20260919_v1'));
  await page.locator('#ppImport').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({schema:'old',decisions:{}}))});
  await page.waitForFunction(()=>document.getElementById('ppStatus').textContent.startsWith('未导入'));
  assert.equal(await page.evaluate(()=>localStorage.getItem('point_pair_pilot_20260919_v1')),original);
  assert.equal(await page.locator('#auditPair option').count(),24);
  await page.locator('#panorama-panel').evaluate(e=>e.open=true);
  if(process.argv[2]){
   await page.locator('#point-pair-pilot').screenshot({path:process.argv[2]+'-panel.png'});
   await page.locator('#panorama').screenshot({path:process.argv[2]+'-panorama.png'});
   await page.locator('#crop').screenshot({path:process.argv[2]+'-crop.png'});
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: six images, variants, candidate preview, blank decisions, Unicode export/import, invalid import rejection, old24 preserved; no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
