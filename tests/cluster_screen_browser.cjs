const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=path.resolve(process.argv[2]),browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({offline:true,viewport:{width:1440,height:1050}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);
  await page.waitForFunction(()=>window.STUDIO?.snapshot().imageReady);
  assert.equal(await page.locator('#case-select option').count(),24);
  assert.ok(await page.evaluate(()=>STUDIO.snapshot().orderRecord.preview_endpoint_original_point_ids.every(x=>x!==null)));
  assert.equal(await page.locator('#rr-relation').inputValue(),'');
  for(let i=0;i<24;i++){
   await page.locator('#case-select').selectOption(String(i));
   await page.waitForFunction(i=>STUDIO.snapshot().caseIndex===i&&STUDIO.snapshot().imageReady,i);
   assert.equal(await page.locator('#rr-focus canvas').count(),1);
   assert.equal(await page.locator('#rr-relation').inputValue(),'');
  }
  await page.locator('#case-select').selectOption('0');
  await page.locator('#rr-method').selectOption('representative');
  await page.locator('#rr-pair').selectOption('1');
  await page.locator('#rr-focus canvas').click({position:{x:200,y:130}});
  await page.waitForSelector('[data-local]');
  await page.locator('#rr-relation').selectOption('对应需核查，暂缓');
  await page.locator('#rr-comment').fill('测试点号 p1/p2；这不是用户审核。');
  const exported=page.waitForEvent('download');await page.locator('#rr-export').click();const download=await exported;
  const data=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.equal(Object.keys(data.decisions).length,1);
  await page.reload();await page.waitForFunction(()=>window.STUDIO?.snapshot().imageReady);
  assert.equal(await page.locator('#rr-relation').inputValue(),'对应需核查，暂缓');
  await page.evaluate(()=>localStorage.clear());await page.reload();await page.waitForFunction(()=>window.STUDIO?.snapshot().imageReady);
  assert.equal(await page.locator('#rr-relation').inputValue(),'');
  await page.locator('#rr-import').setInputFiles({name:'review.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});
  await page.waitForFunction(()=>document.getElementById('rr-status').textContent.includes('导入成功'));
  assert.equal(await page.locator('#rr-relation').inputValue(),'对应需核查，暂缓');
  await page.locator('#rr-import').setInputFiles({name:'review.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...data,binding:{id:'wrong'}}))});
  assert.match(await page.locator('#rr-status').textContent(),/导入失败/);
  await page.locator('#rr-status').evaluate(e=>e.textContent='测试完成，截图仅用于界面检查');
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(root,'qa-temporary.png')});
  assert.deepEqual(errors,[]);
  console.log('PASS: 24 cases offline; images; method/witness switching; zoom; blank decisions; export/persistence; incompatible import rejected; no page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
