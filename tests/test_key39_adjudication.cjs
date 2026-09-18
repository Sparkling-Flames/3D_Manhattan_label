// Run: node tests/test_key39_adjudication.cjs (uses installed Playwright).
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const {key39Empty,key39Validate,key39ValidateLegacy}=require('../tools/thesis_main/analysis/key39_adjudication.js');
const root=path.resolve(__dirname,'..'),evidence=JSON.parse(fs.readFileSync(path.join(root,'analysis_results/human_review_reconciliation_20260918/39图裁决依据.json'),'utf8'));
const legacy=JSON.parse(fs.readFileSync(path.join(root,'analysis_results/human_review_reconciliation_20260918/用户_39图文字审核_原始.json'),'utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
const empty=key39Empty(evidence);assert(empty.decisions.every(r=>!r.answer));assert(empty.point_decisions.every(r=>!r.confirmed));
assert.deepEqual(key39Validate(clone(empty),evidence),empty);
assert.deepEqual(key39ValidateLegacy(legacy,evidence),legacy);
const mismatch=clone(empty);mismatch.decisions[0].condition='wrong';assert.throws(()=>key39Validate(mismatch,evidence));
const duplicate=clone(empty);duplicate.decisions[1]=duplicate.decisions[0];assert.throws(()=>key39Validate(duplicate,evidence));
const repair=clone(empty),point=repair.point_decisions.find(r=>!evidence.cases.find(c=>c.image_id===r.image_id).odd_records.find(x=>x.canonical_annotation_id===r.canonical_annotation_id).pending_update);
Object.assign(point,{action:'add_confirmed_point',confirmed:true,reason:'test'});assert.throws(()=>key39Validate(repair,evidence));point.added_coordinate=[200,300];assert(key39Validate(repair,evidence));
const stale=clone(empty),pending=stale.point_decisions.find(r=>evidence.cases.find(c=>c.image_id===r.image_id).odd_records.find(x=>x.canonical_annotation_id===r.canonical_annotation_id).pending_update);
Object.assign(pending,{action:'remove_confirmed_point',point_index:0,confirmed:true,reason:'test'});assert.throws(()=>key39Validate(stale,evidence));
(async()=>{
  const server=http.createServer((req,res)=>{try{const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(!file.startsWith(root+path.sep))throw Error('outside test root');const ext=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png'})[ext]||'application/octet-stream');fs.createReadStream(file).on('error',()=>{res.statusCode=404;res.end();}).pipe(res);}catch{res.statusCode=404;res.end();}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  let browser;
  try{
    browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1360,height:950},acceptDownloads:true});const page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const url=`http://127.0.0.1:${server.address().port}/analysis_results/image_portrait_20260914_v1/local_review_studio/key39/index.html`;
    await page.goto(url);await page.waitForFunction(()=>window.KEY39_ADJUDICATION_API&&document.querySelector('#key39-adjudication img')?.naturalWidth>0);
    const initial=await page.evaluate(()=>window.KEY39_ADJUDICATION_API.exportData());assert(initial.decisions.every(r=>!r.answer));
    assert.equal(await page.locator('#key39-adjudication select[aria-label="裁决图片"] option').count(),39);
    const caseWithIssue=evidence.cases.find(c=>c.issues.length);await page.getByLabel('裁决图片',{exact:true}).selectOption(caseWithIssue.image_id);
    const q=caseWithIssue.issues[0];await page.getByLabel(q.title+'裁决',{exact:true}).selectOption(q.options[0]);await page.getByLabel(q.title+'依据',{exact:true}).fill('浏览器验收文本，仅存在隔离测试上下文。');
    await page.reload();await page.waitForFunction(()=>window.KEY39_ADJUDICATION_API);let saved=await page.evaluate(()=>window.KEY39_ADJUDICATION_API.exportData());assert.equal(saved.decisions.find(r=>r.issue_id===q.issue_id).note,'浏览器验收文本，仅存在隔离测试上下文。');
    await page.getByLabel('裁决图片',{exact:true}).selectOption(caseWithIssue.image_id);
    if(q.workers.length){await page.getByRole('button',{name:q.workers[0]+' · 点集／3D',exact:true}).first().click();await page.waitForFunction(()=>document.getElementById('variant-select')?.value!=='');assert.equal(await page.evaluate(()=>dataset.cases[currentCase].variants[Number(document.getElementById('variant-select').value)].source.worker_id),String(Number(q.workers[0].slice(1))));}
    const oddCase=evidence.cases.find(c=>c.odd_records.some(r=>!r.pending_update));await page.getByLabel('裁决筛选',{exact:true}).selectOption('odd');await page.getByLabel('裁决图片',{exact:true}).selectOption(oddCase.image_id);
    const odd=oddCase.odd_records.find(r=>!r.pending_update);await page.getByLabel(odd.worker_id+'点复核动作',{exact:true}).selectOption('remove_confirmed_point');await page.getByLabel(odd.worker_id+'原始点编号',{exact:true}).selectOption('0');await page.getByLabel(odd.worker_id+'点复核依据',{exact:true}).fill('隔离测试删除点确认');
    await page.getByRole('button',{name:'确认并保存本份点复核',exact:true}).first().click();saved=await page.evaluate(()=>window.KEY39_ADJUDICATION_API.exportData());assert.equal(saved.point_decisions.find(r=>r.canonical_annotation_id===odd.canonical_annotation_id).confirmed,true);
    const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'导出最终裁决JSON',exact:true}).click();const download=await downloadPromise;const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.deepEqual(exported.decisions,saved.decisions);assert.equal(exported.evidence.cases.length,39);assert.equal(exported.confirmed_point_repair_instructions[0].user_decision.action,'remove_confirmed_point');assert.deepEqual(exported.confirmed_point_repair_instructions[0].candidate_point,odd.raw_points[0]);assert.equal(exported.evidence.pending_export_update.applied_to_geometry,false);
    await page.getByLabel('导入裁决或旧审核JSON',{exact:true}).setInputFiles({name:'roundtrip.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(exported))});await page.waitForFunction(()=>document.querySelector('#key39-adjudication [role="status"]').textContent.includes('导入成功'));
    const after=await page.evaluate(()=>window.KEY39_ADJUDICATION_API.exportData());assert.deepEqual(after.decisions,exported.decisions);assert.deepEqual(after.point_decisions,exported.point_decisions);
    await page.getByLabel('导入裁决或旧审核JSON',{exact:true}).setInputFiles({name:'legacy.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(legacy))});await page.waitForFunction(()=>window.KEY39_ADJUDICATION_API.exportData().legacy_review!==null);const imported=await page.evaluate(()=>window.KEY39_ADJUDICATION_API.exportData());assert.deepEqual(imported.decisions,exported.decisions);assert.deepEqual(imported.legacy_review,legacy);
    await page.getByLabel('导入裁决或旧审核JSON',{exact:true}).setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(mismatch))});await page.waitForFunction(()=>document.querySelector('#key39-adjudication [role="status"]').textContent.includes('导入失败'));assert.deepEqual((await page.evaluate(()=>window.KEY39_ADJUDICATION_API.exportData())).decisions,exported.decisions);
    // A clean independent context verifies the delivered blank defaults and supplies visual QA.
    const clean=await browser.newContext({viewport:{width:1360,height:950}}),preview=await clean.newPage();preview.on('pageerror',e=>errors.push(e.message));await preview.goto(require('node:url').pathToFileURL(path.join(root,'analysis_results/image_portrait_20260914_v1/local_review_studio/key39/index.html')).href);await preview.waitForFunction(()=>window.KEY39_ADJUDICATION_API&&document.querySelector('#key39-adjudication img')?.naturalWidth>0);
    if(process.env.KEY39_SCREENSHOT){await preview.getByText('实际视觉核查 · 初步意见',{exact:true}).scrollIntoViewIfNeeded();await preview.screenshot({path:process.env.KEY39_SCREENSHOT,fullPage:false});}
    await preview.setViewportSize({width:390,height:844});assert(await preview.locator('#key39-adjudication').evaluate(n=>n.scrollWidth<=n.clientWidth+2));
    assert.deepEqual(errors,[]);await clean.close();await context.close();console.log('PASS: schema guards, legacy import, isolated persistence, worker/3D binding, point confirmation, export/import roundtrip, rejected-import preservation, blank defaults; no page errors.');
  }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
