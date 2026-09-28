const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {pathToFileURL}=require('node:url'),path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.resolve('analysis_results/order_gt_screened_20260928');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const ready=()=>page.waitForFunction(()=>STUDIO.snapshot().imageReady&&$('texture-state').textContent==='原图与纹理已载入');
  const select=async id=>{await page.evaluate(async id=>{const ci=dataset.cases.findIndex(c=>c.variants.some(v=>sourceId(v.source)===id));await chooseCase(ci);chooseVariant(dataset.cases[ci].variants.findIndex(v=>sourceId(v.source)===id));},id);await ready();};
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);await ready();
  const summary=JSON.parse(fs.readFileSync(path.join(root,'summary.json'),'utf8'));
  assert.deepEqual(await page.evaluate(()=>[visibleQueue().length,confirmedConnections().length]),[summary.pending,summary.confirmed]);
  assert.equal(await page.evaluate(()=>activeSource().object_kind==='gt_original'),false);
  assert.equal(await page.evaluate(()=>visibleQueue().some(e=>['B6ByNegPMKs-40','X7HyMhZNoso-05'].includes(dataset.cases[e.ci].title))),false);
  const ids=await page.evaluate(()=>({pending:sourceId(activeSource()),confirmed:dataset.cases.flatMap(c=>c.variants).find(v=>v.source.queue_state==='confirmed').source.object_id,manual:dataset.cases.flatMap(c=>c.variants).find(v=>v.source.queue_state==='pending'&&v.source.object_kind==='gt_manual_revision').source.object_id}));
  await select(ids.manual);
  assert.deepEqual(await page.evaluate(()=>previewOrder),await page.evaluate(()=>activeSource().default_preview_order));
  assert.ok(await page.evaluate(()=>previewOrder.map(i=>activeSource().points[activeSource().links_zero_based[i][0]][0]).every((x,i,a)=>!i||x>=a[i-1])));
  await page.locator('#queue-mode').selectOption('confirmed');await ready();await select(ids.confirmed);
  assert.equal(await page.locator('#confirm-order').isDisabled(),true);
  const unchanged=await page.evaluate(()=>({order:[...previewOrder],record:JSON.stringify(saved[sourceId(activeSource())])}));
  await page.evaluate(()=>setPreviewOrder([...previewOrder].reverse(),'test_readonly'));
  assert.deepEqual(await page.evaluate(()=>({order:[...previewOrder],record:JSON.stringify(saved[sourceId(activeSource())])})),unchanged);
  const historical=await page.evaluate(()=>{const [id,r]=Object.entries(saved).find(([id])=>id.startsWith('gt:')&&!dataset.cases.flatMap(c=>c.variants).some(v=>sourceId(v.source)===id));return {schema:reviewSchema,examples_only:false,records:{[id]:r}};});
  await page.locator('#import-orders').setInputFiles({name:'history.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(historical))});
  await page.waitForFunction(()=>$('save-state').textContent.includes('导入完成'));
  const beforeConflict=await page.evaluate(()=>JSON.stringify(saved));
  await page.locator('#import-orders').setInputFiles(path.resolve('analysis_results/order_same_room_review_20260928/evidence/user.json'));
  await page.waitForFunction(()=>$('save-state').textContent.startsWith('导入未应用：'));
  assert.equal(await page.evaluate(()=>JSON.stringify(saved)),beforeConflict);
  await page.locator('#queue-mode').selectOption('pending');await ready();await select(ids.pending);
  const edited=await page.evaluate(()=>{const order=[...previewOrder];[order[0],order[1]]=[order[1],order[0]];setPreviewOrder(order,'test_drag');return {order,binding:inputBinding()};});
  await page.reload();await ready();await select(ids.pending);
  assert.deepEqual(await page.evaluate(()=>({order:[...previewOrder],binding:inputBinding()})),edited);
  await page.locator('#confirm-order').click();await ready();
  assert.equal(await page.evaluate(()=>sourceId(activeSource())),ids.pending);
  assert.equal(await page.locator('#panorama-panel').isVisible(),true);
  assert.equal(await page.locator('#confirm-order').isDisabled(),true);
  assert.deepEqual(await page.evaluate(()=>previewOrder),edited.order);
  assert.equal(await page.evaluate(()=>visibleQueue().length),summary.pending-1);
  const exported=await page.evaluate(id=>confirmedConnections().find(o=>o.object_id===id),ids.pending);
  assert.deepEqual(exported.ordered_source_pair_indices,edited.order);
  const expected=await page.evaluate(id=>{const s=dataset.cases.flatMap(c=>c.variants).find(v=>sourceId(v.source)===id).source;return saved[id].order.flatMap(i=>s.links_zero_based[i]).map(i=>s.points[i]);},ids.pending);
  assert.deepEqual(exported.points_1024x512,expected);assert.equal(exported.closed,true);
  await page.locator('#order-more').evaluate(e=>e.open=true);
  const downloadEvent=page.waitForEvent('download');await page.locator('#export-connections').click();
  const download=await downloadEvent,chunks=[];for await(const chunk of await download.createReadStream())chunks.push(chunk);
  const downloaded=JSON.parse(Buffer.concat(chunks).toString('utf8'));
  assert.equal(downloaded.schema,'matterport_connection_order_v1');assert.deepEqual(downloaded.objects.find(o=>o.object_id===ids.pending),exported);
  await page.locator('#next-order').click();await ready();
  assert.notEqual(await page.evaluate(()=>sourceId(activeSource())),ids.pending);
  assert.equal(await page.locator('#panorama-panel').isVisible(),true);
  const pairingId=await page.evaluate(()=>sourceId(activeSource()));
  await page.locator('#pairing-note').fill('浏览器定向检查：配对待后续处理');await page.locator('#pairing-problem').click();await ready();
  assert.equal(await page.evaluate(()=>sourceId(activeSource())),pairingId);
  assert.equal(await page.locator('#panorama-panel').isVisible(),true);
  assert.equal(await page.evaluate(()=>visibleQueue().length),summary.pending-2);
  assert.equal(await page.evaluate(id=>saved[id].status,pairingId),'pairing');
  await page.locator('#next-order').click();await ready();
  const beforeMove=await page.evaluate(()=>[...previewOrder]);
  await page.locator('#pair-drag-list .pair-token').first().press('Alt+ArrowRight');
  const moved=[...beforeMove];[moved[0],moved[1]]=[moved[1],moved[0]];
  assert.deepEqual(await page.evaluate(()=>previewOrder),moved);
  // Record actual canvas text and label boxes; each toggle must immediately reflow.
  const layouts=await page.evaluate(()=>{
   const originalPlace=placePointLabel,ctx=$('panorama').getContext('2d'),originalText=ctx.fillText;
   const results=[];let boxes=[],texts=[];
   placePointLabel=function(...args){const b=originalPlace(...args);boxes.push({...b,width:args[1]});return b;};
   ctx.fillText=function(text,...args){texts.push(String(text));return originalText.call(this,text,...args);};
   try{for(const [sequence,pair] of [[true,true],[true,false],[false,true],[false,false]]){
    boxes=[];texts=[];$('show-sequence').checked=sequence;$('show-pair-labels').checked=pair;updateOverlayControls();results.push({sequence,pair,boxes,texts});
   }}finally{placePointLabel=originalPlace;ctx.fillText=originalText;$('show-sequence').checked=$('show-pair-labels').checked=true;updateOverlayControls();}
   return results;
  });
  for(const r of layouts){assert.equal(r.texts.some(t=>t.startsWith('对')),r.pair);assert.equal(r.texts.some(t=>/^\d+$/.test(t)),r.sequence);for(const b of r.boxes)assert.ok(b.left>=2&&b.top>=2&&b.right<=1022&&b.bottom<=510);}
  assert.ok(layouts[0].boxes[0].width>layouts[1].boxes[0].width);assert.ok(layouts[0].boxes[0].width>layouts[2].boxes[0].width);assert.equal(layouts[3].boxes.length,0);
  const dense=await page.evaluate(()=>{const pts=[[1,2],[1,8],[10,2],[10,8],[1023,510],[1020,508],[1015,507]],boxes=[];for(const p of pts)boxes.push(placePointLabel(p,60,22,boxes,pts));return boxes;});
  for(const b of dense)assert.ok(b.left>=2&&b.top>=2&&b.right<=1022&&b.bottom<=510);
  const failure=await page.evaluate(()=>{const before=JSON.stringify(saved),set=Storage.prototype.setItem;let result;try{Storage.prototype.setItem=()=>{throw Error('test quota failure');};result=saveReview('confirmed');}finally{Storage.prototype.setItem=set;}return {result,unchanged:JSON.stringify(saved)===before,message:$('save-state').textContent};});
  assert.equal(failure.result,false);assert.equal(failure.unchanged,true);assert.match(failure.message,/保存失败/);
  // 最后一份符合筛选的对象确认后，队列虽空，当前图仍保留。
  const last=await page.evaluate(async()=>{
   const list=visibleQueue(),key=e=>`${e.ci}|${e.source.worker_id} ${e.source.raw_condition}`;
   const e=list.find(e=>e.source.worker_id&&list.filter(o=>key(o)===key(e)).length===1);
   $('image-search').value=dataset.cases[e.ci].title;$('worker-search').value=`${e.source.worker_id} ${e.source.raw_condition}`;
   await applyQueueFilter();return sourceId(activeSource());
  });await ready();
  assert.equal(await page.evaluate(()=>visibleQueue().length),1);
  await page.locator('#confirm-order').click();
  assert.equal(await page.evaluate(()=>visibleQueue().length),0);
  assert.equal(await page.evaluate(()=>sourceId(activeSource())),last);
  assert.equal(await page.locator('#panorama-panel').isVisible(),true);
  assert.equal(await page.locator('#next-order').isDisabled(),true);
  assert.deepEqual(errors,[]);
  if(process.env.ORDER_REVIEW_QA)await page.screenshot({path:process.env.ORDER_REVIEW_QA,fullPage:true});
  await page.evaluate(()=>localStorage.setItem(storageKey,'{invalid-json'));await page.reload();await ready();
  assert.equal(await page.locator('#confirm-order').isDisabled(),true);
  assert.equal(await page.evaluate(()=>localStorage.getItem(storageKey)),'{invalid-json');
  assert.deepEqual(errors,[]);
  console.log('PASS: GT队列计数、待审导航、人工GT默认升序、已确认只读、历史导入与冲突保护、保存刷新与失败保护、配对移出、Matterport下载数组、标签四组合与边缘密集点');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
