// 当前逐图标注人数查阅簿：只消费已核验表，不另定义人员/作答准入。
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
const require=createRequire(path.join(process.cwd(),'package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const flag=process.argv.indexOf('--source-dir');
const source=path.resolve(flag<0?path.join(root,'research/statistics/annotation_counts_20261017'):process.argv[flag+1]);
const tables=JSON.parse(await fs.readFile(path.join(source,'tables.json'),'utf8'));
const checks=JSON.parse(await fs.readFile(path.join(source,'CHECKS.json'),'utf8'));
const contract=JSON.parse(await fs.readFile(path.join(source,'FIELD_CONTRACT.json'),'utf8'));
const previews=path.join(process.cwd(),'annotation_counts_20261017_preview');
await fs.mkdir(previews,{recursive:true});
const wb=Workbook.create();
const summary=wb.worksheets.add('01_汇总');
const images=wb.worksheets.add('02_逐图人数');
const pending=wb.worksheets.add('03_待定与限制图');
const gt=wb.worksheets.add('04_GT问题分类');
const reference=wb.worksheets.add('05_参考与目标待补');
const removed=wb.worksheets.add('06_移出作答');
const labels={image_code:'图片编号',n_retained_workers:'保留独立人数\n跨条件去重',
 n_manual_workers:'manual独立人数',n_semi_workers:'semi独立人数',n_oos_workers:'oos独立人数',
 n_manual_semi_workers:'manual与semi合并独立人数',n_retained_records:'保留作答数',n_raw_records:'原作答数',
 n_removed_records:'移出作答数',n_user_excluded_records:'用户排除作答数',n_pending_records:'清洗待定作答数',
 n_nonindependent_or_other_hold_records:'非独立或其它暂缓数',retained_worker_ids:'保留人员ID列表',
 image_id:'稳定图片ID',building_id:'建筑ID',worker_id:'人员ID',condition:'采集条件',object_id:'稳定作答ID',
 cleaning_disposition:'清洗状态',removal_group:'互斥移出类别',pool_vote_exclusion_reasons:'独立作答移出原因',
 pool_vote_eligible:'独立作答保留',pool_rule_version:'准入规则版本',pool_source_workers:'来源池人数',
 pool_min3_pass:'来源池满3人·本统计不设门',duplicate_effective_worker:'重复有效人员',
 pool_image_exclusion_reasons:'图片分析排除原因·本统计不设门',pool_analysis_eligible:'图片分析资格·本统计不设门',
 pool_analysis_exclusion_reasons:'分析排除原因·本统计不设门',ordinary_difficulty_eligible:'普通难度资格·本统计不设门'};
Object.assign(labels,{current_gt_error:'当前GT明确错误',historical_gt_substantive_error:'历史GT实质错误',
 gt_error_union:'当前或历史\nGT明确错误',gt_uncertainty:'GT不确定',gt_detail_omission:'GT细节遗漏',
 current_issue_pending:'当前问题待定',applicability_pending:'适用性待定',image_analysis_hold:'图片分析暂缓',
 scene:'场景',doorway_status:'门洞状态',oos_subtype:'OOS类型',oos_quality_diagnostic_only:'OOS质量仅诊断',
 difficulty_class:'难度分类',difficulty_exclusion:'难度排除说明',image_hold_reasons:'图片暂缓原因',
 gt_issue_types:'GT问题分类',image_comment:'图片原始备注',difficulty_question:'难度审核原问题',
 current_target_id:'当前目标ID',reference_full_available:'完整当前参考可用',
 n_retained_target_pending:'保留作答中目标待定数',n_retained_reference_pending:'保留作答中参考待补数',
 n_current_quality_usable:'当前质量可用数·非人数门槛',no_retained_annotations:'无保留作答',any_condition_min3:'有条件满3人·非人数门槛'});
Object.assign(labels,{gt_reference_problem:'完整来源明确\nGT或参考问题',later_explicit_reference_problem:'后续明确参考问题',
 later_reference_status:'后续参考状态',later_reference_source_message:'后续参考来源原文'});
const clean=x=>x==null?null:typeof x==='object'?JSON.stringify(x):x;
function header(sh,title,note,width=8){
 sh.showGridLines=false;
 sh.getRangeByIndexes(0,0,2,width).merge();sh.getRange('A1').values=[[title]];
 sh.getRangeByIndexes(0,0,2,width).format={fill:'#173B50',font:{name:'Microsoft YaHei',size:18,bold:true,color:'#FFFFFF'},rowHeight:25};
 sh.getRangeByIndexes(2,0,2,width).merge();sh.getRange('A3').values=[[note]];
 sh.getRangeByIndexes(2,0,2,width).format={fill:'#EDF3F6',font:{name:'Microsoft YaHei',size:11,color:'#334455'},wrapText:true,rowHeight:29};
 sh.freezePanes.freezeRows(6);
}
function nativeTable(sh,rows,fields,name,row=5,col=0){
 assert(fields.every(f=>Object.hasOwn(rows[0],f)),name+' missing fields');
 const values=[fields.map(f=>labels[f]??f),...rows.map(r=>fields.map(f=>clean(r[f])))];
 const range=sh.getRangeByIndexes(row,col,values.length,fields.length);range.values=values;
 range.format={font:{name:'Microsoft YaHei',size:11,color:'#233344'},columnWidth:20,rowHeight:31,wrapText:true};
 sh.getRangeByIndexes(row,col,1,fields.length).format={fill:'#173B50',font:{bold:true,color:'#FFFFFF'},rowHeight:54};
 sh.tables.add(range,true,name).showFilterButton=true;
 fields.forEach((field,i)=>{
  if(field.startsWith('n_'))sh.getRangeByIndexes(row+1,col+i,rows.length,1).setNumberFormat('0');
  if(/reasons|_ids$|object_id|image_id/.test(field))sh.getRangeByIndexes(row,col+i,values.length,1).format.columnWidth=38;
 });
 for(const index of [0,rows.length-1])assert.deepEqual(sh.getRangeByIndexes(row+index+1,col,1,fields.length).values[0],values[index+1]);
 return {rows:rows.length,fields};
}
header(summary,'当前逐图标注人数 · 汇总',
 '只按既有独立作答准入移出用户排除、待定与非独立作答；保留1／2人图和GT问题图。本簿统计标注人数，不是质量分析面板。',8);
const summaryRows=[
 ['库存图片',checks.inventory_images,'含全部移出后0人的图片'],['原始作答',checks.raw_records,'移出前库存'],
 ['原始人员',checks.raw_workers,'移出前库存'],['保留独立作答',checks.retained_records,'跨条件仍为不同原作答'],
 ['保留人员',checks.retained_workers,'全库去重人员'],['有保留作答图片',checks.images_with_retained_annotations,'至少1人'],
 ['保留0人图片',checks.images_with_zero_retained_annotations,'仍列在逐图页'],
 ['逐图独立人员次数合计',checks.image_worker_pairs,'同图同人跨条件只计1次'],
 ['每图人数中位数',checks.workers_per_image.median,'含0人图'],['每图人数最大值',checks.workers_per_image.max,'跨条件去重'],
 ['移出作答',checks.removed_records,'以下三类互斥'],['用户明确排除',checks.removal_groups.user_excluded,'user_excluded'],
 ['清洗待定',checks.removal_groups.pending,'pending'],['非独立或其它暂缓',checks.removal_groups.nonindependent_or_other_hold,'nonindependent_or_other_hold'],
 ['manual保留作答',checks.retained_records_by_condition.manual,'采集条件'],['semi保留作答',checks.retained_records_by_condition.semi,'采集条件'],
 ['oos保留作答',checks.retained_records_by_condition.oos,'采集条件；不自动解释为可用完整layout'],
 ['全排除人员',checks.entirely_excluded_workers.join('、'),'逐条原因见06_移出作答'],
 ['来源版本',checks.version,'manifest-backed当前loader'],['研究合同',checks.contract_version,'准入沿用既有规则'],
 ];
const metrics=[['统计项','数值','说明'],...summaryRows];
summary.getRangeByIndexes(5,0,metrics.length,3).values=metrics;
summary.getRangeByIndexes(5,0,metrics.length,3).format={font:{name:'Microsoft YaHei',size:11,color:'#233344'},columnWidth:28,rowHeight:31,wrapText:true};
summary.getRangeByIndexes(5,0,1,3).format={fill:'#173B50',font:{bold:true,color:'#FFFFFF'},rowHeight:54};
summary.getRange('C:C').format.columnWidth=44;
summary.tables.add(summary.getRangeByIndexes(5,0,metrics.length,3),true,'CountSummary').showFilterButton=true;
labels.n_images='图片数';
nativeTable(summary,tables.people_count_distribution,['n_retained_workers','n_images'],'PeopleDistribution',5,4);
summary.getRange('E:E').format.columnWidth=28;
summary.getRange('H6:H15').values=[['查阅导航'],['02_逐图人数：全部库存图'],['03_待定与限制图：限制并集'],['04_GT问题分类：问题/不确定/遗漏'],['05_参考与目标待补'],['06_移出作答：逐条原因'],['跨条件人数不能相加'],['同图同人可能跨条件出现'],['人数与作答数不完全相同'],['完整证据数组见同目录CSV/README']];
summary.getRange('H:H').format={columnWidth:36,font:{name:'Microsoft YaHei',size:11,color:'#334455'},wrapText:true};
const statusSummary=[['图片状态','图片数','说明'],
 ['待定/排除/限制并集',checks.pending_excluded_or_limited_images,'多种限制的并集，不是整图人工排除总数'],
 ['GT问题并集',checks.gt_any_issue_images,'错误、不确定、细节遗漏可重叠'],
 ['完整来源明确GT/参考问题',checks.explicit_gt_reference_problem_images,'含后续明确不准确待修订来源'],
 ['当前或历史GT错误标记',checks.gt_error_marker_images,'既有布尔标记并集；与完整来源问题分列'],
 ['当前GT明确错误',checks.current_gt_error_images,'当前标志'],['历史GT实质错误',checks.historical_gt_error_images,'历史审计保留'],
 ['GT不确定',checks.gt_uncertainty_images,'不能写成明确错误'],['GT细节遗漏',checks.gt_detail_omission_images,'不能全部写成实质错误'],
 ['图片分析暂缓',checks.image_analysis_hold_images,'不等同于所有原作答移出'],
 ['当前问题待定',checks.current_issue_pending_images,'独立状态轴'],['适用性待定',checks.applicability_pending_images,'不等同于GT错误'],
 ['当前完整参考待补',checks.incomplete_current_reference_images,'不补造未知参考'],
 ['保留作答中有目标待定的图',checks.retained_target_pending_images,'逐条目标绑定未明'],
 ['参考与目标待补并集',tables.reference_pending_images.length,'不影响本次独立人数计数']];
const statusRange=summary.getRangeByIndexes(32,0,statusSummary.length,3);statusRange.values=statusSummary;
statusRange.format={font:{name:'Microsoft YaHei',size:11,color:'#233344'},wrapText:true,rowHeight:38};
summary.getRange('A33:C33').format={fill:'#173B50',font:{bold:true,color:'#FFFFFF'}};
summary.tables.add(statusRange,true,'ImageStatusSummary').showFilterButton=true;
header(images,'逐图保留独立人数',
 '总人数按同图worker_id跨manual/semi/oos去重；分条件人数不可直接相加。原数、移出数与三类原因保留审计；不剔除少人图或GT问题图。',8);
const imageFields=['image_code','n_retained_workers','n_manual_workers','n_semi_workers','n_oos_workers',
 'n_manual_semi_workers','n_retained_records','n_raw_records','n_removed_records','n_user_excluded_records',
 'n_pending_records','n_nonindependent_or_other_hold_records','retained_worker_ids','image_id','building_id'];
const statusFields=Object.keys(tables.image_counts[0]).filter(f=>!imageFields.includes(f)&&!f.endsWith('_evidence'));
const imageInfo=nativeTable(images,tables.image_counts,[...imageFields,...statusFields],'ImageCounts');images.freezePanes.freezeColumns(1);
const extraSpecs=[
 [pending,'pending_excluded_images','PendingImages','待定与限制图片',
  '这是多种限制的并集；不是全部整图人工排除。少人数、OOS诊断和参考待补分别保留，不自动改写为GT错误。',
  ['image_code','image_hold_reasons','current_issue_pending','applicability_pending','image_analysis_hold','n_retained_workers','n_removed_records','image_comment']],
 [gt,'gt_problem_images','GTProblems','GT问题分类与原始原因',
  '完整来源明确GT/参考问题与既有错误标记分列；后续明确不准确待修订保留原文。GT不确定和细节遗漏另轴，可重叠；本页不是明确错误总数。',
  ['image_code','gt_issue_types','gt_reference_problem','gt_error_union','later_explicit_reference_problem','gt_uncertainty','gt_detail_omission','image_comment']],
 [reference,'reference_pending_images','ReferencePending','参考与目标待补图片',
  '当前完整参考待补与保留作答目标未明按源台账分别列示；不等同于GT明确错误，也不因此扣除本次独立标注人数。',
  ['image_code','reference_full_available','n_retained_target_pending','n_retained_reference_pending','current_target_id','n_retained_workers','difficulty_question','image_hold_reasons']],
];
const extraInfo=[];
for(const [sh,key,name,title,note,front] of extraSpecs){
 header(sh,title,note,8);
 const fields=[...front,...Object.keys(tables[key][0]).filter(f=>!front.includes(f)&&!f.endsWith('_evidence'))];
 extraInfo.push({name:sh.name,key,...nativeTable(sh,tables[key],fields,name)});
 sh.freezePanes.freezeColumns(1);
 sh.getRangeByIndexes(6,0,tables[key].length,fields.length).format.rowHeight=104;
 for(const f of ['image_comment','image_hold_reasons','difficulty_question']){
  const i=fields.indexOf(f);sh.getRangeByIndexes(5,i,tables[key].length+1,1).format.columnWidth=64;
 }
}
header(removed,'移出作答明细',
 '移出类别互斥：user_excluded用户明确排除；pending清洗待定；nonindependent_or_other_hold非独立或其它暂缓。详细原因可重叠，不能重复加总。',8);
const removedFields=['image_code','worker_id','condition','removal_group','cleaning_disposition','pool_vote_exclusion_reasons',
 'object_id','image_id',...contract.tables.removed_annotations.columns.filter(f=>!['image_code','worker_id','condition','removal_group','cleaning_disposition','pool_vote_exclusion_reasons','object_id','image_id'].includes(f))];
const removedInfo=nativeTable(removed,tables.removed_annotations,removedFields,'RemovedAnnotations');removed.freezePanes.freezeColumns(2);
removed.getRangeByIndexes(6,0,tables.removed_annotations.length,removedFields.length).format.rowHeight=84;
removed.getRange('F:F').format.columnWidth=62;
const scan=(await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:20},summary:'人数查阅簿错误检查'})).ndjson;
assert(!/"value":"#(REF!|DIV\/0!|VALUE!|NAME\?|N\/A)/.test(scan));
for(const [name,range,file] of [['01_汇总','A1:H30','summary.png'],['01_汇总',`A33:H${32+statusSummary.length}`,'summary_status.png'],
 ['02_逐图人数','A1:H12','images.png'],['03_待定与限制图','A1:H10','pending.png'],
 ['04_GT问题分类','A1:H10','gt.png'],['05_参考与目标待补','A1:H10','reference.png'],['06_移出作答','A1:H10','removed.png']]){
 const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(path.join(previews,file),new Uint8Array(await blob.arrayBuffer()));
}
const filename=path.join(source,'当前逐图标注人数_20261017.xlsx');
await(await SpreadsheetFile.exportXlsx(wb)).save(filename);await fs.rm(filename+'.inspect.ndjson',{force:true});
await fs.writeFile(path.join(source,'WORKBOOK_VERIFICATION.json'),JSON.stringify({version:checks.version,workbook:filename,
 sheets:[{name:'01_汇总',summary_rows:summaryRows.length,distribution_rows:tables.people_count_distribution.length},
 {name:'02_逐图人数',...imageInfo},...extraInfo,{name:'06_移出作答',...removedInfo}],source:'tables.json;CHECKS.json;FIELD_CONTRACT.json',
 source_first_last_rows_checked:true,formula_error_scan:scan,preview_directory:previews,previews_deleted:false},null,2));
console.log(JSON.stringify({workbook:filename,previews,sheets:6}));
