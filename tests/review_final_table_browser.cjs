const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {validateReturn}=require('../tools/thesis_main/analysis/review_return_20260927.js');
const {validateReviewReconciliation}=require('../tools/thesis_main/analysis/review_reconciliation_panel_20260925.js');
(async()=>{
 const root=path.resolve('analysis_results/review_final_20260928');
 const text=fs.readFileSync('analysis_results/review_continue_20260928/data.js','utf8').replace(/\r\n/g,'\n');
 const dataset=JSON.parse(text.split('window.STUDIO_DATA=')[1].split(';\nwindow.STUDIO_IMAGES=')[0]);
 const value=JSON.parse(fs.readFileSync(path.join(root,'evidence/continuation.json'),'utf8'));
 validateReturn(value,dataset,new Set(dataset.cases.map(c=>c.image_id)),new Set(dataset.cases.flatMap(c=>c.review.annotation_ids)),validateReviewReconciliation);
 const b=await chromium.launch({headless:true});
 try{
  const p=await b.newPage({viewport:{width:1440,height:1050}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto(pathToFileURL(path.join(root,'index.html')).href);
  assert.match(await p.locator('#count').textContent(),/3152/);
  assert.equal(await p.locator('#rows tr').count(),40);
  await p.locator('#scene').selectOption('both');
  const codes=await p.locator('#rows tr td:first-child').allTextContents();assert.ok(codes.length>0);assert.ok(codes.every(t=>t.includes('pRbA3pwrgk9-01')||t.includes('pRbA3pwrgk9-11')));
  await p.screenshot({path:path.join(root,'qa-table-temporary.png')});
  await p.locator('#rows button').first().click();assert.match(await p.locator('#details').textContent(),/scene_dimension_evidence/);
  await p.locator('#scene').selectOption('all');await p.locator('#disposition').selectOption('excluded_by_review');assert.match(await p.locator('#count').textContent(),/85/);
  await p.locator('#search').fill('rPc6DW4iMge-09');assert.equal(await p.locator('#rows tr').count(),3);
  await p.locator('#rows button').first().click();assert.match(await p.locator('#details').textContent(),/rPc09_three_workers_same_omission/);
  await p.locator('#search').fill('');await p.locator('#disposition').selectOption('all');await p.locator('#scene').selectOption('inner');
  assert.ok((await p.locator('#rows tr td:first-child').allTextContents()).every(t=>t.includes('uNb9QFRL6hY-51')));
  assert.equal(await p.getByRole('link',{name:'下载全量复核.csv',exact:true}).count(),1);
  await p.getByText('标注者排除统计 · 点击人员查看其明确排除作答',{exact:true}).click();await p.locator('#workers button').filter({hasText:'W037'}).click();assert.match(await p.locator('#count').textContent(),/共 29 份/);await p.getByText('本轮同房图片对照 · 原评论与GT版本',{exact:true}).click();await p.locator('#room').selectOption('G205');assert.equal(await p.locator('#room-images > section').count(),5);assert.match(await p.locator('#room-images').textContent(),/wc-61用户明确只勾选scope/);assert.deepEqual(errors,[]);console.log('PASS: 续审严格校验、3152行、交集筛选、85份排除、同错记录、内侧空间。');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
