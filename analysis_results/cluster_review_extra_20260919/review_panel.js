// Reuse the atlas's image, people and method controls; decisions never change frozen labels.
window.addEventListener('DOMContentLoaded', () => {
  const evidence = window.EXTRA_CLUSTER_EVIDENCE;
  const key = r => [r.key, r.pair.id_a, r.pair.id_b].join('|');
  const version = 'extra_cluster_review_20260919_v1';
  let decisions = {};
  const panel = document.createElement('section'); panel.className = 'adj';
  panel.innerHTML = `<h2>待你核查：24项重点对照</h2><select id="auditPair"></select>
    <button id="auditPrev">上一项</button><button id="auditNext">下一项</button>
    <p id="auditObservation"></p><p id="auditRelations"></p>
    <p>以下判断针对本项列出的两位人员；可以只写文字。其他人员的问题也可在文字中注明人员编号。</p>
    <label>大致范围 <select id="auditRange"><option value="">未填写</option><option>相近</option><option>不同</option><option>不能判断</option></select></label>
    <label>结构细节 <select id="auditDetail"><option value="">未填写</option><option>相近</option><option>有增减或不同表达</option><option>不能判断</option></select></label>
    <label>点位／对应 <select id="auditPosition"><option value="">未填写</option><option>接近</option><option>有需单独记录的差异</option><option>疑似配对或预处理问题</option><option>不能判断</option></select></label>
    <label><input id="auditDefer" type="checkbox">暂缓</label>
    <p><textarea id="auditNote" rows="4" style="width:98%" placeholder="你的最终意见：哪些差异应保留？如有其他作答问题，请注明人员、方法和位置。"></textarea></p>
    <button id="auditExport">导出我的审核</button><label>导入本页审核 <input id="auditImport" type="file" accept=".json"></label><p id="auditStatus"></p>`;
  document.querySelector('main').prepend(panel);
  const el = id => document.getElementById(id);
  evidence.forEach((r,i) => el('auditPair').add(new Option(`${i+1}. P${r.priority} ${r.code} / ${r.condition} / ${r.pair.worker_a} ↔ ${r.pair.worker_b}`,String(i))));
  const fields = ['Range','Detail','Position','Note'];
  function validate(value) {
    if (value.schema !== version || !value.decisions || Array.isArray(value.decisions) || typeof value.decisions !== 'object') throw Error('不是本页审核文件');
    const allowed = new Set(evidence.map(key));
    for (const [k,r] of Object.entries(value.decisions)) {
      if (!allowed.has(k) || !r || typeof r !== 'object' || fields.some(f=>typeof r[f]!=='string') || typeof r.defer !== 'boolean') throw Error('审核项身份或字段不匹配');
      for (const f of fields.slice(0,3)) if (![...el('audit'+f).options].some(o=>o.value===r[f])) throw Error('审核选项不匹配');
    }
    return value.decisions;
  }
  function persist() {
    try { localStorage.setItem(version,JSON.stringify({schema:version,decisions})); el('auditStatus').textContent='已暂存到本浏览器；完成后请导出JSON。'; }
    catch { el('auditStatus').textContent='浏览器暂存不可用，请导出JSON保存。'; }
  }
  function save() {
    const r = evidence[Number(el('auditPair').value)];
    decisions[key(r)] = Object.fromEntries(fields.map(f=>[f,el('audit'+f).value]));
    decisions[key(r)].defer=el('auditDefer').checked;
    persist();
  }
  async function show() {
    const r=evidence[Number(el('auditPair').value)], d=decisions[key(r)] || {};
    el('auditObservation').textContent='Codex初审（非你的裁决）：'+r.observation;
    el('auditRelations').textContent=Object.entries(r.memberships).filter(([m])=>['A0_legacy','A2_local','A3_cyclic_cut08','A3_cyclic','A4_adaptive'].includes(m)).map(([m,c])=>`${m}：${c[0]===c[1]?'同簇':'异簇'} (${c.join(' / ')})`).join('；');
    fields.forEach(f=>el('audit'+f).value=d[f] || ''); el('auditDefer').checked=!!d.defer;
    const i=dataset.cases.findIndex(c=>c.image_id===r.key.split('|')[0]);
    el('history-mode').value=r.condition==='semi'?'Semi':'Manual';
    await chooseCase(i);
    const c=dataset.cases[i], vi=c.variants.findIndex(v=>v.source.canonical_annotation_id===r.pair.id_a);
    if(vi>=0){el('variant-select').value=vi;chooseVariant(vi,true);}
    const p=c.history.partitions[el('history-mode').value];
    const target=p.method_names.indexOf('A3_cyclic');
    el('history-partition').value=String(target);el('history-partition').dispatchEvent(new Event('change'));
    const checks=[...document.querySelectorAll('#history-clusters input[type=checkbox]')];
    for(const check of checks){const label=check.parentElement.textContent;check.checked=[r.pair.worker_a,r.pair.worker_b].some(w=>new RegExp('W0*'+Number(w.slice(1))+'(?:\\s| ·)').test(label));check.dispatchEvent(new Event('change'));}

  }
  fields.forEach(f=>el('audit'+f).addEventListener('input',save)); el('auditDefer').onchange=save;
  el('auditPair').onchange=show;
  for (const [id,delta] of [['auditPrev',-1],['auditNext',1]]) el(id).onclick=()=>{el('auditPair').selectedIndex=Math.max(0,Math.min(evidence.length-1,el('auditPair').selectedIndex+delta));show();};
  el('auditExport').onclick=()=>{
    const payload={schema:version,exported_at:new Date().toISOString(),decisions,evidence};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='12图分簇_我的审核.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  el('auditImport').onchange=async()=>{
    const file=el('auditImport').files[0]; if(!file)return;
    try {
      const incoming=validate(JSON.parse(await file.text()));
      if(Object.keys(decisions).length && !confirm('导入文件将替换本页当前审核，尚未导出的文字会被替换。继续？'))return;
      decisions=incoming;persist();show();
    } catch(e) { el('auditStatus').textContent='未导入：'+e.message; }
    finally { el('auditImport').value=''; }
  };
  try { const saved=localStorage.getItem(version);if(saved)decisions=validate(JSON.parse(saved)); }
  catch(e) { el('auditStatus').textContent='暂存未读取：'+e.message+'；请用导出文件恢复。'; }
  function sync(){
    const c=dataset.cases[currentCase];
    const oldPanel=el('key39-adjudication');if(oldPanel)oldPanel.hidden=!!c.extra_review;
    const oldDifficulty=el('rv-image')?.closest('section');if(oldDifficulty)oldDifficulty.hidden=!!c.extra_review;
    if(!c.extra_review)return;
    const p=c.history.partitions[el('history-mode').value];
    [...el('history-partition').options].forEach((o,i)=>o.textContent=p.method_names[i]);
    el('history-note').textContent=c.title+' · '+(p.method_names[Number(el('history-partition').value)]||'无该条件结果')+' · 冻结结果，不是语义真值；原图、人员点集与3D复用现有工具。';
  }
  document.addEventListener('studio-case',sync);
  el('history-partition').addEventListener('change',sync);
  el('history-mode').addEventListener('change',sync);
  show();
});
