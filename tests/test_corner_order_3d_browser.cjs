const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require('../../tmp/node_modules/playwright-core');
(async () => {
 const browser = await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try {
 const page = await browser.newPage(); const errors=[];
 page.on('pageerror', e=>errors.push(e.message));
 await page.route('**/*', async route=> {
  const url = new URL(route.request().url());
  if (url.pathname.startsWith('/tools/')) {
   const file = path.join('tools/label_studio',path.basename(url.pathname));
   return route.fulfill({path:file,contentType:file.endsWith('.html')?'text/html':'application/javascript'});
  }
  if (url.pathname === '/pano.svg') return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="512"><rect width="1024" height="512" fill="lightblue"/></svg>'});
  if (url.pathname.startsWith('/projects/')) return route.fulfill({contentType:'text/html',body:`<div class="lsf-root lsf-root_mode_labeling"><div class="lsf-label-view"><div id="label-studio-dm" class="lsf-label-view__lsf-container"><div class="lsf-editor"><div class="lsf-current-task__task-id">10</div><div class="lsf-main-content"><div class="lsf-main-view"><img src="/pano.svg"><h3>3D Layout Preview</h3><div class="lsf-richtext">Loading</div></div></div></div></div></div></div>`});
  return route.fulfill({contentType:'application/json',body:'{}'});
 });
 const file = process.env.CORNER_SCRIPT || 'tools/label_studio/official/ls_userscript_annotator.js';
 await page.goto('http://localhost:8080/projects/1/data?task=10');
 await page.evaluate(()=> {
  localStorage.setItem('HOHONET_VIEWER_BASE_URL',location.origin);
  localStorage.setItem('HOHONET_HELPER_BASE_URL',location.origin);
  localStorage.setItem('HOHONET_DISABLE_ACTIVE_TIME','1');
  const points = [[10,20],[10,80],[35,20],[35,80],[60,20],[60,80],[85,20],[85,80]];
  window.H = {task:{id:10,project:1,data:{},annotations:{}},annotationStore:{selected:{id:'99',pk:99,results:points.map(([x,y],i)=>({type:'keypointlabels',area:{x,y},id:String(i)})),serializeCompletion:()=>[]}}};
 });
 await page.addScriptTag({path:file});
 await page.locator('#hohonet-refresh-btn').waitFor();
 const iframe = page.frameLocator('#hohonet-iframe');
 await iframe.locator('canvas').waitFor();
 await page.locator('#hohonet-refresh-btn').click();
 await page.waitForTimeout(300);
 const viewer = page.frames().find(frame => frame.url().includes('/tools/vis_3d.html'));
 await viewer.waitForFunction(() => meshObjects.length > 0);
 assert.ok(await viewer.evaluate(() => scene.children.some(child => child.isMesh)), '3D model must contain meshes');
 assert.deepEqual(errors,[], '3D refresh must not throw');
 await page.waitForFunction(()=>document.querySelectorAll('#hohonet-overlay [data-pctx]').length===8);
 // Refresh again after switching to a Map-backed historical annotation collection.
 await page.evaluate(() => { window.H.task.annotations = new Map(); });
 await page.locator('#hohonet-refresh-btn').click();
 await viewer.waitForFunction(() => meshObjects.length > 0);
 assert.deepEqual(errors,[]);
 // Reader failures must not prevent the viewer receiving fresh geometry.
 await page.evaluate(() => Object.defineProperty(window.H.task, 'annotations', {get(){throw new Error('history unavailable');}, configurable:true}));
 await page.locator('#hohonet-refresh-btn').click();
 assert.deepEqual(errors,[]);
 console.log('3D browser refresh and rendered model passed:',file);
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
