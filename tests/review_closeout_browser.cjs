const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {validateReturn}=require('../tools/thesis_main/analysis/review_return_20260927.js');
const {validateReviewReconciliation}=require('../tools/thesis_main/analysis/review_reconciliation_panel_20260925.js');
(async()=>{
 const root=path.resolve('analysis_results/review_closeout_20260928');
 const s=fs.readFileSync('analysis_results/review_return_20260927/data.js','utf8').replace(/\r\n/g,'\n');
 const d=JSON.parse(s.split('window.STUDIO_DATA=')[1].split(';\nwindow.STUDIO_IMAGES=')[0]);
 const value=JSON.parse(fs.readFileSync('analysis_results/review_final_20260928/evidence/latest.json','utf8'));
 validateReturn(value,d,new Set(d.cases.map(c=>c.image_id)),new Set(d.cases.flatMap(c=>c.review.annotation_ids)),validateReviewReconciliation);
 const b=await chromium.launch({headless:true});
 try{const page=await b.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'index.html')).href);
 await page.getByRole('link',{name:'打开当前结果'}).click();
 assert.equal(await page.getByRole('link',{name:/全量复核\.csv$/}).count(),1);
 assert.deepEqual(errors,[]);
 assert.equal(JSON.parse(fs.readFileSync(path.join(root,'repair_proposals.json'),'utf8')).applied,false);
 const applied=JSON.parse(fs.readFileSync(path.join(root,'effective_point_overrides.json'),'utf8'));assert.equal(applied.applied,true);assert.equal(Object.keys(applied.annotations).length,9);
 assert.equal(applied.annotations['80a4655a847e5a65'].effective_point_labels.includes('p7'),false);
 assert.equal(applied.annotations['f8c20f06811c7321e708'],undefined);
 assert.equal(applied.annotations['2559d23544f7b937'].effective_point_labels.includes('p14'),false);
 console.log('PASS: 最新JSON严格校验、旧入口指向当前CSV、9项修复和撤销。');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
