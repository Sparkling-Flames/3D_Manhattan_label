/* Standalone review receipts. Answers, pairs and navigation are separate. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.ReviewReceipt30 = api; const start = () => api.mount(root.document, () => root.localStorage); if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start); else start(); }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const VERSION = 'quality_review30_receipt_v1', MAX_FILE_BYTES = 1024*1024, MAX_FIELD_LENGTH = 2000;
  const clone = x => JSON.parse(JSON.stringify(x)), equal = (a,b) => JSON.stringify(a) === JSON.stringify(b);
  const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  const keysEqual = (x,ks) => object(x) && equal(Object.keys(x).sort(), [...ks].sort());
  function parseCSV(text) {
    const input=text.replace(/^\uFEFF/,''), rows=[]; let row=[],cell='',state='plain';
    const endCell=()=>{row.push(cell);cell='';state='plain';}; const endRow=()=>{endCell();rows.push(row);row=[];};
    for(let i=0;i<input.length;i++){const c=input[i];if(state==='quoted'){if(c==='"'&&input[i+1]==='"'){cell+='"';i++;}else if(c==='"')state='closed';else cell+=c;}else if(c===','||c==='\r'||c==='\n'){if(c===',')endCell();else{endRow();if(c==='\r'&&input[i+1]==='\n')i++;}}else if(state==='closed')throw Error('CSV引号后的格式无效。');else if(c==='"'){if(cell.length)throw Error('CSV引号格式无效。');state='quoted';}else cell+=c;}
    if(state==='quoted')throw Error('CSV引号未闭合。');if(row.length||cell.length||state==='closed')endRow();return rows;
  }
  function createController(schema,getStorage) {
    const ids=schema.rows.map(r=>r.case_id), pairIds=schema.pair_rows.map(r=>r.pair_id);
    const storageKey=VERSION+':'+schema.dataset_id, positionKey=storageKey+':position';
    let answers=clone(schema.rows),pairs=clone(schema.pair_rows),persistence='empty',storageError='';
    function receipt(){return {format_version:VERSION,dataset_id:schema.dataset_id,case_ids:[...ids],display_order:[...schema.display_order],fields:[...schema.fields],answers:clone(answers),pair_ids:[...pairIds],pair_fields:[...schema.pair_fields],pair_answers:clone(pairs)};}
    function validateRows(input,blank,fields,idField,active,fixedFields){
      if(!Array.isArray(input)||input.length!==blank.length)throw Error('回答数与本清单不匹配。');const originals=new Map(blank.map(r=>[r[idField],r])),accepted=new Map();
      for(const row of input){if(!keysEqual(row,fields))throw Error('回答缺少字段或含额外字段。');const id=row[idField];if(!originals.has(id)||accepted.has(id))throw Error('ID非法或重复。');
        for(const field of fields){if(typeof row[field]!=='string'||row[field].length>MAX_FIELD_LENGTH)throw Error('回答类型或长度无效（每字段最多2000字）。');if(fixedFields.includes(field)){if(row[field]!==originals.get(id)[field])throw Error('案例或配对身份字段不匹配。');continue;}if(!active[id].includes(field)&&row[field]!=='')throw Error('含不适用回答。');const opts=schema.options[field];if(opts&&row[field]!==''&&!opts.includes(row[field]))throw Error('选择项不匹配。');}accepted.set(id,Object.fromEntries(fields.map(f=>[f,row[f]])));}
      return blank.map(r=>accepted.get(r[idField]));
    }
    function validate(value){
      const keys=['format_version','dataset_id','case_ids','display_order','fields','answers','pair_ids','pair_fields','pair_answers'];
      if(!keysEqual(value,keys)||value.format_version!==VERSION||value.dataset_id!==schema.dataset_id)throw Error('回执版本或数据清单不匹配。旧8例回执不能导入本页。');
      if(!equal(value.case_ids,ids)||!equal(value.display_order,schema.display_order)||!equal(value.fields,schema.fields)||!equal(value.pair_ids,pairIds)||!equal(value.pair_fields,schema.pair_fields))throw Error('案例/展示顺序/成对题/字段清单不匹配。');
      // Validate both tables fully before either is assigned.
      return {answers:validateRows(value.answers,schema.rows,schema.fields,'case_id',schema.active_fields,['case_id','case_type']),pairs:validateRows(value.pair_answers,schema.pair_rows,schema.pair_fields,'pair_id',schema.pair_active_fields,['pair_id','left_case_id','right_case_id'])};
    }
    function unavailable(){persistence='unavailable';storageError='本地草稿不可用：必须下载回执；关闭或刷新前请先下载。';}
    function persist(){if(persistence==='unavailable')return false;try{getStorage().setItem(storageKey,JSON.stringify(receipt()));persistence='saved';storageError='';return true;}catch(e){unavailable();return false;}}
    function apply(value,saveDraft=true){const checked=validate(value);answers=checked.answers;pairs=checked.pairs;if(saveDraft)persist();return receipt();}
    function checkText(text){if(typeof text!=='string'||new TextEncoder().encode(text).length>MAX_FILE_BYTES)throw Error('文件超过1 MiB或内容无效。');}
    function importJSON(text){checkText(text);return apply(JSON.parse(text));}
    function toCSV(){const lines=[['#format_version',VERSION],['#dataset_id',schema.dataset_id],['#display_order',...schema.display_order],['#case_fields',...schema.fields],...answers.map(r=>schema.fields.map(f=>r[f])),['#pair_fields',...schema.pair_fields],...pairs.map(r=>schema.pair_fields.map(f=>r[f]))];return '\uFEFF'+lines.map(r=>r.map(x=>'"'+x.replace(/"/g,'""')+'"').join(',')).join('\r\n')+'\r\n';}
    function importCSV(text){checkText(text);const rows=parseCSV(text),pairHeader=4+ids.length;if(rows.length!==5+ids.length+pairIds.length||!equal(rows[0],['#format_version',VERSION])||!equal(rows[1],['#dataset_id',schema.dataset_id])||!equal(rows[2],['#display_order',...schema.display_order])||!equal(rows[3],['#case_fields',...schema.fields])||!equal(rows[pairHeader],['#pair_fields',...schema.pair_fields]))throw Error('CSV版本、清单或字段不匹配。');const decode=(r,fields)=>{if(r.length!==fields.length)throw Error('CSV字段数不匹配。');return Object.fromEntries(fields.map((f,i)=>[f,r[i]]));};const value=receipt();value.answers=rows.slice(4,pairHeader).map(r=>decode(r,schema.fields));value.pair_answers=rows.slice(pairHeader+1).map(r=>decode(r,schema.pair_fields));return apply(value);}
    function load(){let text;try{text=getStorage().getItem(storageKey);}catch(e){unavailable();return false;}if(text===null)return false;try{checkText(text);const checked=validate(JSON.parse(text));answers=checked.answers;pairs=checked.pairs;persistence='restored';return true;}catch(e){persistence='invalid';storageError='发现不匹配草稿，未恢复；请从已下载回执继续。';return false;}}
    function update(kind,id,field,value){const next=receipt(),pair=kind==='pair',rows=pair?next.pair_answers:next.answers,allowed=pair?schema.pair_active_fields:schema.active_fields,row=rows.find(r=>r[pair?'pair_id':'case_id']===id);if(!row||!allowed[id].includes(field))throw Error('案例或字段不匹配。');row[field]=value;return apply(next);}
    function decision(r){return r.case_type==='quality'?r.absolute_quality:r.space_compatibility;}
    function progress(){return {complete:answers.filter(r=>decision(r)!=='').length,partial:answers.filter(r=>decision(r)===''&&schema.active_fields[r.case_id].some(f=>r[f]!=='')).length,total:ids.length,pair_complete:pairs.filter(r=>r.preference!=='').length};}
    function firstIncomplete(){const map=new Map(answers.map(r=>[r.case_id,r]));return schema.display_order.find(id=>decision(map.get(id))==='')||schema.display_order[schema.display_order.length-1];}
    function rowState(id){const row=answers.find(r=>r.case_id===id);return decision(row)!==''?'已回答':schema.active_fields[id].some(f=>row[f]!=='')?'部分填写':'未填写';}
    function savePosition(id){if(!ids.includes(id)&&!pairIds.includes(id))return;try{getStorage().setItem(positionKey,id);}catch(e){unavailable();}}
    function loadPosition(){try{const id=getStorage().getItem(positionKey);return ids.includes(id)||pairIds.includes(id)?id:schema.display_order[0];}catch(e){unavailable();return schema.display_order[0];}}
    return {receipt,validate,apply,load,update,importJSON,importCSV,toCSV,toJSON:()=>JSON.stringify(receipt(),null,2)+'\n',progress,firstIncomplete,rowState,savePosition,loadPosition,storageKey,positionKey,status:()=>({persistence,error:storageError})};
  }
  function mount(document,getStorage){
    const schema=JSON.parse(document.getElementById('receipt-schema').textContent),ctl=createController(schema,getStorage),controls=[...document.querySelectorAll('[data-row-id][data-field]')],draft=document.getElementById('draft-status'),status=document.getElementById('receipt-status');let current=schema.display_order[0];
    function showDraft(){const s=ctl.status(),labels={empty:'本地草稿：尚无草稿。',saved:'本地草稿：已写入本浏览器。',restored:'本地草稿：已恢复本浏览器回答。',invalid:s.error,unavailable:s.error};draft.textContent=labels[s.persistence]+' 浏览器草稿不保证持久；请下载回执备份。';draft.dataset.state=s.persistence;}
    function progress(){const p=ctl.progress();document.getElementById('primary-progress').textContent=`已回答 ${p.complete} / ${p.total} 份；部分填写 ${p.partial} 份（空白/仅查看不计完成）`;document.getElementById('pair-progress').textContent=`可选成对题：${p.pair_complete} / ${schema.pair_rows.length}（不计入30份）`;document.querySelectorAll('[data-go-case]').forEach(b=>{b.dataset.state=ctl.rowState(b.dataset.goCase);b.textContent=b.dataset.goCase+' · '+b.dataset.state;});}
    function fill(){const val=ctl.receipt(),rows=new Map([...val.answers.map(r=>[r.case_id,r]),...val.pair_answers.map(r=>[r.pair_id,r])]);controls.forEach(el=>{el.value=rows.get(el.dataset.rowId)[el.dataset.field];});progress();}
    function locate(id,save=true){current=id;document.querySelectorAll('[data-panel-id]').forEach(p=>{p.hidden=p.dataset.panelId!==id;});const index=schema.display_order.indexOf(id);document.getElementById('current-position').textContent=index>=0?`当前第 ${index+1} 份 / 共 30 份 · 题号 ${id}`:'可选成对题 P01（独立于30份作答）';document.getElementById('prev-case').disabled=index<=0;document.getElementById('next-case').disabled=index<0||index===schema.display_order.length-1;document.querySelectorAll('[data-go-case]').forEach(b=>b.setAttribute('aria-current',b.dataset.goCase===id?'true':'false'));if(save)ctl.savePosition(id);showDraft();}
    function collect(){const v=ctl.receipt(),rows=new Map([...v.answers.map(r=>[r.case_id,r]),...v.pair_answers.map(r=>[r.pair_id,r])]);controls.forEach(el=>{rows.get(el.dataset.rowId)[el.dataset.field]=el.value;});ctl.apply(v);showDraft();progress();}
    function download(kind){try{collect();const text=kind==='json'?ctl.toJSON():ctl.toCSV(),url=URL.createObjectURL(new Blob([text],{type:kind==='json'?'application/json;charset=utf-8':'text/csv;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download='quality_review30_receipt.'+kind;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);status.textContent='已请求下载'+kind.toUpperCase()+'回执；请确认文件已保存。';}catch(e){status.textContent='无法导出：'+e.message;}}
    ctl.load();fill();locate(ctl.loadPosition(),false);
    controls.forEach(el=>el.addEventListener(el.tagName==='SELECT'?'change':'input',()=>{try{ctl.update(el.dataset.kind,el.dataset.rowId,el.dataset.field,el.value);showDraft();progress();}catch(e){status.textContent='回答未写入：'+e.message;}}));
    document.querySelectorAll('[data-go-case]').forEach(b=>b.addEventListener('click',()=>locate(b.dataset.goCase)));
    document.getElementById('go-pair').addEventListener('click',()=>locate('P01'));
    document.getElementById('prev-case').addEventListener('click',()=>locate(schema.display_order[schema.display_order.indexOf(current)-1]));document.getElementById('next-case').addEventListener('click',()=>locate(schema.display_order[schema.display_order.indexOf(current)+1]));
    document.getElementById('download-json').addEventListener('click',()=>download('json'));document.getElementById('download-csv').addEventListener('click',()=>download('csv'));
    document.getElementById('import-receipt').addEventListener('change',async ev=>{const file=ev.target.files[0];if(!file)return;try{if(file.size>MAX_FILE_BYTES)throw Error('文件超过1 MiB。');const text=await file.text();if(/\.json$/i.test(file.name))ctl.importJSON(text);else if(/\.csv$/i.test(file.name))ctl.importCSV(text);else throw Error('请选择本页下载的JSON或CSV。');fill();locate(ctl.firstIncomplete());status.textContent='已导入30份回答和独立可选成对题；定位到展示顺序中第一份未回答题（全答时定位末题）。';}catch(e){status.textContent='导入被拒绝，现有回答保持不变：'+e.message;}finally{ev.target.value='';}});
    return ctl;
  }
  return {VERSION,MAX_FILE_BYTES,MAX_FIELD_LENGTH,parseCSV,createController,mount};
});
