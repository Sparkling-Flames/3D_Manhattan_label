const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const temporary=path.resolve(__dirname,'../../..','.tmp_exchangeability_20261018');
fs.mkdirSync(temporary,{recursive:true});process.env.TEMP=temporary;process.env.TMP=temporary;
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],remote=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
  await page.goto(pathToFileURL(path.join(__dirname,'personnel_exchangeability.html')).href);
  await page.waitForFunction(()=>document.body.dataset.ready==='true');
  assert.equal(await page.locator('#image option').count(),9);
  for(const scheme of ['AbsQ3','RelQ3','RelQT4']){
   await page.selectOption('#scheme',scheme);await page.selectOption('#k','');
   const expected=await page.evaluate(s=>EXCHANGEABILITY.fixed_curves.find(r=>r.scheme===s&&r.layer==='all'&&r.fixed_endpoint==='V'&&Number(r.k)===6),scheme);
   const displayed=await page.locator('#bySize tbody tr').first().locator('td').allTextContents();
   assert.equal(Number(displayed[3]),Number(expected.V_blocks));
   assert.ok(Math.abs(Number(displayed[5])-Number(expected.same_V))<0.000051);
   for(const k of ['6','8','12','16']){
    await page.selectOption('#k',k);assert.ok(await page.locator('#pair option').count()>0);
    assert.match(await page.locator('#background').innerText(),new RegExp('固定'+(Number(k)-1)+'名'));
   }
  }
  await page.selectOption('#anchorClass','higher_faster');assert.match(await page.locator('#support').innerText(),/2–4人/);
  for(const image of await page.locator('#image option').evaluateAll(os=>os.map(o=>o.value).filter(Boolean))){
   await page.selectOption('#image',image);
   await page.waitForFunction(()=>[...document.querySelectorAll('.geom-photo img')].every(i=>i.complete&&i.naturalWidth>0));
  }
  await page.selectOption('#scene','doorway_only');assert.equal(await page.locator('#image option').count(),3);
  await page.selectOption('#metric','D10');
  for(let i=0;i<3;i++){await page.click(`[data-example="${i}"]`);assert.equal(await page.inputValue('#k'),'16');}
  for(const view of ['bev','3d','erp'])await page.locator('#geometryA [data-view]').selectOption(view);
  await page.locator('#geometryA [data-layer="answer"]').uncheck();
  await page.locator('#geometryA [data-layer="answer"]').check();
  const download=page.waitForEvent('download');await page.click('#export');assert.match((await download).suggestedFilename(),/exchanges/);
  await page.click('[data-example="0"]');
  await page.locator('#geometryA [data-view]').selectOption('bev');await page.locator('#geometryB [data-view]').selectOption('bev');
  await page.locator('#geometryA').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(temporary,'exchange.png')});
  await page.setViewportSize({width:850,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.goto(pathToFileURL(path.join(__dirname,'personnel_composition.html')).href);
  await page.waitForFunction(()=>document.body.dataset.ready==='true');assert.equal(await page.locator('#humanFeedback tbody tr').count(),6);
  await page.click('[data-case="3"]');assert.match(await page.locator('#selectedFeedback').innerText(),/已记录相对判断：右侧较好/);
  assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  console.log(JSON.stringify({schemes:3,sizes:4,images:8,original_photos:true,fixed_chain_means_matched:true,high_fast_filter:true,feedback:6,errors,remote,screenshot:path.join(temporary,'exchange.png')}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
