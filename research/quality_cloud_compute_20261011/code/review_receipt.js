/* Offline answer receipts. No network, HTML evaluation, or research identifiers. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else {
    root.ReviewReceipt = api;
    const start = () => api.mount(root.document, () => root.localStorage);
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start);
    else start();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const VERSION = 'quality_blind_sample_receipt_v1';
  const STORAGE_KEY = VERSION + ':20261010:C01-C07-X01';
  const MAX_FILE_BYTES = 1024 * 1024;
  const MAX_FIELD_LENGTH = 2000;
  const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const clone = value => JSON.parse(JSON.stringify(value));
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const sameKeys = (value, keys) => object(value) && equal(Object.keys(value).sort(), [...keys].sort());
  function parseCSV(text) {
    const input = text.replace(/^\uFEFF/, '');
    const rows = []; let row = [], cell = '', state = 'plain';
    function endCell() { row.push(cell); cell = ''; state = 'plain'; }
    function endRow() { endCell(); rows.push(row); row = []; }
    for (let i = 0; i < input.length; i++) {
      const c = input[i];
      if (state === 'quoted') {
        if (c === '"' && input[i + 1] === '"') { cell += '"'; i++; }
        else if (c === '"') state = 'closed';
        else cell += c;
      } else if (c === ',' || c === '\r' || c === '\n') {
        if (c === ',') endCell();
        else { endRow(); if (c === '\r' && input[i + 1] === '\n') i++; }
      } else if (state === 'closed') throw new Error('CSV 引号后的格式无效。');
      else if (c === '"') {
        if (cell.length) throw new Error('CSV 引号格式无效。');
        state = 'quoted';
      } else cell += c;
    }
    if (state === 'quoted') throw new Error('CSV 引号未闭合。');
    if (row.length || cell.length || state === 'closed') endRow();
    return rows;
  }
  const csvCell = value => '"' + value.replace(/"/g, '""') + '"';
  function createController(schema, getStorage) {
    const fields = schema.fields, ids = schema.rows.map(r => r.case_id);
    const blank = clone(schema.rows);
    const fixed = new Map(blank.map(r => [r.case_id, r]));
    let answers = clone(blank), persistence = 'empty', storageError = '';
    function receipt() { return {format_version: VERSION, case_ids: [...ids], fields: [...fields], answers: clone(answers)}; }
    function validate(value) {
      if (!sameKeys(value, ['format_version', 'case_ids', 'fields', 'answers']) || value.format_version !== VERSION)
        throw new Error('回执版本或结构不匹配。请使用本页下载的 JSON/CSV 回执。');
      if (!equal(value.case_ids, ids)) throw new Error('案例ID清单或顺序不匹配。');
      if (!equal(value.fields, fields)) throw new Error('回执字段不匹配。');
      if (!Array.isArray(value.answers) || value.answers.length !== ids.length) throw new Error('必须包含全部八例回答。');
      const accepted = new Map();
      for (const row of value.answers) {
        if (!sameKeys(row, fields)) throw new Error('回答缺少字段或含有额外字段。');
        if (!fixed.has(row.case_id) || accepted.has(row.case_id)) throw new Error('案例ID非法或重复。');
        if (row.case_type !== fixed.get(row.case_id).case_type) throw new Error('案例类型不匹配。');
        const allowed = schema.active_fields[row.case_id];
        for (const field of fields) {
          if (typeof row[field] !== 'string' || row[field].length > MAX_FIELD_LENGTH) throw new Error('回答类型或长度无效（每字段最多2000字）。');
          if (field === 'case_id' || field === 'case_type') continue;
          if (!allowed.includes(field) && row[field] !== '') throw new Error('该案例含有不适用的回答字段。');
          const options = schema.options[field];
          if (options && row[field] !== '' && !options.includes(row[field])) throw new Error('选择项不匹配。');
        }
        accepted.set(row.case_id, Object.fromEntries(fields.map(field => [field, row[field]])));
      }
      return ids.map(id => accepted.get(id));
    }
    function persist() {
      if (persistence === 'unavailable') return false;
      try {
        getStorage().setItem(STORAGE_KEY, JSON.stringify(receipt()));
        persistence = 'saved'; storageError = ''; return true;
      } catch (e) {
        persistence = 'unavailable'; storageError = '本地草稿不可用：必须下载回执，关闭或刷新前请先下载。'; return false;
      }
    }
    function apply(value, saveDraft = true) {
      const checked = validate(value); // Validate entirely before changing any current answers.
      answers = checked;
      if (saveDraft) persist();
      return receipt();
    }
    function checkText(text) {
      if (typeof text !== 'string' || new TextEncoder().encode(text).length > MAX_FILE_BYTES) throw new Error('回执文件超过1 MiB或内容无效。');
    }
    function importJSON(text) { checkText(text); return apply(JSON.parse(text)); }
    function importCSV(text) {
      checkText(text); const rows = parseCSV(text);
      if (!equal(rows[0], ['#format_version', VERSION])) throw new Error('CSV 回执版本缺失或不匹配。');
      if (!equal(rows[1], fields)) throw new Error('CSV 回执字段不匹配。');
      if (rows.length !== ids.length + 2 || rows.slice(2).some(r => r.length !== fields.length)) throw new Error('CSV 回执案例数或字段数不匹配。');
      return apply({format_version: VERSION, case_ids: [...ids], fields: [...fields], answers: rows.slice(2).map(row => Object.fromEntries(fields.map((f, i) => [f, row[i]])))});
    }
    function load() {
      let text;
      try { text = getStorage().getItem(STORAGE_KEY); }
      catch (e) { persistence = 'unavailable'; storageError = '本地草稿不可用：必须下载回执，关闭或刷新前请先下载。'; return false; }
      if (text === null) { persistence = 'empty'; return false; }
      try { checkText(text); answers = validate(JSON.parse(text)); persistence = 'restored'; return true; }
      catch (e) { persistence = 'invalid'; storageError = '发现不匹配的浏览器草稿，未恢复；请从已下载的回执继续。'; return false; }
    }
    function update(id, field, value) {
      const next = receipt(), row = next.answers.find(r => r.case_id === id);
      if (!row || !schema.active_fields[id].includes(field)) throw new Error('案例或字段不匹配。');
      row[field] = value; return apply(next);
    }
    function toCSV() {
      return '\uFEFF' + [['#format_version', VERSION], fields, ...answers.map(row => fields.map(f => row[f]))].map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
    }
    return {receipt, validate, apply, load, update, importJSON, importCSV, toJSON: () => JSON.stringify(receipt(), null, 2) + '\n', toCSV,
      status: () => ({persistence, error: storageError})};
  }
  function mount(document, getStorage) {
    const schema = JSON.parse(document.getElementById('receipt-schema').textContent);
    const controller = createController(schema, getStorage);
    const controls = [...document.querySelectorAll('[data-case-id][data-field]')];
    const draft = document.getElementById('draft-status'), action = document.getElementById('receipt-status');
    function showDraft() {
      const state = controller.status();
      const labels = {empty: '本地草稿：尚无草稿。', saved: '本地草稿：已写入本浏览器。', restored: '本地草稿：已恢复本浏览器中的回答。', invalid: state.error, unavailable: state.error};
      draft.textContent = labels[state.persistence] + ' 浏览器草稿不保证持久保存；请下载回执备份。';
      draft.dataset.state = state.persistence;
    }
    function fill() {
      const rows = new Map(controller.receipt().answers.map(r => [r.case_id, r]));
      controls.forEach(el => { el.value = rows.get(el.dataset.caseId)[el.dataset.field]; });
    }
    function collect() {
      const value = controller.receipt(), rows = new Map(value.answers.map(r => [r.case_id, r]));
      controls.forEach(el => { rows.get(el.dataset.caseId)[el.dataset.field] = el.value; });
      controller.apply(value); showDraft();
    }
    function download(kind) {
      try {
        collect();
        const text = kind === 'json' ? controller.toJSON() : controller.toCSV();
        const url = URL.createObjectURL(new Blob([text], {type: kind === 'json' ? 'application/json;charset=utf-8' : 'text/csv;charset=utf-8'}));
        const link = document.createElement('a'); link.href = url; link.download = 'quality_blind_sample_receipt.' + kind;
        document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
        action.textContent = '已请求下载 ' + kind.toUpperCase() + ' 回执；请确认文件已保存。';
      } catch (e) { action.textContent = '无法导出：' + e.message; }
    }
    controller.load(); fill(); showDraft();
    controls.forEach(el => {
      el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => {
        try { controller.update(el.dataset.caseId, el.dataset.field, el.value); showDraft(); }
        catch (e) { action.textContent = '回答未写入草稿：' + e.message; }
      });
    });
    document.getElementById('download-json').addEventListener('click', () => download('json'));
    document.getElementById('download-csv').addEventListener('click', () => download('csv'));
    document.getElementById('import-receipt').addEventListener('change', async event => {
      const file = event.target.files[0]; if (!file) return;
      try {
        if (file.size > MAX_FILE_BYTES) throw new Error('回执文件超过1 MiB。');
        const text = await file.text();
        if (/\.json$/i.test(file.name)) controller.importJSON(text);
        else if (/\.csv$/i.test(file.name)) controller.importCSV(text);
        else throw new Error('请选择本页下载的 JSON 或 CSV 回执。');
        fill(); showDraft(); action.textContent = '已导入八例用户回答。图像与案例顺序未改变。';
      } catch (e) { action.textContent = '导入被拒绝，现有回答保持不变：' + e.message; }
      finally { event.target.value = ''; }
    });
    return controller;
  }
  return {VERSION, STORAGE_KEY, MAX_FILE_BYTES, MAX_FIELD_LENGTH, createController, parseCSV, mount};
});
