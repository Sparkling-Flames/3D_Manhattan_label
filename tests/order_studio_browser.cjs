/* Run from repository root; checks the standalone file:// workflow without CORS exceptions. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out = path.resolve('analysis_results/order_studio_20260926');
const qa = path.join(out, 'browser_qa');
fs.mkdirSync(qa, {recursive: true});
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(out, 'data.js'), 'utf8'), context);
const cases = context.window.STUDIO_DATA.cases;
let unpaired;
for (const c of cases) {
  vm.runInNewContext(fs.readFileSync(path.join(out, c.history_script), 'utf8').split('\n')[0], context);
  unpaired = c.variants.find(v => v.source.role === 'annotation' && !v.geometry && v.source.points.length);
  if (unpaired) break;
}
assert.ok(unpaired, 'fixture must contain a retained 2D-only annotation');
(async () => {
  const browser = await chromium.launch({headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  const page = await browser.newPage({viewport: {width: 1512, height: 1100}});
  const errors = [], checks = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => {if (m.type() === 'error') errors.push(m.text());});
  const url = pathToFileURL(path.join(out, 'index.html')).href;
  const ready = () => page.waitForFunction(() => window.STUDIO?.snapshot().imageReady && STUDIO.snapshot().textureReady);
  try {
    await page.goto(url); await ready();
    const initial = await page.evaluate(() => STUDIO.snapshot());
    assert.equal(initial.orderRecord.source_identity.canonical_annotation_id, '158cdf9ee8269d7a');
    assert.equal(await page.locator('#card-fit').isVisible(), false);
    assert.equal(await page.locator('#metrics').isVisible(), false);
    assert.equal(await page.locator('#show-edges').isChecked(), false);
    await page.screenshot({path: path.join(qa, '01_default.png'), fullPage: true});
    checks.push('file:// loads actual WebGL and texture; single-source clean default');

    await page.locator('#pair-buttons button').first().click();
    await page.locator('#order-later').click();
    const changed = await page.evaluate(() => STUDIO.snapshot());
    assert.deepEqual(changed.previewOrder.slice(0, 2), [1, 0]);
    assert.equal(changed.sourceGeometry, initial.sourceGeometry);
    const source = JSON.parse(initial.sourceGeometry).pairs[0];
    const reordered = JSON.parse(changed.geometry).pairs[1];
    assert.deepEqual(reordered.top, source.top);
    assert.deepEqual(reordered.bottom, source.bottom);
    assert.equal(reordered.source_pair_id, source.source_pair_id);
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#order-export').click();
    const download = await downloadEvent;
    const record = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    assert.equal(record.source_identity.canonical_annotation_id, '158cdf9ee8269d7a');
    assert.equal(record.source_geometry_writeback, false);
    assert.equal(record.ring_confirmed, false);
    assert.deepEqual(record.preview_endpoint_effective_point_ids_1based,
      changed.previewOrder.flatMap(i => record.source_identity.links_zero_based[i].map(j => j + 1)));
    await page.locator('#order-restore').click();
    assert.equal((await page.evaluate(() => STUDIO.snapshot())).geometry, initial.geometry);
    checks.push('pair move, JSON export identity, unchanged coordinates, exact restore');

    await page.locator('[data-material="texture"]').click();
    await page.locator('[data-view="top"]').click();
    await page.locator('#show-edges').check();
    assert.equal((await page.evaluate(() => STUDIO.snapshot())).geometry, initial.geometry);
    await page.screenshot({path: path.join(qa, '02_top_texture.png'), fullPage: true});
    await page.locator('#worker-search').fill('W014');
    assert.equal((await page.evaluate(() => STUDIO.snapshot())).orderRecord.source_identity.worker_id, 'W014');
    checks.push('BEV, texture and line controls preserve geometry; worker search selects the requested source');

    const deepId = cases[1].annotation_ids[0];
    await page.goto(url + '?annotation=' + deepId); await ready();
    assert.equal((await page.evaluate(() => STUDIO.snapshot())).orderRecord.source_identity.canonical_annotation_id, deepId);
    await page.goto(url + '?annotation=' + unpaired.source.canonical_annotation_id); await ready();
    assert.equal((await page.evaluate(() => STUDIO.snapshot())).geometry, 'null');
    const box = await page.locator('#panorama').boundingBox();
    const point = unpaired.source.points[0];
    await page.mouse.click(box.x + box.width * point[0] / 1024, box.y + box.height * point[1] / 512);
    assert.match(await page.locator('#selection-details').innerText(), /上下配对未确认/);
    await page.screenshot({path: path.join(qa, '03_2d_retained.png'), fullPage: true});
    checks.push('cross-case deep links select exact canonical; missing geometry retains inspectable 2D points');

    await page.goto(url); await ready();
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(qa, '04_mobile.png'), fullPage: true});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert.deepEqual(errors, []);
    checks.push('390px layout has no horizontal overflow; no browser errors');
    fs.writeFileSync(path.join(qa, 'QA.json'), JSON.stringify({passed: true, checks, errors}, null, 2));
    console.log(JSON.stringify({passed: true, checks, errors}));
  } catch (error) {
    await page.screenshot({path: path.join(qa, 'failure.png'), fullPage: true});
    fs.writeFileSync(path.join(qa, 'QA.json'), JSON.stringify({passed: false, checks, errors, failure: String(error)}, null, 2));
    throw error;
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
