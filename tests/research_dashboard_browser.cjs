/* file:// + offline, using generated synthetic packages outside the repository. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(process.argv[2]);
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const context=await browser.newContext({offline:true,viewport:{width:1366,height:900}});
 const page=await context.newPage(),errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
 const open=async name=>{await page.goto(pathToFileURL(path.join(root,name,'index.html')).href);await page.waitForSelector('#navigation button');};
 const module=async key=>page.locator(`[data-module="${key}"]`).click();
 const contains=async (selector,text)=>assert.ok((await page.locator(selector).innerText()).includes(text));
 try{
  await open('empty');
  assert.equal(await page.locator('#navigation button').count(),6);
  assert.equal(await page.locator('#filters select:disabled').count(),7);
  assert.equal(await page.locator('.js-plotly-plot').count(),0);
  await page.screenshot({path:path.join(root,'empty-laptop.png'),fullPage:true});
  for(const key of ['annotation','stability','people','rooms','features']){await module(key);await contains('#results','待接入结果');}
  await module('overview');await page.setViewportSize({width:1920,height:1080});await page.screenshot({path:path.join(root,'empty-projection.png'),fullPage:true});
  await page.setViewportSize({width:1366,height:900});
  for(const name of ['test-a','test-b']){
   await open(name);await contains('#footer-release',name);
   assert.equal(await page.locator('.metric-value').first().innerText(),(name==='test-a'?'2':'3')+'人');
   if(name==='test-b'){await contains('#filter-method','另一套方法');await contains('#filter-classification','另一套分类');assert.ok(!(await page.locator('body').innerText()).includes('test-a'));}
   await page.locator('#filter-building').selectOption('b');
   assert.equal(await page.locator('#filter-room').inputValue(),'r');assert.equal(await page.locator('#filter-image').inputValue(),'i');
   assert.equal(await page.locator('.image-card').count(),1);await page.locator('#reset').click();
   await page.locator('#compare').check();assert.equal(await page.locator('.result-label').count(),0);
   await page.locator('#compare-view').selectOption('prior');assert.equal(await page.locator('.result-label').count(),2);
   await page.locator('#compare').uncheck();assert.equal(await page.locator('.result-label').count(),0);
   await page.locator('#image-search').fill('not-present');await contains('#image-list','没有匹配');await page.locator('#image-search').fill('');
   await page.locator('.image-card').filter({hasText:'j'}).click();await contains('#drawer','未包含图像资源');await page.keyboard.press('Escape');
   await module('stability');await page.waitForSelector('.js-plotly-plot');
   const expected=name==='test-a'?50:100;
   const plot=await page.locator('.js-plotly-plot').evaluate(p=>({y:p.data[0].y,custom:p.data[0].customdata,gaps:p.data[0].connectgaps,unit:p.layout.yaxis.title.text}));
   assert.deepEqual(plot.y,[null,expected,null,null,null]);assert.equal(plot.gaps,false);assert.equal(plot.custom[1][3],2);assert.equal(plot.custom[1][4],'p1、p2');assert.ok(plot.unit.includes('%'));
   await page.locator('.table-details summary').click();await contains('.table-details',String(expected));
   for(const state of ['人数不足','未计算','未达标','判断未决'])await contains('.table-details',state);
   await page.locator('.js-plotly-plot').evaluate(p=>Plotly.Fx.hover(p,[{curveNumber:0,pointNumber:1}]));await page.waitForSelector('.hovertext');
   await page.locator('.legendtoggle').click();await page.waitForFunction(()=>document.querySelector('.js-plotly-plot').data[0].visible==='legendonly');
   await page.waitForTimeout(350);await page.locator('.legendtoggle').click();
   await page.locator('.js-plotly-plot').evaluate(p=>Plotly.relayout(p,{'xaxis.range':[1.5,2.5]}));
   assert.deepEqual(await page.locator('.js-plotly-plot').evaluate(p=>p.layout.xaxis.range),[1.5,2.5]);
   await page.locator('.js-plotly-plot').evaluate(p=>p.emit('plotly_click',{points:[{customdata:p.data[0].customdata[1]}]}));
   await contains('#drawer','继承筛选');await page.waitForSelector('.panorama-scroll svg circle');
   const dot=page.locator('.panorama-scroll circle').first();await dot.click();await contains('#drawer','pair-0');
   await page.locator('[aria-label="对照点集"]').selectOption('perturbation');assert.equal(await page.locator('.panorama-scroll circle').count(),16);
   await page.locator('[aria-label="全景局部放大"]').fill('200');await page.locator('#detail-reset').click();await page.waitForSelector('.panorama-scroll circle');assert.equal(await page.locator('[aria-label="全景局部放大"]').inputValue(),'100');
   await page.locator('[aria-label="人员点集"]').selectOption('perturbation');await contains('#drawer','3D 不可用');
   assert.ok(await page.locator('.panorama-scroll line').evaluateAll(lines=>lines.every(l=>Math.abs(Number(l.getAttribute('x1'))-Number(l.getAttribute('x2')))<=512)));
   await page.locator('[aria-label="人员点集"]').selectOption('raw');
   const frameReady=page.waitForEvent('framenavigated',{predicate:f=>f.url().includes('/cases/')});
   await page.getByRole('button',{name:'展开此点集的 3D 预览'}).click();
   const frame=await frameReady;
   await frame.waitForFunction(()=>window.STUDIO?.snapshot().textureReady);
   const snapshot=await frame.evaluate(()=>STUDIO.snapshot());assert.equal(snapshot.fitStatus,'ok');assert.equal(snapshot.imageReady,true);
   assert.deepEqual(JSON.parse(snapshot.geometry).pairs.map(p=>p.display_index),[1,2,3,4]);
   await page.screenshot({path:path.join(root,name+'-detail.png'),fullPage:true});
   await page.keyboard.press('Escape');await module('people');const replay=page.locator('[aria-label="进入顺序重放步骤"]');await replay.fill('1');assert.equal(await page.locator('#results tbody tr:visible').count(),1);
   await module('features');await contains('#results','未计算');await module('rooms');await contains('#results','当前筛选无结果');
   await module('stability');await page.waitForSelector('.js-plotly-plot');await page.screenshot({path:path.join(root,name+'-chart.png'),fullPage:true});
  }
  await page.setViewportSize({width:800,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(network,[]);assert.deepEqual(errors,[]);
  console.log('PASS: empty + two releases; offline file URL; filters/comparison; nulls/table/units/members; images/points/3D; replay; 1366/1920 layout; no remote requests or page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
