// 从已生成的描述统计表制作静态查阅工作簿；运行目录须能解析artifact-tool。
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(path.join(process.cwd(), 'package.json'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const out = path.join(root, 'research/descriptive_statistics_20261015');
const input = path.join(out, 'tables.json');
const tables = JSON.parse(await fs.readFile(input, 'utf8'));
console.log('Loaded statistics tables');
const workbook = Workbook.create();
const checks = { source: 'research/descriptive_statistics_20261015/tables.json', sheets: [] };
const previews = path.join(process.cwd(), 'statistics_workbook_preview');
await fs.mkdir(previews, { recursive: true });

assert.equal(tables.records.length, 3152);
assert.equal(tables.images.length, 259);
assert.equal(tables.records.filter(r => r.in_worker_931).length, 931);
assert.equal(tables.records.filter(r => r.in_target_836).length, 836);
assert.equal(tables.records.filter(r => r.WQ !== null).length, 1145);
assert(tables.records.every(r => r.difficulty_class), 'inventory difficulty missing');
const clean = value => value === undefined || value === null ? null :
  typeof value === 'object' ? JSON.stringify(value) :
  typeof value === 'string' && value.startsWith('=') ? "'" + value : value;
const summaryColumns = ['panel', 'metric', 'n_records', 'n_valid', 'n_missing', 'n_images',
  'n_workers', 'n_valid_images', 'n_valid_references', 'mean', 'median', 'sd', 'q25', 'q75', 'image_equal_mean'];

function sheet(name, key, fields, { rows = tables[key], note = '' } = {}) {
  assert(Array.isArray(rows), `missing input table: ${key}`);
  const s = workbook.worksheets.add(name);
  const selected = (fields ?? Object.keys(rows[0] ?? {})).filter(f => rows.length === 0 || f in rows[0]);
  assert(selected.length > 0, name);
  assert(rows.length === 0 || selected.every(f => f in rows[0]), `missing field in ${key}`);
  const matrix = [selected, ...rows.map(r => selected.map(c => clean(r[c])))];
  s.getRangeByIndexes(0, 0, matrix.length, selected.length).values = matrix;
  const used = s.getRangeByIndexes(0, 0, matrix.length, selected.length);
  used.format.font = { name: 'Microsoft YaHei', size: 10, color: '#223047' };
  used.format.rowHeight = 21;
  used.format.columnWidth = 16;
  s.getRangeByIndexes(0, 0, 1, selected.length).format = {
    fill: '#16334C', font: { name: 'Microsoft YaHei', bold: true, color: '#FFFFFF', size: 10 },
    rowHeight: 64, wrapText: true,
  };
  selected.forEach((c, i) => {
    const col = s.getRangeByIndexes(0, i, matrix.length, 1);
    col.format.columnWidth = /markability/.test(c) ? 48 : /use_panel|axis_value/.test(c) ? 40 :
      /status/.test(c) ? 34 : /note/.test(c) ? 44 : /reference|source_path|evidence/.test(c) ? 36 :
      /image_id|object_|target_id/.test(c) ? 31 : /panel|metric|axis|status|class|relation|use_panel/.test(c) ? 26 : 16;
    if (rows.some(r => typeof r[c] === 'number')) {
      s.getRangeByIndexes(1, i, Math.max(1, rows.length), 1).setNumberFormat(
        /(^n_|_n$|count|records|workers|images|^rows$|^columns$)/.test(c) ? '0' : '0.000');
    }
  });
  if (rows.length) {
    const table = s.tables.add(s.getRangeByIndexes(0, 0, matrix.length, selected.length), true,
      'Statistics' + checks.sheets.length);
    table.showFilterButton = true;
  }
  s.freezePanes.freezeRows(1);
  s.showGridLines = false;
  for (const index of new Set(rows.length ? [0, rows.length-1] : [])) {
    assert.deepEqual(s.getRangeByIndexes(index+1, 0, 1, selected.length).values,
      [selected.map(c => clean(rows[index][c]))], name + ' source value mismatch');
  }
  checks.sheets.push({ name, source_table: key, rows: rows.length, columns: selected,
    source_rows: tables[key]?.length ?? rows.length, note });
  console.log('Built ' + name + ': ' + rows.length);
  return s;
}
function summary(name, key, dims = []) {
  let rows = tables[key];
  let note = '';
  if (rows.length > 2000) {
    rows = rows.filter(r => ['WQ', 'A10', 'B8L2', 'IoU3D100', 'active_time_seconds'].includes(r.metric));
    note = '仅五种核心指标；全部十种指标见源CSV';
  }
  if (['worker_building', 'worker_room_type'].includes(key)) {
    rows = rows.filter(r => ['worker_931', 'target_836'].includes(r.panel));
    note += '；仅931/836面板';
  }
  return sheet(name, key, [...summaryColumns.slice(0, 1), ...dims, ...summaryColumns.slice(1)], { rows, note });
}

const guide = workbook.worksheets.add('00_中文导读');
guide.showGridLines = false;
guide.getRange('A1:H2').merge();
guide.getRange('A1').values = [['现有研究数据 · 描述统计查阅簿']];
guide.getRange('A1:H2').format = { fill: '#16334C', font: { name: 'Microsoft YaHei', size: 20, bold: true, color: '#FFFFFF' }, rowHeight: 24 };
const notes = [
  ['用途', '静态描述统计；筛选与排序不重算分组统计。更新数据后重跑Python生成表与本工作簿入口。'],
  ['3152库存', '所有已有作答；包含未评分、特殊、例外与时间缺失记录，不等于有效质量样本。'],
  ['1145评分', '原WQ、A10、B8L2、同参考均高棱柱IoU的相同输入集合，数值存在不等于已获主分析资格。'],
  ['931人员面板', '旧固定参考下的普通manual主画像；含54条仅底面等价和41条与当前难度目标不同。'],
  ['836同目标面板', '931中的普通同难度目标子集；主要难度和同房质量条件描述使用此集合。'],
  ['WQ / A10 / B8L2', 'WQ-LS08-20261014 / WQ-A10-20261015 / WQ-B8L2-20261015。三者均0—100分，用户尚未选定唯一最终公式。'],
  ['IoU单位', '主表IoU3D100为0—100；同房表metric=iou_3d时为0—1。现用口径是底面＋均高棱柱。'],
  ['分项', 'iou_2d底面IoU(0—1)；S_bottom_deg底边球面距离(度)；dir自身正交方向RMS(度)；Hmean/Hcenter为参考相对高度误差。'],
  ['时间', 'active_time_seconds为有效标注秒数；raw_active_time_seconds仅为历史原数值。lead_time、已知加秒及未冻结新采集时间不进入有效时间。'],
  ['缺失与分母', '空格=缺失，不是0或低质量。n_records为集合条数，n_valid为该指标有效条数，n_missing为缺失条数。'],
  ['分布', 'mean/median/sd/q25/q75为均值/中位数/样本标准差/四分位数；image_equal_mean先图内均值再图片等权。'],
  ['未知状态', 'unknown/not_recorded不能当否定；范围、可标性、门洞、OOS、难度分别保留。top_boundary_pending空值不自动视作False。'],
  ['人员解释', '原始均分反映任务组成，不是能力排名。同参考相对表现见人员共同参考页，样本很少时不推出人员类别。'],
  ['同房解释', '只保留已记录直接关系；关系表包含候选/未充分确认，主解读先筛relation=confirmed_comparable。未记录同房不等于确认异房。'],
  ['共同人员', 'paired_*及delta仅用指标双侧有效的共同人员；视角差异也包含各图范围/可见条件差异，不作视角因果效应。'],
  ['底面与完整参考', '仅底面等价不能把旧完整WQ嫁接新顶部；931同房旧参考表与836同目标表分开。'],
  ['长表查阅', '大长表仅WQ/A10/B8L2/IoU/时间；人员×建筑/房间粗类仅931/836；省略peer逐作答细表。全部指标、面板和明细见CSV。'],
  ['版本与来源', 'FIELD_CONTRACT.json为口径；SAME_ROOM_NOTES.md为同房补充说明；各sheet源表见末页工作表索引。原标注、GT与人工审核未改。'],
];
guide.getRangeByIndexes(3, 0, notes.length, 2).values = notes;
guide.getRange('A4:A21').format = { font: { name: 'Microsoft YaHei', bold: true, color: '#16334C' }, fill: '#EAF1F6', wrapText: true };
guide.getRange('B4:H21').merge(true);
guide.getRange('B4:B21').values = notes.map(r => [r[1]]);
guide.getRange('A4:H21').format.rowHeight = 42;
guide.getRange('B4:H21').format.wrapText = true;
guide.getRange('A1:A24').format.columnWidth = 22;
guide.getRange('B1:H24').format.columnWidth = 15;
guide.freezePanes.freezeRows(3);

summary('01_全指标概览', 'overview');
sheet('02_259图条件', 'images', ['image_code', 'difficulty_class', 'special_layer', 'oos_axis',
  'doorway_axis', 'markability_from_explicit_label', 'all_answer_count', 'joint_quality_count',
  'room_coarse_type', 'conditional_difficulty', 'difficulty_oos_subtype', 'live_oos_status', 'doorway_status',
  'oos_status_discrepancy', 'top_boundary_pending', 'image_id', 'target_id', 'difficulty_version']);
sheet('03_3152作答筛选', 'records', ['image_code', 'worker_id', 'condition', 'difficulty_class',
  'use_panel', 'WQ', 'A10', 'B8L2', 'IoU3D100', 'active_time_seconds', 'time_status',
  'in_worker_931', 'in_target_836', 'special_layer', 'oos_axis', 'doorway_axis',
  'target_floor_relation', 'new_scope_binding_pending', 'top_boundary_pending', 'ledger_score_status',
  'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'building_id', 'room_id', 'room_coarse_type',
  'record_id', 'object_id', 'image_id', 'reference_id', 'difficulty_target_id', 'score_version',
  'ledger_reference_id', 'ledger_iou_2d', 'ledger_S_bottom_deg', 'ledger_dir', 'ledger_floor_WQ',
  'raw_active_time_seconds', 'time_source', 'time_source_file', 'time_rule_version',
  'project_id', 'runtime_task_id', 'raw_annotation_id', 'source_path']);
summary('04_逐图质量时间', 'by_image', ['image_code']);
summary('05_逐人质量时间', 'by_worker', ['worker_id']);
summary('06_建筑', 'by_building', ['building_id']);
summary('07_粗难度', 'by_difficulty', ['difficulty_class']);
summary('08_特殊场景分轴', 'by_scene', ['axis', 'axis_value']);
sheet('09_场景交集', 'scene_intersections');
summary('10_采集条件', 'by_condition', ['condition']);
summary('11_消费层', 'by_use', ['use_panel']);
summary('12_时间来源状态', 'by_time_status', ['time_status']);
summary('13_人员乘难度', 'worker_difficulty', ['worker_id', 'difficulty_class']);
summary('14_人员乘建筑', 'worker_building', ['worker_id', 'building_id']);
summary('15_人员乘场景', 'worker_scene', ['axis', 'worker_id', 'axis_value']);
summary('16_共同集合评分差', 'score_comparison', ['comparison']);
summary('17_人员共同参考', 'worker_peer_comparison', ['worker_id', 'original_metric']);
sheet('18_时间质量关联', 'time_quality');
const relationColumns = ['image_code_a', 'image_code_b', 'relation', 'n_records_a', 'n_records_b',
  'n_common_workers', 'n_only_a', 'n_only_b', 'physical_same_supported',
  'physical_same_explicit_confirmed', 'building_a', 'building_b', 'image_a', 'image_b',
  'candidate_ids', 'reference_ids_a', 'reference_ids_b', 'use_panels_a', 'use_panels_b'];
const pairColumns = ['image_code_a', 'image_code_b', 'relation', 'metric', 'n_records_a', 'n_records_b',
  'n_common_workers', 'n_pairs', 'n_missing_all_a', 'n_missing_all_b', 'n_unpaired_common',
  'all_a_mean', 'all_b_mean', 'paired_a_mean', 'paired_b_mean', 'delta_b_minus_a_mean',
  'delta_b_minus_a_median', 'delta_b_minus_a_sd', 'delta_b_minus_a_q25', 'delta_b_minus_a_q75',
  'absolute_paired_delta_mean', 'image_a', 'image_b', 'reference_ids_a', 'reference_ids_b'];
const workerPairColumns = ['image_code_a', 'image_code_b', 'relation', 'worker_id', 'metric',
  'value_a', 'value_b', 'paired', 'delta_b_minus_a', 'object_uid_a', 'object_uid_b',
  'reference_id_a', 'reference_id_b', 'use_panel_a', 'use_panel_b'];
for (const [suffix, prefix] of [['', '19'], ['_931', '22']]) {
  const base = Number(prefix), label = suffix ? '旧931' : '主836';
  sheet(`${base}_同房关系${label}`, 'same_room_relations'+suffix, relationColumns);
  sheet(`${base+1}_同房图对${label}`, 'same_room_pair_metrics'+suffix, pairColumns);
  sheet(`${base+2}_同房共同人${label}`, 'same_room_worker_pairs'+suffix, workerPairColumns);
}

// 静态计数为既有研究标签的描述，Excel图表直接绑定可查阅的源单元格。
const counts = new Map();
for (const r of tables.images) counts.set(r.difficulty_class, (counts.get(r.difficulty_class) ?? 0)+1);
guide.getRange('A24:B24').values = [['原259图粗类', '图片数']];
guide.getRangeByIndexes(24, 0, counts.size, 2).values = [...counts];
guide.getRange('A24:B24').format = { fill: '#16334C', font: { bold: true, color: '#FFFFFF' } };
const chart = guide.charts.add('bar', guide.getRangeByIndexes(23, 0, counts.size+1, 2));
chart.title = '259图粗类覆盖（张）';
chart.hasLegend = false;
chart.xAxis = { axisType: 'textAxis' };
chart.yAxis = { numberFormatCode: '0' };
chart.setPosition('D24', 'I38');
summary('25_房间功能粗类', 'by_room_type', ['room_coarse_type']);
summary('26_人员乘房间粗类', 'worker_room_type', ['worker_id', 'room_coarse_type']);
summary('27_原评分账本状态', 'by_ledger_status', ['ledger_score_status']);
summary('28_难度场景交集', 'by_scene_intersections', ['difficulty_class', 'oos_axis', 'doorway_axis']);
sheet('29_同房独立manual时间', 'same_room_pair_metrics_manual_inventory', pairColumns,
  { rows: tables.same_room_pair_metrics_manual_inventory.filter(r => r.metric === 'active_time_seconds'),
    note: '2193独立manual库存时间补充；不要求具备WQ，不与836/931合并。' });
sheet('30_同房独立manual共同人', 'same_room_worker_pairs_manual_inventory', workerPairColumns,
  { rows: tables.same_room_worker_pairs_manual_inventory.filter(r => r.metric === 'active_time_seconds') });
if (tables.ledger_metric_coverage) sheet('31_账本分项覆盖', 'ledger_metric_coverage');
sheet('32_工作表索引', '__index', ['sheet', 'source_csv', 'rows', 'columns', 'note'], {
  rows: checks.sheets.map(r => ({ sheet: r.name, source_csv: r.source_table+'.csv', rows: r.rows,
    columns: r.columns.length, note: r.note || '静态描述；完整字段见同目录CSV' })),
});

for (const item of checks.sheets) {
  const s = workbook.worksheets.getItem(item.name);
  const first = s.getRangeByIndexes(0, 0, Math.min(3, item.rows+1), Math.min(4, item.columns.length)).values;
  assert.deepEqual(first[0], item.columns.slice(0, 4));
  item.header_checked = true;
}
checks.inspection = (await workbook.inspect({ kind: 'table', range: "'01_全指标概览'!A1:F5",
  include: 'values', tableMaxRows: 5, tableMaxCols: 6 })).ndjson;
checks.formula_errors = (await workbook.inspect({ kind: 'match',
  searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',
  options: { useRegex: true, maxResults: 20 }, summary: '工作簿错误值检查' })).ndjson;
const names = ['00_中文导读', ...checks.sheets.map(r => r.name)];
for (let i = 0; i < names.length; i++) {
  const image = await workbook.render({ sheetName: names[i],
    range: i === 0 ? 'A1:H10' : 'A1:F7', scale: 1, format: 'png' });
  await fs.writeFile(path.join(previews, String(i).padStart(2, '0')+'.png'),
    new Uint8Array(await image.arrayBuffer()));
}
const chartPreview = await workbook.render({ sheetName: '00_中文导读', range: 'A23:I39', scale: 1, format: 'png' });
await fs.writeFile(path.join(previews, 'chart.png'), new Uint8Array(await chartPreview.arrayBuffer()));
const filename = path.join(out, '现有研究数据描述统计.xlsx');
console.log('Exporting workbook');
await (await SpreadsheetFile.exportXlsx(workbook)).save(filename);
await fs.rm(filename + '.inspect.ndjson', { force: true });
checks.workbook = path.relative(root, filename).replaceAll('\\', '/');
checks.sheet_count = names.length;
checks.preview_count = names.length + 1;
checks.preview_directory = previews;
checks.source_size_bytes = (await fs.stat(input)).size;
checks.workbook_size_bytes = (await fs.stat(filename)).size;
checks.raw_records = tables.records.length;
checks.inventory_difficulty_complete = true;
checks.units = { IoU3D100: '0—100', iou_3d: '0—1', active_time_seconds: 'seconds' };
checks.value_self_checks = 'first and last source rows of every exported data table';
checks.large_summary_filter = { threshold_rows: 2000,
  metrics: ['WQ', 'A10', 'B8L2', 'IoU3D100', 'active_time_seconds'],
  personnel_building_and_room_panels: ['worker_931', 'target_836'],
  full_data: 'source CSV files and tables.json' };
if (!process.argv.includes('--keep-previews')) {
  for (const name of await fs.readdir(previews)) {
    if (/^(\d{2}|chart)\.png$/.test(name)) await fs.unlink(path.join(previews, name));
  }
  checks.previews_deleted = true;
} else checks.previews_deleted = false;
await fs.writeFile(path.join(out, 'WORKBOOK_VERIFICATION.json'), JSON.stringify(checks, null, 2));
console.log(JSON.stringify({ workbook: filename, sheets: names.length, previews, bytes: checks.workbook_size_bytes }));
