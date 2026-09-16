import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const out='D:/Work/HOHONET/analysis_results/full_history_coverage_20260916';
const d=JSON.parse(await fs.readFile(`${out}/全历史覆盖机器表.json`,'utf8'));
const wb=Workbook.create();
const cell=v=>v===undefined?null:typeof v==='object'&&v!==null?JSON.stringify(v):v;
const col=n=>{let t='';for(n++;n;n=Math.floor((n-1)/26))t=String.fromCharCode(65+(n-1)%26)+t;return t;};
const definitions=[];
function sheet(name,headers,rows,widths=[]) {
 const s=wb.worksheets.add(name);s.showGridLines=false;
 const values=[headers,...rows.map(r=>r.map(cell))];
 const last=col(headers.length-1);s.getRange(`A1:${last}${values.length}`).values=values;
 s.getRange(`A1:${last}${values.length}`).format.rowHeight=25;
 s.getRange(`A1:${last}${values.length}`).format.font.size=11;
 s.getRange(`A1:${last}1`).format={fill:'#173E54',font:{bold:true,color:'#FFFFFF'},rowHeight:38,wrapText:true};
 for(let i=0;i<headers.length;i++)s.getRange(`${col(i)}1:${col(i)}${values.length}`).format.columnWidth=widths[i]??18;
 s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(Math.min(2,headers.length));
 if(rows.length)s.tables.add(`A1:${last}${values.length}`,true,`Table${definitions.length+1}`);
 definitions.push({name,rows:rows.length,cols:headers.length});return s;
}
sheet('阅读说明',['项目','内容'],[
 ['状态','研究准备方案；未导入、未派发；11张共同历史图待复核'],
 ['新人编号','真实worker_id全部留空。新人安排01–15仅为临时安排位置。'],
 ['全部历史','26人身份保留；主计数排除W019/W026，W011历史保留。'],
 ['拟新增',`${d.stats.proposed_pairs}份／${d.stats.proposed_images}图；新人750份＋旧中文172份`],
 ['人员安排','15名新人每人50张；旧中文8人20张、1人12张；不强凑数量。'],
 ['前提','592份补缺以原480份必做全部有效完成为条件；实际导出待更新。'],
 ['共同历史','22张×15人＝330份。11张已采用，11张待本次复核。'],
 ['预测覆盖','已采用19组100张Manual；另2张仅历史Semi。全部历史计入各表。'],
 ['全量预计',`Manual ${d.stats.expected_manual_images}图／${d.stats.expected_pairs}人图；至少8人${d.stats.expected_ge8}图`],
 ['耗时',`约${d.stats.total_estimated_hours.toFixed(1)}操作人时，不含培训、休息、返工。`],
 ['低人数结论','真实观察内共识＋15人以上仍稳定的待验证预测，不补造人数。'],
 ['10月复核','同时抽查已共识图和分歧图，预测在新结果出现前冻结。'],
 ['分类与检验','使用其他房间建立人员画像；目标房间不参与该次人员分类。'],
 ['重要限制','G047/G237无全视角共同人员；逐对交集见同房配对页。'],
 ['来源','同房registry、原用户采用表、原480份分配、历史计算视图与24份导出。'],
 ['表格用途','管理审阅快照；修改Excel不自动改写机器表或原始决定。']
],[22,100]);
const imgHeaders=['图片','同房组','场景','预期难度','历史Manual人数','历史Semi人数','原必做待核实','原目标人数','本次拟新增','预期合计','原必做全完成后缺口','不计原必做时缺口','优先级','共同历史','复核状态','OOS记录','选择理由','image_id','图片路径'];
const imageRow=r=>[r.code,r.room||r.supported_rooms.join('/'),r.scene,r.difficulty,r.history_manual,r.history_semi,r.planned,r.target,r.new_proposed,null,null,null,r.priority,r.core?'是':'否',r.review,r.oos,r.reason,r.image_id,r.image_path];
for(const [name,rows] of [['拟选图片',d.images.filter(r=>r.new_proposed)],['全648图库存',d.images]]) {
 const s=sheet(name,imgHeaders,rows.map(imageRow),[24,20,19,14,15,15,17,15,15,15,20,20,16,14,38,28,62,55,70]);
 for(let i=2;i<=rows.length+1;i++)s.getRange(`J${i}:L${i}`).formulas=[[`=E${i}+G${i}+I${i}`,`=MAX(0,H${i}-J${i})`,`=MAX(0,H${i}-E${i}-I${i})`]];
}
sheet('人员汇总',['安排位置','真实人员ID','姓名','拟新增张数','其中共同历史','楼数','场景工作标签数','历史手工图片','预计操作小时'],d.people.map(r=>[r.slot,r.worker_id,r.name,r.images,r.common_images,r.buildings,r.scenes,r.history_manual_images,r.estimated_hours]),[22,18,18,18,20,14,22,20,20]);
sheet('逐人具体安排',['安排位置','真实人员ID','姓名','顺序','阶段','图片','同房组','场景','用途','优先级','复核状态','条件','执行状态'],d.assignments.slice().sort((a,b)=>a.slot.localeCompare(b.slot)||a.order-b.order).map(r=>[r.slot,r.worker_id,r.name,r.order,r.phase,r.code,r.room,r.scene,r.purpose,r.priority,r.review,r.condition,r.status]),[22,18,18,10,12,25,18,20,55,16,38,15,24]);
const mh=Object.keys(d.matrix[0]);sheet('全历史人员图片矩阵',mh,d.matrix.map(r=>mh.map(k=>r[k])),[24,22,22,...mh.slice(3).map(()=>23)]);
sheet('同房覆盖',['房间组','采用图片','预期Manual图片','历史高人数图','拟新增份数','全视角共同人数','Manual图片清单','解释'],d.rooms.map(r=>[r.room,r.images,r.expected_manual_images,r.history_high,r.new_proposed,r.common_people_all_views,r.codes,r.note]),[16,16,22,20,18,22,90,80]);
sheet('同房配对',['房间组','图片A','图片B','共同人数','其中新人','解释'],d.room_pairs.map(r=>[r.room,r.left,r.right,r.common_people,r.common_newcomers,r.note]),[15,26,26,18,18,90]);
sheet('全历史同房候选',['候选子集','历史有数据视角','预期有数据视角','预期至少8人视角','可比性原记录','待解决事项','图片清单','历史人数','预期人数','口径'],d.full_history_rooms.map(r=>[r.group,r.history_views,r.expected_views,r.expected_ge8,r.comparable?'支持':'待核对',r.holds,r.codes,r.history_counts,r.expected_counts,r.note]),[18,23,23,23,23,65,95,40,40,90]);
sheet('全历史场景覆盖',['场景','历史手工图片','预期手工图片','预期至少8人图片','building数','明确采用房间组数','口径'],d.scenes.map(r=>[r.scene,r.history_images,r.expected_images,r.expected_ge8,r.buildings,r.adopted_rooms,r.note]),[24,21,21,23,18,25,95]);
sheet('备用候选',['优先顺序','候选组','图片清单','场景工作分类','对应历史人数','理由','状态'],d.backup.map(r=>[r.rank,r.group,r.codes,r.scene,r.history,r.reason,r.status]),[15,18,95,48,25,65,26]);
sheet('高人数补视角待核对',['候选子集','已有历史人数','原可比性','OOS待核对','待解决事项','全组图片','池外拟补视角','逐图OOS记录'],d.high_history_backup.map(r=>[r.candidate,r.manual_counts,r.old_comparable?'支持':'待核对',r.oos_pending?'是':'否',r.hold_reasons,r.codes,r.outside_targets,r.oos_by_image]),[18,40,20,20,70,95,80,100]);
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(`${out}/图片名单与人员覆盖.xlsx`);
for(const s of definitions){const preview=await wb.render({sheetName:s.name,range:`A1:${col(Math.min(s.cols,5)-1)}${Math.min(s.rows+1,9)}`,scale:1,format:'png'});await fs.writeFile(`${out}/检查_${s.name}.png`,new Uint8Array(await preview.arrayBuffer()));}
console.log((await wb.inspect({kind:'region',sheetId:'拟选图片',range:'E1:L5',maxChars:1800,tableMaxRows:5,tableMaxCols:8})).ndjson);
console.log(JSON.stringify(definitions));
