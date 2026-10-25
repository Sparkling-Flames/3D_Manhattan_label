const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {pathToFileURL,fileURLToPath}=require('node:url');
const path=require('node:path');
const fs=require('node:fs');
const shots=path.join(__dirname,'v2-resources/qa/workbench-ui');
fs.mkdirSync(shots,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
  const errors=[],network=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
  await page.addInitScript(()=>{window.fetch=()=>{throw Error('offline fetch attempted');};});
  await page.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
  async function ready(module){await page.waitForSelector(`#content[data-ready="${module}"]`,{timeout:60000});assert.doesNotMatch(await page.locator('#content').innerText(),/该模块读取失败|工作台暂时无法打开/);}
  async function go(module){await page.locator(`#navigation [data-module="${module}"]`).evaluate(e=>{if(e.closest('details'))e.closest('details').open=true;});await page.locator(`#navigation [data-module="${module}"]`).click();await ready(module);}
  await ready('overview');await go('data');assert.match(await page.locator('#rowCount').innerText(),/10,439/);
  const moduleIds=await page.locator('#navigation [data-module]').evaluateAll(es=>es.map(e=>e.dataset.module));assert(moduleIds.includes('personnel_main')&&moduleIds.includes('method_supplements'));
  await page.screenshot({path:path.join(shots,'data.png')});
  await page.click('#filterOpen');await page.selectOption('#f-condition','manual');
  assert.match(await page.locator('#rowCount').innerText(),/10,439/); // draft must not apply
  await page.locator('#filterForm button[type=submit]').click();await page.waitForFunction(()=>!document.getElementById('filters').open&&document.getElementById('activeFilters').textContent.includes('manual'));
  await ready('data');assert.doesNotMatch(await page.locator('#rowCount').innerText(),/10,439/);
  const dl=page.waitForEvent('download');await page.locator('.pagehead [data-act="export"]').click();const downloaded=await dl;assert.match(downloaded.suggestedFilename(),/filtered/);const csv=fs.readFileSync(await downloaded.path(),'utf8');assert.ok(csv.length>100000);assert.match(csv,/__snapshot/);
  await page.click('[data-act="reset"]');await page.waitForFunction(()=>document.getElementById('activeFilters').textContent.includes('无附加'));
  await ready('data');
  for(const m of moduleIds){
   await go(m);console.log('module',m,'OK');
   if(m==='images'){await page.screenshot({path:path.join(shots,'images.png')});await page.waitForSelector('.geom-photo image');const photo=await page.locator('.geom-photo image').first().getAttribute('href');assert(fs.existsSync(fileURLToPath(new URL(photo,page.url()))));await page.locator('[data-view]').first().selectOption('bev');await page.locator('[data-view]').first().selectOption('3d');}
   if(m==='workers'){await page.locator('input[data-check]').first().check();await page.click('[data-act="compare"]');await page.waitForSelector('#recordDialog[open]');await page.click('[data-close="recordDialog"]');await page.locator('.versions [data-act=notes]').click();await page.fill('#noteText','离线重构检查');await page.click('[data-act=saveNote]');const notesDownload=page.waitForEvent('download');await page.click('[data-act=exportNotes]');const notes=JSON.parse(fs.readFileSync(await (await notesDownload).path(),'utf8'));assert.equal(notes.snapshot,'v2_integrated_analysis_20261019');assert.ok(Object.values(notes.notes).some(n=>n.text==='离线重构检查'));await page.click('[data-close="notesDialog"]');}
   const tabs=await page.locator('#tabs [data-tab]').count();
   for(let t=0;t<Math.max(1,tabs);t++){
    if(t){await page.locator('#tabs [data-tab="'+t+'"]').click();await ready(m);}
    for(const width of [1440,390]){
     await page.setViewportSize({width,height:width===390?850:1000});
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),m+'/'+t+' overflows '+width);
    }
    await page.setViewportSize({width:1440,height:1000});
   }
  }
  await go('overview');assert.equal(await page.locator('#content [data-oos-entry]').count(),1);
  await page.locator('#navigation [data-oos-entry]').click();await ready('oos');
  assert.equal(await page.locator('[data-oos-image]').count(),28);assert.equal(await page.locator('#review-form').count(),0);
  await go('overview');
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  await page.setViewportSize({width:1280,height:900});await go('images');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true);
  await page.goto(pathToFileURL(path.join(__dirname,'../research_explorer_20261017/explorer.html')).href+'?revision=v1r2#module=all');await ready('data');
  await page.goto(pathToFileURL(path.join(__dirname,'../research_explorer_20261017/explorer.html')).href);if(fs.existsSync(path.join(__dirname,'../research_explorer_20261017/explorer-data/index.json'))){await page.waitForSelector('#overview:not([hidden])');assert.match(await page.locator('#overview').innerText(),/3,222/);}else{await page.waitForSelector('#error:not([hidden])');assert.match(await page.locator('#error').innerText(),/本地数据缺失/);}
  console.log('PASS: historical payload availability handled; all current modules/tabs, desktop/narrow, draft/apply, export, offline photos/BEV/3D, table comparison, notes, legacy link; zero HTTP');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
