import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "file:///C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function colName(index) {
  let value = index + 1;
  let result = "";
  while (value) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

const inputDir = path.resolve(arg("--input-dir", "analysis_results/annotation_research_decision_audit_20260905_v1"));
const inventoryDir = path.join(inputDir, "inventory");
const output = path.resolve(arg("--output", path.join(inputDir, "研究数据审计与50张候选审查.xlsx")));
const previewDir = path.join(os.tmpdir(), "annotation_research_decision_workbook_20260905");

async function readJson(file) {
  return JSON.parse(await fs.readFile(file, "utf8"));
}

async function readCsvValues(file) {
  const imported = await Workbook.fromCSV(await fs.readFile(file, "utf8"), { sheetName: "导入" });
  const values = imported.worksheets.getItem("导入").getUsedRange().values.map((row) => row.map((value) => value ?? ""));
  if (values.length) values[0][0] = String(values[0][0]).replace(/^\uFEFF/, "");
  return values;
}

function typedCell(header, value) {
  const text = String(value ?? "").trim();
  if (text === "true" || text === "True") return true;
  if (text === "false" || text === "False") return false;
  const textual = /(?:_id|_path|sha256|status|reason|note|scope|role|source|field|tag|question|scene|reference|verdict|mapping|pool|layer|condition|stage|split|format|kind|type|basis|policy|interpretation)/i.test(header);
  return !textual && /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(text) ? Number(text) : value;
}

function records(values) {
  if (!values.length) return [];
  const headers = values[0].map((value) => String(value ?? ""));
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""])));
}

function selectRows(rows, fields) {
  return [fields, ...rows.map((row) => fields.map((field) => row[field] ?? ""))];
}

function summaryRows(rows) {
  if (!rows.length) return [];
  const fields = Object.keys(rows[0]).filter((field) => !/(?:_json$|image_ids|task_ids)/i.test(field));
  return selectRows(rows, fields);
}

function addTitle(sheet, title, subtitle, width) {
  sheet.showGridLines = false;
  const span = Math.max(width, 5);
  const titleRange = sheet.getRangeByIndexes(0, 0, 1, span);
  titleRange.merge();
  titleRange.values = [[title]];
  titleRange.format = { fill: "#17365D", rowHeight: 36, font: { name: "Microsoft YaHei", size: 16, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
  const subtitleRange = sheet.getRangeByIndexes(1, 0, 1, span);
  subtitleRange.merge();
  subtitleRange.values = [[subtitle]];
  subtitleRange.format = { fill: "#D9EAF7", rowHeight: 45, font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#17365D" }, wrapText: true, verticalAlignment: "center" };
  sheet.freezePanes.freezeRows(2);
}

function writeTable(sheet, startRow, startCol, values, title) {
  if (!values.length) return startRow;
  const width = values[0].length;
  if (title) {
    sheet.getRangeByIndexes(startRow, startCol, 1, width).values = [[title, ...Array(Math.max(width - 1, 0)).fill("")]];
    sheet.getRangeByIndexes(startRow, startCol, 1, width).format = { fill: "#5B9BD5", font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#FFFFFF" }, rowHeight: 24 };
    startRow += 1;
  }
  const typed = values.map((row, rowIndex) => row.map((value, column) => rowIndex === 0 ? String(value ?? "") : typedCell(String(values[0][column] ?? ""), value)));
  const range = sheet.getRangeByIndexes(startRow, startCol, typed.length, width);
  range.values = typed;
  range.format.font = { name: "Microsoft YaHei", size: 9, color: "#1F2937" };
  range.format.verticalAlignment = "center";
  sheet.getRangeByIndexes(startRow, startCol, 1, width).format = { fill: "#4472C4", font: { name: "Microsoft YaHei", size: 9, bold: true, color: "#FFFFFF" }, wrapText: true, rowHeight: 32, verticalAlignment: "center", borders: { preset: "all", style: "thin", color: "#D8E2EC" } };
  if (typed.length > 1) sheet.getRangeByIndexes(startRow + 1, startCol, typed.length - 1, width).format.borders = { preset: "all", style: "thin", color: "#E5E7EB" };
  for (let column = 0; column < width; column += 1) {
    const header = String(values[0][column] ?? "");
    const samples = values.slice(0, 80).map((row) => String(row[column] ?? ""));
    const longText = /path|note|question|scene|reference|tag|field|policy|interpretation|reason|status|verdict|mapping|source/i.test(header);
    const maxLength = Math.max(header.length, ...samples.map((value) => value.length));
    const cells = sheet.getRangeByIndexes(startRow, startCol + column, typed.length, 1);
    cells.format.columnWidth = longText ? Math.min(42, Math.max(18, Math.min(maxLength + 2, 42))) : Math.min(28, Math.max(9, Math.min(maxLength + 2, 28)));
    if (longText) cells.format.wrapText = true;
    if (/count|rows|number|mapped|unmapped|selected|workers|buildings|image_count/i.test(header)) cells.format.numberFormat = "0";
    if (/rate|probability|difference|iou|error|mean|median|gain/i.test(header)) cells.format.numberFormat = "0.0000";
  }
  const tallTextTable = values[0].some((header) => /note|scene|question|reference|hohonet|bi|advisory|tags|verdict/i.test(String(header)));
  if (tallTextTable) {
    for (let rowIndex = 1; rowIndex < typed.length; rowIndex += 1) {
      const maxLength = Math.max(...typed[rowIndex].map((value) => String(value ?? "").length));
      const height = Math.min(96, Math.max(30, 18 + Math.ceil(maxLength / 90) * 14));
      const row = sheet.getRangeByIndexes(startRow + rowIndex, startCol, 1, width);
      row.format.wrapText = true;
      row.format.rowHeight = height;
    }
  }
  return startRow + typed.length + 2;
}

function addSheet(workbook, name, title, subtitle, blocks) {
  const firstWidth = Math.max(...blocks.map((block) => block.values[0]?.length || 1), 5);
  const sheet = workbook.worksheets.add(name);
  addTitle(sheet, title, subtitle, firstWidth);
  let cursor = 3;
  for (const block of blocks) cursor = writeTable(sheet, cursor, 0, block.values, block.title);
  return sheet;
}

const qa = await readJson(path.join(inventoryDir, "QA.json"));
const dataAuditDir = path.join(inputDir, "data_audit");
const dataAuditQa = await readJson(path.join(dataAuditDir, "QA.json"));
const coverage = records(await readCsvValues(path.join(inventoryDir, "building_asset_coverage.csv")));
const assets = records(await readCsvValues(path.join(inventoryDir, "prescreen_asset_audit.csv")));
const catalog = records(await readCsvValues(path.join(inventoryDir, "package_catalog.csv")));
const references = records(await readCsvValues(path.join(inventoryDir, "reference_link_audit.csv")));
const mappings = records(await readCsvValues(path.join(inventoryDir, "room_region_mapping_audit.csv")));
const mappingRecords = records(await readCsvValues(path.join(inventoryDir, "room_region_mapping_records.csv")));
const modelAssets = records(await readCsvValues(path.join(inventoryDir, "model_asset_summary.csv")));
const ai = records(await readCsvValues(path.join(inputDir, "review50/ai_visual_advisory.csv")));

const dataAuditSpecs = [
  ["full_stage_condition_support_summary.csv", "全历史阶段×条件支持"],
  ["full_high_support_k15_20_summary.csv", "全历史高支持 k15/k20"],
  ["three_path_coverage_and_matched_images.csv", "三路径覆盖与匹配图像"],
  ["old_vs_recomputed.csv", "旧值与复算值"],
  ["independence_sensitivity_summary.csv", "独立性敏感性汇总"],
];
const dataAuditTables = [];
for (const [file, title] of dataAuditSpecs) {
  try {
    const rows = records(await readCsvValues(path.join(dataAuditDir, file)));
    dataAuditTables.push({ file, title, rows, values: summaryRows(rows) });
  } catch {
    // The optional data_audit package may not exist in a partial audit export.
  }
}
const oldVsRecomputed = dataAuditTables.find((table) => table.file === "old_vs_recomputed.csv")?.rows || [];
const coverageAuditRows = records(await readCsvValues(path.join(dataAuditDir, "recomputed_uncertainty_substrate/COVERAGE_AUDIT.csv")));
const coverageAudit = Object.fromEntries(coverageAuditRows.map((row) => [row.check_name, row]));
const stageConditionSupport = dataAuditTables.find((table) => table.file === "full_stage_condition_support_summary.csv")?.rows || [];

const recomputedValue = (metric) => oldVsRecomputed.find((row) => row.metric === metric)?.recomputed_value || "";
const auditObserved = (check) => coverageAudit[check]?.observed || "";
const fullHistoricalRows = [
  ["全历史口径", "数量", "来源/解释"],
  ["canonical 历史记录", recomputedValue("substrate_canonical_annotations"), "data_audit/old_vs_recomputed.csv；不是预筛图像层"],
  ["raw annotation versions", recomputedValue("substrate_raw_annotation_versions"), "包含 raw-only versions；不等同独立分析单位"],
  ["历史图像", auditObserved("image_count"), "COVERAGE_AUDIT；以 base-task/image identity 计"],
  ["历史 worker（人）", auditObserved("worker_count"), "COVERAGE_AUDIT；保留所有 observed workers"],
  ["历史 building", auditObserved("building_count"), "COVERAGE_AUDIT；由 image prefix identity 汇总"],
  ["严格几何可计算记录（全量）", dataAuditQa.coverage.human_strict_annotation_count, "data_audit/QA.json coverage；旧值核对表中的 1013 仅属于旧42复算子集"],
];
const stageConditionIndexRows = [
  ["stage", "condition", "canonical records / image units"],
  ...stageConditionSupport.map((row) => [row.stage, row.condition, `${row.canonical_annotation_count} / ${row.image_unit_count}`]),
];

const countRows = [
  ["分母/层", "数量", "解释"],
  ["全量 machine manifest", qa.count_checks.machine_manifest_items, "prescreen machine manifest；当前可读成员，不等同正式准入"],
  ["预筛中有历史记录的图像", qa.count_checks.history_existing_148, "预筛 machine manifest 的图像层分层；不代表全历史 2501 条记录"],
  ["无现有 annotation record", qa.count_checks.no_existing_annotation_166, "从 machine manifest 分层得到"],
  ["人工审查原始记录", qa.count_checks.human_review_30, "原始 scope 保留；不补判 reference 或最终正确性"],
  ["人工 in_scope / out_of_scope", `${qa.human_scope_counts.in_scope} / ${qa.human_scope_counts.out_of_scope}`, "scope 原文计数"],
  ["candidate remaining", qa.count_checks.remaining_candidate_136, "无记录层扣除人工30；不因旧审图重叠或资产警告过滤"],
  ["old image registry", qa.count_checks.old_registry_214, "历史 registry 分母，不是新研究准入名单"],
  ["旧42复算子集", qa.count_checks.dense42, "rq1 raw recompute 的 high_density_task_metrics 子集；不是全部高支持"],
  ["AI50候选审查", qa.count_checks.selected50, "从 remaining136 选出的 advisory-only 视觉审查集"],
];

const scopeRows = [
  ["层级/来源", "工作簿中的定位", "边界"],
  ["全量历史", "data_audit 核对 2501 canonical records / 214 images / 26 workers / 22 buildings", "不把旧排除人员/旧规则变成新准入条件"],
  ["各阶段×condition×image 支持", "首表列出 7 个 stage×condition 汇总行，另附已落盘支持性表", "仅呈现审计事实，不把支持曲线写成新准入结论"],
  ["旧42复算子集", "作为旧 high-density 复算/资产核对子集", "不是全部高支持，也不是新研究唯一可用数据"],
  ["AI50", "保留 advisory-only 场景描述、问题和 tags", "人工最终判断字段留空，AI 不转换为标签或准入结论"],
];

const packageGroups = new Map();
for (const row of catalog) {
  const key = row.package_id || "(empty)";
  const current = packageGroups.get(key) || { package_id: key, file_count: 0, existing_file_count: 0, format_error_count: 0, package_scope: row.package_scope, package_role: row.package_role, formats: new Set(), key_statuses: new Set() };
  current.file_count += 1;
  current.existing_file_count += row.file_exists === "true" ? 1 : 0;
  current.format_error_count += row.format_status === "error" ? 1 : 0;
  if (row.format) current.formats.add(row.format);
  if (row.key_status) current.key_statuses.add(row.key_status);
  packageGroups.set(key, current);
}
const packageRows = [
  ["package_id", "package_scope", "package_role", "file_count", "existing_file_count", "format_error_count", "formats", "key_statuses"],
  ...[...packageGroups.values()].sort((a, b) => a.package_id.localeCompare(b.package_id)).map((row) => [row.package_id, row.package_scope, row.package_role, row.file_count, row.existing_file_count, row.format_error_count, [...row.formats].sort().join(";"), [...row.key_statuses].sort().join(";")]),
];
const referenceGroups = new Map();
for (const row of references) {
  const key = `${row.existence_status || "(empty)"}||${row.consumer_package || "(empty)"}`;
  const current = referenceGroups.get(key) || {
    existence_status: row.existence_status || "(empty)",
    consumer_package: row.consumer_package || "(empty)",
    link_count: 0,
    consumer_files: new Set(),
    physical_paths: new Set(),
    reference_kinds: new Set(),
    sample_reference_text: row.reference_text || "",
  };
  current.link_count += 1;
  if (row.consumer_file) current.consumer_files.add(row.consumer_file);
  if (row.physical_reference_path) current.physical_paths.add(row.physical_reference_path);
  if (row.reference_kind) current.reference_kinds.add(row.reference_kind);
  referenceGroups.set(key, current);
}
const referenceSummaryRows = [
  ["existence_status", "consumer_package", "link_count", "consumer_file_count", "physical_reference_count", "reference_kinds", "sample_reference_text"],
  ...[...referenceGroups.values()].sort((a, b) => `${a.existence_status}|${a.consumer_package}`.localeCompare(`${b.existence_status}|${b.consumer_package}`)).map((row) => [
    row.existence_status,
    row.consumer_package,
    row.link_count,
    row.consumer_files.size,
    row.physical_paths.size,
    [...row.reference_kinds].sort().join(";"),
    row.sample_reference_text,
  ]),
];
const missingReferenceFields = ["consumer_package", "consumer_file", "consumer_context", "reference_text", "physical_reference_path", "resolved_path", "existence_status"];
const missingReferenceRows = selectRows(references.filter((row) => /missing/i.test(row.existence_status || "")), missingReferenceFields);
const referenceEntryRows = [
  ["文件", "相对路径", "说明"],
  ["完整引用明细 CSV", "inventory/reference_link_audit.csv", "完整 43,733 条引用；工作簿仅呈现 status/package 汇总及真实缺失项"],
];

const assetFields = ["image_id", "building_id", "history_layer", "pool", "review_id", "human_scope_raw", "human_prelabel_verdict_raw", "dense42", "old214_registry", "original_status", "gt_status", "hohonet_txt_status", "hohonet_json_status", "bi_manifest_status", "bi_extended_status", "bi_enclosed_status", "model_asset_issue_codes", "asset_overall_status", "image_path", "gt_path", "hohonet_txt_path", "hohonet_json_path"];
const humanRows = selectRows(assets.filter((row) => row.pool === "human_reviewed_30"), ["image_id", "building_id", "review_id", "human_scope_raw", "human_prelabel_verdict_raw", "human_notes_raw", "gt_status", "gt_source_type", "original_status", "hohonet_txt_status", "hohonet_json_status", "human_final_verdict", "reference_final_verdict"]);
const aiFields = [...(ai[0] ? Object.keys(ai[0]) : []), "human_final_verdict", "reference_final_verdict"];
const aiRows = selectRows(ai.map((row) => ({ ...row, human_final_verdict: "", reference_final_verdict: "" })), aiFields);

const workbook = Workbook.create();
const summarySheet = addSheet(workbook, "说明与分母", "研究数据审计与50张候选审查", "全量历史 / 各阶段条件支持 / 旧42复算子集 / AI50。旧规则、旧排除人员和20人资源限制均不作为新研究准入过滤。", [
  { title: "全历史总体分母（data_audit）", values: fullHistoricalRows },
  { title: "stage×condition 快速索引", values: stageConditionIndexRows },
  { title: "分母与池边界", values: countRows },
  { title: "数据角色", values: scopeRows },
  { title: "审计状态", values: [["字段", "值"], ["inventory QA", qa.status], ["格式检查", `${qa.format_checks.checked} checked / ${qa.format_checks.errors.length} errors`], ["room/region", qa.room_region_mapping.mapping_status], ["SHA", "按用户要求未运行"]] },
]);
summarySheet.getRangeByIndexes(0, 0, 100, 1).format.columnWidth = 36;
summarySheet.getRangeByIndexes(0, 1, 100, 1).format.columnWidth = 18;
summarySheet.getRangeByIndexes(0, 2, 100, 1).format.columnWidth = 90;
addSheet(workbook, "资产索引", "Prescreen 资产索引（314条）", "保留 machine manifest 分层、人工原文连接字段和原图/GT/HoHoNet/Bi 资产状态；不复制原始标注大表。", [{ values: selectRows(assets, assetFields) }]);
addSheet(workbook, "建筑覆盖", "建筑覆盖与资产缺口", "old214、旧42、machine314、历史148、人工30、remaining136 和资产状态按 building_id 汇总。", [{ values: selectRows(coverage, Object.keys(coverage[0] || {})) }]);
addSheet(workbook, "人工30原始", "人工30原始记录（不补判）", "scope、prelabel 和 notes 按原始 export 连接；最终人工判断与 reference 裁决列刻意留空。", [{ values: humanRows }]);
addSheet(workbook, "AI50建议", "AI50 视觉建议（advisory-only）", "AI 观察、问题和 tags 仅作人工复核提示；不作为 GT、room 标签、准入或正式错误结论。", [{ values: aiRows }]);
addSheet(workbook, "来源与差异", "来源目录与差异清单", "package catalog 与 reference link audit 以汇总呈现；完整引用明细保留为 CSV 路径入口，真实缺失项单列。", [
  { title: "package catalog 汇总", values: packageRows },
  { title: "模型资产摘要", values: selectRows(modelAssets, Object.keys(modelAssets[0] || {})) },
  { title: "reference status/package 汇总", values: referenceSummaryRows },
  { title: "真实未找到的历史临时引用", values: missingReferenceRows },
  { title: "完整明细入口", values: referenceEntryRows },
]);
addSheet(workbook, "room-region映射", "room/region 有界来源核查", "只接受明确结构化映射或官方 pano→数值 region class 行对齐；region class 不是 room-instance/空间拓扑 ID，不从视觉相似性推断。", [{ title: "覆盖汇总", values: selectRows(mappings, Object.keys(mappings[0] || {})) }, { title: "实际 image_id→region_class 连接（并集）", values: selectRows(mappingRecords, Object.keys(mappingRecords[0] || {})) }]);

if (dataAuditTables.length) {
  addSheet(workbook, "复算与曲线", "Sol data_audit：旧值复算与独立性曲线", "只读取明确列出的 5 张汇总表；排除 image/task ID 长 JSON 和逐图重采样明细。", dataAuditTables.map((table) => ({ title: table.title, values: table.values })));
}

await fs.mkdir(path.dirname(output), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(output);

for (const [index, sheet] of workbook.worksheets.items.entries()) {
  const values = sheet.getUsedRange().values;
  const range = `A1:${colName((values[0]?.length || 1) - 1)}${Math.min(values.length, sheet.name === "说明与分母" ? 42 : 28)}`;
  const preview = await workbook.render({ sheetName: sheet.name, range, scale: 0.75, format: "png" });
  await fs.writeFile(path.join(previewDir, `${String(index).padStart(2, "0")}_${sheet.name}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
const inspected = await reopened.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 1000 }, summary: "formula error scan" });
const sheetChecks = reopened.worksheets.items.map((sheet) => ({ name: sheet.name, rows: sheet.getUsedRange().values.length, columns: sheet.getUsedRange().values[0]?.length || 0 }));
await fs.writeFile(path.join(previewDir, "VALIDATION.json"), JSON.stringify({ status: "pass", output, bytes: (await fs.stat(output)).size, sheets: sheetChecks, formula_error_scan: inspected.ndjson, previewDir }, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ status: "ok", output, sheets: sheetChecks, previewDir }));
