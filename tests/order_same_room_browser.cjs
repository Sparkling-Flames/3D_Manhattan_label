const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {pathToFileURL}=require('node:url'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const ready=()=>page.waitForFunction(()=>STUDIO.snapshot().imageReady&&$('texture-state').textContent==='原图与纹理已载入');
  await page.goto(pathToFileURL(path.resolve('analysis_results/order_studio_20260926/index.html')).href);
  await ready();await page.evaluate(()=>chooseCase(29));await ready();
  assert.match(await page.locator('#source-badge').textContent(),/模型预标注坐标未改.*历史Trap/);
  assert.ok(await page.locator('#source-badge').isVisible());
  await page.goto(pathToFileURL(path.resolve('analysis_results/order_same_room_review_20260928/index.html')).href);
  await ready();
  assert.deepEqual(await page.evaluate(()=>[dataset.cases.length,dataset.cases.flatMap(c=>c.variants).length,Object.keys(saved).length,Object.values(saved).filter(r=>r.status==='confirmed').length]),[114,1208,89,0]);
  await page.evaluate(()=>chooseCase(31));await ready();
  await page.getByRole('button',{name:'筛选本图同房'}).click();
  assert.equal(await page.locator('#case-select option:not([hidden])').count(),9);
  await page.getByRole('button',{name:'显示全部图片'}).click();
  assert.equal(await page.locator('#case-select option:not([hidden])').count(),114);
  await page.evaluate(()=>chooseCase(43));await ready();
  assert.equal(await page.locator('#variant-select option').count(),26);
  await page.evaluate(()=>chooseVariant(dataset.cases[currentCase].variants.findIndex(v=>v.source.object_id==='a3975721377143bb')));
  assert.equal(await page.locator('#pairing-note').inputValue(),'第3 第4对点匹配错误');
  assert.match(await page.locator('#save-state').textContent(),/匹配错误/);
  const prior=await page.evaluate(()=>({id:sourceId(activeSource()),order:[...previewOrder]}));
  await page.evaluate(()=>chooseVariant(dataset.cases[currentCase].variants.findIndex(v=>v.source.object_kind==='gt_original')));
  assert.match(await page.locator('#source-badge').textContent(),/自带连接次序/);
  await page.locator('#confirm-order').click();
  const gtId=await page.evaluate(()=>sourceId(activeSource()));
  await page.reload();await ready();
  assert.equal(await page.evaluate(id=>saved[id].status,gtId),'confirmed');
  assert.deepEqual(await page.evaluate(id=>saved[id].order,prior.id),prior.order);
  await page.evaluate(()=>chooseCase(113));await ready(); // 新增无人员视角也能加载图片与GT。
  await page.evaluate(()=>chooseCase(dataset.cases.findIndex(c=>c.variants.some(v=>!v.geometry))));await ready();
  await page.evaluate(()=>chooseVariant(dataset.cases[currentCase].variants.findIndex(v=>!v.geometry)));
  await page.locator('#confirm-order').click();
  assert.match(await page.locator('#save-state').textContent(),/无可用点对/);
  assert.deepEqual(errors,[]);
  if(process.env.ORDER_REVIEW_QA){await page.evaluate(()=>chooseCase(29));await ready();await page.screenshot({path:process.env.ORDER_REVIEW_QA,fullPage:true});}
  console.log('PASS: 原工作台模型状态、114图1208来源、同房筛选、历史排列与配对评论、GT确认/重载、离线纹理、无配对保护');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
