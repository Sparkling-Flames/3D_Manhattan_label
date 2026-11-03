'use strict';
(() => {
  const schema = 'missing_ring_order_review_20261104_v1';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = '一键导出全部图片的排序记录';
  button.style.cssText = 'font:inherit;padding:10px 16px;margin:12px 12px 12px 0;cursor:pointer';
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  const container = document.createElement('p');
  container.append(button, status);
  document.querySelector('table').before(container);

  async function loadPageData(path) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = path.replace(/\.html$/, '.js');
      script.onload = () => {
        const data = window.STUDIO_DATA;
        script.remove();
        resolve(data);
      };
      script.onerror = () => { script.remove(); reject(new Error(`无法读取案例数据：${path}`)); };
      document.head.append(script);
    });
  }

  async function buildExport() {
    const paths = [...document.querySelectorAll('a[href^="pages/"]')].map(a => a.getAttribute('href'));
    if (!paths.length) throw new Error('没有找到当前复核页面');
    const snapshots = paths.map(path => ({path, key: schema + ':' + new URL(path, location.href).pathname}));
    for (const page of snapshots) page.text = localStorage.getItem(page.key);
    const records = {}, objects = {};
    let reviewedPages = 0;
    for (const page of snapshots) {
      const data = await loadPageData(page.path);
      if (!data || data.manifest?.export_schema !== schema || !Array.isArray(data.cases)) throw new Error(`案例数据版本不匹配：${page.path}`);
      const sources = new Map();
      for (const c of data.cases) {
        const s = c.variants?.[0]?.source;
        if (!s || s.object_kind !== 'fusion' || !s.object_id?.startsWith('missing_ring:') || objects[s.object_id]) throw new Error(`案例身份缺失或重复：${page.path}`);
        sources.set(s.object_id, s);
        objects[s.object_id] = {...s.review_metadata, feature_ids:s.feature_ids, node_supports:s.node_supports};
      }
      if (page.text === null) continue;
      reviewedPages++;
      let saved;
      try { saved = JSON.parse(page.text); } catch (_) { throw new Error(`本地记录无法解析：${page.path}`); }
      if (!saved || typeof saved !== 'object' || Array.isArray(saved)) throw new Error(`本地记录格式错误：${page.path}`);
      for (const [id, record] of Object.entries(saved)) {
        const s = sources.get(id);
        if (!s || records[id]) throw new Error(`记录身份不匹配或重复：${page.path}；请先逐页导出备份`);
        const binding = JSON.stringify({id:s.object_id, points:s.effective_points || s.points, labels:s.effective_point_labels, links:s.links_zero_based, ...(s.preprocessing ? {preprocessing:s.preprocessing} : {})});
        const n = s.links_zero_based.length;
        if (!record || record.binding !== binding || !['draft','confirmed','pending','pairing'].includes(record.status) || !Array.isArray(record.order) || record.order.length !== n || [...record.order].sort((a,b) => a-b).some((v,i) => v !== i)) throw new Error(`记录与当前案例不匹配：${page.path}；请先逐页导出备份`);
        records[id] = record;
      }
    }
    if (snapshots.some(page => localStorage.getItem(page.key) !== page.text)) throw new Error('导出期间记录发生变化，请重新导出');
    const counts = {confirmed:0, pairing:0, pending:0, draft:0};
    for (const r of Object.values(records)) counts[r.status]++;
    return {schema, examples_only:false, records, objects, formal_results_modified:false, aggregate:true,
      summary:{pages:snapshots.length, pages_with_records:reviewedPages, cases:Object.keys(objects).length, ...counts}};
  }
  window.buildMissingRingExport = buildExport;
  button.onclick = async () => {
    button.disabled = true;
    status.textContent = '正在汇总并核对本浏览器的记录…';
    try {
      const doc = await buildExport();
      if (!Object.keys(doc.records).length) throw new Error('本浏览器没有找到已保存记录；请在完成排序的同一浏览器中打开此页');
      const url = URL.createObjectURL(new Blob([JSON.stringify(doc, null, 2)], {type:'application/json'}));
      const a = document.createElement('a'); a.href = url; a.download = '融合节点排序_全部图片.json'; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      const s = doc.summary;
      status.textContent = `已导出 ${s.pages_with_records}/${s.pages} 页：已采用 ${s.confirmed}，节点问题 ${s.pairing}，待判断 ${s.pending}，草稿 ${s.draft}；共 ${s.cases} 个案例。`;
    } catch (err) { status.textContent = '未导出：' + err.message; }
    finally { button.disabled = false; }
  };
})();
