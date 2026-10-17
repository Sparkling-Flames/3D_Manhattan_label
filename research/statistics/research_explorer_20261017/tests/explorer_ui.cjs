/* File-backed DOM checks. They do not assert real-browser visual acceptance. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');
const root = path.resolve(__dirname, '..');
const data = path.resolve(process.argv[2] || path.join(root, 'explorer-data'));
const html = fs.readFileSync(path.join(root, 'explorer.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'explorer.js'), 'utf8');
const events = [];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check, label) {
  for (let i = 0; i < 200; i++) { if (check()) return; await delay(20); }
  throw Error('Timed out: ' + label);
}
function setup(mode = 'normal') {
  const virtualConsole = new VirtualConsole();
  const dom = new JSDOM(html, { url: 'https://local.test/explorer.html', runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole });
  const w = dom.window, errors = [], downloads = [];
  w.addEventListener('error', event => errors.push(event.message));
  w.scrollTo = () => {};
  w.fetch = async url => {
    const name = String(url).replace(/^explorer-data\//, '');
    if (mode === 'missing-table' && name.startsWith('tables/')) return { ok: false, status: 404 };
    const body = JSON.parse(fs.readFileSync(path.join(data, name), 'utf8'));
    if (mode === 'wrong-commit' && name === 'index.json') body.source_commit = 'wrong';
    return { ok: true, json: async () => body };
  };
  w.Blob = class { constructor(parts, options) { this.parts = parts; this.type = options?.type; } };
  w.URL.createObjectURL = blob => { downloads.push(blob); return 'blob:test'; };
  w.URL.revokeObjectURL = () => {};
  w.HTMLAnchorElement.prototype.click = function () {};
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function () { this.open = false; };
  w.eval(script);
  return { dom, w, errors, downloads, $: id => w.document.getElementById(id) };
}
(async () => {
  const { dom, w, $, errors, downloads } = setup();
  try {
    await until(() => !$('overview').hidden, 'overview');
    assert.match($('overview').textContent, /3,222/);
    assert.equal(w.document.querySelectorAll('#navigation button').length, 11);
    for (const module of ['inventory', 'quality', 'difficulty', 'workers', 'fusion', 'same_room', 'time', 'history', 'all']) {
      w.document.querySelector(`#navigation [data-module="${module}"]`).click();
      await until(() => !$('tableWorkspace').hidden && $('tableSelect').value, module);
      assert.ok($('dataTable').querySelector('thead'));
      events.push({ module, table: $('tableSelect').value, rows: $('rowCount').textContent });
    }
    w.document.querySelector('#navigation [data-module="quality"]').click();
    await until(() => !$('tableWorkspace').hidden, 'quality');
    $('tableSelect').value = 'quality__quality_records';
    $('tableSelect').dispatchEvent(new w.Event('change'));
    await until(() => !$('tableWorkspace').hidden && $('rowCount').textContent === '1,911 / 1,911', 'quality table');
    $('filterField').value = 'condition'; $('filterOperator').value = 'eq'; $('filterValue').value = 'manual'; $('addFilter').click();
    assert.equal($('rowCount').textContent, '1,446 / 1,911');
    $('clearFilters').click();
    $('filterOperator').value = 'range'; $('filterValue').value = '10'; $('filterMax').value = '1'; $('addFilter').click();
    assert.match($('filterMessage').textContent, /最小值/);
    $('clearFilters').click();
    $('nextPage').click(); assert.match($('pageNumber').textContent, /^2 \/ /);
    $('firstPage').click(); assert.match($('pageNumber').textContent, /^1 \/ /);
    const sort = $('dataTable').querySelector('[data-sort="B8L2"]'); sort.click();
    assert.equal($('dataTable').querySelector('[data-sort="B8L2"]').parentElement.getAttribute('aria-sort'), 'ascending');
    $('dataTable').querySelector('[data-sort="B8L2"]').click();
    assert.equal($('dataTable').querySelector('[data-sort="B8L2"]').parentElement.getAttribute('aria-sort'), 'descending');
    $('dataTable').querySelector('tr[data-row]').click(); assert.equal($('detailDialog').open, true);
    $('recordNote').value = 'Portable QA note'; $('saveRecordNote').click(); assert.equal($('noteCount').textContent, '1');
    w.document.querySelector('[data-close="detailDialog"]').click(); assert.equal($('detailDialog').open, false);
    $('notesOpen').click(); assert.match($('notesList').textContent, /Portable QA note/);
    $('exportNotes').click(); assert.match(downloads.at(-1).parts.join(''), /panorama_research_notes_v1/);
    w.document.querySelector('[data-close="notesDialog"]').click(); assert.equal($('notesDialog').open, false);
    $('exportCsv').click(); assert.match(downloads.at(-1).parts.join(''), /"object_id"/);
    $('chartType').value = 'scatter'; $('chartType').dispatchEvent(new w.Event('change'));
    assert.ok($('chart').querySelector('[data-chart-row]'));
    $('chart').querySelector('[data-chart-row]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    assert.equal($('detailDialog').open, true);
    const track = $('detailLinks').querySelector('[data-track-kind="worker"]');
    assert.ok(track); track.click(); assert.equal($('detailDialog').open, false);
    assert.ok($('globalWorker').value); assert.notEqual($('rowCount').textContent, '1,911 / 1,911');
    $('clearGlobal').click(); assert.equal($('rowCount').textContent, '1,911 / 1,911');
    $('tableSearch').value = 'not_a_real_table_987654'; $('tableSearch').dispatchEvent(new w.Event('input'));
    await until(() => !$('emptyModule').hidden, 'empty table search');
    assert.equal($('tableWorkspace').hidden, true);
    $('tableSearch').value = ''; $('tableSearch').dispatchEvent(new w.Event('input'));
    await until(() => !$('tableWorkspace').hidden, 'clear table search');
    // Repeated navigation must end on the most recent table, never a stale load.
    for (const module of ['fusion', 'quality', 'time']) w.document.querySelector(`#navigation [data-module="${module}"]`).click();
    await until(() => !$('tableWorkspace').hidden && $('tableSelect').value === 'statistics__record_lookup', 'newest navigation');
    assert.match($('moduleTitle').textContent, /时间/);
    w.location.hash = '#module=coverage';
    await until(() => !$('coverage').hidden, 'hash navigation');
    assert.equal($('coverage').querySelectorAll('details.document-card').length, 66);
    const legacy = [...w.document.querySelectorAll('a[href]')].filter(a => /核验/.test(a.textContent) && /resumed\.html|\/index\.html$/.test(a.href));
    assert.ok(legacy.length >= 2);
    assert.ok(legacy.every(a => a.href.startsWith('https://panorama-quality-review-20261016.fringnb.chatgpt.site/')));
    assert.deepEqual(errors, []);
  } finally { dom.window.close(); }
  for (const mode of ['wrong-commit', 'missing-table']) {
    const test = setup(mode);
    try {
      if (mode === 'wrong-commit') {
        await until(() => !test.$('error').hidden, mode);
        assert.match(test.$('error').textContent, /提交/);
      } else {
        await until(() => !test.$('overview').hidden, 'overview before missing table');
        test.w.document.querySelector('#navigation [data-module="quality"]').click();
        await until(() => test.$('tableInfo').textContent.includes('表格未能读取'), mode);
        assert.equal(test.$('tableWorkspace').hidden, true);
        assert.match(test.$('tableInfo').textContent, /404/);
      }
      assert.deepEqual(test.errors, []);
    } finally { test.dom.window.close(); }
  }
  console.log(JSON.stringify({ status: 'passed', modules: events, coverage: ['filters', 'invalid range', 'pagination', 'sorting', 'detail close/reopen', 'local notes', 'CSV/JSON exports', 'scatter', 'cross-table IDs', 'empty search recovery', 'repeated navigation', 'hash navigation', 'old review URLs', 'wrong commit rejection', 'missing table error'], scope: 'File-backed DOM tests, not authenticated real-browser visual QA' }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
