/* Real Edge acceptance on the offline file page; downloads use browser events. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'..'),workbench=path.join(root,'research/statistics/research_explorer_v1_r2_20261017');
const temporary=path.join(root,'.tmp_dstruct_browser_20261026'),delivery=path.join(root,'research/workers/dstruct_composition_bridge_20261026');
fs.mkdirSync(temporary,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext({offline:true,viewport:{width:1440,height:1000},acceptDownloads:true});
  const page=await context.newPage(),errors=[],remote=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
  await page.goto(pathToFileURL(path.join(workbench,'composition-variance.html')).href);
  await page.waitForFunction(()=>document.querySelectorAll('#panel option').length===231);
  const data=await page.evaluate(()=>window.CompositionVarianceData);
  assert.match(await page.locator('#overview').innerText(),/14.36%/);
  assert.match(await page.locator('[aria-label="配比方差与严格换类并列解释"]').innerText(),/严格ABC/);
  await page.screenshot({path:path.join(temporary,'desktop-overview.png')});
  let selections=0;
  for(const method of ['DSTRUCT_K2','DSTRUCT_K3','OLD_STRUCTURE_COARSE','OLD_STRUCTURE_FINE']){
   await page.selectOption('#method',method);
   for(const metric of ['B8L2','D10','fusion_turn_n','log_recorded_time','not_complete_evaluable']){
    await page.selectOption('#metric',metric);selections++;
    assert.doesNotMatch(await page.locator('#distributions').innerHTML(),/NaN|undefined/);
   }
  }
  const missing=data.panels.find(p=>p.method==='DSTRUCT_K3'&&p.metric==='log_recorded_time'&&p.valid_teams===0);
  await page.selectOption('#method',missing.method);await page.selectOption('#metric',missing.metric);await page.selectOption('#panel',missing.panel_id);
  assert.match(await page.locator('#panelVariance').innerText(),/没有有效记录/);
  assert.doesNotMatch(await page.locator('#panelVariance').innerText(),/总方差为零/);
  const constant=data.panels.find(p=>p.method==='DSTRUCT_K3'&&p.metric==='fusion_turn_n'&&p.total_variance===0);
  await page.selectOption('#metric',constant.metric);await page.selectOption('#panel',constant.panel_id);
  assert.match(await page.locator('#panelVariance').innerText(),/总方差为零/);
  const rare=data.panels.find(p=>p.image==='B6ByNegPMKs-47'&&p.method==='DSTRUCT_K3'&&p.metric==='not_complete_evaluable'&&p.total_variance>0);
  await page.selectOption('#metric',rare.metric);await page.selectOption('#panel',rare.panel_id);
  const circles=await page.locator('#distributions circle').evaluateAll(ns=>ns.map(n=>Number(n.getAttribute('cx'))));
  assert(circles.length>0&&circles.every(x=>Number.isFinite(x)&&x>=0&&x<=620));
  await page.locator('#panelSupport').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(temporary,'desktop-rare-state.png')});
  await page.locator('summary').click();assert(await page.locator('#configTable').isVisible());
  const downloads=[];
  for(const [selector,name,source] of [
   ['#download','current.csv',null],
   ['a[download][href$="SUMMARY.csv"]','summary.csv','SUMMARY.csv'],
   ['a[download][href$="CONFIGURATIONS.csv"]','configurations.csv','CONFIGURATIONS.csv']]){
   const event=page.waitForEvent('download');await page.locator(selector).click();const download=await event;
   assert.equal(await download.failure(),null);const target=path.join(temporary,name);await download.saveAs(target);
   const bytes=fs.readFileSync(target);new TextDecoder('utf-8',{fatal:true}).decode(bytes);
   if(source)assert.deepEqual(bytes,fs.readFileSync(path.join(delivery,source)));
   else assert.deepEqual([...bytes.subarray(0,3)],[239,187,191]);
   downloads.push({file:name,suggested_filename:download.suggestedFilename(),bytes:bytes.length,source});
  }
  await page.setViewportSize({width:390,height:844});await page.locator('h1').scrollIntoViewIfNeeded();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert(await page.locator('#method').isVisible());await page.screenshot({path:path.join(temporary,'mobile.png')});
  await page.locator('#distributions').scrollIntoViewIfNeeded();
  assert(await page.locator('#distributions').evaluate(e=>e.scrollWidth>e.clientWidth));
  assert((await page.locator('#distributions svg').boundingBox()).width>=610);
  await page.screenshot({path:path.join(temporary,'mobile-distribution.png')});
  await page.locator('#distributions').evaluate(e=>e.scrollLeft=e.scrollWidth);
  await page.screenshot({path:path.join(temporary,'mobile-distribution-scrolled.png')});
  await page.locator('a[href*="tab=2"]').click();
  await page.waitForFunction(()=>document.querySelector('#content')?.textContent.includes('替换'));
  const strictText=await page.locator('#content').innerText();assert.match(strictText,/ABC/);assert.match(strictText,/CA|CB|同类|跨类/);
  await page.locator('#tabs button').nth(1).click();
  const varianceLink=page.locator('#content a[href="composition-variance.html"]').first();await varianceLink.click();
  await page.waitForFunction(()=>document.querySelectorAll('#panel option').length===231);
  assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  const result={schema:'dstruct_composition_browser_qa_20261026_v1',browser:'Microsoft Edge',headless:true,
   protocol:'file:',offline:true,desktop:{width:1440,height:1000},mobile:{width:390,height:844},method_metric_selections:selections,
   missing_time_distinguished:true,constant_results_distinguished:true,rare_state_means_visible:true,
   configuration_details_opened:true,mobile_charts_scroll_at_readable_width:true,native_downloads:downloads,current_download_panel:rare.panel_id,current_download_method:rare.method,
   current_download_metric:rare.metric,strict_abc_navigation:true,main_workbench_return_link:true,
   page_errors:errors,network_requests:remote,visual_inspection:'pending screenshot inspection',temporary_artifacts:'.tmp_dstruct_browser_20261026'};
  fs.writeFileSync(path.join(delivery,'BROWSER_QA.json'),JSON.stringify(result,null,2)+'\n','utf8');
  console.log(JSON.stringify({selections,downloads,temporary}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
