/* Browser QA for the standalone local evidence artifact. No remote session,
 * scientific evaluation, scoring or source-data mutation is performed. */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

async function main() {
  const [html, executable, receipt, screenshot] = process.argv.slice(2);
  if (!html || !executable || !receipt) throw Error('html executable receipt [screenshot]');
  const errors = [], externalRequests = [];
  const browser = await chromium.launch({executablePath: executable, headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const page = await browser.newPage({viewport: {width: 1500, height: 1100}});
  page.on('pageerror', e => errors.push(String(e)));
  page.on('request', req => {if (/^https?:/.test(req.url())) externalRequests.push(req.url());});
  await page.goto('file://' + path.resolve(html), {waitUntil: 'load'});
  const count = await page.locator('#case option').count(), cases = [];
  for (let i=0; i<count; i++) {
    await page.selectOption('#case', String(i));
    const state = await page.evaluate(() => ({
      event: chosen.event.event_id, image: chosen.event.image,
      original_embedded: DATA.images[chosen.event.image].startsWith('data:image/png;base64,'),
      title: document.getElementById('title').textContent,
      counts: Object.fromEntries(['A','C'].map(arm => [arm,{
        workers:chosen.arms[arm].member_workers.length,
        boxes:document.querySelectorAll('#'+arm.toLowerCase()+'_workers input').length,
        groups:(chosen.arms[arm].full_state?.identity_groups||[]).length,
        vote_rows:document.querySelectorAll('#'+arm.toLowerCase()+'_votes tbody tr').length,
        raw_paths:document.querySelectorAll('#'+arm.toLowerCase()+'_svg path').length,
        status:chosen.arms[arm].score_status,
      }]))
    }));
    if (!state.original_embedded || /undefined/.test(state.title)) throw Error('bad title/image');
    for (const a of Object.values(state.counts))
      if (a.workers!==a.boxes || a.groups!==a.vote_rows) throw Error('evidence UI count mismatch');
    await page.click('#allraw');
    const all = await page.locator('[data-worker]:checked').count();
    if (all !== state.counts.A.workers+state.counts.C.workers) throw Error('all-raw toggle mismatch');
    await page.click('#noraw');
    if (await page.locator('[data-worker]:checked').count()) throw Error('hide-all failed');
    await page.click('#donly');
    const d = await page.evaluate(() => chosen.event.D_workers ? chosen.event.D_workers.split('|').length : 0);
    if ((await page.locator('[data-worker]:checked').count())!==2*d) throw Error('D toggle mismatch');
    await page.click('#blockonly');
    if ((await page.locator('[data-worker]:checked').count())!==all-2*d) throw Error('block toggle mismatch');
    await page.check('#showgroups');
    await page.uncheck('#showgroups');
    await page.click('#noraw');
    state.toggle_checks_passed = true;
    cases.push(state);
  }
  await page.selectOption('#case','0');
  if (screenshot) await page.screenshot({path:screenshot, fullPage:false});
  const dimensions = await page.evaluate(async () => {
    const output=[];
    for (const [image,src] of Object.entries(DATA.images)) {
      const img=new Image();img.src=src;await img.decode();
      output.push({image,width:img.naturalWidth,height:img.naturalHeight});
    }
    return output;
  });
  await browser.close();
  if (errors.length || externalRequests.length) throw Error(JSON.stringify({errors,externalRequests}));
  const result={browser_validation_passed:true,case_count:count,errors,external_requests:externalRequests,
    cases,image_dimensions:dimensions,standalone_file:path.resolve(html),
    no_new_fusions_or_scoring:true};
  fs.writeFileSync(receipt,JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({cases:count,images:dimensions.length,browser_validation_passed:true}));
}
main().catch(e=>{console.error(e.stack||e);process.exit(1)});
