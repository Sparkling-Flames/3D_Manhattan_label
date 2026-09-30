const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {pathToFileURL}=require('node:url'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1366,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const ready=()=>page.waitForFunction(()=>STUDIO.snapshot().imageReady&&document.getElementById('texture-state').textContent==='原图与纹理已载入');
 await page.goto(pathToFileURL(path.resolve('analysis_results/order_after_pairing_20260929/index.html')).href);await ready();
 assert.equal(await page.evaluate(()=>visibleQueue().length),23);assert.equal(await page.evaluate(()=>dataset.cases.length),18);
 assert.ok(await page.evaluate(()=>queueEntries.every(({source:s})=>s.links_zero_based.every(([a,b])=>s.points[a][0]===s.points[b][0]))));
 assert.deepEqual(await page.evaluate(()=>previewOrder),await page.evaluate(()=>activeSource().default_preview_order));
 const oid=await page.evaluate(()=>sourceId(activeSource()));await page.locator('#confirm-order').click();
 assert.equal(await page.evaluate(()=>sourceId(activeSource())),oid);assert.equal(await page.evaluate(()=>visibleQueue().length),22);
 assert.equal(await page.locator('#panorama').isVisible(),true);await page.locator('#reopen-order').click();
 assert.equal(await page.evaluate(()=>visibleQueue().length),23);await page.locator('#confirm-order').click();
 await page.reload();await ready();assert.equal(await page.evaluate(()=>confirmedConnections().length),1);
 if(process.env.ORDER_REVIEW_QA)await page.screenshot({path:process.env.ORDER_REVIEW_QA,fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS 新23份排序：预处理共享x、默认升序、确认留图、重新编辑、刷新保存');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
