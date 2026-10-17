const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require('../../tmp/node_modules/playwright-core');

// Faithful reproduction of the real Label Studio environment for the v12
// corner-order userscript: LabelStudio.instances store branch, MobX-like
// observable collections (Array.isArray === false), serializeCompletion
// returning an object, plus Label Studio's own draft PATCH traffic.
function fakeObsArray(items) {
  const arr = Object.create(Array.prototype);
  for (let i = 0; i < items.length; i++) arr[i] = items[i];
  Object.defineProperty(arr, 'length', {value: items.length, writable: true});
  return arr;
}

(async () => {
  const browser = await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage();
    const errors = [];
    const alerts = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', async d => { alerts.push(d.message()); await d.dismiss(); });
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.pathname.startsWith('/tools/')) {
        const file = path.join('tools/label_studio', path.basename(url.pathname));
        return route.fulfill({path:file, contentType:file.endsWith('.html')?'text/html':'application/javascript'});
      }
      if (url.pathname === '/pano.svg') return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="512"><rect width="1024" height="512" fill="lightblue"/></svg>'});
      if (url.pathname.startsWith('/projects/')) return route.fulfill({contentType:'text/html',body:`<div class="lsf-root lsf-root_mode_labeling"><div class="lsf-label-view"><div id="label-studio-dm" class="lsf-label-view__lsf-container"><div class="lsf-editor"><div class="lsf-current-task__task-id">10</div><div class="lsf-main-content"><div class="lsf-main-view"><img src="/pano.svg"><h3>3D Layout Preview</h3><div class="lsf-richtext">Loading</div></div></div></div></div></div></div>`});
      if (url.pathname.startsWith('/api/')) return route.fulfill({contentType:'application/json', body:'{"id":1}'});
      return route.fulfill({contentType:'application/json',body:'{}'});
    });
    const file = process.env.CORNER_SCRIPT || 'tools/label_studio/official/ls_userscript_annotator.js';
    await page.goto('http://localhost:8080/projects/1/data?task=10');
    await page.evaluate(() => {
      window.fakeObsArray = function fakeObsArray(items) {
        const arr = Object.create(Array.prototype);
        for (let i = 0; i < items.length; i++) arr[i] = items[i];
        Object.defineProperty(arr, 'length', {value: items.length, writable: true});
        return arr;
      };
      localStorage.setItem('HOHONET_VIEWER_BASE_URL', location.origin);
      localStorage.setItem('HOHONET_HELPER_BASE_URL', location.origin);
      localStorage.setItem('HOHONET_DISABLE_ACTIVE_TIME','1');
      // Corner results in percent coordinates, like real Label Studio.
      const mk = (x, y) => ({type:'keypointlabels', area:{x,y}, value:{x,y,width:2,keypointlabels:['Corner']}, id:'r'+x+'-'+y});
      const results = [mk(10,20),mk(10,80),mk(35,20),mk(35,80),mk(60,20),mk(60,80),mk(85,20),mk(85,80)];
      const selected = {
        pk: 99, id: 99, results: fakeObsArray(results),
        serializeCompletion: () => ({result: fakeObsArray(results), id: 99}),
      };
      const store = {
        annotationStore: { selected },
        task: { id: 10, project: 1, annotations: fakeObsArray([selected]) },
        taskStore: { selected: { id: 10, project: 1 } },
      };
      window.LabelStudio = { instances: [{ store }] };
      window.H = undefined;
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
    assert.deepEqual(errors, [], '3D refresh must not throw: ' + JSON.stringify(errors));

    // Label Studio draft PATCH with the same, fully paired corners.
    const patchBody = JSON.stringify({id:99, result:[
      {type:'keypointlabels', area:{x:10,y:20}, value:{x:10,y:20,keypointlabels:['Corner']}, id:'a'},
      {type:'keypointlabels', area:{x:10,y:80}, value:{x:10,y:80,keypointlabels:['Corner']}, id:'b'},
      {type:'keypointlabels', area:{x:35,y:20}, value:{x:35,y:20,keypointlabels:['Corner']}, id:'c'},
      {type:'keypointlabels', area:{x:35,y:80}, value:{x:35,y:80,keypointlabels:['Corner']}, id:'d'},
    ]});
    const patchResult = await page.evaluate(async (body) => {
      try { await window.fetch('/api/annotations/99/', {method:'PATCH', body, headers:{'Content-Type':'application/json'}}); return 'ok'; }
      catch (e) { return 'threw: ' + e.message; }
    }, patchBody);
    assert.equal(patchResult, 'ok', 'fully paired PATCH must succeed');
    assert.deepEqual(errors, [], 'submit interception must not throw page errors');
    assert.deepEqual(alerts, [], 'submit interception must not alert: ' + JSON.stringify(alerts));

    // Label Studio draft PATCH with an UNPAIRED corner (odd count) - real world case.
    const oddBody = JSON.stringify({id:99, result:[
      {type:'keypointlabels', area:{x:10,y:20}, value:{x:10,y:20,keypointlabels:['Corner']}, id:'a'},
      {type:'keypointlabels', area:{x:10,y:80}, value:{x:10,y:80,keypointlabels:['Corner']}, id:'b'},
      {type:'keypointlabels', area:{x:35,y:20}, value:{x:35,y:20,keypointlabels:['Corner']}, id:'c'},
    ]});
    const oddResult = await page.evaluate(async (body) => {
      try { await window.fetch('/api/annotations/99/', {method:'PATCH', body, headers:{'Content-Type':'application/json'}}); return 'ok'; }
      catch (e) { return 'threw: ' + e.message; }
    }, oddBody);
    assert.equal(oddResult, 'ok', 'unpaired corners must pass through without blocking');
    assert.deepEqual(alerts, [], 'pass-through must not alert: ' + JSON.stringify(alerts));
    assert.deepEqual(errors, [], 'pass-through must not throw page errors: ' + JSON.stringify(errors));
    console.log('Realistic store repro passed (3D refresh + non-blocking pass-through):', file);
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
