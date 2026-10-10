const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const out=__dirname,browser=await chromium.launch({headless:true,downloadsPath:path.join(out,'_qa_downloads')});
 try{
  const context=await browser.newContext({viewport:{width:1500,height:1050},acceptDownloads:true}),p=await context.newPage(),errors=[];
  p.on('pageerror',e=>errors.push(e.message));await p.goto(require('node:url').pathToFileURL(path.join(out,'review.html')).href);
  assert.equal(await p.locator('#filter').inputValue(),'review');
  assert(await p.locator('#case option').count()>53);
  await p.locator('#filter').selectOption('extent');
  assert.equal(await p.locator('#case option').count(),13);
  await p.locator('#case').selectOption('pRbA3pwrgk9-02');await p.locator('#card').evaluate(im=>im.decode());
  assert((await p.locator('#content').innerText()).includes('淋浴'));
  assert((await p.locator('#opinion').innerText()).includes('需要你确认什么'));
  assert((await p.locator('#opinion').boundingBox()).y<(await p.locator('#card').boundingBox()).y);
  assert.equal(await p.locator('#metrics').evaluate(el=>el.open),false);
  await p.locator('#grade').selectOption('待复核');await p.locator('#scope').selectOption('范围明显不同');await p.locator('#note').fill('QA 临时测试，不是用户意见');
  await p.reload();await p.locator('#case').selectOption('pRbA3pwrgk9-02');assert.equal(await p.locator('#note').inputValue(),'QA 临时测试，不是用户意见');
  const wait=p.waitForEvent('download');await p.locator('#export').click();const download=await wait;const data=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
  assert.equal(data.review_version,'image-difficulty-review-259-20261010-v2');assert.equal(data.records.length,1);assert.equal(data.records[0].image,'pRbA3pwrgk9-02');assert.equal(data.records[0].scope,'范围明显不同');assert(data.records[0].gt_object_id);
  await p.evaluate(()=>localStorage.clear());await p.reload();assert((await p.locator('#status').innerText()).includes('0 张'));
  await p.locator('#filter').selectOption('conflict');assert.equal(await p.locator('#case option').count(),25);
  await p.locator('#case').selectOption('S9hNv5qa7GM-04');assert((await p.locator('#opinion').innerText()).includes('本轮：简单'));
  await p.locator('#case').selectOption('uNb9QFRL6hY-44');assert((await p.locator('#opinion').innerText()).includes('暂不定档'));
  await p.locator('#filter').selectOption('change');assert.equal(await p.locator('#case option').count(),8);
  await p.locator('#case').selectOption('uNb9QFRL6hY-43');assert((await p.locator('#opinion').innerText()).includes('建议从「中等」改为「简单」'));
  await p.locator('#filter').selectOption('uncertain');assert.equal(await p.locator('#case option').count(),60);
  await p.locator('#filter').selectOption('special');assert.equal(await p.locator('#case option').count(),42);
  await p.locator('#filter').selectOption('all');assert.equal(await p.locator('#case option').count(),259);
  const rows=JSON.parse(fs.readFileSync(path.join(out,'review_data.json'),'utf8'));
  assert.equal(rows.filter(r=>r.external_review).length,143);
  for(const r of rows.filter(r=>r.external_review)){assert.equal(r.image_id,r.external_review.image_id);assert.equal(r.gt_object_id,r.external_review.gt_object_id)}
  await p.locator('#case').selectOption('S9hNv5qa7GM-04');assert((await p.locator('#external-review').innerText()).includes('简单'));assert((await p.locator('#external-review').innerText()).includes('未填写备注'));
  assert.equal(await p.locator('#grade').inputValue(),'未审');
  const acknowledged=rows.find(r=>r.external_review?.grade==='认可建议');await p.locator('#case').selectOption(acknowledged.image);assert((await p.locator('#external-review').innerText()).includes('认可当时建议：'+acknowledged.external_review.proposed_class));
  const missing=rows.find(r=>!r.external_review);await p.locator('#case').selectOption(missing.image);assert((await p.locator('#external-review').innerText()).includes('未提供这张图的审核记录'));
  await p.locator('#case').selectOption('S9hNv5qa7GM-04');await p.locator('#card').evaluate(im=>im.decode());await p.screenshot({path:path.join(out,'_qa_external.png'),fullPage:false});

  await p.locator('#search').fill('x8F5xyUWy9e-01');assert.equal(await p.locator('#case option').count(),1);assert((await p.locator('#content').innerText()).includes('非正交'));
  await p.locator('#search').fill('no-such-case');assert.equal(await p.locator('#case option').count(),0);
  await p.locator('#search').fill('');await p.locator('#case').selectOption('pRbA3pwrgk9-02');await p.locator('#card').evaluate(im=>im.decode());
  // No screenshot needed: layout is unchanged; check updated evidence text and image decoding.

  assert.deepEqual(errors,[]);
  const evidence={status:'passed',checks:['143 external reviews bound to image and GT','historical acknowledgement and missing review display','external opinions do not fill user grades','259 image IDs','13 scope priority cases','8 grade changes','60 visual holds','42 special cases','search and empty results','image rendering','local draft reload','JSON export binds image and GT','test drafts cleared'],browser_errors:errors,isolated_context:true,user_data_modified:false};
  fs.writeFileSync(path.join(out,'browser_verification.json'),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));
 }finally{await browser.close();fs.rmSync(path.join(out,'_qa_downloads'),{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exit(1)});
