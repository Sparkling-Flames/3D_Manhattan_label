const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader']});
 const page=await browser.newPage({viewport:{width:1366,height:768}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function dragFirstLast(cancel=false){
  const first=await page.locator('.pair-token').first().boundingBox();
  await page.mouse.move(first.x+first.width/2,first.y+first.height/2);await page.mouse.down();
  await page.mouse.move(first.x+first.width/2+10,first.y+first.height/2,{steps:3});
  assert.equal(await page.locator('.pair-floating').count(),1);
  const last=await page.locator('#pair-drag-list .pair-token').last().boundingBox();
  await page.mouse.move(last.x+last.width+15,last.y+last.height/2,{steps:8});
  if(cancel)await page.keyboard.press('Escape');
  await page.mouse.up();
  assert.equal(await page.locator('.pair-floating').count(),0);
 }
 await page.goto(pathToFileURL(path.resolve('analysis_results/order_acute_examples_20260928/index.html')).href);
 await page.waitForFunction(()=>STUDIO.snapshot().imageReady);
 assert.equal(await page.evaluate(()=>STUDIO_DATA.cases.length),10);
 assert.equal(await page.locator('#edge-color').inputValue(),'#ff2d85');
 await page.locator('#edge-color').selectOption('#00e5ff');
 const overlays=await page.evaluate(()=>{
  const ctx=document.getElementById('panorama').getContext('2d'),oldText=ctx.fillText,oldPath=drawPath;let paths=[],texts=[];
  ctx.fillText=function(text,...args){texts.push(String(text));return oldText.call(this,text,...args);};
  drawPath=function(ctx,points,color,...args){paths.push(color);return oldPath(ctx,points,color,...args);};
  try{drawPanorama();const colors=[...new Set(paths)];document.getElementById('hide-order-overlays').click();paths=[];texts=[];drawPanorama();return {colors,hiddenPaths:paths.length,hiddenNumbers:texts.filter(t=>/^\d+$/.test(t)),fixedLabels:texts.filter(t=>t.startsWith('对')).length};}
  finally{ctx.fillText=oldText;drawPath=oldPath;}
 });
 assert.deepEqual(overlays.colors,['#00e5ff']);assert.equal(overlays.hiddenPaths,0);assert.deepEqual(overlays.hiddenNumbers,[]);assert.ok(overlays.fixedLabels>0);
 await page.locator('#hide-order-overlays').click();assert.ok(await page.locator('#show-edges').isChecked());assert.ok(await page.locator('#show-sequence').isChecked());
 assert.ok(await page.evaluate(()=>document.getElementById('panorama').getBoundingClientRect().bottom<=document.getElementById('panorama-panel').getBoundingClientRect().bottom),'entire panorama must remain visible');
 const before=await page.evaluate(()=>STUDIO.snapshot().previewOrder);
 await dragFirstLast(true);assert.deepEqual(await page.evaluate(()=>STUDIO.snapshot().previewOrder),before);
 await dragFirstLast();
 const after=await page.evaluate(()=>STUDIO.snapshot().previewOrder);assert.deepEqual(after,[...before.slice(1),before[0]]);
 assert.equal(await page.locator('#pair-drag-list .sequence-circle').count(),0);
 assert.equal(await page.locator('.pair-token').last().textContent(),'对1');
 assert.equal(await page.evaluate(()=>pairDisplay(activeSource().links_zero_based[0][0])),`${after.length}·对1`);
 await page.locator('.pair-token').first().hover();assert.equal(await page.evaluate(()=>hoveredPair),after[0]);
 await page.locator('#confirm-order').click();await page.reload();await page.waitForFunction(()=>STUDIO.snapshot().imageReady);
 assert.deepEqual(await page.evaluate(()=>STUDIO.snapshot().previewOrder),after);
 assert.ok(await page.locator('#confirm-order').evaluate(el=>el.getBoundingClientRect().bottom<=innerHeight),'image and sorting controls should fit first screen');
 assert.ok(await page.locator('#viewport-raw').evaluate(el=>el.getBoundingClientRect().bottom>innerHeight),'3D remains below for optional scrolling');
 await page.locator('#next-order').click();await page.waitForFunction(()=>STUDIO.snapshot().caseIndex===1&&STUDIO.snapshot().imageReady);
 await page.screenshot({path:'analysis_results/order_acute_examples_20260928/temporary_qa.png',fullPage:true});
 assert.deepEqual(errors,[]);await browser.close();console.log('pointer sorting, Escape cancellation, fixed identities, confirmation and reload passed');
})().catch(e=>{console.error(e);process.exit(1)});
