import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const base = path.resolve(process.argv[2]);
const d = JSON.parse(await fs.readFile(path.join(base, '分配建议与核验.json'), 'utf8'));
assert.equal(d.schema, 'stage1_image_package_proposal_v2');
const out = path.join(base, 'outputs', '01a0852f-dc20-7081-99dd-0413afa69d79');
const qa = path.join(base, '工作簿检查');
await fs.mkdir(out, {recursive:true});
await fs.mkdir(qa, {recursive:true});
const wb = Workbook.create();
const previews = [];
const palette = {navy:'#153F53', teal:'#267C88', pale:'#EDF5F7', text:'#243A45', line:'#D7E3E8'};
const id = w => `W${String(w).padStart(3,'0')}`;
const personSheet = w => w.language === 'zh' ? w.name : id(w.worker_id);
const col = n => {let s=''; for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s; return s;};
const peopleText = a => a.map(id).join('、');
let tableIndex=0;
function sheet(name, title, note, headers, rows, widths) {
  const s=wb.worksheets.add(name), last=col(headers.length-1), end=5+rows.length;
  s.showGridLines=false;
  s.getRange(`A1:${last}${Math.max(end,6)}`).format={font:{name:'Microsoft YaHei',size:10,color:palette.text},rowHeight:23};
  widths.forEach((w,i)=>s.getRange(`${col(i)}1:${col(i)}${end}`).format.columnWidthPx=w);
  s.getRange(`A1:${last}1`).merge();s.getRange('A1').values=[[title]];
  s.getRange(`A1:${last}1`).format={fill:palette.navy,font:{bold:true,size:18,color:'#FFFFFF'},rowHeight:40};
  s.getRange(`A2:${last}3`).merge();s.getRange('A2').values=[[note]];
  s.getRange(`A2:${last}3`).format={fill:palette.pale,wrapText:true,font:{size:10,color:palette.text}};
  s.getRange(`A5:${last}5`).values=[headers];
  s.getRange(`A5:${last}5`).format={fill:palette.teal,font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:34};
  if(rows.length)s.getRange(`A6:${last}${end}`).values=rows;
  headers.forEach((header,i)=>{
    if((header.endsWith('人员') && widths[i]>220) || (name==='来源与口径' && i===1)){
      s.getRange(`${col(i)}6:${col(i)}${end}`).format.wrapText=true;
      s.getRange(`A6:${last}${end}`).format.rowHeight=60;
    }
  });
  s.tables.add(`A5:${last}${end}`,true,`PlanTable${++tableIndex}`);
  s.freezePanes.freezeRows(5);
  previews.push({name,range:`A1:${last}${Math.min(end, name.startsWith('W')?end:19)}`});
  return s;
}
const summary=sheet('总览','第一阶段 · 三个独立项目','中文、英文必做分Project，可使用相同原图；英文自愿另一个Project。包内编号不是线上任务ID，本地已准备，尚未导入或派发。',
 ['项目','人数','每人必做','必做人图','导入图片','用途'],[
 ['任务7',9,20,null,d.projects.find(p=>p.project_key==='zh_required').images,'整房优先，按个人清单'],['Project G',10,30,null,d.projects.find(p=>p.project_key==='en_required').images,'整房优先，按个人清单'],
 ['Project H',10,0,null,20,'12张门洞＋8张同房，自愿完成'],['原H候选未入H',null,null,null,5,'4张同房转必做、1张门洞备选']],[170,90,110,120,110,390]);
summary.getRange('D6:D8').formulas=[['=B6*C6'],['=B7*C7'],['=B8*C8']];
const assignments=sheet('必做人图','480个人 × 图片组合','按整房优先重新分配，替代旧版配对。中文组内轮换后交换2对跨房间位置，英文交换3对，没有强制最小间隔。',
 ['人员','项目','个人顺序','包内编号','图片编号','房间组','预期难度','主要场景','完整图片ID'],
 d.assignments.map(r=>[id(r.worker_id),r.project_key,r.order,r.package_task_code,r.code,r.batch,r.difficulty,r.scene,r.image_id]),[90,135,95,95,200,110,110,170,340]);
const personnel=sheet('人员总表','中文每人20张 · 英文每人必做30张','Project H最终只放20张，每人最多20张，可不做或只做部分，不逐人另派。缺失的实际参与数量不能填写为已完成。',
 ['人员','语言','必做数','额外规划量','历史提交图','仅草稿图','简单','中等','困难'],
 d.workers.map(w=>[id(w.worker_id),w.language,null,w.optional_planning_count,w.submitted_images,w.draft_only_images,w.simple,w.medium,w.hard]),[100,85,105,125,125,115,105,105,105]);
for(let i=0;i<d.workers.length;i++)personnel.getRange(`C${i+6}`).formulas=[[`=COUNTIF('必做人图'!$A$6:$A$485,A${i+6})`]];
for(const w of d.workers){
 sheet(personSheet(w),`${personSheet(w)} · ${w.language==='zh'?'任务7':'Project G'} · 必做${w.required}张`,'管理用个人清单。自愿图在Project H自由选择，不在此表安排。正式任务入口待项目创建后绑定。',
 ['顺序','包内编号','图片编号','房间组','主要场景','预期难度'],
 d.assignments.filter(r=>r.worker_id===w.worker_id).map(r=>[r.order,r.display_task_code,r.code,r.batch,r.scene,r.difficulty]),[85,145,210,110,200,125]);
}
sheet('英文自愿候选池','Project H · 20张入包、5张暂缓或备选','未接触人员是资格核对，不是必做分配。历史提交与当前可用于几何计算的人数分别列出。',
 ['图片编号','房间组','方向','采用状态','历史提交人数','几何计算人数','未接触人数','未接触人员'],
 d.optional_pool.map(r=>[r.code,r.group,r.kind,r.selection_state,r.history_submitted,r.history_manual,r.eligible_workers.length,peopleText(r.eligible_workers)]),[200,110,125,140,115,115,120,460]);
const images=sheet('逐图人数','历史、必做与自愿实际完成分开','历史＋必做是全部必做完成且可用时的计划量。自愿新增尚未发生，不预测为200份。原目标不是硬上限。',
 ['图片编号','房间组','主要场景','历史Manual','必做新增','历史＋必做','原目标','必做后差额','替补候选人数'],
 d.images.map(r=>[r.code,r.group,r.scene,r.history_manual,r.required_new,null,r.user_target,null,r.alternative_workers.length]),[200,120,175,120,115,125,100,125,135]);
for(let i=0;i<d.images.length;i++){
 const n=i+6;images.getRange(`F${n}`).formulas=[[`=D${n}+E${n}`]];
 images.getRange(`H${n}`).formulas=[[`=IF(G${n}="","",MAX(0,G${n}-F${n}))`]];
}
sheet('房间覆盖','19个已采用房间组的视角覆盖','达到8人仅描述人数，不是统一的收敛门槛。每组实际收敛状态仍需新标注回来后判断。',
 ['房间组','已采用图','历史Manual','必做新增','计划合计','有标注视角','至少8人视角'],
 d.rooms.map(r=>[r.group,r.adopted_images,r.history_manual,r.required_new,r.manual_after_required,r.views_with_manual,r.views_at_least8]),[125,125,135,125,125,155,160]);
sheet('研究与后续分析','人员分类与AABC组合仍是研究主线','分类方案暂不决定；新增结果齐备后汇总各方案的人数、名单、含义、重复性及组内稳定性。',
 ['项目','执行口径'],[
 ['路线一','质量、时间、范围规则判断、Semi表现分别探索粗类；不预设认真／粗心标签。'],
 ['路线二','四块信息15种非空组合，探索不同组数；另保留质量＋时间＋修改幅度三轴方案。'],
 ['AABC','两个A是同类型的两个不同人；按同图实际存在的独立标注组合，人数不够时记不可组合。'],
 ['验证隔离','先用别的房间资料分类，再检查目标房间的人员子类和组合；不根据目标收敛结果调整分类。'],
 ['旧结果','旧26人／20人结果保留原人数，不能改称本轮19人结果。W11保留历史，W19和W26不进本轮主分析。'],
 ['后续报告','先说明单项与联合两条方案的优缺点，再列每组人数和客观证据；分类和研究结论尚未确定。'],
 ['图片预测','同房不同视角、相似场景不同房间并行；同building为对照。收齐后离线多次划分与重排。'],
 ['表单','新Manual只收几何与Scope；不收集的字段不当成漏填，历史语义保留。'],
 ['自愿结果','最多10人各20张，共200人图可能量；按实际人图去重统计；自愿参与不能自动代表全体人员。'],
 ['采集限制','Project H定稿20张：12张门洞、8张同房。历史做过者不能再作为新增独立标注；选做不保证房间补齐。'],
 ['真源','采用依据与原文分存；import_json下三个任务文件及必做manifest是新项目准备数据。'],
 ['运行状态','Project ID和线上任务ID尚未绑定；图片URL来自仓库，尚未在线逐一检查。']],[175,940]);
for(let i=0;i<d.workers.length;i++)assert.equal(personnel.getRange(`C${i+6}`).values[0][0],d.workers[i].required);
assert.deepEqual(summary.getRange('D6:D8').values,[[180],[300],[0]]);
assert.equal(assignments.getUsedRange().values.length,485);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:30},summary:'formula errors'});
await fs.writeFile(path.join(qa,'公式扫描.json'),JSON.stringify(errors));
for(const p of previews){
 const im=await wb.render({sheetName:p.name,range:p.range,scale:1,format:'png'});
 await fs.writeFile(path.join(qa,`${p.name}.png`),new Uint8Array(await im.arrayBuffer()));
}
const target=path.join(out,'第一阶段三项目分配与研究安排.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(target);
const reopened=await SpreadsheetFile.importXlsx(await FileBlob.load(target));
assert.deepEqual(reopened.worksheets.getItem('总览').getRange('D6:D8').values,[[180],[300],[0]]);
assert.equal(reopened.worksheets.getItem('必做人图').getUsedRange().values.length,485);
await fs.writeFile(path.join(qa,'工作簿核验.json'),JSON.stringify({sheets:previews.length,required:480,optionalAssigned:0,reopened:true},null,2));
// 与既有分发表一致：中文一份工作簿收齐9人，英文各自独立文件。
for(const group of [d.workers.filter(w=>w.language==='zh'), ...d.workers.filter(w=>w.language==='en').map(w=>[w])]){
 const delivery=Workbook.create(), english=group[0].language==='en';
 for(const w of group){
  const rr=d.assignments.filter(r=>r.worker_id===w.worker_id), s=delivery.worksheets.add(personSheet(w));
  s.showGridLines=false;s.getRange(`A1:C${rr.length+5}`).format={font:{name:'Microsoft YaHei',size:11},rowHeight:25,columnWidthPx:150};
  s.getRange(`C1:C${rr.length+5}`).format.columnWidthPx=280;
  s.getRange('A1:C1').merge();s.getRange('A1').values=[[`${english?'Project G':'任务7'} · ${personSheet(w)} · ${rr.length} ${english?'required images':'张必做图'}`]];
  s.getRange('A1:C1').format={fill:palette.navy,font:{bold:true,color:'#FFFFFF',size:17},rowHeight:40};
  s.getRange('A2:C3').merge();s.getRange('A2').values=[[english?'Complete Project G in the listed order. Project H is optional. Codes are package labels; live task links pending.':'按本页顺序完成任务7。中文9人清单汇集在这一个文件内，请打开自己姓名的sheet。包内编号待与线上任务绑定。']];
  s.getRange('A2:C3').format={wrapText:true,fill:palette.pale};
  s.getRange('A5:C5').values=[english?['Order','Package code','Image code']:['个人顺序','包内编号','图片编号']];
  s.getRange('A5:C5').format={fill:palette.teal,font:{bold:true,color:'#FFFFFF'}};
  s.getRange(`A6:C${rr.length+5}`).values=rr.map(r=>[r.order,r.display_task_code,r.code]);
  s.freezePanes.freezeRows(5);
 }
 const file=path.join(base,english?'英文必做包':'中文必做包',english?`Project_G_${id(group[0].worker_id)}.xlsx`:'任务7.xlsx');
 await (await SpreadsheetFile.exportXlsx(delivery)).save(file);
 const check=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
 for(const w of group)assert.equal(check.worksheets.getItem(personSheet(w)).getUsedRange().values.length,w.required+5);
 if(!english || group[0].worker_id===28){
  const im=await delivery.render({sheetName:personSheet(group[0]),range:`A1:C${group[0].required+5}`,scale:1,format:'png'});
  await fs.writeFile(path.join(qa,english?'英文个人分发表.png':'中文汇总分发表.png'),new Uint8Array(await im.arrayBuffer()));
 }
}
const hFolder=path.join(base,'英文选做包');
await fs.mkdir(hFolder,{recursive:true});
for(const w of d.workers.filter(w=>w.language==='en')){
 const optional=Workbook.create(), s=optional.worksheets.add(id(w.worker_id));
 const rr=d.optional_pool.filter(r=>r.ready_for_import).sort((a,b)=>a.package_task_code.localeCompare(b.package_task_code));
 s.getRange('A1:C25').format={font:{name:'Arial',size:11},rowHeight:25,columnWidthPx:210};
 s.getRange('A1:C1').merge();s.getRange('A1').values=[[`Project H · ${id(w.worker_id)} · Optional`]];
 s.getRange('A1:C1').format={fill:palette.navy,font:{bold:true,color:'#FFFFFF',size:17},rowHeight:40};
 s.getRange('A2:C3').merge();s.getRange('A2').values=[['Choose any eligible images, up to 20. You may complete none or only some. Skip images marked Already seen. Project links will be supplied after setup.']];
 s.getRange('A2:C3').format={wrapText:true,fill:palette.pale};
 s.getRange('A5:C5').values=[['Package code','Image code','Availability']];
 s.getRange('A5:C5').format={fill:palette.teal,font:{bold:true,color:'#FFFFFF'}};
 s.getRange('A6:C25').values=rr.map(r=>[r.display_task_code,r.code,r.eligible_workers.includes(w.worker_id)?'Optional':'Already seen — skip']);
 s.freezePanes.freezeRows(5);
 const file=path.join(hFolder,`Project_H_${id(w.worker_id)}.xlsx`);
 await (await SpreadsheetFile.exportXlsx(optional)).save(file);
 const check=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
 assert.deepEqual(check.worksheets.getItem(id(w.worker_id)).getRange('A6:C25').values,s.getRange('A6:C25').values);
 if(w.worker_id===34){const im=await optional.render({sheetName:id(w.worker_id),range:'A1:C25',scale:1,format:'png'});await fs.writeFile(path.join(qa,'英文选做分发表.png'),new Uint8Array(await im.arrayBuffer()));}
}
console.log(target);
