const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const screenshots=path.resolve(__dirname,'../../..','.tmp_personnel_composition_20261018');
fs.mkdirSync(screenshots,{recursive:true});
process.env.TEMP=screenshots;process.env.TMP=screenshots;
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1500,height:1050}});
    const errors = [], remote = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => {if (/^https?:/.test(r.url())) remote.push(r.url());});
    await page.goto(pathToFileURL(path.join(__dirname,'personnel_composition.html')).href);
    await page.waitForFunction(() => document.body.dataset.ready === 'true');
    assert.equal(await page.locator('#image option').count(),8);
    assert.equal(await page.locator('#pointEdits tbody tr').count(),24);
    const images = await page.locator('#image option').evaluateAll(os => os.map(o=>o.value));
    for (const scheme of ['Q2','QT4','Q3']) {
      await page.selectOption('#scheme',scheme);
      for (const image of images) {
        await page.selectOption('#image',image);
        assert.ok(await page.locator('#teams tbody tr').count()>0);
        assert.ok(await page.locator('#geometryA svg').count()>0);
      }
    }
    const caseCount=await page.locator('[data-case]').count();
    for(let i=0;i<caseCount;i++) {
      await page.click(`[data-case="${i}"]`);
      const expected=await page.evaluate(i=>window.PERSONNEL_COMPOSITION.review_cases[i],i);
      assert.equal(await page.inputValue('#teamA'),expected.request_a);
      assert.equal(await page.inputValue('#teamB'),expected.request_b);
    }
    await page.selectOption('#metric','D10');
    for(const view of ['bev','3d','erp']) await page.locator('#geometryA [data-view]').selectOption(view);
    await page.selectOption('#scheme','QT4');
    await page.selectOption('#experiment','same_endpoint_order');
    assert.equal(await page.locator('#orderTable tbody tr').count(),12);
    await page.selectOption('#k','2');
    assert.match(await page.locator('#chart').innerText(),/没有主质量/);
    assert.match(await page.locator('#cells').innerText(),/顺序前缀/);
    assert.match(await page.locator('#membersA').innerText(),/无主质量结果/);
    await page.selectOption('#k','4');
    const values=await page.locator('#teamA option').evaluateAll(os=>os.map(o=>o.value));
    const subsets=await page.evaluate(ids=>window.PERSONNEL_COMPOSITION.teams.filter(r=>ids.includes(r.request_id)).map(r=>r.state_key),values);
    assert.equal(new Set(subsets).size,1);
    const download=page.waitForEvent('download');await page.click('#export');assert.match((await download).suggestedFilename(),/composition/);
    await page.click('[data-case="0"]');
    assert.match(await page.locator('#cells').innerText(),/不足2组/);
    await page.locator('#geometryA [data-view]').selectOption('bev');
    await page.locator('#geometryB [data-view]').selectOption('bev');
    await page.locator('#geometryA').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(screenshots,'comparison.png')});
    await page.setViewportSize({width:850,height:1000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
    console.log(JSON.stringify({schemes:3,images:8,review_cases:caseCount,offline:true,errors,remote,screenshot:path.join(screenshots,'comparison.png')}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
