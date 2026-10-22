(function(root){
'use strict';
const numeric = value => value === null || value === undefined || String(value).trim() === '' ? null : Number.isFinite(Number(value)) ? Number(value) : null;
function normalize(data) {
 if (!data || data.schemaVersion !== 1) throw new Error('不支持的数据合同版本');
 for (const key of ['personnel','members','sameRoom']) if (!Array.isArray(data[key])) throw new Error('缺少数据表：'+key);
 const ids = data.personnel.map(r=>r['条件ID']);
 if (new Set(ids).size !== ids.length || ids.some(id=>!id)) throw new Error('条件ID为空或重复');
 return data;
}
function filterPersonnel(rows, condition, search) {
 const query=String(search||'').toLowerCase();
 return rows.filter(r=>(!condition || r['作答条件']===condition) && Object.values(r).join(' ').toLowerCase().includes(query));
}
function matchingMembers(rows, method, condition, building) {
 if (!method || !condition || !building) return [];
 return rows.filter(r=>r.method===method && r.condition===condition && r.heldout_building===building);
}
const api={numeric,normalize,filterPersonnel,matchingMembers};
if(typeof module!=='undefined' && module.exports) module.exports=api;
else root.ResearchCloseout=api;
})(typeof window!=='undefined'?window:globalThis);
