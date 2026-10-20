const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { pathToFileURL } = require('node:url');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => { window.fetch = () => { throw Error('offline fetch attempted'); }; });
    await page.goto(pathToFileURL(path.join(__dirname, 'index.html')).href + '#module=taxonomy');
    await page.waitForSelector('#content[data-ready="taxonomy"]', { timeout: 60000 });
    assert.match(await page.locator('#content').innerText(), /Manual结构表达工作分类/);
    assert.doesNotMatch(await page.locator('#content').innerText(), /该模块读取失败/);
    await page.locator('#tabs [data-tab="6"]').click();
    await page.waitForFunction(() => document.querySelector('#content')?.dataset.ready === 'taxonomy' && document.querySelector('#content')?.textContent.includes('n_pairs_contributing'));
    assert.match(await page.locator('#content').innerText(), /equal_count_origin_count_Qmean10_Qdiff5_matched/);
    assert.deepEqual(errors, []);
    console.log('PASS: offline taxonomy member and corrected A2 matching tables');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
