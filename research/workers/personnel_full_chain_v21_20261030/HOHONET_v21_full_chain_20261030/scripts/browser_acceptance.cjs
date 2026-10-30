/* Fresh local browser for offline research artifacts; no external requests. */
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,'playwright'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'stage06_synthesis/browser_acceptance');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.HOHONET_BROWSER||'/tmp/hohonet_case_viewer_chrome/chrome-linux64/chrome',args:['--no-sandbox','--disable-background-networking','--disable-dev-shm-usage']});
 const context=await browser.newContext({viewport:{width:1440,height:1050},deviceScaleFactor:1,locale:'zh-CN'});
 const tests=[['half','stage01_half_team/HOHONET_latest_half_all36_viewer_ZH.html'],['half_incomplete','stage01_half_team/HOHONET_latest_half_all36_viewer_ZH.html'],['same_room','stage02_same_room/abc/cases/CASE_VIEWER.html'],['same_room_incomplete','stage02_same_room/abc/cases/CASE_VIEWER.html'],['speed','stage03_speed_difficulty/CASES_VIEWER.html'],['report','REPORT_ZH.html']];
 const version=browser.version();const results=[];
 for(const [name,file] of tests){
  const page=await context.newPage();const errors=[],failed=[];page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url().slice(0,160),error:r.failure()?.errorText}));
  await page.route('**/*',r=>/^(file:|data:)/.test(r.request().url())?r.continue():r.abort());
  await page.goto('file://'+path.join(root,file),{waitUntil:'load',timeout:60000});
  if(name==='half'){await page.selectOption('#image','S9hNv5qa7GM-09');await page.selectOption('#arm','C');}
  if(name==='half_incomplete'){await page.selectOption('#image','S9hNv5qa7GM-12');await page.selectOption('#event','3541b27a4eff744938462e2b');await page.selectOption('#arm','A');}
  if(name==='same_room'){await page.selectOption('#view','b');await page.selectOption('#arm','C');}
  if(name==='same_room_incomplete'){
    const choice=await page.evaluate(()=>{const d=JSON.parse(document.getElementById('data').textContent);const e=d.endpoints.find(x=>x.score_status!=='complete_conditional');return {event:String(d.events.findIndex(x=>x.event_id===e.event_id)),view:e.view,arm:e.arm,status:e.score_status};});
    await page.selectOption('#event',choice.event);await page.selectOption('#view',choice.view);await page.selectOption('#arm',choice.arm);
  }
  await page.addStyleTag({content:"body,select,button,table,h1,h2,h3,nav {font-family:'Noto Sans CJK SC',sans-serif!important}"});
  await page.waitForTimeout(800);
  const state=await page.evaluate(()=>({title:document.title,text:document.body.innerText.slice(0,250),width:document.documentElement.scrollWidth,viewport:innerWidth,images:[...document.images].map(x=>({complete:x.complete,width:x.naturalWidth})),canvas:[...document.querySelectorAll('canvas')].map(x=>({width:x.width,height:x.height,hasNonzero:(()=>{try{return x.getContext('2d').getImageData(0,0,x.width,x.height).data.some(v=>v!==0)}catch(e){if(e.name==='SecurityError')return 'tainted_local_file_canvas';throw e}})()}))}));
  await page.screenshot({path:path.join(out,name+'.png'),fullPage:false});
  if(name.endsWith('_incomplete')){await page.locator('#pano').screenshot({path:path.join(out,name+'_panorama.png')});await page.locator(name==='half_incomplete'?'#floor':'#bev').screenshot({path:path.join(out,name+'_floor.png')});}
  results.push({name,file,errors,failed,...state});await page.close();
 }
 await browser.close();
 const result={fresh_local_browser:true,external_requests_allowed:false,browser_version:version,tests:results,all_passed:results.every(x=>!x.errors.length&&!x.failed.length&&x.canvas.every(c=>c.hasNonzero)&&x.images.every(y=>y.complete&&y.width>0)),screenshots_pending_visual_inspection:true};
 fs.writeFileSync(path.join(out,'BROWSER_EXECUTION_CHECKS.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));if(!result.all_passed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1);});
