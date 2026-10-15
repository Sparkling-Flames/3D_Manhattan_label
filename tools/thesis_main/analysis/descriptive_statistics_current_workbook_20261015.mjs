// 当前口径快照的静态查阅工作簿；不重算资格、难度或质量。
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(path.join(process.cwd(), 'package.json'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const arg = name => process.argv.includes(name) ? process.argv[process.argv.indexOf(name)+1] : undefined;
const out = path.resolve(arg('--source-dir') ?? path.join(root, 'research/statistics/descriptive_statistics_current_20261015'));
const tables = JSON.parse(await fs.readFile(path.join(out, 'tables.json'), 'utf8'));
const contract = JSON.parse(await fs.readFile(path.join(out, 'FIELD_CONTRACT.json'), 'utf8'));
const workbook = Workbook.create();
const checks = { source: path.join(out, 'tables.json'), sheets: [] };
const previews = path.join(process.cwd(), 'current_statistics_workbook_preview_'+path.basename(out));
await fs.mkdir(previews, { recursive: true });
const clean = value => value === undefined || value === null ? null :
  typeof value === 'object' ? JSON.stringify(value) :
  typeof value === 'string' && value.startsWith('=') ? "'"+value : value;
const recordFields = ['image_code','worker_id','condition','difficulty_class','analysis_layer','pool_source_workers',
  'current_quality_eligible','WQ','A10','B8L2','IoU3D100','active_time_seconds','target_matched_time_seconds',
  'target_time_interpretation','new_space_target','current_target_id','reference_id','score_version','object_id','image_id'];
const selectedColumns = {
  inventory_all: ['image_code','worker_id','condition','cleaning_disposition','independent_vote_eligible',
    'time_status','active_time_seconds','time_source','time_rule_version','object_id','image_id','building_id','source_path'],
  record_audit: ['image_code','worker_id','condition','difficulty_class','analysis_layer','pool_vote_eligible',
    'pool_source_workers','pool_analysis_eligible','ordinary_difficulty_eligible','gt_error_excluded',
    'current_quality_eligible','rescore_status','quality_audit_status','reference_audit_reasons','pool_vote_exclusion_reasons',
    'WQ','historical_WQ','active_time_seconds','target_matched_time_seconds','target_time_interpretation',
    'new_space_target','current_target_id','reference_id','score_version','object_id'],
  analysis_records: recordFields,
  quality_records: [...recordFields,'iou_2d','S_bottom_deg','dir','Hmean','Hcenter'],
  current_images: ['image','difficulty_class','target_role','new_space_target','gt_error_excluded',
    'difficulty_analysis_eligible','difficulty_analysis_exclusion','reference_status','target_geometry_status',
    'doorway_status','oos_subtype','scene','space_scope_confirmed','top_boundary_pending',
    'full_current_target_geometry_available','target_source_verified','current_target_id','target_source','image_id'],
  pending_rescore: ['image_code','worker_id','condition','new_space_target','current_class','pool_analysis_eligible',
    'current_quality_eligible','quality_audit_status','reference_audit_reasons','input_geometry_unchanged',
    'reference_geometry_unchanged','annotation_identity_unchanged','complete_target_coordinates_equal',
    'full_reference_compatible','reuse_full_quality','current_target_id','reference_id','object_id'],
  same_room_pairs: ['image_code_a','image_code_b','relation','candidate_ids','metric','n_records_a','n_records_b',
    'n_common_workers','n_pairs','n_missing_common_a','n_missing_common_b','paired_a_mean','paired_b_mean',
    'delta_b_minus_a_mean','delta_b_minus_a_median','delta_b_minus_a_sd','absolute_paired_delta_mean','image_a','image_b'],
  same_room_relations: ['image_code_a','image_code_b','relation','candidate_ids','n_records_a','n_records_b',
    'n_common_workers','physical_same_supported','physical_same_explicit_confirmed','evidence_json','image_a','image_b'],
  space_reference_catalog: ['image_code','current_target','role','version_alias','is_admitted_space_candidate',
    'full_reference_available','status','method','minimal_gap','image_analysis_blocked',
    'image_analysis_hold_reasons','target_id','reference_version','source_reference_ids','image_id'],
  affected_records: ['image_code','worker_id','condition','binding_status','score_status','current_quality_eligible',
    'current_reference_full_available','chosen_reference_full_available','chosen_target_is_current',
    'score_input_eligible','person_quality_restriction_clear','pool_analysis_eligible','ordinary_difficulty_eligible',
    'pool_source_workers','annotation_geometry_status','ring_confirmed','independent_vote_eligible',
    'annotation_modified','annotation_cropped','quality_used_for_binding','chosen_target_id','current_target_id','object_id'],
  record_targets: ['image_id','worker_id','condition','current_target','is_admitted_space_candidate',
    'selected_by_binding','binding_status','allowed_by_manual_family','pool_analysis_eligible',
    'pool_source_workers','candidate_ids','target_id','object_id'],
  rescore_comparisons: ['image_code','worker_id','condition','score_status','reasons','WQ','A10','B8L2','IoU3D100',
    'historical_WQ','historical_A10','historical_B8L2','historical_IoU3D100',
    'delta_WQ','delta_A10','delta_B8L2','delta_IoU3D100','reference_version',
    'current_target_id','historical_reference_id','object_id'],
  image_spaces: ['image_id','condition','current_target','is_admitted_space_candidate','full_reference_available',
    'n_pool_workers','n_space_bound_workers','space_bound_min3','pool_analysis_eligible',
    'pool_exclusion_reasons','space_bound_worker_ids','candidate_ids','target_id','same_floor_alias_target_ids','source'],
  remaining_gaps: ['image_code','worker_id','condition','reference_gap','remaining_reasons','minimal_human_question',
    'chosen_target_id','allowed_target_ids','object_id','image_id'],
};

function addTable(name, key, rows = tables[key]) {
  assert(Array.isArray(rows), 'missing table: '+key);
  let fields = [...new Set(rows.flatMap(row => Object.keys(row)))];
  if (!fields.length) fields.push(...(contract.tables?.[key]?.columns ?? []));
  const sourceFields = [...fields];
  if (selectedColumns[key]) fields = selectedColumns[key].filter(field=>sourceFields.includes(field));
  const priority = ['panel','image_code','image','worker_id','condition','building_id','difficulty_class','current_class',
    'scene','doorway_status','oos_subtype','comparison','target_panel_change',
    'analysis_layer','metric','n_peers','value','peer_mean','difference',
    'n_effective_workers','pool_min3_pass','pool_analysis_eligible',
    'ordinary_difficulty_eligible','current_quality_eligible','WQ','A10','B8L2','IoU3D100',
    'active_time_seconds','target_matched_time_seconds','target_time_interpretation',
    'n_records','n_valid','n_missing','mean','median','sd','q25','q75','n_images','n_workers',
    'image_code_a','image_code_b','relation','n_common_workers','n_pairs',
    'paired_a_mean','paired_b_mean','delta_b_minus_a_mean'];
  fields.sort((a,b)=>(priority.includes(a)?priority.indexOf(a):priority.length)-(priority.includes(b)?priority.indexOf(b):priority.length));
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  if (!fields.length) {
    assert.equal(rows.length, 0);
    sheet.getRange('A1:B2').values = [['源表','状态'], [key, '当前0行；字段定义见FIELD_CONTRACT']];
    sheet.getRange('A1:B2').format.columnWidth = 42;
  } else {
    const values = [fields, ...rows.map(row => fields.map(field => clean(row[field])))];
    const used = sheet.getRangeByIndexes(0,0,values.length,fields.length);
    used.values = values;
    used.format = { font: { name: 'Microsoft YaHei', size: 10, color: '#223047' },
                    rowHeight: 42, columnWidth: 18, wrapText: true };
    sheet.getRangeByIndexes(0,0,1,fields.length).format = {
      fill: '#16334C', font: { name: 'Microsoft YaHei', bold: true, color: '#FFFFFF', size: 10 },
      rowHeight: 62, wrapText: true,
    };
    fields.forEach((field,i) => {
      sheet.getRangeByIndexes(0,i,values.length,1).format.columnWidth =
        field==='reason_combination' ? 68 : /layer|relation|target_panel_change/.test(field) ? 30 :
        /source|reference|reason|scope|status|version|exclusion/.test(field) ? 36 :
        /image_id|object_id|inventory_record_id/.test(field) ? 32 : 18;
      if (rows.some(row => typeof row[field] === 'number')) {
        sheet.getRangeByIndexes(1,i,Math.max(1,rows.length),1).setNumberFormat(
          /(^n_|_n$|count|^rows$|columns$)/.test(field) ? '0' : '0.000');
      }
    });
    if (rows.length) {
      sheet.tables.add(used,true,'CurrentStatistics'+checks.sheets.length).showFilterButton = true;
      for (const index of new Set([0,rows.length-1])) {
        assert.deepEqual(sheet.getRangeByIndexes(index+1,0,1,fields.length).values,
                         [fields.map(field => clean(rows[index][field]))], key+' source mismatch');
      }
    }
  }
  sheet.freezePanes.freezeRows(1);
  if (key==='exclusion_intersections') sheet.getRangeByIndexes(1,0,rows.length,fields.length).format.rowHeight = 72;
  checks.sheets.push({name, source_table:key, rows:rows.length, columns:fields,
    omitted_columns:sourceFields.filter(field=>!fields.includes(field))});
  console.log('Built '+name+': '+rows.length);
  return sheet;
}

const guide = workbook.worksheets.add('00_当前口径导读');
guide.showGridLines = false;
guide.getRange('A1:H2').merge();
guide.getRange('A1').values = [['当前研究数据 · 口径核验与描述统计']];
guide.getRange('A1:H2').format = {fill:'#16334C',font:{name:'Microsoft YaHei',size:20,bold:true,color:'#FFFFFF'},rowHeight:26};
const notes = [
  ['版本', '本簿读取当前口径新快照，旧版描述统计及图表另存保留；不将新难度标签套入旧面板。'],
  ['资格优先级', 'GT及既有排除优先；同条件有效真人覆盖按当前审计入口判断，库存不等于可评价样本。'],
  ['分母', '库存、源数据池、可分析作答、已有质量和待处理集合分别列出，集合有交集，不能相加。'],
  ['质量', tables.rescore_comparisons ? '新参考按冻结WQ/A10/B8L2实算，与沿用分数分别留证；不改标注或择高分。未解决的绑定/参考缺口仍为空。' :
    '复用已有分数及明确绑定的参考，需重评分条目保留待办；不为补覆盖挑选参考或高分。'],
  ['难度', '当前难度依据新快照版本；门洞、OOS、范围、可标性保持独立轴。'],
  ['来源采集时长', 'active_time_seconds仅为合格来源池的有效采集秒数；不自动代表新空间或修订目标的耗时。'],
  ['当前目标时长', 'target_matched_time_seconds另表当前稳定目标语境。新目标作答绑定未确认时保持缺失；lead_time不替代。'],
  ['人员解释', '原始均值反映任务组成，不自动作为人员能力排名；新人员资料不足时单列。'],
  ['同房解释', '只使用原记录的直接关系；图对共享人员及视角，不等于独立房间，不由传递关系新增事实。'],
  ['缺失', '空格表示缺失或未确认，不是0分。样本量、分散和缺失随各指标分母读取。'],
  ['查阅方式', '各页有筛选及冻结首行；筛选不会重算预先生成的分组统计。数据更新后重跑统计入口及本构建器。'],
  ['版本', `难度 ${contract.difficulty_version}；WQ ${contract.score_versions.WQ}；A10 ${contract.score_versions.A10}；B8L2 ${contract.score_versions.B8L2}。`],
  ['来源与单位', '原score_version仅WQ绑定上下文；IoU为底面＋均高棱柱(0—100)，同房iou_3d为0—1。historical_*仅审计。'],
  ['明细边界', '同房逐人配对完整长表保留在CSV；本簿提供图对、关系及共同人数。源标注、GT和人工审核未改变。'],
  ...(tables.record_targets ? [
    ['空间展开', '作答×目标表可有多行，但没有新增人员或票数。空间×条件页保留0人来源池，人员数按稳定ID去重。'],
    ['剩余缺口', '逐作答列出未解决参考/绑定及最少人工问题；参考ready、已绑定和统计准入是三层不同状态。'],
  ] : []),
];
guide.getRangeByIndexes(3,0,notes.length,2).values = notes;
guide.getRangeByIndexes(3,1,notes.length,7).merge(true);
guide.getRangeByIndexes(3,1,notes.length,1).values = notes.map(row=>[row[1]]);
guide.getRangeByIndexes(3,0,notes.length,8).format = {font:{name:'Microsoft YaHei',size:10,color:'#223047'},rowHeight:45,wrapText:true};
guide.getRangeByIndexes(3,0,notes.length,1).format = {fill:'#EAF1F6',font:{bold:true,color:'#16334C'}};
guide.getRange('A1:A45').format.columnWidth = 23;
guide.getRange('B1:H45').format.columnWidth = 15;

const specs = [
  ['01_全部库存','inventory_all'], ['02_源池覆盖','source_pools'], ['03_逐条审计','record_audit'],
  ['04_当前图片','current_images'], ['05_可分析作答','analysis_records'], ['06_已有质量','quality_records'],
  ['07_待补人员信息','pending_people'], ['08_待重评分','pending_rescore'],
  ['09_排除原因交集','exclusion_intersections'], ['10_统计概览','overview'],
  ['11_难度分层','by_difficulty'], ['12_人员分层','by_worker'],
  ['13_条件分层','by_condition'], ['14_建筑分层','by_building'], ['15_同房图对','same_room_pairs'],
  ['16_特殊场景','by_scene'], ['17_真人数分布','population_distribution'],
  ['18_逐指标覆盖','metric_coverage'], ['19_共同参考人员对照','peer_comparisons'],
  ['20_同房直接关系','same_room_relations'], ['21_同集合算法差值','algorithm_comparisons'],
  ['22_历史面板增减','historical_panel_changes'],
];
for (const [name,key] of specs) addTable(name,key);
for (const [name,key] of [['23_空间参考目录','space_reference_catalog'],['24_受影响作答状态','affected_records'],
  ['25_作答目标展开','record_targets'],['26_重算历史对照','rescore_comparisons'],
  ['27_空间条件来源池','image_spaces'],['28_剩余缺口','remaining_gaps']]) {
  if (tables[key]) addTable(name,key);
}
addTable((checks.sheets.length+1)+'_工作表索引','sheet_index', checks.sheets.map(item=>({sheet:item.name,source_csv:item.source_table+'.csv',rows:item.rows,columns:item.columns.length,
  omitted_columns:item.omitted_columns.length,note:item.omitted_columns.length?'核心查阅字段；完整列见CSV':'全部字段'})));

const difficultyCounts = new Map();
for (const row of tables.current_images) difficultyCounts.set(row.current_class,(difficultyCounts.get(row.current_class)??0)+1);
const chartTop = notes.length+6;
guide.getRangeByIndexes(chartTop,0,difficultyCounts.size+1,2).values = [['当前难度标签','图片数'],...difficultyCounts];
guide.getRangeByIndexes(chartTop,0,1,2).format = {fill:'#16334C',font:{bold:true,color:'#FFFFFF'}};
const chart = guide.charts.add('bar',guide.getRangeByIndexes(chartTop,0,difficultyCounts.size+1,2));
chart.title = '当前全图难度标签（含未进入分析者）';
chart.hasLegend = false;
chart.xAxis = {axisType:'textAxis'};
chart.yAxis = {numberFormatCode:'0'};
chart.setPosition('D'+(chartTop+1),'J'+(chartTop+15));
checks.formula_errors = (await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',
  options:{useRegex:true,maxResults:20},summary:'当前统计工作簿错误值检查'})).ndjson;
checks.inspection = (await workbook.inspect({kind:'table',range:"'10_统计概览'!A1:F5",include:'values',tableMaxRows:5,tableMaxCols:6})).ndjson;
const names = ['00_当前口径导读',...checks.sheets.map(item=>item.name)];
for (let i=0;i<names.length;i++) {
  const blob = await workbook.render({sheetName:names[i],range:i===0?'A1:H8':'A1:F6',scale:1,format:'png'});
  await fs.writeFile(path.join(previews,String(i).padStart(2,'0')+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
const chartPreview = await workbook.render({sheetName:'00_当前口径导读',range:`A${chartTop+1}:J${chartTop+16}`,scale:1,format:'png'});
await fs.writeFile(path.join(previews,'chart.png'),new Uint8Array(await chartPreview.arrayBuffer()));
const filename = path.join(out,tables.rescore_comparisons ? '现有研究数据描述统计_重评分口径.xlsx' : '现有研究数据描述统计_当前口径.xlsx');
await (await SpreadsheetFile.exportXlsx(workbook)).save(filename);
await fs.rm(filename+'.inspect.ndjson',{force:true});
checks.workbook = filename;
checks.sheet_count = names.length;
checks.preview_directory = previews;
checks.previews_deleted = !process.argv.includes('--keep-previews');
if (checks.previews_deleted) {
  for (const filename of await fs.readdir(previews)) {
    if (/^(\d{2}|chart)\.png$/.test(filename)) await fs.unlink(path.join(previews,filename));
  }
}
await fs.writeFile(path.join(out,'WORKBOOK_VERIFICATION.json'),JSON.stringify(checks,null,2));
console.log(JSON.stringify({workbook:filename,sheets:names.length,previews}));
