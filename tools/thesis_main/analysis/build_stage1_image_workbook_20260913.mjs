import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const base = path.resolve(process.argv[2]);
const d = JSON.parse(await fs.readFile(path.join(base, '分配建议与核验.json'), 'utf8'));
assert.equal(d.schema, 'stage1_image_package_proposal_v1');
const out = path.join(base, 'outputs', '01a0852f-dc20-7081-99dd-0413afa69d79');
const qa = path.join(base, '工作簿检查');
await fs.mkdir(out, {recursive:true});
await fs.mkdir(qa, {recursive:true});
const wb = Workbook.create();
const previews = [];
const palette = {navy:'#153F53', teal:'#267C88', pale:'#EDF5F7', text:'#243A45', line:'#D7E3E8'};
const id = w => `W${String(w).padStart(3,'0')}`;
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
const overview=wb.worksheets.add('使用说明与总览');overview.showGridLines=false;
overview.getRange('A1:J38').format={font:{name:'Microsoft YaHei',size:11,color:palette.text},rowHeight:25,columnWidthPx:110};
overview.getRange('A1:J2').merge();overview.getRange('A1').values=[['第一阶段 · 逐人图片分配建议']];
overview.getRange('A1:J2').format={fill:palette.navy,font:{size:22,bold:true,color:'#FFFFFF'}};
overview.getRange('A3:J4').merge();overview.getRange('A3').values=[['管理用工作簿。中文每人20张；英文每人必做30张，另有可选20张。所有可选任务按0份承诺计入必做预算；这是建议包，未导入或派发。']];
overview.getRange('A3:J4').format={fill:palette.pale,wrapText:true};

const ar=d.assignments.map(r=>[id(r.worker_id),r.language==='zh'?'中文':'英文',r.tier==='required'?'必做':'可选',r.optional_kind||'—',r.order,r.batch,r.code,r.image_id,r.difficulty,r.scene,r.image_path,r.baseline_credit]);
const assign=sheet('全部人图建议','680行人员 × 图片建议','每行只属于一人、一图、一个任务部分；“必做信用”仅指预算计入，不表示已经完成。预期难度等研究信息只供管理者查看。',
  ['人员','语言','任务部分','可选用途','顺序','房间／组','图片编号','完整图片ID','预期难度','场景类型','仓库原图路径','必做预算计入'],ar,[85,65,75,105,65,110,185,300,95,120,340,95]);
const n=ar.length+5;
const wr=d.workers.map(w=>[id(w.worker_id),w.language==='zh'?'中文':'英文',w.submitted_images,w.draft_only_images,null,null,null,null,w.simple,w.medium,w.hard]);
const personnel=sheet('人员总表','每个人需要做多少张','历史提交图按独立图片去重；“仅草稿”也避免重复分配。右侧难度数量只统计必做部分，英文优先困难不是约束。',
 ['人员','语言','历史提交图','仅草稿图','必做','可选同房','可选门洞','提供合计','必做简单','必做中等','必做困难'],wr,[90,65,110,100,85,100,100,100,100,100,100]);
for(let i=0;i<wr.length;i++){
  const r=i+6;
  personnel.getRange(`E${r}:H${r}`).formulas=[[
    `=COUNTIFS('全部人图建议'!$A$6:$A$${n},A${r},'全部人图建议'!$C$6:$C$${n},"必做")`,
    `=COUNTIFS('全部人图建议'!$A$6:$A$${n},A${r},'全部人图建议'!$D$6:$D$${n},"同房补充")`,
    `=COUNTIFS('全部人图建议'!$A$6:$A$${n},A${r},'全部人图建议'!$D$6:$D$${n},"门洞补充")`,
    `=SUM(E${r}:G${r})`]];
}
for(const w of d.workers){
  const rr=d.assignments.filter(r=>r.worker_id===w.worker_id);
  sheet(id(w.worker_id),`${id(w.worker_id)} · ${w.language==='zh'?'中文20张':'英文30张＋可选20张'}`,
    '管理用清单：按房间分组显示，必做在前、可选在后；该人员的原提交与草稿均已核对。查看实际图片请打开语言图片包中同名HTML。',
    ['部分','顺序','房间／组','图片编号','可选用途','预期难度','场景类型','采用状态'],
    rr.map(r=>[r.tier==='required'?'必做':'可选',r.order,r.batch,r.code,r.optional_kind||'—',r.difficulty,r.scene,r.selection_state]),
    [72,62,140,185,105,88,120,245]);
}
const im=d.images.map(r=>[r.code,r.group,r.scene,r.history_manual,r.required_new,null,r.optional_offered,null,r.user_target,r.gap_after_required,peopleText(r.required_workers),peopleText(r.optional_workers)]);
const ims=sheet('逐图人数','每张图：历史、必做、可选分别计算','“全部可选完成后”只是上限情景。门洞补充图未填写目标人数的保持空白；仅复用历史的原人数保留。',
 ['图片编号','组号','场景','历史Manual','必做新增','历史＋必做','可选提供','全可选完成后','原目标','必做后缺口','必做人员','可选人员'],im,[185,125,120,100,95,105,95,120,95,105,340,340]);
for(let i=0;i<im.length;i++){
  const r=i+6;ims.getRange(`F${r}`).formulas=[[`=D${r}+E${r}`]];ims.getRange(`H${r}`).formulas=[[`=F${r}+G${r}`]];
  ims.getRange(`J${r}`).formulas=[[`=IF(I${r}="","",MAX(0,I${r}-F${r}))`]];
}
sheet('房间覆盖','必做阶段实际覆盖哪些房间视角','按19个已采用组核算。至少8人的列仅描述覆盖，不是统一准入门槛；可选视角不能当成必做后已经获得。',
 ['组号','已采用图片','历史Manual','必做新增','必做后Manual','有Manual视角','其中至少8人','可选提供'],
 d.rooms.map(r=>[r.group,r.adopted_images,r.history_manual,r.required_new,r.manual_after_required,r.views_with_manual,r.views_at_least8,r.optional_offered]),[95,120,120,120,130,150,150,120]);
sheet('门洞历史与候选','门洞图：已有标注和本次可选建议','40张历轮记录中，34张保留为候选、3张OOS待核实、3张明确OOS排除。确认／疑似指门洞身份；不能与OOS状态混用。',
 ['图片编号','关联组','门洞身份','OOS处置','历史Manual','历史Semi','未做过的英文人员数','可选提供','已有Manual人员'],
 d.doorway_inventory.map(r=>[r.code,r.groups,r.doorway,r.oos,r.history_manual,r.history_semi,r.clean_english,r.optional_offered,peopleText(r.history_workers)]),[185,145,100,145,110,110,165,105,360]);
const reserve=d.images.filter(r=>r.required_new);
sheet('退出后的替补候选','有人退出：先查该图还能找谁','替补列只说明该人员没接触过这张图，不表示其20／30张工作量仍有空余。不可把自愿任务算成已答应补位，也不能重复派给原标注者。',
 ['图片编号','组号','原目标','历史＋必做','少1人后','未接触替补人数','候选人员'],
 reserve.map(r=>[r.code,r.group,r.user_target,r.required_plan_total,r.one_dropout_total,r.alternative_workers.length,peopleText(r.alternative_workers)]),[185,95,105,125,105,155,460]);
sheet('可选参与情景','可选任务：0人参加也单独保留必做计划','分别枚举哪些英文人员完成全部20张，展示覆盖范围。部分人只做几张时按真实提交逐图统计；这些是情景，不是参与率预测。',
 ['完成20张人数','新增可选份数','至少新增2人图数下限','至少新增2人图数上限','至少新增5人图数下限','至少新增5人图数上限'],
 d.optional_scenarios.map(r=>[r.volunteers_finishing20,r.optional_new,r.min_images_with2_new,r.max_images_with2_new,r.min_images_with5_new,r.max_images_with5_new]),[160,150,180,180,180,180]);
sheet('历史人员图片','每人以前做过什么图片','24份原始导出的全部提交版本与可识别草稿汇总；修订与多份导出不重复增加独立图片数。未保存的浏览行为不在此记录中。',
 ['人员','语言','图片编号','已提交','存在草稿','计入Manual历史','有Semi接触','在648图中','原始导出来源'],
 d.history.map(r=>[id(r.worker_id),r.language,r.code,r.has_submission?'是':'否',r.has_draft?'是':'否',r.manual_in_analysis?'是':'否',r.semi_exposure?'是':'否',r.in_648?'是':'否',r.sources]),[90,70,190,85,95,145,120,110,460]);
sheet('来源与口径','来源、字段与使用边界','本轮是研究探索分配建议，不改Paper A正式方法合同、原始导出、图片采用决定或LS项目配置。',
 ['项目','说明'],[
 ['选图依据',d.selection_source],['同房与图片路径',d.registry_source],['必做匹配来源',d.external_assignment_source],
 ['必做选择理由','沿用已独立核验的43图、19组覆盖候选，解决本次逐人安排；不是科学最优选图，完整多视角研究仍需后续数据。'],
 ['可选组成','每人10张同房补充＋10张门洞；两类共20张，可以不做、部分做或全部做。'],
 ['门洞采用状态','确认是门洞不等于本次已采用。13张新增门洞候选均无明确OOS／待核实记录，仍保留待最终采用状态。'],
 ['历史与未来人员','保留W11历史；后续不派W11；本轮主计算排除W019／W026，其他既往人员按现有可用记录保留。'],
 ['不重复范围',d.exposure_scope],['可选分析','保留实际参与者、提供顺序、跳过和实际人数；自愿参与人员不能自动代表全部英文人员。'],
 ['图片包用法','解压中文／英文图片包，打开index.html，再打开对应人员页。共用images目录只保存原图，不含历史标注或GT。'],
 ['任务身份','图片编号不是LS任务编号；本次没有生成或猜测线上项目号、任务链接，也未派发。'],
 ['单位','1份＝一个人对一张图片的一次作答。分配、实际提交、可用于几何分析的作答是三个不同计数。']],[170,900]);

overview.getRange('A6:D6').values=[['任务组','必做','可选同房','可选门洞']];
overview.getRange('A6:D6').format={fill:palette.teal,font:{bold:true,color:'#FFFFFF'}};
overview.getRange('A7:A8').values=[['中文'],['英文']];
for(const r of [7,8])overview.getRange(`B${r}:D${r}`).formulas=[['E','F','G'].map(c=>`=SUMIF('人员总表'!$B$6:$B$24,A${r},'人员总表'!$${c}$6:$${c}$24)`)];
overview.getRange('A10:D10').values=[['合计',null,null,null]];
overview.getRange('B10:D10').formulas=[['B','C','D'].map(c=>`=SUM(${c}7:${c}8)`)];
overview.getRange('A10:D10').format={fill:palette.pale,font:{bold:true}};
const chart=overview.charts.add('bar',overview.getRange('A6:D8'));
chart.title='必做与可选提供量（人图）';chart.hasLegend=true;chart.yAxis={numberFormatCode:'0'};chart.setPosition('E6','J20');
const notes=[
 '必做：43张图片、19个已采用组；480份新增。原102图池已有383份Manual，必做全完成且可用后为863份。',
 '可选：25张补充图片，提供200个人图名额；其中12张是已采用房间视角，13张是确认门洞的补充候选。',
 '门洞历史：34张可继续考虑的候选中，15张有Manual，共211份；8张已有20人以上，19张尚无Manual。',
 '退出：6张必做图已用尽现有未接触人员；其中3张最多到19人，低于原20人目标。替补表不把可选参与当承诺。',
 '使用顺序：人员总表 → 对应W编号清单 → 解压图片包查看原图。必做和可选各自编号，避免把50张都说成必须完成。',
 '解释边界：8人真实有效共识可记收敛；本表没有因人数不足改写成不收敛，也没有给目标图片提前填收敛结果。'
];
notes.forEach((text,i)=>{const r=22+i*2;overview.getRange(`A${r}:J${r+1}`).merge();overview.getRange(`A${r}`).values=[[text]];overview.getRange(`A${r}:J${r+1}`).format={wrapText:true,fill:i%2? '#FFFFFF':palette.pale};});
previews.unshift({name:'使用说明与总览',range:'A1:J34'});
// 检查可见汇总及全部公式，再检查导出的文件，而不是只检查构建器输入。
assert.deepEqual(overview.getRange('B10:D10').values,[[480,100,100]]);
for(let i=0;i<d.workers.length;i++)assert.deepEqual(personnel.getRange(`E${i+6}:H${i+6}`).values,[[d.workers[i].required,d.workers[i].language==='en'?10:0,d.workers[i].language==='en'?10:0,d.workers[i].total_offered]]);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:30},summary:'formula errors'});
await fs.writeFile(path.join(qa,'公式扫描.json'),JSON.stringify(errors));
console.log('formula scan',errors.ndjson);
for(const p of previews){
  const image=await wb.render({sheetName:p.name,range:p.range,scale:1,format:'png'});
  await fs.writeFile(path.join(qa,`${p.name}.png`),new Uint8Array(await image.arrayBuffer()));
  console.log('rendered',p.name);
}
const target=path.join(out,'第一阶段逐人图片分配建议.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(target);
const reopened=await SpreadsheetFile.importXlsx(await FileBlob.load(target));
assert.deepEqual(reopened.worksheets.getItem('使用说明与总览').getRange('B10:D10').values,[[480,100,100]]);
assert.equal(reopened.worksheets.getItem('全部人图建议').getUsedRange().values.length,685);
await fs.writeFile(path.join(qa,'工作簿核验.json'),JSON.stringify({sheets:previews.length,assignmentRows:680,required:480,optional:200,reopened:true,previews:previews.map(p=>p.name)},null,2));
console.log('saved',target);
