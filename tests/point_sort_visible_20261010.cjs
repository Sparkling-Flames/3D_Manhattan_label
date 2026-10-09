const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8769/');await page.locator('#scope-filter').selectOption('all');
  const select=async id=>{const i=await page.evaluate(id=>POINT_REVIEW_DATA.cases.findIndex(c=>c.record_id===id),id);await page.locator('#case-select').selectOption(String(i));await page.waitForFunction(id=>POINT_REVIEW_STATE().current===id&&POINT_REVIEW_STATE().imageReady,id);};
  await select('R02173');await page.locator('#tool-order').click();
  if(await page.locator('#baseline-choice').isVisible())await page.locator('#baseline-options button').first().click();
  const cards=page.locator('#pair-drag-list .pair-token');await cards.first().waitFor();assert.equal(await cards.count(),6);
  assert.equal(await page.locator('#sort-unpaired').isVisible(),false);
  const before=await page.evaluate(()=>POINT_REVIEW_STATE().pairs),a=await cards.nth(1).boundingBox();
  await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();await page.mouse.move(a.x+a.width/2+10,a.y+a.height/2,{steps:3});
  const target=await page.locator('#pair-drag-list').evaluate(el=>{const b=el.querySelectorAll('.pair-token')[1],r=el.getBoundingClientRect();return {x:r.left+b.offsetLeft+b.offsetWidth+2,y:r.top+b.offsetTop+b.offsetHeight/2};});
  await page.mouse.move(target.x,target.y,{steps:5});await page.mouse.up();
  const after=await page.evaluate(()=>POINT_REVIEW_STATE().pairs);assert.deepEqual(after,[before[0],before[2],before[1],...before.slice(3)]);
  await page.reload();await page.waitForFunction(()=>POINT_REVIEW_STATE().current==='R02173'&&POINT_REVIEW_STATE().imageReady);assert.deepEqual(await page.evaluate(()=>POINT_REVIEW_STATE().pairs),after);
  await page.locator('#undo-step').click();assert.deepEqual(await page.evaluate(()=>POINT_REVIEW_STATE().pairs),before);
  await select('R02155');await page.locator('#tool-order').click();if(await page.locator('#baseline-choice').isVisible())await page.locator('#baseline-options button').first().click();
  assert.equal(await cards.count(),0);assert.equal(await page.locator('#sort-unpaired button').count(),21);assert.match(await page.locator('#edit-status').innerText(),/奇数/);
  assert.deepEqual(errors,[]);await context.close();console.log('PASS x配对候选可见、拖动与刷新、撤销、奇数点解释');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
