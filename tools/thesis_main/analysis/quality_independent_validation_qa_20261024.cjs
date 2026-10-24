const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const os=require('os');

(async()=>{
 const root=path.resolve(__dirname,'../../..');
 const output=path.join(root,'research/quality/quality_independent_validation_20261024');
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1500,height:1100},acceptDownloads:true});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('file:///'+path.join(output,'index.html').replaceAll('\\','/'));
 await page.waitForFunction(()=>loaded&&image.complete);
 const questions=await page.locator('#jump option').count();
 for(let i=0;i<questions;i++){
  await page.selectOption('#jump',String(i));
  await page.waitForFunction(()=>loaded&&image.complete);
 }
 await page.selectOption('#jump','0');await page.waitForFunction(()=>loaded&&image.complete);
 await page.check('#reference');
 const screenshot=path.join(os.tmpdir(),'hohonet_quality_review_20261024.png');
 await page.screenshot({path:screenshot,fullPage:true});
 await page.locator('#leftERP').click({position:{x:200,y:120}});
 const clickZoom=await page.inputValue('#zoom')==='2';
 await page.check('input[value=uncertain]');
 await page.fill('#reason','QA_TEMPORARY_CHECK');
 await page.reload();await page.waitForFunction(()=>loaded&&image.complete);
 const restored=await page.isChecked('input[value=uncertain]')&&await page.inputValue('#reason')==='QA_TEMPORARY_CHECK';
 const downloadEvent=page.waitForEvent('download');await page.click('#export');const download=await downloadEvent;
 const temporary=path.join(os.tmpdir(),'hohonet_quality_review_test_answers.json');await download.saveAs(temporary);
 const exported=JSON.parse(fs.readFileSync(temporary,'utf8'));
 if(questions!==25||!restored||!clickZoom||exported.answered_count!==1||errors.length)throw new Error(JSON.stringify({questions,restored,clickZoom,errors}));
 await page.selectOption('#spatialMode','3d');await page.locator('#zoom').evaluate(e=>{e.value='2';e.dispatchEvent(new Event('input'))});
 const spatialScreenshot=path.join(os.tmpdir(),'hohonet_quality_review_20261024_3d.png');
 await page.screenshot({path:spatialScreenshot,fullPage:true});
 await page.evaluate(()=>localStorage.clear());
 fs.unlinkSync(temporary);
 fs.writeFileSync(path.join(output,'BROWSER_QA.json'),JSON.stringify({schema:'quality_review_browser_qa_v1',
   file_protocol:true,browser:'Microsoft Edge headless',questions,all_embedded_images_loaded:true,
   auto_save_reload_restored:restored,json_export_verified:true,reference_toggle:true,click_to_zoom:clickZoom,zoom_and_3d_controls:true,
   page_errors:errors,test_answers_cleared:true},null,2));
 console.log(JSON.stringify({questions,restored,screenshot,spatialScreenshot}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
