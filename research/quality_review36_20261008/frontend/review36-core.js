(function (root) {
  'use strict';
  const SCHEMA = 'panorama-review36-ratings-v1';
  const BATCH = 'quality-review36-20261008-v1';
  const STORAGE = 'quality-review36-v1';
  function validScore(x) { return Number.isInteger(x) && x >= 1 && x <= 5; }
  function progress(ratings, records) {
    const rs = records.map(r => ratings[r.reviewId]).filter(Boolean);
    const rated = rs.filter(r => r.status === 'rated' && validScore(r.overallScore)).length;
    const unable = rs.filter(r => r.status === 'unable').length;
    return { total: records.length, rated, unable, handled: rated + unable };
  }
  function makeExport(ratings, context) {
    return { schema: SCHEMA, batchId: BATCH, exportedAt: new Date().toISOString(),
      dataSnapshot: context.dataSnapshot, rubricVersion: 'overall-five-level-pilot-v1',
      storageNotice: 'Browser-local ratings; export is not an automatic GitHub sync.',
      ratings: context.records.filter(r => ratings[r.reviewId]).map(r => ratings[r.reviewId]) };
  }
  function validateImport(payload, records, expectedFingerprint) {
    if (payload.schema !== SCHEMA || payload.batchId !== BATCH || !Array.isArray(payload.ratings)) {
      throw new Error('这不是本轮36份评分的JSON文件；旧版两两意见请在历史界面查看');
    }
    if (expectedFingerprint && payload.dataSnapshot !== expectedFingerprint) throw new Error('文件对应的数据快照与本轮不一致');
    const byId = new Map(records.map(r => [r.reviewId, r]));
    const seen = new Set();
    for (const r of payload.ratings) {
      const source = byId.get(r.reviewId);
      if (!source || source.id !== r.recordId || source.imageCode !== r.imageCode || seen.has(r.reviewId)) {
        throw new Error('文件中的作答身份与本轮清单不一致');
      }
      if (!['draft', 'rated', 'unable'].includes(r.status) ||
          (r.status === 'rated' && !validScore(r.overallScore)) ||
          (r.status !== 'rated' && r.overallScore !== null)) throw new Error('评分状态或分值不正确');
      if (typeof r.scopeNote !== 'string' || typeof r.geometryNote !== 'string' ||
          !Array.isArray(r.tags) || r.tags.some(x => typeof x !== 'string') ||
          !Number.isFinite(Date.parse(r.updatedAt))) throw new Error('意见字段或时间格式不正确');
      const versions = source.referenceVersions || ['original', 'manual_revision'];
      if (!versions.includes(r.referenceVersion) || typeof r.gtVisible !== 'boolean' || typeof r.metricsSeen !== 'boolean' ||
          !Array.isArray(r.referencesSeen) || r.referencesSeen.some(v => !versions.includes(v)) ||
          !Array.isArray(r.comparedRecordIds) || r.comparedRecordIds.some(id => !records.some(x => x.id === id && x.imageCode === r.imageCode))) {
        throw new Error('参考版本或查看记录与本轮数据不一致');
      }
      seen.add(r.reviewId);
    }
    return payload.ratings;
  }
  function mergeRatings(current, incoming) {
    const merged = { ...current };
    for (const r of incoming) {
      if (!merged[r.reviewId] || Date.parse(r.updatedAt) > Date.parse(merged[r.reviewId].updatedAt)) merged[r.reviewId] = r;
    }
    return merged;
  }
  function csvCell(x) {
    let s = x == null ? '' : String(x);
    if (/^[=+@\t\r]/.test(s) || /^-\D/.test(s)) s = "'" + s;
    return '"' + s.replace(/"/g, '""') + '"';
  }
  function toCSV(ratings, records) {
    const keys = ['reviewId','recordId','imageCode','status','overallScore','scopeNote','geometryNote','tags','referenceVersion','gtVisible','metricsSeen','referencesSeen','comparedRecordIds','updatedAt'];
    const rows = records.map(r => ({ reviewId:r.reviewId,recordId:r.id,imageCode:r.imageCode,
      status:'unreviewed',overallScore:null, ...(ratings[r.reviewId] || {}) }));
    return '\ufeff' + [keys.map(csvCell).join(','), ...rows.map(r => keys.map(k => csvCell(Array.isArray(r[k]) ? r[k].join('|') : r[k])).join(','))].join('\r\n');
  }
  const api = { SCHEMA, BATCH, STORAGE, validScore, progress, makeExport, validateImport, mergeRatings, toCSV };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Review36Core = api;
})(typeof window !== 'undefined' ? window : globalThis);
