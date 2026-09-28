import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const root=path.resolve(process.argv[2]);
const folder=path.join(root,'import_json/cn_first10_20260922');
const data=JSON.parse(await fs.readFile(path.join(folder,'workbook_input.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'analysis_results/stage1_person_image_packages_20260913_v2/中文必做包/任务7.xlsx')));
const qa=path.join(folder,'预览检查');
await fs.mkdir(qa,{recursive:true});
for(const w of data.workers){
  const s=wb.worksheets.getItem(w.name);
  const rows=data.assignments.filter(r=>r.worker_id===w.worker_id).sort((a,b)=>a.order-b.order);
  assert.equal(rows.length,10);
  s.getRange('A1').values=[[`任务8 · ${w.name} · 10张必做图`]];
  s.getRange('A2').values=[['按本页顺序完成任务8。请打开自己姓名的sheet，仅做所列10张。包内编号不是线上任务ID，项目入口由负责人提供。']];
  s.getRange('A6:C25').values=Array.from({length:20},()=>[null,null,null]);
  s.getRange('A6:C15').values=rows.map(r=>[r.order,r.display_task_code,r.code]);
  assert.deepEqual(s.getRange('A5:C5').values,[['个人顺序','包内编号','图片编号']]);
  const image=await wb.render({sheetName:w.name,range:'A1:C15',scale:1,format:'png'});
  await fs.writeFile(path.join(qa,`W${String(w.worker_id).padStart(3,'0')}.png`),new Uint8Array(await image.arrayBuffer()));
}
const target=path.join(folder,'任务8.xlsx');
await(await SpreadsheetFile.exportXlsx(wb)).save(target);
const check=await SpreadsheetFile.importXlsx(await FileBlob.load(target));
for(const w of data.workers){
  const expected=data.assignments.filter(r=>r.worker_id===w.worker_id).sort((a,b)=>a.order-b.order).map(r=>[r.order,r.display_task_code,r.code]);
  assert.deepEqual(check.worksheets.getItem(w.name).getRange('A6:C15').values,expected);
  assert.ok(check.worksheets.getItem(w.name).getRange('A16:C25').values.flat().every(x=>x==null||x===''));
}
console.log(JSON.stringify({file:target,sheets:9,assignments:90,reopened:true}));
