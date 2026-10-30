/* Offline browser acceptance for the four existing Q/QT case exhibits. */
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,'playwright'));
const out=__dirname,shots=path.join(out,'browser_checks');fs.mkdirSync(shots,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.HOHONET_BROWSER||'/tmp/hohonet_case_viewer_chrome/chrome-linux64/chrome',args:['--no-sandbox','--disable-background-networking','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1440,height:1050},deviceScaleFactor:1,locale:'zh-CN'}),results=[];
 const files=['index.html','case_uNb9QFRL6hY-01.html','case_uNb9QFRL6hY-43.html','case_uNb9QFRL6hY-12.html','case_S9hNv5qa7GM-10.html'];
 for(const file of files){
  const page=await context.newPage(),errors=[],failed=[],states=[];page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url().slice(0,140),error:r.failure()?.errorText}));
  await page.route('**/*',r=>/^(file:|data:)/.test(r.request().url())?r.continue():r.abort());
  await page.goto('file://'+path.join(out,file),{waitUntil:'load',timeout:60000});
  await page.waitForFunction(()=>window.__exhibitReady===true);
  const n=await page.evaluate(()=>window.__exhibitCases);
  for(let i=0;i<n;i++){
   if(i){await page.selectOption('#case',String(i));await page.waitForFunction(()=>window.__exhibitReady===true);}
   await page.click('#focus');await page.check('#other');
   const caseCode=await page.evaluate(()=>current().source.target_meta.image);
   const last=await page.locator('#raw option').last().getAttribute('value');await page.selectOption('#raw',last);await page.check('#rawTeams');
   const state=await page.evaluate(()=>({title:document.title,case:current().source.target_meta.image,raw_records:current().pool.records.length,selected_raw:+document.getElementById('raw').value,focus:[document.getElementById('cx').value,document.getElementById('cy').value,document.getElementById('zoom').value],width:document.documentElement.scrollWidth,viewport:innerWidth,image_complete:img.complete,image_width:img.naturalWidth,closure_policy:window.__exhibitClosurePolicy,statuses:[qp().score_status,tp().score_status],canvases:[...document.querySelectorAll('canvas')].map(c=>({id:c.id,w:c.width,h:c.height,nonzero:c.getContext('2d').getImageData(0,0,c.width,c.height).data.some(v=>v!==0)}))}));
   states.push(state);
   if(file==='index.html'){
    await page.locator('#qCanvas').screenshot({path:path.join(shots,caseCode+'_Q_focus.png')});
    await page.locator('#qtCanvas').screenshot({path:path.join(shots,caseCode+'_QT_focus.png')});
    await page.locator('#bevCanvas').screenshot({path:path.join(shots,caseCode+'_floor.png')});
    if(i===0){await page.click('#full');await page.uncheck('#other');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'index_top.png'),fullPage:false});await page.locator('#qCanvas').screenshot({path:path.join(shots,caseCode+'_Q_full.png')});}
   }
  }
  results.push({file,case_count:n,errors,failed,states});await page.close();
 }
 const receipt={fresh_local_browser:true,external_requests_allowed:false,browser_version:browser.version(),tests:results,all_passed:results.every(t=>!t.errors.length&&!t.failed.length&&t.states.every(s=>s.width<=s.viewport&&s.image_complete&&s.image_width===2048&&s.canvases.every(c=>c.nonzero)&&s.statuses.every(x=>x==='complete_conditional'))),visual_inspection:'pending',font_config:process.env.FONTCONFIG_FILE||null,scientific_results_recomputed:false};
 await browser.close();fs.writeFileSync(path.join(out,'BROWSER_VALIDATION.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));if(!receipt.all_passed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
