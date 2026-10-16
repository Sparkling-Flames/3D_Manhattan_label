// 展示已审计的B8L2快照；不在工作簿中重新选择参考或拟合评分。
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const require = createRequire(path.join(process.cwd(), 'package.json'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const [input, output, previewDir] = process.argv.slice(2);
assert(input && output && previewDir, 'payload, output directory and preview directory required');
const {tables, checks} = JSON.parse(await fs.readFile(input,'utf8'));
const wb = Workbook.create();
const guide = wb.worksheets.add('00_口径与进度');
const labels = {panel:'分析层',metric:'指标',condition:'采集条件',worker_id:'人员ID',image_code:'图片',
 difficulty_class:'难度',n_records:'来源记录数',n_valid:'有效数',n_missing:'缺失数',n_valid_images:'有效图片数',
 n_valid_workers:'有效人员数',mean:'均值',median:'中位数',sd:'标准差',image_equal_mean:'图片等权均值',
 n_source_records:'来源记录数',B8L2_n:'完整质量数',B8L2_mean:'B8L2均值',B8L2_median:'B8L2中位数',
 B8L2_sd:'B8L2标准差',n_scored_images:'评分图片数',n_scored_workers:'评分人员数',
 B8L2_image_equal_mean:'B8L2图片等权均值',active_time_seconds_n:'有效采集时间数',
 active_time_seconds_mean:'采集时间均值 秒',active_time_seconds_median:'采集时间中位数 秒',
 target_matched_time_seconds_n:'同目标时间数',target_matched_time_seconds_mean:'同目标时间均值 秒',
 n_quality_target_time_common:'质量与同目标时间共有数',image_code_a:'同房图片A',image_code_b:'同房图片B',
 n_scored_a:'A评分人数',n_scored_b:'B评分人数',n_common_scored_workers:'共同评分人数',
 common_a_mean:'共同人员A均分',common_b_mean:'共同人员B均分',common_worker_delta_mean:'共同人员B减A',
 common_worker_absolute_delta_mean:'逐人差绝对值均值',common_worker_ids:'共同人员ID',
 building_id:'建筑',scene:'场景',doorway_status:'门洞状态',oos_subtype:'OOS类型',
 object_id:'作答ID',B8L2:'B8L2质量分',IoU3D100:'3D IoU百分分',WQ:'历史WQ对照',A10:'A10对照',
 active_time_seconds:'有效采集时间 秒',target_matched_time_seconds:'同目标时间 秒',time_status:'时间状态',
 image:'图片',current_class:'当前类别',target_role:'目标角色',gt_error_excluded:'GT错误排除',
 difficulty_analysis_exclusion:'难度排除原因',full_current_target_geometry_available:'完整目标可用',
 n_effective_workers:'有效真人数',pool_exclusion_reasons:'来源池排除原因',
 remaining_reasons:'待处理原因',minimal_human_question:'最少人工问题',reference_id:'评分参考ID'};
const common=['n_source_records','B8L2_n','B8L2_mean','B8L2_median','B8L2_sd','n_scored_images',
 'B8L2_image_equal_mean','active_time_seconds_n','active_time_seconds_mean','active_time_seconds_median',
 'target_matched_time_seconds_n','target_matched_time_seconds_mean','n_quality_target_time_common'];
const summary=['panel','metric','n_records','n_valid','n_missing','n_valid_images','n_valid_workers',
 'mean','median','sd','image_equal_mean'];
const specs=[
 ['01_总体分层','overview',summary],
 ['02_逐人概览','by_worker',['condition','worker_id',...common]],
 ['03_逐图概览','by_image',['condition','image_code','difficulty_class',...common]],
 ['04_人员与难度','by_worker_difficulty',['condition','worker_id','difficulty_class',...common]],
 ['05_难度分层','by_difficulty',['panel','difficulty_class',...summary.slice(1)]],
 ['06_特殊场景','by_scene',['panel','scene','doorway_status','oos_subtype',...summary.slice(1)]],
 ['07_同房直接对照','same_room',['image_code_a','image_code_b','condition','n_scored_a','n_scored_b',
 'n_common_scored_workers','common_a_mean','common_b_mean','common_worker_delta_mean',
 'common_worker_absolute_delta_mean','common_worker_ids']],
 ['08_完整质量明细','quality_records',['image_code','worker_id','condition','difficulty_class','B8L2',
 'IoU3D100','WQ','A10','active_time_seconds','target_matched_time_seconds','time_status',
 'iou_2d','S_bottom_deg','dir','Hmean','Hcenter','object_id','reference_id','B8L2_version']],
 ['09_当前图片','current_images',['image','current_class','target_role','gt_error_excluded',
 'difficulty_analysis_exclusion','full_current_target_geometry_available','doorway_status','oos_subtype']],
 ['10_待补人来源池','pending_people',['image_code','condition','n_effective_workers','pool_exclusion_reasons']],
 ['11_参考绑定待办','remaining_gaps',['image_code','worker_id','condition','remaining_reasons','minimal_human_question','object_id']],
 ['12_建筑分层','by_building',['panel','building_id',...summary.slice(1)]],
 ['13_来源与评分覆盖','analysis_records',['image_code','worker_id','condition','difficulty_class','B8L2','IoU3D100',
 'active_time_seconds','target_matched_time_seconds','time_status','target_time_interpretation','object_id']]
];
const categories={ordinary_manual:'普通·人工',ordinary_semi:'普通·模型辅助',special_manual:'特殊·人工',
 special_semi:'特殊·模型辅助',special_oos:'特殊·OOS判断',manual:'人工',semi:'模型辅助',oos:'OOS判断',
 active_time_seconds:'有效采集时间（秒）',target_matched_time_seconds:'同目标时间（秒）',IoU3D100:'3D IoU百分分',
 effective_workers_below_3:'有效真人不足3',current_target_scope_unresolved:'当前目标范围未定',
 answer_space_binding_not_unique:'作答空间绑定未定',
 confirmed_polygon_extends_beyond_complete_source_domain:'确认范围超出完整参考域',
 inherited_person_or_answer_restriction:'继承既有人/作答限制',original_annotation_geometry_unavailable_or_inapplicable:'原作答几何不可用或表示不适用'};
function value(v,field){
 if(v===null||v===undefined||v==='')return null;
 if(['remaining_reasons','pool_exclusion_reasons'].includes(field))return JSON.parse(v).map(x=>categories[x]??x).join('；');
 if(['condition','panel','metric'].includes(field))return categories[v]??v;
 if(typeof v==='string'&&/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v))return Number(v);
 return typeof v==='string'&&v.startsWith('=')?"'"+v:v;
}
const verification={sheets:[],score_version:checks.score_version};
for(const [name,key,fields] of specs){
 const rows=tables[key];assert(rows.length>0);assert(fields.every(f=>f in rows[0]),key+' field mismatch');
 const sh=wb.worksheets.add(name);sh.showGridLines=false;
 const values=[fields.map(f=>labels[f]??f),...rows.map(r=>fields.map(f=>value(r[f],f)))];
 const range=sh.getRangeByIndexes(0,0,values.length,fields.length);range.values=values;
 range.format={font:{name:'Microsoft YaHei',size:10,color:'#233344'},rowHeight:30,columnWidth:19,wrapText:true};
 sh.getRangeByIndexes(0,0,1,fields.length).format={fill:'#173B50',font:{bold:true,color:'#FFFFFF'},rowHeight:46};
 fields.forEach((f,i)=>{
  const col=sh.getRangeByIndexes(0,i,values.length,1);
  col.format.columnWidth=/image_code|reference|object_id/.test(f)?26:/reasons|question|interpretation/.test(f)?48:19;
  if(rows.some(r=>typeof value(r[f])==='number'))sh.getRangeByIndexes(1,i,rows.length,1).setNumberFormat(/(^n_|_n$)/.test(f)?'0':'0.00');
 });
 sh.tables.add(range,true,'B8View'+verification.sheets.length).showFilterButton=true;
 if(key==='remaining_gaps')sh.getRangeByIndexes(1,0,rows.length,fields.length).format.rowHeight=60;
 sh.freezePanes.freezeRows(1);
 assert.deepEqual(sh.getRangeByIndexes(1,0,1,fields.length).values,[values[1]]);
 assert.deepEqual(sh.getRangeByIndexes(rows.length,0,1,fields.length).values,[values.at(-1)]);
 verification.sheets.push({name,key,rows:rows.length,fields});
}
guide.showGridLines=false;
guide.getRange('A1:H2').merge();guide.getRange('A1').values=[['B8L2主线数据与推进状态  2026-10-16']];
guide.getRange('A1:H2').format={fill:'#173B50',font:{name:'Microsoft YaHei',size:18,bold:true,color:'#FFFFFF'},rowHeight:26};
guide.getRange('A3:H24').format={font:{name:'Microsoft YaHei',size:11,color:'#233344'},columnWidth:15,rowHeight:28,wrapText:true};
const notes=[
 ['当前安排','主线先用B8L2；Pro并行探索整体新方案，不限制为B8L2补丁。'],
 ['数据口径','3152库存 → 2834合格来源记录 → 891完整质量；本轮核对与既有快照一致。'],
 ['缺失含义','空白表示当前无有效数值，不能当0分；特殊层完整B8L2当前为0份。'],
 ['时间单位','全部为秒；采集时间与同目标可比时间分开，质量与同目标时间共有440份。'],
 ['同房口径','仅直接确认关系、同条件、同人员比较；共同人员较少不能证明迁移规律。'],
 ['模块状态','人员模型、融合过程、同房实验仍主要为旧WQ/Lee；本簿不是它们已完成B8L2接入。'],
 ['难度状态','采用v4人工复核粗类；普通候选151简单、16中等、39困难，旧v3另存。'],
 ['查阅方式','先看总体与覆盖，再看逐人/逐图；完整来源、参考身份和字段说明见同目录研究包。']
];
for(let i=0;i<notes.length;i++){
 const row=4+i*2;guide.getRange(`A${row}:B${row+1}`).merge();guide.getRange(`C${row}:H${row+1}`).merge();
 guide.getRange(`A${row}`).values=[[notes[i][0]]];guide.getRange(`C${row}`).values=[[notes[i][1]]];
 guide.getRange(`A${row}:B${row+1}`).format={fill:'#E7EFF3',font:{bold:true}};
}
guide.getRange('A21:H21').merge();guide.getRange('A21').values=[['普通层B8L2  ·  公式引用分层表，缺失不纳入均值']];
guide.getRange('A21:H21').format={fill:'#173B50',font:{bold:true,color:'#FFFFFF'}};
guide.getRange('A22:D24').values=[['条件','完整质量数','作答等权均值','图片等权均值'],['manual',null,null,null],['semi',null,null,null]];
for(const [i,panel] of ['ordinary_manual','ordinary_semi'].entries()){
 const src=tables.overview.findIndex(r=>r.panel===panel&&r.metric==='B8L2')+2;assert(src>=2);
 guide.getRange(`B${23+i}:D${23+i}`).formulas=[[`='01_总体分层'!D${src}`,`='01_总体分层'!H${src}`,`='01_总体分层'!K${src}`]];
}
guide.getRange('C23:D24').setNumberFormat('0.00');
verification.formula_errors=(await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:20}})).ndjson;
assert(!/"value":"#(REF!|DIV\/0!|VALUE!|NAME\?|N\/A)/.test(verification.formula_errors));
await fs.mkdir(previewDir,{recursive:true});
for(const [i,name] of ['00_口径与进度',...specs.map(s=>s[0])].entries()){
 const blob=await wb.render({sheetName:name,range:i===0?'A1:H24':'A1:F6',scale:1,format:'png'});
 await fs.writeFile(path.join(previewDir,`${i}.png`),new Uint8Array(await blob.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(output,'B8L2主线数据与状态_20261016.xlsx'));
await fs.rm(path.join(output,'B8L2主线数据与状态_20261016.xlsx.inspect.ndjson'),{force:true});
await fs.writeFile(path.join(output,'WORKBOOK_VERIFICATION.json'),JSON.stringify(verification,null,2));
console.log(JSON.stringify({sheets:specs.length+1,output,previews:previewDir}));
