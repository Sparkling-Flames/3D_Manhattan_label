'use strict';
const cases = window.REVIEW_CASES;
const schema = 'panorama_human_review_v1', key = 'hohonet_uncertainty_review_20260907_v1';
const $ = id => document.getElementById(id), form = $('review-form');
const enums = {visibility:['clear','partial','insufficient'], scope:['one_clear','multiple_candidates','rule_unclear','uncertain'], human_difference:['similar','local','scope','mixed','uncertain','not_applicable'], annotation_assessment:['some_plausible','all_questionable','not_all_checked','uncertain'], oos_assessment:['in_scope','suspected','reviewer_oos','uncertain'], status:['draft','deferred','reviewed']};
const factors = ['scope','occlusion','local','rule','sequence','reference','assumptions'];
let records = {}, current = 0, storageOK = true;
function error(message='') { $('error').textContent = message; $('error').hidden = !message; }
function oosFlag(a) { return ['suspected','reviewer_oos'].includes(a.oos_assessment); }
function complete(a) { return oosFlag(a) ? !!a.oos_reason.trim() : !!(a.visibility && a.scope && a.human_difference); }
function oosUI(a) { $('oos-guidance').hidden = $('oos-save-step').hidden = !oosFlag(a); }
function validate(bundle) {
  if (bundle?.schema !== schema || !Array.isArray(bundle.records)) throw Error('不是本问卷的JSON备份');
  const result = {};
  for (const r of bundle.records) {
    const c = cases.find(c => c.case_id === r?.case_id); let a = r?.answers;
    if (!c || c.image_id !== r.image_id || result[r.case_id]) throw Error('图像身份不匹配或有重复记录');
    if (!a || typeof a !== 'object' || Array.isArray(a) || Object.keys(a).some(k => ![...Object.keys(enums),'factors','notes','oos_reason'].includes(k))) throw Error('答案字段不匹配');
    a = {annotation_assessment:'',oos_assessment:'',oos_reason:'',...a}; // Missing optional fields in older backups stay unanswered.
    for (const [field, values] of Object.entries(enums)) if (a[field] !== '' && !values.includes(a[field])) throw Error('答案选项不匹配：'+field);
    if (typeof a.notes !== 'string' || a.notes.length > 100000 || !Array.isArray(a.factors) || a.factors.some(v => !factors.includes(v)) || new Set(a.factors).size !== a.factors.length) throw Error('备注或多选答案格式错误');
    if ((c.has_humans && a.human_difference === 'not_applicable') || (!c.has_humans && a.human_difference !== 'not_applicable')) throw Error('真人响应适用性不匹配');
    if (typeof a.oos_reason !== 'string' || a.oos_reason.length > 100000) throw Error('OOS理由格式错误');
    if (a.status === 'reviewed' && !complete(a)) throw Error('完成记录缺少必答题或OOS理由');
    if (typeof r.updated_at !== 'string' || typeof r.ai_advice_opened !== 'boolean') throw Error('记录元数据不完整');
    result[r.case_id] = {case_id:r.case_id,image_id:r.image_id,answers:{...a,factors:[...a.factors]},updated_at:r.updated_at,ai_advice_opened:r.ai_advice_opened};
  }
  return result;
}
function bundle() { return {schema, exported_at:new Date().toISOString(), meaning:'独立人工问卷记录；reviewed不是最终裁决。', records:Object.values(records)}; }
function progress() {
  const values = Object.values(records), done = values.filter(r=>r.answers.status === 'reviewed').length, deferred = values.filter(r=>r.answers.status === 'deferred').length;
  $('progress').textContent = `${current+1} / ${cases.length}`;
  $('footer-count').textContent = `已记录 ${values.length} 张 · 本轮完成 ${done} 张 · 暂缓 ${deferred} 张`;
  [...$('case-select').options].forEach((option,i)=> { const c = cases[i], status = records[c.case_id]?.answers.status; option.textContent = `${c.case_id} · ${c.building_id} · ${c.has_humans?'历史':'候选'}${status ? ' · '+({draft:'草稿',deferred:'暂缓',reviewed:'已记录完成'}[status]) : ''}`; });
}
function persist() {
  if (storageOK) {
    try { localStorage.setItem(key, JSON.stringify(bundle())); }
    catch (e) { storageOK = false; }
  }
  $('save-state').textContent = storageOK ? '答案已暂存于当前浏览器；结束时请导出JSON备份。' : '浏览器暂存不可用，答案仅在本页内存中；离开或刷新前请立即导出JSON。';
  progress();
}
function save() {
  const c = cases[current], data = new FormData(form), answers = {};
  for (const field of Object.keys(enums)) answers[field] = data.get(field) || '';
  answers.status ||= 'draft';
  if (!c.has_humans) answers.human_difference = 'not_applicable';
  answers.factors = data.getAll('factors'); answers.notes = $('notes').value; answers.oos_reason = $('oos-reason').value;
  oosUI(answers);
  const valid = answers.status !== 'reviewed' || complete(answers);
  if (!valid) { answers.status = 'draft'; form.querySelector('[name=status][value=draft]').checked = true; }
  records[c.case_id] = {case_id:c.case_id,image_id:c.image_id,answers,updated_at:new Date().toISOString(),ai_advice_opened:!!records[c.case_id]?.ai_advice_opened || $('ai-advice').open};
  error(valid ? '' : oosFlag(answers) ? '已保留为草稿。请在第①步填写OOS依据或待核对问题，再标记本轮完成。' : '已保留为草稿。标记完成前，请填写第1、2题，以及历史图的第4题；可以选择“暂时无法判断”。');
  persist(); return valid;
}
function step(n) {
  document.querySelectorAll('[data-panel]').forEach(e=>e.hidden = e.dataset.panel !== String(n));
  document.querySelectorAll('nav [data-step]').forEach(e=>e.setAttribute('aria-current',e.dataset.step === String(n) ? 'step' : 'false'));
  window.scrollTo(0,0);
}
function variant() {
  const c = cases[current], v = c.variants[Number($('variant-select').value)], base = `cases/${c.case_id}/`;
  $('old-panel').src = base+v.variant+'_panel.jpg';
  $('overlay-link').href = base+'hd/'+v.variant+'.svg';
  $('points-link').href = base+'hd/'+v.variant+'_points.svg';
  $('variant-info').textContent = `${v.label} · 来源ID：${v.source_id}`;
  const adjustment = c.adjustments.find(a=>a.variant === v.variant);
  $('order-warning').hidden = !adjustment && v.original_status !== 'failed';
  $('order-warning').textContent = adjustment ? '此版本存在独立点序预览建议。上图及高清／新版入口仍使用导出顺序；重排未获确认。'+adjustment.explanation : '此版本在当前读取／投影假设下未能生成旧版网格。先看“仅原始点”，不能用红色直连线或NO MESH判定原标注错误。';
}
function show(index) {
  current = Math.max(0,Math.min(cases.length-1,index)); const c = cases[current], base = `cases/${c.case_id}/`;
  form.reset(); $('ai-advice').open = false; $('adjustments').open = false; error();
  $('case-select').value = String(current); $('previous').disabled = current === 0; $('next').disabled = current === cases.length-1;
  $('image-id').textContent = `${c.case_id} · building ${c.building_id} · ${c.has_humans?'有历史标注':'无历史标注候选'} · ${c.image_id}`;
  $('original-link').href = $('original').src = base+'hd/panorama.png';
  $('studio-link').href = base+'hd/studio/index.html'; $('all-panels').src = base+'03_comparison.jpg';
  $('variant-select').replaceChildren(...c.variants.map((v,i)=>new Option(v.label,String(i)))); variant();
  $('human-question').hidden = !c.has_humans; $('no-humans').hidden = c.has_humans;
  $('ai-observation').textContent = c.ai_observation; $('ai-question').textContent = c.ai_question;
  $('adjustments').hidden = !c.adjustments.length; $('adjustment-content').replaceChildren();
  for (const a of c.adjustments) { const p = document.createElement('p'), img = document.createElement('img'); p.textContent = a.variant+'：'+a.explanation+' 当前说明：'+a.observation+' 上排为导出顺序，下面为独立重排预览，不能视为已确认的修正。'; img.src = a.panel; img.loading = 'lazy'; img.alt = '独立点序预览建议，未改原坐标'; $('adjustment-content').append(p,img); }
  const r = records[c.case_id];
  if (r) {
    for (const field of Object.keys(enums)) { const input = form.querySelector(`[name="${field}"][value="${r.answers[field]}"]`); if (input) input.checked = true; }
    for (const value of r.answers.factors) form.querySelector(`[name=factors][value="${value}"]`).checked = true;
    $('notes').value = r.answers.notes;
    $('oos-reason').value = r.answers.oos_reason;
  }
  oosUI(r?.answers || {});
  $('save-state').textContent = !storageOK ? '浏览器暂存不可用，请在离开前导出JSON。' : r ? '已恢复这张图的暂存答案。' : '这张图尚未填写。选择或输入后自动暂存。';
  step(1); progress(); if (location.hash !== '#'+c.case_id) location.hash = c.case_id;
}
function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text],{type})), a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('case-select').replaceChildren(...cases.map((c,i)=>new Option(c.case_id,String(i))));
try { const saved = localStorage.getItem(key); if (saved) records = validate(JSON.parse(saved)); }
catch(e) { storageOK = false; $('save-state').textContent = '暂存读取失败；原暂存未覆盖。可导入备份继续。'; }
$('previous').onclick = ()=>show(current-1); $('next').onclick = ()=>show(current+1);
$('case-select').onchange = ()=>show(Number($('case-select').value)); $('variant-select').onchange = variant;
document.querySelectorAll('[data-step]').forEach(e=>e.onclick = ()=>step(e.dataset.step));
form.oninput = e=> { if (e.target.matches('input,textarea')) save(); }; form.onsubmit = e=>e.preventDefault();
$('save-next').onclick = ()=> { if (save()) { if (current < cases.length-1) show(current+1); else $('save-state').textContent += ' 已到最后一张，请导出JSON备份。'; } };
$('ai-advice').ontoggle = ()=> { if ($('ai-advice').open) save(); };
$('export-json').onclick = ()=>download('全景审查问卷备份.json',JSON.stringify(bundle(),null,2),'application/json;charset=utf-8');
$('export-csv').onclick = ()=> {
  const fields = ['case_id','image_id','visibility','scope','human_difference','annotation_assessment','oos_assessment','oos_reason','factors','notes','status','updated_at','ai_advice_opened'];
  const quote = value => { let s = Array.isArray(value) ? value.join('|') : String(value ?? ''); if (/^[=+\-@\t\r]/.test(s)) s = "'"+s; return '"'+s.replaceAll('"','""')+'"'; };
  const rows = [fields,...Object.values(records).map(r=>fields.map(k=>r.answers[k] ?? r[k]))];
  download('全景审查问卷汇总.csv','\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n'),'text/csv;charset=utf-8');
};
$('import-json').onchange = async()=> {
  try {
    const file = $('import-json').files[0]; if (!file) return;
    if (file.size > 20*1024*1024) throw Error('备份文件超过20MB');
    const incoming = validate(JSON.parse(await file.text())), conflicts = Object.keys(incoming).filter(k=>records[k]).length;
    if (conflicts && !confirm(`将覆盖当前 ${conflicts} 张图的暂存答案。建议先取消并导出当前备份。确认覆盖吗？`)) return;
    records = {...records,...incoming}; storageOK = true; persist(); show(current); $('save-state').textContent += ` 已导入 ${Object.keys(incoming).length} 张。`;
  } catch(e) { error('导入失败，当前答案未改动：'+e.message); }
  finally { $('import-json').value = ''; }
};
window.addEventListener('hashchange',()=> { const i = cases.findIndex(c=>'#'+c.case_id === location.hash); if (i >= 0 && i !== current) show(i); });
show(Math.max(0,cases.findIndex(c=>'#'+c.case_id === location.hash)));
