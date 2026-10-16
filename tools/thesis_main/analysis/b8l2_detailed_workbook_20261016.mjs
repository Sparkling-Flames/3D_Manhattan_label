// 精选宽表查阅簿；所有统计与资格直接消费details表，不在Excel中推断。
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(path.join(process.cwd(), 'package.json'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const arg = name => process.argv.includes(name) ? process.argv[process.argv.indexOf(name)+1] : undefined;
const source = path.resolve(arg('--source-dir') ?? path.join(root, 'research/statistics/b8l2_usage_v6_20261016/details'));
const tables = JSON.parse(await fs.readFile(path.join(source, 'tables.json'), 'utf8'));
const contract = JSON.parse(await fs.readFile(path.join(source, 'FIELD_CONTRACT.json'), 'utf8'));
const sourceChecks = JSON.parse(await fs.readFile(path.join(source, 'CHECKS.json'), 'utf8'));
const relationAdoptionVersion = contract.relation_adoption_version ?? sourceChecks.relation_adoption_version ??
  contract.room_relation_version ?? sourceChecks.room_relation_version;
const adoptedRooms = Boolean(relationAdoptionVersion);
const workbook = Workbook.create();
const guide = workbook.worksheets.add('00_导读与导航');
const previews = path.join(process.cwd(), 'b8l2_details_workbook_preview_'+path.basename(path.dirname(source))+'_'+path.basename(source));
await fs.mkdir(previews, {recursive:true});
const verification = {source: path.join(source, 'tables.json'), input_version: contract.input_version,
  usage_version: sourceChecks.usage_version, relation_adoption_version: relationAdoptionVersion,
  relation_frozen: sourceChecks.relation_frozen,
  score_version: contract.score_version,
  sheets: [], node_exec_args: process.execArgv};
const metricBlocks = ['B8L2','active_time_seconds','target_matched_time_seconds'];
const statistics = ['n','mean','median','sd','image_equal_mean'];
const commonFields = ['quality_source_time_n','quality_target_time_n'];
const statisticsFields = [...metricBlocks.flatMap(metric=>statistics.map(stat=>metric+'_'+stat)),...commonFields];
const specs = [
  ['01_27人库存','worker_inventory','inventory','每人一行；保留尚未进入分析者。此页是库存/覆盖，不跨条件合并质量均分。'],
  ['02_259图库存','image_inventory','inventory','每张库存图一行；排除、未评分、少人来源池保留定位，不以0分填补。'],
  ['03_人员分条件','worker_condition_stats','statistics','按采集条件分开；每个指标的n独立，原始均值不作人员能力排名；来源层与排除计数另列。'],
  ['04_图片分条件','image_condition_stats','statistics','同图按条件分别报告质量、采集秒和同目标秒；各自有效n及共有n分开。'],
  ['05_人员难度专项','worker_difficulty','statistics','相同人员在难度档内的描述统计；人员、图片和建筑组成不同，不解释为独立难度效应。'],
  ['06_人员特殊轴','worker_special_axes','statistics','门洞、OOS与特殊层按源表分轴；轴之间可重叠，不可相加成为独立样本。'],
  ['07_质量时间共有','time_quality_focus','common','专门展示质量与时间同时有效的集合；共有集合的均值/中位数/SD不替代各指标原始总体。'],
  ['08_关系组总体','room_group_summary','statistics','这是关系证据组统计，不把G号或建筑认证成物理房间；范围/可比性限制继续保留。'],
  ['09_人员关系组','room_worker_groups','statistics','人员×证据组内分条件汇总，只有源表给出的关系与资格，不增补传递关系。'],
  ['10_作答定位','record_lookup','lookup','逐条库存作答定位；过滤排除原因、当前质量空值与时间状态，源标注/人工审核不覆盖。'],
  ['11_关系证据登记','room_group_registry','inventory','原关系、成员与证据登记；组级汇总不等于任意两成员均已直接确认同房。'],
  ['12_组视角贡献','room_group_views','statistics','逐组视图的质量与时间贡献；同一图可出现在不同关系事实中，不直接视为独立房间。'],
  ['13_未关联图片','room_unlinked_images','inventory','尚未关联证据组的图片保留未知身份，不能据此认证异房。'],
  ['14_直接图对总体','room_direct_pair_summary','statistics','已登记的直接图对分条件总体，不借传递闭包补新关系；仍不是独立房间样本。'],
  ['15_覆盖与缺口导航','coverage_matrix','inventory','逐项说明已交付统计、定位入口及缺失资料；不把证据组替代为物理房间真值。'],
  ['16_逐条计算状态','calculation_ledger','calculation','保留完整/仅底面/输入问题/参考或目标未明/失败/未运行。诊断值不等于质量统计可用值。'],
  ['17_27人用途排除','worker_usage_summary','inventory','全库存人员逐人覆盖。完整可算、仅底面与质量可用分别计数；OOS诊断值不进入Q或IoU均值。'],
  ['18_场景计算覆盖','scene_usage','inventory','按源表场景交集与采集条件分别计数；门洞与OOS不合并，未标特殊不能认证普通。'],
  ['19_互斥主原因','worker_primary_reasons','inventory','源台账按预声明优先级为每条作答指定一个主原因；此页主原因互斥，不替代全部命中原因。'],
  ['20_多原因命中','worker_reason_hits','inventory','同条作答可有多个语义命中/原始排除原因；不同原因n不能直接相加成为排除总数。'],
];
if (adoptedRooms) {
  const roomPresentation = {
    room_group_summary:['08_用户工作分组','按用户已审核的分类采用房间工作分组；重叠、范围不同和具体争议按源登记保留，不合并成全库唯一房间。'],
    room_worker_groups:['09_人员×房间分组','人员×已采用房间工作分组，按条件和分析层分别统计；不新增explicit_confirmed或唯一物理ID门槛。'],
    room_group_registry:['11_分类采用登记','逐组保留用户分类、采用版本、成员、重叠、范围和争议；不把全部关系自动改为同房。'],
    room_group_views:['12_分组视角贡献','按已采用工作分组展示各视角贡献；相交组和范围不同的视角不自动合并，不跨组相加。'],
    room_direct_pair_summary:['14_采用关系图对','按采用版本中的图对分类汇总；同房、异房、范围不同和具体争议以源分类为准，不另加确认门槛。'],
    room_unlinked_images:['13_工作组外图片','未进入已拆合工作组的图片仍可有原人工分类；查original_user_group_ids，不把工作组外等同于无分类或异房。'],
    coverage_matrix:['15_覆盖与缺口导航','交付范围和缺口直接采用当前来源表；房间分组沿用用户已审核分类，不另加物理身份准入门槛。'],
  };
  for (const spec of specs) if (roomPresentation[spec[1]]) {
    const [name,note]=roomPresentation[spec[1]]; spec[0]=name; spec[3]=note;
  }
  specs.push(
    ['21_人工原组总体','user_original_group_summary','statistics','全部原始人工组按已有分类描述，包括不支持同房、待定及无当前库存组；不是全部已同房。无观测组n=0、估计留空。'],
    ['22_人员人工原组','user_original_worker_groups','statistics','人员×原始人工组按采集条件和分析层展示；沿源分类，不把原组自动等同于拆合后的房间工作组。'],
    ['23_人工原组登记','room_raw_group_evidence','inventory','逐条保留全部原始人工组、已查看状态、用户物理关系分类与当前库存覆盖；不支持/待定原组不标为已同房。'],
  );
}
const labels = {worker_id:'人员ID',image_code:'图片',image:'图片',condition:'采集条件',analysis_layer:'分析层',
  difficulty_class:'难度',current_class:'当前难度',building_id:'建筑ID',group_id:'证据组ID',room_group_id:'证据组ID',
  candidate_id:'关系候选ID',candidate_ids:'关系候选ID',relation:'关系类型',group_relation:'组关系',
  axis:'分轴',axis_value:'轴状态',special_axis:'特殊轴',special_value:'特殊轴状态',
  n_source_records:'来源记录n',n_source_images:'来源图片n',n_source_workers:'来源人员n',
  quality_source_time_n:'质量与采集时间共有n',quality_target_time_n:'质量与同目标时间共有n',
  object_id:'稳定作答ID',image_id:'稳定图片ID',reference_id:'评分参考ID',current_target_id:'当前目标ID',
  B8L2:'B8L2质量',active_time_seconds:'来源采集秒',target_matched_time_seconds:'同目标秒',
  current_quality_eligible:'当前质量资格',pool_analysis_eligible:'来源分析资格',time_status:'时间状态',
  quality_use:'质量用途',metric_applicability_note:'适用性说明',exclusion_reasons:'排除原因',
  remaining_reasons:'剩余原因',minimal_human_question:'最少人工问题',membership_change:'成员变化'};
Object.assign(labels,{n_inventory_records:'库存作答n',n_inventory_images:'库存图片n',n_inventory_workers:'库存人员n',
  n_quality_records:'完整B8L2记录n',n_excluded_records:'来源排除记录n',n_inventory_usable_time:'库存有效采集时间n',
  n_source_time:'来源采集时间n',n_target_time:'同目标时间n',n_quality_missing:'来源中无完整质量n',
  conditions:'包含的采集条件',source_exclusion_reasons:'来源排除原因',quality_exclusion_reasons:'质量缺失或排除原因',
  comparison_stratum:'比较分层',cell_status:'该格状态',level:'轴状态',relation_tier:'关系证据层',
  group_kind:'关系组类型',physical_room_identity_certified:'物理房间身份已认证',
  n_declared_views:'登记视图n',n_registered_views:'登记视图n',n_current_inventory_views:'当前库存视图n',
  n_current_inventory_records:'当前库存作答n',all_declared_views_have_records:'登记视图均有记录',
  n_quality_workers_all_declared_views:'所有视图共同质量人员n',
  n_source_time_workers_all_declared_views:'所有视图共同采集时间人员n',
  n_target_time_workers_all_declared_views:'所有视图共同目标时间人员n'});
Object.assign(labels,{calculation_status:'实际计算状态',quality_usable:'质量统计可用',
  diagnostic_B8L2:'B8L2诊断值·不入均值',diagnostic_IoU3D100:'IoU诊断值·不入均值',
  full_input_available:'完整输入可用',reference_full_available:'完整参考可用',target_binding_unique:'目标唯一绑定',
  is_doorway:'门洞轴',is_oos:'OOS轴',scene_bucket:'场景交集层',primary_reason:'唯一主原因',
  reason_kind:'原因类型',reason:'命中原因',n_records:'作答n',ratio:'占比',
  n_submissions:'原提交n',n_quality_usable:'质量统计可用n',n_full_diagnostic_available:'完整诊断可算n',
  n_computed_not_quality_usable:'已计算但不入质量n',n_oos_submissions:'OOS提交n',n_oos_full_diagnostic:'OOS完整诊断n',
  n_full_computable_inputs:'输入参考与唯一绑定均可用n',n_full_computed:'完整计算n',n_floor_only_computed:'仅底面计算n',
  n_input_uncomputable:'输入不可计算n',n_pending_target:'目标未明n',n_pending_reference:'参考待补n',
  n_measurement_failed:'测量失败n',n_not_run:'未运行n',n_gt_or_reference_unresolved:'GT或参考未决n'});
if (adoptedRooms) Object.assign(labels,{group_id:'房间工作分组ID',room_group_id:'房间工作分组ID',
  group_kind:'工作分组类型',relation_tier:'原关系分类',physical_room_identity_certified:'历史物理身份记录·非门槛',
  relation_adoption_version:'关系采用版本',room_relation_version:'关系采用版本',
  review_code:'人工原组编号',original_group_id:'原始组ID',viewed:'用户已查看',
  user_physical_classification:'用户物理关系分类',user_classification_adopted:'用户分类已采用',
  raw_current:'原始分类与备注',interpretation:'解释与范围记录'});
for(const condition of ['manual','semi','oos']) for(const [prefix,label] of [['inventory','库存'],['source','来源'],['quality','质量']]) {
  labels[prefix+'_'+condition]=condition+'·'+label+'n';
}
const metricLabels = {B8L2:'B8L2',active_time_seconds:'来源采集秒',target_matched_time_seconds:'同目标秒'};
const statLabels = {n:'有效n',mean:'作答均值',median:'中位数',sd:'样本SD',image_equal_mean:'图片等权均值'};
for (const metric of metricBlocks) for (const stat of statistics) labels[metric+'_'+stat]=metricLabels[metric]+'·'+statLabels[stat];
for (const kind of ['source','target']) for (const variable of ['B8L2','seconds']) for (const stat of ['mean','median','sd']) {
  labels[`quality_${kind}_time_${variable}_${stat}`]=`${kind==='source'?'质量+采集秒':'质量+同目标秒'}共有·${variable==='B8L2'?'B8L2':'秒'}·${statLabels[stat]}`;
}
const clean = value => value===null || value===undefined ? null : typeof value==='object' ? JSON.stringify(value) :
  typeof value==='string' && value.startsWith('=') ? "'"+value : value;
const statisticalSuffix = /_(n|mean|median|sd|q25|q75|image_equal_mean)$/;
function fieldsFor(key, rows, kind) {
  let fields=[...new Set(rows.flatMap(row=>Object.keys(row)))];
  if (!fields.length) fields=contract.tables?.[key]?.columns ?? [];
  if (kind==='statistics') {
    assert(statisticsFields.every(field=>fields.includes(field)),key+' statistical fields missing');
    // 仅筛选显示列，统计值和分母由源表提供。
    const identities=fields.filter(field=>!statisticalSuffix.test(field) &&
      !/points|geometry|polygon|floor_xz|evidence_json|source_manifest/.test(field));
    const idFields=['worker_id','image_code','condition','analysis_layer','comparison_stratum','axis','level',
      'group_id','relation_tier','cell_status'].filter(field=>identities.includes(field));
    fields=[...idFields,...statisticsFields.filter(field=>fields.includes(field)),
      ...identities.filter(field=>!idFields.includes(field))];
  } else if (kind==='common') {
    const ids=['worker_id','condition','comparison_stratum','analysis_layer','cell_status'].filter(field=>fields.includes(field));
    const paired=fields.filter(field=>/^quality_(source|target)_time_(B8L2|seconds)_(mean|median|sd)$/.test(field));
    fields=[...ids,...commonFields.filter(field=>fields.includes(field)),...paired,
      ...fields.filter(field=>!statisticalSuffix.test(field) && !ids.includes(field))];
  } else if (kind==='lookup') {
    const front=['image_code','worker_id','condition','difficulty_class','comparison_stratum','analysis_layer',
      'current_quality_eligible','pool_analysis_eligible','B8L2','active_time_seconds','target_matched_time_seconds','time_status'];
    fields=[...front.filter(field=>fields.includes(field)),...fields.filter(field=>!front.includes(field))];
  } else if (kind==='calculation') {
    const front=['image_code','worker_id','condition','calculation_status','quality_usable',
      'is_doorway','is_oos','full_input_available','reference_full_available','target_binding_unique',
      'diagnostic_B8L2','diagnostic_IoU3D100','quality_exclusion_reasons','calculation_reasons',
      'input_geometry_status','input_geometry_reasons','measurement_reasons','full_score_state',
      'reference_status','primary_reason','current_target_id','reference_version','analysis_layer',
      'B8L2','IoU3D100','diagnostic_floor_iou','floor_input_available','source_condition_oos',
      'pool_analysis_eligible','pool_source_workers','cleaning_disposition','independent_vote_eligible',
      'gt_error_excluded','active_time_seconds','target_matched_time_seconds','time_status',
      'time_source','object_id','image_id','reference_id','source_path','usage_version'];
    fields=front.filter(field=>fields.includes(field));
  } else if (key==='room_raw_group_evidence') {
    const selected=['review_code','original_group_id','user_physical_classification','viewed',
      'user_classification_adopted','n_registered_views','n_current_inventory_views','n_current_inventory_records',
      'review_state','relation_adoption_version','note','image_ids','raw_current','interpretation',
      'source_registry','source_pointer'];
    fields=selected.filter(field=>fields.includes(field));
  } else if (key==='room_group_registry') {
    const selected=['group_id','group_kind','candidate_id','relation_tier','review_state','physical_same_supported',
      'physical_room_identity_certified','n_registered_views','n_current_inventory_views','n_current_inventory_records',
      'source_group_codes','subset_scope','issue_tags','excluded_from_this_subset','overlap_image_ids',
      'source_registry','source_pointer'];
    fields=[...selected.filter(field=>fields.includes(field)),...fields.filter(field=>
      !selected.includes(field) && /adopt|version|overlap|scope|dispute|review|relation|classification|user_/.test(field))];
  }
  return fields.filter(field=>!/points_1024|bottom3d|top3d|floor_xz|current_target_floor|geometry_json|polygon/.test(field));
}
const sheetByKey = new Map();
for (const [name,key,kind,note] of specs) {
  const rows=tables[key]; assert(Array.isArray(rows),'missing table: '+key);
  const fields=fieldsFor(key,rows,kind); assert(fields.length,'empty schema: '+key);
  const sh=workbook.worksheets.add(name); sh.showGridLines=false;
  const titleWidth=Math.min(fields.length,12);
  sh.getRangeByIndexes(0,0,2,titleWidth).merge(); sh.getRange('A1').values=[[name.slice(3)]];
  sh.getRangeByIndexes(0,0,2,titleWidth).format={fill:'#173B50',font:{name:'Microsoft YaHei',size:18,bold:true,color:'#FFFFFF'},rowHeight:23};
  sh.getRangeByIndexes(2,0,2,titleWidth).merge(); sh.getRange('A3').values=[[note]];
  sh.getRangeByIndexes(2,0,2,titleWidth).format={font:{name:'Microsoft YaHei',size:10,color:'#465466'},wrapText:true,rowHeight:22,fill:'#EDF3F6'};
  const values=[fields.map(field=>labels[field]??(field.startsWith('ratio_')?
    (labels['n_'+field.slice(6)]??field.slice(6))+'占比':field)),...rows.map(row=>fields.map(field=>clean(row[field])))];
  const range=sh.getRangeByIndexes(5,0,values.length,fields.length); range.values=values;
  range.format={font:{name:'Microsoft YaHei',size:10,color:'#233344'},rowHeight:32,columnWidth:19,wrapText:true};
  sh.getRangeByIndexes(5,0,1,fields.length).format={fill:'#173B50',font:{bold:true,color:'#FFFFFF'},rowHeight:64};
  if (rows.length) sh.tables.add(range,true,'B8Details'+verification.sheets.length).showFilterButton=true;
  fields.forEach((field,i)=>{
    const column=sh.getRangeByIndexes(5,i,values.length,1);
    column.format.columnWidth=/reason|note|question|evidence|interpretation/.test(field)?44:
      /reference_id|target_id|image_id|object_id|worker_ids|image_ids|members/.test(field)?31:19;
    if (rows.length && rows.some(row=>typeof row[field]==='number')) {
      sh.getRangeByIndexes(6,i,rows.length,1).setNumberFormat(field==='ratio' || field.startsWith('ratio_')?'0.0%':
        /(^n_|_n$|count|records$|images$|workers$)/.test(field)?'0':'0.00');
    }
  });
  sh.freezePanes.freezeRows(6);
  sh.freezePanes.freezeColumns(kind==='statistics' || kind==='common' ? 3 : 1);
  for (const index of new Set([0,rows.length-1])) if(index>=0) {
    assert.deepEqual(sh.getRangeByIndexes(index+6,0,1,fields.length).values,[values[index+1]],key+' source mismatch');
  }
  verification.sheets.push({name,key,rows:rows.length,fields,source_columns:Object.keys(rows[0]??{})});
  sheetByKey.set(key,{sh,fields,rows});
  console.log('Built '+name+': '+rows.length);
}

guide.showGridLines=false;
guide.getRange('A1:L2').merge(); guide.getRange('A1').values=[[adoptedRooms?
  'B8L2细致统计 · 人员、图片与用户房间工作分组':'B8L2细致统计 · 人员、图片与关系证据组']];
guide.getRange('A1:L2').format={fill:'#173B50',font:{name:'Microsoft YaHei',size:19,bold:true,color:'#FFFFFF'},rowHeight:25};
const notes=[
  ['主指标','采用冻结WQ-B8L2-20261015；本簿只展示已计算统计，不重评分、不调参。'],
  ['库存与质量','库存人员/图片保留排除与空分位置；条件统计另页，不把库存n当完整质量n。'],
  ['每格分母','B8L2、来源采集秒、同目标秒分别列有效n、均值、中位数、样本SD；缺失不填0。'],
  ['共有集合','quality_source_time_n与quality_target_time_n是质量-时间共有集合；第07页展示共同集合下质量与秒数的分布。'],
  ['房间口径',adoptedRooms?`采用用户已审核分类（${relationAdoptionVersion}）；按已采用工作分组统计，不追加显式确认或唯一物理ID门槛。重叠、范围差异及具体争议保留。`:
    '关系证据组与物理房间不同；G号、建筑和传递连通都不能单独证明同房。未关联不等于异房。'],
  ['时间边界','来源采集时间不自动代表新空间作答时间；lead_time不替代有效秒；外推顶部不能变成完整质量。'],
  ['人员解释','同一人员的任务组成、条件和关系组不同，原始平均不作能力排名，也不推断时间因果。'],
  ['用途与诊断','门洞单列统计；OOS即使可算也只作诊断，不进入Q/IoU均值。计算成功与最终统计准入分别查台账。'],
  ['原因分母','第19页是互斥主原因；第20页是可重叠命中。不能把多原因命中直接相加成排除总数。'],
  ['筛选方式','各表从第6行开始，筛选与冻结保留；筛选不会重算离线统计。完整字段与来源见details的字段合同/CSV。'],
  ['来源',`字段合同版本：${contract.version}；难度：${contract.difficulty_version??sourceChecks.difficulty_version}；表值全部来自同目录tables.json。`],
];
notes.forEach(([title,note],i)=>{
  const row=i+4; guide.getRange(`A${row}:B${row}`).merge(); guide.getRange(`C${row}:L${row}`).merge();
  guide.getRange(`A${row}`).values=[[title]]; guide.getRange(`C${row}`).values=[[note]];
});
guide.getRangeByIndexes(3,0,notes.length,12).format={font:{name:'Microsoft YaHei',size:10,color:'#233344'},wrapText:true,rowHeight:36,columnWidth:12};
guide.getRangeByIndexes(3,0,notes.length,2).format={fill:'#EDF3F6',font:{bold:true,color:'#173B50'}};
const nav=[['查阅页','来源表','行数'],...verification.sheets.map(item=>[item.name,item.key+'.csv',item.rows])];
const navTop=notes.length+5;
guide.getRangeByIndexes(navTop,0,nav.length,3).values=nav;
guide.getRangeByIndexes(navTop,0,1,3).format={fill:'#173B50',font:{bold:true,color:'#FFFFFF'}};
guide.getRangeByIndexes(navTop,0,nav.length,3).format.columnWidth=32;
const workerSheet=sheetByKey.get('worker_inventory');
const workerField=workerSheet.fields.indexOf('worker_id');
const qualityField=workerSheet.fields.indexOf('n_quality_records');
assert(workerField>=0 && qualityField>=0,'worker chart source fields missing');
const chartRow=navTop+nav.length+2;
guide.getRangeByIndexes(chartRow,0,1,2).values=[['库存人员ID','完整B8L2记录数']];
// 库存人员页只提供计数，图中没有合并不同条件的质量均分。
const letter = index => {let value=index+1,out='';while(value){const r=(value-1)%26;out=String.fromCharCode(65+r)+out;value=Math.floor((value-1)/26);}return out;};
guide.getRangeByIndexes(chartRow+1,0,workerSheet.rows.length,2).formulas=workerSheet.rows.map((row,i)=>[
  `='${workerSheet.sh.name}'!${letter(workerField)}${i+7}`,
  `='${workerSheet.sh.name}'!${letter(qualityField)}${i+7}`]);
const chart=guide.charts.add('bar',guide.getRangeByIndexes(chartRow,0,workerSheet.rows.length+1,2));
chart.title='库存人员的完整质量覆盖（保持ID顺序，非排名）'; chart.hasLegend=false;
chart.xAxis={axisType:'textAxis'};chart.yAxis={numberFormatCode:'0'};
chart.setPosition('D'+(chartRow+1),'O'+(chartRow+19));
verification.formula_errors=(await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',
  options:{useRegex:true,maxResults:20},summary:'精选宽表公式错误检查'})).ndjson;
assert(!/"value":"#(REF!|DIV\/0!|VALUE!|NAME\?|N\/A)/.test(verification.formula_errors));
for(const [i,name] of ['00_导读与导航',...specs.map(row=>row[0])].entries()){
  const blob=await workbook.render({sheetName:name,range:i===0?`A1:L${notes.length+3}`:'A1:L11',scale:1,format:'png'});
  await fs.writeFile(path.join(previews,String(i).padStart(2,'0')+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
const chartPreview=await workbook.render({sheetName:'00_导读与导航',range:`D${chartRow+1}:O${chartRow+20}`,scale:1,format:'png'});
await fs.writeFile(path.join(previews,'chart.png'),new Uint8Array(await chartPreview.arrayBuffer()));
const timePreview=await workbook.render({sheetName:'03_人员分条件',range:'I6:T11',scale:1,format:'png'});
await fs.writeFile(path.join(previews,'time_statistics.png'),new Uint8Array(await timePreview.arrayBuffer()));
const filename=path.join(source,'B8L2细致统计_人员图片与关系组.xlsx');
await (await SpreadsheetFile.exportXlsx(workbook)).save(filename);
await fs.rm(filename+'.inspect.ndjson',{force:true});
verification.workbook=filename;verification.sheet_count=specs.length+1;
verification.preview_directory=previews;verification.previews_deleted=false;
await fs.writeFile(path.join(source,'DETAILS_WORKBOOK_VERIFICATION.json'),JSON.stringify(verification,null,2));
console.log(JSON.stringify({workbook:filename,sheets:specs.length+1,previews}));
